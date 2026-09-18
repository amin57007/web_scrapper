from __future__ import annotations

import json

import httpx
import pytest

from ulscrape.errors import CaptchaError
from ulscrape.scraper.captcha_agent import _challenge_error, apply_decision
from ulscrape.scraper.vision import (
    CaptchaDecision,
    complete_vision,
    discover_llm,
    parse_decision,
    vision_prompt,
)


def test_discover_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("UL_LLM_MODEL", raising=False)
    monkeypatch.delenv("UL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cfg = discover_llm()
    assert cfg is not None
    assert cfg.provider == "openai"
    assert cfg.api_key == "sk-test"
    assert cfg.model == "gpt-4o"


def test_discover_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("UL_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    cfg = discover_llm()
    assert cfg is not None
    assert cfg.provider == "anthropic"


def test_discover_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "UL_LLM_API_KEY",
        "LLM_API_KEY",
        "UL_LLM_PROVIDER",
        "UL_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    assert discover_llm() is None


def test_parse_decision_from_markdown() -> None:
    text = """```json
    {"tiles": [0, 4, 8], "done": true, "reason": "buses"}
    ```"""
    decision = parse_decision(text)
    assert decision.tiles == [0, 4, 8]
    assert decision.done is True


def test_vision_prompt_numbers_grid() -> None:
    prompt = vision_prompt("Select all squares with buses", 3, 3)
    assert "0 through 8" in prompt
    assert "buses" in prompt


def test_complete_vision_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content.decode())
        assert body["model"] == "gpt-4o"
        assert body["max_tokens"] == 512
        assert body["response_format"]["type"] == "json_object"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"tiles":[1,2],"done":false}'}}]},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        kwargs.pop("timeout", None)
        return real_client(*args, timeout=5.0, **kwargs)

    monkeypatch.setattr("ulscrape.scraper.vision.httpx.Client", fake_client)
    cfg = discover_llm(api_key="sk", provider="openai", model="gpt-4o")
    assert cfg is not None
    decision = complete_vision(cfg, "prompt", b"\x89PNG")
    assert decision.tiles == [1, 2]
    assert decision.done is False


def test_complete_vision_rejects_null_content(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": None, "refusal": "nope"}}]},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        kwargs.pop("timeout", None)
        return real_client(*args, timeout=5.0, **kwargs)

    monkeypatch.setattr("ulscrape.scraper.vision.httpx.Client", fake_client)
    cfg = discover_llm(api_key="sk", provider="openai", model="gpt-4o")
    assert cfg is not None

    with pytest.raises(CaptchaError, match="refused"):
        complete_vision(cfg, "prompt", b"\x89PNG")


def test_apply_decision_clicks_and_verify() -> None:
    clicks: list[int] = []
    verified = {"n": 0}

    class FakeLocator:
        def __init__(self, kind: str) -> None:
            self.kind = kind

        def nth(self, index: int) -> FakeLocator:
            clicks.append(index)
            return self

        def click(self) -> None:
            if self.kind == "verify":
                verified["n"] += 1

        def count(self) -> int:
            return 1

        @property
        def first(self) -> FakeLocator:
            return self

    class FakeFrame:
        def locator(self, selector: str) -> FakeLocator:
            if "verify" in selector or "rc-button-default" in selector:
                return FakeLocator("verify")
            return FakeLocator("tile")

        def wait_for_timeout(self, _ms: int) -> None:
            return None

    apply_decision(
        FakeFrame(),
        CaptchaDecision(tiles=[0, 2, 2, 99], done=True),
        tile_count=9,
    )
    assert clicks == [0, 2]
    assert verified["n"] == 1


def test_challenge_error_visible() -> None:
    class Node:
        def count(self) -> int:
            return 1

        @property
        def first(self) -> Node:
            return self

        def is_visible(self) -> bool:
            return True

    class Frame:
        def locator(self, _selector: str) -> Node:
            return Node()

    assert _challenge_error(Frame()) is True


def test_challenge_error_missing() -> None:
    class Node:
        def count(self) -> int:
            return 0

    class Frame:
        def locator(self, _selector: str) -> Node:
            return Node()

    assert _challenge_error(Frame()) is False

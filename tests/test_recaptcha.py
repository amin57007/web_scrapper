from __future__ import annotations

import json

import httpx
import pytest

from ulscrape.errors import CaptchaError
from ulscrape.scraper.recaptcha import (
    INJECT_TOKEN_JS,
    extract_sitekey,
    sitekey_from_iframe_url,
    solve_recaptcha_v2,
)


def test_extract_sitekey_from_widget() -> None:
    html = '<div class="g-recaptcha" data-sitekey="6LeTestSiteKeyValueXXXXXX"></div>'
    assert extract_sitekey(html) == "6LeTestSiteKeyValueXXXXXX"


def test_extract_sitekey_from_iframe() -> None:
    html = (
        '<iframe src="https://www.google.com/recaptcha/api2/anchor?'
        'k=6LeIframeSiteKeyValueYYYYYY&hl=en"></iframe>'
    )
    assert extract_sitekey(html) == "6LeIframeSiteKeyValueYYYYYY"


def test_sitekey_from_iframe_url() -> None:
    src = "https://www.google.com/recaptcha/api2/anchor?k=6LeAbcdefghijklmnopqrstuv&hl=en"
    assert sitekey_from_iframe_url(src) == "6LeAbcdefghijklmnopqrstuv"


def test_inject_token_js_mentions_callbacks() -> None:
    assert "g-recaptcha-response" in INJECT_TOKEN_JS
    assert "captchaValid" in INJECT_TOKEN_JS
    assert "ValidateCaptcha" in INJECT_TOKEN_JS


def test_solve_2captcha_polls_until_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/in.php"):
            return httpx.Response(200, json={"status": 1, "request": "task-9"})
        if request.url.path.endswith("/res.php"):
            if calls.count("GET /res.php") < 2:
                return httpx.Response(200, json={"status": 0, "request": "CAPCHA_NOT_READY"})
            return httpx.Response(200, json={"status": 1, "request": "03AGdBq2token"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        kwargs.pop("timeout", None)
        return real_client(*args, timeout=5.0, **kwargs)

    monkeypatch.setattr("ulscrape.scraper.recaptcha.httpx.Client", fake_client)
    monkeypatch.setattr("ulscrape.scraper.recaptcha.time.sleep", lambda _s: None)
    token = solve_recaptcha_v2(
        sitekey="6LeTestSiteKeyValueXXXXXX",
        page_url="https://app.ultralibrarian.com/details/x",
        api_key="key",
        provider="2captcha",
    )
    assert token == "03AGdBq2token"


def test_solve_2captcha_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": 0, "request": "ERROR_WRONG_USER_KEY"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        kwargs.pop("timeout", None)
        return real_client(*args, timeout=5.0, **kwargs)

    monkeypatch.setattr("ulscrape.scraper.recaptcha.httpx.Client", fake_client)
    with pytest.raises(CaptchaError, match="ERROR_WRONG_USER_KEY"):
        solve_recaptcha_v2(
            sitekey="6LeTestSiteKeyValueXXXXXX",
            page_url="https://example.com",
            api_key="bad",
        )


def test_capsolver_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/createTask"):
            return httpx.Response(200, json={"errorId": 0, "taskId": "t1"})
        body = json.loads(request.content.decode())
        assert body["taskId"] == "t1"
        return httpx.Response(
            200,
            json={"errorId": 0, "status": "ready", "solution": {"gRecaptchaResponse": "tok"}},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        kwargs.pop("timeout", None)
        return real_client(*args, timeout=5.0, **kwargs)

    monkeypatch.setattr("ulscrape.scraper.recaptcha.httpx.Client", fake_client)
    monkeypatch.setattr("ulscrape.scraper.recaptcha.time.sleep", lambda _s: None)
    token = solve_recaptcha_v2(
        sitekey="6LeTestSiteKeyValueXXXXXX",
        page_url="https://app.ultralibrarian.com/details/x",
        api_key="key",
        provider="capsolver",
    )
    assert token == "tok"

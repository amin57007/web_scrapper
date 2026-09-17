"""Vision-LLM client used by the reCAPTCHA agent (OpenAI, Anthropic, Gemini, OpenRouter)."""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field

from ulscrape.errors import CaptchaError

DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.0-flash",
    "openrouter": "openai/gpt-4o",
}


class CaptchaDecision(BaseModel):
    """One observe/act step for a reCAPTCHA image grid."""

    tiles: list[int] = Field(default_factory=list)
    done: bool = False
    reason: str = ""


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    api_key: str
    model: str
    base_url: str | None = None


def discover_llm(
    *,
    api_key: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LlmConfig | None:
    """Pick a vision-capable LLM from explicit args or environment variables."""
    key = (
        api_key
        or os.environ.get("UL_LLM_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or None
    )
    if not key:
        return None

    resolved_provider = (provider or os.environ.get("UL_LLM_PROVIDER") or "").strip().lower()
    if not resolved_provider:
        if key == os.environ.get("ANTHROPIC_API_KEY"):
            resolved_provider = "anthropic"
        elif key == os.environ.get("OPENROUTER_API_KEY"):
            resolved_provider = "openrouter"
        elif key == os.environ.get("OPENAI_API_KEY"):
            resolved_provider = "openai"
        elif key in {os.environ.get("GEMINI_API_KEY"), os.environ.get("GOOGLE_API_KEY")}:
            resolved_provider = "gemini"
        else:
            resolved_provider = "openai"

    resolved_model = (
        model
        or os.environ.get("UL_LLM_MODEL")
        or DEFAULT_MODELS.get(resolved_provider, "gpt-4o")
    )
    resolved_base = base_url or os.environ.get("OPENAI_BASE_URL") or os.environ.get("UL_LLM_BASE_URL")
    if resolved_provider == "openrouter":
        resolved_base = resolved_base or "https://openrouter.ai/api/v1"
    return LlmConfig(
        provider=resolved_provider,
        api_key=key,
        model=resolved_model,
        base_url=resolved_base,
    )


def parse_decision(text: str) -> CaptchaDecision:
    """Parse a JSON object out of a model reply (markdown fences allowed)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise CaptchaError(f"vision model did not return JSON: {text[:200]!r}")
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise CaptchaError(f"vision model JSON was invalid: {exc}") from exc
    tiles_raw = payload.get("tiles") or []
    tiles: list[int] = []
    for item in tiles_raw:
        try:
            tiles.append(int(item))
        except (TypeError, ValueError):
            continue
    return CaptchaDecision(
        tiles=tiles,
        done=bool(payload.get("done", False)),
        reason=str(payload.get("reason") or ""),
    )


def vision_prompt(instruction: str, rows: int, cols: int) -> str:
    n = rows * cols
    return (
        "You are helping a user complete a Google reCAPTCHA image challenge on a "
        "website they are signed into, so they can download CAD files they are "
        "allowed to use.\n"
        f"The screenshot is a {rows}x{cols} grid of tiles numbered 0 through {n - 1}, "
        "left-to-right, then top-to-bottom. Tile 0 is the top-left cell.\n"
        f"Challenge instruction:\n{instruction.strip() or '(see the screenshot)'}\n"
        "Select every tile that matches the instruction. If none match, return an "
        "empty list and set done=true so Verify can be clicked.\n"
        'Reply with JSON only, no markdown: {"tiles": [0, 2], "done": false, "reason": "..."}\n'
        "done=true means click Verify after applying tiles (including when tiles is empty)."
    )


def complete_vision(cfg: LlmConfig, prompt: str, png: bytes) -> CaptchaDecision:
    """Send one screenshot to the configured vision model and parse a decision."""
    image_b64 = base64.b64encode(png).decode("ascii")
    if cfg.provider in {"openai", "openrouter"}:
        text = _openai_vision(cfg, prompt, image_b64)
    elif cfg.provider == "anthropic":
        text = _anthropic_vision(cfg, prompt, image_b64)
    elif cfg.provider == "gemini":
        text = _gemini_vision(cfg, prompt, image_b64)
    else:
        raise CaptchaError(f"unsupported LLM provider: {cfg.provider}")
    return parse_decision(text)


def _openai_message_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise CaptchaError("OpenAI-compatible vision response missing content")
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise CaptchaError("OpenAI-compatible vision response missing content") from exc
    if not isinstance(message, dict):
        raise CaptchaError("OpenAI-compatible vision response missing content")
    content = message.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        content = "".join(parts)
    if isinstance(content, str) and content.strip() and content.strip() != "None":
        return content
    refusal = message.get("refusal")
    if refusal:
        raise CaptchaError(f"vision model refused: {refusal}")
    raise CaptchaError("OpenAI-compatible vision response missing content")


def _openai_vision(cfg: LlmConfig, prompt: str, image_b64: str) -> str:
    root = (cfg.base_url or "https://api.openai.com/v1").rstrip("/")
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    if cfg.provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/amin57007/web_scrapper"
        headers["X-Title"] = "ulscrape"
    body: dict[str, object] = {
        "model": cfg.model,
        "temperature": 0,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ],
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(f"{root}/chat/completions", headers=headers, json=body)
        if response.status_code == 400 and "max_tokens" in response.text:
            body.pop("max_tokens", None)
            body["max_completion_tokens"] = 512
            response = client.post(f"{root}/chat/completions", headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
    return _openai_message_text(payload)


def _anthropic_vision(cfg: LlmConfig, prompt: str, image_b64: str) -> str:
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": cfg.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": cfg.model,
                "max_tokens": 512,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
    try:
        return str(payload["content"][0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        raise CaptchaError("Anthropic vision response missing text") from exc


def _gemini_vision(cfg: LlmConfig, prompt: str, image_b64: str) -> str:
    model = cfg.model
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            url,
            params={"key": cfg.api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": image_b64,
                                }
                            },
                        ]
                    }
                ]
            },
        )
        response.raise_for_status()
        payload = response.json()
    try:
        return str(payload["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        raise CaptchaError("Gemini vision response missing text") from exc

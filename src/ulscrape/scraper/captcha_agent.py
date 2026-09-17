"""Agentic reCAPTCHA v2 solver: screenshot → vision LLM → click tiles → repeat."""

from __future__ import annotations

import logging
from typing import Any, Protocol, cast

from ulscrape.config import Settings
from ulscrape.errors import CaptchaError
from ulscrape.scraper.vision import (
    CaptchaDecision,
    LlmConfig,
    complete_vision,
    discover_llm,
    vision_prompt,
)

_log = logging.getLogger(__name__)

MAX_ROUNDS = 8


class SupportsEvaluate(Protocol):
    def evaluate(self, expression: str) -> Any: ...
    def locator(self, selector: str) -> Any: ...
    def wait_for_timeout(self, timeout: int) -> None: ...


def run_captcha_agent(
    page: Any,
    settings: Settings,
    *,
    llm: LlmConfig | None = None,
    max_rounds: int = MAX_ROUNDS,
) -> bool:
    """Solve a visible reCAPTCHA image challenge with a vision LLM.

    Returns True when grecaptcha produced a token. Raises CaptchaError if the
    agent cannot act (no key, no challenge, or too many failed rounds).
    """
    cfg = llm or discover_llm(
        api_key=settings.llm_api_key,
        provider=settings.llm_provider,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )
    if cfg is None:
        raise CaptchaError(
            "reCAPTCHA image challenge needs a vision LLM. Set OPENAI_API_KEY, "
            "ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY."
        )

    frame = _challenge_frame(page)
    if frame is None:
        return False

    _log.info("captcha agent using %s model %s", cfg.provider, cfg.model)
    for round_idx in range(1, max_rounds + 1):
        if _token_present(page):
            return True
        frame = _challenge_frame(page) or frame
        meta = _challenge_meta(frame)
        if meta is None:
            page.wait_for_timeout(1000)
            if _token_present(page):
                return True
            continue
        png = _screenshot_challenge(frame)
        prompt = vision_prompt(meta["instruction"], meta["rows"], meta["cols"])
        _log.info("captcha round %s/%s instruction=%r", round_idx, max_rounds, meta["instruction"][:80])
        decision = complete_vision(cfg, prompt, png)
        apply_decision(frame, decision, tile_count=meta["count"])
        page.wait_for_timeout(1200)
        if _token_present(page):
            return True
        if _challenge_error(frame):
            _log.info("captcha said try again; continuing")
            continue
    if _token_present(page):
        return True
    raise CaptchaError(f"vision captcha agent did not finish in {max_rounds} rounds")


def apply_decision(frame: Any, decision: CaptchaDecision, *, tile_count: int) -> None:
    """Click selected tiles, then Verify when the model says the grid is done."""
    tiles = frame.locator(".rc-imageselect-tile")
    seen: set[int] = set()
    for index in decision.tiles:
        if index in seen or index < 0 or index >= tile_count:
            continue
        seen.add(index)
        tiles.nth(index).click()
        frame.wait_for_timeout(250)
    if decision.done or not decision.tiles:
        verify = frame.locator("#recaptcha-verify-button, .rc-button-default")
        if verify.count():
            verify.first.click()


def _challenge_frame(page: Any) -> Any | None:
    for frame in page.frames:
        url = frame.url or ""
        if "recaptcha" not in url:
            continue
        try:
            if frame.locator(".rc-imageselect-tile, #rc-imageselect").count():
                return frame
        except Exception:
            continue
    return None


def _challenge_meta(frame: Any) -> dict[str, Any] | None:
    try:
        meta = frame.evaluate(
            """() => {
                const tiles = document.querySelectorAll(".rc-imageselect-tile");
                if (!tiles.length) return null;
                const desc = document.querySelector(
                    ".rc-imageselect-desc-wrapper, .rc-imageselect-desc, .rc-imageselect-instructions"
                );
                const four = !!document.querySelector(".rc-imageselect-table-44");
                const cols = four ? 4 : 3;
                return {
                    instruction: desc ? desc.innerText : "",
                    count: tiles.length,
                    cols: cols,
                    rows: Math.round(tiles.length / cols)
                };
            }"""
        )
    except Exception:
        return None
    if not isinstance(meta, dict) or not meta.get("count"):
        return None
    return cast(dict[str, Any], meta)


def _screenshot_challenge(frame: Any) -> bytes:
    target = frame.locator("#rc-imageselect, .rc-imageselect-challenge, body").first
    return bytes(target.screenshot(type="png"))


def _challenge_error(frame: Any) -> bool:
    try:
        text = frame.locator(".rc-imageselect-error-select-more, .rc-imageselect-incorrect-response")
        if text.count() == 0:
            return False
        return True if text.first.is_visible() else False
    except Exception:
        return False


def _token_present(page: Any) -> bool:
    try:
        return bool(
            page.evaluate(
                """() => {
                    if (window.grecaptcha && typeof grecaptcha.getResponse === "function") {
                        try { if (grecaptcha.getResponse()) return true; } catch (e) {}
                    }
                    const el = document.querySelector("[name='g-recaptcha-response']");
                    return !!(el && el.value && el.value.length > 20);
                }"""
            )
        )
    except Exception:
        return False

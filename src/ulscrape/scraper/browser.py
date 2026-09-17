"""Playwright login + CAD export, including the Google reCAPTCHA on the download form."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ulscrape.config import Settings
from ulscrape.errors import AuthError, CaptchaError, ExportError
from ulscrape.models import PartDetails
from ulscrape.scraper.captcha_agent import run_captcha_agent
from ulscrape.scraper.details import parse_details_html
from ulscrape.scraper.recaptcha import (
    INJECT_TOKEN_JS,
    extract_sitekey,
    sitekey_from_iframe_url,
    solve_recaptcha_v2,
)
from ulscrape.scraper.urls import details_url, parse_part_url
from ulscrape.scraper.vision import discover_llm

KICAD_V6_SELECTOR = "#KiCADv6"
STEP_SELECTOR = "#MfrThreeDModel"
DOWNLOAD_BTN = "#export-selection-btn"
SUBMIT_EXPORT = "#submit-export"
LOGIN_GATE = "a.login-return-url"


def download_with_browser(
    url: str,
    dest_zip: Path,
    settings: Settings,
    export_ids: Sequence[int] | None = None,
) -> tuple[Path, PartDetails]:
    """Log in with a real Chrome session, pass reCAPTCHA, download KiCad+STEP."""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ExportError(
            "Playwright is required for captcha-aware downloads. "
            "Install with: pip install playwright && playwright install chrome"
        ) from exc

    ref = parse_part_url(url, base_url=settings.base_url)
    part_url = details_url(ref, base_url=settings.base_url)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright, headed=settings.headed)
        context_kwargs: dict[str, Any] = {
            "user_agent": settings.user_agent,
            "viewport": {"width": 1440, "height": 960},
            "accept_downloads": True,
            "locale": "en-US",
        }
        if settings.storage_state_path and settings.storage_state_path.exists():
            context_kwargs["storage_state"] = str(settings.storage_state_path)
        context = browser.new_context(**context_kwargs)
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = context.new_page()
        page.set_default_timeout(int(settings.poll_timeout_s * 1000))
        try:
            page.goto(part_url, wait_until="domcontentloaded")
            html = page.content()
            details = parse_details_html(html, page_url=page.url)
            if page.locator(LOGIN_GATE).count() > 0 or "Login to Download" in html:
                _login(page, settings)
                page.goto(part_url, wait_until="domcontentloaded")
                html = page.content()
                details = parse_details_html(html, page_url=page.url)
            if page.locator(LOGIN_GATE).count() > 0:
                raise AuthError(
                    "still on the login gate after submitting credentials. "
                    "Check UL_EMAIL / UL_PASSWORD."
                )

            _open_export_panel(page)
            _select_kicad_and_step(page, details, export_ids)
            _accept_required_consents(page)
            _solve_export_captcha(page, settings)
            zip_path = _submit_and_download(page, dest_zip, settings)
            _save_storage(context, settings)
            return zip_path, details
        except PlaywrightTimeout as exc:
            raise ExportError(f"timed out driving the Ultra Librarian UI: {exc}") from exc
        finally:
            context.close()
            browser.close()


def _launch_browser(playwright: Any, *, headed: bool) -> Any:
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]
    try:
        return playwright.chromium.launch(
            channel="chrome",
            headless=not headed,
            args=args,
        )
    except Exception:
        return playwright.chromium.launch(headless=not headed, args=args)


def _login(page: Any, settings: Settings) -> None:
    if not settings.email or not settings.password:
        raise AuthError(
            "Ultra Librarian login is required. Pass --email/--password or "
            "UL_EMAIL / UL_PASSWORD."
        )
    if "login" not in page.url.lower():
        page.locator(LOGIN_GATE).first.click()
        page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector("#Username")
    page.fill("#Username", settings.email)
    page.fill("#Password", settings.password)
    remember = page.locator("#RememberLogin")
    if remember.count():
        remember.check()
    page.locator("button[value='login'], button:has-text('Login')").first.click()
    page.wait_for_load_state("domcontentloaded")
    # OIDC form_post callback: auto-submit if a hidden id_token form appears.
    if page.locator("input[name='id_token'], input[name='code']").count():
        form = page.locator("form").first
        form.evaluate("form => form.submit()")
        page.wait_for_load_state("domcontentloaded")
    if page.locator("#Password").count() and "login" in page.url.lower():
        raise AuthError("Ultra Librarian rejected the login (wrong password or extra challenge).")


def _open_export_panel(page: Any) -> None:
    btn = page.locator(DOWNLOAD_BTN)
    btn.wait_for(state="visible")
    btn.click()
    page.wait_for_selector("#export-selection-parent")
    # Bootstrap collapse: wait until the panel is actually shown.
    page.wait_for_timeout(500)


def _select_kicad_and_step(
    page: Any,
    details: PartDetails,
    export_ids: Sequence[int] | None,
) -> None:
    wanted = set(export_ids or [])
    if not wanted:
        kicad = details.kicad_v6() or details.kicad_v5()
        step = details.step_format()
        if kicad:
            wanted.add(kicad.export_id)
        if step:
            wanted.add(step.export_id)
        if not wanted:
            wanted.update({42, 37})

    for export_id in wanted:
        box = page.locator(f'input.export-option[name="exports"][value="{export_id}"]')
        if box.count():
            box.check(force=True)

    # Prefer the documented KiCad v6 + STEP widgets even if details parsing lagged.
    if page.locator(KICAD_V6_SELECTOR).count():
        page.locator(KICAD_V6_SELECTOR).check(force=True)
    elif page.locator("#KiCAD").count():
        page.locator("#KiCAD").check(force=True)
    if page.locator(STEP_SELECTOR).count():
        page.locator(STEP_SELECTOR).check(force=True)


def _accept_required_consents(page: Any) -> None:
    boxes = page.locator(".consentRequest.required, .mfr-export-consent-item.required")
    count = boxes.count()
    for i in range(count):
        boxes.nth(i).check(force=True)


def _solve_export_captcha(page: Any, settings: Settings) -> None:
    widget = page.locator(".g-recaptcha, iframe[src*='recaptcha']")
    if widget.count() == 0:
        return

    if _recaptcha_already_solved(page):
        return

    clicked = _click_recaptcha_checkbox(page)
    if clicked and _wait_for_recaptcha_token(page, timeout_ms=8000):
        page.evaluate("() => { if (typeof captchaValid === 'function') captchaValid(); }")
        return

    page.wait_for_timeout(1500)
    if _wait_for_recaptcha_token(page, timeout_ms=3000):
        page.evaluate("() => { if (typeof captchaValid === 'function') captchaValid(); }")
        return

    llm = discover_llm(
        api_key=settings.llm_api_key,
        provider=settings.llm_provider,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )
    if llm is not None:
        try:
            if run_captcha_agent(page, settings, llm=llm):
                page.evaluate("() => { if (typeof captchaValid === 'function') captchaValid(); }")
                return
        except CaptchaError:
            if not settings.captcha_api_key:
                raise

    sitekey = _page_sitekey(page)
    if not sitekey:
        html = page.content()
        sitekey = extract_sitekey(html)
    if settings.captcha_api_key and sitekey:
        token = solve_recaptcha_v2(
            sitekey=sitekey,
            page_url=page.url,
            api_key=settings.captcha_api_key,
            provider=settings.captcha_provider,
            timeout_s=settings.poll_timeout_s,
        )
        page.evaluate(INJECT_TOKEN_JS, token)
        return

    if not sitekey:
        raise CaptchaError(
            "export form shows Google reCAPTCHA but no sitekey was found"
        )
    raise CaptchaError(
        "Google reCAPTCHA image challenge was not solved. Set a vision LLM key "
        "(OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY) "
        "or TWOCAPTCHA_API_KEY / CAPSOLVER_API_KEY."
    )


def _page_sitekey(page: Any) -> str | None:
    key = page.evaluate(
        """() => {
            const el = document.querySelector(".g-recaptcha[data-sitekey]");
            if (el) return el.getAttribute("data-sitekey");
            const iframe = document.querySelector("iframe[src*='recaptcha']");
            return iframe ? iframe.src : null;
        }"""
    )
    if not key:
        return None
    if len(str(key)) > 20 and "http" not in str(key):
        return str(key)
    return sitekey_from_iframe_url(str(key))


def _click_recaptcha_checkbox(page: Any) -> bool:
    frames = [
        frame
        for frame in page.frames
        if "recaptcha" in (frame.url or "") and "bframe" not in (frame.url or "")
    ]
    if not frames:
        locator = page.frame_locator("iframe[src*='recaptcha']").first
        try:
            locator.locator("#recaptcha-anchor, .recaptcha-checkbox-border").click(
                timeout=8000
            )
            return True
        except Exception:
            return False
    try:
        frames[0].locator("#recaptcha-anchor, .recaptcha-checkbox-border").click(
            timeout=8000
        )
        return True
    except Exception:
        return False


def _wait_for_recaptcha_token(page: Any, timeout_ms: int) -> bool:
    try:
        page.wait_for_function(
            """() => {
                if (window.grecaptcha && typeof grecaptcha.getResponse === "function") {
                    try { if (grecaptcha.getResponse()) return true; } catch (e) {}
                }
                const el = document.querySelector("[name='g-recaptcha-response']");
                return !!(el && el.value && el.value.length > 20);
            }""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


def _recaptcha_already_solved(page: Any) -> bool:
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


def _submit_and_download(page: Any, dest_zip: Path, settings: Settings) -> Path:
    submit = page.locator(SUBMIT_EXPORT)
    if submit.count() == 0:
        raise ExportError("export submit button was not on the page after login")
    try:
        submit.wait_for(state="visible", timeout=15000)
    except Exception as exc:
        raise CaptchaError(
            "Download submit stayed hidden. reCAPTCHA or required consents are not complete."
        ) from exc
    page.evaluate(
        """() => {
            const btn = document.querySelector("#submit-export");
            if (btn) { btn.classList.remove("disabled"); btn.disabled = false; }
        }"""
    )
    with page.expect_download(timeout=int(settings.poll_timeout_s * 1000)) as download_info:
        submit.click(force=True)
    download = download_info.value
    download.save_as(str(dest_zip))
    if not dest_zip.exists() or dest_zip.stat().st_size < 64:
        raise ExportError("browser download finished but the zip is empty")
    return dest_zip


def _save_storage(context: Any, settings: Settings) -> None:
    path = settings.storage_state_path
    if path is None:
        path = settings.output_dir / ".ul-storage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(path))

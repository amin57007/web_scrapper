"""Google reCAPTCHA v2 helpers used by the Ultra Librarian export form."""

from __future__ import annotations

import re
import time
from urllib.parse import parse_qs, urlparse

import httpx

from ulscrape.errors import CaptchaError

_SITEKEY_RE = re.compile(
    r"data-sitekey\s*=\s*[\"']([A-Za-z0-9_-]{20,})[\"']",
    re.IGNORECASE,
)
_IFRAME_K_RE = re.compile(r"[?&]k=([A-Za-z0-9_-]{20,})")

INJECT_TOKEN_JS = """
(token) => {
    const nodes = document.querySelectorAll(
        "textarea[name='g-recaptcha-response'], [name='g-recaptcha-response']"
    );
    nodes.forEach((el) => {
        el.value = token;
        el.innerHTML = token;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
    });
    if (nodes.length === 0) {
        const ta = document.createElement("textarea");
        ta.name = "g-recaptcha-response";
        ta.id = "g-recaptcha-response";
        ta.style.display = "none";
        ta.value = token;
        const form = document.getElementById("export-submission-form") || document.body;
        form.appendChild(ta);
    }
    if (typeof captchaValid === "function") {
        captchaValid();
    }
    if (window.ultralibrarian
        && window.ultralibrarian.exportvalidation
        && typeof window.ultralibrarian.exportvalidation.ValidateCaptcha === "function") {
        window.ultralibrarian.exportvalidation.ValidateCaptcha(token);
    }
    return true;
}
"""


def extract_sitekey(html: str) -> str | None:
    """Return the reCAPTCHA sitekey from page HTML or iframe URL."""
    match = _SITEKEY_RE.search(html)
    if match:
        return match.group(1)
    iframe = _IFRAME_K_RE.search(html)
    if iframe:
        return iframe.group(1)
    return None


def sitekey_from_iframe_url(src: str) -> str | None:
    """Parse `k=` from a recaptcha iframe src."""
    parsed = urlparse(src)
    keys = parse_qs(parsed.query).get("k") or []
    if keys:
        return keys[0]
    match = _IFRAME_K_RE.search(src)
    return match.group(1) if match else None


def solve_recaptcha_v2(
    *,
    sitekey: str,
    page_url: str,
    api_key: str,
    provider: str = "2captcha",
    timeout_s: float = 180.0,
) -> str:
    """Solve reCAPTCHA v2 through 2Captcha or CapSolver (human-solving APIs)."""
    provider = provider.lower().strip()
    if provider == "capsolver":
        return _solve_capsolver(sitekey, page_url, api_key, timeout_s)
    return _solve_2captcha(sitekey, page_url, api_key, timeout_s)


def _solve_2captcha(sitekey: str, page_url: str, api_key: str, timeout_s: float) -> str:
    with httpx.Client(timeout=30.0) as client:
        submitted = client.post(
            "https://2captcha.com/in.php",
            data={
                "key": api_key,
                "method": "userrecaptcha",
                "googlekey": sitekey,
                "pageurl": page_url,
                "json": "1",
            },
        )
        submitted.raise_for_status()
        payload = submitted.json()
        if payload.get("status") != 1:
            raise CaptchaError(f"2Captcha rejected the task: {payload.get('request')}")
        task_id = payload["request"]
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            time.sleep(5)
            poll = client.get(
                "https://2captcha.com/res.php",
                params={"key": api_key, "action": "get", "id": task_id, "json": "1"},
            )
            poll.raise_for_status()
            result = poll.json()
            if result.get("status") == 1:
                token = str(result.get("request") or "")
                if not token:
                    raise CaptchaError("2Captcha returned an empty token")
                return token
            if result.get("request") not in {"CAPCHA_NOT_READY", "CAPTCHA_NOT_READY"}:
                raise CaptchaError(f"2Captcha failed: {result.get('request')}")
    raise CaptchaError(f"2Captcha timed out after {timeout_s:.0f}s")


def _solve_capsolver(sitekey: str, page_url: str, api_key: str, timeout_s: float) -> str:
    with httpx.Client(timeout=30.0) as client:
        created = client.post(
            "https://api.capsolver.com/createTask",
            json={
                "clientKey": api_key,
                "task": {
                    "type": "ReCaptchaV2TaskProxyLess",
                    "websiteURL": page_url,
                    "websiteKey": sitekey,
                },
            },
        )
        created.raise_for_status()
        payload = created.json()
        if payload.get("errorId"):
            raise CaptchaError(f"CapSolver createTask failed: {payload.get('errorDescription')}")
        task_id = payload.get("taskId")
        if not task_id:
            raise CaptchaError("CapSolver did not return a taskId")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            time.sleep(3)
            poll = client.post(
                "https://api.capsolver.com/getTaskResult",
                json={"clientKey": api_key, "taskId": task_id},
            )
            poll.raise_for_status()
            result = poll.json()
            if result.get("errorId"):
                raise CaptchaError(f"CapSolver failed: {result.get('errorDescription')}")
            if result.get("status") == "ready":
                token = (result.get("solution") or {}).get("gRecaptchaResponse")
                if not token:
                    raise CaptchaError("CapSolver returned no gRecaptchaResponse")
                return str(token)
    raise CaptchaError(f"CapSolver timed out after {timeout_s:.0f}s")

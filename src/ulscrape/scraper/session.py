"""HTTP session, cookie jar, and Ultra Librarian login."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from ulscrape.config import Settings
from ulscrape.errors import AuthError


def build_client(settings: Settings) -> httpx.Client:
    """Create a cookie-aware HTTP client with a browser-like user agent."""
    client = httpx.Client(
        base_url=settings.base_url,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        follow_redirects=True,
        timeout=settings.timeout_s,
    )
    if settings.cookies_path and settings.cookies_path.exists():
        load_cookies(client, settings.cookies_path)
    return client


def load_cookies(client: httpx.Client, path: Path) -> None:
    """Load cookies from JSON `{name: value}` or a Netscape cookie file."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return
    if text.startswith("{") or text.startswith("["):
        payload = json.loads(text)
        if isinstance(payload, dict):
            for name, value in payload.items():
                client.cookies.set(str(name), str(value), domain="ultralibrarian.com")
        elif isinstance(payload, list):
            for item in payload:
                if not isinstance(item, Mapping):
                    continue
                client.cookies.set(
                    str(item.get("name")),
                    str(item.get("value")),
                    domain=str(item.get("domain") or "ultralibrarian.com"),
                    path=str(item.get("path") or "/"),
                )
        return
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, cookie_path, _secure, _expires, name, value = parts[:7]
        client.cookies.set(name, value, domain=domain.lstrip("."), path=cookie_path)


def save_cookies(client: httpx.Client, path: Path) -> None:
    """Write cookies as a simple JSON object for later sessions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dumped = {cookie.name: cookie.value for cookie in client.cookies.jar}
    path.write_text(json.dumps(dumped, indent=2) + "\n", encoding="utf-8")


def login(client: httpx.Client, email: str, password: str) -> None:
    """Sign in with an Ultra Librarian account using the public login form.

    Ultra Librarian uses IdentityServer with an OIDC form_post callback.
    This submits the username/password form and any follow-up auto-post
    forms. A captcha or MFA challenge is reported as AuthError.
    """
    if not email or not password:
        raise AuthError("UL_EMAIL and UL_PASSWORD are required for CAD download")

    login_page = client.get("/Account/Login")
    login_page.raise_for_status()
    soup = BeautifulSoup(login_page.text, "lxml")
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise AuthError("login page had no form")

    payload = _form_fields(form)
    payload["Username"] = email
    payload["Password"] = password
    payload["button"] = "login"
    action = str(form.get("action") or login_page.url)
    response = client.post(urljoin(str(login_page.url), action), data=payload)
    response.raise_for_status()

    response = _follow_auto_post_forms(client, response, hops=4)

    if _looks_like_login_page(response.text):
        raise AuthError(
            "login was rejected. Check UL_EMAIL / UL_PASSWORD, or export "
            "browser cookies to UL_COOKIES after signing in at app.ultralibrarian.com"
        )


def is_authenticated(html: str) -> bool:
    """True when a details page is not showing the anonymous download gate."""
    return "Login to Download" not in html and "login-return-url" not in html


def _form_fields(form: Tag) -> dict[str, str]:
    data: dict[str, str] = {}
    for inp in form.find_all("input"):
        if not isinstance(inp, Tag):
            continue
        name = inp.get("name")
        if not name:
            continue
        itype = str(inp.get("type") or "text").lower()
        if itype in {"submit", "button", "image"}:
            continue
        data[str(name)] = str(inp.get("value") or "")
    return data


def _follow_auto_post_forms(
    client: httpx.Client, response: httpx.Response, hops: int
) -> httpx.Response:
    current = response
    for _ in range(hops):
        soup = BeautifulSoup(current.text, "lxml")
        form = soup.find("form")
        if not isinstance(form, Tag):
            return current
        # OIDC form_post callbacks typically auto-submit a hidden form.
        has_id_token = form.find("input", attrs={"name": "id_token"}) is not None
        has_code = form.find("input", attrs={"name": "code"}) is not None
        if not (has_id_token or has_code):
            return current
        action = str(form.get("action") or current.url)
        current = client.post(urljoin(str(current.url), action), data=_form_fields(form))
        current.raise_for_status()
    return current


def _looks_like_login_page(html: str) -> bool:
    lowered = html.lower()
    return "id=\"password\"" in lowered and "id=\"username\"" in lowered

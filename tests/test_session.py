from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from ulscrape.config import Settings
from ulscrape.errors import AuthError
from ulscrape.scraper.session import (
    build_client,
    is_authenticated,
    load_cookies,
    login,
    save_cookies,
)


def test_is_authenticated_gate() -> None:
    assert is_authenticated("<html>Signed in</html>") is True
    assert is_authenticated('<a class="login-return-url">Login</a>') is False
    assert is_authenticated("<a>Login to Download</a>") is False


def test_netscape_and_list_cookies(tmp_path: Path) -> None:
    netscape = tmp_path / "cookies.txt"
    netscape.write_text(
        "# Netscape HTTP Cookie File\n"
        ".ultralibrarian.com\tTRUE\t/\tFALSE\t0\tsid\tnslist\n",
        encoding="utf-8",
    )
    settings = Settings(cookies_path=netscape)
    client = build_client(settings)
    assert client.cookies.get("sid") == "nslist"

    listed = tmp_path / "cookies.json"
    listed.write_text(
        '[{"name": "token", "value": "from-list", "domain": "ultralibrarian.com", "path": "/"}]',
        encoding="utf-8",
    )
    load_cookies(client, listed)
    assert client.cookies.get("token") == "from-list"
    save_cookies(client, tmp_path / "out.json")
    assert (tmp_path / "out.json").is_file()


def test_login_submits_form() -> None:
    login_html = """
    <form action="/Account/Login" method="post">
      <input id="Username" name="Username" />
      <input id="Password" name="Password" type="password" />
      <input name="__RequestVerificationToken" value="tok" />
    </form>
    """
    posted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/Account/Login" and request.method == "GET":
            return httpx.Response(200, text=login_html)
        if request.url.path == "/Account/Login" and request.method == "POST":
            posted.append(request.content.decode("utf-8"))
            return httpx.Response(200, text="<html><body>Welcome</body></html>")
        return httpx.Response(404)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://app.ultralibrarian.com",
        follow_redirects=True,
    )
    login(client, "user@example.com", "secret")
    assert posted
    assert "Username=user%40example.com" in posted[0]
    assert "Password=secret" in posted[0]


def test_login_rejected() -> None:
    login_html = """
    <form action="/Account/Login" method="post">
      <input id="Username" name="Username" />
      <input id="Password" name="Password" type="password" />
    </form>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=login_html)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://app.ultralibrarian.com",
        follow_redirects=True,
    )
    with pytest.raises(AuthError, match="login was rejected"):
        login(client, "user@example.com", "wrong")


def test_login_requires_email() -> None:
    client = httpx.Client(base_url="https://app.ultralibrarian.com")
    with pytest.raises(AuthError, match="UL_EMAIL"):
        login(client, "", "secret")


def test_login_follows_oidc_form_post() -> None:
    login_html = """
    <form action="/Account/Login" method="post">
      <input id="Username" name="Username" />
      <input id="Password" name="Password" type="password" />
    </form>
    """
    oidc_html = """
    <form action="/signin-oidc" method="post">
      <input type="hidden" name="id_token" value="jwt" />
      <input type="hidden" name="code" value="abc" />
    </form>
    """
    hops: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hops.append(f"{request.method} {request.url.path}")
        if request.method == "GET":
            return httpx.Response(200, text=login_html)
        if request.url.path == "/Account/Login":
            return httpx.Response(200, text=oidc_html)
        if request.url.path == "/signin-oidc":
            return httpx.Response(200, text="<html><body>home</body></html>")
        return httpx.Response(404)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://app.ultralibrarian.com",
        follow_redirects=True,
    )
    login(client, "user@example.com", "secret")
    assert "POST /signin-oidc" in hops

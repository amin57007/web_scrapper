from __future__ import annotations

import json
from pathlib import Path

import httpx

from tests.helpers import write_ul_zip
from ulscrape.config import Settings
from ulscrape.scraper.export import fetch_details, queue_and_download


def test_fetch_details_and_download(details_html: str, tmp_path: Path) -> None:
    zip_bytes = write_ul_zip(tmp_path / "src.zip").read_bytes()
    logged_in_html = (
        details_html.replace("login-return-url", "logged-in").replace(
            "Login to Download", "Signed in"
        )
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        path = request.url.path
        if path.startswith("/details/"):
            return httpx.Response(200, text=logged_in_html)
        if path == "/Export/QueueExport":
            body = request.content.decode("utf-8")
            assert "exports=42" in body
            assert "exports=37" in body
            assert "PartUniqueId=1621ae5d-103f-11e9-ab3a-0a3560a4cccc" in body
            return httpx.Response(200, json={"success": True, "encoded_token": "tok123"})
        if path == "/Export/CheckQueue":
            return httpx.Response(200, json={"state": 2})
        if path == "/Export/Download":
            return httpx.Response(
                200,
                content=zip_bytes,
                headers={"content-type": "application/zip"},
            )
        return httpx.Response(404, text="missing " + path)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://app.ultralibrarian.com")
    details = fetch_details(
        client,
        "https://app.ultralibrarian.com/details/1621ae5d-103f-11e9-ab3a-0a3560a4cccc/Texas-Instruments/OPA2374AIDR",
    )
    dest = tmp_path / "out.zip"
    settings = Settings(output_dir=tmp_path)
    saved = queue_and_download(client, details, dest, settings)
    assert saved == dest
    assert dest.read_bytes() == zip_bytes
    assert any(c.startswith("POST /Export/QueueExport") for c in calls)
    assert any("GET /Export/Download" in c for c in calls)


def test_cookie_roundtrip(tmp_path: Path) -> None:
    from ulscrape.scraper.session import build_client, load_cookies, save_cookies

    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(json.dumps({"session": "abc"}), encoding="utf-8")
    settings = Settings(cookies_path=cookie_file)
    client = build_client(settings)
    assert client.cookies.get("session") == "abc"
    save_cookies(client, tmp_path / "out.json")
    load_cookies(client, tmp_path / "out.json")

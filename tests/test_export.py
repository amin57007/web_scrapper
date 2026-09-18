from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from tests.helpers import logged_in_html, remove_export_checkbox, write_ul_zip
from ulscrape.config import Settings
from ulscrape.errors import AuthError, ExportError
from ulscrape.scraper.export import fetch_details, queue_and_download

Handler = Callable[[httpx.Request], httpx.Response]

OPA_URL = (
    "https://app.ultralibrarian.com/details/"
    "1621ae5d-103f-11e9-ab3a-0a3560a4cccc/Texas-Instruments/OPA2374AIDR"
)
ADRF_URL = (
    "https://app.ultralibrarian.com/details/"
    "f4e05b10-37aa-11ef-bf12-024899f9dfe1/Analog-Devices-Inc/ADRF5051BCCZN"
)


def _client(handler: Handler) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://app.ultralibrarian.com",
    )


def _zip_handler(
    html: str,
    zip_bytes: bytes,
    *,
    queue_assert: Callable[[str], None] | None = None,
    queue_response: httpx.Response | None = None,
    check_response: httpx.Response | None = None,
    download_response: httpx.Response | None = None,
) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/details/"):
            return httpx.Response(200, text=html)
        if path == "/Export/QueueExport":
            if queue_assert:
                queue_assert(request.content.decode("utf-8"))
            if queue_response is not None:
                return queue_response
            return httpx.Response(200, json={"success": True, "encoded_token": "tok123"})
        if path == "/Export/CheckQueue":
            if check_response is not None:
                return check_response
            return httpx.Response(200, json={"state": 2})
        if path == "/Export/Download":
            if download_response is not None:
                return download_response
            return httpx.Response(
                200,
                content=zip_bytes,
                headers={"content-type": "application/zip"},
            )
        return httpx.Response(404, text="missing " + path)

    return handler


def test_fetch_details_and_download(details_html: str, tmp_path: Path) -> None:
    zip_bytes = write_ul_zip(tmp_path / "src.zip").read_bytes()
    html = logged_in_html(details_html)
    calls: list[str] = []

    def queue_assert(body: str) -> None:
        assert "exports=42" in body
        assert "exports=37" in body
        assert "PartUniqueId=1621ae5d-103f-11e9-ab3a-0a3560a4cccc" in body

    inner = _zip_handler(html, zip_bytes, queue_assert=queue_assert)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        return inner(request)

    client = _client(handler)
    details = fetch_details(client, OPA_URL)
    dest = tmp_path / "out.zip"
    saved = queue_and_download(client, details, dest, Settings(output_dir=tmp_path))
    assert saved == dest
    assert dest.read_bytes() == zip_bytes
    assert any(c.startswith("POST /Export/QueueExport") for c in calls)
    assert any("GET /Export/Download" in c for c in calls)


def test_adrf5051_queues_step_id_21(adrf_details_html: str, tmp_path: Path) -> None:
    zip_bytes = write_ul_zip(tmp_path / "src.zip").read_bytes()
    html = logged_in_html(adrf_details_html)

    def queue_assert(body: str) -> None:
        assert "exports=42" in body
        assert "exports=21" in body
        assert "exports=37" not in body
        assert "PartUniqueId=f4e05b10-37aa-11ef-bf12-024899f9dfe1" in body

    client = _client(_zip_handler(html, zip_bytes, queue_assert=queue_assert))
    details = fetch_details(client, ADRF_URL)
    dest = tmp_path / "adrf.zip"
    saved = queue_and_download(client, details, dest, Settings(output_dir=tmp_path))
    assert saved == dest
    assert dest.read_bytes() == zip_bytes


def test_v5_only_queues_24_and_step(details_html: str, tmp_path: Path) -> None:
    zip_bytes = write_ul_zip(tmp_path / "src.zip").read_bytes()
    html = remove_export_checkbox(logged_in_html(details_html), "KiCADv6")

    def queue_assert(body: str) -> None:
        assert "exports=24" in body
        assert "exports=37" in body
        assert "exports=42" not in body

    client = _client(_zip_handler(html, zip_bytes, queue_assert=queue_assert))
    details = fetch_details(client, OPA_URL)
    assert details.kicad_v6() is None
    assert details.kicad_v5() is not None
    queue_and_download(client, details, tmp_path / "v5.zip", Settings(output_dir=tmp_path))


def test_no_kicad_or_step_falls_back_to_default_ids(details_html: str, tmp_path: Path) -> None:
    zip_bytes = write_ul_zip(tmp_path / "src.zip").read_bytes()
    html = logged_in_html(details_html)
    for html_id in ("KiCADv6", "KiCAD", "MfrThreeDModel"):
        html = remove_export_checkbox(html, html_id)

    def queue_assert(body: str) -> None:
        assert "exports=42" in body
        assert "exports=37" in body

    client = _client(_zip_handler(html, zip_bytes, queue_assert=queue_assert))
    details = fetch_details(client, OPA_URL)
    assert details.kicad_v6() is None
    assert details.step_format() is None
    queue_and_download(client, details, tmp_path / "fb.zip", Settings(output_dir=tmp_path))


def test_explicit_export_ids_override_parsed(details_html: str, tmp_path: Path) -> None:
    zip_bytes = write_ul_zip(tmp_path / "src.zip").read_bytes()
    html = logged_in_html(details_html)

    def queue_assert(body: str) -> None:
        assert "exports=42" in body
        assert "exports=21" in body
        assert "exports=37" not in body

    client = _client(_zip_handler(html, zip_bytes, queue_assert=queue_assert))
    details = fetch_details(client, OPA_URL)
    queue_and_download(
        client,
        details,
        tmp_path / "ids.zip",
        Settings(output_dir=tmp_path),
        export_ids=[42, 21],
    )


def test_auth_error_without_credentials(details_html: str, tmp_path: Path) -> None:
    client = _client(lambda request: httpx.Response(200, text=details_html))
    details = fetch_details(client, OPA_URL)
    assert details.login_required is True
    with pytest.raises(AuthError, match="UL_EMAIL"):
        queue_and_download(
            client,
            details,
            tmp_path / "out.zip",
            Settings(output_dir=tmp_path, email=None, password=None),
        )


def test_auth_error_still_logged_out(
    details_html: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ulscrape.scraper.export.sess.login", lambda *_a, **_k: None)
    client = _client(lambda request: httpx.Response(200, text=details_html))
    details = fetch_details(client, OPA_URL)
    with pytest.raises(AuthError, match="still logged out"):
        queue_and_download(
            client,
            details,
            tmp_path / "out.zip",
            Settings(output_dir=tmp_path, email="user@example.com", password="secret"),
        )


def test_login_then_download(
    details_html: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_bytes = write_ul_zip(tmp_path / "src.zip").read_bytes()
    monkeypatch.setattr("ulscrape.scraper.export.sess.login", lambda *_a, **_k: None)
    gated = details_html
    signed_in = logged_in_html(details_html)
    details_gets = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/details/"):
            details_gets["n"] += 1
            html = gated if details_gets["n"] <= 2 else signed_in
            return httpx.Response(200, text=html)
        if path == "/Export/QueueExport":
            return httpx.Response(200, json={"success": True, "encoded_token": "tok-login"})
        if path == "/Export/CheckQueue":
            return httpx.Response(200, json={"state": 2})
        if path == "/Export/Download":
            return httpx.Response(
                200,
                content=zip_bytes,
                headers={"content-type": "application/zip"},
            )
        return httpx.Response(404, text="missing " + path)

    client = _client(handler)
    details = fetch_details(client, OPA_URL)
    saved = queue_and_download(
        client,
        details,
        tmp_path / "logged.zip",
        Settings(output_dir=tmp_path, email="user@example.com", password="secret"),
    )
    assert saved.read_bytes() == zip_bytes


def test_fetch_details_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    client = _client(handler)
    with pytest.raises(ExportError, match="could not load"):
        fetch_details(client, OPA_URL)


def test_queue_export_unauthorized(details_html: str, tmp_path: Path) -> None:
    html = logged_in_html(details_html)
    client = _client(
        _zip_handler(
            html,
            b"unused",
            queue_response=httpx.Response(401, json={"success": False}),
        )
    )
    details = fetch_details(client, OPA_URL)
    with pytest.raises(AuthError, match="login required"):
        queue_and_download(client, details, tmp_path / "x.zip", Settings(output_dir=tmp_path))


def test_queue_export_non_json(details_html: str, tmp_path: Path) -> None:
    html = logged_in_html(details_html)
    client = _client(
        _zip_handler(
            html,
            b"unused",
            queue_response=httpx.Response(200, text="<html>captcha</html>"),
        )
    )
    details = fetch_details(client, OPA_URL)
    with pytest.raises(ExportError, match="did not return JSON"):
        queue_and_download(client, details, tmp_path / "x.zip", Settings(output_dir=tmp_path))


def test_queue_export_failed_payload(details_html: str, tmp_path: Path) -> None:
    html = logged_in_html(details_html)
    client = _client(
        _zip_handler(
            html,
            b"unused",
            queue_response=httpx.Response(
                200, json={"success": False, "message": "captcha required"}
            ),
        )
    )
    details = fetch_details(client, OPA_URL)
    with pytest.raises(ExportError, match="captcha required"):
        queue_and_download(client, details, tmp_path / "x.zip", Settings(output_dir=tmp_path))


def test_queue_export_missing_token(details_html: str, tmp_path: Path) -> None:
    html = logged_in_html(details_html)
    client = _client(
        _zip_handler(
            html,
            b"unused",
            queue_response=httpx.Response(200, json={"success": True}),
        )
    )
    details = fetch_details(client, OPA_URL)
    with pytest.raises(ExportError, match="no encoded_token"):
        queue_and_download(client, details, tmp_path / "x.zip", Settings(output_dir=tmp_path))


def test_check_queue_failed_state(details_html: str, tmp_path: Path) -> None:
    html = logged_in_html(details_html)
    client = _client(
        _zip_handler(
            html,
            b"unused",
            check_response=httpx.Response(200, json={"state": 3}),
        )
    )
    details = fetch_details(client, OPA_URL)
    with pytest.raises(ExportError, match="queue failed"):
        queue_and_download(
            client,
            details,
            tmp_path / "x.zip",
            Settings(output_dir=tmp_path, poll_timeout_s=5, poll_interval_s=0),
        )


def test_check_queue_timeout(details_html: str, tmp_path: Path) -> None:
    html = logged_in_html(details_html)
    client = _client(
        _zip_handler(
            html,
            b"unused",
            check_response=httpx.Response(200, json={"state": 1}),
        )
    )
    details = fetch_details(client, OPA_URL)
    with pytest.raises(ExportError, match="timed out"):
        queue_and_download(
            client,
            details,
            tmp_path / "x.zip",
            Settings(output_dir=tmp_path, poll_timeout_s=0, poll_interval_s=0),
        )


def test_download_html_instead_of_zip(details_html: str, tmp_path: Path) -> None:
    html = logged_in_html(details_html)
    client = _client(
        _zip_handler(
            html,
            b"unused",
            download_response=httpx.Response(
                200,
                content=b"<html>login</html>",
                headers={"content-type": "text/html; charset=utf-8"},
            ),
        )
    )
    details = fetch_details(client, OPA_URL)
    with pytest.raises(ExportError, match="HTML instead of a zip"):
        queue_and_download(client, details, tmp_path / "x.zip", Settings(output_dir=tmp_path))


def test_download_too_small(details_html: str, tmp_path: Path) -> None:
    html = logged_in_html(details_html)
    client = _client(
        _zip_handler(
            html,
            b"unused",
            download_response=httpx.Response(
                200,
                content=b"PK tiny",
                headers={"content-type": "application/zip"},
            ),
        )
    )
    details = fetch_details(client, OPA_URL)
    with pytest.raises(ExportError, match="too small"):
        queue_and_download(client, details, tmp_path / "x.zip", Settings(output_dir=tmp_path))


def test_cookie_roundtrip(tmp_path: Path) -> None:
    from ulscrape.scraper.session import build_client, load_cookies, save_cookies

    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(json.dumps({"session": "abc"}), encoding="utf-8")
    settings = Settings(cookies_path=cookie_file)
    client = build_client(settings)
    assert client.cookies.get("session") == "abc"
    save_cookies(client, tmp_path / "out.json")
    load_cookies(client, tmp_path / "out.json")

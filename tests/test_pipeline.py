from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from tests.helpers import logged_in_html, write_ul_zip
from ulscrape.config import Settings
from ulscrape.models import PartDetails, PartRef
from ulscrape.pipeline import fetch_part, inspect_url

OPA_URL = (
    "https://app.ultralibrarian.com/details/"
    "1621AE5D-103F-11E9-AB3A-0A3560A4CCCC/Texas-Instruments/OPA2374AIDR"
)


def test_browser_fetch_does_not_prefetch_details_over_httpx(
    monkeypatch: pytest.MonkeyPatch, ul_zip: Path, tmp_path: Path
) -> None:
    def boom(*_args: object, **_kwargs: object) -> PartDetails:
        raise AssertionError("browser fetch must not call httpx fetch_details")

    monkeypatch.setattr("ulscrape.pipeline.fetch_details", boom)

    def fake_download(
        url: str,
        zip_path: Path,
        settings: Settings,
        export_ids: object = None,
    ) -> tuple[Path, PartDetails]:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path.write_bytes(ul_zip.read_bytes())
        details = PartDetails(
            ref=PartRef(
                part_uuid="1621ae5d-103f-11e9-ab3a-0a3560a4cccc",
                manufacturer="Texas Instruments",
                mpn="OPA2374AIDR",
            )
        )
        return zip_path, details

    monkeypatch.setattr("ulscrape.scraper.browser.download_with_browser", fake_download)
    result = fetch_part(
        OPA_URL,
        Settings(output_dir=tmp_path / "libraries", use_browser=True),
    )
    assert result.zip_path is not None
    assert result.zip_path.name == "Texas_Instruments_OPA2374AIDR.zip"
    assert result.symbol_lib is not None and result.symbol_lib.exists()


def test_http_fetch_installs_library(
    details_html: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_bytes = write_ul_zip(tmp_path / "src.zip").read_bytes()
    html = logged_in_html(details_html)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/details/"):
            return httpx.Response(200, text=html)
        if path == "/Export/QueueExport":
            body = request.content.decode("utf-8")
            assert "exports=42" in body
            assert "exports=37" in body
            return httpx.Response(200, json={"success": True, "encoded_token": "tok-http"})
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

    def fake_build_client(_settings: Settings) -> httpx.Client:
        return httpx.Client(
            transport=transport,
            base_url="https://app.ultralibrarian.com",
            follow_redirects=True,
        )

    monkeypatch.setattr("ulscrape.pipeline.build_client", fake_build_client)
    result = fetch_part(
        OPA_URL,
        Settings(output_dir=tmp_path / "libraries", use_browser=False),
    )
    assert result.zip_path is not None
    assert result.zip_path.name == "Texas_Instruments_OPA2374AIDR.zip"
    assert result.symbol_lib is not None and result.symbol_lib.exists()
    assert result.part is not None
    assert result.part.ref.mpn == "OPA2374AIDR"


def test_inspect_url_returns_public_metadata(
    details_html: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/details/"):
            return httpx.Response(200, text=details_html)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    def fake_build_client(_settings: Settings) -> httpx.Client:
        return httpx.Client(
            transport=transport,
            base_url="https://app.ultralibrarian.com",
            follow_redirects=True,
        )

    monkeypatch.setattr("ulscrape.pipeline.build_client", fake_build_client)
    details = inspect_url(OPA_URL, Settings(use_browser=False))
    assert details.ref.mpn == "OPA2374AIDR"
    assert details.login_required is True
    assert details.kicad_v6() is not None
    assert details.step_format() is not None

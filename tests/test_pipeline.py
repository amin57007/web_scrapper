from __future__ import annotations

from pathlib import Path

import pytest

from ulscrape.config import Settings
from ulscrape.models import PartDetails, PartRef
from ulscrape.pipeline import fetch_part


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
        "https://app.ultralibrarian.com/details/1621AE5D-103F-11E9-AB3A-0A3560A4CCCC/Texas-Instruments/OPA2374AIDR",
        Settings(output_dir=tmp_path / "libraries", use_browser=True),
    )
    assert result.zip_path is not None
    assert result.zip_path.name == "Texas_Instruments_OPA2374AIDR.zip"
    assert result.symbol_lib is not None and result.symbol_lib.exists()

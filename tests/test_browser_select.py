from __future__ import annotations

from pathlib import Path

import pytest

from ulscrape.models import PartDetails, PartRef
from ulscrape.scraper.browser import _select_kicad_and_step

FIXTURES = Path(__file__).parent / "fixtures"


def _dummy_details() -> PartDetails:
    return PartDetails(ref=PartRef(part_uuid="00000000-0000-0000-0000-000000000000"))


def test_select_kicad_and_step_in_collapsed_accordion() -> None:
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    html = (FIXTURES / "export_panel_collapsed.html").read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium not available: {exc}")
        page = browser.new_page()
        try:
            page.set_content(html)
            assert not page.locator("#KiCADv6").is_visible()
            _select_kicad_and_step(page, _dummy_details(), export_ids=[42, 37])
            assert page.locator("#KiCADv6").is_checked()
            assert page.locator("#MfrThreeDModel").is_checked()
            assert not page.locator("#KiCAD").is_checked()
        finally:
            browser.close()

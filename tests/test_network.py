from __future__ import annotations

import os

import pytest

from ulscrape.config import Settings
from ulscrape.scraper.export import fetch_details
from ulscrape.scraper.session import build_client
from ulscrape.scraper.urls import parse_part_url

LIVE_URL = (
    "https://app.ultralibrarian.com/details/"
    "1621AE5D-103F-11E9-AB3A-0A3560A4CCCC/Texas-Instruments/OPA2374AIDR"
)

pytestmark = pytest.mark.network


@pytest.mark.skipif(
    os.environ.get("UL_SKIP_NETWORK") == "1",
    reason="UL_SKIP_NETWORK=1",
)
def test_live_details_page() -> None:
    parse_part_url(LIVE_URL)
    settings = Settings.from_env()
    with build_client(settings) as client:
        details = fetch_details(client, LIVE_URL)
    assert details.ref.mpn.upper().startswith("OPA2374")
    assert details.kicad_v6() is not None or details.kicad_v5() is not None
    assert details.step_format() is not None

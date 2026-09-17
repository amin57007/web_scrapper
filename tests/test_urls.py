from __future__ import annotations

import pytest

from ulscrape.errors import UrlParseError
from ulscrape.scraper.urls import details_url, parse_part_url


def test_parse_details_url() -> None:
    ref = parse_part_url(
        "https://app.ultralibrarian.com/details/1621AE5D-103F-11E9-AB3A-0A3560A4CCCC/Texas-Instruments/OPA2374AIDR"
    )
    assert ref.part_uuid == "1621ae5d-103f-11e9-ab3a-0a3560a4cccc"
    assert ref.manufacturer == "Texas Instruments"
    assert ref.mpn == "OPA2374AIDR"
    assert ref.slug == "Texas_Instruments_OPA2374AIDR"


def test_parse_bare_uuid() -> None:
    ref = parse_part_url("1621ae5d-103f-11e9-ab3a-0a3560a4cccc")
    assert ref.part_uuid == "1621ae5d-103f-11e9-ab3a-0a3560a4cccc"
    assert "/details/1621ae5d-103f-11e9-ab3a-0a3560a4cccc" in ref.url


def test_parse_cad_portal_query() -> None:
    ref = parse_part_url(
        "https://cad.ultralibrarian.com/orcad/Home?partUuid=1621ae5d-103f-11e9-ab3a-0a3560a4cccc&mfr=Texas-Instruments&mpn=OPA2374AIDR"
    )
    assert ref.mpn == "OPA2374AIDR"
    assert ref.manufacturer == "Texas Instruments"


def test_parse_rejects_unrelated_url() -> None:
    with pytest.raises(UrlParseError):
        parse_part_url("https://example.com/parts/opa2374")


def test_details_url_roundtrip() -> None:
    ref = parse_part_url("1621ae5d-103f-11e9-ab3a-0a3560a4cccc")
    assert details_url(ref).endswith("/details/1621ae5d-103f-11e9-ab3a-0a3560a4cccc")

from __future__ import annotations

import pytest

from tests.helpers import logged_in_html
from ulscrape.errors import DetailsParseError
from ulscrape.models import CadFormat, PartDetails, PartRef
from ulscrape.scraper.details import parse_details_html


def test_parse_details_html(details_html: str) -> None:
    details = parse_details_html(
        details_html,
        page_url="https://app.ultralibrarian.com/details/1621ae5d-103f-11e9-ab3a-0a3560a4cccc/Texas-Instruments/OPA2374AIDR",
    )
    assert details.ref.mpn == "OPA2374AIDR"
    assert details.ref.manufacturer == "Texas Instruments"
    assert details.ref.part_uuid == "1621ae5d-103f-11e9-ab3a-0a3560a4cccc"
    assert details.part_id == 2456935
    assert details.status == "Active"
    assert "operational amplifier" in details.description
    assert details.datasheet_url is not None
    assert details.preview_3d_url is not None
    assert details.csrf_token == "test-csrf-token"
    assert details.login_required is True

    kicad6 = details.kicad_v6()
    assert kicad6 is not None
    assert kicad6.export_id == 42
    assert kicad6.has_symbol and kicad6.has_footprint

    step = details.step_format()
    assert step is not None
    assert step.export_id == 37
    assert step.has_3d


def test_kicad_v5_format(details_html: str) -> None:
    details = parse_details_html(details_html)
    v5 = details.kicad_v5()
    assert v5 is not None
    assert v5.export_id == 24


def test_parse_adrf5051_uses_step_id_21(adrf_details_html: str) -> None:
    details = parse_details_html(
        adrf_details_html,
        page_url="https://app.ultralibrarian.com/details/f4e05b10-37aa-11ef-bf12-024899f9dfe1/Analog-Devices-Inc/ADRF5051BCCZN",
    )
    assert details.ref.mpn == "ADRF5051BCCZN"
    assert details.ref.manufacturer == "Analog Devices Inc"
    assert details.ref.part_uuid == "f4e05b10-37aa-11ef-bf12-024899f9dfe1"
    kicad6 = details.kicad_v6()
    assert kicad6 is not None
    assert kicad6.export_id == 42
    step = details.step_format()
    assert step is not None
    assert step.html_id == "ThreeDModel"
    assert step.export_id == 21
    assert step.has_3d
    assert details.format_by_id(37) is None


def test_step_html_ids() -> None:
    mfr = CadFormat(html_id="MfrThreeDModel", export_id=37, label="STEP", has_3d=True)
    generic = CadFormat(html_id="ThreeDModel", export_id=21, label="STEP", has_3d=True)
    ap214 = CadFormat(html_id="other", export_id=99, label="STEP AP214", has_3d=True)
    stl = CadFormat(html_id="STL", export_id=57, label="STL", has_3d=True)
    iges = CadFormat(html_id="IGES", export_id=45, label="IGES v5.3", has_3d=True)
    assert mfr.is_step and generic.is_step and ap214.is_step
    assert not stl.is_step
    assert not iges.is_step


def test_kicad_helpers_by_label() -> None:
    v6 = CadFormat(html_id="custom", export_id=99, label="KiCad v6 nightlies")
    v5 = CadFormat(html_id="KiCAD", export_id=24, label="KiCAD v5")
    details = PartDetails(
        ref=PartRef(part_uuid="00000000-0000-0000-0000-000000000000"),
        formats=[v6, v5],
    )
    assert v6.is_kicad and v5.is_kicad
    assert details.kicad_v6() is v6
    assert details.kicad_v5() is v5


def test_logged_in_page_does_not_require_login(details_html: str) -> None:
    details = parse_details_html(logged_in_html(details_html))
    assert details.login_required is False


def test_no_formats_raises() -> None:
    html = """
    <html><body>
      <link rel="canonical" href="https://app.ultralibrarian.com/details/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/X/Y" />
    </body></html>
    """
    with pytest.raises(DetailsParseError, match="no CAD export formats"):
        parse_details_html(html)


def test_missing_uuid_raises() -> None:
    html = "<html><body><h1>empty</h1></body></html>"
    with pytest.raises(DetailsParseError, match="could not find part UUID"):
        parse_details_html(html)


def test_uuid_from_javascript_when_url_unrelated() -> None:
    html = """
    <html><body>
      <input id="KiCADv6" name="exports" type="checkbox" value="42" class="export-option">
      <label for="KiCADv6">KiCAD v6+</label>
      <script>ultralibrarian.pricinghandler.PartUniqueId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";</script>
    </body></html>
    """
    details = parse_details_html(html, page_url="https://app.ultralibrarian.com/other")
    assert details.ref.part_uuid == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

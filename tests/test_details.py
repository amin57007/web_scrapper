from __future__ import annotations

from ulscrape.models import CadFormat
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
    stl = CadFormat(html_id="STL", export_id=57, label="STL", has_3d=True)
    assert mfr.is_step and generic.is_step
    assert not stl.is_step

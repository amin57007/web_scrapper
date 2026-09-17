from __future__ import annotations

from pathlib import Path

from ulscrape.kicad.library import install_into_library
from ulscrape.kicad.sexpr import quoted_atom, replace_property, top_level_forms
from ulscrape.models import PartDetails, PartRef
from ulscrape.pipeline import import_zip


def test_replace_footprint_property() -> None:
    symbol = '(symbol "U" (property "Footprint" "SOIC-8") (property "Value" "x"))'
    updated = replace_property(symbol, "Footprint", "UltraLibrarian:SOIC-8")
    assert '"UltraLibrarian:SOIC-8"' in updated


def test_install_into_library(ul_zip: Path, tmp_path: Path) -> None:
    result = import_zip(ul_zip, tmp_path / "libraries")
    assert result.extracted is not None
    assert result.extracted.layout == "ultralibrarian-kicadv6"
    assert result.symbol_lib is not None and result.symbol_lib.exists()
    text = result.symbol_lib.read_text(encoding="utf-8")
    names = [quoted_atom(form, 0) for _, _, form in top_level_forms(text, "symbol")]
    assert "OPA2374AIDR" in names
    assert "UltraLibrarian:SOIC-8_3.9x4.9mm_P1.27mm" in text

    pretty = result.footprint_lib
    assert pretty is not None
    mods = list(pretty.glob("*.kicad_mod"))
    assert len(mods) == 1
    fp_text = mods[0].read_text(encoding="utf-8")
    assert "${KICAD_3RD_PARTY}/UltraLibrarian.3dshapes/OPA2374AIDR.step" in fp_text

    assert result.model_dir is not None
    assert (result.model_dir / "OPA2374AIDR.step").exists()
    assert (tmp_path / "libraries" / "sym-lib-table").exists()
    assert (tmp_path / "libraries" / "fp-lib-table").exists()


def test_merge_second_symbol(ul_zip: Path, tmp_path: Path) -> None:
    libraries = tmp_path / "libraries"
    import_zip(ul_zip, libraries)
    extracted = import_zip(ul_zip, libraries).extracted
    assert extracted is not None
    details = PartDetails(
        ref=PartRef(
            part_uuid="00000000-0000-0000-0000-000000000000",
            manufacturer="TI",
            mpn="OPA2374AIDR",
        )
    )
    written = install_into_library(extracted, libraries, details=details, overwrite=True)
    text = written["symbol_lib"].read_text(encoding="utf-8")
    names = [quoted_atom(form, 0) for _, _, form in top_level_forms(text, "symbol")]
    assert names.count("OPA2374AIDR") == 1

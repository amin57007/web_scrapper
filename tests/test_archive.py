from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tests.helpers import write_ul_zip
from ulscrape.errors import ArchiveError
from ulscrape.kicad.archive import detect_layout, extract_zip, inspect_zip


def test_inspect_kicadv6_zip(ul_zip: Path) -> None:
    grouped = inspect_zip(ul_zip)
    assert len(grouped["symbols"]) == 1
    assert grouped["symbols"][0].endswith(".kicad_sym")
    assert len(grouped["footprints"]) == 1
    assert grouped["footprints"][0].endswith(".kicad_mod")
    assert len(grouped["models"]) == 1
    assert detect_layout(grouped["all"]) == "ultralibrarian-kicadv6"


def test_extract_zip(ul_zip: Path, tmp_path: Path) -> None:
    extracted = extract_zip(ul_zip, tmp_path / "out")
    assert extracted.layout == "ultralibrarian-kicadv6"
    assert extracted.symbols[0].read_text(encoding="utf-8").startswith("(kicad_symbol_lib")
    assert extracted.footprints[0].suffix == ".kicad_mod"
    assert extracted.models[0].suffix == ".step"


def test_classic_kicad_layout(tmp_path: Path) -> None:
    zip_path = write_ul_zip(tmp_path / "classic.zip", layout="classic")
    grouped = inspect_zip(zip_path)
    assert detect_layout(grouped["all"]) == "ultralibrarian-kicad"


def test_v5_layout(tmp_path: Path) -> None:
    zip_path = write_ul_zip(tmp_path / "v5.zip", layout="kicad-v5")
    grouped = inspect_zip(zip_path)
    assert detect_layout(grouped["all"]) == "ultralibrarian-kicad-v5"
    extracted = extract_zip(zip_path, tmp_path / "v5out")
    assert extracted.symbols[0].suffix == ".lib"


def test_rejects_zip_slip(tmp_path: Path) -> None:
    zip_path = tmp_path / "slip.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.kicad_sym", "(kicad_symbol_lib)")
        zf.writestr("footprints.pretty/x.kicad_mod", "(footprint \"x\")")
    with pytest.raises(ArchiveError, match="unsafe"):
        inspect_zip(zip_path)


def test_rejects_empty_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("readme.txt", "no cad here")
    with pytest.raises(ArchiveError, match="no KiCad"):
        extract_zip(zip_path, tmp_path / "out")

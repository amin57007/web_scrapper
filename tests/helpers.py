from __future__ import annotations

import zipfile
from pathlib import Path

SYMBOL_TEXT = """(kicad_symbol_lib (version 20211014) (generator kicad_symbol_editor)
  (symbol "OPA2374AIDR"
    (property "Reference" "U" (id 0) (at 0 5.08 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Value" "OPA2374AIDR" (id 1) (at 0 -5.08 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Footprint" "SOIC-8_3.9x4.9mm_P1.27mm" (id 2) (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (symbol "OPA2374AIDR_0_1"
      (rectangle (start -5.08 5.08) (end 5.08 -5.08)
        (stroke (width 0.254) (type default))
        (fill (type background))
      )
    )
  )
)
"""

FOOTPRINT_TEXT = """(footprint "SOIC-8_3.9x4.9mm_P1.27mm" (version 20211014) (generator pcbnew)
  (layer "F.Cu")
  (pad "1" smd rect
    (at -3.81 1.905)
    (size 1.5 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask")
  )
)
"""

STEP_TEXT = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ulscrape fixture'),'2;1');
FILE_NAME('OPA2374AIDR.step','2026-01-01T00:00:00',('ulscrape'),('ulscrape'),
  'ulscrape','ulscrape','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;
"""


def write_ul_zip(path: Path, *, layout: str = "kicadv6") -> Path:
    """Build a synthetic Ultra Librarian KiCad zip matching documented layouts."""
    with zipfile.ZipFile(path, "w") as zf:
        if layout == "kicadv6":
            zf.writestr("KiCADv6/OPA2374AIDR.kicad_sym", SYMBOL_TEXT)
            zf.writestr(
                "KiCADv6/footprints.pretty/SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod",
                FOOTPRINT_TEXT,
            )
            zf.writestr("STEP/OPA2374AIDR.step", STEP_TEXT)
        elif layout == "kicad-v5":
            zf.writestr("KiCAD/20220101/20220101.lib", "EESchema-LIBRARY Version 2.4\n")
            zf.writestr(
                "KiCAD/20220101/footprints.pretty/SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod",
                FOOTPRINT_TEXT,
            )
            zf.writestr("STEP/OPA2374AIDR.step", STEP_TEXT)
        elif layout == "classic":
            zf.writestr("OPA2374AIDR/KiCAD/OPA2374AIDR/OPA2374AIDR.kicad_sym", SYMBOL_TEXT)
            zf.writestr(
                "OPA2374AIDR/KiCAD/OPA2374AIDR/footprints.pretty/SOIC-8.kicad_mod",
                FOOTPRINT_TEXT,
            )
            zf.writestr("OPA2374AIDR/STEP/OPA2374AIDR.step", STEP_TEXT)
        else:
            raise ValueError(layout)
    return path

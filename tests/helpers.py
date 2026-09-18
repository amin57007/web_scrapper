from __future__ import annotations

import re
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


def logged_in_html(html: str) -> str:
    """Flip the public details gate so parse_details_html sees a signed-in page."""
    return html.replace("login-return-url", "logged-in").replace(
        "Login to Download", "Signed in"
    )


def remove_export_checkbox(html: str, html_id: str) -> str:
    """Drop one CAD checkbox and its label from a details-page fixture."""
    html = re.sub(rf'<input[^>]*\sid="{re.escape(html_id)}"[^>]*>\s*', "", html)
    return re.sub(
        rf'<label for="{re.escape(html_id)}">.*?</label>\s*',
        "",
        html,
        flags=re.DOTALL,
    )


_EXPORT_PANEL_CSS = """
.collapse:not(.show) { display: none; }
.custom-control-input {
    position: absolute;
    z-index: -1;
    opacity: 0;
    width: 1px;
    height: 1px;
}
#submit-export.hidden { display: none; }
"""


def export_panel_html(
    *,
    collapsed: bool = True,
    kicad_v6: bool = True,
    kicad_v5: bool = True,
    step_id: str = "MfrThreeDModel",
    step_value: int = 37,
    extra_step: str = "",
    consents: bool = False,
    submit: bool = False,
    submit_hidden: bool = False,
) -> str:
    """Minimal Ultra Librarian export panel matching Bootstrap collapse + custom-control."""
    collapse_class = "collapse" if collapsed else "collapse show"
    toggle_class = "accordion-toggle collapsed" if collapsed else "accordion-toggle"
    kicad_v5_input = ""
    if kicad_v5:
        kicad_v5_input = (
            '<input id="KiCAD" name="exports" type="checkbox" value="24" '
            'class="custom-control-input export-option">'
            "<label for=\"KiCAD\">KiCAD v5</label>"
        )
    kicad_v6_input = ""
    if kicad_v6:
        kicad_v6_input = (
            '<input id="KiCADv6" name="exports" type="checkbox" value="42" '
            'class="custom-control-input export-option">'
            "<label for=\"KiCADv6\">KiCAD v6+</label>"
        )
    step_input = (
        f'<input id="{step_id}" name="exports" type="checkbox" value="{step_value}" '
        f'class="custom-control-input export-option">'
        f'<label for="{step_id}">STEP</label>'
    )
    consents_html = ""
    if consents:
        consents_html = """
            <input type="checkbox" class="consentRequest required custom-control-input" id="consent1">
            <label for="consent1">Required manufacturer consent</label>
            <input type="checkbox" class="mfr-export-consent-item required custom-control-input" id="consent2">
            <label for="consent2">Required export consent</label>
        """
    submit_html = ""
    if submit:
        hidden_class = " hidden" if submit_hidden else ""
        submit_html = (
            f'<button id="submit-export" type="button" class="btn{hidden_class}">'
            "Download Selected</button>"
        )
    return f"""<!DOCTYPE html>
<html>
<head><style>{_EXPORT_PANEL_CSS}</style></head>
<body>
    <button id="export-selection-btn" type="button">Download Now</button>
    <div id="export-selection-parent">
        <form id="export-selection-form">
            <div class="card export-group">
                <a class="{toggle_class}" data-toggle="collapse" data-target="#ef-kicad">KiCAD</a>
                <div id="ef-kicad" class="{collapse_class}">
                    {kicad_v5_input}
                    {kicad_v6_input}
                </div>
            </div>
            <div class="card export-group">
                <a class="{toggle_class}" data-toggle="collapse" data-target="#ef-3d">3D CAD Model</a>
                <div id="ef-3d" class="{collapse_class}">
                    {step_input}
                    {extra_step}
                </div>
            </div>
            {consents_html}
            {submit_html}
        </form>
    </div>
</body>
</html>"""

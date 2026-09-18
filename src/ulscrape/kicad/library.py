"""Install extracted CAD files into a KiCad 3rd-party library tree."""

from __future__ import annotations

import shutil
from pathlib import Path

from ulscrape.kicad import sexpr
from ulscrape.models import ExtractedFiles, PartDetails

EMPTY_SYMBOL_LIB = '(kicad_symbol_lib (version 20211014) (generator "ulscrape")\n)\n'


def install_into_library(
    extracted: ExtractedFiles,
    output_dir: Path,
    *,
    lib_name: str = "UltraLibrarian",
    details: PartDetails | None = None,
    overwrite: bool = True,
) -> dict[str, Path]:
    """Copy symbol / footprint / 3D files into KiCad library folders.

    Layout (compatible with Import-LIB-KiCad-Plugin and kicad-libsync):
        output_dir/{lib_name}.kicad_sym
        output_dir/{lib_name}.pretty/*.kicad_mod
        output_dir/{lib_name}.3dshapes/*.{step,wrl,stp}
        output_dir/parts/{slug}/   original extracted tree + metadata.json
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = details.ref.slug if details else extracted.source.stem
    part_dir = output_dir / "parts" / slug
    part_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {"part_dir": part_dir}

    if details:
        (part_dir / "metadata.json").write_text(
            details.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        written["metadata"] = part_dir / "metadata.json"

    pretty_dir = output_dir / f"{lib_name}.pretty"
    model_dir = output_dir / f"{lib_name}.3dshapes"
    pretty_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    written["footprint_lib"] = pretty_dir
    written["model_dir"] = model_dir

    footprint_names: list[str] = []
    preferred_model: Path | None = None
    for model in extracted.models:
        dest = model_dir / model.name
        if dest.exists() and not overwrite:
            continue
        shutil.copy2(model, dest)
        shutil.copy2(model, part_dir / model.name)
        if preferred_model is None or model.suffix.lower() in {".step", ".stp"}:
            preferred_model = dest

    model_ref = None
    if preferred_model:
        model_ref = f"${{KICAD_3RD_PARTY}}/{lib_name}.3dshapes/{preferred_model.name}"
        written["model"] = preferred_model

    for footprint in extracted.footprints:
        text = footprint.read_text(encoding="utf-8")
        name = sexpr.quoted_atom(text, 0) or footprint.stem
        name = _safe_name(name)
        if model_ref:
            text = sexpr.replace_model_path(text, model_ref)
        dest = pretty_dir / f"{name}.kicad_mod"
        if dest.exists() and not overwrite:
            continue
        dest.write_text(text, encoding="utf-8")
        (part_dir / f"{name}.kicad_mod").write_text(text, encoding="utf-8")
        footprint_names.append(name)
        written.setdefault("footprints", dest)

    symbol_lib = output_dir / f"{lib_name}.kicad_sym"
    written["symbol_lib"] = symbol_lib
    primary_fp = f"{lib_name}:{footprint_names[0]}" if footprint_names else None
    for symbol_file in extracted.symbols:
        if symbol_file.suffix.lower() == ".lib":
            dest_legacy = part_dir / symbol_file.name
            shutil.copy2(symbol_file, dest_legacy)
            written["legacy_symbol"] = dest_legacy
            continue
        text = symbol_file.read_text(encoding="utf-8")
        _merge_symbol_library(symbol_lib, text, lib_name, primary_fp, overwrite)
        shutil.copy2(symbol_file, part_dir / symbol_file.name)

    _write_lib_tables(output_dir, lib_name)
    return written


def _merge_symbol_library(
    lib_path: Path,
    incoming_text: str,
    lib_name: str,
    footprint_ref: str | None,
    overwrite: bool,
) -> None:
    existing = lib_path.read_text(encoding="utf-8") if lib_path.exists() else EMPTY_SYMBOL_LIB

    existing_names = {
        sexpr.quoted_atom(form, 0)
        for _, _, form in sexpr.top_level_forms(existing, "symbol")
    }
    additions: list[str] = []
    replacements: dict[str, str] = {}
    for _, _, form in sexpr.top_level_forms(incoming_text, "symbol"):
        name = sexpr.quoted_atom(form, 0)
        if not name:
            continue
        updated = form
        if footprint_ref:
            updated = sexpr.replace_property(updated, "Footprint", footprint_ref)
        updated = sexpr.replace_property(updated, "ki_keywords", lib_name)
        if name in existing_names:
            if overwrite:
                replacements[name] = updated
            continue
        additions.append(updated)

    merged = existing
    if replacements:
        pieces: list[str] = []
        last = 0
        for start, end, form in sexpr.top_level_forms(existing, "symbol"):
            name = sexpr.quoted_atom(form, 0)
            pieces.append(existing[last:start])
            pieces.append(replacements.get(name or "", form))
            last = end + 1
        pieces.append(existing[last:])
        merged = "".join(pieces)

    if additions:
        end = sexpr.matching_paren(merged, merged.find("("))
        insert = "\n".join(additions) + "\n"
        merged = merged[:end] + insert + merged[end:]

    lib_path.write_text(merged, encoding="utf-8")


def _write_lib_tables(output_dir: Path, lib_name: str) -> None:
    sym_table = output_dir / "sym-lib-table"
    fp_table = output_dir / "fp-lib-table"
    _ensure_table_entry(
        sym_table,
        "sym_lib_table",
        lib_name,
        f"${{KIPRJMOD}}/{lib_name}.kicad_sym",
    )
    _ensure_table_entry(
        fp_table,
        "fp_lib_table",
        lib_name,
        f"${{KIPRJMOD}}/{lib_name}.pretty",
    )


def _ensure_table_entry(path: Path, root: str, name: str, uri: str) -> None:
    lib_line = (
        f'  (lib (name "{name}")(type "KiCad")(uri "{uri}")(options "")(descr "ulscrape"))\n'
    )
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if f'(name "{name}")' in text:
            return
        end = sexpr.matching_paren(text, text.find("("))
        path.write_text(text[:end] + lib_line + text[end:], encoding="utf-8")
        return
    path.write_text(f"({root}\n{lib_line})\n", encoding="utf-8")


def _safe_name(name: str) -> str:
    invalid = '<>:"/\\|?* '
    cleaned = name.strip()
    for char in invalid:
        cleaned = cleaned.replace(char, "_")
    return cleaned or "unnamed"

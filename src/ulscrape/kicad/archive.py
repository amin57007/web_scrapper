"""Inspect vendor CAD zips (Ultra Librarian, SnapMagic-style, generic KiCad)."""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath

from ulscrape.errors import ArchiveError
from ulscrape.models import ExtractedFiles

SYMBOL_SUFFIXES = (".kicad_sym", ".lib")
FOOTPRINT_SUFFIXES = (".kicad_mod",)
MODEL_SUFFIXES = (".step", ".stp", ".wrl", ".iges", ".igs", ".stl")


def inspect_zip(zip_path: Path) -> dict[str, list[str]]:
    """Return member names grouped by CAD kind, rejecting zip-slip paths."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ArchiveError(f"not a readable zip: {zip_path}") from exc

    with zf:
        names = zf.namelist()

    unsafe = [name for name in names if _is_unsafe(name)]
    if unsafe:
        raise ArchiveError(f"archive has unsafe member paths: {unsafe[:3]}")

    return {
        "symbols": [n for n in names if n.lower().endswith(SYMBOL_SUFFIXES) and not n.endswith("/")],
        "footprints": [
            n for n in names if n.lower().endswith(FOOTPRINT_SUFFIXES) and not n.endswith("/")
        ],
        "models": [n for n in names if n.lower().endswith(MODEL_SUFFIXES) and not n.endswith("/")],
        "all": [n for n in names if not n.endswith("/")],
    }


def detect_layout(member_names: list[str]) -> str:
    """Classify a zip using layouts documented by tested KiCad importers."""
    lowered = [name.replace("\\", "/") for name in member_names]
    if any("/kicadv6/" in name.lower() or name.lower().startswith("kicadv6/") for name in lowered):
        return "ultralibrarian-kicadv6"
    if any("/kicad/" in name.lower() or name.lower().startswith("kicad/") for name in lowered):
        if any(name.lower().endswith(".kicad_sym") for name in lowered):
            return "ultralibrarian-kicad"
        return "ultralibrarian-kicad-v5"
    if any("/3d/" in name.lower() or name.lower().startswith("3d/") for name in lowered):
        return "samacsys-kicad"
    if any(name.lower().endswith(".kicad_sym") for name in lowered) and any(
        name.lower().endswith(".kicad_mod") for name in lowered
    ):
        return "snapmagic-flat"
    return "generic"


def extract_zip(zip_path: Path, dest_dir: Path) -> ExtractedFiles:
    """Extract CAD members into dest_dir, preserving relative paths."""
    grouped = inspect_zip(zip_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(grouped["symbols"] + grouped["footprints"] + grouped["models"])
    if not wanted:
        raise ArchiveError(f"no KiCad symbol, footprint, or 3D model in {zip_path}")

    extracted = ExtractedFiles(source=zip_path, layout=detect_layout(grouped["all"]))
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(wanted):
            target = dest_dir / Path(name)
            if _is_unsafe(name):
                raise ArchiveError(f"refusing to extract unsafe path {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            lowered = name.lower()
            if lowered.endswith(SYMBOL_SUFFIXES):
                extracted.symbols.append(target)
            elif lowered.endswith(FOOTPRINT_SUFFIXES):
                extracted.footprints.append(target)
            else:
                extracted.models.append(target)
    return extracted


def _is_unsafe(name: str) -> bool:
    pure = PurePosixPath(name.replace("\\", "/"))
    return pure.is_absolute() or ".." in pure.parts

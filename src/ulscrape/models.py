"""Domain models for Ultra Librarian parts and KiCad library output."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class CadFormat(BaseModel):
    """One CAD export checkbox on an Ultra Librarian details page."""

    html_id: str
    export_id: int
    label: str
    has_symbol: bool = False
    has_footprint: bool = False
    has_3d: bool = False

    @property
    def is_kicad(self) -> bool:
        return "kicad" in self.label.lower() or self.html_id.lower().startswith("kicad")

    @property
    def is_step(self) -> bool:
        html_id = self.html_id.lower()
        if html_id in {"mfrthreedmodel", "threedmodel"}:
            return True
        label = self.label.strip().upper()
        return label == "STEP" or label.startswith("STEP ")


class PartRef(BaseModel):
    """Identity of an Ultra Librarian part, usually parsed from a details URL."""

    part_uuid: str
    manufacturer: str = ""
    mpn: str = ""
    url: str = ""

    @property
    def slug(self) -> str:
        mfr = _safe_token(self.manufacturer) or "unknown"
        mpn = _safe_token(self.mpn) or self.part_uuid
        return f"{mfr}_{mpn}"


class PartDetails(BaseModel):
    """Public metadata scraped from an Ultra Librarian details page."""

    ref: PartRef
    description: str = ""
    status: str = ""
    datasheet_url: str | None = None
    part_id: int | None = None
    preview_3d_url: str | None = None
    csrf_token: str | None = None
    login_required: bool = True
    formats: list[CadFormat] = Field(default_factory=list)

    def format_by_id(self, export_id: int) -> CadFormat | None:
        for item in self.formats:
            if item.export_id == export_id:
                return item
        return None

    def kicad_v6(self) -> CadFormat | None:
        for item in self.formats:
            if item.html_id.lower() == "kicadv6":
                return item
        for item in self.formats:
            if item.is_kicad and "v6" in item.label.lower():
                return item
        return None

    def kicad_v5(self) -> CadFormat | None:
        for item in self.formats:
            if item.html_id.lower() == "kicad" and "v6" not in item.label.lower():
                return item
        return None

    def step_format(self) -> CadFormat | None:
        for item in self.formats:
            if item.is_step:
                return item
        return None


class ExtractedFiles(BaseModel):
    """CAD files found inside a vendor zip."""

    source: Path
    symbols: list[Path] = Field(default_factory=list)
    footprints: list[Path] = Field(default_factory=list)
    models: list[Path] = Field(default_factory=list)
    layout: str = "unknown"


class PipelineResult(BaseModel):
    """What one fetch/import run wrote to disk."""

    part: PartDetails | None = None
    zip_path: Path | None = None
    extracted: ExtractedFiles | None = None
    part_dir: Path | None = None
    symbol_lib: Path | None = None
    footprint_lib: Path | None = None
    model_dir: Path | None = None
    files_written: list[Path] = Field(default_factory=list)


def _safe_token(value: str) -> str:
    cleaned = []
    for char in value.strip():
        if char.isalnum() or char in "._-":
            cleaned.append(char)
        elif char in " /\\":
            cleaned.append("_")
    return "".join(cleaned).strip("_")

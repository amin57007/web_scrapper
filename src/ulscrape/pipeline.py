"""End-to-end: Ultra Librarian URL or zip → KiCad library tree."""

from __future__ import annotations

from pathlib import Path

from ulscrape.config import Settings
from ulscrape.kicad.archive import extract_zip
from ulscrape.kicad.library import install_into_library
from ulscrape.models import PartDetails, PipelineResult
from ulscrape.scraper.export import fetch_details, queue_and_download
from ulscrape.scraper.session import build_client, save_cookies
from ulscrape.scraper.urls import parse_part_url


def fetch_part(
    url: str,
    settings: Settings | None = None,
    *,
    lib_name: str = "UltraLibrarian",
    overwrite: bool = True,
    export_ids: list[int] | None = None,
) -> PipelineResult:
    """Scrape a part page, download the KiCad+STEP zip, and install the library."""
    settings = settings or Settings.from_env()
    output = settings.output_dir
    output.mkdir(parents=True, exist_ok=True)

    if settings.use_browser:
        from ulscrape.scraper.browser import download_with_browser

        with build_client(settings) as client:
            details = fetch_details(client, url)
        zip_path = output / "downloads" / f"{details.ref.slug}.zip"
        zip_path, details = download_with_browser(url, zip_path, settings, export_ids=export_ids)
    else:
        with build_client(settings) as client:
            details = fetch_details(client, url)
            zip_path = output / "downloads" / f"{details.ref.slug}.zip"
            queue_and_download(client, details, zip_path, settings, export_ids=export_ids)
            if settings.cookies_path:
                save_cookies(client, settings.cookies_path)

    return import_zip(
        zip_path,
        output,
        lib_name=lib_name,
        overwrite=overwrite,
        details=details,
    )


def import_zip(
    zip_path: Path,
    output_dir: Path,
    *,
    lib_name: str = "UltraLibrarian",
    overwrite: bool = True,
    details: PartDetails | None = None,
) -> PipelineResult:
    """Install an already-downloaded Ultra Librarian (or similar) zip."""
    extract_root = output_dir / "downloads" / f"{zip_path.stem}_extracted"
    extracted = extract_zip(zip_path, extract_root)
    written = install_into_library(
        extracted,
        output_dir,
        lib_name=lib_name,
        details=details,
        overwrite=overwrite,
    )
    files = [path for path in written.values() if path.is_file()]
    files.extend(p for p in written["footprint_lib"].glob("*.kicad_mod"))
    if written["model_dir"].exists():
        files.extend(p for p in written["model_dir"].iterdir() if p.is_file())
    return PipelineResult(
        part=details,
        zip_path=zip_path,
        extracted=extracted,
        part_dir=written["part_dir"],
        symbol_lib=written.get("symbol_lib"),
        footprint_lib=written.get("footprint_lib"),
        model_dir=written.get("model_dir"),
        files_written=sorted(set(files)),
    )


def inspect_url(url: str, settings: Settings | None = None) -> PartDetails:
    """Fetch public part metadata without downloading CAD files."""
    settings = settings or Settings.from_env()
    parse_part_url(url, base_url=settings.base_url)
    with build_client(settings) as client:
        return fetch_details(client, url)

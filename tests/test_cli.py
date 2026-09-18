from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ulscrape.cli import app
from ulscrape.errors import AuthError, ExportError
from ulscrape.pipeline import import_zip
from ulscrape.scraper.details import parse_details_html

runner = CliRunner()

OPA_URL = (
    "https://app.ultralibrarian.com/details/"
    "1621ae5d-103f-11e9-ab3a-0a3560a4cccc/Texas-Instruments/OPA2374AIDR"
)


def test_cli_import_zip(ul_zip: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["import-zip", str(ul_zip), "-o", str(tmp_path / "libraries")],
    )
    assert result.exit_code == 0, result.output
    assert "symbols=1" in result.output
    assert "footprints=1" in result.output
    assert "models=1" in result.output
    lib = tmp_path / "libraries" / "UltraLibrarian.kicad_sym"
    assert lib.exists()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "fetch" in result.output
    assert "import-zip" in result.output


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_info(details_html: str, monkeypatch: pytest.MonkeyPatch) -> None:
    details = parse_details_html(details_html, page_url=OPA_URL)
    monkeypatch.setattr("ulscrape.cli.inspect_url", lambda _url: details)
    result = runner.invoke(app, ["info", OPA_URL])
    assert result.exit_code == 0, result.output
    assert "OPA2374AIDR" in result.output
    assert "Texas Instruments" in result.output
    assert "KiCAD v6+" in result.output
    assert "CAD download requires" in result.output


def test_cli_info_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_url: str) -> None:
        raise ExportError("could not load details")

    monkeypatch.setattr("ulscrape.cli.inspect_url", boom)
    result = runner.invoke(app, ["info", OPA_URL])
    assert result.exit_code == 1
    assert "could not load details" in result.output


def test_cli_fetch_auth_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AuthError("Ultra Librarian requires a free account")

    monkeypatch.setattr("ulscrape.cli.fetch_part", boom)
    result = runner.invoke(app, ["fetch", OPA_URL, "-o", str(tmp_path), "--http"])
    assert result.exit_code == 1
    assert "free account" in result.output


def test_cli_fetch_success(
    ul_zip: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    libraries = tmp_path / "libraries"

    def fake_fetch(_url: str, _settings: object, lib_name: str = "UltraLibrarian"):
        return import_zip(ul_zip, libraries, lib_name=lib_name)

    monkeypatch.setattr("ulscrape.cli.fetch_part", fake_fetch)
    result = runner.invoke(app, ["fetch", OPA_URL, "-o", str(libraries), "--http"])
    assert result.exit_code == 0, result.output
    assert "symbols=1" in result.output
    assert (libraries / "UltraLibrarian.kicad_sym").exists()


def test_cli_import_zip_missing(tmp_path: Path) -> None:
    result = runner.invoke(app, ["import-zip", str(tmp_path / "missing.zip")])
    assert result.exit_code == 1
    assert "zip not found" in result.output

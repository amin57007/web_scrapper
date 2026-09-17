from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ulscrape.cli import app

runner = CliRunner()


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

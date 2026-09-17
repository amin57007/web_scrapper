"""Command-line interface for Ultra Librarian → KiCad."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ulscrape import __version__
from ulscrape.config import Settings
from ulscrape.errors import UlscrapeError
from ulscrape.pipeline import fetch_part, import_zip, inspect_url

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Download Ultra Librarian IC CAD files and install them as KiCad libraries.",
)
console = Console()


def _settings(
    output: Path,
    cookies: Path | None,
    email: str | None,
    password: str | None,
    captcha_key: str | None = None,
    use_browser: bool | None = None,
    headed: bool | None = None,
    storage: Path | None = None,
) -> Settings:
    return Settings.from_env(
        output_dir=output,
        cookies_path=cookies,
        email=email,
        password=password,
        captcha_api_key=captcha_key,
        use_browser=use_browser,
        headed=headed,
        storage_state_path=storage,
    )


@app.callback()
def _version_flag(
    version: Annotated[
        bool, typer.Option("--version", help="Show version and exit.")
    ] = False,
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit()


@app.command("info")
def info_cmd(
    url: Annotated[str, typer.Argument(help="Ultra Librarian details URL or part UUID.")],
) -> None:
    """Scrape public part metadata (symbol/footprint/3D availability). No login."""
    try:
        details = inspect_url(url)
    except UlscrapeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[bold]{details.ref.manufacturer} {details.ref.mpn}[/bold]")
    console.print(details.description)
    console.print(f"UUID: {details.ref.part_uuid}")
    if details.status:
        console.print(f"Status: {details.status}")
    if details.datasheet_url:
        console.print(f"Datasheet: {details.datasheet_url}")
    table = Table(title="CAD formats")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Symbol")
    table.add_column("Footprint")
    table.add_column("3D")
    for fmt in details.formats:
        table.add_row(
            str(fmt.export_id),
            fmt.label,
            "yes" if fmt.has_symbol else "",
            "yes" if fmt.has_footprint else "",
            "yes" if fmt.has_3d else "",
        )
    console.print(table)
    if details.login_required:
        console.print(
            "[yellow]CAD download requires a free Ultra Librarian login "
            "(UL_EMAIL / UL_PASSWORD or --cookies).[/yellow]"
        )


@app.command("fetch")
def fetch_cmd(
    url: Annotated[str, typer.Argument(help="Ultra Librarian details URL or part UUID.")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="KiCad library output directory.")
    ] = Path("libraries"),
    lib_name: Annotated[str, typer.Option("--lib-name", help="KiCad library nickname.")] = (
        "UltraLibrarian"
    ),
    cookies: Annotated[
        Path | None,
        typer.Option("--cookies", help="JSON or Netscape cookie file from a signed-in browser."),
    ] = None,
    email: Annotated[
        str | None, typer.Option("--email", envvar="UL_EMAIL", help="Ultra Librarian email.")
    ] = None,
    password: Annotated[
        str | None,
        typer.Option("--password", envvar="UL_PASSWORD", help="Ultra Librarian password."),
    ] = None,
    captcha_key: Annotated[
        str | None,
        typer.Option(
            "--captcha-key",
            envvar="TWOCAPTCHA_API_KEY",
            help="2Captcha or CapSolver API key used when the checkbox is not enough.",
        ),
    ] = None,
    browser: Annotated[
        bool,
        typer.Option("--browser/--http", help="Drive Chrome (handles reCAPTCHA). Default: Chrome."),
    ] = True,
    headed: Annotated[
        bool,
        typer.Option("--headed", help="Show the Chrome window (also UL_HEADED=1)."),
    ] = False,
    storage: Annotated[
        Path | None,
        typer.Option("--storage", help="Playwright storage_state.json to reuse a signed-in session."),
    ] = None,
) -> None:
    """Log in, complete reCAPTCHA, download KiCad + STEP, and install the library."""
    settings = _settings(
        output,
        cookies,
        email,
        password,
        captcha_key=captcha_key,
        use_browser=browser,
        headed=True if headed else None,
        storage=storage,
    )
    try:
        result = fetch_part(url, settings, lib_name=lib_name)
    except UlscrapeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    _print_result(result)


@app.command("import-zip")
def import_cmd(
    zip_path: Annotated[Path, typer.Argument(help="Already-downloaded Ultra Librarian zip.")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="KiCad library output directory.")
    ] = Path("libraries"),
    lib_name: Annotated[str, typer.Option("--lib-name", help="KiCad library nickname.")] = (
        "UltraLibrarian"
    ),
) -> None:
    """Install symbol, footprint, and 3D model files from a local zip."""
    if not zip_path.is_file():
        console.print(f"[red]zip not found: {zip_path}[/red]")
        raise typer.Exit(1)
    try:
        result = import_zip(zip_path, output, lib_name=lib_name)
    except UlscrapeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    _print_result(result)


def _print_result(result: object) -> None:
    from ulscrape.models import PipelineResult

    assert isinstance(result, PipelineResult)
    if result.part:
        console.print(f"[green]Imported {result.part.ref.manufacturer} {result.part.ref.mpn}[/green]")
    if result.extracted:
        console.print(
            f"layout={result.extracted.layout}  "
            f"symbols={len(result.extracted.symbols)}  "
            f"footprints={len(result.extracted.footprints)}  "
            f"models={len(result.extracted.models)}"
        )
    if result.symbol_lib:
        console.print(f"symbol library : {result.symbol_lib}")
    if result.footprint_lib:
        console.print(f"footprint lib  : {result.footprint_lib}")
    if result.model_dir:
        console.print(f"3D models      : {result.model_dir}")
    if result.part_dir:
        console.print(f"part folder    : {result.part_dir}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

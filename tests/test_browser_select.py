from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import export_panel_html
from ulscrape.config import Settings
from ulscrape.errors import AuthError, CaptchaError, ExportError
from ulscrape.models import CadFormat, PartDetails, PartRef
from ulscrape.scraper.browser import (
    _accept_required_consents,
    _check_hidden_input,
    _login,
    _open_export_panel,
    _select_kicad_and_step,
    _solve_export_captcha,
    _submit_and_download,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _dummy_details() -> PartDetails:
    return PartDetails(ref=PartRef(part_uuid="00000000-0000-0000-0000-000000000000"))


def _details_with(*formats: CadFormat) -> PartDetails:
    return PartDetails(
        ref=PartRef(part_uuid="00000000-0000-0000-0000-000000000000"),
        formats=list(formats),
    )


@pytest.fixture(scope="module")
def chromium_browser():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    try:
        try:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium not available: {exc}")
        yield browser
        browser.close()
    finally:
        playwright.stop()


@pytest.fixture
def page(chromium_browser):
    page = chromium_browser.new_page()
    try:
        yield page
    finally:
        page.close()


def test_select_kicad_and_step_in_collapsed_accordion(page) -> None:
    html = (FIXTURES / "export_panel_collapsed.html").read_text(encoding="utf-8")
    page.set_content(html)
    assert not page.locator("#KiCADv6").is_visible()
    _select_kicad_and_step(page, _dummy_details(), export_ids=[42, 37])
    assert page.locator("#KiCADv6").is_checked()
    assert page.locator("#MfrThreeDModel").is_checked()
    assert not page.locator("#KiCAD").is_checked()


def test_select_collapsed_adi_step_id_21(page) -> None:
    page.set_content(
        export_panel_html(collapsed=True, step_id="ThreeDModel", step_value=21)
    )
    assert not page.locator("#ThreeDModel").is_visible()
    details = _details_with(
        CadFormat(html_id="KiCADv6", export_id=42, label="KiCAD v6+", has_symbol=True),
        CadFormat(html_id="ThreeDModel", export_id=21, label="STEP", has_3d=True),
    )
    _select_kicad_and_step(page, details, export_ids=None)
    assert page.locator("#KiCADv6").is_checked()
    assert page.locator("#ThreeDModel").is_checked()
    assert not page.locator("#KiCAD").is_checked()


def test_select_already_expanded_checkboxes(page) -> None:
    page.set_content(export_panel_html(collapsed=False))
    assert page.locator("#KiCADv6").count() == 1
    _select_kicad_and_step(page, _dummy_details(), export_ids=[42, 37])
    assert page.locator("#KiCADv6").is_checked()
    assert page.locator("#MfrThreeDModel").is_checked()


def test_select_kicad_v5_when_v6_missing(page) -> None:
    page.set_content(export_panel_html(collapsed=True, kicad_v6=False))
    details = _details_with(
        CadFormat(html_id="KiCAD", export_id=24, label="KiCAD v5", has_symbol=True),
        CadFormat(html_id="MfrThreeDModel", export_id=37, label="STEP", has_3d=True),
    )
    _select_kicad_and_step(page, details, export_ids=None)
    assert page.locator("#KiCAD").is_checked()
    assert page.locator("#MfrThreeDModel").is_checked()
    assert page.locator("#KiCADv6").count() == 0


def test_select_fallback_ids_when_formats_unparsed(page) -> None:
    extra = (
        '<input id="ThreeDModel" name="exports" type="checkbox" value="21" '
        'class="custom-control-input export-option">'
        '<label for="ThreeDModel">STEP</label>'
    )
    page.set_content(
        export_panel_html(collapsed=True, extra_step=extra)
    )
    _select_kicad_and_step(page, _dummy_details(), export_ids=None)
    assert page.locator("#KiCADv6").is_checked()
    assert page.locator("#MfrThreeDModel").is_checked()
    assert page.locator("#ThreeDModel").is_checked()


def test_select_explicit_export_ids_still_ticks_step_widgets(page) -> None:
    extra = (
        '<input id="ThreeDModel" name="exports" type="checkbox" value="21" '
        'class="custom-control-input export-option">'
        '<label for="ThreeDModel">STEP</label>'
    )
    page.set_content(export_panel_html(collapsed=True, extra_step=extra))
    _select_kicad_and_step(page, _dummy_details(), export_ids=[42])
    assert page.locator("#KiCADv6").is_checked()
    assert page.locator("#MfrThreeDModel").is_checked()
    assert page.locator("#ThreeDModel").is_checked()


def test_hidden_checkbox_stays_checked_when_set_twice(page) -> None:
    page.set_content(export_panel_html(collapsed=True))
    locator = page.locator("#KiCADv6")
    assert _check_hidden_input(locator)
    assert locator.is_checked()
    assert _check_hidden_input(locator)
    assert locator.is_checked()


def test_check_hidden_input_missing_locator(page) -> None:
    page.set_content("<html><body></body></html>")
    assert _check_hidden_input(page.locator("#KiCADv6")) is False


def test_accept_required_consents(page) -> None:
    page.set_content(export_panel_html(collapsed=True, consents=True))
    _accept_required_consents(page)
    assert page.locator("#consent1").is_checked()
    assert page.locator("#consent2").is_checked()


def test_open_export_panel_expands_collapsed_groups(page) -> None:
    page.set_content(export_panel_html(collapsed=True))
    page.wait_for_timeout = lambda _ms: None  # type: ignore[method-assign]
    _open_export_panel(page)
    assert page.locator("#KiCADv6").evaluate("el => el.closest('.collapse').classList.contains('show')")


def test_submit_missing_button_raises(page, tmp_path: Path) -> None:
    page.set_content(export_panel_html(collapsed=False, submit=False))
    with pytest.raises(ExportError, match="submit button"):
        _submit_and_download(page, tmp_path / "out.zip", Settings(poll_timeout_s=2))


def test_submit_downloads_zip(page, tmp_path: Path) -> None:
    html = export_panel_html(collapsed=False, submit=True)
    html = html.replace(
        "</body>",
        """
<script>
document.getElementById("submit-export").addEventListener("click", () => {
  const bytes = new Uint8Array(128);
  bytes[0] = 0x50; bytes[1] = 0x4b;
  const blob = new Blob([bytes], {type: "application/zip"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "cad.zip";
  document.body.appendChild(a);
  a.click();
});
</script>
</body>""",
    )
    page.set_content(html)
    dest = tmp_path / "cad.zip"
    saved = _submit_and_download(page, dest, Settings(poll_timeout_s=10))
    assert saved == dest
    assert dest.stat().st_size >= 64


def test_solve_export_captcha_skips_when_absent(page) -> None:
    page.set_content("<html><body><p>no widget</p></body></html>")
    _solve_export_captcha(page, Settings())


def test_solve_export_captcha_already_solved(page) -> None:
    page.set_content(
        """
        <div class="g-recaptcha" data-sitekey="6LeTestSiteKeyValueXXXXXX"></div>
        <textarea name="g-recaptcha-response">xxxxxxxxxxxxxxxxxxxxxTOKEN</textarea>
        """
    )
    _solve_export_captcha(page, Settings(llm_api_key=None, captcha_api_key=None))


def test_solve_export_captcha_raises_without_keys(page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ulscrape.scraper.browser._click_recaptcha_checkbox", lambda _p: False)
    monkeypatch.setattr(
        "ulscrape.scraper.browser._wait_for_recaptcha_token",
        lambda _p, timeout_ms=0: False,
    )
    monkeypatch.setattr("ulscrape.scraper.browser._recaptcha_already_solved", lambda _p: False)
    monkeypatch.setattr("ulscrape.scraper.browser.discover_llm", lambda **_k: None)
    page.set_content('<div class="g-recaptcha" data-sitekey="6LeTestSiteKeyValueXXXXXX"></div>')
    page.wait_for_timeout = lambda _ms: None  # type: ignore[method-assign]
    with pytest.raises(CaptchaError, match="was not solved"):
        _solve_export_captcha(page, Settings(llm_api_key=None, captcha_api_key=None))


def test_solve_export_captcha_missing_sitekey(page, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ulscrape.scraper.browser._click_recaptcha_checkbox", lambda _p: False)
    monkeypatch.setattr(
        "ulscrape.scraper.browser._wait_for_recaptcha_token",
        lambda _p, timeout_ms=0: False,
    )
    monkeypatch.setattr("ulscrape.scraper.browser._recaptcha_already_solved", lambda _p: False)
    monkeypatch.setattr("ulscrape.scraper.browser.discover_llm", lambda **_k: None)
    page.set_content('<div class="g-recaptcha"></div>')
    page.wait_for_timeout = lambda _ms: None  # type: ignore[method-assign]
    with pytest.raises(CaptchaError, match="no sitekey"):
        _solve_export_captcha(page, Settings(llm_api_key=None, captcha_api_key=None))


def test_login_requires_credentials() -> None:
    with pytest.raises(AuthError, match="UL_EMAIL"):
        _login(object(), Settings(email=None, password=None))

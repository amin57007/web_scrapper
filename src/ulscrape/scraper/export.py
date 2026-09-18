"""Queue and download Ultra Librarian CAD exports (KiCad + STEP)."""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlencode

import httpx

from ulscrape.config import DEFAULT_EXPORT_IDS, Settings
from ulscrape.errors import AuthError, ExportError
from ulscrape.models import PartDetails
from ulscrape.scraper import session as sess
from ulscrape.scraper.details import parse_details_html
from ulscrape.scraper.urls import details_url, parse_part_url

QUEUE_READY = 2
QUEUE_FAILED = {3, 4}


def fetch_details(client: httpx.Client, url: str) -> PartDetails:
    """GET a public details page and parse it."""
    ref = parse_part_url(url, base_url=str(client.base_url))
    try:
        page = client.get(details_url(ref, base_url=str(client.base_url)))
        page.raise_for_status()
    except httpx.HTTPError as exc:
        raise ExportError(f"could not load Ultra Librarian details page: {exc}") from exc
    details = parse_details_html(page.text, page_url=str(page.url))
    if not details.ref.url:
        details.ref.url = str(page.url)
    return details


def queue_and_download(
    client: httpx.Client,
    details: PartDetails,
    dest_zip: Path,
    settings: Settings,
    export_ids: Sequence[int] | None = None,
) -> Path:
    """Submit /Export/QueueExport, poll CheckQueue, then save the zip."""
    if details.login_required and not sess.is_authenticated(
        client.get(details.ref.url or details_url(details.ref)).text
    ):
        if settings.email and settings.password:
            sess.login(client, settings.email, settings.password)
        else:
            raise AuthError(
                "Ultra Librarian requires a free account to download CAD files. "
                "Set UL_EMAIL and UL_PASSWORD, or pass --cookies from a signed-in browser."
            )

    page = client.get(details.ref.url or details_url(details.ref))
    page.raise_for_status()
    live = parse_details_html(page.text, page_url=str(page.url))
    if live.login_required:
        raise AuthError("still logged out after authentication; CAD download is blocked")

    chosen = list(export_ids or _default_export_ids(live))
    if not chosen:
        raise ExportError("no KiCad/STEP export IDs available for this part")

    token = _queue_export(client, live, chosen, page_url=str(page.url))
    _poll_queue(client, token, settings)
    return _download_zip(client, token, dest_zip)


def _default_export_ids(details: PartDetails) -> list[int]:
    ids: list[int] = []
    kicad = details.kicad_v6() or details.kicad_v5()
    if kicad:
        ids.append(kicad.export_id)
    step = details.step_format()
    if step:
        ids.append(step.export_id)
    if not ids:
        ids.extend(DEFAULT_EXPORT_IDS)
    return ids


def _csrf_headers(token: str | None) -> dict[str, str]:
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    if token:
        headers["RequestVerificationToken"] = token
    return headers


def _queue_export(
    client: httpx.Client,
    details: PartDetails,
    export_ids: Sequence[int],
    *,
    page_url: str,
) -> str:
    data: list[tuple[str, str]] = [
        ("PartUniqueId", details.ref.part_uuid),
        ("BxlToken", ""),
        ("AdvertiserReferrerTag", ""),
        ("AdvertiserTerm", ""),
        ("DistributorUniqueIds", ""),
        ("current_url", page_url),
    ]
    for export_id in export_ids:
        data.append(("exports", str(export_id)))

    encoded = urlencode(data, doseq=True)
    response = client.post(
        "/Export/QueueExport",
        content=encoded.encode("utf-8"),
        headers=_csrf_headers(details.csrf_token),
    )
    if response.status_code in {401, 403}:
        raise AuthError("QueueExport rejected the session (login required)")
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise ExportError(
            "QueueExport did not return JSON. The site may be showing a captcha or login wall."
        ) from exc

    if not payload.get("success"):
        message = payload.get("message") or "QueueExport failed"
        raise ExportError(str(message))
    token = payload.get("encoded_token")
    if not token:
        raise ExportError("QueueExport succeeded but returned no encoded_token")
    return str(token)


def _poll_queue(client: httpx.Client, token: str, settings: Settings) -> None:
    deadline = time.monotonic() + settings.poll_timeout_s
    url = f"/Export/CheckQueue?queueToken={token}"
    while time.monotonic() < deadline:
        response = client.get(
            url,
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExportError("CheckQueue returned non-JSON") from exc
        state = payload.get("state")
        if state == QUEUE_READY:
            return
        if state in QUEUE_FAILED:
            raise ExportError(f"CAD export queue failed (state={state})")
        time.sleep(settings.poll_interval_s)
    raise ExportError(f"CAD export timed out after {settings.poll_timeout_s:.0f}s")


def _download_zip(client: httpx.Client, token: str, dest_zip: Path) -> Path:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with client.stream("GET", f"/Export/Download?queueToken={token}") as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" in content_type.lower():
            raise ExportError("Download returned HTML instead of a zip (login or captcha?)")
        with dest_zip.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    if dest_zip.stat().st_size < 64:
        raise ExportError(f"downloaded file is too small: {dest_zip}")
    return dest_zip

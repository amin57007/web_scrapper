"""Parse public Ultra Librarian details HTML (no login required)."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ulscrape.errors import DetailsParseError
from ulscrape.models import CadFormat, PartDetails, PartRef
from ulscrape.scraper.urls import parse_part_url

_PART_ID_RE = re.compile(r"pricinghandler\.PartId\s*=\s*(\d+)")
_UUID_JS_RE = re.compile(
    r"pricinghandler\.PartUniqueId\s*=\s*\"([0-9a-fA-F-]{36})\"",
    re.IGNORECASE,
)


def parse_details_html(
    html: str,
    *,
    page_url: str = "https://app.ultralibrarian.com/",
) -> PartDetails:
    """Extract part metadata and CAD format checkboxes from a details page."""
    soup = BeautifulSoup(html, "lxml")

    ref = _parse_ref(soup, html, page_url)
    formats = _parse_formats(soup)
    if not formats:
        raise DetailsParseError("no CAD export formats found on details page")

    header = soup.select_one("h1.part-detail-mfr-header")
    if header:
        spans = [s.get_text(strip=True) for s in header.find_all("span")]
        if len(spans) >= 1 and not ref.manufacturer:
            ref.manufacturer = spans[0]
        if len(spans) >= 2 and not ref.mpn:
            ref.mpn = spans[1]

    description_el = soup.select_one(".part-detail-description")
    description = ""
    if description_el:
        raw_title = description_el.get("title")
        if isinstance(raw_title, list):
            description = str(raw_title[0]).strip() if raw_title else ""
        elif raw_title:
            description = str(raw_title).strip()
        if not description:
            description = description_el.get_text(strip=True)

    status = ""
    for div in soup.find_all("div", title=True):
        if "Status:" in div.get_text():
            status = str(div.get("title") or "").strip()
            if not status:
                status = div.get_text(strip=True).replace("Status:", "").strip()
            break

    datasheet = soup.find("a", string=re.compile(r"^\s*Datasheet\s*$", re.I))
    datasheet_url = None
    if isinstance(datasheet, Tag) and datasheet.get("href"):
        datasheet_url = urljoin(page_url, str(datasheet["href"]))

    preview = soup.select_one("iframe[title*='3D'], .preview-3d--container iframe")
    preview_3d_url = None
    if isinstance(preview, Tag) and preview.get("src"):
        preview_3d_url = str(preview["src"])

    csrf_el = soup.find("input", attrs={"name": "__RequestVerificationToken"})
    csrf_token = None
    if isinstance(csrf_el, Tag):
        csrf_token = str(csrf_el.get("value") or "") or None

    unique_el = soup.find("input", attrs={"id": "PartUniqueId"})
    if isinstance(unique_el, Tag) and unique_el.get("value"):
        ref.part_uuid = str(unique_el["value"]).lower()

    part_id = None
    match = _PART_ID_RE.search(html)
    if match:
        part_id = int(match.group(1))

    login_required = soup.select_one("a.login-return-url") is not None or bool(
        soup.find("a", string=re.compile(r"Login to Download", re.I))
    )

    return PartDetails(
        ref=ref,
        description=description,
        status=status,
        datasheet_url=datasheet_url,
        part_id=part_id,
        preview_3d_url=preview_3d_url,
        csrf_token=csrf_token,
        login_required=login_required,
        formats=formats,
    )


def _parse_ref(soup: BeautifulSoup, html: str, page_url: str) -> PartRef:
    canonical = soup.find("link", rel="canonical")
    href = ""
    if isinstance(canonical, Tag):
        href = str(canonical.get("href") or "")
    candidate = href or page_url
    try:
        ref = parse_part_url(candidate)
    except Exception:
        js_uuid = _UUID_JS_RE.search(html)
        if not js_uuid:
            raise DetailsParseError("could not find part UUID on details page") from None
        ref = PartRef(part_uuid=js_uuid.group(1).lower(), url=page_url)

    preview_parent = soup.select_one("#preview-parent")
    if isinstance(preview_parent, Tag):
        if preview_parent.get("data-mfrname") and not ref.manufacturer:
            ref.manufacturer = str(preview_parent["data-mfrname"])
        if preview_parent.get("data-mfrpn") and not ref.mpn:
            ref.mpn = str(preview_parent["data-mfrpn"])
    if not ref.url:
        ref.url = page_url
    return ref


def _parse_formats(soup: BeautifulSoup) -> list[CadFormat]:
    formats: list[CadFormat] = []
    seen: set[int] = set()
    for inp in soup.select('input.export-option[name="exports"]'):
        if not isinstance(inp, Tag):
            continue
        raw_id = inp.get("value")
        html_id = str(inp.get("id") or "")
        if raw_id is None:
            continue
        try:
            export_id = int(str(raw_id))
        except ValueError:
            continue
        if export_id in seen:
            continue
        seen.add(export_id)
        label_el = soup.find("label", attrs={"for": html_id})
        label = html_id
        has_symbol = has_footprint = has_3d = False
        if isinstance(label_el, Tag):
            label = label_el.get_text(" ", strip=True) or html_id
            for img in label_el.find_all("img"):
                title = str(img.get("title") or "").lower()
                if "symbol" in title:
                    has_symbol = True
                if "footprint" in title:
                    has_footprint = True
                if "3d" in title:
                    has_3d = True
        formats.append(
            CadFormat(
                html_id=html_id,
                export_id=export_id,
                label=label,
                has_symbol=has_symbol,
                has_footprint=has_footprint,
                has_3d=has_3d,
            )
        )
    return formats

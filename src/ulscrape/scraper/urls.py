"""Parse Ultra Librarian part URLs into a PartRef."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from ulscrape.errors import UrlParseError
from ulscrape.models import PartRef

# https://app.ultralibrarian.com/details/{uuid}/{manufacturer}/{mpn}
_DETAILS_RE = re.compile(
    r"/details/(?P<uuid>[0-9a-fA-F-]{36})(?:/(?P<mfr>[^/?#]+))?(?:/(?P<mpn>[^/?#]+))?",
    re.IGNORECASE,
)

# https://cad.ultralibrarian.com/orcad/Home?partUuid=...&mfr=...&mpn=...
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def parse_part_url(value: str, *, base_url: str = "https://app.ultralibrarian.com") -> PartRef:
    """Accept a details URL, CAD portal URL, or a bare UUID."""
    text = value.strip()
    if not text:
        raise UrlParseError("empty Ultra Librarian URL")

    if _UUID_RE.match(text):
        uuid = text.lower()
        return PartRef(
            part_uuid=uuid,
            url=f"{base_url.rstrip('/')}/details/{uuid}",
        )

    parsed = urlparse(text)
    if not parsed.scheme:
        parsed = urlparse("https://" + text)

    match = _DETAILS_RE.search(parsed.path)
    if match:
        uuid = match.group("uuid").lower()
        mfr = unquote(match.group("mfr") or "").replace("-", " ").strip()
        mpn = unquote(match.group("mpn") or "").strip()
        host = parsed.netloc or "app.ultralibrarian.com"
        path = f"/details/{uuid}"
        if match.group("mfr"):
            path += f"/{match.group('mfr')}"
        if match.group("mpn"):
            path += f"/{match.group('mpn')}"
        return PartRef(
            part_uuid=uuid,
            manufacturer=mfr,
            mpn=mpn,
            url=f"{parsed.scheme}://{host}{path}",
        )

    query = parse_qs(parsed.query)
    uuid = (query.get("partUuid") or query.get("partUniqueId") or [""])[0]
    if uuid and _UUID_RE.match(uuid):
        mfr = (query.get("mfr") or [""])[0]
        mpn = (query.get("mpn") or [""])[0]
        return PartRef(
            part_uuid=uuid.lower(),
            manufacturer=mfr.replace("-", " "),
            mpn=mpn,
            url=f"{base_url.rstrip('/')}/details/{uuid.lower()}",
        )

    raise UrlParseError(
        f"not an Ultra Librarian part URL: {value!r}. "
        "Expected /details/<uuid>/<mfr>/<mpn> or ?partUuid=<uuid>"
    )


def details_url(ref: PartRef, *, base_url: str = "https://app.ultralibrarian.com") -> str:
    """Build the canonical app.ultralibrarian.com details URL for a part."""
    if ref.url and "/details/" in ref.url:
        return ref.url
    parts = [base_url.rstrip("/"), "details", ref.part_uuid]
    if ref.manufacturer:
        parts.append(ref.manufacturer.replace(" ", "-"))
    if ref.mpn:
        parts.append(ref.mpn)
    return "/".join(parts)

# Ultra Librarian scrape and download

Observed from the live site `app.ultralibrarian.com` (anonymous details page
for Texas Instruments OPA2374AIDR) and from `/js/handler.min.js`.

## Part URL forms

All of these are accepted by `ulscrape.scraper.urls.parse_part_url`:

```
https://app.ultralibrarian.com/details/<uuid>/<Manufacturer>/<MPN>
https://cad.ultralibrarian.com/orcad/Home?partUuid=<uuid>&mfr=...&mpn=...
<uuid>
```

Example:

https://app.ultralibrarian.com/details/1621AE5D-103F-11E9-AB3A-0A3560A4CCCC/Texas-Instruments/OPA2374AIDR

## Public details page (no login)

`GET /details/<uuid>/...` returns HTML that includes:

| Field | Where |
|---|---|
| Canonical URL | `<link rel="canonical">` |
| Manufacturer / MPN | `h1.part-detail-mfr-header` spans |
| Description | `.part-detail-description` |
| Status | `div[title]` containing `Status:` |
| Datasheet | `a` whose text is `Datasheet` |
| 3D preview iframe | `https://3d.ultralibrarian.com/<uuid>` |
| Part UUID | `#PartUniqueId` |
| Numeric part id | `pricinghandler.PartId = …` |
| CAD checkboxes | `input.export-option[name=exports]` |
| CSRF | `input[name=__RequestVerificationToken]` |

Live export checkbox values used by this tool:

| `id` | `value` | Label |
|---|---|---|
| `KiCAD` | **24** | KiCAD v5 |
| `KiCADv6` | **42** | KiCAD v6+ |
| `MfrThreeDModel` | **37** | STEP |
| `IGES` | 45 | IGES v5.3 |
| `STL` | 57 | STL |

KiCad v6+ checkboxes advertise symbol + footprint. STEP is a separate 3D
export. `ulscrape fetch` requests **42 and 37** so the zip contains both
the KiCad library and a STEP model.

Anonymous pages show `Login to Download`. That is why `info` works without
credentials and `fetch` does not.

## Authenticated CAD download

The details page wires:

```javascript
ultralibrarian.exporthandler.SetupExportDownload(
  "/Account/SubmitAgreement",
  "/Export/CheckQueue?queueToken=",
  "/Export/Download?queueToken="
);
```

The form `#export-submission-form` posts to `/Export/QueueExport`.

Flow implemented in `ulscrape.scraper.export`:

1. Sign in (`/Account/Login` with `Username` / `Password`, then follow any
   OIDC `id_token` auto-post form) **or** load cookies from `--cookies`.
2. Re-fetch the details page (need a fresh CSRF token while authenticated).
3. `POST /Export/QueueExport` as `application/x-www-form-urlencoded` with
   `PartUniqueId`, repeated `exports=<id>`, `current_url`, and header
   `RequestVerificationToken`.
4. JSON response `{ "success": true, "encoded_token": "..." }`.
5. Poll `GET /Export/CheckQueue?queueToken=...` every 2 seconds.
   - `state == 2` ready
   - `state in {3, 4}` failed
6. `GET /Export/Download?queueToken=...` → zip bytes.

If the response is HTML instead of JSON/zip, the site is showing a login
wall or captcha. Export cookies from a signed-in browser and pass
`--cookies`.

## Environment

| Variable | Meaning |
|---|---|
| `UL_EMAIL` | Account email |
| `UL_PASSWORD` | Account password |
| `UL_COOKIES` | Path to JSON `{name: value}` or Netscape cookies |
| `UL_OUTPUT` | Default output directory |
| `UL_BASE_URL` | Override API host (tests) |

## Terms

CAD content is provided by Ultra Librarian for use in your own PCB designs
under their terms of use. This client automates the same download a browser
performs with **your** account. It does not bypass payment, captcha, or
access controls.

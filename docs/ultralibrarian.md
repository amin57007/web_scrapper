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
Google reCAPTCHA v2 is on that form after login: callbacks `captchaValid` /
`captchaInvalid`, widget `.g-recaptcha`, and `grecaptcha.reset()` after submit.

`ulscrape fetch` **defaults to Chrome (Playwright)** so it can:

1. Open the part URL and click **Download Now**
2. Sign in with `UL_EMAIL` / `UL_PASSWORD` (IdentityServer + OIDC form_post)
3. Check KiCad v6+ (`#KiCADv6`) and STEP (`#MfrThreeDModel`)
4. Tick required consent boxes
5. Complete reCAPTCHA:
   - click the "I'm not a robot" checkbox in the recaptcha iframe
   - if that is not enough, send the sitekey to 2Captcha or CapSolver and
     inject `g-recaptcha-response`, then call `captchaValid()`
6. Click `#submit-export` and save the browser download as a zip

`--http` uses the raw endpoints without a browser (no reCAPTCHA widget):

1. `POST /Export/QueueExport` with `PartUniqueId`, `exports=42`, `exports=37`
2. Poll `GET /Export/CheckQueue?queueToken=...` (`state == 2` ready)
3. `GET /Export/Download?queueToken=...`

## Environment

| Variable | Meaning |
|---|---|
| `UL_EMAIL` | Account email |
| `UL_PASSWORD` | Account password |
| `UL_STORAGE` | Playwright `storage_state.json` to reuse a session |
| `TWOCAPTCHA_API_KEY` | 2Captcha key for reCAPTCHA v2 |
| `CAPSOLVER_API_KEY` | CapSolver key (used if 2Captcha is unset) |
| `UL_HEADED` | `1` to show the Chrome window |
| `UL_USE_BROWSER` | `0` to force the HTTP-only path |
| `UL_COOKIES` | Path to JSON `{name: value}` or Netscape cookies (HTTP path) |
| `UL_OUTPUT` | Default output directory |
| `UL_BASE_URL` | Override API host (tests) |

## Terms

CAD content is provided by Ultra Librarian for use in your own PCB designs
under their terms of use. This client automates the same login, reCAPTCHA,
and download a browser performs with **your** account. It does not bypass
payment or invent recaptcha tokens.

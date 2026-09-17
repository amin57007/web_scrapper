# Architecture

`ulscrape` is a small pipeline: **URL → public HTML → (optional login) → CAD zip → KiCad library**.

```
Ultra Librarian URL
        │
        ▼
  scraper.urls.parse_part_url
        │
        ▼
  scraper.export.fetch_details     (GET /details/…, no login)
        │
        ├─ info command stops here
        │
        ▼
  scraper.browser.download_with_browser   (Chrome: login, reCAPTCHA, download)
        │  or scraper.export.queue_and_download when --http
        ▼
  kicad.archive.extract_zip        (KiCAD / KiCADv6 / STEP layouts)
        │
        ▼
  kicad.library.install_into_library
        │
        ▼
  libraries/UltraLibrarian.{kicad_sym,pretty,3dshapes}
```

## Packages

| Path | Responsibility |
|---|---|
| `ulscrape.scraper.urls` | Parse details URLs, CAD-portal query strings, bare UUIDs |
| `ulscrape.scraper.details` | BeautifulSoup parse of the public details page |
| `ulscrape.scraper.session` | httpx client, cookie jar, IdentityServer login + OIDC form_post |
| `ulscrape.scraper.export` | Queue / poll / download CAD zip |
| `ulscrape.kicad.archive` | Zip-slip checks, layout detection, extract symbol/footprint/3D |
| `ulscrape.kicad.sexpr` | Small s-expression walker (no kiutils dependency) |
| `ulscrape.kicad.library` | Merge `.kicad_sym`, copy `.pretty` + `.3dshapes`, lib tables |
| `ulscrape.pipeline` | Glue used by the CLI |
| `ulscrape.cli` | Typer commands: `info`, `fetch`, `import-zip` |

## Design constraints

- **No KiCad install required to run tests.** Fixtures are synthetic Ultra Librarian zips.
- **Login is optional for metadata.** `info` only hits the public details page.
- **CAD download uses the user's account.** Credentials stay in env vars / a cookie file; they are never logged. reCAPTCHA is completed in Chrome (checkbox click, then an agentic vision-LLM loop on the image grid, then 2Captcha/CapSolver if you provide those keys).
- **Zip members are never extracted with `..` or absolute paths.**
- **Vendor zip layouts are identified, not assumed.** See [kicad-libraries.md](kicad-libraries.md).

## Why not wrap Import-LIB-KiCad-Plugin?

That plugin (and kicad-libsync) already import zips you downloaded by hand.
This repo adds the missing **URL → zip** step and a stand-alone installer with
the same on-disk layout those tools expect, so you can keep using them if you
prefer.

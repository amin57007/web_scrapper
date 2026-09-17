# Usage

## Inspect (no account)

```bash
ulscrape info "https://app.ultralibrarian.com/details/<uuid>/<mfr>/<mpn>"
```

Prints manufacturer, MPN, description, datasheet URL, and the CAD format
table (KiCad v5/v6, STEP, …). Use this to confirm the part before download.

## Fetch (account required)

```bash
export UL_EMAIL="you@example.com"
export UL_PASSWORD="..."
ulscrape fetch "<url>" -o ./libraries --lib-name UltraLibrarian
```

Flags:

- `-o / --output` library root (default `libraries/`)
- `--lib-name` KiCad nickname
- `--cookies cookies.json` skip password login
- `--email` / `--password` override env vars

## Import a zip from your Downloads folder

Same end state, no network:

```bash
ulscrape import-zip ~/Downloads/ul_OPA2374AIDR.zip -o ./libraries
```

This is the tested path used by Import-LIB-KiCad-Plugin and kicad-libsync.
Use it when Ultra Librarian serves a captcha in `fetch`.

## Python API

```python
from pathlib import Path
from ulscrape.config import Settings
from ulscrape.pipeline import fetch_part, import_zip, inspect_url

details = inspect_url(
    "https://app.ultralibrarian.com/details/1621AE5D-103F-11E9-AB3A-0A3560A4CCCC/Texas-Instruments/OPA2374AIDR"
)
print(details.ref.mpn, details.kicad_v6())

# Offline:
import_zip(Path("ul_OPA2374AIDR.zip"), Path("libraries"))

# Online (needs UL_EMAIL / UL_PASSWORD):
fetch_part(details.ref.url, Settings.from_env(output_dir=Path("libraries")))
```

## Tests

```bash
make test          # fixtures only
make test-all      # plus live GET of a public details page
```

Network tests talk only to the public OPA2374AIDR details page. They do
not log in or download CAD zips.

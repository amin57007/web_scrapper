# web_scrapper (`ulscrape`)

Take an [Ultra Librarian](https://app.ultralibrarian.com/) part URL, download
the KiCad CAD package (schematic **symbol**, PCB **footprint**, and **3D
STEP** model), and install them into a KiCad library tree.

Public part metadata is scraped without a login. CAD file download uses
**your** Ultra Librarian account (free registration). The importer path
also accepts a zip you already downloaded in a browser, which is the same
workflow used by the tested KiCad plugins this project is based on.

This is a local CLI. It does not call a language model at runtime.

## What you get

```
libraries/
  UltraLibrarian.kicad_sym          # merged symbol library
  UltraLibrarian.pretty/            # .kicad_mod footprints
  UltraLibrarian.3dshapes/          # .step / .wrl models
  sym-lib-table                     # project library table
  fp-lib-table
  parts/<MFR>_<MPN>/                # per-part copy + metadata.json
  downloads/<MFR>_<MPN>.zip         # original vendor zip
```

Footprint `(model ...)` paths are rewritten to
`${KICAD_3RD_PARTY}/UltraLibrarian.3dshapes/<file>.step`, and the symbol
`Footprint` property is rewritten to `UltraLibrarian:<footprint>`.

## Requirements

| Dependency | Why |
|---|---|
| **Python 3.11+** | Runtime |
| Ultra Librarian account | Only for `ulscrape fetch` CAD download |
| KiCad 6+ | To open the installed libraries |

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

python scripts/check_env.py    # must print "environment OK"
ulscrape --help
```

For tests and lint:

```bash
pip install -r requirements-dev.txt
pip install -e .
make test
```

## Quick start

### 1. Inspect a part URL (no login)

```bash
ulscrape info \
  "https://app.ultralibrarian.com/details/1621AE5D-103F-11E9-AB3A-0A3560A4CCCC/Texas-Instruments/OPA2374AIDR"
```

### 2. Download KiCad + STEP (account + reCAPTCHA)

`fetch` drives a real Chrome session: login, select **KiCAD v6+** and **STEP**,
complete Google reCAPTCHA, then download.

```bash
export UL_EMAIL="you@example.com"
export UL_PASSWORD="your-password"
# Optional, used if clicking "I'm not a robot" is not enough:
# export TWOCAPTCHA_API_KEY="..."

ulscrape fetch \
  "https://app.ultralibrarian.com/details/1621AE5D-103F-11E9-AB3A-0A3560A4CCCC/Texas-Instruments/OPA2374AIDR" \
  -o libraries
```

Copy `.env.example` to `.env` instead of exporting by hand. Never commit passwords.

If the checkbox challenge needs a solver, set `TWOCAPTCHA_API_KEY` or `CAPSOLVER_API_KEY`.
To watch the browser: `ulscrape fetch <url> --headed`.

### 3. Import a zip you already downloaded

```bash
ulscrape import-zip ~/Downloads/ul_OPA2374AIDR.zip -o libraries
```

Then in KiCad: **Preferences → Manage Symbol Libraries** and **Manage
Footprint Libraries**, project-specific, add:

- `${KIPRJMOD}/UltraLibrarian.kicad_sym`
- `${KIPRJMOD}/UltraLibrarian.pretty`

Copy `libraries/` next to your `.kicad_pro`, or copy the generated
`sym-lib-table` / `fp-lib-table` entries. Set the path variable
`KICAD_3RD_PARTY` to the `libraries/` folder so 3D models resolve.

## Commands

| Command | Login | What it does |
|---|---|---|
| `ulscrape info <url>` | no | Scrape manufacturer, MPN, datasheet, CAD formats |
| `ulscrape fetch <url>` | yes + reCAPTCHA | Chrome login, KiCad v6 + STEP, install library |
| `ulscrape import-zip <zip>` | no | Extract symbol / footprint / 3D model from a local zip |

`<url>` can be a details page, a CAD-portal `?partUuid=` link, or a bare UUID.

## Based on tested repositories

The zip layout and KiCad install rules follow open, tested importers
rather than guessing:

| Project | What we reused |
|---|---|
| [Steffen-W/Import-LIB-KiCad-Plugin](https://github.com/Steffen-W/Import-LIB-KiCad-Plugin) | Identify Ultra Librarian zips by a `KiCAD/` folder, `.kicad_sym` / `.pretty`, STEP/WRL |
| [lognd/kicad-libsync](https://github.com/lognd/kicad-libsync) | `KiCADv6/` + `footprints.pretty/`, rewrite `Footprint` to `lib:name` |
| [HarveyBates/kandle](https://github.com/HarveyBates/kandle) | Per-part naming, 3D model next to symbol/footprint |
| AquaPack Robotics KiCad guide | Classic UL paths: `KiCAD/.../footprints.pretty`, `STEP/*.step` |

The download client talks to the same endpoints the Ultra Librarian web
app uses (`/Export/QueueExport`, `/Export/CheckQueue`, `/Export/Download`)
with KiCad v6+ export id `42` and STEP export id `37`.

## Docs

- [Architecture](docs/architecture.md)
- [Ultra Librarian scrape / download](docs/ultralibrarian.md)
- [KiCad library layout](docs/kicad-libraries.md)
- [Usage](docs/usage.md)

## Development

```bash
make install-dev
make test          # offline unit tests + zip fixtures
make test-all      # includes a live details-page scrape
make lint
```

## License

MIT. CAD files you download remain subject to [Ultra Librarian's terms](https://www.ultralibrarian.com/).
Use this tool with an account you own, for parts you are allowed to download.

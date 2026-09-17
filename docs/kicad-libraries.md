# KiCad library layout

Ultra Librarian does not give KiCad a single “component file”. A download is
a zip that contains a symbol library, a footprint library, and (if selected)
a STEP/WRL model. This project installs those pieces the same way the
tested importers do.

## Vendor zip layouts we recognize

### Ultra Librarian KiCad v6+ (`kicad-libsync`)

```
KiCADv6/<part>.kicad_sym
KiCADv6/footprints.pretty/<footprint>.kicad_mod
STEP/<part>.step
```

### Ultra Librarian classic (`Import-LIB-KiCad-Plugin`, AquaPack guide)

```
[<part>/]KiCAD/<name>/<name>.kicad_sym   # or .lib for v5
[<part>/]KiCAD/<name>/footprints.pretty/<footprint>.kicad_mod
[<part>/]STEP/<part>.step
```

Detection rule (from Import-LIB): a directory whose name is `KiCAD` or
`KiCADv6`, then the first `.kicad_sym` / `.lib`, `.pretty` / `.kicad_mod`,
and `.step` / `.stp` / `.wrl`.

### SnapMagic-style flat zip

```
<part>.kicad_sym
<footprint>.kicad_mod
<part>.step
```

Still imported: we key off extensions, not folder names.

## Installed tree

```
<output>/
  UltraLibrarian.kicad_sym
  UltraLibrarian.pretty/
    <footprint>.kicad_mod
  UltraLibrarian.3dshapes/
    <part>.step
  sym-lib-table
  fp-lib-table
  parts/<MFR>_<MPN>/
    metadata.json
    original symbol / footprint / step copies
```

`lib-name` defaults to `UltraLibrarian` so it matches Import-LIB-KiCad-Plugin
global libraries. Override with `--lib-name`.

## Rewrites

After copy:

1. Symbol property `Footprint` becomes `UltraLibrarian:<footprint-name>`.
2. Footprint `(model "...")` becomes
   `${KICAD_3RD_PARTY}/UltraLibrarian.3dshapes/<file>.step`.
3. Project tables gain entries pointing at `${KIPRJMOD}/UltraLibrarian.kicad_sym`
   and `${KIPRJMOD}/UltraLibrarian.pretty`.

Set KiCad path `KICAD_3RD_PARTY` to the output directory (or copy that
folder to your existing 3rd-party library root).

## Using the files in KiCad

1. Copy `libraries/` next to your `.kicad_pro`, or merge the table files.
2. Schematic editor → Preferences → Manage Symbol Libraries → Project Specific
   → add `UltraLibrarian.kicad_sym`.
3. PCB editor → Preferences → Manage Footprint Libraries → add
   `UltraLibrarian.pretty`.
4. Place the symbol; the footprint field should already resolve.
5. 3D viewer uses the rewritten STEP path once `KICAD_3RD_PARTY` is set.

# Universal Koei Tecmo Save Editor

A free Windows save editor by **Mexican**. Edit supported character, inventory,
equipment and progression fields, compare saves, and convert between selected
platforms. Searchable editors share backups, Undo, change reviews and Light/Dark
themes. No Python installation is needed for the Windows app.

**[Download for Windows](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/latest)**
· **[Supported games](docs/SUPPORTED_GAMES.md)**
· **[User guide](docs/EDITOR_WORKSPACE.md)**
· **[What's new](docs/RELEASE_NOTES.md)**

<!-- BEGIN SUPPORTED GAMES -->
**97 game/platform profiles across 15 platforms.** [Browse the full supported-games list](docs/SUPPORTED_GAMES.md) for editions, platforms and exact editing scope.
<!-- END SUPPORTED GAMES -->

**Version 3.0.** Choose a supported edition below and keep a separate save copy.

## What you can do

- **Explore progression:** browse read-only cards for verified opened-save values,
  equipment and mapped collections. [Dashboards](docs/PROGRESSION_DASHBOARDS.md).

- **Edit saves:** search fields and records, adjust values, inspect equipment,
  review named before/after changes, and save a separate edited copy.
- **Browse copied saves:** choose an exact game/platform and scan a folder.
  Search, sort and filter qualified copies and identical gameplay files.
  [Save Library](docs/SAVE_LIBRARY.md).
- **Reuse edits:** export a reviewed edit preset and apply it to the same
  byte-identical source after previewing the complete resulting changes.
  [Edit Presets](docs/EDIT_PRESETS.md).
- **Personalize the workspace:** pin frequently used fields, keep multiple game
  sessions open, and export complete JSON or spreadsheet-friendly CSV reviews.
  [Pins and reviews](docs/FIELD_PINS_AND_REVIEWS.md).
- **Compare saves:** inspect mapped changes and other payload differences across
  96 scalar profiles. [Compare Saves](docs/SAVE_COMPARISON.md).
- **Convert saves:** 139 directed routes cover qualified DW6, DW7 XL, DW8 XL and
  Persona 5 Strikers transfers. Review one copy or queue multiple conversions.
  [Routes and limits](docs/SAVE_CONVERSION.md) · [Batch Converter](docs/BATCH_CONVERSION.md).

Editing scope varies by edition and save revision. Some newer profiles allow
only conservative reductions or specific equipment choices; the supported-games
list describes each one. Optional [experimental editing](docs/EXPERIMENTAL_EDITING.md)
expands only explicitly mapped numeric fields.

## New in v3.0

- **A more capable workspace:** Ctrl+K command palette, favorites/recent tools, English/German navigation and offline help, scalable text and responsive layouts.
- **Faster reviewed editing:** reusable resource presets across compatible copies, validated bulk actions, selective save transfer and a read-only Save Research Lab.
- **Richer progression:** improved dashboards, record comparisons, interactive HTML reports and [deeper game-specific controls](docs/GAME_SPECIFIC_EXPANSION.md) within existing qualified profiles.
- **Save management:** organized copied-save browsing, read-only Save Doctor, bounded save-location discovery and local Save Vault snapshots, branches and safe restore to new directories.
- **Automation:** code-free Workflow Builder, reviewed multi-copy batch plans, a scriptable JSON CLI with dry runs, and durable interrupted-run inspection. [Automation guide](docs/AUTOMATION.md).
- **Community and reliability:** data-only help plugins, offline validation/feedback reports, indexed search, stronger regression/fuzz coverage and repeatable benchmarks.

[Full v3.0 release notes and limits](docs/RELEASE_NOTES.md). Support remains 97 profiles across 15 platforms, with 139 scoped conversion routes; no new game edition or in-game qualification is implied.

## Quick start

1. Download and extract the complete Windows ZIP, then run its EXE. Alternatively,
   use the standalone EXE. Keep the ZIP's bundled files together.
2. Make a separate copy of your save folder outside the live game/cloud location.
   Choose its exact game, edition and platform, then **Open Save Copy**.
3. Stage edits, check **Review Changes**, and choose **Save As...** to write a new
   game-save copy. **Export Review** writes a report. Undo and automatic backups
   are available.

Console profiles require supported extracted/decrypted exports and any original
companion metadata specified in their guide. Decryption, console reimport and
resigning use external save tools. File-level validation is tested; **edited or
converted game loading and re-saving remain unverified**.

Origins proficiency-level and Old Coin writers remain unimplemented.
[Request status](docs/ORIGINS_REQUEST_STATUS.md). DW7 XL PC weapon base attack,
element and capacity live in game data; arbitrary save edits to those parameters
remain unavailable. [Weapon scope](docs/DW7XL_WEAPONS.md).

## Run from source and contribute

With Python 3.10 or newer and Tkinter, run from the repository root:

```text
python -m pip install -e .
python -m koei_editor
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [build instructions](docs/BUILDING.md),
and the [documentation index](docs/README.md). AI coding agents should read
[AGENTS.md](AGENTS.md).

Discord: `mexicannn` · [Mexican's Steam profile](https://steamcommunity.com/id/theonlyjuandeagingmexican/)

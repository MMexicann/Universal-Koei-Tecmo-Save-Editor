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
**98 game/platform profiles across 15 platforms.** [Browse the full supported-games list](docs/SUPPORTED_GAMES.md) for editions, platforms and exact editing scope.
<!-- END SUPPORTED GAMES -->

**Version 3.1 development source.** The download link always points to the latest published Windows build. Choose a supported edition below and keep a separate save copy.

## What you can do

- **Explore progression:** browse read-only cards for verified opened-save values,
  equipment and mapped collections. [Dashboards](docs/PROGRESSION_DASHBOARDS.md).
- **Track completion:** check achievements only when a supported platform source
  verifies them, or keep an optional manual checklist. Unavailable states remain
  clearly marked.

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
  97 scalar profiles. [Compare Saves](docs/SAVE_COMPARISON.md).
- **Manage mods:** import validated ZIP packages, keep separate profiles, check
  declared dependencies/conflicts, and safely manage Nioh 2 PC mods through its
  documented Mods folder method. [Mod Manager scope and safeguards](docs/MOD_MANAGER.md).
- **Convert saves:** 145 directed routes cover qualified DW6, DW7 XL, DW8 XL, Persona 5 Strikers and resource-only WO3U/SW4 transfers. Review one copy or queue multiple conversions.
  [Routes and limits](docs/SAVE_CONVERSION.md) · [Batch Converter](docs/BATCH_CONVERSION.md).

Editing scope varies by edition and save revision. Some newer profiles allow
only conservative reductions or specific equipment choices; the supported-games
list describes each one. Optional [experimental editing](docs/EXPERIMENTAL_EDITING.md)
expands only explicitly mapped numeric fields.

The [game data encyclopedia feed](docs/GAME_DATA_ENCYCLOPEDIA.md) is
intentionally scoped to verified Three Hopes Switch character/weapon mappings,
Hyrule Warriors Wii U catalog names, and a few cited Hyrule mechanics; it is
not a complete gameplay reference or a Character Workshop interface.

## New in v3.1

- **DW8 XL PS4 editor:** resources, officer stats, weapon-action aptitudes and existing ranked attributes for decrypted CUSA00397 zero-extension copies, with original metadata, backups, Undo and reviewed Save As. Conversion to PC accepts both supported native PC template formats.
- **Import five research candidates:** inspect Gundam 2, Totori/Rorona/Ayesha Plus Vita and original Uncharted Waters IV PK copies in a separate read-only workspace. These are research observations; editing support is not implied. [Research Import](docs/RESEARCH_IMPORT.md).
- **Six new scoped conversion routes:** WO3 Ultimate PS3 ↔ Definitive Edition PC moves unallocated growth points and gems; SW4 US PS3 ↔ SW4 DX PC moves gold only. WO3U PS4 → PC transfers 354 directly mapped crystal/orb/material balances, with a separate wider scope adding five base stats for 145 playable officers. Destination progression and equipment remain intact.
- **Clearer conversions:** exact source/destination filters, source/template filenames and companions, numeric before/after previews for the new routes, and an explicit reverse-route action that swaps copies and requires a fresh review.
- **Requested PS4 transfers:** DW8 XL PS4 → PC is available within its documented profile. WO3U adds a limited PS4 resource route; full WO3U/SW4 PS4 migration still needs broader format evidence and original exports. [Exact scope and remaining evidence](docs/WARRIORS_PS4_TRANSFERS.md).

[Release notes and limits](docs/RELEASE_NOTES.md). The development source contains 98 profiles across 15 platforms and 145 scoped routes. Edited/converted game loading remains unverified.

The mod manager is development-source functionality and currently supports only
the documented Nioh 2 PC Mods folder method with an already installed mod
loader. It never installs loader files or writes into original game files.
Other Koei Tecmo titles remain unsupported until their installation methods and
restoration behavior are verified.

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

The development source also includes a [Character & Weapon Workshop](docs/CHARACTER_WEAPON_WORKSHOP.md)
for mapped Dynasty Warriors, Samurai Warriors and Warriors Orochi profiles.
This feature is not part of the published v3.1 binaries.

Discord: `mexicannn` · [Mexican's Steam profile](https://steamcommunity.com/id/theonlyjuandeagingmexican/)

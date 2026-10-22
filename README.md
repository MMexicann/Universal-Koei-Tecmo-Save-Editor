# Universal Koei Tecmo Game Toolkit

A free Windows toolkit by **Mexican** for editing, comparing and converting
supported Koei Tecmo saves. Browse progression, organize save copies and automate
reviewed edits, with backups, Undo and a review before saving.

**[Download for Windows](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/latest)**
· **[Supported games](docs/SUPPORTED_GAMES.md)**
· **[User guide](docs/EDITOR_WORKSPACE.md)**
· **[Documentation](docs/README.md)**

**Game Toolkit v1.0 is in preparation.** The latest published app is
**Universal Koei Tecmo Save Editor v3.1**. The new name continues the same project;
v1.0 will be a branding version reset, preserving earlier releases and history.
[Planned release notes](docs/TOOLKIT_V1_RELEASE_NOTES.md).

<!-- BEGIN SUPPORTED GAMES -->
**98 game/platform profiles across 15 platforms.** [Browse the full supported-games list](docs/SUPPORTED_GAMES.md) for editions, platforms and exact editing scope.
<!-- END SUPPORTED GAMES -->

[Features](#features) · [Games](#supported-games) · [Downloads](#download-and-install)
· [Compatibility](#compatibility) · [Contributing](#run-from-source-and-contribute)

## Features

- **Edit and review:** searchable character, inventory, equipment and progression
  fields; presets, selective transfers, pinned fields and JSON/CSV change reports.
- **Explore progression:** read-only dashboards for mapped save values and
  collections, with offline HTML reports. [Dashboard guide](docs/PROGRESSION_DASHBOARDS.md).
- **Manage save copies:** browse folders, find documented save locations, inspect issues
  with Save Doctor and keep snapshots in the local Save Vault.
  [Save management](docs/SAVE_MANAGEMENT.md).
- **Compare and convert:** compare mapped values and payload differences; review
  individual or queued conversions across **145 scoped routes**.
  [Conversion scope](docs/SAVE_CONVERSION.md).
- **Automate reviewed work:** build workflows, reuse presets and run batch jobs
  from the command line. [Automation](docs/AUTOMATION.md).
- **Use one workspace:** retained editor sessions, Light/Dark themes, English/German
  shell controls, offline help and data-only community plugins.
  [Community plugins](docs/COMMUNITY_PLUGINS.md).

## Supported games

Examples below refer to selected editions and save revisions, not every release
in a series. **98 profiles does not mean 98 distinct games.**

| Family | Examples with registered editing profiles |
| --- | --- |
| Dynasty Warriors | 3 Remastered, 4 Hyper/XL, 5 Special, 6, 7/XL/Empires, 8/XL/Empires, 9 Empires, Origins |
| Samurai Warriors and Orochi | Samurai Warriors 2, 4/DX/4-II, 5; Warriors Orochi, Z, 3 Ultimate, 4/Ultimate |
| Other Warriors titles | All-Stars, Abyss, Pirate Warriors 1–4, Gundam/3/Reborn, Legends of Troy |
| Nintendo collaborations | Hyrule Warriors/Legends/Definitive Edition, Age of Calamity; Fire Emblem Warriors/Three Hopes; Three Houses |
| Atelier and Gust | Selected Rorona, Totori, Meruru, Ayesha, Escha & Logy, Sophie/2, Firis, Ryza/2/3 DX; Nights of Azure 2; Blue Reflection: Second Light |
| Action and RPG | Nioh 3, Ninja Gaiden Black/II, Wo Long, Persona 5 Strikers, Dragon Quest Builders 2, Berserk, Attack on Titan, Dead or Alive 5 |
| Classics and more | Selected Romance of the Three Kingdoms, Nobunaga’s Ambition, Uncharted Waters, Gemfire, Monster Rancher DS, Pokémon Conquest, Tecmo Super Bowl, Project Zero/Fatal Frame |

Save profiles cover Windows and DOS PC, PlayStation 2/3/4/Vita, Xbox/Xbox 360,
Switch/Wii U/3DS/DS, NES/SNES and Macintosh. **The distributed app is for Windows.**
Use the [platform catalog](docs/SUPPORTED_GAMES.md) to check an exact edition,
region, required files and available controls.

## What's changing for v1.0

- A new **Game Toolkit** identity for the existing save tools and workflows.
- Read-only **Scenario View** cards for six existing strategy profiles.
  [Scope and limits](docs/SCENARIO_ARMY_EDITOR_REPORT.md).
- Integration groundwork in source: a DW3 Steam achievement provider and
  [Three Hopes/Hyrule Warriors reference data](docs/GAME_DATA_ENCYCLOPEDIA.md).
  Achievement lookup and encyclopedia browsing interfaces are still pending;
  these additions do not expand save-editing support.

No additional game profiles or platforms have been integrated since v3.1.
Features still under review are excluded. See the [pending v1.0 notes](docs/TOOLKIT_V1_RELEASE_NOTES.md)
and [published v3.1 notes](docs/RELEASE_NOTES.md) for their separate scopes.

## Download and install

No Python installation is needed for either Windows download.

| Download | How to use it |
| --- | --- |
| [Standalone EXE · v3.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/UniversalKoeiTecmoSaveEditor-v3.1.exe) | Download and run the self-contained app. |
| [Portable Windows ZIP · v3.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/UniversalKoeiTecmoSaveEditor-v3.1-Windows.zip) | Extract the entire ZIP and run its EXE; keep the bundled runtime beside it. |
| [Source ZIP · v3.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/UniversalKoeiTecmoSaveEditor-v3.1-Source.zip) | Source code for the published release; requires Python to run. |

[Checksums](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/SHA256SUMS.txt)
· [Defender scan report](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/DefenderScan-v3.1.json)
· [All releases](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases)

1. Make a separate copy of your save folder outside the live game/cloud location.
2. Choose the exact game, edition and platform, then **Open Save Copy**.
3. Stage edits, check **Review Changes**, then **Save As...** to a new save copy.
   **Export Review** creates a report, not a game save.

## Compatibility

- **Verified scope:** file-level validation and copy-preservation checks are
  documented per profile. **Edited/converted in-game loading and re-saving remain
  unverified.** [Validation evidence](docs/VALIDATION.md).
- **Console saves:** use the required extracted/decrypted exports and original
  companion metadata. Extraction, decryption, reimport and resigning use external tools.
- **Partial conversions:** routes transfer only their listed fields. WO3U and SW4
  routes do not provide complete migration. [Route limits](docs/SAVE_CONVERSION.md).
- **Experimental and research:** opt-in experimental editing expands only mapped
  numeric fields. Research Import is read-only and adds no supported editing profiles.
  [Experimental scope](docs/EXPERIMENTAL_EDITING.md) · [Research Import](docs/RESEARCH_IMPORT.md).

Editing controls vary by profile; some permit reductions only. Origins proficiency
levels/Old Coins and arbitrary DW7 XL PC weapon base-parameter edits remain unavailable.
[Origins status](docs/ORIGINS_REQUEST_STATUS.md) · [DW7 XL weapon scope](docs/DW7XL_WEAPONS.md).

## Run from source and contribute

With Python 3.10 or newer and Tkinter, run from the repository root:

```text
python -m pip install -e .
python -m koei_editor
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [build instructions](docs/BUILDING.md),
[technical documentation](docs/README.md) and [LICENSE](LICENSE).
AI coding agents should read [AGENTS.md](AGENTS.md).

Discord: `mexicannn` · [Mexican's Steam profile](https://steamcommunity.com/id/theonlyjuandeagingmexican/)

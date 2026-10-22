# Universal Koei Tecmo Game Toolkit

A free Windows toolkit by **Mexican** for editing, comparing and converting
supported Koei Tecmo saves, planning builds and organizing copied saves.
Review changes before saving, with backups and Undo.

**[Download for Windows](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/latest)**
· **[Supported games](docs/SUPPORTED_GAMES.md)**
· **[Getting started](docs/EDITOR_WORKSPACE.md)**
· **[What's new](docs/TOOLKIT_V1_RELEASE_NOTES.md)**

**Game Toolkit v1.0 is in development; publication is on hold.** The current published download is
**Save Editor v3.1**. The new name continues the same project; the planned
version reset preserves earlier releases and repository history.

<!-- BEGIN SUPPORTED GAMES -->
**98 game/platform profiles across 15 platforms.** [Browse the full supported-games list](docs/SUPPORTED_GAMES.md) for editions, platforms and exact editing scope.
<!-- END SUPPORTED GAMES -->

[Features](#features) · [Games](#supported-games) · [Install](#download-and-install)
· [Compatibility](#compatibility) · [Documentation](docs/README.md)

## Features

- **Edit and review saves:** searchable character, equipment, inventory and
  progression controls, side-by-side comparisons, presets and JSON/CSV reviews.
  [Editor guide](docs/EDITOR_WORKSPACE.md).
- **Keep playthroughs organized:** browse save copies, use Save Doctor and Save
  Vault, and prepare isolated copies with Smart Playthrough Profiles.
  [Save tools](docs/SAVE_MANAGEMENT.md) · [Playthrough profiles](docs/SMART_PLAYTHROUGH_PROFILES.md).
- **Plan character and weapon builds:** compare mapped values and stage reviewed
  plans for DW3 Remastered, DW8 XL PC, WO3 Ultimate PC and SW4 DX PC.
  [Character & Weapon Workshop](docs/CHARACTER_WEAPON_WORKSHOP.md).
- **Explore progress and convert copies:** dashboards, separate manual checklists
  and optional DW3 Remastered Steam achievements; individual or queued conversion across
  **145 scoped routes**. [Progression](docs/PROGRESSION_DASHBOARDS.md) · [Conversions](docs/SAVE_CONVERSION.md).
- **Create and manage mods:** package user-provided replacements in Mod Creation
  Workshop; import and manage **Nioh 2 PC** mods with separate profiles and
  dependency/conflict checks. [Creation Workshop](docs/MOD_CREATION_WORKSHOP.md) · [Mod Manager](docs/MOD_MANAGER.md).
- **Find games and inspect files:** Steam Game Hub, documented emulator launch
  profiles and a read-only Asset Explorer for supported ZIP, G1T and media subsets.
  [Game Hub](docs/APPLICATION_SHELL.md#game-hub) · [Emulators](docs/EMULATOR_HUB.md) · [Assets](docs/ASSET_EXPLORER.md).
- **Manage selected PC settings:** review supported Atelier Arland DX game and
  installed-mod settings, save profiles and keep verified backups.
  [Configuration Manager](docs/GAME_CONFIGURATION.md).
- **Reuse and share reviewed work:** automation, resource presets for qualified
  profiles, local controller-profile records and data-only community packages.
  [Automation](docs/AUTOMATION.md) · [Presets](docs/REUSABLE_PRESETS.md) · [Community formats](docs/COMMUNITY_TOOLKIT.md).

Development source also includes a [browser-local Mod Testing Sandbox](docs/MOD_TESTING_SANDBOX.md),
an [offline Localization Studio](localization-studio/README.md) for supported plain-text tables,
and a [snapshot-based patch analyzer](docs/PATCH_COMPATIBILITY_ANALYZER.md).
These are separate source tools; their file handoffs require review in the
receiving application.

## Supported games

Examples below cover **selected editions and save revisions**. Profiles count
individual game/platform combinations, not distinct games or complete series.

| Family | Examples with registered editing profiles |
| --- | --- |
| Dynasty Warriors | 3 Remastered, 4 Hyper/XL, 5 Special, 6, 7/XL/Empires, 8/XL/Empires, 9 Empires, Origins |
| Samurai Warriors and Orochi | Samurai Warriors 2, 4/DX/4-II, 5; Warriors Orochi, Z, 3 Ultimate, 4/Ultimate |
| Other Warriors titles | Pirate Warriors 1–4, Gundam/3/Reborn, All-Stars, Abyss, Legends of Troy |
| Nintendo collaborations | Hyrule Warriors and Age of Calamity; Fire Emblem Warriors, Three Hopes and Three Houses |
| Atelier and Gust | Selected Arland, Dusk, Sophie, Firis and Ryza editions; Nights of Azure 2; Blue Reflection: Second Light |
| Action and RPG | Nioh 3, Ninja Gaiden Black/II, Wo Long, Persona 5 Strikers, Dragon Quest Builders 2, Berserk, Attack on Titan, Dead or Alive 5 |
| Strategy and classics | Selected Romance of the Three Kingdoms, Nobunaga’s Ambition, Uncharted Waters, Gemfire, Monster Rancher DS, Pokémon Conquest, Tecmo Super Bowl and Project Zero/Fatal Frame |

Save profiles span PC, PlayStation, Xbox, Nintendo and classic platforms.
**The downloadable application runs on Windows.** Save Vault and Playthrough
Profiles also require Windows when running from source. Use the
[full platform catalog](docs/SUPPORTED_GAMES.md) for exact editions, regions,
required files and available controls. Research on additional ports or editions
adds no new editing support; the inventory remains 98 profiles and 15 platforms.

## Download and install

The published Windows downloads require no Python installation.

| Download | Installation |
| --- | --- |
| [Standalone EXE · v3.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/UniversalKoeiTecmoSaveEditor-v3.1.exe) | Download and run. |
| [Portable Windows ZIP · v3.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/UniversalKoeiTecmoSaveEditor-v3.1-Windows.zip) | Extract everything and run the EXE; keep bundled files together. |
| [Source ZIP · v3.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/UniversalKoeiTecmoSaveEditor-v3.1-Source.zip) | Source for the published release; Python is required. |

[Checksums](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/SHA256SUMS.txt)
· [Defender report](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/download/v3.1/DefenderScan-v3.1.json)
· [All releases](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases)

1. Copy your save folder outside the live game/cloud location.
2. Select its exact game, edition and platform, then **Open Save Copy**.
3. Stage edits, check **Review Changes**, then **Save As…** to a new copy.
   **Export Review** creates a report.

The v1.0 features described above are development-source changes until that
release is published; the v3.1 downloads retain their published feature set.

## Compatibility

- **Save support is profile-specific.** Some controls allow reductions only.
  File-level checks are documented; edited/converted game loading and re-saving
  remain unverified. [Evidence and limits](docs/VALIDATION.md).
- **Console saves need prepared exports.** Use the required extracted/decrypted
  files and original companions. Decryption, reimport and resigning use external tools.
- **Conversions transfer listed fields only.** WO3U and SW4 routes do not provide
  complete migration. Experimental editing is opt-in; Research Import is read-only.
- **Mod support is separate from save support.** Mod Manager supports Nioh 2 PC’s
  documented Mods folder method with an existing loader. It does not install
  loaders. Nexus currently provides website links; its API workspace is gated
  pending application registration. [Nexus availability](docs/NEXUS_MODS_BROWSER.md).
- **Other tools retain their limits.** Controller profiles store bindings without
  applying them to games. Troubleshooting folder scans currently fail closed on
  Windows and report unavailable evidence; no diagnosis is inferred.
  [Controller scope](docs/CONTROLLER_INPUT_PROFILES.md) · [Troubleshooting](docs/GAME_TROUBLESHOOTING.md).

## Run from source and contribute

Clone this repository or [download and extract main](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/archive/refs/heads/main.zip) for development features. With Python 3.10 or newer and Tkinter, run from the repository root:

```text
python -m pip install -e .
python -m koei_editor
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [build instructions](docs/BUILDING.md),
[documentation](docs/README.md) and [LICENSE](LICENSE).

Discord: `mexicannn` · [Mexican's Steam profile](https://steamcommunity.com/id/theonlyjuandeagingmexican/)

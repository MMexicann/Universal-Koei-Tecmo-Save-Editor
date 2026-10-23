# Universal Koei Tecmo Game Toolkit

A free toolkit by **Mexican** for editing, comparing and converting
supported Koei Tecmo saves, planning builds and organizing copied saves.
Review changes before saving, with backups and Undo.

**[Download for Windows and Linux](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/latest)**
· **[Supported games](docs/SUPPORTED_GAMES.md)**
· **[Getting started](docs/EDITOR_WORKSPACE.md)**
· **[What's new](docs/RELEASE_NOTES.md)**

**Toolkit 1.0.1** adds Linux builds and connects the mod, reference and browser
tools. Earlier releases and existing save compatibility are preserved.

<!-- BEGIN SUPPORTED GAMES -->
**98 game/platform profiles across 15 platforms.** [Browse the full supported-games list](docs/SUPPORTED_GAMES.md) for editions, platforms and exact editing scope.
<!-- END SUPPORTED GAMES -->

[Features](#features) · [Games](#supported-games) · [Install](#download-and-install)
· [Compatibility](#compatibility) · [Documentation](docs/README.md)

## Features

- **Find every tool:** open **Tools** to search workspaces and see supported games. [Feature guide](docs/TOOLKIT_FEATURES.md).
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
  Workshop, export supported manager packages and manage **Nioh 2 and Nioh 3 PC**
  mods with separate libraries, profiles and dependency/conflict checks.
  Loaders are installed separately. [Workshop handoff](docs/MOD_WORKSHOP_MANAGER.md) · [Mod Manager](docs/MOD_MANAGER.md).
- **Find games and inspect files:** sort Steam installations, export installation
  reports, use emulator profiles and preview supported ZIP, G1T and media subsets.
  [Game Hub](docs/APPLICATION_SHELL.md#game-hub) · [Emulators](docs/EMULATOR_HUB.md) · [Assets](docs/ASSET_EXPLORER.md).
- **Manage selected PC settings:** review supported Atelier Arland DX game and
  installed-mod settings, save profiles and keep verified backups.
  [Configuration Manager](docs/GAME_CONFIGURATION.md).
- **Use the command line and share reviewed work:** searchable catalogs, save
  inspection, comparisons, conversions, automation and path-free support diagnostics.
  [CLI](docs/CLI.md) · [Diagnostics](docs/DIAGNOSTICS.md) · [Automation](docs/AUTOMATION.md).

**Tools** also opens the bundled [Mod Testing Sandbox](docs/MOD_TESTING_SANDBOX.md),
[Localization Studio](localization-studio/README.md), searchable [encyclopedia](docs/GAME_DATA_ENCYCLOPEDIA.md)
and [patch analyzer](docs/PATCH_COMPATIBILITY_ANALYZER.md). No separate Node server is needed.

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
**The application runs on Windows and compatible x86_64 Linux systems.**
Save Vault and Playthrough Profiles still require Windows. Use the [full platform catalog](docs/SUPPORTED_GAMES.md)
for exact editions, regions, required files and controls. Research candidates add no editing support.

## Download and install

The published Windows downloads require no Python installation.

For Linux, see [installation and platform limits](docs/LINUX.md).

| Download | Installation |
| --- | --- |
| [Standalone GUI EXE · v1.0.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/UniversalKoeiTecmoGameToolkit-v1.0.1.exe) | Download and run. |
| [Portable Windows ZIP · v1.0.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/UniversalKoeiTecmoGameToolkit-v1.0.1-Windows.zip) | Extract everything and run the EXE; keep bundled files together. |
| [CLI EXE · v1.0.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/UniversalKoeiTecmoGameToolkit-v1.0.1-CLI.exe) | Optional command-line edition; run with `--help` in a terminal. |
| [Source ZIP · v1.0.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/UniversalKoeiTecmoGameToolkit-v1.0.1-Source.zip) | Source for the published release; Python is required. |
| [Linux x86_64 · v1.0.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/UniversalKoeiTecmoGameToolkit-v1.0.1-Linux-x86_64.tar.gz) | Extract and run the GUI or the separate `cli/` executable. See [Linux prerequisites](docs/LINUX.md). |

[Checksums](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/SHA256SUMS.txt)
· [Linux checksums](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/UniversalKoeiTecmoGameToolkit-v1.0.1-Linux-x86_64.SHA256SUMS)
· [Linux verification](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/LinuxVerification-v1.0.1.json)
· [Defender report](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/download/toolkit-v1.0.1/DefenderScan-v1.0.1.json)
· [All releases](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases)
· [Save Editor v3.1](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/releases/tag/v3.1)

1. Copy your save folder outside the live game/cloud location.
2. Select its exact game, edition and platform, then **Open Save Copy**.
3. Stage edits, check **Review Changes**, then **Save As…** to a new copy.
   **Export Review** creates a report.

## Compatibility

- **Save support is profile-specific.** Some controls allow reductions only.
  File-level checks are documented; edited/converted game loading and re-saving
  remain unverified. [Evidence and limits](docs/VALIDATION.md).
- **Console saves need prepared exports.** Use the required extracted/decrypted
  files and original companions. Decryption, reimport and resigning use external tools.
- **Conversions transfer listed fields only.** WO3U and SW4 routes do not provide
  complete migration. Experimental editing is opt-in; Research Import is read-only.
- **Mod support is separate from save support.** Nioh 2 and Nioh 3 require their
  documented loaders, installed separately. Deployment is Windows-only; Linux supports libraries and packages.
  Nexus API access awaits application registration. [Nexus availability](docs/NEXUS_MODS_BROWSER.md).
- **Other tools retain their limits.** Controller profiles do not apply game bindings.
  Troubleshooting is read-only; unavailable evidence stays unknown and repairs are manual.
  [Controller scope](docs/CONTROLLER_INPUT_PROFILES.md) · [Troubleshooting](docs/GAME_TROUBLESHOOTING.md).

## Run from source and contribute

Extract the Source ZIP above for version 1.0.1, or [clone/download main](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/archive/refs/heads/main.zip) for ongoing development. With Python 3.10 or newer and Tkinter, install from the repository root, then launch the GUI or view CLI help:

```text
python -m pip install -e .
python -m koei_editor
universal-koei-toolkit --help
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [build instructions](docs/BUILDING.md), [documentation](docs/README.md) and [LICENSE](LICENSE).

Discord: `mexicannn` · [Mexican's Steam profile](https://steamcommunity.com/id/theonlyjuandeagingmexican/)

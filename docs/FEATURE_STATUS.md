# Feature implementation status

This matrix describes **Toolkit 1.0.1**. Implemented code, a passing automated check
and successful use inside a game are separate evidence levels.

Save coverage remains **98 game/platform profiles, 15 save platforms and
145 scoped conversion routes**. The additional Nioh 3 mod adapter does not add
a save profile or prove compatibility with another edition.

## Implemented and connected in 1.0.1

| Feature | Available implementation | Boundary |
| --- | --- | --- |
| Tools directory | Searchable navigation, menu and command-palette routes; retained editor sessions | Scope is displayed per tool. English/German controls retain original reviewed technical descriptions. |
| Native Linux edition | x86_64 GUI and headless CLI builds, dependency notices and Linux CI | Compatible glibc systems; see [Linux requirements](LINUX.md). Use the versioned release download. |
| Mod Manager | Separate Nioh 2 and Nioh 3 PC libraries, profiles and documented loader methods | Windows GUI deployment; Linux package/library work. Required loaders are installed separately. [Methods](MOD_MANAGER.md). |
| Workshop handoff | Review and export a supported manager ZIP, then import into the matching game library | Import neither installs nor enables the mod. Generic Workshop packages remain separate. [Handoff](MOD_WORKSHOP_MANAGER.md). |
| Nexus manual workflow | Official game-page links, per-game capability labels and explicit local ZIP import for supported adapters | Public API browsing and integrated downloads remain unavailable. [Availability](NEXUS_MODS_BROWSER.md). |
| Browser companions | Mod Testing Sandbox and Localization Studio launch from the app using bundled assets and an owned loopback server | No separate Node/Python server is required. The Sandbox does not execute mods; Studio supports documented text/subtitle formats. |
| Encyclopedia | Desktop search, exact edition/kind filters, record details and field-level sources/licenses | Three Hopes Switch and Hyrule Warriors Wii U reference records only. [Coverage](GAME_DATA_ENCYCLOPEDIA.md). |
| Patch analyzer | Desktop comparison of explicit baseline/candidate JSON and optional requirements, with new-file report exports | No automatic snapshot capture or Mod Manager/Tracker compatibility pipeline. [Input contract](PATCH_COMPATIBILITY_ANALYZER.md). |
| Steam discovery | Standard Linux, XDG and Flatpak roots; bounded library/manifests scanning shared by Hub and Tracker | Installation metadata does not establish a native Linux port or Proton compatibility. [Discovery](APPLICATION_SHELL.md#game-hub). |
| Troubleshooting | Bounded folder/configuration checks through anchored Linux and native Windows access | Unsupported filesystems and unavailable evidence remain unknown; native Windows behavior requires Windows checks. [Scope](GAME_TROUBLESHOOTING.md). |
| Mod CLI | Method catalog, local package validation/import and reviewed Workshop export | No deployment command or automatic installation. [Commands](CLI.md). |

The encyclopedia feed and patch-analyzer command existed in 1.0 without these
desktop surfaces. The browser projects were separate source components; 1.0.1
bundles their runtime assets and adds application launch/lifecycle integration.
The Nexus API implementation remains a development/testing component even
though its source is included. Historical 1.0 notes describe that release,
not this release's behavior.

## Remaining blockers and limits

| Capability | Current status / required next evidence |
| --- | --- |
| Public Nexus API integration | Requires actual Nexus application registration evidence and integration review. There is no public registration toggle or credential bypass. |
| Linux Save Vault / Smart Playthrough Profiles storage | Windows-only managed storage remains. Linux equivalents for the required native directory creation, locking and restoration guarantees need implementation and qualification. |
| Actual game loading | Edited/converted saves, mod loading and game re-saving remain unverified. Procedural fixtures and file-operation tests cannot supply that evidence. |
| Additional mod installation games | Only the two documented adapters are implemented. Each additional title requires its own loader/layout, ownership, conflict and restoration contract. A Nexus website entry is insufficient. |
| Full graphical scenario/army editing | Existing Scenario View is read-only. Ownership, deployment and scenario writers require independently mapped native fields, dependencies and controlled save evidence. |
| Universal configuration management | Verified settings are limited to Atelier Rorona/Totori/Meruru DX PC and documented Arland DX Fix settings. Other game formats have no adapters. |
| Controller/OS remapping | Profiles store and export app-owned bindings. Applying Steam Input, game bindings or OS/controller-driver mappings is not implemented. |
| All-game encyclopedia | The reference catalog is intentionally limited. Other games need reviewed edition-specific records and licensed field-level provenance. |
| Exact-build compatibility certification | Tracker observations and analyzer inputs remain distinct. The reviewed exact-build compatibility catalog has no entries; unknown builds are not automatically incompatible. |
| Automatic playthrough activation | Profiles prepare isolated save copies and retain component snapshots. They do not activate mods, change game settings or launch a playthrough automatically. |

Use [the feature guide](TOOLKIT_FEATURES.md) for navigation and
[the supported-games catalog](SUPPORTED_GAMES.md) for each save profile's exact
edition, writable scope and remaining qualification limits.

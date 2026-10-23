# Find and use toolkit features

This guide describes version **1.0.1**. Toolkit 1.0 has a
narrower feature set; use its release notes when using that download.

Open **Tools** in the top navigation to search the directory. Each entry states
its scope and opens its workspace. **Ctrl+K** also finds tools; **Editing and
Research** retains direct menu entries. Open editors stay available while
switching workspaces.

| Task | Open | Scope |
| --- | --- | --- |
| Edit saves | Game Library | Exact registered game, edition and save platform. |
| Inspect progress or completion | Inside an editor | Save-backed values and separately marked manual checklists. |
| Plan character/weapon builds | Supported editor's Character & Weapon Workshop tab | DW3 Remastered, DW8 XL PC, WO3 Ultimate PC and SW4 DX PC mapped fields. |
| Inspect strategy records | Supported editor's Scenario View | Read-only records in six strategy profiles; existing writable fields remain in Edit Fields. |
| Manage mods | Mod Manager | Nioh 2 PC and Nioh 3 PC have distinct documented loader methods. |
| Create a mod package | Mod Creation Workshop | Your supplied replacements; reviewed manager ZIP export for supported layouts. |
| Check staged mod projects | Mod Testing Sandbox | Bundled browser workspace; manifest, dependency, hash and path checks. |
| Browse Nexus | Nexus Mods | Official websites and manual ZIP import for supported manager games; API registration remains pending. |
| Browse save copies | Save Library | Qualified copied-folder scans and comparison. |
| Snapshot or restore a save | Save Library → Save Doctor / Detection / Vault | Windows-only managed storage. |
| Prepare a playthrough copy | That management window → Smart Playthrough Profiles | Isolated Vault-backed copies; component exports remain inert data. |
| Compare or convert saves | Compare Saves / Save Converter / Batch Converter | Exact profile and route-specific fields; new destinations. |
| Reuse edits | Reusable Editing Presets / Workflow Builder | Compatible fields, preview, Undo and review. |
| Transfer selected fields | Transfer from Save Copy | Open the destination copy in its editor first. |
| Find Steam installations | Game Hub | Reviewed IDs; Windows and known Linux Steam roots. Proton compatibility is unverified. |
| Observe installed builds | Help Center → Game Version Tracker | Steam build metadata and local history; no inferred compatibility. |
| Edit game settings | Game Configuration Manager | Rorona DX, Totori DX and Meruru DX PC, including selected Arland DX Fix settings. |
| Organize bindings | Controller & Input Profiles | App-owned profiles and exports; no OS/Steam Input remapping. |
| Configure emulator launches | Emulator Integration Hub | User-selected executables and documented launch profiles. |
| Inspect assets | Game Asset Explorer | Read-only supported ZIP, G1T and common-media subsets. |
| Search reference data | Game Data Encyclopedia | Exact Three Hopes Switch and Hyrule Warriors Wii U records, with sources. |
| Compare patch observations | Patch Compatibility Analyzer | Explicit before/after JSON snapshots and optional requirements; reviewed exports. |
| Translate text copies | Localization Studio | Supported CSV/TSV, JSON, TXT, SRT and WebVTT; no proprietary game packages. |
| Investigate save formats | Save Research Lab / Research Import | Inspection and reports; unverified candidates are not editing profiles. |
| Diagnose selected folders | Game Troubleshooting Center | Bounded read-only evidence; unknown checks remain unknown. |
| Review community packages | Help Center → Plugins | Local data packages; no downloaded code execution or hosted marketplace. |
| Export support information | Help Center → Toolkit diagnostics | Local reports; no automatic transmission. |

## Mod workflow

1. Select the exact game in **Mod Manager** and read its method and loader requirements.
2. Download on the official website or export a matching package from Workshop.
3. Import the ZIP for validation and library review. Workshop's manager export can
   hand it directly to the matching library; a generic Workshop ZIP is different.
4. On Windows, choose the game folder and a profile, review requirements and
   conflicts, then explicitly apply. Importing never installs or enables a mod.

Nioh 2 requires its existing Mod Enabler; Nioh 3 requires its existing Loose File
Loader. Neither adapter establishes actual in-game validation. Other games in
the Nexus website list do not have manager installation adapters.

## Host platforms

The Linux edition includes the GUI and a headless CLI. Registered platform names
describe save formats, so a Windows PC save profile can still be inspected on
Linux. They do not assert native Linux game availability. Save Vault,
Playthrough Profile storage and game mod deployment retain their Windows-only
host limits. See [Linux installation and evidence](LINUX.md).

The browser companions are bundled with the application and served only over
the toolkit's local loopback connection. Export browser work before closing
the application; restoration across toolkit restarts is not guaranteed.

The CLI supports save workflows, mod archive review/import and Workshop package
exports. It does not automate game deployment. See [CLI](CLI.md),
[Workshop handoff](MOD_WORKSHOP_MANAGER.md) and the [documentation index](README.md).

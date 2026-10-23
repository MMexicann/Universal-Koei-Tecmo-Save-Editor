# Koei Tecmo Mod Testing Sandbox

The browser-local sandbox stages mod folders in separate game, exact-build, and mod-ID namespaces. It previews planned destination paths, detects duplicate targets and file/directory collisions, and validates a JSON mod manifest before preparing a ZIP download.

Open **Editing and Research → Mod Testing Sandbox** in the packaged Toolkit.
The managed local server opens the bundled tool in your default browser without
a separate Python or Node installation. Keep the Toolkit running and retain your
original mod folders; export needed results before closing. The
[browser companion guide](BROWSER_COMPANIONS.md) explains session storage and scope.

## Run and test

From `tools/mod_testing_sandbox/`, run `npm test` and `npm run build`. The app is buildless JavaScript with no runtime dependencies. `npm run build` copies the static site to `dist/`.

Import one folder at a time. A folder must contain exactly one `mod-manifest.json`, `manifest.json`, or Mod Creation Workshop `mod.json`. Workshop projects must place `mod.json` at the selected project root. Its `replacements[].source_path` entries are normalized to NFC, must exist under that folder, and each target is path-checked. Declared replacement SHA-256 values are verified against imported bytes and rechecked after browser storage restore; hashing is limited to 64 MiB per file while the total selected folder limit is 256 MiB. Workshop manifests over the per-file hashing limit fail closed. Workshop's model default of `schema_version: 1` is honored when the field is omitted. `game_version` supports exact labels, `*`, or documented comma-separated SemVer ranges; the selected game/build and Windows PC platform still must match. Required dependencies must also be staged in the workspace at compatible versions. The browser does not open Workshop ZIPs or trust `verification.json` reports. A `koei-mod.json` file is Mod Manager package metadata and is accepted inside the Nioh 2 manager ZIP, not as a Sandbox folder manifest.

The initial save-profile list uses Windows PC IDs registered in `src/koei_editor/game_registry.py`: `dw8xl`, `wolong`, `nioh3`, `samurai5_pc`, `wo4_ultimate`, and `atelier_ryza3_dx_pc`. The separate Nioh 2 Mod Manager package route uses manager ID `nioh2_pc` and its own import restrictions; it does not add Nioh 2 to the save-profile snapshot IDs. The user enters the exact build/profile string. This is manifest-declared compatibility preflight; it is not native game-format or game-load verification.

## Companion-tool contracts

The Toolkit provides the managed launcher, while browser-to-desktop data handoffs
remain explicit files requiring review in the receiving tool. The sandbox directly
reads the Workshop's native project `mod.json` format; it does not apply browser
messages or packages to the native application automatically.

- **Mod Manager inventory:** read-only path inventory with contract `koei.mod-manager.inventory/v1`, `gameId`, `gameVersion`, and `files`. It can mark staged paths as additions or replacements without reading an installed game directory.
- **Mod Manager / Playthrough Profiles:** registered save profiles get the bounded `ProfileComponentSnapshot` envelope from [PR #112](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/112): `component: "mod_configuration"`, `provider: "mod_manager"`, `schema_version: 1`, `game_id`, `game_version`, and an inert `payload` limited to 256 KiB. It contains no mod file bytes and never auto-applies. For Nioh 2, the sandbox creates one package ZIP matching the import contract in [PR #129](https://github.com/MMexicann/Universal-Koei-Tecmo-Toolkit/pull/129): one `.ini`, at least one `.fmt`, `.vb`, `.ib`, or `.dds` asset, all files under the `.ini` marker folder, and optional root `koei-mod.json` metadata. The manager validates the ZIP again. The sandbox does not connect to the desktop manager or install files.
- **Mod Creation Workshop:** Workshop project folders with native `mod.json` manifests are accepted and validated against their selected sources and build/profile. `koei.mod-sandbox.workshop-brief/v1` returns the selected context, native manifest template, and validation issues. Workshop ZIPs are not opened; its `verification.json` is treated as untrusted data and is not used as proof.
- **Game Troubleshooting Center:** the sandbox can copy or download a `koei-game-troubleshooting` schema version 1 report with sandbox findings in the Center's `findings` shape. It reports sandbox manifest and conflict checks only, marks installation/runtime checks as `not_checked`, and omits file paths, payload bytes, hashes, and local filesystem paths. The Center currently has no report import action; the handoff is an AI-readable compatible report for review, not a direct import flow. A separate detailed `koei-tecmo-mod-sandbox-audit` report includes relative source and destination paths.

Clipboard, downloaded JSON, and same-origin events are data handoffs only. The companion applications are not connected by this sandbox.

## Safety boundary

The app does not parse ZIP imports, execute scripts or plugins, launch games, read game installations, or write to game installations. It imports folder files as inert data into IndexedDB namespaces, with a tab-memory fallback. Folder imports are serialized to avoid duplicate mod-ID races; the workspace planner also blocks duplicate IDs if a restored or externally supplied state contains them. Generic package export requires a separate checkbox and click. A Nioh 2 manager ZIP is a per-mod library import package; the Mod Manager separately revalidates it and requires its own confirmation before installation changes.

Path traversal, absolute paths, reserved Windows names, unsafe ZIP metadata destinations, duplicate/case-colliding paths, file/directory prefix conflicts, missing files, wrong game/build/platform declarations, unsatisfied required Workshop dependencies, mismatched hashes, and fixed size/count limits block staging or export. The downloadable JSON report is designed for review by companion tools and AI assistants; it reports the checks performed and does not claim game-level validation.

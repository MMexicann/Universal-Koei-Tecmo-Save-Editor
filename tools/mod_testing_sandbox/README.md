# Koei Tecmo Mod Testing Sandbox

A browser-local static app for staging compatible mod folders, reviewing destination changes, detecting conflicts, and checking a JSON installation manifest before exporting a ZIP.

## Run locally

Use a static HTTP server from this directory and open `index.html`. Folder import, IndexedDB persistence, Web Crypto, and downloads work best from `localhost` or HTTPS.

```sh
npm test
npm run build
```

The build copies the app into `dist/`, the static deploy directory. The app has no runtime dependencies. The test suite also uses Python 3 for the Mod Manager importer interoperability check; it skips that check when Python 3 is unavailable.

## Safety and integrations

- Imported content is treated as data. The app does not parse or execute archives, scripts, plugins, or game binaries.
- Each mod is stored under its own browser workspace/game/build/mod-ID namespace. IndexedDB is used when available; otherwise the workspace exists in tab memory.
- Workshop project folders place native `mod.json` at the selected root. Replacement paths are NFC-normalized; declared SHA-256 values are checked on import and storage restore, with a 64 MiB per-file hashing limit and a 256 MiB total folder limit. Workshop's default `schema_version: 1` applies if omitted. ZIP packages and verification reports are not opened or trusted.
- Compatibility means the manifest declares the selected registered title ID and a matching selected build/profile. Workshop ranges use the Workshop SemVer rules; other manifests require an exact game build/profile. The short profile list is initial support metadata; there is no native game-format validation.
- Export creates a ZIP download only after a separate confirmation. It never reads or writes an original game installation.
- Mod Creation Workshop project folders use its native `mod.json` schema. The sandbox returns validation issues in a data-only JSON brief.
- Registered save profiles can preview the bounded Smart Playthrough Profiles component contract in PR #112. Nioh 2 has a separate per-mod ZIP handoff matching the Mod Manager importer contract in PR #129 (`.ini` plus supported assets and optional root `koei-mod.json`). Export is blocked when the mod has unresolved required staged dependencies or destination conflicts. Since the manager contract stores dependency IDs only, required version constraints other than `*` also block this handoff. The sandbox-selected build/profile is not represented in the manager ZIP and the manager does not verify it; this handoff is package-format validation only. The manager revalidates imported ZIPs and separately confirms deployment; neither route auto-applies or installs a mod.
- The Troubleshooting Center report uses `koei-game-troubleshooting` schema v1 for sandbox findings and marks installation/runtime checks `not_checked`. The Center currently has no report import action. A separate detailed sandbox audit includes relative paths, conflicts and safety state without mod file bytes.

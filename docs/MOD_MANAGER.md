# Koei Tecmo Mod Manager

The Editing and Research menu and Ctrl+K command palette open the retained Mod
Manager workspace. It imports validated ZIP packages, maintains separate
profiles, checks declared dependencies and conflicts, and applies one verified
game-specific installation method.

## Supported installation method

The first supported adapter is **Nioh 2 for Windows PC**, using the
Nioh 2 Mod Enabler's Mods folder convention. The selected folder must directly
contain nioh2.exe and an existing d3d11.dll. The manager does not download,
install, replace, or remove the loader. Before file changes, the user confirms
that the DLL is the configured Nioh 2 Mod Enabler and that the game is closed.
The manager checks that the DLL exists but cannot identify its version or
prove that it is a compatible loader.

The public [Nioh 2 Vortex extension installation notes](https://github.com/ChemGuy1611/ChemBoy1-Vortex-Games/blob/main/game-nioh2/NOTES_FOR_MOD_AUTHORS.md)
and [layout notes](https://github.com/ChemGuy1611/ChemBoy1-Vortex-Games/blob/main/game-nioh2/EXTENSION_EXPLAINED.md)
identify nioh2.exe, target the Mods directory, and recognize packages with an
.ini file plus .fmt, .vb, .ib, or .dds assets. The extension also distinguishes
root-level d3d11.dll loader packages. The
[Nioh 2 Mod Enabler page](https://www.nexusmods.com/nioh2/mods/18?tab=description)
documents the loader's per-mod DISABLED folder suffix. These sources define
the adapter's scope; the manager independently implements its own validation
and file operations.

No other Koei Tecmo title is supported. In particular, different Wo Long and
other game instructions include root-level files and loader variants that need
their own exact installation and restoration procedures.

## Package format

- Direct import accepts ZIP only. 7z files must be extracted and repackaged as
  ZIP by the user.
- A package must contain exactly one .ini file and at least one .fmt, .vb, .ib,
  or .dds file. Files outside the folder containing the .ini marker are
  rejected. The marker folder is installed under a manager-chosen subfolder in
  Mods.
- Unknown payload types, FOMOD installer layouts, symbolic links, Windows
  device names, path traversal, case-insensitive duplicate paths, and packages
  over bounded entry/count/size limits are rejected. README.md, README.txt,
  CHANGELOG.md, and files named LICENSE or LICENSE.* are ignored.
- Optional root-level koei-mod.json declares metadata and relationships:

        {
          "schema_version": 1,
          "game_id": "nioh2_pc",
          "id": "sample-mod",
          "name": "Sample Mod",
          "version": "1.0",
          "dependencies": [],
          "conflicts": []
        }

  Dependency and conflict IDs use the same safe lowercase ID format. Archives
  without metadata use an ID derived from the ZIP filename.

The library stores imported package bytes in application state and records a
SHA-256 hash and size for every file. The service verifies the stored package
again before installation, and verifies staged bytes before deployment.

## Nexus download handoff

The Nioh 2 workspace can accept the browser's frozen `NexusDownloadRequest`
through `enqueue_nexus_download(request, downloader)`. The manager checks that
the request identifies provider `nexus`, Nexus domain `nioh2`, game ID
`nioh2_pc`, numeric scoped/mod/file-version IDs, safe file/version identifiers,
and a safe display filename. The filename is a logical label; the manager
stages the download as `.zip` and validates the actual archive bytes. It
accepts at most three waiting requests and returns immediately; `True` means a
request entered the queue.

The browser supplies a narrow in-memory downloader capability exposing only
`download_archive(request, destination)`. The manager calls that method with a
destination inside a manager-owned temporary directory. Nexus API keys,
free-user authorization, and resolved signed CDN links stay in the browser
client and are neither read by the manager nor written by it. The queued
request and capability are held only in memory while the job is queued or
active. The manager verifies that the downloader produced a regular ZIP within
the existing 1 GiB archive limit, then passes it to the same `import_archive`
ZIP validation used by local imports. A safe temporary filename derived from
the selected Nexus filename keeps the existing filename-based fallback
metadata useful for packages that do not include `koei-mod.json`. The manager removes the temporary download
after processing and only adds a validated package to the library; it never
enables, installs, applies, or removes a mod as part of the download.

`poll_nexus_download_results()` returns completed jobs without blocking. The
workspace polls this queue and reports success or a sanitized error in its
status area. Results use `imported`, `download_failed`, `rate_limited`,
`package_rejected`, or `manager_error`; messages contain no downloader
exception text. For HTTP 429, the result carries a safely parsed `Retry-After`
delay when available and never retries automatically. An `imported`
result means the package passed validation and is ready for the user to review
before taking a separate profile or install action. This adapter is
intentionally Nioh 2-only even though Nexus discovery
can list other Koei Tecmo games; each additional game needs its own validated
manager installation contract.

## Profiles, conflicts and file changes

Profiles hold independent enabled-mod lists per selected game installation.
Enabling a mod with a declared dependency requires that dependency to be enabled
in the same profile. Declared conflicts and incompatible profile asset paths
block profile application. The manager does not infer load order; it stops when
two selected mods declare a possible asset-path conflict that the loader cannot
resolve safely.

Apply uses the loader's documented enabled folder name and DISABLED suffix.
The service never overwrites an existing Mods entry. It only writes new
manager-owned mod subfolders and renames folders whose entire contents still
match the recorded hashes. Uninstall removes only a verified manager-owned
disabled mod folder. Removing a library entry requires that the mod is
uninstalled and absent from every registered profile.

The separate Mod Creation Workshop emits a generic `mod.json` and
`verification.json` package for declared replacement files. That package is
not an installable input to this Nioh adapter: it must not be converted into a
game folder layout without a dedicated, documented Nioh export contract.
Likewise, the manager does not claim compatibility with exact installed game
builds. The game compatibility analyzer and version tracker produce separate
reports; they are not currently consulted during mod installation. Playthrough
profile component snapshots also do not control this local mod library.

Transactions use a same-volume staging directory, an atomic journal, hash
verification and rollback. On restart, uncommitted operations are rolled back;
committed operations finish cleanup. If a folder changed outside the manager,
or recovery cannot verify either side of a rename, the manager stops and keeps
the journal for inspection rather than deleting or overwriting the changed
folder.

The manager never writes original game files beside nioh2.exe and never
installs or replaces d3d11.dll. It does not keep a duplicate backup of an
original game file because supported operations do not alter one. Uninstalled
mods remain in the local library and can be applied again. User-created content
inside Mods remains untouched.

## Source and license review

The Vortex extension is GPL-3.0; its source is not copied into this MIT project.
The adapter is implemented independently from its public installation
documentation. GokonSoftworks' published license prohibits redistribution and
commercial use, and zmod does not publish a license, so neither codebase is
reused. A separate MIT Nioh loader repository has conflicting Nioh 2/Nioh 3
claims and is not treated as a verified Nioh 2 implementation.

## Evidence limits

The repository tests use synthetic ZIP packages and temporary game-folder
fixtures; they prove path validation, profile rules and manager file operations.
They do not run a game, validate a specific d3d11.dll, or prove that a modded
game loads or saves correctly. See
[Mod Manager validation](MOD_MANAGER_VALIDATION.md) for exact commands and
results.

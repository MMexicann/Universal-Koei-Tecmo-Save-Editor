# Contributor and agent guide

Start with [CONTRIBUTING.md](CONTRIBUTING.md). This project is Mexican's
Universal Koei Tecmo Save Editor: one lightweight Windows executable, an explicit
game/platform library and a shared Tkinter interface. Preserve existing games,
branding, themes, backups, Undo, Review Changes and safe saving.

## Repository layout

- [src/koei_editor](src/koei_editor/): installable application package. The
  launcher and registry live here; `python -m koei_editor` is the source entry.
- [src/koei_editor/games](src/koei_editor/games/): one package per implemented
  game/platform, with its codec, parser, editor and optional presentation.
- [src/koei_editor/shared](src/koei_editor/shared/): scalar contracts/GUI,
  cipher primitives, themes, preferences and copy/backup/path protections.
- [src/koei_editor/research](src/koei_editor/research/): unregistered codecs and
  inspection candidates. Research modules do not imply gameplay support.
- [src/koei_editor/data](src/koei_editor/data/): reviewed runtime JSON metadata;
  no saves, account identifiers or extracted game assets.
- [docs](docs/README.md): architecture, formats, validation, coverage and research.
- [tools](tools/): Windows build, packaging, source-manifest maintenance,
  requirements and [adapter starter](tools/adapter_template/INSTRUCTIONS.md).
- [tests](tests/README.md): format, contract, GUI and packaging checks.
  Procedural generators are test data, not genuine player saves.

Use qualified package imports. Do not add flat root modules, compatibility shims,
`sys.path` injection or alternate launchers to bypass the package structure.
Read the narrower `AGENTS.md` in a folder before changing its files.

## Supported games are explicit

[game_registry.py](src/koei_editor/game_registry.py) declares implemented adapters
with exact game/platform, extension and qualified editor/backend modules.
[supported_games.py](src/koei_editor/supported_games.py) is the canonical code
inventory derived from that registry. [SUPPORTED_GAMES.md](docs/SUPPORTED_GAMES.md)
and the README must agree with it.

For every new adapter or support-scope change, update the registry, reviewed
runtime metadata, canonical supported-game inventory, generated supported-game
document, README and relevant tests together. Add qualified imports/data to the
Windows build and public source manifest. Test the registered adapter and its
documented game/platform before claiming support. A screenshot, console patch,
runtime trainer, cipher vector or research candidate is insufficient.
Never try another game's parser after the selected parser rejects input.

Regenerate the code index and documents with
`python -m tools.update_supported_games`, then verify them with
`python -m tools.update_supported_games --check`.

Unreleased preparation must keep the existing version and latest-release links
accurate. Label the README inventory as development source when it adds support
beyond the published binary. Keep per-game mechanic checklists and exact input
blockers current; do not expose private research files in the source manifest.

## Save-editing rules

Keep parsing out of Tk callbacks and game logic out of the launcher. Reuse the
scalar backend contract (`read_save`, `fields_for`, `stage`, `review`, `serialize`,
`save_as`, `backup`, `restore`); DW3 retains its tagged schema and patch workflow.
Changes remain separate from the immutable original snapshot. Assigning an
opened value must unstage the edit, including unusual original values.

Give writable fields stable IDs, storage width/encoding, validated bounds,
record identity and source/revision evidence. Select dynamic fields from
qualified existing records. Preserve unknown bytes/IDs/flags/padding, original
seeds and higher or unusual values. Max must honor `maxable=False` and must not
use a storage ceiling or published cheat target as a natural gameplay cap.
Keep resources, history, ownership, equipped references and derived values
distinct; preserve reward and prerequisite dependencies. Story completion stays
separate from stats/resources and content unlocks.

Validate game/platform/revision, size, structure and every applicable native
checksum before exposing fields. Establish a byte-exact unchanged roundtrip.
Recompute integrity only during a qualified edit and reparse the output; do not
silently repair damaged input or normalize unknown data. PSU offsets come from
container entries, not an example's absolute position.

Every registered scalar editor must use `BoundScalarAdapter`: it validates the
complete pending map, preserves exact typed opened values as no-ops, and reparses
edited output to confirm every requested value before a copy is accepted. Keep
these guarantees in new scalar backends and the adapter template. Any future
bespoke editor must provide equivalent native read-back and value verification
in its save path. DW3 retains its separate tagged-document and audited patch
workflow.

Use shared safety/storage helpers for file operations. Open separate save copies
outside live game/Steam Cloud directories, reject resolved aliases, detect
changed sources and write atomically to new destinations. Restore must validate
the exact bounded bytes that will be written. Keep automatic backups, staged
Undo, Review Changes and original-source protection intact.

## Research and validation

Do not execute supplied game binaries. Keep binaries, private static analysis,
player saves, owner context, personal paths and external source copies outside
the checkout and release assets. Respect source licences; independently verify
facts rather than importing restricted code/catalogs. Document precise missing
DLLs, assets, owner context, native fixtures or controlled action pairs.

Install and run from the repository root:

```text
python -m pip install -e .
python -m tools.run_tests --workers 4
python -m koei_editor --smoke-test
```

Non-Windows development can install `tools/requirements/dev.txt`; Tk tests need
a display. Run focused tests for changed formats and required integration,
GUI/privacy/build checks. Cover corruption/foreign formats, boundaries and
dependencies, surgical byte preservation, unchanged roundtrips, backups/restore
and source safety. Report failures and skips honestly. Keep procedural evidence,
genuine-file qualification and actual game-load/re-save validation separate.

The parallel runner isolates each test module in a subprocess; do not use threads
to share Tk roots or mutable test globals. New `tests/test*.py` modules are
discovered automatically. CI distributes the entire suite over four Windows
shards and verifies their combined coverage before building. Keep full coverage
and failure propagation intact; timing estimates affect scheduling only. The
serial `python -m unittest discover -s tests -v` remains useful for debugging.
Desktop-dependent Tk modules/test helpers are coordinated within each job to
protect clipboard and focus; preserve that grouping when extending the runner.

## Build and release

Build on 64-bit Windows; Linux checks do not produce or validate a Windows EXE.
See [BUILDING.md](docs/BUILDING.md) and [VALIDATION.md](docs/VALIDATION.md).

```text
python -m pip install -e .
python -m pip install -r tools/requirements/build.txt
python -m tools.package_release --verify-only
python -m tools.build_windows
python -m tools.package_release --verify-executable
```

Keep application, build and package versions consistent. Public paths and hashes
belong in [tools/SOURCE_MANIFEST.json](tools/SOURCE_MANIFEST.json); refresh only
reviewed public files with `python -m tools.refresh_manifest`. Do not weaken
dependency/archive/privacy checks to make a build pass. Coordinate manifest
refreshes in shared work. Respect the repository workflow and branch protection,
and verify the actual published version, descriptions and downloads before
claiming a release is complete.

# Application architecture

The application is an installable package under `src/koei_editor`. Install it
with `python -m pip install -e .` and run `python -m koei_editor` from the
repository root. The entry point delegates to `koei_editor.application.main`.
The same package is bundled into a portable Windows folder with one launcher
and its complete adjacent runtime. The Windows ZIP preserves that folder.

## Package boundaries

| Location | Responsibility |
| --- | --- |
| `src/koei_editor/application.py` | Single Tk root, platform/game selection, retained workspaces, shortcuts and close checks |
| `src/koei_editor/game_registry.py` | Explicit implemented adapters, extensions, platform and qualified module paths |
| `src/koei_editor/supported_games.py` | Canonical supported-game inventory derived from the registry |
| `src/koei_editor/games/<game>/` | Dedicated codecs, parsers, editing rules and presentations |
| `src/koei_editor/shared/` | Scalar contract/GUI, ciphers, appearance, preferences, copied-save safety/storage |
| `src/koei_editor/research/<game>/` | Unregistered inspection and codec candidates |
| `src/koei_editor/data/` | Reviewed runtime JSON definitions and support metadata |
| `tools/` | Windows build, package verification, manifest and inventory maintenance |
| `docs/` | Formats, source provenance, coverage, validation and contributor references |
| `tests/` | Format, contract, GUI/integration, safety and packaging checks |

Imports use qualified package paths. Runtime JSON is packaged with the app;
source and frozen-resource loading use the same reviewed metadata. New game code
belongs in its own package rather than adding root modules or launcher branches.

## Registry, library and sessions

`game_registry.GAMES` contains implemented game/platform adapters. The registry
records independent file qualification separately from published-format support.
Research codecs stay outside that list. A selected game never falls back to a
different game's parser after rejection. `Game.scalar_backend` declares the
same backend for GUI operations and copied-save command-line checks.

The application caches each workspace in a separate frame. Switching games
retains documents, pending edits, field searches and form values. Shortcuts act
on the visible session; closing checks hidden sessions for pending changes.
The library filters by platform and scrolls when needed. Theme preferences store
only the Light/Dark choice, separately from saves; smoke/self-test flows do not
write application preferences.

Pure `shared/library_catalog.py` filtering searches names, editions, short IDs,
platforms and features without probing saves or selecting parsers. Series and
platform filters combine, with a lazily created All-platform view. Compact cards
and retained-session buttons keep large inventories usable. Ctrl+F searches all
platforms; Enter opens only a single result.

Run `python -m tools.update_supported_games` when support changes. Its generated
code index, [supported-game document](SUPPORTED_GAMES.md) and README table must
agree with the registry, runtime metadata and tested behavior.

## Scalar editing contract

[adapter_contract.py](../src/koei_editor/shared/adapter_contract.py) defines the
field, format, frozen document, backend and launcher session contracts. The
bound adapter checks completeness, selected identity and extensions before
calling the dedicated reader/writer. Shared GUI operations use that adapter;
game-specific presentation can inspect the underlying backend.

Scalar backends expose validated original fields, immutable staged changes,
review, serialization and guarded file operations. Assigning an opened value
unstages it. Dynamic fields are derived from qualified existing records, not
manufactured by pending edits. Max honors field metadata, dependency rules and
higher/unusual original values. Search follows labels/groups/records and both
opened and pending displayed values. A record selector uses the field's native
group/slot identity; the Pending only view shows staged rows. Visible-field and
hidden-pending counts make active filters explicit. Max Visible applies only to
filtered rows without dropping hidden pending edits. The selected row, table
sort and scroll position survive refreshes while those rows remain visible.
`limit_values` returns validated Max targets, including a target equal to the
opened value when it is a valid natural maximum. Applying that target removes
a pending reduction when the opened value was already at maximum. Unusual
opened values and fields marked `maxable=False` remain excluded from Max
targets, including after deliberate individual reductions. `maximums` returns
the complete normalized pending map instead; valid target assignments must not
be removed before staging.

Adjust Selected applies an integer delta to each selected pending value through
backend validation, preserving hidden edits and recording one Undo batch. Text
and named choices use their own controls. Revert Selected removes selected
pending keys together and validates the complete final payload, so restoring a
whole loadout does not fail on transient duplicate states. Partial restoration
that leaves invalid dependencies is rejected without changing edits or history.
All accepted GUI edit batches pass the backend's complete payload/dependency
validation before updating pending edits or Undo. The adapter also validates
native dependencies before and after its exact-opened-value unstage shortcut;
restoring one equipped reference cannot silently introduce a duplicate in a
different slot. A backend stage result must contain the requested typed value;
silently dropping a requested edit is rejected before GUI acceptance. Max and
Review failures appear as errors while retaining the opened snapshot, pending
edits and history.

[scalar_presentation.py](../src/koei_editor/shared/scalar_presentation.py)
defines data-only inspection tables, hints and filename guidance. A game can
provide a presentation class or optional backend hooks without introducing
game-ID branches into the shared GUI. Inspectors search all columns. Table sorting changes only display order and
preserves native row IDs/selection; sorting persists when scalar rows refresh.
Selected displayed rows can be copied with headers using Ctrl+C or the inspector
button. Named-choice and text hooks remain optional and backend-validated;
all game encodings and prerequisites stay in the dedicated backend.
An unusual opened choice remains visible as an exact preserved-value option.
Bulk selections receive that option only when every selected field has the
same opened value; Revert Selected restores different originals individually.

[verified_editor.py](../src/koei_editor/shared/verified_editor.py) contains the
existing shared native DW8 XL/PW3 layouts. Other scalar games retain their own
backend and codec in their game package. The
[adapter starter](../tools/adapter_template/INSTRUCTIONS.md) and
[shared contract tests](../tests/scalar_contract.py) document these seams.

## Dedicated formats and research

DW3 retains its tagged Unreal schema, AES envelope, patch writer, feature
modules and established backup conventions in `games/dw3`. It implements the
launcher session contract while retaining its dedicated editing workflow.
Its legacy module version is separate from the application release version.

DW4 Hyper and USA PS2 XL retain separate identities/parsers. PSU metadata and
payload offsets come from directory entries. Sophie 2 retains its attributed
MIT codec, tagged record qualification and occupied-record discovery. Origins
qualifies native slot revisions and distinguishes resource/stat fields from
active campaign, derived progression and reward state. DW7 XL, WO3 Ultimate,
SW4 DX and PW4 use dedicated native format and dependency validation.

The [format and coverage index](README.md) records exact supported revisions,
sources and blockers. Research primitives for additional titles do not create
library cards or authorize gameplay writes from a matching cipher vector,
generic checksum or fingerprint sentinel. Private binaries/assets/player data
are never part of the runtime metadata or public source package.

## Saving, testing and packaging

Shared path/storage helpers reject live-save/Steam Cloud paths and resolved
aliases, detect changed sources, create automatic snapshot backups and write
atomically to new destinations. Restore validates the same bounded bytes that
will be written. No-edit serialization is byte-exact; edits change only declared
fields and required integrity metadata, preserving unknown bytes and seeds.

Console backends can require an identity companion. An optional
`prepare_self_test_copy(document, destination)` hook prepares minimal identity
metadata for copied-save CLI validation; full account and signing metadata is
never copied. The ordinary registered reader then validates that working copy.

Windows uses native CNG; non-Windows development optionally uses the crypto
provider in `tools/requirements/dev.txt`. GUI tests need a display. Procedural
tests, genuine copied-file qualification and actual game loading remain separate
forms of evidence; see [VALIDATION.md](VALIDATION.md).

The build and packager in `tools` traverse qualified registered dependencies,
collect package metadata and validate reviewed paths against
`tools/SOURCE_MANIFEST.json`. Package checks protect against private files,
foreign binaries and personal paths. The Windows workflow runs native tests,
EXE smoke/startup and archive/hash checks before publishing a new release.
Existing releases are not overwritten. See [BUILDING.md](BUILDING.md).

Context-dependent console adapters may implement `prepare_copy_context` for
the shared copied-save self-test. The backend validates and copies its original
bounded companion opaquely into the new private output before reopening the
gameplay copy. It never fabricates identity metadata, extracts account values
or constructs PFD/STFS signing; self-test outputs remain private local files.

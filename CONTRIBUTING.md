# Contributing

Contributions can improve an existing editor, document a format, or establish a
new game/platform mapping. Start with this workflow; AI coding agents should also
read [AGENTS.md](AGENTS.md). The application stays a single lightweight Windows
executable with dedicated game logic and a shared Tkinter interface.

## Run and understand the project

From the repository root with Python 3.10 or newer and Tkinter:

```powershell
python -m pip install -e .
python -m koei_editor
python -m tools.run_tests --workers 4
python -m koei_editor --smoke-test
```

Windows uses native CNG for DW3 encryption and needs no third-party runtime
package. Non-Windows development may install `tools/requirements/dev.txt`; GUI work
requires a display. Read the parser and tests for the format you change.
The parallel runner uses isolated processes, so Tk roots and mutable fixtures
are never shared between modules. Reduce `--workers` on machines with limited
memory. On Linux, run it under `xvfb-run -a` when no display is available.
Use ordinary `unittest discover -s tests -p 'test_your_game.py' -v` for focused
checks or serial discovery for debugging; run the full suite before submission.
The [documentation index](docs/README.md) groups architecture, format and coverage
notes. Application code belongs in `src/koei_editor`, game adapters in
`src/koei_editor/games/<game>`, shared behavior in `src/koei_editor/shared`,
unregistered candidates in `src/koei_editor/research`, runtime JSON in
`src/koei_editor/data`, and build/development helpers in `tools`.
[ARCHITECTURE.md](docs/ARCHITECTURE.md), [SAVE_FORMAT.md](docs/SAVE_FORMAT.md),
[KOEI_FORMATS.md](docs/KOEI_FORMATS.md) and
[DW4_PLATFORM_FORMATS.md](docs/DW4_PLATFORM_FORMATS.md) provide background;
[VALIDATION.md](docs/VALIDATION.md) records evidence and remaining checks.

`src/koei_editor/application.py` owns the library and sessions, while `src/koei_editor/game_registry.py` declares
explicit adapters. `src/koei_editor/shared/verified_gui.py` delegates scalar editing to an injected
backend. DW8/PW3 share `src/koei_editor/shared/verified_editor.py`; DW4 Hyper and PS2 XL have separate
parsers. DW3 keeps its existing schema, feature modules and patch writer.

## Add a scalar adapter

Start with [adapter_template/INSTRUCTIONS.md](tools/adapter_template/INSTRUCTIONS.md).
Its parser/editor/test scaffolds stay unregistered and reject unmapped files.
[adapter_contract.py](src/koei_editor/shared/adapter_contract.py) defines `ScalarField`, `ScalarFormat`,
`ScalarDocument`, `ScalarBackend` and the common launcher `EditorSession` contract.
Existing game writers keep their own codec/container logic. The bound adapter
checks the selected game/platform and extension before delegating; it never tries
another backend after rejection. DW3 implements the launcher session contract
while retaining its tagged document and established patch workflow.

A scalar `Game` registration declares a qualified backend such as
`scalar_backend='koei_editor.games.your_game.parser'`.
That enables the shared copied-save self-test and binds the backend to the exact
game/platform. The shared GUI's core operations use the same contract, preserving
staging, batch Undo, review, automatic backups, source-change checks and atomic
Save As to a new destination. Save As returns a freshly validated frozen document;
assigning an opened value unstages it. `SaveError` rejects invalid formats/values;
`FileExistsError` rejects an existing destination.

Every new adapter or support-scope change must update the registry, runtime
metadata, canonical [supported-game code](src/koei_editor/supported_games.py),
generated [supported-game document](docs/SUPPORTED_GAMES.md), README and relevant
tests together. The code inventory derives from registered adapters; research
notes and screenshots do not add supported games. Verify the registered game,
platform, module paths and documented features before claiming support.
Use qualified package imports; do not add flat root modules or import-path shims.

After updating the adapter and metadata, run:

```powershell
python -m tools.update_supported_games
python -m tools.update_supported_games --check
```

This regenerates the readable code index, supported-game document and README
table from the registry. A passing consistency check does not substitute for
format qualification or the adapter's required tests.

Use `maxable=False` for fields that permit deliberate individual edits but should
be excluded from bulk Max, such as historical counters or dependency-sensitive
choices. The backend's `limit_values` and `maximums` must honor that metadata,
preserve higher existing values and use validated original records to select fields.
`limit_values` returns assignments to stage, including targets equal to opened
values so Max can remove a pending reduction. `maximums` returns the complete
normalized pending map. Validate native dependencies for the final batch and
after removing a pending key; the original-value shortcut must not skip them.

When native title identity requires a companion file, qualify that context on
file reads and safe saves. The optional backend hook
`prepare_self_test_copy(document, destination)` supplies the qualified companion
for private copied-save CLI outputs. Prefer minimal identity-only context.
Profiles that explicitly bind the complete original companion must preserve
those exact opaque bytes, check their bounded digest before writing and after
atomic creation and actual destination read-back, and
use atomic new-file storage. Never synthesize or edit account/signing fields,
interpret ownership, or include companion/player bytes in public outputs. In-memory `decode` remains a profile parser.

Optional backend `record_label`, `field_hint` and `inspection_rows` hooks supply
data for the standard inspector. Richer read-only views subclass
`ScalarPresentation` in [scalar_presentation.py](src/koei_editor/shared/scalar_presentation.py), returning
`InspectionTable` objects and field guidance. The game's editor declares its
`presentation_type`, summary and subtitle. Keep game-specific presentation in
adapter modules; adding a game should require no shared GUI or CLI ID branches.

For independently proved enumerations, an optional `field_options(document,
field_id)` hook returns `(native_integer, display_name)` choices. Backend
validation remains authoritative; choices are excluded from Max unless a
meaningful natural maximum exists. Proven fixed-width names may declare
`kind='text'`, with byte/encoding validation in the game backend and
`maxable=False`. The shared GUI keeps mixed text/numeric bulk edits separate.

Mapped numeric fields can declare an `experimental_maximum` property containing
their exact native encoding ceiling. Use `within_numeric_limits` from the shared
experimental policy in their numeric validator; None keeps the normal range.
Declare signedness, packed widths, bias, sentinel exclusions or exact float
precision explicitly. Choices/flags/references retain hard constraints. The
bound adapter scopes an acknowledged experimental session through all save and
read-back operations; backend format/identity/integrity checks still apply.
Test both modes, ceilings/overflow, cache isolation, reopened higher originals,
Max, Undo and actual destination read-back. See
[experimental editing](docs/EXPERIMENTAL_EDITING.md).

Subclass [tests/scalar_contract.py](tests/scalar_contract.py)'s
`ScalarContractTests` alongside `unittest.TestCase`, providing `game_id` and
`fixture_bytes()`. Its shared checks exercise no-op round trips, immutable staged
changes and unstage, review, surgical payload edits, invalid fields/values,
cross-platform documents, backup/restore, existing destinations and source
changes. Declare `payload_integrity_offsets` only for mapped native integrity
stored inside the decoded payload. Add separate format-specific corruption and
dependency checks and record copied-native/in-game evidence honestly.

```powershell
python -m unittest tests.test_adapter_contract -v
python -m unittest tests.test_universal_app -v
python -m koei_editor --smoke-test
```

## Map a save format

1. Identify the exact game, platform, region, build and DLC. Record source/license
   evidence. A console export, asset decryptor or memory trainer is not proof of
   a PC disk format, and related editions can differ.
2. Work on reviewed copies outside live save and cloud folders. Record input
   hashes locally. Keep saves, account context and detailed private reports out
   of Git, public documents and release archives.
3. Identify the container, native title/revision markers, lengths, alignment,
   encoding/encryption layers and integrity coverage. Establish a byte-exact
   no-edit decode/encode roundtrip before gameplay writes.
4. Capture a before/after pair with one controlled game action and displayed
   values, plus an unchanged control. Use mechanics documentation to distinguish
   current values, lifetime totals, ownership, equipped references and derived
   stats; correlate those concepts with the actual serialized bytes.
5. Document each field's offset, width/endianness, stride/count, encoding, IDs,
   valid values, dependencies and source/version. Confirm boundaries against
   additional records/copies; do not promote plausible patterns to proven fields.
6. Implement surgical writes, recompute integrity, reparse, and compare decoded
   payloads. Only declared fields and their required integrity/size metadata may
   change. Preserve unknown bytes, original seeds and container entries/padding.
7. Test valid edits, invalid values, corruption/truncation, wrong editions,
   immutable input, backups/restore and Undo/review. Record actual game
   load/re-save separately, including the tested edition/build.

Use read-only inspection for uncertain fields. Research notes and candidate
codecs can be contributed without adding a game card. A library entry needs an
implemented editor with explicit platform provenance; record source-backed
format support separately from independent native-save validation. A stream
vector or a passing procedural test never substitutes for a complete real save.

## Building an edited save

Here, building a save means **modifying a validated copy and recomputing its
codec/container integrity**. It does not mean inventing a playable file from
zeros or treating a synthetic test fixture as a player's save.

For example, the existing DW8 backend stages a supported field, serializes in
memory, then writes through its guarded Save As workflow:

```python
from pathlib import Path
from koei_editor.shared import verified_editor as backend

original = backend.read_save(Path(r'D:\SaveCopies\dw8-copy.dat'), 'dw8xl')
assert backend.serialize(original, {}) == original.raw
changes = backend.stage(original, {}, 'gold', 12345)
encoded = backend.serialize(original, changes)
reopened = backend.decode(encoded, 'dw8xl')
assert reopened.payload == backend.changed_payload(original, changes)
backend.save_as(original, changes, Path(r'D:\SaveCopies\dw8-edited.dat'))
```

The destination must be new. `save_as()` checks the opened source, preserves a
backup and uses atomic storage. Avoid direct `write_bytes()` on player data.
Reuse `src/koei_editor/shared/verified_self_test.py` rather than building an alternate file-write path:

```powershell
python -m koei_editor --game dw8xl --self-test "D:\SaveCopies\dw8-copy.dat" "D:\SaveCopies\DW8Test"
```

Use a new/empty output directory. Require exit 0, `success: true`, input-hash
preservation and the reported backup/roundtrip checks. `--game pw3`,
`--game dw4hyper`, `--game dw4xl_ps2`, `--game atelier_sophie2` and `--game origins`
select their own registered scalar backends and extensions. Origins accepts
native slot copies; `USER.dat` system data is excluded.
DW3 uses `python -m koei_editor --self-test INPUT OUTPUT`. These reports do not
establish in-game loading or turn a procedural input into genuine-file evidence.

## Fixtures and focused tests

The public suite uses generated fixtures and published known-answer vectors.
Good examples are `synthetic_raw()` in
[tests/test_verified_editors.py](tests/test_verified_editors.py), `procedural_raw()`
in [tests/test_dw4hyper_format.py](tests/test_dw4hyper_format.py), and
`procedural_psu()` in [tests/test_dw4xl_format.py](tests/test_dw4xl_format.py).
Use distinctive unknown data so unintended zeroing becomes visible. Crypto
provider vectors are in [tests/test_save_provider.py](tests/test_save_provider.py).

Optional copied real saves are selected locally:

| Environment variable | Copied input |
| --- | --- |
| `DW8XL_SAVE_COPY` | Native PC DW8 XL `.dat` |
| `DW7XL_SAVE_COPY` | Native PC DW7 XL Definitive gameplay `.dat` copy |
| `WO3U_SAVE_COPY` | Native PC WO3 Ultimate Definitive `SAVEDATA.BIN` copy |
| `SW4DX_SAVE_COPY` | Current-revision SW4 DX gameplay `.dat` copy |
| `SW2_PC_SAVE_COPY` | Original 2008 Windows PC Samurai Warriors 2 revision-2 gameplay `.dat` copy; not HD/XL/console |
| `WO1_NATIVE_SAVES` | Folder of reviewed flat original 2008 Windows PC Warriors Orochi revision-2 `.dat` copies; not Z/later/console |
| `PW3_SAVE_COPY` | Native PC Pirate Warriors 3 `.dat` |
| `PW4_SAVE_COPY` | Native revision-15 one-step-region PW4 gameplay `.dat` copy |
| `DW4HYPER_SAVE_COPY` | Native PC Hyper `save.dat` copy |
| `DW4XL_PSU_COPY` | USA PS2 XL `.psu` export |
| `SOPHIE2_SAVE_COPY` | Native Steam 1.08 Atelier Sophie 2 `data.dat` copy |
| `ORIGINS_SAVE_COPIES` | Folder of copied native Steam `SLOT*.dat` Origins saves |
| `NIOH2_SAVE_COPY` | PC Nioh 2 user `.bin` copy for read-only inspection |
| `NIOH_SAVE_COPY` | Native PC Nioh USER copy for strict read-only codec checks |
| `NIOH3_NATIVE_DIR` | Reviewed native Nioh 3 USER copies for codec and surgical edit checks |
| `NIOH3_ENCRYPTED_COPY` / `NIOH3_DECRYPTED_COPY` | Matching reviewed Nioh 3 native USER reference pair |
| `NIOH3_SAVE_COPY` / `NGII_SAVE_COPY` | Native copies for real Tk editor save/backup/restore workflows |
| `NGII_NATIVE_DIR` | Extracted original Xbox 360/Xenia Ninja Gaiden II revision-6 story copies |
| `BERSERK_VITA_NATIVE_DIR` | Reviewed decrypted EU PCSB01085 Berserk Vita gameplay copies with original `sce_sys/param.sfo` |
| `DOA5_PS3_NATIVE_DIR` | Reviewed original US/EU PSN DOA5 native exports with original `PARAM.SFO`; PS3 PFD extraction/signing stays external |
| `POKEMON_CONQUEST_NATIVE_DIR` | Reviewed vanilla US Nintendo DS raw Pokémon Conquest `.sav` copies; emulator/container wrappers excluded |
| `SIGMA_PC_NATIVE_DIR` / `SIGMA2_PC_NATIVE_DIR` | Separate Master Collection PC research-inspection copies |
| `NG2_BLACK_STEAM_NATIVE_DIR` | Black Steam native GVAS copies for research inspection |
| `SOPFFO_NATIVE_DIR` / `SOPFFO_STEAM_NATIVE_DIR` | Separate Epic launch / Steam native USER and SYSTEM research copies |
| `DW6_SAVE` | Native original Windows DW6 `save.dat` copy |
| `DW9EMP_SYSTEM_COPY` | Current native PC DW9 Empires SYSTEMDATA `SAVEDATA.BIN`; a missing genuine fixture skips |
| `DW7_PS3_US_COPY` / `DW7_PS3_EU_COPY` | Copied decrypted PS3 DW7 US/EU `APP.BIN` exports |
| `SW4_PS3_US_COPY` | Copied decrypted PS3 SW4 US `DATA.BIN` export |
| `DW7E_PS3_SYSTEM_COPY` | Copied decrypted US PS3 DW7 Empires SYSTEM `DATA.BIN` |
| `HYRULE_SAVE_COPY` / `CALAMITY_SAVE_COPY` | Independently shared Wii U Hyrule `APP.BIN` / Switch AoC `svdt` exports |
| `HYRULE_DE_COPY` | Copied native Switch Definitive Edition `zmha.bin` |
| `FE_WARRIORS_SAVE_COPY` | Copied native Switch FE Warriors `scenario0`/`scenario1`/`scenario2`; modified reference state is labelled |
| `HYRULE_SOURCE_REFERENCE` / `CALAMITY_SOURCE_REFERENCE` | Private upstream reference examples; distinct from independent player-save evidence |
| `STARS_SAVE_COPY` | Native All-Stars complete PC container for AES-envelope, gold-edit and GUI checks |
| `OROCHIZ_NATIVE_SAVE` | Native Orochi Z revision2 `save.dat` for unchanged/surgical field and GUI checks |
| `DW8E_SAVE_FOLDER` | Reviewed native DW8 Empires system/campaign/quick copies for codec checks |
| `KATANA_GOLDEN_DIR` | Locally reviewed upstream encrypted/decrypted reference-pair directory |
| `ROTK13_SAVE_COPIES` | Private folder of reviewed original PC revision-14 TC XIII campaign `.s13` copies |
| `DW3_TEST_REPORTED_SAVE` | Explicit DW3 regression copy used by `test_save_variants.py` |

For example:

```powershell
$env:DW8XL_SAVE_COPY = 'D:\SaveCopies\dw8-copy.dat'
python -m unittest discover -s tests -p 'test_verified_editors.py' -v
```

Tests requiring a missing fixture skip. Count skips honestly. A real-file
roundtrip is stronger than a generator test, but still does not prove that the
edited file loads in-game. Do not commit fixture contents or private source URLs.
See [EXISTING_EDITORS.md](docs/EXISTING_EDITORS.md) for source/licence checks and
[ATELIER_SOPHIE2_FORMAT.md](docs/ATELIER_SOPHIE2_FORMAT.md) for the new tagged adapter.

## Submit code and build artifacts

Fork the repository, create a focused branch, and open a pull request against
`main`. Link supporting public evidence and describe the exact game/platform
and revisions affected. Use issues to share reproducible bugs or format findings
without attaching private saves or game files.

Keep patches focused and preserve existing features, themes and author branding.
Explain the problem, resulting behavior, format/evidence source, validation and
remaining uncertainty. Prefer meaningful regressions around byte preservation,
identity, integrity or dependencies over tests that merely repeat a constant.
Keep parsers independent from GUI callbacks and route user operations through
backups, staged changes, Undo, review and new-destination Save As.

Build on 64-bit Windows using [BUILDING.md](docs/BUILDING.md). The key checks are:

```powershell
python -m pip install -e .
python -m pip install -r tools/requirements/build.txt
python -m tools.package_release --verify-only
python -m tools.build_windows
python -m tools.package_release --verify-executable
```

PyInstaller produces one standalone Windows EXE. A Linux validation bundle does
not test Windows CNG or constitute a Windows release. Add new public metadata to
`tools.build_windows.DATA` and explicit adapter imports through the registry as needed.

Packaging uses an explicit source whitelist, not every file in the checkout.
After reviewing public changes, refresh existing hashes with
`python -m tools.refresh_manifest`; include new public paths explicitly with
`python -m tools.refresh_manifest --add FILE...`, then run the verifier. Preserve the
matching application/build/manifest version. Exclude game files, saves, account
identifiers, personal paths and third-party binaries; document dependency licenses
instead of weakening the packager. Build/package integrity and privacy checks
must pass before distributing assets.

# Tests

From the repository root with Python/Tkinter, install the source package and run:

```text
python -m pip install -e .
python -m tools.run_tests --workers 4
```

Public rule and boundary tests run without a save. Private-fixture integration tests are skipped when the research copy is absent; no player save is distributed. See ../docs/VALIDATION.md for the completed checks.

The runner schedules whole test modules in isolated Python subprocesses and
prints module results, test totals, skips and failures.
Choose fewer workers on machines with limited memory. GUI tests still need a
display; on headless Linux use `xvfb-run -a python -m tools.run_tests --workers 4`.
Private-fixture environment variables are inherited by every worker.
Modules using Tk or Tk test helpers are coordinated within each job because
clipboard and focus belong to the desktop, even when Python processes differ.

CI uses four Windows shards with two processes per shard. Each shard uploads
its report and logs, including on failure. The build verifies all four reports
cover the complete current module inventory exactly once before building the
EXE. New modules join automatically; scheduling estimates in
`tools/test_timings.json` are not a list of allowed tests. No tests are omitted
to meet a time target, and failures, missing reports and import errors fail CI.

For a serial run or a focused module, the usual commands remain available:

```text
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p 'test_your_game.py' -v
```


The universal application adds `test_universal_app.py`, `test_origins_tools.py`,
`test_save_provider.py` and `test_universal_packaging.py`. Origins synthetic files
exercise opaque copy operations only; they are not real gameplay fixtures.
GUI tests need a display. The optional non-Windows crypto provider is in
`tools/requirements/dev.txt` (relative to the repository root). `python -m koei_editor --smoke-test` initializes the
selector and all registered interfaces. See ../docs/ORIGINS_FORMAT.md for Origins evidence.

`test_verified_editors.py` adds independently generated PC fixtures, published
cipher known answers, native checksums, corruption rejection, bounded scalar
edits, unchanged-byte round trips, backup/restore, source-change detection and
the explicit game/platform support gate. GUI tests exercise both new PC editing workflows.
To validate explicit copies of real samples without adding them to the source tree:

```powershell
$env:DW8XL_SAVE_COPY = 'D:\SaveCopies\dw8xl\save.dat'
$env:PW3_SAVE_COPY = 'D:\SaveCopies\pw3\OP3WIN0000.dat'
python -m unittest discover -s tests -p 'test_verified_editors.py' -v
```

These two sample tests skip when no path is supplied. They verify files, not
game loading. See ../docs/KOEI_FORMATS.md for public reference evidence and PC scope.

Game-mechanics tests cover the inferred/read-only PW3 progression model,
bounded-limit behavior, higher-value preservation and read-only inspection.
See ../docs/GAME_MECHANICS.md for source evidence and unresolved gameplay dependencies.

`test_dw4hyper_format.py` uses procedural fixtures alongside independent genuine-file qualification of
the native PC profile. To run its genuine-file check, set `DW4HYPER_SAVE_COPY` to an
unchanged copied native Hyper `save.dat` outside live save folders. The real-file
case skips without that path; procedural tests never imply genuine sample validation.

`test_p5s_codec.py` reproduces the attributed 32-byte PC stream vector and checks
read-only candidate spans; its research-only partial vector is distinct from complete native PC
qualification in `test_p5strikers_pc.py` and the independent review tests.
`test_dw8e_candidate_codec.py` exercises independent procedural envelope/checksum
arithmetic; the newer registered custom-horse editor and genuine
SystemSave checks live in `test_dw8e_horses.py`.

`test_dw4xl_format.py` covers the separate USA PS2 PSU parser with procedural
containers, directory-order/padding preservation and native inner checksum
validation. Its genuine-file test uses `DW4XL_PSU_COPY` and skips without an
explicit copied export. Console metadata and PC Hyper saves are rejected.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the mapping and copied-save workflow
and [AGENTS.md](../AGENTS.md) for project conventions.


Unreleased expansion tests cover DW5 Special, DW8 Empires custom horses, Hyrule
Warriors Legends, native PC Persona 5 Strikers, Wo Long and decrypted PS3 Ayesha
separately. Optional fixture environment variables are documented in their game
notes; private native bytes never enter the source tree. Independent audit tests
exercise field eligibility, malformed staging, all-field surgical edits and
preserved integrity/dependencies. Library search, named choices, text controls,
column sorting, Ctrl+C and existing editor sessions have real Tk regression
checks. Native-file tests are not actual edited game-load tests.

Console expansion tests keep US PS3 WO3 Ultimate (`test_wo3u_ps3.py`) separate
from PC Definitive, and US PS3 DW8 Empires SYSTEM (`test_dw8e_ps3_horses.py`,
`test_dw8e_ps3_gui.py`) separate from PC and console campaigns. Genuine copies
use `WO3U_PS3_US_COPIES` and `DW8E_PS3_SYSTEM_COPY`, with original `PARAM.SFO`
beside each input. Actual Tk workflows and the registered copied-save self-test
cover private opaque metadata propagation, backups, Undo/Review and restore.
`test_console_expansion_registry.py` verifies platform separation and that
unqualified candidates cannot create library cards.

Strikeforce and Xbox SW2 tests are read-only native observations, not editing
qualification. Their optional inputs are `STRIKEFORCE_PS3_US_COPY`,
`STRIKEFORCE_PS3_US_SECOND_COPY` and `SW2_XBOX360_EXPORT_COPY`. SW2 HD's four
procedural probe tests demonstrate partial-sum collisions and uncovered bytes;
no genuine HD file is claimed. See each console checklist for exact blockers.

Additional Musou PC tests cover the separately qualified SW4-II revision
`0x31A4` adapter and unregistered read-only Spirit of Sanada outer framing.
Set `SW4II_SAVE_COPY` and optionally `SW4II_SECOND_SAVE_COPY` to separate native
gameplay copies; set `SANADA_PC_SAVE_COPIES` to a copied directory containing
`SAVEDATA0000.dat`, `SAVEDATA0001.dat` and `SYSDATA.dat`. Genuine-file cases skip
when those inputs are absent. `test_sw4ii_gui.py` uses the genuine copy when
provided, otherwise a procedural fixture, and requires Tk with a display.
See [SW4-II](../docs/SW4II_FORMAT.md) and
[Sanada](../docs/SANADA_PC_RESEARCH.md) for exact qualifications and blockers.

The Gust expansion adds format, scalar-contract, independent-audit and GUI tests
for original PC Sophie, original PC Ryza 2 and PC Fatal Frame II Remake. The GUI
checks use the registered editors and cover editing, Undo, Review Changes,
themes, Save As, backup and Restore. Optional genuine-file checks use copied
inputs outside live save folders:

| Environment variable | Copied input |
| --- | --- |
| `SOPHIE_SAVE_COPIES` | Folder of original Sophie extensionless `GAMEDATA*` snapshots |
| `SOPHIE_SAVE_COPY` | One original Sophie gameplay copy for the GUI check |
| `RYZA2_SAVE_COPY` | Original Ryza 2 PC gameplay `.dat` copy |
| `FF2_REMAKE_SYSTEM_COPY` / `FF2_REMAKE_GAMEPLAY_COPY` | Native Fatal Frame II Remake system/gameplay `.bin` copies |
| `FATAL_FRAME2_SYSTEM_COPY` | Native Fatal Frame II Remake system copy with positive Photo Points for the GUI check |
| `RORONA_DX_CANDIDATE_DIR` / `MERURU_DX_CANDIDATE_DIR` | Folders of native PC gameplay copies for read-only structural checks |

The Arland checks qualify layout and byte preservation, not integrity or writable
support. Procedural checks do not establish genuine-file or actual game loading.

Licensed Musou tests in `test_gundam1_ps3*`, `test_kens_rage1_ps3*` and `test_kens_rage2_ps3*` cover
qualified decrypted PS3 profiles, identity-only companions, native integrity,
manual dependency guards and copied GUI workflows. Genuine fixture paths are
selected explicitly; see [format and evidence notes](../docs/LICENSED_MUSOU.md).
The genuine Ken's Rage 2 samples have completed galleries: unchanged preservation
is genuine evidence; unlock edits currently use procedural locked entries.

`test_rotk13_format.py` covers original PC XIII revision-14 additive encoding,
preview integrity, tagged campaign identity, city quantities, storage boundaries,
unknown-reference preservation, shared scalar contracts and safe copy/restore.
`test_rotk13_gui.py` exercises the actual shared Tk workflow. Set
`ROTK13_SAVE_COPIES` to a private directory of complete reviewed `.s13` campaign
copies to enable genuine-file and genuine-GUI checks. These tests do not establish
an edited game load. See [the format evidence](../docs/ROTK13_FORMAT.md).

`test_berserk_aot_envelopes.py` checks unregistered read-only outer-envelope
diagnostics for Windows Berserk, AoT1 and the observed AoT2 PK sample. Its
procedural/adversarial cases include checksum collisions, wrong-family inputs,
immutable snapshots, exact byte preservation and absence of gameplay/file-write
APIs. Optional genuine tests use `BERSERK_SAVE_COPY`, `AOT1_SAVE_COPY` and
`AOT2_PK_SAVE_COPY`; missing inputs skip. These prove no gameplay mappings or
edited game loads. See [the evidence note](../docs/OTHER_KOEI_PC_RESEARCH.md).

Original Windows PC Samurai Warriors 2 and Warriors Orochi have separate
`test_sw2_pc_format.py` / `test_sw2_pc_gui.py` and
`test_wo1_pc_format.py` / `test_wo1_pc_gui.py` suites. Set `SW2_PC_SAVE_COPY`
to a reviewed SW2 `.dat` copy and `WO1_NATIVE_SAVES` to a folder of reviewed
flat Orochi `.dat` copies to enable genuine-file tests. Missing inputs skip.
`test_classic_musou_review.py` and `test_classic_musou_safety.py` independently
check malformed changes, unusual-value preservation, dependencies, retained
GUI sessions and live-path protection. See the separate
[SW2](../docs/SW2_PC_FORMAT.md) and [Orochi](../docs/WO1_PC_FORMAT.md) evidence;
generated fixtures and file-level tests do not establish edited game loading.

`test_three_houses.py` and `test_three_houses_audit.py` distinguish procedural
gameplay save-format v13/v23 fixtures from optional private extracted slots.
`THREE_HOUSES_SAVE_COPY` selects a reviewed copied slot;
`THREE_HOUSES_REVIEW_COPIES` selects multiple copied slots separated by the
local `os.pathsep`. Tests cover checksum/shape rejection, original-record
eligibility, ordinary-item restrictions, unlimited-durability protection,
unusual values, immutable staged changes, surgical edits, guarded backups and
restore. Live Tk workflows skip when no existing display is available. These
checks do not establish exact software build, DLC entitlement or Switch loading.

New native-profile checks optionally use `RYZA1_SWITCH_NATIVE_DIR`,
`DW8XL_PS3_SAVE_COPY` (with original `PARAM.SFO`),
`DW8XL_PS3_REFERENCE_COPY`, and `DQB2_PC_SAVE_COPIES` (local path-separated
files/directories). Keep these files and variables private; missing fixture cases
skip explicitly. Public procedural checks are distinct from native-file and
edited in-game validation.

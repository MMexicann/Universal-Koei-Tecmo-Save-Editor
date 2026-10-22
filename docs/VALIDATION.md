# Universal development validation

## Game Version & Compatibility Tracker

The tracker validation uses generated Steam library folders and manifests with
synthetic app IDs/build IDs, procedural compatibility records, and temporary
local history files. The fixtures cover exact `(game profile, Steam app ID,
platform, build ID, artifact)` matches; unknown results for other apps/builds;
verified-to-unsupported rechecks; per-category unlisted-artifact warnings;
build-change history; malformed metadata; and path-free persistence. No game is
launched and the fixture does not depend on a real Steam account or installed
game.

The packaged compatibility catalog currently has no exact-build records. In
that state the tracker reports `unknown` for all categories. This is deliberate:
there is no reviewed evidence in this checkout for a specific editor, mod,
configuration tool, or asset format on an exact Steam build. The validator
requires exact app/build identities and versioned evidence before showing
`verified` or `unsupported`.

```json
{
  "schema": "koei-version-tracker-validation/v1",
  "status": "pass_with_gui_skips",
  "base_commit": "048563c1f9f608c9b0572560176093fe6a72834d",
  "commands": {
    "unit_tests": "PYTHONPATH=src python -m unittest tests.test_version_tracker tests.test_save_discovery tests.test_help_center tests.test_universal_app tests.test_game_data_encyclopedia",
    "source_manifest": "PYTHONPATH=src python -m tools.package_release --verify-only",
    "supported_game_inventory": "PYTHONPATH=src python -m tools.update_supported_games --check"
  },
  "unit_tests": {
    "run": 113,
    "passed": 82,
    "skipped": 31,
    "failures": 0,
    "gui_skips": "Tk display tests skipped because DISPLAY and xvfb-run are unavailable."
  },
  "source_manifest": {
    "status": "passed",
    "verified_public_files": 1208
  },
  "supported_game_inventory": {
    "status": "passed",
    "registered_adapters": 98
  },
  "syntax_and_diff_checks": {
    "py_compile": "passed for changed Python modules and tests",
    "git_diff_check": "passed"
  },
  "fixture": {
    "type": "procedural Steam metadata and temporary path-free history",
    "real_game_launched": false,
    "real_steam_install_used": false,
    "local_install_paths_persisted": false
  },
  "catalog": {
    "exact_compatibility_records": 0,
    "missing_exact_record_status": "unknown",
    "verified_or_unsupported_claims_seeded": false
  },
  "release_created": false,
  "version_bumped": false
}
```

## v3.1 common-core editing and resource transfers

The new DW8 XL PS4 editor reuses the already-qualified CUSA00397 zero-extension
reader and common field mapping. Bound-contract, Tk, backup/restore and metadata
race tests cover surgical writes and original-context preservation. The public
full-file reference lacks original console metadata, so generated title-only
context does not establish independent native-export evidence or game loading.

The four new resource-only WO3U/SW4 PS3 ↔ PC routes use independently mapped
balances and each endpoint's existing writer. Procedural tests check numeric
endian conversion, every retained destination byte, bounds, native integrity,
seed/header preservation, exported readback and reverse copies. Optional paired
native checks skip without complete original context. The narrower one-way WO3U PS4 scope transfers 354 directly documented
crystal/orb/material balances; actual public-origin payload and native-PC guarded
Save As checks preserve every other PC byte. The reference lacks original PS4
metadata; generated context tests remain separate. The second scope verifies
1,079 values across 1,805 mapped bytes, preserving every other PC byte and
the complete saved-state block, including exact unusual-target no-ops. Complete WO3U/SW4 PS4
transfers and edited/converted game loading remain unverified.
[Scope, evidence and blockers](WARRIORS_PS4_TRANSFERS.md).

## v2.6 new titles and shared tools

Orochi Z native initial and growth tables independently establish all five saved
base-stat bounds for 96 IDs. Two distinct gameplay states qualify 1,526 boundary
serializations, with unusual originals preserved. Two distinct WO3 Ultimate PC
states qualify 526 surgical compatibility resets. Native GUI/save/backup/restore
checks preserve ownership, equipment and unrelated bytes.

Fatal Frame II US PS2 research checks eight complete exports, 32 occupied
instances and twelve distinct gameplay states. Private candidate assignments
preserve container/checksum bytes, but that does not independently prove retail
stock linkage or dependency rules. AI-assisted EU prototype leads and separate
retail RAM stock labels are insufficient for that missing step. The proposed
writer stays unregistered and outside the release. [Research](FATAL_FRAME2_PS2_FORMAT.md).

Troy EU PS3 qualification independently decrypts the original representation
and matches the supplied RPCS3 bytes: one native state, two representations. A
separate bitwise CRC, complete table walk, exact original SFO, surgical native
exports and real Tk backup/save/restore workflow corroborate the narrow profile.
Ambiguous high wallet words remain opaque. [Exact scope](TROY_PS3_FORMAT.md).

Save Library, presets, pins and CSV review regressions cover cancellation before
Tk delivery, changed roots with retained file inodes, original-source/context
freshness before and after native serialization, full-map validation, source-
bound field-definition fingerprints, frozen complete exports, typed values and
spreadsheet-safe labels. Failed operations preserve staged history and completed
files as documented. Native read-only browser checks cover WO3 PC, supplied WO3
PS3 and Nights of Azure 2 Switch, without changing original sources/context.

Windows release testing caught incompatible `ctime` meanings in CPython 3.14:
[path stat/lstat preserves creation time](https://github.com/python/cpython/blob/v3.14.7/Modules/posixmodule.c),
while [handle fstat exposes native change time](https://github.com/python/cpython/blob/v3.14.7/Python/fileutils.c).
Save Library and review-export checks now retain full before/after freshness
within each API and bind the APIs using common file identity, size and modified
time. Active regressions simulate valid differing clocks, independent timestamp
changes, wrong handles and same-byte replacements without weakening copy guards.

The complete source suite and required Windows build/startup/Defender/download
gates must pass for publication. Edited/converted in-game load/re-save remains
unverified; unresolved Origins and DW7 XL requests retain their documented limits.

## v2.5.4 review-export filename fix

A privately supplied decrypted WO3 Ultimate US PS3 export opens under the
existing exact profile and has a byte-exact unchanged roundtrip. Before the
fix, actual Tk review exports using a plain name, a `.json` name or `APP.BIN`
all reproduce “Choose a .changes.json review file.” The exact review suffix
works. After the fix, all four choices export the complete expected typed JSON
review, and all five supplied save/context files retain their original hashes.
Private saves, context, native reports and account data are excluded from Git
and release assets.

GUI regressions also cover Unicode/case variants, partial suffixes, directories
whose names contain the suffix, cancellation, existing normalized destinations
and a frozen WO3U review exported after Undo. Existing source files, pending
edits and previously exported reports remain unchanged. This is report-export
validation; gameplay mappings and in-game loading claims do not change.

## v2.5.3 weapons, new profiles and shared refinements

DW7 XL PC weapon qualification independently inspects native parameter loaders,
save serializers and equipment/seal pickers. Three distinct native PC states
pass 54 independent equipment exports: 18 reference substitutions, 18 learned
seal substitutions and 18 removals. Each preserves the native seed and every
unrelated payload byte. Duplicate slots/seals, original smith reservations,
unknown records and suspended-battle cases are guarded. Base attack, element,
element level and capacity are external parameters, not mapped save members.
[Exact controls and proof](DW7XL_WEAPONS.md).

Original DW7 XL US/EU PS3 setters/getters/validators independently establish
Gold and 65 playable officers' six stored scalar bounds, active-weapon choice
and negative unlearned-meter operations. Official regional code comparisons,
499 surgical edits and 413 no-ops per native context, shared scalar self-tests,
and GUI/copy/backup/restore checks pass. Both original regions share one gameplay
state. [PS3 format and external signing limits](DW7XL_PS3.md).

Nights of Azure 2 Switch qualifies three complete native states from two source
archives, without claiming independent publishers. An independent walk checks
60 active unsigned-byte FNV-1a blocks; 35 numeric/preservation cases, 379 invalid
cases and three copied-native save/backup/restore workflows check Libra and its
coupled preview. Chapter checkpoints, unknown preview padding and inactive clear
tails remain unchanged. Only exact English Chapter 1/7/Clear profiles qualify;
no natural cap is inferred from a modified source. [Scope](NOA2_SWITCH_FORMAT.md).

WO3 Ultimate's native mount-menu lookup, state-copy bridge and serializers
qualify two stored selectors. Two original native sources pass 20 exact-byte
exports and two GUI/save/backup/restore workflows. Ownership, binary item ranks,
ordinary item equipment and inactive battle actors remain separate.

Cross-game regressions cover completed backup/context/manifest retention after
disk errors and concurrent replacements in 24 formats, plus DW3 prepared-report
retention. Shared GUI tests exercise large choice filtering, mixed selection,
named/formatted review search and complete frozen typed JSON export. The full
suite, native Windows builds/startups, active Defender scans and exact public
download verification remain required release gates. Eleven reviewed user guides
are bundled. Actual edited/converted game loading remains untested; Origins
proficiency-level and Old Coin writers remain unimplemented.

## v2.5.2 DW6 expansion, DW7 XL transfer and Origins inspection

DW7 XL's one-way original US/European PS3 to Definitive Edition PC route is
independently audited against a literal native map: 21,676 numeric members and
185 byte spans transfer 50,138 canonical bytes. All 420,165 remaining payload
bytes, destination revision and cipher seed stay unchanged. Six copied native
pairings use three distinct PC states and two original PS3 regional contexts
containing one shared gameplay state. Three test-created PS3 typed states derived
from those native PC templates yield exact original PC files, including the
checksum-uncovered final byte; these are not genuine matched platform pairs. Mutations
of both inputs' unknown progress extensions and suspension flags fail closed.
Native PC and official PS3 update serializers were inspected statically;
no game code was executed. [Scope and format proof](DW7XL_CONVERSION.md).

The combined candidate also checks all four DW6 scopes across eleven PC/PS3
references and 81 original Xbox contexts representing 40 gameplay states.
Nine Origins slots qualify guarded stored-XP/Battle Art inspection only;
proficiency-level and Old Coin writers remain unimplemented. Backup/export
regressions verify actual snapshots, companion metadata and final outputs.
Failed writes retain completed files to protect concurrent replacements;
never import a failed operation's output. Actual game loading/re-saving is
unverified for these edits and conversions. Full source/native Windows tests,
both packaged startups, active Defender scans and exact published-download
verification remain mandatory. Eight reviewed user guides are bundled.

## v2.5.1 actual offline-guide packaging

A check of the actual v2.5 public Windows ZIP found the seven advertised guide
files absent, despite all hash/content/scan checks matching the produced runtime.
The public v2.5 description was corrected without altering its immutable downloads.
The patch collects only the seven explicit reviewed guides into both native
builds, validates their exact source-manifest bytes and tests the resulting ZIP
contents. Missing, changed and unreviewed guide resources are separate rejection
cases. Fresh complete source/Windows checks, both startup forms, all exact-payload
Defender scans and actual public-download verification remain required.

## v2.5 editor workspace and Origins copy safety

Focused GUI checks exercise category counts, pending-row styling across both
themes, compact/expanded controls, minimum-window table space, search shortcuts,
filter clearing, session selection and retained pending edits. Forty-two focused
Origins/GUI cases pass with the separately acquired public revision-29 DLC slot
selected; public test inputs remain procedural. Existing library, conversion,
comparison and batch GUI regression checks pass separately.

Origins write regressions inject source changes during serialization and atomic
creation, destination corruption and existing-output collisions. Backups reject
stale sources. A successful copy is read from disk and qualified again; failure
cleanup removes only the exact bytes created by the current operation. Changed
destination bytes are retained. No proficiency, Old Coin or new-game writer is
qualified by these tests. Actual game-load/re-save acceptance remains untested.
The complete source suite, native Windows tests, both packaged startup checks,
active Defender scans and actual public-download verification remain mandatory.

## v2.4 DW6 equipment, migration review and batch conversion

Focused checks cover named DW6 equipment bits in both byte orders, complete
pending-mask capacities, existing same-officer equipment references, unknown
original preservation, surgical writes, native copy reopens, actual GUI workflows
and semantic PC/PS3 migration with untouched destination remainder. Private inputs
include one independent original PC and two US PS3 exports. Level/EXP/learned-tree
writes remain read only; no edited/converted game-load acceptance is claimed.
Migration review recomputes changed officer/horse counts and names from typed
snapshots and explains empty-slot replacement without widening transfer scope.

Batch checks exercise whole-queue read-only preflight, mixed families and the
conversion-only PS4 endpoint, relative private plans, path collisions, source/
context races, cancellation boundaries and partial failures. Completed reports
rederive output from frozen native snapshots and verify actual bytes, original
target metadata and exact stored receipts; forged reviews/receipts and modified
outputs fail. GUI checks cover retained sessions, worker progress, save-plan/report
retry, bounded review text and busy-close guards. Explicit UTF-8 report reads and
canonical Windows temporary paths are included in cross-platform regressions.

Four unregistered source-only inspectors were checked against fourteen private
native references, including eleven Vita files and three US/EU Gundam 2 copies.
They do not add editor profiles or qualify gameplay writes. All registered
interfaces and retained tools pass source smoke startup. The complete suite and
native Windows builds/startup/active Defender gates remain mandatory before
publication; final download hashes must match that native evidence.


## v2.3 native comparison workspace

Thirty-six focused comparison/GUI/converter/library tests passed without skips
when the independent Qoga native pair was selected. Checks cover conditional
fields, changed definitions, exact typed values, higher originals, outside-span
counts, forged summaries, stale original metadata, changed sources, atomic
report read-back, CLI argument isolation, workers, paging and retained sessions.
Gameplay files and companions remain unchanged. Public fixtures are procedural;
private native references are excluded. Full-suite and native Windows packaging/
Defender publication gates remain required. See [comparison instructions](SAVE_COMPARISON.md).

## v2.2 original PS3 title-family expansion

The three new original PS3 profiles have four independent complete public
exports qualified after private PFD extraction. Copied native files pass
unchanged roundtrips, manual wallet writes, untouched-byte preservation, exact
original PARAM.SFO binding, actual destination read-back and paired backup/restore.
Seventy-eight focused tests passed without skips when private exports were
selected. Actual Tk workflows exercise open, read-only inspection, Review, Undo,
manual/no-Max editing and safe copy output. Public fixtures are procedural;
private bytes and context are excluded. These checks do not establish internal
integrity or edited game-load/re-save acceptance. The full suite and native
Windows packaging/active Defender gates remain required for publication.

See [profile instructions and evidence](PS3_NEW_FAMILIES.md).

## v2.1.2 typed DW6 migration and DW8 XL PS4

The focused generated/native checks exercise all 20 directed routes, including
DW6's u64 skill mask, individual u32 fields, one-byte flags/opaque neighbors and
complete horse records. They compare semantic values, unchanged destination
spans, real native reopens and reverse results. Review, GUI, CLI and schema-2
receipts identify partial DW6 scope explicitly. PS4 tests reject nonzero extension
data, malformed/foreign metadata, backup races and unsupported revisions.

Privately copied independent original PC and both US PS3 DW6 exports passed all
four exported forward/reverse paths with complete original-byte equality on the
reverse and native semantic skill-mask equality. The upstream DW8 XL full-file
PS4 reference passed each of its three outbound transforms and exact reverses.
Original PS4 metadata was absent from that reference; context/export checks for
this new endpoint use procedural title-only metadata and do not prove a genuine
owner export. No source save, original account context, key, binary or static
report is committed or released. No converted save is claimed to load in-game.

US PS3 named unlocks preserve every byte except the selected playable byte;
relocking and resource Max unlocks are rejected. The PC correction similarly
preserves three opaque neighboring bytes. Actual original US exports and
procedural files pass all-field surgical checks and safe output reopens.

The full inventory and native Windows workflow remain release gates. Publication
requires stable source-manifest validation, both packaged startup workflows and
active Defender scans of runtimes, standalone EXE and both final archives, with
hashes bound to the release commit and downloads. The published Defender JSON
and checksum list provide the final execution evidence.

## v2.1.1 conversion and DW6 PS3

The new [Save Converter](SAVE_CONVERSION.md) registers 12 exact routes and
transfers complete shared gameplay spans through independently implemented
per-game codecs. Tests cover all directed and reverse paths, native integrity,
template encryption/context retention, nonzero-tail rejection, changed inputs,
forged plans, backup races, exclusive output folders, actual output read-back,
background GUI work and CLI dry run/failure behavior. Six P5S directions passed
private native PC/PS4/Switch exports and byte-exact reverse results. DW8 XL
PS3/Vita full-file source references passed both directions; the modified PC
reference is refused. DW8 PC routes have procedural preservation/codec evidence.

The [US DW6 PS3 adapter](DW6_PS3_FORMAT.md) was qualified on two independently
acquired native BLUS30110 exports. Both passed unchanged roundtrips, every
exposed field's surgical big-endian byte comparison, original metadata retention
and actual new-copy read-back. Public tests additionally exercise the shared
scalar contract, experimental encoding bounds, malformed/foreign profiles,
unknown records, original unstage, backup/metadata races and forged restore.
The registered editor retains pending edits across converter navigation.

Linux source checks use a real virtual display, the complete test inventory,
all-profile GUI smoke startup, generated inventory consistency and the reviewed
public source manifest. These checks do not produce or validate a Windows EXE.
The existing protected release workflow runs every module on four Windows
shards, verifies combined coverage, builds portable and standalone forms,
checks packaged startup and requires active Defender scans on the exact final
downloads. `DefenderScan-v2.1.1.json` and `SHA256SUMS.txt` are the authoritative
published binary evidence, bound to their actual commit and assets.

Edited DW6 PS3 loading and converted-save loading/re-saving in the actual games
remain unverified. No native save, metadata, key, source reference or private
report is part of the checkout or release assets. Console signing/import remains
external. Unsupported games, regions and conversion revisions are documented
with specific remaining inputs instead of inferred from editor availability.

## v2.1 experimental numeric editing — release qualification pending

The explicit session option expands declared numeric fields to their exact
encoding ceilings. Supported maxima remain visible and Max retains supported
targets. Choices, references, ownership, record discovery, checksum validation,
native dependencies and saved-value read-back remain enforced. DW3 uses its
existing tagged patch audit; scalar profiles use the bound adapter. Public
regressions cover strict defaults, opt-in isolation, native roundtrips, overflow,
protected values, Max restoration, warning cancellation and Undo history.

The final integrated source is being checked with the complete public suite.
Native Windows builds and real Defender scans must pass before publication;
their authoritative evidence will be `DefenderScan-v2.1.json`, tied to the
tested commit and exact downloaded asset hashes. Edited in-game loading and
re-saving of experimental values remains unverified.

## v2.02 dual Windows downloads — native qualification pending

Version 2.02 prepares two builds of the same 90-profile application: a portable
`--onedir --noupx` runtime and a standalone `--onefile --noupx` EXE. The direct
EXE embeds its runtime and required notices. The Windows ZIP contains only the
versioned application folder, with the launcher and `_internal`; developer
documentation remains in the Source ZIP.

The release gate requires active/current Microsoft Defender scans of both
complete candidates **before either binary is executed**. Both packaged smoke
tests then run, followed by static package/privacy checks and scans of the exact
final downloadable EXE, Windows ZIP and Source ZIP. Before/after inventories,
SHA-256 hashes, version and the tested commit must agree at publication.

The exact v2.02 native build, packaged startup tests and real Defender scans
have not yet been recorded here. Publication remains pending until that Windows
run passes; local policy tests, earlier releases and static comparisons do not
establish a clean scan for these new assets. The published
`DefenderScan-v2.02.json` and its exact Windows workflow run are the authoritative
records of eventual native qualification; they bind the results to the tested
commit and final asset hashes. This source section records the preparation
state before that run. No edited in-game load/re-save validation is added by
this distribution change.

## v2.01 Defender release qualification — 2026-10-13

The 2.0 assets were withdrawn after a Microsoft Defender Sabsik detection was
reported during download. Static comparison found no newly introduced native
runtime or bootloader payload: the code matches the official hash-verified
PyInstaller wheel and existing runtime libraries. This does not prove the
detection is false. See [the evidence and release gate](DEFENDER_RELEASE_GUARD.md).

The portable runtime replaces self-extracting one-file packaging. Focused
packaging, omission/privacy, workflow and scanner-policy tests passed locally;
the exact original Windows runtime's 92 prospective external files also passed
strict static preflight, including Tcl/Tk 9 embedded libraries. Scanner policy
tests are not antivirus results. The Windows workflow must pass the complete
test inventory and real active/current Defender scans of the runtime and both
downloadable archives before publication. Its downloadable report binds those
verdicts to exact asset hashes and the tested commit. No scan is claimed clean
when the engine, cloud connection or input is unavailable.

## v2.0 expansion and refinements — 2026-10-13

The release combines the 14 previously prepared profiles with existing-editor
improvements for Nioh 3, Sophie 2 PS4, Three Hopes, Project Zero PS2, Firis PC,
original Gundam PS3 and DW8 PS3. The library contains 90 profiles across 15
platforms. Independent reviews checked item identities, active inventory
capacities, source/companion races, field eligibility and integrity preservation.
Shared Max targets can restore only an exact typed opened numeric value after
a pending reduction; nonmaxable fields remain excluded.

Focused genuine-file and actual Tk workflows passed for the expanded inventory
controls, preserving original sources and unrelated bytes. The respective format
documents record corpus and test details. Private inputs remain outside the
checkout. Full local regression and native Windows release verification are
recorded separately below and in the repository workflow. The complete local
Python 3.12/Tk run passed 2,227 tests across all 252 modules: 461 optional
fixture/platform skips, no failures or errors. This run preceded the final
version-label change to 2.0; inventory, packaging and GUI startup were checked
again afterward. The release workflow runs the complete final source on Windows
before publishing. Edited in-game loading/re-saving is untested in this update.

## Sol development expansion — 2026-10-13

The source library now has 90 registered profiles across 15 platforms. The
[development report](SOL_EXPANSION.md) lists the 14 additions, shared fixes,
source qualification boundaries and final verification results. Native reference
inputs remain outside the checkout. New scalar profiles use the same bound
complete-pending-map and actual-destination read-back checks as existing profiles.


## v1.91 universal save contract — 2026-10-12

Registered scalar game/platform profiles all pass through `BoundScalarAdapter`.
The adapter validates the complete pending edit map, treats only an exact
same-type opened value as a no-op, requires byte-identical output for an
unchanged save, and decodes every edited serialization again to confirm native
validity and the requested field values. Save As reopens the actual destination
on disk, checks the backend-returned document against that read-back, validates
the saved payload and requested field values, then returns the freshly read
document. DW3 is the only bespoke editor; its existing immutable snapshot,
integrity, patch and read-back audit remains in place.

Direct `stage`, `limit_values` and `maximums` calls in the 16 older scalar
backends identified below now validate and normalize the complete pending map
too. The new-game parser template uses the shared validator, and the contributor
guide requires the bound adapter or equivalent save-path checks for future
profiles. The full Linux suite ran **2,050 tests: 599 skipped, zero assertion
failures, and one environment error**. The only error is the existing RotK3 Tk
GUI test, which cannot create a window because this runner has no `$DISPLAY`;
the other tests completed. Focused adapter-contract/pending-safety/WO4 checks
passed **42 tests** with two unavailable-fixture/display skips. Inventory and
release-package verification also passed. The native Windows suite and EXE
build remain pending in the v1.91 release workflow.

The [public source catalog](EDITOR_SOURCE_CATALOG.md) records more than twenty
additional online game/edition leads and why none yet meets native-writer
qualification. They are research-only; no unverified parser was registered.

## Existing-editor expansion — 2026-10-11

The [current expansion checklist](RICH_EDITOR_EXPANSION.md) extends 19 existing
profiles while retaining 44 registered game/platform profiles and version 1.6.
Six parallel implementation lanes reviewed all 43 profiles other than DW3
Remastered. Independent cross-lane reviews checked mapping evidence, original
eligibility, staged dependencies, integrity, unusual-value preservation and
new controls; no supplied game or external editor executable was run.

Focused results from this pass:

| Check | Result and evidence boundary |
| --- | --- |
| Samurai/early Dynasty | 175 tests passed, no skips; 761 new native fields exercised surgically, including own-pool equipment and occupied mount references. |
| Orochi/modern Dynasty | 269 distinct tests passed; one current DW9 Empires SYSTEM fixture unavailable. Genuine WO3/WO1/PC DW8E editing and Tk save/backup/restore passed. |
| Hyrule/Fire Emblem | 145 checks passed across the main run and separately enabled native Three Hopes check; includes both Three Houses revisions and native Legends. |
| Team Ninja | 24 focused native/GUI checks passed, including both Nioh 3 revisions and original NGII story regression. Enabled Wo Long naming has source/schema, procedural and Tk evidence; the genuine corpus has no enabled named set. |
| Persona/Gust | Nine new depth checks passed, including genuine P5/Ryza 2 and Tk; broader 66-check lane had 65 passes and one unavailable Sophie 2 native fixture. |
| Console/Pirate/strategy | 53 core checks plus three PC horse checks passed. Four genuine Gundam exports cover 20 eligible pilots/80 equipped slots; native PS3 DW8E covers four ordinary horses/28 fields. |
| Shared actions and DW8 weapon order | Root targeted native/GUI checks passed; independent 53-check review and all 82 qualified native DW8 pairs passed. Real minimum-window Light/Dark checks covered DW8, Three Houses, Gundam and DW8E. |
| Whole application startup | All 44 registered interfaces, themes and retained switching initialized successfully. |

These focused sets overlap and must not be summed as a distinct full-suite
count. The integration pull request records the combined Linux/Tk regression
result with available private native fixtures and the native Windows run.
The Windows workflow checks the public suite, standalone EXE startup, embedded
metadata/privacy and archive/hash consistency before its preview artifact is
accepted and the ordinary PR is merged. Release jobs are disabled for this
non-publishing branch; no release marker, tag or version bump is introduced.

Positive eligible native coverage remains missing for enabled Wo Long battle-set
renaming. PR #43 reports a second private native DW7 XL PC copy with one owned
unlearned positive seal meter and adds an optional surgical reduction, reparse
and increase-rejection test. The three native PC states available to maintainers
contain no eligible positive meter, so review does not independently reproduce
that positive case. A controlled learning pair and game load remain untested. Missing private
fixtures and platform-specific checks are reported as skips rather than passes.
No edited save was imported, loaded or re-saved in a game during this pass.
The linked lane checklists retain exact further mechanic/input blockers.


## Independent development-branch validation — 2026-10-11

This review started at remote `codex/prepare-next-update`, commit
`f7ca0121d4e98a7caf09f8545a5a7413a0b8dc3e`, on
`codex/independent-validation`. Parallel audits reviewed all 28 registered
adapters. Results below are from this review, not inherited qualification claims.
The complete suite for that 28-adapter snapshot ran **1,136 tests in 356.160 seconds: 824 passed,
312 skipped, no failures or errors**, using Python 3.12 and actual Tk on a virtual
Xorg display. Qualified copied-native inputs were explicitly configured for all
six new editors, Wii U Hyrule, Age of Calamity and Pirate Warriors 3.
Skips require unavailable private fixtures, except one Windows filename-rule
check; two fixture-dependent GUI skips also require Windows. There were no
display-only skips. A prior full run had 1,123 tests, two stale GUI expectation
failures and 328 skips; those expectations were corrected before the final run.

The [non-publishing Windows run](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/actions/runs/38094440495)
was dispatched with `publish=false` at application/test commit `a969687`.
It completed successfully: source checks, standalone EXE build and executable
verification passed; both release jobs were skipped. This is native Windows
evidence for the 28-adapter application/test snapshot, not the subsequent
29-adapter integration below.

### Confirmed defects and narrow fixes

- Registered scalar Stage, limits and Max could retain invalid prior edits or
  normalize them into valid values. The bound adapter now checks complete pending
  mappings, dynamic field identities and values before delegation. DW8/PW3 and
  Origins also enforce these checks in their direct backend APIs. Exact-type
  unusual opened values remain preservable and removable. Cached immutable
  validation and prevalidated Max targets avoid repeated native decryption.
- DW8/PW3 exposed fields from forged payload/raw/seed snapshots. Field lookup now
  qualifies the immutable snapshot before exposing writable fields.
- Legends rejected unchanged above-limit rupees/stars in pending edits. Original
  equality now precedes edit-bound validation without accepting booleans/floats.
- DW5 Special and DW8 Empires leaked `TypeError` for malformed field IDs. Those
  requests now raise `SaveError` without changing pending edits or source bytes.
- Wo Long's inspector crashed on an unmapped optional companion value such as
  `null`, an integer or a boolean. Only qualified companion arrays are inspected;
  other optional data survives unchanged.
- Inspector filtering reset the selected sort order. Filtering now reapplies
  that order; the regression also checks selection retention and visible-row copy.

The new adversarial regressions failed before these fixes. Two existing GUI
tests also had stale expectations: DW7 Undo restores the opened input, and
All-Stars then had three supported inspector groups. The later upstream update
adds Hero cards, and the four-group expectation was restored. Corrected tests
retain their original save/backup and byte-preservation assertions.

### Procedural and GUI checks

Independent generated inputs for the 21 older scalar adapters passed byte-exact
no-op roundtrips, one targeted edit per adapter, unstage, immutable originals,
Max exclusions and preservation of higher originals. All 420 ordered foreign
scalar-fixture combinations rejected. DW3 separately passed a surgical officer
skill-point edit and rejected 21 foreign fixtures, three damaged encrypted
inputs and two oversized-array counts. Sophie 2's documented optional zero
trailer permits changing its length; that was not classified as corruption.

Focused results (test totals include skips):

| Check | Tests | Passed | Skipped |
| --- | ---: | ---: | ---: |
| DW5 Special, DW8E, Legends, genuine copies and actual Tk | 55 | 55 | 0 |
| Bound pending-edit, scalar contract and shared pending regressions | 31 | 31 | 0 |
| Shared DW8/PW3 contract, snapshot, affinity and format regression | 79 | 74 | 5 |
| Origins pending, parser, snapshot, progression and weapons | 29 | 28 | 1 |
| Storage/source/restore adversarial regressions | 15 | 15 | 0 |
| Actual Tk library, named choices, tables and new-game workflows | 45 | 41 | 4 |
| DW7/All-Stars corrected GUI and format regressions | 22 | 21 | 1 |
| Package, dependencies, inventory and publication-gate regressions | 46 | 46 | 0 |

The shared focused skips were four missing copied-native inputs and one absent
display in that separate run. Origins lacked a genuine copy; All-Stars lacked
its genuine sample. The GUI batch lacked two Legends workflows, native P5S and
native Ayesha; subsequent actual-Tk copied-native checks covered those workflows.
The complete suite uses actual Tk on a virtual Xorg display with qualified native
copies for all six new editors, Wii U Hyrule, Age of Calamity and Pirate Warriors 3.

### Updated development branch integration

The development branch advanced to `bdb3833` while this review was finishing.
That update was integrated without replacing validation work: it adds the
29th registered adapter, Three Hopes, and All-Stars owned-card equipment.
The upstream stricter format-object identity check and this branch's pending-edit
guards both remain. The overlapping DW7 Undo assertion has equivalent semantics;
the All-Stars inspector expectation now includes the newly implemented Hero cards.

Affected shared-contract, pending-edit, GUI/session, registry, packaging and
inventory suites passed **102/102 tests, no skips, in 35.196 seconds** with actual
Tk. Three Hopes and All-Stars equipment suites ran **28 tests in 8.829 seconds:
21 passed, seven skipped for unavailable genuine copies**. Independent procedural
probes checked Three Hopes' 143 native-stored sections/nested checksums, mirrored
fields, surgical edits, unsupported targets and 25 corruptions; All-Stars probes
checked owned-pool equipment boundaries, campaign/hero boundaries, invalid
references, unstage and unchanged unrelated encrypted blocks. Those probes passed
and are synthetic evidence only. No independently verified genuine Three Hopes or
All-Stars file, or game loading, is claimed by this review.

The entire 1,136-test suite was not repeated after this integration. Its result
above applies to the original 28-adapter snapshot; these affected-area checks,
29-interface source and installed-wheel startup checks, and fresh manifest and
inventory checks apply to the integrated branch. The Windows run also predates
this integration.

### Genuine-file verification

All downloaded/exported saves, private hashes and provenance remain outside Git.
Public tests generate their own inputs; optional native checks use environment
variables and skip when copies are absent.

| Game/platform | Independently checked input and limits |
| --- | --- |
| DW5 Special PC | Public premodified 46,000-byte native save; all 728 qualified fields checked surgically, plus actual Tk save/backup/restore. |
| DW8 Empires PC | Public native SYSTEM copy; both qualified horse-body fields checked. Campaign, quick-save and custom-officer profiles rejected. Actual Tk and copied-save CLI self-test passed. |
| Hyrule Legends 3DS | Public 234,594-byte export; all 323 fields and combined resource/card/fairy/seal edits checked. Master Sword data preserved. Actual Tk and CLI self-test passed. |
| Persona 5 Strikers PC | Three distinct public 5,627,552-byte saves; native checksum rejection, no-op and surgical edits across qualified occupied slots, plus actual Tk. |
| Wo Long PC | One public trainer-modified revision-1.302 gameplay save; native checksums, no-op, resource/stack edits and actual Tk passed. Byte-identical mirrors count as one fixture. Same-size SYSTEM data rejected. |
| Atelier Ayesha PS3 | Three public US/Japanese exports decrypted independently outside Git; published Cole values, no-op, Cole/stack edits and actual Tk passed. An encrypted unsupported digital-region export rejected. External PFD authentication and PS3 reimport were not checked. |
| Hyrule Wii U / Age of Calamity Switch | Two cached public Wii U exports and one AoC export; every qualified field checked surgically (495, 689 and 367 fields), Max exclusions/high values and unchanged source hashes passed. |

No edited save was loaded or re-saved by a game. Premodified and trainer-modified
files provide genuine-file evidence, not pristine gameplay or game-load evidence.

### Installed package, packaging and remaining limits

A non-editable wheel installed in an isolated environment outside the checkout
loaded all 29 editor/parser/backend registrations and all 14 runtime JSON files.
Its 195 entries contained no tests, tools, saves or binaries; runtime JSON bytes
matched the wheel exactly. Module listing and actual-Tk all-interface/theme
smoke startup passed. The source manifest verifies 411 public entries, and the
generated-inventory check passed.
The version remains 1.6. Linux checks do not validate Windows CNG or an EXE;
native build status belongs to the explicitly non-publishing workflow run.

Historical limitation in this v1.6 / 29-adapter snapshot: 16 older backends
could retain unknown prior keys during direct `stage`; PW4 and Sophie 2 could
also normalize malformed pending values in direct `maximums` calls. For
example, direct PW4 Max with pending `{'beli': -1}` became a maximum, and
`{'beli': '1'}` raised `TypeError`. The v1.91 source changes above close these
direct-call gaps and add read-back value confirmation to the shared registered
scalar save path. The affected direct modules were DW7 XL, PW4, DW4 Hyper/PS2 XL,
Sophie 2, WO3U, SW4 DX, DW9E, Orochi Z, Wii U Hyrule, AoC, Hyrule Definitive,
FE Warriors, DW7E PS3, DW7 PS3 and SW4 PS3.

Coordination: the validation changes affect shared contracts/GUI, Origins and
narrow DW5/DW8E/Legends/Wo Long edge cases. No registrations or game mechanics
were authored by this review; the new registration/equipment come from upstream.
Concurrent implementation branches should preserve these regressions and refresh
the reviewed source manifest after integrating overlapping edits.

## Licensed Musou expansion (2026-10-11)

Linux Python 3.12 with a real Tk/Xvfb display completed **1,189 tests: 854
passed, 335 skipped, zero failures/errors**. Skips concern absent unrelated
private fixtures and platform-specific checks. The focused licensed Musou suite
completed **41 tests, all passed, zero skips**, with all eight genuine PS3 copies
explicitly selected. Three registered scalar contracts, malformed/foreign input,
dependency/unknown-value preservation, native checksums where established,
source safety, backup/restore and retained GUI sessions are covered.

Gundam 1 passes four genuine unchanged roundtrips and 269 independent surgical
skill-bit additions across 20 qualified pilot records. Ken's Rage 1 passes two
genuine unchanged roundtrips and 16 surgical skill-point edits. Their genuine
Tk editing/review/Undo/save/backup/restore workflows also pass. Ken's Rage 2
passes two genuine unchanged roundtrips and genuine GUI preservation workflows;
its unlock edits remain procedural because both genuine samples already have
all mapped galleries unlocked. No actual edited game-load/re-save was performed.

All 32 registered interfaces pass the startup smoke test. Three native
copied-save CLI workflows pass unchanged input/backup/restore checks and report
zero Max edits, as all new controls disable bulk Max. Gundam and Ken's Rage 2
report established native integrity; Ken's Rage 1 explicitly reports external
integrity and unverified native checksums. Inventory consistency, all six new
qualified Windows build imports and **424 reviewed public source files** pass
packaging/privacy verification. No Windows EXE/CNG run, version bump, tag or
release was performed. See [exact scope and blockers](LICENSED_MUSOU.md).

## Hunting/monster Windows investigation, 2026-10-11

The branch based on preparation commit `bdb3833` adds qualification notes for
[Toukiden Kiwami](TOUKIDEN_KIWAMI_RESEARCH.md),
[Toukiden 2](TOUKIDEN2_RESEARCH.md) and
[Monster Rancher 1 & 2 DX](MONSTER_RANCHER_DX_RESEARCH.md). **No editor or writable
mapping qualified for these four titles.** The existing 29-game registry,
runtime metadata, supported inventory and version 1.6 remain unchanged.

Python 3.12/Linux with Tk under Xvfb completed these existing-game checks:

| Check | Exact result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 1,148 tests in 423.657 seconds: 813 passed, 335 skipped, no failures or errors. |
| Focused GUI/integration/library/choice/packaging/dependency suite | 71 tests in 29.838 seconds: all passed, no skips, failures or errors. Modules: `test_universal_app`, `test_new_game_integration`, `test_library_search`, `test_named_field_choices`, `test_universal_packaging`, `test_package_dependency_review`. |
| `python -m koei_editor --smoke-test` | All 29 registered interfaces, themes and switching initialized successfully. |
| `python -m tools.update_supported_games --check` | 29 supported game/platform adapters; consistency passed. |
| `python -m tools.package_release --verify-only` | All 411 reviewed public source files verified; no private saves, source copies, identifiers or game assets added. |
| Documentation links / whitespace | 124 local links resolved in the eight investigation/coverage documents; `git diff --check` passed. |

The full suite's skips cover unavailable optional fixtures and platform-specific
requirements. No target-game fixture was treated as an existing adapter input.
An initial run was interrupted after a virtual-display connection problem; the
completed run above used the corrected display. No native Windows executable
build or edited game-load/re-save was performed.

Kiwami acquisition yielded five candidate files from two public archives;
Toukiden 2 yielded thirteen files from one public archive. These remained
private analytical inputs, without native codec/integrity or revision proof.
Monster Rancher DX yielded no complete native Windows fixture. For **each** of
the four target games: procedural adapter tests **0**, qualified genuine-file
unchanged roundtrips **0**, surgical edit/checksum/dependency tests **0**,
backup/Undo/Review/GUI editor workflows **0**, actual edited game-load/re-save
validation **0**. Existing-game regressions do not qualify these candidates.
The linked notes and [input checklist](REMAINING_INPUTS.md) record the precise
serializer, native-file and controlled-action evidence still needed.

## Berserk and Attack on Titan Windows follow-up

The 2026-10-11 follow-up is **read-only envelope research**, with no new gameplay
adapter. The three privately reacquired native contributor files qualify only
the observed outer cipher/u16 sum and unchanged reconstruction. Revision gates,
semantic records, additional integrity and edited game-load/re-save remain
unqualified. [Evidence and reproducible inputs](OTHER_KOEI_PC_RESEARCH.md).

With `BERSERK_SAVE_COPY`, `AOT1_SAVE_COPY` and `AOT2_PK_SAVE_COPY` supplied,
`python -m unittest tests.test_berserk_aot_envelopes -v` completed **15 tests in
11.236 seconds: 15 passed, zero failures/errors/skips**. Twelve cases cover
independent procedural arithmetic, additive collisions, malformed/wrong-family
inputs, immutable snapshots, buffer-subclass size bypass, forged qualification
flags, privacy and absence of gameplay/file-writing APIs. Three cases check
genuine unchanged ciphertext roundtrips and first/last-body corruption rejection.
No native bytes or owner context appear in the public fixtures.

Independent arithmetic additionally checked all three genuine files: **3/3
outer sums and byte-exact roundtrips**, **21/21 single-byte corruptions**,
**12/12 incorrect lengths**, **6/6 wrong-profile selections** and **6/6 alternate
cipher-family checks** behaved as expected. Wrong-profile rejection here follows
the distinct observed sizes; it does not prove a universal title identifier.

The headless Linux baseline ran **1,148 tests in 216.708 seconds: 734 passed,
409 skipped, five errors**. All five errors are pre-existing Tk setup failures
from the unavailable display: two `test_gui_v11.AppearanceGuiTests` cases and
three `test_weapon_bonus_labels.WeaponBonusLabelTests` cases. Other display,
private-fixture and platform-dependent tests skip. The source GUI smoke test
also stops at Tk creation with `no display name and no $DISPLAY environment
variable`; it did not validate GUI startup. The supported-inventory check passes
for the unchanged **29 adapters**.

The final full Linux run supplied all three new genuine-copy inputs and
completed **1,163 tests in 223.269 seconds: 749 passed, 409 skipped, five errors**.
The same five unavailable-display errors remain; no new regression failed.
The focused packaging/inventory suite completed **23 tests in 0.530 seconds,
all passed**. Manifest/privacy verification passed for **414 reviewed public
source files** (plus the manifest itself); the Windows build configuration was
inspected without producing or executing a Windows EXE.

The publication-disabled [Windows workflow](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/actions/runs/38096642271)
then tested implementation commit `bea25520e408b2676a551e9424b42014fb1e41f7`
on Windows/Python 3.14: **1,163 tests in 404.467 seconds, 822 passed, 341 skipped,
zero failures/errors**. The twelve new procedural cases ran; the three optional
genuine-copy cases skipped because private saves were not uploaded to CI.
The locally completed genuine-file tests above remain separate evidence.

All **29 source interfaces**, themes and switching passed GUI startup. The
standalone Windows EXE built and passed frozen GUI startup, embedded metadata/
module privacy verification and local archive packaging. The workflow uploaded
validation artifacts only; `publish=false`, and both `prepare_release` and
`release` jobs were **skipped**. No merge, version bump, tag or GitHub release
occurred. The follow-up commit records these results and refreshes only the
documentation manifest hashes; runtime code/data remain the tested bytes.

No title-specific surgical edit, dependency/backup/Undo/Review Changes/save GUI
workflow is claimed because no writable Berserk/AoT adapter exists. Linux tests
do not validate Windows CNG, a Windows EXE or actual edited game loading. No
game/editor/trainer binaries were executed, no saves/identifiers/assets were
published, and version 1.6 remains unchanged.

## Earlier development runs

Run the complete public suite and all-interface startup check from the repository root:

```text
python -m pip install -e .
python -m unittest discover -s tests -v
python -m koei_editor --smoke-test
python -m tools.package_release --verify-only
python -m tools.build_windows --print-config
```

On Windows, Python/Tkinter and native CNG are sufficient for source tests. On
non-Windows, install the optional AES development provider with
`python -m pip install -r tools/requirements/dev.txt` and provide a graphical display
for Tk tests (for example, a locally installed Xvfb). Windows remains the target
for the standalone EXE and native CNG validation.

## Regional and Special edition qualification — 2026-10-11

Branch `codex/special-regional-editions` is based on the current preparation
commit `bdb3833a1ad4169c12d3f889d5e971dc481c9cc2`. This work implements an
**unregistered, read-only PSP envelope inspector**, clarifies DW5 Special's
regional evidence, and records product/format research. It adds **no gameplay
editor, writable field, regional conversion or supported-game entry**. All 29
existing adapters remain registered and the application version remains 1.6.

Validation used Linux Python 3.12.14, Tk 9.0, a preexisting Xvfb testing runtime
and the optional development crypto provider. No downloaded game/editor binary
was executed. The three privately acquired PSP references were explicitly
configured; unrelated private gameplay fixtures were not supplied.

| Check | Exact result and limit |
| --- | --- |
| Complete corrected public suite | **1,165 tests in 370.497 seconds: 830 passed, 335 skipped, zero failures/errors.** Skips require unavailable private fixtures or platform checks. Includes existing corruption, integrity, dependencies, unusual-value preservation, safe storage, backups/restore and procedural GUI regressions. |
| Focused regional/PSP/DW5/inventory suite | **39 tests in 1.165 seconds: 37 passed, 2 skipped, zero failures/errors.** Both skips require the missing private DW5 genuine copy. The procedural DW5 Tk workflow covers Apply, Review, Undo, manual-only Max, copied saving and backups. |
| PSP inspector alone, with references | **15 passed, zero skips/failures:** 12 procedural boundary/privacy cases and three public-submission envelope cases. No secure hash authentication, decryption, gameplay layout, codec roundtrip or surgical edit is tested. |
| PSP inspector without references | **12 procedural passes, 3 optional-reference skips.** A same-length altered encrypted payload deliberately remains structurally matchable with both verification flags false. Native file-list MAC/padding regressions protect the independently corrected boundary. |
| Existing DW5 suites | **18 tests: 16 passed, 2 missing-genuine-fixture skips.** Historical 728-field genuine qualification belongs to the prepared base; no fresh regional genuine roundtrip/edit is claimed. |
| Interface and inventory | All **29** registered interfaces initialize with themes and switching; generated inventory check passes unchanged. PSP candidates and regional aliases cannot select a writer. |
| Build/source/privacy | Windows build configuration prints successfully; all **416** reviewed public source entries verify, version 1.6. No private saves, identifiers, game assets, downloaded source copies or binaries are packaged. Whitespace and modified-document local links pass. No Windows executable was built. |

An independent source/fixture review found a secure-file declaration offset
error in the first inspector and procedural generator. The corrected native
13-byte filename / 16-byte hash / 3-byte padding rule has two adversarial
regressions. An earlier full run was interrupted to apply the correction and is
not counted above; the complete run uses the corrected implementation.

Additional private data inspections establish PSP metadata for DW6/DW7/SW3 Z
Special, two exact-length decoded PS2 CodeBreaker outer streams and matching
additive stored values in three US PS2 DW6 payloads. These are narrower factual
observations, not authenticated native gameplay or registered-adapter tests.
The X-Port outer checksum remains unchecked. No genuine Orochi Special gameplay
export or fresh DW5 regional control was acquired.

**Zero new-edition gameplay roundtrips, surgical edits or actual edited
game-load/re-save validations were performed.** PSP authentication/decryption
and console re-encryption/import remain external and unqualified; payload
identity/revision, integrity, semantic fields and controlled mechanic pairs
remain blockers. DW6 PS2 additionally lacks complete native integrity/field
proof; DW5 Japanese/Simplified-Chinese compatibility and regional text remain
unproved. See [DW6](DW6_SPECIAL_REGIONAL_RESEARCH.md),
[DW7](DW7_SPECIAL_PSP_RESEARCH.md), [PSP responsibilities](PSP_SPECIAL_RESEARCH.md),
[DW5 regional qualification](DW5_SPECIAL.md),
[additional regional scope](REGIONAL_EDITION_SCOPE.md) and
[exact supplier inputs](REMAINING_INPUTS.md#regional-and-psp-special-inputs).

## Earlier development checks

A prior cloud run completed **486 tests: 236 passed, 250 skipped, no failures
or errors**. Skips are predominantly private-fixture integration tests, plus
Windows-only checks. Existing regressions were retained. New tests cover game
switching, hidden pending changes, active-game shortcut routing, theme retention,
DW3 synthetic edit/Undo/Review/Save As, Origins artifact identity, original-byte
preservation, backup hash/game validation, existing-file and destination-race
rejection, live-save aliases, copy comparisons, packaging metadata/privacy and
single-entry build configuration. AES ECB/CBC use published NIST vectors.

The run explicitly supplied both genuine public PC samples using
`DW8XL_SAVE_COPY` and `PW3_SAVE_COPY`. Without those paths, two additional sample
tests skip. New PC regressions cover published cipher vectors, native checksum
rejection, cross-game identity and revision checks, 485 core scalar fields and
supported existing DW8 weapon-attribute ranks,
unchanged ciphertext round trips, unrelated plaintext preservation, bounds,
backup/hash/game checks, read-only PW3 currency, concurrent source changes,
immutable destinations, full copied-save workflows and the verified PC support
gate. Tk workflows cover individual/bulk edits, Undo, Review, Save As, restore,
retained hidden edits, minimum-window accessibility and DW3 CLI argument order.

Mechanics regressions additionally cover read-only PW3 level/XP inspection,
the explicitly inferred health curve, rejection of unobserved zero bar/slot
capacities, preservation of higher existing values during bulk-limit actions,
read-only inspection callbacks and research notes that cannot activate parsers.
The second genuine low-progression PW3 PC save was validated separately through
the same copied-save workflow; both PC samples corroborate the observed model.

Independent review also decoded DW8 original and max-edited outputs with the
published converter and independently reconstructed the PW3 word cipher/checksum.
PW3 Beli editing was withheld because the published money patch changes two
fields whose relationship needs controlled PC samples. Character stat edits
remain enabled; both currency fields are preserved.

The real public Origins reference was separately inspected and copied through
backup, restore and Save Copy As. Every output matched its original bytes; an
unchanged comparison reported zero differences. This verifies copy operations,
not gameplay parsing or game loading. Those earlier checks covered opaque copies only. Native Origins editing is now
qualified separately as described below.

The universal source GUI and existing DW3 GUI initialize under Xvfb. The rebuilt
local Linux one-file PyInstaller validation bundle initializes all six registered
interfaces, including the DW4 candidate, and passes archive checks: 390 entries,
14 matching metadata files and 266 Python modules. It was built with the system Python 3.13/Tk 8.6 after the hosted runtime
bundle failed strict privacy checks. The retained validation bundle omits the
optional non-Windows DW3 crypto provider. Bundled copied-save self-tests
validated the genuine DW8 and PW3 PC samples, checking 3,968 and 235 fields
respectively, original preservation, backups and restoration. The DW4 candidate
bundled workflow checked 331 fields on an explicitly procedural fixture, retaining
false sample-qualification and in-game-validation flags. Those workflows record that in-game loading is untested.
This is a development validation bundle, not a Windows executable. A native Windows build, its archive verification and packaged
source/fixture workflows must be checked on Windows before distribution. Private
DW3 integration checks still need the original explicitly supplied fixtures.

The latest pass includes 23 passing DW4 candidate format tests and one skipped
genuine-PC sample test, 19 DW8 Empires candidate arithmetic tests and 17 Persona 5
Strikers stream/structure tests. A published 32-byte PC screenshot is the P5S
known answer; constructed files do not establish full native integrity. GUI tests
exercise the injected DW4 backend, Undo/review/copy writes, retained session and
fully visible status/hints at the minimum window size. The user-authorized platform split makes source-backed DW4 Hyper and PS2 XL
selectable while their independent sample flags remain false. The current 123-entry source manifest
verifies; candidate implementations and the renewed research report are included
in reviewed public source inputs, while no sample save is included.

No code, branches, tags, releases or workflow runs were published.

# Contributor validation

Use separate save copies for development and testing. Private player saves and game files are not included in public downloads.

Run the automated suite on Windows:

```powershell
python -m unittest discover -s tests -v
```

Integration cases that require private fixtures skip when those fixtures are unavailable. Check the test output for failures and skips; do not describe skipped cases as passed.

To exercise the GUI against your own explicit save copy, choose a new or empty output directory:

```powershell
python gui.py --self-test "D:\SaveCopies\GameStatusData.sav" "D:\SaveCopies\EditorTest"
```

The workflow creates working copies and a `self-test-report.json`. Confirm the process exits successfully and the report records success and input preservation. The Windows executable supports the same arguments.

For changes to parsing or editing, check:

- Unchanged saves round-trip byte-for-byte.
- A targeted edit preserves unrelated records and properties.
- Resized strings/arrays regenerate enclosing sizes, envelope length and padding.
- Malformed input and invalid new values fail before writing.
- Backups, restore, pending-change rollback and Undo preserve the original copy.
- Explicit Huanglong Elixir balances remain the final count when combined with Musou clears; repeated clears do not award Elixirs twice.

Review each output's `.changes.json` for the actual byte patches and encrypted blocks. Keep detailed validation reports private; summarize reproducible failures when contributing a fix.

See [BUILDING.md](BUILDING.md) for executable build instructions and
[SAVE_FORMAT.md](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/blob/main/docs/SAVE_FORMAT.md)
for the supported structures and editing rules. Technical reference files are
also included in the source download.

The final platform pass adds 23 passing PS2 XL procedural tests and one skipped
genuine export test. GUI integration exercises PSU opening, edits, Undo/review,
Save As with the correct extension, copied-save self-test and cross-platform
rejection. Platform filtering preserves PC sessions and defaults to Windows PC.
The library contains four PC editors and one PS2 editor; the two DW4 entries use
published-format provenance and retain false independent-sample flags.

## v1.2 preparation

The final v1.2 source suite passed 486 tests: 236 passed and 250 skipped, with
no failures or errors. Removed consumer research/mechanics controls and format
badges while preserving editing, safety and read-only inspection. Twenty-two
GUI tests exercise both platforms, themes, minimum-window layouts and complete
copy editing workflows. Source and Linux one-file startup checks pass. The v1.2 Linux archive contains
390 entries, 14 matching JSON files and 263 Python modules; privacy checks pass.
The contributor save-edit example was executed on a procedural DW8 fixture;
local documentation links were checked. Native Windows build and game loading
remain separate checks. New contributor and AI-agent guides are included in
the public source whitelist. The matching-version tag workflow gates publication
on native Windows tests, executable startup, archive privacy and artifact hashes.

## v1.3 existing-editor integration

The final source run passed **544 tests: 289 passed, 255 skipped, no failures
or errors**, with DW8/PW3 copies, the published native Nioh 2 user copy and all
five upstream Katana encrypted/decrypted pairs explicitly selected. Missing
private DW3, genuine DW4/Sophie2 and other copied-native cases remain skipped.

Sophie 2's focused suite passed 19 tests, with its one real-copy case skipped.
Frozen upstream vectors and a separately loaded upstream model establish codec
and field agreement on procedural data, not independent game-save qualification.
Peer review reproduced and fixed opaque encrypted-footer loss, scalar range
crossing into equipment, extra palette data and live-backup-directory aliases.
The copied-save self-test checks 14 procedural fields, changes 10 supported
quality values, preserves higher qualities and both EXP fields, verifies all
integrity/payload expectations, and restores original bytes. Its sample/in-game
flags remain false. Twenty-four GUI tests cover retained sessions, dynamic
field groups, quality/EXP edits, Undo, review, inspection, Save As, restore and
scroll/focus accessibility in both themes at the minimum window size.

Katana source-only tests passed 17 with four copied-native cases skipped. Full
Nioh1/2/3 and SOP cipher pairs match in both directions with original header key
material retained; all gameplay edits are rejected where integrity is unmapped.
Wo Long's dummy demonstrates CBC only and is rejected for malformed JSON and
stale native checksums. Independent literal-C checksum/custom-cipher vectors and
procedural corruption/identity tests pass. Nioh 2's 14 inspection tests pass,
including its genuine 2,715,432-byte PC user fixture, with active runtime
integrity flags unchanged. These sources add no selectable gameplay editor.

Source and Linux bundled startup checks pass. The validation archive has 393
entries, 14 exact JSON files, 266 Python modules and three exact embedded
notices; privacy checks pass. The bundled procedural Sophie2 copied-save
workflow also passes all 14 fields and original/backup restoration checks.
The standalone build embeds the
Sophie 2 MIT notice and checks its exact bytes as well as public JSON metadata;
saves/account data and third-party binaries remain excluded. Native Windows
release validation runs through the matching-tag workflow. No in-game reload
was performed in this cloud environment. See EXISTING_EDITORS.md for exact source
licences, platform distinctions and download failures.

## v1.4 Origins and adapter contracts

Origins native envelope checks and serializer lengths were independently traced
in the installed Steam executable. All nine copied slots, spanning revisions
16, 17 and 29, decrypt with matching checksums and re-encrypt unchanged byte for
byte. Resources, existing bonds, provincial peace, catalogue-qualified weapon
reinforcement and persistent battle clear history have native serializer and
limit evidence in ORIGINS_FORMAT.md. The DLC point field is absent from older
profiles. Independent tests cover exact revision offsets, empty/reserved/special
weapon exclusion, monotonic manual history and training/history exclusion from
Max; history edits preserve active story and reward state.

Procedural and copied-file tests cover unchanged round trips, field-only plaintext
and ciphertext changes, legitimate maxima, preserved higher existing balances,
malformed checksums and layouts, forged documents, wrong-game selection, backup
restore and source/destination safety. Shared adapter contract and Tk workflow
regressions cover the existing editors and the new Origins interface. Native
Origins edited saves have not been loaded into the game during this task.

Theme regression tests restart both the universal application and standalone DW3
with isolated preference files, including actual appearance selector callbacks,
corrupt settings, failed atomic writes and no-write smoke mode. DW3 weapon label
tests verify stat names in selectors and review while item tabs, numeric IDs and
the opened save remain unchanged.

## v1.5 PC expansion

Linux Python 3.12/Tk 9 with a real Xvfb display ran the full public regression
suite: **777 discovered, 497 passed, 280 skipped, zero failures**. The skipped
cases require private DW3/native fixtures or platform-specific inputs; generated
fixtures remain procedural evidence. An inspector-search test initially expected
one match despite its token appearing in several columns; its assertion was
corrected and the full run repeated successfully.

A separate **113-test run passed with zero skips**, using privately held genuine
public DW7 XL, WO3 Ultimate, SW4 DX, PW4 and DW8 XL saves, five DW8 Empires files,
and two Nioh 3 native revisions plus an encrypted partner. It includes unchanged
roundtrips, surgical resource/stat/equipment/coin edits, native integrity,
malformed inputs, dependencies, high/unknown-value preservation, shared adapter
contracts and actual Tk workflows. DW8 Empires and Nioh 3 qualify source-only
codecs; their checks do not establish gameplay editing.

The final DW8/PW3 snapshot/restore hardening then passed **50 focused tests with
zero skips**, including five new adversarial cases, both genuine PC samples,
compatibility/affinity edits and GUI backup/Undo/Review/Save As. Sophie 2's new
refill/inventory and independent boundary/layout/filter tests pass using generated
and published differential data; its independent genuine save is still missing.
Additional source-only Orochi Z, All-Stars and Abyss tests use procedural data.

A further shared Max guard preserves PW3 bar/skill-slot values below their
qualified minimum. Its new regression, snapshot/restore checks and existing Max
regressions passed nine focused tests after that final change.

The universal startup smoke test passes with all eleven registered editors,
platform selection, retained sessions and both themes. The reviewed source
manifest verifies 210 public entries. The source and Windows archives exclude
player saves, attached binaries, private static-analysis outputs and owner data.
The Windows ZIP includes the coverage checklists; source-only modules remain
outside the writable game library.

Native Windows publication is gated by the existing Windows workflow: full
public tests, source GUI startup, Windows PyInstaller build, standalone EXE
startup, bundled metadata/privacy validation, archive generation and SHA-256
verification. Workflow logs provide the platform-specific test/skip counts.
Linux checks are not a substitute for those Windows checks.

**No edited file was loaded and re-saved by an actual game in this expansion.**
File-level qualification, procedural GUI checks and packaged application startup
are separate evidence. See [EXPANSION_COVERAGE.md](EXPANSION_COVERAGE.md) and its
per-game checklists for exact revisions, editable mechanics, legitimate bounds,
dependencies and remaining input blockers. In particular, SW4 manual base-stat
storage bounds and WO3 resource edit bounds are excluded from Max.

## v1.6 organized-package pre-release checks

The final cloud run completed **958 tests in 180.893 seconds: 689 passed,
269 skipped, no failures or errors**, using Python 3.12, Tk under Xvfb and
22 privately configured fixture/reference inputs. Skips include unavailable
private DW3 fixtures, unsupported platform checks and the missing genuine
DW9 Empires SYSTEMDATA sample. Procedural DW9 Empires tests verify the
source-backed current profile; they are not genuine-file or game-load tests.

All 22 registered game/platform editors passed application startup, theme and
game-switching checks. Independent isolated wheel installation verified all
22 editor/parser/backend imports, 14 runtime JSON resources, both module and
console launch commands and three published AES provider checks. The wheel
contained 162 entries and no tests, fixtures or attached binaries.

Independent native reviews checked 433 Orochi Z fields surgically, including
all 96 per-officer base-attack bounds, and separate available-gold/material
fields in All-Stars without changing lifetime earnings. Orochi Z passed 23
focused format/contract/GUI/review tests. Reacquired genuine SW4 DX checks
passed 21 focused tests. Fire Emblem Warriors passed 19 focused and independent
checks; its genuine public export was already modified. Special weapon and
progression restrictions remain preserved. No edited save was loaded or
re-saved in an actual game during this expansion.

The reviewed source manifest contains 331 public files and requires 116 runtime
dependency files. Independent source-ZIP extraction verified every source byte
and hash, installed the extracted package without repository import paths,
loaded all 22 editors and 14 JSON resources, initialized both GUI launch
commands, and passed 45 packaging/workflow/provider regressions. Windows ZIP
documentation comes only from explicitly reviewed manifest entries; private
files and source Python modules cannot be discovered into that ZIP.

The native [Windows workflow](../.github/workflows/windows-release.yml) must
pass the full public suite, source GUI startup, PyInstaller build, frozen EXE
startup, executable privacy/metadata verification and release-archive hashes
before publishing. Linux checks do not substitute for those Windows checks.
Release preparation respects protected merges and checks the exact tested
commit before dispatching publication.

The first native Windows run executed 958 public tests and found one test-only
path comparison: a temporary `RUNNER~1` folder resolved to its long Windows
name. The test now compares canonical destination paths while retaining exact
source, output and backup-byte checks. The unchanged runtime and corrected test
passed 24 focused genuine-file/GUI/integrity checks locally; native verification
must pass again before publication.

## Console expansion on prepare-next-update

The console-only pass adds qualified US PS3 WO3 Ultimate resource controls and
US PS3 DW8 Empires SYSTEM custom-horse Body Type controls. Japanese PS3 SW2 HD,
US PS3 Strikeforce and each legacy Xbox360 title retain separate research-only
status and exact blockers; diagnostic fixtures do not qualify writable profiles.

**96 focused tests passed with no skips**, using Python 3.12, Tk under Xvfb,
the genuine DW8E SYSTEM export, both genuine WO3 Ultimate exports, both genuine
Strikeforce exports and the extracted genuine Xbox360 base SW2 payload. These
checks distinguish procedural corruption/dependency tests from genuine no-op
roundtrips and surgical edits. Actual Tk workflows exercise Undo, Review,
themes, backup, Save Copy As and restore. SW2 HD probes use procedural fixtures
because its exact genuine Japanese native profile is still missing.

Registered copied-save self-tests separately passed on genuine DW8E SYSTEM and
both WO3 Ultimate exports, preserving source bytes, unchanged copies and
restored backups. The narrow manual controls are deliberately excluded from
Max. DW8E verifies its native checksum; WO3 records external integrity and does
not authenticate arbitrary unknown-byte corruption or establish a global
checksum-free format. Mandatory original PARAM.SFO context is copied opaquely
only to private self-test outputs.

Full discovery on the initial base `f7ca012` completed **1,158 tests in
363.616 seconds: 828 passed, 327 skipped and three failed**. Two failures
(DW7 XL GUI staging and the All-Stars Hero Card inspector expectation) also
reproduced on an untouched copy of that base. The third was the support-catalog
test's platform whitelist, extended here for research-only Xbox360 entries with
an explicit no-writable-Xbox assertion. During validation the shared preparation
branch advanced to `bdb3833`, resolving both existing GUI failures. This console
branch was rebased onto that update with both instances' metadata preserved;
**103 focused tests then passed with no skips**, including all three previously
failing cases. A second complete discovery run after that rebase was not made.

All **31 registered interfaces** passed application startup, theme and game
switching checks. Generated support inventory and the **430-file reviewed
public source manifest** verify. Windows build configuration includes both new
adapters, but a native Windows EXE was not built or tested in this pass.

**No edited console export was loaded and re-saved in an actual game.** PS3
PFD reimport/resigning and Xbox360 STFS reimport/hash/signing remain external.
No player saves, game/editor binaries, account identifiers or private analysis
are included in Git or the reviewed public package.

## Additional Musou PC branch

The `codex/additional-musou-pc` work started at preparation commit `f7ca012`
and integrated the subsequent `bdb3833` preparation changes without replacing
other game lanes. On Linux/Python 3.12 with Tk/Xvfb and the optional development
crypto provider, **34 focused tests passed with no skips**: SW4-II format,
scalar contract, independent adversarial review and real Tk workflow; Sanada
read-only framing; generated inventory and explicit support gates.

The full integrated suite completed **1,174 tests: 839 passed, 335 skipped, no
failures or errors**. Skips require other private fixtures or platform-specific
checks; both genuine SW4-II copies and all three Sanada files were supplied.
The generated inventory checks 30 registered adapters. Source packaging verifies
423 explicitly reviewed public files at unchanged version **1.6**; no player
files, downloaded binaries or private analysis enter the manifest.

Two independently shared genuine SW4-II copies passed unchanged roundtrips and
targeted all-field preservation checks. The Tk workflow used a genuine copy
for named equipment selection, officer/weapon/mount edits, Review, Undo,
themes, Save As, manual/automatic backups and Restore Backup dialogs. Native
integrity, original headers/seeds, custom/unknown records and unusual values
are preserved. Procedural cases additionally populate all six exact checksum
sections, reject outer-repaired native corruption and protect existing-record
ownership and dependencies. Three genuine Sanada files passed byte-exact outer
framing reconstruction; this does not qualify inner integrity or gameplay edits.

The registered SW4-II genuine copied-save CLI self-test passed, checking 817
fields, native integrity, unchanged bytes, protected input and backup restoration.
Its Max phase changed zero fields because natural limits are unqualified; actual
targeted edits are covered by the genuine-file and Tk tests above. All registered
interfaces initialized and switched successfully. Windows build configuration
includes the new registered backend/editor automatically. No Windows EXE was
built here, and no edited save was loaded or re-saved in an actual game.

Original DW9 and optional Bladestorm files were acquired and inspected privately,
but native identity/integrity and field ownership remain unqualified. Archive
extraction is not a native roundtrip test. The original-only DW8 Windows lane
has no separately established product/format; the acquired XL converter fixture
checks the existing XL format only. Exact remaining inputs are recorded in each
game note and [the supplier checklist](REMAINING_INPUTS.md).

## Gust expansion development checks

Before integration with the other instance's latest reviewed work, the complete
Linux/Xvfb suite ran **1,182 tests in 328.210 seconds: 854 passed, 328 skipped,
no failures or errors**. Missing private fixtures and platform-specific checks
account for the skips. This is source validation, not a Windows executable run.

After rebasing onto `bdb3833` from `codex/prepare-next-update`, **172 focused
integration tests ran in 122.085 seconds: 165 passed, seven skipped, no failures
or errors**. They include the three new format/contract/audit/GUI suites, genuine
copied-save checks, read-only Arland checks, shared adapter/session contracts,
Three Hopes and All-Stars integration, live-save guards and packaging. All
**32 registered editors** passed application startup, theme and switching smoke
checks. The generated inventory and source/privacy verifier passed with
**442 reviewed public manifest entries**; both attributed codec notices are
required and embedded. Independent integration review confirmed all primary
registry/catalog records are preserved and Ayesha PS3/Sophie 2 adapters unchanged.

Genuine-file qualification is separate from the procedural generators. Original
Sophie has byte-exact roundtrips across 31 snapshots from one shared player
archive, with independent surgical checking of 97,303 aggregate mapped fields.
Its no-checksum support explicitly relies on original-PC community evidence;
native loader/integrity confirmation remains an input. Ryza 2 uses a distinct
native gameplay autosave with passing envelope integrity; mislabeled Ryza 1
files are excluded. Fatal Frame II Remake qualifies native system/gameplay
framing, both checksum layers and its distinct JSON schema, preserving the
binary photo suffix. Native GUI edits, Undo, Review Changes, themes, Save As,
backup and exact Restore passed for all three registered editors.

Rorona/Meruru's 44 genuine PC gameplay snapshots support only read-only
structural qualification and unchanged roundtrips. Totori's independently
qualified PS4 title/Cole lead does not qualify PC gameplay or internal integrity.
Other Gust/Blue Reflection profiles remain unregistered with exact per-mechanic
blockers in [the research notes](README.md). Calendar/story/event dependencies
are kept separate from resource edits.

**No edited file was loaded or re-saved in an actual game.** Native Windows
build/startup validation remains required before publication. Version 1.6 and
release links are unchanged; this work creates no release, tag or merge.

## Team Ninja expansion (unreleased)

The Team Ninja branch adds two registered editing profiles without changing the
release version: Nioh 3 Windows USER revisions `0x01030001` / `0x01040000`, and
original Ninja Gaiden II Xbox 360/Xenia extracted revision-6 stories. It is based
on the shared preparation branch and preserves the other instances' Three Hopes,
All-Stars and Wo Long work.

The final Linux/Xvfb public regression run completed **1,224 tests in
348.728 seconds: 876 passed, 348 skipped, zero failures or errors**.
Skips require unavailable private/platform inputs; separate opt-in genuine-file
runs are recorded below. The run includes the other instances' integrations.
An existing DW7 GUI fixture now explicitly reselects its field after Undo, and
the catalog test recognises separate PS4 research and Xbox 360/Xenia profiles.

Independent genuine-file audits exercised **29 editable fields across the two
Nioh 3 revisions** and **76 fields across 22 original NGII stories** individually
and in batches. Restoring the selected field and native checksum reproduces the
complete original payload. Encrypted Nioh 3 Amrita/Gold deductions changed only
the two eight-byte balance fields and checksum in plaintext and ciphertext;
keys, header, seed, tail and every other byte remain exact. A genuine CON package
corroborates original NGII title identity but is not accepted for editing.

Separate private-input tests establish unchanged Nioh PC cipher roundtrips for
two public USER copies with seven flags retained; Nioh 2 uses the retained-four-
flag upstream reference and tests unchanged copy/backup/restore. These do not
verify the unresolved native gameplay integrity algorithms. SOP FFO uses one
Epic launch USER/SYSTEM pair and two Steam USER files plus SYSTEM, separately
from upstream cipher references. Seven Sigma PC gameplay copies, 31 Sigma 2 PC
stories and 19 Black Steam files qualify bounded research inspection, with no
gameplay writes. Sigma's independent redistribution is byte-identical to the
first corpus and is not counted as a second player.

A focused **45-test native research run passed with zero skips**, covering
Nioh 1/2, separate Epic/Steam SOP FFO and separate Sigma 2/Black inspection.
The final integrated genuine GUI/Sigma inspection run passed **7 tests with
zero skips**. Independent format, scalar-contract and surgical-edit checks
cover the two new registered adapters.

Real Tk workflows under Linux/Xvfb exercise both registered editors with
procedural and genuine inputs: search, stack and balance edits, Review Changes,
Undo, Max exclusions, inspection, Light/Dark themes, new-copy saving, exact
backups/restore, destination collision and source replacement rejection. An
independent Nioh 3 GUI check preserves unsigned 64-bit balance precision.
Procedural generators, genuine files and actual game loading are separate
evidence classes. No player files, downloaded source copies, binaries, owner
identifiers or private analysis are included in the reviewed source manifest.

**Actual edited game-load/re-save validation is unperformed for both new
editors.** Linux checks do not replace the native Windows build/EXE workflow;
no Windows executable was built or release published in this task. No game or
third-party editor binary was executed and no integrity flag was cleared.
See [Team Ninja research](TEAM_NINJA_RESEARCH.md) and its per-game coverage tables
for the exact remaining integrity consumers, mechanic dependencies and inputs.

## Licensed action RPG Windows qualification — blocked

The 11 October 2026 investigation on `codex/licensed-action-rpg-expansion`
adds no DQH I/II or Fate/Samurai Remnant adapter or gameplay field. See
[the evidence and exact enabling inputs](LICENSED_ACTION_RPG_STATUS.md).

Linux Python 3.12.14 / Tk 9.0 under the environment's existing Xvfb display ran
the complete public suite: **1,148 tests in 245.878 seconds, 813 passed,
335 skipped, zero failures or errors**. Unavailable private fixtures and
platform-specific cases remain skipped. An initial headless run had five Tk
display errors; the complete displayed run resolved them. No additional native
fixture environment variables were supplied for this investigation.

The source application smoke test initialized **all 29 existing registered
game/platform interfaces**, both themes, platform selection and game switching.
Those regression and GUI tests cover the existing editors and procedural
workflows; they are not DQH or Fate gameplay-edit validation.

After the documentation/research-metadata changes, **46 focused inventory,
source packaging, universal packaging, dependency-review and release-preparation
tests passed in 1.861 seconds with zero skips, failures or errors**. The generated
inventory check still reports 29 adapters. The explicit source manifest verifies
409 public files at unchanged version 1.6, including the new status document;
no saves, owner identifiers, private reports, assets or downloaded binaries were
added. `git diff --check` passes.

Privately acquired DQH1 bytes passed a complete bounded compressed-stream
decode (61,648 consumed; 642,716 produced). DQH2's complete 1,575,744-byte file
was inspected/reacquired. These checks prove neither title's native checksum,
unchanged serialization roundtrip, surgical edit, dependency enforcement,
backup/restore workflow or edited game load. No native Fate file was acquired,
so no Fate file test ran. No target-specific adapter, malformed-input test or
GUI editing workflow could be qualified. No edited save was loaded/re-saved
in any of these three games and no native Windows EXE build was validated.

## Strategy expansion: original PC XIII

Linux Python 3.12.14/Tk 9 under Xvfb completed **971 tests in 199.283 seconds:
673 passed, 298 skipped, zero failures or errors**. `ROTK13_SAVE_COPIES` supplied
all seven privately held genuine original-PC revision-14 TC campaign copies.
The skips are existing private-fixture and Windows-specific cases; no skipped
case is counted as passed. The unchanged base had 958 tests: 660 passed and 298
skipped. All thirteen added format/contract/GUI cases pass without skips.

Native tests establish seven byte-exact unchanged roundtrips, **84 targeted edits**
(each of twelve quantities on each save), preview checksum/header preservation,
field-only body changes, staging/unstaging and seven safe-save/backup/restore
workflows with unchanged source hashes. Procedural checks cover identity,
revision/section rejection, a frozen generator vector, unsigned 16-/32-bit
boundaries, unusual higher values, separate population components, unknown
district references, forged snapshots, changed sources, immutable destinations,
foreign backups and live-directory/resolved-alias rejection.

Actual Tk tests pass on both a genuine and a procedural campaign, covering search,
manual edits, disabled bulk Max, Undo, Review Changes, inspection, retained edits
across game/theme switching, Save As, backup restore and foreign-input rejection.
Two existing selector checks initially rejected the new card's word
"development"; naming commerce, farming and culture explicitly fixed the wording
without weakening those tests, and the complete suite was repeated successfully.

The genuine copied-save CLI self-test also passes: **720 fields checked, zero
changed**, input preserved, byte-exact no-op roundtrip and backup restoration.
No natural Max is established, so targeted manual edits are tested separately.
Its checksum result describes native preview integrity, not a campaign-body
checksum. All **23 registered interfaces** initialize in the startup smoke test.
Generated inventories match; packaging verifies **339 reviewed public files**
and includes all **120 required runtime files**. Windows build configuration
includes the qualified XIII backend/editor; no new runtime dependency is added.

**No edited save was loaded or re-saved in a game.** No native Windows EXE build
or Windows CNG run was performed. Exact executable build/DLC provenance,
additional regions, PK/console profiles and officer/relationship/equipment
dependencies remain unqualified. The [format evidence](ROTK13_FORMAT.md) and
[candidate review](STRATEGY_EXPANSION.md) record these and the XIV/Nobunaga blockers.
This development branch changes no version, tag or release.

## Original Windows PC SW2 and Warriors Orochi additions

The expansion branch is based on `codex/prepare-next-update` at `bdb3833`.
The full Python/Tk suite under Xvfb completed **1,189 tests in 273.674 seconds:
854 passed, 335 skipped, no failures or errors**. Only the new original-PC
fixture variables were configured; unrelated unavailable private fixtures and
platform-specific cases remain skips. After the final SW2 malformed-Mapping
guard and terminology clarification, the combined original-PC format/contract,
actual Tk GUI, independent review and path-safety checks passed **42 tests in
24.824 seconds, zero skips, no failures or errors**.

Two independently acquired original Windows PC saves per game qualified the
period title-specific disk-reader/writer facts. All four passed byte-exact
unchanged roundtrips. Every exposed field was individually changed and reparsed
surgically: **2,329 + 2,314 SW2 fields and 2,468 + 791 Orochi fields, 7,902 edits
in total**. Independent simultaneous all-field edits also preserved every
byte outside mapped fields and the native checksum. Originals remained intact.
Procedural corruption, foreign-profile, malformed staging, eligibility,
dependency, unknown-byte and unusual/higher-value tests are separate evidence.
Actual Tk tests exercise the registered cards, retained sessions, both themes,
search, staging, Review Changes, Undo, protected Max, inspection, automatic
backup, Save As, validated restore, changed-source rejection and live-path
protection. Neither game falls back to a related game's parser.

The registered copied-save CLI self-tests passed for SW2 (2,329 fields) and
Orochi (791 fields). All **31 registered interfaces** passed application startup,
themes and game switching. Inventory generation/checking passed; the existing
Windows build configuration includes both qualified editor/parser imports and
runtime metadata without a build-core change.

An independent private wheel build and isolated installation passed with zero
repository import paths: **31 registrations, 31 inventory entries, 31 CLI
listings, 92 module references / 61 distinct imports, 30 scalar formats and all
14 runtime JSON resources**. The installed package additionally passed four
genuine-file unchanged roundtrips, surgical edits, integrity reparses and
source-preservation checks. No wheel or player data was published.

**Actual edited game-load/re-save and native Windows EXE build/startup validation
were not performed.** An installed original Windows release, exact language/build
and player-run load/re-save of a surgical edit are still needed. Native natural
caps/catalogs and controlled progression, acquisition/equipment, fusion,
guard/mount and story/reward pairs are listed separately in
[SW2](SW2_PC_FORMAT.md) and [Warriors Orochi](WO1_PC_FORMAT.md). Linux file,
application and packaging tests do not establish those missing validations.
Version 1.6 is unchanged; no merge, tag or release is part of this work.

## Three Houses development branch — 2026-10-11

The separately registered Nintendo Switch Three Houses adapter accepts exact
main-campaign gameplay serialization v13 and v23 profiles. It is separate from
Warriors and Three Hopes. Public extracted candidates establish framing and
native payload-byte integrity, not authenticated title/region/build/DLC or clean
unmodified gameplay controls. Exact prerequisites and missing inputs are in
[THREE_HOUSES_FORMAT.md](THREE_HOUSES_FORMAT.md) and
[THREE_HOUSES_MECHANICS.md](THREE_HOUSES_MECHANICS.md).

Final focused `tests.test_three_houses` + `tests.test_three_houses_audit` results:
**29 run, 28 passed, 1 skipped** with the optional private copied-file variables
configured. The single skip is the real Tk workflow because no existing display
was available. Without private inputs: **29 run, 26 passed, 3 skipped**. Two
headless shared-GUI callback tests pass Apply Selected/atomic batch validation,
Review Changes, Undo, new-destination Save As, source preservation and backup /
restore. This exercises callbacks and native storage, not rendered Tk controls.

Eight exact-length public extracted candidates (four v13, four v23) pass
byte-exact unchanged roundtrips, native checksum validation, all **82 exposed
field checks** and original-source preservation. Of those, **74 deliberately
changed fields** have surgical byte differences confined to the declared scalar
and checksum bytes 0–3; the remaining eight controls are already at their minimum
and are verified no-ops. Ordinary equipment identities, unknown records,
original flags, DLC owners, progression/mirrors and all other bytes survive.
Eight shared copied-save self-tests additionally pass input preservation,
native integrity, byte-exact roundtrip, backups and restores. Their automated
bulk-Max edit count is **0**, because every field is excluded from Max; the
independent explicit decrease tests provide edit evidence.

Adversarial checks cover bad checksum, truncation/trailer, wrong native profile,
foreign selected adapter, count/NPC structure mismatches, malformed staged
batches, unknown/duplicate/unjoined/dead/DLC owners, unknown item IDs, unusual
high values and prohibited unlimited-durability grants. Restores validate native
integrity even when an attacker adjusts the backup manifest hash. Changed
sources, resolved aliases and existing destinations cannot be overwritten.

`python -m koei_editor --smoke-test` was attempted and returned exit 1 at Tk root
creation: `TclError: no display name and no $DISPLAY environment variable`.
Live GUI validation remains blocked. A downloaded distribution Xvfb runtime was
briefly started during setup, contrary to the assignment's no-downloaded-binary
constraint; it and that preliminary test run were stopped. Those results are not
used as validation evidence. Subsequent checks use the existing Python/runtime
packages and source code, without that display runtime. No downloaded save-editor
or game executable was run.

No edited save has been imported, loaded or re-saved on Nintendo Switch. No
Windows EXE was built. This branch does not bump versions, tag, merge or release;
the application/package version and latest-release links remain v1.6.

The final full public regression run completed **1,177 tests: 760 passed,
417 skipped, zero failures/errors** in 205.501 seconds. Skips report unavailable
private fixtures/inputs, displays or native Windows prerequisites; they are not
claimed as passes. Five previously unguarded Tk-only appearance/weapon-label
tests now use the same no-display skip policy as other GUI tests, preserving
their display-enabled behavior. The final integration group (adapter/audit,
inventory, package/privacy, adapter contract and new-game integration) with
private Three Houses copies completed **75 tests: 73 passed, 2 display skips**.
The preliminary catalog-schema mismatch and stale in-progress inventory were
corrected before that final full run; catalog validation remains strict.

`tools.update_supported_games --check` passes for all 30 registered source
adapters. `tools.package_release --verify-only` verifies all **417 public source
files** at unchanged v1.6, and `tools.build_windows --print-config` includes the
qualified Three Houses editor/parser imports. No native Windows executable or
release artifact is produced by these checks.


## v2.7 progression dashboard qualification

The dashboard layer projects qualified opened documents into immutable display
objects and uses the existing editors for field navigation. It changes no native
parser, writer, game registration or conversion route. Read-only views retain
unknown/unusual values, distinguish physical records and saved references from
ownership, and never infer overall story completion or proficiency levels.

Focused tests exercise real Canvas clicks, selection/filter/page consistency,
responsive layouts, long text, explicit-denominator bars, retained themes and Tk
timer destruction. Integration checks cover stable-field navigation through
hidden filters, unchanged pending edits/Undo, source/backups, failed-open retention,
presentation failure fallback and dashboard replacement after Save As. DW3 has
equivalent tagged-document lifecycle and navigation checks. Packaged startup
smoke tests render clearly identified internal samples without opening any save.

Private file-level audits cover one DW8 XL PC copy, two distinct WO3 Ultimate PC
states and nine Origins slots across revisions 16, 17 and 29. Mapped field links
resolve and original source hashes plus exact no-edit serialization are retained.
DW3 dashboard validation uses generated tagged-schema fixtures; no independent
native DW3 copy was available in this pass. These tests do not establish edited
or converted game loading/re-saving. Origins proficiency-level/Old Coin writers
and arbitrary DW7 XL weapon base-parameter editing remain unavailable.

The official release workflow requires complete source/Windows coverage, actual
portable and standalone startup, active updated Defender scans of exact payloads,
and artifact integrity before publication. Individual optional native tests skip
when their private inputs are absent; release CI does not contain player saves.

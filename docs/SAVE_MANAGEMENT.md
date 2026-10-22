# Save Doctor, automatic detection and Save Vault

Version **3.0** extends Save Library with read-only diagnostics, bounded location
discovery and a local native-qualified snapshot vault.

Open **Save Library → Save Doctor / Detection / Vault**. The tools also open from
**Manage selected copies**, which carries the selected profile and copies into
the tool window. The main game library and editor sessions stay available.

## Save Doctor

Choose the exact game/platform, select a separate save copy and run diagnostics.
An optional expected SHA-256 verifies that the file matches a known digest.
Reports distinguish path safety, bounded file reads, compatibility/native
validation, original companion context, unchanged serialization and freshness.
Native integrity checks come from the selected registered backend; a successful
report does not establish that every unknown byte has a known native checksum.
Unsupported revisions and foreign or damaged inputs remain rejected. The tool
never tries another game's parser or repairs input.

Doctor accepts every registered game profile, including DW3's separate tagged
workflow. Reports omit local paths, save bytes, account information and native
exception messages. Export creates a new JSON report and refuses an existing
file. A passing diagnostic is separate from actual in-game loading/re-saving.

```text
python -m koei_editor --game wo1 --save-doctor ./SaveCopies/slot.dat
python -m koei_editor --game wo1 --save-doctor ./SaveCopies/slot.dat --expected-sha256 FULL_64_CHARACTER_DIGEST
```

## Automatic detection

Detection inspects Steam roots, bounded `libraryfolders.vdf` and app manifests,
reviewed Steam app IDs, userdata remote directories, and documented native save
locations. Windows, Linux Steam and Proton paths are considered where mapped.
It never launches games, scans entire disks, reads gameplay bytes or writes to
the discovered locations. Linked paths and special files are excluded.

Installed-game and folder matches are **candidates**, not native save validation.
Only repository-backed app IDs and paths are mapped. An unmapped game remains
available through manual copied-save selection. Paths appear locally in the
tool window; public JSON summaries omit personal folders/account identifiers.
Copy the save and its required original metadata into a separate folder before
using Doctor, Library or Vault. Existing live-save and Steam Cloud write
protections remain in force.

```text
python -m koei_editor --discover-saves
python -m koei_editor --discover-saves --steam-root ./Steam
```

## Save Vault

Create a vault in a separate local folder or load an existing vault. A snapshot
records the exact copied gameplay file and original required companion files,
its SHA-256 digests, profile, time, label, branch and parent. Native validation
runs before admission and again on the captured bundle. DW3 and registered
scalar profiles use their own readers, without editing gameplay.

Select snapshots to compare gameplay/context bytes and, for matching scalar
profiles, changed mapped field IDs. Labels and branches organize local history.
Verification checks stored hashes and native qualification. Restoration requires
a **new directory**, preserves original filenames/companions, verifies the exact
restored bytes, and never replaces an existing save. The tool window restores
under a selected parent with a unique snapshot-based directory name.

Deleting a leaf snapshot removes it from the visible index; stored immutable
bytes are retained for safety. This is not secure erasure or automatic disk
reclamation. Bounds limit metadata, snapshot count and stored gameplay bytes.
Concurrent operations use a local lock. A stale lock after interruption is
reported rather than automatically discarded. Checksums detect accidental
damage; they are not authentication against someone able to rewrite both the
store and its index.

```text
python -m koei_editor --vault-operation create --vault-path ./MyVault
python -m koei_editor --vault-operation snapshot --vault-path ./MyVault --game wo1 --save-path ./SaveCopies/slot.dat --snapshot-label BeforeBattle
python -m koei_editor --vault-operation list --vault-path ./MyVault
python -m koei_editor --vault-operation verify --vault-path ./MyVault
python -m koei_editor --vault-operation restore --vault-path ./MyVault --snapshot-id SNAPSHOT_ID --restore-dir ./RestoredCopy
python -m koei_editor --vault-operation compare --vault-path ./MyVault --snapshot-id FIRST_ID --other-snapshot SECOND_ID
python -m koei_editor --vault-operation branch --vault-path ./MyVault --snapshot-id SNAPSHOT_ID --vault-branch Alternate
```

Use `--snapshot-id` with `verify` to verify one snapshot. `label` requires
`--snapshot-id` and `--snapshot-label`; `delete` requires `--snapshot-id`.
`snapshot` optionally takes `--vault-branch` and `--parent-snapshot`.
Commands run without a graphical display. Failures return exit 1, invalid/mixed
options return exit 2, and bounded or cancelled discovery returns exit 3.

## Smart Playthrough Profiles

Open **Smart Playthrough Profiles…** from the Vault tab. A profile combines a
verified Vault snapshot with an exact game-version label and up to three typed
component snapshots: Mod Manager configuration, Configuration Manager game
settings, and Character Workshop build data. Review the component schema and
current adapter limits in [Smart Playthrough Profiles](SMART_PLAYTHROUGH_PROFILES.md).

Preview compares the profile version with the version entered by the user. The
application does not detect the installed game build. Preparing a profile makes
a new isolated folder, restores the selected Vault snapshot there, and stages
the manager components as inert JSON. It does not launch or switch a game,
apply mods/settings/builds, or write a live save. An optional pre-switch backup
accepts only a separate copied save and stores it in a new Vault history branch.
Existing folders and Vault snapshots are never overwritten. An interrupted
preparation can leave an incomplete new environment folder; its error identifies
any backup snapshot that was completed before the interruption.

Each preview and prepared environment can export an AI-readable JSON report.
Reports label the game version as user-asserted and record
`live_save_written: false`; prepared reports also record
`components_applied: false`. Reports contain Vault/profile IDs and relative
staging paths, not local save paths or save bytes. Compatibility means an exact
version-string match plus a verified native Vault snapshot. It does not mean
the game or staged manager data has been loaded.

## Multi-save organization

The existing Library gains folder and duplicate filters, deterministic sorting,
multi-selection across pages, select-matches/clear-selection controls and batch
requalification. Selection never authorizes deleting or overwriting a source.
Identical gameplay bytes can still have different original console/account
context; duplicate groups do not establish interchangeable whole-save folders.
The copied-folder browser retains its scalar-profile scope; DW3 diagnostics and
vault snapshots are available through the management window's profile picker.

Public tests use procedural fixtures and selected-profile contracts, including
corruption, changed source/context, unsafe paths, storage tampering, read-only
detection, report privacy and real Tk worker/lifecycle behavior. They do not
establish new native game-format support or in-game qualification.

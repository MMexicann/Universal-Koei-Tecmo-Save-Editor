# Dynasty Warriors: Strikeforce — US PS3 investigation

The unregistered [inspector](../src/koei_editor/research/strikeforce_ps3/inspection.py)
accepts copied decrypted US `BLUS30471-SAVEDATA` `APP.BIN` and requires its
original `PARAM.SFO` beside the copy. It exposes anonymous slot, storehouse and
officer inspection tables, including comparison of selected and persistent
progression copies. **Gameplay writes and library registration remain
blocked by native integrity qualification.** This is separate from PSP, Xbox
360, Japanese PS3 and European `BLES00825` profiles. No revision is invented
from the varying first bytes.

## Concrete record qualification

Two publicly shared US exports have length 295,012 bytes (`0x48064`), matching
the published three-region `0x18000` stride. Exact save-directory metadata is
checked; only `SAVEDATA_DIRECTORY` is interpreted. Account identifiers and
player names are never displayed. Metadata is mandatory because the payload
has no independently qualified native title/revision identifier.

An existing player record requires the big-endian structure marker `0xC8` at
region `+0x64`, nonempty bounded name bytes at `+0x74` mirrored at `+0xB1`, a
selected-officer ID below 42 at `+0xD8`, and the complete persistent identity
sequence 0–41 at `+0x1878 + officer × 0x40`. Names are compared as opaque bytes
and discarded from inspection results. Every region with the recognized marker
must pass: a valid second region cannot hide a damaged first region. Regions
with a zero marker remain unqualified; existing cheat-created resource and EXP
values do not manufacture player records. Unusual values and unknown bytes are
never repaired or normalized.

The source-proposed gold scalar is big-endian DWORD `+0x1588`. The 196 material
IDs start at `+0x9B8`, ownership bytes at `+0xA7C`, and quantities at `+0xB44`.
The ID array ends exactly at ownership. Apollo's all-material block starts
eight bytes earlier at `+0x9B0`; treating that block start as row zero pairs
the wrong IDs with quantities. The eight-byte prefix and four bytes between
ownership and quantities remain opaque. Source-listed IDs 0–187 and 197 are
recognized for inspection; other IDs, including empty `0xFF`, are unqualified.
Only a known ID with raw ownership exactly 1 and positive quantity is labelled
an existing positive row. That label is **not authorization to write**. Duplicate
IDs, zero quantities, unknown flags and quantities such as 150 remain intact.

The 42 persistent officer records start at `+0x1874`, stride `0x40`: stored ID
`+4`, raw status `+5`, level BE16 `+6`, EXP BE32 `+8`, 12 BE16 progression words
`+0xC`, and weapon references BE16 `+0x28/+0x2A`. Selected progression words
at region `+0xE0` are inspected separately. A genuine file contains different
selected and persistent progression values for the same officer: blindly
editing or synchronizing these copies is unsafe. Apollo's “Quick Level Gain”
halfword at `+0xDE` is the low half of stored EXP, not a qualified level field.

## Evidence and licensing

Offset/stride facts are independently implemented from the published
[Apollo BLUS30471 patches](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30471.savepatch).
The public [alsharfa EU PS3 editor source](https://github.com/alsharfa/Dynasty-Warriors-Strikeforce-ps3-save-editor/tree/a92709c2b8aedb6bbd23a36afad4bb0228d376ff)
corroborates the eight-byte storehouse prefix and full-width officer fields.
It supplies no reuse licence; no code, name catalog or bundled game-data asset
is incorporated. Its EU revision claim is not transplanted to the US profile.

Genuine US sources are [GameFAQs 34790](https://gamefaqs.gamespot.com/ps3/974378-dynasty-warriors-strikeforce/saves/34790)
and [34848](https://gamefaqs.gamespot.com/ps3/974378-dynasty-warriors-strikeforce/saves/34848).
Both are modified player states; the second explicitly advertises modified
weapons. Patched values also occur in unoccupied regions. Their provenance
establishes genuine-file structure, not clean baseline mechanics or a controlled
edited-save game-load test. All player files, account context and private
external source copies stay outside Git.

Apollo and the public editor omit a game-internal checksum update for their
scalar writes. That omission does **not prove** no native integrity dependency
exists. The public editor's historical verification reports reversible byte
writes; it does not establish edited US save loading. Its public issue list
provided no independent loaded-edit evidence. PS3 `PARAM.PFD` encryption,
authentication and ownership remain external; an eventual editor must require
external reimport/resigning and must not claim to rebuild PFD.

## Per-system coverage and exact blockers

| System | Implemented result | Missing evidence before writes |
| --- | --- | --- |
| Input identity / revision / integrity | Mandatory exact US metadata, bounded structure, immutable no-op roundtrip | Native load/serializer integrity behavior or controlled, credible US edited-load/re-save evidence; native revision discrimination. |
| Gold | Per-existing-region candidate inspection | Integrity qualification; legitimate cap for Max (published 999,999 and 9,999,999 targets disagree). |
| Storehouse materials/items | All 196 rows inspected, including IDs, raw ownership, quantities and conservative row classification | Integrity; controlled acquisition/use/storage pairs proving US row ownership/order, item names and quantity bounds; creation/deletion dependencies. |
| Officers / EXP / weapon proficiency / abilities | All 42 identities, level, full EXP and raw progression words inspected | Integrity; level/EXP thresholds, growth rewards, ability interpretation and selected/persistent synchronization rules. |
| Weapons / fusion / equipment | Persistent main/sub weapon references inspected | Native owned-weapon instances, valid IDs, acquisition, main/sub references, forging/fusion and stat-generation dependencies; assets from an unlicensed bundled database are not reused. |
| City facilities / development | No writes or unqualified EU offset transplantation | Controlled US facility-level/EXP pairs and completion/upgrade triggers. |
| Orbs / Chi skills / officer cards / treasures / collections | No writes | US array identities, earned versus owned states, equip constraints and trophy/reward triggers; published EU/PSP correspondence is insufficient. |
| Stages / story / requests / relationships / mounts / bodyguards | No writes | Exact applicable mechanic identities and serialized prerequisites; story completion remains separate from resources. |

Seven focused tests cover procedural no-op snapshots, anonymous tables, exact
size/region rejection, two-slot structural corruption, record identity,
storehouse alignment including row 196, empty/unknown IDs, flags, duplicate rows,
unusual values, mandatory/bounded metadata and source/context changes. Optional
genuine qualification uses `STRIKEFORCE_PS3_US_COPY` and
`STRIKEFORCE_PS3_US_SECOND_COPY`. No gameplay writer exists, so gameplay surgical
edits, GUI saving/backups/restore and actual game loading are deliberately not
claimed as tested. Metadata/structural rejection does not authenticate arbitrary
unknown-byte corruption while native integrity remains unresolved.

## EU editor-source retry

The complete public EU `BLES00825` writer and its
[verification record](https://github.com/alsharfa/Dynasty-Warriors-Strikeforce-ps3-save-editor/blob/a92709c2b8aedb6bbd23a36afad4bb0228d376ff/FORMAT_VERIFICATION.txt)
were reviewed again. The record describes three 295,012-byte gameplay inputs
and reversible field writes, but explicitly says those inputs are not bundled.
The repository's sole `reference/00006.bin` is a weapon database, not a save.
Its verification text does not supply an independently reproducible edited
save-load/re-save check or a native integrity update routine.

The current Apollo save tree has no `BLES00825` export. The reviewed GameFAQs
save list offers PS3 US exports; its European entries belong to PSP, which is
not a substitute. Therefore an EU adapter needs a genuine complete decrypted
`BLES00825-SAVEDATA/APP.BIN` with its original `PARAM.SFO`, plus native
loader/writer integrity evidence or a controlled edited-load/re-save pair
showing the complete external reimport/resign workflow. The existing US files
and an EU executable's title string do not qualify EU save editing. No
unsupported library entry or copied upstream weapon database is added.

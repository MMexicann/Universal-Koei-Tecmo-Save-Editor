# Fire Emblem Warriors: Three Hopes — Switch extracted slot

This independent adapter opens a separately extracted, extensionless `SlotData`
copy. It accepts the observed **5,243,228-byte (`0x50015C`)** native slot profile,
first u32 little-endian 1 and the complete section layout below. This is a save
profile, not proof of an exact game build, region or entitlement. Other sizes,
section revisions and shapes are rejected. Console encryption/import and owner
reassignment are outside this adapter. Keep `UserData` and the complete original
save-management export intact; only a new copy of the selected slot is written.

## Sources and independent native files

[async-amethyst/few2-010-binary-templates](https://github.com/async-amethyst/few2-010-binary-templates)
at commit `9b6e9946e5a33e182f80fbe3553e7c2afbebbdcb` supplies a save-specific
`FEW2Save.bt`, detailed scalar/record widths and factual character/weapon IDs.
It is MIT, copyright 2022 SilentLuna; the applicable notice is retained with
factual name tables. Its parser/editor implementation is not copied wholesale
or executed. This Python adapter independently implements bounded traversal,
native checksums, immutable snapshots, original-record qualification and safe
copy storage. The separate DeathChaos ThreeCopes templates describe `LINKDATA_A`
**game assets**, not save offsets, and are not used for save records.

The public [Three Hopes modding discussion](https://gbatemp.net/threads/any-interest-in-modding-hacking-few-three-hopes.614680/)
supplies `slotdata4.rar` attachment 317150 on page 2 and `save.rar` attachment
319394 on page 6. The latter contains complete native `SlotData0`, `SlotData2`,
`SlotData3`, `SlotData4`, `SlotData5` and `UserData`. These progressed exports
include edited/cheat-like values, not untouched gameplay controls or proof of
natural stat caps. The archive and player data remain private. No game binary,
player name or save is distributed. A separate public ImHex template attachment
317502 on page 4 explicitly identifies both eight-byte name arrays for each of
Shez and Byleth; its implementation is not shipped.

## Section integrity and exact bounds

All 143 top-level sections start at `0x15C`, with 16-byte headers holding u32
checksum/total size/revision/reserved. The strict observed revision/reserved
profile is 1/0. Ordered total sizes are:

```text
0x298, 0x560, 0x6EFC8, 0x85B0, 0x1DB20,
136 × 0xD80,
0x1AF0A4, 0x1AF0A4
```

Top-level section 2 at `0x954` contains an additional nested `0x560` section at
`0x6F3BC`, ending at its parent end `0x6F91C`. The parent checksum is the sum of
its **own body only**, bytes `0x964..0x6F3BB`; the nested section independently
sums its body. Other sections sum bytes after their 16-byte header to their
section end. All **144 own-body u32 sums** independently match all six complete
native exports (five archive slots and one separate upload). Blindly summing the entire nested parent's body, as the template's
opaque default appears to suggest, is incorrect; this implementation explicitly
separates the child. Supported bounded body sums fit u32 without overflow.

The final parsed section ends `0x466734`; the remaining 629,288 bytes of slot
capacity and the opaque parts of the `0x15C` prefix are preserved byte-for-byte.
Section checksums check integrity of their section bodies. No full-file/header/tail
checksum is invented or claimed, and arbitrary corruption in unchecked opaque
capacity cannot be detected. Edits only recompute the changed gameplay section's
own checksum. The record/name mirrors are checked before exposing controls.

## Qualified writable fields

| Field | Proof and dependency gate |
| --- | --- |
| Gold | Current u32 at `0x77F64`, within gameplay section `0x77ECC..0x959EB`. The save template distinguishes gold from renown at +8. Existing balance can decrease from opened value down to zero; no increase, storage-target Max, earning history, reward or shop-purchase action. Its exact natural cap is unqualified, so no Max is offered. |
| Existing material stocks | Up to 33 positive quantities in the template's nine explicitly typed material arrays. Each u16 LE quantity can decrease to zero or an intermediate opened balance. Empty and exceptional full-width words are read-only. Six adjacent opaque bytes in every eight-byte record, discovery state, facility upgrades and reward records are preserved. Category/physical-stock labels are used until exact item-name order is independently qualified; no Max or increases. |
| Shez name | Eight-byte ASCII array at `0x841FC`, mirrored in prefix `0x3C`. Both original eight-byte arrays must match exactly; nonempty printable ASCII text must already exist. Requires a currently deployed Shez native ID 110/111 and the corresponding positive-HP/level physical profile. Inactive/default records do not manufacture ownership. |
| Byleth name | Eight-byte array at `0x84224`, mirrored in prefix `0x64`, with the same original equality/ASCII gates. Requires an original Byleth recruitment bit (bit0 male/bit1 female at `0x77FF4`) and a corresponding positive-HP/level native profile ID0/1. No recruitment or gender bit is changed. |
| Name validation | New names are nonempty 1–8 printable ASCII characters; shorter names zero-pad only the two declared eight-byte arrays. Untouched non-ASCII/unusual arrays are preserved and remain uneditable. Assigning the opened displayed name is an exact no-op preserving stale padding. Names are excluded from Max; Review Changes and Undo use strings. |

Field eligibility derives solely from the immutable opened snapshot. Pending
changes cannot activate an unowned/default field. All pending edits are checked
before new edits, Undo, Max and serialization. Native `SlotData3` qualifies
both names; `SlotData4` qualifies the recruited Byleth name. The other
three reviewed slots qualify only resource controls. This conservative current-deployment gate
can withhold Shez customization even where the character exists in the broader
campaign roster; it does not guess an unqualified roster-ownership flag.

The reviewed save template's material arrays begin after exactly 1,150 24-byte
weapon records, four opaque bytes, 1,040 eight-byte accessory records and 249
eight-byte consumable records. This independently places the material master
block at `0x831B4`. Its explicitly typed quantity arrays are:

| Native category | First quantity | Eight-byte records |
| --- | --- | ---: |
| Stones | `0x831BC` | 8 |
| Building materials | `0x8366C` | 4 |
| Training gear | `0x836BC` | 3 |
| Combat manuals | `0x836E4` | 3 |
| Smithing sets | `0x8370C` | 3 |
| Furnishings | `0x83734` | 3 |
| Licenses | `0x8375C` | 3 |
| Insignias | `0x83784` | 3 |
| Storage materials | `0x837AC` | 3 |

Following the final array's native gaps, battalion records and trailing bytes
arrives at the independently qualified Shez name `0x841FC`; no flattened
inventory or cross-category stride is assumed. All six reviewed native exports
admit 29–33 positive material stocks and pass the complete section checksums.
Their edited/cheat-like state does not prove a natural material cap. Reductions
change only the selected two quantity bytes and the gameplay body's checksum;
they do not perform a purchase, upgrade, exchange, reward claim or discovery.
All 33 quantities remain searchable, including withheld empty/unusual words.

## Per-mechanic checklist and precise blockers

| Mechanic | Implemented feature or missing evidence |
| --- | --- |
| Gold / renown | Decrease-only opened gold; renown is inspected and preserved. Renown shop/NG+ unlock prerequisites and earned/spent history are unmapped. Public discussion includes inability to claim renown characters after arbitrary save modifications, so no general renown/unlock action. Natural gold cap still needed before increases/Max. |
| Character customization | Qualified existing Shez/Byleth ASCII name pairs. Non-ASCII encoding and unqualified ownership states remain preserved/read-only. Gender, recruitment, deployment and class/equipment references never change. |
| Character stats / levels / EXP | 136 named physical profiles, stride `0xD80`, with stored HP/level/equipped weapon references inspected. Source stat setters do not qualify level/EXP curve, training, class rewards, caps, limit-break resets or derived stats. Native high/edited values do not establish legitimate bounds. |
| Classes / skills / combat arts / unique abilities | IDs exist in source, but mastery/learning, class unlocks, unique ability identity, prerequisites, skill capacity and rewards lack synchronized native proof. No arbitrary skill-ID replacement. |
| Weapon inventory / forging / attributes | 1,150 physical 24-byte records from `0x79D98`, named type, added might/durability, forge steps and skill IDs inspected. Stored forge steps and added stat terms are distinct. Matching material consumption, per-weapon natural limits, smithy progression and intrinsic/personal-weapon rules remain unqualified; no forged-stat or identity writes. |
| Weapon durability / repair / appraisal / personal weapons | Basic/rusted identities exist but repair/reforge results, costs, unique-weapon entitlements and equipped convoy references are not fully proven. No creation, swap or broad maximum. |
| Stones / facility materials | Existing positive stocks in nine save-specific categories support reductions only; all 33 quantities are searchable. Item-name order, natural caps, discovery and acquisition transitions remain unqualified. No facility upgrade, reward claim or generic inventory-slot Max. |
| Accessories / consumables / gifts / ingredients | Kept read-only: per-position identities, quantity/discovery semantics and special ownership/equipment dependencies remain incomplete. Material-array proof does not qualify the separate 249-record consumable array. |
| Battalions | Source pool and deployment references exist; ownership, usable limits, dismissal restrictions and reward/slot capacity dependencies remain unqualified. Public discussion describes an undismissable-battalion reward loop; no destructive blanket wipe. |
| Bonds / support / camp activity / training / facilities | Per-record thresholds, activity points, first-time rewards and prerequisite transitions need controlled native pairs. No guessed array offsets. |
| Character recruitment / NG+ / DLC / costumes | Read-only original admission checks where specifically mapped. Full starter records, gender/campaign gates, rewards and entitlements are missing; no unlock writes. |
| Campaign / route / stages / ranks / records / collections | Kept separate from resource/customization actions. Chapter changes alone can fail loading or leave inconsistent rewards; stage/rank/claim and collection transitions need exact native proof. No completion action. |
| Other versions/regions/platforms | Only the exact observed native section profile is supported. A first prefix value of1 is not claimed as a game build. Matching complete native files and source/native layout proof required for other shapes. |

## Verification

`tests.test_three_hopes` contains ten format/native checks and four real-Tk
workflows. With `THREE_HOPES_COPY` pointing privately to an admitted complete
`SlotData3` export, **14/14 pass without skips**. Procedural data tests endian
encoding, all 144 checksum-covered-body corruption cases (including the nested
child), malformed size/header/revision, exact immutable snapshot/format/raw type,
original ownership/name-mirror/ASCII gates, invalid mixed pending edits and
containers, surgical field/name-pair/checksum differences, exact name no-op/Undo,
extensionless backups, source-change rejection and destination protection.

The genuine file passes byte-exact unchanged serialization and independent
edits to every qualified exposed field. Each edit changes only its declared
scalar/name pair and the gameplay-section checksum; source data, recruitment,
class/gender/deployment and opaque capacity remain unchanged. Real Tk tests on
procedural and copied genuine data cover named search, Apply, string Review,
Undo, inspection, themes, backup/new-copy Save As and exact-byte restore.
Without the optional private native input, three native-dependent tests explicitly
skip. No newly edited save has been imported, loaded or re-saved in the game.

`tests.test_three_hopes_audit` adds eight independent review checks. The reviewer
traversed stored native headers independently of the production table, checked
literal known-answer checksum triples, tested all six distinct public exports
(five slots from `save.rar` plus the separately uploaded `slotdata4.rar`), and
independently verified every exposed positive native field's exact scalar/name
pair/checksum writes. Ownership, original mirror agreement, unusual padding,
invalid pending batches, immutable snapshot qualification and surgical unknown
byte preservation pass. Registered procedural and genuine copied-save checks also
verify the canonical checksum profile, backup, source preservation and CLI use
from an unrelated working directory. **The combined 22 checks pass without skips
under real Tk/Xvfb with all six private inputs.** The review's optional native controls use
`THREE_HOPES_REVIEW_COPIES`, joined with the local `os.pathsep`; they remain private.
This independent review is not edited game-load/re-save validation.

Additional material checks cover all 33 records independently, zero-count
withdrawal from editable fields after reopening, original eligibility and
full-width-word exclusions, all pending-map validation, precise checksum/byte
preservation, original-value Undo and exclusion from Max. The real Tk material
workflow exercises category search, Apply, Review, Undo, themes, new-copy Save As,
backup and restore. Native every-field audits also cover each newly admitted
stock across all six private sources; these are native format checks, not
controlled gameplay acquisition/spending pairs or edited game-load validation.

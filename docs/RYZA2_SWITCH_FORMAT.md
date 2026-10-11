# Original Atelier Ryza 2 — Nintendo Switch

The adapter qualifies original **Atelier Ryza 2: Lost Legends & the Secret Fairy**
Switch main-game `data.dat` exports with native header/app revision 0. It offers
**unspent skill-tree SP deductions** and searchable existing inventory/equipment
inspection. Existing ordinary quality controls use the conservative 1–100 editor
range only when the adjacent native word is zero. Max is disabled; natural SP
ceilings, higher quality progression and learned-node edits are not inferred.
PC revision 1, Ryza 1, Ryza 3 and DX are separate profiles.

## Native evidence and source qualification

The freely shared [Viren070/NX_Saves collection](https://github.com/Viren070/NX_Saves/blob/main/index.md)
contains a `Super Starter` original Switch export for title `01009A9012022000`.
Its gameplay and autosave are byte identical, so they count as **one reference
state**, not independent earned-state observations. A companion system file is
not gameplay and is rejected. The starter is treated as a modified reference: its unspent
SP is 117,431,850 and its 249 existing item records have nonzero adjacent quality
words. That is not evidence of a legitimate SP cap, natural quality limits,
clean progression or edited-save game acceptance.

The existing MIT-attributed Gust envelope codec validates both native integrity
layers and preserves the original seed, header, footer and trailer. The reference
has a complete 737,231-byte decoded root payload and a byte-exact no-edit
roundtrip. Save files and external source copies remain outside the checkout,
source manifest and release assets. No game or downloaded editor binary ran.

The Switch profile was independently inspected: header revision 0, exact
`app_ver` body `BE32(1), BE32(0)`, original Ryza 2 map markers, `AlchemyTree`,
`ruin` and `Feeding`, and absence of Ryza 1's `FieldMix`. Complete root framing
and unique tags are required. Item version 2, 100-byte records and five exact
capacities (200, 150, 5,000, 150, 50) are checked. Party version 3 qualifies ten
1,300-byte records, existing unique character identities and eight-item equipment
arrays. Ownership IDs, serials and empty-slot framing are validated before
controls. Only Ryza is named; other character IDs remain numbered until an
independent mapping is established.

The native `AlchemyTree.ver` body is exactly `BE32(2), BE16(4)`. Its unique
`SkillPoint` body is `BE32(4), BE32(balance)`. The second word is the writable
big-endian unspent SP scalar; the first is a width prefix. The separate
`SkillState` node and every other byte remain untouched. The balance must be
nonnegative signed 32-bit; edits allow only 0..the opened balance. Unknown,
duplicate or unsupported tree/scalar profiles do not expose an SP field.

Public [Ryza 2 field research](https://github.com/sterben-Dev10/SaveWizard-Resources/blob/main/SaveWizard-Codes/Atelier%20Ryza%202%20Lost%20Legends%20%26%20the%20Secret%20Fairy%20%5BSaveWizard%5D.txt)
and the independently qualified [PC profile](RYZA_FORMATS.md) corroborate record
geometry: instance `LE16 +0`, item ID `LE16 +4`, quality `LE16 +6`, adjacent
word `LE16 +8`. No third-party implementation or bulk item catalog was copied.
Switch record structure was inspected independently; PC title/revision bytes
are not accepted as Switch identity. A two-byte quality write is admitted only
when that adjacent word is zero, matching the public DWORD write without
normalizing adjacent data. Empty/important/sentinel records remain read only.
**All 249 records in the native starter fail this zero-adjacent condition and
are inspection only.** The acquired Switch reference proves the SP edit;
conditional zero-adjacent quality edits currently have source/profile and
procedural evidence, not a genuine Switch zero-adjacent edit fixture.

## Mechanics and coverage checklist

The [official skill-tree manual](https://www.koeitecmoamerica.com/manual/ryza2/en/7300.html)
describes SP earned through synthesis, quests/events and spent on recipes and
alchemy skills. A balance deduction does not learn a recipe or unlock a skill.
The [official synthesis manual](https://www.koeitecmoamerica.com/manual/ryza2/en/4200.html)
distinguishes item quality, trait-slot/material-loop unlocks, item level and
character dexterity. None is derived from an arbitrary resource cheat target.

| System | Implemented/tested or specific remaining blocker |
| --- | --- |
| Unspent skill-tree SP | Exact typed big-endian scalar deductions; native targeted edit, unchanged learned state and safe copied-file workflow pass. No increases or Max. |
| Existing inventory/equipment | Searchable location/slot, item/instance IDs, quality, adjacent value and control availability. No item creation, movement or equip-reference writes. |
| Ordinary quality | Conditional 1–100 controls require zero adjacent value, valid existing ownership and ordinary pool. Procedural/source evidence only for that branch; the acquired modified starter's quality records are all read only. A clean same-profile synthesis pair is needed for independent native qualification. |
| Higher quality and adjacent values | No nonzero-adjacent normalization or linked-value writes. Need native quality-cap node and controlled synthesis/equip pairs; a DWORD cheat value is not dependency proof. |
| Item names/categories | Native IDs remain visible; independently qualified ID/name/applicability mapping is missing. No third-party bulk catalog imported. |
| Traits/effects/elements/rebuild | Recipe, trait-slot and level-cap dependencies plus controlled synthesis/rebuild pairs are missing. Unknown values remain intact. |
| Cole/gems and stack quantities/uses | Native tags/records provide leads; displayed balances/counts, preview relationships, boundaries and action pairs are unproved. |
| Learned skills/recipes | `SkillState` is preserved. Exact IDs, prerequisite and reward dependencies plus acquisition pairs are missing. |
| Character/alchemy growth | Party structure is qualified, not EXP/level/stat semantics. Native thresholds, current/derived relationships and controlled growth pairs needed. |
| Exploration/ruins/collections/quests | Native tags alone do not establish completion, prerequisites or reward claims; controlled action pairs required. |
| Story/events/calendar | Kept separate from resources; no completion, rewind or reward operations. |
| Other revisions/DX/Ryza 3 | Need matching independent native gameplay and title/layout/integrity qualification. Current latest NX_Saves corpus has no Ryza 3 gameplay export; GitHub disk-editor queries found no usable Ryza 3 writer. |

## Validation

`tests/test_ryza2_switch.py` generates deliberately non-playable profiles for
strict title/revision/framing/integrity rejection, SP endianness and bounds,
learned-state/unknown-byte preservation, conservative quality dependencies and
shared safe storage. Select `RYZA2_SWITCH_SAVE_COPY` privately for the native
modified starter to additionally test unchanged roundtrip, SP-only surgical
changes, copied Save As, source preservation, backup and exact restore. With a
display, its GUI test exercises open, searchable inspector data, edit, Undo,
Review Changes, themes, Save As and restore using that reference. Public runs
without a native copy use a labelled generated fixture and skip the native test.

Source qualification means the actual export's integrity, unchanged roundtrip
and scoped SP write pass; it does not claim the reference is an unmodified
earned state. No edited Switch game-load/re-save or Windows executable validation
was performed by these Linux checks. Root integration must register the exact
scope, update inventories and qualify the Windows workflow before publication.

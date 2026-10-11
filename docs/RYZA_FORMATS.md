# Original Atelier Ryza PC qualification

The development adapter for **Atelier Ryza 2: Lost Legends & the Secret Fairy,
original Steam PC** edits quality on existing ordinary inventory and equipped
item records, and reduces qualified unspent skill-tree SP. It uses the shared
staged Undo, Review Changes, copied-save, backup, restore and atomic Save As
workflow. It does not support Ryza DX,
Ryza 2 DX, Ryza 3 or console files. The separate
[original Ryza 1 Switch adapter](RYZA_SWITCH_FORMAT.md) qualifies complete
revision-4 main-game exports for conservative existing-item quality edits
and searchable equipment/trait inspection; it does not qualify Ryza 1 PC.
The [original Ryza 2 Switch profile](RYZA2_SWITCH_FORMAT.md) separately qualifies
revision-0 main-game SP reductions and inventory/equipment inspection, with
conditional zero-adjacent quality controls. Its modified starter reference is
not evidence of clean progression or natural resource caps.

## Native evidence and framing

The public [SaveGame.pro Ryza 2 archive](https://savegame.pro/pc-atelier-ryza-2-lost-legends-the-secret-fairy-savegame/)
contains one independently inspected `AutoSave/data.dat` gameplay file with a
739,697-byte decoded payload. Its native XOR and additive integrity checks
pass. Its `GameData00`, `GameData10` and `SystemData` files are byte-identical
to files in the site's [original Ryza archive](https://savegame.pro/pc-atelier-ryza-ever-darkness-the-secret-hideout-savegame/).
Those mislabeled copies are rejected by the Ryza 2 adapter and are not evidence
of Ryza 2 gameplay support. Only `.dat` files were extracted for inspection;
no bundled shortcut, executable or third-party editor was run. Player files
and archive contents remain outside the repository and release assets.

The codec reuses the existing Gust envelope implementation, attributed to
[Tartarshia/Sophie2SaveEditor](https://github.com/Tartarshia/Sophie2SaveEditor/tree/93d807072a852c73799394af4d32fb164841cd3e)
under the repository's
[MIT notice](../licenses/atelier-sophie2-save-editor-MIT.txt). Ryza gameplay
records were independently inspected. Reusing a passing envelope is not a
claim that Sophie 2 and Ryza share a gameplay schema.

The parser qualifies all of the following before exposing writable fields:

- Native integrity, bounded file size, original header profile and decoded
  preamble; the header alone cannot distinguish the two titles.
- Complete root node framing, unique root tags and the exact native `app_ver`
  body `BE32(1), BE32(1)`. These are observed serialization values, not a
  claim about a marketing patch number.
- Ryza 2 `AlchemyTree`, `ruin`, `Feeding` and title-specific map markers;
  rejection of the original Ryza `FieldMix` profile.
- Inventory layout version `BE16(2)`, Party version `BE16(3)`, five exact
  pool capacities (200, 150, 5,000, 150, 50), 100-byte item stride and
  10 framed Party records of 1,300 bytes each.
- Existing Party identities, eight-item equipment arrays, occupied item IDs
  and unique instance serials across inventory and equipment. Empty equipment
  can retain a character/slot-reserved serial without becoming an owned item.

Node total sizes are little endian; array byte counts are big endian. Within
each qualified 100-byte Ryza 2 item, the instance serial is LE16 at `+0`, item
ID is signed LE16 at `+4`, and quality is LE16 at `+6`. The next LE16 at `+8`
is distinct native data and remains unchanged. Public
[PS4 SaveWizard code leads](https://github.com/sterben-Dev10/SaveWizard-Resources/tree/main/SaveWizard-Codes)
helped locate tags and strides; their DWORD quality writes are not used because
they also overwrite that adjacent value. PC layout and checksums were verified
independently. Unknown positive item IDs and unknown record bytes are retained.

Important-item pools, empty records and quality values `0`/`0xffff` are
read only. The editor neither creates ownership nor changes IDs, serials,
equipment assignments, traits, effects or adjacent synthesis data. Existing
quality above an editable cap is preserved byte-for-byte during no-op saving;
restoring an opened unusual value unstages its edit.

An optional SP control separately qualifies the unique `AlchemyTree.ver`
child body `BE32(2), BE16(4)` and unique `SkillPoint` child body
`BE32(4), BE32(balance)`, with a nonnegative signed four-byte balance. Only
the second word is written, in big endian; item quality remains little endian.
Absent, duplicate or unknown tree/scalar profiles do not grant an SP field.
The separate `SkillState` array and every learned node remain unchanged.
[The expansion note](PERSONA_GUST_DEPTH.md) records the native scalar evidence,
exact qualification and surgical tests.

## Mechanics and exact blockers

The [official Ryza 2 synthesis manual](https://www.koeitecmoamerica.com/manual/ryza2/en/4200.html)
describes quality, item level versus character dexterity, material-loop effects
and the requirement to unlock trait slots. Quality has a legitimate natural
upper bound of 999, but its initial cap is 100 and later caps require
progression/skill unlocks. The
[player discussion of those unlocks](https://gamefaqs.gamespot.com/ps4/296163-atelier-ryza-2-lost-legends-and-the-secret-fairy/answers/579874-what-a-best-start-to-begin-crafting-999-quality-items)
is corroborating mechanics evidence, not a native offset source. The adapter
therefore allows deliberate quality edits from **1 to 100**, excludes them
from bulk Max and preserves higher opened values. Controlled before/after
saves for the quality-limit skill nodes are required before admitting higher
edits; a storage ceiling or cheat value does not substitute for this mapping.

The [official skill-tree manual](https://www.koeitecmoamerica.com/manual/ryza2/en/7300.html)
describes SP earned from synthesis, quests and events and spent on recipes and
alchemy skills. The SP control allows only **0 to the opened balance**, with
Max disabled. A deduction does not learn a skill, unlock a recipe or raise the
quality cap. The opened balance supplies the upper bound; no natural maximum or
SP increase is inferred. Higher nonnegative originals remain reversible.

| Mechanic | Implemented/tested or specifically blocked |
| --- | --- |
| Item quality | Existing ordinary inventory/equipment LE16 edits, 1–100; surgical native tests and copied-save workflow pass. |
| Inventories and equipment | Existing IDs, serials and locations inspected; qualified quality controls are separate. No item creation, movement, equip assignment or ID replacement. Item catalog/applicability and controlled transfer pairs are missing. |
| Quantities | Pool occupancy is distinct from a stack/use count. No guessed quantity field; independent per-item count/use pairs required. |
| Traits, potentials and effects | Recipe/material-loop and unlocked-slot dependencies apply. Native slot/level layout, IDs and controlled synthesis pairs are required before writes. |
| Synthesis and rebuild | Item level, dexterity, effect loops and recipe dependencies remain unchanged. Native action pairs and dependency schema are missing. |
| Cole and other currencies | Native gameplay/header-preview relationship, natural bounds and controlled purchase/reward pairs are not qualified; no currency writes. |
| Recipes, character/alchemy EXP | Serialized unlock/EXP fields, progression thresholds and reward dependencies are not qualified; no writes. |
| Unspent skill-tree SP | Qualified big-endian scalar deductions, 0..opened balance; native surgical checks pass. Increases/natural caps need displayed earn/spend pairs. No learned-node changes. |
| Learned skill tree and higher quality caps | Initial quality cap 100 enforced. Exact serialized cap-unlock nodes and prerequisite pairs are missing; SP reductions do not unlock them. |
| Friendship, exploration, ruins and collections | Native tags alone do not qualify completion/reward semantics. Controlled action pairs and reward dependencies are missing. |
| Story, calendar and events | Kept separate from resource edits; no completion or rewind controls. |

The [original Ryza synthesis guide](https://barrelwisdom.com/ryza/synthesis-basics)
also records the 999 quality limit, varying trait-level limits, alchemy-level
dependencies and quality's lack of effect on gathering tools. These observations
are title-specific mechanics leads and are not transplanted to a Ryza 2 schema.

## Other Ryza titles

**Original Ryza 1 PC is blocked and unregistered.** Both public gameplay copies
pass the envelope checks and have coherent earlier 66-byte inventory records,
but their final `secret_base` node declares 3,532 bytes with only 112 remaining.
The nested plant-array size declares 3,420 bytes which are absent. This could
be native zero-tail elision or an altered upstream save. No native loader/source
or independent third gameplay file has established that omission as legitimate.
The parser rejects it; it never pads, repairs or rewrites it. Required input:
an independently sourced complete original Steam gameplay save, or factual
native loader/serializer evidence explaining this exact omission.

Separate freely shared original Ryza Switch gameplay files in
[Viren070/NX_Saves](https://github.com/Viren070/NX_Saves/blob/main/index.md)
pass the same envelope checks and have complete root framing (491,876-byte
decoded main-game profiles, native header revision value 4). DLC episodes have
different revision profiles. These console files corroborate envelope reuse
but neither qualify the PC revision-0 omission nor establish PC compatibility;
the PC parser rejects them. The [separate Switch qualification](RYZA_SWITCH_FORMAT.md)
now proves complete main-game quality writes without accepting the incomplete
PC tail. DLC episode profiles remain excluded. A separate
[PC save-sharing discussion](https://www.reddit.com/r/Atelier/comments/18eupuq/)
links an independent collection, but its filetransfer.io download host returned
403 during research; no file from that lead has been inspected.

**Original Ryza 3 is blocked and unregistered.** The
[Barrel Wisdom PC-save collection](https://barrelwisdom.com/blog/atelier-pc-saves)
offers system data for the trilogy, not gameplay fixtures. A system file cannot
qualify currencies, items or character records. Required input: a freely shared
original Steam Ryza 3 gameplay `.dat`, native checksum/record qualification and
controlled action pairs for proposed edits. Asset tooling and runtime trainers
remain research leads rather than disk-save offsets. No original/DX cross-title
schema assumptions are made.
The [public prologue-skip save video](https://www.youtube.com/watch?v=ZEC_0Cz5L88)
is another gameplay lead, explicitly limited by its author to version 1.00 and
all DLC. Its download description was not retrievable, so it provides no native
file evidence.

## Validation distinction

[Format and contract tests](../tests/test_ryza_format.py) use deliberately
non-playable procedural buffers to exercise malformed framing, foreign titles,
checksums, ownership, bounds, unusual originals, exact unchanged serialization,
LE16-only edits, immutable snapshots and backup/restore/source protections.
[Independent audit tests](../tests/test_ryza_audit.py) separately exercise staged
mapping rejection, no-quality records, all-field byte preservation and GUI
Undo/Review Changes/Save As/backup/restore. Procedural data is not genuine-save
evidence.

The optional `RYZA2_SAVE_COPY` test independently exercises the public native
Ryza 2 autosave: exact unchanged roundtrip, surgical quality edit, native
read-back verification, copied-file Save As, backup and byte-exact restore.
The [expansion tests](../tests/test_persona_gust_depth.py) additionally qualify
its SP framing and surgical deduction, generated unknown/duplicate profiles,
endianness, bounds, unusual originals, Undo/Max exclusions and actual Tk controls.
The GUI integration suite also accepts that privately held fixture. There is
**no actual game-load or re-save validation** of an edited file, no Windows
binary qualification from these Linux tests and no claim that the early-game
sample covers every patch, DLC or later-game layout.

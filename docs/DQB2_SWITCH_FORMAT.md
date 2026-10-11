# Dragon Quest Builders 2 — original Nintendo Switch

This separately registered profile edits complete extracted original Switch
`CMNDAT.BIN` gameplay copies, native revision `0x40004`. It does not decrypt,
sign, move ownership, operate on a console or transplant a PC save. The original
[Steam PC profile](DQB2_PC_FORMAT.md) remains separate.

## Supported mechanics

- Reduce quantities of twenty individually reviewed ordinary medicines and crop
  seeds in existing pocket/bag stacks. Eligible originals contain 2–999 items;
  edits keep at least one and never exceed the opened quantity. Max is disabled.
- Search all fifteen pocket and 420 bag records by name, ID, slot, container,
  quantity and edit availability. Unknown, empty, single-item and unusual
  records remain read-only and byte-preserved.
- Inspect separately stored player level, EXP, HP/bonus, fullness, attack,
  defense and equipped weapon, hammer, shield and armor IDs.
- Shared Undo, Review Changes, validated backups/restore and atomic Save As;
  source changes and live PC/cloud paths are rejected.

Export the complete original slot with your console save manager, make a
separate copy, edit its `CMNDAT.BIN`, then retain the other original slot and
system files when reimporting. This editor does not recreate those companions.
Do not mix CMNDAT and island files from different players or save slots.

## Native source and platform evidence

The complete GPL-3.0
[turtle-insect/DQB2 writer](https://github.com/turtle-insect/DQB2/tree/c551524dc9179a3d614390cb5ab6f2f73300a2fc)
explicitly supports Switch and Steam. Independently implemented factual framing
and ordinary-record rules from the existing PC backend are reused after separate
Switch qualification; no upstream GPL implementation, bulk catalog, executable
or extracted game assets are incorporated.

The title-labelled public
[NX_Saves archive](https://github.com/Viren070/NX_Saves/blob/603dc50937246f08ed80670c1aa1d0c0607fa73d/index.md)
contains two distinct native gameplay slots in `NX6400000-GAME` and
`NX6400000-01-GAME`, plus original system/photo/island companions. The source
labels this archive `All Items Unlocked No Hacks`, Spanish, title
`010042000A986000`. That source label does not prove an unmodified save or a
natural limit; eligibility comes from the independently reviewed field scope.
The complete native exports establish two original 5,800,318-byte padded
CMNDATs with distinct shorter used lengths, both decoding to 5,627,194 bytes.
Known medicine/seed records independently match the published record geometry.

A second archive labelled `Hacked` contains a CMNDAT byte-identical to one
previously shared PC copy. That repeated file is not counted as independent
Switch evidence or as proof of PC/Switch ownership conversion. Player data,
system companions and all downloaded archives remain private.

The observed Switch header and record layout also occur in the qualified PC
profile. Raw CMNDAT bytes alone cannot establish the original device or account.
The selected adapter therefore identifies the documented platform; it does not
invent a platform marker. The Switch document, format/backend binding and backup
manifest use their own `dqb2_switch` identity. PC documents/backups cannot be
passed to Switch operations, and Switch operations never probe another parser
after rejecting a foreign document or an unsupported native revision.

## Complete bounded integrity and byte preservation

The native header is `0x2A444` bytes, followed by one zlib body, with the used
length stored little-endian at `0x10`. Switch input must have the observed exact
native prefix/revision and complete padded capacity. The reader validates the
native Adler checksum, EOF, absence of concatenated/trailing compressed members
and the exact bounded decoded size. Truncation, overexpansion, corrupt streams,
foreign extents, unsupported revision words and compact unqualified Switch
copies are rejected rather than repaired.

No-op serialization returns every original byte. A qualified edit changes only
selected 16-bit quantity words in decoded data; IDs, equipment, growth,
ownership, recipe, quest and island references remain intact. Recompression
updates the required used length; all other header bytes and every byte of the
original unused tail remain at the original absolute positions. Growth into
opaque unused bytes is rejected. Edited bytes are fully reparsed before writing.

No native writer evidence requires changing `SYDAT.BIN` for these inventory
reductions, so it is neither edited nor made an artificial opening prerequisite.
Keep it and all original companion files with the matching original slot.

## Coverage checklist and blockers

| Mechanic | Coverage / specific blocker |
| --- | --- |
| Ordinary medicines and crop seeds | Twenty named factual item IDs, existing-stack reductions only; no new ownership or zeroing. |
| Other blocks, furniture, food, dyes and materials | Searchable numeric records; require individually reviewed identities/applicability before writable quantities. |
| Player EXP/level/HP/fullness/stats | Stored-word inspection; require controlled displayed action pairs and dependency rules before writes. Published editor storage ceilings are not natural gameplay limits. |
| Equipment, tools and appearance | Equipped ID inspection; ownership/applicability and reference rules need independent proof. |
| Gratitude, residents, crops, island storage/building | Separate STGDAT structures and cross-file rules; require matched complete action pairs and integrity/layout qualification. |
| Recipes, quests/story, Explorer's Shores, Buildertopia and collections | Prerequisite/reward/ownership evidence remains missing; no completion/unlock edits. |
| Other Switch revisions, demos, PC/Game Pass/PS4 | Separate independent native qualification required; identical-looking prefixes do not widen support. |

## Tests and validation limits

`test_dqb2_switch.py` covers the separately bound scalar contract, rejection of
PC documents/backups and other game IDs, complete native framing/integrity,
surgical selected/bulk quantities, opaque header/tail and readonly record
preservation, malformed fields, backups/restore, source/alias protections and
actual Tk search/edit/Undo/Review/Save As workflows. Optional genuine files use
`DQB2_SWITCH_SAVE_COPIES` with copied files/directories separated by local
`os.pathsep`. Both distinct No Hacks slots qualify byte-exact native no-op
behavior; the slot containing eligible existing stacks also qualifies targeted
quantity edits and native Tk workflows. The other slot's empty/unsupported
inventory is preserved. An actual edited Switch game-load/re-save has not been
performed.

# Selective save-to-save transfer

Open the destination save copy in its explicit editor, choose **Editing and
Research → Transfer from Save Copy...**, then open a separate source copy.
Select individual fields in **Select values**,
choose **Preview Selected Values**, and inspect **Complete preview**. The preview
includes existing edits outside the selection. **Apply Reviewed Transfer** stages
the complete result as one Undo action; **Save As** writes a separate edited copy
through the existing backup, source-change, atomic-write and read-back workflow.
No transfer preview or Apply action writes either original save.

Search filters the list without clearing hidden selections. **Select Visible**
adds currently visible fields; **Clear Selection** removes every selection.
Changing the selection invalidates the preview. Source, destination, companion
metadata and pending edits are checked again before Apply. A failed validation or
presentation refresh retains the original pending edits and Undo history.

## Qualified routes

| Profile | Transferable values | Identity and restrictions |
| --- | --- | --- |
| DW8 XL PC | Gold, gems, facility and weapon materials | Existing reviewed resource portability policy; exact native signature/revision |
| WO3 Ultimate Definitive PC | Reviewed resource, attribute-orb and crafting-material balances | Existing reviewed resource portability policy; exact native signature/revision |
| WO3 Ultimate Definitive PC | Two persisted mount loadout references | Existing native loadout roles and mount lookup table; destination must originally own the mount with supported rank 1; Unequipped is allowed |
| Origins Steam slot saves | Gold, base-game and exposed DLC skill-point pools | Same qualified native slot revision; existing parser eligibility and native constraints |
| Pokémon Conquest US vanilla DS raw saves | Gallery IV components 1–3 and Speed IV | Same native species ID appearing exactly once within the same physical gallery bank in each save; record positions may differ |
| Dynasty Warriors: Gundam US/EU decrypted PS3 exports | Learned skills on six named qualified level-30 pilots | Explicit published named pilot records; additive learning only; same regional title profile; original PARAM.SFO required |
| Dynasty Warriors: Gundam US/EU decrypted PS3 exports | Four selected skill references on those pilots | Destination must have originally learned the skill and it must not be inherent; complete final four-slot set must be distinct |

Conquest components 1–3 retain their existing neutral numbering: their individual
HP/attack/defense correspondence is unproved. Each gallery bank is independent;
no values are copied between banks and generation counters remain untouched.
Duplicate or unknown species and missing matches are excluded. This route edits
gallery persistence, not current scenario Pokémon.

Equipment routes copy existing loadout references. They never create inventory,
change item identities, acquisition/ownership, item rank or native equipment
records. Gundam learning selected in the same transfer cannot make a newly learned
skill equippable: save and reopen the destination first, as its native editor
requires. Select every affected field for a loadout swap; a partial selection
that produces duplicate references fails before any edit is staged.

## Evidence and exclusions

Transfer uses the registered `BoundScalarAdapter`, immutable documents, existing
field readers, native serializers and decoded read-back validation. It reuses
resource policy from [reusable presets](REUSABLE_PRESETS.md) and the
source/pending/preview contracts in `shared/edit_presets.py`; it does not patch
source offsets into another save. Cross-platform routes remain in the existing
[Save Converter](SAVE_CONVERSION.md), where the complete mapping is qualified.
A matching numeric slot, byte offset, label or field ID alone never qualifies a
character or inventory record for selective transfer.

The **Exclusions** tab reports unsupported fields, ambiguous identities, missing
matches and original ownership/learning failures. Other profiles, officer slot
statistics without independent identity, physical weapon records, arbitrary
story completion, rewards, prerequisites, levels/EXP, account/signing metadata
and unknown flags remain unavailable. Native save integrity and console
reimport/resigning requirements are unchanged.

`tests/test_save_transfer.py` covers semantic record reordering, ambiguous and
missing identities, packed-bit and bank preservation, selection errors, native
revision mismatch, additive learning, equipment dependency failures, complete
loadout swaps, mount ownership/rank constraints and stale previews.
`tests/test_transfer_gui.py` exercises deliberate preview, hidden selections,
one-step Undo and rollback. These use procedural fixtures; they do not establish
new genuine-save evidence or in-game loading. Format evidence remains in
[Conquest](POKEMON_CONQUEST_DS_FORMAT.md), [WO3 depth](WARRIORS_V26_DEPTH.md) and
[console pilot mechanics](CONSOLE_PIRATE_STRATEGY_DEPTH.md).

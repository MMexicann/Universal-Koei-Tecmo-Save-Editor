# Dragon Quest Builders 2 — original Steam PC CMNDAT

This is a separate original Steam PC profile for copied `CMNDAT.BIN` files.
Dragon Quest Builders 2 was developed by Square Enix and Omega Force; the Steam
store credits KOEI TECMO GAMES CO., LTD. It is not Dragon Quest Heroes, Builders
1, the demo, Game Pass, Switch or PS4 support.

## Implemented controls

- Reduce existing pocket/bag quantities for twenty individually reviewed ordinary
  medicine and crop-seed IDs. A stack must have 2–999 opened items; edits retain
  at least one item and never exceed the opened quantity. Max is disabled.
- Search all 15 pocket and 420 bag rows by container, slot, item ID, known name,
  quantity and edit availability. Unknown IDs remain numeric and inspection only.
- Inspect separately stored level, EXP, HP/bonus, fullness, attack/defense and
  equipped weapon/hammer/shield/armor IDs. No growth or equipment edits.
- Shared Undo, Review Changes, automatic backups, validated restore and atomic
  Save As protect originals and detect changed source copies.

Keep the edited CMNDAT with all the other original files of that same save slot;
this editor does not recreate an island, change ownership, synchronize cloud
saves or transplant progress between players.

## Native framing and independent source facts

The complete writer in
[turtle-insect/DQB2](https://github.com/turtle-insect/DQB2/tree/c551524dc9179a3d614390cb5ab6f2f73300a2fc)
is GPL-3.0 and explicitly supports Switch and Steam. Its CMNDAT reader preserves
a `0x2A444`-byte header, decodes the following zlib stream, and its save path
recompresses the body and updates only the little-endian used length at `0x10`.
It does not clear integrity flags or recalculate a separate inner checksum.
This adapter independently implements those factual framing/record rules; no
GPL implementation, bulk item catalog, binary or asset is incorporated.

The inspected original Steam headers carry `aerC`, supported header words at
`0x04/0x08/0x0C`, and revision words `0x40003` or `0x40004`. Every acquired native
CMNDAT body is exactly 5,627,194 bytes. The reader requires one complete bounded
zlib stream, verifies its native Adler checksum, rejects concatenated members,
truncation, overexpansion and unexplained decoded extents, and never repairs
damaged input. A title-specific header/body geometry gate excludes island/photo
files even though those also use `aerC`.

Fifteen pocket records begin at body `0x55B28D`; 420 bag records at `0x55B2C9`.
Each record consists of little-endian 16-bit item ID and 16-bit quantity. The
bag ends immediately before separate equipped records at `0x55B959`.
Only the qualified quantity word changes. Original IDs, empty/single/unusual
records, equipped references, player growth, craft flags and all world/story
bytes are retained.

Medicine/seed names are twenty hand-written factual ID mappings checked against
the original author's release reference, not an imported enumeration. Their
quantity controls do not assume that every item with the same storage width is
an ordinary stack or that 999 is a natural cap. Crops planted in an island are
separate STGDAT records; changing an inventory seed stack does not edit a crop.

## Compact files and opaque native padding

The two freely shared
[SaveGame.Pro PC exports](https://savegame.pro/pc-dragon-quest-builders-2-savegame/)
have a physical 5,800,318-byte native capacity with a shorter used length.
One contains nonzero stale bytes in unused capacity. Two author's own
[Hermit's Heresy native examples](https://github.com/default-kramer/HermitsHeresy/tree/442da7ef0819260bf1dc6d0cc75b5f98246a2d81)
are compact files whose physical size equals used length; one is explicitly
labelled a no-cheat post-Buildnoculars save, the other an earliest gameplay save.
These genuine originals remain private and are not distributed.

Unchanged serialization returns the exact original bytes. Edited compact files
remain compact. Edited padded files keep the same physical size and every byte
of the original unused tail at its original absolute position; stale bytes are
not zeroed or normalized. Level-6 zlib compression safely fits the acquired
native files. If any edited padded body would grow into original unused bytes,
the writer rejects that edit instead of overwriting them. Edited output is
fully reparsed before writing.

## Mechanic coverage and remaining blockers

| Mechanic | Coverage / exact blocker |
| --- | --- |
| Existing ordinary medicine and crop seeds | Implemented conservative named stack reductions, keeping one and preserving opened ownership. Other item kinds need separately reviewed IDs/applicability. |
| Blocks, furniture, food, dyes and other bag items | Searchable numerical inspection; need individually reviewed identity/kind rules before writable quantities. No item creation or replacement. |
| Player level/EXP/HP/stats/fullness | Separately inspected stored words; need displayed controlled action pairs, growth/stat dependencies and legitimate limits before writes. |
| Equipment, tools and appearance | Equipped IDs are inspected; need ownership and appearance applicability/reference evidence. No ID swaps. |
| Gratitude/hearts, residents/NPCs, crops, island construction/storage | Stored in separate island/world structures or have cross-file dependencies. Need matched CMNDAT/STGDAT controlled pairs and complete record rules. |
| Recipes, Explorer's Shores, story/quests, Buildertopia and collections | Published editor leads exist, but ownership, prerequisites, rewards and cross-file rules are unqualified. No completion/unlock actions. |
| Other platforms/builds/demo | Require independent complete native fixtures and identity/layout qualification; published cross-platform claims are not imported as support. |

Hermit's Heresy notes that inconsistent CMNDAT and STGDAT can send the game back
to the title screen. This adapter therefore does not transplant files or change
island/quest state. No game or downloaded editor executable was run.

## Validation

`test_dqb2_pc.py` covers unchanged compact/padded copies, both qualified revision
words, surgical individual/bulk quantity changes, malformed headers/extents,
native checksum failures, zlib bombs, unused-tail preservation, dependency and
unusual-value guards, frozen snapshots, safe Save As, backups/restore and actual
Tk search/edit/Undo/Review workflows. Optional genuine-file checks use
`DQB2_PC_SAVE_COPIES`, containing files/directories separated by local
`os.pathsep`. Missing private files skip those cases; generated fixtures are not
genuine-game evidence. Edited game-load/re-save validation has not been performed.

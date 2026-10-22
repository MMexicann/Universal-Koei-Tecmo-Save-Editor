# Original Project Zero / Fatal Frame — European PlayStation 2

This adapter opens complete `.psu` exports of **SLES-50821**, directory
`BESLES-50821zero0`. It is separate from Fatal Frame II Remake and from the
original game's US/Japanese editions. PSV signatures and memory-card import are
handled by the player's export/import tool.

## Sources and independent implementation

- [karas84/ProjectZeroSaveEditor](https://github.com/karas84/ProjectZeroSaveEditor/tree/89116d7547ed7e5767f64d6afa9719b6ca736a42)
  is MIT-licensed **parser-only** research. Its packed European `MC_GAMEDATA`
  structure, camera labels and checksum reader establish layout facts; it is
  not an upstream save writer.
- [karas84/Himuro](https://github.com/karas84/Himuro/tree/b2359d0908c7eec576efef5af17a2004062eeb64)
  is MIT-licensed native decompilation research. `CAM_CUSTOM_WRK` independently
  corroborates camera upgrade bytes, function selections and the 64-bit point
  balance. Undecompiled game routines are not claimed as writer proof.
- [Apollo's European PS2 exports](https://github.com/bucanero/apollo-saves/tree/master/PS2/SLES50821)
  provide five distinct complete exports, with twelve occupied native slots and
  three empty slots. The additional `100` export duplicates `00000001` and was
  not counted again. Research-only conversion from PSV to PSU preserved every
  native gameplay byte, icon and icon metadata. It did not recreate a PSV
  signature or demonstrate a game import.

The implementation is original Python using these independently checked format
facts. No upstream code, game assets, export contents or player identifiers are
included in source or release assets.

## Framing and integrity

PSU file locations are calculated from directory entries and their 1,024-byte
padding, rather than from a sample's absolute offsets. Root identity, directory
entries, unique names, regular-file modes, entry counts, bounded sizes and exact
container termination are checked before exposing fields.

Each `BESLES-50821zero[0-2]` file is exactly **585,596 bytes**. For occupied
slots, the little-endian checksum at offset zero equals the sum of all bytes
from offset 16 through the end. All twelve acquired occupied slots match this
algorithm. The gameplay header additionally identifies its kind, supported
mission framing and valid minute/second/frame values. Empty slots are accepted
only as the complete observed pattern: 48 zero bytes followed by `0xff` bytes.
They remain unchanged and cannot be initialized through the editor.

Native camera state begins at `0x42e0`; the point balance is the 64-bit value
at camera offset 16. The first three bytes are existing Range, Maximum Charge
and Charge Speed upgrade tiers. A write modifies only selected scalar bytes
and the checksum of each changed occupied slot. Container metadata, padding,
other slots, photographs, inventory, unknown values and function selections
remain byte-identical. Unchanged serialization returns the original bytes.

## Mechanics coverage

| System | Implemented scope / remaining blocker |
| --- | --- |
| Camera points | Reduce a positive existing balance; preserve high opened values. No invented natural cap or Max. |
| Range, maximum charge and charge speed | Reduce existing stored tiers 1–3. Initial/unusual tiers stay read-only. Upgrade purchase/reward interactions are not granted. |
| Film stocks | Reduce existing ordinary film stocks at native IDs 1–4, retaining at least one sheet. Only opened quantities 1–99 qualify; zero and unusual quantities stay untouched. Selection, experience/acquisition flags and pickup history remain unchanged. |
| Camera sub/special functions | Searchable stored function and equipped-selector inspection. Ownership, unlock prerequisites and equip dependencies need controlled gameplay pairs before writes. |
| Healing and key items | All 200 stored inventory positions per occupied slot are searchable. Film IDs are labelled separately; other names, stack limits and critical-item dependencies need independently corroborated item mappings. |
| Story, missions and rooms | Slot mission/room/play-time inspection. No completion, difficulty or clear-reward edits. |
| Photographs, ghost album and collections | Preserved; album and reward dependencies require controlled snapshots. |
| Health and battle state | Preserved; derived/temporary versus persistent state needs further proof. |
| Empty slots and other editions | Empty slots preserved. New-game initialization and US/Japanese layouts are unsupported. |

Camera and film controls intentionally do not grant skills, complete stories or manufacture
resources. Assigning the opened value removes the staged change; Undo, Review
Changes, searchable inspectors, automatic backups and safe Save As use the shared
interface. Source copies are checked again after backup, aliases are rejected,
and restore validates the exact bounded snapshot before writing.

## Validation

Seven focused tests cover procedural reordered containers, malformed inputs,
checksums in every slot, empty-slot corruption, unusual values, forged snapshots,
surgical edits, backups/restore, aliases and a source-change race. Private native
qualification exercises the five complete exports, each available field and
copied-file self-tests. A real Tk workflow covers opening, searching, staging,
Undo, Review Changes and saving. All seven passed with the native fixtures and a
display. These are file/GUI checks; **edited game loading and memory-card reimport
have not been performed**.

## Film-stock refinement

The current primary [Himuro native decompilation](https://github.com/Mikompilation/Himuro/tree/adcc35fb4602726ca9a692f2289bec816ce112db)
supplies stronger inventory evidence than the earlier parser-only source.
[`ig_camra.c`](https://github.com/Mikompilation/Himuro/blob/adcc35fb4602726ca9a692f2289bec816ce112db/src/ingame/menu/ig_camra.c)
selects film from `poss_item[1..4]` only when nonzero and separately consults
film experience flags.
[`item_ctl.c`](https://github.com/Mikompilation/Himuro/blob/adcc35fb4602726ca9a692f2289bec816ce112db/src/ingame/map/item_ctl.c)
adds twelve sheets to these pickup quantities and clamps them to 99.
These are native scalar stock values, rather than acquisition flags. The
existing packed save map places `poss_item[200]` at `0x197c`.

The independently implemented controls reduce each opened qualified stock to
1–its opened quantity, with bulk Max disabled. Keeping one sheet avoids changing
the existing film selection or acquisition/experience relationship. No ordinary
film type name is assigned without independent name-to-ID evidence. The
MIT-licensed Himuro source binds `poss_item[1]` through `poss_item[4]` to the
named `film14`, `film37`, `film74` and `film90` debug values in
[`g2d_debug.c`](https://github.com/Mikompilation/Himuro/blob/adcc35fb4602726ca9a692f2289bec816ce112db/src/graphics/graph2d/g2d_debug.c#L457-L460).
The inspector and reduction-field labels now use those four title names while
keeping the same qualified slots, bounds and one-sheet minimum. Editable labels
retain the `film stock` search term alongside each verified film type. Other items,
story and rewards remain untouched.

Five distinct complete native PSU exports qualify twelve occupied slots and
45 positive film stocks. Focused validation exercises each new native field,
surgical preservation, checksum read-back, full copied-file backup/restore and
the existing real Tk workflow. Procedural checks separately cover zero and
unusual stock exclusion, minimum-one enforcement, bounds, unstage and immutable
selection/other-item records. Edited game loading remains unperformed.

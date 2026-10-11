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
| Camera sub/special functions | Searchable stored function and equipped-selector inspection. Ownership, unlock prerequisites and equip dependencies need controlled gameplay pairs before writes. |
| Film, healing and key items | All 200 stored inventory positions per occupied slot are searchable. Names, stack limits and critical-item dependencies need independently corroborated item mappings. |
| Story, missions and rooms | Slot mission/room/play-time inspection. No completion, difficulty or clear-reward edits. |
| Photographs, ghost album and collections | Preserved; album and reward dependencies require controlled snapshots. |
| Health and battle state | Preserved; derived/temporary versus persistent state needs further proof. |
| Empty slots and other editions | Empty slots preserved. New-game initialization and US/Japanese layouts are unsupported. |

Camera controls intentionally do not grant skills, complete stories or manufacture
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

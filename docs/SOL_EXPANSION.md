# Development expansion — 2026-10-13

This update adds **14 game/platform profiles**, bringing the development source
to **90 profiles across 15 platforms**. Macintosh and SNES are new platforms.
The application version remains 1.91 and its released Windows downloads retain
their earlier 76-profile scope. This development update publishes no release.

## Added profiles

| Game / profile | Platform | Implemented controls |
| --- | --- | --- |
| [Bandit Kings of Ancient China](BANDIT_KINGS_MAC_FORMAT.md) | Macintosh | Owned prefecture resource and existing hero ability reductions. |
| [Nobunaga’s Ambition](NOBUNAGA_AMBITION_NES_FORMAT.md) | NES | Owned active fief Gold/Rice reductions; native checksum. |
| [Gemfire](GEMFIRE_BATTERY_FORMAT.md) | NES | Player-owned province Gold/Food/Loyalty/Farming/Protection. |
| [Gemfire](GEMFIRE_BATTERY_FORMAT.md) | SNES | Same controls with separate native pointers and global offsets. |
| [Bladestorm: The Hundred Years’ War](BLADESTORM_PS3_FORMAT.md) | EU PS3 | Money and existing positive book SP reductions. |
| [Atelier Firis](FIRIS_PC_FORMAT.md) | Original Steam PC | Cole and qualified existing ordinary item quality reductions. |
| [Blue Reflection: Second Light](BRSL_PC_FORMAT.md) | Original Steam PC | Existing uniquely identified ordinary container quantity reductions. |
| [Atelier Ryza](RYZA_PC_FORMAT.md) | Original Steam PC | Qualified existing ordinary item/equipment quality reductions. |
| [DW8 Xtreme Legends Complete Edition](DW8XL_VITA_FORMAT.md) | Vita plaintext | Resources, officer stats, aptitudes and existing attribute ranks. |
| [One Piece: Pirate Warriors](PIRATE_WARRIORS_PS3_FORMAT.md) | US PS3 PSN | Thirteen named existing level-growth word reductions. |
| [One Piece: Pirate Warriors 2](PIRATE_WARRIORS_PS3_FORMAT.md) | EU PS3 PSN | Primary spendable Berry reductions; secondary word preserved. |
| [One Piece: Pirate Warriors 3](PW3_PS3_FORMAT.md) | EU PS3 PSN | Existing progressed-character HP/Attack/Defense reductions. |
| [Dynasty Warriors 8](DW8_PS3_FORMAT.md) | Original US PS3 PSN | Gold and two Ambition material reductions. |
| [Attack on Titan / A.O.T. Wings of Freedom](AOT1_VITA_FORMAT.md) | EU Vita | Money and existing positive numbered material quantity reductions. |

These are profile additions; some titles already have another platform editor.
Each registration describes its exact accepted edition, format and controls.
Manual reductions without a proven natural cap do not gain a bulk Max action.

## Existing-editor refinements

- Record selection, pending-only filtering, visible/hidden pending counts and
  searches that include pending values make large existing editors easier to use.
- Field-table scroll, focus and sort order survive refreshes.
- Original unusual enum values can be restored after a supported edit without
  transferring one record’s unusual identity to another record.
- Max Selected/Visible now restores and unstages a lowered field whose opened
  value was already its natural maximum.
- Unstaging one field validates the final pending payload so equipped loadouts
  cannot acquire duplicate references.
- Staging verifies that the backend retained the requested typed value. Max and
  Review errors preserve the session and are shown through the shared error UI.
- Independent review corrected Gemfire SNES ownership/calendar offsets and
  incidental interior `KOEI` bytes. Nobunaga’s native rebel owner 51 remains
  accepted and read-only.

All scalar registrations use `BoundScalarAdapter`: complete pending validation,
unchanged byte-exact roundtrip, edited serialization decode, requested-value
checks, and reopening of the actual destination before accepting a saved copy.
New profiles also check changed sources, preserve original snapshots, create
backups and write atomically to new destinations.

## Evidence and remaining candidates

The format documents distinguish procedural fixtures, public source references,
native file qualification and edited in-game loading. No game binary was run
and no edited save was loaded/re-saved inside a game in this session. PS3/Vita
profiles classified as external integrity use published save-writer facts and
preserve original metadata; they require an external import/resign workflow.
They do not claim proof of every possible internal checksum or corruption.

Gemfire/Nobunaga are complete native writer/decompilation implementations with
procedural fixtures; occupied independent native campaign copies remain needed.
Bandit Kings and DW8 references are publicly modified exports/scenarios, not
controlled natural-gameplay pairs. Gust’s precisely matched terminal profiles
stay opaque and retain mandatory native envelope checks; arbitrary truncation
or invented padding is not accepted. AOT’s upstream recipe filename and byte
order discrepancies are documented separately from corroborated field facts.

The twenty-profile goal was not reached in this pass. Fresh research included
original Lydie & Suelle, fifteen Shallie DX gameplay snapshots, original Ryza 3,
DW8 Switch/PS4, DW7 XL PS3, Gundam 2, Dragon Quest Heroes PS3, original Bladestorm
Xbox 360, classic NES strategy titles, Nintendo Monster Rancher and Tecmo sports
variants, Toukiden/Toukiden 2/WO3 Ultimate Vita and Arland/Dusk console editions.
Toukiden's public Vita archive is an encrypted CMA container; Toukiden 2 and
WO3 Ultimate have exports but no qualified Vita save writer or field map.
Current DOA5 Plus save patches are crypto stubs with no gameplay edits.
Missing native archives, incomplete serializers, unresolved active
integrity or unmapped gameplay fields kept those candidates outside the library.
The linked research documents record actionable remaining inputs.

## Verification

Focused public, native-reference and actual Tk workflows passed during each
implementation lane. Independent reviews covered the retro ownership/checksum
logic, Gust terminal preservation, Vita DW8 layout and console companion races.
Actual Tk startup initialized all 90 interfaces, theme changes and switching.
Inventory and package-source validation passed with 902 explicitly reviewed
public source files. Native reference tests remain private and optional in CI.

The complete test inventory runs in four isolated shards with independently
coordinated displays. Native Windows tests, EXE building and package scans are
visible in [the repository workflow](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/actions/workflows/windows-release.yml).
Ordinary development pull requests run those checks without publishing a release.

# Atelier Ryza 3 DX — Steam PC

The adapter for **Atelier Ryza 3 DX: Alchemist of the End & the Secret Key**
reduces the opened unspent skill-tree SP and gem balances for rebuilding/duplication. Both fields
use the standard staged editing, Undo, Review Changes, copied-save protection,
backup, restore and atomic Save As workflow. Three searchable inspection tables
show native inventory/key record words, Party record identities and save-backed
sections. Unproved fields remain read only. This profile is separate from original
Ryza 3, earlier trilogy titles, console exports and system saves.

## Native fixture and independent loading evidence

A freely shared gameplay file is linked in
[DXVK issue 5753](https://github.com/doitsujin/dxvk/issues/5753). Although the issue
uses the shortened game title, its author explicitly identifies the **Atelier
Ryza 3 DX** save directory and provides an in-game fast-travel reproduction
through Ashra-am Baird Outskirts and Forgotten Village. A DXVK developer thanks
the author for providing the save and reports testing the reproduction on the
595 NVIDIA driver, NVK and RADV. This is independent evidence of the original
shared native save loading in the DX game. It does **not** establish that our
edited output has been loaded or re-saved in the game. No game or editor binary
was executed during this investigation. Player files and their owner paths stay
outside the repository and release assets.

The gameplay container is 720,176 bytes, with a 2,480,654-byte decoded payload.
The companion system container is not a gameplay fixture. Native XOR and
additive checks pass, and unchanged codec reconstruction is byte exact. The
adapter reuses the existing MIT-attributed
[Sophie 2 Gust envelope codec](../src/koei_editor/games/sophie2/atelier_sophie2_codec.py),
under the [existing notice](../licenses/atelier-sophie2-save-editor-MIT.txt).
No external gameplay implementation or item catalog was copied.

The native DX layout differs from the qualified original Ryza 1/2 profiles:

- Header revision is little-endian 4; header words at 40/44 are 1/1.
- The decoded preamble is little-endian **20150730**, followed by 28 zero bytes.
  This is a native serialization discriminator, not a marketing patch number.
- The unique `info.app_ver` body is little-endian 1/1.
- Forty-one preceding roots must be complete and match the qualified tag order
  and exact sizes. Title markers include `SecretKey`, `AtelierMaking`, `itemquiz`
  and the native secret-base/Rasen map schema.
- Inventory version is LE16(2); limits are LE32(700), LE32(15000). Five inventory
  arrays have LE32 byte-count prefixes and observed 128-byte record grouping,
  with counts 700, 250, 15000, 250 and 50. These are layout capacities, not
  editable stack counts or natural resource maxima.
- Party version is LE16(1), followed by 14 framed 1,600-byte `Party` records and
  complete trailing nodes. Nonstandard native identities stay intact; 14 slots
  are not a claim that the base game has 14 playable characters.
- `AlchemyTree.version` is LE32(2), LE16(0). The separate `skill_state` has a
  LE32(758) prefix and 758 bytes; none of those learned-state bytes are written.
- Secret-key version is LE16(1), with two independently bounded 1,280-byte pools.
  Their observed record grouping is exposed as raw words, without invented key
  IDs, rarity, effects, use counts or ownership controls.

## Exact terminal omission

The independently loaded file has an unusual **eight-byte terminal omission**.
At decoded offset 2,479,832, `order_switch` declares 830 bytes while only 822
remain. Its `version` node is exactly 14 bytes with LE16(1). Its final
`order_data` node declares 799 bytes, with a LE32(780) byte-count prefix; the
last eight declared array bytes are absent.

Only this exact tag/location/version/length geometry is admitted, after all 41
preceding roots have validated completely and the native envelope checks have
passed. The 822 available terminal bytes are retained as an opaque block.
Nothing pads, repairs, reconstructs or edits the missing bytes. A different
shortfall, altered tail header, later node, damaged preceding framing, wrong
profile or failed integrity check rejects before fields are exposed. Writes
occur in earlier complete roots and preserve this ending byte for byte.

This evidence does not qualify the much larger omission in original Ryza 1 PC,
Blue Reflection: Second Light's different terminal profile, or any original
Ryza 3 layout. Each requires its own native evidence.

## Writable balances and dependencies

The two controls independently qualify their unique explicit scalar tags:

| Field | Native serialization | Allowed action |
| --- | --- | --- |
| Unspent skill-tree SP | `AlchemyTree.skill_point`: LE32(4), nonnegative signed LE32 balance | Reduce to 0..opened balance; preserve learned states and selected node. |
| Gems | `item.mix_gem`: LE32(4), nonnegative signed LE32 balance | Reduce to 0..opened balance; preserve items, recipes, unlocks and reduction history. |

Only the second four-byte word changes. Unknown prefixes or negative original
values grant no control and remain unchanged. There is no guessed natural cap,
no increase, no Max, no ownership creation and no prerequisite/reward write.
Higher existing balances remain reversible by assigning their opened values.
The public reference contains very high SP; that value is not used as a claimed
natural gameplay maximum.

The [official Ryza 3 skill-tree manual](https://www.koeitecmoamerica.com/manual/71cYx2DZ/en/7300.html)
explains SP acquisition through synthesis/rebuilding, events, reference books and
quest rewards; skills require adjacent nodes and some conditions. Deducting SP
does not learn a skill or raise a quality cap. The
[duplication manual](https://www.koeitecmoamerica.com/manual/71cYx2DZ/en/5500.html)
and [rebuilding manual](https://www.koeitecmoamerica.com/manual/71cYx2DZ/en/5600.html)
distinguish gems earned from item reduction and gems spent on separately
unlocked duplication/rebuilding. A balance edit does not grant those abilities.
These mechanics sources establish those concepts; the DX fixture independently
qualifies its different native serialization.

## Mechanics coverage checklist

| System | Implemented or precise blocker |
| --- | --- |
| Unspent SP | Native LE32 deductions; learned nodes, selection and rewards preserved. Increases require displayed earn/spend pairs and balance bounds. |
| Gems | Native LE32 deductions; separate items/unlocks/history preserved. Increases require displayed reduction/duplication pairs and limits. |
| Cole | `money.money` has three words, not an unambiguous single scalar. Wallet/history/preview roles need controlled purchase/reward pairs before writes. |
| Inventory and key records | Searchable observed record grouping and raw words. Item/key identity, names and category mappings need an independently verified title-specific catalog and transfer/use pairs. |
| Item quality | Words at +6/+8 look related and are equal on sampled records. Their respective meaning/dependency is unproved. Need displayed controlled synthesis/rebuild pairs or title-specific native writer evidence; earlier-title quality offsets are not transplanted. |
| Quantity, uses, CC | Native counts versus record occupancy and stack/use/charge roles need controlled action pairs. The array capacity is not a quantity control. |
| Traits, super traits, effects and elements | The [synthesis manual](https://www.koeitecmoamerica.com/manual/71cYx2DZ/en/5100.html) describes distinct loops, unlocked trait/super-trait slots, elements and quality locks. Native slot/ID/level/effect mappings and applicability remain missing. |
| Quality caps and recipes | “Max Quality” and recipe unlocks have skill/loop dependencies. Exact `skill_state` node meanings and unlock pairs are missing; no bulk unlocks. |
| Item duplication/rebuilding | Depend on learned skills, recipes, item identity and rebuild limits. Native action pairs and dependency mappings needed; resource deductions do not enable either system. |
| Party, stats and EXP | Framed records inspected read only. Need title-specific character identity/name mappings, stored-versus-derived stat roles, EXP thresholds and equipment/level action pairs. |
| Equipment and tools | No equip replacement or ID swaps. Gathering/adventure tool applicability and native equip references need controlled equip/use pairs. |
| Secret keys | The [key manual](https://www.koeitecmoamerica.com/manual/71cYx2DZ/en/7700.html) distinguishes ten attached keys, four rarities, motif, uses, elements and four effect types. Exact pool/attachment/ownership/effect/use fields remain missing. |
| Order Drives | Level/Action Order dependencies are described in the [party manual](https://www.koeitecmoamerica.com/manual/71cYx2DZ/en/7500.html). The terminal native block is opaque and never editable; no reconstruction. |
| Exploration, maps, secret bases and feeding | Native roots exist; exact progression, facility, reward and tool/key dependencies need controlled pairs. Tags alone are not a completion mapping. |
| Quests, achievements and collections | Need native prerequisite/completion/reward-claim pairs; kept separate from resource deductions. |
| Friendship and customization | Native roots retained; stored meanings, options and legitimate unlock prerequisites not qualified. |
| Story, calendar, events, movies/music and DLC | No story completion, rewind or DLC entitlement controls. Different layouts/revisions need separately qualified genuine files. |

## Validation

[The focused tests](../tests/test_ryza3_dx_pc.py) distinguish non-playable procedural
buffers from the optional native fixture selected with `RYZA3_DX_PC_SAVE_COPY`.
They exercise native integrity, identity/revision rejection, exact tail handling,
unknown scalar profiles, surgical all-field edits, immutable snapshots, bounds,
Max exclusion, unstage, read-only inspection, changed-source protection,
backups/restores and safe new destinations. With a graphical display, the
actual Tk session checks open, searchable inspection, field filtering, apply,
Undo, Review Changes, themes, Save As and restore, using the native copy when
selected. Edited-save game loading/re-saving has not been performed. One native
DX gameplay layout does not qualify every later revision or DLC variation.

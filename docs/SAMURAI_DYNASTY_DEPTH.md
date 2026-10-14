# Existing Samurai / classic Dynasty editor depth

This development-source follow-up reviews SW4-II first, then original SW2,
SW4 DX, DW4 Hyper, USA PS2 DW4 XL, Windows DW5 Special and original Windows
DW6. It adds independent stored fields and existing equipment choices to six
adapters. The reviewed SW4 DX progression and mount systems still need specific
dependency evidence; its current functional editor remains available.

## Added controls and their proof

| Exact adapter | New control and serialized fact | Qualification and dependencies |
| --- | --- | --- |
| SW4-II PC, revision `0x31A4` | Officer equipped mount byte `0x1052 + officer*0x8C + 0x3D` | Initialized standard officers 0–55; targets are existing known occupied mount records in the opened 20-record pool `0xCA42`, stride `0x10`. Known types 0–12, positive combat stats and `1 <= level <= ceiling <= 50` qualify targets. Empty type 26 and unknown/DLC types cannot become targets. The reference changes alone; acquisition, rank, EXP, abilities, growth and stats remain separate. |
| Original SW2 Windows PC, revision 2 | Officer equipped weapon byte `0xC + officer*0xEC + 0xC0` | Already owned officers only. The target must be a known weapon in that officer's existing eight-record pool, `+0x28`, stride 19, own-family ID below 104 and occupied bonus count 1–8. Empty ID 127, foreign families, unknown/count-zero records and unowned officers are excluded. No identity, bonus, element, ownership or rare-weapon acquisition changes. |
| DW5 Special native Windows | Officer stored Attack/Defense bytes `0xEC + officer*88 + 6/+7` | Already playable records, original byte `+0 == 1`, only. These are stored base values rather than derived battle totals; equipment, Life/Musou, merit, title, unlocks and rewards are preserved. Individual 0–255 byte bounds; no natural stat cap or Max is claimed. |
| DW6 original Windows | Existing weapon stored damage-bonus u32 `2904 + officer*168 + 8 + slot*16 + 4` | Original known weapon ID and known element 0–3 qualify the existing record. Empty ID 174, unknown IDs and unusual elements remain opaque. Bonus is separate from weapon base/total attack. Individual unsigned 32-bit storage bounds only; the source's tentative value 32 and UI display ceiling are not natural Max values. Identity, element, skill mask and progression stay unchanged. |
| DW4 Hyper Windows PC | Existing occupied general item positions, officer `0xB8 + officer*24 + 0xA..0xF` | Replace or unequip an originally occupied known-owned general slot. General IDs are 0–12 and 24–31; empty is 32. Empty/unknown/unowned original slots are excluded. A target must already be owned in the opened snapshot and remain owned after the batch; pending grants cannot create eligibility. Duplicate general items reject. Officer weapon EXP must remain unchanged in the same batch. |
| DW4 XL PS2 USA `SLUS-20812`, PSU | Existing occupied general item positions at the same inner officer-relative offsets | XL-specific general IDs 0–12 and 24–40; empty is 41. The same original-occupancy, original-ownership, duplicate and unchanged-weapon-EXP rules apply. Inner offsets are resolved from the exact `BASLUS-20812` container entry; icons, metadata, other entries and padding stay byte-identical. |

All new controls are excluded from Max. A mount/weapon/item choice has no ordered
maximum; a numeric storage ceiling is not a natural gameplay cap. Original
unusual equipment references can be restored through unstaging. Fields and
targets are selected from the immutable opened snapshot; staging never creates
new writable records. Final batches are validated before serialization and
before a new staged edit or Undo assignment is accepted.

The general-item feature deliberately uses occupied positions as its boundary:
it can change what a position already holds, or clear it. It cannot fill an
originally empty position. The published sources establish that usable general
position count depends on weapon progression but do not establish the exact
threshold table. Keeping weapon EXP unchanged prevents a simultaneous edit from
invalidating that boundary. This feature does not claim the missing capacity
formula or automatically repair previously modified equipment.

The independent native inputs contain 56 new SW4-II mount references, 26 SW2
weapon references, 96 DW5 Special base stats, 202 DW6 bonuses, 192 Hyper general
slots and 189 XL general slots: **761 new writable fields in those particular
opened states**. Counts vary with original occupancy and qualification. In the
SW4-II native copy, equipped reference 0 points to inventory slot 0 whose type
is 12, while other inventory types occupy different positions; the reference
is not interpreted as a mount-type replacement.

## Public evidence and licence boundaries

- [SW4-II PC memory schema, pinned revision](https://github.com/Hexorg/CheatEngineTables/blob/0e7092b235f62ee5af4d3942c4323eb6c414f9c6/tables/shinkansen_samurai_warriors_4-ii_v1003_583.ct)
  identifies the officer `Mount` byte at `+0x3D` separately from weapon reference
  `+0x3B`, mount type and combat records. It is factual static research; no cheat
  script was executed or imported, and trainer targets are not caps.
  [Native-editor research](https://game.ali213.net/forum.php?mod=viewthread&tid=5953892)
  and the [official PC manual](https://cdn.steamstatic.com/steam/apps/348470/manuals/steam-sw4-2-mnl%28EN%29.pdf)
  distinguish equipment selection, acquisition and growth. The independently
  obtained [public PC native save](https://savegame.pro/pc-samurai-warriors-4-ii-savegame/)
  corroborates the serialized reference and occupied inventory. Native checksum
  and pool facts are documented in [SW4II_FORMAT.md](SW4II_FORMAT.md).
- [Van's original-PC SW2 editor description](https://dl.3dmgame.com/patch/14394.html)
  and its previously inspected disk accessors establish `+0xC0`, eight weapon
  slots, own-family IDs and the byte-level encoding. Its redistribution
  restrictions are respected: no reference executable, implementation, resources
  or catalogs are copied. Independent genuine inputs from
  [Speedrun](https://www.speedrun.com/sw2/resources/u6qw3) and
  [SaveGame.Pro](https://savegame.pro/pc-samurai-warriors-2-savegame/)
  corroborate the existing pool. See [SW2_PC_FORMAT.md](SW2_PC_FORMAT.md).
- [The contemporary DW5 Special PC save guide](https://game.ali213.net/thread-1001825-1-1.html)
  explicitly maps Zhao Yun's Attack at `0xF2`, Defense at `0xF3`, base `0xEC`,
  stride 88, separately from merit/title and equipment. The independently shared
  [Special CG save](https://dl.3dmgame.com/patch/2672.html) corroborates all 48
  records. It is premodified; its boosted values do not prove natural ceilings.
  The earlier statically inspected period editor corroborates native integrity;
  no editor/game binary was executed or bundled. See [DW5_SPECIAL.md](DW5_SPECIAL.md).
- [cnopt's DW6 research, pinned revision](https://github.com/cnopt/dynastywarriors6-reverse-engineering/tree/f2152f67b031091a0268154203d25fa9f65d2664)
  independently distinguishes weapon identity, bonus, element and mask; the
  Weapons / Damage section demonstrates changing the bonus while retaining
  identity and explains its addition to weapon base damage. The independent
  [native PC save](https://savegame.pro/pc-dynasty-warriors-6-savegame/)
  corroborates existing records. The project has no explicit licence: factual
  offsets and behavior are used in an original implementation, with no source,
  binaries, screenshots or assets incorporated. See [DW6_RESEARCH.md](DW6_RESEARCH.md).
- [DW4 Hyper format, pinned revision](https://github.com/talkative-platano/dw4hyper-save-editor/tree/3638c8dc23d2607b862a1105bfc9806e69d9e871)
  and [DW4 XL format, pinned revision](https://github.com/talkative-platano/dw4xl-save-editor/tree/b3ea895c6e854accd6860fd51ce69aeb024f53e9)
  identify the equipped item bytes, category, empty sentinels and dependence on
  weapon EXP. Independently obtained genuine Hyper and USA PS2 XL exports
  corroborate the occupied positions; source observations are implemented
  independently, without external source/UI code. Their existing qualification
  and integrity rules remain in [DW4_PLATFORM_FORMATS.md](DW4_PLATFORM_FORMATS.md).

## Reviewed mechanics and exact remaining inputs

| Adapter / system | Reviewed status and exact remaining evidence |
| --- | --- |
| SW4-II character EXP, level, move/Musou growth; proficiency | Existing EXP/level inspection retained. Threshold and growth/move/Musou unlock routines or asset tables plus controlled level-up copies are missing. A distinct DX-style saved proficiency system is not assumed for II. |
| SW4-II personal grid, acquired nodes and equipped skill tiers | The PC schema contains seven skill bit spans, eight equipped skill bytes and eight tier bytes. It does not identify the owned-node dictionary, prerequisite edges, tier encoding or valid capacity. Need a purchase/equip pair with unchanged control and native lookup rules. Blanket all-bits writes would grant unproved skills. |
| SW4-II weapon rank/level/EXP/attack, attributes, fusion | Existing attribute magnitudes and own-pool selection remain available. Need generation/fusion thresholds, attack-growth dependencies, valid attribute replacement/duplicate/exclusion rules and template dictionaries before upgrading, replacing identities or creating records. |
| SW4-II mounts, abilities, growth and equipment | Existing known mount selection and stats added. Unknown/DLC types, abilities, rank/EXP/growth ceilings require native enums, entitlement/slot rules and acquisition/growth/equip pairs; no ownership or ability grants. |
| SW4-II currency/tomes, resources, custom characters, collections/story/Survival | Current resources remain independent; natural held-resource caps require add/spend routines or controlled cap pairs. Appearance/name/occupancy dictionaries, collection flags and story/clear/reward/interim dependencies remain missing. No relationship/exploration mechanic is inferred from another game. |
| SW4 DX level/EXP, four attack-move proficiency tracks | Current revision `0x39EA` native executable was statically decoded again without execution. Stored stat getters at `0x14018BE40`, `0x14018BED0`, `0x14018BF60` read base values separately from skill modifiers through runtime asset pointers. Native cap facts do not supply the external EXP-to-proficiency-level table or derived growth/reward rules. Need matching parameter assets or controlled single-track proficiency and level-up pairs. |
| SW4 DX mounts, personal abilities, weapons and Chronicle | `0x140067CA5` reads officer `+0x3D` into the runtime mount reference, separately from the own-pool weapon copy at `0x140067C6D`. This does not identify DX mount ownership/type domains. Existing gold/gems, base stats, qualified character unlocks, own-pool weapons and attached skill ranks/activation remain functional. Mount ownership/equip pairs and asset enums; weapon-generation exclusions/templates; personal-ability rules; Chronicle node/goal/friendship/biography/prerequisite dictionaries are still needed. No new speculative DX writer is added. |
| Original SW2 skills, guards, mounts, weapon elements, progression | Ordinary acquired skills and weapon bonuses remain available; own-pool equipment added. Rare skills need shop/Survival reward/prerequisite proof; guards need hired-ownership/equip evidence distinct from catalog growth; mounts need purchase/replace/equip records; element byte needs the original-PC enum; level/EXP and clear flags need threshold/reward/action pairs. |
| DW4 Hyper / USA PS2 XL equipment and other mechanics | Occupied general positions added without capacity expansion. Need weapon-level capacity thresholds or controlled progression/equip copies to fill empty positions. Existing officer/item/weapon/bodyguard points stay separate from story. Hyper custom creation/model/moveset, challenge-ranking sorted updates, live suspended-battle changes and XL custom/Legend/reward fields need their native transitions; source guesses about live flags are not promoted. |
| DW5 Special officer progression, equipment, bodyguards, Shura | Attack/Defense storage is now independent manual editing. Life/Musou width/cap/derived behavior, merit/title thresholds, selected equipment prerequisites, bodyguard talent/growth/skills, regional names, Shura activation/resources/companions and story/rare-item rewards still need native routines/assets or controlled original-Windows pairs. A modified genuine file alone proves neither natural caps nor legitimate acquisitions. |
| DW6 weapon/horse skills, progression, resources and story | Bonus editing does not create a natural maximum. Version 2.4 adds separately qualified equipment-bit controls, five-weapon/four-horse capacity enforcement and existing own-inventory equipped-weapon choices; see [DW6 equipment proof](DW6_PS3_FORMAT.md#v24-equipment-qualification). Officer skill nodes/level/reward rules, outfit/title eligibility, horse growth/descriptors/transformation and stage/gallery dependencies remain unresolved. No currency/bond/bodyguard/fusion system is invented where this DW6 format has not established one. |

## Validation

[test_samurai_dynasty_depth.py](../tests/test_samurai_dynasty_depth.py) covers all
new groups with generated bytes: unchanged roundtrip, surgical payload diffs,
native integrity/container preservation, bounds, invalid pending batches,
unknown/empty/foreign targets, original-reference unstaging, ownership and
duplicate dependencies, manual-only Max, copied saving, original backup and
validated restore. The GUI case opens each of six real Tk editor classes and
exercises Apply, Review, Undo, Save As and original backup/restore.

The opt-in native matrix uses `SW4II_SAVE_COPY`, `SW2_PC_SAVE_COPY`,
`DW5_SPECIAL_COPY`, `DW6_SAVE`, `DW4HYPER_SAVE_COPY` and `DW4XL_PSU_COPY`.
Each new field in the six independently obtained native copies is edited
individually, reparsed and compared against its field span plus required native
integrity words; original sources remain unchanged. Missing native inputs skip
that native case, and a missing Tk display skips only the GUI workflow. The
existing focused format/contract/review/GUI suites are also rerun.

The final focused run with all six native bindings and Xvfb passed **175 tests
across 18 modules, with no skips or failures**, including the unchanged SW4 DX
regressions and the new nine-test depth suite. The native expansion matrix
individually checked the 761 newly qualified fields listed above. A separate
procedural/Tk run of the new suite passed eight cases and skipped only its
unsupplied private-native case. These counts describe this particular run and
do not imply broader build/region qualification.

These checks establish serialized behavior and editor safety. **Edited in-game
loading and re-save have not been performed** for the additions; neither
generated fixtures, successful native serialization nor Tk saving establishes
that separate result. No player saves, private URLs/paths, personal names, game
binaries or external implementation code are distributed.

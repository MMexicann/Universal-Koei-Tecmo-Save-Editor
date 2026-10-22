# Existing Orochi and modern Dynasty editor depth

Review date: 2026-10-11. This pass extends qualified existing PC editors. It does
not add a platform, bypass integrity, or claim an edited save was loaded in a
game. Research used static executable/period-tool inspection, native save copies
and current public mechanics references. Supplied binaries were never executed.
Private saves, disassembly, downloaded sources, player names and account context
remain outside the checkout and release assets.

The implementations keep edits separate from immutable opened bytes. New
equipment, appearance and seal-learning choices are excluded from Max. The
shared Undo, Review Changes, backups, restore and new-destination saving remain
in use. Unknown records, unsupported IDs, dormant references and higher original
values are preserved. A missing controlled action pair does not prevent an
independently proved edit that leaves its dependencies intact.

## Warriors Orochi 3 Ultimate Definitive Edition PC

The existing adapter already edits resources and qualified weapon capacity,
reinforcement and existing attribute ranks. Version 2.6 also offers a deliberate
compatibility reset to zero, a separate 64-record item inventory and pending-aware
item choices. [Current qualification](WARRIORS_V26_DEPTH.md).
The following systems now include the v2.5.3 mount refinement:

| New control | Qualification and bounds | Independent evidence |
| --- | --- | --- |
| Unallocated upgrade stones | Playable officer with original promotion count 1..9 and original balance 0..891; manual 0..891 | Native serializer `0x140258CA0` maps the word at officer `+52`; level gains add to that word after promotion, while allocation subtracts spending and clamps the remaining balance to 891 |
| Equipped items | Active original slots only, count 2..6; choices are originally owned non-mount items with positive original rank, or Unequipped | Native ownership menu, positive-rank getter, six-reference duplicate guard and selected-slot assignment; the packed serializer maps six bytes at officer `+38` and count at `+44` |
| Owned mount loadouts | Two stored selector bytes at `0xE943` and `0xE0DF`; original owned binary mount items 28..31 with rank exactly 1, or Unequipped | Native system-copy bridge, explicit packed selector serialization and mount menu lookup/set/clear paths prove ordinals 0..3 and empty 255 |

Officer records start at file `0xECF2`, stride `0x2B0`. The 145 playable records
are distinct from five internal records. Ownership is the 64-bit mask at
`0xD9AC`; 64 rank words start at `0xD9B4`. Native `0x14025C048` requires an item
ID below 64 and a positive rank. The item menu at `0x1403248B2` checks ownership;
`0x1403248C8`–`0x1403248DD` separates mount IDs 28..31 into their own tab.
`0x1403253FE`–`0x1403254C6` rejects duplicate six-slot references before writing
the selected byte. Numeric item labels avoid importing an unverified name table.

Equipment qualification requires all active references to be supported, owned
and unique, and all dormant slots to be empty (`255`). The serializer checks the
complete staged equipment batch. Clearing an occupied slot and then transferring
its item to another slot is accepted; unstage operations that would recreate a
duplicate are rejected. Direct serialized batches cannot bypass these guards.

The native allocation UI around `0x1403624E0`, `0x140362EAC`–`0x14036309B` and
promoted level-gain path around `0x14025B240` establish 891 as the unallocated
balance cap. Editing this separate balance preserves promotion, EXP, base stats,
allocation totals and slot count. Original balances above 891 stay opaque;
the supplied native sample has 19 balances of 999, which are preserved. It
qualifies 126 upgrade balances and 812 active equipment selectors.

For mounts, native `0x140248C60` / `0x140248D70` copy the current and serialized
system objects in opposite directions. Following that bridge resolves the
menu's runtime members to the two file offsets above. Serializer
`0x14025D060` visits both bytes, while setter `0x1403252E0` uses table
`0x140A7F020`: item IDs 28, 29, 30 and 31 become stored ordinals 0, 1, 2 and 3.
The remaining thirteen table entries are unmapped. The native clear path writes
255. Choices come only from original ownership and original rank-one records;
unknown/unowned/unusually ranked originals keep that loadout read only.
Both loadouts may use the same owned mount. No mount is acquired, upgraded or
renamed, and the numbered labels do not infer which mode/team uses a loadout.
Stored battle objects and ordinary equipped items are preserved; changing a
persistent loadout does not rewrite a mounted actor in a battle snapshot.

Both genuine PC references qualify two selectors and four owned mounts. Twenty
copied-native exports checked every choice/empty assignment against literal
one-byte expectations, actual destination read-back and original preservation.
Two native GUI workflows checked Review, Undo, Max exclusion, backups, Save As
and restore. The six focused WO3 modules passed 46 tests without skips. Loading
or resuming an edited save in-game remains untested. Experimental mode now also
preserves the existing reinforcement decrease-only bound and leaves unusual
original reinforcement bytes above 99 read only.

| Reviewed mechanic | Remaining dependency or evidence required |
| --- | --- |
| Level / EXP / promotion | Runtime EXP thresholds are reached through root `+0x1DA240` (`0x14025B870`); promotion and level transitions also affect growth, rewards, EXP resets, stones and item slots. The complete matching initialization/growth data and transition proof remain missing |
| Allocated stats | A separate allocation balance is proved; individual allocated-stat writes still need complete base-growth and recalculation dependencies |
| Weapon reinforcement / compatibility | Existing bounded fields remain; descriptor-grade-specific attack calculation uses native `0x14025B9A0`, but the complete matching descriptor-grade map needed for broader reinforcement caps is unavailable |
| Fusion / crafting / ownership | Independent existing ranks and resources remain; fusion material costs, consumption, acquisition and special-weapon descriptors are not replaced by invented combinations |
| Bonds / team effects | The complete persistent relationship map, thresholds and reward interactions remain unproved |
| Item ranks / mount ownership | Original ownership/ranks qualify ordinary-item and mount-loadout choices. Acquisition, rank changes and complete mount naming/mode association still need native rules |
| Story, Hundun and content unlocks | Clear flags, prerequisite routes and unlock rewards remain separate; no blanket unlock writes |

Sources: [PC achievement/mechanics guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2851197510)
(refreshed during this pass), [Hundun guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2839992420),
[Apollo console patch facts](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPEB02052.savepatch),
and the earlier [native format review](OROCHI_RESEARCH.md). Console patch values
were corroborated against PC native routines, rather than copied as PC offsets.

## Original Warriors Orochi PC

Adds switching the equipped weapon within each officer's eight existing weapon
records. The period editor's title-specific disk getter at `0x404830`, with
label table `0x4B25C8`, identifies the byte at officer `+1`; records start at
`0xC`, stride `0xC8`. The UI displays slots 1..8 and stores 0..7. Choices use
the existing qualified original own-family weapon records, coherent attribute
mask and capacity. At least two qualified original choices and a qualified
original selector are required. Cross-family, empty, malformed or unusual
references stay opaque. No ownership, descriptor or weapon pool is created.

The earlier genuine original PC sample supplies 63 changeable selectors; the
complete sample has only one qualifying choice per officer and adds none.
Each eligible native selector was independently changed, its additive checksum
recomputed, its output reparsed and all other non-checksum bytes preserved.
The genuine Tk check exercises the owned selector, Max exclusion, Review, Undo,
backup, Save As and byte-exact restore.
This is native-save qualification backed by a period-tool disk mapping; the
original game's executable and an in-game load/re-save test remain unavailable.

The same original-PC getter maps five stored officer u16 stat words at `+4`,
`+6`, `+8`, `+10` and `+12` within each resolved record. These names and offsets
are evidence for read-only inspection; they do not qualify stat writes. No
controlled Growth Points allocation pair currently ties each named stat to its
stored word or establishes allocation side effects, bounds, or game loading.

The next useful evidence is a revision-2 original-PC `save.dat` with exact
region/build provenance, an unchanged copy, and displayed values for one chosen
officer. Starting separately from that same baseline, provide five isolated
before/after pairs: spend exactly one Growth Point on Life, then repeat for
Musou, Attack, Defense and Speed. Record all five displayed stats, Growth
Points, level, EXP and proficiency before and after each action, plus the exact
officer selected. The corresponding native copies must identify which stored
word changed, preserve all other records and unknown bytes, and pass the native
checksum. Only after those mappings and any coupled changes are understood
should a manually edited duplicate be loaded and re-saved in the original game.

| Reviewed mechanic | Remaining dependency or evidence required |
| --- | --- |
| Stock Growth Points / EXP / levels / base stats | Existing stock control remains manual; five stored stat words remain read only. Growth limits, EXP thresholds, each stat's allocation mapping and any coupled rewards need matching native transition proof |
| Weapon fusion | Existing qualified capacity, attack bonus and attribute ranks remain; fusion acquisition and consumption are distinct |
| Skills / proficiency / costumes | Prerequisites, rewards and threshold side effects remain unproved |
| Story / character unlocks | Named route/clear flags and reward dependencies remain unproved |
| Horses | Cavalier/lead-character battle behavior does not prove a persistent independent horse inventory |

Sources: [original Windows manual](https://oldgamesdownload.com/manual/warriors-orochi-windows-manual-english/),
[Van's Build 513 announcement](https://game.ali213.net/thread-1992333-1-1.html)
(refreshed during this pass), [fusion guide](https://gamefaqs.gamespot.com/ps2/938105-warriors-orochi/faqs/50450),
and [original-PC format evidence](WO1_PC_FORMAT.md). The period tool's
redistribution restrictions are respected: no code, binary or localization
catalog is imported.

## Musou Orochi Z PC

Reviewed stock EXP, level-associated EXP, base attack, proficiency, fusion,
alchemy, equipped weapons and rewards. Existing controls already cover stock
EXP, independently proved base attack and within-level EXP, and qualified owned
weapon selection, capacity, attack bonus and existing attribute ranks. The v2.6 follow-up adds independently bounded base Life, Musou, Defense and Speed
using each officer's native initial/growth tables. Unusual originals stay opaque.
[New fields and distinct-state validation](WARRIORS_V26_DEPTH.md). Level transitions require
native growth/RNG and stat rewards; proficiency thresholds 10/20/25/35/45 can
grant costumes and wallpapers. Alchemy changes material consumption and class
bits. None is reduced to an isolated counter write.

Sources: the exact Z [basic information](https://wikiwiki.jp/orochis/無双OROCHI%20Z/基本情報),
[fusion](https://wikiwiki.jp/orochis/無双OROCHI%20Z/武器融合),
[alchemy](https://wikiwiki.jp/orochis/無双OROCHI%20Z/武器錬成),
[FAQ](https://wikiwiki.jp/orochis/無双OROCHI%20Z/よくある質問),
[public native save page](https://savegame.pro/pc-musou-orochi-z-savegame/)
and [native review](OROCHI_RESEARCH.md).

## Warriors All-Stars PC

Reviewed gold, materials, hero progression, owned Hero Cards, regard, quests and
routes. Existing nine-slot gold, occupied material quantities and equipped cards
within each hero's original 20-card pool remain. No additional safe field was
proved. Hero EXP thresholds and card level/rarity/skill-derived stats need the
matching external tables; regard/request and route completion award cards and
other rewards. Battle-local Bravery is distinct from persistent hero levels.

Sources: [Understanding Warriors All Stars](https://steamcommunity.com/sharedfiles/filedetails/?id=2911155500),
[materials](https://steamcommunity.com/sharedfiles/filedetails/?id=1128232772),
[quests](https://steamcommunity.com/sharedfiles/filedetails/?id=1128263301),
[card elements](https://steamcommunity.com/sharedfiles/filedetails/?id=1132460396),
[achievements](https://steamcommunity.com/sharedfiles/filedetails/?id=1400955882),
[recruitment/routes](https://steamcommunity.com/sharedfiles/filedetails/?id=2801764723),
[public native save page](https://savegame.pro/pc-warriors-all-stars-savegame/)
and [native review](STARS_WO4_RESEARCH.md).

## Dynasty Warriors 7 Xtreme Legends Definitive Edition PC

Version 2.5.3 adds [existing weapon loadouts and learned applied seals](DW7XL_WEAPONS.md).
New weapon choices use original owned references already equipped by a playable
officer; ownership alone does not prove the external availability/DLC predicate.
New applied-seal controls replace/remove only originally occupied ordinary
learned positions. Native menus prove duplicate restrictions, five reserved
smith-learning references and direct removal without compaction. Both new groups
are unavailable during suspended battles and excluded from Max/experimental
bypass. Three distinct native PC states pass 54 independent surgical exports,
with original seed and every unrelated payload byte preserved. These are not
in-game tests. Arbitrary base attack/element edits remain outside the save format.

A separate [v2.5.2 PS3 XL → PC conversion preview](DW7XL_CONVERSION.md) now
transfers qualified existing persistent state with mixed-width native mapping.
This is distinct from the individual editor controls below; converted in-game
loading and equivalent completion remain unverified.

Adds manual reduction of an existing owned, unlearned weapon's seal meter.
Weapon records start at decoded `0x4E39`, stride 20; flags are word `+4`, meter
word `+6`. Only exact original flags `1` and original meter 1..1000 qualify.
The allowed range is 0..the opened meter. Learned, unowned, unknown-flag and
unusually high records remain opaque. This cannot increase toward an unknown
seal threshold or revoke a learned seal/system reward.

Native `0x5A4CF0` implements an explicit negative meter operation clamped at
zero. Positive progression is distinct: `0x6B8973` sets learned flag bit 4 and
the seal-award path calls `0x599AD0`. Increasing, learning or granting seals
requires the missing matching weapon/seal definitions and reward dependencies.
The existing stats, spendable points and owned active-weapon selectors remain.

Procedural tests prove decrease-only bounds, exact meter-byte changes, native
integrity and seed retention, malformed pending rejection and Max exclusion.
The supplied complete genuine sample contains no eligible unlearned meter;
its native test verifies exclusion and unchanged reconstruction. No genuine
unlearned-meter edit or in-game load is claimed. Named weapons, purchased skills,
guardians, titles, town, bonds and stage progression still require their matching
external definitions and dependencies; no persistent level/EXP field is invented.

Sources: [converter/native fixture research](https://github.com/koko-tsuu/dw7xl_save_converter)
at `15aee59cc773cb401ddad3b4c9099a03629cf700`,
[public native save discussion](https://steamcommunity.com/app/968790/discussions/0/595160389826986033/),
[Apollo console patch facts](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30873.savepatch)
and [native review](DYNASTY_RESEARCH.md). The converter is factual/fixture
research; no external converter implementation is copied or relicensed.

## Dynasty Warriors 8 Empires PC

Adds six appearance controls alongside existing Body Type for qualified ordinary
occupied custom horses: Head Size, Neck Length, Torso Length, Leg Length, Tail
Length and Muscle Volume. The PC native table independently matches all 150
fixed ordinals at decoded `0x38104`, stride `0x4C`; seven member bytes occupy
`+0x10`..`+0x16`. Body Type retains its independently published 0..4 bound.
The other six controls accept only original same-member positions witnessed in
qualified occupied ordinary horses in that opened PC file. PS3 values are not
imported as PC evidence. Type/model qualification excludes special/unknown
records, while every unknown and unusually high member remains preserved.

The genuine PC sample has two qualifying occupied rows. Head, neck and tail
witness positions 0 and 4, torso and legs only 0, and muscle only 2. Fourteen
individual native edits verify member-only changes, original seed and envelope
metadata, both checksums and reparse. Native Tk checks exercise the selector,
Review, Undo, backup, Save As and byte-exact restore. These are appearance
positions, not new horse identities, models, abilities, speed or ownership.
Unknown universal slider ranges, acquisition rules and campaign resource/story
dependencies remain blockers.

Sources: [contemporary PC horse schema, post 15](https://www.tapatalk.com/groups/koeiwarriors/dw8e-modding-efforts-t17446-s10.html),
[public PC save bundle discussion](https://steamcommunity.com/app/322520/discussions/0/1319961868335012150/?ctp=2)
and [original custom-horse evidence](DW8E_CUSTOM_HORSES.md). Published numerical
facts are independently checked against PC native records; no external source
code or horse catalog is copied.

## Dynasty Warriors 9 Empires PC

Reviewed SYSTEM inventory, CAW, campaign state, resources and progression.
The existing adapter edits quantities of already occupied known inventory
records, with manual native bounds and preserved ownership. CAW slots remain
inspection only. No additional safe field was proved: a genuine current
SYSTEM file is missing, and native campaign revision `0x317B03` has a different
578-byte metadata profile. Campaign affiliation, titles, territorial completion,
marriage/children and rewards require independent campaign qualification and
dependency proof, rather than a SYSTEM offset transplant.

Sources: [official manual](https://www.koeitecmoamerica.com/manual/dw9e/en/),
[mechanics guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2705195639),
[asset-context tool](https://github.com/HeitorSpectre/DW9E-Bin-Tool)
(MIT; no implementation copied) and [native review](DYNASTY_RESEARCH.md).

## Dynasty Warriors Origins PC

Reviewed gold, base/DLC skill points, ranks, weapon mastery/proficiency, bonds,
training, province peace, replay history, traits, equipment and campaign clears.
Existing qualified revisions 16/17/29 already expose resources, formed bonds,
training, peace, replay history and known reforgable weapon upgrades. No
additional safe field was proved. Mastery/proficiency can grant movesets and
rewards; traits and acquisition/equipped IDs need the matching native catalogs.
Replay results remain distinct from campaign completion and its unlocks.

Sources: official [systems](https://www.koeitecmoamerica.com/dw_origins/us/system/),
[DLC](https://www.koeitecmoamerica.com/dw_origins/us/dlc/),
[updates](https://www.koeitecmoamerica.com/dw_origins/us/update/),
[asset research](https://github.com/Kelebek1/dwo),
[public native DLC save](https://github.com/VdustR/game-save-dwo-d4h)
and [qualified native format](ORIGINS_FORMAT.md). Asset research is not a save
decoder; no asset implementation/catalog or public save is bundled.

## Source and validation boundaries

Steam guides, official manuals, forum reports and wikis are read for factual
mechanics; their text and catalogs are not redistributed. Apollo's repository
is [GPLv3](https://github.com/bucanero/apollo-patches/blob/main/LICENSE) (license
refreshed during this pass); its console patch facts are independently
corroborated against native PC evidence. No Apollo implementation is copied.
Native static observations are implemented independently. Existing Steamless
research is MIT and stays private; it is neither executed as a game nor added
to the runtime. A missing or restrictive external source license does not become
permission to import code, catalogs or binary assets.

New focused tests are [WO3 depth](../tests/test_wo3u_depth.py),
[original WO1 equipment](../tests/test_wo1_pc_equipment.py),
[DW7 decrease-only learning](../tests/test_dw7xl_learning.py) and
[PC DW8E appearance depth](../tests/test_dw8e_appearance_depth.py).
They distinguish procedural field/dependency proof, genuine native-file
qualification and actual game-load validation. No actual game-load/re-save
test or Windows executable build is claimed in this pass.

The fixture-enabled family regression run exercised 269 tests under Tk/Xvfb:
266 passed and three skipped. The DW7 equipped-choice and Origins native-envelope
skips used older environment-variable aliases; both passed when rerun with the
reviewed copies. The remaining skip is DW9 Empires' unavailable genuine SYSTEM
fixture. The subsequent original-WO1 equipment module, including the newly added
genuine selector GUI workflow, passed all four tests without skips. These results
cover 269 distinct passing tests and one genuine-fixture skip in the final scope.

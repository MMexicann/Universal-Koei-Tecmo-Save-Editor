# Atelier Meruru DX PC qualification

Meruru DX is currently a **read-only research candidate**, not a supported
save editor. Seventeen publicly shared PC gameplay copies pass the complete
558,080-byte fingerprint and byte-exact unchanged checks. The remaining
release blocker is native integrity for the gameplay chunks that would be
edited. No checksum-free money or inventory writer is claimed.

## Native files and currency lead

[Barrel Wisdom's PC collection](https://barrelwisdom.com/blog/atelier-pc-saves)
identifies Steam app **936190** and provides two separately described clear
copies. The minimal clear copy has tag-three word 1000; the equipped clear
copy described as having plentiful money has 364433. Fifteen further gameplay
copies from [SaveGamePro](https://savegame.pro/pc-atelier-meruru-the-apprentice-of-arland-dx-savegame/)
match the same complete chunk layout. Many have balances at or near 9,999,999.
These modified-looking reference values do not establish a legitimate Cole cap.

The immutable inspector in
[inspection.py](../src/koei_editor/research/meruru_dx/inspection.py) requires
little-endian magic 20100403, the exact 24 tag/size pairs, exact file size and
the complete final tag-1024 bounds. Its `cole_lead()` function reads the
four-byte little-endian payload of tag three at **0xCF9C**, after validating
the entire frozen inspection. It does not expose scalar gameplay fields,
Max actions, a serializer or file-writing operations. Unusual balances are
reported without clamping. The exact layout is also recorded in
[ARLAND_DX_RESEARCH.md](ARLAND_DX_RESEARCH.md).

Each acquired copy's reserved header and final payload are zero. These are
observations about those files, not proof that checksum enforcement is absent.
The word at 0xCF9C is a title-specific currency lead; an original PS3 mapping
at 0xCB58 and memory-editor addresses must not be substituted for it.

## What the working calendar tool proves

[jrpx's calendar transfer tool](https://github.com/jrpx/Atelier-Meruru-Date-Transfer-Tool/tree/c75f8d3457379677c1e84ff87232f85918ee6985)
is CC0-1.0. Its source writes **only one byte at 0x5493E**, the first byte of
the eight-byte tag-eleven payload. The README explicitly reports successful
game loading and completion after using the tool. No checksum update occurs.

This is concrete native edit/load evidence for that byte in the author's
Steam revision. It rules out a mandatory whole-file checksum covering that
byte in that revision. It does **not** rule out per-chunk integrity protecting
tag three, character data or inventory. The acquired saves are not labelled
with the author's exact build, and no complete native reader/writer has been
recovered. The tool's own documented failures include year transitions,
Hom elapsed-time tasks, shop income and event dependencies. Calendar transfer
therefore remains excluded from the application.

A separately acquired **Vita Plus PCSE00296** export now supports an independent
editor documented in [MERURU_PLUS_VITA_FORMAT.md](MERURU_PLUS_VITA_FORMAT.md).
Static inspection of Remumu's full Vita writer establishes Cole and character
word edits without game-internal integrity updates. Four distant field addresses
also coincide with the PC leads, but the complete Vita fingerprint differs in
tags 14 and 23. This is useful title-specific evidence, not proof of the later
DX PC port's integrity model, and the PC inspector deliberately rejects the
Vita layout rather than widening its acceptance rules.

## Mechanics and coverage checklist

The [official PC manual linked by Steam](https://store.steampowered.com/manual/936190)
is the primary gameplay source: development and popularity pages 18/24–28,
requests 31–34, recruitment 39, equipment 40, synthesis 45–51, menus 52–55 and
extras 14. The [official store description](https://store.steampowered.com/app/936190/)
also distinguishes development points, construction and the population/time
goal. Mechanics are not inferred from cheat names.

| Actual system | Current result | Exact blocker before a safe feature |
| --- | --- | --- |
| Current Cole | Bounded tag-three observation; all 17 copies roundtrip unchanged | Native integrity for tag three and labelled controlled purchase/sale saves; natural limit before Max |
| Development points | Official manual distinguishes points received from reporting tasks and points spent on facilities | PC points mapping, distinction between unspent points/rank totals, integrity and task/report/reward dependencies |
| Kingdom rank | Unlocks further goals and construction; evaluated after three years | Rank thresholds, whether stored or derived, and linked task/facility unlock records |
| Population | Explicit kingdom objective | PC counters and recruitment/growth/facility rules; must not imply story completion |
| Popularity | Low popularity can cause Game Over; separate from population and points | Native current value, decay/history, thresholds and game-over dependencies |
| Development goals/tasks | Goals are received, reported, fulfilled and reported again for rewards | Distinct accepted/completed/reported/reward records plus prerequisite graph; do not conflate these flags |
| Facilities and bonuses | Construction spends development points and adds specific bonuses | Facility IDs/ownership, construction costs, rank prerequisites and derived bonus updates |
| Town and personal requests | Rewards and personal events/support benefits differ | Native request identities, active/fulfilled/reported flags, deadlines and reward counters |
| Character recruitment/party | Recruiting and dismissing are separate; borrowed equipment must be retained | Native owner roster, available/recruited/party flags and equipment references |
| Character EXP/levels/skills | Separate combat progression from alchemy progression | Qualified PC record stride, recruited owners, EXP thresholds and derived skill/stat updates; console offsets are insufficient |
| HP/MP/LP | LP affects combat when below 25%; travel and some attacks consume it | Native current versus maximum/base values, recovery/death rules and equipment-derived values |
| ATK/DEF/speed | Equipment, effects and low LP modify effective stats | Separation of base/stored and derived combat values before exposing stat edits |
| Alchemy EXP/level | Level and reference books govern synthesis access | Native PC EXP/level fields, thresholds and recipe/book prerequisites |
| Basket/container inventories | Basket items can weaken or break; the container differs in availability | Exact serialized occupied/empty records, serial IDs, capacity/count, transfer/equipment/shop references and chunk integrity |
| Item quality/rank | Ingredient quality affects effect gauges and resulting bonuses | Native serialized quality field and occupancy rules, legitimate bounds, decay/rank dependencies; memory quality offsets are not disk proof |
| Existing consumable uses | Item exhaustion and breakage differ from item ownership | Native use counter, original capacity/type qualification and depleted/broken-item rules |
| Traits/effects/cost level | Traits inherit within ingredient-derived cost; effects depend on gauges and item type | Native IDs, applicability and combination rules, cost accounting and complete record integrity; no copied third-party trait catalog |
| Weapons/armor/accessories | Owned equipment changes ATK/DEF, skills and effects | Existing ownership/reference maps, item compatibility and safe equipped-stat refresh |
| Reference books/recipes | Books and alchemy level unlock synthesis options | Acquired/read/unlocked records plus prerequisite/reward dependencies |
| Exploration/routes/gathering | Travel costs days; gathering/monster completion can unlock areas | Native location IDs, route states, gathering/battle prerequisites and history |
| Hom tasks/shop income | Calendar tool documents elapsed-time and income conflicts | Assignment/elapsed-time/result records and timer transitions; no date-byte shortcut |
| Calendar/events/endings/clear state | Kept separate from resources and stats | Complete date/year/timer layout, event prerequisite/reward transitions and same-build controlled action pairs |
| Library/collections/music/movies | Main menu contains item/monster/character/help library; extras are story-dependent | Native entry catalog, seen/discovered/reward flags and system versus gameplay file split |
| Costumes/groundwork/voice extras | Official manual says these become available as the story progresses | Native ownership/selection records and scenario/system prerequisites |

Runtime research was also checked independently against
[bbfox0703's non-English DX Cheat Engine table](https://github.com/bbfox0703/Mydev-Cheat-Engine-Tables/tree/main/Atelier%20Meruru%20DX)
and [the older Fearless discussion](https://fearlessrevolution.com/viewtopic.php?p=119695).
They offer memory-level leads for money, alchemy, friendship and existing
items. They do not implement native PC disk-save integrity. No code, table,
complete item/trait catalog or bundled binary is imported.

## Minimal missing inputs

The native Meruru DX executable matching a gameplay copy is
`A13V_x64_Release_EN.exe` for English or `A13V_x64_Release.exe` for the
other supported languages. Supply the executable's game build/language and
an unchanged copied `GAMEDATAxx` from that build for **static** loader/writer
analysis. No executable will be run.

Alternatively, provide a reproducible same-build edited-save/game-load/re-save
control for the specific money/inventory chunk. A money pair should change
only one displayed purchase/sale, with starting and ending Cole values and an
unchanged control. Inventory pairs should use one already-owned consumable,
move one item between basket/container, equip/unequip one owned item and
synthesize one labelled item in separate pairs. Do not send live cloud folders,
Steam account identifiers or signing context.

## Validation

[Candidate tests](../tests/test_meruru_dx_candidate.py) check complete layout
bounds, foreign/system/truncated inputs, forged snapshots, unusual Cole values,
opaque-byte preservation and exact no-op roundtrips. The optional genuine-file
test uses `MERURU_DX_CANDIDATE_DIR`; all 17 acquired copies were checked again
in the current investigation. Public fixtures are procedural boundary tests,
not manufactured playable saves. No new GUI writer, edited-game validation or
executed game binary is claimed.

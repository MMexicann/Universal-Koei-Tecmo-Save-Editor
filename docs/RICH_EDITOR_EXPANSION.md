# Existing editor expansion — unreleased development

This pass reviews the 43 existing game/platform profiles other than DW3
Remastered. It extends existing codecs and editors; the supported inventory
remains **44 profiles**. Application version 1.6 and published release assets
are unchanged. No game or downloaded editor binary was executed.

## Implemented additions

| Editor/platform | Added editing content |
| --- | --- |
| Wo Long, PC | Custom names for enabled existing battle sets; original loadout, Virtues, spells and enable flags preserved. |
| Persona 5 Strikers, PC | Forty additional selected stack identities: seven incenses, nine ailment remedies and twenty-four skill cards. |
| Samurai Warriors 4-II, PC | Select qualified occupied mounts for existing standard officers. |
| WO3 Ultimate Definitive, PC | Unallocated upgrade stones on already promoted officers; owned ordinary-item equipment with active-slot and duplicate checks. |
| Hyrule Warriors Legends, 3DS | Reduce existing owned fairy trust without changing level, personality, refresh or skills. |
| Fire Emblem: Three Houses, Switch | Instruction motivation choices and original learned/equipped ability loadout movement/unequip, with owner/deployment and duplicate guards. |
| Nioh 3, PC | Eleven additional named ordinary consumables, eighteen total, retaining original quantity-reduction rules. |
| Atelier Ryza 2, PC | Reduce qualified unspent skill-tree SP; learned skills/recipes remain separate. |
| DW4 Hyper, PC / DW4 XL, PS2 | Replace or unequip originally occupied, known-owned general-item slots; no duplicate equipment or concurrent weapon-EXP change. |
| DW5 Special, PC | Manual stored Attack/Defense on already playable officer records. |
| DW6, PC | Manual damage-bonus words on existing qualified weapons. |
| Samurai Warriors 2, original PC | Select an existing known weapon from the same officer's inventory pool. |
| Warriors Orochi, original PC | Select an existing known weapon from the same officer's inventory pool. |
| DW7 XL Definitive, PC | Reduce qualified owned, unlearned weapon seal meters; acquisition and learned flags preserved. |
| DW8 XL, PC | Atomically reorder an officer's two originally equipped, qualified weapons. |
| DW8 Empires, PC / US PS3 SYSTEM | Six additional horse appearance members, restricted to same-member positions witnessed in qualified original occupied ordinary records. |
| Dynasty Warriors: Gundam, US/EU PS3 | Choose originally learned non-inherent equipped skills on qualified level-30 pilots; occupied-slot swaps stay atomic. |

These are **19 expanded game/platform profiles**, not nineteen additional games.
Fields are selected from each immutable original. Manual editing limits are not
advertised as natural caps; choices, reductions and unsupported maxima are
excluded from Max. Story, acquisition, rewards and prerequisite transitions
remain separate from these edits.

## Shared editing actions

All scalar workspaces gain **Adjust Selected**, adding/subtracting an integer
from each selected pending value with backend validation and one Undo batch.
Text and named choices use Apply Selected. A failed field rejects the whole
adjustment; hidden pending edits survive.

**Revert Selected** restores opened values by removing the selected pending
edits and validating the final complete batch. This avoids transient duplicates
when restoring a moved ability loadout. An incomplete selection that leaves
invalid equipment is rejected; Undo can restore the complete previous batch.
Backups, Review Changes, retained sessions and new-copy Save As remain shared.

## DW8 XL weapon-order proof

The existing decoded officer reader identifies two adjacent zero-based u16
weapon-pool references at `0x7FC9 + officer*0x48 + 0x30/+0x32`.
The independently described native PC permanent structure places its two
weapon references at `+0x7C/+0x7E` following the same stat, compatibility,
level/EXP and leadership fields. The existing converter establishes the shared
decoded save layout. See the factual source links in
[DW8_COMPATIBILITY.md](DW8_COMPATIBILITY.md).

The new operation admits only a distinct pair of in-range references to
existing qualified weapon records. It exposes the first weapon as a choice of
those **two original slots** and writes the other reference in the same
transaction. It conserves the exact equipped multiset; weapon identities,
states, affinities, attack, attributes, ownership and all other officers remain
unchanged. It cannot equip a third weapon or infer unlocks. Both references
are declared, with the second recorded as a dependent mirror. Order has no Max.

`tests.test_dw8_weapon_order` covers unchanged native reconstruction, original
pair admission, empty/sentinel/out-of-range/duplicate rejection, exact paired
writes, original unstaging, excluded Max, genuine-file surgical edits and Tk
choice/Review/Undo/backup/Save As. The implementation is original; no foreign
editor code or catalog is incorporated.

## Whole-library coverage and blockers

Each reviewed game has a mechanics checklist with concrete missing evidence:

| Review lane | Profiles covered | Detailed additions and remaining blockers |
| --- | --- | --- |
| Team Ninja | Wo Long, Nioh 3, original NGII Xbox360/Xenia | [TEAM_NINJA_DEPTH.md](TEAM_NINJA_DEPTH.md) |
| Persona/Gust/Fatal Frame | P5 Strikers, Sophie, Sophie 2, Ryza 2, FF2 Remake | [PERSONA_GUST_DEPTH.md](PERSONA_GUST_DEPTH.md) |
| Samurai/early Dynasty | SW4-II, SW4 DX, SW2 PC, DW4 Hyper, DW4 XL PS2, DW5 Special, DW6 | [SAMURAI_DYNASTY_DEPTH.md](SAMURAI_DYNASTY_DEPTH.md) |
| Orochi/modern Dynasty | WO3 PC, WO1 PC, Orochi Z, All-Stars, DW7 XL, DW8 Empires PC, DW9 Empires, Origins | [OROCHI_DYNASTY_DEPTH.md](OROCHI_DYNASTY_DEPTH.md) |
| Hyrule/Fire Emblem | Wii U HW, Switch HWDE/AoC/FEW/Three Hopes/Three Houses, 3DS Legends | [HYRULE_FIRE_EMBLEM_DEPTH.md](HYRULE_FIRE_EMBLEM_DEPTH.md) |
| Console/Pirate/strategy | PW3, PW4, DW7/SW4/DW7E/DW8E/WO3 PS3, Ayesha PS3, Gundam PS3, Ken's Rage 1/2 PS3, ROTK XIII PC | [CONSOLE_PIRATE_STRATEGY_DEPTH.md](CONSOLE_PIRATE_STRATEGY_DEPTH.md) |
| DW8 XL | Native PC profile | Weapon-order proof above and [DW8_COMPATIBILITY.md](DW8_COMPATIBILITY.md) |

DW8 Empires PC appears in two coordinated lanes; it is counted once. The
other unchanged profiles have specific progression, field-identity, catalog,
native-input or reward/dependency blockers. Their existing qualified controls
are retained. This review does not activate research-only games or assume
another platform's offsets work.

## Validation boundaries

New feature checks include procedural malformed/dependency cases, native-file
unchanged/surgical edits where fixtures exist, and real Tk editing, Undo,
Review, backup, save and restore workflows. Focused checks and validation boundaries are recorded in
[VALIDATION.md](VALIDATION.md); the integration pull request records the final
combined regression result and native Windows preview run.

Wo Long enabled battle-set naming still lacks a positive eligible native sample;
its edit path has static/schema, procedural and GUI evidence, and a native
enabled rename pair is the specific missing input. DW7 unlearned seal-meter
reduction has an optional file-level surgical test for an eligible record in a
second private native PC copy reported in PR #43. Maintainer review copies have
no eligible positive meter, so the reported positive case is not independently
reproduced. A controlled learning action pair remains missing.
No edited save has been imported, loaded and re-saved in its game in this pass.
Private fixtures, owner context and binaries remain outside Git and artifacts.

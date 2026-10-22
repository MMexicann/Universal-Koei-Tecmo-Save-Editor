# Hyrule Warriors console-export adapters

These adapters edit **decrypted native exports** from the explicitly selected
platform. They do not decrypt console storage, resign saves or change save-owner
context. Work on a separate export copy and retain the original console backup.
Wii U uses `APP.BIN`; Switch Age of Calamity uses the extensionless file `svdt`.
Rename edited copies to their native names only when transferring them using an
already authorized export/import workflow.

## Evidence and scope

The independent Python implementations use format facts from:

- [MarcRobledo/savegame-editors](https://github.com/MarcRobledo/savegame-editors/tree/b4db8cd11157c6d5ae54a0a5edc88dba82aebe9d),
  MIT, copyright Marc Robledo. Wii U source v20161101 and AoC source v20260405.
- [BtEtta/save-editors](https://github.com/BtEtta/save-editors/tree/b77b1ac19d26f083365106ce8e8ed1ef32a23ba6/aoc),
  MIT under its README licence, copyright 2026 Robin Zalek. It documents the
  AoC 1.3.0 weapon pool, native version byte, preserved total-earned rupees,
  weapon protection, named weapon/seal IDs and report ID 175.

Selected factual name tables retain both applicable MIT permission notices in
adapter catalogs. Neither upstream editor/UI nor game images/assets are shipped.
Source-backed support, an upstream bundled example, independently acquired
player-save qualification and actual edited game loading are distinct evidence.
Both adapters now have **independently shared complete player-export qualification**
and keep `sample_verified=True`. Actual edited console-load/re-save validation
remains unperformed.

Three complete upstream reference exports were checked privately: one Wii U
example and two different AoC examples. All have nontrivial native progression
and inventories. They are upstream source examples, not evidence of independent
console ownership, region or load testing, and are excluded from Git/releases.

Additionally, two independently shared Wii U player exports and one independently
shared AoC player export were downloaded from public forum contributions. The
Wii U player describes two successive completion states including DLC; the AoC
player reports 100%completion with both DLC waves. All match the selected native
layout and pass byte-exact no-op, targeted edits for every qualified field, and
real Tk copied-native save/backup/restore workflows. Copies and detailed private
provenance are excluded from Git/releases. There is no actual edited game-load
claim. The Wii U examples expose 495 and689 qualified fields; AoC exposes 367
(206 existing weapon protections, 160 named material quantities, rupees).

The decoder checks exact size and observed reference header marker. The upstream
sources expose no native checksum/encryption layer for these decrypted exports;
these adapters preserve every byte outside qualified scalar edits and perform a
full reparse. They do not claim to detect arbitrary corruption in unknown bytes.
Wii U: size `0x300000`, big-endian, observed marker `15010500`; meaning/build of
that marker remains unqualified. AoC: size `0x100000`, little-endian, marker
`89000000`, source-mapped 1.3.0 layout. Other header markers and editions are
rejected. In particular, Wii U support does not imply 3DS Legends or Switch
Definitive Edition support, and AoC does not imply Switch 2 support.

## Edition and platform boundaries

These Hyrule titles use separate native profiles. A matching filename or a
shared Zelda setting does not select a compatible parser.

| Game and platform | Accepted input and profile | Editing scope / status |
| --- | --- | --- |
| Hyrule Warriors, Wii U | Decrypted `APP.BIN`, `0x300000` bytes, observed marker `15010500` | Resource, existing map-card, weapon-star and ordinary-seal fields; progression, ownership and reward flags remain protected. [Wii U source](https://github.com/MarcRobledo/savegame-editors/tree/b4db8cd11157c6d5ae54a0a5edc88dba82aebe9d) |
| Hyrule Warriors Legends, Nintendo 3DS | Decrypted `zmha.bin`, `0x39462` bytes, source-mapped version 1.0.0 | Separate 3DS resource, card, weapon and owned My Fairy name/trust fields. No Wii U offsets are used. [3DS source](https://github.com/nedron92/HWL-SaveEditor/tree/4259e42b4ee6d643859fc218e436c20c337cb358) |
| Hyrule Warriors: Definitive Edition, Nintendo Switch | Decrypted `zmha.bin`, `0x3D8E4` bytes, observed marker and stored-size checks | Separate Switch resource, weapon-star and ordinary-seal fields; fairy, character progression and map systems remain read-only. [Switch profile sources](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/blob/d16d36c7509c01dca770f402babd83ff2e9ae6e7/Configs/0100AE00096EA000.json) and [dedicated editor source](https://github.com/iAroc/iAroc.github.io/tree/15e4a928bdffb202a7893e14fde432f2dcbc10b3/hyruleWarriors) |
| Hyrule Warriors: Age of Calamity, Nintendo Switch | Extensionless `svdt`, `0x100000` bytes, source-mapped 1.3.0 profile | Discovered inventory and reports, rupees, and existing weapon-protection fields; growth, fusion, quest rewards and unlocks remain protected. [AoC format source](https://github.com/MarcRobledo/savegame-editors/tree/b4db8cd11157c6d5ae54a0a5edc88dba82aebe9d) and [weapon/data definitions](https://github.com/BtEtta/save-editors/tree/b77b1ac19d26f083365106ce8e8ed1ef32a23ba6/aoc) |
| Hyrule Warriors: Age of Imprisonment, Nintendo Switch 2 | Nintendo's [product listing](https://www.nintendo.com/us/store/products/hyrule-warriors-age-of-imprisonment-switch-2/) identifies this as a separate Switch 2 title; no complete native save or independently mapped layout is qualified here | Research only; no editor is registered. A separate profile needs the complete native export and any associated system/companion files, exact game/update/DLC provenance, an unchanged control, and controlled before/after pairs for a resource spend, character growth, weapon change and quest/reward. The existing Wii U, 3DS, Switch and Age of Calamity profiles must not be applied to it. |

The Switch 2 row is a candidate intake, not evidence that its save can be
decoded or safely edited. Preserve the original console backup and owner context;
share copies and provenance privately, and keep them out of the public PR. Before
adding a writer, identify its archive/encryption/integrity layers, establish a
byte-exact unchanged roundtrip, and reparse a surgical edit.

## Wii U coverage checklist

| Mechanic | Implemented scope / precise remaining blocker |
| --- | --- |
| Rupees | Current u32 at `0x14C`, range 0..9,999,999. Higher originals remain unchanged by Max. |
| Material inventory | 77 named u16 slots at `0x13D2C`, cap 999. Only positive opened quantities qualify writes. Zero slots remain inspectable. Discovery bitset at `0x13E2C` is preserved; upstream's discover-all mask does not prove individual discovery-bit access, so exhausted/undiscovered slots are not manufactured. |
| Adventure map consumables | Named existing positive u8 cards, cap 5. Adventure `0x141E8`, Master Quest `0x19240`, Twilight `0x1BA6C`, Termina `0x1E298`; sparse map-specific card IDs preserve unused bytes. Empty cards/maps and DLC entitlement are not granted because their ownership/discovery mapping is missing. |
| Weapon stars | Existing recognized normal/Legendary records, u16 stars at `record+0x0A`, range 0..5. Pool has 1030 physical `0x4C`-byte slots from `0x8D74C`. Unknown/empty/blank/hacked states, reserved Ganon/Cucco IDs and Master Sword identity/state remain read-only. No weapon is created, replaced, reordered or equipped. |
| Ordinary weapon skill seals | Existing normal-weapon ordinary skill countdown at `record+0x2C+4*slot`. Deliberately decrease remaining KOs to0..opened count; 0 unseals. Original value unstages. Excluded from Max. Source example contains initial 1000/2000/3000 and partial 38/783/991/1682 counters, corroborating countdown semantics. |
| Weapon identity / base power / fusion / skills | Searchable named weapon and skill inspection. IDs, base power, skill IDs, equipment references and all other record bytes are preserved. Safe arbitrary changes need class-compatible skill rules, fusion transfer/cost behavior and tier/ownership dependencies. Published editor permits raw mutations; this adapter does not treat its unrestricted choices/storage ceilings as legitimate gameplay limits. |
| Legendary / Evil's Bane seals | Read-only. These require collection/prerequisite state as well as KOs; the ordinary-seal action never changes them. Collection flags and prerequisite dependencies are unqualified. |
| Character levels / EXP | Named read-only records: packs `0x8C184` and `0x8CB24`, stride`0x38`, stored level-minus-one byte +7 and u32 EXP +8. The source writes level and EXP independently and supplies no EXP curve or coupling; legitimate synchronized growth needs that missing mapping. Empty/default DLC records are not interpreted as unlocked characters. |
| Character health / attack / badges / combos / skills | No writes. Upstream's unnamed u16 “damage” field is offered an impossible99,999,999 range; neither its meaning nor natural limits are qualified. Badge/skill trees require flags, material costs, prerequisites and derived-stat mappings. |
| Character / weapon / costume unlocks | No writes. Ownership flags, DLC gates and reward dependencies are missing. Named default records do not prove ownership. |
| Legend / Adventure / Challenge / Ganon / Cucco progression | No story-completion actions. Stage/rank, reward, skulltula, heart-piece/container, gallery and campaign flag layouts/dependencies are unmapped. Cards and ordinary weapon/resources remain separate from completion. |
| Music / movies / medals / collections | No writes; per-record flags and reward prerequisites are missing. No unsupported collection is created. |

## Age of Calamity coverage checklist

| Mechanic | Implemented scope / precise remaining blocker |
| --- | --- |
| Rupees | Current u32 at `0x2C3A4`; deliberate writes are bounded by `min(9,999,999, opened lifetime total)`. Total-earned u32 at `0x3C2BF` is inspected and preserved. BtEtta updates history if current exceeds total; this implementation avoids fabricating history by bounding the current balance instead. Existing unusual higher balances remain unchanged by Max and can be unstaged. |
| Named discovered inventory | u16 quantities at `0x2C14E+2*ID`; discovery byte at `0x2C2DD+ID` must already equal1. Fruit, mushrooms, vegetables/wood, meat, ingredients, fish, insects, minerals, monster and Guardian parts, cap 999. Discovered exhausted quantities can be refilled; discovery bytes/unknown states are preserved. Unused IDs are excluded. |
| Trophies / DLC reports | Named discovered trophies/reports, cap 9999, including PotA Guardian research materials and GoR Report: Hidden Battles ID 175. Existing discovery is required; no DLC entitlement/quest is created. |
| Special collectibles | Korok Seeds ID 147, Terrako Components ID 149 and Ethereal Stones ID 150 are inspected only. Collection flags, quest consumption, rewards and story/character unlock dependencies are missing; resource Max never changes them. |
| Weapon protection | Existing recognized weapons for their catalog-mapped character, u8 `record+0x4C`, only opened values0/1. 0 permits fusion selection; 1 protects the weapon. Rusty, unknown, broken/debug, mismatched-owner and unusual protection records remain inspection only. Protection is excluded from Max; it never changes identity, equipment or ownership. |
| Weapons / seals inventory | Searchable named read-only records:21 character pools of71 physical `0x51`-byte records from `0x11E6`. The source identifies temporary battle capacity beyond normal storage. Inspect level, EXP, two stored power terms, protected/rusty state, six seal IDs and their saved parameter pairs; preserve ordering and every unknown byte. |
| Weapon levels / EXP / level caps / power / quality | No writes. Upstream explicitly leaves EXP caps for weapon types unresolved; level/EXP/power terms and level20/25/30/50 cap codes require synchronized progression and blacksmith/quest prerequisites. Raw “quality0..23” and power storage ceilings do not prove natural bounds. |
| Fusion / seal editing / polishing | No writes. Default seal parameters, percent units, tier/shape compatibility, hidden-seal level prerequisites, fusion multipliers/costs and rusty-result mappings are not qualified. Existing inspection does not claim these are safely writable. |
| Character levels / EXP / stats |21 named read-only level-minus-one records at `0x2BCAD`, stride 30. Marc writes level alone; accompanying progress encoding/EXP curve is unqualified. Its AoCNotes describes fractional progress but the complete examples do not establish that interpretation. Health, combos, special gauges and training growth require quest/skill-derived mappings. |
| Character / costume unlocks / upgrades / cooking | No writes. Roster, recipe, equipment and upgrade flags/prerequisites/rewards are unqualified. Default locked records are not ownership evidence. |
| Campaign / challenges / towers / quests / DLC laboratories | No completion actions. Stage results, exploration, blood-moon, challenge/quest completion, rewards and gate flags are unmapped. Inventory/protection edits preserve these systems. |
| Gallery / movies / music / medals / collections | No writes; record flags and dependencies are missing. |
| Earlier save revisions | BtEtta identifies markers87 (1.1.0 uncertain),120/122 (1.2.x), with different material/rupee/weapon offsets and record capacities. Complete independently qualified earlier examples are missing; these layouts are rejected rather than guessed. |

Mechanics references also consulted:
[Wii U weapon guide / Legendary prerequisites](https://gamefaqs.gamespot.com/wii-u/745183-hyrule-warriors/faqs/72769/leg-skills),
[Hyrule Warriors weapons](https://www.zeldadungeon.net/wiki/Hyrule_Warriors_Weapons),
[AoC material guide](https://game8.co/games/Hyrule-Warriors-Age-of-Calamity/archives/306165),
and [published AoC item-limit discussion](https://www.reddit.com/r/AgeofCalamity/comments/qu6mh9/question_about_item_limits/).
Discussion/guide mechanics alone do not qualify serialization offsets.

## Validation

`tests/test_hyrule_formats.py`:25 tests cover source-reference no-op/targeted
roundtrips (optional private inputs), wrong size/header/platform, immutable
snapshots, endian encoding, surgical byte changes, original-value unstage,
higher-value Max preservation, existing-record selection, special/resource
exclusions, seal prerequisites, protection exclusions, preserved lifetime
history, backups, exact-byte restore and changed-source protection.

`tests/test_hyrule_gui.py`:4 real Tk workflows under Xvfb cover named search,
Apply, Review, Undo, named weapon/seal inspection, themes, visible Max exclusions,
automatic backup, new-copy saving, restore and extensionless Save As defaults.
Procedural fixtures prove behavior; they are not playable-save qualification.
These 29 tests plus five independent Hyrule safety audits pass when both optional
source-reference and genuine-export inputs are supplied. A combined run also
includes one unrelated PS3 safety audit:35 tests,35 passed. With no private
fixtures, four source/genuine input checks skip honestly. The registered scalar
contracts additionally verify exact platform binding for both new game cards.
Use `HYRULE_SOURCE_REFERENCE`/`CALAMITY_SOURCE_REFERENCE` for source examples and
`HYRULE_SAVE_COPY`/`CALAMITY_SAVE_COPY` for separate reviewed genuine export copies.

Independent audits reject invalid pending Max values, immutable/foreign snapshot
forgeries and hash-consistent wrong-layout backups, and confirm extensionless
backup/manifest separation and higher-value/unknown-record preservation.

Windows packaging/console import/game loading are separate checks. No console
binary was executed and no edited console load/re-save has been performed.

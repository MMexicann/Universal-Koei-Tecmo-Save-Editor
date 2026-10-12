# Expansion coverage and remaining inputs

This checklist records the implemented scope of this expansion and the evidence
still required for deeper editing. The linked game checklists contain native
addresses, format details, sources, test commands and individual mechanic
blockers. A qualified codec is distinct from a gameplay editor; a successful
file roundtrip is distinct from loading an edited file in the game.

The v1.91 source contains **76 registered game/platform profiles across 13 platforms**.
The new separately qualified profiles are described below;
the registry-derived [inventory](SUPPORTED_GAMES.md) is authoritative.
Research-only formats remain outside the library.

## v1.91 additional-game survey

The survey reviewed 22 additional game/platform candidates. These remain
research-only because their complete native integrity, writable field maps,
record ownership or controlled gameplay pairs are not yet qualified. Do not
interpret a title below as supported by the application.

| Candidate | Main qualification blocker |
| --- | --- |
| [Fairy Tail](FAIRY_TAIL_SWITCH_RESEARCH.md), Nintendo Switch | Container framing and checksums are known, but no writable gameplay field is mapped. |
| [Dead or Alive 5 Last Round](DOA5LR_PC_RESEARCH.md), Windows PC | Title-specific semantic map and complete integrity coverage are missing. |
| [Blue Reflection: Second Light](BLUE_REFLECTION_RESEARCH.md), Windows PC | The guide-node length is unresolved and fields are unmapped. |
| [Ninja Gaiden 2 Black](NINJA_GAIDEN_RESEARCH.md), Windows PC | Native story payload integrity is unresolved. |
| [Ninja Gaiden Sigma 2 Master Collection](NINJA_GAIDEN_RESEARCH.md), Windows PC | Payload integrity and occupied inventory boundaries are unresolved. |
| [Nioh Complete Edition](NIOH_INTEGRITY_RESEARCH.md), Windows PC | Active native integrity checks are unresolved. |
| [Nioh 2 Complete Edition](NIOH_INTEGRITY_RESEARCH.md), Windows PC | Active native integrity checks are unresolved. |
| [Berserk and the Band of the Hawk](BERSERK_PC_RESEARCH.md), Windows PC | Title/revision identity, inner integrity and controlled field pairs remain incomplete. |
| [Attack on Titan: Wings of Freedom](AOT1_PC_RESEARCH.md), Windows PC | Title/revision identity, complete integrity and controlled field pairs remain incomplete. |
| [Attack on Titan 2: Final Battle](AOT2_PC_RESEARCH.md), Windows PC | Exact build identity, complete integrity and controlled field pairs remain incomplete. |
| [Samurai Warriors: Spirit of Sanada](SANADA_PC_RESEARCH.md), Windows PC | Inner integrity, serializer and writable action pairs are still needed. |
| [Atelier Rorona DX](RORONA_DX_FORMAT.md), Steam PC | Native integrity, catalog mapping and ownership rules remain unresolved. |
| [Atelier Meruru DX](ARLAND_DX_RESEARCH.md), Steam PC | Native integrity and field mapping remain incomplete. |
| [Atelier Totori DX](TOTORI_DX_PS4_FORMAT.md), PS4 CUSA14014 | Native integrity and controlled action pairs remain incomplete. |
| [Dynasty Warriors: Strikeforce](STRIKEFORCE_PS3.md), US PS3 | Exact revision, native integrity and progression rules need qualification. |
| [Samurai Warriors 2 HD with Xtreme Legends](SW2HD_PS3.md), JP PS3 | Full export identity, revision and native integrity remain unqualified. |
| [Atelier Lulua](LULUA_NELKE_SWITCH_RESEARCH.md), Nintendo Switch | A qualified decoder, exact roundtrip and controlled writable actions are needed. |
| [Nelke & the Legendary Alchemists](LULUA_NELKE_SWITCH_RESEARCH.md), Nintendo Switch | Switch-specific codec, integrity and writable actions remain unqualified. |
| [Dynasty Warriors 9](DW9_ORIGINAL_PC_RESEARCH.md), original Windows PC | Native integrity and record ownership remain unqualified. |
| [Dragon Quest Heroes: Slime Edition](LICENSED_ACTION_RPG_STATUS.md), Windows PC | Title identity, integrity and semantic field mapping remain incomplete. |
| [Dragon Quest Heroes II](LICENSED_ACTION_RPG_STATUS.md), Windows PC | Header, slot boundaries, integrity and gameplay semantics remain unresolved. |
| [Ninja Gaiden Sigma](NINJA_GAIDEN_RESEARCH.md), Windows PC | Title/revision identity and native serializer/integrity need qualification. |

These titles are useful research targets. Registration requires the complete
native evidence and gameplay qualification described in the contributor guide;
the current library remains at 76 profiles until then.

A follow-up checked a newly published MIT DW3 Remastered editor for the existing
Windows Steam profile and a DW8 XL PC/PS3/PS4/Vita container converter. The DW3
source exposes Challenge Mode board edits, but its own limits are not game caps
and board scores can cross item-reward thresholds; controlled reward and
achievement pairs are still needed. The converter does not qualify new
platform writers. Neither lead changes the supported profile count.

A broader online sweep also catalogued more than twenty additional edition or
platform leads, including PS4 Save Wizard recipes, older Japanese PC/PC-98
editors, and community tools for ROTK X/XI/XII, DW5 PC, DW7 Empires PC, and
Musou Orochi Z PC. Those sources establish that editors exist, but not safe
native write behavior: revision scopes, checksums, field dependencies, reuse
terms and representative saves are incomplete. The [public source catalog](EDITOR_SOURCE_CATALOG.md)
lists the research and its blockers. These leads are not counted as registered
games or implemented support.

The [existing-editor expansion](RICH_EDITOR_EXPANSION.md) reviews every supported
profile except DW3 Remastered and adds content to 19 existing profiles. Its
per-lane checklists supersede earlier read-only claims for those controls;
unproved progression, acquisition and reward transitions remain blocked.

## v1.9 additions

| New profile | Implemented controls | Specific next evidence for deeper editing |
| --- | --- | --- |
| [Legend of Liu Bei, original Traditional Chinese DOS](REKO3_DOS_FORMAT.md) | Existing allied troop reductions and within-level EXP; 384-record inspection. | One controlled troop/EXP/level-up pair and successful edited game load; class, equipment and derived growth rules. |
| [ROTK III, original Traditional Chinese DOS](ROTK3_DOS_FORMAT.md) | Ordinary-officer abilities and owned-city gold/rice/commerce/military-supply reductions. | Complete occupied player campaign and displayed-value action pairs; rank, loyalty, armies and diplomacy dependencies. Initialized native reference is distinct from an occupied player save. |
| [Tenshouki PK, original Japanese Windows 95](NOBU6_PK_PC_FORMAT.md) | Existing district gold/rice/horse/firearm reductions and six inspectors. | Complete occupied native player campaign, build label and one district purchase/reward pair; officer/army/ownership relationships. |
| [Gundam Reborn, EU/JP PS3](GUNDAM_REBORN_PS3_FORMAT.md) | Money and existing Amuro/Kamille Team Point reductions; resource inspection. | Named material-use, pilot-skill, plan-fusion/equip and reward pairs with original PARAM.SFO. |
| [Gundam 3, US PS3](GUNDAM3_PS3_FORMAT.md) | Money reductions; lab EXP/license inspection. | Purchase and lab progression/equipment pairs; console load/re-save confirmation and other-region writer proof. |
| [TRINITY, US PS3](TRINITY_PS3_FORMAT.md) | Money reductions; SP and named stat-word inspection. | Money purchase/load check plus stat-level/skill purchase pairs proving stored-versus-derived values. |
| [Original Totori](TOTORI_PS3_FORMAT.md), [Meruru](MERURU_PS3_FORMAT.md), [Rorona](RORONA_PS3_FORMAT.md), PS3 | Cole reductions; named character and system inspection. | Original-edition purchase/synthesis/equip/level pairs and edited load/re-save; PS3 evidence does not qualify DX or Plus. |
| [Sophie 2, PS4 CUSA28451 app 1.0](SOPHIE2_PS4_FORMAT.md) | Quality reductions for nine named ordinary material identities; use refills for nineteen named battle-item identities within existing capacity; party/inventory/equipment inspection. | Synthesis/equip and wallet pairs; other item identities, trait/effect dependencies and edited game-load proof. |
| [Ninja Gaiden Black SYSTEM, original Xbox](NINJA_GAIDEN_BLACK_XBOX_FORMAT.md) | Restore numeric save-list order; inspect thirty slot timestamps. | Genuine SYSTEM.dat plus original EEPROM and successful load-order check. Story-slot inner integrity still needs separate evidence; story editing remains unregistered. |

Genuine-file checks, complete published-writer evidence, procedural tests and
actual game-load validation are recorded separately in each linked document.
No edited game load is claimed for this expansion.

## v1.8 additions

See the individual new format documents in the [documentation index](README.md) for exact native qualification, supported revisions, mechanics and remaining dependencies.

## Earlier v1.72 additions

- [Persona 5 Strikers English Switch](P5STRIKERS_SWITCH_FORMAT.md): money, Persona
  points, unspent BOND points and 94 reviewed existing stack identities. Two
  distinct native files qualify full direct-buffer writing and exact framing;
  character/Persona growth, skills and story/reward transitions remain separate.
- [Ryza 2 original Switch](RYZA2_SWITCH_FORMAT.md): unspent skill-tree SP
  deductions and existing inventory/equipment inspection. Learned nodes and
  nonzero-adjacent quality remain untouched. The acquired modified starter proves
  the SP write; conditional zero-adjacent quality has procedural/source evidence.
- [Dragon Quest Builders 2 original Switch](DQB2_SWITCH_FORMAT.md): named existing
  medicine/seed deductions and searchable pockets/bag/player/equipment records.
  Two distinct complete native slots qualify the padded framing. World, island,
  equipment ownership and story dependencies remain separate.
- [Original Chinese DOS ROTK II](ROTK2_DOS_FORMAT.md): owned-province gold/rice
  deductions and province inspection. The complete native raw writer and original
  scenario-reference layouts are qualified; independent player-save and edited
  game-load validation remain separate and unperformed.
- [DOA5 Plus Vita](DOA5_PLUS_VITA_RESEARCH.md): both block checksums and unchanged
  re-encryption qualify two distinct public native states, but no Plus-specific
  persistent writable field is proved. This remains unregistered.

Attached executables were investigated as static data. They were never run.
Private static analysis copies, freely shared player saves, owner identifiers,
game assets and personal paths are excluded from source packages and releases.
The initial oversized Dynasty Warriors 9 Empires transfer was resolved with an
accessible replacement. Its native save code was inspected statically.

## Original Windows PC additions

The original 2008 Windows PC SW2 and Warriors Orochi additions are qualified
separately from this earlier attached-game survey. Both have integrated scalar
editors, period original-PC disk-reader/writer evidence and two independent
genuine files. [SW2](SW2_PC_FORMAT.md) covers money, owned-officer growth,
acquired ordinary skills and existing weapon bonuses;
[Warriors Orochi](WO1_PC_FORMAT.md) covers shared Growth Points and existing
weapon bonuses, capacity and acquired effect ranks. The notes keep original PC,
console and later editions separate and list per-system dependencies and exact
remaining inputs. No edited game load or native Windows EXE validation is claimed.

## Ten attached games

| Attachment / game | Delivered scope | Qualification and remaining essential input |
| --- | --- | --- |
| `SM6EN.exe` / Dynasty Warriors 7: Xtreme Legends Definitive Edition | Native PC editor: gold; health, attack, defense, power, speed and spendable skill points for 65 playable records; selection between already equipped owned weapons; searchable weapon/seal/equipment/skill inspection | Genuine native sample, native cipher/checksum and exact revision qualified. External `LINKDATA_CMN` / `LINKDATA_ENG` parameter/localization containers and indexes, or controlled action pairs, are needed for weapon/skill/title identities and dependencies. [Full checklist](DYNASTY_RESEARCH.md#dynasty-warriors-7-xtreme-legends-definitive-edition) |
| `WO3U.exe` / Warriors Orochi 3 Ultimate Definitive Edition | Native PC editor: five stats for 145 playable records, growth points/gems, 58 orb balances, 295 crafting balances, existing weapon slots, all qualified ranked attribute types and guarded attack-reinforcement reductions; read-only progression and weapon inspection | Genuine copied native file and static packed serializer qualified. Names, natural resource clamps, promotion/EXP rewards, fusion, equips, bonds and clear/unlock dependencies need parameter tables or controlled pairs. [Full checklist](OROCHI_RESEARCH.md#warriors-orochi-3-ultimate-definitive-edition) |
| `SamuraiWarriors4DX.exe` / Samurai Warriors 4 DX | Native PC editor: gold/eight gems, five base stats for 55 standard officers, guarded standard-character unlocks, existing own-pool weapon selection, attached skill levels/activation; searchable weapon and progression inspection | Genuine current-revision copy, full envelope and four gameplay checksums qualified. Growth/proficiency tables, record dictionaries and Chronicle/reward pairs remain necessary for derived progression and further content edits. [Full checklist](SAMURAI_RESEARCH.md#samurai-warriors-4-dx-implemented-native-pc-adapter) |
| `OPPW4.exe` / One Piece: Pirate Warriors 4 | Native revision-15 resource editor: spendable Beli and quantities of already obtained qualified coin records; current/lifetime counters and coin history are kept separate | Genuine slot, ordered object layout, outer checksum and object checksums qualified. Only one-step WW/JP/EA region family and revision 15 qualify; attached writer revision 22 needs separate migration evidence. [Full checklist](PIRATE_ABYSS_RESEARCH.md#pirate-warriors-4) |
| `OROCHI_Z.exe` / Musou / Warriors Orochi Z | Native revision2 PC editor: Stock EXP, base attack for 96 officers, existing weapon attack bonus, attribute capacity, owned ranked effects, own-pool equipped references and guarded within-level EXP; searchable officer/weapon inspection | Genuine native save qualifies plaintext size/revision/marker, byte-sum integrity, unchanged roundtrip and surgical writes. Other stats, growth/reward coupling, exact names, new attributes/weapons, alchemy and story unlocks need native catalogs and controlled pairs. [Full checklist](OROCHI_RESEARCH.md#musou--warriors-orochi-z) |
| `Star_US.exe` / Warriors All-Stars | Native current-revision PC editor: available gold and existing positive material quantities in campaign slots, with separate lifetime earnings and slot inspection | Complete genuine save, native packed serializer and grant/spend paths qualify revision `0x170302F4`, ten-block AES framing and scalar semantics. Native active serializers perform no extra payload checksum; original seeds/padding and untouched blocks preserved. Fingerprint is not a payload checksum. Hero/card growth, material names/acquisition, regard and story rewards need record/dependency maps. [Full checklist](STARS_WO4_RESEARCH.md#all-stars-coverage-checklist) |
| `WO4.exe` / Warriors Orochi 4 / Ultimate | Separate native PC editors: Gems, Crystals, Growth Points, officer Skill Points, existing element stock and Skill Orb reductions; Ultimate also exposes promoted officers’ unspent Upgrade Stones. Searchable officers, weapons and histories | Matching DLLs and supplied native saves resolve encryption/layout proof. Exact original 20180720 and Ultimate 20200101 profiles; older Ultimate 20191201, names, growth/equipment/fusion/story/Infinity dependencies and edited game loads remain separate. [Original](WO4_PC_FORMAT.md), [Ultimate](WO4_ULTIMATE_PC_FORMAT.md) |
| `SW5.exe` / Samurai Warriors 5 | Native revision39 slot-zero castle/menu editor: Gold, Stock EXP, shared Skill Points, Stock Weapon Mastery, Lumber, Mineral and Fabric; searchable officer, weapon and mount records | Original supplied save/VDF resolve owner-dependent decryption. Full serializer/current-copy selection and seven resource bounds are proved; checkpoints, allocations, facilities and story preserved. Battle/resume states, other slots/revisions, growth, equipment, friendship and reward dependencies need separate proof. [Checklist](SAMURAI5_PC_FORMAT.md) |
| `WARRIORSAbyss.exe` / Warriors: Abyss | Native revisionA4 PC gameplay Karma Embers editor and searchable read-only persistent recruitment records | Supplied gameplay/system/VDF resolve owner decryption; complete category geometry and no native body checksum independently proved. System revision77 remains separate research. Recruitment, permanent levels, Records-of-Sin conversion, customization and reward dependencies need controlled pairs/catalogs. [Checklist](ABYSS_PC_FORMAT.md) |
| `DW9Emp.exe` / Dynasty Warriors 9 Empires | Source-backed current PC SYSTEMDATA editor: manual existing ordinary inventory quantities; searchable 800 native item IDs and 900 read-only custom-officer records | Exact native plaintext serializer/revision/size recovered; no save checksum/cipher/owner key in this path. A genuine current PC SYSTEMDATA file, active catalog/ownership evidence and controlled pairs remain missing. Campaign saves and older layouts are unqualified. [Full checklist](DYNASTY_RESEARCH.md#dynasty-warriors-9-empires) |

The native editors above retain existing branding/themes and
copied-save workflows: automatic backups, staged Undo, Review Changes,
source-change detection and atomic Save As to a new destination. Story
completion is separate from resource/stat edits. SW4 DX's guarded content unlock
does not complete a story or create a missing starter weapon. Unregistered
candidates have no editable library card or gameplay writer.

## Implemented limits and dependency guards

| Game | Validated bounds and safeguards |
| --- | --- |
| DW7 XL | Gold 999,999; health 1,000; attack/defense 1,400; power/speed 100; skill points 9,999. Native NPC records remain unchanged. Active weapon is a choice, excluded from Max, and must resolve to an already equipped owned valid record. Qualified owned unlearned positive seal meters permit reductions; purchased-skill flags remain inspection-only. The native sample has no eligible positive unlearned meters; see the depth checklist. |
| WO3 Ultimate | Health/Musou/attack/defense 999; natural speed 180. Existing higher values, including the acquired sample's speed 200, survive Max. Resource limits are published edit bounds rather than recovered natural clamps, so growth points/gems/orbs/materials are excluded from Max. Standard proven attribute ranks are 1–10; Verity is rank 1. Empty/unknown weapons, zero/unknown attributes and unsupported slot layouts are read-only; slot changes cannot hide or activate dormant attributes. |
| SW4 DX | Gold 999,999 and eight gems 99. Base stat edits use the stored u16 range and have no Max because growth caps are unresolved. Skill Max respects each existing ceiling, unusual values and locked state; IDs/ceilings are preserved. Equip selection stays in the officer's occupied own pool. Character unlock requires an occupied qualified equipped weapon and applies the native new-character marker without setting stage completion. |
| DW9 Empires | Current SYSTEMDATA only, exact `0x2F1C28` size and `0x210602F0` revision. Existing item quantities 1..999 edited manually; zero/higher entries, identities and acquisition state preserved. All inventory controls excluded from Max; campaign currency and custom-officer records are not writable. |
| PW4 | Beli 999,999,999; eligible current coin quantities 999. Only native IDs 0–399 with an obtained flag and positive earned history qualify. Max preserves higher values. Ownership, earned/spent history, lifetime Beli and growth rewards remain unchanged; no empty coin record is created and no guessed character/rarity name is assigned. |
| Orochi Z | Stock EXP 99,999; 96 officers' stored base attack uses ID-specific floors 70..120 and ceilings 400..480. Existing weapon attack bonus 20, attribute capacity at least owned-mask bit count and at most eight, owned ranked effects 1..10 stored as level minus one. Unknown/empty weapons, malformed masks/capacity and enum5 remain read-only. Max preserves higher values; masks, alchemy, equipment, collections, officer EXP/other four stats and story stay untouched. |
| All-Stars | Available gold 9,999,999 in each existing slot whose native selected-hero identity is 0..99. Existing 45 material IDs expose only positive ordinary quantities for manual 1..9,999 edits; zero/higher stacks remain read-only and material Max is disabled. Empty/unknown slots are not created. Gold Max preserves higher balances; lifetime earnings, acquisition, purchases/training/rewards and progression remain unchanged. Only current F4 revision accepted; all ten encrypted fingerprints and campaign selections validated. |

## Deeper mechanics: investigated coverage and blockers

These rows summarize the important mechanics in the linked checklists. Grouped
categories retain separate stored values, rewards and dependencies; a currency
edit does not simulate a purchase, fusion, promotion or stage reward.

| Game | Further systems requiring specific evidence |
| --- | --- |
| DW7 XL | Named roster/equipment, seal grants/learning completion and system seal rewards require native parameter/localization tables. Qualified unlearned seal-meter reductions do not grant learned flags. Purchased skills/EX unlocks need officer definitions, costs, prerequisite masks and stat rewards. Guardian beasts, titles, bonds/sworn allies, Story/Conquest/Legend/town progression and gallery require ownership/record identities and reward pairs. No persistent level/EXP mapping has been proved; another game's level field is not substituted. |
| WO3 Ultimate | Stored level/EXP/promotions are inspected. Qualified originally promoted officers expose unallocated upgrade stones, and owned ordinary-item slots permit guarded equipment choices. Level reset, allocated stones and promotion rewards remain blocked. Proficiency/abilities, compatibility/reinforcement and derived attack need exact semantics and grade caps. Full orb/material names, recipes, attribute acquisition/fusion, unowned or special-item equipment, mounts, bonds/companions, costumes/colors, Story/Redux/stage rewards, Gauntlet/keystones/allies, Duel cards and gallery need native ID tables and one-action acquisition/equip/clear pairs. |
| SW4 DX | Level/EXP/proficiency are inspected; external threshold/growth tables block consistent writes. Rare/DLC weapon creation, skill replacement and ceilings need templates and exclusion rules. Personal skills/gauges, consumables, mounts, custom character appearance/names, Chronicle goals/mentors/friendship/companions/biographies and stage/rare-weapon/collection unlocks need qualified asset dictionaries or controlled pairs. Historical kills/spending remain records rather than spendable resources. Older migration revisions need genuine samples and layouts. |
| PW4 | Coin rarity/name catalogs, acquisition and growth-map spending remain separate from quantity edits. Character/DLC unlocks, beginning/character Growth Maps, derived stats, skill ownership/equips/specials, Soul Maps, costumes, Dramatic/Free/Treasure Log, DLC challenges and gallery need native named record maps and prerequisite/reward pairs. System saves, three-/four-step regional variants and revision 22 migration are unqualified. Conventional weapon fusion/mount controls are not invented for this title. |
| Orochi Z | Stock EXP, native bounded base attack and existing weapon bonus/capacity/owned ranks are implemented. Exact officer names require native `/etc/unitbase.bin` association; embedded surname/given fragments cannot be indexed directly. Other four stats, level transitions and proficiency remain protected: native growth uses nonserialized RNG and linked skill/costume/wallpaper rewards. Coherent already progressed officers have manual EXP edits confined to their opened level; no automatic level transition or Max. New weapons/attributes and full fusion transactions require collection/ownership/cost maps; alchemy requires recipes, crafted stock and equipped-mask dependencies. Treasures are permanent prerequisites, not consumable material counts; mounts derive from Cavalier skill/faction rather than an invented inventory. Story/Dramatic/Versus/Survival and gallery need labelled eligibility, result and reward pairs. |
| All-Stars | Spendable slot gold, existing material quantities, existing own-pool Hero Card selection and lifetime-gold inspection are implemented separately; edits do not grant material acquisition, training, purchase history or rewards. Material names need native ID association; community alphabetical lists do not establish storage order. Hero levels/EXP/actions differ from battle-local Bravery; hero cards differ from conventional weapons. Card rarity/attack/affinity/elements/traits/material consumption, special gifts and unowned equipment, regard/Hero Skills, requests, faction rosters/Opoona/ending routes and gallery need record IDs, legitimate bounds and dependency pairs. Regard, card affinity and temporary team effects must remain distinct. Earlier revisions need native layouts/migration controls. |
| WO4 / Ultimate | Matching supplied DLLs and native copies qualify separate original 20180720 and Ultimate 20200101 resource/SP profiles, existing element stock, Skill Orb reductions and Ultimate unspent Upgrade Stones. Further officer EXP/level/promotion transitions, allocated stones, weapon creation/equipment/fusion, Infinity crafting, camp upgrades, bonds/support, sacred treasures/deification, mounts and stage/gallery rewards need native catalogs and controlled action pairs. Older Ultimate 20191201 needs separate full serializer proof; base and Ultimate caps differ. [Original](WO4_PC_FORMAT.md), [Ultimate](WO4_ULTIMATE_PC_FORMAT.md). |
| SW5 | Supplied owner context and native slot-zero revision39 castle/menu copies qualify complete framing and seven resource controls. Battle/resume saves, other slots/revisions, officer growth/unlocks, allocated skills/mastery, weapon crafting/attributes/equipment, horses, facilities, Musou/Citadel rewards, bonds and gallery need separate current-copy/layout and dependency proof. Trial saves remain distinct. [Checklist](SAMURAI5_PC_FORMAT.md). |
| Abyss | Supplied owner context and revisionA4 gameplay copies qualify complete framing, Karma Embers and read-only recruitment records. Recruitment grants, permanent growth/transcendence, Unique Weapons/limit breaks, emblems/traits, tactics/formations, Records-of-Sin conversion, clear rewards, customization and DLC need catalogs and controlled persistent action pairs. System revision77 and run-resume state remain separate; in-run levels and computed team totals are not assumed permanent scalars. [Checklist](ABYSS_PC_FORMAT.md). |
| DW9 Empires | Current SYSTEMDATA quantity pool and 900 CAW records are mapped; active item-name/category/ownership evidence, genuine current fixture and controlled pairs remain necessary. Campaign metadata/full layout precede gold/rations/army, merit/reputation, officer growth, trained/inherited compatibility, artifacts/gems/secret plans, kingdom/territory/stroll progression, bonds/spouse/children/recruitment, mounts/arrows/furniture and gallery. Read-only CAW inspection does not qualify inheritance, stat or appearance writes; older revisions require separate profiles. |

## Additional games and existing-editor expansion

| Game | Delivered scope | Remaining blockers and checklist |
| --- | --- | --- |
| Dynasty Warriors 6, original Windows PC |41 named one-way playable unlocks, four combat stats for existing qualified horses (0..500), named existing weapon element choices and officer/weapon/horse inspection | Genuine native save and public author reload evidence support mapped categories. Level/EXP-derived rewards, skill-tree bits, weapon bonus bounds/equips, horse growth/transform/skill masks, stages and gallery need native routines or controlled pairs. Other platforms and DW6 Empires are separate formats. [Checklist](DW6_RESEARCH.md) |
| Dynasty Warriors 7, PS3 |US/EU copied decrypted APP.BIN: manual gold and 62 officer stat/skill-point records | Three genuine public exports qualify exact profile and surgical edits; no edited console load. Published targets do not justify Max; named roster, seals/skills/beasts/equipment and unlock/progression/reward maps need PS3 routines or controlled pairs. [Checklist](PS3_EXPANSION.md) |
| Samurai Warriors 4, PS3 |US copied decrypted DATA.BIN: manual gold and eight gems, with read-only paired proficiency level/EXP inspection and four gameplay checksums | Genuine regional exports qualify US profile and distinguish rejected Japanese layouts. Natural caps, proficiency level/EXP thresholds and growth dependencies, weapons/skills, Chronicle/bonds/mounts and unlock/reward maps remain unresolved. External console PFD signing/import is separate. [Checklist](PS3_EXPANSION.md) |
| Ken's Rage 2, EU PS3 | Decrypted `DATA.BIN` beside `BLES01801` `PARAM.SFO`; manual locked-gallery unlocks and collection inspection | Two genuine complete exports validate six CRC32 checks and unchanged GUI/backup/restore. Genuine galleries are already unlocked; surgical unlock tests are procedural. Growth, scrolls and missions need controlled pairs. Apollo reimport/resign and actual edited console loading remain external/unverified. [Evidence](LICENSED_MUSOU.md) |
| Dynasty Warriors: Gundam, US/EU PS3 | Decrypted `DATA.BIN` beside original `PARAM.SFO`; learning-only native skill flags on six qualified level-30 pilots; EXP/levels/equipment inspection | Four genuine exports qualify exact framing and three byte sums; native skill additions preserve equipped references and unknown bits. EXP/derived stats, parts, other pilots and mission/reward maps require independent evidence. Apollo reimport/resign and actual game loading remain unverified. [Evidence](LICENSED_MUSOU.md) |
| Ken's Rage, US/EU PS3 | Decrypted `DATA.BIN` beside recognized original `PARAM.SFO`; positive existing base-fighter skill-point balances | Two genuine files qualify header profile and published fields with surgical byte preservation. Gameplay integrity is not independently established; PFD remains external. Meridian Chart, ownership, growth and mission maps and console acceptance require further proof. [Evidence](LICENSED_MUSOU.md) |
| Gundam 2 / 3 / Reborn and other assigned platforms | Public patch/source leads only; no registration | Need independently qualified complete extracted/decrypted gameplay files, native identity/revision/length/integrity and controlled system-specific growth, equipment and reward pairs. [Exact inputs by title/platform](LICENSED_MUSOU.md) |
| Dynasty Warriors 7 Empires, PS3 |US copied decrypted SYSTEM DATA.BIN: manual bonus points | Genuine native system export qualifies exact 121,030-byte revision `0x12072200` and surgical edits. Campaign PLAY files, currency/army/fame/abilities, weapon/item/mount ownership, relationships, territories and progression need distinct profiles and dependency maps. Bonus-point edits preserve bought/unlocked rewards; Max is disabled. [Checklist](PS3_EXPANSION.md#dynasty-warriors-7-empires-us-ps3-system-profile) |
| Dynasty Warriors 8 Empires, US PS3 SYSTEM | Manual existing custom-horse Body Type; searchable native horse records | Genuine SYSTEM envelope/checksum and all 150 PS3 horse identities independently qualified; four ordinary occupied rows writable in the acquired sample. Campaign resource ownership/order, other sliders, stats/abilities/equipment, rewards and console loading remain separate blockers. [Checklist](DW8E_PS3.md) |
| Warriors Orochi 3 Ultimate, US PS3 NPUB31505 | Manual unallocated growth points and gems; read-only officers, weapons and inventory inspection | Two genuine Ultimate exports qualify exact native PS3 markers and original metadata; firsthand US direct-edit success report supports these two fields. Other resource/stat/fusion/progression writes and full native integrity research remain blocked. No local console load. [Checklist](WO3U_PS3.md) |
| Hyrule Warriors, Wii U |Rupees, existing named materials/map cards, qualified weapon stars and ordinary seal KO countdowns; named character/weapon/skill inspection | Two independently shared genuine APP.BIN exports qualify the observed profile; progression curves, badge prerequisites, ownership/equips, special collection seals, stage/gallery dependencies and other layouts require further qualification. [Checklist](HYRULE_FORMATS.md#wii-u-coverage-checklist) |
| Hyrule Warriors: Age of Calamity, Switch |Rupees bounded by opened lifetime total, discovered named materials/trophies/DLC reports, existing weapon protection and named weapon/seal inspection | Independently shared genuine svdt qualifies the observed profile; character/weapon growth coupling, cap quests, seal/fusion/polishing rules, special collectibles, ownership/DLC and stage/quest/gallery rewards remain unresolved. [Checklist](HYRULE_FORMATS.md#age-of-calamity-coverage-checklist) |
| Hyrule Warriors: Definitive Edition, Switch |Manual rupees and existing ordinary named material quantities; qualified existing normal/Legendary weapon stars with natural 0–5 Max and ordinary seal KO decreases; read-only named character, fairy-food and weapon/skill records | Genuine publicly shared modified native zmha.bin qualifies observed 252,132-byte marker/size and surgical edits. Resource controls exclude Max; Master Sword, special/unknown seals, weapon identities/state/power/equips and all unknown bytes remain intact. Discovery/food/fairy growth, progression, fusion, maps and rewards need separate ownership/dependency proof. [Checklist](SWITCH_WARRIORS_RESEARCH.md) |
| Fire Emblem Warriors, Switch |Manual gold and positive ordinary drops, existing generic weapon stars and ordinary-seal KO decreases; named characters/weapons and special-material inspection | Genuine publicly shared modified 1.5.0 native scenario qualifies observed94,892-byte header/size and surgical writes. Resources exclude Max; special scrolls/opus/essences/Master Seals, unique/amiibo stars, True Power/Legendary seals, character growth/crests, bonds/roster/DLC and Story/History rewards remain read-only until exact caps, ownership and dependencies qualify. [Checklist](FIRE_EMBLEM_WARRIORS_FORMAT.md) |
| Dynasty Warriors 8 Empires | Strict source-only native SystemSave and Battle/Empire/Quick codec: exact sizes, title revision, applicable checksums and unchanged roundtrips of five files from one public bundle | No gameplay writer/card. Conflicting currency order and unqualified officer/array identities block resources/troops/stats/merit, aptitude/stratagems, equipment, relationships/offspring, custom content, territories and collections. Native executable/parameter data or controlled pairs required. [Checklist](DYNASTY_RESEARCH.md#dynasty-warriors-8-empires) |
| Nioh 3, Windows PC | Native USER Amrita/Gold deductions and quantity reductions for seven known common item IDs in qualified item-box/storehouse arrays; equipment level, pre-forge and reinforcement inspected separately | Genuine revisions 0x01030001/0x01040000, actual native tags/lengths/boundaries, cipher and whole-body checksum qualify surgical edits. Capacity/acquisition, currency increases/purchases, growth/skills, equipment transformations, affixes, Scrolls and story/reward dependencies remain blocked. No flags cleared. [Checklist](NIOH3_RESEARCH.md#coverage-and-precise-blockers) |
| Ninja Gaiden II, original Xbox 360/Xenia | Extracted revision-6 story editor: manual Yellow Essence, existing unique ordinary consumable/ammunition reductions, searchable inventory and separate Karma inspection | Twenty-two genuine stories plus matching native content in one original-title CON qualify framing, native word checksum and records. CON/STFS is rejected; weapon/health/Ninpo, ownership, rewards and system progression remain blocked. [Checklist](NINJA_GAIDEN_RESEARCH.md) |
| Dynasty Warriors 8 XL | Existing native editor expanded with four weapon-action aptitudes for 82 officers (25/50/75/100), qualified existing weapon affinity choices (0/1/2), and read-only 838 physical ally records | Affinity is a choice excluded from Max; numeric Heaven/Earth/Man association is not guessed. Weapon attack/identity/equips, skill ownership, ally recruitment/rewards, mounts, Ambition facilities, story/gallery and costumes need qualified limits/IDs and controlled dependencies. Existing resource/stat/attribute editing retained. [Checklist](DW8_COMPATIBILITY.md#coverage-checklist) |
| Atelier Sophie 2 | Existing tagged Steam PC 1.08 editor expanded with searchable occupied inventory/equipment inspection and remaining-use edits/refill bounded by each record's existing positive capacity; existing quality and Sophie/Plachta alchemy EXP edits retained | Independent genuine native file and game-load qualification remain pending. Traits/effects/stat bonuses need catalogs and per-item applicability; item creation, capacity, combat skills/AP, alchemy levels/recipes/catalysts/essences, resources, money/bonds/quests/story/exploration require native ownership, threshold and reward pairs. Alchemy EXP has no Max. [Checklist](SOPHIE2_COVERAGE.md) |
| One Piece: Pirate Warriors 3 | Existing genuine-qualified stats, special bars and equipped skill-slot editing retained; added currency/coin/progression mechanics coverage and PC runtime evidence review | No new uncertain currency/coin/story writer. Current/earned Beli save-to-runtime correspondence and legitimate cap remain unproved; two-byte coin semantics, limit breaks, skill acquisition, Kizuna progression, costume ownership, Legend/Dream Log and event/shop gallery require controlled pairs. [Checklist](PW3_COVERAGE.md) |

## Other investigated game leads

### Additional Musou PC lane

| Game | Delivered scope and exact remaining inputs |
| --- | --- |
| Samurai Warriors 4-II, Windows PC | Registered native revision `0x31A4` editor; manual current gold, five held strategy-tome resources, existing standard-officer stored base stats, qualified existing own-pool weapon selection and attached attribute magnitudes, and occupied-mount combat stats. Two independent genuine saves and static native-editor inspection qualify exact checksum spans and record ownership. Unknown populated regions are preserved. Need natural limits, growth/skill dependencies, weapon fusion/acquisition, mount training/equipment, customization, friendship, collections and reward maps, plus edited game loading. [Format and full checklist](SW4II_FORMAT.md) |
| Samurai Warriors: Spirit of Sanada, Windows PC | Two genuine gameplay copies and a system companion qualify distinct lengths, original-seed outer cipher/word sum and byte-exact unchanged reconstruction. Unregistered read-only codec rejects modified envelopes. Need matching `SWSanada.exe` serializer or equivalent PC format research, title/build and inner integrity, existing-record ownership and controlled growth, weapon, inventory, friendship, exploration and reward pairs. [Full checklist](SANADA_PC_RESEARCH.md) |
| Dynasty Warriors 9 original, Windows PC | One genuine bundle acquired with distinct PLAYERDATA and thirteen STORYDATA files; native integrity and record ownership remain unqualified, so no adapter or gameplay writer. Need matching original-game serializer/integrity research, full/trial/build/region/DLC controls and one-action resource, growth, equipment, horse, relationship, exploration and reward pairs. This is separate from 9 Empires. [Full checklist](DW9_ORIGINAL_PC_RESEARCH.md) |
| Dynasty Warriors 8 original-only Windows editions | No distinct original-only Windows product/native format qualified. The acquired XL converter fixture passes the existing XL integrity and unchanged roundtrip; it does not justify another adapter. Reopen with an identifiable official original-only Windows product/build and a genuine native save. Microsoft Store DX is an XL edition requiring separate compatibility evidence. [Edition matrix](DW8_ORIGINAL_PC_SCOPE.md) |
| Bladestorm: Nightmare, optional Windows candidate | Genuine personal/campaign files acquired, but no strong PC identity/integrity/field source; the additional-game implementation gate is unmet. No adapter or support claim. Need native PC serializer research and labelled untouched files with controlled actions. [Evidence gate and mechanics](BLADESTORM_PC_RESEARCH.md) |

The Gust expansion adds three separately qualified editors: original Sophie
resources/occupied quality, original Ryza 2 quality within its base cap, and
Fatal Frame II Remake shared system Photo Point reductions. See
[Sophie](SOPHIE_PC_FORMAT.md), [Ryza](RYZA_FORMATS.md) and
[Fatal Frame II](FATAL_FRAME2_REMAKE_FORMAT.md) for field evidence, mechanics and
test distinctions. Genuine-file GUI edit/Undo/Review/Save As/backup/restore checks
passed for all three; actual edited game loading remains untested.

[Arland](ARLAND_DX_RESEARCH.md), [Dusk/Nelke](DUSK_DX_RESEARCH.md) and
[Blue Reflection](BLUE_REFLECTION_RESEARCH.md) now have genuine gameplay leads
and precise remaining codec, integrity or semantic blockers. Rorona/Meruru have
unregistered read-only layout inspectors. Totori DX PS4 title/Cole evidence does
not establish Totori PC support or safe internal integrity handling. Ayesha PS3
and Sophie 2 adapters are unchanged by this Gust expansion.

| Game | Result and exact remaining input |
| --- | --- |
| Dynasty Warriors 5 Empires, Xbox 360 | No registered writer. No genuine extracted native profile, reusable source or complete integrity; turn/Delegate and shop dependencies remain unqualified. External STFS rebuilding/resigning would remain necessary. [Exact inputs](XBOX360_EXPANSION.md) |
| Dynasty Warriors 6 Empires, Xbox 360 | No registered writer. Native ruler/officer campaigns, balance/gem ownership/order and checksum source missing. External STFS rebuilding/resigning would remain necessary. [Exact inputs](XBOX360_EXPANSION.md) |
| Dynasty Warriors 7, Xbox 360 | No registered writer. Native Conquest export and integrity/record map missing; old download listing now returns a sunset page. External STFS rebuilding/resigning would remain necessary. [Exact inputs](XBOX360_EXPANSION.md) |
| Samurai Warriors 2, base, Xbox 360 | No registered writer. Genuine hashed STFS extraction and observed additive diagnostics implemented. Native region/revision, complete checksum coverage and money/record ownership still block a writer. External STFS rebuilding/resigning would remain necessary. [Exact inputs](XBOX360_EXPANSION.md) |
| Samurai Warriors 2 XL, Xbox 360 | No registered writer. Distinct XL native export and title-update/revision/integrity proof missing; base-game bytes and advertised container basenames do not qualify XL. External STFS rebuilding/resigning would remain necessary. [Exact inputs](XBOX360_EXPANSION.md) |
| Warriors Orochi, Xbox 360 | No registered writer. Native Xbox export/integrity and shared Growth Points versus officer EXP/weapon ownership proof missing; GameFAQs aggregates other platforms. External STFS rebuilding/resigning would remain necessary. [Exact inputs](XBOX360_EXPANSION.md) |
| Warriors Orochi 2, Xbox 360 | No registered writer. Listed genuine Xbox download requires login. Native integrity and growth/proficiency/fusion/equipment/stage dependency proof missing. External STFS rebuilding/resigning would remain necessary. [Exact inputs](XBOX360_EXPANSION.md) |
| PS4 SW4 DX/SW5/WO4 commercial-editor leads | No PS4 profile or writer. Need legally obtained decrypted gameplay copies, exact title/build, native identity/integrity and independent semantic maps; original source and licence/permission are prerequisites for implementation reuse. No proprietary binary is redistributed. [Supplier checklist](REMAINING_INPUTS.md) |
| WO3 Ultimate, other PS3 patch profiles | NPUB50173 and NPEB02052 patches remain leads, separate from qualified US NPUB31505. Matching genuine exports and region/revision/integrity qualification are required before another adapter; no PC fallback. [Checklist](WO3U_PS3.md) |
| Atelier Totori DX, Steam PC | No gameplay adapter. Published Cole offsets lack disk identity/revision/integrity, and a mislabeled download was Rorona DX. Need complete app 936180 gameplay slot plus SYSDATA and unchanged control; installed A12V-prefixed executable would enable static loader/writer analysis. Inventory/equipment/synthesis/traits, adventurer licence/exploration, friendships/events/calendar/endings and collections have separate detailed blockers. [Checklist](TOTORI_PC_RESEARCH.md) |
| Samurai Warriors 2 HD with Xtreme Legends, Japanese PS3 | Bounded money/partial-checksum and three EXP/weapon-anchor probes only. No genuine NPJB00439 full export/header/revision/all-integrity proof; ownership, growth/skills, guards/horses, modes/story/collections remain blocked. Matching partial sums cannot qualify this profile. [Checklist](SW2HD_PS3.md) |
| Dynasty Warriors: Strikeforce, US PS3 | Genuine modified exports qualify anonymous occupied-record, 42-officer and 196-storehouse inspection with corrected eight-byte ID prefix. Native integrity/revision and acquisition/growth/equip synchronization remain unresolved; no gameplay writer. [Checklist](STRIKEFORCE_PS3.md) |
| Dragon Quest Heroes II, PC | Genuine complete `SAVEDATA.BIN` acquired; plaintext-looking profile; the uploader describes multiple progressed slots, but native slot boundaries remain unqualified. Native header/integrity, slot boundaries and resource/growth/equipment/reward maps need the matching serializer or controlled native pairs. No gameplay adapter. [Checklist](OTHER_KOEI_PC_RESEARCH.md) |

| Samurai Warriors 2 HD, Japanese PS3 | Unregistered read-only candidate money/checksum inspection; no gameplay profile or writer. Need decrypted NPJB00439 DATA.BIN, complete size/header/revision and native record identities. Growth/skills, weapons/attributes, guards/horses, Survival/story/stages and collections require mappings and dependency pairs. [Checklist](PS3_EXPANSION.md#totori-dx-and-samurai-warriors-2-hd-investigation) |
| Dynasty Warriors: Strikeforce, PS3 | Genuine public exports were obtained/decrypted, but state-like first bytes do not establish a revision and published slot/storehouse facts do not prove native integrity/ownership. Need title/revision/integrity qualification and controlled progression/acquisition/equip pairs before resources, storehouse, growth/abilities or story editing. [Checklist](PS3_EXPANSION.md#further-ps3-leads-investigated) |
| Dragon Quest Heroes I/II, Windows | DQH1's genuine complete `SAVEDATA.BIN` independently decodes as LZP2; DQH2's complete unwrapped file was reacquired. Neither qualifies title/revision, native integrity, slot identities or surgical edits. Need matching Windows serialization/integrity evidence and controlled resource, growth, skill, equipment and accessory-alchemy pairs. DQH2 vocation growth, companion growth and weapon proficiency are separate systems. No gameplay adapters. [Exact evidence and inputs](LICENSED_ACTION_RPG_STATUS.md) |
| Fate/Samurai Remnant, Windows | No complete genuine native save or matching serializer acquired. Full/demo cloud paths and transfer rules do not qualify interchangeable profiles. Need exact edition/build, original save folder, native identity/integrity/serialization and controlled resource, Iori/Servant progression, mounting and workshop pairs. Story/ownership/reward transitions remain separate. No gameplay adapter. [Exact evidence and inputs](LICENSED_ACTION_RPG_STATUS.md) |
| Berserk and the Band of the Hawk; Attack on Titan 1/2, PC | Genuine complete native files qualify the observed Koei word ciphers, native u16 checksums, unchanged ciphertext roundtrips and corruption rejection. Berserk/AoT1 use three advances, AoT2 PK uses one; no semantic gameplay fields are qualified. Runtime trainers and LINKDATA asset editors do not supply disk-save maps. Matching serializers or controlled progression/inventory/equipment/reward pairs required. No gameplay adapters. [Checklist](OTHER_KOEI_PC_RESEARCH.md) |

| Dragon Quest Heroes II, PC | Genuine complete `SAVEDATA.BIN` acquired; plaintext-looking profile; the uploader describes multiple progressed slots, but native slot boundaries remain unqualified. Native header/integrity, slot boundaries and resource/growth/equipment/reward maps need the matching serializer or controlled native pairs. No gameplay adapter. [Checklist](OTHER_KOEI_PC_RESEARCH.md) |
| Berserk and the Band of the Hawk; Attack on Titan 1/2, PC | Reproducible unregistered read-only diagnostics qualify the three genuine complete contributor files' observed outer Koei ciphers/u16 sums and unchanged ciphertext reconstruction. Berserk/AoT1 use three advances, AoT2 PK uses one. Native/procedural regressions also demonstrate additive checksum collisions; title/revision, body integrity and semantic records remain unqualified. No gameplay adapters. Native Windows serializers or source-backed record maps and controlled action pairs are needed. Separate [Berserk](BERSERK_PC_RESEARCH.md), [AoT1](AOT1_PC_RESEARCH.md) and [AoT2](AOT2_PC_RESEARCH.md) checklists preserve accessory/Eclipse, first-game gear/skills and sequel customization/camaraderie/Territory Recovery distinctions. |

| Nioh / Nioh Complete Edition and Nioh 2 Complete Edition PC | Native decoding and strict read-only inspection; seven/four active flags retained. Native integrity consumers remain unresolved after public-source and mathematical candidate research. Console editions stay separate. [Checklist](NIOH_INTEGRITY_RESEARCH.md) |
| Stranger of Paradise, Epic launch PC / later SYSTEM reference | Genuine Epic revision-0x22020200 and Steam revision-0x23013100 USER/SYSTEM framing, plus a separate later source SYSTEM pair, implemented. Native gameplay integrity, unobserved builds and field/reward dependencies remain unresolved. [Checklist](SOPFFO_RESEARCH.md) |
| Ninja Gaiden Sigma / Sigma 2 / Ninja Gaiden 2 Black | Distinct edition/platform investigation. Seven Sigma PC gameplay files, 31 Sigma 2 Master Collection PC stories and 19 Black Steam files acquired; bounded descriptive/native/Unreal inspection and one Sigma 2/Black metadata CRC recovered. Native integrity remains unresolved; no gameplay card. Console variants need their own profiles. [Checklist](NINJA_GAIDEN_RESEARCH.md) |

## Prepared additional profiles

The unreleased source also implements DW5 Special Windows, DW8 Empires Windows
custom horses, Hyrule Warriors Legends 3DS, Persona5 Strikers Windows, Wo Long
Windows, Atelier Ayesha PS3 US/Japanese exports and Fire Emblem Warriors: Three
Hopes Switch exports. Each has a native-qualified dedicated profile, targeted
preservation checks and a mechanic checklist. See [the prepared update](PREPARED_UPDATE.md)
for the complete feature table and [the supplier checklist](REMAINING_INPUTS.md)
for further input needs. Their controls do not imply another platform, ownership
creation, automatic story completion or unqualified natural-cap bulk actions.

## Fire Emblem: Three Houses — separate Switch adapter

[Exact gameplay v13/v23 profiles](THREE_HOUSES_FORMAT.md) use independently
implemented native byte-sum integrity, original inventory/count qualification
and source-backed base-owner eligibility. Gold, twelve specifically identified
ordinary-equipment convoy quantities and finite durability have decrease-only
controls, all excluded from Max. Unknown/quest/relic/accessory/consumable/material
items, unknown/DLC owners and entitlement stay read-only. Qualified joined base owners also have instruction motivation and original learned/equipped ability choices. Eight public extracted
candidates have file validation; no clean exact-build/DLC-labelled control or
edited Switch game-load/re-save was available.

Read-only inspection distinguishes character EXP/stats, eleven proficiency
rank/EXP pairs and mirrors, class mastery/certification, ability/art ownership
and inactive equips beyond original learned loadout movement, barracks/equipped battalion copies and anonymous support-point
records. The [mechanics checklist](THREE_HOUSES_MECHANICS.md) lists prerequisite
and controlled-action inputs for each system, with main campaign, free revisions
and Cindered Shadows/Expansion Pass scope separately qualified. This title does
not use the Fire Emblem Warriors or Three Hopes parser.

## Validation boundaries and follow-up inputs

Regional/Special candidates remain separate from the supported inventory.
[DW6 Special](DW6_SPECIAL_REGIONAL_RESEARCH.md), [DW7 Special](DW7_SPECIAL_PSP_RESEARCH.md)
and [Orochi/Samurai PSP Special](PSP_SPECIAL_RESEARCH.md) have publisher product
evidence and, where acquired, metadata-only encrypted-envelope observations.
No authenticated plaintext, gameplay roundtrip or safe writer is qualified.
[Additional regional scope](REGIONAL_EDITION_SCOPE.md) tracks which apparent
differences are product branding, text encoding or demonstrably distinct native
profiles. DW5 Special's existing equipment editor remains one revision-3
Windows profile; its qualified header markers are now 0x00000003 and 0x00010003.
Regional product evidence does not imply interchangeable saves.

Genuine privately held copies qualify unchanged roundtrips and targeted file
edits for DW7 XL, WO3 Ultimate, SW4 DX and PW4. Existing DW8 XL/PW3 genuine-file
qualification is retained. DW8 Empires genuine PC SystemSave files qualify
existing custom-horse appearance edits; its campaign files qualify codecs only.
The separate US PS3 DW8 Empires SYSTEM horse adapter and
US PS3 WO3 Ultimate resource adapter have genuine no-op/surgical and Tk
qualification. WO3's public resource edit/load report is external evidence,
not a local game-load test or global integrity claim. Nioh 3 genuine encrypted/decoded USER
profiles and original Ninja Gaiden II extracted stories qualify targeted
gameplay-field edits. DW6 and PS3 DW7/SW4/DW7 Empires native public samples
qualify their specific profiles;
Wii U Hyrule Warriors and Switch Age of Calamity have independently shared
complete native exports as well as upstream reference examples.
Switch Definitive Edition and Fire Emblem Warriors use publicly shared modified
native files; hacked values are not treated as natural gameplay caps.
DW9 Empires is source-backed without a genuine current native fixture.
Sophie 2 uses procedural/differential layout tests. All-Stars and Z have
genuine native qualification and targeted gameplay-field edits; Abyss remains a
procedural owner-context candidate. Optional native tests skip honestly when their input is absent.

Format tests check bounds/dependencies, unknown-byte preservation, malformed
input, immutable snapshots and applicable native integrity. GUI and integration
checks exercise editing/search, Undo, Review Changes, backups, Save As and
themes. **No edited save was loaded and re-saved in an actual PC or console game
during this expansion.** Windows application build/smoke/package checks are
separate from that missing game-load validation; their results belong in the
release/build validation record, not an inferred claim of gameplay success.

The shared implementation preserves existing higher or unusual values,
preserves unknown ID bytes and exposes only independently qualified fields.
Storage ceilings and public cheat targets are not
automatically natural gameplay limits. Legitimate array/revision variations
are supported only when separately qualified; arbitrary foreign, migration,
console or modded layouts are rejected rather than repaired or normalized.

Exact filenames and edition-specific supplier requirements are listed in
[REMAINING_INPUTS.md](REMAINING_INPUTS.md).
Useful follow-up inputs are copied native saves with build/region/DLC labels,
an unchanged control, displayed values, and one action between before/after
copies (purchase, promotion, fusion, equip, recruitment, stage clear or unlock).
The supplied matching WO4 gameplay DLLs and SW5/Abyss original-owner context
resolved their previous decoding blockers. Further controlled action pairs and
catalogs qualify additional mechanics; a genuine current DW9 Empires SYSTEMDATA
file remains missing. Inputs stay private and do not belong in the source
manifest, test fixtures or release downloads.

Licence/provenance details remain in each game note and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Public editors, patches,
runtime tables and planners informed factual investigation; their offsets,
runtime pointers and asset IDs were not promoted to native mappings without
qualification. Restricted-source implementations and extracted catalogs are
not included in the expansion.

## Hunting and monster-development candidates

[Toukiden Kiwami](TOUKIDEN_KIWAMI_RESEARCH.md),
[Toukiden 2](TOUKIDEN2_RESEARCH.md) and
[Monster Rancher 1 & 2 DX](MONSTER_RANCHER_DX_RESEARCH.md) were investigated
separately from the Warriors, Team Ninja, Gust and strategy work. None qualified
a Windows gameplay writer in this pass. Public Toukiden archives provide
candidate file observations, without native revision/codec/integrity proof;
complete native Monster Rancher DX files remain missing. Their separate notes
record mechanics, source/licence evidence, unsuccessful qualification attempts
and controlled captures needed for each system. No new adapter, game card or
runtime metadata was added for an unqualified candidate.

## v1.71 additional native profiles

- [Original Ryza Switch](RYZA_SWITCH_FORMAT.md): existing ordinary quality 1–100, searchable inventory/equipment and read-only traits. Exact main-game revision, adjacent-value and ownership gates preserve synthesis/equipment dependencies. Original Ryza PC remains a separate blocked format.
- [DW8 XL US PS3 PSN](DW8XL_PS3_FORMAT.md): resources, stored officer stats, weapon-action aptitudes and existing weapon ranks; original PARAM.SFO binding and external Apollo reimport/signing. Other regions/disc editions remain separate.
- [DQB2 Steam PC](DQB2_PC_FORMAT.md): existing named medicine/seed reductions, searchable pockets/bag and read-only player/equipment. Complete CMNDAT framing and opaque native padding are preserved; world/STGDAT and growth dependencies remain read only.

Each linked checklist records implemented mechanics and specific blockers. Genuine-file and actual Tk tests establish file/GUI behavior; edited in-game loading has not been performed. No player saves, account context or downloaded binaries are public source or assets.

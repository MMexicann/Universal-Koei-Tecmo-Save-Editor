# Remaining inputs by game and platform

For the earlier 19-profile depth expansion, see [the current feature/blocker checklist](RICH_EDITOR_EXPANSION.md). In particular, a native enabled Wo Long battle-set rename pair and a controlled DW7 XL seal-learning action pair remain missing; their new controls have source/procedural/Tk evidence, and one native owned unlearned positive DW7 XL meter now has file-level reduction tests. Actual edited game-load/re-save remains a separate check.


## v1.9 additions: next inputs

| New profile | Implemented controls | Specific next evidence for deeper editing |
| --- | --- | --- |
| [Legend of Liu Bei, original Traditional Chinese DOS](REKO3_DOS_FORMAT.md) | Existing allied troop reductions and within-level EXP; 384-record inspection. | One controlled troop/EXP/level-up pair and successful edited game load; class, equipment and derived growth rules. |
| [ROTK III, original Traditional Chinese DOS](ROTK3_DOS_FORMAT.md) | Ordinary-officer abilities and owned-city gold/rice/commerce/military-supply reductions. | Complete occupied player campaign and displayed-value action pairs; rank, loyalty, armies and diplomacy dependencies. Initialized native reference is distinct from an occupied player save. |
| [Tenshouki PK, original Japanese Windows 95](NOBU6_PK_PC_FORMAT.md) | Existing district gold/rice/horse/firearm reductions and six inspectors. | Complete occupied native player campaign, build label and one district purchase/reward pair; officer/army/ownership relationships. |
| [Gundam Reborn, EU/JP PS3](GUNDAM_REBORN_PS3_FORMAT.md) | Money and existing Amuro/Kamille Team Point reductions; resource inspection. | Named material-use, pilot-skill, plan-fusion/equip and reward pairs with original PARAM.SFO. |
| [Gundam 3, US PS3](GUNDAM3_PS3_FORMAT.md) | Money reductions; lab EXP/license inspection. | Purchase and lab progression/equipment pairs; console load/re-save confirmation and other-region writer proof. |
| [TRINITY, US PS3](TRINITY_PS3_FORMAT.md) | Money reductions; SP and named stat-word inspection. | Money purchase/load check plus stat-level/skill purchase pairs proving stored-versus-derived values. |
| [Original Totori](TOTORI_PS3_FORMAT.md), [Meruru](MERURU_PS3_FORMAT.md), [Rorona](RORONA_PS3_FORMAT.md), PS3 | Cole reductions; named character and system inspection. | Original-edition purchase/synthesis/equip/level pairs and edited load/re-save; PS3 evidence does not qualify DX or Plus. |
| [Sophie 2, PS4 CUSA28451 app 1.0](SOPHIE2_PS4_FORMAT.md) | Quality reductions for twenty-three named ordinary material identities; use refills for nineteen named battle-item identities within existing capacity; party/inventory/equipment inspection. | Synthesis/equip and wallet pairs; other item identities, trait/effect dependencies and edited game-load proof. |
| [Ninja Gaiden Black SYSTEM, original Xbox](NINJA_GAIDEN_BLACK_XBOX_FORMAT.md) | Restore numeric save-list order; inspect thirty slot timestamps. | Genuine SYSTEM.dat plus original EEPROM and successful load-order check. Story-slot inner integrity still needs separate evidence; story editing remains unregistered. |

Keep complete gameplay files and their original identity companions together in
private copies. Label the exact edition/build and make one ordinary in-game
action between before/after captures, with displayed values and unchanged control.
No account or player data belongs in a public contribution or release.

## v1.72 profile expansion inputs

| Profile | Exact useful next input |
| --- | --- |
| Atelier Ryza 2, original Nintendo Switch | Clean same-revision `data.dat` synthesis/equip pair with displayed quality and SP. The acquired modified starter proves SP reductions, but all existing quality records have nonzero adjacent values. Higher-cap progression, learned-node and trait/effect dependencies need separate pairs. [Details](RYZA2_SWITCH_FORMAT.md). |
| Dragon Quest Builders 2, original Nintendo Switch | Complete matching CMNDAT/STGDAT/SYSDAT slot copies with one labelled inventory, level/EXP, equipment or island action and unchanged control. Current native copies qualify existing medicine/seed reductions; they do not prove world or cross-file ownership changes. [Details](DQB2_SWITCH_FORMAT.md). |
| Romance of the Three Kingdoms II, original Chinese DOS | Original player-authored extensionless raw campaign, exact build and unchanged control; one labelled gold/rice or officer action pair and successful edited game load/re-save. Existing references establish the published layout, not independently shared player-save history. [Details](ROTK2_DOS_FORMAT.md). |
| Persona 5 Strikers, English Nintendo Switch | Complete same-profile `savedata` export with one labelled BOND purchase, Persona fusion/growth, equipment or reward action and unchanged control. Native resources/stacks are qualified; dependency-sensitive progression remains untouched. [Details](P5STRIKERS_SWITCH_FORMAT.md). |
| Dead or Alive 5 Plus, PS Vita (unregistered) | Complete decrypted original US `PCSE00235` or JP `PCSG00167` export, unchanged `sce_sys/param.sfo`, and locked-to-earned costume or one-setting pair with exact fighter/outfit and build. Cipher/checksums are qualified; Vita-specific persistent writable mappings are missing. [Details](DOA5_PLUS_VITA_RESEARCH.md). |

## Latest additional-editor profiles

| Registered profile | Exact next input for deeper editing |
| --- | --- |
| Berserk, EU PS Vita PCSB01085 | Decrypted `app0000.dat` / actual slot plus original `sce_sys/param.sfo`; one material purchase/use, gold gain/spend, level-up, accessory enhancement/equip or Eclipse reward pair with displayed values. Native US PCSE01034 exports are needed separately. Vita evidence does not resolve the Windows serializer. [Checklist](BERSERK_VITA_FORMAT.md). |
| Dead or Alive 5, original US/EU PS3 PSN | Native `SAVE_SYS.DAT` with unchanged original `PARAM.SFO`; a genuinely locked-to-earned costume pair identifying fighter and outfit, plus unchanged control. Current shared originals already have all mapped flags set, so targeted unlock tests use constructed derivatives. Other editions/title IDs need their own framing and mappings. [Checklist](DOA5_FORMAT.md). |
| Pokémon Conquest, North American Nintendo DS VPYT | Clean raw 256/512 KiB `.sav` copies with one labelled gallery stat observation or gallery/active-party, link, EXP, ability, evolution, currency, equipment or warrior action pair. HP/Attack/Defense IV component ordering is still unnamed; only Speed is independently identified. Other regions/ROM modifications need separate qualification. [Checklist](POKEMON_CONQUEST_DS_FORMAT.md). |

External Vita/PS3 reimport and signing remain the export tool's responsibility.
Actual edited game loading and re-saving are still needed for all three profiles.

## Five follow-up candidates

These are development investigations, not additional supported-game entries.
The existing public gameplay copies have been reacquired where available;
sending more unidentified complete saves alone will not resolve an unknown
native writer or checksum. Keep game binaries and original export metadata
private.

| Game and exact platform | Specific useful input | What it would resolve |
| --- | --- | --- |
| Samurai Warriors 2 with Xtreme Legends HD, Japanese PS3 | Complete decrypted **NPJB00439 `DATA.BIN` and its original `PARAM.SFO`**; exact edition/build, displayed money/level values, and a purchase or EXP before/after pair. | The matching XL gameplay layout, identity, complete section integrity and progression/equipment mappings. NPJB00464 Empires is a different game. [Checklist](SW2HD_PS3.md) |
| Atelier Rorona DX, Windows PC | Matching **`A11R_x64_Release_en.exe`** or **`A11R_x64_Release.exe`**, language/build label; alternatively a reproducible Cole-only or occupied-item offline edit followed by successful game load and re-save. | Native reader/writer and integrity handling. Twenty-seven genuine gameplay copies already establish the observed framing and early character/item leads. [Checklist](RORONA_DX_FORMAT.md) |
| Atelier Meruru DX, Windows PC | Matching **`A13V_x64_Release_EN.exe`** or **`A13V_x64_Release.exe`**, language/build label; alternatively a reproducible money/item offline edit followed by successful game load and re-save. Controlled purchase, synthesis and equip pairs help map dependencies. | Integrity of currency, character and item writes, separately from the author's successful but dependency-unsafe calendar tool. Seventeen genuine gameplay copies are already available. [Checklist](MERURU_DX_FORMAT.md) |
| Atelier Totori DX, decrypted PS4 CUSA14014 | Exact-profile game-internal save reader/writer evidence, or a reproducible Cole/item offline edit with successful reimport, game load and re-save; preserve original `PARAM.SFO` privately. | Native integrity and edit acceptance. The existing CUSA14014/GAMEDATA00 export already corroborates Cole, character and item-record geometry. PC tools and PS4 signing do not establish the inner checks. [Checklist](TOTORI_DX_PS4_FORMAT.md) |
| Berserk and the Band of the Hawk, Windows PC | Matching **`BERSERK.exe`**, build/language label, unchanged native control; before/after saves for a gold purchase, material use, accessory equip/upgrade or character EXP gain, with displayed values. | Disk linkage of gameplay records, native revision and any additional inner integrity. Three independent PC saves already pass the outer cipher/checksum and exact unchanged roundtrip. [Checklist](BERSERK_PC_RESEARCH.md) |

No executable is run during investigation. A controlled pair should perform
one ordinary in-game action between captures; trainer-modified resources and
complete story saves cannot isolate that action's stored values or dependencies.

## Additional Musou PC inputs

| Game | Exact remaining input |
| --- | --- |
| Samurai Warriors 4-II | Native `SAVEDATA0000.dat`–`SAVEDATA0004.dat` copies with exact Windows build/language/DLC, unchanged control and displayed before/after values. Revision `0x31A4` exact native checksums support manual resources/base stats, existing own-pool weapon selection/attached attribute magnitudes and occupied-mount combat stats. Need natural limits and controlled skill purchase/growth, weapon fusion/acquisition, mount training/abilities/unowned mount acquisition, customization, friendship, collection and reward pairs. Actual edited game loading remains untested. [Details](SW4II_FORMAT.md) |
| Spirit of Sanada | `SAVEDATA0000.dat`/`SAVEDATA0001.dat` and `SYSDATA.dat` are acquired; outer framing is tested. Need matching `SWSanada.exe` for static analysis or reliable PC serializer research, build/region/DLC labels, native title/inner integrity/record ownership, and separate Clan EXP, training, weapon skill, inventory, mount, friendship, exploration and reward pairs. [Details](SANADA_PC_RESEARCH.md) |
| Original Dynasty Warriors 9 | `PLAYERDATA/SAVEDATA.BIN` and thirteen `STORYDATA*/SAVEDATA.BIN` copies are acquired; preserve their different parent classes. Need matching original PC native serializer/integrity evidence, full-versus-trial/build/region/DLC-labelled controls and resource, officer allocation, gem/equipment, horse, relationship, discovery and claim-reward pairs. Empires input does not address this lane. [Details](DW9_ORIGINAL_PC_RESEARCH.md) |
| DW8 original-only PC edition | First establish an identifiable official original-only Windows product/build plus untouched native save. Existing Steam XL fixtures and shortened regional names do not qualify another native format. Actual Microsoft Store DX input would address a separate XL compatibility question. [Edition matrix](DW8_ORIGINAL_PC_SCOPE.md) |

The optional [Bladestorm PC candidate](BLADESTORM_PC_RESEARCH.md) has genuine
files but lacks the strong PC format source needed to satisfy the additional-game
gate; no adapter is registered.

## Supplier workflow

This is a supplier checklist for further development. **Current implementation**
means the unreleased development source; published support is the inventory accompanying the
installed GitHub release. The [supported-game list](SUPPORTED_GAMES.md) identifies
registered editors; a researched format does not automatically provide a card.

Supply copies outside live game/cloud folders. Include game, platform, region,
installed build and DLC; retain original filenames and relative folder structure.
For a paired sample, save once unchanged, perform **one** recorded action, then
save again and provide the displayed before/after values. Keep originals intact.
Never put player saves, game binaries/assets, owner identifiers or personal paths
in Git or public issue attachments. Owner-dependent inputs must be shared privately;
no account passwords or console credentials are needed.

## Original Windows PC additions

For the original 2008 Windows PC additions, see the separate
[SW2](SW2_PC_FORMAT.md) and [Warriors Orochi](WO1_PC_FORMAT.md) profiles:

| Original PC game | Implemented controls | Exact next evidence |
| --- | --- | --- |
| Samurai Warriors 2 | Money, owned officers' stored growth, acquired ordinary skills, existing weapon bonuses and same-owner weapon selection. | Revision-2 native `save.dat`, installed language/build, unchanged control and a single level-up, skill purchase, weapon upgrade/equip, guard hire/growth, mount purchase or Survival/story reward pair. A matching original Windows serializer and growth/parameter tables would qualify caps and dependent transitions; an edited copy must be loaded/re-saved in the original game. |
| Warriors Orochi | Shared Growth Points, qualified existing weapon bonus/capacity/acquired effect ranks and same-owner weapon selection. | Revision-2 native `save.dat`, installed language/build, unchanged control and one EXP allocation/level-up, proficiency/ability acquisition, equipped weapon/ability, fusion, unique-item or stage/reward pair. Matching original Windows weapon/character tables would qualify names and dependent transitions; an edited copy must be loaded/re-saved in the original game. |

Keep these inputs separate from SW2 HD/XL/Empires, console editions, Orochi Z
and later Orochi games. They do not substitute for either original PC format.

## Ten attached games

| Game | Current implementation / remaining gap | Exact useful files and next evidence |
| --- | --- | --- |
| DW7 XL Definitive, PC | Gold, officer stats/skill points, existing equipped weapon selection and qualified unlearned seal-meter reductions. Named equipment/skill rewards and progression need more evidence. | Native `save.dat` from `KoeiTecmo/Dynasty Warriors 7 DX/Savedata`; `inputmap1.dat`, `inputmap2.dat` and `inputmapm.dat` are separate input bindings. Matching `LINKDATA_CMN`, `LINKDATA_ENG`, `LINKDATA_CMN.IDX`, `LINKDATA_ENG.IDX`; one purchase, seal-learning, skill-allocation, equip or stage-reward pair. |
| WO3 Ultimate Definitive, PC | Stats/resources, existing weapon slots/attributes, unallocated stones on already promoted officers and owned ordinary-item equipment. Promotion/EXP transitions, fusion, special-item or mount acquisition, bonds and unlock rewards remain unresolved. | Native `SAVEDATA.BIN` from the qualified PC build; unchanged control and one promotion, growth allocation, fusion, equip, bond event or clear/reward pair. Matching installed parameter/localization files help name orbs/materials/weapons; preserve actual filenames. |
| Samurai Warriors 4 DX, PC | Resources, base stats, guarded standard-officer unlocks, existing own-pool equipment and attached skills. Growth and Chronicle/reward dependencies need evidence. | `SAVEDATA0000.dat`–`SAVEDATA0004.dat` gameplay copies; retain any companion system/input files under their original names. Current build/DLC labels, matching growth/weapon/skill catalogs and one level-up, proficiency, rare-weapon, mount or Chronicle event pair. |
| Pirate Warriors 4, PC | Revision15 one-step WW/JP/EA slot Beli and already obtained coin quantities. Current revision22 and other regions/system saves need separate profiles. | `OP4WINSLOT0000.dat` (or actual `OP4WINSLOT%04d.dat`) plus separate `OP4WINUSER.dat`; exact region/build/DLC. One coin gain/spend, Growth Map node, Soul Map, skill/equip or stage-reward pair. Include earlier/current unchanged copies to qualify migration. |
| Musou / Warriors Orochi Z, PC | Stock EXP, officer base attack and existing weapon attack bonus, attribute capacity and owned ranked effects. Own-pool equipment and coherent within-level EXP are also editable; level transitions, other stats, growth/rewards, new effects, alchemy and story remain protected. | Native revision2 `save.dat`, unchanged control and one growth-point allocation, level-up, fusion, attribute/rank, alchemy, proficiency reward or equip pair. Matching `LINKDATA*.BIN`/`.IDX` and `LINKDATA.ANS`/`.BNS`/`.CNS`/`.DNS`/`.ENS`, especially `/etc/unitbase.bin` and weapon/text tables, are needed for exact names and dependencies. Treasure acquisition differs from consuming a crafting material. |
| Warriors All-Stars, PC | Available gold and existing positive material quantities in campaign slots; lifetime earnings inspected separately. Existing own-pool Hero Card selection is also implemented. Card growth/properties, material names/acquisition, regard and route rewards remain unresolved. | Complete current revision `0x170302F4` `SAVEDATA.BIN`, including its global block and nine slot blocks. Build/DLC labels and one training purchase, currency gain/spend, named material acquisition/consumption, card acquisition/equip/customization, hero growth, regard event or route-clear pair; matching installed `LINKDATA.BIN` and `LINKDATA.IDX` qualify names, growth curves and card descriptors. A partial slot is insufficient for complete framing; older revisions need their own native control and migration evidence. |
| Warriors Orochi 4 / Ultimate, PC | Separate original 20180720 and Ultimate 20200101 native editors are implemented; supplied DLLs and copies resolved decoding/layout blockers. | Keep complete `SAVEDATA.BIN`/`SAVEDATAU.BIN` copies with exact base/Ultimate build and DLC labels. Provide an unchanged control and one labelled weapon/fusion/equip, EXP/level/promotion/allocated-stone, camp, Infinity or stage-reward pair. Matching localization/parameter catalogs would enable names and dependency maps. Older Ultimate 20191201 needs its matching native serializer/build. [Original](WO4_PC_FORMAT.md), [Ultimate](WO4_ULTIMATE_PC_FORMAT.md). |
| Samurai Warriors 5, PC | Revision39 slot-zero castle/menu saves now support seven resources; supplied original `steam_autocloud.vdf` resolves owner-dependent decoding. | Complete `SAVEDATA00.BIN` and original VDF, exact build/DLC and unchanged control; one labelled purchase/reward, officer growth/skill, weapon/mastery/equip, horse, facility or bond action pair. Other slots and battle/resume states need separate native copies and matching serializer selection. Trial `SAVEDATATRIAL.BIN` remains separate. [Checklist](SAMURAI5_PC_FORMAT.md). |
| Warriors: Abyss, PC | RevisionA4 `GAMEDATA00.BIN` now supports Karma Embers and recruitment inspection; supplied original VDF resolves owner-dependent decoding. | Matching complete `SYSTEMDATA.BIN`, gameplay slot and original `steam_autocloud.vdf`, exact build/DLC and unchanged control. Provide one labelled persistent recruitment, permanent growth, Unique Weapon, Records-of-Sin conversion or customization/reward action pair with displayed values; supply a separate run-resume control. System revision77 and other gameplay revisions need their own proof. [Checklist](ABYSS_PC_FORMAT.md). |
| DW9 Empires, PC | Current SYSTEMDATA existing quantity edits and read-only custom-officer records; genuine current save and campaign support remain missing. | `SYSTEMDATA/SAVEDATA.BIN` for current header `0x210602F0`, plus `CAMPAIGNDATA000/SAVEDATA.BIN` or actual slot000–029. Separate `sinpmap.dat` is input binding, not integrity. Matching `LINKFILE_*.BIN`/`LINKIDX_*.BIN`, locale catalogs and one item, monthly budget, artifact/gem, relation or custom-officer pair. |

Detailed mechanic blockers are in [the coverage checklist](EXPANSION_COVERAGE.md)
and its linked game notes. A filename or source offset alone does not qualify
another revision, an ownership grant or an edited game load.

## Additional implemented platforms and investigated screenshot leads

Console exports below must be **extracted/decrypted gameplay files**, preserving
native names. Encrypted PS3 PFD metadata and Xbox360 signed CON/STFS containers
need their own validated container handling; a PC/raw parser must not be applied
to them. Existing console export/import tools remain responsible for signing.

| Game/platform | Current status | Further input needed |
| --- | --- | --- |
| DW6 original PC | Named officer unlocks, horse combat stats and existing named weapon elements; other growth/equipment records read-only. | Native `save.dat` with one level-up/skill purchase, horse growth/transform, weapon acquisition/equip or clear/reward pair; original Windows executable and matching catalogs if available. Empires/Special/console files are separate formats. |
| Hyrule Warriors Wii U | Resource/card, weapon-star and ordinary-seal edits; progression/collection prerequisites read-only. | Extracted `APP.BIN`, build/DLC and one growth/badge, fusion, equip, special-seal, map-card or stage-reward pair. Preserve complete original export. |
| Hyrule Warriors Definitive Edition Switch | Manual rupees/existing materials, generic weapon stars and ordinary seal KO reductions; character/food inspection. | Extracted `zmha.bin`, unchanged unmodified control and one material/discovery, fairy-feed/refresh, growth, fusion/equip or map-reward pair. Other markers/sizes require separate profiles. |
| Hyrule Warriors: Age of Calamity Switch | Rupees, discovered resources and existing weapon protection; growth/seals/special collectibles read-only. | Extracted extensionless `svdt`, exact build/DLC; one level-up, blacksmith cap upgrade/fusion, protection/equip, collectible or quest-reward pair. Earlier revisions differ. |
| Fire Emblem Warriors Switch | Gold, existing ordinary drops, generic weapon stars and ordinary-seal KO decreases; no character-growth/story grants. | Complete extracted `scenario0`, `scenario1` or `scenario2`, preserving separate `system`; exact build/DLC. Unmodified control and one material/drop, smithy fusion, ordinary-seal, character growth, crest, bond or History-mode reward pair. 3DS is a separate format. |
| DW7 PS3 US/EU | Manual gold/stats/skill points in decrypted exports. | Decrypted `APP.BIN` from `BLUS30690`/`BLES01149`, optional identity-only `PARAM.SFO`, one skill purchase/seal/equip/guardian-beast or clear/reward pair. Natural caps and named records need PS3-specific evidence. |
| SW4 PS3 US | Manual gold/eight gems; paired proficiency level/EXP inspected only. | Decrypted `DATA.BIN` from `NPUB31564`, optional `PARAM.SFO`, one proficiency level-up/EXP, growth, weapon/skill/equip, Chronicle/bond or reward pair. Japanese layouts require their own scalar profile. |
| DW7 Empires PS3 US | Manual SYSTEM bonus points; campaign unsupported. | Decrypted `NPUB30846-SYSTEM/DATA.BIN` plus `NPUB30846-PLAY*/DATA.BIN`, optional `PARAM.SFO`; one bonus purchase, campaign resource, fame/ability, relationship or territory pair. SYSTEM and PLAY are not interchangeable. |
| DW8 Empires US PS3 SYSTEM | Existing custom-horse Body Type implemented; campaign remains read-only research. | Decrypted NPUB31656-SYSTEM APP.BIN with mandatory original PARAM.SFO; controlled appearance/equipment/acquisition pair and console reimport/load. Separate NPUB31656-EMPIRE exports need actual resource order/owner bridge. [Details](DW8E_PS3.md) |
| Strikeforce US PS3 | Genuine-file anonymous record/storehouse inspection; no writer. | Decrypted BLUS30471-SAVEDATA APP.BIN with mandatory original PARAM.SFO. Native serializer/integrity or credible controlled US edited-load proof; acquisition/use, selected versus persistent growth/ability and equip/mission pairs. [Details](STRIKEFORCE_PS3.md) |
| WO3 Ultimate US PS3 | Manual unallocated growth points/gems in qualified NPUB31505; rich systems inspected only. | Decrypted APP.BIN with mandatory unchanged original NPUB31505-SAVEDATA PARAM.SFO; our console load/re-save and controlled progression/fusion/equipment/reward pairs. NPUB50173/NPEB02052 patch profiles need separate genuine native qualification. [Details](WO3U_PS3.md) |
| SW2 with Xtreme Legends HD, Japanese PS3 | Money/partial checksums and three EXP/weapon anchors inspected only; no native profile. | Complete decrypted NPJB00439 DATA.BIN with original identity metadata, native length/header/revision and all section integrity. Controlled money/growth/skill/weapon/guard/horse/mode/clear pair; Empires and other platforms remain separate. [Details](SW2HD_PS3.md) |
| Totori DX Steam PC | No editor; source Cole offsets lack title/framing/integrity qualification. | Actual app936180 gameplay slot (`GAMEDATAxx`/`SAVEDATA`, retain the game's original name) plus `SYSDATA`, language/build and unchanged control; exact A12V-prefixed executable if available. One Cole purchase/sale, synthesis/equipment, licence/rank or calendar/event pair. Rorona app936160 is different. |
| DW5 Empires, Xbox 360 | Legacy-editor leads only; no qualified gameplay writer. | Native extracted export with exact region/revision and complete integrity, unchanged control and resource/item purchase and turn/Delegate pair. Keep the signed container privately; external STFS reimport/resigning remains necessary. [Details](XBOX360_EXPANSION.md) |
| DW6 Empires, Xbox 360 | Legacy-editor leads only; no qualified gameplay writer. | Native extracted export with exact region/revision and complete integrity, unchanged control and ruler/officer funds/gems/forging pair. Keep the signed container privately; external STFS reimport/resigning remains necessary. [Details](XBOX360_EXPANSION.md) |
| DW7, Xbox 360 | Legacy-editor leads only; no qualified gameplay writer. | Native extracted export with exact region/revision and complete integrity, unchanged control and Conquest money/skill purchase/weapon/seal pair. Keep the signed container privately; external STFS reimport/resigning remains necessary. [Details](XBOX360_EXPANSION.md) |
| SW2, base, Xbox 360 | No registered gameplay writer; each edition is separate. | Samurai2.dat and region/revision/complete-integrity proof; existing genuine diagnostic has an ambiguous second checksum endpoint; unchanged control and acquisition/equipment/growth/stage pairs. External STFS rebuilding/resigning remains required. [Details](XBOX360_EXPANSION.md) |
| SW2 XL, Xbox 360 | No registered gameplay writer; each edition is separate. | distinct native XL export/title-update and native integrity; unchanged control and acquisition/equipment/growth/stage pairs. External STFS rebuilding/resigning remains required. [Details](XBOX360_EXPANSION.md) |
| WO1, Xbox 360 | No registered gameplay writer; each edition is separate. | Xbox-native export and Growth Points versus officer EXP identity; unchanged control and acquisition/equipment/growth/stage pairs. External STFS rebuilding/resigning remains required. [Details](XBOX360_EXPANSION.md) |
| WO2, Xbox 360 | No registered gameplay writer; each edition is separate. | freely available native OROCHI_EX export and growth/proficiency/fusion dependencies; unchanged control and acquisition/equipment/growth/stage pairs. External STFS rebuilding/resigning remains required. [Details](XBOX360_EXPANSION.md) |
| SW4 DX / SW5 / WO4 PS4 | Save Wizard/Chaoszage commercial-editor examples do not supply a reusable implementation or native profile. | Legally obtained decrypted gameplay exports with native filenames/title IDs/build/DLC (basenames unverified here), unchanged controls and per-system action pairs; independent native identity/integrity/serialization proof. PS4 signing remains external. No commercial editor binaries are redistributed. |

For a legacy editor, public factual documentation and independently recovered
format rules can guide an original implementation. Reusing implementation code
also requires its original source and an explicit compatible licence or maintainer
permission. A binary-only download or commercial product screenshot supplies
neither that permission nor a tested native save mapping.

## Newly implemented profiles and further expansion

| Game/platform | Implemented now | Exact further input |
| --- | --- | --- |
| Dynasty Warriors 5 Special, Windows | Existing ordinary item ranks, own-family stored weapon attack adjustment/weight and existing attribute ranks; named officer, item, weapon and bodyguard inspection. | Unmodified native `save.dat`, language/build, one item pickup, weapon acquisition/equip, officer growth, bodyguard training or Shura action pair. Matching weapon/item parameter tables or original Windows executable help prove total stats and reward prerequisites. Japanese title numbering is Shin Sangokumusou 4 Special; console DW5, Empires and DW6 Special are different games. |
| Hyrule Warriors Legends, 3DS | Rupees, existing materials/base-map cards, generic weapon stars, ordinary seal decreases, existing printable ASCII My Fairy names and owned fairy trust reductions. | Extracted `zmha.bin` with exact version/DLC; unmodified control and one fairy-name/food/skill, level/EXP/badge, fusion/equip, DLC-card or stage/reward pair. DE and Wii U layouts are different. |
| Atelier Ayesha, PS3 US/Japanese | Decrypted export Cole and qualified existing stack reductions; float quality/properties, effects and memory words inspected separately. | Decrypted `USR-DATA` copied to `.bin`, optional identity-only `PARAM.SFO` for BLUS31152/BLJM60486, one sale/purchase, synthesis/use, memory purchase or calendar/event pair. Apollo handles PFD reimport/signing; PC/DX/Chinese profiles require their own native exports. |
| Fire Emblem Warriors: Three Hopes, Switch | Gold and existing material-stock reductions, owned Shez/Byleth ASCII name customization; character/weapon inspection. | Extracted extensionless `SlotData0`–`SlotData5`, exact version/DLC, one level/class/mastery, materials, forging/equip, support or route/reward pair. Existing header/body names and all 144 integrity sections are synchronized; stat/ownership grants remain blocked. |
| Ken's Rage 2, EU PS3 | Manual locked-gallery unlocks; existing nonzero statuses preserved. | Decrypted `BLES01801` `DATA.BIN` beside `PARAM.SFO`, with at least one genuinely locked gallery entry; unchanged control and one growth/EXP, scroll acquire/equip/transfer or mission/reward pair. Other regions/platforms need their own native profiles. [Evidence](LICENSED_MUSOU.md) |
| Dynasty Warriors: Gundam, US/EU PS3 | Learning-only skill flags and original learned non-inherent skill-loadout choices on six qualified level-30 pilots; EXP/levels and other equipment inspected. | Decrypted `BLUS30058`/`BLES00147` `DATA.BIN` beside original `PARAM.SFO`; one labelled EXP/level/stat, lower-level skill acquisition, part/equip or mission/reward pair. Other pilots/platforms/editions require independent maps. [Evidence](LICENSED_MUSOU.md) |
| Ken's Rage, US/EU PS3 | Positive existing eight base-fighter skill-point balances; anomalous/empty records inspected. | Decrypted `BLUS30504-00`/`BLES01062-00` `DATA.BIN` plus `PARAM.SFO`; native serializer/integrity proof, edited console load, ownership and one skill purchase/Meridian Chart, equip, growth or mission/reward pair. DLC/other platforms require separate profiles. [Evidence](LICENSED_MUSOU.md) |
| Gundam 2 / 3 / Reborn | Unregistered PS3 patch leads; no native profile. | Complete decrypted regional `DATA.BIN` with build/revision provenance, identity/length/full integrity and controlled resource/growth/parts-or-plan/equipment/friendship/reward pairs. PS2/Xbox 360/Vita filenames and layouts need separate proof. [Per-title details](LICENSED_MUSOU.md) |

## Strategy-game profiles

Original PC XIII revision-14 city quantities are implemented. Additional regions,
exact executable build/DLC provenance, officer serialization and dependencies,
and edited game load/re-save remain unqualified. XIV requires a verified `LWC`
decoder/encoder plus integrity and record mappings. Sphere of Influence and
Taishi require accessible complete native campaigns and edition-specific disk
codec/field evidence. See [the candidate review](STRATEGY_EXPANSION.md) for exact
download, format and mechanics blockers; system/unlock files do not fill those gaps.

| Fire Emblem: Three Houses, Switch | Exact gameplay serialization v13/v23; gold and existing convoy quantity/equipment durability reductions; distinct read-only mechanics. | Clean extracted main-campaign copies with exact game revision/region/DLC provenance; controlled level/stat-booster/certification, rank/talent/mastery/reward, repair/trade/equip, battalion hire/assignment/endurance and support-conversation pairs plus unchanged controls. v12, padded exports, system/suspend and Cindered Shadows side-story framing need separate qualification. Edited Switch game load/re-save is untested. [Details](THREE_HOUSES_FORMAT.md). |

## Other researched PC formats

The [licensed action RPG status](LICENSED_ACTION_RPG_STATUS.md) distinguishes
the acquired evidence from missing native proof. These three candidates have no
registered editor or qualified gameplay edits.

| Game | Exact next input |
| --- | --- |
| Dragon Quest Heroes: Slime Edition, Windows | Complete original `SAVEDATA.BIN`, exact Steam build/edition/DLC and unchanged control; matching original Windows loader/serializer/integrity implementation or source-backed native editor. One gold/mini-medal gain/spend, existing ingredient change, character growth, skill allocation, equipment and accessory-alchemy pair with displayed values. Public LZP2 decoding alone proves no native checksum or writable field. Retain any owner context privately. |
| Dragon Quest Heroes II, Windows | Complete original `SAVEDATA.BIN` with exact build/edition/DLC and unchanged control; matching Windows loader/serializer/integrity implementation. Label slots and provide separate resource/material, protagonist vocation growth, companion growth, weapon proficiency, skill allocation, equip and accessory-enhancement pairs. PS3/Vita checksum services and PS4 patches do not qualify Windows integrity. |
| Fate/Samurai Remnant, Windows | Complete original full-game save folder retaining `Savedata/SAVEDATA*.BIN` and any `SavesDir/*.sav`, exact build/DLC and unchanged control, plus matching native serializer/integrity evidence. Identify demo copies separately. One resource/material, Iori growth/skill, Saber/other Servant growth/skill, mounting upgrade/equip/disassembly and workshop renovation/carving/reward pair. Owner context stays private; asset extractors and runtime trainers do not supply the disk contract. |
| DW8 Empires PC | Existing occupied custom-horse body type is implemented in qualified `SystemSave.dat`. Supply controlled examples for the other six appearance sliders, names, stats/abilities and campaign resource ownership; `EmpireSave*.dat`/`QuickSave*.dat` remain separate. |
| Sophie 2 PC | Genuine Steam1.08 `data.dat`, unchanged control and one quality/use/refill, alchemy EXP, trait/effect, equipment or recipe/action pair. Native item applicability and derived progression need separate proof. |

The additional Gust profiles now distinguish acquired gameplay evidence from
missing proof. Original Sophie is implemented; its remaining native loader and
controlled synthesis/growth inputs are listed in [Sophie PC](SOPHIE_PC_FORMAT.md).
Ryza 2 implements base-cap quality and qualified unspent SP reductions; [Ryza](RYZA_FORMATS.md) records
the exact incomplete Ryza 1 PC tail, absent Ryza 3 gameplay and higher-cap skill
dependencies. [Arland DX](ARLAND_DX_RESEARCH.md) records 27 Rorona and 17 Meruru
gameplay files plus a title-qualified Totori PS4 export, all still lacking a
qualified internal integrity model before writes. [Dusk DX](DUSK_DX_RESEARCH.md)
records acquired Ayesha DX, Escha & Logy DX and Nelke gameplay; Shallie DX has
only system data. [Blue Reflection](BLUE_REFLECTION_RESEARCH.md) records acquired
BR1/Second Light gameplay and specific integrity/semantic gaps.
[Fatal Frame II Remake](FATAL_FRAME2_REMAKE_FORMAT.md) is implemented for shared
system Photo Point reductions; named item eligibility and enhancement/collection
dependencies need controlled native pairs. No private save is requested for Git.
| Nioh3 PC | Complete native `USER` files with exact build, equipped/owned inventory examples, labelled level/stat/skill or equipment/forge/scroll pairs. Fixed published pool bases do not match every qualified revision. |

| Nioh 3 PC | Amrita/Gold deductions, existing common-stack reductions and tagged-pool inspection are implemented for two exact USER revisions. Need build-labelled carry/storage capacity and pickup/transfer pairs, currency-increase/purchase dependencies, native growth/skill maps, equipment/forge/owned-Scroll pairs and actual edited game-load/re-save. [Checklist](NIOH3_RESEARCH.md) |
| Nioh / Nioh2 PC | Genuine files are available and decode; the missing piece is the native active checksum algorithm, then controlled growth/equipment/dependency pairs. Integrity flags must not be erased. |
| Wo Long PC | Three currencies, existing ordinary stack reductions and enabled existing battle-set names are implemented. Need an eligible native battle-set rename pair, matching item-name catalogs and controlled Virtue/level/skill, forging/equipment, acquisition and quest/reward pairs. |
| Stranger of Paradise PC | Genuine Epic launch USER/SYSTEM framing is now qualified; native gameplay integrity/update routines are still essential, followed by one-action resource/job/EXP/gear/synthesis/rift/reward pairs. Steam revision-0x23013100 USER/SYSTEM framing is separately qualified; unobserved builds and later Epic revisions require their own proof. [Checklist](SOPFFO_RESEARCH.md) |
| Persona5 Strikers PC | Native encrypted PC framing/checksum and occupied-slot money/Persona/BOND balances plus selected existing consumable/cooking, incense, remedy and skill-card quantities are implemented. Need one BOND purchase, character/Persona level, recipe/acquisition or quest-reward pair before expanding those systems. |
| Ninja Gaiden II Xbox 360/Xenia | Extracted revision-6 essence and stack editor implemented. Need actual edited game-load/re-save; native weapon/upgrade, health/Ninpo, ownership/reference and Karma/reward pairs. CON/STFS extraction/signing remains external. [Checklist](NINJA_GAIDEN_RESEARCH.md) |
| Ninja Gaiden Sigma, each platform | Seven PC gameplay copies establish bounded descriptive framing; native identity/revision/integrity remain unresolved. Need exact edition/platform/build proof and controlled resource, weapon/Ninpo, inventory, customization or reward pairs. Console formats need their own exports. Do not substitute Sigma 2, original II or Black. |
| Ninja Gaiden Sigma 2 Master Collection PC | Genuine story corpus acquired and metadata CRC recovered. Need the second native body-integrity algorithm/serializer and controlled essence/stack, weapon/Ninpo, ownership and reward pairs. PS3/Vita/Switch layouts remain separate. |
| Ninja Gaiden 2 Black Steam PC | Genuine GVAS story/system corpus acquired and typed wrapper bounded. Need native embedded story-body integrity at 0x14, separate SYSTEM integrity and resource/record/ownership/dependency pairs. Its Steam editor is not native integrity proof; PS5/Xbox Series are separate. |

## Hunting and monster development: Windows candidates

No editor qualified for these four candidates. Acquired Toukiden archives are
private research inputs, without proved native codec/integrity or writable
fields. The requested library registration, runtime metadata and supported
inventory additions therefore remain blocked together; these candidates do not
change the supported inventory. The game notes give a specific blocker for every
investigated mechanic.

| Candidate | Exact next inputs |
| --- | --- |
| [Toukiden Kiwami](TOUKIDEN_KIWAMI_RESEARCH.md), Steam app363130 | Complete original `DATA0.BIN`/`DATA1.BIN`/`DATA2.BIN` and `DATASYS.BIN` copies; build, language, DLC and selected slot. Matching native save/load/integrity routine or source-backed codec evidence; unchanged control and separate Haku purchase, existing-material consumption, acquire/equip, fortify/reforge, Mitama growth/Boost selection and mission/reward pairs. |
| [Toukiden 2](TOUKIDEN2_RESEARCH.md), Steam app551730 | Retain all actual `play??_user.bin`, `play??_chkp.bin`, `play??_safe.bin`, `play??_btle.bin` partners and `system.bin`, with build/language/DLC and slot/role labels. Matching native serializer/integrity or controlled encrypted/plain references; unchanged control and separate Haku, existing material, equip/fortify/reforge, Mitama/Boost, facility/story/reward pairs. Plain-looking partners cannot replace active files without native proof. |
| [Monster Rancher 1 DX](MONSTER_RANCHER_DX_RESEARCH.md), Steam app1716120 | Complete private original `mfdx_en`/`mfdx` contents, actual extensionless `BISLPS-*` slots and companions, game/language/build and vanilla/mod status. Native serializer/checksum proof; unchanged control, active/frozen occupancy, money, stat/work/training, rest/item condition, weekly age/lifespan and freeze/thaw/unlock pairs. |
| [Monster Rancher 2 DX](MONSTER_RANCHER_DX_RESEARCH.md), Steam app1716120 | Same complete original folder, preserving actual slot names and `psdata001.bin` when present to resolve the reported directory dependency. Separate drill/errantry, stress/fatigue, lifespan-item and one-use flags, expedition, freeze/thaw and reward/prerequisite captures. Runtime monster editors and InfiniteFreezer sidecars do not establish native serialization. |

Keep owner identifiers, source copies and static analysis private. Each eventual
editor needs native unchanged roundtrips, surgical integrity/dependency tests,
safe-storage and GUI checks, followed by actual edited Windows game loading and
re-saving. Neither public save acquisition nor existing-game regressions count
as those qualifications.

| Berserk and the Band of the Hawk PC | The complete public `BKSAVEDATA0000.dat` now passes reproducible outer-envelope diagnostics; no gameplay editor. Need exact build/region/DLC and matching original `BERSERK.exe` for static serializer/getter analysis, or source-backed Windows save-editor documentation plus controlled native pairs. Capture money gain/spend, material purchase/use, existing accessory enhancement/promotion/amalgamation/equip, character level-up, and separate per-character Eclipse/checkpoint/desire/reward actions with displayed values and an unchanged control. Title text alone does not prove revision or all integrity. [Details](BERSERK_PC_RESEARCH.md). |
| Attack on Titan / Wings of Freedom PC | The public `atwin0000.dat` passes reproducible three-advance outer-envelope diagnostics; no title/revision/body schema or gameplay writer. Need exact Windows build/region and matching original native serializer/getters or documented native Windows editor, plus one funds/material gain/spend, gear develop/upgrade/fortify/equip, horse change, character growth/skill or mission-reward pair. Retain full native save folder and unchanged control; Vita offsets are separate. [Details](AOT1_PC_RESEARCH.md). |
| Attack on Titan 2 / Final Battle PC | The observed complete `AOT2_PK_WIN0000.dat` contribution passes one-advance outer-envelope diagnostics; PK filename does not prove installed revision/entitlement. Need exact base/Final Battle build/region/DLC, matching original native serializer/getters or source-backed Windows editor, and full native folder with separate funds/material, existing equipment/reinforcement/development/equip, customization, camaraderie reward, regiment and Territory Recovery action pairs plus unchanged controls. No ownership/story/reward grants follow from resource changes. [Details](AOT2_PC_RESEARCH.md). |

No edited PC or console game-load/re-save was performed by this project during
this expansion. A successful file roundtrip, GUI workflow or Windows app build
is reported separately from that remaining validation.

## Regional and PSP Special inputs

Provide complete private original folders with exact product/platform,
language/build, original filenames and export-tool/version/settings. For PSP,
include an unchanged encrypted directory and its matching authenticated
decrypted export; a decrypted payload alone is not a console-importable package.
Native gameplay identity/revision, serialization, integrity and unknown-byte
preservation must qualify before any write. External import/re-encryption and
secure metadata updates remain outside the research inspector.

| Candidate | Exact next inputs |
| --- | --- |
| DW5 Special Windows regional qualification | Unmodified Japanese, Traditional Chinese and mainland Simplified Chinese `save.dat` copies with build/language provenance and a matched unchanged control/action pair. Existing shared Traditional-Chinese premodified evidence cannot qualify Japanese/Simplified-Chinese serialization or bodyguard text. See [DW5 qualification](DW5_SPECIAL.md). |
| DW6 Special PS2/PSP | Each region's complete native export; PS2 container and game integrity; PSP secure title-key/mode and authenticated plaintext. Then controlled officer/skill/Meng Huo, weapon/equip, horse and story/reward pairs. Claimed native Windows Special first needs product/build evidence; ordinary Chinese Windows is a different candidate. [Details](DW6_SPECIAL_REGIONAL_RESEARCH.md). |
| DW7 Special PSP | Matching plaintext for the acquired encrypted Japanese envelope plus a second independent state; native integrity and money purchase, growth/reset, weapon acquisition/equip and Story/Chronicle pairs. Taiwan catalog branding is not translation/save-format proof. [Details](DW7_SPECIAL_PSP_RESEARCH.md). |
| Orochi 3 Special PSP | Complete original Japanese secure-save package and matching authenticated decrypted export; native profile/integrity plus growth-reset, Rachel/Abe no Seimei, resources, bonds and weapon/fusion/reward pairs. [Details](PSP_SPECIAL_RESEARCH.md). |
| SW3 Z Special PSP | Clean encrypted package without foreign PS3 artifacts and matching authenticated plaintext; native profile/integrity plus officer growth, weapon/equip, custom-officer, creation/history/challenge and reward pairs. [Details](PSP_SPECIAL_RESEARCH.md). |

The [additional regional checklist](REGIONAL_EDITION_SCOPE.md) records other
verified product/format distinctions and assignment boundaries. No player data,
owner context, assets or title keys should be posted on the PR; keep those
inputs local. Actual edited game-load/re-save follows qualified file tests and
remains separately required.

## v1.71 profile expansion inputs

| Game/platform | Implemented | Needed for deeper coverage |
| --- | --- | --- |
| Original Atelier Ryza, Switch | Existing ordinary quality 1–100; searchable inventory/equipment/traits. | Controlled quality-cap, synthesis/rebuild/trait, earn/spend, growth and equip/transfer pairs; independently qualified item identities. PC/DX/DLC episode files need separate complete native qualification. [Checklist](RYZA_SWITCH_FORMAT.md) |
| DW8 XL, original US PS3 PSN | Resources, officer stats, weapon-action aptitudes and existing weapon ranks. | Exact NPUB31449 APP.BIN with original PARAM.SFO, controlled progression/reward/weapon acquisition pairs, and edited console load/re-save. Other editions/regions require independent native exports. [Checklist](DW8XL_PS3_FORMAT.md) |
| DQB2, original Steam PC | Existing named medicine/seed reductions and searchable inventory/player status. | Controlled additional item applicability, player growth, and matched CMNDAT/STGDAT world/progression pairs; original same-slot companion files for game-load validation. Other platforms require independent native qualification. [Checklist](DQB2_PC_FORMAT.md) |

DW5 Special's reported compatible header variant is fixed; its marker is retained without inferring locale/build or allowing conversion. Regional action-pair/catalog dependencies above remain unchanged.

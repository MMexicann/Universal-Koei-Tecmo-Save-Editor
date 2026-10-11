# Prepared update — unreleased

The combined development source prepares the next update without a version
bump, tag or GitHub release. The latest published download remains **v1.6**.
The registry-derived [supported inventory](SUPPORTED_GAMES.md) reflects source
support. A Windows preview build is provided as a workflow artifact after the
combined checks; it does not replace the published release.

The subsequent [existing-editor expansion](RICH_EDITOR_EXPANSION.md) adds editing
content to 19 of the 44 registered profiles, with shared relative adjustment and
selective revert controls. Its table is the current feature delta; the tables
below describe the preceding integration. Version and publication stay unchanged.

The newest follow-up adds the separate **Atelier Meruru Plus US PS Vita**
decrypted-export editor, bringing the source inventory to **45 profiles**. It
offers manual Cole, base attack/defense/speed, base HP/MP/LP increases and
current HP/MP/LP reductions for thirteen named characters, with searchable
character and inventory records.
See [its format and mechanics checklist](MERURU_PLUS_VITA_FORMAT.md).
Meruru DX PC, Rorona DX PC, Totori DX PS4, Japanese SW2 with XL HD and Berserk PC
remain unregistered; [the exact input checklist](REMAINING_INPUTS.md) and linked
per-game notes record the new native files, bounded inspectors and remaining
writer qualification. Vita evidence does not qualify the PC port.

## Added game/platform profiles

| Game / edition | Platform | Implemented controls |
| --- | --- | --- |
| Atelier Sophie — Original Steam PC · GAMEDATA slots | Windows PC | Cole, Tess tickets and existing basket/container quality; searchable inventory and alchemy progression. |
| Atelier Ryza 2 — Lost Legends & the Secret Fairy · original Steam PC | Windows PC | Existing ordinary item and equipment quality from 1–100; searchable inventory and equipment. |
| Fatal Frame Ii — Crimson Butterfly REMAKE · Steam PC | Windows PC | Shared system Photo Point reductions; per-slot inventory, camera and collection inspection. |
| Warriors Orochi — Original Windows PC · save revision 2 | Windows PC | Growth Points and existing weapon attack bonuses, attribute capacity and owned effect ranks. |
| Samurai Warriors 4-Ii — Windows PC edition | Windows PC | Gold, tomes, officer stats, existing weapons and mount stats. |
| Samurai Warriors 2 — Original Windows PC · save revision 2 | Windows PC | Money, stored officer growth, acquired ordinary skill ranks and existing weapon bonuses. |
| Dynasty Warriors 8 Empires — Windows PC · SystemSave.dat | Windows PC | Existing custom-horse body type; searchable appearance, stats and ability records. |
| Wo Long: Fallen Dynasty — Windows PC · USERDATA | Windows PC | Genuine Qi, copper, accolades, existing ordinary stack reductions and searchable equipment. |
| Persona 5 Strikers — Windows PC · SAVEDATA.BIN | Windows PC | Money, Persona points, unspent BOND points and existing named consumable/cooking quantities. |
| Hyrule Warriors Legends — Nintendo 3DS · zmha.bin | Nintendo 3DS | Rupees, materials, existing map cards, weapon stars, ordinary seal counters and My Fairy names. |
| Atelier Ayesha — The Alchemist of Dusk · PS3 US/Japanese export | PlayStation 3 | Cole, existing stack reductions and searchable inventory quality, properties and effects. |
| Dynasty Warriors 5 Special — Shin Sangokumusou 4 Special · Windows PC | Windows PC | Existing ordinary item ranks, weapon attack/weight and attributes; named officer/bodyguard inspection. |
| Fire Emblem Warriors: Three Hopes — Switch · extracted SlotData exports | Nintendo Switch | Gold reductions, owned Shez/Byleth name customization and searchable character/weapon records. |
| Dynasty Warriors 8 Empires — US · decrypted SYSTEM APP.BIN | PlayStation 3 | Existing custom-horse Body Type; searchable appearance, stats and ability records. |
| Warriors Orochi 3 Ultimate — US · decrypted APP.BIN · NPUB31505 | PlayStation 3 | Manual unallocated growth points and gems; searchable officer, weapon and inventory inspection. |
| Nioh 3 — Windows PC · USER revisions 0x01030001 / 0x01040000 | Windows PC | Amrita and Gold deductions, existing common-item quantity reductions; separate equipment level, pre-forge and reinforcement inspection. |
| Ninja Gaiden Ii — Original Xbox 360 / Xenia · extracted revision-6 story | Xbox 360 / Xenia | Yellow Essence, existing consumable and ammunition reductions; searchable inventory and separate Karma inspection. |
| Dynasty Warriors: Gundam — US/EU · decrypted DATA.BIN + PARAM.SFO | PlayStation 3 | Learn native skill flags on six qualified level-30 pilots; inspect EXP, levels and equipment. |
| Fist Of The North Star: Ken'S Rage — US/EU · decrypted DATA.BIN + PARAM.SFO | PlayStation 3 | Manual existing skill-point balances for eight base fighters; inspect progression resources. |
| Fist Of The North Star: Ken'S Rage 2 — EU · decrypted DATA.BIN + PARAM.SFO | PlayStation 3 | Unlock locked music, movie and event gallery entries; preserve existing collection states. |
| Romance Of The Three Kingdoms Xiii — Original PC · revision 14 · TC | Windows PC | City gold, supplies, population, wounded troops, fealty, commerce, farming, culture and troop proficiencies. |
| Fire Emblem: Three Houses — Switch · gameplay save-format v13/v23 | Nintendo Switch | Gold and twelve ordinary weapon types’ existing convoy quantity/durability reductions; separate mechanics inspection. |

Each has its own parser and explicit identity/revision gates. Resource ceilings
without natural-cap proof are manual editing limits and are excluded from Max.
Unknown items, unrelated regions, empty records, acquisitions and dependent
story/level/reward transitions are preserved.

## Expanded existing editors

| Editor | Addition |
| --- | --- |
| DW4 Hyper and DW4 Xtreme Legends PS2 | Already-owned harness/orb assignment with item-ownership protection; Hyper additionally supports guarded existing created-officer cosmetics and consistent paired progression mirrors. Independent genuine exports now qualify both profiles. |
| Warriors All-Stars PC | Select already-owned ordinary Hero Cards from the same hero pool; searchable occupied card records, preserving special gifts and card properties. |
| DW7 XL Definitive PC | Named first/second existing equipped-weapon choices reference only valid owned inventory slots. |
| DW6 PC | Named element choices for existing qualified weapons: Fire, Ice, Lightning or none. |
| Warriors Orochi Z | Existing own-pool equipped weapon selection and coherent progressed EXP confined to the already opened level. |
| Warriors Orochi 3 Ultimate Definitive PC | Additional qualified ranked weapon attributes and guarded attack-reinforcement reductions; binary/dormant effects remain preserved. |
| Hyrule Warriors Definitive Edition Switch | Existing generic weapon stars and ordinary positive seal KO reductions; special weapons and collection-dependent seals stay protected. |
| Samurai Warriors 4 PS3 | Searchable native weapon and attached-skill records, separate from proficiency EXP/level inspection. |
| Dynasty Warriors: Origins | Searchable existing weapon slots, upgrades and six stored trait IDs/levels; reserved records preserved. |

Other implemented games were reviewed for additional save-backed systems; the
per-game notes record specific dependency or input blockers. DW3 Remastered's
existing rich editor is retained. No runtime trainer address or another
platform's mapping is presented as a native save field.

## Interface and maintenance

- Search games by name, short name, platform or feature; filter by series and
  platform, including All platforms. Ctrl+F focuses global library search and
  Enter opens a single result.
- Compact cards, result counts, clear filters and visible resume-session buttons.
- Named choice controls and bounded backend-validated text fields; multi-field
  staging stays atomic and preserves Undo and Review Changes.
- Sort field, inspector and review tables by clicking columns; copy selected
  inspector rows with headings. Large integers retain exact sorting precision.
- Keep per-game modules under `src/koei_editor/games`, common utilities under
  `shared`, unregistered research under `research`, and notes under `docs`.
- Keep supported games synchronized in the registry, code index, runtime
  catalog, README and generated document. AGENTS/CONTRIBUTING require this.
- Guard the additional official live save directories and preserve source-copy,
  backup, new-destination and restore protections.

## Research and validation

The [regional-edition follow-up](REGIONAL_EDITION_SCOPE.md) distinguishes
publisher-verified products from proved save compatibility. DW5 Special keeps
its existing Windows equipment adapter with explicit regional evidence limits.
DW6 Special PS2/PSP, DW7 Special PSP, Orochi 3 Special PSP and SW3 Z Special PSP
remain research-only. A bounded unregistered PSP envelope inspector checks
selected product metadata and secure declarations; it cannot authenticate,
decrypt, edit or encrypt gameplay. See [PSP responsibilities](PSP_SPECIAL_RESEARCH.md),
[DW6 product distinctions](DW6_SPECIAL_REGIONAL_RESEARCH.md) and
[DW7 qualification](DW7_SPECIAL_PSP_RESEARCH.md). No native Windows DW6 Special
product/profile or cross-region conversion is claimed.

The original PC profiles above have independent period disk-reader/writer
evidence and two independently shared genuine files each. SW2 HD PS3, console
containers, Orochi Z and later Orochi games are separate profiles. The
[SW2](SW2_PC_FORMAT.md) and [Orochi](WO1_PC_FORMAT.md) notes record native
integrity, serialization, per-mechanic blockers and validation distinctions.

The three newly supplied files identify Orochi Z, WO3 Ultimate Definitive PC
and SW4 DX respectively; the file described as DW7 is an Orochi Z file.
[The supplier table](REMAINING_INPUTS.md) lists exact remaining inputs.
[Additional research](ADDITIONAL_EDITOR_SURVEY.md) and game notes distinguish
real save editors, asset tools, runtime trainers and unsupported platform leads.
The [Team Ninja coverage](TEAM_NINJA_RESEARCH.md) records native integrity and
mechanic blockers for Nioh 1/2, Stranger of Paradise, Sigma/Sigma 2 and Black.
Each edition/platform stays separate; active integrity flags are retained.

The separate hunting/monster-development investigation acquired public PC save
archives for [Toukiden Kiwami](TOUKIDEN_KIWAMI_RESEARCH.md) and
[Toukiden 2](TOUKIDEN2_RESEARCH.md), but neither native codec/integrity nor
writable mappings qualified. [Monster Rancher 1 & 2 DX](MONSTER_RANCHER_DX_RESEARCH.md)
also remains blocked on complete native Windows files and serialization proof.
These four titles add no library card or runtime support claim; each note records
mechanic dependencies, source/licence boundaries and exact next inputs.

Native shared player exports qualify unchanged roundtrips, targeted byte edits,
checksums where present, malformed inputs, GUI workflows and backups. Procedural
fixtures cover independent adversarial cases. No attached executable was run;
no edited save was loaded/re-saved in a game. Native Windows build checks and
full regression totals are recorded after integration. No player files,
account identifiers, attached binaries or personal paths are included in Git.

The Berserk/AoT follow-up adds reproducible **read-only outer-envelope research**
and detailed mechanic/input checklists. All three genuine Windows contributor
copies pass unchanged cipher/checksum diagnostics; their gameplay records,
revision gates and remaining integrity are still unqualified. They add no game
cards or writable features. [Evidence and tests](OTHER_KOEI_PC_RESEARCH.md).

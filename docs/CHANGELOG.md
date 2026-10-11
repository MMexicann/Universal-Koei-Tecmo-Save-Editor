# Changelog

## v1.72

- **Persona 5 Strikers — English Nintendo Switch:** money, Persona points, unspent BOND points and named existing consumable, ingredient, incense, remedy and skill-card stacks; searchable character and Persona inspection.
- **Atelier Ryza 2 — original Nintendo Switch:** unspent skill-tree SP reductions and searchable existing inventory/equipment records.
- **Dragon Quest Builders 2 — original Nintendo Switch:** reduce existing named medicine and seed stacks; search pockets, the bag and player/equipment status.
- **Romance of the Three Kingdoms II — original Chinese DOS:** reduce owned provinces’ gold and rice; search province ownership, population and resource records.
- **Clearer library:** full-size illustrated cards now show by default. The **Compact cards** toggle is larger, bold and easier to find beside the search controls.

## v1.71

- Fixed DW5 Special opening for the compatible native header variant while preserving the original revision marker.
- Added original Atelier Ryza Switch existing quality editing and searchable inventory/equipment/trait inspection.
- Added original US PS3 PSN Dynasty Warriors 8 XL resources, officer stats, weapon-action aptitudes and existing weapon attribute ranks.
- Added Steam Dragon Quest Builders 2 existing named medicine/seed stack reductions and searchable pockets/bag/player inspection.
- The library now contains 51 game/platform profiles across nine platforms.
- Parallelized complete Windows regression checks across four jobs with verified combined coverage; optimized equivalent checksum/fixture work.
- Strengthened source/context checks around new adapters’ backups, restore and safe saving.

## v1.7

- Added 26 game/platform profiles, bringing the library to 48 across nine platforms.
- Added PC editors for Atelier Sophie, Atelier Ryza 2, Fatal Frame II: Crimson Butterfly REMAKE, Warriors Orochi, Samurai Warriors 2 and 4-II, Dynasty Warriors 5 Special and 8 Empires, Wo Long, Persona 5 Strikers, Nioh 3 and Romance of the Three Kingdoms XIII.
- Added PS3 editors for Atelier Ayesha, Dynasty Warriors 8 Empires, Warriors Orochi 3 Ultimate, Dynasty Warriors: Gundam, Ken's Rage 1/2 and original Dead or Alive 5.
- Added Switch editors for Fire Emblem Warriors: Three Hopes and Fire Emblem: Three Houses; Hyrule Warriors Legends on 3DS; Atelier Meruru Plus and Berserk on Vita; original Ninja Gaiden II on Xbox 360/Xenia; and Pokémon Conquest on DS.
- Expanded Dynasty, Samurai and Orochi equipment, mount, horse appearance, officer stats, weapon bonuses, upgrade stones and Hero Card controls.
- Added P5 Strikers incenses, remedies and selected skill cards; Ryza 2 SP reductions; eighteen named Nioh 3 consumables; Wo Long battle-set names; Three Houses motivation/ability loadouts; and Legends fairy trust reductions.
- Added global library search, series/platform filters, compact cards and visible session resume controls.
- Added sortable field/inspector/review tables, inspector row copying, validated Adjust Selected and selective Revert actions.
- Preserved Light/Dark themes, backups, Undo, Review Changes and safe Save As workflows; synchronized the code and README supported-game inventories.

## v1.6

- Added Dynasty Warriors 6 PC named officer unlocks, existing horse combat stats
  and searchable officer/weapon/horse records.
- Added Dynasty Warriors 9 Empires PC SYSTEMDATA inventory quantities and
  searchable inventory/custom-officer records.
- Added Warriors Orochi Z PC Stock EXP, officer base attack, existing weapon attack bonuses,
  attribute capacity and owned attribute ranks with searchable records.
- Added Warriors All-Stars PC available gold and existing material quantities in campaign slots,
  with separate lifetime-gold inspection.
- Added Hyrule Warriors Wii U resources, weapon stars and ordinary skill-seal
  counters; Age of Calamity Switch resources, weapon protection and named
  equipment/seal inspection; Definitive Edition Switch rupees, existing named
  materials and character/fairy-food/weapon inspection.
- Added Fire Emblem Warriors Switch resources, existing weapon stars and
  ordinary skill-seal counters with named character/equipment inspection.
- Added decrypted PS3 Dynasty Warriors 7 US/EU gold/stats/skill points and
  Samurai Warriors 4 US gold/gems with proficiency inspection; Dynasty Warriors
  7 Empires US system bonus points.
- Added platform groups to the library, default Windows PC selection and
  inspector search across all columns.
- Organized source into an installable `src/koei_editor` package with separate
  game adapters, shared utilities, runtime data and research modules.
- Moved development documentation and build/maintenance tools into dedicated
  folders. Source setup is `python -m pip install -e .`, followed by
  `python -m koei_editor`.
- Added a canonical registry-derived supported-game index, synchronized README
  and generated game document, contributor folder guides and documentation index.

## v1.5

- Added native PC DW7 XL Definitive, WO3 Ultimate Definitive, Samurai Warriors 4
  DX and Pirate Warriors 4 editors with revision/integrity qualification.
- Added officer stats/skill points and owned weapon switching in DW7; WO3
  resources/stats and existing weapon slots/attributes; SW4 resources, manual
  base stats, guarded unlocks, equipment and attached weapon skills; PW4 Beli
  and quantities of existing obtained coins.
- Expanded DW8 XL with weapon-action compatibility, individual affinity and
  ally inspection. Expanded Sophie 2 with saved-capacity consumable refills and
  occupied inventory inspection.
- Added searchable inspector tables, immutable-snapshot and restore hardening,
  and transitive registered-adapter packaging checks.
- Added mechanic checklists and strict source-only format research for games
  whose gameplay mappings, native inputs or owner context remain unqualified.
  Genuine save file tests do not establish edited game loading.

## v1.4

- Replaced DW3 weapon bonus item names with stat labels in editing and review.
- Added native Origins Steam slot editing for Gold, base-game/DLC Skill Points,
  existing bonds, provincial peace and eligible weapon reinforcement from +0,
  with revision-specific qualification, integrity regeneration and copy backups.
- Added manual clear-history edits for 35 supported battles, preserving completed
  history and excluding these flags from Max. Campaign events, endings and battle
  rewards are unchanged.
- Preserved bond events, reward claims, XP, active story/unlock flags, weapon identities,
  traits and equipment references; training counts are excluded from bulk Max.
- Added field search by name, group and record to scalar editors. Max Visible
  Fields respects the filter and hidden pending edits remain staged.
- Remembered the selected Light/Dark appearance across restarts, including
  standalone DW3 sessions. Damaged or unavailable settings fall back safely.
- Added a formal adapter/session contract, generic scalar presentation hooks,
  registry-driven self-tests and a contributor starter with shared tests.
- Kept existing game sessions, fields and save workflows intact.

## v1.3

- Added Atelier Sophie 2 (Steam PC 1.08 layout), adapting the MIT-licensed
  existing save codec to the standard copy/backup/Undo/review/Save As workflow.
  Edit existing item/equipment quality and Sophie/Plachta alchemy EXP; supported
  quality fields have individual and bulk Max actions.
- Added a scrollable game grid and document-specific field groups so additional
  editors remain accessible at the minimum window size.
- Added native PC Nioh-family and Wo Long codec research with known-answer tests,
  and strict read-only Nioh 2 inspection. These have no gameplay editor cards.
- Documented checked existing-editor sources, licensing, actual blockers and
  repository name/About settings.


## v1.2

- Expand the DW3 editor into one Universal Koei Tecmo Save Editor executable.
- Add a game library with Windows PC selected by default and a separate
  PlayStation 2 platform option. Keep each game's session while switching.
- Add DW4 Hyper PC officer stats/EXP/unlocks, weapon EXP, items, bodyguard points
  and difficulty editing.
- Add DW8 XL Complete Edition PC resources, officer stats and existing weapon
  attribute ranks, with progression/equipment inspection.
- Add Pirate Warriors 3 PC character stats, special bars and skill slots, with
  read-only level/XP, currency and costume inspection.
- Add USA PS2 DW4 Xtreme Legends `.psu` editing for officers, weapon EXP, items,
  bodyguard points and difficulty.
- Share Light/Dark appearance across editors and retain Mexican's Contact dialog.
- Preserve all DW3 v1.1 features, automatic backups, Undo, Review Changes, Save As
  and backup restore. New editors write to a new destination and preserve unrelated data.
- Update standalone Windows packaging, source manifests and integrity checks.

## v1.1

- Fixed Huanglong Elixir editing and Musou completion on new/reset saves with an omitted zero Elixir counter. A completed story is no longer required before using these controls.
- Added an Unlock Yellow Uniform shortcut under Bodyguards → Appearance Unlocks, using the existing special-color unlock.
- Added Light and Dark appearance options, with updated spacing and colors across forms and review dialogs.

## v1.0

- Added unlocks for all 42 music tracks alongside the 50 movies in a dedicated Collections tab.
- Expanded weapon element editing: choose Fire, Lightning, Steel or Wind for one copy or all owned unique weapons, including weapons queued for acquisition.
- Kept element controls available when a weapon's saved bonuses need to be preserved. Element edits retain its other flags and bonus values.
- Refreshed the interface and clarified the supported limits used by Max actions. Higher existing item and weapon values are preserved.
- Added a Contact dialog with Mexican's Discord username and Steam profile.
- Separated pending edits from saved-value notes and completed the Unlock Everything Supported preset's content unlocks.
- Preserved unusual floating-point fields during unrelated edits.

Existing officer, item, bodyguard, stage, side story, Musou completion, campaign save and Huanglong Elixir controls remain available, with backups, Undo and Review Changes.

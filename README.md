# Universal Koei Tecmo Save Editor

A free Windows save editor by **Mexican**, with a game library, shared Light/Dark
themes, searchable records, backups, Undo and Review Changes. Switch between
games while keeping each editing session open. Full-size illustrated cards show by
default; the larger **Compact cards** toggle switches to a denser list.

The released **version 1.91** supports **76 game/platform profiles across 13 platforms**.
No Python installation is needed for the Windows app.

## Supported games

Select the game and platform that match your save. Console editors open
extracted or decrypted save exports: `.psu` for
PlayStation 2, `APP.BIN` for Wii U and DW7/DW8 XL PS3, `DATA.BIN` for SW4 PS3, and `svdt`
for Age of Calamity. The development source also accepts original Bladestorm PS3 `PLAYDATA` copies
and the newly qualified Pirate Warriors PS3 exports. Some PS3 profiles require the original `PARAM.SFO` beside
the copied gameplay file and edited output. Export and reimport/resign PS3 saves
with Apollo Save Tool; this editor does not rebuild `PARAM.PFD` or sign exports.

Berserk and Meruru Plus Vita editors open decrypted exports with their original
`sce_sys/param.sfo`. DW8 XL Vita opens the qualified plaintext `MainData00.dat` profile.
Meruru Plus uses `USR-DATA0000`; Berserk uses `app0000.dat` or another supported
slot. Export and reimport with a Vita save manager. Pokémon Conquest and Monster Rancher DS open raw
Nintendo DS `.sav` exports. The development source adds Gemfire NES/SNES and
Nobunaga NES raw battery exports, plus Bandit Kings Macintosh `.cim` data forks.
Attack on Titan Vita uses `app0000.dat` with original `sce_sys/param.sfo`.

Persona 5 Strikers PS4 opens a decrypted English `APP.BIN` export with its
original `sce_sys/param.sfo`; reimport using your PS4 save manager.

Samurai Warriors 5 and Warriors: Abyss need the original `steam_autocloud.vdf`
beside the copied save and edited output. Copy the complete save folder first.

Ninja Gaiden II opens extracted Xbox 360/Xenia story `.dat` copies; CON/STFS
packages require a separate extraction and reintegration workflow. Sigma 2 and
Ninja Gaiden 2 Black use different formats.

The table below describes the **development source on main**, including additions
that are not in the v1.91 Windows download.

<!-- BEGIN SUPPORTED GAMES -->
| Game / edition | Platform | Implemented scope |
| --- | --- | --- |
| DYNASTY WARRIORS 3 — Complete Edition Remastered | Windows PC | Character progression, equipment, companions and unlocks. |
| DYNASTY WARRIORS 8 — Xtreme Legends Complete Edition · PC | Windows PC | Resources, officer stats, weapon compatibility, affinity, attribute ranks and equipped weapon order. |
| DYNASTY WARRIORS 7 — Xtreme Legends Definitive Edition · PC | Windows PC | Gold, officer stats, skill points, active weapons and existing unlearned seal-meter reductions. |
| ONE PIECE: PIRATE WARRIORS 3 — Windows PC edition | Windows PC | Individual or bulk character stats, special bars and skill slots. |
| ONE PIECE: PIRATE WARRIORS 4 — Windows PC · WW/JP/EA revision 15 | Windows PC | Beli, existing obtained coin quantities and searchable resource history. |
| DYNASTY WARRIORS 4 HYPER — Native Windows PC edition | Windows PC | Character stats, weapon levels, items, owned harness/orb and occupied general-item equipment, bodyguards and customization. |
| ATELIER SOPHIE 2 — The Alchemist of the Mysterious Dream · PC | Windows PC | Item quality, battle-item refills, inventory inspection and alchemy EXP. |
| ATELIER SOPHIE 2 — The Alchemist of the Mysterious Dream · PS4 CUSA28451 app 1.0 | PlayStation 4 | Named existing material-quality reductions and battle-item uses within capacity; searchable inventory, equipment, Party and alchemy records. |
| ATELIER TOTORI — The Adventurer of Arland · original PS3 US/EU | PlayStation 3 | Cole reductions; searchable named character levels, EXP and serialized progression sections. |
| ATELIER MERURU — The Apprentice of Arland · original US PS3 | PlayStation 3 | Cole reductions; searchable named character levels, EXP and serialized progression sections. |
| ATELIER RORONA — The Alchemist of Arland · original US PS3 | PlayStation 3 | Cole reductions; searchable seven named character raw records and serialized systems. |
| ATELIER SOPHIE — Original Steam PC · GAMEDATA slots | Windows PC | Cole, Tess tickets and existing basket/container quality; searchable inventory and alchemy progression. |
| ATELIER RYZA 2 — Lost Legends & the Secret Fairy · original Steam PC | Windows PC | Ordinary item/equipment quality from 1–100 and qualified unspent skill-tree SP reductions; inventory inspection. |
| ATELIER MERURU PLUS — The Apprentice of Arland · US decrypted PCSE00296 | PlayStation Vita | Cole; 13 named characters’ base stats (attack/defense/speed), base HP/MP/LP increases and current-gauge reductions; searchable records. |
| FATAL FRAME II — Crimson Butterfly REMAKE · Steam PC | Windows PC | Shared system Photo Point reductions; per-slot inventory, camera and collection inspection. |
| DYNASTY WARRIORS 4 — Xtreme Legends · SLUS-20812 | PlayStation 2 | Character stats, weapon levels, items, owned harness/orb and occupied general-item equipment, and bodyguard growth. |
| DYNASTY WARRIORS: ORIGINS — Steam PC · slot saves | Windows PC | Gold, Skill Points, bonds, provincial peace, weapon upgrades and battle history. |
| WARRIORS OROCHI 3 ULTIMATE — Definitive Edition · PC | Windows PC | Officer stats, growth points, upgrade stones, gems, crafting, weapon attributes and owned ordinary-item equipment. |
| WARRIORS OROCHI — Original Windows PC · save revision 2 | Windows PC | Growth Points, weapon bonuses, attribute capacity, effect ranks and existing own-pool weapon selection. |
| SAMURAI WARRIORS 4 DX — Windows PC edition | Windows PC | Gold, gems, officers, existing weapons and attached skills. |
| SAMURAI WARRIORS 4-II — Windows PC edition | Windows PC | Gold, tomes, officer stats, existing weapons, mount stats and occupied-mount selection. |
| SAMURAI WARRIORS 2 — Original Windows PC · save revision 2 | Windows PC | Money, stored officer growth, acquired skills, weapon bonuses and existing own-pool weapon selection. |
| DYNASTY WARRIORS 6 — Native Windows PC edition | Windows PC | Named officer unlocks, horse combat stats, existing weapon elements and damage bonuses; searchable records. |
| DYNASTY WARRIORS 9 EMPIRES — Windows PC · SYSTEMDATA | Windows PC | Existing item quantities; searchable inventory and custom officer records. |
| WARRIORS OROCHI Z — Native Windows PC edition | Windows PC | Stock EXP, officer base attack, existing weapon bonuses/attributes and own-pool equipment selection. |
| WARRIORS ALL-STARS — Windows PC · revision F4 | Windows PC | Gold, existing materials, owned Hero Card selection and searchable card records; separate lifetime earnings. |
| HYRULE WARRIORS — Wii U · APP.BIN | Wii U | Rupees, existing materials and map cards, weapon stars and ordinary seal KO counters. |
| HYRULE WARRIORS — Definitive Edition · zmha.bin | Nintendo Switch | Rupees, existing materials, weapon stars, ordinary seal KO counters and searchable records. |
| HYRULE WARRIORS: AGE OF CALAMITY — Switch · svdt | Nintendo Switch | Rupees, discovered materials, trophies and reports; existing weapon protection and inspection. |
| FIRE EMBLEM WARRIORS — Switch · scenario0/1/2 exports | Nintendo Switch | Gold, existing ordinary materials, generic weapon stars and ordinary seal KO counters; named inspection. |
| DYNASTY WARRIORS 7 — US/EU · decrypted APP.BIN | PlayStation 3 | Gold and 62 officers’ health, attack, defense, power, speed and skill points. |
| DYNASTY WARRIORS 7 EMPIRES — US · decrypted SYSTEM DATA.BIN | PlayStation 3 | Manual system bonus-point editing; campaign saves use a separate format. |
| SAMURAI WARRIORS 4 — US · decrypted DATA.BIN | PlayStation 3 | Gold, eight gems and searchable weapon proficiency/EXP inspection. |
| DYNASTY WARRIORS 8 EMPIRES — Windows PC · SystemSave.dat | Windows PC | Existing custom-horse appearance choices; searchable horse stats and ability records. |
| WO LONG: FALLEN DYNASTY — Windows PC · USERDATA | Windows PC | Genuine Qi, copper, accolades, ordinary stack reductions, existing battle-set names and equipment inspection. |
| PERSONA 5 STRIKERS — Windows PC · SAVEDATA.BIN | Windows PC | Money, Persona/BOND points and existing consumables, cooking supplies, incenses, remedies and selected skill cards. |
| HYRULE WARRIORS LEGENDS — Nintendo 3DS · zmha.bin | Nintendo 3DS | Rupees, materials, map cards, weapon stars, ordinary seals, My Fairy names and existing fairy trust reductions. |
| ATELIER AYESHA — The Alchemist of Dusk · PS3 US/Japanese export | PlayStation 3 | Cole, existing stack reductions and searchable inventory quality, properties and effects. |
| DYNASTY WARRIORS 5 SPECIAL — Shin Sangokumusou 4 Special · Windows PC | Windows PC | Existing item ranks, stored officer attack/defense, weapon attack/weight and attributes; named records. |
| FIRE EMBLEM WARRIORS: THREE HOPES — Switch · extracted SlotData exports | Nintendo Switch | Gold reductions, owned Shez/Byleth name customization and searchable character/weapon records. |
| DYNASTY WARRIORS 8 EMPIRES — US · decrypted SYSTEM APP.BIN | PlayStation 3 | Existing custom-horse appearance choices; searchable horse stats and ability records. |
| WARRIORS OROCHI 3 ULTIMATE — US · decrypted APP.BIN · NPUB31505 | PlayStation 3 | Manual unallocated growth points and gems; searchable officer, weapon and inventory inspection. |
| NIOH 3 — Windows PC · USER revisions 0x01030001 / 0x01040000 | Windows PC | Amrita and Gold deductions, eighteen named ordinary consumable reductions; separate equipment inspection. |
| NINJA GAIDEN II — Original Xbox 360 / Xenia · extracted revision-6 story | Xbox 360 / Xenia | Yellow Essence, existing consumable and ammunition reductions; searchable inventory and separate Karma inspection. |
| DYNASTY WARRIORS: GUNDAM — US/EU · decrypted DATA.BIN + PARAM.SFO | PlayStation 3 | Learn skill flags and choose already learned equipped skills on six qualified level-30 pilots; progression inspection. |
| DYNASTY WARRIORS: GUNDAM REBORN — EU/Japan · decrypted DATA.BIN + original PARAM.SFO | PlayStation 3 | Spendable money and existing Amuro/Kamille Team Point reductions; searchable pilot progression, earnings and material storage. |
| DYNASTY WARRIORS: GUNDAM 3 — US · decrypted DATA.BIN + original PARAM.SFO | PlayStation 3 | Spendable money reductions; searchable Mobile Suit Laboratory EXP and license-bit storage. |
| TRINITY: SOULS OF ZILL O'LL — US · decrypted PLAY.DAT + original PARAM.SFO | PlayStation 3 | Spendable money reductions; searchable SP storage and named Areus, Dagda and Selene stat words. |
| NINJA GAIDEN BLACK — Original Xbox · SYSTEM.dat + original console EEPROM | Original Xbox | Restore numeric save-slot order; searchable thirty-slot time and list-position records. |
| FIST OF THE NORTH STAR: KEN'S RAGE — US/EU · decrypted DATA.BIN + PARAM.SFO | PlayStation 3 | Manual existing skill-point balances for eight base fighters; inspect progression resources. |
| FIST OF THE NORTH STAR: KEN'S RAGE 2 — EU · decrypted DATA.BIN + PARAM.SFO | PlayStation 3 | Unlock locked music, movie and event gallery entries; preserve existing collection states. |
| ROMANCE OF THE THREE KINGDOMS XIII — Original PC · revision 14 · TC | Windows PC | City gold, supplies, population, wounded troops, fealty, commerce, farming, culture and troop proficiencies. |
| FIRE EMBLEM: THREE HOUSES — Switch · gameplay save-format v13/v23 | Nintendo Switch | Instruction motivation, existing learned ability loadouts, gold and ordinary convoy quantity/durability reductions. |
| BERSERK AND THE BAND OF THE HAWK — EU PS Vita · decrypted PCSB01085 | PlayStation Vita | Gold deductions, eighteen named existing enhancement materials and searchable character status. |
| DEAD OR ALIVE 5 — Original US/EU PS3 PSN · SAVE_SYS.DAT + PARAM.SFO | PlayStation 3 | Sixty-three individual costume unlock controls and searchable costume records. |
| POKÉMON CONQUEST — US Nintendo DS · raw native save | Nintendo DS | Existing gallery Pokémon IV components and Speed IV; searchable gallery Pokémon records. |
| ATELIER RYZA — Ever Darkness & the Secret Hideout · original Switch main game | Nintendo Switch | Existing ordinary item/equipment quality 1–100; searchable inventory, equipment and read-only trait slots. |
| DYNASTY WARRIORS 8 — Xtreme Legends · US PS3 PSN NPUB31449 · APP.BIN + PARAM.SFO | PlayStation 3 | Gold, gems, facility/weapon materials, 82 officers’ stored stats, weapon-action aptitudes and existing weapon attribute ranks. |
| DRAGON QUEST BUILDERS 2 — Original Steam PC · CMNDAT.BIN | Windows PC | Existing named medicine/seed stack reductions; searchable pockets, bag and player/equipment status. |
| ATELIER RYZA 2 — Lost Legends & the Secret Fairy · original Switch | Nintendo Switch | Unspent skill-tree SP reductions; searchable existing inventory and equipment records. |
| DRAGON QUEST BUILDERS 2 — Original Nintendo Switch · CMNDAT.BIN | Nintendo Switch | Existing named medicine/seed stack reductions; searchable pockets, bag and player/equipment status. |
| PERSONA 5 STRIKERS — English Nintendo Switch · savedata export | Nintendo Switch | Money, Persona points, unspent BOND points and existing named consumable, ingredient, incense, remedy and skill-card stacks. |
| ROMANCE OF THE THREE KINGDOMS II — Original Chinese DOS · raw save copies | DOS PC | Owned-province gold and rice reductions; searchable province ownership, population and resource records. |
| PERSONA 5 STRIKERS — English PS4 · decrypted APP.BIN + original sce_sys/param.sfo | PlayStation 4 | Money, Persona/BOND points and existing named consumables, ingredients, incenses, remedies and skill-card stacks. |
| UNCHARTED WATERS: NEW HORIZONS — Original English DOS · KOUKAI2.DAT | DOS PC | Existing-slot gold and eight protagonist attributes; searchable campaign and sailor records. |
| ROMANCE OF THE THREE KINGDOMS: LEGEND OF LIU BEI — Original Traditional Chinese DOS · MSAVE0–4.R3S | DOS PC | Existing allied troop reductions and within-level EXP; searchable character and carried-item records. |
| ROMANCE OF THE THREE KINGDOMS III — Original Traditional Chinese DOS · SANGOKU3.SAV | DOS PC | Six existing officer abilities and owned-city resource/commerce reductions; searchable slots, cities and officers. |
| NOBUNAGA'S AMBITION: TENSHOUKI — Original Japanese Windows Power-Up Kit · SAVEDAT.n6p | Windows PC | Existing district Gold, Rice, Horses and Firearms reductions; searchable generals, castles, clans, treasures and slots. |
| PROJECT ZERO / FATAL FRAME — Original European PS2 · SLES-50821 PSU export | PlayStation 2 | Existing camera-point and base-upgrade tier reductions; searchable slots, camera functions and inventory. |
| ATELIER RYZA 3 DX — Alchemist of the End & the Secret Key · Steam PC revision 4 | Windows PC | Unspent skill-tree SP and gem reductions for rebuilding/duplication; searchable inventory, secret-key and Party records. |
| MONSTER RANCHER DS — US Nintendo DS · raw 32/64 KiB export | Nintendo DS | Existing matched monster stats and lifespan, breeder/ranch/monster names and gold reductions; searchable records. |
| TECMO SUPER BOWL — NES · compatible original 28-team battery SRAM | NES | Team control, healthy player conditions and per-slot playbooks; searchable standings, conditions and injury records. |
| WARRIORS OROCHI 4 — Original Windows PC · revision 20180720 | Windows PC | Gems, Crystals, Growth Points, officer Skill Points, existing weapon elements and Skill Orb reductions; searchable records. |
| WARRIORS OROCHI 4 ULTIMATE — Windows PC · revision 20200101 | Windows PC | Gems, Crystals, Growth Points, officer Skill Points and Upgrade Stones, existing Skill Orbs and attribute inventory; searchable progression and weapons. |
| SAMURAI WARRIORS 5 — Windows PC · revision 39 castle/menu slot zero | Windows PC | Gold, Stock EXP, shared Skill Points, Stock Weapon Mastery and building materials; searchable officers, weapons and mounts. |
| WARRIORS: ABYSS — Windows PC · revision A4 gameplay slots | Windows PC | Karma Embers and searchable persistent recruitment records; preserves original Steam owner context. |
| BANDIT KINGS OF ANCIENT CHINA — Original English Macintosh · SUI0/SUI1 data forks | Macintosh | Owned-prefecture Gold, Food, Metal and Fur reductions; existing hero Strength, Dexterity and Wisdom reductions. |
| NOBUNAGA'S AMBITION — Original English NES · 17-fief battery profile | NES | Owned active fief Gold and Rice reductions with native additive checksum validation. |
| GEMFIRE — NES · native structurally qualified battery records | NES | Player-owned province Gold, Food, Loyalty, Farming and Protection; searchable province records. |
| GEMFIRE — SNES · native structurally qualified battery records | SNES | Player-owned province Gold, Food, Loyalty, Farming and Protection; searchable province records. |
| BLADESTORM: THE HUNDRED YEARS’ WAR — Original EU BLES00113 · decrypted PLAYDATA + PARAM.SFO | PlayStation 3 | Money and existing positive book Skill Point reductions; searchable book records. |
| ATELIER FIRIS — The Alchemist and the Mysterious Journey · original Steam PC | Windows PC | Cole deductions and qualified existing ordinary basket/container quality reductions; searchable inventory. |
| BLUE REFLECTION: SECOND LIGHT — Original Steam PC · native tagged gameplay profile | Windows PC | Existing uniquely identified ordinary container quantity reductions; searchable inventory records. |
| ATELIER RYZA — Ever Darkness & the Secret Hideout · original Steam PC | Windows PC | Qualified existing ordinary item/equipment quality reductions; searchable inventory and Party equipment. |
| DYNASTY WARRIORS 8 — Xtreme Legends Complete Edition · plaintext Vita revision 0x131002F0 | PlayStation Vita | Resources, 82 officers’ stored stats, weapon-action aptitudes and existing weapon attribute ranks. |
| ONE PIECE: PIRATE WARRIORS — Original US PSN NPUB30836 · DATA.BIN + PARAM.SFO | PlayStation 3 | Thirteen named characters’ existing level-growth word reductions; searchable progression. |
| ONE PIECE: PIRATE WARRIORS 2 — Original EU PSN NPEB01795 · DATA.BIN + PARAM.SFO | PlayStation 3 | Primary spendable Berry reductions; searchable secondary currency and progression. |
| ONE PIECE: PIRATE WARRIORS 3 — Original EU PSN NPEB02211 · DATA.BIN + PARAM.SFO | PlayStation 3 | Existing progressed-character HP, Attack and Defense reductions; searchable progression and currency. |
| DYNASTY WARRIORS 8 — Original US PSN NPUB31234 · plaintext APP.BIN + PARAM.SFO | PlayStation 3 | Gold and Ambition facility/weapon material reductions; searchable resources. |
| ATTACK ON TITAN / A.O.T. WINGS OF FREEDOM — Original EU PCSB00898 · app0000.dat + sce_sys/param.sfo | PlayStation Vita | Money and existing positive numbered material-quantity reductions; searchable stored quantities. |
<!-- END SUPPORTED GAMES -->

## Download and use

Download the **Windows EXE** from the
[latest GitHub release](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/latest)
and run it. The **Windows ZIP** includes the same executable and documentation.
The standalone app needs no Python installation.

1. Make a separate copy of your save outside the game and Steam Cloud folders.
2. Search the **Game Library**, filter by series or platform, and choose
   **Open Editor**, then **Open Save Copy**. **Ctrl+F** searches all platforms.
3. Edit values or use the available bulk actions. **Find fields** and
   **Find records** help locate characters, equipment and inventory entries.
   **Adjust Selected** adds or subtracts from selected numbers;
   **Revert Selected** restores their opened values.
4. Check **Review Changes**; use **Undo** to reverse an edit batch.
5. Choose **Save As** to create an edited copy. Automatic backups and backup
   restore are available.

Return to **Game Library** to switch games. Your sessions and Light/Dark theme
are retained.

## Run from source

From the repository root with Python 3.10 or newer and Tkinter:

```powershell
python -m pip install -e .
python -m koei_editor
```

## Contribute

Read [CONTRIBUTING.md](CONTRIBUTING.md) for development and new adapters.
AI coding agents should read [AGENTS.md](AGENTS.md).
The [documentation index](docs/README.md) includes build instructions and formats.

## Contact

Discord: `mexicannn`.
[Mexican's Steam profile](https://steamcommunity.com/id/theonlyjuandeagingmexican/).

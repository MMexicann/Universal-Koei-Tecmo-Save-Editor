# Universal Koei Tecmo Save Editor

A free Windows save editor by **Mexican**, with a game library, shared Light/Dark
themes, searchable records, backups, Undo and Review Changes. Switch between
games while keeping each editing session open.

**Development source:** additions below are available in source. The latest
Windows download remains v1.6 until the next release.

## Supported games

Select the game and platform that match your save. Console editors open
extracted or decrypted save exports: `.psu` for
PlayStation 2, `APP.BIN` for Wii U and DW7 PS3, `DATA.BIN` for SW4 PS3, and `svdt`
for Age of Calamity. Some PS3 profiles require the original `PARAM.SFO` beside
the copied gameplay file and edited output. Export and reimport/resign PS3 saves
with Apollo Save Tool; this editor does not rebuild `PARAM.PFD` or sign exports.

Meruru Plus for PS Vita opens a copied, decrypted `USR-DATA0000` with its original
`sce_sys/param.sfo`. Export and reimport it with a Vita save manager.

Ninja Gaiden II opens extracted Xbox 360/Xenia story `.dat` copies; CON/STFS
packages require a separate extraction and reintegration workflow. Sigma 2 and
Ninja Gaiden 2 Black use different formats.

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
| ATELIER SOPHIE — Original Steam PC · GAMEDATA slots | Windows PC | Cole, Tess tickets and existing basket/container quality; searchable inventory and alchemy progression. |
| ATELIER RYZA 2 — Lost Legends & the Secret Fairy · original Steam PC | Windows PC | Ordinary item/equipment quality from 1–100 and qualified unspent skill-tree SP reductions; inventory inspection. |
| ATELIER MERURU PLUS — The Apprentice of Arland · US decrypted PCSE00296 | PlayStation Vita | Cole; 13 named characters’ base attack/defense/speed, base HP/MP/LP increases and current-gauge reductions; searchable records. |
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
| FIST OF THE NORTH STAR: KEN'S RAGE — US/EU · decrypted DATA.BIN + PARAM.SFO | PlayStation 3 | Manual existing skill-point balances for eight base fighters; inspect progression resources. |
| FIST OF THE NORTH STAR: KEN'S RAGE 2 — EU · decrypted DATA.BIN + PARAM.SFO | PlayStation 3 | Unlock locked music, movie and event gallery entries; preserve existing collection states. |
| ROMANCE OF THE THREE KINGDOMS XIII — Original PC · revision 14 · TC | Windows PC | City gold, supplies, population, wounded troops, fealty, commerce, farming, culture and troop proficiencies. |
| FIRE EMBLEM: THREE HOUSES — Switch · gameplay save-format v13/v23 | Nintendo Switch | Instruction motivation, existing learned ability loadouts, gold and ordinary convoy quantity/durability reductions. |
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

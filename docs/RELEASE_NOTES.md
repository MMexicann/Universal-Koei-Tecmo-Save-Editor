# Universal Koei Tecmo Save Editor v1.7

26 additional game/platform editors bring the library to **48 profiles across nine platforms**, with richer equipment controls and a searchable interface. Mexican's branding, Light/Dark themes, backups, Undo and Review Changes remain available throughout.

## New editors

| Game | Platform | Features |
| --- | --- | --- |
| Atelier Sophie | Windows PC | Cole, Tess tickets and existing basket/container item quality. |
| Atelier Ryza 2 | Windows PC | Existing item/equipment quality and unspent skill-tree SP reductions. |
| Fatal Frame II: Crimson Butterfly REMAKE | Windows PC | Shared system Photo Point reductions; inventory, camera and collection views. |
| Warriors Orochi | Windows PC | Growth Points, existing weapon bonuses/attributes and owned weapon selection. |
| Samurai Warriors 4-II | Windows PC | Gold, tomes, officer stats, existing weapons and mount stats/selection. |
| Samurai Warriors 2 | Windows PC | Money, officer growth, acquired skills and existing weapons. |
| Dynasty Warriors 5 Special | Windows PC | Item ranks, officer attack/defense and existing weapon attack, weight and attributes. |
| Dynasty Warriors 8 Empires | Windows PC | Existing custom-horse appearance choices and searchable horse records. |
| Wo Long: Fallen Dynasty | Windows PC | Genuine Qi, copper, accolades, existing stack reductions and battle-set names. |
| Persona 5 Strikers | Windows PC | Money, Persona/BOND points, existing consumables, cooking supplies, incenses, remedies and selected skill cards. |
| Nioh 3 | Windows PC | Amrita/Gold deductions and eighteen named consumable reductions. |
| Romance of the Three Kingdoms XIII | Windows PC | City gold, supplies, population, wounded troops, fealty, development and troop proficiencies. |
| Atelier Ayesha | PlayStation 3, US/Japan | Cole and existing stack reductions; searchable item quality, properties and effects. |
| Dynasty Warriors 8 Empires | PlayStation 3, US | Existing custom-horse appearance choices in SYSTEM saves. |
| Warriors Orochi 3 Ultimate | PlayStation 3, US | Unallocated growth points and gems; searchable officers, weapons and inventory. |
| Dynasty Warriors: Gundam | PlayStation 3, US/EU | Learn skills and select learned equipped skills on six level-30 pilots. |
| Fist of the North Star: Ken's Rage | PlayStation 3, US/EU | Existing skill-point balances for eight base fighters. |
| Fist of the North Star: Ken's Rage 2 | PlayStation 3, EU | Music, movie and event gallery unlocks. |
| Dead or Alive 5 | PlayStation 3, original US/EU PSN | Sixty-three individual costume-unlock controls. |
| Fire Emblem Warriors: Three Hopes | Nintendo Switch | Gold reductions, owned Shez/Byleth names and searchable character/weapon records. |
| Fire Emblem: Three Houses | Nintendo Switch | Motivation, existing ability loadouts, gold and ordinary convoy quantity/durability reductions. |
| Hyrule Warriors Legends | Nintendo 3DS | Rupees, materials, map cards, weapon stars/seals, My Fairy names and existing fairy trust reductions. |
| Atelier Meruru Plus | PlayStation Vita, US | Cole and thirteen named characters' base stats, base HP/MP/LP increases and current-gauge reductions. |
| Berserk and the Band of the Hawk | PlayStation Vita, EU | Gold deductions and eighteen named existing enhancement materials. |
| Ninja Gaiden II | Xbox 360 / Xenia | Yellow Essence and existing consumable/ammunition reductions. |
| Pokémon Conquest | Nintendo DS, US | Existing gallery Pokémon IV components and Speed IV, with searchable names for all 200 species. |

## Richer existing editors

- **Dynasty Warriors:** DW4 Hyper/XL gain owned harness, orb and general-item equipment; Hyper adds created-officer cosmetics. DW6 gains existing weapon elements and damage bonuses. DW7 XL adds owned-weapon selection and unlearned seal-meter reductions. DW8 XL can reorder an officer's two equipped weapons.
- **Orochi and All-Stars:** WO3 Ultimate Definitive gains upgrade stones, existing ordinary-item equipment, additional weapon attributes and attack-reinforcement reductions. Orochi Z gains owned-weapon selection and EXP edits within the current level. All-Stars gains owned Hero Card selection.
- **Hyrule and inspection:** Hyrule Warriors Definitive Edition gains weapon stars and ordinary seal KO counters. Origins adds searchable weapon upgrades/traits; Samurai Warriors 4 PS3 adds searchable weapons and attached skills.

## Easier editing

- Search games by title, platform or feature; filter by series/platform and resume open sessions from compact library cards. **Ctrl+F** searches the full library.
- Sort field, equipment and Review Changes tables by column; copy selected inspector rows with their headings.
- **Adjust Selected** adds or subtracts from selected numbers in one Undo batch. **Revert Selected** restores their opened values.
- Named equipment choices, searchable inventories and validated bulk actions keep large editors manageable.

Download **UniversalKoeiTecmoSaveEditor-v1.7.exe** for the standalone Windows app, or the **Windows ZIP** for the same executable and documentation. No Python installation is needed. Open a separate save copy, review your edits and use **Save As**.

Console/handheld editors use extracted or decrypted exports. Reimport/resign PS3 saves with Apollo Save Tool; use a Vita save manager for Vita exports and an external extraction/reintegration tool for Xbox 360 packages. Pokémon Conquest opens raw `.sav` copies.

From source with Python/Tk: `python -m pip install -e .`, then `python -m koei_editor`.

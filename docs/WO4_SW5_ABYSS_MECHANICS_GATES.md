# WO4, Samurai Warriors 5 and Warriors: Abyss mechanic gates

This supplement records official mechanics and independently observed native
semantics for the supplied-input investigation. It does not itself register an
editor or establish game-load validation. Format writers and current qualification
belong in [Orochi research](OROCHI_RESEARCH.md), [Samurai research](SAMURAI_RESEARCH.md)
and [Pirate/Abyss research](PIRATE_ABYSS_RESEARCH.md). No game binaries were executed;
external source copies, disassembly and player files remain private.

## Warriors Orochi 4 and Ultimate

The original manual is at [WO4](https://www.koeitecmoamerica.com/manual/wo4/);
the separate expansion manual is at
[WO4 Ultimate](https://www.koeitecmoamerica.com/manual/wo4u/en/).
The original manual does not use the expansion's `/en/` path.

| System | Mechanics and safe editing gate |
| --- | --- |
| Party | Three playable officers, four support officers and a mount. Power/Technique/Speed support benefits depend on complete groups of five support points; preserve those derived totals. |
| Level and EXP | Shared Growth Points are distributed into an officer's EXP. Level comes from EXP and game parameter tables; do not treat a runtime level byte as an independently writable native level. |
| Skill Points | Level-up awards and converted Skill Orbs supply a per-officer spendable pool. Learning a skill also changes learned bits and applies consequences; currency editing must preserve those bits. |
| Camp Rewards | Purchased with Gems and Crystals, with level/sortie prerequisites. Quantity does not establish reward ownership or eligibility. |
| Bonds | Pair-specific progress from battle/training affects support, lottery rewards and training returns. Preset pairs can trigger events; preserve reward/event flags when editing resources. |
| Weapons | Attack, rarity, compatibility, attached attributes, element inventory and sockets are separate. Compatibility gained through use derives an attack bonus. Sale/dismantling consumes a weapon; inventory refill cannot recreate ownership. |
| Fusion | Existing element quantities are spendable materials. Additional sockets cost Gems/Crystals. Acquiring an undiscovered element can require a discovery flag; refill only admitted existing entries unless both are proved. |
| Results | Rank depends on time and defeated enemies. Rank, objective rewards, lotteries and reward claims are distinct records; no resource action should complete a stage. |

Official chapters: [original Party](https://www.koeitecmoamerica.com/manual/wo4/4200.html),
[Upgrades](https://www.koeitecmoamerica.com/manual/wo4/4300.html),
[Weapons](https://www.koeitecmoamerica.com/manual/wo4/4400.html),
[Results](https://www.koeitecmoamerica.com/manual/wo4/4900.html),
[Bonds](https://www.koeitecmoamerica.com/manual/wo4/5300.html).

### Edition-specific limits and native semantic cross-checks

| Pool | Original WO4 | Ultimate | Preserved partner |
| --- | ---: | ---: | --- |
| Spendable Gems | 9,999,999 | 9,999,999 | Lifetime earned Gems |
| Spendable Crystals | 999 | 999 | Lifetime earned Crystals |
| Shared Growth Points | 999,999 | 99,999,999 | Officer EXP/level/rewards |
| Element inventory per entry | 999 | 9,999 | Discovery and unusual entries |
| Per-officer Skill Points | Requires original native qualification | 999 | Learned skills and effects |
| Unspent Upgrade Stones | Ultimate-only mechanic | 9,999 | Allocated upgrades/promotion |

Wallet and Growth bounds above come from edition-specific native clamp routines;
element limits additionally match each edition's official Weapons chapter. These
limits must not be transplanted between formats. An existing higher/unusual value
remains preserved and excluded from a Max action.

Ultimate static source evidence (RVA addresses identify the supplied matching
module, not a universal offset for every build):

- `213160` grants/deducts the story-global `+CC` pool, bounded 9,999,999;
  positive grants with the history flag also update `+D0`.
- `213370` grants/deducts `+D4`, bounded 999; flagged positive grants update `+D6`.
  `213310` independently adjusts `+D8`, bounded 99,999,999.
- `465170` applies a selected amount through officer EXP routine `20DF90`, then
  deducts that same amount from `+D8`: the Growth Points training pool.
- `2193A0` gives 300,000 to `+D8` and 100 to `+D4` behind one-time bonus flags.
  The [official product page](https://www.koeitecmoamerica.com/wo4u/product/)
  independently names the Deluxe bonuses as 300,000 Growth Points and 100
  Crystals. Arena Points are a separate bonus/currency.
- `20E820` adjusts officer runtime `+78` Skill Points, bounded 999. The
  `20EB3F` purchase chunk checks skill-specific cost, debits that pool, sets a
  learned-skill bit at `+68` and calls `211050` to apply the consequence.
  `20F26E` converts a story-global `+166` Skill Orb by consuming one and granting
  Skill Points through the same setter. The orb getter clamps 999; the full
  acquisition writer must be qualified before offering orb refill/Max.
- `20F9C0` adjusts runtime `+178` unspent Upgrade Stones, bounded 9,999, and is
  called by level-up after promotion. `20F7A0` refunds four allocated upgrades
  (`+17C/+17E/+180/+182`) into this pool through a parameter-table cost, then
  clears those allocations. `20FE8D` and sibling spenders perform the converse.
  Changing only an admitted promoted officer's pool must leave allocations intact.
- `210A70` resets EXP, promotion and the stone pool after refund/reset processing.
  Raw level/promotion writes would bypass this progression machinery.

[Ultimate Upgrades](https://www.koeitecmoamerica.com/manual/wo4u/en/4300.html)
requires level 100 for promotion, returns the officer to level 1 and permits nine
promotions. Level-up after promotion grants Upgrade Stones; promotion count also
unlocks skills. Resetting upgrades refunds allocations, whereas resetting EXP
and skills restores default growth and loses Upgrade Stones.

[Ultimate Weapons](https://www.koeitecmoamerica.com/manual/wo4u/en/4400.html)
adds sacred-treasure switching gated by story and weapon crafting using
Gems/Crystals plus Infinity materials.
[Infinity features](https://www.koeitecmoamerica.com/manual/wo4u/en/8100.html)
recruit allies separately from Story. Its five support effects concern EXP,
Gems, Crystals, weapons and chests, rather than Story's support-point groups.
Resetting Infinity clears ally/tower parameters while preserving materials and
crafted weapons. [Floor objectives](https://www.koeitecmoamerica.com/manual/wo4u/en/8200.html)
and escape conditions control advancement; fast-clear advancement is conditional.

## Samurai Warriors 5

The [official Camp chapter](https://www.koeitecmoamerica.com/manual/sw5/en/4100.html)
establishes dependencies that a rich editor must preserve:

- My Castle Rank comes from Musou story progression and limits building upgrades.
  Dojo level limits both officer level and weapon mastery rank.
- Stock EXP and Stock Weapon Mastery are distinct shared pools. Officer Skill
  Points purchase skills; officer levels and mastery unlock different actions.
- A weapon's rank must not exceed its owner's mastery rank to equip it. Gold and
  Skill Gems improve weapons; Blacksmith level limits attached skill levels.
- Weapon crafting changes weapon type and requires the appropriate building
  level. Shop stock/rare items also depend on building level.
- Stables level limits mount capacity. Mount EXP derives level/abilities;
  skill drills consume a donor mount, rather than merely adjusting a skill byte.
- Citadel officer pairs gain friendship by marching together; Hermit's Retreat
  events have thresholds. Friendship and event claims are separate.

[Game modes](https://www.koeitecmoamerica.com/manual/sw5/en/1100.html) distinguish
Musou story unlocks, Citadel material rewards, Free Mode and interim battle saves.
The [inventory chapter](https://www.koeitecmoamerica.com/manual/sw5/en/4400.html)
requires sale when weapon/mount capacity is exceeded. The official manual does
not establish all numeric maxima: native building gates and complete record
ownership are required before Max or equipment actions. Multiple serialized save
copies/checkpoints additionally need native current-copy selection; a plausible
Gold value at the same relative offset in each copy is not sufficient.

## Warriors: Abyss

Official [site](https://www.koeitecmoamerica.com/warriors_abyss/us/) and patch notes
establish revision-sensitive persistent systems. Patch numbers here refer to the
game, not this editor's release number.

| Source | Mechanic and dependency |
| --- | --- |
| [Update 3](https://www.koeitecmoamerica.com/warriors_abyss/us/update3.html) | Depths of Torment requires the patch, first Gouma defeat and saving a Soul Record at Results. Records of Sin are separate rewards. Change Music and tracks have completion/achievement gates. |
| [Update 4](https://www.koeitecmoamerica.com/warriors_abyss/us/update4.html) | Karma Embers cap rises from 999,999 to 9,999,999. Cumulative Levels spend Karma; their ceiling grows through Training Hall First Completion Bonuses. Levels above 500 derive a permanent movement-speed increase. |
| [Update 4](https://www.koeitecmoamerica.com/warriors_abyss/us/update4.html) | Unique Weapon ownership gives +50% Attack; Transcendence gives +100%. Traversal progress becomes shared across heroes. Records of Sin conversion values depend on record rank. |
| [Update 6](https://www.koeitecmoamerica.com/warriors_abyss/us/update6.html) | Sealing Ceremony bans already unlocked heroes/formations/treasures after first Gouma defeat. Customization can temporarily undo bans or disable persistent level/weapon benefits without erasing ownership. |
| [Update 7](https://www.koeitecmoamerica.com/warriors_abyss/us/update7.html) | Extra Records rewards apply from Traversal 1. Full inventory auto-converts rewards into Karma. Change Level Bosses requires at least ten Gouma defeats; hidden challenge selections require prior completion. |
| [Update 8](https://www.koeitecmoamerica.com/warriors_abyss/us/update8.html) | Additional records can immediately convert to Karma. Fixed unavailable-DLC Unique Weapons leaving Collection markers stuck: ownership, entitlement and new-item flags are distinct. |

Karma funds Hall of Bonded Souls unlocks, whereas run EXP/rewards, Soul Records,
Records of Sin and permanent cumulative growth are distinct systems. DLC may
unlock associated heroes after the tutorial; bonus Karma is claimed after the
first Results screen. Do not create entitlements or claim flags as a side effect
of currency editing. Native revision/cap evidence must agree with the patch's
mechanics before an old save receives the newer ceiling.

## Public implementation leads and exclusions

A bounded public-source search included exact game names, native save filenames,
DLL names, English/Chinese editor queries and source-bearing repositories. No
complete public native PC gameplay-save writer was established by this search;
this is not a claim that none exists.

- [Fragonite/zmod](https://github.com/Fragonite/zmod/tree/81dfd576e46037c85fcbc5892304863d45dee772)
  supplies runtime WO4U corroboration: officer promotion at `+177` and zero-based
  runtime level at `+378`. It is a runtime mod, has no declared licence, and was
  consulted for facts only; no source/catalog was imported.
- [Wynathan/wynathan-abyss](https://github.com/Wynathan/wynathan-abyss/tree/10cafe7f656740ebcab192ab81215347e1a81a00)
  and [Suyukn/warriors-abyss-tool](https://github.com/Suyukn/warriors-abyss-tool/tree/694eb77f21b9d9ef85a342d38a1f0402c93256d5)
  are MIT mechanics/build planners, not native save codecs. Normal/transcended
  emblems, traits, summon effects and tactics are useful mechanic distinctions;
  their static catalogs/assets were not copied.
- The Abyss text-change patcher writes localization assets, not gameplay saves.
  The Compile Heart Orochi-engine asset toolkit is unrelated to Koei's Orochi
  saves. Neither qualifies a save profile.
- Trainers, commercial PS4 patches, screenshots and console-platform mappings
  cannot establish the missing PC disk serializer, integrity or native field IDs.

Use the per-game format/test evidence for current implemented scope. These
mechanics explain the required dependencies; they do not invent unproved fields,
attribute ID dictionaries, legitimate reward claims or story completion actions.

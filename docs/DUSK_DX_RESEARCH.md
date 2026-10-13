# Dusk DX PC: native inputs found, gameplay writes blocked

This pass inspected independently shared PC files for Ayesha DX and Escha &
Logy DX. It did not register a PC editor: the native PC loader, integrity and
writable gameplay schema remain unqualified. These are separate profiles from
the [implemented Ayesha PS3 export adapter](AYESHA_PS3_FORMAT.md), which was not
modified. No game or third-party editor executable was run. Archives, extracted
saves, owner context and third-party source copies remain outside the checkout.

## Actual input evidence

| Exact title | Independently shared input inspected | Result and precise next input |
| --- | --- | --- |
| Ayesha DX, PC app1152300 | [SaveGame.Pro gameplay archive](https://savegame.pro/pc-atelier-ayesha-the-alchemist-of-dusk-dx-savegame/) contains a complete `GAMEDATA77`; a [separate public author's archive](https://www.patreon.com/posts/atelier-ayesha-35367735) contains `GAMEDATA16`, `GAMEDATA17` and `SYSDATA`. | All three gameplay files are 813,056 bytes and begin `57dc320100000000`. Their observed byte order and size differ from the 742,400-byte big-endian PS3 profile. The second author explicitly identifies a repack; neither source establishes the exact current Steam build. Need a Steam build/language-labelled original gameplay file, unchanged re-save, controlled displayed Cole purchase/sale pair and PC loader/writer or independently proved integrity coverage. |
| Escha & Logy DX, PC app1152310 | [SaveGame.Pro archive](https://savegame.pro/pc-atelier-escha-logy-alchemists-of-the-dusk-sky-dx-savegame/) contains sixteen `GAMEDATA00.pcsave` through `GAMEDATA15.pcsave` files and `SYSDATA.pcsave`. | Gameplay sizes range from 63,760 to 76,544 bytes. Each has a 256-byte plaintext prefix followed by an encoded body; system data is 3,840 bytes. Encoding, compression, complete framing and native integrity are unresolved. Need exact Steam build/language, matched original/decoded pair or PC serializer evidence, unchanged control and one resource/item action pair. These sixteen saves establish available native research inputs, not a qualified decoder or field map. |
| Shallie DX, PC app1152320 | [Barrel Wisdom's public PC-save collection](https://barrelwisdom.com/blog/atelier-pc-saves) provides system data. A fresh [SaveGame.Pro Shallie DX archive](https://savegame.pro/pc-atelier-shallie-alchemists-of-the-dusk-sea-dx-savegame/) additionally supplies fifteen actual `GAMEDATA*.pcsave` gameplay snapshots spanning chapters, both protagonists, clear/NG+ and endings. | Actual gameplay is now available for research, separately from the system unlock file. The checksum-enforcing Gust codec still rejects the acquired gameplay bodies with a native marker mismatch. Need native title/platform loader or matched original/decoded pair establishing framing, compression and integrity, exact build/language and controlled resource/item actions. Neither the collection labels nor additional native files establish a writer. |

The initial inspection only extracted and read files. There is no demonstrated
native decode/encode roundtrip, surgical gameplay edit, GUI save qualification
or edited game-load/re-save result for these PC profiles. No plausible value,
PS3 address, runtime pointer or shared Gust signature was promoted to a disk
field. GameFAQs' PC/DX save pages list older PS3 exports under their actual
platform headings; the page title does not convert them to PC/DX evidence.

The existing checksum-enforcing Sophie 2/Ryza body decoder rejects the observed
Escha & Logy gameplay body and Shallie system file at the native boundary
candidates. It was not changed to ignore their marker/integrity failures.
Likewise, private read-only probes of the published asset scrambling variants
did not establish native save integrity. An asset key list is not a save decoder.

## Important mechanics and exact feature blockers

All mechanics below are **blocked for PC gameplay editing** until the relevant
title's native profile qualifies. The official manuals document rules and
dependencies; they do not establish serialized offsets or storage limits.

### Ayesha DX

- **Cole and inventory quantities:** obtain a displayed sale/purchase pair and
  occupied-record/item-kind evidence. Stack counts, equipped instances,
  registered shop items and new acquisition must remain distinct.
- **Quality, traits, properties and effects:** [item data](https://www.koeitecmoamerica.com/manual/duskdx/ayesha/en/4300.html)
  distinguishes item-specific traits from transferable properties. Effect
  applicability depends on the item's attribute bands; increasing attributes
  can remove an effect. Need native item categories, property-class compatibility
  and synthesized before/after records, rather than an unrestricted ID picker.
- **Synthesis, recipes, alchemy EXP and skills:** [synthesis](https://www.koeitecmoamerica.com/manual/duskdx/ayesha/en/3600.html)
  requires the recipe's ingredients and alchemy level. Maximum synthesis CP is
  twice alchemy level; the trait stock yard holds five traits. Property stock
  and available skills depend on growth. Need EXP thresholds, learned-skill and
  recipe ownership evidence separately from an experience balance.
- **Character growth and memory diary:** [Notes](https://www.koeitecmoamerica.com/manual/duskdx/ayesha/en/3200.html)
  explains that memory points buy diary bonuses such as HP increases. Need a
  controlled earn/spend pair that separates balance, history and purchased
  bonuses; writing every memory-related word identically is not justified.
- **Equipment, friendship, exploration, albums and library:** need native
  occupied ownership/reference maps, friend-event thresholds and separate
  discovery/collection/reward records. Story, endings and calendar edits remain
  separate from resources, even on a clear save.

### Escha & Logy DX

- **Cole versus rank and activity funds:** [main menu](https://www.koeitecmoamerica.com/manual/duskdx/escha-logy/en/4100.html)
  distinguishes current spending money from performance rank and monthly funds.
  Assignment reporting grants rank points and line bonuses; monthly funds
  depend on assignment/rank history. Need a purchase/sale pair and a separate
  funds receipt pair. Calendar rewinds must not replay these rewards.
- **Inventory versus adventure-item uses:** the same manual states a container
  limit of 99 per item, while adventure equipment automatically refills in town.
  Its equip cost and available equipment frames constrain use. Need separate
  quantity, remaining-use, synthesized capacity and equipped-reference records;
  99 is not a universal field cap.
- **Effect strength, traits, effects and properties:** [item data](https://www.koeitecmoamerica.com/manual/duskdx/escha-logy/en/4300.html)
  gives an effect-strength bar maximum of 120. Item-specific traits/effects do
  not inherit; properties do, with PP and a three-property limit. Attribute
  points used by synthesis skills cap at five per attribute. Need matching
  native item/recipe applicability and property inheritance rules. These limits
  do not prove a raw quality/EXP/quantity field or its encoding.
- **Alchemy/battle EXP, recipes and equipment:** need exact growth curves,
  learned-skill/recipe ownership and separate derived equipment effects. A level
  alone does not supply those dependencies.
- **Assignments, experiments, requests, friendship, exploration and journal:**
  need prerequisite, paid-cost, report/reward and discovery maps. Four-month
  assignments, true-ending/clear history and calendar/event state remain outside
  resource editing. [Clear-data rules](https://www.koeitecmoamerica.com/manual/duskdx/escha-logy/en/2400.html)
  carry money/equipment to subsequent playthroughs, not every progress field.

### Shallie DX

- **Cole, inventory and equipped use counts:** actual public gameplay snapshots
  are now acquired, but their native bodies remain undecoded. Qualify the
  codec/integrity, then obtain purchase/sale and item-use/refill pairs. The
  separate system difficulty file cannot establish any of these fields.
- **Synthesis, equipment frames, effect strength and properties:** [item data](https://www.koeitecmoamerica.com/manual/duskdx/shallie/en/4300.html)
  distinguishes remaining uses from synthesized capacity and equipment frames.
  Synthesis can alter both. Its effect-strength bar tops out at 120, while
  effects are item-specific and depend on attribute bands. PP permits up to
  three inherited properties. Need native item-kind/capacity/applicability
  evidence before increasing uses or writing properties/effects.
- **Battle/alchemy growth, skills and friendship:** [character status](https://www.koeitecmoamerica.com/manual/duskdx/shallie/en/4200.html)
  has a distinct Growth System after levelling. Friendship affects events and
  assists. Need separate EXP thresholds, growth currency/purchased nodes,
  prerequisite and friend-event evidence; these are not independent maxable
  resource scalars.
- **Motivation, exploration, collections and Life Tasks:** [Life Tasks](https://www.koeitecmoamerica.com/manual/duskdx/shallie/en/3200.html)
  ties motivation to task completion and exploration actions. Main tasks can
  trigger events or advance chapters; free tasks award type-specific bonuses.
  Need separate current motivation, task history, claimed rewards, chapter and
  discovery records. A task-completion bulk edit would cross story/reward
  dependencies and is not a resource feature.

## Source and licence boundaries

[bbfox0703's Cheat Engine tables](https://github.com/bbfox0703/Mydev-Cheat-Engine-Tables)
contain separate runtime scripts for all three DX games. They were read as
leads, never executed or copied into the project. Runtime addresses and trainer
values do not establish disk serialization or legitimate bounds.
[VitaSmith's Gust tools](https://github.com/VitaSmith/gust_tools) document asset
formats; their `.e` codec is not native save evidence. The MIT Ayesha PS3 editor
remains a source for its explicitly documented console profile only.

## Additional Gust candidate: Nelke PC

[ValveSoftware/Proton issue 2580](https://github.com/ValveSoftware/Proton/issues/2580)
contains an independently shared actual PC `SAVE DATA01.pcsave` reproducer for
app886820. The privately inspected file is 392,900 bytes and its plaintext title
identifies `Nelke and the Legendary Alchemists 01.00`; its summary reports turn
3, weekday and first playthrough. The opaque gameplay body remains undecoded.
The existing Sophie 2/Ryza decoder does not qualify it, and no bypass or schema
transfer was added.

Need a native loader/writer or matched original/decoded pair that proves
framing, compression and checksums, a second unchanged save/re-save control,
current Steam build context and a displayed purchase/sale action pair. The
[official PC manual](https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/886820/manuals/Nelke_win%28EN%29.pdf)
separates weekday management, holiday activities and turn-based tasks. Money
must be mapped separately from production stock, population, wages/profit,
facility assignments, research, friendship and task rewards. Those systems need
their own controlled production, purchase, research or relationship pairs;
changing a turn/task completion word would affect story and reward dependencies.
No Nelke gameplay edit, native roundtrip or actual game-load result is claimed.

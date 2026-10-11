# Lulua and Nelke Switch: native exports acquired, writers blocked

These are research candidates, not supported gameplay editors. Complete public
Switch exports are available, but neither title has a qualified save decoder,
native integrity implementation or unchanged decode/encode roundtrip. No game
or third-party editor executable was run. Player files, downloaded source,
private probes and manual images remain outside the repository.

## Native evidence and codec checks

The public [NX_Saves collection](https://github.com/Viren070/NX_Saves/tree/main/nintendo/switch/savegames)
labels the following archives with their exact Switch title IDs. Its archive
labels do not independently establish game update, region or DLC configuration.

| Candidate | Complete acquired exports | Result |
| --- | --- | --- |
| Atelier Lulua: The Scion of Arland, Switch `0100B1400CD50000` | The Complete archive contains `GameData00/data.dat` (83,968 bytes), `GameData01/data.dat` (84,144 bytes) and `SystemData/data.dat` (2,368 bytes). Separate GameData00 and GameData01 archives are also available. | Gameplay files begin with little-endian word 1 and have an apparent 256-byte plaintext metadata prefix followed by an opaque body. No decoded gameplay schema is established. |
| Nelke & the Legendary Alchemists: Ateliers of the New World, Switch `01006ED00BC76000` | The Super Starter archive contains `SAVE_DATA_00` (128,096 bytes) and `SYSTEM_DATA` (1,616 bytes). | Gameplay has a plaintext Nelke title prefix and zero padding to the apparent `0x800` body boundary. Its modified-starter provenance is not a controlled original baseline or proof of legitimate caps. |

The existing checksum-enforcing Sophie 2/Ryza save decoder rejects these native
files with an encrypted-body marker mismatch. Body probes at `0x100`, aligned
boundaries through `0x200`, and larger plausible boundaries including `0x800`
and `0x1000` did not qualify it. Changing word endianness alone did not qualify
the observed gameplay bodies. No marker or checksum rejection was bypassed.

[VitaSmith/gust_tools](https://github.com/VitaSmith/gust_tools) provides explicit
**asset** `.e` scrambling seeds for A20 (Lulua) and ANW (Nelke). Read-only probes
of those documented asset seeds and chunked scrambling, plus big/little endian
and extra-PRNG variants, did not produce a valid footer for either Lulua gameplay
slot or Nelke gameplay. The tools' [save request 67](https://github.com/VitaSmith/gust_tools/issues/67)
and [save request 86](https://github.com/VitaSmith/gust_tools/issues/86) explicitly
decline save-codec implementation. Asset support is therefore not save support.

Public PS4 SaveWizard codes supply a useful Lulua **lead**: separate named
`m_unitContainer` and `m_unitBasket` arrays, 32-byte records, and distinct item ID,
quality, three traits, four effects, use count and quantity fields. A commercial
patch service can handle integrity outside the visible patch list. Those facts
do not prove native Switch structure, ownership, an unencrypted save, or the
absence of native checksums. No restricted code or item/trait catalog was copied.
The searched public Lulua trainer repository targets process memory and supplies
no native save serializer; advertised memory features are not disk mappings.

## Lulua mechanic coverage checklist

The [official multi-platform manual](https://www.koeitecmoamerica.com/manual/lulua/en/)
establishes the following systems. All writes remain blocked first by the native
codec/integrity qualification above, then by the specific field evidence below.

| Important mechanic | Rules to preserve and next field proof |
| --- | --- |
| Cole and owned inventory | Obtain a displayed purchase/sale pair and identified occupied records. The [main menu](https://www.koeitecmoamerica.com/manual/lulua/en/5100.html) distinguishes the town container from the limited gathering basket; neither may be treated as unlimited empty-slot creation. |
| Quality, traits, effects, awakened effects and boost items | [Synthesis](https://www.koeitecmoamerica.com/manual/lulua/en/7200.html) distinguishes item quality from elemental properties, traits and recipe/category-dependent awakened effects. TP constrains trait inheritance. Multiple synthesis averages material properties and does not inherit traits or awakened effects. Need title/platform-qualified record layout, item categories, applicability and single synthesis controls; a quality cheat target does not establish a natural cap. |
| Remaining uses, capacity and quantity | The same manual displays both use count and produced quantity. [Interrupt](https://www.koeitecmoamerica.com/manual/lulua/en/8300.html) can work even when item uses reach zero, with slower gauge refill. Need use/refill and synthesis-capacity pairs; zero must not be mistaken for an unowned item, and synthesized capacity must not be inferred from a cheat value. |
| Equipment and party formation | [Equipment](https://www.koeitecmoamerica.com/manual/lulua/en/5200.html) requires a weapon, permits two accessories, and restricts usable/Interrupt items to alchemists. The number of equipable tools grows with story progress. [Party](https://www.koeitecmoamerica.com/manual/lulua/en/5300.html) permits up to three attackers and two supporters, with combination-dependent Primal Arts. Need owned references, character eligibility and slot/prerequisite maps; no universal equipment-ID picker. |
| Battle EXP, level, base stats and skills | [Status](https://www.koeitecmoamerica.com/manual/lulua/en/5400.html) distinguishes accumulated EXP from EXP to next level. Total equipped-item quality contributes to ATK/DEF/SPD, so displayed totals are not independent base fields. Active, Assist and Passive skills differ. Need growth thresholds, base/derived separation and learned-skill prerequisites. |
| Alchemy EXP, level, recipes and TP | [Synthesis](https://www.koeitecmoamerica.com/manual/lulua/en/7100.html) requires recipe ownership and sufficient alchemy level; recipes come from books or Alchemyriddle. Need controlled synthesis/recipe purchase pairs, thresholds and TP dependencies. |
| Friendship and character events | [Status](https://www.koeitecmoamerica.com/manual/lulua/en/5400.html) says friendship rises with battles and time and can enable special events. Need separate current bond, event history and reward ownership records. |
| Exploration, tools and collections | [Gathering](https://www.koeitecmoamerica.com/manual/lulua/en/4300.html) ties exploration rate to collected monster/item information and gives better quality odds at 100%. Need separate observed discovery records and computed completion; do not equate a single percentage with collection ownership. Guides cover recipes, items, effects and traits. |
| Alchemyriddle, schedule, requests and story | [Alchemyriddle](https://www.koeitecmoamerica.com/manual/lulua/en/6100.html) separates main pages that advance story from secondary basic/advanced pages, keyword acquisition, deciphering and claimed rewards. Chapter completion can award EXP/recipes. Need distinct prerequisites and reward records. Story completion stays separate from resource actions; no blanket decipher/unlock action. |

## Nelke mechanic coverage checklist

The [official manual](https://www.koeitecmoamerica.com/manual/nelke/en/) is a set of
scanned pages; the linked pages below were inspected visually. Nelke's town
management is different from Lulua's item-synthesis system. No Lulua/Sophie
quality, equipment or EXP layout is transferred to it.

| Important mechanic | Rules to preserve and next field proof |
| --- | --- |
| Money, income and population | [Town development](https://www.koeitecmoamerica.com/manual/nelke/en/mnl041.html) links profitable production/sales to population growth. Need a displayed spending pair, separate income receipt and population update controls; current spending money is not an income or population counter. |
| Facilities, workforce and production/sales | [Weekdays](https://www.koeitecmoamerica.com/manual/nelke/en/mnl014.html) separates construction, placing residents, making/selling items and advancing a turn with Start Job. Need facility identity/position, resident ownership/assignment and queued job/result records; no duplicate worker or completion-without-cost writes. |
| Materials, storage, synthesis and research | [Game flow](https://www.koeitecmoamerica.com/manual/nelke/en/mnl010.html) distinguishes gathering/production requests, synthesis jobs and holiday research. The [info menu](https://www.koeitecmoamerica.com/manual/nelke/en/mnl035.html) separately lists owned storage, research status, equipment and reduction into elements. Need identified owned-record arrays, item kinds, job inputs/outputs and research dependencies. |
| Friendship, support, EXP and facility unlocks | [Holidays](https://www.koeitecmoamerica.com/manual/nelke/en/mnl027.html) ties visits to friendship, EXP and new facilities; the info menu says resident requests improve friendship and support. Need separate bond/support/growth records and event/unlock prerequisites. |
| Action Gauge and investigations | Holidays consume the Action Gauge; investigations consume its remainder and can trigger battles/material discoveries. Need a controlled visit/investigation pair, natural gauge capacity and distinct queued results; no invented refill cap. |
| Equipment and battle growth | The info menu says equipment assists investigations and battle. Need owned item/equipped references, character growth thresholds and applicability; title-specific combat fields have not been mapped. |
| Achievements and purchased bonuses | The info menu distinguishes completed achievements from points spent on bonuses. Need separate point balance, completion history and purchased/reward records. |
| Turns, weekday/holiday phase, tasks and story | Game flow advances one turn when weekdays finish; Start Job and End Holiday trigger phase transitions and queued work. Need task deadlines, progress/reward states and transition dependencies. Calendar/turn or blanket task completion must stay separate from resources. |

## Exact next inputs

For each Switch title, the shortest useful input is its **matching update's
decompressed executable `main`/NSO**, with title ID, update version and language,
for static loader/writer analysis, or a public title/platform-specific save
codec with complete native checksum coverage. A PC executable can supply a
research lead, but does not independently qualify Switch keys or serialization.

Also obtain an unmodified Switch gameplay export, its associated system file,
an unchanged save/re-save control, and one displayed purchase/sale or existing
item-use/synthesis pair. For Nelke this should be separate from the already
modified Super Starter save. A matched native encrypted/decoded export plus a
documented successful edit/load/re-save can provide an alternative codec lead.
Additional complete save copies alone do not establish encryption or integrity.

No native roundtrip, surgical edit, GUI writer test or edited game-load result is
claimed for either candidate. These findings do not add supported-library rows.

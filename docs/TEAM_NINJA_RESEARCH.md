# Team Ninja native PC save expansion

This document separates implemented editing, verified format inspection and
missing native proof. The current changes are unreleased. No game executable,
third-party binary or attached binary was executed, and no player save or owner
identifier is included in the source tree.

## Wo Long: Fallen Dynasty

The new [adapter](../src/koei_editor/games/wolong/wolong_parser.py) qualifies the
acquired Windows PC USER profile: exactly 5,120,272 bytes, `WLNUSR` identity,
revision `0x23121200`, a 256-byte header, matching inner revision, block-aligned
AES-CBC body and zero-padded UTF-8 JSON. It rejects SYSTEM files, unknown revisions,
wrong lengths, duplicate JSON keys, nonfinite numbers, damaged integrity and
unqualified inventory structures. The native USER and BACKUP files and a SYSTEM
file were independently acquired from a freely shared
[SaveGameWorld save](https://www.savegameworld.com/pc-wo-long-fallen-dynasty-savegame-100/).
All three pass the existing codec's native header and body checksums. The shared
save's description explicitly reports trainer-modified items; its unusual values
are evidence of existing data, not evidence of natural limits.

The cryptographic implementation already present in this project is derived
with attribution from MIT-licensed
[KatanaSaveDataResigner](https://github.com/mi5hmash/KatanaSaveDataResigner/tree/4c90a2b388438cb27a9752e6eab7333257de215f).
The new gameplay layer is independently written around the native JSON schema.
Both checksum ranges cover their full native header/body spans. Editing does not
disable integrity or rebind the save owner. An unchanged file is returned byte
for byte. Changed integer tokens retain the spelling and ordering of every other
JSON token, original header context, overall file size and zero padding. Both
checksums are rebuilt, the original input representation is retained, and the
output is reparsed and verified before saving a new copy. Selected custom-name
string tokens use the same lexical preservation and native integrity workflow.

### Current controls and limits

- `PlayerData.senki`, `sen` and `bukun`: manual Genuine Qi, Copper and Accolades
  balance controls. The range 0..2,147,483,647 is a conservative editor input
  limit, **not a recovered natural gameplay cap**. All Max actions leave these
  fields unchanged. Higher opened values remain unchanged on no-op and can be
  restored by Undo. `senki_storage` and `new_senki_storage` are shown separately
  and never rewritten as if they were the current available balance.
- Existing ordinary carried/storage stacks: quantity may be reduced to
  1..the opened quantity. The adapter requires a nonzero existing item key and
  instance, quantity greater than one, ordinary observed flag 8, no equipment
  slot, equipment part 0, stored item level 1 and weapon-skill level 0. Item
  creation/deletion and quantity increases remain unavailable because per-item
  capacities and reward/ownership dependencies are not yet qualified. Max is
  disabled. The acquired USER has 59 such carried and 18 stored stacks; these
  counts are fixture observations, not a required occupancy count.
- Existing enabled battle-set custom names: manual renaming of the matching
  `UIData.ui_battleset_slot_data_info` string when both native arrays have
  exactly 50 slots and the corresponding `BattleSetData.enable_flag` is boolean
  true. Input accepts 1..16 printable ASCII characters, a conservative editor
  limit rather than a proved game cap; opened Unicode/longer names remain
  preserved and reversible. This changes only the display-name token, padding
  and native checksums. Enabling a set or changing its equipment, Virtues and
  spells remains unavailable. Max is disabled.
- Searchable inspection: every populated record in the 600 carried and 2,000
  stored physical slots, including numeric item key, instance, quantity, rarity,
  stored item-level and weapon-skill fields, equipment part/slot and flags;
  companion IDs, bond levels/points/flags; character level, stored skill maximum,
  the five-Virtue array and both stored-Qi fields. Display names are not guessed
  from hashes or an alphabetical guide. The physical array counts are save
  structure, not a claim about an in-game carry capacity.

The GUI retains shared backups, Undo, Review Changes, themes and copy-only safe
saving. Tests distinguish procedural data, genuine-file qualification and actual
game loading. [Format tests](../tests/test_wolong_format.py) cover native integrity,
malformed/foreign input, exact no-op, lexical preservation, targeted edits,
unusual values, no-Max, stack reductions, snapshot forgery, backups/restore and
source protection. [GUI tests](../tests/test_wolong_gui.py) cover search, manual
edits, Review/Undo, inspection, themes and saving. `WOLONG_SAVE_COPY` enables the
private genuine USER test. Edited game-load/re-save validation has not been
performed by this project.

The [expansion evidence and tests](TEAM_NINJA_DEPTH.md) distinguish generated
enabled-set renaming from native qualification: the genuine USER/BACKUP corpus
has no enabled battle sets or nonempty custom names. Positive name editing has
generated surgical-format and actual Tk Save As coverage, but no native enabled
named-set qualification or actual game-load/re-save validation. An intact
current-revision copy with such a set and a controlled rename pair are required.

### Mechanics coverage and remaining proof

The [official update history](https://www.teamninja-studio.com/wolong/us/update/)
confirms important dependencies: Store Genuine Qi unlocks at the maximum level;
Apex Bonus unlocks at level 500; later updates raise stored-Qi and selected item
capacities; hidden Wizardry requires acquired Hidden Tomes; Martial Arts
replacement/improvement and Stratagems have separate unlock prerequisites.
Updates also explicitly add native tamper checks for Dragon's Cure Pot upgrades.
These mechanics must not be reduced to unconditional bit toggles or storage
ceilings.

| System | Current result / exact missing proof |
| --- | --- |
| Available currencies | Tested manual balances; natural caps and current-build grant/spend clamps need native routines or controlled boundary/action pairs. |
| Stored Qi, Apex Bonus and level-cap expansion | Read-only native fields. Need Store/Withdraw/Apex before/after pairs and native level/EXP/extra-level dependencies; do not confuse stored Qi with available or lifetime Qi. |
| Five Virtues, level, skill points and Wizardry | Read-only level/Virtue inspection. Need level-up/reset, learned-tome and spell-unlock pairs; level, distributed Virtues, extra levels and skill-point arrays are linked. |
| Ordinary inventories | Tested existing quantity reductions; increases require per-item carry/storage limits and catalog/type qualification. Numeric keys remain explicit. |
| Equipment reinforcement and rarity | Read-only inspection. In the genuine file, stored `item_level` 17 accompanies the author's reported +16 equipment: the stored field is not a direct displayed upgrade value. Need native conversion and material/reward/cap prerequisites before writes. |
| Martial Arts and replacement | Stored `weapon_skill_level`, inscriptions and DLC inscription arrays are separate systems. Need replacement/unlock/upgrade pairs and native derived-value/cache consumers. |
| Embedment, special effects, graces, Jewelry Essence | Native nested orb/inscription schemas exist; names, categories, allowed combinations, per-category magnitudes, costs and locked/premium distinctions need a licensed independently qualified catalog plus native consumers or controlled pairs. No affix/code injection is offered. |
| Battle-set custom names | Existing enabled sets can be renamed conservatively; positive native named-set and controlled rename-pair qualification remains missing. No loadout or enable-flag writes. |
| Equipment references, battle-set loadouts, appearance | Existing references, entry/instance numbers and appearance are preserved. Need equip/swap/remodel pairs that identify every cross-reference and any cache updates. |
| Companions and bonds | Read-only IDs, bond levels, points and flags. Need named ID mapping, bond thresholds and gear/reward flags before any bond/unlock writer. |
| Divine Beasts, Dragon's Cure Pot, customization | Native save fields exist but acquisition/upgrade dependencies and tamper checks require native routines or controlled pairs. |
| Mission progress, flags, DLC, NG+ and Thousand-Mile Journey | Native mission structures are preserved. Need mission/flag/reward and DLC ownership pairs; story completion remains separate from resources. |
| Titles, records, collections, gestures and unlocks | Native arrays exist; need stable catalogs, prerequisites and paired reward/history behavior. No blind all-unlock action. |

For further qualification, supply separate native current-build USER/BACKUP
copies plus pairs surrounding one ordinary action (displayed balances, Store Qi,
level-up/reset, equipment upgrade, Martial Arts change, consumable use/transfer,
bond increase or mission reward). Matching executable/module files can support
static validation of natural bounds and callbacks. No account transfer is
required for this adapter; original owner/header context is preserved.

## Nioh / Nioh Complete Edition and Nioh 2 Complete Edition

Native PC decoding is established on genuine files, but the active gameplay
integrity rules remain unresolved. The Nioh Complete Edition inspector now
requires exact USER size, title/revision/body framing and all seven observed
flag shapes. Nioh 2 rejects mutable/forged snapshots and validates the exact
bounded restore bytes. Both remain unregistered and reject every gameplay edit;
the seven/four flags are retained exactly.

The [integrity investigation and mechanic checklist](NIOH_INTEGRITY_RESEARCH.md)
records the recovered genuine input, source checks and analytical candidates.
Several public tools advertise a checksum fix but clear flags instead. More
unlabelled saves alone do not prove the missing active routines. Required:
native save-loader/integrity consumers or an independently verifiable algorithm,
then intact one-action pairs for balances, growth/skills/proficiency, forging,
familiarity, Guardian Spirits, Soul Cores/Scrolls and reward/progression state.
Original PS4 Nioh, Complete Edition PC/PS4 and remastered profiles are separate;
no console schema is transplanted into a PC writer.

## Nioh 3: implemented native USER editor

The [registered PC adapter](../src/koei_editor/games/nioh3/parser.py) implements
Amrita/Gold deductions and existing positive quantity reductions for thirty-two
known common item IDs in the item box and storehouse. The two genuine USER revisions `0x01030001` and
`0x01040000` qualify the native cipher/body checksum and actual tagged arrays:
2,500 equipment records, 1,500 item-box records and 400 storehouse records.
Published fixed bases address the wrong bytes; native tags, both lengths and
adjacent boundaries prove the supported profiles. Other revisions fail closed.

Balances support `0..opened balance`; their eight-byte records have separately
proved revision-specific tags and adjacent boundaries. These deductions do not
perform purchases or level-ups. Only `1..opened quantity` is writable for stacks. Unknown/empty/nonordinary records and
ambiguous duplicate known IDs do not grant writes. Increases, removal, Max,
acquisition and cross-pool transfers need capacity/reference/reward proof.
Equipment inspection keeps current level, pre-forge level and reinforcement
separate, and now exposes numeric-only source-reported rarity/modifier-slot
fields. Those subfields have no native action-pair proof and remain read only.
Original keys, seeds, header, tail and unknown bytes are preserved; integrity is
rebuilt and the output reparsed. No integrity flags are cleared.

See [native format, validation and exact mechanic blockers](NIOH3_RESEARCH.md).
The [expansion note](TEAM_NINJA_DEPTH.md) records the twenty-five additional ordinary
item identities, independent native corroboration and unchanged reduction rules.
Genuine encrypted/decoded edits and actual Tk Save As/backup/restore workflows
are distinct from edited game-load/re-save validation, which is unperformed.
Currency increases/purchase dependencies, level/EXP, skills/proficiency, equipment transformations, affixes,
owned Scrolls, customization and mission/reward state remain separate blockers.

## Stranger of Paradise: Final Fantasy Origin

A live download on the corrected
[SaveGamePro page](https://savegame.pro/pc-stranger-of-paradise-final-fantasy-origin-savegame/)
provided genuine Epic PC USER/SYSTEM files. The earlier dead MediaFire comment
link was not the current download button. These are launch revision
`0x22020200`: USER is 6,216,976 bytes and SYSTEM is 17,568 bytes. The newer
Katana cipher pair is SYSTEM revision `0x23013100`. Two independently shared
Steam USER files and a SYSTEM file from
[niemasd/Game-Saves](https://github.com/niemasd/Game-Saves/tree/08e8418187862dde9d70877c9fc367fa80304009/PC/Stranger%20of%20Paradise%20-%20Final%20Fantasy%20Origin)
now separately qualify complete Steam framing at that revision. A dedicated [native framing inspector](../src/koei_editor/research/sopffo/sopffo_native.py)
retains encrypted/decrypted representations and exact no-op bytes. No gameplay
editor/card is enabled while native gameplay integrity remains unresolved.

See [per-system evidence and blockers](SOPFFO_RESEARCH.md). Live-memory inventory
source and PS4 job-EXP patches do not qualify PC serialized records. Launch Epic and the acquired Steam revision have separate observed profiles;
unobserved builds and console profiles must be proved independently. Required:
native integrity/update routines, then controlled currency/Anima/rat-tail/Dragon
Treasure, job/EXP/limit-break, equipment/affinity/Chaos-effect/synthesis,
companions, customization, rift/monster/labyrinth and mission/reward pairs.
Ownership, derived stats and story completion remain separate.

## Ninja Gaiden: implemented original II and separate later formats

The [original Ninja Gaiden II adapter](../src/koei_editor/games/ninja_gaiden_ii/parser.py)
accepts 31,744-byte extracted Xbox 360/Xenia revision-6 stories, supported by
22 genuine files plus matching native content in one CON package. It edits
Yellow Essence manually and reduces existing unique ordinary consumable and
ammunition stacks. Native big-endian word checksums are validated/rebuilt;
unknown bytes, record variants, native markers and the opaque trailer survive.
Karma, ownership, weapons, health/Ninpo, rewards and progression stay separate.
CON/STFS input is rejected; extraction and signed reintegration remain external.

The public archive is titled “Black” but explicitly targets original Xbox 360
Xenia title `544307D5`, independently corroborated by its container. It does not
qualify the 2025 Black remake. Likewise `ng2stryd` is an STFS directory filename,
not a native raw signature. Neither mislabel is used to invent a format.

[Ninja Gaiden format/mechanic coverage](NINJA_GAIDEN_RESEARCH.md) keeps original
II, Sigma, Sigma 2 and Black and each researched platform separate. Genuine
corpora include seven Sigma Master Collection PC gameplay files, 31 Sigma 2
Master Collection PC stories and 19 Black Steam files. Sigma's descriptive
envelope does not establish native integrity. Sigma 2 and Black native payloads
have two integrity fields; one recovered header CRC does not validate the other
body check. Black's distinct Unreal GVAS wrapper also requires exact
class/revision/property/array validation. The public Steam editor's existence
alone does not authorize writes or brute-force unlocks. Dedicated read-only
inspection candidates remain under `research`, without library cards.

## Additional unqualified Team Ninja formats

Rise of the Ronin PC remains outside this assignment's implemented support.
The MIT Katana source documents a 256-byte unencrypted native envelope but its
fixture is a dummy; complete native USER/SYSTEM, integrity and gameplay maps
are still required. No neighbouring Team Ninja schema is automatically selected
when the chosen parser rejects a file.

The optional [older native corpus tests](../tests/test_teamninja_native.py) use
`TEAM_NINJA_NATIVE_DIR` for privately held Nioh and Wo Long files. The Wo Long
expansion has separate generated name-edit tests and native regression checks.
New format, independent audit and [GUI workflow tests](../tests/test_team_ninja_gui.py) exercise the separate
registered Nioh 3 and original Ninja Gaiden II backends. Player files, source
copies, binaries and owner identifiers remain outside the checkout and bundles.

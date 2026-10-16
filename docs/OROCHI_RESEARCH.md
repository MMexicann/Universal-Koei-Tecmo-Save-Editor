# Warriors Orochi native PC coverage

Reviewed against the attached executables, public source facts, mechanics
references and a privately held public Steam save. Executables were inspected
and their SteamStub code section decoded statically; they were never executed.
No executable, decoded game image, player save or account context belongs in
this repository or its packages. Implementations are independently written;
no upstream project was copied into the application.

## Warriors Orochi 3 Ultimate Definitive Edition

`src/koei_editor/games/wo3u/wo3u_parser.py` / `src/koei_editor/games/wo3u/wo3u_editor.py` implement the Steam Windows packed layout.
The inspected executable identifies Steam app 1879330 and product version
1.0.0.1. Accepted files have exactly `0x2119CA` bytes and begin with the
little-endian marker `0x140318F1`. The native root serializer visits 150 officer
records, 145 groups of 16 weapon records, additional stage/team sections and an
opaque `0xA0000` section. The final five officer records are internal records;
they are inspected but have no writable fields.

The reached native save path serializes little-endian values then passes that
buffer directly to `WriteFile`; loading reads the same bytes and runs the
packed-field serializers. No save-owner binding, external crypto DLL, save cipher
or aggregate payload-checksum operation appears in that path. The root marker
and complete officer/weapon layout markers are qualified before writing. This
is structural qualification, not a claim that arbitrary corruption of every
unknown gameplay byte can be detected. Unknown data and every marker are
preserved rather than repaired or normalized.

Officer marker low words are `0x6DA8`, weapon marker low words `0x6228` in this
qualified revision; upper words must agree but are preserved because ASLR changes
them. These are serialized low DWORDs of object/vtable addresses. They are **not
checksums**, and a particular player's entire marker value is not a universal
constant. Other executable revisions with changed table offsets are rejected.

Static evidence locations in the inspected image:

| Routine | Observed behavior |
| --- | --- |
| `0x1402DFA9B`, `0x1402DFAC4` | Native allocation and save length `0x2119CA` |
| `0x1402487A0`, `0x1402488F0` | Clear output buffer, serialize packed native sections |
| `0x1402465B0` | Serialize/check title and revision marker `0x140318F1` |
| `0x140274F90`, `0x140275110` | Direct native `WriteFile` / `ReadFile` |
| `0x140258CA0` | Packed officer serializer, not a raw runtime memory copy |
| `0x14026C8C0` | Packed weapon serializer with eight ID bytes and eight ranks |
| `0x14026CC90` | Weapon descriptor lookup and special IDs 1250..1394 |
| `0x14026D4B0`..`0x14026D551`, `0x14026E290`..`0x14026E312` | Factory paths distinguish binary IDs 26..31 and 46..57 from ranked IDs 0..25 and 32..45 |
| `0x1404080D5`, `0x140409724` | Blacksmith UI checks each of eight ranks: binary ranges have one rank; other native attributes reach rank ten |
| `0x14026C8C0`, `0x14026CC90` | Serialize runtime reinforcement byte `+0xB` at packed weapon `+3`; total attack reads it separately from descriptor attack and u32 compatibility |
| `0x140248C60`, `0x140248D70` | Copy the `0xEBF8`-byte current/serialized system bodies in opposite directions; establishes the menu-to-save bridge for both mount loadouts |
| `0x14025E4F2`, `0x14025F172` | Serialize the separate mount selector bytes at system/file `0xE0DF` and `0xE943` |
| `0x1403252E0`, table `0x140A7F020` | Mount menu maps owned item IDs 28..31 to stored ordinals 0..3; the other thirteen lookup positions are unmapped |

The independent public native sample was acquired from an annotated
[Steam save-sharing discussion](https://steamcommunity.com/app/1879330/discussions/0/592904528464062941/).
It has the exact length/title/layout and SHA-256
`e9a6ec40c7c1807dcb301d318d520aced64d920ac0a1452821ea42091f99c0a9`.
The author describes maximal stats except deliberately low Musou, low bonds,
minimal weapon attributes and plentiful crafting materials. All 145 playable
records show health/attack/defense 999, Musou 200 and speed 200, independently
corroborating the public field labels but not establishing natural caps.
The source deliberately contains cheat values, including speed 200; the editor
uses the guide's natural speed maximum 180 and Max preserves existing 200. The five extra internal records differ.
There are 1,109 occupied native weapon records and 445 instances of attribute
ID 31 at rank 1; the author's description of Verity on Samurai-type weapons
corroborates that ID. The 58 orb and 295 crafting-resource bytes match the
published spans, without adopting console container offsets or endianness by
assumption.

A later user-supplied `SAVEDATA.BIN`, initially unidentified by its filename,
independently matches the same `0x2119CA` PC profile and every structural marker.
It exposes 841 existing ranked effects beyond the previously named subset and
31 ordinary nonzero reinforcement counters. All 872 additional controls were
tested surgically on this copy. Its unusual balances and other unedited values
remain intact; it does not establish natural resource caps or game-load results.

Additional sources:

- [Apollo NPEB02052 patches](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPEB02052.savepatch):
  public labels/strides used as research leads, checked against the native
  packed serializers and sample. Patch titles and cheat values alone are not
  natural-cap evidence. Console files themselves are not accepted.
- [Steam PC mechanics guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2851197510):
  promotions reset level, expand item slots, award upgrade stones and have
  dependent bonuses; normal stats reach 999 except speed, whose natural maximum is 180. The guide also
  distinguishes orb fusion, bond consumption and story/Gauntlet unlock routes.
- [Hundun unlock guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2839992420):
  character unlock requires a specific Gauntlet completion and subsequent
  mode transition; unlocking a bit without those dependencies is not exposed.
- [PythWare/Warriors-Orochi-2-Editors](https://github.com/PythWare/Warriors-Orochi-2-Editors):
  stage/unit asset editors, not a compatible disk-save editor. No code reused.
- [ashimpure/WO3UDEXL](https://github.com/ashimpure/WO3UDEXL) and
  [WO3U Equipment Mods](https://github.com/ryuuseispt-ui/WO3U-Equipment-Mods):
  gameplay/modding leads; no native disk mapping or implementation was copied.

### Writable fields and limits

Offsets are native PC file offsets, little endian. Fields always come from the
immutable original snapshot; pending edits cannot manufacture records.

| Field | Native offset/stride | Behavior |
| --- | --- | --- |
| Unallocated growth points | `0x1378`, u32 | Individual edits through 9,999,999 |
| Precious stones / gems | `0x137C`, u32 | Individual edits through 999,999 |
| Health, Musou, attack, defense, speed | `0xECF2 + officer*0x2B0 + {0,2,4,6,8}`, u16, 145 records | Stat edits, bulk Max; 999 except speed 180 |
| Attribute orbs | `0xE944`, 58 u8 values | Individual balances through 99 |
| Crafting materials | Seven spans defined in parser, 295 u8 values | Individual balances through 99 |
| Existing weapon attribute slots | `0xC8012 + weapon*0x1C`, u8, 145*16 records | 0..8; decreasing cannot hide attributes; increasing cannot activate dormant IDs |
| Existing attribute ranks | `0xC801C + weapon*0x1C + attr_slot`, u8 | Proven standard IDs 5..11 use 1..10; Verity ID31 is binary rank1 |
| Other existing native ranked effects | Same rank span, native IDs 0..25 and 32..45 | Individual and Max through ten; new labels use native numeric IDs until the exact localization association is proved |
| Existing reinforcement | `0xC8013 + weapon*0x1C`, u8 | Existing 1..99 only, manual decrease to 0..opened value; raising and bulk Max are disabled |
| Unallocated upgrade stones | Officer `+52`, u16 | Already promoted original records with balance 0..891 only; manual 0..891, excluded from Max; allocation, promotion and growth unchanged |
| Existing owned ordinary-item equipment | Officer `+38`..`+43`, active count `+44` | Original owned positive-rank non-mount item choices or empty; qualified active slots only, no duplicates, no Max or ownership changes |
| Existing owned mount loadouts | `0xE943` and `0xE0DF`, u8 | Stored lookup ordinals 0..3 select original owned binary mount items 28..31; 255 means Unequipped. Original ownership/rank and selector qualification, no Max or experimental expansion |

The [existing-editor depth review](OROCHI_DYNASTY_DEPTH.md) documents the native
serializer, allocation clamp, ownership/rank getter and complete staged equipment
guard that qualify these two additional controls. Higher original stone balances
and unsupported equipment layouts stay opaque.

Growth-point, gem, orb and material edit bounds come from public patch limits;
their natural caps have not yet been recovered from native gameplay clamps.
These fields are excluded from **all** bulk Max actions. Higher existing balances
can remain unchanged. Stat/rank/slot bulk actions also preserve higher existing
values. No ID is assigned to an empty weapon or empty attribute slot; zero-rank
and unknown attributes, unknown weapons and unsupported slot-count layouts
remain inspection-only. Normal descriptor IDs end before special range
1250..1394; IDs outside the qualified descriptor range are preserved read only.

Native binary effects are IDs 26..31 and 46..57. They receive one rank rather
than a guessed ten; the existing independently named Verity control retains its
rank-one compatibility behavior, while the other binary IDs are inspected only.
Zero ranks and dormant attributes are never activated. Reinforcement increases
need the grade-specific ceilings, which are distinct from the native absolute
99 clamp. Decreasing an already ordinary value cannot exceed its opened grade
ceiling; descriptor, grade, costs and equipped references are preserved.
Version 2.6 separately offers an explicit compatibility reset to zero, with no
arbitrary increases; see [the new qualification](WARRIORS_V26_DEPTH.md). The native total-attack getter reads reinforcement directly.

The shared GUI provides search, grouped field controls, existing-weapon inspection,
separate progression, resource and mount-loadout tables, staged batch Undo, Review Changes,
automatic backups and atomic Save As to a new `.bin` destination. Restore qualifies
the exact bounded bytes written, including the backup manifest/hash. Common
path protections and source-change detection remain in force.

### Owned mount loadouts

The two native stored mount selectors are separate from each officer's ordinary
item references. The current system object begins at runtime root `+0x33B60`;
the serialization copy begins at `+0x42760`. Native `0x140248C60` copies the
`0xEBF8`-byte body to the serialization copy, and `0x140248D70` restores it in
the opposite direction. Following that bridge establishes the menu members
root `+0x424A3` / `+0x41C3F` as system/file `0xE943` / `0xE0DF`, rather than
treating runtime root offsets as file offsets. The packed serializer explicitly
reads and writes each byte at `0x14025F172` / `0x14025F183` and
`0x14025E4F2` / `0x14025E503`.

The original ownership mask and item-rank table are the same already qualified
records used by ordinary-item equipment. The native mount tab admits item IDs
28..31 and its assignment routine `0x1403252E0` maps those IDs through a
seventeen-entry lookup table. Only the first four entries identify mounts;
they produce stored ordinals 0..3. The native clear path
`0x1403250F4`–`0x140325194` writes the signed empty sentinel -1, stored as 255.
The editor offers only originally owned mount records with original binary rank
exactly 1, plus Unequipped. An unknown original selector or a selector pointing
to an unowned or unusually ranked mount keeps that loadout read only. The other
qualified loadout remains available. Pending edits cannot manufacture ownership
or admit a previously unsupported mount.

Both stored loadouts can refer to the same owned mount; the ordinary-item
six-slot duplicate check does not apply across them. Labels remain numbered
loadouts and native item IDs, without guessing mount names or a game-mode/team
association. Assignment changes only the selected byte. Item ownership/ranks,
acquisition and collection/reward state, ordinary equipment and stored battle
objects remain unchanged. This does not alter a mounted actor inside an existing
battle snapshot; the effect of loading/resuming edited copies remains untested.
Mount choices are excluded from Max and experimental numeric expansion.

The same refinement closes an experimental-range bypass for existing weapon
reinforcement. A decrease-only field now retains its opened upper bound even in
experimental mode, and unusual original reinforcement bytes above 99 remain
read only instead of becoming eligible when that mode is enabled.

### Coverage checklist

| Important system | Implemented or precise remaining blocker |
| --- | --- |
| Currency and stock EXP/growth points | Individual balance editing; native natural clamps still needed for resource Max |
| 145 playable officers' five stored stats | Writable, tested; higher values preserved; five internal slots protected |
| Character identity/names | Record indices and progression inspected; native roster-ID/name association not proved, so names are not guessed |
| Level and EXP | Read-only stored level/EXP; controlled level-up and promotion pairs needed to prove recalculation, rewards and level reset |
| Promotions and upgrade stones | Manual unallocated balance 0..891 for qualified already promoted records; promotion, allocated stones, growth/rewards and slot-count transitions remain protected pending complete transition proof |
| Proficiency and abilities | Public source separates multiple bytes/ranks; natural progression/skill prerequisites and packed semantics need controlled pairs |
| Weapon ownership/types | Existing IDs inspected; no cloning, empty-record manufacture or guessed weapon names |
| Weapon attribute slots | Safe existing-record expansion/reduction; reduction cannot hide owned attributes; expansion cannot activate dormant IDs |
| Weapon attributes, elements and fusion | All existing native ranked IDs 0..25/32..45 writable through ten; binary/unknown/zero/dormant effects preserved. Attribute acquisition/swap and the full 58-name catalogue need native ID/name tables and fusion dependency pairs |
| Weapon compatibility and reinforcement | Existing ordinary reinforcement decreases are writable. Increases need grade-specific caps. Compatibility is a separate packed u32: a deliberate reset to zero is qualified in v2.6; arbitrary increases require the missing descriptor-grade map |
| Attribute-orb inventory | 58 balances editable; ID-to-name catalogue and natural clamps pending |
| Crafting inventory/recipes | 295 balances editable; materials' names, receipt/new flags, recipe unlocks and natural clamps pending |
| Equipped items and item enhancement | Qualified active ordinary-item selectors can choose original owned positive-rank items or empty; duplicates rejected. Enhancement/acquisition and slot-count changes require further dependency proof |
| Bonds and companions | Low-bond genuine fixture available; pair symmetry, support thresholds, consumption and maximum semantics not yet mapped |
| Mounts | Two stored loadouts can select originally owned rank-one mount items 28..31 or Unequipped. Unknown selectors and unusual ranks remain read only. New acquisition, rank changes, names and mode/team association remain unqualified |
| Costumes and color customization | Annotated changed colors present; exact character/color-channel association and costume prerequisites not proved |
| Story, stages and campaigns | Preserved and separate from resources/stats; chapter endings, Redux/side-story unlocks and rewards need controlled completion pairs |
| Gauntlet/exploration, keystones and allies | Public patches indicate regions; four keystone types, summon ownership, progression/rewards and ally consumption need native mappings and controlled pairs |
| Duel cards/collections | Preserved; card ownership/new flags and gallery rewards/dependencies not proved |
| Gallery, music and movies | No independent PC packed-field map or controlled unlock pairs acquired |
| Revision variations | Exact 1.0.0.1-compatible packed layout qualifies; differently sized/marked/modded layouts rejected |
| Edited game loading | Not performed: no Windows game installation/load/re-save available in cloud |

### Validation

With `WO3U_SAVE_COPY` pointing to a reviewed copied native save outside the
checkout:

```text
python -m unittest tests.test_wo3u_format tests.test_wo3u_review tests.test_wo3u_expansion -v
python -m unittest tests.test_wo3u_gui -v
```

The first command passed 29 tests with the user-supplied native fixture present,
including the native no-op roundtrip, surgical stat edit, every newly exposed
rank/reinforcement control, binary categories and malformed/empty layouts.
Without the private fixture, two native tests skip honestly. The second passed
three GUI tests under Xvfb, including the user-supplied copy:
search, grouped controls, edit validation, review, Undo, backup, Save As, inspector
and theme switching. Fixtures generated by `procedural_raw()` are explicitly
synthetic. A native complete bulk action preserved all five internal records;
1,399 changed bytes belonged only to declared Musou or existing weapon-slot
fields. This is file-level validation, not an edited game-load claim.

The mount refinement adds `tests.test_wo3u_mounts`. A focused run of that module
and the five format/review/expansion/depth/GUI modules passed **46 tests with no
skips**, with the supplied native fixture available and Tk under Xvfb. The two
independent native references each qualify both loadouts and all four existing
mount choices. Twenty copied-native exports independently changed each selector
to 0, 1, 2, 3 and 255, reparsed the actual destination, and preserved every other
byte and both originals. Two additional native GUI workflows passed choice
selection, Max exclusion, Review, Undo, automatic backup, Save As and byte-exact
restore. These are structural/native-file checks; no edited save was loaded in
the game.

## Musou / Warriors Orochi Z

`src/koei_editor/games/orochiz/` implements the native Windows PC revision-2
`save.dat` layout. The inspected executable identifies product version 1.0.0.0.
A genuine publicly shared PC save was obtained from
[Savegame.pro](https://savegame.pro/pc-musou-orochi-z-savegame/), retained privately,
and independently qualifies the native length, marker, checksum and record
layout. The archived live path is `KOEI/Musou OROCHI Z/Savedata/save.dat`.
Never edit the live folder: open a separate copy.

Accepted saves contain exactly `0x25F48` bytes, revision u16 at `0x4` equal to 2
and the native first-section DWORD marker 3000 at `0x8`. The writer copies
`0x5EE8` bytes from its first runtime block into file offset 8, then `0x20028`
bytes from the second block into file offset `0x5EF0`. It writes this plaintext
buffer directly; no cipher, owner key or companion DLL appears in this path.

The checksum is the u32 byte sum of bytes before `0x25F24`. Its 20-byte native
integrity record is that u32 followed by sixteen zero bytes, all validated by
the loader. The final sixteen opaque bytes are excluded and retained unchanged.
The checksum detects ordinary corruption; a byte sum is not cryptographic title
proof, and an intentionally forged native-size/revision/marker file cannot be
distinguished universally from an authentic save. Unknown gameplay bytes are
preserved and are never repaired to invented defaults.

| Routine | Native evidence |
| --- | --- |
| `0x5AC2E0`, `0x5ABE10` | Serialize/load raw sections `0x5EE8` and `0x20028` |
| `0x5AC214`, `0x5AC854` | Exact read/write size `0x25F48` |
| `0x5AB6B0` | Revision u16 equals 2 before integrity validation |
| `0x5AB630`, `0x5AB510`, `0x5E8990` | Clear integrity record, byte sum, compare all twenty bytes |
| `0x47C94F` | First-section marker 3000 |
| `0x474AA0` | Set serialized stock EXP balance and clamp it to 99,999 |
| `0x52B200`, `0x47A410` | Allocate stock EXP to officer, run level/stat progression |
| `0x52B170`, table `0x6D5E90` | Within-level EXP display uses the current level's native threshold; all 99 threshold entries independently corroborated |
| `0x52DB7A` | Store remaining stock EXP after weapon fusion |
| `0x474FF0` | Read stored officer attack and add separate existing weapon base attack |
| `0x4747A0`, `0x477A70` | Independent stored base-attack setter and per-officer growth clamp |
| `0x4752B0` | Reset initial five stats using the ID-indexed native base table |
| `0x52DBA0` | Copy an existing `0x18`-byte weapon into the fusion model |
| `0x52E180`..`0x52E193` | Weapon attack-bonus byte clamped to 20 |
| `0x52E1A0`..`0x52E1B3` | Attribute capacity byte clamped to eight |
| `0x52E1D4`..`0x52E203` | Owned attribute level-minus-one byte clamped to nine |
| `0x52DCF4` onward | Ranked-attribute list skips native enum five |
| `0x475980` | Whole weapon assignment also updates collection bits; ID manufacture excluded |
| `0x474880`, `0x474890`, `0x531800`, `0x531810` | Read/write the officer's serialized equipped-slot byte; duplicated equipment UI helpers use the same selector |
| `0x474FD0` | Separate proficiency-like u16 divided by 1,000 |
| `0x477DC0` / `0x47B162` | Increment the distinct playtime frame counter, not a currency |

### Mechanics and implemented controls

The exact Z-specific [basic information](https://wikiwiki.jp/orochis/無双OROCHI%20Z/基本情報),
[weapon fusion](https://wikiwiki.jp/orochis/無双OROCHI%20Z/武器融合),
[weapon alchemy](https://wikiwiki.jp/orochis/無双OROCHI%20Z/武器錬成) and
[FAQ](https://wikiwiki.jp/orochis/無双OROCHI%20Z/よくある質問) describe this release's
96 playable characters, stock EXP, fusion, alchemy and proficiency rewards.
They corroborate stock EXP 99,999, attack reinforcement +20, eight ordinary
attribute slots, ranked attributes through level ten and three separate alchemy
abilities. The fourteen ordinary named attributes are a display catalogue;
that order is **not** assumed to be the native fifteen-value enum. No absent
identity is assigned a guessed label.

The adapter edits the following independently identified save-backed systems:

| Control | File layout and dependency |
| --- | --- |
| Stock EXP / Growth Points | u32 `0x5E30`, 0..99,999; shared balance used for leveling and fusion, not the playtime counter at `0x5E2C` or individual officer EXP |
| Officer base attack | u16 `0xC + id*0xDC + 8`, 96 records; individual initial floors 70..120 and per-officer natural ceilings 400..480, preserved in the interpreted limits module; separate from weapon and skill effects |
| Base Life, Musou, Defense and Speed | Officer-relative u16 `+4`, `+6`, `+10`, `+12`; v2.6 uses independently qualified per-ID initial floors and growth ceilings, preserves unusual originals and separates battle/weapon effects. [Native tables and validation](WARRIORS_V26_DEPTH.md) |
| EXP within current level | u32 officer `+0x10`; only already progressed stored levels 1..97 with EXP in that level's native band. Manual edits stay below the next threshold; excluded from bulk Max |
| Equipped weapon choice | Byte officer `+1`, stored slots 0..7 displayed as 1..8; dropdown contains only qualified occupied records already in this officer's own pool. Original reference must qualify; excluded from bulk Max |
| Existing weapon attack bonus | Officer `0xC + id*0xDC`, weapon `+0x14 + slot*0x18`, bonus byte `+7`, 0..20; identity/base weapon attack unchanged |
| Existing weapon attribute capacity | Same weapon byte `+6`, at least the number of owned mask bits and at most eight; changing capacity cannot manufacture an attribute |
| Existing owned ranked attribute levels | Mask u16 `+2`; byte `+8 + attributeID` stores level minus one; displayed/edited as 1..10; enum five excluded |

All 96 officer records and 768 physical weapon slots are searchable in read-only
inspection. Weapons are recognized only when their existing native ID is below
empty sentinel 414, their attribute mask uses the native fifteen bits, and their
capacity can hold the owned mask. Unknown IDs, malformed mask/capacity pairs and
empty records retain every byte. The separate alchemy mask `+4`, all fifteen
attribute identities and collection bits are untouched. The explicit Equipment
control changes only the selector; it cannot create, transfer or consume weapons.
Increasing an existing ranked effect or capacity edits its value only; it does
not simulate consuming a material weapon or acquiring a new effect.

Max preserves unusually high resource balances, bonuses and attribute ranks.
The independent genuine save contains pre-existing hacked rank bytes of 19
(displayed 20), so these are explicitly preserved rather than lowered to ten.
An explicit manual edit can lower a mapped value into its supported range, or
return to the original unusual value to remove a pending edit.

The native 99-entry EXP table is described independently by
`20*L*L + 780*L` through stored level 49, then
`86240 + 2720*(L-49)`. Every entry agrees with the supplied executable.
`0x47A410` adds EXP, then runs threshold crossings and five growth-stat changes
using a random state outside the serialized blocks. The editor therefore offers
only coherent progressed records and stays inside their opened level band;
unprogressed level zero, final level 98, unknown levels and inconsistent EXP
remain read only. It never guesses the missing random progression or writes
level/reward flags. The older genuine sample has eight qualifying progressed
officers. The later uploaded save has all 96 at stored level 98/EXP 220,000 and
correctly exposes no growth control; it supplies 96 existing equipment choices.

Native total-attack `0x474FF0` reads the selector, indexes this officer's own
eight-record pool and adds the selected weapon's descriptor attack to base
attack. Equipment UI setters change the same byte directly. Consequently a
qualified own-pool selection does not require rewriting a cached attack value.
The native whole-weapon assignment and collection updates remain excluded.

### Coverage checklist and exact blockers

| System | Implemented or precise remaining blocker |
| --- | --- |
| Native container, revision and integrity | Implemented; genuine unchanged roundtrip and targeted reparse qualified |
| Stock EXP / Growth Points | Individual editing and Max, native balance cap 99,999; playtime preserved separately |
| Officer names/identity | ID-indexed records inspected. Full-name builder `0x58CEF0` uses external officer table at `0x9C8FD0`; embedded strings contain surname/given fragments and cannot be indexed directly as 96 names. Matching `/etc/unitbase.bin` from the installed LINKDATA archive is needed for exact ID/name association |
| Officer base attack / other four stats | Base attack writable through its ID-specific ceiling, proven by independent setter/clamp and separate weapon-attack addition. Other four u16 values inspected only; their exact label-to-field and derived skill contributions are not independently qualified |
| Level and EXP | Manual EXP inside an already progressed, coherent opened level is writable; next-level thresholds and Max excluded. Full level transitions remain blocked by the coupled five-stat growth/rewards and nonserialized random state |
| Proficiency, costumes and wallpapers | Raw proficiency inspected. Z rewards costumes at proficiency 10/20 and wallpapers at 25/35/45; reward/unlock flags and native progression units remain unqualified, so no isolated proficiency write |
| Officer unlocks and special skills/talents | Native packed skill flags remain preserved. Skill acquisition prerequisites, legitimate rank identity and reward dependencies need labelled acquisition pairs and matching item/text metadata |
| Existing weapon reinforcement | Attack bonus editable; weapon base grade/type and derived total attack remain unchanged |
| Equipped weapons | Choose qualified existing records from the same officer's pool with an already valid reference. Empty/unknown/malformed/cross-officer choices are rejected; no transfer, manufacture or bulk Max |
| Existing weapon attribute slots/ranks | Safe capacity and owned ranked levels editable; attribute names require native localization/enum association, enum five is excluded |
| New weapons, attribute acquisition/swap, fusion transaction | Existing records inspected only. Whole assignment updates collection bits, so ID/family/collection/dependency relationships must be qualified before creation or consumption |
| Alchemy abilities and crafted inventory | Separate mask preserved. Z has fifteen distinct abilities, max three equipped and stock up to 99; recipe prerequisite/crafted stock/equipped ability relationships and exact bit catalogue need native mapping |
| Treasure collection | Z treasures are permanent acquired prerequisites, not consumable materials. Acquisition/reward bits and stage prerequisites need controlled unlock pairs; no invented consumable treasure balance |
| Mounts | Z mounts derive from Cavalier skill and leader faction: high skill selects Red Hare or Matsukaze. No mount inventory is invented; native skill/faction dependencies must be mapped |
| Story/extra/Dramatic campaigns and stages | Progress preserved separately. Dramatic eligibility includes proficiency and roster conditions; stage/result/unlock/reward relations need controlled completion pairs |
| Versus and Survival | Result/progression sections retained; named mode/streak records and legitimate progression/record dependencies not qualified |
| Gallery, music/movies, costume/color customization | Related reward bits and exact content IDs not proved; matching localization/assets plus controlled unlock/equip pairs required |
| Revision variations | Only the qualified revision-2 native profile accepted; unsupported revisions and malformed integrity rejected |
| Edited game loading | Not performed; no installed Windows game available in cloud |

### Validation

`tests/test_orochiz_format.py` covers procedural identity/revision/checksum
rejection, every integrity byte, opaque-tail preservation, existing-only weapons,
rank encoding, capacity dependencies, ID-specific base-attack floors/ceilings, unusual values, surgical Max, immutable
snapshots, backup/restore and source-change safety. `OROCHIZ_NATIVE_SAVE` can point
to the privately copied public native fixture: its optional check performs an
unchanged roundtrip and every qualified individual field edit, verifies each
edit changes only its field and checksum, reparses it and preserves the original.
The public fixture generator is procedural; it is never claimed as game data.
`tests/test_orochiz_gui.py` exercises search, Apply, Review Changes, Undo, safe Max,
inspection, themes, automatic backup and new-destination Save As under Xvfb.
The shared scalar contract adds unchanged/surgical roundtrip, bounds, frozen
identity and backup/restore tests. No test executes the game binary, loads an
edited save in the game, or distributes the sample.

The independent `tests/test_orochiz_review.py` rechecks existing-only ownership,
mask/capacity constraints, enum-five preservation, unknown bits/tail, native
field isolation and a GUI workflow using a private genuine-copy input. It also
corroborates all 96 interpreted attack bounds against the attached executable.
The combined format, contract, procedural GUI and independent review suites
passed 29 tests with the later uploaded native fixture under Xvfb, including
`tests/test_orochiz_equipment.py`: same-officer choices, empty/unknown references,
surgical integrity updates and the genuine dropdown/Undo/Review/Save As workflow.
The older progressed native copy separately qualifies the growth controls via
`tests/test_orochiz_growth.py`, selected with `OROCHIZ_GROWTH_SAVE`; five focused
tests cover every legitimate progressed band, malformed EXP/levels, preserved
dependencies, individual genuine surgery and genuine GUI/source-backup saving.
A further independent `tests/test_orochiz_progression_review.py` audit passes
five checks covering combined selection/EXP/weapon edits, invalid pending changes,
unusual-layout preservation, genuine progressed combinations and final-level
exclusion. Its reviewer also independently compared all 99 native EXP thresholds.
The complete current Orochi Z native/adversarial/Tk suite passes 39 checks.
All are file and GUI validation, with no edited in-game load validation.

No matching DLL or save-owner secret is indicated by the qualified native save
path. Further rich controls require the matching installed game's LINKDATA
parameter/localization records and labelled one-action native save pairs; the
existing independently tested controls remain available without those inputs.

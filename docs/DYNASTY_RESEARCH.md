# Dynasty Warriors PC expansion evidence and coverage

Original DW9 PC fixture acquisition and mechanic-specific blockers are recorded
in [the original-game investigation](DW9_ORIGINAL_PC_RESEARCH.md). It remains
separate from the DW9 Empires adapter below. [DW8 edition qualification](DW8_ORIGINAL_PC_SCOPE.md)
found no distinct original-only Windows product or native format; XL/Complete
and Empires names do not qualify another original-edition adapter.

Research was performed statically. No supplied game executable was launched.
Public player saves and attached executables stay outside the repository,
builds and release assets. No Steam owner identifiers or custom character names
are recorded here. Successful editor serialization is not a game-load test.

## Dynasty Warriors 7: Xtreme Legends Definitive Edition

Native gameplay filename `save.dat` and the `KoeiTecmo/Dynasty Warriors 7 DX/Savedata`
folder are present in the statically decoded executable. `inputmap1.dat`,
`inputmap2.dat` and `inputmapm.dat` are separate input maps.

Implemented `src/koei_editor/games/dw7xl/dw7xl_codec.py`, `src/koei_editor/games/dw7xl/dw7xl_parser.py`, `src/koei_editor/games/dw7xl/dw7xl_editor.py` and format/
shared scalar contract regressions. The explicit PC adapter accepts only the
470,307-byte native revision `0x11080200`. It exposes gold, health, attack,
defense, power, speed and spendable skill points for 65 playable record slots,
plus switching between their already equipped owned weapons: 456 static fields.
Qualified owned, unlearned weapon records additionally permit manual seal-meter
reduction to 0..the opened meter, excluded from Max. See the
[existing-editor depth review](OROCHI_DYNASTY_DEPTH.md) for native negative-operation
proof and the genuine complete fixture's absence of eligible unlearned records.
Officer identity names are not inferred from an unverified roster order.

The GUI retains Undo, Review Changes, copied-source backups, immutable source
snapshots and new-destination saving. Active weapon is a choice excluded from
Max; selecting an empty, unsupported or unowned referenced record is rejected.
Named choices identify the first/second equipped weapon and its inventory slot,
without inferring an asset-backed weapon name or granting a new reference.
Max preserves higher existing numbers. Unknown payload bytes and unusual
opened values roundtrip unchanged. Native NPC slots 66–92 remain untouched.
Searchable inspection tables show equipment/guardian references, purchased
skill masks and all 1,738 physical weapon records, including ownership flags
and seal learning meters. These tables do not grant weapons or unlock seals.

A separate [v2.5.2 conversion preview](DW7XL_CONVERSION.md) transfers qualified
persistent state from original US/European PS3 XL into this PC profile. It does
not add independent progression-edit controls or qualify converted game loading.
Three distinct PC states and original regional PS3 context are now available.

### Independent executable evidence

The supplied x86 `SM6EN.exe` contains the PC save path and filename. Its text
section was decoded privately as static data before disassembly. The address
references below are virtual addresses in that particular executable revision;
they are evidence, not runtime hooks. No unpacked executable or unpacking tool
is shipped. No third-party implementation was pasted into the editor.

| Evidence | Native address / observation |
| --- | --- |
| Word encryption / decryption | `0x8289F0` / `0x828A90` |
| Checksum | `0x828990`: sum complete little-endian 16-bit pairs |
| Top-level serializer and revision | `0x5993A0`, version check at `0x5993CD` |
| System serializer and validation | `0x5A0200`, `0x5A01B0`: 0x1F78 bytes |
| Officer serialization | `0x59E5B0`: 92 serialized 0x80-byte records through `0x59B5A0` |
| Officer validator | `0x59B4C0`: native field limits and equipped references |
| Health increment | `0x59B660`: accepts up to 1,000 |
| Attack / defense increment | `0x59B690` / `0x59B6C0`: accepts 1..1,400 |
| Power / speed increment | `0x59B6F0` / `0x59B720`: clamps increments to 100 |
| Purchased skill bit setter | `0x59B750`: indexes below 12 |
| Active equipped weapon switch | `0x59B7D0`: selects one of two valid weapon references |
| Weapon serialization | `0x5A5310`, `0x5A4BF0`: 1,738 records, 20 bytes each |
| Weapon ownership / seal learning | `0x5A4DD0` / `0x5A4CF0`: bit 0 ownership / stored learning meter |
| Seal learning reward path | `0x6B88A0`, `0x6B8936`, `0x599AD0`: grants system seal ownership and learned bit using external weapon/seal metadata |

The header is checksum `u16` at byte 0 and seed `u16` at byte 2. Encryption
uses `state = state * 0x5B1A7851 + 0xCE4E` modulo 2^32 **twice** per 32-bit
word; the result XORs the word. The final three bytes use a separate stream
restarted from the original seed's low byte, with two byte-state advances each.
There is no inner byte cipher. The native checksum includes the first two
bytes of that three-byte tail, and omits the final odd byte. The final byte is
therefore genuinely not integrity protected; the editor preserves it instead
of promising stronger native integrity than the game provides.

All offsets below are decoded payload positions, excluding the four-byte
header. Gold is `0xC7C`. Playable officer records start at `0x2039`, stride
`0x80`. Relative fields: health `+6`, attack `+8`, defense `+10`, power `+12`,
speed `+14`, purchased skill bits `+16`, two equipped weapon references
`+18/+20`, active weapon index `+22`, guardian reference `+24`, and spendable
skill points `+26`. The skill point cap 9,999 is verified in the native reader;
the stat caps are additionally corroborated by native stat gain functions.
The field at `+4` is a small enum: it is deliberately **not labelled level**.
Weapons start at `0x4E39`, stride 20: flags `+4`, ownership bit 0, seal meter
`+6`. Unknown flags and other weapon fields are preserved.

The executable names `LINKDATA_CMN`, `LINKDATA_ENG`, `LINKDATA_CMN.IDX` and
`LINKDATA_ENG.IDX`. The associated game parameter/localization containers and
indexes were not supplied. The routines dereference runtime parameter tables
for weapon definitions, seal requirements and officer skills; those complete
tables were not recovered from the executable alone. These matching data files,
or controlled one-action save pairs, are the concrete additional inputs needed
for named equipment, skill and title writes.

### Public evidence and validation

- [DW7 XL save converter research](https://github.com/koko-tsuu/dw7xl_save_converter),
  inspected at commit `15aee59cc773cb401ddad3b4c9099a03629cf700`, supplies a
  native PC fixture. Its anonymous console example is base DW7 and does not
  qualify XL; its conversion is explicitly unfinished. Its PC arithmetic was checked against
  the actual native routines. Its full-word-only checksum helper omits a pair
  the native checksum includes; the editor follows the executable.
- [Public Steam save-sharing discussion](https://steamcommunity.com/app/968790/discussions/0/595160389826986033/)
  supplies a downloadable native save. Its bytes are identical to the converter
  fixture, so these are **one independent PC sample**, not two.
- [Apollo DW7 XL patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLUS30873.savepatch)
  provides semantics and a 65-player roster count. Console offsets were not
  reused directly: native PC serialization and endianness were checked first.

Tests prove genuine unchanged roundtrip, gold-only surgical serialization and
officer stats/skill-point/owned-active-weapon surgical serialization,
synthetic targeted multi-officer edits, original seed preservation, native
tail handling, checksum/revision/size/type rejection, immutable snapshots,
Max behavior, active-weapon dependencies, inventory inspection, backups,
restore, changed-source rejection and live-folder/symlink protection. Synthetic
test data is labelled and contains no shipped player save. An optional private
fixture uses `DW7XL_SAVE_COPY`. No edited save was loaded in the game.

### Per-game coverage checklist

| Mechanic | Status / exact blocker |
| --- | --- |
| Gold | Implemented; native cap 999,999 |
| Health, attack, defense, power, speed | Implemented; native serialization, limits and gain functions recovered |
| Spendable officer skill points | Implemented; native cap 9,999; purchased flags kept separate |
| Active equipped weapon | Implemented; only existing equipped owned references; no bulk Max |
| Weapon inventory ownership | Searchable read-only physical records; granting requires native weapon classification and acquisition dependencies |
| Seal learning / weapon seals | Original exact owned/unlearned flags and meter 1..1000 permit decrease only, with no Max or reward changes. Increasing, acquiring or revoking a learned seal still requires external weapon-to-seal thresholds and system reward dependencies |
| Weapon names, types, attack and seal slots | Need weapon parameter/localization data; five native short fields have unproven semantics and are preserved |
| Officer names / slot identities | Need native playable roster identity table or controlled named saves; standard roster order is not proof |
| Purchased skills / EX unlocks | Read-only masks; need officer-specific definitions, available bit counts, costs, prerequisites and any stat rewards from game parameter data |
| Guardian beasts / mounts | Read-only equipped references; Red Hare ID 7 corroborated by published patch; ownership bitsets and other named IDs remain unproven |
| Titles, unlocks and stat rewards | Need native title enums, per-officer criteria and reward dependencies; the small officer enum is not a level |
| Story mode / stages / Conquest progression | System serializer recovered; named bit/record meanings and clear/reward dependencies need additional parameter data or controlled saves |
| Legend mode / town / merchant progression | System structure exists, but named fields, branch requirements and rewards remain unmapped |
| Bonds / sworn allies | Officer enum/reference fields are not sufficient proof; named progression and ownership mappings need controlled samples |
| Gallery / movies / music / collections | Need named system bit definitions and native unlock dependencies; no blanket story/content unlock |
| EXP / levels | No independent proof of a persistent DW7 level/EXP field; no analogous DW8 fields invented |
| Legitimate revisions/layout variations | Only exact supplied executable / genuine revision qualified; other sizes/revisions fail closed |
| Game-load validation | Requires Windows game plus disposable save-owner context; not performed |

## Dynasty Warriors 8 Empires

`src/koei_editor/research/dw8e/dw8e_codec.py` now qualifies a strict native-PC codec independently of the
broader arithmetic-only `src/koei_editor/research/dw8e/dw8e_candidate_codec.py`. It requires an explicit
SystemSave or BattleSave profile, exact native sizes, both relevant checksums
and decoded title revision `0x140828F1`. The research codec remains separate
from the newly implemented SystemSave adapter described below. Unknown envelope metadata and original seed are
preserved; metadata preceding checksum byte `0x408` is not checksum protected.

The outer header/body boundary is `0x40C`; checksum/seed are `0x408/0x40A`.
SystemSave is 244,952 bytes and uses the inner byte cipher seed `0x14082801`
plus a final byte checksum. Battle/Empire/Quick saves are 1,083,236 bytes and
use only the outer word cipher. The outer generator uses three advances per
word, unlike DW7 XL. One SystemSave, three EmpireSave and one QuickSave from
the [public Steam save-sharing discussion](https://steamcommunity.com/app/322520/discussions/0/1319961868335012150/?ctp=2)
all satisfy the applicable checksum(s), share the title revision, and roundtrip
unchanged. They are five files from a single public save bundle, not five
independent players. Private tests use `DW8E_SAVE_FOLDER`. Raw-byte surgical
serialization tests establish codec behavior only, without gameplay claims.

The development SystemSave adapter edits seven appearance members in qualified
already occupied custom horses. Body Type remains manually 0–4; the six other
members admit only original same-member positions witnessed in qualified ordinary
PC horses, with no values imported from PS3. The table begins at
decoded `0x38104`, contains 150 records of `0x4C` bytes, and each fixed
record identifier at `+0x44` must equal `30 + slot`. The seven appearance bytes
are `+0x10`..`+0x16`; actual model identity, movement speed,
power, abilities, ownership and names remain unchanged. Max does not alter
this category. Searchable inspection shows all 150 records. See
[custom-horse proof, tests and limitations](DW8E_CUSTOM_HORSES.md).
The [depth review](OROCHI_DYNASTY_DEPTH.md) records the additional six controls,
independent native PC witnesses and GUI/backup/restore tests.
The genuine system sample roundtrips unchanged and qualified body edits are
surgical; this does not establish an edited game-load test.

Published numerical cipher observations originated in
[DW8E modding research](https://www.tapatalk.com/groups/koeiwarriors/dw8e-modding-efforts-t17446-s10.html)
and were inspected via the
[decrypter research samples](https://github.com/bucanero/ps3-save-decrypters/tree/b2e98ed254e6afc57697bf19fddf84296863dad1/dw8xl-decrypter/samples).
Public console patches and a PC runtime Cheat Engine table supply hypotheses,
but neither alone proves a native serialized field, its record identity or
safe progression dependencies. Currency order labels disagree between sources.
No runtime pointer from a Cheat Engine table is used as a file offset.

| Mechanic | Status / exact blocker |
| --- | --- |
| Native PC system/empire/quick codecs | Genuine-file checksums and unchanged roundtrips qualified; no game-load test |
| System bonus points / bonus equipment / completion | Need exact scalar meanings, native bounds and reward/unlock dependencies |
| Empire gold, materials and troops | Plausible 40-record stride observed; published order conflicts; native serializer/controlled before-after saves required |
| Officer merit, level, health, attack, defense, leadership | Plausible 0x5C-stride records observed; starting identity and field limits not independently proved |
| Weapon aptitude and stratagem slots | Repeated byte arrays resemble runtime layouts; precise enum semantics, prerequisites and ownership remain unproven |
| Existing custom horse Body Type | Registered development SystemSave editor: occupied, known original 0–4 only; manual 0–4, no Max or new horses |
| Other six horse sliders | Qualified original ordinary horses only; choices restricted to original same-member PC witnesses, no Max; universal natural domains remain unqualified |
| Horse models, speed, power and abilities | Read-only inspection; effect/ownership dependencies remain unqualified |
| Weapons, items and reinforcement | Need native inventory schemas, named records, limits, ownership and equipment dependencies |
| Relationships, marriage, children and recruitment | Need campaign record identities and relationship/offspring dependencies |
| Custom officers, units, scenarios, flags and bases | Separate custom officer files observed; serialization and legitimate bounds not recovered |
| Campaign choices, fame, territory and completion | Need native campaign enums, ownership and clear/reward dependencies |
| Movies, events, collection and music | Need named bit maps; no story unlocks guessed |
| Further safe editor features | Native PC executable/parameter data or controlled before/after native saves are still essential |

## Dynasty Warriors 9 Empires

The initially oversized attachment was replaced with an accessible executable.
Its Steam 1.0.1.1 code was inspected statically; no game executable was run.
The implemented current native PC **SYSTEMDATA/SAVEDATA.BIN** profile is
3,087,400 bytes (`0x2F1C28`) with little-endian revision `0x210602F0`.
Older revisions `0x20083100`/`0x21051400` and sizes `0x2F1A15`/`0x2F1BF0`
are rejected. This is a source-backed editor: no independently acquired genuine
current gameplay save or edited game-load/re-save has been qualified.

Native main-save requests distinguish SYSTEMDATA from
`CAMPAIGNDATA000` through `CAMPAIGNDATA029`; the campaign profile is
`0x317B03` bytes and is not editable. Whole-kind-2 serializer and direct native
ReadFile/WriteFile paths establish plaintext SYSTEMDATA, without a payload
checksum, cipher or owner key in this path. A CryptoMD5 path hashes the executable
itself rather than the save. External `sinpmap.dat` is a separate 110-byte input
binding file; it is not save integrity. No missing DLL or original-owner secret
is currently required for this specific SYSTEMDATA profile.

The first serialized inventory stores 800 little-endian u16 quantities at
`4 + 2*itemID`. Native setter `0x14064A620` clamps at999. Only existing ordinary
quantities1..999 qualify **manual** edits1..999. Zero/higher values and all other
bytes remain intact. Every field is excluded from Max because these categories
have not been qualified as independent freely maximizable resources.
All 800 slots remain searchable by native ID; no guessed names are assigned.

The native serializer-to-live bridge qualifies 900 custom-officer records at
`0x1E137F`, stride`0x212`, for read-only inspection. Their saved names,
flag bytes and eight-u16 vectors are preserved. Full capacity ends at
`0x27F1C8`; the remaining `0x72A60`-byte tail remains untouched. Runtime CAW
addresses do not become disk offsets without that bridge.

| Mechanic | Implemented scope / exact blocker |
| --- | --- |
| SYSTEMDATA identity, plaintext and revision | Static native profile and strict procedural qualification; genuine current PC file and game-load validation remain missing. Other revisions/layouts require separate serializers and samples. |
| Existing inventory quantities | Manual native-ID edits for occupied ordinary entries; searchable800-slot inspection. Active item-name/category and ownership proof is still needed. Localization includes inherited DW9 bait strings which do not prove meaningful Empires inventory names or availability. |
| Gold/rations/army strength, merit and reputation | No writes. Campaign budget, rank and reward-dependent domains need the complete campaign serializer/profile and controlled purchase/monthly-result/reward pairs. An inventory u16 is not presumed campaign currency. |
| Artifacts, gems, weapons and secret plans | No writes. Artifact rarity gates weapon grade and gem capacity; equipment, elements, secret-plan sets and large battle plans need exact active catalog identities, ownership/equip references and prerequisite/reward routines. Conventional weapon reinforcement/fusion systems are not invented. |
| Officer levels/stats, compatibility and custom officers |900 CAW records inspected, not written. Campaign-trained compatibility differs from inherited CAW compatibility; level/stat rewards, natural caps, child/inheritance and derived weapon grades require qualified native dependencies and controlled pairs. |
| Bonds/marriage/children/recruitment | No writes. Companionship ranks, sworn allies, spouse/parent links, campaign-end child creation and acquisition rewards need exact record domains and consistency rules. A raw relation or child byte alone is insufficient. |
| Campaign/territories/stroll/exploration | Campaign sizes/folders discovered, no writer. Need the first578-byte metadata and full campaign layout, ownership/capital/defense/army/month gates, action power and clear/reward dependencies. Story completion remains separate from inventory edits. |
| Mounts/arrows/hideaway furniture/appearance | No writes; active named catalogs, ownership, slot/equip links and acquisition rules are missing. Legacy localized assets and runtime appearance tables do not independently qualify save maps. |
| Collections/gallery/movies/music | No writes; persistent record identities and legitimate unlock/reward dependencies remain unqualified. |

Gameplay mechanics were checked against the
[official English manual](https://www.koeitecmoamerica.com/manual/dw9e/en/)
and [Steam mechanics guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2705195639).
MIT [DW9E-Bin-Tool](https://github.com/HeitorSpectre/DW9E-Bin-Tool/tree/348dfbd23bd84330abd63b867f7ef59c2fd791ad)
provides asset-container context, not a disk-save codec. Public translation
assets and runtime CAW export/import scripts were inspected privately as leads;
no assets, player data, restricted source or runtime scripts are incorporated.
The relevant native asset/localization catalogs remain separate inputs.

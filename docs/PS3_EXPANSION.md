# Dynasty Warriors 7, DW7 Empires and Samurai Warriors 4: PS3 exports

Original US/EU **DW7 Xtreme Legends** has a separate
[native-bound editor and guide](DW7XL_PS3.md). It is not the base-DW7 format below.

These are separate PS3 adapters. They accept copied **decrypted** exports, not
PC saves or encrypted files copied directly from a console. Use Apollo Save Tool
to export a decrypted `APP.BIN` (DW7) or `DATA.BIN` (DW7 Empires/SW4), keep the original
export separately, edit the copy, and reimport/resign with Apollo before loading
on the PS3. This application does not update console `PARAM.PFD`, encrypt files
or change save ownership. No console credentials are required.

## Qualified profiles and validation

| Adapter | Exact qualified profile | Integrity and identity |
| --- | --- | --- |
| Dynasty Warriors 7 | US `BLUS30690` and EU `BLES01149`; decrypted `APP.BIN`, 453,564 bytes (`0x6EBBC`), big-endian revision `0x11011200` | Exact length/revision checked. Apollo's published scalar patches contain no additional game checksum update; console encryption/authentication remains in external PFD metadata. A conflicting optional `PARAM.SFO` companion is rejected. |
| Dynasty Warriors 7 Empires | US `NPUB30846-SYSTEM`; decrypted `DATA.BIN`, 121,030 bytes (`0x1D8C6`), big-endian revision `0x12072200` | Exact SYSTEM length/revision checked. PFD encryption/authentication remains external. When present, `PARAM.SFO` must identify exactly this SYSTEM directory; campaign exports are rejected. |
| Samurai Warriors 4 | US PSN `NPUB31564`; decrypted `DATA.BIN`, 409,600 bytes (`0x64000`), big-endian revision `0x2118` | Four native gameplay checksums, standard officer identities 0–54 and regional discriminator checked. Japanese offsets are rejected. A conflicting optional `PARAM.SFO` companion is rejected. |

A standalone file retains its internal qualified profile. When `PARAM.SFO` is
present beside the opened copy, only its `SAVEDATA_DIRECTORY` identity is read;
account fields are neither extracted nor displayed. Existing unusual/higher
values, unknown IDs, flags, padding and nonedited systems remain unchanged.

Three genuine publicly shared DW7 exports (two US and one EU), plus five US and one
Japanese SW4 exports, were downloaded from GameFAQs and decrypted privately
using an independently implemented interpretation of the documented PS3 PFD
AES layout. No player files, PFD keys, account identifiers or console binary
code are included in the repository. Unchanged roundtrips and surgical scalar
edits passed against the qualified genuine profiles. The Japanese SW4 sample
qualified the differing checksum layout but is deliberately rejected by the US
editor. **Edited console loading/re-saving has not been tested.**

Eight focused tests cover procedural roundtrips, genuine qualification, surgical
edits, checksum corruption, unsupported platform/region, immutable snapshots,
manual staging/unstaging, unusual-value preservation, backups/restore, changed
sources and real Tk search/apply/review/Undo/save workflows. Tests requiring
private inputs use `DW7_PS3_US_COPY`, `DW7_PS3_EU_COPY` and `SW4_PS3_US_COPY`;
without these variables, genuine qualification is explicitly skipped.

## Features and coverage

| Game/system | Result | Specific remaining evidence/input |
| --- | --- | --- |
| DW7 gold | Manual editing, 0–999,999 | Native PS3 resource cap proof before automatic Max. |
| DW7 health, attack, defense | Manual editing for 62 officer slots, up to the published 1,000 target | Natural limits beyond the published patch target; per-slot named roster mapping. |
| DW7 power, speed | Manual editing up to 100, only when the untouched upper storage byte is zero | Native PS3 full-word accessors before exposing unusual upper-byte values. |
| DW7 skill points | Manual editing for 62 slots, up to 9,999 | Native PS3 gameplay cap before automatic Max. Purchased skill flags remain unchanged. |
| DW7 guardian beasts, skills, weapon ownership/seals | No writes | Guardian patch value 7 alone does not prove ownership, unlock or equip prerequisites; weapon and skill structures need PS3 native routines or controlled action pairs. |
| DW7 character unlocks, levels/EXP, campaigns, stages, collections | No writes | Exact bit identities, EXP/stat/reward dependencies and controlled before/after saves. |
| SW4 gold and eight gem quantities | Manual editing, gold up to 999,999 and gems up to 99 | PS3 native cap evidence for Max; exact ordered gem-name table. |
| SW4 weapon proficiency | Read-only levels and four stored EXP values for 55 qualified standard officers | Exact level/EXP threshold and growth dependencies are unqualified; published level-only patches are insufficient. No proficiency writes are exposed. |
| SW4 character stats, levels/EXP, unlocks | No writes | Published EXP and 50-gauge cheat targets alone do not prove legitimate level/stat/gauge dependencies; native PS3 generation/reward routines or controlled saves required. |
| SW4 weapons, skills, rarity, reinforcement/fusion | Searchable read-only 60 × 8 weapon records with eight named skills, stored ceiling/rank and raw flags | Published first-weapon patches contain placeholder IDs. Existing owner/type aliases and PS3 activation/rank reward dependencies still need native routines or controlled action pairs before writes. |
| SW4 mounts, bonds/bodyguards, Chronicle/story, exploration, stages, movies/music | No writes | Per-system stored identities and dependencies; completion remains separate from resources. |
| SW4 Japanese profiles | Checksum research only; US adapter rejects them | JP gold layout differs by regional serialized sections; qualify exact scalar offsets separately before registering JP editing. |

All current PS3 manual controls set `maxable=False`: published cheat targets are
not treated as natural gameplay caps. Story completion and equipment/content
creation are not bundled into resource changes.

## Published evidence and licensing

Offset/width/stride facts are independently reimplemented from the published
[Apollo patch database](https://github.com/bucanero/apollo-patches/tree/main/PS3):
`BLUS30690.savepatch`, `BLES01149.savepatch` and `NPUB31564.savepatch`.
The four-part checksum's mathematical definition was independently implemented
and matched all stored checksums in genuine regional saves; reference
[Apollo core checksum implementation](https://github.com/bucanero/apollo-lib/blob/main/source/crc_util.c)
(`apollo_hash_sw4`) and its documented big-endian output. The repository does not
copy Apollo GPL implementation code or include the patch database wholesale.

Genuine public sources:

- [DW7 US save 21989](https://gamefaqs.gamespot.com/ps3/606303-dynasty-warriors-7/saves/21989)
- [DW7 US save 22252](https://gamefaqs.gamespot.com/ps3/606303-dynasty-warriors-7/saves/22252)
- [DW7 EU save 23050](https://gamefaqs.gamespot.com/ps3/606303-dynasty-warriors-7/saves/23050)
- [SW4 US save 34725](https://gamefaqs.gamespot.com/ps3/730732-samurai-warriors-4/saves/34725)
- [SW4 JP save 23789](https://gamefaqs.gamespot.com/ps3/730732-samurai-warriors-4/saves/23789)

## Totori DX and Samurai Warriors 2 HD investigation

The Apache-2.0 [jrpx/AtelierTotoriColeCheat](https://github.com/jrpx/AtelierTotoriColeCheat)
identifies Steam app 936180 and changes three little-endian Cole bytes at
`0xB3FC` to 400,000/600,000. It does not identify file headers, revisions, size,
checksums or slot layout. These are candidate offset facts, not an editor profile.
A public SaveGame.Pro page labelled Totori DX supplied a `936160/SYSDATA` archive
of 36,864 bytes, identifying Rorona DX rather than Totori; the Cole offset falls
outside that file, so the mismatched sample was excluded. A correct Totori
Steam 936180 `GAMEDATAxx`/`SAVEDATA` file is still required, together with native
serializer/integrity evidence. The MIT
[atelier-arland-fixes](https://github.com/nicoverbruggen/atelier-arland-fixes)
provides useful native equipment and item-container facts, including 999
serialized container records and a demonstrated crash caused by changing the
scan limit to 5,000. Runtime equipment offsets are not used as disk offsets.

Apollo `NPJB00439.savepatch` identifies Japanese PS3 Samurai Warriors 2 HD
`DATA.BIN`: big-endian money at `0x2758`, and additive byte checksum over
`0x8..0x36DF`, written at both `0x36E0` and `0x23790`. It does not establish a
native file size, header/revision or character/weapon array identities. No
matching genuine fixture was present in the public Apollo save database. A
copied decrypted NPJB00439 export (with optional `PARAM.SFO` for identity) or
native PS3 serialization routines is needed before exposing writes; bounds and
prerequisites for its character growth, weapons/attributes, skills, guards,
horses, Survival, story/stages and collections remain unqualified.

The two corresponding GameFAQs PS3 save pages (compilation 723490 and standalone
737594) were revisited and contain no downloadable save entries. Original PS2,
Xbox, Xbox 360, Vita and HD PS3 files are separate profiles; their offsets and
product identifiers are not transplanted. The current money/checksum candidate
does not justify a standalone PS3 writer without native identity/layout evidence.

The SW4 US weapon inspector independently walks the source-documented block at
`0x3882`: 60 pools × eight `0x22`-byte records end exactly before gold at `0x7842`.
The public PS3 patch's per-pool stride is `0x110` and its eight-byte arrays locate
ceilings at `+2`, skill IDs at `+0xA`, ranks at `+0x12`, and raw flags at `+0x1A`.
The genuine US sample has 180 nonempty records with 1,440 attached skills;
empty identity 180, unknown IDs/ceilings/ranks/flags are preserved. Named skill
inspection does not interpret raw flags as qualified PS3 activation controls.
Nine resource fields remain writable, with existing section checksums and
decrypted-export/reimport/resign requirements unchanged.

## Dynasty Warriors 7 Empires: US PS3 system profile

The separate `dw7e_ps3` adapter accepts the **SYSTEM** `DATA.BIN` export from
`NPUB30846-SYSTEM`, 121,030 bytes (`0x1D8C6`), revision `0x12072200`.
It edits the system bonus-points pool at big-endian DWORD `0xA54`, using the
published 99,999 manual target with automatic Max disabled. It preserves all
purchased/unlocked rewards, story and campaign bytes. Campaign `PLAY` exports
are not supported by this system profile. Reimport/resign through Apollo as for
the other PS3 adapters; optional `PARAM.SFO` must identify exactly
`NPUB30846-SYSTEM`. Campaign, different-region and unknown directory variants
are rejected before reading or writing a copy.

The genuine public [GameFAQs save 35288](https://gamefaqs.gamespot.com/ps3/672622-dynasty-warriors-7-empires/saves/35288)
contains an already decrypted system file and identity metadata. Its unchanged
roundtrip and targeted point edit passed. Six focused tests cover native and
procedural qualification, surgical preservation, rejected profiles/values,
backups/restore, changed sources and the actual Tk bonus control, Review, Undo,
Max preservation and Save. The optional genuine fixture variable is
`DW7E_PS3_SYSTEM_COPY`. Console loading/re-saving remains untested.

| DW7 Empires system | Coverage/blocker |
| --- | --- |
| System bonus points | Manual edit implemented and genuine-file qualified. |
| Campaign food, information and gold | Published `NPUB30846-PLAY*` patches identify u16 fields at `0x2BD0E`, `0x2BD12` and `0x2BD16`, but a matching decrypted campaign export/native serializer is needed to qualify file identity, revision and structure independently from SYSTEM. |
| Officer abilities, fame/virtues, ranks and stats | Published six-ability patches target level thresholds, not independently qualified EXP/level/reward dependencies; controlled campaign action pairs/native routines required. |
| Weapons, items, mounts, friendships/families, kingdom/campaign progress | Serialized record IDs, ownership and campaign-dependent prerequisites remain unqualified. System bonus editing does not unlock or complete these systems. |

## Further PS3 leads investigated

Two genuine US Strikeforce saves were acquired from
[GameFAQs 974378](https://gamefaqs.gamespot.com/ps3/974378-dynasty-warriors-strikeforce/saves),
IDs 34790 and 34848. Both qualify as `BLUS30471-SAVEDATA` through metadata;
private decryption yielded `APP.BIN` of 295,012 bytes (`0x48064`). The first
bytes differ (`00010000` / `01010100`) and appear to be state flags rather than
a revision identifier. Apollo's source facts describe three slot regions at
stride `0x18000`, gold and 196 storehouse ID/ownership/quantity entries; one
shared save has modified quantity 150. Exact native identity/revision/integrity
and record ownership semantics are required before exposing edits. Character
EXP/proficiency, growth and abilities must be qualified together; patch targets
alone are insufficient. No Strikeforce adapter is registered from these facts. The new
[US record inspector](STRIKEFORCE_PS3.md) independently qualifies occupied player
records and separates 42 persistent officers from selected-state copies. Its
196-row material-ID array begins at `0x9B8`, eight bytes after Apollo's broad
patch block start. It preserves empty/unknown IDs, raw flags and modified values
without authorizing writes; native integrity/revision remains the exact blocker.

Samurai Warriors 2 HD's correctly identified GameFAQs pages
[723490](https://gamefaqs.gamespot.com/ps3/723490-sengoku-musou-2-with-moushouden-and-empires-hd/saves)
and [737594](https://gamefaqs.gamespot.com/ps3/737594-sengoku-musou-2-with-moushouden-hd-version/saves)
contained no public save downloads at the time checked. Its unregistered
`research/sw2hd_ps3/inspection.py` diagnoses candidate money, partial checksums
and three separately published EXP/weapon anchors; it deliberately offers no
game profile or write API. Four procedural tests verify checksum endianness,
duplicated sums, bounded immutable input, raw record preservation and checksum
collisions/uncovered bytes that cannot qualify complete integrity. These are
not genuine-file qualification. See the updated [exact-edition checklist](SW2HD_PS3.md).

## Dynasty Warriors 8 Empires PS3 codecs and SYSTEM custom horses

The [US public GameFAQs export 30046](https://gamefaqs.gamespot.com/ps3/806920-dynasty-warriors-8-empires/saves/30046)
contains both `NPUB31656-SYSTEM` and `NPUB31656-EMPIRE3` console files.
PFD encryption was removed privately without executing a game binary.
The campaign plaintext is 1,091,800 bytes; SYSTEM is 251,036 bytes and retains
a game byte cipher with seed `0x14082801` plus a final byte-sum checksum.
Decoded SYSTEM is 251,035 bytes. Both decoded revisions are little-endian
`0x140828F1`. Their sizes differ from PC envelopes; the codecs are not
interchangeable. These envelopes roundtrip unchanged and research byte edits
roundtrip after serialization. Console loading remains untested.

The unregistered `research/dw8e_ps3/codec.py` validates these explicit profiles,
checks SYSTEM integrity and inspects the source-proposed 40-row resource array
at `0x5BF4`, stride `0xE4`. It has no gameplay staging, Max, GUI or file writer.
Its records report the raw ordinal, prefix flag and three stored DWORDs.
The [published Apollo patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPUB31656.savepatch)
calls the values materials/money/troops, while a separately published PC
runtime table calls them materials/troops/gold. The order conflict and absence
of a native PS3 save-owner bridge prevent safe gold/troop editing. Positive
records alone do not prove whether owners are kingdoms, territories or other
campaign actors. The single offsets `0x5F84/0x5F88/0x5F8C` in the same patch
are row 4 of this array, not a separate global resource pool.

The [official manual](https://store.steampowered.com/manual/322520) distinguishes
materials, gold and troops obtained from victories, monthly territory income
and strategy commands; they pay for commands, equipment and base fortification.
It separately describes total kingdom troop strength, officer troop allocation,
level/Merits, Way of Life, relationship and campaign progression. These values
must not be conflated with resource DWORDs or SYSTEM bonus points. Richer
controls require native serialized identities, the actual resource order and
owner relationship, EXP/level thresholds, and acquisition/equipment dependencies.
No completion, reward, relationship or officer stat patch is exposed here.

Three codec tests cover procedural profiles, corrupted SYSTEM checksum,
wrong revision/platform/size, exact immutable snapshots, read-only records
and optional genuine exports through `DW8E_PS3_SYSTEM_COPY` and
`DW8E_PS3_EMPIRE_COPY`. They are distinct from game-load validation.


The new separate [US SYSTEM adapter](DW8E_PS3.md) independently identifies the
PS3 custom-horse table at decoded `0x39B94`, checks all 150 ordinal identities,
and implements manual Body Type editing for qualified existing ordinary horses.
It recomputes the existing game byte checksum and preserves type/model/stats,
abilities and ownership. The original exact `NPUB31656-SYSTEM` metadata is
mandatory beside source and destination. This narrow SYSTEM feature does not
resolve campaign resource ownership/order. Genuine surgical and actual Tk
backup/save/restore tests pass; console loading remains untested.

## Warriors Orochi 3 Ultimate: US PS3 NPUB31505

The separate [US Ultimate adapter](WO3U_PS3.md) edits only unallocated growth
points and precious stones. Two genuine exports establish `NPUB31505-SAVEDATA`,
native revision `0x140318F1`, plaintext length `0x2119CA`, and every PS3 officer
and weapon marker. Original metadata is mandatory. Apollo's `NPUB50173` and
`NPEB02052` patch identifiers are leads, not alternative accepted identities.

A firsthand US PS3 direct-hex-edit report corroborates these two resources.
Its incorrect numeric conversion is not implemented. The narrow writer changes
only the selected little-endian DWORD and preserves all other bytes; arbitrary
unknown-byte corruption cannot be authenticated by record checks. It makes no
global native-checksum-absence claim. Officer progression, weapons/fusion,
inventories, bonds, stages and collections are inspected or preserved rather
than written. Genuine no-op/surgical and Tk backup/save/restore tests pass;
external PFD reimport/resigning and our actual console load remain separate.

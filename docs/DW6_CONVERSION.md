# DW6 PC, PS3 and Xbox 360 progress migration

**Unreleased development, version unchanged at 2.5.1:** original Japanese PS3
`BLJM60041`, European PS3 `BLES00215`, North American Xbox 360 `4B4F07E0` and
European Xbox 360 `4B4F07E1` join PC and US PS3 as conversion-only endpoints.
Thirty directions transfer roster/horses. Thirty **`-progress`**
routes also transfer all 45 persistent stage records and 17 Musou availability/clear
records. Thirty **`-campaigns`** routes additionally transfer all 20 stored Musou
run slots. Thirty **`-records`** routes additionally transfer 40 music/170 movie
availability bits and five challenge boards. The four scopes remain separate
choices in the converter. Options, suspended battles and all other unmapped bytes stay from the
destination template. No scope transfers an active interim battle snapshot.

Version 2.1.2 adds **PC ↔ US PS3 BLUS30110** transfer of all 41 officer records
and eight complete horse records. It is explicitly a **partial progress
migration**, not a full story/suspended-battle conversion. The destination
template retains stages, story clears, gallery, challenge results, options,
suspended battles and every byte outside the two mapped arrays. Finish a
suspended battle in the destination game before making its template.

Use the Save Converter with a separate original PC `save.dat` copy and a copied
PFD-decrypted PS3 `APP.BIN` with original `PARAM.SFO`. Review displays the scope
before export; CLI dry runs and schema-2 receipts also identify it as
`roster-and-horses`. PS3 reimport, PFD authentication and resigning use an external
save manager. See [conversion instructions](SAVE_CONVERSION.md).

## Independently established geometry

| Record | Original PC | US PS3 | Typed transformation |
| --- | --- | --- | --- |
| Native file | 212,248 bytes | 212,240 bytes | Destination framing and untransferred bytes retained. |
| Officers | `0xB58`, 41 × `0xA8` | `0xB18`, 41 × `0xA8` | Same canonical identities 0–40. |
| Skill tree, officer +0 | Little-endian u64 | Big-endian u64 | One whole eight-byte mask; unusual/reserved bits preserved. |
| Eight weapons, officer +8 | Eight four-u32 records | Same records, big endian | ID, stored bonus, element and skill mask transfer together, including empty/unknown entries. |
| Officer +136 through +160 | Seven little-endian u32s | Seven big-endian u32s | Identity, outfit, title, stored level, EXP, kills and selected weapon slot. |
| Officer +164 | One playable byte plus three opaque bytes | Same byte framing | Copy byte and opaque remainder without word swapping. |
| Horses | `0x2A08`, 8 × `0x3C` | `0x29C8`, 8 × `0x3C` | Fifteen u32s per complete record, converted individually. |

Horse EXP begins **24 bytes into** its complete record: `0x2A20` on PC and
`0x29E0` on US PS3. The six preceding words are color, name suffix, name prefix,
physique, eyes and title. They precede EXP, saddle/type, element, skills, speed,
quality, attack, jump and destruction. The old combat-stat base remains correct
for editing those stats, but copying 60 bytes starting at EXP would miss the
first horse's identity/growth and mistakenly copy challenge bytes after horse 8.
Migration copies the complete original state; it does not independently edit or
invent growth, skills, inventory, rewards or progression. Existing empty entries,
unusual values and source record relationships are preserved without clamping.

The full-tree native mask is little-endian `FF FF FF FF FF FF 01 00` on PC and
big-endian `00 01 FF FF FF FF FF FF` on PS3. Both represent the same 49 enabled
bits. Copying the eight bytes unchanged or swapping two separate u32s would
produce the wrong learned skills. Semantic-value tests supplement reverse
roundtrips, which alone cannot detect a symmetrically wrong transform.

## Sources and research

- [cnopt's PC research](https://github.com/cnopt/dynastywarriors6-reverse-engineering/tree/f2152f67b031091a0268154203d25fa9f65d2664)
  and its Cheat Engine table establish disk officer fields, native horse spacing
  and preceding name/descriptor positions. The existing factual names/IDs are
  reused; no upstream implementation or assets are imported.
- [Public DW6SaveGameEditor 0.1.0 archive link](https://f.gvn.co/threads/pc-download-huong-dan-mod-ss4mspecial-dw4hyper-dw6-ssm6.1548988/)
  led to an older .NET editor. It was inspected statically, never executed.
  Its numeric array positions independently corroborate all fifteen horse words,
  the officer fields, selected weapon slot and split PC skill-mask halves. Its
  source/licence is not supplied; no implementation or enum catalog is copied.
- [Apollo's BLUS30110 patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30110.savepatch)
  independently establishes PS3 combat/weapon coordinates and strides.
- [Native PC export](https://savegame.pro/pc-dynasty-warriors-6-savegame/),
  [US PS3 export 34847](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/34847)
  and [independent US PS3 export 16788](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/16788)
  corroborate the canonical arrays, 64-bit masks, one-byte flags and horse domains.
  Native files, keys, account context and static reports remain private.
- The publisher's [official original DW6 playable demo](https://www.gamecity.ne.jp/smusou5/trial/)
  was acquired for static investigation. This is a Japanese trial, not the
  qualified US retail PS3 or original Windows save fixture. It is not run or
  distributed and does not establish retail game-load validation.

## Checks and remaining scope

Generated tests exercise every typed field with asymmetric values, reserved
mask bits, one-byte flags with opaque neighbors, all eight horses, foreign
formats, context/source races, forged review claims, safe exports and exact
destination remainder preservation. Opt-in tests use private copies of the
independent PC export and both PS3 exports; all four forward/reverse exported
paths preserve the entire original source when reversed through that original
template. They also compare decoded skill-mask values and untouched destination
spans, not merely hash or length equality.

The US PS3 editor separately adds named one-way playable unlocks, named weapon
controls and searchable complete officer/weapon/horse inspection. PC unlocks now
write only the proven flag byte, preserving its three opaque neighbors. Officer skill-tree, level/EXP and horse descriptor/growth editing remain read only. Version 2.4 separately adds named equipment-skill toggles, horse elements and existing same-officer equipped-weapon choices; complete record migration preserves those values.

**No converted or edited save has been loaded/re-saved in an actual game by this
project.** Neither inspected native profile establishes an internal gameplay
checksum; PS3 authentication is external. Active battle transfer needs its own
typed serialization/dependency map. Special and Empires remain unavailable.
Japanese/European PS3 and NA/EU Xbox 360 use the separately qualified development
profiles below. Xbox outer-container integrity is distinct from native gameplay
integrity and actual game loading.

## v2.4 review and remaining research

Review now compares canonical typed records with the destination template:
changed officer counts/names and changed horse counts/slots are shown before
export, in CLI dry runs and batch review. Empty source records replace the
corresponding destination slots; this is not an inventory merge. These summaries
are recomputed from immutable inputs during review validation and cannot expand
the transfer scope.

Static investigation of the official Japanese PC trial found its save reader
and writer use **212,168 bytes**, compared with the qualified retail PC's
212,248 bytes. It therefore does not establish retail offsets or US PS3 story/
battle conversion. A matching record array alone is insufficient evidence for
the remaining serialized state. Neither a blanket endian swap nor replacing the
whole destination with source bytes is offered.

The [Xbox PAL save-set author's account](https://www.xpgamesaves.com/resources/dynasty-warriors-6-full-legit-saveset-dw6-european-pal.3178/)
reports that renaming containers caused failed loads and that injecting gameplay
into a genuine destination container was required. The current download requires
login. Separately preserved public 2011 binary captures now provide native
original-game evidence, described below; no login barrier was bypassed.
Empires and Special evidence does not qualify this original game's route.

## Unreleased native stage and Musou mapping

The later [official English PC demo announcement](https://worthplaying.com/article/2008/10/4/news/55450-dynasty-warriors-6-pc-english-demo-available-now/)
led to a complete installer preserved in the
[public GameFront archive](https://web.archive.org/web/20151028095120/http://www.gamefront.com/files/11992788).
Its SHA-256 is `f0e51dcdb488c0bfaf3b9eb3ab2c832238bba6ddcb79e40c5e4a31064ac5ecf0`.
The extracted executable's MD5 matches the independently
[published file identity](https://www.shouldiremoveit.com/DYNASTY-WARRIORS-6-Playable-Demo-132370-program.aspx),
`0680523e58556d09bc1c9786d555502f`. Installer and game were never executed.
Their bytes and private disassembly remain outside the repository.

This demo's native reader VA `0x5D1A10` and writer `0x5D1A60` read/write exactly
`0x33D18` (212,248) bytes. Constructor `0x5CF890` places 41 officers at `0xB58`,
45 stage records at `0x2640`, 17 Musou records at `0x29C4`, and eight horses at
`0x2A08`. Stage constructor `0x5CF6D0` initializes three u32s and separate bytes
at +12, +13 and +16; Musou constructor `0x5CE3F0` initializes bytes +0 and +1.
Initialization also uses the same first-17 officer indices for Musou availability
and playable prerequisites. The demo's version footer differs from the native
retail PC reference, so its framing and footer are never transplanted.

| Array | PC | US/European/Japanese PS3 | Transform |
| --- | --- | --- | --- |
| Stages, 45 × 20 | `0x2640` | `0x2600` | Three u32s converted separately; the eight remaining flag/padding bytes copied without word swapping. |
| Musou, 17 × 4 | `0x29C4` | `0x2984` | Availability byte, clear byte and two opaque padding bytes copied unchanged. |
| Japanese complete file | — | 212,176 bytes | Exact original `BLJM60041-SAVEDATA` metadata required; every untransferred byte comes from this region's own template. |

The complete native PC reference, both independent US PS3 references and the
[Japanese reference 16605](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/16605)
corroborate these arrays, individual counter values, byte flags, officer IDs and
horse boundaries. Metadata, exact lengths and canonical identities distinguish
profiles; regions are never relabelled or padded into one another.

The `-progress` scope transfers **8,336 bytes** of canonical typed state. Existing
roster-only routes retain their **7,368-byte** scope and preserve destination
stage/Musou records. Review names changed stage/mode IDs and explains that locked
or incomplete source entries also replace destination state. Extended receipt
hashes and read-back checks cover the extended scope, preventing a review from
being silently downgraded to roster-only validation.

Generated checks use asymmetric words and flag/padding bytes, including native
default stage time `0x4F1A0`, to catch an incorrect blanket endian swap. Private
native checks exercise all six progress directions with each US reference:
twelve actual forward/reverse export pairs, with complete original bytes restored
and individual numeric/flag values compared independently. Four additional basic
Japanese paths pass safe exports and exact reverses. These are format and copied-file
checks; **actual game loading/re-saving remains unverified**.

Reviewed provenance and layouts are packaged in `dw6_migration_evidence.json`.
The regional conversion-only endpoints do not add scalar editors to the
94-profile inventory.

## European PS3 qualification

Four independent original European exports were acquired from the
[GameFAQs save archive](https://archive.org/details/game-faqs-saves-2024-09-05),
preserving their original `BLES00215-SAVEDATA` metadata. The original listings are
[16807](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/16807),
[16808](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/16808),
[16825](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/16825) and
[19093](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/19093).
Only the archive index and selected small save members were downloaded.

All four decrypted gameplay files are exactly **212,240 bytes**. Their 41
big-endian canonical officer identities, complete horse records, stage/Musou
arrays and run slots independently corroborate the typed map. US and European
files share a size, so that size alone cannot select a region. European file
reads require the exact European directory in bounded original `PARAM.SFO`;
the complete original metadata digest is bound and rechecked around backup and
export. Japanese and European framing share one conversion-only implementation,
with distinct immutable formats, sizes and required title directories. Scalar
editing remains available only through the separately qualified PC/US editors.

## Stored Musou run slots

Native constructor `0x5CF890` constructs **20 × 132-byte records** at PC `0x108`,
ending exactly at the officer boundary `0xB58`. Record constructor `0x5CEFF0`
and reset routine `0x5CF050` establish this layout:

| Relative range | Native representation | Transfer |
| --- | --- | --- |
| +0 through +19 | Five timestamp u32s | Convert each word independently. |
| +20 through +115 | Six 16-byte result records | Convert each record's three u32s; copy its two flag and two padding bytes unchanged. |
| +116 through +131 | Four u32 selections | Preserve the complete mode/difficulty/stage/horse relationship, converting each word. |

The result constructor `0x5CF6F0` and reset routine preserve the distinction
between three numeric words and byte flags. Empty-slot defaults include mode
17, difficulty 5, stage 0 and horse 8. These sentinel values are transported,
not turned into gameplay choices or independently edited.

The native PC, five US, four European and Japanese references independently match
the full array at PS3 `0xC8`, ending at `0xB18`. They include empty, completed and
unfinished runs, with ordinary timestamp words and stage indices below six as
well as completed stage-six records. The map does not come from applying a
constant offset to unexamined bytes. No native references or player timestamps
are packaged.

The separate `-campaigns` scope carries **10,976 canonical bytes**: the existing
8,336-byte persistent scope plus these complete 2,640 bytes. All officers and
horses travel with their referenced run slots. Review identifies changed slot
numbers and explains replacement of empty as well as occupied slots. Hashes,
receipts and destination read-back include the complete selected scope. Basic
and `-progress` routes continue to preserve destination run slots.

The large interim battle object starting after the persistent records remains
excluded. This scope also retains gallery, challenges, options and native framing;
the separate records scope below transfers gallery and challenges.
Finish suspended battles before making both copies. Stored-slot transfer has
copied-native preservation and semantic-value checks; **loading and resuming
the converted slots in the destination game remains unverified**.

## Gallery and challenge records

The separate `-records` scope adds **227 canonical bytes** to campaign migration:
27 bytes carrying 210 qualified gallery availability bits, plus 50 four-byte
challenge records. The combined scope is **11,203 canonical bytes**. It replaces
source availability and complete boards, including locked entries and lower
scores; it does not merge maximum scores or manufacture rewards.

| Data | PC | US/European PS3 and NA/EU Xbox | Japanese PS3 | Transfer |
| --- | --- | --- | --- | --- |
| Music, 40 availability bits | `0xB4` | `0xAC` | `0xAC` | Five bytes, copied as bits. |
| Movies, 170 availability bits | `0xB9` | `0xB1` | `0xB1` | Twenty-one complete bytes and two low bits; the six high reserved bits stay from the destination. |
| Challenges, five boards × ten ranks × four bytes | `0x2BF6` | `0x2BA8` | `0x2BB6` | Each score is u16 and changes byte order; its officer byte and opaque byte remain byte values. |

Native music/movie setters `0x5CEE00`/`0x5CEE40` index their separate 40/170
availability tables. Movie playback `0x5E4350` connects these IDs to movie files;
the ending table maps Musou officer *i* to movie bit `9 + 10*i`. Partial original
exports independently match those ending bits to persistent Musou clear flags.
The constructor at `0x5CF973`, five-board loader `0x5CE400` and score reader
`0x59CB0F` establish the challenge layout and u16 score width. Independently
played European references contain changed scores and officer references.

Three additional original US references,
[16687](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/16687),
[16754](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/16754) and
[19334](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/19334),
bring the PC/PS3 qualification corpus to eleven files. All endpoint/reference
pairs pass typed-value checks, actual safe exports and exact reverses, preserving
original metadata and the untouched destination remainder. Native inputs are
not packaged. Actual game loading remains unverified.

Options stay platform-specific. PC initializes graphics/audio settings in the
space before its Musou slots, and controller mappings differ between platforms.
Suspended battle state is also separate: native serialization includes a
variable-length script/event queue with opaque typed payloads and relocated
references. Its regional object sizes and packing differ, so a global word swap
or a destination event queue cannot qualify an active-battle transfer.

## North American and European Xbox 360 qualification

Three preserved public XPG downloads provide 81 original CON containers:
[40 North American exports](https://web.archive.org/web/20110730191047id_/http://www.xpgamesaves.com/files/getdownload/4995-dynasty-warriors-6-north-american-version-single-acheivements-full-saveset/),
[40 European exports](https://web.archive.org/web/20110730190734id_/http://www.xpgamesaves.com/files/getdownload/5259-dynasty-warriors-6-european-pal-version-single-acheivements-full-saveset/)
and [one additional European container](https://web.archive.org/web/20110730190225id_/http://www.xpgamesaves.com/files/getdownload/5827-dynasty-warriors-6/).
The regional sets share gameplay states: they represent **40 distinct payloads**,
not 81 independent playthroughs. Native containers, extracted files and original
account context remain private.

Both extracted regional files are **212,496 bytes**, big-endian. Officers start
at `0xB18`, stages at `0x2600`, Musou records at `0x2984`, complete horses at
`0x29C8`, run slots at `0xC8`, gallery at `0xAC` and challenges at `0x2BA8`.
The native version marker is `07 09 04 00` at `0x33E04`. The additional trailer
is unmapped and retained byte-exact; no achievement semantics are inferred.
The 210 gallery bits, typed challenges and every other transferred field are
independently checked against the native references.

Opening `DW6_NA.dat` or `DW6_EU.dat` requires its unchanged original container
beside it as **`ORIGINAL.CON`**. Exact title ID, filename, native framing and
file length must match. The bounded reader accepts only the observed small
single-file, level-zero CON profile; it verifies header/root and every file-table
and gameplay-block SHA-1, block use, chain bounds and the contained native profile.
It refuses unsupported STFS layouts. RSA signatures are not verified. The
original container hash is bound to review, backup and export checks. The raw
file may differ from its embedded original, allowing converted copies to reopen;
the actual exported raw file is checked against the reviewed result.

Export creates converted raw gameplay plus the unchanged destination CON.
**The CON still contains the old template gameplay.** Replace its embedded
`DW6_NA.dat`/`DW6_EU.dat` with the new raw file in Horizon or an equivalent
save manager, then rehash/resign and restore it. This editor does not write STFS
or sign containers. See the [step-by-step workflow](SAVE_CONVERSION.md).

All 81 contexts pass integrity and copied-file checks. All 72 added directed
routes and all four scopes for each original Xbox reference pass safe exports,
independent typed-value/preservation checks and exact reverses. No inner gameplay
checksum was identified across the 40 states; the related PC writer writes raw
state. Those observations are not direct proof of the Xbox PPC serializer or
absence of an internal checksum. **Actual converted Xbox loading/re-saving
remains unverified.** Japanese, Korean and Asian Xbox title IDs remain unsupported.

## Suspended battle research

Static comparison of the official Japanese and English PC demos explains an
80-byte regional difference: a localized battle-text buffer has different
capacity and encoding. The suspended object also contains multiple typed
subobjects and a variable script/event queue. Native queue writer `0x544520`
delegates to `0x53F7C0` and serializes typed payloads with relocated references.
Preserving a destination queue while transplanting source battle objects, or
swapping every word, would leave incompatible state. A safe active-battle
converter still needs those payload kinds, reference packing, locale handling
and native load/resume controls. These findings do not expand any route's scope.

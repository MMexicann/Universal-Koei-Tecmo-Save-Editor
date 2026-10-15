# DW6 PC and original PS3 progress migration

**Unreleased development, version unchanged at 2.5.1:** original Japanese PS3
`BLJM60041` joins PC and US PS3 as a conversion-only endpoint. Six directions
transfer roster/horses. Six additional routes ending in **`-progress`** also
transfer all 45 persistent stage records and 17 Musou availability/clear records.
The two scopes remain separate choices in the converter. Gallery, challenge
boards, options, suspended battles and all other unmapped bytes stay from the
destination template. This does not continue an active campaign or battle.

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
checksum; PS3 authentication is external. Full story and battle transfer needs
its own typed serialization/dependency map. Public Xbox 360 save-set listings
were found, but no independently qualified extracted original-game payload was
obtained. Xbox 360, EU PS3, Special and Empires routes remain unavailable.
Japanese PS3 is now covered by the separate development profile described below.

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
into a genuine destination container was required. The public listing's download
requires login; other historic mirrors currently lead to dead Megaupload links.
No extracted original DW6 Xbox payload, native integrity map or successful
cross-platform load control was obtained. Empires and Special evidence does not
qualify this original game's route.

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

| Array | PC | US/Japanese PS3 | Transform |
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
The Japanese endpoint does not add a scalar editor to the 94-profile inventory.

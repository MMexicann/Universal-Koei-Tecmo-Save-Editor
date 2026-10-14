# DW6 PC and original US PS3 roster migration

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
write only the proven flag byte, preserving its three opaque neighbors. Skill
tree, level/EXP and horse descriptor/growth editing remain read only.

**No converted or edited save has been loaded/re-saved in an actual game by this
project.** Neither inspected native profile establishes an internal gameplay
checksum; PS3 authentication is external. Full story and battle transfer needs
its own typed serialization/dependency map. Public Xbox 360 save-set listings
were found, but no independently qualified extracted original-game payload was
obtained. Xbox 360, Japanese/EU PS3, Special and Empires routes remain unavailable.

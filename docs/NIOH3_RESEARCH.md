# Nioh 3 native PC USER editor and remaining research

The registered adapter in `src/koei_editor/games/nioh3` accepts native encrypted
or decoded Windows PC USER copies with revisions `0x01030001` and `0x01040000`.
It reduces existing positive quantities of thirty-two identified common items
in the item box and storehouse, and deducts source-mapped Amrita and Gold balances.
Assigning the opened amount undoes an edit. Increases, zeroing item records and
bulk Max remain unavailable. Equipment, unknown items,
progression, acquisition and rewards remain read only. The previous no-write
envelope inspector remains in `src/koei_editor/research/nioh3/nioh3_native.py`.
SYS data, console saves and other revisions are rejected.

## Proved native array boundaries

Both acquired USER revisions have contiguous native serialization blocks. Each
stores a u32 tag, u32 outer length and u32 byte count before its record array.
The outer length equals byte count plus four; the next native tag starts exactly
at the array end. Explicit profiles require these exact tags and lengths at
their acquired positions; finding plausible headers elsewhere cannot relocate
or qualify an array.

| Pool | Tag offset / value | Array start | Count × stride | Byte count |
| --- | --- | --- | --- | --- |
| Equipment | `0x240349` / `0x938A61DD` | `0x240355` | 2,500 × `0xF0` | `0x927C0` |
| Item box | `0x2D2B15` / `0xE255E585` | `0x2D2B21` | 1,500 × `0xE8` | `0x54F60` |
| Storehouse items | `0x327A81` / `0x7E3D5D38` | `0x327A8D` | 400 × `0xE8` | `0x16A80` |

The following block at `0x33E50D` has tag `0xAD8691AB` and length four. Published
bases `0x270066`, `0x302832` and `0x35779E` address the wrong bytes in these
revisions. The qualified storehouse byte count proves 400 records, rather than
the published 393. This does not qualify any unobserved revision or later DLC.

## Writable record qualification and dependencies

Thirty-two factual disk IDs are independently corroborated against the public
editor and genuine record tables. The original seven are `0x05E7` Elixir,
`0x382A` Sacred Water, `0xF3EE` Arrow,
`0xA70B` Incendiary Arrow, `0xF8DD` Ochoko Cup, `0x8A41` Salt and `0x79CF` Rifle
Ammunition. These are little-endian u16 values, rather than byte-order text. No
external item or affix catalog is incorporated.

The eleven additions are Antidote, Antiparalytic Needle, Arrowproof Amulet,
Daion-Jin's Sake, Dung Ball, Fireproof Amulet, Sacred Ash, Smoke Ball, Throwing
Stone, Travel Amulet and Water Amulet. Their exact IDs, pinned Apache-2.0 factual
source, native-record corroboration and official manual evidence are recorded
in [the expansion note](TEAM_NINJA_DEPTH.md). The same original-record
qualification and reduction-only rules below apply to every addition.

Fourteen further additions are Yokai Water Pot, Scampuss Furball, Summoner's
Candle, Righteous Jasper, Power Pill, Lantern Plant Fruit, Steel Pill,
Luckbringer Amulet, Uchiko Powder, Fragrant Wood, Healing Pill, Tiger-Running
Amulet, Sacred Brush and Herbal Remedy. Each has a qualified positive native
stack in at least one of the two reviewed revisions; the corpus does not contain
every item in every pool/revision. The same pinned factual source and independent
native-record qualification apply. [The refinement evidence](TEAM_NINJA_DEPTH.md#nioh-3-fourteen-further-ordinary-consumables)
records exact IDs and distinguishes native writes from generated coverage.

An eligible original item-box/storehouse record has a known ID at `+0x00`, the
same appearance ID at `+0x02`, a positive u16 quantity at `+0x04`, zero level,
pre-forge level and reinforcement at `+0x06`/`+0x08`/`+0x0A`, and a nonzero
instance index at `+0x1C`. Duplicate known IDs in one pool fail closed. Unknown
IDs, zero stacks, empty slots and nonordinary shapes remain read only. Dynamic
fields come exclusively from the immutable original snapshot.

Each field allows `1..opened quantity`, deliberately avoiding inferred carry or
storage caps. Higher/unusual opened values remain byte-exact and reversible.
Only quantity bytes and the native body checksum change. Identity, allocation,
appearance, shortcuts/equipped references, acquisition, rewards and unknown
flags remain intact. These edits cannot remove the final item, move it between
pools or grant ownership. All quantity fields have `maxable=False`; Max retains
staged reductions. Controlled restock/capacity/removal pairs are still required
before increases or zero become writable.

Equipment inspection displays current level, pre-forge level, reinforcement and
appearance separately. A genuine record has level 16 and pre-forge level 8;
these are not universally mirrored. Equipment and derived statistics are not
written on the strength of a repeated header pattern.

## Revision-specific source-mapped balances

The Apache-2.0 editor's historical commit
[`4be2f62ddad3631dc931c675b527bb4124802c4e`](https://github.com/alfizari/Nioh-3-Save-Editor/blob/4be2f62ddad3631dc931c675b527bb4124802c4e/main.py)
names Amrita and Gold at `0x3ADE49` and `0x3ADE59`, and reads/writes each as
eight-byte little-endian values in its Stats UI. Its equipment/item bases match
the acquired native arrays. This mapping matches revision `0x01040000`; earlier
revision `0x01030001` has the same adjacent native balance tags 36 bytes earlier.
Later published fixed currency offsets point inside another native block in
these two files and are not used.

| USER revision | Amrita tag / u64 value | Gold tag / u64 value | Following independent tag |
| --- | --- | --- | --- |
| `0x01030001` | `0x3ADE1D` / `0x3ADE25` | `0x3ADE2D` / `0x3ADE35` | `0x3ADE3D` |
| `0x01040000` | `0x3ADE41` / `0x3ADE49` | `0x3ADE51` / `0x3ADE59` | `0x3ADE61` |

Amrita has tag `0x13B43052` and length eight; Gold has tag `0x75AD54DF` and
length eight. The following tag `0x571E4459` has length four and different
original values in the two genuine copies; its meaning is not guessed. The
profiles also require the revision-specific preceding one-byte tag and the
next three native tag/length pairs. Any mismatch blocks the entire editor,
including item edits; plausible sequences elsewhere do not qualify fields.

The [official manual's progression instructions](https://www.gamecity.ne.jp/manual/nioh3/eng/4100.html)
identify held Amrita as spent at shrines and separately describe grave recovery,
character attributes and the Amrita Gauge. The source-mapped balance fields do
not authorize those separate records. Deductions allow `0..opened u64 amount`,
including zero and unusual high originals, with no assumed cheat ceiling or
Max. Only selected balance bytes and the native checksum change: grave/state,
EXP, attributes, history and all other bytes remain exact. Editing a balance
does not perform a purchase, allocation, reward or level-up. Increases and any
transaction/progression simulation remain blocked pending controlled native
gameplay pairs and actual game-load/re-save validation.

## Other native serialization research

Both genuine bodies parse from `0x190` as a deterministic top-level chain of
u32 tag, u32 length and exactly that many payload bytes, ending in zero padding.
Revision `0x01030001` has 527 top-level blocks ending at `0x7F3EEF`; revision
`0x01040000` has 535 ending at `0x7F3F3D`. This independently corroborates the
qualified inventory and balance boundaries rather than locating patterns by
an unconstrained search.

A native array at `0x15DA3D`, tag `0xFE422A50`, outer length `0xE2904` and byte
count `0xE2900`, contains 4,000 records of stride `0xE8` and ends at the equipment
tag `0x240349`. One copy contains equipment-shaped records; the other is empty.
Its ownership/storage semantics are not proved, so it does not generate fields.
Neither genuine copy has a source-described owned scroll record. Published
scroll bases and playthrough IDs alone cannot prove native scroll ownership.
Scroll generation serials and instance indices occupy distinct namespaces;
usage, reveal/ownership flags, account context, effects and equipment references
must be qualified together before attempts, seeds or scroll creation can change.

## Qualified native envelope

| Native property | Qualified value |
| --- | --- |
| User file size | `0x9001B0` |
| Clear user identity | `RNNUSR` followed by two zero bytes |
| Header size | `0x158` |
| Body size | `0x900058` |
| Header length/body length fields | u32 little endian at `0x18`/`0x1C` |
| Observed user revisions | u32 `0x01030001` and `0x01040000` at `0x08` |
| Matching body revision | u32 at `0x15C` |
| Integrity-covered body | `[0x190, 0x900190)` |
| Integrity seed/result | u32 little endian at `0x900190`/`0x900194` |
| Cipher exclusion | Final eight bytes, retained exactly |

The per-save checksum starts with an unsigned 64-bit zero accumulator. For each
`0x400`-byte block in the covered body, sum 128 signed little-endian 64-bit
values, add that sum to the accumulator, XOR with the stored 32-bit seed and
reduce to 64 bits. The resulting checksum is
`(accumulator // 0xFFFFFFFF + (accumulator & 0xFFFFFFFF)) & 0xFFFFFFFF`.
The division is not a normal upper-word shift. This is the native game's weak
integrity checksum, not a cryptographic authentication claim. No flags are
cleared, damaged input is not repaired, and the original seed is retained.

The existing MIT-attributed Katana primitives reproduce the encrypted
USER sample's entire decoded gameplay body. The published plaintext fixture has zeroes in the 64-byte body-key span
`[0x49, 0x89)`, while its encrypted partner retains wrapped key material there.
The decoders preserve the original decrypted header with wrapped
key material and retains the unencrypted final eight bytes. The entire body,
all header bytes outside that key span and the tail match the acquired reference
exactly. The full decoded files are not asserted to be byte-identical across
their different key representations. The game adapter applies the decoded
field/checksum delta to the original custom CTR ciphertext with its unchanged
stream, then decodes and validates the result again. No account rebinding is
exposed, and the original seed, wrapped keys and excluded tail remain intact.

## Coverage and precise blockers

| Discovered system | Result or required evidence |
| --- | --- |
| Native identity/revision/size and body checksum | Implemented game adapter and retained no-write inspector; genuine files and malformed-input tests |
| Native encryption/decryption | Genuine encrypted USER pair qualifies decoded representation, surgical quantity/balance writes/reparse and exact no-op ciphertext |
| Common consumables and ammunition | Reduce existing positive quantities of thirty-two identified ordinary item-box/storehouse IDs; no acquisition, removal or Max |
| Quantity increases and natural capacities | Need build-labelled displayed capacities, prerequisite/upgrade state and controlled pickup/restock/transfer pairs; storage ceilings and cheat targets are not natural caps |
| Amrita and Gold balances | Historical source and explicit native tag profiles qualify u64 deductions `0..opened`, including zero; no Max, increases, transaction history or level-up simulation |
| Currency increases, lifetime/grave state and transaction dependencies | Need controlled held/spent/recovered/reward pairs and displayed values; independent state is preserved and not inferred from the balance fields |
| Seven character attributes | Historical source maps names, and separate native seven-element current/base vectors exist; no allocations, derived stats, EXP/level or attribute writes qualify |
| Existing equipment level and pre-forge level | Native pool inspected read only; level 16/pre-forge 8 proves distinct values. Controlled upgrade/forge pairs and derived/equipped behavior needed before writes |
| Existing equipment reinforcement | Native pool and source-backed `+0x0A` inspected read only. Controlled upgrade pairs, category-specific limits and derived-stat/equipped dependencies remain required before writes |
| Affix IDs/values and fixed/inherited/star metadata | Source descriptions exist; effect limits depend on category and game build, and external catalogs/asset-derived data are not incorporated. Needs qualified native pool plus factual independent category limits |
| Existing scroll fields, attempts and seeds | No source-described owned scroll qualifies in either acquired file; fixed pool `0x176CCE` does not prove ownership. Need an owned-scroll native copy, native pool/type boundaries, and controlled attempt/reward/reveal/equip changes |
| Equipment/consumable/storage pool boundaries | Actual tags, both lengths, strides and adjacent boundaries qualify the two explicit profiles above; published addresses do not |
| Familiarity/proficiency | Published `+0x14` interpretations conflict, including account/context and familiarity readings. Labelled single-action pairs and authoritative field semantics remain required |
| Appearance, equipped flags/references and ownership | Separate from numeric equipment stats. Need controlled appearance/equip/acquisition pairs and validation of cross references |
| Spirits and companions | No ownership/progression mapping qualifies; need native acquisition/equip/upgrade pairs and prerequisite/reward transitions |
| Level, EXP, skills/proficiency, story, missions and collections | No independently qualified native disk maps or reward transitions established; level/stat changes alone would not model these dependencies |

The unregistered inspector still accepts qualified USER copies for inspection,
returns an unchanged copy byte for byte and rejects every gameplay edit. Both it
and the registered adapter reject SYS data, unobserved revisions, inconsistent inner revision/lengths,
truncation, oversized input, corrupted covered bodies and forged snapshots.

## Source and licence provenance

Only independently authored factual implementations are contributed. No GPL or
PolyForm implementation, catalog, extracted game data, player save or account
identifier is included in this project's public source/runtime packages.

- [alfizari/Nioh-3-Save-Editor](https://github.com/alfizari/Nioh-3-Save-Editor/tree/b5d0789791fe31d06ad325d4012aa0333c60cd8f),
  commit `b5d0789791fe31d06ad325d4012aa0333c60cd8f`, Apache-2.0: two native user
  copies, matching encrypted/decrypted pair, envelope/body-checksum observations
  and inventory/stat mapping leads. Third-party executables were not executed.
  Historical Apache commit
  [`4be2f62ddad3631dc931c675b527bb4124802c4e`](https://github.com/alfizari/Nioh-3-Save-Editor/blob/4be2f62ddad3631dc931c675b527bb4124802c4e/main.py)
  independently corroborates the exact acquired inventory bases and u64
  Amrita/Gold fields; its published 393-storehouse-record claim is superseded by
  the native array's proved 400-record byte count.
- [Master-Bayesian/Nioh3-Scroll-Generator](https://github.com/Master-Bayesian/Nioh3-Scroll-Generator/tree/4e2ec6d3e9640ba11e821adc7b037d793a112448),
  commit `4e2ec6d3e9640ba11e821adc7b037d793a112448`, GPL-3.0: independently
  corroborating native USER checksum, scroll semantics and version-scoped maps.
- [lylarcher/Nioh3EquipmentAffixEditor](https://github.com/lylarcher/Nioh3EquipmentAffixEditor/tree/2409a4fdb9fbf948f65d3958ec94c2b31d5b5404),
  commit `2409a4fdb9fbf948f65d3958ec94c2b31d5b5404`, PolyForm Noncommercial:
  documented moved/variable inventory layouts, reinforcement observations and
  fixed-affix dependencies. No code or datasets are reused.
- [mi5hmash/KatanaSaveDataResigner](https://github.com/mi5hmash/KatanaSaveDataResigner),
  MIT: custom-cipher family comparison. Its Nioh 3 reference pair is SYS data,
  not a player USER fixture. Ronin and Fatal Frame II fixtures are labelled
  dummies, so those do not establish another gameplay editor.
- [Nioh 3 official manual](https://www.gamecity.ne.jp/manual/nioh3/eng/5100.html)
  and [official updates](https://teamninja-studio.com/nioh3/us/update/): shrine
  blessings and restocking have game-specific dependencies; no other Nioh
  edition's capacities or serialized schema is transplanted.
  [Making Progress](https://www.gamecity.ne.jp/manual/nioh3/eng/4100.html) and
  [Exploration and Growth](https://www.gamecity.ne.jp/manual/nioh3/eng/9200.html)
  distinguish held/spent Amrita, grave recovery and character progression.

`tests/test_nioh3_native.py` retains independent signed-boundary vectors and
no-write inspector regressions. `tests/test_nioh3_format.py` covers generated
revision/tag/length boundaries, unknown/empty/nonordinary records, duplicate IDs,
unusual u16/u64 originals, malformed pending maps/snapshots, surgical edits, seeds/tail,
shared scalar contracts, source changes during serialization/backup and validated
backup/restore. [Expansion tests](../tests/test_nioh3_expansion.py) additionally
cover all eleven new identities in both pools/revisions, native eligible
reductions and the actual Tk control workflow. Optional locally held native
copies are selected using `NIOH3_NATIVE_DIR`; the pair uses `NIOH3_ENCRYPTED_COPY` and
`NIOH3_DECRYPTED_COPY`. Shared GUI workflows in `tests/test_team_ninja_gui.py`
exercise opening copies, field editing, Undo, Review Changes, themes, new-copy
saving and backup restoration, with optional native `NIOH3_SAVE_COPY` input.
Native qualification and unchanged roundtrips do not
constitute actual Windows game-load/re-save validation, which remains unperformed.

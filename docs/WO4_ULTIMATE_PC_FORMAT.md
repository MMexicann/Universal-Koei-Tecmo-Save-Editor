# Warriors Orochi 4 Ultimate — Windows PC

The `wo4_ultimate` adapter opens a separate native `SAVEDATAU.BIN` copy with
system revision **20200101**. The original WO4 revision is a separate adapter.
It provides spendable Gems, Crystals, Growth Points, progressed officers’
unspent Skill Points, promoted officers’ unspent Upgrade Stones, reductions of
existing Skill Orbs and existing ordinary attribute-element quantities.
Searchable inspectors show balances versus earnings, officer progression,
attribute inventory and existing weapon records.

## Native codec and identity

The supplied Ultimate gameplay DLL was inspected statically, never executed.
Its AES-CBC writer at RVA `511930`, reader `512310`, key selector `511080` and
native save dispatcher prove two encrypted blocks in a 927,576-byte file:

| Block | File offset | Container size | Payload size | Key index |
|---|---:|---:|---:|---:|
| System | `0` | `0x6E734` | `0x6E714` | 1 |
| Gameplay | `0x6E734` | `0x74024` | `0x7400F` | 0 |

Each block ends in an unencrypted 32-bit seed. The decrypted buffer contains
its payload, original alignment bytes and the 16-byte `FingerPrint01234` marker.
Keys are generated from ten ordered `(3.66*x)*(1-x)` binary64 recurrences,
starting at `(key_index+1)*0.5*0.5`, followed by the native LCG. The common
`wo4.codec` implementation preserves each seed and padding exactly.
No Steam account input is required by this recovered envelope.

Native header serializer `207AF0` emits three DWORDs and four bytes. The
Ultimate initializer `207BA0` supplies revision 20200101; the parser requires
that exact revision, rather than trusting a filename. Writer `209310` and
reader `209470` dispatch the header, actual system vtable `D18BD0` and gameplay
vtable `D18C08`; their serializers `23CD60` and `23C9B0` emit the complete
payload tree. The separate `naga` classes handle the original-game layout and
are not substituted for Ultimate.

The complete serializer uses scalar endian writes, fixed raw arrays, and
reserved regions; no native whole-payload checksum is emitted. The terminal
AES marker is **not** a checksum. The backend accurately declares integrity
`none`; it validates both encrypted markers, exact geometry, edition revision
and both explicitly zero-emitted reserved regions (`0x6051E` system bytes and
`0xF000` gameplay bytes). Arbitrary corruption of another unknown payload byte
cannot be detected by the AES marker. Damaged input is never repaired.

## Qualified field mappings

Offsets below are relative to the decrypted system block. They are calculated
from the header (16 bytes), system options (112 bytes), two player-option
records (148 bytes each), then the story/resource component at `0x1A8`.
The Ultimate component serializer is `22E560`; the scalar widths and ordered
arrays come from its actual writer calls, not a runtime-offset transplant.

| Mechanic | Packed offset/width | Natural cap / action | Proof |
|---|---|---|---|
| Spendable Gems | `0x274`, 4 bytes | 9,999,999 | `213160` available balance; its optional positive-grant branch separately updates lifetime `0x278` |
| Spendable Crystals | `0x27C`, 2 bytes | 999 | `213370`; separate optional lifetime partner `0x27E`; Deluxe reward `2193A0` |
| Growth Points | `0x280`, 4 bytes | 99,999,999 | `213310`; training `465170` spends this pool through officer level-up `20DF90`; Deluxe reward `2193A0` |
| Existing attribute quantities | `0x28E + 2*ID`, 2 bytes | 1–9,999 | 64-entry serializer; update `213240` bounds indices/caps quantities and separately marks acquisition |
| Existing Skill Orbs | `0x30E`, 2 bytes | Reduce only, no Max | `20F26E` consumes one from component `+166` while granting officer Skill Points; full natural grant cap remains unqualified |

The official Deluxe product description independently identifies the exact
300,000 Growth Points and 100 Crystals native reward branch. Gems purchase and
fusion spending distinguish available currency from accumulation/history.
Lifetime counters, acquisition flags, reward claims and story completion do
not change with resource edits.

Only positive ordinary attribute stacks with IDs 1–63 and quantities at or
below 9,999 become writable. ID 0, unowned/zero stacks and unusual quantities
remain read only. Publicly verified names/order have not been recovered, so
the interface uses explicit numeric IDs and never invents names.

Gameplay starts with 200 officer records of **780 (`0x30C`) packed bytes**, then
8,032 weapon records of 31 bytes at `0x26160`; three training records of 373
bytes start `0x62E00`, followed by 200 challenge records of 38 bytes at `0x6325F`.
They end at `0x6500F` before the reserved bytes. These are actual serialized
counts; the 32 extra weapon records are preserved.

Officer writer `232D70` and copy routines `2490B0`/`24A2F0` prove the following:

| Field | Packed officer offset | Natural cap / qualification |
|---|---|---|
| EXP — inspection | `0`, 4 bytes | Level-up `20DF90` also grants Skill Points and, after promotion, Upgrade Stones; no EXP writes |
| Unspent Skill Points | `0x14`, 2 bytes | 999; `20E820` grants/spends; `20EB3F` spends the skill cost before setting a learned-skill bit |
| Promotions — inspection | `0x10D`, 1 byte | Native 0–9; promotion/reset dependencies are not bypassed |
| Unspent Upgrade Stones | `0x10E`, 2 bytes | 9,999; `20F9C0` updates only this pool; promoted existing officers only |

Skill Point editing requires an already progressed record (positive ordinary
EXP at or below 999,999 and ordinary promotion count). Upgrade Stones also
require a nonzero existing promotion. Empty reserved and unknown-growth records
stay read only. Existing higher pool values remain unchanged by Max, and
assigning the original value unstages an edit even when it is unusual.

Upgrade Stone reset `20F7A0` refunds four separate allocation words and clears
them; spending `20FE8D` and its sibling paths deducts stones while increasing
allocations. Pool edits preserve all allocated stats and do not perform either
operation. Skill Orbs, Skill Points, Growth Points, EXP and Upgrade Stones are
distinct mechanics in the editor.

Weapon writer `230E40` proves two initial words and ten attribute ID bytes plus
ten rank bytes per record. The inspector shows stored ID/rank pairs without
assuming display encoding or granting new weapons, sockets, ranks or ownership.

## Mechanics and coverage

| System | Coverage / remaining blocker |
|---|---|
| Gems, Crystals, Growth Points | Writable balances; lifetime earnings separate/read only |
| Officer Skill Points | Writable existing progressed records; learned-skill bits preserved |
| Upgrade Stones | Writable unspent pool for existing promoted officers; allocation words preserved |
| Skill Orbs | Existing pool reductions; full grant bound remains missing |
| Attribute-element inventory | Existing ordinary quantities and validated Max; names/order not proved |
| Levels/EXP, promotions, allocated stats | Inspect EXP/promotions; level-up/reset and reward dependencies block writes |
| Weapons, attached attributes, fusion, compatibility, sockets | Searchable native inspector; display rank encoding, camp-derived limits, acquisition and equipped references block writes |
| Skills/camp rewards, bonds, training rewards | Their flag, prerequisite and reward dependencies need complete semantic maps |
| Sacred treasures, mounts, DLC costumes/entitlements | Exact ownership/eligible-record and reward maps missing |
| Story, side-story, difficulty, ranks, objectives | Completion/reward dependencies remain unproved; no completion actions |
| Infinity towers, allies, crafting/materials, fragments | Separate Ultimate structures require semantic/resource identity maps; story roster cannot substitute |
| Gallery, music, movies, collections | Separate unlock/viewing flag mapping and reward dependencies missing |

Authoritative mechanics references:

- [Official Upgrades manual](https://www.koeitecmoamerica.com/manual/wo4u/en/4300.html): Skill Points from level-up/Skill Orbs, shared Growth Points, level-100 promotion up to nine times, Upgrade Stones and reset/allocation behavior.
- [Official Weapons manual](https://www.koeitecmoamerica.com/manual/wo4u/en/4400.html): attribute inventory cap 9,999, Gems/Crystals fusion, compatibility, sockets and weapon rarity.
- [Official Infinity Mode manual](https://www.koeitecmoamerica.com/manual/wo4u/en/8100.html): separate ally roster and reset behavior; materials and crafted weapons survive a reset.
- [Official product description](https://www.koeitecmoamerica.com/wo4u/product/): independent Deluxe Growth Point/Crystal reward identification.
- [Public native save lead](https://savegame.pro/pc-warriors-orochi-4-ultimate-savegame/): independently shared native files; page labels alone do not establish edition.
- [zmod runtime research](https://github.com/Fragonite/zmod), commit `81dfd576e46037c85fcbc5892304863d45dee772`: promotion/derived-level distinction, corroborated against the native serializer; no runtime offsets used as disk offsets.

## Validation

The supplied genuine Ultimate revision-20200101 copy qualifies this profile.
Independently shared public files decrypt but carry revision 20191201 or the
original revision 20180720; they do not qualify this newer writer profile.
Revision 20191201 needs separate version-sensitive serializer qualification.
Private native files are used only for local qualification. Player files, identifiers and attached DLLs are not
committed or distributed. Tests separately label procedural data.
Checks cover exact unchanged ciphertext roundtrips, every exposed field's
surgical decrypted-byte change, original seeds/padding, preserved histories,
learned skills/allocations/promotion dependencies, higher/unknown preservation,
foreign-original revision rejection, bad markers/reserved regions, immutable
snapshots, natural bounds, source-change races, backups/restore and actual Tk
Open/Stage/Undo/Review/Save As workflows. Edited game-load/re-save testing has
not been performed by this project.

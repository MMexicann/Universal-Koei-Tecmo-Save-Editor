# Warriors Orochi 4 — original Windows PC

The `wo4_pc` adapter opens separate `.bin` copies of the original Windows game's
927,576-byte combined save. It edits Gems, Crystals, Growth Points and existing
ordinary weapon-element quantities and progressed officers' Skill Points;
existing ordinary Skill Orbs support reductions. Searchable views show resource histories,
all 64 element quantity words, 200 officer records and 8,032 weapon records.
Ultimate has a different system revision and a separate adapter.

Implementation: [codec](../src/koei_editor/games/wo4/codec.py),
[parser](../src/koei_editor/games/wo4/parser.py),
[presentation](../src/koei_editor/games/wo4/editor.py),
[checks](../tests/test_wo4_pc.py).

## Evidence and identity

The supplied matching original gameplay DLL was inspected as a PE file and
disassembled statically. It was never executed. The supplied native save was
decrypted, reconstructed through the recovered writer and compared byte for
byte. No binary, player save, extracted catalog, account context or private
path is included in the repository. This implementation independently expresses
format facts; it does not import another project's editor or game code.

All code addresses below are original DLL RVAs, not Ultimate addresses. The
initializer at `0x1BDEE0` installs the actual system/play vtables and writes
revision `20180720`. Header serializer `0x1BDE30` emits three little-endian
DWORDs and four uninterpreted bytes; the native loader also compares this
revision at `0x298E81`. Root pack/unpack `0x1BF3E0`/`0x1BF540` walk one system
object and exactly one play object. The root initializer writes the revision as
a QWORD, establishing the following zero word; the acquired native header is
`(20180720, 0, 0)`.

The adapter deliberately supports only that exact revision and header-word
combination. It preserves the final four header bytes. It does not infer that
the two zero words are independently writable fields or claim that another
combination is invalid for every native revision. Other header combinations
require a matching native file and loader-state qualification. Ultimate's
`20200101` revision is rejected rather than retried as original WO4.

## Native envelope and serializer

The complete file is two AES-128-CBC blocks followed individually by an
unencrypted four-byte IV seed:

| Component | Plaintext bytes | Encrypted span plus seed | File start |
| --- | ---: | ---: | ---: |
| System | `0x6E714` | `0x6E734` | `0` |
| Gameplay | `0x7400F` | `0x74024` | `0x6E734` |

Each decrypted span ends in `FingerPrint01234`, preceded by 12 system padding
bytes or one gameplay padding byte. These bytes and original IV seeds are
preserved, including nonzero padding. Original encrypt/decrypt wrappers are
`0x451B30`/`0x452510`; fingerprint store/compare are `0x451B74`/`0x452573`.
The gameplay and system key indices are respectively zero and one.

At `0x451280`, initialize a binary64 value with `(index + 1) * 0.5 * 0.5`, then
perform ten ordered iterations `(3.66 * value) * (1.0 - value)`. The low DWORD
of the resulting binary64 bit pattern seeds the key generator. This operation
order matters: it differs from the previously investigated All Stars seed.
Key bytes use the upper byte after each `state * 0x343FD + 0x269EC3`; IV bytes
use bits 16–23 after each `state * 0x15A4E35 + 1`. Arithmetic wraps at 32 bits.
Neither owner IDs nor the Steam sidecar are inputs to this original cipher.

The fingerprint checks the native end marker, not general data integrity.
Changing a CBC block away from the marker can pass it; changing the IV seed
also changes the first plaintext block without changing the marker. Accordingly
the adapter reports `INTEGRITY_KIND = None`, and never describes this marker as
a payload checksum or silently repairs a damaged file.

Native vtable serializers are system `0x1E48B0` and play `0x1E4510`.
Their full call trees resolve to endian scalars, fixed arrays and raw byte
copies; there is no additional native payload hash/checksum operation. The
root packer zeroes its output buffer and calls these same serializers. System
components are 112 configuration bytes, two 148-byte player option records,
global progression, gallery and the final system component, followed by
`0x6051E` reserved bytes. Global progression begins at packed `0x1A8`.

| Gameplay component | Count | Packed stride | Start | Native serializer |
| --- | ---: | ---: | ---: | --- |
| Officers | 200 | `0x30C` | `0` | `0x1DCCF0` |
| Weapons | 8,032 | `0x1F` | `0x26160` | `0x1DAF70` |
| Training records | 3 | `0x175` | `0x62E00` | `0x1E1220` |
| Challenge records | 200 | `0x26` | `0x6325F` | `0x1D83C0` |
| Reserved bytes | — | — | `0x6500F` | raw `0xF000` bytes |

These packed strides differ from runtime object strides. The complete geometry
ends exactly at `0x7400F`; the writer preserves every opened unknown byte rather
than normalizing the native reserved spans.

## Writable fields and mechanics

Offsets below are in the concatenated plaintext, starting with the system.
The global component serializer `0x1D9250` correlates the packed fields with
native runtime accesses. The official original manual distinguishes
[camp upgrades and Growth Points](https://www.koeitecmoamerica.com/manual/wo4/4300.html),
[weapon fusion, element quantities and weapon sales](https://www.koeitecmoamerica.com/manual/wo4/4400.html),
and [result rewards](https://www.koeitecmoamerica.com/manual/wo4/4900.html).

| Field | Offset / encoding | Qualified natural limit and native evidence |
| --- | --- | --- |
| Spendable Gems | `0x274`, u32 LE | 9,999,999; setter `0x1C5D80` clamps global `+0xCC`. Positive grants optionally update separate history `+0xD0`. |
| Spendable Crystals | `0x27C`, u16 LE | 999; setter `0x1C5F90` clamps global `+0xD4`. Positive grants optionally update separate history `+0xD6`. |
| Shared Growth Points | `0x280`, u32 LE | **999,999**, independently recovered at original `0x1C5F30`, global `+0xD8`. Ultimate's separately recovered `0x213310` setter caps this resource at 99,999,999; that limit does not apply to original WO4. |
| Existing ordinary element quantities | `0x28E + ID*2`, u16 LE, IDs 0–63 | 999; original `0x1C5E60` caps global `+0xE6 + ID*2` and positive acquisition also touches discovery bits at `+0x541C`. The original official manual independently gives the 999 inventory limit. |
| Officer Skill Points | Gameplay start plus `ID*0x30C + 20`, u8, IDs 0–199 | 99; original setter `0x1C2F70` writes live officer byte `+0x74`. The live object embeds its save record at `+0x60` (`0x1DD1A0`), and `0x1DCCF0` emits relative `+0x14` as packed byte `+20`. |
| Existing Skill Orbs | `0x30E`, u16 LE | Reductions 0–opened only, for an existing opened ordinary balance of 1–999; no Max. Original `0x1C37F0` checks global `+0x166`, converts an orb through the officer point setter and decrements this separate word. `0x1D93B5` serializes that word immediately after the 64 element words. |

The three resources support Max with their separately recovered natural caps;
Max preserves higher opened balances and unusual originals. Elements are
exposed only when their opened quantity is 1–999, remain 1–999 during edits and
are excluded from Max. Empty/unusual quantities stay intact. Editing a quantity
does not acquire an element, change discovery flags, equip it, perform fusion
or mark a camp prerequisite/reward complete. Numeric element IDs are retained
until an independently verified native name order is available.

Officer point controls are limited to existing records with stored EXP 1–999,999.
The original EXP path at `0x1C2885` correlates the first save DWORD with the
live record `+0x60` and clamps it to 999,999. This provides a deliberately narrow
progressed-record gate; it does not unlock a character or infer the full
roster/unlock status. Zero or unusual EXP records remain inspection only.
Point fields support 0–99 and Max, preserving unusual higher opened byte values,
including when a smaller edit was pending. The original skill-purchase path
`0x1C3210` checks the pool, debits a skill-specific cost through `0x1C2F70`, then
sets separate learned bits at `+0x64` and applies derived consequences through
`0x1C4390`. Those bits/consequences are not part of a pool edit. Skill Orbs and
Skill Points are distinct fields; adjusting one does not consume or grant the
other, learn skills or change reward histories.

Earned Gem/Crystal histories at `0x278`/`0x27E` are inspected separately and
never written. The genuine file demonstrates that available resources cannot
be assumed bounded by these historical counters. Growth Points are shared
training resources, distinct from officer EXP and Skill Points. Base-game
party composition is three playable officers, four support officers and a
mount; support bonuses in groups of five are derived from Power/Technique/Speed.
These mechanics are not transplanted from Ultimate's additional systems.

## Coverage checklist

| Mechanic | Implemented scope or precise remaining blocker |
| --- | --- |
| Native encryption/revision | Implemented complete two-block reader/writer and exact original revision gate; matching DLL and owner context are no longer missing. Other header variants need native qualification. |
| Gems, Crystals and Growth Points | Implemented bounded individual and bulk actions; histories/prerequisites remain separate. |
| Weapon-element inventory | Existing ordinary quantities editable; all 64 stored words searchable. Discovery and unknown/higher words preserved. Native ID/name order still needs verified game-data correlation. |
| Officer EXP/levels | Searchable 200 native records: serialized EXP; level is not inferred from EXP or another stored field. Safe writes need native level/EXP reconciliation and controlled gameplay pairs. |
| Skill Points, Skill Orbs and learned skills | Implemented progressed-record Skill Point controls 0–99 and existing ordinary Skill Orb reductions; original setter/serializer and independent cost/conversion paths proved. Learned skills, prerequisites, derived consequences and reward grants remain unchanged. Their safe write dependencies require controlled skill/unlock pairs. The adjacent packed DWORD `+21` remains unlabeled. Ultimate's different width/cap do not apply. |
| Weapons, compatibility, attack, attributes and fusion | All 8,032 raw records searchable. Native packed geometry is proved; record ownership, empty markers, equipped references, human names and compatibility/derived-attack dependencies need verified mappings before writes. |
| Camp upgrades, rewards, unlocks and stages | Resource controls do not complete these actions. Native flags and prerequisite/reward dependencies require matched progression comparisons and setter evidence. |
| Bonds and support officers | Separate pair records, bond rewards and support-derived effects need native ownership/threshold maps. No blanket unlock or bond writer. |
| Mounts, costumes and customization | Existing raw bytes preserved; catalog identity, ownership and equipped dependencies require native data correlation and before/after controls. |
| Challenges, training slots and collections | Exact fixed native serializer geometry recovered; individual meanings, campaign ownership and reward counters need controlled changes before writes. |
| Story completion and gallery/music/movies | No resource action alters story/gallery progression. Unlock flags and associated rewards need independent native maps. |
| Ultimate-only mechanics | Promotion, Infinity Mode and sacred-treasure switching are outside this original profile. |

## Validation

The focused suite checks independently constructed non-playable containers,
ordered binary64 key derivation, actual full encode/decode reconstruction,
nonzero seed/padding preservation, actual byte counts (including typed
memoryviews), truncated/oversized input, wrong revisions/header states and
fingerprint corruption. It explicitly tests the marker's inability to detect
unrelated CBC corruption rather than claiming a checksum exists.

The genuine supplied original file passes a true byte-exact codec roundtrip,
229 qualified fields (three balances, 55 existing elements, 170 progressed
officer Skill Point pools and one existing Skill Orb pool), surgical plaintext
comparisons, unchanged histories, seeds and padding. Resource-only edits also
preserve the complete original gameplay ciphertext; Skill Point edits touch
only their mapped individual gameplay bytes and no learned flags/EXP/equipment.
Synthetic and genuine records are distinguished in tests. Actual Tk checks
exercise native opening, searches, inspectors, staging, Undo, Review Changes,
theme switching, Save As, automatic backup and restore. Storage checks cover
changed sources, forged snapshots, corrupted backup manifests/content, live
folder aliases and atomic writes to new destinations.

`WO4_PC_SAVE_COPY` optionally supplies the genuine private native file to
`python -m unittest tests.test_wo4_pc -v`. Genuine-file qualification is true;
edited-save acceptance inside the game and an in-game re-save have **not** been
performed. Those remain separate from the passing native writer and GUI checks.

# Dynasty Warriors 6 — original US PS3

The `dw6_ps3` adapter opens copied **PFD-decrypted** original US
`BLUS30110-SAVEDATA/APP.BIN`, exactly **212,240 bytes**, with its unchanged
original `PARAM.SFO`. It edits named one-way playable officer unlocks, qualified existing horse combat
stats and weapon stored damage bonuses/elements, named weapon/horse skills, horse elements and existing same-officer weapon selection, with searchable named records. Shared staging, Undo, Review Changes,
experimental numeric limits, automatic backups, restore and verified new-copy
Save As apply. Max is disabled for this profile.

## Native proof and sources

- [Apollo BLUS30110 patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30110.savepatch)
  specifies four-byte horse writes beginning `0x29F0`, eight rows with stride
  `0x3C`, and eight weapon slots per officer with officer stride `0xA8`.
  Its weapon power byte at `0xB27` is the low byte of the big-endian stored bonus
  word at `0xB24`; element writes at `0xB2A` occupy the low half of the word
  at `0xB28`. This adapter writes the independently corroborated complete words.
- [GameFAQs US export 34847](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/34847)
  and [separate US export 16788](https://gamefaqs.gamespot.com/ps3/942167-dynasty-warriors-6/saves/16788)
  supply two native player-derived exports with original metadata. Both were
  decrypted and qualified privately. They can already contain modified values;
  they do not establish natural gameplay caps.
- [cnopt's original DW6 research](https://github.com/cnopt/dynastywarriors6-reverse-engineering)
  establishes the independently implemented PC record semantics and elemental
  enum. PS3 uses the corroborated record strides and typed values at a different
  starting offset and byte order. The existing reviewed weapon-ID inventory
  gates known entries; IDs and names are not rewritten.

No GPL patch code/catalog or unlicensed upstream implementation is copied.
Player saves, PFDs, keys, metadata and external source files remain private and
outside source/release assets. The new implementation reuses this project's
scalar contract and safe storage.

Every read validates exact size and all 41 canonical **big-endian** officer IDs
0–40 at `0xB18 + index*0xA8 + 136`; original title identity comes from the bounded
original companion. PC, encrypted exports, Japanese profiles, Empires, Special
and other lengths/layouts are rejected. The playable byte at +164 is `01` followed by three zero bytes in both original
US exports, while the preceding numeric words are big endian. It is not a u32
flag. One-way writes preserve all three opaque neighbors; unknown byte values
remain read only. Public PC unlock/reload evidence and native PS3 framing
corroborate this narrow control. No independently established native
gameplay checksum is claimed. The published patch writes these exported words
directly; external PS3 PFD authentication must be rebuilt by the save manager.
Structural qualification does not detect arbitrary corruption of opaque bytes.

## Controls and preservation

| System | Native field and implemented scope |
| --- | --- |
| Horses | Eight rows, base `0x29E0`, stride `0x3C`; speed +16, attack +24, jump +28, destruction +32, unsigned big-endian u32. Occupancy requires observed type 60–64, positive +20 and four positive stats. Individual 0–500 normal editing bounds; these are not independently tested native caps. Higher opened values stay unchanged. |
| Adjacent horse value | +20 is deliberately read-only; the patch's fifth numeric target does not independently name its mechanic. EXP, type, descriptors and names are unchanged. Element/skill controls are separately qualified. |
| Existing weapons | Eight slots per officer, base `0xB20 + officer*0xA8`, stride `0x10`: ID +0, stored damage bonus +4, element +8, skill mask +12. Only existing known IDs with element 0–3 qualify. Empty ID 174 and unknown IDs/elements are excluded. |
| Weapon bonus | Manual u32 bonus control, normal conservative editing bound 0–100 following the source target. This is not total attack or an independently verified natural cap. Experimental mode permits the exact unsigned encoding range; Max stays disabled. |
| Weapon element | 0 Fire, 1 Ice, 2 Lightning, 3 no element. Hard choice constraints apply in both modes; identity, bonus, mask and neighboring entries remain unchanged. |
| Weapon skills | Ten independently corroborated bits at weapon +12: Air Wave, Mystic Seal, True Musou, Leech, Concentration, Balance, Berserk, Renbu Spirit, Arrow Sight and Flash (bits 0–9). Individual toggles preserve neighboring bits. The complete resulting mask allows at most five skills. Unknown bits or over-capacity originals stay read only; Max disabled. |
| Horse skills | Eleven bits at horse EXP-base +12: Arrow Dance, Find Saddle, Find Weapon, Musou Spirit, Renbu Gait, Winged Hoof, Jagged Hoof, Steel Hoof, Water Spirit, Stone Spirit and Wind Spirit (bits 0–10). Same qualified occupancy as horse stats; at most four skills. Unknown/over-capacity originals stay read only. Horse growth/EXP is preserved; these are equipment effects, separate from the officer skill tree. |
| Horse element | Qualified occupied horse EXP-base +8, four-byte choice: Fire/Ice/Lightning/None = 0/1/2/3. Unknown original choices remain read only. |
| Equipped weapon | Officer +160 u32, zero-based index 0–7. Choices list only this officer's existing known-ID/known-element weapon slots; the opened index must also qualify. Empty and unknown records cannot be equipped or manufactured. |
| Officers | Named stored level, EXP, kills, title, outfit, equipped slot and 64-bit skill-mask inspection; level/EXP/learned-tree progression remains read only. One-way playable-byte unlocks at +164 preserve all other bytes and are excluded from Max. |
| Story, acquisition and rewards | Preserved. Playable unlocks are a separate content action; they do not mark story completion or grant skill nodes. |
| Regional/platform scope | US BLUS30110 only. A separately inspected Japanese BLJM60041 export has a different length and is not accepted. PC/US PS3 roster-and-horse migration is offered separately; [its scope](DW6_CONVERSION.md) preserves destination story/battle state. |

Writes change only the requested native field spans. The full original
`PARAM.SFO` digest is bound to opening, backups, output and restore. Same-title
metadata with changed opaque bytes is refused. Backup context manifests bind
both save and metadata hashes; restore reparses the exact bounded bytes written.
Assigning an unusual opened value remains an exact no-op/unstage.

## Validation

`test_dw6_ps3.py` includes the shared scalar contract, all-field surgical
big-endian writes, foreign size/endianness/context, unknown/empty exclusion,
experimental boundaries, higher originals, backup/context races, forged
restore and copied CLI self-test. `test_conversion_gui.py` opens the registered
DW6 PS3 editor and verifies its staged values survive converter navigation.
`DW6_PS3_SAVE_COPIES` optionally supplies separate reviewed US native copies,
separated by the host platform's path separator.

Both separately acquired US copies passed no-edit roundtrips, every exposed
field's surgical byte comparison, new-copy editing with actual read-back and
opaque companion preservation. Actual PS3 game loading/re-saving after editing
has not been performed; export/reimport/resigning remain external.

## v2.4 equipment qualification

[cnopt's disk research](https://github.com/cnopt/dynastywarriors6-reverse-engineering)
provides equipment-mask domains, positions and capacity evidence. Static inspection
of the older [DW6SaveGameEditor 0.1.0 archive](https://f.gvn.co/threads/pc-download-huong-dan-mod-ss4mspecial-dw4hyper-dw6-ssm6.1548988/)
independently corroborates bit ordinals and power-of-two decoding, plus the
stored selected-weapon index. Its code and enum catalog are not imported;
this project implements individual masked writes independently. Apollo's published
PS3 attribute writes occupy the low half of these same big-endian mask words.
The PC and both US PS3 exports have only known equipment bits and observed counts
within the five/four limits; existing identities, arrays and selected slots agree.

`test_dw6_equipment.py` uses asymmetric masks to check each named bit and the last
officer/weapon, complete pending-mask limits, remove-before-add, unknown originals,
invalid own-pool selections, hard bounds in experimental mode, exact source-byte
preservation and PC/PS3 semantic migration. Actual Tk workflows check named search,
choice controls, capacity errors without pending-map loss, Undo, Review, themes and
safe output. Native tests remove known equipment bits, reopen actual written
copies and retain all other bytes/context. They do not establish edited in-game
acceptance or qualify officer-level/skill-tree editing.

An older [editor-user report](https://gamefaqs.gamespot.com/boards/945966-dynasty-warriors-6/47751842)
describes a skill-screen lock after premature full officer-tree unlocks. This is
anecdotal game behavior, not a serialization map. Officer growth and learned-node
editing therefore remain separate, read only; migration copies their complete
existing relationship together.

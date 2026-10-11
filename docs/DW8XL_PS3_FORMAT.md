# Dynasty Warriors 8 Xtreme Legends — original US PS3 PSN

The separate `dw8xl_ps3` adapter accepts a copied, **PFD-decrypted** original
US PSN `NPUB31449-SAVEDATA/APP.BIN`, with its unchanged original `PARAM.SFO`
beside the copy. Apollo export/reimport and console `PARAM.PFD` authentication
remain external. PC saves, original-only DW8, Vita/PS4, disc releases and other
regions are not qualified by this adapter.

## Native framing and source evidence

The exact native file length is `0xB7F45` (753,477 bytes). The first `0xB7F44`
bytes use the byte XOR stream with starting state `0x13100200`; each byte advances
`state = (state * 0x41C64E6D + 0x3039) mod 2^32` and XORs bits 16–23.
The final byte stays outside this cipher and stores the sum of **all decoded
payload bytes**, modulo 256. The qualified five-byte plaintext signature is
`F0 02 10 13 09`. Every open checks the exact size, signature and complete native
checksum. Unchanged serialization returns the byte-exact original; an edit
recomputes the checksum, retains every unrelated byte and reparses the output.
The PC four-byte outer checksum/seed and word XOR layer do not apply here.

Published factual evidence:

- [Apollo NPUB31449 patches](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPUB31449.savepatch)
  explicitly specify the whole native byte cipher, final-byte sum and the
  resource, officer, aptitude and six weapon attribute-rank locations.
- [Apollo byte-cipher implementation](https://github.com/bucanero/apollo-lib/blob/main/source/decrypt.c)
  and [dedicated DW8 XL decrypter](https://github.com/bucanero/ps3-save-decrypters/tree/master/dw8xl-decrypter)
  independently corroborate the native stream and checksum behavior.
- [koko-tsuu's save converter](https://github.com/koko-tsuu/dw8xl_save_converter/tree/8ca795108a4f4f0bee91c55d3efce0c6da78515f)
  describes distinct PC/PS3/PS4/Vita framing and provides a complete PS3 codec
  reference. Its factual shared payload map corroborates relative record fields.
- [Apollo's public NPUB31449 player export](https://bucanero.github.io/apollo-saves/PS3/NPUB31449/)
  supplies a separate genuine console file and original metadata. Its console
  PFD wrapper was decoded privately for qualification; no player metadata,
  credentials, binary, account values or save files are distributed here.

Apollo projects are GPL licensed; no implementation source, patch database or
assets are imported. The converter has no declared project license in the
reviewed snapshot; it is used only for factual observations and its private
reference comparison. This project's independent adapter reuses the project's
existing scalar descriptors, mathematical cipher primitive, safe storage and
opaque PS3 context-handling code.

## Features and mechanics checklist

Offsets refer to the decoded gameplay payload; integers are little endian.
All controls are manual and excluded from Max. Published cheat targets are
editing bounds, not independent evidence of natural gameplay limits. Original
higher/unusual values are preserved, and assigning the opened value unstages.

| System | Implemented scope / remaining blocker |
| --- | --- |
| Gold | `0x105`, u32, 0–9,999,999. Current balance is separate from progression/history. |
| Gems | `0x1D43`, u16, 0–9,999, following the existing conservative resource bound. |
| Facility/weapon materials | `0x1F6D1` / `0x1F6D3`, u16, 0–9,999; two distinct balances. |
| Officer stats | 82 records, stride `0x48`; attack/defense at `0x7FD5`/`0x7FD7`, u16 0–1,500; health at `0x7FD9`, u16 0–1,000. Numbered slots avoid unqualified roster naming. Stored stats are separate from EXP and level-up rewards. |
| Four weapon-action compatibilities | Four bytes from `0x7FDB + officer*0x48`; only 25/50/75/100 are selectable (one through four stars). Dash, Dive, Shadow Sprint and Whirlwind are distinct from weapon affinity/elements. Original other encodings remain no-op safe. |
| Existing weapon attribute ranks | 1,830 physical entries, base `0xE715`, stride `0x18`; qualified states 1/3 with nonempty u16 identity at +2; six attribute IDs at +6 and six ranks at +12. Existing recognized ranked attributes with opened rank 1–10 allow manual 1–10 edits. Unknown IDs, zero/higher ranks, empty/unqualified states remain untouched. No attribute creation, weapon identity, power, affinity, ownership or equipped-reference writes. |
| Weapon/officer inspection | Searchable weapon IDs and existing attribute names/IDs/ranks; numbered officer stored-level/EXP and equipped-reference inspection. Only independently named attributes receive names; unknown identities remain numeric. |
| EXP/levels, leadership, skills, bodyguards and mounts | Inspect selected existing values without changing them. Natural thresholds, growth/reward dependencies and platform-specific record ownership need controlled native action pairs. |
| Campaign, stage, collection, unlock and DLC rewards | No writes. These remain separate from resources/stats; exact prerequisites, ownership and reward identities need independent qualification. |
| Other regions/platforms/revisions | Separate complete native files plus original metadata and integrity/layout evidence are needed; matching filenames or converter options alone do not qualify an editor. |

## Validation

`tests.test_dw8xl_ps3` covers exact no-op, foreign revision/length and checksum
corruption rejection, immutable snapshots, surgical scalar/rank byte ranges,
unusual values, compatibility choices, unknown/empty weapon exclusions, mandatory
exact metadata identity and digest binding, source changes, new-destination atomic
saving, backups/restore and real Tk Search/Apply/Review/Undo/Save workflows.

With the private genuine export and independent public converter reference
provided, **8/8 tests pass**. The genuine player export exposes 578 base fields;
every field's targeted payload write was independently confined to its declared
span, with complete encoded/reparsed edits for representative resource/officer
controls. That already edited export has no qualifying positive weapon ranks.
The separate source reference exposes 3,538 qualified existing rank fields;
every rank was individually checked for surgical payload writes, with twelve
representative complete cipher/checksum/reparse edits. Procedural tests additionally
cover unknown/zero/higher rank and unqualified-state exclusions. The two reference
classes are kept distinct; neither player's existing hacked values nor the
converter reference establishes natural gameplay maxima.

Optional private variables:
`DW8XL_PS3_SAVE_COPY` selects the PFD-decrypted original US PSN `.bin` copy with
its original `PARAM.SFO`; `DW8XL_PS3_REFERENCE_COPY` selects the separate published
converter PS3 reference. Three private-data tests skip explicitly without these
inputs. Actual edited PS3 game-load/re-save validation has not been performed.

# Persona 5 Strikers: observed encrypted PC English profile

The PC adapter handles complete PC `SAVEDATA.BIN` copies with decrypted version `0x20012000`, size `0x55DEA0`, ten serialized blocks and the observed zero trailer suffix. It does not convert Switch/PS4 saves or transfer account ownership. Two freely shared PC player saves qualify the framing, checksum and unchanged roundtrips. Neither the original authors' game-load claims nor a successful editor roundtrip constitutes our own game-load validation.

## Implemented controls

The nine player save slots have individual money, persona-point and unspent BOND-point controls. Reserved block 0 is preserved. A slot is editable only when its header differs from the empty `FFFF` sentinel and both bounded name fields contain nonempty, terminated, valid UTF-8 without control characters. Unknown name encodings and ambiguous/empty slots remain inspection only. Names and stream context are not returned by the inspector.

Thirty-four selected ordinary consumables and twenty cooking ingredients have named searchable stack controls when already present with a quantity byte of 1–99 and an untouched adjacent byte of zero. Examples include Medicine, Soul Drop, Leblanc Coffee/Curry, Salmon, Rice and Crab. Empty stacks, unusual higher quantities and nonzero adjacent bytes stay unchanged. Writes change the single mapped quantity byte; they never manufacture items, rewrite a neighboring quantity, unlock recipes or equip anything.

Forty additional selected mappings cover seven incenses, nine ailment remedies
and 24 elemental/healing skill cards, bringing the total to 94 selected stack
identities. They use the same occupied-slot, positive-quantity and zero-adjacent
byte qualification. Incense edits replenish supplies for later game use; they
do not apply stat changes. Skill-card edits do not teach a Persona or replace
learned/equipped skills. Exact selected mappings, independently checked sources,
native surgical checks and remaining dependencies are recorded in
[the expansion note](PERSONA_GUST_DEPTH.md).

All Max actions leave this game's fields unchanged. Money/persona-point edit ranges of 0–9,999,999, unspent BOND-point range 0–999 and ordinary stack range 1–99 are conservative manual editor limits, not verified natural caps. Existing higher resource balances can be inspected and preserved unchanged. Replenishing a cooking ingredient does not unlock its associated recipe.

The workspace retains the shared themes, Undo, Review Changes, new-destination saving, backup snapshots and verified restore. Both native player copies and procedural malformed inputs are tested without publishing their bytes or personal context.

Read-only character growth and held-Persona inspectors show ten named character level bytes and ten bounded held ID words per qualified slot. The independently transcribed character level byte starts at slot-relative `0x7F846` with stride `0x80`; the held-ID words start at `0x832CA` with stride 2 and omit `FFFF` empties. Both public player saves' level bytes agree with their advertised level-99 progress in the relevant slots. Neither inspector grants ownership, edits level/EXP, increases held capacity or treats a raw ID as a qualified fusion/skill mapping.

## Framing, cipher and integrity

The PC converter describes a `0x1C` header, ten slots of `0x88E36` bytes (`0x88DF4` base plus two 33-byte names), names at slot-relative `0x87842` and language/layout marker `0x0036EE7F` at relative `0x938`. Every block's marker is checked. The selected-slot signed DWORD at offset 4 must be −1 through 9. Unknown header, slot body and tail bytes remain byte-identical unless an explicitly staged field overlaps them.

The cipher advances the 32-bit LCG `1103515245 × state + 12345` before XORing each byte with bits 16–23 of the state. Only the first `size − 4` bytes are transformed. The original project's separately tested research primitive recovers a unique low-24-bit stream equivalence class from the four version bytes; this class cannot identify the original account. Ambiguous recovery is rejected. A recovered state is kept private within the frozen snapshot, omitted from its representation and retained for encrypted writes.

The first trailer byte is the sum of the **decrypted** preceding bytes modulo 256. This independently matches both complete public PC files and differs from their encrypted-byte sums. The final three bytes are zero in both observed profiles and other suffixes are rejected. This closes the earlier research-only checksum blocker: the upstream transform rewrote the checksum during both encryption and decryption and did not validate incoming files. Our decoder verifies the incoming plaintext checksum before exposing fields. After edits, only its byte is recalculated and the complete encrypted output is decoded again. A no-op returns the original encrypted bytes exactly.

An additive byte checksum detects ordinary accidental damage but permits arithmetic collisions; it is not an authenticity or cryptographic ownership proof. No stronger game checksum is claimed.

## Factual mapping sources and licensing

- [zarroboogs/p5spc.saveutil](https://github.com/zarroboogs/p5spc.saveutil/tree/2462a2043aba3bc551d2eb6b732a81d2374aa826), `SaveCrypt.cs`, `SaveConvert.cs` and its published encrypted/decrypted 32-byte screenshot: cipher, exact platform descriptors, names and slot framing. No repository license was identified; its code is not incorporated. The project's original stream implementation and screenshot test already existed.
- [Amuyea's Switch/English hex-edit discussion](https://gbatemp.net/threads/persona-5-strikers-hex-edit.584529/): gameplay identities, little-endian money/persona/BOND fields and related maps. The author explicitly distinguishes PC investigation from tested Switch support.
- [Published item/offset worksheet](https://docs.google.com/spreadsheets/d/1CeCiLDemo1cmc34Mg6WTs4Y4f-5yQsjWq2bGksaPktQ/edit): individually transcribed position/name facts for selected ordinary stacks, including the expansion's incenses, remedies and skill cards; its complete dataset is not bundled. Unknown IDs are excluded.
- [Amuyea-gbatemp/Persona-5-Strikers-Scramble-Save-Editor](https://github.com/Amuyea-gbatemp/Persona-5-Strikers-Scramble-Save-Editor/tree/7466afbb3c1bbcf550d4ff5c18e293103969e678): GPL-3.0 source at the expansion's checked commit, read as a corroborating factual reference only. No GPL code or cheat actions were copied. Its low-byte inventory reads and four-byte generic writer differ; our bounded writer preserves neighboring bytes.
- [Public PC player archives](https://savegame.pro/pc-persona-5-strikers-savegame/), attributed on the page to Zeal and Akahika: two complete encrypted PC saves downloaded separately. One advertises level 99 and the other completed compendium/BOND content; intentional modifications are possible. These are player-derived files, not unmodified gameplay cap evidence. All downloaded archives, player bytes and decoded copies stay outside source and release packaging.
- The later [English Switch qualification](P5STRIKERS_SWITCH_FORMAT.md) independently acquired two complete native exports from the public NX_Saves catalog and matched its own platform framing and Switch writer facts. It uses a separate plaintext Switch adapter; this PC adapter does not convert or open those exports. The older [Switch Yuzu thread](https://gbatemp.net/threads/persona-5-strikers-100-yuzu-save-data.683968/) remains a shortener-only source, separate from those acquired files.

## Coverage and remaining inputs

| Mechanic | Status / exact blocker |
| --- | --- |
| Money, persona points, unspent BOND points | Individual mapped writes; no verified natural-cap bulk action. |
| Consumables, cooking ingredients, incenses, remedies and skill cards | 94 selected named mappings, existing ordinary positive stacks only. Item use, stat application and skill teaching remain separate game actions. Other IDs need individual semantic/category qualification. |
| BOND levels, skill ranks, EXP and prerequisite requests | Preserved. Need EXP/rank tables and prerequisite/reward coupling; unspent points are distinct from earned level/EXP. |
| Character level, EXP, HP/SP and stats | Ten named level-byte records inspected read only; growth writes blocked. Published display fields do not prove growth curves, EXP consistency or acquired-character prerequisites. Need native transition pairs or static serializer/setter evidence. |
| Persona ownership, held slots, compendium, fusion, level/stats and eight-skill sets | Ten held ID words inspected read only; writes blocked. Need ownership/referenced-slot constraints, valid ID/skill applicability and EXP/stat dependencies. A maxed compendium player file does not establish those rules. |
| Weapons, armor, accessories and equipment | Preserved. Public inventory maps alone do not prove equipped references, required characters or special-item acquisition dependencies. |
| Recipes, requests, valuables, Jail/story completion, collections and NG+ | Preserved. Recipe ownership and story rewards must be qualified separately from ingredient/resource quantities. |
| Native PC revisions / language variants | Only the observed English marker/name layout and zero trailer suffix qualify. Need genuine copies and matching version/layout evidence for others. |
| English Nintendo Switch | Implemented separately in [its native Switch adapter](P5STRIKERS_SWITCH_FORMAT.md); this PC adapter still requires the encrypted PC format. |
| Japanese Switch / PS4 | Not implemented. Need independent complete exports with exact title/version/language, framing/integrity qualification and safe console import contract. |
| Actual game loading | Not performed. Need an owner-operated PC load of an edited copy and before/after in-game observation; do not treat automated codec/GUI checks as that test. |

Focused checks use optional private `P5S_PC_SAVE_COPIES` containing paths separated by the platform path separator. Public tests generate their own native-size procedural data. [Expansion tests](../tests/test_persona_gust_depth.py) cover the new stack selections, unusual/adjacent-byte rejection, surgical changes, growth/held-Persona preservation, native copies and actual Tk controls. No paths, names, account IDs or player data belong in published fixtures.

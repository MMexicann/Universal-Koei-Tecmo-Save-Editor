# Dynasty Warriors 8 Xtreme Legends Complete Edition — PlayStation Vita

The `dw8xl_vita` profile opens a copied, exported plaintext `MainData00.dat`
of exactly `0xB7F45` bytes. It supports the published gameplay layout beginning
`F0 02 10 13 09` (revision `0x131002F0`) and validates the final byte as the sum
of the preceding `0xB7F44` plaintext bytes modulo 256. PC outer encryption,
PS3 byte encryption, and the larger PS4 container are rejected. Export/import
and Vita filesystem authentication remain external; this editor changes no
owner metadata and performs no platform conversion.

## Source and qualification

[koko-tsuu's complete platform converter](https://github.com/koko-tsuu/dw8xl_save_converter/tree/8ca795108a4f4f0bee91c55d3efce0c6da78515f)
publishes an active PC/PS3-to-Vita writer and a complete Vita-format reference.
Its writer strips the four-byte PC wrapper, retains the plaintext gameplay
layout and native sum byte, and identifies Vita's exact size and signature.
The independent parser accepts that reference and validates its sum; the
project's independently established DW8 gameplay descriptors match the complete
conversion's unchanged plaintext layout. Factual resource, officer and weapon
locations are also corroborated by the
[published DW8 XL patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPUB31449.savepatch)
and the converter's exact cross-platform gameplay preservation.

The converter has no declared reuse licence in the examined revision. Its
implementation was not imported. This adapter independently implements the
plaintext trailer rule and reuses this project's scalar descriptors and safe
storage helpers. Public source/reference files remain outside the checkout.
The reference's provenance does not establish an independently acquired Vita
player campaign: this is a **published-format implementation**,
`sample_verified=False`, `game_load_verified=False`. Independent edited Vita
game-load and resave testing remains outstanding. No region-specific identity
or roster naming beyond the published revision is asserted.

## Editable scope

Gold (`0x105`, u32), gems (`0x1D43`, u16), two material balances (`0x1F6D1`
and `0x1F6D3`, u16), 82 stored officer attack/defense/health records (stride
`0x48`), and four weapon-action aptitudes are shared by the documented gameplay
layout. Aptitudes permit 25/50/75/100, representing one through four stars.
Existing qualified weapon entries (base `0xE715`, stride `0x18`, count 1830)
permit changes to already attached, recognized attribute ranks 1–10. Unknown
attributes, zero/higher ranks, unqualified states and empty identities remain
read only. Names and record ownership are not reconstructed.

All controls are manual, with Max disabled: published editing bounds are not
claimed natural gameplay caps. Original higher/unusual values remain untouched
and exact reassignment unstages them. Level/EXP, acquisition, equipment
references, story, DLC and reward histories are preserved. An edited file
changes only the requested field bytes and the final native sum byte; every
output is reparsed, and Save As reopens the actual destination through the
shared adapter.

## Checks

`tests/test_dw8xl_vita.py` covers exact unchanged bytes, checksum corruption,
foreign sizes/revisions/types, immutable snapshots, surgical edits, valid
aptitude choices, unknown/empty weapon exclusions, unusual originals,
new-destination backup/restore and a source race during backup. The optional
`DW8XL_VITA_REFERENCE_COPY` check validates the full source reference separately
from the procedural tests. Procedural bytes are not game-load evidence.

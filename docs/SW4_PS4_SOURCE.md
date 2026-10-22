# Original Samurai Warriors 4 PS4 → PC gold transfer

Development source adds `sw4_ps4-to-samurai4dx-ps4-gold`, a one-way transfer
from a restricted decrypted US CUSA00919 export to an existing SW4 DX PC save.
It replaces **gold only: one 32-bit balance, four mapped bytes**. It is not in
the published v3.1 Windows build and does not migrate full progression.

## Required copies

Use a separate decrypted original SW4 `app.dat` with its unchanged original
`sce_sys/param.sfo`, and a native current-revision SW4 DX PC `save.dat` template.
Console extraction/decryption remains external. Encrypted PFS images, other
PS4 regions, PS4 DX, SW4-II and Spirit of Sanada are excluded.

The source must be exactly `0xBB800` bytes, start with little-endian revision
`0x2118`, and contain the 55 consecutive standard officer identities at
`0xC1A + index * 0x44`. Original metadata must identify CUSA00919. The complete
metadata is preserved privately and checked before and after opening/backup;
account or signing fields are never synthesized or edited.

## Integrity and exact profile restriction

A supplied decrypted native export on 2026-10-22 independently established the
revision, length, record identities and four matching stored checksum cells at
`0x4`, `0xA8`, `0xC16` and **`0x80532`**, all little endian. This final location
differs from the independently qualified PS3 format's `0x58532`.

The first three checksums match the original SW4 section arithmetic. With
checksum cells zeroed, define byte sums:

| Sum | Half-open byte span |
| --- | --- |
| a | `[0x8, 0xA8)` |
| b | `[0xAC, 0x8EC)` |
| c | `[0xC1A, 0x78D6)` |
| d | `[0x85DE, 0x58532)` |
| e | `[0x78D6, 0x85DF)` |
| f | `[0x8, 0x78D6)` |

The expected cells are `((c+a)*b+e) & 0x7FFFFFFF`,
`(a*(c+b+d)) & 0x7FFFFFFF`, `f`, and the sum of those three masked to 31 bits.

**Every byte in `[0x85DE, 0x80532)` must be zero.** The available reference has
an entirely zero large section; it cannot distinguish a longer PS4 checksum
span from the PS3 span. A nonzero variant is rejected even when the known sums
match. This restriction avoids pretending the remaining coverage is proven.
The tail `[0x80536, 0xBB800)` is opaque and has no claimed checksum protection;
it is kept in the source snapshot/backup and never transplanted to PC.

## Gold mapping and destination preservation

The source balance is the unsigned little-endian word at `0x7842`. Its mapping
uses the separately established original SW4 resource location, exact shared
revision, matching original officer/weapon/resource section geometry and
matching section arithmetic. This is corroboration through the shared original
SW4 layout, not a recovered PS4 executable routine or a controlled gold-change
pair. Gameplay semantics and loading still require confirmation in-game.

The existing PC backend independently maps gold at decoded `0x7DA6` and supplies
its authoritative native writer. Every changed assignment must be within
0–999,999; incompatible values are rejected without clamping, including under
experimental policy. An exact unusual existing destination value remains an
unchanged no-op. Lower incoming balances replace higher ones.

The PC template's cipher seed, header, gems, standard/custom officers, weapons,
mounts, Chronicle, story, options and every other payload byte remain intact
except required native integrity cells. The complete PC envelope and section
checksums must pass before and after conversion. Gem type/order correspondence,
linked equipment, custom-character appearance/name migration, reward state and
full progression remain unqualified. No reverse PS4 writer or console signing
is provided.

## Use and validation

Select the exact route in Save Converter, review the gold before/after value,
then export to a new folder. Both original inputs are backed up and rechecked;
source backups bind the original gameplay and complete metadata by digest.
The usual path-free receipt explicitly records the gold-only scope and
`game_load_verified: false`.

```text
python -m koei_editor --convert sw4_ps4-to-samurai4dx-ps4-gold --source Ps4Copy/app.dat --template PcCopy/save.dat --dry-run
```

Procedural regressions cover exact native qualification, corruption, identity,
nonzero-region rejection, metadata/source races, bounded backup readback,
replacement-file preservation, strict conversion bounds, unusual no-ops and
surgical PC changes. Optional local native tests use `SW4_PS4_NATIVE_COPY`
for source qualification and `SW4_PS4_US_COPY` with `SW4DX_SAVE_COPY` for transfer.
Player saves, original metadata, private hashes and source paths are excluded
from the repository and all release assets. File-level checks do not establish
converted in-game loading or re-saving.

The [earlier investigation](SW4_PS4_RESEARCH.md) records the public encrypted
exports and legacy PC migration research. Decrypted data is now available for
this US profile; complete migration still needs additional native integrity,
typed dependency and edition-migration evidence.

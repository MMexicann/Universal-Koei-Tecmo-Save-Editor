# DW7 Xtreme Legends PS3 to Definitive Edition PC

The **Save Converter** adds the one-way route `dw7xl_ps3-to-dw7xl` in v2.5.2.
It transfers qualified persistent state from original US **BLUS30873** or
European **BLES01496** PS3 Xtreme Legends into a native PC Definitive Edition
save template. Base DW7, Empires, Japanese/Asian PS3, old 2012 Windows saves and
PC-to-PS3 conversion are separate, unsupported routes.

This is a conversion preview. Copied-file format and preservation checks have
passed; **loading and re-saving a converted copy in the destination game has not
been tested**. A PS3 save described as 100% complete does not establish that every
PC achievement, bundled DLC item or edition-specific condition will be complete.
The converter moves stored state and does not synthesize a completed save.

## Use it

1. Finish any suspended battle in both editions, then close both games.
2. Export/decrypt a copy of the PS3 XL save with Apollo or another compatible
   save manager. Keep its **original `PARAM.SFO` beside `APP.BIN`**. A decrypted
   XL gameplay file is exactly 470,303 bytes; the encrypted, padded 470,304-byte
   file is not accepted. Do not trim an encrypted file or substitute base DW7.
3. Create and copy a native **Definitive Edition PC `save.dat`** outside the
   live save/Steam Cloud folders. This file is the destination template; it
   supplies PC settings, platform state and encryption seed.
4. Open **Save Converter**, search `DW7` or either supported PS3 title ID, and
   select **DW7 Xtreme Legends · US/European PS3 → DW7 XL Definitive Edition · PC**.
   Select the PS3 source and PC template, then **Review conversion**.
5. Review the replacement counts and exclusions. Export to a new folder. Both
   inputs receive verified backups; the output contains `save.dat` and a
   private `conversion.json` receipt. Keep the originals and test a separate
   converted copy in the PC game.

The console metadata is required to identify and back up the source. It is not
copied into the PC output. The app does not decrypt PFDs, verify console signing,
resign packages or derive an account identity. If an operation fails, do not
import its retained incomplete output.

```text
python -m koei_editor --convert dw7xl_ps3-to-dw7xl --source Ps3Copy/APP.BIN --template PcCopy/save.dat --dry-run
python -m koei_editor --convert dw7xl_ps3-to-dw7xl --source Ps3Copy/APP.BIN --template PcCopy/save.dat --output-dir ConvertedDw7
```

The same route works in Batch Converter, with a separate reviewed template and
new output directory for each job.

## Transfer and retained data

The reviewed route transfers **50,138 canonical bytes** of qualified shared
state. Numeric members are converted individually; byte arrays retain their
original bit order.

The source replaces corresponding values, including lower scores and locked
states. This is not an inventory merge or an automatic unlock operation.

| Shared state | Mapping |
| --- | --- |
| System head | Typed 32-bit/16-bit progress and ownership masks, gold, history and seal ownership |
| Story records | Four 306-byte records, qualified 16-bit members only |
| Legend/Conquest state | Typed progress masks, existing references, learning meters, 64 individual seal-state bytes, bonds and availability |
| Officers | All 92 native records, including the 65 playable slots; stats, purchased flags, equipment, guardian references and progression stay together |
| Weapons | All 1,738 physical records; typed counts, ownership/learned flags, meters and five stored references |
| Guardians | Sixteen records, each containing two separate 16-bit members |
| Stage context | Both 150-byte context structures, with 75 individual 16-bit members each |
| Challenges | Eighty complete 20-byte ranking records, with separate 32-bit and 16-bit members |

Destination PC settings, revision, original cipher seed, platform/string/identity
state, unknown fields and padding remain unchanged. The complete `0x60000`-byte
suspended-battle area and following reserved `0x5000` bytes are retained,
including stale bytes in an inactive battle. Unidentified Story/Legend extension
areas must be zero in both copies: the last 100 bytes of each story record,
Legend offsets `0x38E`..`0x3A8` and `0x502`..`0x504`. Nonzero extension state is
rejected because its meaning and dependencies are unqualified.

An active or unfamiliar suspension
flag in either copy is rejected. The converter recomputes the native PC word
checksum and reparses the output. It does not add a checksum to the PS3 plaintext
or pretend that a copied title file authenticates the console export.

PC bundled content can be enabled by the game's own code rather than a saved
ownership flag. PS3 DLC availability is not a transferable entitlement. This
route does not grant missing assets, change Steam achievements, migrate console
profiles or promise equivalent completion across editions.

## Format evidence

Offsets are decoded payload positions; PC has a four-byte checksum/seed header
before them. The native PS3 plaintext begins with big-endian revision
`0x11080200`; PC uses the same numeric revision in little endian. A native PS3
payload and a decoded PC payload are both `0x72D1F` bytes. Equal lengths alone do
not qualify conversion: the map treats each known word, dword and byte array
individually. Unknown regions are never blanket-swapped.

| Payload region | Native structure |
| --- | --- |
| `0x4`..`0x1F7C` | System block, `0x1F78` bytes |
| `0x1F7C`..`0x2039` | Destination-retained settings/platform region |
| `0x2039`..`0x4E39` | 92 × 128-byte officers |
| `0x4E39`..`0xD601` | 1,738 × 20-byte weapons |
| `0xD601`..`0xD641` | 16 × four-byte guardians |
| `0xD641`..`0xD6D7` | 150-byte stage-context mirror |
| `0xD6D7`..`0xDD17` | 80 × 20-byte challenge results |
| `0xDD17`..`0xDD1F` | Destination-retained eight-byte challenge trailer |
| `0xDD1F`..`0x6DD1F` | Destination-retained suspended-battle object |
| `0x6DD1F`..`0x72D1F` | Destination-retained reserved tail |

Independent static inspection of the native PC serializer and official PS3
BLUS30873 v01.01 update establishes the common revision, block ordering and
mixed typed layout. PC top-level serializer `0x5993A0`, system `0x5A0200`,
officers `0x59E5B0`, weapons `0x5A5310`, guardian serializer `0x59AAD0`, context
`0x5A1320`, challenge block `0x59F630` and suspended battle `0x5A3830` supply the
PC boundaries. These are addresses in the inspected binary, not runtime hooks.
The PS3 top-level serializer at `0x281194` and system serializer at `0x290A64`
independently corroborate the console layout. No game code was executed.

Two original regional PS3 exports have their exact original metadata and
PFD-declared plaintext length. They contain the **same gameplay state** and do
not count as two independent progression histories. Three distinct public PC
states qualify native integrity, unchanged roundtrips and destination templates;
two later posted PC states appear to share a creator. All supplied states are
advanced saves, not controlled one-action samples. Edited game loading remains
separate and unverified.

Community and primary references:

- [GameFAQs PS3 XL save listings](https://gamefaqs.gamespot.com/ps3/635632-dynasty-warriors-7-xtreme-legends/saves)
  identify the two original US/European exports. Public player files and account
  metadata stay outside the repository and release.
- [Apollo US XL patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLUS30873.savepatch)
  independently corroborates resource/stat positions and 65 playable records.
  Patch targets alone were not used as a cross-platform schema.
- [koko-tsuu's unfinished DW7 XL converter research](https://github.com/koko-tsuu/dw7xl_save_converter/tree/15aee59cc773cb401ddad3b4c9099a03629cf700)
  supplies the pre-existing PC reference. Its README says conversion is unfinished;
  its anonymous console fixture matches base DW7, not XL. Its padding/header
  rewrite is not used. No third-party implementation is incorporated.
- [Steam edition/DLC discussion](https://steamcommunity.com/app/968790/discussions/0/1743353798890985725/)
  distinguishes successful old-PC-to-DX migration reports from this PS3 request.
  Those reports do not validate PS3 conversion.

## Verification

Format and conversion tests cover exact revision/framing, mandatory regional
metadata, independent mixed-width values, byte flags, dependency groups,
source/template preservation, suspension refusal, retained unknown areas,
backups, changed-source/context races, forged snapshots, actual output reparse
and the one-way route restriction. GUI, CLI and mixed-game batch tests exercise
the registered route. Optional private fixtures use `DW7XL_PS3_SAVE_COPIES` and
`DW7XL_PC_SAVE_COPIES`; no player bytes are included in the public tests.

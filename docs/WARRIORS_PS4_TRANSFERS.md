# DW8 XL, WO3 Ultimate and Samurai Warriors 4 transfers

v3.1 adds a DW8 XL PS4 editing profile and four **resource-only PS3 ↔ PC**
conversion routes, plus a one-way WO3U PS4 → PC route for 354 directly mapped
crystal/orb/material balances, plus a separate scope adding 145 officers’ five
base stats. It does not establish complete WO3U or SW4 PS4 conversion.

## Requested PS4 → PC transfers

| Game | Available scope | Remaining evidence |
| --- | --- | --- |
| Dynasty Warriors 8 Xtreme Legends Complete Edition | Decrypted US PS4 CUSA00397 `APP.BIN` with original `sce_sys/param.sfo` → PC common revision `0x131002F0`. The entire `0xB7F44` common gameplay core transfers. PS4 input must be exactly `0xD0F45` bytes with an entirely zero extension. | Other regions/revisions and nonzero extensions need separate qualification. Independent original-context exports and converted in-game load/re-save remain outstanding. |
| Warriors Orochi 3 Ultimate | PS4 CUSA00588 → PC transfers rare crystals, 58 attribute-orb balances and 295 material balances (355 bytes); a separate wider scope also adds five base stats for 145 playable officers (1,805 bytes total). Two separate **US PS3** ↔ PC routes transfer growth points/gems. Full migration remains unavailable. | The new source profile requires exact native markers and original metadata. Broader migration needs the complete saved-state schema, controlled transfer pairs and DLC/reward compatibility. [Exact PS4 evidence and limits](WO3U_PS4_RESOURCE_TRANSFER.md). |
| Samurai Warriors 4 | Full PS4 → SW4 DX PC transfer is unavailable. Two new routes transfer only mapped resources between **US PS3** SW4 and PC SW4 DX. | Need complete decrypted PS4 exports with original metadata and the full platform/revision schema, native integrity, progression/equipment relationships and edition-specific content policy. SW4-II and Spirit of Sanada remain separate games. |

Console extraction, decryption, reimport and resigning use external save tools.
Use a copied save created by the destination edition as a template. Do not rename
an encrypted console container to a PC filename.

## DW8 XL PS4 editing

Choose the PS4 CUSA00397 zero-extension profile in the game library. Open a
separate decrypted `APP.BIN` with its original `sce_sys/param.sfo`. Save As and
Restore require that same unchanged original companion beside the destination.
Backups retain the opened gameplay and its original metadata. Self-test copies
copy the original companion; no account/signing context is synthesized.

The editor exposes the existing common-core mapping: gold, gems, facility and
weapon materials, 82 officer records' stored stats, four weapon-action aptitudes
and ranked attributes on qualified existing weapons. Unknown IDs, unusual ranks,
record identities, EXP, story and extension bytes remain intact. Automatic Max
is disabled because these bounds are manual editing limits.

No native PS4 gameplay checksum is claimed. Size, common revision, zero extension,
title context, immutable staging and actual saved-byte/value readback are checked.
Those checks do not verify console authentication or successful in-game loading.

For conversion **to PC**, the destination template may use either exact PC
header already accepted by the editor: `f002101309` or `f027021909`. Both native
PC checksums are validated before its original cipher seed is reused. The entire
destination gameplay core is replaced by the unchanged common-revision source,
including its `f002101309` header. An alternate-header PC file remains unavailable
as a conversion source; its header and unknown content are never normalized.
Private complete public PS4 and alternate-header PC references passed native PC
checksum/readback and an exact PS4 reverse. The PS4 reference lacks original
metadata, so application export tests use procedural context; converted game
loading remains unverified.

## Resource-only routes

Find these directions in Save Converter, or use their exact CLI route IDs:

| Route IDs | Transferred values | Destination retained |
| --- | --- | --- |
| `wo3u_ps4-to-wo3u-ps4-materials` | Rare crystals, 58 attribute-orb balances and 295 material balances: 354 balances / 355 bytes, little endian. | Every other PC byte, including gems, growth points, platform markers, officers, weapons, progression, settings and saved-state sections. |
| `wo3u_ps4-to-wo3u-ps4-stats-materials` | The same material balances plus 725 directly mapped base-stat words: 1,079 values / 1,805 bytes. | Levels, EXP, promotions, equipment references, internal officers, the entire saved-state block, settings and all other PC bytes. |
| `wo3u_ps3-to-wo3u`, `wo3u-to-wo3u_ps3` | Unallocated growth points and gems: two unsigned little-endian 32-bit balances, 8 mapped bytes. | All serialized markers, officers, weapons, growth allocation, rare crystals, ownership, promotions, rewards, story, DLC and other bytes. |
| `sw4_ps3-to-samurai4dx`, `samurai4dx-to-sw4_ps3` | Gold only: one unsigned 32-bit balance, 4 mapped bytes. Each native writer uses its own offsets and endian order. | Eight gem balances, officers, weapons, mounts, custom characters, Chronicle, story, options and all other payload bytes except required destination integrity. PC header and cipher seed remain original. |

PS3 WO3U requires `NPUB31505-SAVEDATA`, decrypted `APP.BIN` and original
`PARAM.SFO`. PC uses native Definitive Edition `SAVEDATA.BIN`, revision
`0x140318F1`. PC and PS3 serialized record markers are qualified independently;
none are transplanted. Both resource offsets are `0x1378` and `0x137C`, but that
coincidence does not establish whole-file compatibility. Both native readers run. Every changed assignment must pass the destination
field validator. A PC gem assignment above the PS3 bound of **999,999** is
rejected without clamping; exact higher opened destination values remain no-ops.
Higher PS3 opened balances may transfer to PC within its 9,999,999 bound.

SW4 requires US PS3 `NPUB31564` revision `0x2118`, decrypted `DATA.BIN` and
original `PARAM.SFO`; PC SW4 DX requires revision `0x39EA` `save.dat`. Gold is at
PS3 `0x7842` big endian / PC decoded `0x7DA6` little endian. Gold is bounded to
999,999. All eight destination gem balances remain unchanged: their cross-edition
identity/order has not been qualified. Both native section checksums and the PC
envelope sum are required and rebuilt by the existing destination writer.

Transfers replace these balances, including lower values. They do not merge
best values, award dependent rewards or migrate progression. Experimental editor
limits cannot widen conversion bounds. Review displays the original destination
and incoming value for every transferred balance. Both inputs are backed up;
export creates a new directory and the usual path-free scoped receipt.

```text
python -m koei_editor --convert wo3u_ps4-to-wo3u-ps4-materials --source Ps4Copy/APP.BIN --template PcCopy/SAVEDATA.BIN --dry-run
python -m koei_editor --convert wo3u_ps3-to-wo3u --source Ps3Copy/APP.BIN --template PcCopy/SAVEDATA.BIN --dry-run
python -m koei_editor --convert sw4_ps3-to-samurai4dx --source Ps3Copy/DATA.BIN --template PcCopy/save.dat --output-dir ConvertedResources
```

## Evidence and validation

The DW8 common-core mapping and PS4 framing reuse the independently implemented
[DW8 conversion evidence](SAVE_CONVERSION.md). The public full-file PS4 reference
has no original console metadata; generated title-only metadata tests context
behavior without claiming independent owner-export evidence. Nonzero extension
bytes are rejected in both editing and conversion.

Resource facts come from the existing qualified adapters, not imported converter
code: [WO3U PS3](WO3U_PS3.md), [WO3U PC](OROCHI_RESEARCH.md),
[SW4 PS3](PS3_EXPANSION.md) and [SW4 DX PC](SAMURAI_RESEARCH.md). These are
independently mapped manual balances. No upstream implementation, player save,
account context or extracted game asset is packaged.

`test_resource_conversion.py` checks every new direction, numeric/endian values,
the complete retained destination payload, seed/header preservation, checksums,
strict bounds under experimental policy, metadata/backup races, forged reviews,
exports and exact reverses. Its optional native-copy test requires paired local
copies and original PS3 metadata; absence is a skip, not native validation.
`test_dw8xl_ps4_editor.py` checks the bound scalar contract, dynamic record guards,
unusual opened values, staged Undo/review, surgical edits, source/context races,
backups, restore and actual Tk Save As. Existing all-route, CLI, batch and GUI
tests include the new endpoints. Procedural tests and copied-native file checks
do not establish edited/converted in-game load/re-save.

The SW4 PS4 investigation acquired two genuine encrypted console images, which
still require external decryption before gameplay qualification. It also identified
the unproved cross-edition gem-order assumption; those routes retain destination
gems. [Public sources and exact missing inputs](SW4_PS4_RESEARCH.md).

Native-copy checks passed gold-only transfers against five US PS3 SW4 states and
one PC reference, in all ten directed pairs with exact reverses. WO3U PS3 → PC
also exported a higher original PS3 gem balance and reversed byte-exactly into
its unchanged original PS3 template. The acquired public-origin WO3U PS4 payload
passed all 354 assignments through guarded native PC Save As with every other
byte preserved; its PS4 context was generated test metadata, not original metadata.
These are file-level checks; converted in-game loading remains unverified.

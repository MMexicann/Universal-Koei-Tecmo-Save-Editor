# Attack on Titan / A.O.T.: Wings of Freedom — European PS Vita

`aot1_vita` is an independently authored published-format profile for original
European `PCSB00898` decrypted `app0000.dat` copies with their original
`sce_sys/param.sfo`. US, Japanese, Windows, PS3/PS4, sequel and Final Battle
profiles are separate and excluded.

## Evidence and native qualification

[Apollo's exact PCSB00898 recipe](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PSV/PCSB00898.savepatch)
publishes money and 81 numbered item quantity fields. The full bounded fixed
address interpreter was reviewed in
[Apollo's writer](https://github.com/bucanero/apollo-lib/blob/864dfd86c34acaf7e9a01eb3c55302b301e5cea3/source/patches.c).
For example, its raw money target `7F 96 98 00` represents 9,999,999 as a little
endian DWORD, and `E7 03` represents 999 as a little endian WORD. These published
byte facts were independently implemented without importing GPL source or any
catalog.

The original
[RinCheat SE recipe](https://github.com/Rinnegatamante/rinCheat/blob/d17fd2a7a542346e503afd9cd1df8c5e8bd33626/SE_cheats_db/PCSB00898.lua)
and the complete
[SE disk writer](https://github.com/Rinnegatamante/rinCheat/blob/d17fd2a7a542346e503afd9cd1df8c5e8bd33626/SE_module/index.lua)
were also reviewed. This is the save editor module, separate from the runtime
trainer database. It writes fixed scalar bytes and declares `needs_crc32=false`,
so its whole-file CRC path is unused for this title. This declaration is a source
writer setting, not a native game flag; this adapter never clears a gameplay
integrity flag.

There are two publication discrepancies: the recipes target `app000.dat`, while
both native exports actually contain `app0000.dat`, and RinCheat's `int2str`
reverses numeric recipe values that are already written as byte-swapped constants.
Thus the original RinCheat recipe is not treated as an independently proved
working console import. The adapter uses the intended byte patterns as published
by Apollo's fixed-address recipe, corroborated on the two native exports. It
accepts the actual native filename and preserves its exact layout. No upstream
code was executed or copied into this implementation.

Two distinct complete exports from the
[Apollo PCSB00898 collection](https://github.com/bucanero/apollo-saves/tree/c6fa97f2f4ef1b3469f0421c727997108821e188/PSV/PCSB00898)
(`00000001.zip`, `00000002.zip`) qualify 768,000-byte (`0xBB800`) geometry and
this exact observed 32-byte prefix:

```text
0000000000000000f0e70500000000000000000000000000c043020000000000
```

No revision or checksum meaning is invented for those framing bytes. The original
bounded PSF1.1 SFO must contain `PARENT_DIRECTORY=/PCSB00898`. Both native balances
and quantities agree with the published storage widths and byte order. The second
collection export is described as a maidump export; neither is controlled clean
before/after gameplay evidence.

## Writable fields and dependencies

| Field | Offset | Storage | Editing scope |
| --- | --- | --- | --- |
| Money | `0x34` | unsigned 32-bit, little endian | Reduce from opened balance to zero |
| Quantity of native record `i` in `0..80` | `0x35CA0 + i * 0x30` | unsigned 16-bit, little endian | Positive existing quantities only; reduce to zero |

The writer does not create a positive quantity in a zero row, select a new item
identity, set discovery/ownership, grant equipment, alter equipped references or
change story, rewards, character growth and collection flags. Native indices have
no assumed item names or rarity labels. Positive opened quantities define upper
bounds; the published 999 target is not claimed as a natural limit. All controls
disable Max, and exact typed original values unstage edits, including unusual
money or quantity values.

## Integrity and copy safety

`INTEGRITY_KIND='external'` identifies this published direct scalar writer scope.
No native gameplay checksum or its absence has been independently established.
The adapter qualifies bounded complete geometry, observed framing and exact
original SFO identity; it does not claim arbitrary corruption detection, repair
bad input or disable integrity. Vita import, authentication and signing remain
with the save manager. No edited game-load/re-save was available.

Unknown bytes and original context remain unchanged. Safe file reads and final
atomic new-destination writes check the complete opened source and original SFO
digest. Backups include paired context metadata. Restore validates the exact
bounded snapshot it will write and the same original SFO. Edited output reparses,
and `BoundScalarAdapter` checks every requested value.
Save As and Restore reopen the actual written copy, verify its complete bytes
against the requested output or backup hash, and compare the original SFO digest
again after writing. A same-title companion swap during writing or read-back is
rejected. A failed final verification retains the opened session and reports an
error; it does not delete a destination another process may have replaced.

Private native exports, images, original metadata, sealed keys, save-manager files
and downloaded external source copies stay outside the checkout. This adapter
copies only the bounded original SFO opaquely for private copied-save checks; it
never synthesizes, interprets or edits account/signing fields.

## Validation

`tests/test_aot1_vita.py` has nine procedural checks covering all eligible
resource fields, surgical preservation, zero-row gates, bounds, invalid pending
maps, unusual originals, typed no-ops, complete framing/title identity, immutable
snapshots, backup/restore, existing destinations and source/context races.
Postwrite checks exercise opaque same-title companion changes and a restored
payload modified after creation.

The optional `AOT1_VITA_NATIVE_DIR` test passes on both complete native exports:
unchanged roundtrips, one-unit reductions of each positive mapped resource,
readback, allowed-byte changes and unchanged original sources. Without the
private directory it skips. Native import and edited game-load/re-save were not
performed; these checks do not resolve native integrity or recipe portability.

The actual source Tk editor passed open/search/select/stage, Review, Undo,
disabled Max, inspection, backup and atomic Save As on one original export.
Reopened output changed only the selected money bytes and retained the complete
source and original SFO. Registered GUI/storage contracts live in
`tests/test_sony_new_profiles_gui.py` and
`tests/test_sony_new_scalar_contracts.py`.

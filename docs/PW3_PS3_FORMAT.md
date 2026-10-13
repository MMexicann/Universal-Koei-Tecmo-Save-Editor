# One Piece: Pirate Warriors 3 — original EU PS3 PSN

`pw3_ps3` independently implements the published original European PS3 PSN
`NPEB02211` stat writer. Open a copied decrypted `DATA.BIN` with its unchanged
original `PARAM.SFO`. This is separate from the Windows PC profile, and does not
accept other PS3 titles, disc regions, Vita, PS4, or Switch editions.

## Evidence

[Apollo's NPEB02211 patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPEB02211.savepatch)
explicitly supplies the 47-record PS3 stat map and says stored HP/Attack/Defense
can reset when a character levels up. Its published character count, stride,
widths, and endian order were independently implemented. No GPL source code or
external catalog was imported.

The complete published disk writer was reviewed through
[Apollo's `apply_cheat_patches`/`resignSave` workflow](https://github.com/bucanero/apollo-ps3/blob/d7e4d6ee69464db7958acb771c8ecf5de4502358/source/exec_cmd.c)
and the complete
[patch interpreter](https://github.com/bucanero/apollo-lib/blob/864dfd86c34acaf7e9a01eb3c55302b301e5cea3/source/patches.c).
The flow decrypts the protected file, applies the selected bounded scalar writes,
emits the complete buffer, re-encrypts, and authenticates external `PARAM.PFD`.
The entire title patch contains no gameplay integrity update. This establishes a
published stat writer; it does not establish the absence of native integrity or
that this project's edits have loaded in-game.

The original exported reference from the
[Apollo NPEB02211 collection](https://github.com/bucanero/apollo-saves/tree/c6fa97f2f4ef1b3469f0421c727997108821e188/PS3/NPEB02211)
(`00000001.zip`, described as fully unlocked) was privately decrypted with its
original PFD context. The complete file is 960,512 bytes (`0xEA800`), with
big-endian first two DWORDs `(0, 2)` and zero bytes at `0x0C..0x17`. Other framing
words remain opaque. The original SFO directory is exactly `NPEB02211-00`.
The reference contains an unusually high primary currency word; it is a public
reference with unlocked progression, not controlled clean gameplay evidence.

Native files, owner context, names, images, downloaded source copies and private
decryption tooling stay outside the checkout. The adapter never changes signing,
account information, PFD, or SFO bytes.

## Writable storage

For native record `i` in `0..46`, the stride is `0x1F0`:

| Value | Relative offset | Storage | Editing scope |
| --- | --- | --- | --- |
| Stored HP | `0xF4` | unsigned 16-bit, big endian | Existing positive value, reduce to at least 1 |
| Stored Attack | `0xF6` | unsigned 16-bit, big endian | Existing positive value, reduce to zero |
| Stored Defense | `0xF8` | unsigned 16-bit, big endian | Existing positive value, reduce to zero |
| XP | `0xF0` | unsigned 32-bit, big endian | Read only |
| Stored level index | `0xFB` | unsigned byte | Read only |

Only records with positive XP and a stored level index in `1..99` expose stat
fields. Initial, unprogressed, unknown-level, and zero-stat records remain read
only; reducing stats never grants character ownership or progression. Record
numbers are physical storage identities, not unproved character names. Stat
changes can reset on level-up as documented by the published writer.

Opened values define upper bounds. All controls disable Max, and higher or
unusual originals are preserved. Exact typed original values remove staged edits.
XP, levels, special bars, equipped skill slots, learned skills, medal ownership,
progression, unlock prerequisites, story and unknown bytes stay intact.

The two published currency words at `0xC074` and `0xC078` are read only.
The source writes them together with different targets, and there is no controlled
proof of their relationship. Currency, medal, level, XP, ownership and collection
patches are excluded from this profile.

## Integrity and safe copies

`INTEGRITY_KIND = 'external'` describes the published writer's native-file
workflow. Native gameplay integrity is not independently established, and this
profile does not claim arbitrary corruption detection or checksum absence.
The parser qualifies complete geometry, observed framing and exact original
SFO identity. It never clears integrity flags or repairs damaged input.
Console reimport, encryption and external PFD authentication remain the save
manager's responsibility.

The complete original SFO is retained opaquely and bound by digest. Safe reads,
backups, new-destination atomic Save As and restore recheck both that context and
the opened source. Serialized edits reparse, and `BoundScalarAdapter` verifies
every requested value while preserving the immutable original. Restore qualifies
the exact bounded bytes that will be written, with the original context digest.
After writing, both operations reparse the new snapshot and compare its expected
bytes/hash, original companion digest and directory; they recheck the context
before accepting it. Save As additionally rechecks the original source after
writing. Rejection leaves a raced destination unaccepted and avoids deleting a
path another actor may have replaced.

## Validation

`tests/test_pw3_ps3.py` covers all 141 possible procedural stat fields, surgical
readback, typed no-ops, progression/zero-record dependency gates, unusual opened
stats, invalid pending maps, malformed geometry, framing, wrong editions, frozen
documents, original context, changed sources, backups, restore and new destinations.
Fault injection also covers valid same-title companion replacement immediately
after writing and after reopening, plus source changes after atomic creation.

Seven procedural tests pass. The optional original-reference test through
`PW3_PS3_NATIVE_DIR` additionally passes unchanged roundtrip and one-unit surgical
readback for every eligible native stat while preserving the source. Without the
private reference variable that test skips. No edited game-load/re-save or
independent controlled action pair was available.

The actual source Tk editor also passed open/search/select/stage, Review,
Undo, disabled Max, inspection, backup and atomic Save As on the original
public reference. The saved copy read back correctly, changed only the selected
stat bytes, and preserved the source and original SFO. Registered workflows are
covered in `tests/test_sony_new_profiles_gui.py` and the shared storage contracts
in `tests/test_sony_new_scalar_contracts.py`.

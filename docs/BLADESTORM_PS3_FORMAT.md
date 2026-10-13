# Bladestorm: The Hundred Years' War — original European PS3

`bladestorm_ps3` is an independently authored published-format resource editor
for the original European `BLES00113` edition. It accepts a separate decrypted
`PLAYDATA` export copied as `.bin`, beside its unchanged original `PARAM.SFO`.
US, Japanese, PSN, Nightmare, and other console editions are excluded.

## Evidence and qualification

The title-specific published writer is
[Apollo's BLES00113 patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLES00113.savepatch).
The corresponding
[PS3 game configuration](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/games.conf)
and complete [Apollo save processing](https://github.com/bucanero/apollo-ps3/blob/d7e4d6ee69464db7958acb771c8ecf5de4502358/source/exec_cmd.c)
establish external decrypt/edit/PFD processing. Its complete
[interpreter](https://github.com/bucanero/apollo-lib/blob/864dfd86c34acaf7e9a01eb3c55302b301e5cea3/source/patches.c)
emits the complete modified file buffer. The public patch writes money and book SP directly. These facts were
reimplemented independently; no Apollo source code or catalogs were imported.
Apollo patches use GPL licensing, which does not license this project's code.

Two independent original exports in the
[public Apollo BLES00113 save collection](https://github.com/bucanero/apollo-saves/tree/c6fa97f2f4ef1b3469f0421c727997108821e188/PS3/BLES00113)
(`00000322.zip`, `00000459.zip`) were privately decrypted from their original
PFD context. Both decrypted files are exactly 496,592 bytes (`0x793D0`). The
qualified header profile has `01 01` at `0x02` and
`BC 42 00 00 FF FF FF FF` at `0x2C`. These are observed framing markers;
no release number, gameplay stat, or checksum meaning is asserted for them.
The input title additionally requires the bounded original SFO directory
identity `BLES00113PLAY` followed by one decimal slot digit.

Native files, player names, account context, images, downloaded source copies,
and decryption tooling remain outside the checkout. The adapter does not execute
game binaries or write PFD, SFO, ownership, or signing data.

## Writable storage and dependencies

| Field | Offset | Width and byte order | Scope |
| --- | --- | --- | --- |
| Published primary money | `0x84` | unsigned 32-bit, big endian | Reduce from opened value to zero |
| Existing book SP pool, record `i` in `0..15` | `0x394 + i * 0x54` | unsigned 32-bit, big endian | Positive opened balances only; reduce to zero |
| Published secondary money | `0xAB8` | unsigned 32-bit, big endian | Read only |

The published money patch writes both money words. Their relationship has not
been demonstrated by a controlled game action, so the secondary word remains
read only. Book record indices are storage identities, not named book IDs.
Positive existing SP qualifies a pool for reductions without granting a book,
creating a balance in a zero record, or touching learned skill/ownership fields.
Those dependencies, experience, levels, equipment, story, awards, and unknown
bytes remain intact. Published cheat targets are not natural gameplay caps;
all fields use `maxable=False`, and assigning an exact typed opened value
unstages an edit even for unusually high values.

## Integrity and copy safety

This profile reports `INTEGRITY_KIND = 'external'`. The complete published
resource writer performs direct resource writes and external PFD authentication.
No native gameplay integrity algorithm has been independently established.
The parser checks bounded geometry, observed framing, and original title
context; it does not claim to detect arbitrary gameplay corruption or infer that
an internal checksum does not exist. It never clears integrity flags or repairs
input. Edited output must be reimported and resigned externally with Apollo.

The original SFO is retained opaquely and bound by digest. Reads and final writes
recheck that context and the complete original source snapshot. Save As writes
atomically to a new `.bin` destination beside the same original SFO, creates a
backup with context metadata, reparses output, and uses `BoundScalarAdapter`
readback. Restore validates the exact bounded bytes it will write and requires
the same original context digest. After writing, Save As and restore reparse the
new snapshot, compare its original companion digest and identity, and recheck
that context before accepting it. Save As also rechecks the opened source after
writing. A detected external race raises an error and leaves the new destination
unaccepted; it is not deleted because another actor may have replaced it.

## Validation

`tests/test_bladestorm_ps3.py` covers procedural no-op and surgical edits for
all mapped pools, zero-record dependency gates, preserving the secondary money
word and all other records, unusual originals, typed no-ops, bounds, invalid
pending maps, wrong editions, malformed framing, frozen snapshots, backups,
restore, existing destinations, and source/context races, including same-title
companion replacement immediately after writing and after reopening.

All ten tests passed with the two original public exports enabled through the
private `BLADESTORM_PS3_NATIVE_DIR`. The original-export test checks every positive
mapped field with a one-unit reduction, unchanged roundtrips, exact readback,
allowed-byte changes, and unchanged sources. Without that private environment
variable, nine procedural tests pass and the original-export test skips.
No edited game-load/re-save or independent controlled gameplay pair was available.

The registered copied-save CLI also passed on one original export, checking
16 writable fields and preserving the input. Its report correctly identifies
external integrity, with `native_integrity_verified: false` and
`in_game_load_tested: false`.

The registered GUI workflow and three registered shared scalar storage contracts
also pass. The actual Tk workflow covers search, staging, Review, Undo, disabled
Max, inspection, backup and Save As; these remain file/UI checks.

# Warriors: Legends of Troy — original European PS3

The `troy_ps3` adapter opens a **PFD-decrypted, extensionless `PROFILE`** beside
its complete original **`BLES01183-WLOT PARAM.SFO`**. Its initial scope is the
qualified **103,435-byte revision-38 populated profile** with 53 serialized
music identities and 99 serialized item identities. It rejects other lengths,
table geometries, regions and editions. This is deliberately a narrow profile;
it does not claim every early-game or differently populated save works.

Make a separate export copy outside the live game folder. Keep the original
`PARAM.SFO` beside both the opened copy and destination. Save As creates a new
extensionless file. Reimport it as `PROFILE` using the appropriate PS3 save
manager and rebuild external PFD authentication/signing. The editor does not
change account data or rebuild `PARAM.PFD`.

## Implemented controls

- Reduce the existing **saved Kleos balance**, from zero through the opened
  balance. This is the source-backed persistent resource, distinct from a
  stage's running combo score, best score and healing effects.
- Inspect 53 native music identity strings and 99 native item identity/status
  records through searchable tables. Item names come from the opened file;
  there is no copied external item catalogue. The item word and two status
  bytes are presented literally, without guessing price, ownership or capacity
  semantics.
- Shared staging, Undo, Review Changes, backups, restore, new-file Save As and
  exact source/context-change detection apply.

Kleos increases, Max and experimental increases are disabled. The public cheat
target is not used as a natural gameplay cap. Purchases, item acquisition,
equipped grids, character attributes, chapter results, difficulties, gallery
unlocks and rewards are not changed. The public all-stage-clear recipe has a
completion prerequisite and is not exposed as an unconditional unlock action.
Raw wallet words above `0x7FFFFFFF` remain read only: the available source does
not establish native signedness or sentinel behavior there. The qualification
boundary is not a claimed gameplay maximum. The resource inspector retains
the exact raw word even when no wallet edit is offered.

## Native format and evidence

The primary [chaoszage title-specific save writer, preserved by Apollo](https://github.com/bucanero/apollo-patches/blob/d396aa4f2452b02382c4e7066d712f6ce9116964/PS3/BLES01183.savepatch)
locates Kleos between the music and item collections and specifies a complete
trailing CRC32. [Apollo's patch interpreter](https://github.com/bucanero/apollo-lib/blob/a938bd30dd8a19bc5e37d661d503d97bbd54b254/source/patches.c)
explicitly treats parenthesized offsets as **decimal**. Its `write next (-11)`
therefore means eleven bytes before the second anchor, not hexadecimal `0x11`.
The adapter independently implements these facts rather than importing GPL
patch-engine code or a third-party item catalogue.

The [author-shared European export](https://web.save-editor.com/bbs/savedata/ps3/bbs.cgi?list=pickup&num=667)
contains original PS3 and separately supplied RPCS3 representations, described
by the author as a completed save. Independent PS3-envelope decryption exactly
reproduces the included RPCS3 `PROFILE`, including its existing valid checksum.
These are **two representations of one native gameplay state**, not two
independent playthroughs or a controlled purchase/action pair. The author's
completion claim was not verified in-game. Player bytes, save hashes, metadata,
downloaded archives and private static research remain outside the repository.

| Native fact | Qualified representation |
| --- | --- |
| PROFILE prefix | Two big-endian DWORDs: `38`, `2` |
| Length | 103,435 bytes; encrypted export is 103,440 bytes because of PFD padding |
| Music table | Count 53 at `0x16E06`; bounded length-prefixed UTF-16BE identities |
| Collection boundary | Music names, count 42 and opaque status bytes, then the resource boundary |
| Saved Kleos | Big-endian 32-bit word at `0x17200`; acquired state stores 4,498; only opened nonnegative values common to signed/unsigned storage are writable |
| Item names | Count 99 at `0x17204`; bounded length-prefixed UTF-16BE identities |
| Item status table | Matching count 99; six bytes per existing identity; retained literally |
| Complete native integrity | Standard CRC32 over `[0, file_length - 4)`, stored as the final big-endian DWORD |

The writer checks identity, exact size, CRC32, both table counts, bounded valid
UTF-16, unique native identities, the source-relative Kleos anchor and the
complete item-table/end-of-file boundary. Damaged inputs are rejected without
repairing them. A no-op returns the original bytes exactly. A qualified edit
changes only the four wallet bytes and required four checksum bytes, then
reparses before the copied save is accepted. Unknown engine state, flags, item
words and trailer data remain opaque and unchanged.

## Validation and remaining work

[`test_troy_ps3.py`](../tests/test_troy_ps3.py) covers surgical no-op/edits,
corruption and resealed malformed/foreign layouts, complete pending maps,
experimental-policy hard limits, unknown-value preservation, context/source
changes, backups/restore and actual Tk search/edit/review/Undo/Save As. Optional
native tests use `TROY_PS3_NATIVE_DIR`, a private folder containing decrypted
`PROFILE` and the complete original `PARAM.SFO`; they skip when absent.

The native copied-file qualification includes wallet reductions, complete
CRC/read-back and source-hash preservation. An independent audit matched a
bitwise reflected-polynomial CRC implementation against the entire native file,
walked both UTF-16 table boundaries independently and verified six surgical
on-disk copies plus the native Tk open/Undo/review/Save As/restore workflow.
Metadata changes while opening, post-creation source changes and checksum-valid
destination replacements are explicitly rejected without deleting completed
backups or outputs. **Edited in-game loading and
re-saving have not been performed.** Other native PROFILE geometries require
their own complete exports and independently qualified boundaries. US/Japanese,
Xbox 360 and unrelated Koei profiles are not accepted by this adapter.

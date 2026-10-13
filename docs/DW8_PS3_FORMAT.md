# Dynasty Warriors 8 — original US PS3 PSN

This adapter targets original US PSN `NPUB31234-SAVEDATA/APP.BIN`, after
external PS3 PFD decryption. The original unchanged `PARAM.SFO` must accompany
the copied input and every Save As/restore destination. Disc, other regional,
XL, Empires, PC and Vita profiles remain separate.

## Native evidence

The exact active [Apollo NPUB31234 patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPUB31234.savepatch)
binds the original PSN title directory and names Gold plus Ambition facility
and weapon materials. The complete native
[public export](https://github.com/bucanero/apollo-saves/tree/c6fa97f2f4ef1b3469f0421c727997108821e188/PS3/NPUB31234)
contains original `APP.BIN`, `PARAM.PFD`, and `PARAM.SFO`. Its published
provenance explicitly says maximum money, all characters level 50 and maximum
stats: this is a **modified native player export**, not an untouched campaign
or an independent edited game-load test.

Only the published individual save archive was privately acquired. Original
ciphertext was retained, PFD gameplay decryption performed outside the checkout,
and title identity read from original bounded metadata. The resulting native
file is exactly **665,767 bytes (`0xA28A7`)**, beginning `13 01 13 00`.
Gold and both material balances match the exact public patch's targets.

The active patch execution path mutates the declared big-endian resource bytes
and leaves the remaining payload intact; PS3 PFD encryption/authentication and
re-signing remain external. The original native file is already plaintext after
PFD decryption. No XL byte cipher or additive suffix is applied. We do not
invent an additional gameplay checksum or normalize unexplained bytes. All
opaque body and trailing bytes are retained exactly, and no-op returns the
complete original file. Qualification is `published_format=True`,
`sample_verified=True` for this explicitly modified native export,
`editing_verified=False`, and `game_load_verified=False`.

Only factual offsets and observed framing are independently implemented.
Apollo's GPL source/patches and any player/account data are not copied into
source or release assets. No game or emulator binary was run. Console
import/resigning is outside the adapter.

## Controls and preservation

| Field | Native mapping | Write scope |
| --- | --- | --- |
| Gold | `0xBD`, unsigned BE32 | Reduce the opened balance |
| Ambition facility materials | `0x21CF9`, unsigned BE16 | Reduce the opened balance |
| Ambition weapon materials | `0x21CFB`, unsigned BE16 | Reduce the opened balance |
| Ambition fame | `0x221D5`, unsigned BE16 | Inspection only |

Published cheat targets do not establish natural caps. Max and increases are
excluded; unusually high opened balances stay readable and exact typed no-ops.
Material spending does not change facility levels, unlocks or weapon instances.
Officer activation, EXP, levels, stats, purchased skills, weapon attributes,
animals, equipment, battles, story and reward dependencies stay intact.
Additional fields require qualified existing records and native dependency
proof before writes, even when a broad cheat patch exists.

The mandatory metadata gate checks exactly `NPUB31234-SAVEDATA`. The full
bounded original metadata digest is bound to the opened snapshot, backup and
destination. The copied sidecar is opaque and never rebuilt or interpreted for
account ownership. Changing even an unparsed sidecar byte blocks saving.
The same original digest is checked after atomic file creation and after native
read-back; a sidecar change retaining the title identity cannot bind the new
file to different context. Restore also reopens the written bytes and checks
both their backup digest and the original companion digest before success.
`prepare_copy_context` preserves the complete original bounded companion for
private CLI copied-save workflows.

## Validation and limitations

`tests/test_dw8_ps3.py` checks every resource, immutable staging, byte-exact
no-op, big-endian surgical edits, unusual typed values, complete pending-map
validation, bad geometry/header and foreign identity rejection, mandatory
context/digest binding, backup/restore, existing destinations and source changes
after backup. Fault injections change an opaque same-title sidecar byte after
atomic saving/restoring and during save read-back; every operation rejects the
changed context. Its Tk workflow opens a copied file, stages, undoes, reviews,
changes theme, saves and restores. `DW8_PS3_REFERENCE_COPY` selects the private
PFD-decrypted modified public `APP.BIN` beside its original `PARAM.SFO` for
native roundtrip and all-resource surgery. The source ciphertext, metadata,
private reports and modified output remain outside source downloads.

An independently shared untouched original US PSN campaign and controlled
spending pairs would strengthen field qualification. Loading/re-saving the
edited file on the original console remains unperformed; no such result is
claimed.

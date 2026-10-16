# Fatal Frame II: Crimson Butterfly — original US PS2 qualification report

**Status: unregistered research candidate. No original Fatal Frame II PS2 editor
or writer is included in this release.** Complete US exports establish native
container geometry and integrity, and independent retail RAM cheats corroborate
six stock names. The link from those named retail stocks to the candidate's US
on-disk fields and their dependent state is not independently qualified.

This report concerns the original US **SLUS-20766** PS2 title and native directory
`BASLUS-20766ZERO-BD`. It does not qualify European/Japanese editions, Xbox
Director's Cut, the Wii remake, the modern Crimson Butterfly Remake or unofficial
PC ports. Other supported Fatal Frame editions retain their own separate scopes.

## Native evidence

[Apollo's public US PS2 collection](https://github.com/bucanero/apollo-saves/tree/2b0815d8fd994f8e285f7cafcf4a977ba94b1260/PS2/SLUS20766)
contains eight complete export archives. Their contained native files were
privately converted from PSV to PSU framing without changing their contents.
Independent walks of the original PSV and converted PSU manifests confirmed
identical native files, with **32 occupied slot instances representing 12 distinct
gameplay byte states**. These counts do not establish eight independent players
or unmodified gameplay histories. No player saves, account context, icons or
other game assets are distributed.

The native copies independently confirm these file extents and checksum rules:

| Native file | Observed extent | Integrity |
| --- | ---: | --- |
| `BASLUS-20766ZERO-BD` summary | 136 bytes | Final little-endian u32 signed-byte sum |
| `Zero2System` | 44 bytes | Final little-endian u32 signed-byte sum |
| Each `Zero2Play0`–`Zero2Play4` | 36,155 bytes | Final little-endian u32 signed-byte sum |

The checksum adds each preceding byte interpreted as a signed eight-bit value,
modulo `2**32`; an unsigned-byte sum fails the genuine files. Never-written
slots in this corpus contain zero data followed by `0xFFFFFFFF`. Occupied files
contain 58 indexed eight-byte records at slot-relative `0xBA5`. Each record has
two signed little-endian words: the first equals its index, or 255 when the
second word is zero. These are observed structural facts, not independent proof
of each field's retail gameplay meaning.

PSU file positions depend on entry order and padding. Any future implementation
must walk complete container headers, preserve unknown files and metadata,
validate every applicable native checksum and reject damaged or foreign copies.

## Independent retail name corroboration

[GameHacking.org's SLUS-20766 entry](https://gamehacking.org/game/103708) attributes
the six individual stock cheats in **Max Item Codes** to **Code Master**. Its
decrypted Codebreaker-v7 display gives the following retail RAM quantity words:

| Named stock | Retail RAM address |
| --- | ---: |
| Type-14 film | `0x2BD00C` |
| Type-61 film | `0x2BD014` |
| Type-90 film | `0x2BD01C` |
| Type-Zero film | `0x2BD024` |
| Herbal Medicine | `0x2BD02C` |
| Sacred Water | `0x2BD034` |

This independently corroborates the named stock ordering and eight-byte RAM
stride. **RAM addresses are not save-file offsets.** These cheats do not prove
the retail save-block ordering, disk linkage, checksum dependencies, ownership
rules or whether additional state must change. Their quantity target of 99 is
also not adopted as a qualified editing cap. No cheat code or catalog is copied
into the application.

## Prototype source limits and release blocker

The [MioPan source snapshot](https://github.com/Mikompilation/MioPan/tree/b0f3bd4898fec100e0a3612d66004b1b0cbff044)
contains save-manifest and item-use leads in `system/mc/dat/save_data.c`,
`system/mc/prg/mc_cmn.c`, `mc_check_broken.c`, `mc_set_data.c`,
`ingame/item/prg/item.c`, `item.h` and `ingame/item/dat/item_dat.c`.
**Its authors explicitly describe heavy AI-assisted reconstruction of a
February 2004 European prototype. It is not a verified US retail decompilation.**
Its AGPL-3.0 code and assets are not copied into this project.

The separately inspected, older Minakami partial decompilation also targets that
European prototype. It leaves the relevant item-loss and inventory-save routines
as external assembly, so it does not independently close the retail gap.

The prototype manifest suggests an inventory offset of
`0xC + 0x380 + 0x250 + 0x5C0 + 1 + 8 = 0xBA5`. Its item-use routines suggest
reducing existing finite film/medicine stocks while retaining at least one could
avoid removal and acquisition transitions. Native US geometry and independent
RAM names make these useful research leads, but do not establish that the retail
disk words have the same meaning or that this write has no dependent retail
state. **Public editing remains deferred until an independent retail save writer,
reviewed retail static routines or controlled native action pairs establish
that linkage and the required dependent writes.**

## Implementation checks and their limits

A private, independently written candidate was exercised against the complete
copied-native corpus. Its 22 focused tests passed, including an actual Tk
open/search/stage/Undo/review/Save As/restore workflow, reordered PSU entries,
malformed containers, signed-byte integrity, surgical serialization, strict
bounds, immutable snapshots and late copy/backup/restore changes. A private
on-disk audit completed 184 stock assignments: 183 surgical outputs and one exact
no-op, plus eight backup/restore cycles. Original player exports remained
unchanged.

Those checks establish the candidate's implementation behavior against its
proposed schema. They do not independently qualify the proposed retail stock
semantics. **No edited game load/re-save or controlled retail action pair has
been validated.** The candidate source and tests are retained privately for
future work and are excluded from public support, source distribution and
release game counts.

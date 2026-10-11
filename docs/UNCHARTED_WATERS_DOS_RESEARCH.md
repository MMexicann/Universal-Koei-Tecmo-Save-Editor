# Original Uncharted Waters — DOS native-writer gate

Original Uncharted Waters remains unregistered. It is a distinct native format
from the supported English DOS Uncharted Waters II adapter. This follow-up
found a precise original-game save reader, but no complete corresponding save
writer or native integrity proof. No speculative writable profile was added.

[Water1-MapViewer](https://github.com/onionmixer/Water1-MapViewer/tree/d3dbc8c209ac1d8f5f3e83cd3b732081f684c551)
is MIT-licensed. Its `SaveDataReader.cpp` is a reader, not a gameplay save
writer. The pinned source describes `SAVE.DAT` of 61,756 bytes, five allocations
starting at `0x100` with stride `0x3000`, and `0x1DAA` bytes of interpreted
slot data. Eleven-byte slot names begin at offset 5. Its fleet money field
is a little-endian word at slot-body `0xC54 + 9`.

The source separately maps ship ownership/active flags, crew, hull, sails,
supplies, cargo IDs/quantities and morale. Cargo capacity is derived from
ship records; food/water use their own scaled representation. Those details
make a useful starting point for richer mechanics investigation, but they
do not prove legitimate field limits or consequence-safe writes.

The viewer's engine-derived documentation cites reconstructed native routines
in `src/main_game/game_loop.c` and `shin_mem.h`. Those files are absent from
the inspected public repository. Its executable-size/hash recognition applies
to map-generation assets, not to a native save-write path. A read-only parser,
an old DOS release date, or plausible money values cannot establish that no
checksum or companion dependency exists.

Exact remaining requirements:

- A complete original DOS save writer, or equivalent statically recovered
  native save/load routines, establishing full slot framing and any integrity
  transformation. A writer for Uncharted Waters II or IV cannot substitute.
- Genuine original `SAVE.DAT` with occupied gameplay slots, preferably an
  unchanged re-save and a labelled purchase/sale pair. Prove slot ownership,
  money and supplies independently before extending into cargo/crew systems.
- Natural limits, signed/scaled value handling and ownership/capacity
  dependencies, followed by full-byte no-op, surgical edits, malformed-input,
  safe-copy/backup/restore and actual Tk checks.

No game executable was downloaded or run, and no source implementation,
catalogue or extracted game asset was copied into the editor. This document
records a concrete source gate; it does not advertise original-game support.

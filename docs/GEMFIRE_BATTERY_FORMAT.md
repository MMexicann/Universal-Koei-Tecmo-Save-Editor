# Gemfire USA NES and SNES battery records

The `gemfire_nes` (`.sav`) and `gemfire_snes` (`.srm`) profiles edit copied raw
8,192-byte battery images. They implement existing player-province gold, food,
loyalty, farming and protection. ROMs, emulator states, wrappers and unqualified
record structures are rejected. These layouts are derived from the USA titles;
Japanese Royal Blood and other editions have not been independently qualified.
Battery records lack a separate region/revision tag, so identity is qualified
by their native record structures and pointers rather than a claimed region tag.

These are **source-backed native-format profiles**. Procedural fixtures establish
the safety and byte-preservation behavior; independent occupied native gameplay
images, controlled actions and actual game-load/re-save verification are still
missing. The public SNES SRAM archive reviewed during development contained an
empty image and was rejected. It establishes no successful native qualification.
No save contents are included in this repository.

## Public evidence and implementation

Facts were checked against the public native/bytecode disassemblies and their
record studies, rather than against cheats or a related platform's save size. Reviewed revisions
are NES `04e4e86f46172014ca7adcfdafba7eb24da6cb30` and SNES
`ae7bc75b97bb048a2e2b6b746c3e81059479d5f2`:

| Profile | Evidence |
| --- | --- |
| NES USA | [GemFire-decompiler](https://github.com/chrisaacson69/GemFire-decompiler): [native header study](https://github.com/chrisaacson69/GemFire-decompiler/blob/04e4e86f46172014ca7adcfdafba7eb24da6cb30/docs/00-recon.md), [schema](https://github.com/chrisaacson69/GemFire-decompiler/blob/04e4e86f46172014ca7adcfdafba7eb24da6cb30/docs/schema.md), [bank 1 assembly](https://github.com/chrisaacson69/GemFire-decompiler/blob/04e4e86f46172014ca7adcfdafba7eb24da6cb30/source/asm/bank1.asm), [bank 6 assembly](https://github.com/chrisaacson69/GemFire-decompiler/blob/04e4e86f46172014ca7adcfdafba7eb24da6cb30/source/asm/bank6.asm), [bank 30 assembly](https://github.com/chrisaacson69/GemFire-decompiler/blob/04e4e86f46172014ca7adcfdafba7eb24da6cb30/source/asm/bank30.asm) |
| SNES USA | [Gemfire-snes-decompiler](https://github.com/chrisaacson69/Gemfire-snes-decompiler): [header study](https://github.com/chrisaacson69/Gemfire-snes-decompiler/blob/ae7bc75b97bb048a2e2b6b746c3e81059479d5f2/docs/00-recon.md), [corrected data map](https://github.com/chrisaacson69/Gemfire-snes-decompiler/blob/ae7bc75b97bb048a2e2b6b746c3e81059479d5f2/docs/08-data-map.md), [native assembly](https://github.com/chrisaacson69/Gemfire-snes-decompiler/blob/ae7bc75b97bb048a2e2b6b746c3e81059479d5f2/src/native.asm), [save/load routines](https://github.com/chrisaacson69/Gemfire-snes-decompiler/blob/ae7bc75b97bb048a2e2b6b746c3e81059479d5f2/src/comusr1.c), [load/header routines](https://github.com/chrisaacson69/Gemfire-snes-decompiler/blob/ae7bc75b97bb048a2e2b6b746c3e81059479d5f2/src/settei.c) |

The NES `cmd_save` at `$A995` copies `0x769` bytes from `$6000` to the selected
SRAM slot; `cmd_load` at `$A9DC` checks `KOEI` at state offset `0x765`, copies
the complete state back and redraws it. Bank 1 `new_game_setup` at `$8791`
checks the same four bytes before offering Continue. These are complete native
block-copy writers, without an additional sum, encryption or signing layer.

The SNES save/load routines copy `$7E:C004..$7E:C76C`, likewise `0x769` bytes,
through syscall `$17` (`$00:9B3C`) and its native MVN block-copy implementation.
The load path checks the same `KOEI` footer. Its native header reports 8 KiB SRAM.
Its record tables occupy the same relative offsets as NES, with pointers based
at `$C004` instead of `$6000`. Its globals do not share that relative layout:
native month `$C007` is relative `+3`, and native player IDs `$C028/$C029` are
relative `+0x24/+0x25`; NES uses `+7` and `+0x28/+0x29` respectively.

The public bytecode listing omits the contents of the NES SRAM slot-address
data table. The adapter therefore does **not invent slot bases or assign slot
numbers**. It locates complete existing state blocks by the verified relative
`KOEI` footer and qualifies all mapped arrays and relationships. Inspection
identifies a state by its byte offset in the opened battery image. Only
nonoverlapping, complete, structurally qualified states are accepted. Bytes
outside those state blocks remain opaque and are preserved. An absent footer
is treated as an unoccupied/opaque region, as in the native availability check;
there is no checksum that can diagnose arbitrary damage to unknown bytes.
Candidate blocks are qualified before incidental `KOEI` bytes inside a qualified
state are ignored, including combinations of editable stat values that spell
those bytes. A `KOEI` occurrence outside every qualified state is conservatively
rejected if its implied block fails qualification; without the original slot
table, such an occurrence cannot be distinguished from a damaged occupied state.

The public source repositories did not declare a licence in the reviewed root
trees. This implementation is independently written from the documented facts.
No upstream code, game strings, record-name catalogs, ROM data or binaries are
copied into the application or source archive. The earlier SNES record note
called the province table a lord table; the later corrected data map and native
record operations resolve that error. A province's word at offset zero is a
leader-list head, **not** a general occupied-record identity number.

## Record layout and editable fields

All offsets below are relative to the start of a qualified `0x769`-byte state.

| Record | Offset | Stride | Count | Qualification |
| --- | ---: | ---: | ---: | --- |
| Player faction IDs (NES) | `0x28` | 1 | 2 | Existing army/faction IDs `0..29`; `255` means unused |
| Player faction IDs (SNES) | `0x24` | 1 | 2 | Same ID bounds, different relative globals |
| Army/faction | `0x35` | 4 | 30 | Leader at `+1` is `0..63` or `255`; partner at `+2` is `0..29` or `255` |
| Leader | `0xAD` | 10 | 64 | Next pointer `+0`; province `+5` is `0..29` or `255`; faction `+6` is `0..29` or `255` |
| Province | `0x32D` | 36 | 30 | Leader-list head `+0`; faction at `+14` is `0..29` or `255` |
| Native footer | `0x765` | — | — | Exact `KOEI` |

Nonzero pointers must identify aligned members of the selected platform's
leader table. Linked lists must be acyclic and disjoint. Assigned leaders must
agree with their province's faction, and referenced chain members must agree
with both their province number and owner. Player factions and owned provinces
must reference occupied army records. At least one linked leader and one player
province must exist. Month is qualified as `1..12`. This conservative structure
can reject transitional or unusual native images that have not been validated.
It does not claim acceptance of every battery image for either platform.

| Province field | Relative offset | Encoding | Native natural cap | Evidence |
| --- | ---: | --- | ---: | --- |
| Gold | `+2` | little-endian u16 | 999 | Trade/recruit resource operations and capped native additions |
| Food | `+4` | little-endian u16 | 999 | Trade and give-food operations and capped native additions |
| Loyalty | `+8` | u8 | 100 | Give-food command and its cap check |
| Farming | `+9` | u8 | 100 | Cultivation command and its cap check |
| Protection | `+10` | u8 | 100 | Protection command and its cap check |

Only provinces whose existing faction is one of the state's saved player IDs
expose fields. Enemy and unoccupied provinces remain inspection only. Soldiers
at `+6`, troop divisions, deployment, leaders, faction ownership, gems,
prerequisites, calendar, turn flags and story state are preserved. The natural
caps qualify Max; opened higher values are preserved by Max and exact typed
opened values unstage as no-ops. New values must meet the documented bounds.

## Safety and validation

Both profiles use `BoundScalarAdapter`, immutable opened snapshots and shared
safe copy/backup/restore storage. Edited saves reparse and read back every
requested value. The complete output is reopened from disk after Save As.
Destinations must be new, source changes are detected, and unknown bytes remain
exact. No-edit serialization returns the original battery bytes exactly.

`tests/test_gemfire_battery.py` supplies procedural fixtures with two state
blocks, distinctive unknown bytes and enemy provinces. It checks moving state
locations, platform pointer identity, cycles/shared chains, faction ownership,
malformed/truncated/empty images, all-field surgical writes, unusual-value
unstaging and Max, immutable snapshots, pending-map validation, safe storage,
backups, restore and a writer that drops edits. The two registered profiles
also run the shared scalar contract suite.

Optional separately reviewed native images can be selected with
`GEMFIRE_NES_SAVE_COPY` and `GEMFIRE_SNES_SAVE_COPY`. Their qualification and
unchanged serialization would be stronger evidence than a procedural fixture,
but still would not establish edited gameplay loading or controlled semantics.

```text
python -m unittest tests.test_gemfire_battery -v
```

# Nobunaga's Ambition — original English NES, 17 fiefs

The adapter accepts a separate `.sav` copy of the original **8,192-byte battery
save bank**, mapped to CPU `$6000`–`$7FFF`. It qualifies the 17-fief scenario,
English native names, and intact original `Tokugawa`/`Oda` title anchors. The
50-fief scenario, translated editions, successors replacing either anchor,
16 KiB exports, savestates and emulator containers remain outside this profile.
This narrow identity gate is deliberate; the editor does not guess another
profile when native framing differs.

## Complete native source evidence

The published [Nobunaga decompilation](https://github.com/chrisaacson69/na1-decompiler/tree/52d5532eb0b0ac8312a38088cda4242748924994)
contains both native disk-bank operations and their bytecode callers. The
[bank-zero reader/writer](https://github.com/chrisaacson69/na1-decompiler/blob/52d5532eb0b0ac8312a38088cda4242748924994/nobunaga/source/4-c/bank_00.c)
provides `verify_sram_save_integrity` at `$821E` and
`write_sram_save_checksum_and_signature` at `$A3AA`; the original
[6502 syscall](https://github.com/chrisaacson69/na1-decompiler/blob/52d5532eb0b0ac8312a38088cda4242748924994/nobunaga/source/1-asm-6502/bank_15_labeled.asm)
at `$C5AA` proves the unsigned byte-sum algorithm and exact count handling.
The [SRAM decoder](https://github.com/chrisaacson69/na1-decompiler/blob/52d5532eb0b0ac8312a38088cda4242748924994/nobunaga/tools/sram-decode-province.py)
explicitly maps the original 8 KiB save bank and province fields.

This adapter independently expresses factual storage information. No external
implementation, game binaries, assets, name tables or source copies are
included. No explicit source-reuse license was found; the publication is used
only as factual format evidence. No game/emulator executable was run. Public source claims based on
actual original-game SRAM are distinct from our procedural validation. We have
not obtained an independent native saved campaign or performed game loading;
qualification is `published_format=True`, `sample_verified=False`,
`editing_verified=False`, `game_load_verified=False`.

Some older upstream documentation describes checksum location as unfinished
or summarizes its span as the full save body. The complete later source and
native syscall supersede those descriptions for the implementation here.

## Native integrity

The native writer copies through `$0200`, selects source/destination SRAM
banks, and adds each byte into an unsigned 16-bit accumulator. The count loop
compares only the low count byte: zero means a full 256-byte block. The final
`0x81EB` count therefore means exactly `0xEB` bytes, not a huge array length.

| Stored bytes / coverage | Exact file-relative meaning |
| --- | --- |
| Checksum | Unsigned LE16 at `0x1FEB`–`0x1FEC` |
| Signature | `KOEI\0` at `0x1FED`–`0x1FF1` |
| First coverage | `[1, 0x1000)` |
| Second coverage | `[0x1001, 0x1FEB)` |
| Exclusions | Offsets 0 and `0x1000`, checksum, signature and trailing bytes |
| Arithmetic | Byte sum modulo 65,536 |

The reader rejects bad integrity before exposing fields. No-op serialization
returns the exact input; checksum regeneration occurs only after qualified
field edits. The bound scalar adapter permits only the exact checksum range
as required integrity changes and verifies every requested native field again.
Excluded bytes, signature and trailer stay byte-exact.

## Fields and existing-record gates

| Native structure | File-relative mapping |
| --- | --- |
| Scenario fief count | LE16 at `0xD9D`, must be 17 |
| Year / season | Year LE16 at `0xD9F`; season byte at `0xD5F`, 0–3 |
| Province policy | `0xCF7 + fief_index`; 0–5 active, 255 excluded |
| Owner map | `0xE15 + fief_index`, original daimyo IDs 0–16; native special owner 51 is read only |
| Province array | `0x1001`, 17 records of 26 bytes |
| Gold / rice | Unsigned LE16 at province +0 / +6 |
| Daimyo names | `0x17A8`, 17 records of 9 bytes |

Only existing active fiefs receive resource controls. Ownership and policy are
validation/inspection fields; they are never changed. Gold and rice can only
be reduced from their opened balances. The implementation uses neither a
storage ceiling nor example cheat target as a natural cap. Max is disabled and
higher existing values remain readable, preserved, and exact typed no-ops.
The source's `set_fief_ownership_record` pathway also assigns owner ID 51 to
ordinary fiefs. That native special state is preserved and inspected read only;
it never indexes the 17-entry daimyo name table or receives resource controls.

| System | Scope or remaining requirement |
| --- | --- |
| Gold / rice | Individually reduce existing active fief balances |
| Search and ownership records | All 17 fiefs with native owner/name/policy |
| Debt, town, output, dams, loyalty, wealth | Preserved; history/high-water mechanics remain separate from current resources |
| Men, morale, skill, arms | Preserved; coupled army and battle records not qualified for writes |
| Tax, grant policy, ownership and succession | Inspection/preservation only; no conquest or member creation |
| Daimyo stats, age, health, names, portrait state | Preserved; no succession/name edits or natural cap claims |
| Story/victory/date/other scenario | Preserved; no progression or scenario conversion |
| Native game qualification | Matching independent English 17-fief native campaign, spending/action pairs and edited game load/re-save still required |

## Checks

`tests/test_nobunaga_ambition_nes.py` covers every mapped fief/resource,
unchanged roundtrip, native checksum inclusion/exclusion boundaries, surgical
writes limited to each resource and the two integrity bytes, typed pending
values, immutable snapshots, inactive records, corrupt checksums and foreign
framing, backups/restore, source change after backup, new destinations and
on-disk readback. Its deliberately procedural SRAM is not a playable native
campaign and is never labeled genuine evidence.

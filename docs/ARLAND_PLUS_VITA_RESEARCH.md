# Totori Plus and Rorona Plus — Vita native retry

These profiles remain unregistered investigations. The Meruru Plus Vita writer,
original PS3 patches and DX PC/PS4 layouts do not establish their native writer
or game-internal integrity model.

Public Apollo exports were acquired privately with their original
`sce_sys/param.sfo` and system/slot metadata:

- [Totori Plus US PCSE00231](https://bucanero.github.io/apollo-saves/PSV/PCSE00231/):
  seven distinct gameplay files, each 282,624 bytes.
- [Rorona Plus US PCSE00466](https://bucanero.github.io/apollo-saves/PSV/PCSE00466/):
  seven gameplay files across two archives. Five are 393,216 bytes; two are
  380,928 bytes. Both sizes contain native plaintext chunk framing. The larger
  size alone is **not** evidence of PFS encryption.

Both titles start with little-endian magic 20100403 and a 32-byte header. Their
sequential `(u32 tag, u32 payload_length)` lists are different from each other,
Meruru Plus Vita and the later DX versions:

```text
Totori Plus tags 1–22:
33264, 5172, 4, 3972, 152520, 51, 57164, 4, 5632, 1, 20,
68, 940, 1452, 8, 4536, 400, 1836, 14325, 168, 96, 64

Rorona Plus tags 1–32:
39392, 8416, 4, 6112, 138252, 128, 100816, 4, 5248, 1, 8,
68, 132, 3328, 8, 9376, 47984, 4137, 128, 768, 384, 112,
256, 234, 4, 4, 64, 7048, 32, 188, 832, 488
```

Totori's final tag 1024 is at `0x44D31`, length 719 including its eight-byte
header. Rorona's final tag is at `0x5B5E4`, length 6684 including its header,
ending at 380,928. The five larger Rorona exports additionally have a 12,288-byte
allocation tail. Future parsers must preserve that tail and qualify both
observed variants, rather than truncate it or reject one solely by size.
These are structural observations, not proofs that header/trailer values are
inactive checksums or that matching-looking fields are writable.

The public VitaCheat entries for
[Totori](https://github.com/r0ah/vitacheat/blob/master/db/PCSE00231.psv) and
[Rorona](https://github.com/r0ah/vitacheat/blob/master/db/PCSE00466.psv) describe
runtime money, inventory, combat and calendar addresses. They do not implement
an offline native save reader/writer or establish save offsets. Repository and
code searches found no complete Vita Plus writer for either title; no restricted
code, catalogs, game assets or binaries were incorporated.

| System | Exact qualification needed |
| --- | --- |
| Money | Vita-specific native field identity/width and complete save integrity/writer proof; runtime money addresses and DX/PS3 offsets do not suffice |
| Existing characters and gauges | Native ordinal identities, joined/available records, base versus equipment-derived stats and current/effective-maximum dependencies |
| Levels, EXP and alchemy | Native thresholds, growth, recipe/skill unlocks and reward transitions; no independent-level or EXP shortcut |
| Inventory, quality, uses and quantities | Native occupied identity, serial, width, capacity and ordinary versus unique/equipped/registered-shop dependencies |
| Traits, effects and synthesis | Native item applicability and trait/effect choices; public runtime layouts cannot qualify disk record strides |
| Equipment | Native ownership/equipped references and derived-stat effects, with controlled equip/unequip pairs |
| Friendship, requests and personal events | Separate relationship/request/completion/report/reward records and thresholds |
| Calendar, assignments, exploration and endings | Exact title-specific time/event transitions, deadlines and reward dependencies; calendar cheats are excluded |
| System data, extras and collections | Separate system framing, integrity and discovery/ownership/selected-state mappings |
| Console import | Original title context, immutable source/metadata binding, safe copy storage and external Vita import remain required |

A useful next input is a **complete title-specific native save writer or
loader/integrity analysis**, followed by labelled one-action gameplay pairs.
The acquired native saves remove the missing-fixture blocker, but unlabelled
completed saves alone do not resolve those semantics. No actual edited game-load
or re-save was performed. All exports remain outside Git and release assets.

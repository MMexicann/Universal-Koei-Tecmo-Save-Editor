# FAIRY TAIL — original Nintendo Switch format research

The native gameplay container and its complete block integrity are now
independently recovered. Gameplay field meanings are not sufficiently proved,
so FAIRY TAIL is not registered as a supported editor. The reusable codec lives
under `koei_editor.research.fairy_tail_switch`, with no GUI adapter or public
supported-game entry. A working checksum does not establish inventory ownership
or wallet semantics.

## Qualified native evidence

The title-labelled public
[NXResources/NX_Saves collection](https://github.com/NXResources/NX_Saves/tree/638ee26ec4fd4fa1121f1cf3caa997e8dc5f169f)
contains a Spanish `Super Starter` export for title `0100CF900FA3E000`.
Three original gameplay slots and their management/system companions were
acquired privately. Player files, identifiers, external archive contents and
catalogs are not distributed.

Every block has a twenty-byte little-endian header:
`signature[4], header_size, body_size, revision, checksum`. Extents cover the
complete originals exactly. Gameplay begins with outer `#USR` revision
`0x10001`, containing ten ordered leaves. All outer and inner checksums use
32-bit FNV-1a with the important native detail that each byte is **signed-char
extended before XOR**, seed `0x811C9DC5`, multiplier `0x1000193`. Unsigned-byte
FNV-1a does not match. Independently verifying all thirty-nine block checksums
across the five genuine files confirms both high-bit behavior and bounded
parent/leaf framing.

| Gameplay leaf | Revision | Qualified body size |
|---|---|---|
| `#NFD` | `0x40001` | 5280 |
| `#PRD` | `0xA0001` | 2609 |
| `#QUD` | `0x50001` | Variable |
| `#PTD` | `0xD0001` | 7784 |
| `#IND` | `0x10001` | Variable |
| `#PLD` | `0x90001` | 631 |
| `#GLD` | `0x20001` | 3492 |
| `#STD` | `0x30001` | 10470 |
| `#CTD` | `1` | 4 |
| `#RTD` | `0x10001` | Variable |

Original gameplay lengths are 31,549, 33,210 and 32,883 bytes. Management is
`#MNG` with `#LSD`; system is `#SYS` with `#STD`, `#SSD` and `#GRD`.
Those companions help corroborate the checksum algorithm but are not accepted
as gameplay slots. No codec normalization, corruption repair or unbounded
decompression is performed.

The codec validates complete immutable gameplay snapshots, requires exact
leaf order/revisions/fixed extents, rejects truncation/trailing blocks and
roundtrips unchanged bytes exactly. A research-only same-length leaf
replacement recomputes only the leaf and enclosing hash, preserving all other
bytes; it is deliberately not a field-authorizing editor backend.

## Mechanics and mapping gates

[Official character development](https://www.koeitecmoamerica.com/manual/fairytail/en/3300.html)
and [guild facilities](https://www.koeitecmoamerica.com/manual/fairytail/en/4200.html)
distinguish character level/EXP, character rank, Fairy Points, Jewels, Lacrima,
guild rank and facility development. Character rank unlocks Lacrima equipment
capacity; facility upgrades involve missions/materials and prerequisites.
These systems cannot be treated as interchangeable generic money/EXP words.

| System | Current evidence / precise blocker |
|---|---|
| Native integrity and slot framing | Qualified with all thirty-nine checksums, three gameplay no-ops and surgical codec-only test changes |
| Jewels wallet / lifetime totals / Fairy Points | `#PLD` is structurally qualified; candidate words need controlled spending/rank pairs or a complete disk writer proving their meanings and dependencies |
| Inventory, battle items and materials | `#IND` has dynamic record geometry; type/instance/item-ID/count ownership meanings are unresolved. An ordinary consumable catalog and controlled obtain/use pair are required |
| Lacrima, recipes, synthesis and equipment | Need owned-item types, attached/equipped references, rank capacity and facility prerequisites; no guessed ID insertion or equipment Max |
| Character EXP, ranks, HP and battle stats | Need native stored-versus-derived mapping. Runtime editor authors report displayed stats are recalculated through battles/levels/equipment |
| Fairy Points and Magic Foundation | Distinct character-rank and growth systems; no generic duplicate-stat assumptions |
| Guild facilities, quests, rewards and recruitment | Need complete native masks, reward/cost dependencies and controlled completion pairs; preserve story progression |
| Candy/Nikora rewards and collection | Need ordinary-versus-quest identity and claimed-reward state proof |
| Revisions, regions, PC / later titles | Exact original Switch evidence only; separately qualify other layouts/platforms rather than reusing offsets |

The public [Fearless Revolution PC table](https://fearlessrevolution.com/viewtopic.php?t=13251)
was inspected as XML source without executing it. Its live item pointers and
wallet-object offsets do not identify the corresponding serialized Switch
fields; it contains no qualifying item-ID dropdown or complete native writer.
No executable trainer or borrowed cheat implementation is incorporated.
GitHub save-editor/source searches and EdiZon configuration checks did not
produce a complete disk writer or qualified catalog for this title.

The shortest path to an editor is a labelled before/after native save pair
changing exactly one Jewels purchase, one ordinary consumable use, or one
character-rank investment, with the original companions retained. A complete
open-source native writer identifying those same fields would also resolve
the mapping gate. More copies with unrelated progress changes do not establish
safe scalar semantics by themselves.

## Tests

`tests/test_fairy_tail_switch_codec.py` exercises signed-byte known answers,
procedural no-ops, immutable envelopes, strict framing/extent/revision checks,
corrupt inner hashes despite a valid outer hash, surgical leaf/hash spans and
wrong-type inputs. Private `FAIRY_TAIL_SWITCH_SAVE_COPIES` enables three genuine
gameplay no-ops/surgical codec-only changes and both companions' checksums.
All originals remain unchanged. Deliberately changing an opaque test byte
demonstrates the codec; it does not prove a gameplay field or successful game
loading. No edited-game-load validation was performed.

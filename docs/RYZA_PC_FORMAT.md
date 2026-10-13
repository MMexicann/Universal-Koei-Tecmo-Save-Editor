# Original Atelier Ryza Steam PC

The separate [parser](../src/koei_editor/games/ryza_pc/parser.py) and
[editor](../src/koei_editor/games/ryza_pc/editor.py) accept the observed original
Steam PC app 1121560 source-reference profile. Existing qualified ordinary item
and equipment quality can be reduced from the opened value down to 1; all Max
actions are disabled. This is separate from the shared Switch/Ryza 2 backend,
which retains its existing rejection rules. Ryza DX, later titles, console
revisions, system data and other terminal geometries are excluded.

## Source-reference qualification and integrity

The [SaveGame.Pro original Ryza archive](https://savegame.pro/pc-atelier-ryza-ever-darkness-the-secret-hideout-savegame/)
contains original-PC `GameData00/data.dat` and `GameData10/data.dat` gameplay
slots and separate system data. Both complete encrypted gameplay files were
reacquired and independently checked outside the checkout. They both pass the
mandatory XOR and additive native envelope checksums implemented by the
[existing MIT-attributed Gust codec](../src/koei_editor/games/ryza/codec.py).
The source's exact executable patch/build, language and editing history are not
independently established. These are public source-reference gameplay copies;
some opened quality values are 999 and do not prove a natural gameplay cap.
They are not controlled action pairs or independent edited game-load tests.

Both decoded payloads have 482,881 bytes and begin with big-endian serializer
date 20150729 followed by 28 reserved zero bytes. Their native header and
`info/app_ver` qualify original PC revision 0. The 29 complete roots before the
terminal data have identical names and sizes in both slots and must all match.
Title-specific `_I_HOUSE_KLAUDIA_01`, `_T_BODEN`, `FieldMix` and `memorymap`
framing excludes other Ryza titles. The native item revision is 1, not the
previous unqualified candidate parser's assumed revision 2.

The final `secret_base` begins at decoded offset 482,769. Both copies retain
exactly 112 bytes: the native version-2 prefix, bounded `housingTypeTbl` extent,
and `plantDataTbl` header/extent. The enclosing span declares 3,532 bytes and
the plant extent declares 3,420 bytes absent from the decoded stream. The narrow
adapter recognizes this exact source-reference terminal profile and retains it
as opaque bytes. It never completes/parses the plant records, pads the stream,
repairs the input or accepts arbitrary shortened nodes. Full native checksum
validation and exact decoded length are mandatory, and every edit must retain
all 112 original terminal bytes. A title-specific native loader or untouched
save/re-save control is still needed to interpret this omission or extend
secret-base/plant support. This unresolved terminal interpretation is kept
separate from edits to fully bounded earlier item records.

## Existing records and controls

The native item pools have big-endian extent words and independently bounded
66-byte records. Existing instance ID at +0 and item ID at +2 are little-endian
16-bit words; existing quality at +4 is little-endian 16-bit. This matches the
qualified original Ryza native record facts rather than a later title's record
layout. The adjacent +6 word remains opaque and must be zero before a record
gains a quality control. Item/equipment instances must be occupied and unique;
malformed or duplicate ownership rejects the document. Important pools and
zero/FFFF qualities remain read-only. Higher opened quality values are
reversible as exact typed no-ops, and no natural cap or increase is inferred.

| Pool | Physical records | Qualification |
| --- | --- | --- |
| Ordinary basket | 200 | Existing occupied, unique-instance, positive quality with zero adjacent word. |
| Important basket | 100 | Inspection only. |
| Ordinary container | 5,000 | Same conservative existing-quality gate. |
| Important container | 100 | Inspection only. |
| Expendable container | 50 | Same existing-quality gate; quantities/uses remain opaque. |
| Party equipment | 8 per existing character | Existing references/identity required; quality only. |

The Party block has nine framed 952-byte records at revision 3. Only native
existing character IDs 0 through 5 and empty records qualify. Each occupied
member's eight-record equipment extent is checked before fields are selected.
Header/footer/seed, all inventory bytes outside each two-byte quality field,
unknown IDs, synthesized capacities, equipment references and terminal data
remain exact. Save As uses immutable staging, complete pending-map validation,
mandatory native read-back, source-change checks, backups and atomic writing to
a new destination. Restore validates the exact bounded bytes it writes.

## Mechanics and remaining limits

The [official original Ryza manual](https://www.koeitecmoamerica.com/manual/ryza/en/)
and [synthesis guide](https://barrelwisdom.com/ryza/synthesis-basics) distinguish
quality, material-loop effects, traits, recipes, alchemy growth and rebuilding.
Reducing quality changes only the stored quality word. No quantity/use refill,
item creation/replacement, traits/effects, equipment assignment, currency/gems,
EXP/levels, recipes, friendship, quests, collection completion, secret-base
plants, story or calendar control is offered. Each needs its own native map,
applicability/ownership rules, prerequisites/rewards and controlled actions.
No 999 cheat value is promoted to a natural cap or bulk Max feature.

[Focused tests](../tests/test_ryza_pc.py) cover procedural exact root/terminal
geometry, both mandatory integrity checks, foreign revisions, occupancy,
unusual/zero/coupled quality gates, bounds, exact unchanged roundtrips and
surgical two-byte reductions. Shared scalar contract tests cover staging,
read-back and safe file operations. The optional `RYZA_PC_SAVE_COPY` native
workflow passed on a source-reference slot, including byte-exact no-op, surgical
quality reduction, native read-back, Save As, backup and exact restore. Both
public gameplay slots pass structural/integrity checks; their thousands of
existing records do not imply every mechanic is qualified. No game binary was
executed, no edited game was loaded or re-saved here, and no source-reference
player bytes enter the checkout or release assets.

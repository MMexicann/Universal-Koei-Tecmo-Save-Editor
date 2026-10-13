# Original Atelier Firis Steam PC

The adapter accepts the observed original PC `GAMEDATA` profile for Steam
app 527290, with serializer date 20160829 and exactly 1,228,800 bytes. Firis DX,
PS4/Vita/Switch exports, system files and other native revisions are separate
profiles. The [parser](../src/koei_editor/games/firis_pc/parser.py) and
[editor](../src/koei_editor/games/firis_pc/editor.py) provide conservative Cole
and existing whole-number quality reductions. Every control is excluded from
Max. Edited game loading has not been independently performed.

## Evidence and integrity

[Barrel Wisdom's player-authored original-PC save collection](https://barrelwisdom.com/blog/atelier-pc-saves)
provides a complete original `GAMEDATA00`, separately labelled from Firis DX.
Its native header is big-endian 20160829 followed by 28 reserved zero bytes.
Thirty-three complete roots use little-endian tagged spans. The last complete
root ends at 773685; the remaining 455115 bytes are zero in this copy and remain
opaque. Header, root names and sizes, item/Party revisions and pool bounds all
must match before fields are exposed. The source's exact executable build and
language were not independently established; the adapter qualifies this native
serialization profile rather than claiming every original PC revision.

A separate title-specific
[Steam discussion](https://steamcommunity.com/app/527290/discussions/0/2595630410185608794/)
reports replacing container records directly with a hex editor and successfully
repairing subsequent gameplay on January 17, 2018. That is public native
plaintext writer/load testimony without global checksum resealing, distinct
from this implementation's own checks. The original download links in that
thread now return 404. No checksum word is asserted from the serializer date;
no integrity bytes are guessed, bypassed or repaired. The parser labels the
source-backed original plaintext profile's integrity kind `none`. An
independent unchanged re-save and native loader analysis would strengthen this
qualification; the report is not evidence for DX's encrypted body.

The separately published
[Firis DX PS4 quality patch facts](https://github.com/sterben-Dev10/SaveWizard-Resources/tree/main/SaveWizard-Codes)
identify `m_unitContainer`, stride 0x34 and a float quality field. Those facts
were corroborated independently against the original-PC native pool extents
and existing records: each 52-byte record begins with big-endian instance/item
IDs followed by float32 big-endian quality at +4. For example, the original
copy contains existing qualities 50, 37, 19, 18 and 20 at that location, surrounded
by intact item/effect/quantity data. The console patch's 999 target supplies no
natural cap and is never used as a Max target. No third-party code, patch
list, item catalogue or player bytes are copied into the project.

## Native gates and conservative controls

| Record | Qualification and operation |
| --- | --- |
| Cole | Root `money`, nested `money` span 18, first big-endian signed 32 word. The independently shared native copy stores 900. Permit only 0..opened nonnegative balance; preserve the remaining four native bytes. No balance increase or natural cap is inferred. |
| Ordinary basket | `m_unitKago`, 100 physical records, 52 bytes each. Existing non-FFFF instance/item identities only. |
| Ordinary container | `m_unitContainer`, 4000 physical records, 52 bytes each; stored active limits remain 60/1000. Physical storage does not authorize expanding active capacity. |
| Existing quality | Float32 big-endian at record +4, only finite whole-number opened values 1..16777215 with unique instance identity across all observed pools and a record within the opened active pool limit. Permit 1..opened. Unknown/fractional/nonfinite qualities and spare physical records remain inspection-only. |
| Important pools | 100 records each in `m_unitKagoImportant` and `m_unitContainerImportant`; read-only, including their quality. |
| Party | Revision 3, twelve 840-byte framed records with unique existing identities, plus 128 bytes of native reference/LP data. Inspection/validation only; no character stats, references or ownership changes. |
| Alchemy | Native `mix_lv/m_lv` and `m_exp` big-endian words are inspected read-only. |

Cole and quality fields retain stable IDs, widths, encodings and opened-value
bounds. Assigning the exact typed opened value unstages it. Unknown record
bytes, items, properties/effects, quantities, equipped references, padding,
calendar, prerequisite and reward state remain exact. Negative or unusually
encoded resources do not gain a writable control. Duplicate instance identity
makes the affected item records read-only.

The inspector separately displays the opened active limits and physical record
counts. The independently downloaded original clear copy confirms limits of
60 basket and 1,000 container records in the native BE32 `limitSize` pair,
against physical allocations of 100 and 4,000. Quality controls use the lower
of each opened limit and its physical allocation. Plausible stale records in
spare physical slots remain searchable and read-only; their presence does not
authorize ownership. Unusual limits are shown exactly and preserved. Inventory
rows now report actual quality eligibility instead of ordinary-pool membership,
so fractional, ambiguous and out-of-capacity records are clearly read-only.

## Mechanics still requiring their own proof

The [official Firis manual](https://www.koeitecmoamerica.com/manual/firis/en/)
keeps travel, synthesis and growth distinct. The adapter does not create or
move items, write quantity/use counts, alter traits/effects, equip references,
change alchemy or battle EXP/levels, learn recipes/skills, unlock proficiency,
change friendship, mark quests/collections complete or alter exam/calendar
state. These features need native ownership/applicability rules, growth curves,
prerequisite/reward relationships and controlled actions. Resource reductions
do not grant these dependent systems.

## Validation

[Focused tests](../tests/test_firis_pc.py) cover procedural complete framing,
foreign/truncated/forged snapshots, finite/fractional/unknown quality gates,
ambiguous identity rejection, exact no-op and surgical float/integer writes.
An additional capacity-boundary check retains occupied-looking spare records,
confirms they have no controls, and checks the inspector's eligibility/capacity
tables without mutating the source or native limits.
The shared scalar contract checks immutable staging, full pending-map
validation, read-back, source safety, backups, restore and new destinations.
The optional `FIRIS_PC_SAVE_COPY` test checks an independently copied native
original-PC slot: exact no-op, surgical reduction, Save As, backup and exact
restore. That genuine-file workflow passed locally. Procedural fixtures remain
non-playable test data. The same original native slot also passed actual Tk
Open, Search, Apply, Undo, Review, Inspect, theme change, Save As, backup and
Restore checks. Both source copies remained unchanged; the quality edit changed
only its selected four-byte scalar, preserving equipment and active limits.
No game binary was executed, no independent edited
load/re-save occurred, and no private input is included in the source archive.

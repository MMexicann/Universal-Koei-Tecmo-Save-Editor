# BLUE REFLECTION: Second Light original Steam PC

The [parser](../src/koei_editor/games/blue_reflection_second_light_pc/parser.py)
and [editor](../src/koei_editor/games/blue_reflection_second_light_pc/editor.py)
qualify two observed original Steam PC app 1423600 native gameplay profiles.
Only existing ordinary-container quantity reductions are writable, from the
opened positive count down to 1. Zero/removal, increases, creation, arbitrary IDs
and Max are excluded. Original Blue Reflection, Quartet and console exports
are separate profiles. Edited game loading remains independently untested.

## Native evidence, identity and integrity

[Barrel Wisdom's independently shared original-PC saves](https://barrelwisdom.com/blog/atelier-pc-saves)
provide clear and NG+ pre-final-boss `GameData00/data.dat` and
`GameData01/data.dat` copies. They have 205984 and 213712 native bytes, respectively.
Their mandatory native XOR and additive envelope checksums both pass the
existing [MIT-attributed Gust envelope codec](../src/koei_editor/games/sophie2/atelier_sophie2_codec.py).
The original seed,256-byte header, three opaque footer bytes and zero trailer
are preserved. Unchanged serialization returns the byte-exact original; edited
serialization recomputes both native checksums and independently reparses the
output before acceptance.

Decoded sizes are 790986 and 796231 bytes. The preamble is big-endian 20150729 plus
28 reserved zero bytes; tagged spans are little-endian and scalar/array extents
are predominantly big-endian. Numeric item record words have independently
observed little-endian encoding. Both complete root geometries are explicitly
bounded, including title-specific `SchoolComm`, `SchoolDev`, `LinkSketch` and
`mix_party` blocks. The Party block has fifteen 5374-byte records, version 5/6,
with native IDs 0..11 and three FFFF/empty identities. Item versions 1/2 and
app revisions 1/0 and 1/1 are qualified together. No generic Atelier schema or
Quartet's twenty-record roster is accepted.

Both checksum-valid native streams have an exact final 50-byte `Guide` tail
whose declared span is 54 and whose last word is the length 4 of
`isGuidingScenario`. This narrow adapter validates those exact 50 bytes and
keeps them opaque. It does not interpret the missing value, pad the stream,
append a zero, assert a general truncation/elision rule or expose a terminal
control. Every edited payload must retain the original decoded length and
those exact bytes. Foreign geometry and other malformed tails are rejected.
A native loader or untouched save/re-save pair is still needed for broader
terminal-node interpretation. That uncertainty does not require rewriting the
terminal data to reduce an independently bounded earlier record.

## Existing record and quantity proof

The separately published
[Second Light PS4 patch facts](https://github.com/sterben-Dev10/SaveWizard-Resources/tree/main/SaveWizard-Codes)
label a container quantity operation, anchored at `m_unitContainer`, with a
byte operation 26 bytes after the name and record stride 88 bytes. The original-PC
native node independently has a four-byte big-endian 440000 extent followed by
5000 records of 88 bytes. Counting its 15-character name, NUL and extent puts the
source-backed quantity byte at record +6. The first two little-endian 16-bit
words independently distinguish native instance and item identities;FFFF
identifies empty records. This is source-backed mapping with native-PC
structural corroboration, distinct from a controlled displayed consume pair.
The source has no project-compatible declared licence; only facts were used
for the independently implemented adapter. No code/patch list/catalogue is
copied. Its 255 cheat target establishes neither a natural cap nor safe creation.

The independently shared NG+ copy contains positive quantities at +6, including
1, 2 and 11, and zero at +7. The clear copy retains record metadata with zero
counts and exposes no quantity controls. Zero-count records are not converted
into owned inventory. The backend exposes only count>1, zero-high-byte,
non-FFFF records with instance identity unique across all three native pools.
It writes exactly one byte at +6 and keeps the entire rest of the 88-byte record
unchanged. Count 1, zero, unknown/high-byte, duplicate-identity, important and
expendable pool records stay read-only.

| Pool | Bounded native geometry | Operation |
| --- | --- | --- |
| Ordinary container |5000 records ×88 bytes | Qualified positive count reductions,1..opened; no Max. |
| Important container |300 records ×88 bytes | Inspection only. |
| Expendable container |50 records ×88 bytes | Inspection only. |
| IDs, quality, traits/effects and equipment references | Existing opaque bytes | Preserved exactly; no replacement or derived-effect claims. |

The backend uses immutable documents, stable field IDs, full pending-map
validation, exact typed no-op/unstage, native edited read-back and shared safe
storage. Save As requires a new copied destination, source-change checks and
automatic backups. Restore validates the bounded bytes it writes. Live
Second Light save folders are excluded.

## Mechanics and remaining limits

The [official crafting manual](https://www.koeitecmoamerica.com/manual/brsl/3200.html)
distinguishes owned materials, memories/recipes and helper effects.
[Coins](https://barrelwisdom.com/second-light/items/coin/en) are a craftable Tool;
the inherited `money` and `Jewel` tags are not exposed as verified currency.
[Talents/TP](https://www.koeitecmoamerica.com/manual/brsl/7200.html) have cumulative
levels, spendable points, linked Ao rewards and story prerequisites. Fragment
ownership/equipment, school facilities, dates/friendship, exploration, requests
and story have their own prerequisites/rewards. All remain read-only and need
native action/reference maps before broader writes. Reducing an existing
ordinary-container count neither crafts a recipe nor claims a reward.

[Focused tests](../tests/test_brsl_pc.py) cover both exact root profiles,
checksums/corruption, title/Party/tail rejection, duplicate/empty/unusual records,
bounds, one-byte surgical edits, original envelope metadata retention and
byte-exact no-op. Shared scalar contracts cover staging, read-back and safe
file operations. The optional `BRSL_PC_SAVE_COPY` genuine test passed on the
NG+ native copy, including surgical reduction, new-copy Save As, native checksum
read-back, backup and exact restore. The native clear copy independently passes
all codec/structure checks with zero editable fields. This is source-backed
writer qualification and genuine-file evidence, not independent edited
game-load/re-save evidence. No game binary was executed or distributed.

# Uncharted Waters: New Horizons — original English DOS

The adapter targets the original English DOS `KOUKAI2.DAT` layout: a 151-byte
directory followed by ten 31,944-byte slots, totaling exactly 319,591 bytes.
It accepts separate `.dat` copies. Console editions, translations, emulator
snapshots, remake data and unrelated files are not accepted.

Existing occupied slots offer carried gold in **coins** and eight named
protagonist attributes: Leadership, Seamanship, Knowledge, Intuition, Courage,
Swordsmanship, Charm and Luck. Natural limits are 600,000,000 coins and 100 for
each attribute. 10,000 coins equal one ingot. Max preserves values already above
those limits, and assigning an unusual opened value unstages an edit. Empty
slots never acquire editable controls or newly generated gameplay state.

## Sources, framing and complete writer

[JohanLi/uncharted-waters-2-research](https://github.com/JohanLi/uncharted-waters-2-research)
publishes an MIT-licensed DOS save editor and detailed original-game mechanics.
Its [format.ts](https://github.com/JohanLi/uncharted-waters-2-research/blob/main/save-editor/format.ts)
has the complete native raw writer, including `setGold` and
`setProtagonistStats`. Its
[server.ts](https://github.com/JohanLi/uncharted-waters-2-research/blob/main/save-editor/server.ts)
returns the entire modified save buffer directly. There is no encryption,
checksum, compression or reconstruction layer in that output path. This
adapter independently implements the format facts; no source implementation,
asset, font, name catalog, port map or ship template is copied. It does not use
the external editor's automatic weapon/armor replacement, ship conversion,
location changes or other bundled side effects.

The external writer originally exposes slot one. Its explicit slot-offset
function and all ten slots in the original reference establish the repeated
layout; this adapter independently supports the qualified occupied slots only.
Native directory entries begin at `1 + slot_index * 15`, with a twelve-byte
date label and protagonist ID at +13. An empty date label denotes an unused
entry. Occupied labels follow the English `Mon/dd/yyyy` representation.

| Structure | Exact mapping |
| --- | --- |
| Slot | `151 + slot_index * 31944` |
| Current date/time | Slot +6 year offset from 1501, +7 zero-based month, +8 zero-based day, +9 twenty-minute ticks |
| Current port | Slot +10, 0–129 or 255 for at sea/unused |
| Carried gold | Slot +`0x60A`, unsigned LE32 |
| Sailor array | Slot +`0x612`, 120 records of 42 bytes |
| First six protagonists | Sailor IDs 0–5, native LE16 record identity at +18 |
| Sailor name | Two null-terminated ASCII components, nine bytes each |
| Eight attributes | Sailor +20 through +27, one byte each |
| Levels | Sailor +28 Navigation, +29 Battle; read only |
| Experience | Sailor +30 Navigation LE16, +32 Battle LE16; read only |
| Fame | Slot +`0x5B6` + protagonist ID *14; trade/piracy/adventure LE16 at +0/+2/+4 |
| Port array | Slot +`0x4F40`, 130 records of 20 bytes |

Title/locale qualification uses exact file geometry, original English native
framing anchors (`Joao Franco` in protagonist record zero and `Lisbon` in port
record zero), all six protagonist record IDs in every slot, occupied label,
protagonist, calendar and port bounds. Wrong geometry, locale anchors, native
record identities and malformed occupied framing are rejected. All other bytes,
empty slots, unusual attributes and currencies, story, rewards, equipment,
ships and unknown directory metadata remain intact.

## Reference evidence and validation boundaries

The repository publishes an individual original
[`raw/KOUKAI2.DAT`](https://github.com/JohanLi/uncharted-waters-2-research/blob/main/raw/KOUKAI2.DAT)
reference with the full original English arrays. Its directory has **ten blank
slot labels**, and the initialized slot bodies are repeated. This is a native
initialization/reference file, **not an independently authored occupied player
campaign**. The adapter accepts it for unchanged roundtrip and read-only slot
inspection and correctly offers zero writable fields.

The reference was obtained individually for private qualification. No game
executables, whole-game archives, art, fonts or other game assets were downloaded
for this adapter, and the reference is excluded from source/release downloads.

Support is explicitly **published-format**: `published_format=True`,
`sample_verified=False`, `editing_verified=False`, `game_load_verified=False`.
The full original reference proves title, array geometry and byte-exact native
roundtrip. The complete public native writer establishes raw integrity and field
write semantics. Occupied-record edit tests are procedural, not native occupied
campaign checks, and no edited file has been loaded in the original game.

## Mechanics coverage checklist

The source's [stats mechanics](https://github.com/JohanLi/uncharted-waters-2-research/blob/main/game-details/stats.md)
establish attributes as directly stored values capped at 100 wherever raised,
without equipment modifiers. The
[level mechanics](https://github.com/JohanLi/uncharted-waters-2-research/blob/main/game-details/levels.md)
distinguish Navigation and Battle levels from their separate progress counters:
the next-level threshold is `30 * min(level, 18)^2`, capped at 9,720, and gaining
levels triggers dependent attribute rolls. Those differences are kept explicit.

| System | Implemented feature or specific blocker |
| --- | --- |
| Carried gold | Occupied-slot edits 0–600,000,000 coins; no bank balance or purchase/reward flags changed. Cap is source-correlated to original executable mechanics. |
| Eight protagonist attributes | Independently editable 0–100; Max preserves higher existing values. Other protagonist records remain inspection only. |
| Slot search and named records | All ten slot states; occupied protagonist/date/gold/levels/fame and six existing protagonist records per occupied slot. Names are read from the save itself. |
| Navigation/Battle levels and EXP | Inspection only. Missing controlled native action pairs proving safe level/XP/attribute-roll edits together. EXP is progress toward the next level, not lifetime EXP. |
| Fame, ranks and royal missions | Three distinct fame values inspected. Safe write ceilings, prerequisite/reward and appointment dependencies are not qualified; no automatic ranks or story rewards. |
| Ship construction, durability, crew, provisions and cargo | Detailed source leads exist. Missing occupied native campaign validating owned ship instances, fleet/supply references and coupled capacity/crew/cargo changes. No copying external editor's bundled Tekkousen conversion. |
| Inventory, equipment, discoveries and contracts | Missing qualified occupied inventory/reference evidence and acquisition/equipment/reward dependencies. No weapon/armor injection or replacement. |
| Bank, ports, date/time, affiliation, companions and story | No writes. Location changes in the external editor are explicitly experimental and require original map assets; excluded. Story and ownership remain separate from attributes and resources. |

## Tests and remaining inputs

`tests/test_uncharted_waters2_dos.py` checks a distinctive procedural two-slot
campaign for all gold/attribute edits, limits and types, staged review/unstage,
higher-original preservation during Max, empty-slot exclusion, immutable
snapshot validation, wrong size/locale/identity/calendar rejection, full unknown
byte preservation, backups/restore, existing destinations, changed sources and
the final source check after backup immediately before atomic Save As. An actual
Tk workflow opens the procedural `.dat` copy, uses named controls, edits, undoes,
reviews, changes theme, saves and restores it. Optional `UW2_DOS_REFERENCE_COPY`
checks the unchanged original initialized reference and its zero writable slots.

The next essential input is an independently shared **occupied original English
DOS `KOUKAI2.DAT` campaign** with edition/creation history. Controlled before/after
gold spending or stat growth pairs would additionally corroborate field semantics
and natural limits. Original-game edited loading/re-saving remains unperformed.
Other languages and console platforms need their own layout/title proof before
support can be extended.

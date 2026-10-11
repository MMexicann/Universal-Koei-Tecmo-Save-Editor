# Berserk and the Band of the Hawk — PS Vita EU

The `berserk_vita` adapter edits complete decrypted **PCSB01085** gameplay
exports using their original `sce_sys/param.sfo`. It supports the observed
960,512-byte revision-2 `app0000.dat` / `app0002.dat` layout. Windows and Japanese
Vita formats remain separate. Console decryption/authentication and reimport
remain the responsibility of the Vita save manager.

## Native and writer qualification

[EvilGoku's published Vita editor](https://gbatemp.net/threads/release-berserk-and-band-of-the-hawk-save-editor.503586/)
contains a complete managed .NET editor. It was inspected statically, never run.
Its full Save handler opens the selected file, seeks to a selected status record,
writes one little-endian `u32` EXP and five little-endian `u16` status values,
seeks to Gold and writes one `u32`, seeks to the selected material and writes one
byte, then closes the stream/writer. There are no native cipher, checksum,
serializer reconstruction or metadata mutations in that path. The ListBox read
handlers independently read those same offsets and widths. The material name
order comes from its actual UI initialization, rather than a guessed inventory
catalog. No third-party implementation or binary is incorporated or distributed;
no source licence was supplied, so only independently verified format facts
are used.

[Apollo's public Vita corpus](https://github.com/bucanero/apollo-saves/tree/master/PSV/PCSE01034)
provides two distinct full gameplay files with the above geometry. **The repository
folder says PCSE01034, but the original PSF1.1 metadata actually identifies
`PARENT_DIRECTORY=/PCSB01085`.** The adapter follows the original native metadata
and supports the EU profile. The reference editor titles itself US; matching
native EU record geometry qualifies the fact mapping, while US support still
requires a genuine original US export. Neither directory labels nor a sibling
edition are treated as native identity proof.

Both acquired files pass byte-exact no-edit roundtrips. All nineteen exposed
fields were individually changed, re-read and compared: only the selected
field's byte span changed. Full character and adjacent currency/history bytes
stay identical. This is native-file qualification and static writer evidence;
an edited save has **not** been loaded in the game by this project.

## Observed layout and controls

| Record | Native storage | Implemented behavior |
| --- | --- | --- |
| Complete gameplay | 960,512 bytes; exact observed 32-byte revision-2 header; two native roster ID arrays at `0x44` and `0x54` | Rejects truncation, extra bytes, other headers/rosters and foreign/missing Vita metadata. |
| Spendable Gold | Little-endian `u32` at `0x3774` | Reduce the opened balance only; preserve all adjacent history and unusual opened values. Max disabled. |
| Ordinary enhancement materials | 18 bytes at `0x3690 + index` | Manual quantity 0–99 only for opened records whose original quantity is 1–99. Zero and unusual records are preserved and not activated. The editor range is not claimed as a natural gameplay maximum; Max disabled. |
| Character status | Eight 384-byte records starting at `0xF0`; `u32` EXP followed by five `u16` words | Searchable inspection of EXP, vitality, attack, defense, technique and an unknown word. No growth/status writes. |

The material controls are Red/Blue/Yellow/Brown/White/Black Stone, Ruby,
Aquamarine, Topaz, Amber, Quartz, Jet, Fire Ruby, Water Aquamarine, Wind Topaz,
Earth Amber, Light Crystal and Black Crystal, following the reference writer's
UI order. This name map does not imply a mapping for accessories, skill colors,
rarities or reward records.

Only the first four character names are unambiguous in the source: Guts,
Griffith, Casca and Judeau. The reference labels for the remaining four carry
question marks; the inspector therefore uses character slot numbers for them.
The unknown fifth status word is not called a specific mechanic.

## Mechanics coverage and remaining blockers

The [official game manual](https://store.steampowered.com/manual/502280) explains
that the shop buys/sells accessories and materials, and enhancement consumes
matching-color materials (printed pages24–26). The native Vita editor independently
establishes the selected stored resource records. The manual is a mechanics
reference; its Windows edition does not establish any Vita offsets.

| Mechanic | Status / specific missing proof |
| --- | --- |
| Gold and existing ordinary materials | Implemented with manual edits, named search, review, Undo and safe copy saving. Natural limits and zero-record acquisition flags need controlled acquisition/purchase pairs before Max or discovery edits. |
| Character levels, EXP and status growth | Read-only. Levels reach99 and EXP also affects stats and available actions (manual p27); the dependent updates and later four native identities need controlled level-up/resave pairs before writing. |
| Accessories, equipment, skills and reinforcement | Not writable. Three accessories can be equipped, each can carry four skills, and amalgamation consumes another accessory (pp25–29). Need occupied-record IDs/geometry, equipped references, four skill IDs/ranks, reinforcement/class encoding and controlled enhancement/amalgamation pairs. |
| Character-specific action unlocks, frenzy and death-blow gauges | Not writable. Need persistent-versus-runtime classification, prerequisites and native action/ownership records. |
| Horses | Not writable. Scenario/condition unlocks and charge/endurance/speed are separate (p30); need ownership, horse IDs and selected references with controlled equip pairs. |
| Story battles, behelits, gallery, music/movies and character/costume unlocks | Not writable. Need independent clear/reward/claim/ownership records and controlled single-action pairs. Resource edits never complete story or claim rewards. |
| Endless Eclipse, desires and active runs | Not writable. Depth/checkpoints, per-character rewards, shared first clears and temporary run resources differ (pp31–32). Need controlled floor/desire/claim pairs and the native slot/partner relationship before progression writes. |
| Other regions/revisions | Need a complete original decrypted export and its original metadata; US `PCSE01034` is not inferred from a download folder name. |

Keep the entire original exported directory and its other `app*.dat` partners.
This adapter edits one opened file and never rewrites `sdslot.dat`, another
partner, metadata, signing fields or console account data. Reimport into the
matching game/profile using the existing save manager.

## Storage and tests

Immutable original snapshots, staged edits, batch Undo, Review Changes and the
shared search/inspector GUI are used. Reads, backups, Save As and restores bind
the original metadata digest; changed or different metadata cannot be used for
saving/restoring the opened snapshot. Save As requires a new destination with
the same unchanged original companion metadata. Backups preserve the original
raw save; destination writes and restores use shared atomic storage.

`tests/test_berserk_vita.py` covers generated opaque-byte preservation, all field
spans, invalid/unknown/dependent fields, foreign revision/metadata rejection,
unusual/zero/sentinel preservation, source changes, metadata changes, forged
restore rejection, backup/restore and actual Tk search/Undo/review/save workflows.
`BERSERK_VITA_NATIVE_DIR` optionally selects a private directory containing both
reviewed native copies. Fixtures and owner-bearing metadata are never committed.
The copied self-test creates only minimal public title metadata, never console
account/signing fields; it is not a console-reimport bundle.

# Romance of the Three Kingdoms III — original Traditional Chinese DOS

## Current qualification

An independently implemented parser, staged native writer and shared GUI exist
for the **662,640-byte original Traditional Chinese `SANGOKU3.SAV` profile**.
The scoped profile is registered after independent review. The acquired native file
is an initialized installation file with ten empty slots; it is **not an occupied
player campaign**. Native unchanged roundtrip and empty-slot GUI opening were
checked. Occupied-record edits, preservation and GUI workflows were checked with
explicitly procedural tables. Edited game loading has not been performed.

The exact native signature is ASCII `1992.01.08`. The same signature occurs in
the separately acquired 648,710-byte English initialized file; a signature alone
cannot select an edition. English, Japanese, console and reconstructed builds
are rejected. The Japanese writer's declared 605,520-byte layout has 62-byte
officers, whereas this profile has 49-byte officers.

## Source and complete native writer

[BeckYang/San3Mender, pinned c0e6b4ac](https://github.com/BeckYang/San3Mender/tree/c0e6b4ac8facb774ef88403d1011935a3789c8b8)
is an existing Traditional Chinese/Japanese DOS save editor. Its README describes
opening `SANGOKU3.SAV`, selecting existing records, editing and saving, and states
that its bounds follow game rules. `SaveState.save()` opens the native file for
read/write, seeks each changed city/country/officer record and writes its native
record bytes. `City.toRaw()` and `Person.toRaw()` preserve their original record
buffers and replace mapped bytes. There is no additional cipher, checksum,
compression, signing or whole-file normalization in that complete save path.

No licence declaration was found in this source snapshot. This project uses
independently implemented format facts and does not redistribute its code,
glyph mappings, city/officer catalogues, game data or external binaries.

The original initialized TC native file was acquired from the public
[Chinese DOS game catalogue entry](https://dos.zczc.cz/games/%E4%B8%89%E5%9B%BD%E5%BF%973/).
Only its native save member was retrieved with HTTP byte ranges from the archive;
ZIP size and CRC were checked before private qualification. No game executable
or asset member was extracted or executed. The complete English native member
from [lemon-teapot/rotk3](https://github.com/lemon-teapot/rotk3) was independently
retrieved in the same way and establishes a concrete incompatible edition.
Neither file is included in the repository or downloads.

## Exact storage and identity

| Record | Absolute base / stride | Meaning |
| --- | --- | --- |
| Signature | `0..9` | ASCII `1992.01.08` |
| Slot directory | `10 + slot * 14`, ten records | LE16 year, month at `+2`, city at `+4`, scenario at `+5`, difficulty at `+6`, six native glyph bytes at `+7` |
| Slot allocation | Slot stride `0xCE01` | Zero-based slot ID; offsets below are absolute first-slot bases |
| Cities | `0x1B8 + slot * 0xCE01`, 45 × 74 bytes | Four signed officer references at `+8/+10/+12/+14`, native four-byte city name at `+65` |
| Officers | `0x544E + slot * 0xCE01`, 600 × 49 bytes | Signed next-officer ID at `+3`, stored six abilities at `+16..21`, six native name glyph bytes at `+42` |

The file has an additional native tail beyond ten strides plus the 150-byte
signature/index region. **527,520 bytes is not a qualified TC file size**; it is
only an arithmetic boundary and was initially considered before the actual
native member disproved that size assumption. The entire acquired 662,640-byte
file, including the tail, remains intact during writes. An external editor's
“every other size is TC” fallback is not used.

An empty slot has year/month/scenario zero and city/difficulty `255`. Its body
allocation may contain unrelated initialization bytes and is never interpreted
as cities or officers. No field can create an occupied slot. Occupied indices
require month `1..12`, scenario `1..6`, city ID `0..44` and difficulty `0/1`.
Occupied city tables require 45 nonzero distinct native names; officer references
must be in their native array or use the source's negative terminal convention.
Existing officer chains must be acyclic. Existing officers are identified by the
source's positive signed War/Intelligence admission; unusual unsigned values
are not converted to ordinary records.

## Writable scope and mechanics checklist

| Mechanic | Implemented scope / precise limit |
| --- | --- |
| Officer abilities | Existing ordinary Land Command, Naval Command, War, Intelligence, Politics and Charisma at `+16..21`; manual edits `1..100`, as explicitly bounded by the original working editor. Zero/unusual ability fields remain read only. No Max action or inferred natural-cap claim. |
| City currency/food | Existing owned-city Gold LE16 `+26` and Rice LE32 `+28`; reduce only from the opened balance. A city's existing mayor must reference an admitted officer with ruler ID `0..20`. Unclaimed/unqualified cities remain inspection only. |
| Commerce | Existing city LE16 `+46`, reduce only. Commerce is a city value rather than spendable cash; no Max or storage-ceiling claim. |
| Existing military supplies | Crossbows `+50` LE16, Heavy Crossbows `+52` LE16, War Horses `+54` LE16, Warships/Heavy Ships/Light Ships `+57/+58/+59` bytes; reduce existing balances only. These do not create equipped units, troops or city ownership. |
| Development, cultivation, irrigation, flood control, civil loyalty | Searchable read-only city values. Their effects on seasonal production, disaster handling and political state require independent dependency proof before safe bulk increases. |
| Troops, training, morale | Searchable read-only officer values. These differ from the six abilities; morale's external editor range is 120, not an assumed generic stat cap of 100. Troop/supply/battle dependencies are not edited. |
| Officer loyalty, treasure and equipment effects | Read only; no transplant from officer base abilities or guessed changes to derived bonuses. |
| Ownership, officer relocation/roles and linked lists | Read only. The external writer has explicit multi-record relocation/death/appearance handling; this implementation never changes those records or reference chains. |
| Orders, work, rewards, scenario completion and calendar | Read only and independent from manual abilities/resource deductions. January appearance and death events are not cancelled by stat edits. |
| Custom names | Native glyph IDs are searchable. No copied restricted glyph catalogue or guessed Big5 decoding; user-created glyphs and their unknown tail storage are preserved. |

All controls have stable slot/record IDs. The three searchable inspectors show
slot status, cities and officers; ordinary record IDs are used where native names
cannot be independently decoded. Source copies are immutable, assigning the
opened value unstages an edit, Max performs no changes, and unknown bytes remain
untouched. Saving uses fresh structural readback, automatic backups, atomic new
destinations and changed-source/live-game-folder protection. Restore verifies
the bounded bytes against the game-specific backup manifest and parser.

## Checks and remaining inputs

`tests/test_rotk3_dos.py` covers two noncontiguous procedural occupied slots,
every exposed field's independent offset/width surgery, combined edits, untouched
indices/empty slots/tail, unusual abilities, ownership, malformed/foreign builds,
cycles, bounds, malformed field IDs, forged snapshots, source races, alias/new
destination protection, backup damage/wrong-game rejection and actual Tk
Apply/Undo/Review/Save As workflows in both themes.

`ROTK3_DOS_INITIAL_COPY` privately enables initialized native byte-exact roundtrip,
empty-slot qualification, safe unchanged Save As and actual GUI opening. These
tests do **not** validate editing an occupied genuine save. No fixture, hash of a
player campaign, personal path, glyph table or account information is published.

Remaining priority: an independently shared or owner-supplied **occupied original
Traditional Chinese `SANGOKU3.SAV` of this exact native profile**, plus an unchanged
re-save and controlled officer-ability/city-resource pair. These establish actual
record admission and edited game-load/re-save acceptance. Japanese/English input
would require independent identity/geometry qualification rather than selecting
this parser after another edition fails.

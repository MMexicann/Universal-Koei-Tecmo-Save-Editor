# Atelier Meruru Plus — US PlayStation Vita

The editor opens **decrypted PCSE00296 gameplay exports**. It edits Cole and
six base stats for 13 named existing character records, and reduces their
opened current HP/MP/LP gauges. Character and numeric inventory inspectors
are searchable. It preserves level/EXP, skills, equipment, ownership, quests,
calendar, development, story and every unknown byte.

This is the original **Vita Plus** profile, not Meruru DX PC, PS3, PS4 or
Switch. [MERURU_DX_FORMAT.md](MERURU_DX_FORMAT.md) records the distinct PC
investigation and remaining integrity blocker.

## Open and reimport

Export/decrypt your own save using a suitable Vita save manager or Apollo.
Make a separate copy of the entire exported folder and open its native
extensionless `USR-DATA0000`. Keep the original `sce_sys/param.sfo` in the
same copied export. Save As writes a new extensionless file; every destination
must have the same unchanged original metadata. Automatic backups, Undo,
Review Changes and restoration are available.

To put the edited file back on the console, use your save manager's supported
import process and the game's native filename. This application does not
decrypt console archives or generate Vita authentication/signing data.

## Format and source proof

[Apollo's public Meruru Plus upload](https://github.com/bucanero/apollo-saves/issues/385)
explicitly identifies the title and provides a decrypted export. Its bounded
PSF1.1 metadata contains `PARENT_DIRECTORY` equal to `/PCSE00296`, unlike PS3's
`SAVEDATA_DIRECTORY` field. The adapter reads only this identity value and
never extracts account or signing fields. It stores a digest of the complete
original companion to detect changes without disclosing its contents.

The native gameplay file is 558,080 bytes with little-endian magic 20100403,
a 32-byte header and 24 sequential `(u32 tag, u32 payload_length)` records:

```text
46120, 6972, 4, 5628, 179724, 121, 100768, 4, 6968, 1,
8, 68, 604, 2030, 8, 3584, 95968, 1469, 84, 384, 94260,
4800, 108, 80
```

Final tag 1024 is at **0x86465**, stored length 8091 **including** its eight-byte
header. All lengths, identities and bounds are validated. In particular tag 14
has 2030 bytes and tag 23 has 108 bytes; DX PC has 2220/128 respectively and is
rejected. Reserved header and trailer payloads are opaque and preserved;
zero values are not used as checksum evidence.

The [published Remumu Vita editor and author/user discussion](https://gbatemp.net/threads/release-remumu-atelier-meruru-save-editor.443645/)
provide independent writer evidence. The complete `ProcessSave` and `ExportSave`
methods in the freely shared version 0.8 binary were inspected **statically**.
The binary was never executed, distributed or imported into this project.
No reusable source licence is established; only factual offsets, widths and
writer behavior are recorded, with an independent implementation here.

Its complete export method writes the unchanged original bytes, then patches
Cole, the calendar word and 11 character words per record, and closes the
stream. No checksum, crypto or integrity helper is called. The author identifies
Cole and character stats as working; a user reports no further bugs. The
item writer is explicitly unfinished and absent from that export method.
The genuine Vita export independently matches these field positions, 13 ordinal
identities and the full platform fingerprint.

This establishes patch-only **game-internal** handling for the qualified Cole
and character spans. External Vita save authentication remains the save
manager's responsibility. It is not a claim that arbitrary regions, other
builds or the later DX PC port share that integrity model. Edited loading with
this new application has not been performed.

| Stored field | Native mapping | Editor behavior |
| --- | --- | --- |
| Cole | Tag 3, four-byte little-endian word at 0xCF9C | Manual 0–9,999,999; no natural-cap or Max claim |
| Character identity | Tag 4 at 0xCFA8, stride 0x1B0, 13 records, first word 0–12 | Every identity must match; never changed |
| Level / EXP | Character+4/+8, u32 little-endian | Inspection only; no threshold/skill grants |
| Current HP / MP / LP | Character+0x0C/+0x10/+0x14, u32 little-endian | Decrease only, up to the original opened value; HP minimum 1, MP/LP minimum 0 |
| Base HP / MP / LP | Character+0x18/+0x1C/+0x20, u32 little-endian | Increase only from the original value, within the manual 0–999 limit; HP minimum 1; no Max |
| Base attack / defense / speed | Character+0x24/+0x28/+0x2C, u32 little-endian | Manual 0–999; no Max |
| Observed item records | Tag 7 at 0x3A441; 2099 records of 48 bytes | Searchable numeric inspection only |

The manual stat ranges are conservative editor limits within the reference
writer's unsigned storage width. They are **not** claimed legitimate gameplay
maxima. Higher or unusual original values remain byte-identical unless the
user deliberately replaces them; assigning an opened value unstages the edit.
All fields have `maxable=False`.

The Vita reference's ordinal character order is Meruru, Keina, Lias, Mimi,
Gino, Sterk, Esty, Gio, Totori, Rorona, Rufus, Hanna and Pamela. Original PS3
offset lists use a different ordering and must not be transplanted. Existing
native IDs are preserved and these controls do not recruit anyone or unlock
party members.

The reference's words labelled HP/MP/LP are **base stats**, not effective maxima.
The genuine export has current gauges above these bases because equipment and
traits contribute additional effects. The editor never treats base stats as
refill caps, clamps current gauges to them or changes equipment to enforce a
derived-value assumption. Base changes preserve all current gauges, equipment,
level/EXP and skill bytes. Decreasing a base HP/MP/LP value could put a
preserved current gauge above its new effective maximum; those base fields
therefore only allow increases from the original value. Current-gauge reductions
preserve all base stats.

## Rich-system coverage and remaining blockers

The [official game manual](https://store.steampowered.com/manual/936190)
documents the Arland mechanics retained in DX; the separate Vita writer/native
layout establishes this profile's storage. The distinction between popularity,
population, unspent development points and kingdom rank matters. Requests,
reports, rewards and construction are distinct actions. Full current mechanics
research is in [MERURU_DX_FORMAT.md](MERURU_DX_FORMAT.md).

| Mechanic | Implemented result or specific remaining blocker |
| --- | --- |
| Money | Cole edits; natural cap remains unproved, so Max is disabled |
| Character combat stats | 13 named records; manual ATK/DEF/speed, increase-only base HP/MP/LP; manual limits, no Max |
| Current HP/MP/LP | Existing positive HP and qualified signed-range gauges can be reduced; effective maxima/refill remain blocked by equipment-derived calculations |
| Character level/EXP/skills | Named inspection; need native thresholds and derived skill/stat transitions before direct edits |
| Friendship/support/personal events | Need qualified native affinity records and event/reward thresholds; no raw 100% shortcut |
| Recruitment/party | Native IDs inspected; need availability/recruited/party flags and equipment references before roster edits |
| Existing inventory | Numeric serial, identity, float-quality, trait/effect and use-word leads inspected; the reference does not write items and admits an incorrect quality interpretation |
| Item uses/quantity/deletion/acquisition | Need independent use-versus-stack semantics, original capacity/occupancy, unique serial and equipped/shop-reference rules; no acquisition or refill writer |
| Quality/traits/effects/synthesis | Need independent serialized quality proof, valid item/trait/effect combinations and ingredient cost/rank dependencies; no third-party catalog copied |
| Equipment | Need native equipped references, ownership compatibility and a controlled equip/unequip pair; base-stat edits do not change loadouts |
| Alchemy EXP/level/recipes/books | Need native fields, EXP thresholds and level/book prerequisites; no level/resource conflation |
| Development points/rank/population/popularity | Need exact separate counters, rank thresholds and construction/report/reward dependencies; official mechanics do not establish offsets |
| Facilities/development tasks | Need native task/facility IDs, accepted/completed/reported records, costs and unlock prerequisites |
| Requests/Hom/shop income | Need native task/timer/result schemas and controlled action pairs; calendar tool reports elapsed-time conflicts |
| Exploration/routes/gathering | Need location identities, travel/unlock/encounter prerequisites and reward history |
| Calendar/story/endings/clear state | Reference calendar edits are deliberately omitted; need complete date/year/event transitions and reward prerequisites |
| Library/collections/music/movies | Need title-specific seen/discovered/system records and catalogs; no blanket unlock writer |
| Costumes/groundwork/voice extras | Need owned/available/selected flags and story/system prerequisites |

## Tests and safety

[Parser](../src/koei_editor/games/meruru_plus_vita/parser.py),
[workspace](../src/koei_editor/games/meruru_plus_vita/editor.py) and
[tests](../tests/test_meruru_plus_vita.py) cover immutable documents, every
tag/size/trailer/ordinal identity, DX-PC rejection, all writable fields with
surgical byte comparisons, boundary/dependency rejection, Max exclusion,
higher-value preservation, exact unchanged roundtrips and safe new-file writes.

Backups include a private companion-digest sidecar so restoration requires
the same original metadata. Source and destination changes are checked before
writing. The shared copied-save self-test creates a minimal title-only PSF
containing no account or signing fields; that synthetic identity companion is
for local validation, not console reimport.

Optional genuine-file checks use `MERURU_PLUS_VITA_EXPORT_COPY` for an unchanged
decrypted gameplay copy with original `sce_sys/param.sfo`. All writable families,
backups, restoration and the real Tk Open/Undo/Review/Save As workflow were
checked with the acquired native export. Procedural fixtures are boundary tests
and are never described as playable game saves. No player save, account data,
game binary, external editor or extracted catalog enters source or release assets.

# Monster Rancher DS — US Nintendo DS

This profile edits raw US Nintendo DS backup-memory `.sav` copies with the
native `MonsterRancherDS` signature. The US release corresponds to Japan's
second Monster Farm DS game; the first Japanese game, other regional editions,
DeSmuME `.dsv` wrappers and save states are not qualified by this profile.
Export backup memory to raw `.sav`, copy it outside emulator battery folders,
edit that copy and reimport through the same save manager. No ROM is required.

## Editing and mechanics

- Six stored monster stats: Power, Intelligence, Skill, Speed, Defense and Life
  for occupied current/frozen records that match across both native replicas.
  Species IDs 3, 56 and 156 are individually qualified by genuine occupied
  references. Other species remain searchable and read-only until their native
  ID domain is independently established; numeric IDs are not guessed breeds.
  Manual edits use the ordinary 0–999 range. The six-stat budget is 5994;
  existing unusual totals may be preserved or reduced. Existing Overdrive
  stats above 999 remain unchanged by Max; their other stats also skip Max
  to avoid consuming the budget. Deliberate reductions remain available.
- Extend existing positive remaining lifespan up to 9999 native units. Normal
  weekly time costs ten units; stress, fatigue and tournaments can cost more.
  Frozen monsters do not age while stored. Remaining lifespan is distinct
  from calendar age and growth stage, and peaches can extend it beyond its
  starting value. Max lifespan preserves unusual higher originals; expired
  monsters are not revived and do not expose stat/lifespan writes.
- Change existing canonical printable ASCII breeder, ranch and monster names,
  with twelve-character limits. Empty/unrecognized encodings remain read-only;
  unchanged names retain their exact original padding.
- Reduce existing spendable gold without increasing the opened balance.
  Lifetime winnings, breeder grade and tournament reward state remain intact.
  Gold has no Max action because a natural wallet cap is not established.
- Search both replicas' current/thirty frozen monster records, all fifty
  discrete inventory positions per replica, and ranch/calendar status.
  Selected ordinary items have factual names; other IDs stay visible without
  guessed labels. Inventory records store one item ID each, not stack counts.
  Usable inventory capacity depends on house upgrades, so item additions,
  removals or compaction are not implemented.
- Shared Light/Dark GUI, named records, field/record searching, validated bulk
  actions, Undo, Review Changes, automatic backups, atomic Save As and bounded
  checked restore. Source-copy changes, existing destinations, Steam Cloud
  paths and recognized emulator battery directories are rejected.

The Overdrive mechanic permits individual stats up to 1500 while retaining the
5994 total. This editor does not grant Overdrive, alter monster species,
activate breeding items, raise stats beyond ordinary limits or claim those
prerequisites are fulfilled.

## Native format proof

The complete MIT-licensed
[ExcaliburZero/mrds_extract parser and checksum writer](https://github.com/ExcaliburZero/mrds_extract/tree/90a3c526199a68b07e57ecf7a73d81700440bfd1)
includes `mrds-fix-save-checksums`, a native parser, independent save patterns
and tests with five genuine US gameplay exports. This implementation was
written independently from reviewed structural/checksum facts; no external
runtime dependency, source catalog, save or ROM is incorporated.

The exact 34-byte signature precedes two 15,584-byte entries. Each entry has a
CRC-32 of its first 56 bytes at relative 56 and a CRC-32 of bytes `[0,15580)`
at relative 15580. The body CRC includes the newly calculated header CRC.
The published table uses polynomial `0xEDB88320` and standard initial/final
XORs; independent standard `zlib.crc32` matches every checksum in all five
native files. The physical files are 32 or 64 KiB; all bytes after the two
entries remain opaque and are preserved at their original absolute positions.

| Entry-relative location | Stored field | Proof / write scope |
|---|---|---|
| 10, 27 | Thirteen-byte ranch/breeder name buffers | Published native parser; existing canonical ASCII only, max twelve + NUL |
| 48–52 | Calendar year/month/week/day | Published native pattern; inspection only |
| 70, 140 | Breeder grade, lifetime money won | Published native pattern; inspection only |
| 352 | Little-endian u32 spendable gold | Complete native parser/writer; existing balance reductions |
| 356 | Fifty little-endian u16 item IDs | Complete native parser; inspection only |
| 456 | Thirty-one 420-byte monster records | Published native parser/pattern; current then thirty frozen |
| Monster +0 | Twelve-byte monster name | Native parser and genuine full-length ASCII names |
| Monster +18 | Species ID (`0xFFFF` empty) | Native parser and initialized/occupied genuine references; never modified |
| Monster +30, +32 | Age, remaining lifespan | Published native pattern; age read-only, positive lifespan extension |
| Monster +40…+50 | Six little-endian u16 stats | Complete native parser and native power-edit checksum tests |

Both CRCs in both entries must be valid before any fields are exposed. The
save counter's active ordering is unresolved, so the editor never selects a
winner or copies a complete entry over another. Ranch/breeder names must match
and be canonical before any edits are offered. Gold is eligible only when its
two original balances match. Each occupied monster is eligible only when its
entire original 420-byte record matches in both replicas, its name is canonical
and its species ID is individually qualified and stat words fall in the known
ordinary/Overdrive domain. Unmatched
records and unusual values are preserved. Authorized edits update only the
corresponding spans in both replicas plus their required CRCs, then reparse.

## Mechanics references

- [Source author's MRDS lifespan research](https://github.com/ExcaliburZero/mrds_info/blob/eac2c6c7d129b286f3a1cd4eba4f661e22c2e6f1/docs/monster_raising/lifespan.rst):
  native time units, freezing, zero-life death and legitimate 9999 remaining-life
  ceiling. Facts are paraphrased; no source tables or prose are copied.
- [Source author's item research](https://github.com/ExcaliburZero/mrds_info/blob/eac2c6c7d129b286f3a1cd4eba4f661e22c2e6f1/docs/items.rst):
  fifty-item capacity requires the largest house; consumables, farm effects,
  breeding items, fruit and valuables are distinct systems.
- [Title-specific Overdrive discussion](https://gamefaqs.gamespot.com/boards/946519-monster-rancher-ds/56007220)
  and [stat-limit discussion](https://gamefaqs.gamespot.com/boards/946519-monster-rancher-ds/55923781):
  ordinary 999 stats, 1500 Overdrive stats and unchanged 5994 total budget.
- [Public title-specific item IDs](https://www.almarsguides.com/retro/walkthroughs/NDS/Games/MonsterRancherDS/ActionReplay/ItemIDs/):
  individually cross-checked ordinary ID/name facts used for inspection, not
  ownership writes or a transplanted cheat implementation.

## Coverage checklist and remaining blockers

| System | Status / precise remaining proof |
|---|---|
| Current/frozen six stored stats | Implemented for native-qualified species IDs 3/56/156, ordinary bounded edits, budget checks and preservation of Overdrive/higher values; other IDs need independent catalog/domain proof |
| Remaining lifespan | Implemented positive extension, independently documented ceiling; age/growth unchanged |
| Ranch/breeder/monster names | Implemented canonical ASCII; other native encodings need a verified writer/encoding before rename support |
| Spendable gold | Implemented reductions; increases/Max need independently established wallet range and overflow behavior |
| Calendar, breeder grade, winnings | Searchable inspection; writing needs rank/reward/date dependencies and controlled gameplay pairs |
| Inventory/food/fruit/peaches | Searchable discrete IDs; changes need current house capacity, packed-list behavior and consumption dependencies |
| Passive farm items, house upgrades | Preserved; ownership/upgrade state, effects and prize relationships are not mapped |
| Stress, fatigue, trust, discipline, shape, wit, fame | Important mechanics, but no qualified native field spans/writer; runtime overlay addresses do not prove disk offsets |
| Techniques, training/drill history, growth stages | Preserved; native meanings, costs, learned/equipped dependencies and record domains need qualification |
| Species, fusion, breeder unlocks, Overdrive | Preserved; combination costs, ownership, invitation and breed prerequisites need controlled pairs |
| Tournaments, ranks, major cups, errantry, events | Preserved; no guessed completion/reward masks or story bulk action |
| Encyclopedia and per-breed maximum grade | Published pattern identifies opaque areas; bit/index meanings and unlock dependencies need proof before edits |
| Replica recovery / active generation | Both complete CRCs required; differing valid records remain read-only, no inferred counter order |
| Other editions/containers | US raw native exports only; regional identity/layout and wrapper writer proof needed separately |

## Validation

`tests/test_monster_rancher_ds.py` covers procedural 32/64 KiB frames, all four
CRCs, foreign title/wrappers/extents, replica mismatches, unchanged roundtrips,
surgical edits, ASCII names, empty/dead/unknown records, lifespan bounds,
Overdrive budgets, unusual-original preservation, Max, immutable documents,
backups/restore, changed-source races, live-path aliases and an actual Tk
open/search/stage/Undo/Review/Inspect/Save As/restore workflow.

Private `MRDS_SAVE_COPIES` enables five genuine public source-fixture files:
initialized game, returning-to-ranch snapshots and two later ranch snapshots.
They qualify complete native checksums, exact no-op roundtrips, paired
name/stat/lifespan/gold edits, both physical sizes and safe file workflows.
The initialized empty ranch exposes no fabricated monster or name ownership.
Tests leave originals unchanged. No player names, files or personal paths are
published. Edited-save game loading and subsequent in-game re-saving have not
been performed; genuine-file qualification is not that validation.

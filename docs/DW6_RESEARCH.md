# Dynasty Warriors 6 — original Windows PC

The adapter implements named playable-officer unlocks, existing horse combat
stats, existing weapon element choices, manual stored weapon damage bonuses and
searchable officer/weapon/horse inspection. This is the original Windows game,
not DW6 Empires, PS2 Special, PS3 or Xbox 360. The latest independent bonus
expansion and native/GUI checks are documented in
[Samurai / classic Dynasty editor depth](SAMURAI_DYNASTY_DEPTH.md).

## Provenance and qualification

- [cnopt's public research and reader](https://github.com/cnopt/dynastywarriors6-reverse-engineering/tree/f2152f67b031091a0268154203d25fa9f65d2664),
  pinned to `f2152f67b031091a0268154203d25fa9f65d2664`, documents officer,
  weapon and horse records. Its **Unlocking officers** section compares native
  before/after files, edits `save.dat`, reloads through the game's options, and
  demonstrates newly playable officers. **Warhorses** identifies editable disk
  stats with screenshots and explains the effective 500 limit.
- A freely shared [native PC save](https://savegame.pro/pc-dynasty-warriors-6-savegame/)
  was downloaded and extracted privately. The download contains the native
  `Savedata/save.dat` plus separate input maps. Its actual file is 212,248 bytes,
  readable plaintext, with all 41 canonical officer identities. No player data,
  account context, upstream executable, game artwork or save is distributed.
- The public project has no explicit project licence. This implementation uses
  factual record positions, numeric identities, names and documented behavior;
  it does not incorporate that project's parser code, binaries, dependencies,
  images or assets. Our parser, storage safeguards and tests are independently
  written. The secondary [GUI reader](https://github.com/cnopt/dw6-imgui-save-parser/tree/d021b466d6c00aa9d0679ef8456d9292f3ad3b22)
  is an additional research lead, not an imported implementation.

The strict observed profile requires exactly 212,248 bytes and officer IDs
0–40 in their 41 canonical rows. No independent build/revision marker or native
checksum algorithm was identified. Public successful direct-file reloads
support the original unlock/horse write categories without checksum repair. The
adapter leaves all other bytes untouched; it does not invent a checksum, owner
secret or encryption wrapper. Structural qualification is not cryptographic
authentication, and other sizes/reassigned officer identities are rejected.

## Record proof and writable scope

Officers start at decimal 2,904 with 168-byte records. The reader consumes four
bytes after its nominal seek before reading the first value; blindly copying
the nominal seek would shift every field. The actual records contain eight
skill-tree bytes, eight 16-byte weapon entries, then identity at +136, outfit
+140, title +144, stored level index +148, EXP +152, kills +156, selected weapon-slot
word +160 and a one-byte playable value +164 with three opaque neighbors.
The 64-bit skill-mask and complete horse geometry are documented in the
[new cross-platform mapping](DW6_CONVERSION.md). The source's Xu Huang unlock at hex `1874`
matches row 19's +164 exactly. Canonical officer names and weapon IDs are
corroborated by the private native sample.

Playable values 0/1 are editable as a **one-way unlock**. Unknown values stay
read only. Unlock All Qualified Officers is a separate action and does not
change story, rewards, skill trees, levels or equipment. Resource Max excludes
all unlock flags.

Eight 60-byte horse rows start at decimal 10,784. Their initial stat group
matches the documented native record: EXP +0, type +4, element +8, skills +12,
Speed +16, unqualified adjacent value +20, Attack +24, Jump +28 and Destruction
+32. The research's explicitly named memory entries establish that order; the
disk screenshot corroborates the initial stat group and 60-byte spacing.
Writable horse rows require an observed type (60, 61 or 64), positive adjacent
value and four positive combat stats. Empty, unknown and unusual variants stay
read only. Speed, Attack, Jump and Destruction accept 0–500; the documented
effective ceiling is 500. Max preserves higher existing values. Returning to
an unusual opened value unstages an edit. EXP, skill mask, type, element,
descriptors, model, names and all other bytes are preserved.

The weapon inspector recognizes 123 known weapon IDs, shows eight existing
slots per officer, and omits the documented empty ID 174. Unknown IDs and masks
remain visible as numeric/raw values. Damage is a **bonus over weapon base
damage**, not total attack. Existing known weapon elements now support deliberate individual edits. The native reader maps each 16-byte record to four independent u32 values: ID, damage bonus, element and skill mask. Its explicit enum is 0 Fire, 1 Ice, 2 Lightning and 3 Standard (no element). Element is a choice rather than an ordered upgrade and is excluded from every Max action. Only an original known weapon ID with an original known element qualifies; empty ID 174, unknown IDs and unknown element values remain read only. An element edit preserves identity, damage bonus, skill mask, inventory, officer progression and every other byte. This does not establish damage limits or skill acquisition dependencies.

Stored damage bonuses are now individually editable on the same qualified
existing known weapon records. The bonus is the independent u32 at weapon `+4`,
not total attack; identity, element, mask, inventory and officer growth remain
unchanged. Its manual unsigned 32-bit bound is a storage limit, excluded from
Max. The published tentative value 32 and displayed attack limit do not prove
a natural bonus maximum. No weapon acquisition or skill-mask writes are added.

## Coverage and exact remaining inputs

| System | Implemented or precise blocker |
| --- | --- |
| Playable characters | 41 named, qualified 0→1 unlocks; separate bulk action; relocking unavailable. |
| Horse combat stats | Four existing-record stats and validated bulk Max, preserving higher values and other horse state. |
| Officer level/EXP and derived stats | Read-only stored values. Level changes alter Life/Musou/Attack/Defense; EXP alone does not immediately level. Need controlled level-up/EXP pairs or the native PC executable's level/reward routines before exposing progression edits. |
| Officer identity, title, outfit and kills | Read-only. Identity can redirect inventories/progression; title affects stat distribution. Need independently identified title/outfit domains, eligibility and update dependencies. Identity replacement is deliberately unavailable. |
| Officer skill trees | Read-only raw eight-byte data. Per-officer nodes/counts differ; broad FF writes in old research do not identify every valid node or reserved bit. Need node maps, level/prerequisite rules and controlled allocation pairs. |
| Weapons and equipment | Named inventory, manual existing-element choices and independent stored damage bonuses on qualified existing weapons. Bonus edits use u32 storage bounds with no Max; the proposed “32” maximum and display limit remain unproven natural caps. Skill mask and equipment references stay read only. Need native natural bonus bounds, equipped references, rank/weapon-type eligibility and controlled acquisition/equip pairs. |
| Weapon elements / skills | Existing known element enum writable individually, excluded from Max; native sample contains all four valid choices. Skill masks remain read only: published lists describe skills but do not prove every bit, valid combinations or five-slot enforcement in disk records. Need exact masks, enum/slot limits and acquisition/write-path proof. |
| Horse EXP/level/growth, names, type and model | Read-only. Growth descriptors and model transformation are interdependent. Red Hare requires the relevant coat, eyes/physique, level and Wind Spirit conditions; changing a type/model alone does not create a legitimate horse. Need complete descriptor offsets/enums and controlled growth/transform pairs. |
| Horse skills/elements | Read-only. Skills are a combined mask with a four-skill limit. Need complete bit semantics and native mutation/slot rules before writing masks. |
| Stages, difficulty records, objectives, challenges and leaderboards | Preserved. Public runtime identity changes also affected challenge results, showing dependencies. Need native disk field maps and controlled clear/objective/reward pairs, separate from playable unlocks. |
| Gallery, movies, music, costumes and collections | Preserved; no qualified disk flag maps. Need controlled unlock/view/equip pairs and legitimate prerequisites. |
| Currency, bonds, companions/bodyguards, fusion, reinforcement and other inventories | No safely identified independent DW6 disk systems in the inspected evidence. No fields or mechanics are invented from systems in later games. Further controls require proof that the specific system exists and is saved. |
| Other platforms/editions | Not supported by this adapter. Need a complete native fixture, its platform/container/integrity specification and independent field mappings. A PC record map does not qualify DW6 Empires or console saves. |

## Validation

Nine format tests, three registered adapter contract checks and one GUI workflow
passed with the private native fixture enabled. The opt-in `DW6_SAVE` test verifies genuine unchanged roundtrip,
inspection and surgical horse edits; no native save is committed. Procedural
checks cover foreign sizes/identity, frozen snapshots, bounds, unusual values,
separate unlocks, unqualified/empty horses, byte preservation, backups, validated
restore and changed-source rejection. The GUI test covers named search, separate
unlocking, Apply, Max, Undo, Review Changes, searchable inspectors, themes,
copy-only save and backups.

Public author game-reload evidence supports the mappings. **This project has
not performed an edited in-game load or re-save.** Such validation requires the
original Windows game plus controlled saves from a player; it remains distinct
from successful parser and GUI tests.

## Unreleased weapon-element expansion checks

`tests/test_dw6_elements.py` adds named existing-record selection, all four valid choices, surgical single-word writes, unknown/empty records, invalid values, choice exclusion from Max, review/unstage and guarded new-copy/backup/reopen checks. With `DW6_SAVE` pointing to the privately held independent native sample, all **202 qualified existing weapon element fields** passed individual surgical edits and reparsing; the sample contains Fire, Ice, Lightning and no-element records. The combined existing format/contract and new element checks passed **19 tests** with the native fixture. No player save, source parser code or asset is included, and no new edited in-game load is claimed.

The underlying public research remains pinned to `f2152f67b031091a0268154203d25fa9f65d2664`; the independent implementation uses its factual enum and record positions. Its lack of an explicit project licence still precludes copying its implementation.

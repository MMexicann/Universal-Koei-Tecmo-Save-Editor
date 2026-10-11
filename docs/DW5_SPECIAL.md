# Dynasty Warriors 5 Special — Windows equipment and stored-stat editor

This is **Shin Sangokumusou 4 Special / 真・三國無双4 Special**, the Windows
Special edition. **Dynasty Warriors 5 Special** is the corresponding Western
series numbering; that name alone does not establish a Western Windows release.
It is distinct from DW5/XL on PS2, DW5 Empires, and Shin Sangokumusou 5 Special
(DW6 Special).

Open a separate copy of the native `save.dat`, originally stored under
`Documents/KOEI/Shin Sangokumusou 4 Special/Savedata/`. This adapter supports the
46,000-byte profile with either qualified header marker `0x00000003` or
`0x00010003` at byte offset 4. It does not convert memory-card containers or
support console formats.

## Regional qualification

Product existence and native-format qualification are separate:

| Product / regional title | Product evidence | Save evidence and current scope |
| --- | --- | --- |
| Japan: 真・三國無双4 Special / Shin Sangokumusou 4 Special, Windows | [KOEI's 2006 history](https://www.gamecity.ne.jp/history_2006_1.htm) records the Windows launch on June 22, 2006; the [Windows product page](https://www.gamecity.ne.jp/smusou4sp/win/) also remains available. | No separately provenance-qualified Japanese native save was available for this regional investigation. Product identity does not prove compatibility with the tested profile. |
| Taiwan: 真‧三國無雙4 Special, Traditional Chinese Windows | [Taiwan KOEI's catalog](https://www.gamecity.com.tw/products/products/ee/Rlsmusou4sp.htm) explicitly lists Windows XP Chinese retail/bundle products separately from Xbox 360. [Contemporary launch coverage](https://gnn.gamer.com.tw/detail.php?sn=23858) announces the Traditional Chinese PC first sale on June 22, 2006. | The previously qualified [3DM CG-save listing](https://dl.3dmgame.com/patch/2672.html) labels its genuine premodified save **Traditional Chinese**. This qualifies the source-labeled 46,000-byte revision-3 sample and mapped equipment fields; it does not authenticate the executable's locale/build or establish interchangeability with Japanese saves. |
| Mainland China: 真三国无双4 Special, Simplified Chinese Windows | [Contemporary release reporting](https://www.gamersky.com/news/200811/128779.shtml) identifies Netyuan/网元网 as distributor and November 5, 2008 as launch date. | No matching native save, executable serializer or controlled action pair was obtained. Compatibility, text encoding and any revision differences remain unqualified. |

The existing `dw5special` adapter is retained. No regional clone, conversion or
extra supported-game entry is justified by these product names or retail bundles.
The byte-count, exact qualified header marker and checksum identify the supported profile; **no
native region discriminator has been proved**. A successfully parsed file is
not evidence that Japanese, Traditional Chinese and Simplified Chinese editions
share an interchangeable format. Bodyguard name bytes remain opaque, and no
regional name conversion is performed.

To qualify another region, obtain a native copy with the actual region/build
recorded privately, its unchanged control, and one-field before/after actions.
Verify profile, record addressing, encoding and integrity independently, then
exercise surgical edits through this adapter. An edited load and subsequent
native re-save are needed to establish game acceptance; a product page or
unchanged file roundtrip cannot establish that result.

## Compatible header variant

A separately supplied native bug-report copy exposed the exact `03 00 01 00`
marker at byte offset 4, which the previous `03 00 00 00`-only check rejected.
Its size, checksum position/coverage, item table, all 48 officer records and all
192 physical weapon slots match the published Windows Special geometry. Its
54 occupied weapon IDs belong to their officer families; the remaining 138
use the known empty sentinel. Existing ordinary ranks, weight/attack bytes and
attribute records obey the same qualified storage rules.

Both exact markers are now accepted. The upper word's meaning and the supplied
copy's executable region/build remain unproved: this is a compatible observed
header variant, not a region discriminator or conversion. No other marker is
accepted, even with a recomputed checksum. Every save preserves its original
marker, and the encoder rejects conversions between the two supported markers.
Existing empty, unusual, unknown and dependency-sensitive records retain the
same eligibility guards; no field scope or natural cap was expanded.

## Implemented controls

The editor offers named records for all 48 playable officers and their four
physical weapon slots. It writes qualified **already existing** equipment and
stored officer stats:

- Ten ordinary item ranks: stored 0–19 means level 1–20. Empty sentinel `0xFF`
  and unusual higher values remain read-only and unchanged.
- Existing own-family weapon weight: Light, Standard or Heavy. Weight is a
  choice, separate from attack and officer stats.
- The existing weapon attack adjustment byte, manually 0–40. This is the
  stored editable attack adjustment field, not a claim that total battle attack
  equals that byte. Weapon identity and its base parameters stay unchanged.
- Existing named weapon attribute ranks, stored 0–19. No empty attribute slot
  is populated, no attribute ID replaced, and no new weapon is created.
- Stored base Attack and Defense bytes on already playable officer records.
  Individual 0–255 edits use byte storage bounds, with no natural stat cap or
  Max. Equipment-derived battle totals, Life/Musou, merit, title, ownership and
  rewards remain separate and unchanged.

The latest field proof, native surgical matrix and GUI checks are documented in
[Samurai / classic Dynasty editor depth](SAMURAI_DYNASTY_DEPTH.md).

These controls are manual-only; Max does not alter them. Unknown weapon IDs,
nonzero identity high bytes, cross-family records, unoccupied officer records,
unknown attribute IDs and unusual original values are preserved. Searchable
inspection covers 48 officers, 192 weapon slots, 39 item records, eight bodyguards
and separate Shura resource words. English labels translate the published
Chinese identifiers; bodyguard names are shown as original bytes because
region-specific encoding has not been qualified.

## Format and mapping evidence

The [contemporary PC-save guide](https://game.ali213.net/thread-1001825-1-1.html)
by 小苹果 (June 25, 2006), with corrections credited to c-a and other contributors,
explicitly gives the native filename, checksum address, complete 48-name officer
order, 88-byte officer stride, item table and bodyguard layout. Its equipment
mapping is:

| Data | Decoded/native file position | Qualified write |
| --- | --- | --- |
| Ordinary items | `0x1534 + ID`, IDs 0–9 | Existing stored rank 0–19 |
| Officer records | `0xEC + ID * 88`, IDs 0–47 | Stored Attack `+6` and Defense `+7`, manual byte edits only when opened playable byte `+0` is 1; other progression inspected |
| Four weapon slots | Officer `+20 + slot * 16` | Existing own-family records only |
| Weapon ID | Weapon `+0`, high byte `+1` | Inspection; IDs `officer*4..officer*4+3` qualify that owner |
| Weight | Weapon `+2` | Manual 0/1/2 |
| Evolution attack | Weapon `+3` | Inspection; prerequisites unqualified |
| Five effect/rank pairs | Weapon `+4..+13` | Existing effect IDs 0–9, original ranks 0–19; rank byte only |
| Attack adjustment | Weapon `+14` | Manual 0–40; higher originals unchanged |
| Unknown weapon byte | Weapon `+15` | Preserve |
| Checksum | `0xB390`, LE DWORD | Sum of all preceding bytes |
| Trailer after checksum | `0xB394..0xB3AF` | Preserve |

Static inspection of the independently downloaded c-a editor from
[3DM's editor page](https://dl.3dmgame.com/patch/2670.html) corroborates its
46,000-byte read/write count, the byte-sum algorithm and record addressing.
Linux UPX only decompressed that editor file for analysis; neither it nor any
game executable was run. Its embedded initial template has the same revision
and checksum-valid layout. No source implementation or embedded template was
copied into the project.

A separate freely shared native save from
[3DM's Special CG-save page](https://dl.3dmgame.com/patch/2672.html)
independently matches the native profile, all 48 officer records, weapon
identities, empty sentinels and item rank table. Its listing labels the download
Traditional Chinese, without specifying an executable build. It is a **genuine premodified
save**; unusually boosted stats and weapons are not evidence for natural caps.
[Fourth-weapon mechanics](https://kongming.net/dw5/4th_weapons/) distinguish
weapon base attack, weight and individual bonuses; [rare-item mechanics](https://kongming.net/dw5/rare_items/)
distinguish rankless orbs/harnesses/special rewards from ordinary item levels.
These PS2 mechanics references provide context, while the Special-specific
mapping guide supplies the native PC addresses and limits.

## Per-mechanic coverage

| Mechanic | Status or specific blocker |
| --- | --- |
| Ordinary item levels | Tested existing-rank manual edits; no ownership grants. |
| Weapon weight, attack adjustment, existing attribute levels | Tested manual edits preserving weapon IDs, evolution state and unused slots. |
| Weapon acquisition, fourth weapons, evolution attack, new effects | No writer. Native acquisition/reward flags, rarity requirements and effect-slot rules need static game code or controlled pairs. |
| Officer Life/Musou/Attack/Defense | Stored Attack/Defense bytes manually editable on already playable records; Life/Musou inspected. Natural per-officer limits and item/weapon-derived totals remain unproven, so no automatic stat Max or effective-stat writes. |
| Officer merit, rank/title, levels and KO totals | Inspection. Merit thresholds, title transitions and growth/reward recalculation require native rules; no independent rank/EXP action. |
| Officer unlocks, outfits and equipment selections | Inspection. Correct reward/ownership/prerequisite relationships and unused-state initialization remain unresolved. |
| Bodyguards, talents, stats, skills, title and name | Inspection. Talent-growth formula, natural skill-slot limits, title dependencies and regional text encoding remain missing. |
| Shura gold, iron, starting iron and companions | Separate inspection. Native session activation, resource width/clamps and companion Life/max-Life relationships are not qualified sufficiently for writes. |
| Orbs, harnesses and 20 special items | Inspection only. These are rankless content/prerequisite rewards; ordinary item-level actions do not change them. |
| Free/Musou/Legend/Shura stage history, music/movies and collections | No writer. Native flag arrays, stage identities and dependent rewards require a matching Windows executable or controlled native before/after saves. |

For further qualification, supply the original Windows Special executable and
matching parameter/localization assets, or native `save.dat` pairs around one
weapon upgrade/equip, level/title transition, bodyguard growth/skill gain,
rare-item reward or Shura save. Retain the actual region/build and unchanged
control. The already supplied Orochi Z-sized `save.dat` is a different game.

## Validation

The public test input is procedural. Optional `DW5_SPECIAL_COPY` enables a
private genuine premodified save test: unchanged byte-identical roundtrip,
every qualified item/weapon field edited individually, correct checksum,
reparse and exact equality to a one-byte edit plus checksum update. Focused
checks also reject malformed size/revision/checksum, invalid values and forged
snapshots; preserve high/unknown/empty records; and exercise backup, restore,
new-destination saving and source mutation rejection. No player saves, editor
binaries, names/account values or personal paths are published. Actual edited
**game loading has not been performed**.

The original equipment qualification included procedural profile/corruption/bounds/snapshot/staging checks,
a genuine unchanged roundtrip and surgical edits of all 728 qualified equipment fields,
plus independent procedural and genuine Tk workflows for named choices,
Apply, Review, Undo, manual-only Max, inspection, copied saves, backup and restore.
No original sample was changed and no edited save was loaded in the game.

The earlier regional follow-up reran the then-current DW5 suites with Tk/Xvfb: **18 tests
discovered, 16 passed, 2 skipped** (both private-native cases). The procedural
GUI case exercises Apply, Review, Undo, manual-only Max, copied saving and
backups. The historical genuine/GUI results above belong to the
prepared adapter's earlier qualification, not a new cross-region validation.
No 46,000-byte DW5 native copy was present in that regional follow-up's private
inputs. Reacquiring the previously documented CG-save download was blocked by
an HTTP timeout and HTTPS 502 from its legacy download host. No new region-specific
genuine qualification or actual game loads were performed in that follow-up.
The latest depth work used the privately held previously qualified source-labeled
native copy to verify all 96 new stored Attack/Defense fields, totaling 824
qualified fields in that opened state; it adds no
Japanese/Simplified Chinese compatibility claim or edited game-load result.
See the linked depth report for current checks.

The header-variant fix was additionally checked against the supplied native
copy: byte-exact unchanged roundtrip, individual surgical edits/reparse of all
234 eligible fields (10 item ranks, 96 officer base-stat bytes, 54 weights,
54 attack adjustments and 20 attribute ranks), and the registered copied-save
self-test including immutable input, backups and restore. The focused format,
independent safety/GUI and regional-scope suites passed all 24 tests with this
private input and a real Tk/Xvfb display, with no skips. The existing GUI case
exercised named weight choices, Apply, Review, Undo, manual-only Max, searchable
inspection, copied Save As and restore. The original native copy was preserved;
no game executable or external editor was executed. These checks establish
file-level editing and GUI behavior, not edited game loading or a new regional
compatibility claim.

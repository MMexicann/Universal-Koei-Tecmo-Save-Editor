# WO3 Ultimate PS4 resource-transfer source

This conversion-only source profile admits a strict decrypted PS4 WO3 Ultimate
`APP.BIN` layout. It exposes rare crystals, attribute-orb balances and material
stock for a one-way resource transfer, with a separately reviewed scope adding
five stored base stats for 145 playable officers, to the existing PC Definitive
Edition writer. It does not add
a PS4 scalar editor, reverse destination writer or whole-save migration.

## Source facts

The [July 2022 author transfer discussion](https://steamcommunity.com/app/1879330/discussions/0/5788831477038148469/)
includes a complete original-poster PS4 payload in comment #2. Comment #5
explicitly identifies it as a decrypted PS4 Ultimate export after the game's
PS3-to-PS4 import. The author describes a successful PC rename/load test by a
friend. Other participants report missing bonus Gauntlet maps/subtitles, so the
report is not evidence of equivalent DLC, reward or edition completeness.

The acquired public payload has exactly `0x2119CA` bytes, begins with
`F1 18 03 14`, and has SHA-256
`9431b07f8a558313750c75ea8cd276fc65bb171a85db23d5b891730e64090319`.
Its original `sce_sys/param.sfo` was **not** supplied, so the payload's region
cannot be established from that file. No native original-context PS4 export is
claimed. A separately posted SaveWizard-decrypted ZIP link is now expired and
returns a parked-domain HTML page; it is not a second acquired reference.

On 2026-10-22 a separate supplied decrypted export and accompanying original
CUSA00588 metadata passed this same exact profile. Both transfer scopes passed
actual native PC prepare/export/readback, original-context source backups and
source preservation. The wider scope verified all 1,079 mapped values and kept
every other PC byte intact, including the complete saved-state body. One unusual
source stat was preserved as an exact existing target no-op; new assignments
above supported bounds remain rejected. This is additional original-context
file evidence, not an in-game load or controlled platform/action pair. Supplied
gameplay and companion data remain private and are not packaged.

The [public CUSA00588 PS4 cheat facts](https://www.patreon.com/chaoszage/posts/ps4-cusa00588-3-61894007)
independently identify the US PS4 edition and numerous matching native disk
locations: crystals `0xD5DC`, officer stats `0xECF2..0xECFA` with stride `0x2B0`,
attribute orbs `0xE944`, materials `0xE9A8..0xEAA8`, weapon effect IDs `0xC8014`,
effect ranks `0xC801C` and weapon stride `0x1C`. Its author explicitly says the
PS3 facts were ported to PS4, except the separately located ticket code. The post labels the first control “32767 Crystals” at `1000D5DC`, the orb
span “99 Skill Individual Jewel All Species” at `4000E944` with count `0x3A`,
and “All Materials x98” with counts `0x10`, `0x10`, `0x10`, `0x22`, `0x22`,
`0x22`, `0x91` at the seven spans. Only these labels/geometry facts are used;
the published cheat targets are not adopted as gameplay caps. These
are format/location facts, not evidence that published cheat values are natural
caps. No source implementation or code catalogue is copied into the app.

[Sony title metadata mirrored by sce-tmdb-scraper](https://github.com/FlexBy420/sce-tmdb-scraper/blob/abba1a1c2efd2ace308e9bbf2c2960b08fe282f4/tmdb/json/CUSA00588.json)
identifies `UP4108-CUSA00588_00-WORO3ULTHDDBOOT0` as WARRIORS OROCHI 3 Ultimate.
EU `CUSA00661` is a real separate title, but it is not admitted by this narrow
original-context reader. No title ID is inferred from the reference author's
language, location, account or file name.

## Exact admitted marker profile

The complete file must match all of these address-fragment tables:

| Start | Count | Stride | Four-byte marker |
| --- | ---: | --- | --- |
| `0xECE8` | 150 | `0x2B0` | `10 69 F8 00` |
| `0x3CE94` | 145 | `0x2B8` | `10 69 F8 00` |
| `0x28008` | 1 | 4 | `70 6A F8 00` |
| `0xC800C` | 2320 | `0x1C` | `B0 6B F8 00` |

The first table matches the existing 150-officer serialized array. The second
lies inside the larger saved-state section, with a different record stride;
it cannot be treated as another ordinary officer table. These markers are not
checksums. The PC reference has distinct marker values and even contains older
ASLR-dependent fragments in the saved-state table. Blind marker replacement or
whole-payload transplantation is therefore excluded.

Qualification requires exact length/revision and every table entry, immutable
raw bytes and original `sce_sys/param.sfo` whose title is exactly CUSA00588.
Complete companion bytes are bound by digest and rechecked around opening and
backup. No native PS4 aggregate checksum is claimed. Native signing, console
container decryption and account reassignment stay external.

## Resource semantics and retained data

Only directly corroborated PS4 resource records transfer: current rare crystals
at `0xD5DC` (u16 little endian), 58 attribute-orb balances at `0xE944` (u8), and
295 material balances in the seven spans listed by the public PS4 source. This
is 354 separate balances / 355 mapped bytes. The existing PC native mapping
independently identifies the corresponding fields, labels, widths and bounds.
Crystals use the separately mapped current balance, not the unrelated earned
history or a storage ceiling. The target permits 0–999 crystals and 0–99 for
each material/orb balance.
The acquired PS4 reference contains 177 crystals, orb balances from 0 to 12,
and material balances from 0 to 36, all within current supported PC limits.
Unallocated growth points and gems are excluded from this PS4 route because
the acquired PS4-specific facts do not independently locate those two words.

The destination PC reader and writer remain authoritative for permitted values.
The source profile itself supplies only native storage qualification, not a
PS4 gameplay maximum. The PC template's markers, officers, equipment, gems, growth points,
progression, story, DLC, rewards, suspended-state sections and every
other byte remain unchanged. Values above the target's supported bound must be
rejected without clamping. Exact opened values remain preservation cases under
the normal bound adapter rules.

## Validation and broader blockers

`tests/test_wo3u_ps4_export.py` covers immutable/no-op reads, both endpoints of
every marker table, wrong sizes/platforms/revisions, exact-title original
metadata, companion/source races, backup context with bounded actual readback of gameplay/manifest/companions,
foreign replacement retention and complete retained PC bytes.
The optional `WO3U_PS4_REFERENCE` test checks the actual public-origin PS4 payload
and typed 355-byte transfer through the native PC writer. The reference lacks
original metadata; generated title-only contexts establish API behavior, not
independent original-owner or in-game evidence.

The PC root native serializer at `0x1402488F0` includes a conditional opaque
`0xA0000` saved-state copy, saved-stage records and several platform/object
contexts. The PS4 reference's known markers do not qualify the complete opaque
schema or every field's endian/edition semantics. Broader conversion needs
independent native PS4 contexts/revisions, controlled platform pairs, complete
persistent/suspended-state boundaries and DLC/reward compatibility. A raw rename
report cannot replace those checks. Edited or resource-converted game
loading/re-saving has not been performed by this project.

A private guarded copied-native PC probe used the acquired PS4 payload as source
and a separately acquired native PC reference as template. It verified all 354
assigned values after actual Save As and readback; exactly 355 bytes changed,
with every byte outside the declared spans and both inputs unchanged. PS4
companion context was generated title-only for that probe because the author's
original metadata is absent. That probe proves payload-to-PC software behavior,
not original-owner context, PS4 game loading or console authentication.

## Separate base-stat and material scope

A second one-way scope adds the five directly mapped saved base-stat words for
145 playable officers. It transfers 725 base-stat values plus the original 354
resource balances: **1,079 values / 1,805 mapped bytes**. The narrower 354-balance
scope remains available and never changes any officer stat.

The same exact-title PS4 source independently labels “All Chars HP 999” at
`4100ECF2`, “All Chars Musou 999” at `4100ECF4`, “All Chars ATK 999” at
`4100ECF6`, “All Chars DEF 999” at `4100ECF8`, and “All Chars SPEED 500” at
`4100ECFA`. Its repeat descriptor `409102B0` identifies count `0x91` (145) and
stride `0x2B0`. These are five u16 words, matching the separately qualified PC
native serializer and existing stored-base-stat fields. The published speed
500 target is a cheat target, not a gameplay cap: the destination PC writer
continues to permit changed speed only from 0 to 180, and the other four stats
only from 0 to 999. Exact unusual values already present in the opened target
are no-ops; new unsupported incoming values are rejected without clamping or
experimental numeric expansion.

This scope preserves every other officer byte, including level, EXP, proficiency,
promotion count, allocated/unallocated upgrade points, equipment-slot metadata,
equipped references, ownership and reward dependencies. It does not claim to
migrate character progression or manufacture a matching level/reward history.
The five internal officer records are excluded. Source stats replace destination
stats, including lower values; they are not best-value merges.

Deeper root-serializer analysis confirms the ordinary 150-officer marker array
occupies exactly `0xECE8..0x28008`. Immediately afterward the native root at
`0x1402488F0` writes a four-byte saved-state context word and copies an opaque
`0xA0000` saved-state body. The weapon table begins at `0xC800C`, exactly
`0x28008 + 4 + 0xA0000`. The additional 145 officer snapshots at `0x3CE94`,
stride `0x2B8`, lie inside that opaque body. Both the complete body and its context
word remain byte-exact from the destination PC template. The primary first145
stat words are separate from those saved-state snapshots.

`test_wo3u_ps4_stats_transfer.py` verifies all 1,079 semantic values and every
other PC byte, five internal records, the complete saved-state block, narrower
scope isolation, reverse refusal, strict target bounds under experimental policy,
exact unusual-target no-ops and guarded PC Save As. An optional paired-native
payload test rechecks the acquired author PS4 reference against the independently
acquired PC reference. Two PS4 source speed words are 200; the native PC reference
already contains 200 at those positions, so those exact assignments remain no-ops.
A different template that would require newly assigning 200 must be rejected.
Original PS4 metadata and actual converted game loading remain unqualified.

## Further native boundary and public-export research

Static inspection of the native PC loader identifies the 240-byte span
`0xEBF8..0xECE8` as platform configuration: `CControllerSettingWin` reads its
binding array from runtime root `+0x51374`, and `COptionMenuWin` copies the whole
configuration object at root `+0x51360`. Preserving this span also retains the
PC control bindings. A raw-import report in the public Steam discussion describes
an unassigned controller Down binding after transfer.

The native saved-state capture helper at `0x14026A390` positively identifies the
contents of the opaque `0xA0000` body. It captures the current-system object, a
`0x6200` stage object, 145 officer snapshots, 2,320 weapon snapshots and additional
actor/resource state. The acquired PS4 and PC references both have a zero first
saved-state flag while retaining populated snapshots with different platform
address fragments. That flag alone does not establish that the body can safely
be copied, cleared or reconstructed. These routes preserve its complete PC bytes.

An independent [EU CUSA00661 save discussion](https://playersquared.com/threads/warriors-orochi-3-ultimate-starter-save-set-platinum-cusa00661.19134/)
provides a public retail USB export, but it contains encrypted `SAVEDATA00` and
its key companion, without readable `APP.BIN` or original `sce_sys/param.sfo`.
It does not qualify an additional decrypted source profile. Participants also
report that Advanced Mode export/import into the recipient's own save still
failed. Their differing DLC installations are a proposed cause; the exact
byte-level cause is unproven. This supplies another reason that whole-save
compatibility cannot be inferred from matching payload size and title alone.

A separate [Japanese PS4 format post](https://emu.web-g-p.com/info/bbs/patchcode/ps4/bbs.cgi?list=pickup&num=12260)
from November 2017 corroborates weapon attribute/slot geometry and names gems
at `0x137C`. It explicitly distinguishes PS4 from PS3 addresses, but supplies no
exact CUSA or revision. Its cheat value is not evidence of a native cap. These
additional observations do not widen the supported US source fields or prove
weapon ownership, equipped references, ID correspondence or DLC compatibility.

A full progression transfer still needs independently established PS4 persistent
state and ID/dependency mappings, plus a qualified policy for scene snapshots.
The PC serializer establishes destination packing; it does not by itself prove
portability of PS4 runtime snapshots or their resource identifiers. No game
binary was executed during this static research.

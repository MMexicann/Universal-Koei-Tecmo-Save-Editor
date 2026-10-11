# Arland DX native save qualification

This work does **not** register Totori DX, Rorona DX or Meruru DX as editors.
Rorona and Meruru now have genuine public gameplay-file evidence and bounded,
read-only inspection packages. Native integrity and writable gameplay profiles
remain unqualified. The inspectors expose no gameplay fields or file writer.
Totori DX also has a separately title-qualified decrypted PS4 gameplay lead;
that export does not qualify the missing native PC profile.

## Native evidence and framing

The [Rorona DX Steam save-sharing discussion](https://steamcommunity.com/app/936160/discussions/0/570414689743552256/)
links a publicly downloadable multi-ending archive. Twenty-seven gameplay slot
copies, spanning early assignments, endings and overtime, each have 380,928 bytes.
The accompanying instructions identify app **936160**, Rorona DX. Some copies
contain deliberately increased resources; their large values are not natural
gameplay caps. Their exact executable build and editing history are unknown.

[Barrel Wisdom's player-authored PC save collection](https://barrelwisdom.com/blog/atelier-pc-saves)
provides two Meruru DX gameplay files and identifies app **936190**. Its minimal
clear save and equipped clear save both have 558,080 bytes. Fifteen additional
gameplay copies from the [Meruru DX SaveGamePro archive](https://savegame.pro/pc-atelier-meruru-the-apprentice-of-arland-dx-savegame/)
independently match that layout. These are genuine player-file comparisons, not
bundled dummy fixtures; no game-loading claim follows from inspection alone.
Exact installed revisions and controlled action pairs are still missing.

Both observed layouts have little-endian word `20100403` at offset zero and
32-byte headers, followed by sequential `(u32 tag, u32 payload_size)` chunks.
The magic alone is shared and cannot identify a game. Every tag and exact length
must match before the research inspector accepts a candidate:

| Candidate | Ordinary tags | Exact payload sizes in tag order | Final tag and bounds |
| --- | --- | --- | --- |
| Rorona DX observed PC layout | 1–32 | 39392, 8416, 4, 6112, 138252, 128, 100816, 4, 5248, 1, 8, 68, 132, 3584, 8, 9376, 47984, 4137, 128, 768, 384, 120, 256, 234, 4, 4, 64, 7048, 32, 188, 832, 488 | tag1024 at `0x5B6EC`, length6420 |
| Meruru DX observed PC layout | 1–24 | 46120, 6972, 4, 5628, 179724, 121, 100768, 4, 6968, 1, 8, 68, 604, 2220, 8, 3584, 95968, 1469, 84, 384, 94260, 4800, 128, 80 | tag1024 at `0x86537`, length7881 |

The final length **includes** its eight-byte tag/length header, unlike ordinary
chunk payload lengths. Header reserved words and trailer payloads are zero in
the acquired files, but remain opaque and byte-preserved by inspection. This is
not proof that native checksums are absent; none is claimed or silently repaired.
System files of 36,864 bytes fail both gameplay fingerprints.

Implemented inspectors:
[Rorona](../src/koei_editor/research/rorona_dx/inspection.py) and
[Meruru](../src/koei_editor/research/meruru_dx/inspection.py).
The bounded [Rorona gameplay observations](../src/koei_editor/research/rorona_dx/observations.py)
also retain twelve early character EXP leads and 2,100 item-quality records.
The [Meruru inspector](../src/koei_editor/research/meruru_dx/inspection.py)
exposes its source-correlated Cole lead without authorizing a write. Full
mechanic and prerequisite checklists are maintained separately for
[Rorona](RORONA_DX_FORMAT.md) and [Meruru](MERURU_DX_FORMAT.md).

### Totori DX decrypted PS4 lead

[Apollo's public Totori DX upload](https://github.com/bucanero/apollo-saves/issues/452)
explicitly identifies decrypted PS4 **CUSA14014** clear and system exports.
The [official PlayStation product](https://store.playstation.com/en-nz/product/EP4108-CUSA14014_00-APPA12TOTORI0000)
independently identifies that title. The acquired main `USR-DATA.dat` has
380,928 bytes, and its companion SFO metadata identifies CUSA14014, clear data,
GALAXY adventurer rank and Cole189067. Its tag3 four-byte little-endian payload
at **`0xB3FC` reads189067**, agreeing exactly with native preview metadata and
corroborating the published currency lead on this separate platform.

Despite sharing Rorona PC's total size, this Totori export has **22 different
chunks** with payload sizes40848,5172,4,3972,152520,51,57164,4,5632,1,24,68,
940,1616,8,4536,400,1836,15013,168,112,64. Its final tag1024 begins at
`0x46E39`; stored length90567 includes the eight-byte header. The Rorona
inspector rejects it. Header reserved words and trailer payload are zero, which
still does not prove absence of native game checksums. PS4 PFS signing is
external to a decrypted export; game-internal integrity must be qualified
independently before writes.

Two included backup/copy files are identical to each other but differ from the
main slot in15,904bytes; these are **not** a controlled Cole-only pair. Another
336,112-byte `USR-DATAb.dat` has a different unidentified layout and is excluded.
The separate system export's native metadata explicitly names Atelier Totori.
No account identifiers, signing files or player bytes are imported into source.
The [title-qualified PS4 inspector](../src/koei_editor/research/totori_dx_ps4/inspection.py)
requires the original export's CUSA14014/GAMEDATA00 identity and retains ten
character records and 1,099 item-record leads. Its
[mechanic checklist](TOTORI_DX_PS4_FORMAT.md) distinguishes observed disk geometry
from equipment, synthesis, capacity and progression dependencies that remain
unqualified. It provides no staging or edited-save writer.

## Public format leads and limits

[Apollo PS3 patch data](https://github.com/bucanero/apollo-patches/tree/0ccc07ed39ea378db83e9901dbfa610b04637d7d)
is GPL-3.0 source evidence, inspected separately; no patch database or editor code
is imported. Its Rorona **Plus** profiles BLES02050/NPUB31522/BLJM61127 place Cole
at `0xBAF8`, character EXP at `0xBB0C` with stride `0x1F4`, and item quality at
`0x2EF90` with stride `0x30` across 2100 records. These early positions align
with the acquired PC chunks: tag3's four-byte payload starts at `0xBAF8`, and
tag7 starts at `0x2EF88`. Observed float qualities corroborate the early item
lead. **Later PS3 Plus offsets do not align**: published alchemy/ticket/friendship
addresses point at unrelated PC content. Original PS3 Rorona has another layout.
Therefore neither an entire console schema nor console integrity assumptions
can be transplanted into a PC adapter. Cheat target 9,999,999 is not a proved
Cole cap; similarly an EXP patch target is not a legitimate level progression.

[Arland runtime fixes](https://github.com/nicoverbruggen/atelier-arland-fixes/tree/96a4506892de3284a8adc78a4b6a96d67e8bbf59)
(MIT) supply useful serialization and quality mechanics, but runtime structures
are not disk-save offsets. In particular Totori's runtime item stride `0x34`
differs from the Rorona Plus quality lead's `0x30`. Trait/effect table bounds
do not establish item applicability or disk ownership.

[Meruru's calendar transfer source](https://github.com/jrpx/Atelier-Meruru-Date-Transfer-Tool/tree/c75f8d3457379677c1e84ff87232f85918ee6985)
(CC0-1.0) transfers only byte `0x5493E`; its exclusive loop endpoint is `0x5493F`.
In both acquired Meruru sources this is the first byte of tag11's eight-byte
payload. That observation qualifies its location, not a complete date encoding.
The author reports year rollover failure, repeated investment income and
unadjusted quest/Hom timers after rewinds. Calendar edits remain deliberately
blocked pending all dependent timers and event transitions.
The author's explicit report of beating the game with this tool is useful
offline-edit evidence for this one calendar byte on the author's PC revision.
It does not establish the integrity rules for other chunks, money or items.

Totori app **936180** remains separate from Rorona app **936160**. The misleading
Totori archive discussed in [Totori's research checklist](TOTORI_PC_RESEARCH.md)
contains Rorona system data, not Totori gameplay. The three-byte `0xB3FC` Cole
tool has a newly recovered source-author gameplay account on Steam app936180.
The [author's announcement](https://steamcommunity.com/app/936180/discussions/0/2865909887924677355/)
links their GitHub tool and describes its 400,000/600,000 targets. In their
[later gameplay post](https://steamcommunity.com/app/936180/discussions/0/2865909982608566012/),
they discuss their Cole tool while investigating a missed
Rorona appearance, then establish that the problem was a synthesis/flashback
prerequisite: "I wondered if I screwed up the wrong 1s and 0s. Turns out I
didn't." This supplies author testimony connecting the narrow offline money
tool to continued gameplay, rather than an assertion that no edit-use
testimony exists.
It does not provide controlled before/after files, a displayed edited balance,
an executable revision or independent edit/load/re-save validation. The
three-byte writer still does not establish full storage width, natural bounds,
complete framing or integrity for arbitrary fields/revisions. No
genuine Totori DX **PC** gameplay slot was acquired in this investigation; the
decrypted PS4 lead above must not be advertised as Steam support. A second independently downloaded
[Manga Council PC archive](https://mangacouncil.blogspot.com/2018/12/atelier-totori-adventurer-of-arland-dx.html)
contains only36,864-byte `SYSDATA` and a credits image, and also supplies no PC
gameplay evidence.

## Mechanics and implementation blockers

The [Rorona DX achievement guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2962194705)
documents friendship gained through requests and travel, level-dependent
character endings, recipe progression through pie quality, and seed/garden
synthesis. These require separate prerequisites; resource edits must not mark
their stories or recipes complete. The [Meruru DX synthesis guide](https://steamcommunity.com/sharedfiles/filedetails/?id=3137827892)
distinguishes weapon, armor, accessory and usable-item trait applicability and
uses up to five traits per piece; quality also controls effects. A universal
trait dropdown or changing item IDs would bypass these restrictions.

| Mechanic | Current result | Specific missing evidence for an editor |
| --- | --- | --- |
| Cole/currencies | Rorona source-backed early disk lead; Meruru tag3 values1000 and364433 in the minimal/equipped clear pair agree with author descriptions; Totori PS4 tag3 value189067 agrees exactly with native preview metadata. No writable fields. | Exact platform loader/integrity model, title/build qualification and controlled purchase/sale pair; legitimate cap before Max. Totori PC still needs genuine gameplay bytes. |
| Inventory/quantity/quality | Rorona early quality/stride lead corroborated; all opaque bytes preserved. Totori runtime and Meruru console leads remain separate. | Native existing-record counts, occupied/empty identity rules, quantity semantics, equipment/registered-shop references and checksum-safe edits. |
| Traits/potentials/effects/synthesis | Runtime/table and guide facts only; item applicability dependencies explicitly blocked. | Native catalogs or source-backed IDs, applicability, synthesis cost/quality dependencies and controlled synthesis pair. |
| Equipment | No ownership or equipped references changed. | Title-specific record/reference mapping and controlled equip/unequip pair. |
| Character/alchemy EXP and skills | Rorona early character EXP lead; main-game and overtime profiles differ. No direct levels/stats written. | Native EXP thresholds, derived stat/skill updates, recruited-character identity and main/overtime rules. |
| Recipes/friendship/exploration/collections | Mechanics researched; story/resource separation retained. | Native unlock/history/ownership records, all prerequisite/reward dependencies and controlled discoveries/requests. |
| Story/assignments/calendar/events | No writes; Meruru rewind conflicts are explicit. | Complete date/timer transitions and event prerequisites; a single-byte transfer is insufficient. |
| Native integrity | Not qualified for either PC profile. | Exact PC reader/writer evidence or a reproducible, title/revision-labelled successful native edit/load/re-save control establishing checksum handling. Zero framing and PS3 patch absence alone do not suffice. |

## Validation distinction

[Rorona tests](../tests/test_rorona_dx_candidate.py) and
[Meruru tests](../tests/test_meruru_dx_candidate.py) check full tag/length/trailer
bounds, foreign/system input rejection, immutable and unforgeable snapshots,
unknown-byte preservation and exact unchanged roundtrips. Procedural patterned
inputs are structural tests, not manufactured playable saves. Optional genuine
tests require externally copied gameplay directories via
`RORONA_DX_CANDIDATE_DIR` and `MERURU_DX_CANDIDATE_DIR`; they neither download nor
publish player files. All27 acquired Rorona copies, all15 Meruru archive copies
and both independently authored Meruru copies passed layout/unchanged checks.
Native game loading, edited-game validation and GUI save/backup/restore have
**not** been performed for these unregistered, read-only candidates. No binaries
were executed and no player bytes or external source copies enter the checkout.

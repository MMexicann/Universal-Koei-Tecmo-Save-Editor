# Atelier Rorona DX PC: qualification and mechanic checklist

**This profile is read-only research, not a supported editor.** Twenty-seven
genuine, publicly shared PC gameplay copies qualify the observed layout and
several early gameplay leads. No native loader/writer or controlled edited-save
load establishes complete integrity handling yet. It would be premature to
advertise writable support even though these files are plaintext.

The [Arland format notes](ARLAND_DX_RESEARCH.md) contain the complete tag lengths,
the distinct Totori and Meruru fingerprints, public provenance and source
licences. The new [read-only observations](../src/koei_editor/research/rorona_dx/observations.py)
give a future investigator bounded access to the corroborated early leads,
without inventing a staging, saving or checksum API.

## Rechecked native evidence

The [Steam Rorona DX save-sharing discussion](https://steamcommunity.com/app/936160/discussions/0/570414689743552256/)
links an archive containing twenty-seven gameplay copies, including early
assignments, endings and overtime. They were downloaded again and independently
passed the existing complete 380,928-byte structural fingerprint. Their README
identifies Steam app 936160 and explains clear data, EX clear data and overtime.
It does not explain how increased resources were created, prove Steam build
identity or document an offline edit followed by a native load.

| Lead | Observed disk geometry | Qualification and limit |
| --- | --- | --- |
| Cole | Tag 3, four-byte little-endian word at `0xBAF8` | Early PS3 Plus fact independently agrees with the PC chunk; this value occurs only at that position in all 27 copies. Natural cap and native edit acceptance remain unproved. |
| Character EXP | Twelve records in the start of tag 4; stride `0x1F4`, EXP word at record `+8`, first at `0xBB0C` | Early PS3 Plus EXP lead corroborated by native copies; first record words are IDs 0–11 in every copy. The second word is retained without claiming its level/update semantics. Remaining tag bytes are opaque. |
| Item quality | First 2,100 records in tag 7; stride `0x30`, little-endian float at record `+8`, first at `0x2EF90` | Early PS3 Plus quality lead agrees with native records; qualities include 50, 100 and 120. Two preceding words and nine following words are exposed as raw words, without claiming full item identity, ownership, trait or use semantics. The final sixteen bytes remain opaque. |
| Empty-looking item records | The first two signed words are both `-1` | An observed marker, not proof of ownership, list membership, capacity or safe creation. Mixed, unknown and unusual values are preserved. |

The observations keep the original float bits alongside its decoded value.
Nonfinite values and unknown words remain unchanged; there is no repair or
normalization. A title/length/tag mismatch or forged inspection is rejected
before any observation. These facts are neither console support nor an
established PC writer.

## Mechanics and implementation coverage

The [Rorona DX achievement guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2962194705)
describes friendship from requests/travel, character-ending requirements,
quality-dependent pie progression and garden/seed synthesis. The
[official DX description](https://store.steampowered.com/app/936160/)
establishes the separate overtime content. The
[official English manual](https://cdn.akamai.steamstatic.com/steam/apps/936160/manuals/steam_rorona_EN.pdf)
distinguishes mandatory/optional assignment stamps and vouchers (pp. 23–26),
popularity and quest deadlines (pp. 27–29), hiring fees and friendship
(pp. 35, 54), ingredient quality/effect thresholds/trait costs (pp. 41–44),
weapon-shop equipment synthesis (p. 45), and basket/container membership
(pp. 49–51). Resource, growth, synthesis and story systems must remain separate
rather than granting ending or recipe rewards while changing a number.

| Actual system | Prepared result | Specific remaining evidence |
| --- | --- | --- |
| Cole, purchases, sales and wholesale | Read-only four-byte currency lead, rechecked on 27 copies | Native reader/writer integrity coverage or a controlled Cole-only edit/load/re-save; displayed purchase/sale pair and legitimate cap before Max. |
| Vouchers, popularity and assignment stamps | Distinct currency, evaluation and reward systems researched; no writes | PC stored balances versus history, optional/mandatory stamp grid, earned/claimed reward flags and controlled quest/reward pairs. Later PS3 Plus offsets do not establish these PC fields. |
| Character levels, EXP, stats and skills | Twelve bounded early EXP record leads | Recruit/party identity, EXP thresholds, growth and learned-skill updates; separate main-game/overtime rules; native integrity. A direct EXP patch must not leave derived stats inconsistent. |
| Alchemy level and EXP | Mechanics identified; no cross-edition offset promoted | PC alchemy record and thresholds, derived recipe/skill dependencies and controlled synthesis pair. Later PS3 Plus offsets do not align with this PC layout. |
| Basket/container inventory and item quality | 2,100 bounded read-only quality record leads | Physical/list capacities, native item catalogs, item membership, owner references, equipped/registered-shop dependencies and quality/effect calculation. |
| Traits, effects and remaining item uses | Unnamed native words retained for comparison | Exact PC word meanings, trait applicability, synthesis cost/restriction rules, effect thresholds and consumption/refill action pairs. PS4 Save Wizard templates are a separate platform and cannot supply the complete PC schema. |
| Weapons, armor and accessories | No ownership or equipment writes | Native references and controlled equip/unequip pairs; recalculation of stats/effects and equipped item dependencies. |
| Friendship, requests and character endings | No writes; prerequisites explicitly retained | PC friendship/request records, completed reward history and controlled request/travel pairs. Changing friendship must not claim an ending or request reward. |
| Recipes, pies, seeds, garden and synthesis progression | Mechanic checklist established | Native unlock records and prerequisite/reward transitions; quality and trait dependencies. |
| Hom, workshop decorations and time capsule | Additional work/decorating/transfer systems identified; no writes | Native task/decorating records, owned-item references, completion times and delayed-transfer rules; controlled task assignment and decoration/transfer pairs. |
| Exploration, collection and gallery/costumes | Gameplay/system files kept distinct | Title-specific discovery flags and rewards; separate system-file profile for gallery/costumes. The 36,864-byte system file remains rejected by this gameplay inspector. |
| Assignments, calendar, events and overtime | No writes | Full date encoding, assignment/event timers, ending transitions and overtime dependencies. Runtime date freezing is not proof of safe disk edits. |
| Native integrity and revision | Strict observed tag/length fingerprint only | Native Rorona DX PC executable reader/writer trace, including every envelope and gameplay integrity check, or reproducible title/build-labelled targeted edit/load/re-save evidence. Zero header/trailer bytes and a trainer-modified archive are insufficient. |

## Investigation and validation

The MIT-licensed [Arland runtime fixes](https://github.com/nicoverbruggen/atelier-arland-fixes)
were rechecked. Their save hooks target Totori's original serializers rather
than reimplementing a complete Rorona disk reader/writer. They explicitly do not
read/write disk saves. Their runtime repair and equipment work therefore do not
prove Rorona's complete integrity model. Direct Steam searches for save, hex,
edit and cheat found runtime date-freezing guidance, resolution edits and shared
saves; none established native acceptance of an offline Rorona save edit.
Public repository searches found no Rorona save-editor source implementing the
missing reader/writer. A second search in English, Japanese and Chinese found
the [PC research thread](https://web.save-editor.com/bbs/community/pc/bbs.cgi?list=pickup&num=3667),
its [questions thread](https://web.save-editor.com/bbs/community/pc/bbs.cgi?list=pickup&num=3668)
and [PC save-sharing thread](https://web.save-editor.com/bbs/savedata/pc/bbs.cgi?list=pickup&num=2513).
The fetched threads contain administrative links rather than an offline edit
or checksum implementation. The shared archive's
[original author's post](https://ko-fi.com/post/Atelier-Rorona-The-Alchemist-of-Arland-DX--100-S-K3K87P6CL)
identifies a PC save but does not establish how its increased resources were
made. The published
[Remumu editor](https://gbatemp.net/threads/release-remumu-atelier-meruru-save-editor.443645/)
is for Meruru on Vita in 2016, before the 2018 DX PC release; it does not
qualify Rorona PC. Current public Arland mod save hooks still call opaque
original Totori serializers; the release DLLs provide no Rorona disk-loader
implementation. No game or downloaded editor executable was run.

The most useful missing input is the native Rorona DX PC executable:
`A11R_x64_Release_en.exe` for English, or `A11R_x64_Release.exe` for the
Japanese/Chinese variant. Static analysis must establish complete load/save
integrity before this candidate can be promoted. Alternatively, a controlled
offline Cole edit followed by a labelled successful native load and re-save,
with an unchanged control and the exact edit procedure, can establish a narrow
currency qualification. An arbitrary save that contains high Cole cannot.

[Candidate tests](../tests/test_rorona_dx_candidate.py) and
[observation tests](../tests/test_rorona_dx_observations.py) passed **9/9 with no
skips**, using the reacquired 27 gameplay copies. They cover complete framing,
foreign/system input, forged snapshots, exact unchanged bytes, bounded gameplay
leads and unusual/nonfinite values. Procedural inputs test structure and do not
pretend to be playable saves. There is no edited-game load, GUI save/backup
workflow or writable adapter qualification for this profile. Player copies,
personal paths, third-party source and binaries remain outside public files.

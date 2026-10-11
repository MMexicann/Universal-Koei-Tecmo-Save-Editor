# Berserk and the Band of the Hawk: Windows qualification

The Windows game remains **research-only**. Three complete public native files
qualify their observed outer cipher, checksum and common title header, but the native gameplay
records, save revision and any further integrity have not been established.
No writable fields or library card are registered. The identified existing
save editor targets PS Vita and cannot supply Windows field mappings.

## Native file evidence

The [SaveGame.Pro contribution](https://savegame.pro/pc-berserk-and-the-band-of-the-hawk-savegame/)
contains `BKSAVEDATA0000.dat`, 1,268,512 bytes (`0x135B20`). Two additional
complete native saves were downloaded from freely shared
[GTrainers contribution 3202](https://gtrainers.com/load/categories/savegames/berserk_and_the_band_of_hawk_save_game_the_game_done_100/30-1-0-3202)
and [contribution 3203](https://gtrainers.com/load/categories/savegames/berserk_and_the_band_of_hawk_save_game_the_game_done_100_pc/30-1-0-3203).
All three files have distinct plaintext and ciphertext, the same complete size,
the documented title/slot header and a valid three-advance outer checksum.
Each was reviewed privately; only native data files were extracted.
The contributors' “100% completed” labels
does not establish ordinary field values, the installed DLC, region, executable
build, save revision or a successful edited game load. The archive's shortcuts
and link files were not run; only the native data file was extracted.

Observed complete-file facts:

- The first four bytes store a little-endian u16 checksum and u16 seed.
- Starting at the stored seed, each complete payload u32 is XORed with the
  state after **three** advances of
  `state = (state * 0x5B1A7851 + 0xCE4E) mod 2^32`.
- The checksum equals the sum of all decrypted little-endian u16 words modulo
  65,536. The decoded payload is `0x135B1C` bytes.
- Payload offset `0` starts the exact ASCII title
  `BERSERK and the Band of the Hawk`, followed by NUL padding. Offset `0x80`
  starts the ASCII display label `Saved Data: 1`. Neither the display label
  nor the opaque decimal text in the following header establishes a native
  format revision. The player's remaining header/body contents stay private.
- The original seed and entire ciphertext are preserved by an unchanged
  decrypt/encrypt roundtrip. Independently tested one- and four-advance
  candidates fail this native checksum. Single-bit changes at the first and
  last ciphertext payload bytes fail the matching outer checksum.

These facts qualify the shared observed envelope across three native copies. They do not prove a semantic record
layout or the absence of internal integrity. A recomputed outer sum alone
cannot authorize a gameplay write. Complete-byte identity, payload identity
and native checksum validation are file tests; no edited output was imported,
loaded or re-saved in the game.

## Existing editor and source survey

| Reference | Scope and licence finding | Consequence for a Windows editor |
| --- | --- | --- |
| [EvilGoku's GBAtemp release](https://gbatemp.net/threads/release-berserk-and-band-of-the-hawk-save-editor.503586/), May 11, 2018 | The thread is in Sony PS Vita. Its attachment contains one .NET GUI executable and no source or licence. Static metadata explicitly titles it “Berserk and Band of the Hawk (U) Save Editor Psvita”. Its controls cover character status, gold and materials. | Static inspection found direct byte reads/writes without the Windows cipher, native checksum, title/revision or complete-layout qualification. No Windows field equivalence was proved. The executable was never run, and its implementation and private analysis are not distributed. |
| [iccugs/BERSERK_trainer](https://github.com/iccugs/BERSERK_trainer/tree/afec9a6c7685b3b6c9bb7092762a686af9b99937), `afec9a6c7685b3b6c9bb7092762a686af9b99937` | Live process trainer; no implementation licence located. Its gold control is commented out. | Live gauges, pointers and large cheat targets do not qualify disk offsets, persistent growth or natural limits. No code was copied or run. |
| [predprey's Fearless PC table](https://fearlessrevolution.com/viewtopic.php?t=5), V1003 | Downloadable XML Cheat Engine table, reviewed only as text. No implementation licence established. Gold, enhancement materials, 32-byte accessory records and `0x180`-stride character getters are shown alongside captured native instruction excerpts. | The excerpts supply concrete getter and mechanic leads for later executable analysis, but neither a Windows file serializer nor a memory-to-disk correspondence. No scripts, catalogs or implementations were copied or executed. |
| [Lyall/BerserkFix](https://github.com/Lyall/BerserkFix/tree/c64747519f6967df6264a1efbd7bf369f7b3aea5), `c64747519f6967df6264a1efbd7bf369f7b3aea5` | MIT display, frame-rate and runtime fixes. | The reviewed source contains no native save serializer or inventory/progression schema. No source was incorporated. |
| [ayozetr's PC tutorial translation](https://github.com/ayozetr/berserk-band-of-the-hawk-es/tree/a10d3affa706dc9d4650f5f54e82bb90c251986c), `a10d3affa706dc9d4650f5f54e82bb90c251986c` | The licence grants MIT terms to the original software/docs and explicitly excludes `translation/`, which derives from Koei's game text. | Mechanic facts are summarized with attribution; translated text, catalogs and game assets are not bundled. LINKDATA/text layouts are asset layouts, not player-save records. |

Repository and code searches for the exact native basename, the PC title with
save/checksum terms, and Berserk save-editor projects found no qualifying public
Windows save serializer. PS Vita save exports and PS4 cheats remain separate
platform evidence. The source survey supplies leads and mechanics, not a licence
to transplant unverified console or runtime offsets.

The additional [Nexus story-clear contribution](https://www.nexusmods.com/berserkandthebandofthehawk/mods/17)
and its [Ayaka listing](https://ayakamods.com/mods/game-clear-save.4594/) describe
different progression and include screenshots. Both require login to download;
their save contents were not acquired and are not counted as native fixtures.
The Japanese [Vita save-modification board](https://web.save-editor.com/bbs/cfw/psvita/bbs.cgi?list=pickup&num=12497)
was also checked; the reviewed thread contains no field or integrity mapping.
The separate Japanese [PC modification thread](https://web.save-editor.com/bbs/community/pc/bbs.cgi?list=pickup&num=3589)
and [PC save thread](https://web.save-editor.com/bbs/savedata/pc/bbs.cgi?list=pickup&num=2487)
contain title/index links, but no save attachments, currency values, field maps
or checksum calculation in their reviewed posts. English, Japanese and Chinese
offline save/hex-editor searches supplied live trainers and save-location guides,
without a qualifying Windows file writer. A
[Manga Council contribution](https://mangacouncil.blogspot.com/2017/02/berserk-and-band-of-hawk-save-game.html)
describes completed collections and links a Google Drive copy; the reviewed
download redirects to Google sign-in and was not acquired.

## Persistent mechanics and dependencies

The official [Steam PC manual](https://store.steampowered.com/manual/502280)
is the primary mechanical reference. Page numbers below are its printed pages.
It is read privately, with no manual pages/assets included in this repository.
The tutorial reference supplies additional rules absent from the short manual.

| Mechanic | Established gameplay facts | Required native mapping before editing |
| --- | --- | --- |
| Money and materials | The briefing shop buys and sells accessories/materials (manual p24); the tutorial also distinguishes purchasable equipped items and shop stock refreshed after victories (`e2575.u11.s76`). Enhancement consumes materials of the skill's corresponding color (p25, tutorial `s78`). | Current quantities versus earned/spent history; native IDs, widths, arrays, unusual values and item/reward ownership; monetary/material limits and costs. Do not adopt a trainer target, storage ceiling or the progressed sample's values as Max. |
| Existing accessories and reinforcement | Three accessories can be equipped (p29). An accessory can carry four skills; amalgamation combines skill levels and consumes the other accessory (p26). Tutorial `e2575.u11.s75` and `s78`–`s81` distinguish duplicate equipped effects, reinforcement to +9, class promotion using rare materials and choosing inherited skills when more than four result. | Occupied-record identity, item/class/rarity IDs, reinforcement versus promoted class, four skill IDs/ranks, native base stats, equipped references and material compatibility. The +9 mechanic does not prove its storage encoding or permit creating accessories. |
| Character growth and skills | Character level naturally reaches 99; EXP increases level, stats and sometimes available actions (p27). Tutorial `e2575.u11.s89` distinguishes action-level unlocks and vitality restoration on level-up. | Per-character ownership and record identity, EXP curve, stored level versus derived stats, action prerequisites and reward transitions. A manual cap is not an offset map; level or EXP writes cannot bypass unresolved dependent fields. |
| Frenzy, death blow and sub-weapons | The manual describes battle gauges and character-specific battle effects; accessories affect their operation (pp9–14, p28). | Determine which quantities persist. Runtime gauge pointers do not establish stored growth, transformation, skill ownership or cooldown fields. |
| Warhorses | Scenario completion or special battle conditions unlock horses (p30). Charge power, endurance and speed are distinct. | Existing ownership, horse identity and equipped references; do not create a reinforcement system or edit unlocks as resource quantities. |
| Endless Eclipse and behelits | Desires span five layers; depth affects rewards, checkpoints open after reaching layers, and stray war demons can award behelits (pp31–32). Tutorial `e2575.u11.s86`–`s90` separates story-gated depth, per-character layer rewards, shared first-time desire progress/rewards, and an active run whose vitality/items and abandonment rules differ from permanent records. | Character-specific cleared layers/checkpoints and reward claims; shared desire identity/first-clear/claim flags; active-run state and behelit/gallery prerequisites. A numeric floor/desire edit must not silently grant, reset or duplicate rewards. |
| Story, gallery and unlocks | Story clears add battles/events (pp23–24); tutorial `e2575.u11.s82`, `s85` connects behelits to gallery panels and scenarios to events. | Separate completion/ranks, reward claims, ownership, entitlement and resource edits. No blanket story-completion or unlock operation is qualified. |

## Exact enabling inputs

### What the renewed investigation established

The new unregistered
[title inspector](../src/koei_editor/research/berserk_pc/inspection.py) requires
the exact observed NUL-padded title at payload `0x00..0x3F` and slot-one display
label at `0x80..0x8F`, after the existing envelope validates. It exposes only
read-only qualification flags and unchanged re-encoding. It accepts no
replacement plaintext and has no field, staging, saving or library API.
The display label is deliberately not treated as a native revision, and another
slot label remains outside the observed inspection profile.

[Inspection tests](../tests/test_berserk_pc_inspection.py) exercise immutable
snapshots, malformed input, ciphertext corruption, forged snapshots and foreign
headers with deliberately recomputed valid outer sums. The native corpus check
uses the optional `BERSERK_PC_NATIVE_DIR` variable without embedding saves.
The focused run passed **21 tests with no skips**, including all three genuine
complete copies, existing shared envelope regressions and the single-file native
checksum test. This is unchanged-file validation, not gameplay-edit acceptance.

Static reinspection of the Vita editor recovered a currency write at file
`0x3774`, byte material writes at `0x3690 + index` and a character EXP read/write
at `0xF0 + 0x180 * index`. The PC table's shop and enhancement excerpts instead
access currency at **live object + `0x37B4`**. Plausible integers at related
positions in the decrypted PC copies do not prove that these objects are
serialized unchanged, or that the Vita offsets apply to Windows. These addresses
are research leads only; no Windows gameplay field is implemented from them.
In particular, the Vita EXP/level offsets produce zero for all eight candidate
character records in all three Windows copies, including the contribution
advertised as level 99. That contradicts directly adopting this console record
map. No acquired contribution provides a displayed currency balance to resolve
the competing plausible integer locations. A constant `0x40` relocation between
live pointers and a console file is therefore not established for the PC save.

The remaining field checklist is explicit:

| System | Current Windows editor status | Specific proof still needed |
| --- | --- | --- |
| Spendable currency and ordinary materials | No writes | Native disk getter/serializer linkage or controlled quantity action pairs, and full integrity |
| Existing accessories, four skills and reinforcement | No writes | Occupancy/ownership, native record array, IDs/ranks, reinforcement/class dependencies and equipped references |
| Character EXP, level and permanent stats | No writes | Native per-character identity, disk fields, EXP curve and derived-stat/action dependencies |
| Three equipped accessories, items and horses | No writes | Existing owned record pools and native equipment selectors; horse unlock conditions |
| Endless Eclipse depths, desires and checkpoints | No writes | Permanent versus active-run records, per-character versus shared rewards and claim dependencies |
| Behelits, gallery, costumes, scenarios and story | No writes | Separate ownership/completion/claim/entitlement flags and prerequisite graph |
| Native title/revision and integrity | Outer envelope/title inspection only | Matching executable build/serializer or controlled native action pairs establishing revision and all inner integrity |

The shortest path to an editor is a matched Windows serializer/getter or
controlled native action pairs with the corresponding displayed values and
build context. Further unrelated progressed saves cannot qualify arbitrary
integer search/replacement. Needed inputs are:

1. The matching original `BERSERK.exe` for static serializer/getter analysis,
   with executable version/build, region and installed DLC context. It will
   not be executed or distributed. A source-backed Windows save editor is
   another route if its revision/record/integrity evidence is independently
   verified and its licence is respected.
2. Complete copied native save folders: an unchanged control plus before/after
   pairs for one purchase/sale, one material use, one existing accessory
   enhancement/amalgamation and one equipment change, with visible identities
   and quantities. Accessory promotion needs its own pair.
3. Per-character EXP/level/action-growth pairs and separate Eclipse checkpoint,
   first-desire completion and reward-claim pairs. Record story gates and
   active-run state without conflating them with resource edits.
4. Proof of all internal integrity and a native title/revision gate, followed
   by surgical payload comparisons and actual edited game-load/re-save
   validation on the identified Windows build.

The qualified outer envelope can be reused when those facts are available.
Until then, gameplay edits, GUI save/Undo/review workflows for this title and
edited game-load claims remain blocked; existing registered editors are
unaffected.

# Totori DX — decrypted PS4 export qualification

**Current result:** bounded, read-only inspection of the public **CUSA14014
GAMEDATA00** layout. This is not a registered editor. Cole, character and item
geometry now have concrete native correlations, but the PS4 game-internal
integrity model is still missing. No gameplay writer, GUI card or PC support is
claimed. Do not add a writable profile merely because the payload is plaintext.

## Exact source and platform

[Apollo issue 452](https://github.com/bucanero/apollo-saves/issues/452) provides
clear/New Game+ and system exports explicitly labelled decrypted PS4 CUSA14014.
The [official PlayStation listing](https://store.playstation.com/en-nz/product/EP4108-CUSA14014_00-APPA12TOTORI0000)
independently identifies the game. The clear archive contains one main
380,928-byte `USR-DATA.dat`, two identical 380,928-byte backup/copy files and one
excluded 336,112-byte alternate. The main and backups differ in many systems;
these are **two unique states, not controlled before/after action pairs**.
The separate 36,864-byte system export is excluded.

[The new inspector](../src/koei_editor/research/totori_dx_ps4/inspection.py) requires
both immutable exact-size gameplay bytes and bounded SFO metadata. It selectively
reads only `TITLE_ID=CUSA14014` and `SAVEDATA_DIRECTORY=GAMEDATA00`. The exported
metadata resides in `sce_sys/param.sfo`; account/signing fields and preview text
are never retained in its document. Other regions, directory identities, PC,
original PS3, system files and the alternate layout are rejected. The installed
revision is unknown; the profile is the full observed structural fingerprint.

PS4 PFS encryption, ownership and import signing remain external to the decrypted
export. This fact does **not** establish whether game-internal integrity exists.
An encrypted PS4 container is not accepted by the research inspector.

## Framing and read-only correlations

The little-endian word at zero is `20100403`, followed by a 32-byte header and
sequential `(u32 tag, u32 payload_size)` chunks. Every ordinary tag and size is
required, rather than identifying the title from magic or total length alone.
The ordinary payload sizes for tags 1–22 are:

```text
40848, 5172, 4, 3972, 152520, 51, 57164, 4, 5632, 1, 24,
68, 940, 1616, 8, 4536, 400, 1836, 15013, 168, 112, 64
```

Final tag 1024 begins at `0x46E39` and stores length 90,567 **including its
8-byte header**. This layout differs from equally sized Rorona DX PC files;
their inspector and this inspector reject one another's fingerprints. Header
reserved words and the trailer happen to be zero in the acquired copies, but
neither observation proves absence of checksums.

| System | Native correlation | What is still unproved |
| --- | --- | --- |
| Cole | Tag 3 is four bytes at `0xB3FC`. Its unsigned little-endian value agrees exactly with the main export's native Money preview. | Complete PS4 loader/integrity path, successful edited import/load and legitimate cap; no Max target is inferred. |
| Character records | Tag 4 begins `0xB408`: ten 396-byte records and a 12-byte opaque tail. Stored IDs are 0–9; stored level is `+4` and EXP lead `+8`. The main Totori, Mimi and Sterk level values independently agree with native preview. | PS4 character identity/catalog confirmation beyond preview, joined-state qualification, EXP thresholds, skill/derived-stat recalculation and level-up rewards. |
| Basket/container item geometry | Tag 7 begins `0x3179F`: 100 basket plus 999 container records, each 52 bytes, followed by 16 opaque/limit bytes. All 3,297 observed records across the three copies match occupied or canonical-empty constructor shape. | Full PS4 serializer and ID catalog, instance/reference semantics, acquisition rules, dependent equipment/shop/Chim references and checksums. |
| Basket/container limits | Immediately after all 1,099 records, the first two little-endian words agree with familiar 60/100 basket and 999 container limits in the inspected states. The remaining two words are opaque IDs. | Unlock/entitlement prerequisites and all limit invariants; physical capacity is not permission to enlarge an opened basket. |

### Item record evidence

[Arland fixes](https://github.com/nicoverbruggen/atelier-arland-fixes/tree/96a4506892de3284a8adc78a4b6a96d67e8bbf59)
(MIT) documents **PC runtime** constructors, 100/999 record capacities, ten
character sets, quality, five trait indices, four effect indices and a tail
word. These facts were independently compared against all native PS4 item
records. They are useful geometry evidence; runtime memory addresses are never
used as disk offsets.

The observed PS4 records consist of two signed ID words, IEEE-754 float quality,
five signed trait indices, four signed effect indices and a signed tail word.
Canonical empties have both IDs `-1`, quality `50.0` and all ten remaining words
`-1`. In the main export, one basket and 66 container records are occupied; in
the two identical backup copies, the basket is empty and six container records
are occupied. These counts are research comparisons, not files distributed by
this project. The first ID appears to distinguish instances and the second is an
item-ID lead; reference semantics are not promoted to ownership proof.

The source's 204 trait / 223 effect bounds and quality ceiling 120 corroborate
the ordinary inspected shapes. They do not prove applicability of any particular
trait/effect to an item. Unknown IDs, unusual float bit patterns, above-natural
values, and all opaque bytes remain preserved and readable in inspection. No
sanitization or repair is performed. Float bits are stored as integer bits in
immutable research records so NaNs do not invalidate an unchanged roundtrip.

### Additional exact-platform community mappings

The Japanese [PS4 Totori DX analysis thread 17325](https://web.save-editor.com/bbs/patchcode/ps4/bbs.cgi?list=pickup&num=17325)
independently supplies the following positions, all within the acquired
CUSA14014 chunks:

| Published PS4 mapping | Chunk-relative location | Current use |
| --- | --- | --- |
| Cole `0xB3FC` | tag 3 `+0` | Read-only native-preview-correlated value. |
| Character EXP `0xB410`, stride `0x18C` | tag 4 record `+8` | Read-only source-backed lead; no level/reward action. |
| HP/MP/LP/attack/defense/speed additive values `0xB43C`–`0xB450` | tag 4 record `+0x34`–`+0x48` | Six read-only stored bonus leads, kept separate from base/effective stats. |
| Item quality `0x317A7`, stride `0x34`, count 1,099 | tag 7 item `+8` | Independently corroborates the observed 52-byte inventory geometry. |
| Zero-based year/month/day `0x40D18/1C/20` | tag 11 `+8/+12/+16` | Read-only leads; no calendar rewinds. |
| Alchemy EXP `0x4178C` | tag 15 `+4` | Read-only u32 lead; no threshold/recipe changes. |
| Adventurer points `0x42AF0` | tag 18 `+0` | Read-only u32 lead; no rank/category/reward changes. |

These posts explicitly describe **CYBER Save Editor PS4 and Advance Mode**.
They establish exact-platform field leads, but the commercial save service's
hidden import/integrity processing prevents treating their lack of visible
checksum codes as proof that a standalone raw writer needs no checksum. The
related [PC discussion 3674](https://web.save-editor.com/bbs/community/pc/bbs.cgi?list=pickup&num=3674)
asserts matching PC/PS4 formats, but there is still no acquired native PC slot
or independent PS4 loader specification. Its linked PC save-sharing thread has
only administrative posts; its PS4 save-sharing thread's one download is
explicitly reported encrypted. Neither supplies a controlled decrypted edit
pair. No commercial code database is imported.

The [DX-specific carry-over guide](https://bozumemo.blogspot.com/2018/09/dx_15.html)
reports that all Cole and equipped weapons/armor/accessories carry into New
Game+, while container equipment does not. This explains why stored equipment,
container ownership and clear-state data must remain separate. It does not
qualify copying arbitrary inventory records into equipment.

### Why source-backed PC hooks do not qualify a PS4 writer

The MIT mod's save writer/loader detours call the original game functions with
an opaque stream after repairing loaded **memory**. They do not include the
whole file serializer, chunk reader, checksum coverage or checksum updater.
The documented three-byte [PC Cole tool](https://github.com/jrpx/AtelierTotoriColeCheat/tree/a5c683a85757d69ff4b4af614304a36e59119f89)
(Apache-2.0) happens to target `0xB3FC`, but neither that coincidence nor the
PS3 patch database establishes the PS4 integrity model. Original PS3 Totori's
Cole lead is `0x9554`, illustrating the edition difference.

No external editor/database, extracted catalog or private game file is copied
into this implementation. The inspector independently expresses the verified
structural facts and intentionally offers no `serialize` or `save_as` function.

## Mechanics coverage and concrete blockers

The [official game description](https://store.steampowered.com/app/936180/)
separates synthesis, exploration, battle, requests, adventurer points/ranks and
friendship. [The player-authored ending guide](https://steamcommunity.com/sharedfiles/filedetails/?id=1939593505)
describes calendar-sensitive boat/character events, travel-based friendship,
rank-specific request bonuses, a wealth-ending Cole prerequisite and Mimi's
level-up/event interaction. These facts describe mechanics, not save offsets or
blanket unlock permissions.

| Important mechanic | Implemented result | Exact requirement before safe writes |
| --- | --- | --- |
| Cole | Read-only native-preview-correlated u32 lead. | PS4 integrity qualification and controlled buy/sell plus edited import/load; a legitimate cap before Max. |
| Basket/container items and quantities | Read-only record geometry and raw instance/item IDs. No quantity field invented; physical item records are not fungible stack counts. | PS4 item/instance catalog, occupied slot ownership, move/use/delete pairs, all references and acquisition/limit rules. |
| Item quality, traits, effects and synthesis | Read-only original bits/indices; canonical empty/ordinary shape diagnostics. | Per-item applicability, synthesis cost/effect calculations, quality dependencies, native cached effects and a controlled synthesis pair. |
| Weapon/armor/accessory equipment | No writes or mapping guessed from the PC equipped-memory set. | Native PS4 equipped item records/references, recruited owner identity and controlled equip/unequip pair; confirm stat/skill cache updates. |
| Battle level, EXP, HP/MP/LP, stats and skills | Character IDs/level/EXP and six source-backed additive stat leads are read-only. | Native thresholds, derived stat/skill caches, recruits, level-up event/reward dependencies and a controlled battle level-up pair. |
| Alchemy level/EXP, recipes and books | Native preview confirms alchemy level; exact PS4 community source provides a read-only alchemy EXP lead. | Title-specific alchemy EXP/recipe acquisition records, recipe costs/eligibility, thresholds and controlled synthesis/book learning. |
| Adventurer licence, points, rank, quests and exploration | Native preview confirms rank; exact PS4 community source provides a read-only points lead. No point/rank writes. | Separate earned category counters/rank entitlement/map and quest flags, reward handling, licence renewal dates and controlled completed request/rank-up. |
| Friendship, character events and endings | No writes. Friendship is linked to travel and event prerequisites, rather than a universal unlock flag. | PS4 named friendship records and bounds, relationship/party/event prerequisites, one controlled travel/event pair per affected chain. |
| Chim workers, duplication, Hom-type automation and shops | No systems invented from related Arland editions; source describes Totori's Chims and item duplication. | Totori-specific worker/state/assigned item records, timers, unlock prerequisites and duplicated-item identity rules. |
| Boat construction, calendar, travel and story | Source-backed zero-based calendar leads are read-only; kept separate from ordinary resources. | Complete time/event transition rules, dependent timers, boat requirements and controlled travel/construction pairs. |
| Collections, music, gallery, bonus characters and New Game+ | Clear/system exports remain separate; no bulk content unlock. | Correct gameplay/system ownership and unlock records, DLC entitlement and carry-over prerequisites. |
| Game-internal integrity and supported revisions | Unqualified; all bytes preserved, no silent repair. | Static PS4 loader/file-writer evidence identifying every integrity check, or a controlled native edited import/load/re-save establishing handling for this exact layout. |

**Most useful next input:** the exact CUSA14014 gameplay executable/module for
static file reader/writer analysis, or a copy of a successfully Cole-edited
CUSA14014 export alongside its pre-edit original, displayed amount and native
load/re-save confirmation. A normal unchanged re-save plus one purchase/sale
pair would also separate preview/history from current money. Additional
controlled inventory/equipment/synthesis actions can qualify independently once
integrity is resolved. No missing account secret or game-specific key has been
proved; requesting one would currently be speculation.

## Tests and validation distinction

[Tests](../tests/test_totori_dx_ps4_candidate.py) cover all 22 tag/length pairs,
trailer bounds, same-sized foreign Rorona and system/alternate rejection,
required SFO title/directory identity, duplicate/missing/malformed metadata,
unknown-byte preservation, immutable/forged documents and exact unchanged
roundtrips. Metadata selection never retains account/signing values.

Seven tests pass with the optional native export directory supplied via
`TOTORI_DX_PS4_CANDIDATE_DIR`, including all three complete gameplay copies and
all 3,297 inventory records. Public procedural fixtures are patterned structural
inputs, not playable saves. The native main level/Cole checks use its original
preview; the copied backups can have stale preview and are not treated as a
controlled action pair. Gameplay edits, GUI workflows and actual game-load
validation were **not** performed because this remains an unregistered read-only
candidate. No game or downloaded editor binary was executed.

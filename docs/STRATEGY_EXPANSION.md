# Strategy-game expansion

The v1.9 expansion adds a separately qualified original Japanese Windows 95 [Tenshouki PK](NOBU6_PK_PC_FORMAT.md) district-resource editor. It does not qualify later Nobunaga campaign formats.

Investigated 2026-10-10 (UTC). The implemented profile is **original Romance of the
Three Kingdoms XIII, Windows PC, save revision 14, Traditional Chinese sample
qualification**. It edits existing city money, supplies, civilian population
and military population, wounded troops, fealty, commerce/farming/culture and
spear/horse/bow proficiencies through the shared editing workflow. See
[the format document](ROTK13_FORMAT.md). It does not imply Power Up Kit,
Switch, XIV, or Nobunaga campaign support.

## Candidate selection and licence boundaries

| Candidate | Evidence inspected | Result and exact missing inputs |
| --- | --- | --- |
| XIII original PC | Seven complete public player-shared TC campaign copies; independently decoded native headers and tagged records; static inspection of Van's published native save reader/writer and city-field definitions | Implemented only the demonstrated revision-14 city quantities. Exact executable build/DLC provenance and edited game load/re-save remain unavailable. Officer serialization and dependencies need further mapping. |
| XIII Power Up Kit, Switch JP | [EdiZon's original configuration](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/blob/d16d36c7509c01dca770f402babd83ff2e9ae6e7/Configs/0100882001380000.json) and [configuration generator](https://github.com/rushairer/san13pkeditorconfig) identify JP title 0100882001380000 and a direct binary editor; source history labels 1.0.0 | No complete genuine JP campaign was acquired. Need native size/title/revision/structure, integrity rules and an actual campaign. The published morale entry overlaps military population; it is not trustworthy. PC city stride is 0xF2, while this config uses 0xF6: offsets were not transferred. |
| XIV original and Power Up Kit, PC SC | Public player-shared native campaign and autosave copies; original `SN14SVD_VER0000` and expansion `SN14SVEXVER0000` headers | The `LWC\x1A` custom compressed body is unresolved. Need a qualified decoder/encoder with exact compressed stream and symbol-table semantics, native integrity, field mappings and unchanged roundtrips. Original/expansion header and body boundaries differ. No gameplay writer is registered. |
| Sphere of Influence, Windows PC | [Nobu14Editor Build0101](https://dl.3dmgame.com/patch/41946.html), [1.02 Build0208](https://dl.3dmgame.com/patch/55569.html), Japanese modding documentation and English system-completion descriptions | Both editor descriptions explicitly exclude save files. Memory/scenario/parameter/new-officer formats do not establish Western Sphere campaign offsets. Need a complete native campaign with edition/build provenance, disk codec/integrity and source-backed fields or controlled action pairs. `systemcfgPKEN.n14` completion data is not city/resource data. |
| Taishi, Windows PC | [Official mechanics manual](https://www.koeitecmoamerica.com/manual/taishi/en/index.html); Taishi_SimEditor_fmanager officer-editor listings; Japanese campaign descriptions | Officer-editor download pages returned HTTP 403; its source, input format and licence could not be verified. Published campaign archive endpoints returned HTTP 404. Unlock-only `prdataN.n15` and account configuration do not qualify a campaign. Need an accessible native campaign, disk encoding/integrity and a factual field map for the exact edition. |

No downloaded game/editor executable was run. Van's proprietary editor was
statically inspected outside the checkout; its redistribution notice requires
the author's permission. Its implementation, UI resources, catalogs and binaries
are not copied or shipped. The adapter independently implements verified format
facts. Unlicensed configuration repositories provide leads, not reusable source
or authority to assign their cheat targets as natural limits. No external
player-save contents, account identifiers or game assets are published.

The public-source search also reviewed [Vampirk/san13-editor](https://github.com/Vampirk/san13-editor)
(live Korean XIII PK objects; its `.S13` unpacker handles game-asset containers,
not campaign saves) and [RuruBros/San14Tenkazu](https://github.com/RuruBros/San14Tenkazu)
(live Korean XIV Complete Edition editing; disk officer registration applies to
new games, and its save probes record runtime JSON, not a native disk codec).
Neither repository provides an explicit project licence for reusing that code.
The [MIT-licensed XIV scenery editor](https://github.com/leafril/SAN14-Scenery-Effect-Editor)
changes runtime scenery data for one Korean Complete Edition build. Reported
save persistence establishes those runtime mechanics, but supplies no campaign
`LWC` encoder, checksum or city/officer disk map. No code from these sources is
used in the adapter, and no memory/scenario offsets are transferred into saves.

## Persistent mechanics versus outcomes

XIII city money and supplies are current stockpiles. Civilian, military and
wounded population are separately serialized components. Military population
is not a deployed unit's troop count, a private-army capacity, wounded/returning
troops, or a historical kill total. Editing a quantity does not change city
ownership, governor, ruler, army orders, events or scenario outcomes. A city's
district reference is not its force owner. Fealty, development and troop training
are current stored quantities; maximum growth, forecasts, unlock levels and
derived combat effects are separate fields and remain unchanged.

XIII officer base attributes, growth/experience, skill ranks, bonds, marriages,
sworn siblings, grudges, loyalty, treasure ownership and equipped references were
investigated but are not writable. The native officer section uses variable
serialization; memory layouts and Switch offsets do not establish its disk
coordinates. These systems require record identity and prerequisite/dependency
proof, preferably controlled action pairs and an unchanged control.

Taishi's [information manual](https://www.koeitecmoamerica.com/manual/taishi/en/6100.html)
distinguishes clan gold/provisions/horses/muskets, labor/seeds/fertilizer, base
militia/infantry/wounded/HP and officer LEA/VAL/INT/POL/FOR. Army/unit attributes,
forecast harvest/income and loyalty components can be derived. Treasure ownership
and marriage/clan relationships require separate dependency mapping. The manual
establishes mechanics, not serialized offsets. Historical/scenario editors and
story-unlock files were kept separate from campaign research.

## Validation boundary

Public tests generate procedural inputs; they contain no player data. Optional
native tests use `ROTK13_SAVE_COPIES`, pointing to a private folder of reviewed
copies. File qualification, edited reparse and surgical preservation are separate
from actual gameplay acceptance. **Edited saves were not loaded in a game.**
Windows executable building and Windows CNG validation are also not established
by Linux format/Tk checks. This branch changes no version, tag or release.

# Additional classic and strategy save-editor leads

This round distinguishes complete game-save writers from scenario editors,
runtime trainers and checksum-only patches. The following unfinished leads are
not supported editor registrations. No downloaded game/editor executable was
run, no player file was uploaded to a web editor, and no private save is bundled.

| Game/platform | Source inspected | Precise remaining input or proof |
| --- | --- | --- |
| Tenshouki with Power-Up Kit, original Japanese Windows | [Complete published native raw writer](https://github.com/tenshoukijp/nobu6_tool_savedataeditor/tree/69455e9f566874d8440a572041a61cc0c52e72fa); independently implemented `nobu6_pk_pc` | Genuine occupied 844,623-byte `SAVEDAT.n6p`, then edited game load/re-save; current source/procedural qualification is explicit in [its format document](NOBU6_PK_PC_FORMAT.md) |
| Romance of the Three Kingdoms XIII with Power-Up Kit, Switch | [EdiZon exact title configuration](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/blob/d16d36c7509c01dca770f402babd83ff2e9ae6e7/Configs/0100882001380000.json) and [complete bin.lua save-buffer writer](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/blob/d16d36c7509c01dca770f402babd83ff2e9ae6e7/Scripts/bin.lua) | Genuine exported `Partner-SaveData/savedata_pk*.s13` from title `0100882001380000` to establish native size/header/revision and platform binding; independently resolve conflicting field labels before writes |
| Bladestorm: The Hundred Years' War, Xbox 360 | [MarkH221 complete STFS save editor](https://github.com/MarkH221/BladestormSaveEditor), full open/patch/reinsert/rehash/resign path | Genuine original Xbox 360 STFS save and its first extracted gameplay file, to qualify exact container identity, slot framing and mapped records; PS3 files cannot substitute |
| Champion Jockey: G1 Jockey & Gallop Racer, PS3 | [Apollo patches](https://github.com/bucanero/apollo-patches/tree/main/PS3), `BLES01235` / `BLUS30863` | Genuine PFD-decrypted story/system files and source-backed writable gameplay fields; complete additive checksum is known, but checksum-only support is insufficient |
| Toukiden Kiwami, Vita | [Public checksum web tool](https://web.save-editor.com/tool/wse_checksum_fix_psvita_title_Toukiden_Kiwami.html) and Vita save collections | Complete published checksum/writer algorithm and matching genuine decrypted native export. The web tool posts to an opaque server CGI; its existence does not establish a local codec or field map |
| Romance of the Three Kingdoms XI, Windows | [PythWare/ROTK-XI-Tools](https://github.com/PythWare/ROTK-XI-Tools), complete `ROTK11_tool.pyw` | This source explicitly writes scenario mods, not saved campaigns. A complete campaign writer and matching native save are still needed |
| Uncharted Waters IV with Power-Up Kit, original Windows | [litsungyi/Dk4PkEditor](https://github.com/litsungyi/Dk4PkEditor) and [public original native files](https://github.com/supermizar/dk4pk) | Current active program is a reader; old editing entry is commented out and references an unavailable `Kafka::FileWriter`. Header word +24/integrity handling remains unqualified. HD mappings are not interchangeable |
| Uncharted Waters IV HD, Windows | [Kyeongrok/dh4-helper](https://github.com/Kyeongrok/dh4-helper), active `SaveEditService` money writer | Matching genuine HD native gameplay export and exact edition/header qualification; original small `.DK4` files do not qualify the HD layout |

## Switch XIII Power-Up Kit details

EdiZon binds its configuration to Switch title `0100882001380000`, explicitly
selects `Partner-SaveData`, and matches `savedata_pk\d+\.s13`. Its complete
`bin.lua` reads the opened native save buffer, changes declared bytes, and returns
the same full buffer. It performs no checksum or encryption transformation in
that save path. The configuration names Gold at `0x1322` and 60 city groups
with Gold/Food beginning at `0x56D6` / `0x56DA`, city stride `0xF6`.

These are useful public disk-editing facts, but the configuration alone does not
provide native magic, total size, revision or title-owner sidecar geometry.
It also labels each city's same stored address as both Soldiers and Morale;
these must not become two conflicting editable controls. Its published widget
ceilings are not independently proven natural game maxima. The existing
original Windows XIII revision-14 additive codec is expressly a different
edition and does not qualify these Switch files.

The NXResources/NX_Saves full non-truncated tree inspected during this round
contains no matching XIII export. The Nobu6 editor archives, including their
nested source ZIP, similarly contain no matching occupied player `.n6p`.
These searches establish which inspected collections lacked inputs; they do
not establish that no public save or editor exists elsewhere.

## Champion Jockey checksum facts

The published patches give separate complete unsigned additive checksums:
story seed `0x190518`, body `[0x10, 0x190528)`; system seed `0xA628`, body
`[0x10, 0xA638)`, both stored at `0xC`. Native byte order, title geometry and
editable record semantics still need a matching export and complete writer.
No account, jockey/career ownership, horse catalogue, progression or resource
mapping is inferred from these checksum spans.

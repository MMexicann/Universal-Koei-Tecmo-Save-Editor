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
| Toukiden 2, Japanese Vita | [Genuine Apollo export](https://github.com/bucanero/apollo-saves/tree/master/PSV/PCSG00830), labelled story mode cleared | Native plaintext files and original title sidecar are now acquired; complete checksum/writer and source-backed gameplay field semantics remain missing |
| Toukiden: The Age of Demons, US Vita | [Apollo archive](https://github.com/bucanero/apollo-saves/tree/master/PSV/PCSE00381) | This archive contains only encrypted Vita Content Manager `savedata.psvimg` / `psvmd` / `psvinf`, not a decrypted gameplay export; original owner decryption context or a decrypted export and complete native writer are required |
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

Following configuration history also recovered the
[original author generator](https://github.com/rushairer/san13pkeditorconfig).
Its `index.js` independently assigns both Soldiers and Morale to city +`0x42`;
this confirms the conflict originates in the source generator, rather than a
transcription error in a mirrored configuration. No native save or relevant
issue attachment was present in that source repository.

The NXResources/NX_Saves full non-truncated tree inspected during this round
contains no matching XIII export. The Nobu6 editor archives, including their
nested source ZIP, similarly contain no matching occupied player `.n6p`.
These searches establish which inspected collections lacked inputs; they do
not establish that no public save or editor exists elsewhere.

## Toukiden native acquisition and source blockers

The Japanese Toukiden 2 export contains twelve gameplay files named
`play00`, `play01`, and `play02`, each with separate `user`, `safe`, `chkp`,
and `btle` variants. Slot 0 files are 497,875 bytes; slots 1 and 2 are
497,629 bytes. `system.bin` is 39,565 bytes. These are low-entropy plaintext
native data with the original Vita title sidecar; none was conflated with a
Kiwami or PC file. No matching current regional Toukiden savepatch was present
in the official Apollo PSV collection, and current `apollo-lib` native
decryption/patch modules provide no Toukiden-specific checksum implementation.

The public checksum site's forum and Toukiden 2 page returned HTTP 403 during
the follow-up inspection. No access controls were bypassed and no player file
was sent to its server. Remaining requirements are a complete native checksum
and disk-record writer, or equivalent statically recovered serialization, and
proven Haku/equipment/Mitama/material/mission mappings with their dependencies.
Plaintext alone does not qualify a working save editor.

## Champion Jockey checksum facts

The published patches give separate complete unsigned additive checksums:
story seed `0x190518`, body `[0x10, 0x190528)`; system seed `0xA628`, body
`[0x10, 0xA638)`, both stored at `0xC`. Native byte order, title geometry and
editable record semantics still need a matching export and complete writer.
No account, jockey/career ownership, horse catalogue, progression or resource
mapping is inferred from these checksum spans.

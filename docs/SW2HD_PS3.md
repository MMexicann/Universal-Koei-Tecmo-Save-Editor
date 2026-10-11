# Samurai Warriors 2 with Xtreme Legends HD: Japanese PS3 research

No gameplay adapter is registered. The unregistered
[`inspection.py`](../src/koei_editor/research/sw2hd_ps3/inspection.py) offers
bounded, immutable, **read-only candidate probes**. It cannot open a qualified
game session, stage changes, serialize, repair integrity or write player files.
Neither a successful probe nor matching candidate checksums identifies the game.
`inspect_export(DATA_BIN_bytes, PARAM_SFO_bytes)` additionally rejects a
conflicting companion title through the shared bounded, selective SFO reader.
It retains only the public candidate title ID, not metadata/account values or a
save-directory suffix. Matching context still leaves gameplay qualification and
editing disabled.

## Exact editions and source-backed leads

The candidate is Japanese PS3 **Sengoku Musou 2 with Moushouden HD Version**,
PSN `NPJB00439`. The disc compilation `BLJM61092` contains both this game and
Empires; its two gameplay profiles cannot be combined. Apollo's patch title
includes “Empires,” but its money/checksum offsets are not an Empires profile.
Original PS2, PS2 virtual-memory-card exports on PS3, PC, Xbox 360 and Vita files
are separate and do not qualify this candidate.

The [official HD product description](https://www.gamecity.ne.jp/sengoku2/hd/)
distinguishes the with-Xtreme-Legends and Empires titles, their trophies and
game modes. All 32 playable with-Xtreme-Legends officers are available initially.
Officer availability therefore must not be used as proof of story completion.
The published cross-save feature does not establish identical PS3/Vita bytes.

## Mechanics that affect the eventual editor

The official HD description distinguishes Story/Free, Survival, Mercenary and
Sugoroku modes. Story endings, survival records, mercenary objectives and
Sugoroku finances must not be bundled into a global money/stat action. The
Empires campaign and custom officers belong to a separate game profile.

The [HD/XL progression guide](https://game-de.com/sengoku2/status/max.htm)
describes officer level 70 and continued stat growth after level/merit reaches
its ceiling. Therefore editing EXP alone must not imply fully grown stats.
The primary archived save discussion reports a 150,000 EXP ceiling and
gameplay normalization of higher values; this remains a source observation,
not a qualified save-field bound or a reason to normalize opened values.

The [weapon-effect guide](https://game-de.com/sengoku2/buki/bukikouka.htm)
describes eight effect slots, at most three occurrences of the same effect,
and ordinary effect strength +20. Its
[orb/fusion guide](https://game-de.com/sengoku2/neta/houzyu.htm) separates
earned fusion materials from the effects purchased with them. The published
+99 cheat is consequently not a legitimate Max target. Ownership flags,
active effect count, effect multiplicity and material-consumption dependencies
still require actual native records before a weapon/fusion writer is exposed.
No third-party guide table, roster, asset catalog or editor code was imported.

The [Apollo mapping](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPJB00439.savepatch)
identifies `DATA.BIN`, a big-endian money DWORD at `0x2758`, and the sum of bytes
`0x8..0x36DF`, stored as big-endian DWORDs at `0x36E0` and `0x23790`.
The 9,999,999 money patch target is not evidence of a natural gameplay cap.
The independently written diagnostic does not copy Apollo GPL code or patches.

Primary user research in [archived thread 7070](https://web.save-editor.com/cache/bbs_savedata_ps3/7070.html)
supplies three EXP anchors: Yukimura `0x2C`, Ina `0xE3C` and Katsuie `0x1D3C`,
with reported officer stride `0xF0`. Three proposed Yukimura weapon positions
are `0x47`, `0x5A` and `0x6D`, each `0x13` bytes: type, element, eight effect IDs,
eight effect values and a count. The source explicitly leaves acquisition flags
unmapped and reports display corruption at +99 and freezing above it. A later
post questions the first two gem offsets. The inspector exposes only those raw
EXP/weapon anchors; it does not manufacture a complete roster, infer ownership,
interpret effect IDs, normalize counts, or treat reported targets as edit bounds.
No third-party editor implementation or enumeration catalog was imported.

## Qualification blockers and per-system coverage

| System | Implemented coverage | Evidence needed for gameplay controls |
| --- | --- | --- |
| Native profile and integrity | Bounded candidate checksum diagnostics | Genuine decrypted `NPJB00439` export, exact length/header/revision and all section integrity; independently qualify disc identity before adding it. |
| Money | Read-only source-proposed DWORD | Above native profile and legitimate bound; a controlled purchase/reward pair to exclude display/history aliases. |
| Officer EXP, level and growth | Three read-only published EXP anchors | Native record identity/count and level/EXP thresholds, derived stats, skill/reward dependencies. The proposed stride alone does not qualify all records. |
| Skills | None | Purchased/acquired IDs, rank bounds and acquisition/EXP prerequisites. |
| Weapons, elements, effects and fusion | Three raw candidate weapon probes | Actual ownership/acquisition flags, equipped references, record identity/type compatibility, safe effect ranks/counts, and fusion/reward dependencies. |
| Gems and inventories | None | Resolve contradictory offsets; independent quantity/order/cap and ownership evidence. |
| Mounts and bodyguards | None | Existing-record identities, acquired/equipped references and growth dependencies. |
| Survival, Mercenary and Sugoroku | None | Mode-specific records, current versus historical counters, reward dependencies. |
| Story, stages and collections | None | Exact separate completion/collection bits and prerequisite/reward behavior; never bundle these into money or EXP. |

The published sum covers only an initial section. Changes to the header and
later sections can retain both matching sums; compensated byte changes can
also collide inside the range. Matching sums therefore prove neither complete
native integrity nor title/revision identity. The minimum probe size `0x23794`
only reaches the last published checksum DWORD; the 2 MiB ceiling limits
processing. Neither is a claimed native file size.

## Genuine inputs and validation

The independently reviewed public [upload thread 258](https://web.save-editor.com/bbs/savedata/ps3/bbs.cgi?list=pickup&num=258)
has no SW2 HD save attachment. The PS3 GameFAQs pages for
[compilation 723490](https://gamefaqs.gamespot.com/ps3/723490-sengoku-musou-2-with-moushouden-and-empires-hd-version/saves)
and [with-Xtreme-Legends 737594](https://gamefaqs.gamespot.com/ps3/737594-sengoku-musou-2-with-moushouden-hd-version/saves)
also supplied no matching downloadable native fixture. Related PS2 virtual-card
downloads are not HD exports. No matching native serializer source or qualified
full export was found in this investigation. No game/editor binary was executed.

The renewed investigation rechecked the two exact PS3 GameFAQs profiles,
Apollo's public save-database tree, Japanese upload/editing archives, an
RPCS3 compatibility thread, Reddit, NextGenUpdate and Japanese/English searches.
The standalone and compilation GameFAQs pages still have no matching native
download. Some forum pages could not be inspected because they rejected
automated access; no claims are made about attachments behind those blocks.

A genuine public save was downloaded from the separately indexed
[SW2 Empires HD GameFAQs page](https://gamefaqs.gamespot.com/ps3/737592-sengoku-musou-2-empires-hd-version/saves).
Its companion identifies **NPJB00464**, not NPJB00439; it is therefore rejected
by `inspect_export` and does not qualify this editor. Search snippets mentioning
“Mushouden” on that page are game aliases, not proof that the archive contains
the with-Xtreme-Legends profile. No player files are included in this project.

The [checksum-support reference](https://emu.web-g-p.com/info/system/save_ps3_system_title_supported_checksum.html#checksum_sengoku_musou_2_hd)
explicitly distinguishes the with-Xtreme-Legends title's two checksum operations
from Empires, which has none. The
[archived questions thread](https://web.save-editor.com/cache/bbs_savedata_ps3_etc/3904.html)
records actual corruption after historical money/gem patches. These establish
why the separately sourced sum patch and a filename alone cannot justify a
writer; they do not establish any additional checksum formula.

**Minimum input to unblock the next step:** a copied **decrypted** gameplay
`DATA.BIN` from Japanese PS3 Sengoku Musou 2 **with Xtreme Legends HD** and
its original `PARAM.SFO` companion, with the displayed money and one officer's
name/level/EXP recorded. The exact source title/build is needed. An early-game
save plus a before/after purchase or EXP-reward pair is preferable to a fully
modified save. Disc owners should state that it came from the compilation's
with-Xtreme-Legends title, rather than Empires; disc identity remains a separate
qualification. An encrypted export can be decrypted by its owner with Apollo.
No game executable, account ID, console key or login is requested.

### Separate Empires HD lead: NPJB00464

The newly acquired public PS3 Empires export is an initialized **0%** save,
with original companion title `NPJB00464`. Its encrypted `DATA.BIN` is
`0x97400` bytes. Private static PS3-envelope investigation produced a
same-length plaintext candidate beginning with big-endian DWORD `0x485`;
decrypt/re-encrypt reproduced the original encrypted bytes exactly, and the
original export remained unchanged. This is envelope/candidate evidence,
not an implemented gameplay editor or an edited game-load test.

The initialized sample has no populated campaign state: all later sections
beyond the initial system records are zero, including the published campaign
money example. Thus it does not provide positive edit evidence for campaign
resources, officers, domains, troops or policies.

The primary [archived editing discussion](https://web.save-editor.com/cache/bbs_savedata_ps3/7070.html)
distinguishes Empires campaign money from the save-list preview value. It
reports that the campaign stores money in units of ten, as a big-endian word,
and that the actual location varies with scenario and chosen daimyo. Its
example address `0x8397E` concerns slot 1, the 1561 Kawanakajima scenario and
Ashikaga Yoshiteru; it is **not** a universal Empires offset. The separate
preview at `0x15F0` must not be used as spendable campaign money. Both the
discussion and the checksum-support reference describe Empires as having
no internal checksum, unlike with-Xtreme-Legends.

To qualify a separate Empires editor, obtain a copied decrypted
`NPJB00464 DATA.BIN` and original companion **after starting and saving an
actual campaign**, recording slot, scenario, daimyo and displayed money.
A before/after purchase or policy expenditure plus an unchanged control is
needed to identify the actual campaign record and unit conversion. Additional
scenario/daimyo copies are required before claiming a general variable-layout
writer. Officer training, troop/domain resources, policies, campaigns and
collections need their own controlled action pairs and dependency mappings.
The initialized export, with-Xtreme-Legends mappings and PS2/PC/Vita/Xbox
offsets cannot substitute for these inputs. No Empires library entry was added.

Six procedural tests in
[`test_sw2hd_ps3_candidate.py`](../tests/test_sw2hd_ps3_candidate.py) pass:
bounded immutable input, big-endian money and duplicate sums, preservation of
unusual raw EXP/weapon values, matching/foreign/malformed companion metadata,
and negative proof that partial sum matches never enable editing or native
qualification. These are **synthetic diagnostic tests**. Separately, the
downloaded genuine Empires export was rejected through its original companion
metadata. That is genuine wrong-edition rejection evidence, not positive
with-Xtreme-Legends validation.
There is no genuine-file no-op/edit evidence and no actual game-load/re-save
test for this profile. GUI backup/save/restore tests would require a qualified
writer and are consequently not claimed.

Any future adapter would edit copied **decrypted gameplay exports** only.
Apollo/external tooling would still be required to reimport and resign the
console save. Editing `DATA.BIN` does not rebuild PS3 `PARAM.PFD`, encrypt the
export, change ownership, or establish a game-load test.

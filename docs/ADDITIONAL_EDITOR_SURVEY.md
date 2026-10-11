# Additional save-editor survey

This follow-up revisited every earlier screenshot recommendation and broadened
native-save searches across Koei Tecmo, Omega Force, Gust and Team Ninja games.
The table records factual leads and specific blockers; it does not activate
unsupported library entries. Existing code was read for format facts and
independently implemented. Restricted or unlicensed implementation code and
catalog dumps were not incorporated.

| Lead / game | Outcome |
| --- | --- |
| [Hyrule Warriors Wii U and Age of Calamity editors](https://github.com/marcrobledo/savegame-editors) | Existing explicit Wii U/Switch adapters retained and rechecked. Growth, reward and fusion dependencies are tracked in [family notes](FAMILY_NEXT_RESEARCH.md). |
| [Hyrule Warriors Legends editor](https://github.com/nedron92/HWL-SaveEditor) | Separate 3DS native export acquired and qualified; original adapter adds resources, existing cards/weapons and owned fairy names. See [format notes](HYRULE_LEGENDS_FORMAT.md). |
| [Hyrule Warriors Definitive editor](https://github.com/iAroc/iAroc.github.io/tree/15e4a928bdffb202a7893e14fde432f2dcbc10b3/hyruleWarriors) | Existing Switch adapter expanded with existing generic weapon stars and ordinary seal KO reductions. Master Sword and special/collection seals excluded. |
| [EdiZon community definitions](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts) | Existing Switch HWDE/Fire Emblem formats independently qualified; definitions alone do not establish natural caps or reward-safe growth. |
| [Apollo patches and saves](https://github.com/bucanero/apollo-patches) | DW7/SW4/DW7 Empires PS3 available. SW2 HD Japanese, DW8 Empires, Strikeforce and WO3 PS3 are separately investigated; platform-specific checksums, ownership/layout or missing native exports remain blockers. |
| Totori DX PC money source | Actual Totori app936180 native gameplay/save framing still missing. Rorona app936160 samples are deliberately rejected. See [Totori notes](TOTORI_PC_RESEARCH.md). |
| Dynasty Warriors 6 C# research | Existing PC adapter gains named existing weapon elements. No source implementation copied. Progression/reward/horse transformation writes require separate proof. |
| Dynasty Warriors 5 Special legacy editor and contemporary native guide | Genuine Windows revision3 save and static checksum/I/O evidence support an original item/weapon editor. No third-party binary executed. See [DW5 notes](DW5_SPECIAL.md). |
| Legacy Xbox360 DW5/6 Empires, DW7, SW2/XL, WO1/2 editors | Binary-only/forum-gated downloads or unclear source licences cannot qualify native title identity, signed containers or dependencies. Need separately extracted native gameplay copies and exact title/region. |
| PS4 Save Wizard / Chaoszage SW5 | Commercial GUI examples are evidence of another product, not reusable source or a qualified PS4 serializer here. Need legally decrypted native exports and independent integrity/maps. |
| [Persona 5 Strikers PC utility](https://github.com/zarroboogs/p5spc.saveutil) and [Switch editor](https://github.com/Amuyea-gbatemp/Persona-5-Strikers-Scramble-Save-Editor) | Two full native PC player saves close PC framing/checksum gaps. Original bounded PC writer preserves neighboring bytes, stream context and reserved block. Switch/PS4 remain separate. |
| Nioh / Nioh2 / Nioh3 / Wo Long / Stranger of Paradise | Genuine Nioh copies decode, but clearing checksum flags is rejected. Wo Long gains a native-checksum-verified original lexical JSON writer. Nioh3 published fixed inventory offsets fail genuine profiles. [Detailed findings](TEAM_NINJA_RESEARCH.md). |
| Atelier Ayesha PS3 editor | Three independently decrypted public US/Japanese exports match framing; two advertised Japanese Cole values corroborate money exactly. Native quality is float32, not the upstream lossy integer approximation; two memory words remain distinct and read only. |
| [Ninja Gaiden 2 Black editor](https://github.com/real-guilty/NG2B-Save-Editor), [Nexus listing](https://www.nexusmods.com/ninjagaiden2black/mods/117) | Public Steam-only compiled editor statically inspected without execution. Flags for Chapter Challenge/Master Ninja and Tag completion are factual leads, but it lacks file identity/integrity checks; no qualified native Steam SYSTEMSAVE.DAT.sav acquired. Game Pass 1.1 support is explicitly broken and removed in 1.2. Story-bit brute force and collection-trigger prerequisites are not safe native mappings. No binary/source reused or new adapter registered. |
| [Ninja Gaiden II Xbox360/Xenia checksum utility](https://github.com/ike9000e/ngii-save-update-util) | The separate [extracted revision-6 story editor](NINJA_GAIDEN_RESEARCH.md) implements Yellow Essence and existing consumable/ammunition reductions, qualified with genuine stories. Container extraction/signing, other revisions, weapon/reward dependencies and actual edited game loading remain separate. |
| Fire Emblem Warriors: Three Hopes | Earlier LINKDATA templates are assets, not saves. A separate save-specific MIT template and public exported slots were found in the follow-up; all 144 native section checksums now qualify six public exports. A separate original adapter provides guarded owned-character name customization and gold reductions; deeper class/growth/forging/reward systems remain protected. [Format checklist](THREE_HOPES_FORMAT.md). See [family notes](FAMILY_NEXT_RESEARCH.md). |
| DQ Heroes I/II, Berserk, Attack on Titan 1/2 | Native files and editor/runtime leads are revisited individually. A genuine sample is a useful control, not a field or checksum mapping by itself; current per-title findings are in family/coverage notes. |
| Toukiden Kiwami and Toukiden 2, Windows | Separate publicly shared native-named PC archives acquired privately. Windows codec/integrity and writable mappings remain unproved; plaintext companions and runtime/console tools do not qualify an editor. See the separate [Kiwami](TOUKIDEN_KIWAMI_RESEARCH.md) and [Toukiden 2](TOUKIDEN2_RESEARCH.md) mechanic checklists and rejected hypotheses. |
| Monster Rancher 1 & 2 DX, Windows | Runtime viewers, mod sidecars and PS1 documentation were distinguished from native DX serialization. The previously shared DX saves were removed because of embedded player IDs; no complete native fixture acquired. [Separate MR1/MR2 blockers](MONSTER_RANCHER_DX_RESEARCH.md) cover money, development, condition, lifespan and ownership. |
| Romance of the Three Kingdoms, Nobunaga's Ambition, Fatal Frame and Blue Reflection | [Original PC ROTK XIII](ROTK13_FORMAT.md) city quantities and [Fatal Frame II Remake](FATAL_FRAME2_REMAKE_FORMAT.md) system Photo Point reductions are implemented. Other ROTK editions, Nobunaga, Blue Reflection and unqualified Fatal Frame profiles remain research-only; see each format and candidate checklist. |

Source-only discoveries stay under research, never as advertised game cards.
The [supplier checklist](REMAINING_INPUTS.md) gives precise files for unresolved
current candidates. Actual edited game-load/re-save validation remains separate
from automated native-file and GUI verification.

## Next minor-release research

Six separately reviewed profiles have been implemented in development source:
[Persona 5 Strikers PS4](P5STRIKERS_PS4_FORMAT.md),
[original Project Zero PS2](PROJECT_ZERO_PS2_FORMAT.md),
[New Horizons DOS](UNCHARTED_WATERS2_DOS_FORMAT.md),
[Ryza 3 DX PC](RYZA3_DX_PC_FORMAT.md),
[Monster Rancher DS](MONSTER_RANCHER_DS_FORMAT.md) and
[Tecmo Super Bowl NES](TECMO_SUPER_BOWL_NES_FORMAT.md).
New Horizons remains published-format support without an occupied player-save
fixture; the other native-file qualifications and all game-load distinctions
are recorded in their individual documents. The canonical supported inventory
is authoritative for current registrations.

[Fairy Tail Switch](FAIRY_TAIL_SWITCH_RESEARCH.md) now has complete verified
native block checksums, but wallet/item meanings still need controlled gameplay
pairs. It remains unregistered.

**Marvel Ultimate Alliance 3 — Switch** was also revisited as a Team Ninja
candidate. Genuine exported slots and public costume-edit/load reports were
located in the [save-editing discussion](https://gbatemp.net/threads/marvel-ultimate-alliance-3-save-editing.543823/page-15).
The Deadpool costume states mix Expansion Pass, Infinity and other reward
prerequisites. Changing an already-owned outfit's viewed flag is distinct from
granting ownership. Complete native integrity, character-record ownership and
useful prerequisite-safe field mappings remain unqualified, so no supported
entry or bulk costume unlock was added. Useful next inputs are exact-title
same-build native locked/earned/viewed action pairs with displayed outfit names,
original companions and unchanged controls, or a complete native writer.

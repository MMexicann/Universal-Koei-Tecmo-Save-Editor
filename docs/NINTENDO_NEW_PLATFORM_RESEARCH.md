# Additional Nintendo/Warriors platform investigation

This round investigated actual new game/platform profiles rather than adding
unverified variants to the supported library. Complete full writers and genuine
exports remain prerequisites; live-process cheats, empty repositories, generic
console envelope tools and unrelated platform offsets do not qualify editing.

| Candidate | Sources rechecked and current result | Exact enabling input |
| --- | --- | --- |
| Fire Emblem Warriors — Nintendo 3DS | GitHub title/editor/save queries, [ayink/few](https://github.com/ayink/few) (empty repository), the public 3DS editor-library tree, and the dedicated existing Switch writer. No complete 3DS gameplay writer plus matching native export was acquired. The main save-editing discussion/GameFAQs pages rejected this round's automated requests; no assertion is made about inaccessible attachments. | A complete extracted genuine 3DS gameplay save with exact title/region/build and its filenames, plus a complete accepted native writer/loader or controlled edit/load/re-save pairs proving integrity and named resource/material/weapon structures. Switch `scenario` maps are not reused. |
| Dynasty Warriors: Strikeforce — US/EU PS3 | Fresh [full editor source](https://github.com/alsharfa/Dynasty-Warriors-Strikeforce-ps3-save-editor/tree/a92709c2b8aedb6bbd23a36afad4bb0228d376ff) is unchanged from the prior checked commit. The bundled `reference/00006.bin` remains a weapon database, not a player save. Its verification notes describe reversible scalar file writes, not native edited-load integrity. Existing two genuine US exports and read-only records remain separate from the EU source. | Native serializer/integrity behavior or credible controlled accepted US edit/load/re-save evidence; matching EU native exports if qualifying BLES00825 separately. Selected/persistent officer growth and inventory ownership need controlled pairs. [Full checklist](STRIKEFORCE_PS3.md). |
| Samurai Warriors 2 with Xtreme Legends HD — Japanese PS3 NPJB00439 | Rechecked existing exact-edition sources and current Apollo database: no NPJB00439 native export was acquired. Its partial section sum and wrong-edition initialized NPJB00464 Empires file cannot register a gameplay writer. | Complete decrypted NPJB00439 `DATA.BIN` with original `PARAM.SFO`, displayed money/level/EXP and full section integrity/serializer proof; controlled money/growth/equip pairs. [Full checklist](SW2HD_PS3.md). |

A concrete working alternate was acquired from the public
[Apollo CUSA19640 database](https://github.com/bucanero/apollo-saves/tree/master/PS4/CUSA19640):
**English Persona 5 Strikers for PS4**, a new platform for this project. Its
complete platform converter, native export and original title metadata qualified
[a dedicated useful editor](P5STRIKERS_PS4_FORMAT.md) with resources, named
existing item stacks, searchable inspectors and safe contextual storage.
No player saves, owner fields, binaries, foreign code or private paths are shipped.

## Further platform fallbacks checked

- **Dragon Quest Builders 2 — PS4:** the freshly inspected
  [Hermit's Heresy source](https://github.com/default-kramer/HermitsHeresy)
  has no PS4-specific serializer/profile and its labelled captured examples are
  Steam files. The complete turtle-insect writer explicitly supports Switch and
  Steam. The checked current Apollo PS4 catalog has no Builders entry or
  acquired decrypted PS4 CMNDAT. A complete genuine **decrypted PS4 `CMNDAT.BIN`
  with original `sce_sys/param.sfo`**, exact title/revision and matching original
  slot companions is needed, plus an explicit complete PS4 native writer or
  controlled accepted edit/load/re-save pairs before reusing inventory geometry.
  Similar-looking `aerC` headers alone do not register PS4 support.
- **Metroid: Other M — Wii:** title-specific public repository searches found
  [Other M Redux](https://github.com/ShadowOne333/Metroid-Other-M-Redux), gameplay
  patches and HD/controller setup. Its documented Hard/Theater/Gallery action
  is a live-memory Gecko patch, not a disk-save writer; its note says the
  Gallery remains empty. No complete game-native save serializer/checksum or
  named disk-record mapping was acquired. A genuine extracted title/region-
  labelled Wii gameplay save plus complete native integrity and field evidence
  is required. Generic Wii export/decryption and runtime flag addresses do not
  establish the game's inner format or collection dependencies.

Some new public web searches returned bot challenges; inaccessible pages are not
reported as inspected. No console saves, game/editor binaries, private paths or
foreign code are published by this investigation.

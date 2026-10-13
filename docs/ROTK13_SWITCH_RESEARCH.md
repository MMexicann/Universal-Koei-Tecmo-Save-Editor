# Romance of the Three Kingdoms XIII Power-Up Kit — Nintendo Switch

This is a new research lead for Switch title `0100882001380000`, separate from
the registered original Windows revision-14 Traditional Chinese editor. It is
not a supported profile. No adapter or gameplay writer has been registered.

## Actual disk-editor evidence

The pinned [EdiZon save-editor configuration](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/blob/d16d36c7509c01dca770f402babd83ff2e9ae6e7/Configs/0100882001380000.json)
targets `Partner-SaveData/savedata_pkN.s13` and declares 363 controls: three
general balances and six controls for each of sixty city records. This is an
EdiZon **disk-save configuration**, distinct from the repository's separate
Atmosphère memory cheats. It is explicitly marked beta.

The accompanying [binary save script](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/blob/d16d36c7509c01dca770f402babd83ff2e9ae6e7/Scripts/bin.lua)
reads the save-file buffer, writes specified little-endian scalar bytes and
returns that modified buffer. It does not implement a title-specific decoder,
revision gate or native integrity recalculation. Its complete generic writer
establishes that the source intends direct disk writes; it does not establish
complete integrity coverage or compatibility with every Switch revision.

The configuration's first city gold value is four bytes at `0x56d6`; the sixty
city records use a `0xf6` stride and the last city gold word is `0x8f88`.
The general gold word is at `0x1322`. These are source claims, not independently
validated native addresses. The advertised maximum 999,999 is an editor limit,
not independently proven natural gameplay capacity.

Each city's purported morale control aliases the same offset as its soldiers
control. For example, both first-city labels target `0x56e2`. This conflict is
present in the published configuration and prevents treating all labels as
verified distinct gameplay resources. No catalogue or implementation was copied.

## Exact inputs needed

- A complete native Switch export for this title, with build/language, file and
  slot identity; retain the original companion directory privately.
- Exact title/revision/length recognition and native integrity coverage proved
  from a serializer or controlled native re-save evidence. The generic script
  alone does not prove the absence of a checksum.
- Unchanged control and one displayed gold/food action pair, establishing city
  ownership, actual scalar semantics and field relationships independently of
  the conflicting soldiers/morale labels.
- Surgical roundtrip, corruption/foreign-edition rejection, safe storage and
  GUI verification before registration; actual edited game loading separately.

Online and repository review found this complete published generic writer, but
no matching native qualification sample or integrity proof. Validation in this
pass: no Switch adapter tests, no genuine-file roundtrips and no edited game-load
checks. Windows XIII geometry and its checksum rules were not transferred.

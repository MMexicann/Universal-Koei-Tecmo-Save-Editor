# Pokémon Conquest — North American Nintendo DS

The adapter edits individual values (IVs) of existing gallery Pokémon in raw
`.sav` exports. It exposes four separate numeric controls per qualified record,
with 0–31 bounds, selected/bulk Max, a searchable gallery inspector and the
shared backups, Undo, Review Changes and atomic Save As workflow.

The three HP/attack/defense components have explicit numbered labels because
their individual stat ordering is not independently documented. The fourth is
Speed IV. This preserves honest before/after values even where a Pokémon's four
opened IVs differ; there is no composite scalar hiding unequal original values.
Forretress Speed is excluded from Max and remains available for deliberate
individual edits. Its Gyro Ball benefits from slower user speed; Max must not
silently discard that build choice. No Pokémon is created, moved or relinked.

## Native structure and integrity

Qualified raw lengths are 262,144 and 524,288 bytes. All 26 section headers must
contain `TWL-P-VPYT\0\0`, independently documented as the North American game
code. Each of the two native banks has 13 sections, occupying `0xB5BE` bytes:

```text
A0 A0 30 C76 AB8 1A58 A44 2278 F18 504 408 E0 3D08
```

Each header contains a little-endian 32-bit checksum at +0, a descriptor at +4,
a generation counter at +8 and the title marker at +12. The checksum is the sum
of the payload bytes after the 24-byte header. Fixed sections cover their whole
physical payload and require descriptor zero. Scenario-Pokémon section 7 and
gallery section 12 use the descriptor shifted right nine bits as their checked
payload length. Native samples have zero low descriptor bits; other flags are
rejected. Dynamic lengths must fit the original physical section boundaries.
Every section is verified before any writable field is offered. Bad input is
rejected rather than repaired. Outer unused space must have the observed erased
`FF` padding; the original 256/512 KiB length is preserved.

Gallery sections begin at `0x78B6` and `0x12E74`. After their 24-byte header and
`0xE10` bytes of warrior-gallery data are counted 12-byte Pokémon records. The
checked gallery length must be at least `0xE10` and its remaining bytes divisible
by 12. Only declared existing records with exact vanilla species words 0–199
are writable. Unknown species/flagged words remain inspectable and unchanged.

IV components occupy five-bit ranges at record +4, shifts 15/20/25, and +8,
shift 0 for Speed. Writers merge those five bits into the original word, retaining
EXP-related/unknown packed bits, flags and neighboring components. Only a touched
gallery section's checksum is recomputed. No generation counter is incremented.

Both banks retain their own original records, lengths, generation counters and
field groups. Their slots are not assumed to represent matching Pokémon. Select
both groups for a bulk action affecting both generations. Scenario Pokémon and
gallery Pokémon are separate serialized systems; this editor does not imply
that a gallery edit changes the current army's corresponding Pokémon.

ARDS `.duc`, DeSmuME `.dsv`, compressed/container saves, European/Japanese titles
and expanded record layouts are rejected. A ROM hack retaining an identical
vanilla save layout cannot be identified from these bytes alone; this adapter's
supported scope is the original North American game.

## Evidence and licences

- [MathyFurret's Conquest Save File Patcher](https://github.com/MathyFurret/conquestsavefiletools)
  provides an actual North American save writer, gallery bounds, 12-byte records,
  IV bit masks and byte-sum repair. Its Forretress option specifically sets the
  fourth IV to zero. Its issue 1 documents incompatibility with Pokémon-slot
  expansion hacks. No explicit repository licence was found: this adapter is an
  independently written implementation of factual file mappings, not copied code.
- [Deijin27's conquest-hexpat](https://github.com/Deijin27/conquest-hexpat), MIT,
  independently documents the full two-bank section sizes and native headers.
- [RanseiLink game-code enum](https://github.com/Deijin27/RanseiLink/blob/master/RanseiLink.Core/Enums/ConquestGameCode.cs),
  GPL-3.0, independently identifies VPYT as North America. Its
  [species-ID enum at commit 1bc9e5a](https://github.com/Deijin27/RanseiLink/blob/1bc9e5a5c496a8359b68085112c42ae7df8b04c4/RanseiLink.Core/Enums/PokemonId.cs)
  corroborates the public factual zero-based identities. The project is GPL-3.0,
  including its earliest published licence; it is not MIT. No upstream enum,
  algorithms or implementation/catalog files are incorporated.
- [The public Ransei Gallery order](https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_by_Ransei_Gallery_order)
  independently supplies all 200 species names in the game's ordering. This
  adapter contains an independently written map of bare species-ID/name facts
  for every native ID 0–199. Article prose, tables, sprites and other game assets
  are not copied. Gallery display positions can omit unavailable Reshiram; native
  species IDs retain their fixed identities and are not shifted by that omission.
- [Serebii's Conquest mechanics](https://www.serebii.net/conquest/battle.shtml)
  distinguishes tactical combat, warriors, items and Pokémon from ordinary-series
  games. [The Pokémon list](https://www.serebii.net/conquest/pokemon.shtml) confirms
  Forretress uses Gyro Ball. These are references, not redistributed text/assets.
  [Bulbapedia's Conquest-specific Gyro Ball effect](https://bulbapedia.bulbagarden.net/wiki/Gyro_Ball_(move)#Pok%C3%A9mon_Conquest)
  separately confirms damage increases when the user is slower than the target.
  [Its Conquest IV description](https://bulbapedia.bulbagarden.net/wiki/Individual_values#Pok%C3%A9mon_Conquest)
  independently gives the natural 0–31 range and distinguishes default Pokémon's
  uniform 15 IVs from later linked wild Pokémon; 31 is not merely a storage ceiling.

Three distinct genuine native copies were checked privately: an independently
shared Twitch Plays Pokémon Conquest copy and two GameFAQs submissions from a
public archive. One GameFAQs submission is an ARDS container whose raw save was
extracted privately; only that raw payload is used for qualification. The copies
have differing gallery counts and both observed raw lengths. All 26 checksums
match for every copy, and no-edit roundtrips are byte exact. Every admitted IV
component is tested against independently applied masks and byte-sum repair.
The test suite keeps these genuine inputs optional and private. Procedural
fixtures test corruption, bounds, unknown records, packed overlap, backups,
source safety, Undo/review and actual Tk Save As. No edited game-load/re-save
validation was performed and no saves are published.

## Mechanic coverage checklist

| Mechanic | Coverage or specific blocker |
| --- | --- |
| Gallery Pokémon IVs | Existing vanilla species records: three numbered components and Speed IV, 0–31; bit-safe writes and per-bank integrity. |
| Gallery duplicate banks | Independent counted records and generation display; no assumed slot pairing or counter changes. |
| Forretress Speed / Gyro Ball | Manual IV editing; excluded from Max to retain slow builds. |
| Species, abilities and moves | Preserved; species replacement/ability validity and move derivation require separate mappings and dependency proof. |
| Current scenario Pokémon / EXP / Link | Preserved; gallery mappings are not promoted to current-party or maximum-link editing. |
| Warrior identity / recruitment / capacity | Preserved; ownership and Pokémon-reference dependencies need controlled native pairs. |
| Gold, items and kingdom resources | No source-backed disk writer/validity proof established in this research round. |
| Energy, warrior skills and evolutions | Need title-native storage mapping, valid states and dependency/reward proof. |
| Episodes, story and kingdom capture | Preserved separately from IV edits; flags, rewards and prerequisites require controlled native action pairs. |
| Password/downloaded-event history | Preserved; availability, one-time-use and episode dependencies unqualified. |

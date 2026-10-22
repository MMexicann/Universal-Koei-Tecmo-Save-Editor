# Original Warriors Orochi on Windows PC

This investigation targets the original 2008 Windows release. Orochi Z, Warriors
Orochi 2/3/4, PSP, PS2, Xbox 360 and other console containers are separate formats.
No related-game or runtime-trainer address establishes a disk field in this title.

## Evidence and provenance

The original [Windows manual](https://oldgamesdownload.com/manual/warriors-orochi-windows-manual-english/)
identifies `My Documents/KOEI/WARRIORS OROCHI/Savedata` as the save location. Its
printed pages 3 and 18–23 distinguish persistent growth, equipment and battle
data. End-of-stage and Camp saves persist character growth in both Story and Free
Mode. Interim saving is a separate battle-state operation; clearing or losing a
battle deletes the interim state. A reviewed ordinary gameplay copy is required;
the editor does not create or modify interim battle data.

Two independently shared archives were inspected privately:

- [2008 original PC save](https://www.playground.ru/warriors_orochi/cheat/warriors_orochi_sohranenie_100-757738).
  The description reports unlocked content. A contemporaneous comment describes
  unusually high weapon effect ranks; this is useful preservation evidence, not
  a natural-cap reference.
- [2018 original PC save](https://www.playground.ru/warriors_orochi/cheat/warriors_orochi_sohranenie_savegame_igra_projdena_na_100-831460).
  The archive contains the original `Warriors OROCHI/Savedata/save.dat` directory
  plus separate controller mappings. Its description reports level 99 officers
  and fourth weapons with eight level-ten effects.

Both ordinary gameplay files contain exactly `0x24180` bytes, little-endian
revision 2 at offset 4 and an observed first-section DWORD 3000 at offset 8.
The DWORD at `0x24160` equals the sum of preceding bytes in both copies. The
source reader does **not** check the value at offset 8, so the adapter does not
invent a signature check there. A checksum and filename alone do not prove all
gameplay fields; the title-specific disk reader, record resolver and field
getter/setter evidence below establish the implemented format.

[Van's original OrochiEditor Build 513 announcement](https://game.ali213.net/thread-1992333-1-1.html)
and its readme explicitly support the original English/Japanese/Traditional
Chinese Windows 1.0 releases and distinguish direct save editing from process
attachment and LINKDATA asset editing. The posted Resource archive contains
localization resources, not permission to copy executable source. The author's
redistribution restriction is respected: no editor binary, external source copy,
localization catalog, player save, controller mapping or game asset is shipped.
Downloaded editors are never executed. The archive was extracted with a
source-built decompressor. PECompact's aPLib and LZMA data were decoded as data
for static inspection; its loader was not emulated or executed. Only independently
written factual format/field implementations enter the application.

## Qualified original PC reader, layout and integrity

The original Windows editor's explicit disk-save path accepts the complete
plaintext buffer directly, checks the exact size and u16 revision, verifies its
additive checksum, then resolves records inside that same buffer. Its disk writer
updates only the additive DWORD and writes the same exact-size buffer. This
is original title-specific disk evidence, not a runtime trainer address or an
Orochi Z layout transplanted into the earlier game. Both independent public saves
corroborate the complete length, revision, checksum, record strides and field
interpretation. The original game's executable was not available; the distinction
between period-editor format evidence and native-game load validation remains
explicit.

| Period editor static location | Factual behavior |
| --- | --- |
| `0x407620`, `0x40769F`, `0x4076FA` | Disk reader: exact `0x24180` bytes, revision u16 at offset 4 equal to 2 |
| `0x407710`–`0x407752` | Sum all bytes before `0x24160`; compare the stored little-endian u32 |
| `0x407780`, `0x407810`–`0x407858` | Recompute that DWORD and write the same complete plaintext buffer |
| Count table `0x4B2034`, resolver `0x404330` | 79 officer records, 632 physical weapon slots; officer base `0xC`, stride `0xC8`, eight weapons per record |
| `0x40450F`, `0x4045D7`, UI `0x4174C9` | Read/write stock Growth Points at `0x40C8`, u32; the period UI uses an edit bound 99,999, not proof of a native game clamp |
| `0x4045F0`, `0x404730` | Weapon properties in records at officer `+0x14`, stride `0x16`: ID u16 `+0`, ownership mask u16 `+2`, capacity u8 `+4`, attack bonus u8 `+5`, fifteen rank bytes at `+6` |
| `0x404633`–`0x404643` | Four weapon tiers selected by descriptor ID modulo four; own-family IDs corroborated by all 79 fourth-weapon IDs `4*record + 3` in the second independent copy |
| `0x4177E0` | Deliberately skip native attribute enum 5; its mask and stored rank remain read only |
| Label/getter tables `0x4B25C8`, `0x404830` | The 79-record officer resolver supplies a stable record index; the disk getter reads level byte `+0` (displayed plus one), equipped weapon byte `+1`, costume byte `+2`, five named stat words as u16 at `+4/+6/+8/+A/+C`, proficiency u16 `+E` and EXP u32 `+0x10` |

The first DWORD, upper revision word at `+6`, DWORD at `+8` and the final 28 bytes
after the checksum have no check in the inspected reader. They are retained
exactly, including nonzero values; no zero-padding requirement is invented.
No checksum is disabled, normalized or silently repaired on input. No-edit
serialization is byte-exact. Qualified edits change only selected mapped bytes
and the required four checksum bytes, then reparse the output.

The title-specific exact-size/revision/checksum profile rejects different native
sizes and revisions. Procedural foreign-input tests use the separate SW2 and
Orochi Z generators and a console-container prefix; they are not genuine-file
qualification for those other titles. Additive integrity is not cryptographic
authenticity: an intentionally constructed matching-size,
revision and checksum file cannot universally be distinguished from genuine
game data. Unknown records stay opaque rather than being repaired into defaults.

## Implemented controls

`games/wo1_pc/wo1_codec.py`, `wo1_parser.py` and `wo1_editor.py` provide the
registered `wo1` Windows adapter. The existing GUI supplies search, grouped
controls, read-only growth/weapon inspectors, Review Changes, staged Undo,
automatic backups, validated restore and atomic Save As to a new copied `.dat`.

| Writable control | Domain and safety boundary |
| --- | --- |
| Shared Growth Points | `0x40C8`, u32; individual edits use the explicit storage range `0..4,294,967,295`. This is not a natural gameplay cap. All bulk Max actions exclude this balance. Officer EXP, growth, playtime, abilities and rewards are unchanged. |
| Existing weapon attack bonus | Existing own-family weapon byte `+5`; individual edits use explicit byte storage range `0..255`. Bulk Max excludes it. Normal fusion guides describe +20, but a PC game clamp has not been proved; unusual/higher opened values are retained. |
| Existing weapon capacity | Byte `+4`, between the opened ownership-mask bit count and eight; individual only, no bulk Max. Decreasing cannot hide an owned effect, increasing cannot acquire or activate an absent effect. |
| Already owned named effect ranks | Byte `+6+enum`, stored as displayed rank minus one; fourteen named effects use `1..10` with the original PC manual's natural maximum. Native enum 5, absent effects and mask identities remain untouched. Higher opened ranks survive Max; assigning the opened value unstages a prior edit. |
| Existing equipped weapon | Officer byte `+1`, displayed as slot 1..8; only qualified original own-family weapon choices with a supported original selector and at least two choices; no Max, ownership or pool changes |

### Stored officer stats: read-only research candidate

The original PC period getter at `0x404830` and label table at `0x4B25C8` name
Life, Musou, Attack, Defense and Speed as u16 words at officer-relative offsets
`+4`, `+6`, `+8`, `+10` and `+12`. The disk reader resolves 79 officer records
from base `0xC` at stride `0xC8`; independent native saves qualify the current
file profile and preserve these bytes. This is a credible mapping candidate,
but no controlled native character-growth or level-transition pair has verified
how the displayed stat changes map to those words or revealed coupled changes.
Character Growth allocates Growth Points to a character to raise its level; it
does not expose separate Growth Point purchases for individual stats.
These values therefore remain read only. An experimental numeric option cannot
replace the missing field-to-action evidence.

The [existing-editor depth review](OROCHI_DYNASTY_DEPTH.md) records the selector
proof, 63 qualifying genuine early-save choices, exact checksum/byte tests and
native Tk selector/Review/Undo/backup/Save As/restore validation.

Writable weapon properties require an original descriptor in this record's four
IDs `4*record..4*record+3`, no unknown mask bit 15, and a capacity that holds all
owned mask bits and is at most eight. Cross-family IDs, NPC/unknown IDs, observed
empty ID 345, inconsistent masks and unusual capacity layouts are preserved
entirely and receive no controls. Pending edits cannot manufacture eligibility.
The early public save has one weapon with ten slots and ten rank-99 effects; the
whole unusual record is therefore preserved read only, including all ten ranks.

Independent original PC column/getter associations establish enum names:
`0 Flame, 1 Ice, 2 Bolt, 3 Flash, 4 Slay, 6 Drain, 7 Absorb, 8 Air, 9 Brave,
10 Range, 11 Multi, 12 Agility, 13 Might, 14 Rage`.
The manual's display order is not treated as a native index order. The byte writer
edits a qualified rank without using the period tool's acquisition behavior that
sets an absent ownership bit. No weapon, effect, reward or story state is created,
consumed or granted implicitly.

## Mechanics and dependency boundaries

The original manual establishes the following systems without importing later
Orochi mechanics:

| System | Original-game behavior and editing boundary |
| --- | --- |
| Growth Points / stock EXP | Shared persistent balance earned after successful battles; spent on character growth and weapon fusion. Distinct from per-officer EXP, current battle EXP and playtime. No separate gem or gold balance is inferred. |
| Character growth | EXP fills a gauge; leveling raises five base abilities. Displayed level has a maximum of 99. Stored EXP, level, base stats, equipped-weapon effects and team ability effects must remain distinct; isolated level transitions require native progression/reward qualification. |
| Attack-category proficiency | Earned only by the active character from defeated enemies; one officer counts as 100 soldiers. Strengthens special attacks. A natural limit or reward-bit relationship is not inferred from a maximal save. |
| Abilities | Eighteen named ability types; up to seven equipped abilities apply to the whole team. Officers acquire three or four abilities through battle conditions. Acquisition flags, recomputed global ranks and equipped references are separate. The period editor's FAQ warns that global ranks are recomputed after battles from officer acquisition flags; editing only global ranks is not a coherent acquisition transaction. |
| Existing weapons | Weapons are awarded to all three team members after victory when treasure boxes were obtained. Equipment chooses an existing weapon. Ownership, descriptor/type, equipped reference, bonus attack and attribute state must remain separate. |
| Weapon fusion | Consumes Growth Points and the material weapon. Adds only effects available on that weapon, within the base weapon's available slots. An existing effect's natural rank limit is ten. Editing an existing effect value is not a fusion/ownership transaction and must never consume or manufacture records implicitly. |
| Equipment and unique items | Character-unique items require specific acquisition conditions. Equipped weapon/ability references cannot manufacture ownership or grant unique-item rewards. |
| Mounts | Cavalier gives mounted attack/defense bonuses and starts a battle mounted. The original [character/skill guide](https://www.tapatalk.com/groups/koeiwarriors/warriors-orochi-unlock-characters-skills-guide-t18274.html) links the special horse to Cavalier and the lead character; no independent persistent horse inventory is invented. |
| Bodyguards | No persistent recruitable bodyguard system is established by the original Windows manual. No bodyguard editor or related-game bodyguard offsets are inferred. |
| Story and records | Four faction campaigns, character unlocks, stage results, unique-item acquisition and gallery rewards remain distinct from resource/stat edits. A period editor's ability to set a clear bit does not qualify prerequisites or coupled rewards. |

The fourteen weapon effect labels in the manual are Flame, Ice, Bolt, Flash,
Slay, Drain, Absorb, Air, Brave, Range, Multi, Agility, Might and Rage. This display
order is not assumed to be the native enum order. Unknown identities and unusual
stored values must remain untouched, including the early save's modified ranks.
The contemporary [original-game fusion guide](https://gamefaqs.gamespot.com/ps2/938105-warriors-orochi/faqs/50450)
describes eight held weapons, eight attribute slots and normal attack bonus +20.
It is a mechanics corroboration, not a PC disk-offset or revision reference.

## Coverage and exact remaining inputs

| System | Implemented state or specific blocker |
| --- | --- |
| Native disk framing, revision and integrity | Period original-PC reader/writer facts implemented; two independent native copies qualify unchanged and surgical roundtrips. Native game-loader execution is separate and unperformed. |
| Persistent currencies | Shared Growth Points writable; no separate currency is invented. A native original PC growth-point clamp or documented controlled ceiling is needed before resource Max. |
| Character stats, level and EXP | Five getter-mapped u16 stat words are read-only candidates; stored level and EXP remain inspection only. Provide a revision-2 native baseline with exact region/build provenance and an unchanged control. Capture an isolated Growth Points allocation to one selected character and, independently from the same baseline, a level-gain transition; the native UI does not allocate points to individual stats. Record the exact allocation, all five displayed stats, Growth Points, displayed level, EXP, proficiency and selected officer on each side. Compare all five stored stat-word deltas, the stored level byte (displayed plus one), EXP and any coupled fields, and verify the native checksum. These captures must establish growth dependencies and bounds without assuming independently writable stats. A manually edited duplicate must then load and re-save in the original game before writable stat support. |
| Proficiency | Stored u16 inspected; controlled active-character enemy-count and proficiency/reward pairs are needed for persistent units, natural ceiling and reward dependencies. |
| Abilities/skills | Acquisition flags, global recomputed rank, prerequisites and seven equipped references remain preserved. Native acquire/equip pairs and exact flag-to-ability correspondence are needed before coherent edits. |
| Existing weapons and attributes | Qualified bonus/capacity/owned rank values writable. The four-tier identity stays unchanged, and records with unqualified layouts remain read only. |
| Weapon acquisition and fusion transactions | Preserved. Native before/after acquisition and fusion pairs must identify source-consumption, ownership, collection/equipped references, costs and rewards before creating or consuming weapons/effects. |
| Equipped weapon choice | Existing original own-family qualified weapon pool selectable; unsupported original selectors and unqualified targets remain opaque. No new weapon acquired. |
| Costume/ability choice | Existing selector bytes preserved. Matching acquisition/prerequisite and display/selection proof is still needed. |
| Unique items and mounts | Ownership/reward flags and Cavalier/lead-character mount dependencies remain protected. Controlled acquire/equip pairs are needed; no invented horse inventory. |
| Bodyguards | No persistent original PC bodyguard subsystem established; no unrelated-game offsets used. |
| Story, stage results and gallery rewards | Preserved and separate from resources. Controlled original-PC stage-clear/unlock pairs are needed to associate stages, clear state, result counters, character/unique-item unlocks and coupled gallery rewards. |
| Revision/region variations | The period source names English/Japanese/Traditional Chinese 1.0; the implemented profile is exact revision 2 and size `0x24180`. Other revisions/lengths reject. Independent copies with documented region/build context would strengthen per-region qualification. |
| Edited game loading | Requires an installed original Windows game and a player-run load/re-save of a surgical edited copy, with exact region/build and displayed values. No such validation has been performed. |

## Validation results

`tests/test_wo1_pc_format.py` covers procedural original-profile qualification,
corrupt size/revision/checksum, foreign SW2/Z/container rejection, mutable/equal
format forgeries, own-family weapon eligibility, capacity dependencies, unused
enum preservation, rank encoding, higher-value unstage and Max, surgical writes,
malformed pending batches, backup/restore integrity and changed-source safety.
Its procedural bytes are generated test data, not a playable save or genuine
qualification evidence. The shared registered scalar contract exercises staging,
review, no-op/surgical serialization, path protections, backups and restoration.

`WO1_NATIVE_SAVES` selects a local folder of reviewed flat `.dat` copies. With the
two independently acquired original PC files, genuine tests qualified byte-exact
unchanged roundtrips and **3,259 individual surgical edits**: 2,468 qualified
fields in the early copy and 791 in the complete copy. Their 415 and 79 qualified
weapons respectively remain existing own-family records; unqualified records
and unknown bytes survive. All each-field outputs reparse, original source bytes
remain unchanged, and Max preserves higher/unqualified data. No saves, edited
outputs or player/controller data are published.

`tests/test_wo1_pc_gui.py` exercised real Tk under Xvfb using both procedural
bytes and a private genuine copy: search, Apply, Review Changes, Undo, filtered
Max, inspectors, themes, automatic backup and new-destination Save As. The
focused format/registered-contract/GUI run passed **12 tests, zero skips** in
25.128 seconds. The final combined run, including **13 independent mixed-game
adversarial/retained-session review tests**, passed **25 tests, zero skips** in
25.081 seconds after the pending-batch validation fix. These are application and
genuine-file tests, **not** edited-game loading or Windows executable validation.

# Fire Emblem Warriors — Nintendo Switch native exports

The adapter independently implements an extensionless `scenario0`, `scenario1`
or `scenario2` export. It accepts the observed 1.5.0 layout: exactly `0x172AC`
(94,892) bytes, little-endian first word `0x13`, and a second word equal to the
file length. This is an observed layout discriminator, not proof that `0x13`
is a game version. Nintendo 3DS saves, other layouts, encrypted console archives
and `system` are not supported. Keep `system` and the complete original export
folder unchanged; import a separately edited scenario copy through the user's
existing save-management workflow. No console account, encryption or signing
bypass is provided.

## Nintendo 3DS edition — separate, unqualified profile

The New Nintendo 3DS release is a separate platform target. Its 2017
[save-editing discussion](https://gbatemp.net/threads/fire-emblem-warriors-save-editing-discussion.489382/)
describes `scenario0`–`scenario2` and `system` and records an early little-endian
investigation. The opening post labels the weapon and character area as guesswork:
it proposes 300 records of `0x40` bytes at `0x1262E`, while calling the weapon
and attribute IDs probable and the character block unidentified. Those leads do
not qualify a 3DS writer or prove that the proposed records are correct.

The later [Switch save-editing thread](https://gbatemp.net/threads/fire-emblem-warriors-save-editing.505591/)
explicitly excludes 3DS. Its source-backed `1.5.0` Switch layout is a separate
profile; matching filenames, fields or early resource offsets do not establish
that the Switch parser accepts 3DS exports. Nintendo's [3DS update history](https://en-americas-support.nintendo.com/app/answers/detail/a_id/27735/~/how-to-update-fire-emblem-warriors-%28new-nintendo-3ds%29)
records a 1.5.0 update that raised the character level cap to 150 and added the
Legendary attribute, among other changes. Therefore early 3DS notes cannot be
treated as a complete current-version mechanics or record map.

| Edition | Current evidence | Support status and next qualification |
| --- | --- | --- |
| Switch, observed 1.5.0 export | This document's fixed-size layout, public editor sources and one modified USA/EUR player export | Implemented for the exact observed layout. Japanese-region equivalence and console load/re-save remain unverified. |
| New Nintendo 3DS | Exploratory 2017 field notes and a separate official update history | No adapter. Need a complete untouched extracted scenario export with title region and installed version recorded; matched before/after copies for one labelled resource, weapon and character-progression action; and a no-op/surgical roundtrip that confirms the full-file boundary and any integrity rules. Keep `system` alongside the capture as an unchanged companion. Qualify each region/version separately. |

Until those 3DS inputs exist, do not register the Switch parser for 3DS, expose
the preliminary weapon table, or write the 3DS resource leads. The raw game data
may still require the platform's own container/export step; that boundary must
be documented separately from any game-level scenario parser.

## Evidence and provenance

The primary [Switch save-editing discussion](https://gbatemp.net/threads/fire-emblem-warriors-save-editing.505591/)
starts with CrisFTW's May 2018 research, specifically USA/EUR Nintendo Switch;
Japanese support was untested. Its EdiZon configuration maps raw scalar reads and
writes with no checksum repair. We inspected the public EdiZon configuration
`0100F15003E64000.json` and `Scripts/bin.lua` at commit
`d16d36c7509c01dca770f402babd83ff2e9ae6e7`, attributed to CrisFTW/Brawl345.
No distribution licence was located for that repository.

The thread's public Scarlet C++ source attachment (`Fire Emblem Warriors Sauce`)
uses direct little-endian writes and independently confirms three material
regions, including Rowan's separate `0xFC38`/`0xFC3A` pair. Its bundled source
archive SHA-256 is `a932940525e1fc4800161c6b8b3704f6f33f7bf642e816f919bb2ae3654e5e5b`.
Several historical blanket actions in this editor are unsuitable: contemporary
reports describe character loss, and the author originally could not test it.
We do not reproduce those actions.

The public [neomy2 weapon editor](https://gbatemp.net/download/fire-emblem-warriors-weapon-editor.35529/)
v0.5.1 (2019-01-25) was inspected statically with a separate Java decompiler.
The researched editor was never executed. Archive SHA-256 is
`1bd59b99d9e68f65e6e131241ac51d71a3eecf959680bfc7192ab66d85669b7d`.
Its getter, field renderer and direct byte setter settle the weapon structure
more precisely than the original prose. No licence was located for these
attachments. Our Python parser/UI and safety logic are independently written;
only factual names, identities, locations and limits are transcribed. No upstream
program code, game images or binary assets are shipped.

A public [CrisFTW player export](https://gbatemp.net/download/fire-emblem-warriors.35112/)
(version 1.5.0, August 2018) contains a 94,892-byte scenario plus the separate
496-byte system file. **Its author explicitly modified money, materials, levels,
weapons and story** and reports DLC requirements. It is genuinely exported player
data, but not an unmodified baseline and not evidence that its unusually large
special-item quantities are legitimate. The archive remains private and is never
redistributed. Resource descriptions, file structure and native parsed fields
agree with the published mappings. We do not claim its modified state was newly
loaded on a console by this project.

Independent gameplay references supplement the editor mappings:
[Materials](https://fireemblemwiki.org/wiki/Materials) describes ordinary drops
from enemies and support rewards separately from personal-weapon enhancement
items; [weapons](https://fireemblemwiki.org/wiki/List_of_weapons_in_Fire_Emblem_Warriors)
explicitly lists generic weapons with star rank 0–5 and unique weapons such as
Falchion/Yato/Raijinto with fixed star rank 0 and progression-dependent might.
The [weapon-attribute guide](https://fireemblemwiki.org/wiki/Weapon_attribute)
separately corroborates seal KO requirements, forging costs and the dependency
that transferable Bonus/Swap/Break/Slay/Gen attributes require a matching innate
non-personal weapon. This is why arbitrary attribute creation is withheld.
These references corroborate the generic/unique distinction. They do not
corroborate natural money/material caps, so those resources have manual controls
with conservative published-editor ceilings and no Max action.

## Format and integrity

Published Switch readers/editors modify the scenario directly without encrypting,
compressing or repairing a checksum. The independently shared export is consistent
with that raw layout. Bytes `0x08..0x27` are opaque header data and are preserved;
their meaning is not recovered. No mapped checksum layer is implemented, and
edited console load/re-save validation remains unperformed. The strict size,
marker and embedded-length checks reject mismatching revisions, not every possible
corruption of an otherwise matching opaque region.

Gold is a little-endian u32 at `0x32C`, source edit ceiling 9,999,999; natural gameplay cap is uncorroborated, so gold is excluded from Max. The catalogue names
203 u16 item counters in the documented regions. Of these, 106 are repeatable
ordinary character/enemy drops and 97 are scrolls, opuses, essences or Master
Seals. Only already-positive ordinary quantities are editable, source edit ceiling 999. The natural gameplay cap is uncorroborated, so material quantities are excluded from Max.
No discovery/unlock bitset is qualified, so an exhausted zero count is read-only;
no missing ownership is fabricated. Existing quantities above 999 survive Max
and can be unstaged back to their original value.
Direct serialization also treats exact typed opened values as no-ops, including
unusual material or weapon-star values. If an unusual higher star value has a
pending reduction, Max restores the opened value and removes that reduction;
it preserves the original higher value rather than retaining the smaller edit.

The weapon editor's bounded getter reads **600 physical 32-byte records**, starting
at `0x127AC` for `0x4B00` bytes, ending exactly at file length. This corrects the
original discussion's one-byte-earlier prose; do not assume 300 64-byte records
or transplant the separately documented 3DS offsets.

| Relative offset | Width | Meaning and write policy |
| --- | --- | --- |
| `0x00..0x0F` | 8 × u16 LE | Remaining KOs corresponding to the 8 attribute slots |
| `0x10..0x17` | 8 × u8 | Attribute IDs; read-only named inspection |
| `0x18..0x19` | u16 LE | Weapon ID; source renderer labels low byte, unknown high-byte IDs excluded |
| `0x1A` | u8 | Stars; 0–5 only for 36 recognized generic E–S weapon identities |
| `0x1B` | u8 | Opaque/tier-associated byte; preserved |
| `0x1C` | u8 | Slayer bitmask; named context but no editing |
| `0x1D..0x1F` | 3 bytes | Opaque/references; preserved |

`0xFFFF` weapon IDs denote empty entries. Unknown identities remain inspect-only.
Unique/amiibo weapons use badge/scroll/opus power tiers and are excluded from star
writes even though the historical editor permits arbitrary bytes. Only naturally KO-sealed ordinary attributes on an existing recognized weapon
can decrease a positive remaining counter to zero; zero removes that ordinary KO
requirement. The independently documented initial limits are Healing Gift /
Warrior Gift / Awaken Gift (IDs 23–25): 2,000; Triangle+ / Pair Up+ / Critical+ /
Warrior+ / Health+ / Desperate+ (26–31): 5,000; Armor Strike (37): 3,000;
Fury Builder (38): 2,500; Critical Focus / Antiair Focus (47/48): 4,000.
Opened values above the matching limit are excluded, as are positive unusual
counters on attributes that normally have no KO seal. Raising counters,
inventing attributes, changing slot capacity or completing special seals is not
allowed. True Power (ID 34) and Legendary (55) require progression prerequisites
and are always excluded. All KO actions are excluded from Max. No weapon ID,
attribute ID, slayer flag, equipped reference or ownership byte changes.

## Mechanic coverage checklist

| System | Implemented feature or exact blocker |
| --- | --- |
| Gold | Current gold scalar; bounded published-editor ceiling; natural cap uncorroborated, excluded from Max |
| Repeatable character/enemy drops | Searchable named 106-slot catalogue; existing-positive quantities; published-editor ceiling 999, excluded from Max pending natural-cap proof |
| Scrolls / opuses | Read-only named quantities; unique-weapon badge tier/reward flags and consumed-state prerequisites unqualified |
| Essences / skills / crests | Read-only quantities; character skill/crest ownership, costs and learned-state flag mapping unqualified |
| Master Seals / promotion | Read-only quantity; promotion/class/base-stat and costume dependencies not safely mapped |
| Generic weapon quality | Existing generic E–S stars 0–5; targeted and group Max tests |
| Unique / amiibo weapon power | Identity inspection; scroll/opus badge tier, attack calculation and legitimate star behavior unqualified |
| Ordinary sealed attributes | Named existing attribute inspection and decrease-only remaining KOs; no attribute creation |
| True Power / Legendary | Named inspection; unique-weapon badges, prerequisites and reward flags missing |
| Forging / fusion / appraisal / slayers | Existing identities and flags preserved; native power calculation, slot capacity, appraisal state and cost dependencies unqualified |
| Equipment / ownership / sorting | Named physical slots; equipped and record-reference identities not safely mapped |
| Character levels / EXP / derived stats | Named 32-character inspection at EXP `0xFF0C + 0xD4*i`, stored level +4 (display +1); only a handful of published EXP thresholds and no complete curve, growth-stat recalculation or unlock qualification |
| Bonds / support conversations | Original blanket edit assumes all DLC characters unlocked, warns about array length and event triggers; exact revision-dependent matrix and A/A+ reward flags missing |
| Character / DLC unlocks | Not implemented; no proven per-character ownership and DLC prerequisite flags |
| Story / History maps / difficulty / rewards | Kept separate; original cheats overwrite broad flag regions with character-loss reports; no independent per-map/reward/dependency schema |
| Costumes / classes / music / gallery / medals | Research categories; source costume field can alter deployed character identity, and reward/collection schemas are not qualified |
| System/playtime | Separate `system` untouched; not needed for supported scenario edits |

## Validation

`tests.test_fire_emblem_warriors` has nine checks for format bounds, immutable
snapshots, byte-exact unchanged serialization, one-field byte ranges, dynamic
ownership exclusions, special-item/True Power/Legendary preservation, unknown
records, unusual originals, invalid pending edits before Max, backup/restore,
source-change detection and optional public-export qualification.
`tests.test_fire_emblem_warriors_gui` adds four real Tk workflows: procedural
search/Apply/Review/Undo/inspection/theme/new-copy Save/backup/restore, the same
workflow on a temporary public-player-export copy, and ordinary-seal/extensionless
Save As behavior, and Max restoring an unusual higher opened star value after a
pending reduction. With the private optional fixture supplied, those **13/13 tests pass**.
The independent `tests.test_fe_review` adds eight adversarial checks for exact
immutable type, invalid pending Max edits, higher/unknown/unique records, special
seals, opaque headers, source transplantation, extension/collision guards,
foreign-byte restore and every exposed positive public-export field. Combined
with a real Tk display and the private fixture, **21/21 tests pass without skips**.
Without it, three genuine-export tests skip explicitly.

The public player export exposes 139 editable fields (106 ordinary drops, 32
generic-weapon star fields and gold) and 49 occupied weapon records. Every exposed
field was independently targeted, serialized/reparsed and checked to alter only
its declared byte range. It contains no qualifying positive ordinary seal counters;
seal mutation tests therefore use procedural fixtures. Original player files and
all opaque/unknown bytes remain untouched. No edited game-load/re-save, Japanese
region, other game version or 3DS validation is claimed.

Optional developer variable: `FE_WARRIORS_SAVE_COPY` points to a private matching
scenario export. Never add that export, system file, private account identifiers,
archive paths or personal paths to repository/release assets.

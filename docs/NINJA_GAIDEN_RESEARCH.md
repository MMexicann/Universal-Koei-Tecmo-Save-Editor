# Ninja Gaiden: separate editions and native save profiles

The implemented original **Ninja Gaiden II Xbox 360/Xenia editor** accepts only
the independently qualified revision-6 **extracted story `.dat`** profile.
Ninja Gaiden Sigma, Sigma 2, Ninja Gaiden 2 Black and their individual platforms
are separate formats. No game executable or third-party editor binary was run.
Player files, downloaded reference sources, owner context and private analysis
remain outside the checkout and public source package.

## Original Ninja Gaiden II: Xbox 360/Xenia extracted stories

The [codec](../src/koei_editor/games/ninja_gaiden_ii/codec.py),
[parser](../src/koei_editor/games/ninja_gaiden_ii/parser.py) and
[editor](../src/koei_editor/games/ninja_gaiden_ii/editor.py) are independently
implemented. Published source facts were compared against **22 genuine extracted
story files** and the story entry in **one genuine Xbox 360 CON package** from a
freely shared [GTrainers Xenia save](https://gtrainers.com/load/categories/savegames/ninja_gaiden_2_black_savegame_for_xenia_emulator_ninja_master_completed/30-1-0-13649).
Although the page's title says “Black”, its description explicitly says the
original second game and specifies original Xbox 360 title `544307D5`. The
package's native title metadata independently confirms that game identity.
This archive does **not** qualify the 2025 Black remake.

The native profile is exactly **31,744 bytes**. Its first 32 bytes contain the
big-endian gameplay length `0x7880`, revision `6`, two native `0x01234567`
markers and the qualified revision's other fixed header words. The first
four-byte inventory record must be one of the separately documented Dragon
Sword records: ID `1`, quantity `1`, level variant `0..2`, or ID `7`, quantity
`1`, variant `0`. A generic checksum-shaped byte array does not qualify.
Future, unusual-header or other edition profiles are rejected pending separate
native evidence; none are normalized into this profile.

The native checksum is the modulo-2^32 sum of **big-endian 32-bit words over
`[0, 30,848)`**, stored big-endian at **30,848**. All 23 native gameplay blocks
match it. The [GPL-3 utility's documentation and separately inspected source](https://github.com/ike9000e/ngii-save-update-util/tree/ff3fb1506ce0f5b94a66f61b3e8e038900bc2010)
independently document this checksum and the 128 four-byte item records at byte
48. Its source and implementation were not incorporated. The
[separate browser editor](https://github.com/rnrmfdlapdlf/ninja-gaiden2-save-editor/tree/0f8fab00a63eb7faf18214b2be8db8410584a3ab)
provides additional essence/Karma/item-label facts; no explicit licence was
found, and none of its implementation is copied.

The browser editor's apparent `ng2stryd` “raw magic” is the **STFS directory
entry filename** in the inspected genuine CON file, preceding the native
gameplay entry. It must not be treated as a native title header or used to
invent a 35,840-byte gameplay profile. The editor excludes CON/STFS packages:
their allocation tables, hashes and signing are separate integrity layers.
It also excludes the 2,048-byte system data, companion metadata and thumbnails.
The native extracted stories carry no container ownership context to rewrite.

### Implemented controls and preservation

- **Yellow Essence balance**, native big-endian `u32` at byte 40: manual edits.
  `0..4,294,967,295` is the storage/input range, not a recovered natural cap.
  All Max operations leave it unchanged. Higher or unusual opened balances
  survive unchanged serialization and can be restored by assigning the opened
  value or Undo.
- **Existing unique ordinary consumable/ammunition stacks**: reduce quantity to
  `1..the opened quantity`. Records contain a big-endian `u16` identity, one
  quantity byte and one variant byte. Only independently named IDs with a
  nonzero existing quantity greater than one, a zero ordinary variant and a
  unique identity are eligible. Item IDs, variants and slot positions are never
  rewritten. Duplicate IDs, unknown records, weapon variants and one/zero
  quantities remain read-only. There is no creation, deletion or increase.
- **Searchable inspection** retains physical slot, numeric identity, name where
  qualified, quantity, variant and eligibility for every nonzero inventory
  record. Karma is displayed separately as a historical score at byte 560.
  It is not spendable essence, EXP or story completion.

Eligible names currently cover Herb/Grains of Spiritual Life, Talisman of
Rebirth, Life of the Gods/Thousand Gods, Jewel of the Demon Seal, Spirit of the
Devils, Devil Way Mushroom, Muramasa's Omusabi, Incendiary Shuriken and Fiends
Bane Bow arrows. Labels are supported by public source; a quantity byte's 255
storage ceiling is never presented as a natural carry capacity.

Unknown bytes, native nonce words, header markers, unknown identities, the
fourth record byte, score, equipped records and the complete 892-byte trailer
after the checksum are preserved. A no-op returns the original bytes exactly.
An edit changes only declared scalar bytes and the required checksum, then
reparses the output. Shared Save As uses immutable staged changes, Review Changes,
Undo, automatic backups, exact-byte restore validation, source-change checks and
new destinations; themes and copied-source protection remain intact.

### Validation and exact remaining mechanics

[Format and scalar contract tests](../tests/test_ninja_gaiden_ii.py) cover
unchanged roundtrips, independent checksum arithmetic, native identity/revision,
corruption/foreign formats, existing-record dependencies, unusual quantities,
surgical byte preservation, malformed pending maps, frozen-snapshot forgery,
bulk-Max exclusions, backups/restore and changed-source protection. Procedural
fixtures are generated and do not constitute player saves. Set `NGII_NATIVE_DIR`
to a separately held reviewed corpus to run genuine-file tests; those tests
exercise every eligible existing stack and an essence edit across 22 genuine
stories. Actual edited game-load/re-save validation has **not** been performed.

| Mechanic | Current coverage / exact additional proof |
| --- | --- |
| Available Yellow Essence | Implemented manual native balance. Natural grant/spend clamps and maximum balance need native consumers or controlled displayed boundary pairs. |
| Carried consumables and ammunition | Implemented existing unique ordinary stack reductions. Increases require item-specific capacities and use/purchase/reward pairs; creation/removal requires slot/ownership/equipment dependency proof. |
| Karma, records and rewards | Read-only native score. Need score/reward and chapter-results pairs before any history or reward editing. |
| Weapons, Dragon Sword and upgrades | Item IDs/variants preserved; published Dragon Sword codes qualify identity only. ID 7 has distinct sword identity. Need upgrade/equip/action pairs, equipped-reference consumers and move prerequisites before level or ownership changes. |
| Ninpo, Ninpo capacity and health | Preserved. Existing public editors normalize duplicated halfwords, which does not prove their distinct meanings or dependencies. Need health-upgrade, damage/heal and Ninpo acquisition/use pairs with native consumers. |
| Techniques, skills and equipment choices | Preserved. Need move/weapon acquisition, upgrade and selection pairs; an inventory byte is not proof of a learned skill or equipped reference. |
| Experience/character levels | No Nioh-style EXP/level scheme is transplanted. Weapon/Ninpo upgrade records and Karma remain separate systems. |
| Companions/spirits, familiarity/proficiency and forging | No related-game schemas are transplanted. Original game's equipment/upgrade mechanics require their own native evidence. |
| Costumes/customization, chapter unlocks, difficulty, missions and completion | System data and progression remain separate and unchanged. Need genuine system format, integrity and one-action reward/unlock pairs. |
| Xbox 360 CON/STFS exports | Input rejected. Need qualified directory/allocation/hash parsing and native signing or an explicitly supported extraction workflow before container writes. |
| Other native revisions/record variants | Input rejected where header/mandatory-record profile differs. Need genuine intact saves, title metadata and native revision consumers. |

## Ninja Gaiden Sigma, Sigma 2 and Ninja Gaiden 2 Black

These editions are investigated separately. The original Xbox 360 checksum,
big-endian records and title profile above do not establish PS3, Vita, Switch,
Master Collection Windows or the 2025 Black remake.

### Sigma: Master Collection Windows/Steam research

The separately shared [GTrainers Sigma 1 save](https://gtrainers.com/load/categories/savegames/ninja_gaiden_sigma_1_savegame_all_difficulties_and_costumes_are_open/30-1-0-14091)
supplies **seven genuine gameplay files**, each exactly **240,976 bytes
(`0x3AD50`)**, alongside distinct 11,960-byte system data, 5,560-byte Survival
data and 2,588-byte user settings. An independently downloaded
[SaveGameWorld archive](https://www.savegameworld.com/pc-ninja-gaiden-sigma-1-savegame/)
contains the same byte-identical seven gameplay files. That is a redistribution
of the same corpus, not an independent second-player qualification.

The [unregistered shape inspector](../src/koei_editor/research/ninja_gaiden_sigma_pc/inspection.py)
strictly bounds the exact gameplay size, a UTF-16 `Game Save` description and a
seven-number slash-separated descriptive envelope. At `0xA00`, the native data
begins with variable little-endian words resembling a table, **not Sigma 2's
native length/revision/CRC header**. Those diagnostic words and description
integers are retained without guessing gameplay meanings. The PS3 health,
essence and Karma patch positions contain zero data in this PC corpus; they
cannot qualify PC fields.

The generic description is not a definitive native title signature. No native
revision, payload integrity, serializer or gameplay field has been proved.
Inspection therefore reports `qualified_game_profile=False`,
`integrity_verified=False`, `writable=False` and no recovered revision. Only
byte-exact unchanged copies are returned. Even a structurally accepted body
mutation never becomes a passing integrity check or permission to edit.
[Tests](../tests/test_ninja_gaiden_sigma_pc.py) cover bounded/malformed UTF-16,
foreign sizes and envelopes, exact snapshots, unresolved-integrity boundaries
and all seven genuine gameplay copies through `SIGMA_PC_NATIVE_DIR`.

The [public PC hex-list description](https://www.nexusmods.com/ninjagaidenmastercollection/mods/9)
explicitly describes brute-force item discovery. Its existence does not prove
occupied records, native integrity or safe gameplay prerequisites. A separate
[Sigma PC trainer author](https://www.nexusmods.com/ninjagaidenmastercollection/mods/156)
warns that all-weapon/Ninpo unlocks after Chapter 4 can break the game. This is a
concrete progression dependency to resolve before any ownership writer.
No third-party trainer or editor was executed, copied or shipped.

The hex-list's [author discussion](https://www.nexusmods.com/ninjagaidenmastercollection/mods/9?tab=posts)
gives a fixed `0x3906D` guide position and four-byte item codes, but those do not
prove a revision-independent inventory boundary. Its hidden running-attack
scroll example appears at different positions in the genuine story and mission
copies, with a displayed byte string crossing the apparent native alignment.
The author warns to retain that hidden scroll and to keep bow/arrow records
together; users report that injected inventory can remove Muramasa's shop
stock. These are concrete ownership/shop/move dependencies, not support for
unconditional item creation. No checksum recalculation mentioned in a guide
is insufficient proof that the native format has no integrity checks.

The essential missing inputs are a revision-matched native serializer/loader
and integrity rules (or proof of their absence), explicit native identity,
controlled displayed essence/inventory/equip/Ninpo/health pairs, and chapter
reward/weapon/technique prerequisites. Gameplay, system, Survival and user
settings remain separate profiles; none inherits Sigma 2 or console layouts.

### Sigma 2: Master Collection Windows/Steam research

An independently inspected [public-domain format note](https://gist.github.com/nm004/9eabd7b94b644fd8365e503471aec6cf)
documents Windows Master Collection profile fields and two CRC32 locations.
**31 genuine story files** from the separately shared
[GTrainers Sigma 2 save](https://gtrainers.com/load/0-0-1-13590-20) corroborate
the exact **35,968-byte** format: a `0xA00` UTF-16 description block followed by
`0x8280` bytes of native revision-6 data. This is not the original Xbox 360
profile's size, byte order or checksum scheme.

The native metadata CRC at relative `0xC` is **CRC32/BZIP2 over `[0x10, 0x1C)`**,
stored little-endian. It validates in all 31 genuine stories and covers the
separate native payload checksum word at `0x14`. The latter's range/algorithm
is **not qualified**. A valid metadata CRC only authenticates those 12 metadata
bytes, not the gameplay data. Research into conventional CRC variants, ranges,
byte order, initial states and additive checksums did not establish the native
payload rule. The read-only research inspector reports `integrity_verified=False`
and `writable=False`; it does not expose a supported editor.

The public note separates four character profiles at absolute offsets `0x13F0`
(Ryu), `0x16B0` (Rachel), `0x1970` (Ayane) and `0x1C30` (Momiji), stride `0x2C0`.
It names essence at `0x14A0` as a signed 32-bit value and an initial inventory
record at `0x14A4` as `u16` identity, quantity byte and level byte. These facts
are inspection leads, not transferable original-game offsets. Total inventory
boundaries and record/reward dependencies are not yet proved. Health, Ninpo,
loaded/pending costume choices and melee references remain read-only. Total
Karma (`0x1EFC`), current-stage Karma (`0x1F00`) and stage-start Karma (`0x1F04`)
are separate score values, not essence or EXP.

Essential inputs: a native revision-matched serializer/checksum implementation
or loader module, and controlled displayed essence, item use/transfer,
weapon/Ninpo upgrade, equip/costume and stage-result pairs. Full payload
integrity must be verified before any gameplay writer is enabled.

### Ninja Gaiden 2 Black: Windows/Steam research

The public [Black Steam editor repository](https://github.com/real-guilty/NG2B-Save-Editor/tree/fd7b25934e9cda24d47d9a59c7b7a3398ef22a0f)
contains compiled PyInstaller artifacts rather than reviewable application
source and has no explicit licence. Its README describes brute-force system
unlocks and mutually exclusive Tag Mission weapon selections. Nothing is
executed, copied or represented as native integrity/dependency qualification.

The separately shared [GTrainers Black Steam save](https://gtrainers.com/load/categories/savegames/ninja_gaiden_2_black_savegame_ninja_master_is_open/30-1-0-13376)
now supplies **18 genuine story saves and one genuine system save**. These
are GVAS v3, engine 5.4.2, UE4 package version 522, UE5 package version 1012,
custom format 3 with 79 custom-version entries. Every acquired file, including
story-named files, declares `/Script/NINJAGAIDEN2BLACK.SystemSaveData`.
The research parser derives byte-array offsets from the bounded complete
property tags: story files have `Title`, `Subtitle`, `Detail` and `ByteData`;
system files have `Title` and `ByteData`. `ByteData` is an
`ArrayProperty(ByteProperty)` and the outer format ends with four zero bytes.
No account context, titles or private data are exported to runtime metadata.

All 18 story arrays are `0x8280` bytes, native revision 6. Their native metadata
CRC32/BZIP2 over `[0x10, 0x1C)`, stored at `0xC`, independently validates in all
18. The payload checksum at `0x14` remains unqualified. System arrays are a
distinct `0x24B0` bytes; neither gameplay interpretation nor integrity is
qualified. Resemblance to Sigma 2 is investigated rather than treated as a
licence to transplant its fields. Both story and system inspection remain
unregistered and unwritable. Tests distinguish unchanged structural inspection
from full native integrity, genuine-file edit qualification and game loading.

The essential Black inputs are now **native payload integrity/serializer
evidence and controlled action pairs**, rather than another unexamined player
archive. System unlocks need their own integrity, difficulty/mode/reward and
equipment-reference proof. Mutually exclusive Dragon Sword/True Dragon Sword
and Dragon Claw/Tiger Fang/Blade of the Archfiend choices must not become blind
all-weapons toggles. Ownership, equipped references, derived stats and story
completion remain separate.

### Coverage and remaining platforms

| Edition / platform | Result and exact blocker |
| --- | --- |
| Original Ninja Gaiden II Xbox 360/Xenia extracted revision-6 stories | Implemented essence and existing stack reductions above. Other revisions, system data and STFS writes remain excluded. |
| Sigma 2 Master Collection Windows/Steam | Genuine full files, bounded read-only profiles and native metadata CRC; payload checksum, occupied inventory boundaries and native action dependencies remain unresolved. |
| Sigma 2 PS3 | [Region-specific Apollo patches](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLUS30380.savepatch) provide console-only leads with difficulty-dependent item locations and artificial cheat targets. Need genuine decrypted region-specific exports, all native integrity and controlled profile/item/reward pairs. These patches do not qualify Windows. |
| Sigma 2 Plus Vita | Distinct edition. Need genuine decrypted exports, title/revision/integrity and Vita-specific serializers/mechanics; PS3 or Windows schemas are not assumed. |
| Sigma 2 Master Collection Switch/PlayStation/Xbox | Distinct platform copies. Need complete native containers, integrity and platform-specific field/action evidence. Windows inspection alone adds no support. |
| Sigma PS3 | [Separate Apollo patch lead](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLUS30036.savepatch) uses completely different gameplay positions. Need native decrypted region exports and serializer/checksum/dependency proof; no Sigma 2 schema is transplanted. |
| Sigma Plus Vita | Distinct edition. Need native exports, integrity and edition-specific equipment/skill/customization/progression dependencies. |
| Sigma Master Collection Windows/Steam | Seven genuine gameplay files and bounded unregistered shape inspection. Need definitive native title/revision/serializer/integrity and displayed resource/equipment/Ninpo/technique/control pairs; all-weapon/Ninpo unlocks have reported Chapter 4 dependencies. |
| Sigma Master Collection Switch/PlayStation/Xbox | No platform evidence inherited from Windows or PS3. Need exact platform containers, serializer/integrity and controlled gameplay pairs. |
| Ninja Gaiden 2 Black Windows/Steam | 19 genuine outer GVAS files structurally inspected; story metadata CRC validated. Story payload and system integrity, stable occupied records and native dependencies remain unresolved. |
| Ninja Gaiden 2 Black PlayStation/Xbox and Windows Store | Separate platforms; Steam GVAS evidence does not qualify their containers, identities or integrity. |

Across unqualified editions, currencies and inventories need current-versus-score
distinctions and per-item capacities; weapons/Ninpo/health require upgrade,
ownership, equip and derived-value consumers; techniques/skills require their
own prerequisites; customization needs costume/loaded/pending references;
female-character profiles need separate equipped/quantity validation; chapter,
difficulty, Tag Mission, reward and completion state require system/progression
pairs. Nioh EXP, proficiency, forging, familiarity or spirit schemas are never
substituted for these games' mechanics.

### Razor's Edge: original US PS3 PSN story retry

The [NPUB31184 public catalogue](https://bucanero.github.io/apollo-saves/PS3/NPUB31184/)
provides an author-edited beginning-of-game export and a separate progressed
archive. Three distinct complete story/checkpoint exports were acquired,
including their original `PARAM.SFO` and console `PARAM.PFD`. Console decryption
was performed privately; neither downloads, player files nor account context
enter source or releases. The system file is a different profile and excluded.

Every acquired decrypted story is **35,184 bytes (`0x8970`)**, has big-endian
native size/revision `(0x8970, 6)`, and retains the observed constant framing.
All three independently verify **CRC32/BZIP2 over `[0x10,0x1C)`**, stored
big-endian at `0x0C`. This metadata CRC covers the separate word at `0x14`.
That word's gameplay coverage/algorithm remains unresolved. A valid metadata
CRC therefore cannot establish complete integrity or authorize a gameplay edit.
Published nearby PC and Xbox profiles are different; their checksums and item
records are not transferred here.

The [title-specific Apollo patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPUB31184.savepatch)
explicitly identifies Ryu/Ayane Karma at `0x11E8`/`0x11F0` as big-endian words
and labels those edits working. The author-edited native export agrees with
its published targets. Karma is a spendable skill/upgrade resource in Razor's
Edge, unlike the score use in other Ninja Gaiden editions; the cheat target is
not a legitimate natural maximum. The same patch combines story/checkpoint
and system annotations, extreme health/Ninpo values, costumes and chapter/trial
completion. Those unrelated fields and dependencies remain unqualified.

The new [bounded read-only inspector](../src/koei_editor/research/ninja_gaiden_3_razors_edge_ps3/inspection.py)
checks this native geometry and metadata CRC, reads only the two source-backed
Karma words and reports `integrity_verified=False`, `writable=False`.
File inspection additionally requires the original NPUB31184 story/checkpoint
`PARAM.SFO`, parsed selectively with bounded reads. It never promotes a system
export or another region into the story profile and never repairs a checksum.
Only the exact immutable original can pass its no-edit encoding operation.

[Regression tests](../tests/test_ng3_razors_edge_ps3_inspection.py) cover framing,
CRC corruption, malformed context, mutated inspection snapshots, unchanged
copies and the distinction between metadata and gameplay integrity. All three
private native stories were checked with
`NG3_RAZORS_EDGE_PS3_EXPORT_COPIES`; procedural files are separate boundary
fixtures. No edited game-load/resave was performed and no library card was added.

| Mechanic | Result / exact remaining requirement |
| --- | --- |
| Native story metadata | Size/revision/framing and metadata CRC verified on three distinct genuine stories |
| Gameplay integrity | Need the exact `0x14` payload checksum algorithm and coverage, or matching native serializer/loader evidence; a repaired metadata CRC does not resolve it |
| Ryu/Ayane unspent Karma | Source-backed read-only inspection; writes additionally need complete gameplay integrity and upgrade/reward dependencies |
| Skills, weapons and enhancements | Need qualified owned/acquired/upgraded records, costs and prerequisites; no level or ownership grants |
| Health, Ninpo and Life Bar upgrades | Need legitimate current/max/upgrade record dependencies; extreme published cheat targets are excluded |
| Costumes and system settings | Need a separate system-format integrity writer and exact named ownership/selected records |
| Chapter Challenge, trials, difficulty and completion | Need separate progression/result/reward records; story completion must remain separate from resource edits |
| Other platforms/regions/revisions | Need their own complete native exports and loader/writer qualification |

# Hyrule Warriors Definitive Edition: Switch native export

The independent adapter opens an extracted `zmha.bin` copy from Nintendo Switch.
It does not decrypt console storage or manage console accounts, keys or import.
The qualified observed profile is exactly **252,132 bytes (`0x3D8E4`)**, starts
with `00261015`, and stores its own complete size as little-endian u32 at `0xC`.
Other sizes, markers, editions and stored-size mismatches are rejected.

## Evidence and provenance

- [EdiZon factual definitions](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/blob/d16d36c7509c01dca770f402babd83ff2e9ae6e7/Configs/0100AE00096EA000.json)
  identify Switch title `0100AE00096EA000`, native filename `zmha.bin`, direct
  little-endian rupees/material quantities, character fields and fairy food.
  Their `bin.lua` performs direct scalar reads/writes without integrity repair.
- [iAroc's dedicated web editor](https://github.com/iAroc/iAroc.github.io/tree/15e4a928bdffb202a7893e14fde432f2dcbc10b3/hyruleWarriors)
  independently corroborates rupees at `0x2B8`, materials at `0x1AFE`, the
  character record group at `0x3307A`, and raw save export without a computed
  checksum. The project supplies no qualified save size or native fixture.
- [Public save-sharing thread](https://gbatemp.net/threads/request-hyrule-warriors-de-editor.506421/)
  contains attachment `hyrule-warriors-zip.130517`, one complete native file.
  The uploader explicitly describes edited progression. It contains nontrivial
  inventories and progression, but its existing hacked values are **not** proof
  of natural limits. The file remains private and is not distributed.
- [EdiZon issue 17](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/pull/17)
  documents successful progress persistence after a save-management bug was
  fixed in EdiZon 1.3.2. Earlier save-lock speculation is not treated as a native
  checksum or antipiracy algorithm.
- [EdiZon issue 8](https://github.com/WerWolv/EdiZon_CheatsConfigsAndScripts/pull/8)
  explicitly distinguishes changing a stored level from updating character
  stats and warns that its EXP action has additional irreversible consequences.
  No such progression action is reproduced here.

No project licence was located for the EdiZon definition repository or iAroc's
editor implementation. This project independently implements the storage,
parser, validation and UI contracts. Only factual byte positions, widths,
record ordering and English item/character identities inform the adapter; no
upstream script, UI, translated catalog, dependency or game asset is included.

The profile checks observed identity/size and preserves unknown bytes. Public
successful direct-file editing supports the current scalar write categories;
no aggregate native checksum is identified or fabricated. The adapter cannot
detect arbitrary corruption in unknown bytes. This is structural qualification,
not cryptographic authentication, and does not qualify other revisions.

## Coverage and precise blockers

| System | Implemented scope / remaining evidence |
| --- | --- |
| Rupees | Manual u32 edits at `0x2B8`, 0..9,999,999. Higher opened originals are preserved and can be restored to unstage. Published edit bounds do not establish a natural gameplay clamp; excluded from automatic Max. |
| Named materials | 102 known bronze/silver/gold factual identities in the u16 inventory beginning at `0x1AFE`; only opened ordinary quantities 1..999 qualify manual edits 1..999. Zero, higher, unidentified and reserved slots remain unchanged. Natural clamps and discovery-bit identities require further proof before Max, exhausted-item refill or acquisition actions. |
| Fairy food | 129 named u8 quantities inspected read-only. The source's 255 target is a storage ceiling; legitimate quantity limits, discovery/ownership and fairy-feed consumption dependencies are unresolved. |
| Character progression | 31 named records, stride `0x30` from `0x3307A`: existing unlock byte+`0xA`, EXP u32+`0x12` and stored level index byte+`0x1A`, all read-only. Need synchronized growth/stat/heart rewards, exact level encoding and acquisition dependencies. Reserved Ganon/Cucco rows are inspected without granting ownership. |
| Character health/attack/badges/combos | No writes. The public source calls one health field uncertain and permits values beyond its u16 width. Native caps, derived growth and badge nodes/costs/prerequisites need controlled growth/allocation pairs or native routines. |
| Existing weapon stars | Qualified normal state `0x03` and existing Legendary state `0x13`, known ordinary weapon IDs, stars u16 at record+`0x14`, 0–5 with natural Max. Master Sword ID 60 is excluded by identity regardless of state; reserved Ganon/Cucco IDs 108/109 and unknown states/IDs stay read-only. The observed pool has 1,030 × `0x28` physical entries from `0x337F4` to EOF, 345 occupied rows and 344 qualified star fields. No identity, state, base power, equipped reference or collection flag changes. |
| Ordinary weapon seals | Existing positive known ordinary KO counters may decrease 0..opened value, conservative admission at most 5,000, normal state `0x03` only. 38 genuine native counters qualify. Skill IDs/slots are preserved, named inspection covers IDs 0..54, and every KO action is excluded from Max. Evil's Bane 41, Legendary 42, Exorcism 53 and the entire Master Sword record are always excluded. Larger/unusual or unknown counters remain read-only. |
| Power / fusion / collection-sensitive seals | Stored base power is distinct from the derived star-adjusted attack. Power, skill creation/swaps, capacity, fusion costs, reward/collection flags and special-seal prerequisites remain read-only. Master Sword / Evil's Bane / Legendary / Exorcism collection dependencies are unqualified. Other profiles need independent layout proof; Wii U offsets are not reused. |
| Adventure map cards/stages/exploration | No writes. Candidate Adventure offsets do not qualify all nine maps, reward/medal/rank/objective bits, fog, item cards, searches or prerequisite state. Need exact map record identities and controlled use/clear/reward pairs. |
| My Fairy / companions | Food inspection does not edit fairy ownership, element, personality, skills, trust, refresh levels, clothing or companion skills. Need native fairy records and feed/refresh/equip pairs, with growth thresholds and dependencies. |
| Story/character/weapon/costume unlocks | No writes. Unlock flags alone cannot create starter equipment or rewards. Need explicit ownership/entitlement and reward dependencies; story remains separate from resource controls. |
| Collections/gallery/music/movies/medals | No writes; named flag records and legitimate unlock/reward prerequisites are missing. |
| Other revisions/platforms | Need separate complete native samples, their exact identity/size/integrity and independent field maps. Wii U, 3DS Legends, Age of Calamity and Switch 2 are different formats. |

## Validation

Fifteen format/contract/native and real-Tk checks pass with `HYRULE_DE_COPY`
enabled. The private native file passes byte-exact unchanged roundtrip, surgical
known-material edits and independent edits to all 382 qualified weapon fields.
Procedural checks cover malformed shapes/markers/stored size, immutable snapshots,
invalid pending edits before Max, special/unknown/empty/higher record exclusions,
original-value unstage, material Max exclusion, read-only growth/food inspection,
backup/restore and source/destination protection. GUI workflows cover named
search, weapon-star Apply/Review/Undo, ordinary-seal Max exclusion, inspection,
themes and backup/new-copy saving. Without the native input, two native checks
skip explicitly.

**No edited Switch save was imported, loaded or re-saved in the game.** The
shared downloaded file is edited native data, not an untouched gameplay control.
Controlled unmodified before/after saves remain useful for deeper qualification.

## Unreleased weapon expansion evidence and checks

The dedicated Switch source `CreateWeaponObj` reads eight little-endian u16 KO
counters at +0..+0xE, ID +0x10, base power +0x12, stars +0x14, eight u8 skills
+0x16..+0x1D and identifier +0x1E. `SaveCurrentProcess` writes those exact fields;
our surgical writers touch only staged star/ordinary-counter bytes. The source
has a `<212` UI filtering error; its full named weapon catalogue includes Yuga's
ID 212, and we preserve that independently mapped valid record.

[nedron92's original Legends source](https://github.com/nedron92/HWL-SaveEditor/blob/master/source/core/HWLWeapon.cpp)
independently describes the same relative weapon structure and enumerates states
`0x03` normal, `0x13` Legendary and `0x0B` Master Sword. This corroborates state
interpretation alongside the dedicated Switch getters and actual native record
patterns; no 3DS absolute position or file-size rule is transplanted. Its
`change_stars` recalculates a display value as base damage × (1 + stars × 0.1);
`save_stars` stores only +0x14 and no derived attack scalar. We preserve the
Switch record's base power and all state/identity/reference bytes. The 0–5 star
quality range is independently described as gameplay weapon quality, not inferred
from its u16 storage ceiling. We do not reproduce its 650 base-power cheat limit.
No project licence was found; only factual layout/identity observations are used,
with independent Python implementation and no source/assets copied.

The native specimen contains one Master Sword (ID 60, state 0x0B) with both
Evil's Bane and Exorcism counters. Its entire 40-byte record remains identical
across every targeted new-feature test. All 382 qualified weapon fields were
independently changed, serialized/reparsed and checked for differences confined
to their declared scalar range. Every unknown/empty/reserved record, ordinary
weapon's base power, skill IDs, state and opaque references are preserved.

The existing eight format checks and original real-Tk workflow, plus six new
format/native/GUI checks in `tests.test_hyrule_definitive_expansion`, pass
**15/15** with the private genuine export variable enabled. New tests cover
surgical star+counter edits, source-specific Yuga ID, special-seal/Master Sword
exclusions even under unusual states, reserved/foreign IDs, higher-star Max
preservation and original-value unstage, invalid pending edits before Max,
individual genuine native fields and searchable stars/seals with visible Max,
Review, Undo, theme, inspection, backup/new-copy saving and restore. Two optional
native checks skip if the private fixture is absent. This remains native-file and
real-Tk qualification, not actual edited Switch game-load/re-save validation.


# Additional Switch Warriors native-format investigation

This round acquired complete title-labelled public Switch exports from the
[NX_Saves catalog](https://github.com/Viren070/NX_Saves/tree/main/nintendo/switch/savegames).
Archive contents were examined as data only; no binaries were executed. Unlike
the PC envelopes, the observed files are plaintext. Plaintext alone does not
qualify a gameplay writer, and none of these candidates is registered as a
supported editor.

| Exact title/platform | Native material acquired | Precise remaining requirement |
| --- | --- | --- |
| Dynasty Warriors 8: Xtreme Legends Definitive Edition — Switch `0100E9A00CB30000` | Complete `SVDT`, 2,424,832 bytes; native header includes a revision-38 word. | A full Switch writer/loader or an accepted controlled edit/load/re-save pair establishing native integrity and named field records. Existing PC encryption, PS3 patch offsets and repeated-looking records are not used as Switch mappings. |
| One Piece: Pirate Warriors 4 — Switch `01008FE00E2F6000` | Complete `SlotData0`, 2,560,028 bytes, and `UserData`, 10,240 bytes. Serialized header order is checksum/revision/length, with observed revision14. | A complete Switch serializer/writer or targeted gameplay pairs proving all nested checksum coverage plus Beli/coin/growth meanings. The PC revision15 serializer uses different framing/header order; no offset subtraction or revision substitution is advertised. |
| Warriors Orochi 4 / Ultimate — Switch `010016A00AEC0000` | Two distinct exports with `SVDT`, 5,210,112 bytes, and `SVDTU`, 927,523 bytes. Their leading version/date words are 20180720 and 20200101. | Complete Switch integrity/serialization and field evidence, plus partner-file dependencies. Matching filenames and public progress labels do not establish resource offsets, active edition or absence of checksums. The missing PC gameplay DLL is not a Switch format input. |

The public EdiZon save-script/config corpus and Switch editor collection were
checked for title-specific full writers; their available Koei adapters concern
other games. Published live-process cheats and commercial save-modifying services
supply feature labels without a reusable native disk writer. No foreign code,
patch catalog, player bytes, game assets or binaries are incorporated.

Switch-specific source or controlled native comparisons are the enabling inputs;
these candidates no longer need speculative decryption research merely to inspect
their acquired plaintext exports. A separate source-backed English Switch
[Persona 5 Strikers adapter](P5STRIKERS_SWITCH_FORMAT.md) was qualified in this
round instead of registering these unresolved formats.

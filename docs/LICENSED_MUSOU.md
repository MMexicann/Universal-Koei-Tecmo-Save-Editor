# Licensed Musou: Gundam and Ken's Rage

This expansion covers the assigned Gundam and Ken's Rage games only. The
registered console editors accept copied **decrypted gameplay files**, never
signed console containers. Keep `DATA.BIN` and edited `.bin` copies beside the
original `PARAM.SFO`. Its bounded `SAVEDATA_DIRECTORY` identifies the selected title and slot.
Gundam 1 uses an identity-only companion; the v1.9 Gundam profiles bind the
complete original companion digest. Account fields are never interpreted or
edited. Missing, malformed or foreign
identity companions are rejected. Apollo remains responsible for decrypting,
reimporting, encrypting and resigning the original console save. This application
does not write `PARAM.PFD`, change ownership or produce signed-console exports.

All controls use the existing scalar workspace, immutable staging, Undo,
Review Changes, automatic snapshot backups and atomic Save As to a new file.
The copied-save CLI uses the profile-specific context hook: older profiles
generate an identity-only companion; the v1.9 profiles preserve the exact opaque
original companion in the private output directory. Neither signs a save or
changes ownership; player metadata is never included in public artifacts.

## Dynasty Warriors: Gundam: US/EU PS3

Profile `gundam1_ps3` requires `BLUS30058` or `BLES00147` metadata and decrypted
`DATA.BIN`, 561,152 bytes (`0x89000`). The observed native identifier is
`0x00002711`, with framing words `0x20` and `0x1DD2` at `0x14` and `0x18`.
Four genuine [US](https://github.com/bucanero/apollo-saves/tree/master/PS3/BLUS30058)
and [EU](https://github.com/bucanero/apollo-saves/tree/master/PS3/BLES00147) saves
qualify identical gameplay framing and three big-endian byte-add integrity words:

| Stored sum | Half-open coverage |
| --- | --- |
| `0x8` | `[0x20, 0x2000)` |
| `0xC` | `[0x1DD1, 0x88DD0)` |
| `0x10` | `[0x20, 0x89000)` |

The individually mapped pilots are Amuro, Kamille, Judau, Domon, Heero and Loran.
Their published EXP bases are `0x188`, `0x49C`, `0x93A`, `0xAC4`, `0xDD8` and
`0x10EC`; no assumed stride creates other records. The level byte is base +16,
equipped skill references are base +23..26, and 36 learned bits begin at base +29.
Each byte uses its least significant bit first. A skill write adds one bit and
preserves every other mask bit, padding byte and native reference. The broad
seven-byte all-skills cheat is not reproduced. Labels retain native skill IDs;
an inferred guide order does not establish a native name catalog.

Only qualified existing level-30 pilot records accept learning edits. Removing
learned skills and bulk Max are unavailable. Unknown levels, references and
unqualified records remain unchanged. Equipped references were independently
cross-checked against learned bits in all four genuine inputs. Complete native
unchanged roundtrips and missing-skill surgical additions pass file checks;
edited console acceptance remains untested.

The [skill acquisition guide](https://www.k-rakuraku.com/musou/kihon/sukir.html)
corroborates the level-30/36-skill boundary; it does not prove lower-level native
dependencies or authorize a copied skill-name catalog. Gundam backups include
an identity-only `.sfo` sidecar alongside the `.bin` and `.json` snapshot files.
Keep all three together for restore; its destination must retain the same
qualified title/slot identity. Full player metadata is never copied into backups.

The [US Apollo patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLUS30058.savepatch)
and [EU patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLES00147.savepatch)
provide independent record positions and integrity facts. Genuine saves were
reviewed against Apollo saves commit `c6fa97f2f4ef1b3469f0421c727997108821e188`.
Pilot and mobile-suit points represent growth/EXP rather than an established
spendable currency. The patches change both EXP and stored levels, without
proving level thresholds or derived stat updates. EXP and levels remain read
only. Four equipped skill references are now writable on qualified level-30
records with six distinct, in-range, learned selected/inherent references.
Choices use only originally learned non-inherent IDs. Selecting an already
equipped skill atomically swaps the two slots; duplicate, unlearned and inherent
choices are rejected. Learned bits and both inherent references stay unchanged;
a newly learned staged skill becomes an equipment choice after saving and
reopening. Equipment choices have no Max. Exact source/native corroboration and
swap/Undo dependencies are in
[CONSOLE_PIRATE_STRATEGY_DEPTH.md](CONSOLE_PIRATE_STRATEGY_DEPTH.md).

Further inputs: controlled EXP/level/stat and skill-acquisition pairs,
lower-level skill prerequisites, mobile-suit growth and parts/equipment pairs,
and mission-clear/reward and collection dependencies. Other pilot records and
PS2/Xbox 360 profiles need separately proven native identities, layouts and
integrity. Optional genuine tests use `GUNDAM1_PS3_COPIES`, a private folder
containing the reviewed regional copies; no player bytes are committed.

The four genuine inputs provide 20 qualified pilot records and 269 missing-skill
single-bit additions. Every independent output reparses with all three native
sums and changes only its target skill byte and required integrity words.

## Ken's Rage: US/EU PS3

Profile `kens_rage1_ps3` requires `BLUS30504-00` or `BLES01062-00` metadata and
decrypted `DATA.BIN`, 786,432 bytes (`0xC0000`). Two genuine player exports from
[InsideGame's public save page](https://in-sidegame.com/fist-of-the-north-star-kens-rage-ps3/)
share the exact eight-word header `(0, 0, 0x1B8D, 0, 0, 1, 0xF1, 0)`.
These are observed layout identifiers; they are not an invented release version.

The [US Apollo patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30504.savepatch)
and [EU patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLES01062.savepatch)
individually name the eight base fighters Kenshiro, Toki, Raoh, Rei, Shin,
Thouzer, Jagi and Mamiya. Their skill-point fields are two-byte big-endian values
at `0x12F + index * 0x240`. Only positive original balances whose preceding two
bytes are zero qualify for editing. Empty balances and anomalous high-half
values are inspected, with no latent resource grant or partial-word overwrite.
No DLC fighter is manufactured from the remaining published offsets.

The [player mechanics guide](https://gamefaqs.gamespot.com/ps3/976861-fist-of-the-north-star-kens-rage/faqs/61481)
distinguishes unspent skill points from purchased Meridian Chart nodes and
equipped abilities. Resource edits preserve learned nodes, equipped skills,
temporary battle gauges, story/mission flags and all unknown bytes. Manual
0..9999 edits are allowed; 9999 is the published editing target, **not a proved
natural maximum**. An unusual higher original balance survives unchanged and
can unstage a pending edit by assigning its opened value. Bulk Max is disabled.

The published patches perform direct gameplay writes with no native checksum
update. No game-internal integrity algorithm has been independently established;
header matching cannot detect arbitrary non-header corruption. This adapter
declares `INTEGRITY_KIND='external'`, keeps `editing_verified=False`, and never
reports a verified native checksum. PFD authentication is external and untouched.
Genuine unchanged roundtrips and surgical byte comparisons qualify the scoped
published field implementation; they do not prove the absence of an internal
checksum or actual edited console acceptance.

Both genuine inputs pass all eight one-field surgical edits (16 total), with
the original bytes preserved through GUI edit/review/Undo/Save As/backup/restore.
The US/EU header and published mappings are independently identical; this
Save As requires the same exact supported title/slot companion as the opened
copy and rechecks source and destination identity immediately before writing.
Restore requires its admitted destination title/slot to remain unchanged while
validating backup bytes. It does not validate account ownership or convert
signed regional containers.

Further inputs: native serializer/integrity confirmation and edited console
load/re-save; fighter ownership flags and controlled SP purchase/Meridian Chart,
equipped skill, persistent growth and mission-clear/reward pairs. Other regional
headers, DLC, Xbox 360 and Ken's Rage 2 layouts need independent qualification.
Optional genuine checks use `KENS_RAGE1_PS3_SAVE_COPIES`, private paths separated
by the platform's path separator.

## Ken's Rage 2: EU PS3

Profile `kens_rage2_ps3` requires `BLES01801` metadata and decrypted `DATA.BIN`,
786,432 bytes (`0xC0000`). Native framing has version 2, main size `0x54C4`,
internal size `0x548C` and independently checked section versions and lengths.
Two [Apollo public saves](https://github.com/bucanero/apollo-saves/tree/master/PS3/BLES01801)
independently qualify the complete layout and all six CRC32 words. Unknown bytes,
including the nonzero opaque tail beyond `0x54E4`, are preserved byte for byte.

CRC32 words are big endian; the following coverage is half-open. Children are
updated before the global parent. Invalid input is rejected before editing;
checksums are regenerated for qualified edits and the output is reparsed.

| Stored CRC | Coverage |
| --- | --- |
| `0x2C` | `[0x30, 0x4B8)` |
| `0x4C4` | `[0x4C8, 0x16A0)` |
| `0x16AC` | `[0x16B8, 0x1FEC)` |
| `0x1FF8` | `[0x1FFC, 0x20CC)` |
| `0x20D8` | `[0x20DC, 0x54E4)` |
| `0xC` | `[0x20, 0x54E4)` |

The [EU Apollo patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLES01801.savepatch)
provides five CRC operations; the sixth untouched section is independently
confirmed in both genuine inputs. Collection positions are music `0x212`
(54 bytes), movies `0x24E` (7), events `0x28B` (62), `0x2EE` (15) and `0x2FE`
(133). Each entry has a stable offset-derived field ID and a one-byte status.
Only an originally zero entry accepts the published unlock target 1. Existing
1, observed 2 and unknown higher states are inspected and preserved. Relocking
and bulk Max are unavailable. There is no guessed name catalog or blanket
overwrite of complete collections.

Both genuine samples already have all 271 mapped collection entries nonzero.
Their complete unchanged roundtrips and GUI open/inspection/unchanged Save As,
backup and restore qualify native preservation. Surgical unlocks, Undo and
review are tested on clearly procedural locked records. **A genuine locked
gallery entry and an edited console load remain untested.** Registration retains
`editing_verified=False` while the independently qualified native profile has
`sample_verified=True`.

The [publisher's PS3 manual](https://199xhokutonoken.files.wordpress.com/2013/02/shm_ps3_it.pdf)
distinguishes persistent Life, Aura, Attack, Defense and Technique growth/EXP
from battle Life/Aura reserves. Signature moves depend on story progress or
Aura growth. Scrolls have ownership, five equipped slots, inventory/transfer
rules and derived Nexus bonuses. None of these systems is represented by a
gallery flag. The published defeated-enemy counter at `0x12D0` is history,
not a resource; it is not exposed for editing.

Further inputs: an incomplete unchanged `BLES01801` export containing locked
gallery entries; labelled growth level/EXP, scroll acquire/equip/proffer/receive
and mission-clear/reward pairs; scroll identities and dependency rules. US,
Japanese, Xbox 360 and Wii U editions require independent complete native
profiles and genuine files. No offsets are transferred between platforms.

## Gundam 2, Gundam 3 and Reborn: current scope

| Title | v1.9 status | Remaining systems and inputs |
| --- | --- | --- |
| Gundam 2, US/EU PS3 | Unregistered; four genuine native exports have now been acquired and three byte-add integrity domains corroborated. [Retry](GUNDAM2_PS3_RETRY.md). | Pilot Points are EXP. Controlled growth/level/stat, skill acquisition, parts/lab submission and equipment pairs are needed to establish safe writable dependencies. Missing-save claims from the earlier survey are superseded. |
| Gundam 3, US PS3 BLUS30703 | Registered money reductions, lab EXP and license inspection. The complete published money writer and one genuine original US export qualify this scoped profile. [Format](GUNDAM3_PS3_FORMAT.md). | Lab-level thresholds, license versus owned-part records, growth, friendship, skill and mission dependencies need controlled pairs. Other regions require independent writer/layout qualification. |
| Gundam Reborn, EU NPEB02060 / JP NPJB00533 PS3 | Registered money and existing Amuro/Kamille Team Point reductions, named resource inspection; two genuine complete exports qualify native additive integrity. [Format](GUNDAM_REBORN_PS3_FORMAT.md). | Individually mapped materials, other pilot records, skills, plans/component fusion, equipment and mission/reward dependencies need controlled pairs and native schemas. Regional patches are not interchangeable profiles. |

The [Gundam 2 publisher manual](https://archive.org/details/ps2_Dynasty_Warriors-_Gundam_2_USA)
proves maximum pilot level **50**, despite the Apollo patch's “Level 30” target.
Pilot Points are EXP; suit, pilot level and body-part rank affect skill
acquisition. Collected parts, licenses and equipped skills are different
systems. Lab submission consumes owned parts; lab technology gates upgrades.
Seven friendship tiers affect partner attacks and missions. These mechanics
explain the required dependencies; a PS2 manual does not qualify PS3 offsets.

Gundam 3 player-authored [friendship](https://www.supercheats.com/playstation3/walkthroughs/dynastywarriorsgundam3-walkthrough01.txt)
and [skill](https://www.supercheats.com/playstation3/walkthroughs/dynastywarriorsgundam3-walkthrough02.txt)
guides distinguish partner, playable-pilot and operator rights, unread messages,
friendship milestones and Memorial Mission prerequisites. A primary manual was
not obtained in this pass; no control is chosen from those guide claims alone.

Reborn's patch distinguishes spendable money from lifetime money earned,
pilot EXP from stored level and Team Points, and materials from plans. Its bulk
pilot counts and speculative ultra-stat plan labels do not establish safe
record ownership or natural maxima. Player-authored
[skill-system notes](https://w.atwiki.jp/shin_gmusou/pages/210.html) corroborate
individual pilot skill availability and Team Point activation. A primary manual,
controlled action pairs and native plan schemas remain missing.

PS2 Gundam 1/2 need extracted memory-card gameplay entries with native identity,
revision, layout and integrity; exact entry filenames are not established here.
Xbox 360 Gundam 1/2/3 and Ken's Rage 1/2 need separately extracted gameplay
entries, exact title/region/build, endianness and game checksums; native filenames
remain unqualified and CON/STFS signing stays external. Shin Gundam Musou Vita
and Ken's Rage 2 Wii U similarly need their own complete decrypted/extracted
gameplay files and platform-specific profiles. None can reuse PS3 offsets.

## Sources and licence boundary

[Apollo patches](https://github.com/bucanero/apollo-patches),
[Apollo saves](https://github.com/bucanero/apollo-saves) and the
[Apollo library](https://github.com/bucanero/apollo-lib) supply public factual
leads and integrity cross-checks. The adapters independently implement the
observed file facts using Python integer/byte operations and standard CRC32.
No Apollo GPL implementation, third-party catalog, downloaded executable,
player save, account identifier or extracted game asset is included in source
or package inputs. Public saves and signed metadata were inspected privately;
downloaded binaries were not executed.

## Validation distinctions

Earlier expansion validation (historical counts):

Final focused run: **41 passed, zero skipped/failed**. Full regression run:
**1,189 discovered, 854 passed, 335 skipped, zero failures/errors**. All eight
genuine copies were explicitly selected. Startup, inventory consistency,
copied-save CLI and 424-file source/privacy checks pass. These outcomes do not
replace the per-title limitations above.

Procedural tests verify all mapped transitions, malformed/foreign input,
checksum failures, metadata identity, higher-state preservation, source changes,
backups/restore and surgical byte preservation. Genuine-file tests explicitly
select private copies through `KENS_RAGE2_PS3_SAVE_COPIES` (paths separated by
the platform's path separator); they skip when copies are absent. Real Tk
workflows run with a display. File qualification does not establish console
acceptance: **no edited save was loaded or re-saved in an actual game**.
Windows executable/native CNG validation also remains separate from Linux tests.

## Additional console source retry

The earlier missing-export blockers for Gundam 2, Gundam 3 and Reborn are
superseded by the v1.9 documents linked above. Gundam 2 remains research-only
because safe progression/equipment dependencies are unresolved. Gundam 3's
published complete money-write path retains external console integrity; it does
not claim a verified game-internal checksum. Reborn independently validates its
native additive checksum. No related game's checksum or record ordering is
transplanted into another profile.

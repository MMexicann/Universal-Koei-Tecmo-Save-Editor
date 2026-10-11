# Warriors All-Stars and Warriors Orochi 4 research

Reviewed 2026-10-10. Attached executables were read as byte buffers and
statically disassembled; neither executable was run. No game assets, binaries,
player saves, account data or private filesystem paths are included here.

## All-Stars: recovered PC envelope

The qualified PC adapter lives in `src/koei_editor/games/stars/`. It edits
available gold in existing campaign slots and existing ordinary material
quantities by numeric ID. Lifetime earned gold is inspected separately.
`src/koei_editor/research/stars/stars_candidate_codec.py` remains an immutable,
unchanged-reconstruction inspector; its permissive envelope check does not
authorize edits or imply support for earlier gameplay revisions.

The executable is AMD64, with an encrypted `.text` section and a SteamStub 3.1
`.bind` entry point. Its original code was decrypted privately for static
inspection using the documented header arithmetic; no instruction from the
executable was executed. The inspected code imports Windows CNG AES and embeds
`SAVEDATA.BIN` plus the standard `Documents/KoeiTecmo/WARRIORS ALL-STARS/Savedata`
path. This agrees with the [public backup manifest](https://github.com/mtkennerly/ludusavi-manifest/blob/master/data/manifest.yaml)
and the [PC save-location discussion](https://steamcommunity.com/app/610190/discussions/0/598539991659863325/).

Recovered instruction addresses below are RVAs in this supplied revision,
not save offsets and not supported revision identifiers:

| Routine RVA | Static finding |
| --- | --- |
| `0x71D4C0` | File span sizing: global plaintext `0x79B66`, slot plaintext `0x78E41`; each rounds to 16 bytes, adds 16 sentinel bytes and a 4-byte seed. |
| `0x71C450`, `0x71C360` | Global block uses key index 9; nine subsequent slot blocks use indices 0–8. |
| `0x71D560` | Initial double `(index+1)*0.5/10`, then ten ordered `x=(1-x)*(3.66*x)` operations. The native coefficient's IEEE754 bytes at RVA `0xA9BC98` are `48 E1 7A 14 AE 47 0D 40`. The low DWORD of the final double seeds key generation. |
| `0x71DF90` | AES-128 key: advance unsigned DWORD with `state*0x343FD+0x269EC3`, emit the high byte, repeat 16 times. |
| `0x71E440` | IV: advance unsigned DWORD with `state*0x15A4E35+1`, emit bits 16–23, repeat 16 times. |
| `0x71E560`, `0x71E8A0` | Explicit CNG `ChainingModeCBC`, key length 128, no CNG padding. |
| `0x71CB50`, `0x71BF10` | Encrypt and compare the final 16 bytes `FingerPrint01234`; store the initial IV seed as an unencrypted trailing DWORD. |
| `0x71C170` | Native encrypted slot offset `0x79B84 + slot*0x78E64`. |

The observed complete encrypted file size is `0x4B9D08` (4,955,400 bytes):

| Block | Key index | Plaintext bytes | Encrypted bytes | Seed bytes |
| --- | --- | --- | --- | --- |
| Global/system | 9 | `0x79B66` | `0x79B80`, including padding/sentinel | 4 |
| Each of nine slots | 0–8 | `0x78E41` | `0x78E60`, including padding/sentinel | 4 |

Original IV seeds and padding are preserved exactly. The native fingerprint
comparison is **not a checksum over the preceding payload**: the regression
suite demonstrates that changing a CBC block far from the trailer still passes
the sentinel. The native serializer audit below establishes the current revision
and narrow scalar layout separately. The outer key/IV arithmetic does not take
an account ID; the supplied executable and acquired file do not require save-owner
context for this envelope. No account or entitlement changes are implemented.

The key seeds are stored explicitly after independently checking the executable's
ordered double arithmetic. This avoids floating-point differences in future
portable interpreters. All ten native block keys are distinct. Three independently
checked key hex answers are index 0 `830284a809ce8f8865cc668dd3cf29bd`,
index 8 `f3a06c0e5210e4f2c546bb96b6d11542` and global index 9
`685e72a485f9b2fe4dbe386a94b2a921`. Keys do not establish a gameplay revision.

`inspect_candidate(raw)` checks exact observed size and all ten decrypted
sentinels. `reencode_unchanged(document)` rejects any modified payload, padding,
seed or block order and verifies byte-exact reconstructed ciphertext. It has no
file writer and does not use a sentinel as authorization for gameplay writes.

### Qualified current serialization and scalar proof

The current writer supports exactly 4,955,400 encrypted bytes and revision
`0x170302F4`. Header routine `0x4912F0` serializes three DWORDs plus four bytes;
it accepts native revisions F1–F4, while the supplied build initializes
`0x17030204` and ORs `0xF0` to emit F4. Earlier revisions are not writable because
component layout and reserved spans change with version. Both stored slot
selections must be 0–8 for this qualified profile. Unknown remaining header
bytes and all original block seeds/padding are retained.

Root serializer `0x48F470` uses system component runtime `+0x470`, then nine
campaign components `+0x19BA0 + slot*0x6D820`. Their actual vtables resolve to
system serializer `0x44A000` and campaign serializer `0x44A670`. The active
component tree was disassembled through compiler-split function fragments:

- System children `0x462640`, `0x4745C0`, `0x46AFA0`, `0x469B60`, `0x470710`.
- Campaign children `0x45B1D0`, `0x4559E0`, `0x466410`, `0x464810`,
  `0x44CCD0`, `0x44B040`, `0x45F540`, `0x461240`.
- Generated scalar/array helpers, raw one-byte copies `0x552520`/`0x5525B0`,
  and the revision-dependent zero-filled reserved spans.

The only remaining external endpoints in these active serializers are memory
copies, stack-cookie checking and resolved array element/count virtual methods.
The array vtables and constructors were checked: these methods select bounded
records or read their counts. No checksum, hash, account-derived key or extra
payload transformation occurs in this tree. Native AES load `0x71BF10` verifies
the fingerprint then copies the exact selected plaintext span; native file
load `0x71C510` verifies complete length and the ten outer blocks. The writer
adds the native fingerprint and original seed to each AES-CBC block. Thus the
adapter reports **no payload checksum**, and never calls the fingerprint a full
payload-integrity guarantee. Unrelated payload corruption remains undetectable
by that fingerprint and cannot be silently repaired.

Offsets below are relative to an individual decrypted campaign payload, unless
marked global. They are derived from native serialized widths, not runtime
object offsets:

| Field | Packed offset / width | Native proof and safety |
| --- | --- | --- |
| Existing campaign selected hero | `0xA3C` / signed 16 bits | Preview `0x44A2B0` reads campaign runtime `+0xA48`, accepts 0–99. Serializer `0x4559E0` writes its component `+0x198` at packed `+0x196`, after the first component's `0x8A6` bytes. Empty `-1` and unknown values exclude the campaign from all writable fields. No hero identity is changed. |
| Available gold | `0x2F6A` / unsigned 32 bits | Campaign `0x4559E0` serializes runtime `+0x26CC`. Its preceding packed component is `0x8A6` bytes; the second component's preceding scalars/arrays consume `0x26C4`. Getter/setter `0x455250`/`0x455270` clamp at 9,999,999. Max preserves higher opened values. |
| Existing material stacks | `0x2F10 + materialID*2` / unsigned 16 bits; 45 IDs | `0x4559E0` serializes the 45 words at runtime `+0x2672`; getter/setter `0x4552A0`/`0x4552D0` accept IDs 0–44 and cap at 9,999. Only existing ordinary positive quantities are writable, individually 1–9,999; zero, higher values and empty/unknown campaigns remain read only. Bulk Max excludes materials. |
| Lifetime earned gold | Global `0x1CE` / unsigned 32 bits | Header 16 bytes plus configuration `0xEC` bytes; `0x4745C0` emits a DWORD, five 40-byte arrays and six bytes before runtime `+0xD4`. This history is read only. |

Native grant/spend routine `0x47EDD0` increases global `+0xD4` only for positive
gold grants, while it changes campaign `+0x26CC` for positive and negative
amounts. Material-sale call `0x6AFB6A` grants gold and `0x6AFBE7` passes a
negated selected material quantity to `0x47EF10`. The latter changes the 45
material-stack array and processes acquisition/request notification paths only
on positive grants. Reward/crafting call `0x6B73B8` processes five material
ID/quantity entries. The editor changes existing balances/quantities directly;
it does not synthesize a purchase, acquisition, reward claim, lifetime grant,
request completion or achievement event.

The genuine copy has nine qualified selected-hero records and corroborates the
available gold/material offsets. It also has available balances above its
lifetime earnings, so no guessed `available <= lifetime` dependency is enforced.
Material names, rarity, origin and trait recipes are documented in the community
guide, but its alphabetical ordering is not proof of native IDs. The editor
therefore shows honest numeric material IDs and preserves all ownership/history
bytes. No game catalog was extracted or bundled.

### Existing ordinary Hero Card selection (unreleased expansion)

The native campaign serializer `0x44A670` writes 100 hero records through
`0x466410`, then 2,200 card records through `0x464810`. Their packed sizes are
`0x48D` and `0x53` respectively; these differ from runtime strides `0x498` and
`0x58`. Relative to each campaign payload, the hero array starts at `0x3F6E`
and the card array at `0x20682`. The equipped-card DWORD is at hero packed
`+0x20E` (runtime `+0x214`). Setter `0x466080` changes that DWORD alone. The live
hero embeds its saved component at `+0x34`; gameplay path `0x46514D` reads the
corresponding reference at `+0x248`, resolves the actual card, and applies its
effects. This is an equipment reference, distinct from the hero's ordinal ID.

Native ownership predicate `0x464220` restricts an ordinary hero's pool to
physical card records `20*heroID .. 20*(heroID+1)-1`; friendship-gift records
2,000–2,199 follow a separate path. Occupied-card check `0x464310` requires a
valid physical index and signed stored card identity 0–1,999. The editor exposes
selection only when the original already resolves to an occupied ordinary card
in the same hero pool and that pool has at least two qualified cards. It offers
only other occupied cards from that pool, rejects empty/unknown/cross-hero/gift
references in stage, review and serialization, and excludes equipment from Max.
No card, acquisition, growth, regard, story or reward bytes change.

The genuine public PC export contains 144 eligible hero selectors with 1,539
qualified pool choices across its nine campaigns. Every choice is tested for a
surgical four-byte plaintext edit and preservation of the remaining native
cipher blocks, seeds and padding. The searchable card inspector displays its
2,655 occupied records with numeric card identity, stored attack, element and
trait IDs; these properties remain read only. Numeric labels avoid asserting an
unproved name or item catalog.

Card growth is deliberately separate: load helper `0x463D70` derives runtime
level through external `GrowthExpData` lookup `0x483250`, then recomputes stored
rarity and attack through `0x4877F0`/`0x487B20`. The matching installed `LINKDATA.BIN` and `LINKDATA.IDX` assets (both names
appear in the executable), including their growth tables, card descriptors and
name/localization catalogs, plus controlled customization pairs
are required before modifying card EXP, level, attack, rarity, traits, element,
affinity or fusion state. Choosing an existing card requires none of those
properties to be rebuilt.

### All-Stars coverage checklist

These are mechanically documented systems to map, not invented writable fields.
One complete genuine PC file is now privately qualified. Native serializers
and update routines establish the narrow implemented fields below. Broader
mechanics still need semantic catalogs and controlled action comparisons;
neither the complete file nor a working cipher alone establishes those fields.

| Mechanic | Research result and specific remaining proof |
| --- | --- |
| Gold/training purchases | **Implemented:** available balances in qualified existing campaigns, native cap 9,999,999; lifetime earnings read only. Purchase-specific quest/history and training-level dependencies remain blocked by controlled training/purchase comparisons. |
| Character levels, EXP, actions, stats | Actions unlock with levels (guide reports all actions at level 20); map EXP versus derived level/stats and action flags. Bravery is battle-local and must not be presented as permanent character level. |
| Characters and route rosters | Initial factions and recruited roster differ; Opoona has ending dependencies. Distinguish permanent availability from current campaign recruitment; preserve selected protagonist and faction. |
| Hero cards/equipment | **Implemented:** select existing ordinary cards inside each hero’s native twenty-record pool when the original reference is valid; no Max, creation or transfer. Search occupied cards by numeric identity and inspect stored attack/element/trait IDs. Friendship Gifts, growth, rarity, attack, affinity, element/trait edits and occupied trait capacity require matching card descriptors/growth tables and controlled customization pairs. Card affinity is distinct from regard. |
| Card customization and materials | **Implemented:** existing ordinary quantities for 45 material IDs, manual 1–9,999 without acquiring empty stacks; bulk Max excludes them. Names-to-native-ID catalog, card traits/capacity, recipe checks, consumption and quest/reward dependencies remain blocked by native catalog or controlled named-material/customization comparisons. |
| Elements | Five reported card elements: Fire, Ice, Lightning, Darkness, Love, plus no element. Frenzy is a combat effect, not a discovered sixth card element. IDs/ranks remain unmapped. |
| Regard/bonds and Hero Skills | Regard rewards and paired Hero Combo/Combo Skills require distinct character-pair records. Map asymmetric/symmetric structure, thresholds and prerequisites before bulk changes. |
| Requests/quests | Three request stages have fixed card/reward structure and reset with the main story/new game plus. Map active requests, progress, claimed rewards and reset behavior separately. |
| Stories, endings and map battles | Three faction routes, hero endings and true route unlocks have prerequisites. Require separate actions from currency/stat edits; no completion flags are enabled. |
| Gallery, songs and collections | Achievement and discussion evidence identify collectibles/unlocks; map ownership separately from viewing/new flags and DLC entitlements. |
| Mounts/bodyguards/weapon proficiency | Not established as independent permanent systems in this title. Do not import another Warriors game's features by analogy. |

Mechanics sources actually read:

- [Understanding Warriors All Stars](https://steamcommunity.com/sharedfiles/filedetails/?id=2911155500): Heroes, Hero Cards, Bravery and battle-local effects.
- [Materials List](https://steamcommunity.com/sharedfiles/filedetails/?id=1128232772): material names, origins, rarity and trait recipes.
- [Quest Compendium](https://steamcommunity.com/sharedfiles/filedetails/?id=1128263301): regard/card rewards, three-stage requests and story reset behavior.
- [Card elements](https://steamcommunity.com/sharedfiles/filedetails/?id=1132460396): five elements and Frenzy distinction.
- [Achievements guide](https://steamcommunity.com/sharedfiles/filedetails/?id=1400955882): action/level progression and ending/Opoona dependencies.
- [Setsuna character unlock guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2801764723): faction recruitment and true-route prerequisites.

Guide observations are community mechanics evidence, not serialization offsets
or independently established gameplay bounds.

## Warriors Orochi 4 / Ultimate — qualified PC editors

The originally supplied `WO4.exe` was a launcher. The subsequently supplied
matching `WO4.dll`, `WO4U.dll` and native saves resolved that missing input.
Both modules were inspected statically, never executed. Complete native
serializers and the independent two-block AES implementation now qualify
separate original and Ultimate gameplay adapters. The encrypted fingerprint
is an end marker, not a body checksum; the complete writers emit no additional
native body checksum.

- [Original PC format](WO4_PC_FORMAT.md): revision 20180720 and its qualified
  header/layout. Gems, Crystals, Growth Points, progressed officers’ byte Skill
  Points (cap 99), existing weapon-element quantities and Skill Orb reductions.
- [Ultimate PC format](WO4_ULTIMATE_PC_FORMAT.md): revision 20200101 and its
  qualified header/layout. Gems, Crystals, Growth Points, progressed officers’
  word Skill Points (cap 999), promoted officers’ unspent Upgrade Stones,
  existing attribute inventory and Skill Orb reductions.
- Both have searchable native officer, weapon, inventory and history records;
  unchanged full reconstruction, surgical native edits, protected storage and
  actual Tk workflow checks passed. Edited game loading remains unperformed.

The per-edition format checklists are authoritative. Older Ultimate revision
20191201 needs its own version-sensitive serializer qualification. Remaining
work concerns named native catalogs and field/dependency maps for weapons,
fusion, equipment, officer growth, learned skills, camp/bonds, story rewards,
Infinity progression and collections. Neither Steam-owner metadata nor another
launcher is required for the recovered WO4 envelopes.

See the [official mechanics and source gates](WO4_SW5_ABYSS_MECHANICS_GATES.md).
The [public WO4U mod loader](https://github.com/Fragonite/zmod) supplies runtime
corroboration only; no runtime or PS4 offsets were promoted as PC disk offsets.

## Sample acquisition and validation limits

Public GitHub repository searches, Steam discussions and Steam guides were
retried after networking became available. Those discussions supplied
save-location and load/corruption reports. A later normal download from
[SaveGamePro's All-Stars page](https://savegame.pro/pc-warriors-all-stars-savegame/)
successfully supplied native `SAVEDATA.BIN`, exactly 4,955,400 bytes, and two
separate input maps. The file remains private. Its first test exposed an earlier
research error: the logistic coefficient was incorrectly recorded as 4.0.
Re-reading the actual native constant and complete routine established 3.66;
with that correction, all ten encrypted sentinels and a byte-exact unchanged
roundtrip pass on the genuine file. This corrects the unregistered research
codec's false key fact. Subsequent complete native serializer/update-path
inspection qualifies the separate current-F4 gold/material/card-selection copy editor described
above. The native header rule is independently recovered, and the genuine
plaintext begins with `0x170302F4`. WO4 discussions inspected
initially supplied save troubleshooting; renewed SaveGamePro downloads now supplied encrypted player exports described below.
Some later guide requests returned HTTP 429; those are rate limits, not evidence
that a feature or sample does not exist. No access control was bypassed.

The procedural test generator independently uses the documented double/key/IV
arithmetic and distinctive payload/nonzero padding. Seven focused checks pass;
one optional `STARS_SAVE_COPY` check now also passes on the acquired private
native copy. Tests cover exact no-edit ciphertext, ten-block boundaries, altered
snapshot rejection, invalid parameters, truncation/foreign input, damaged
sentinels and the sentinel's inability to detect unrelated CBC corruption.

All-Stars genuine outer-envelope roundtrip and targeted gold/material/card-selection
output reconstruction are verified. The expanded registered-editor suite passes
28 checks under Xvfb with zero skips: eleven format, one original GUI, six new
card-equipment (including genuine surgical and GUI), six prior independent
audit and four new independent card-equipment review checks. Eight separate
unchanged candidate-codec checks also passed previously. Tests cover exact plaintext preservation outside each targeted scalar,
unchanged encrypted blocks, original seeds/nonzero padding, malformed input and
unsupported revisions, empty campaign/material exclusion, higher values, safe
backups/restore, changed-source rejection, live-folder aliases, search, Undo,
Review Changes, themes and safe saving. The original procedural GUI fixture is synthetic; the new card-selector GUI workflow opens a separate copy of the genuine public native export.
**No edited All-Stars save was loaded in the game.** WO4 now has separately
qualified native PC editors described above. Follow-up native fixtures remain private and should be
selected by environment variable; never add them to the source manifest.

For deeper All-Stars qualification, provide complete native PC `SAVEDATA.BIN`
copies from the same supported build before and after one identified action:
named material acquisition/consumption; training or level gain; one card equip,
trait customization or fusion; one regard interaction or request reward; and
one explicitly identified route/ending unlock. A legitimate native ID/name
catalog or matching build's data files would establish human-readable hero,
material and card names; unrelated platform offsets cannot substitute. The
attached All-Stars executable already supplies this build's serializer and
outer encryption; no matching DLL or save-owner key is currently missing.

Steamless's static wrapper documentation was inspected at
[commit cd770bf](https://github.com/atom0s/Steamless/tree/cd770bf9749d3e4f438d23ac643917ad1a804257).
Its CC BY-NC-ND 4.0 implementation remains outside this repository and release.
No third-party unpacker code was copied into the public candidate module, which
implements the game's independently observed save arithmetic using the
project's existing CNG AES provider.

A renewed GitHub repository search for `Warriors Orochi save editor`,
`Warriors Orochi 4 save`, `WO4U.dll` and `Warriors Orochi 3 save editor` found no
repository match. Earlier code search found only mod-loader references to the
DLL. Search absence does not establish that a sample or editor does not exist;
the initial launcher-only investigation preceded the matching DLL inputs. Current
WO4 qualification and remaining revision-specific blockers are described above.

### Renewed WO4 public player-export acquisition

Normal public download links on [the WO4 page](https://savegame.pro/pc-warriors-orochi-4-savegame/)
and [Ultimate page](https://savegame.pro/pc-warriors-orochi-4-ultimate-savegame/)
now supplied 7z archives. They were inspected and extracted privately without
executing any binaries or included shortcuts. The base-labelled page contains
`SAVEDATAU.BIN`, 927,576 bytes; the Ultimate-labelled page contains both
`SAVEDATA.BIN` and `SAVEDATAU.BIN`, each 927,576 bytes. Both include separate
135-byte input maps. The filenames and page descriptions do not prove their
revision, edition or loadability. Neither the common word/byte stream cipher
hypotheses nor unencrypted parsing qualified their headers; no speculative
codec or gameplay adapter was added during that initial investigation. The later
matching DLLs and supplied same-build saves now qualify the two PC editors;
public exports with older Ultimate revisions remain outside their supported scope.

Legacy console/source leads were rechecked. `PythWare/Warriors-Orochi-2-Editors`
is an asset-editing lead without an explicit source licence, not a qualified
Xbox disk-save codec. `JustGillin/omni360` is an Xbox game installer/download
project, not a Warriors save editor; `SHODAN-HORAI/SHODAN-Stat-Editor` concerns
another title. Apollo's public PS3 save collection currently has no Orochi entry
in its title index. Existing PS3 patch definitions and original community
Xbox editors still require an exact decrypted gameplay export, matching title
revision, native integrity proof and safely identified dependencies; console
patch offsets are not used as PC offsets. No restricted code or game assets were
copied into this project.

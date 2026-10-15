# Dynasty Warriors: Origins — native Steam format evidence

The Origins adapter implements the native Steam envelope and surgical resource,
existing-bond, provincial-peace and qualified weapon-reinforcement edits for slot
revisions 16, 17, and 29. Revision 29 also supports its separate DLC skill-point
pool. Native executable analysis and copied-save roundtrips establish the
format evidence below. Loading and re-saving an edited copy in the game has not
been validated; procedural fixtures do not establish that outcome either.

The v2.5 request status is tracked [separately](ORIGINS_REQUEST_STATUS.md).
Weapon proficiency and Old Coin writes remain unavailable. Backup creation now
checks the opened source before and after backup; Save As checks it around
serialization/output creation and reparses the actual destination. Failed
post-write verification retains the destination and reports failure; comparing
bytes before deletion cannot protect a concurrent replacement. Do not import
output from a failed save operation; review again and choose a new destination.

## Native executable evidence

The save reader, writer, serializer dispatch, size calculators, and merchant
resource operations were inspected read-only in the installed x64 executable
for Steam build **21711288**, executable SHA-256
`5b8599854143ef7483b272dfa28f7cae616add6b2a8c31550c8a0c8eb1bd63d9`.
Addresses below are RVAs relative to the executable image base, not trainer
addresses or offsets inferred from encrypted differences.

The codec independently implements the observed arithmetic without an asset
encryption key, DW3 key, or AES hypothesis. Game assets, save payloads, player
identifiers, personal paths, and private reports are excluded from public files.

## Native envelope

| Kind | File size | Decrypted body size |
| --- | ---: | ---: |
| Slot | `0x271664` (2,561,636 bytes) | `0x271660` |
| USER | `0x2804` (10,244 bytes) | `0x2800` |

The four-byte header contains a little-endian 16-bit checksum followed by a
little-endian 16-bit stream seed. For each little-endian 32-bit body word,
advance the unsigned 32-bit state once, then XOR the word:

```text
state = (state * 0x5b1a7851 + 0xce4e) mod 2^32
output_word = input_word XOR state
```

The checksum sums all decrypted little-endian 16-bit body words modulo 65,536.
Native routines are reader RVA `0x18a6fa0`, writer `0x18a6e80`, and checksum
`0x18a6d90`. The native step table at `0x34f0168` contains one- and two-step
variants; only the demonstrated one-step Steam variant is supported.

This weak checksum verifies envelope integrity, not cryptographic authentication
or game identity. The gameplay parser separately qualifies slot kind, revision,
native serialized length and structure. USER can be decoded and roundtripped
but is rejected by the gameplay slot editor. No alternative codec is probed.

Nine reviewed native slot copies and one USER copy passed checksum verification,
byte-exact decode/encode roundtrip, and input-preservation checks. The public
tests cover independently expressed procedural arithmetic, no-op roundtrip,
corruption/truncation, wrong kind, invalid parameters, related-game cipher
rejection, and targeted-byte preservation. `ORIGINS_SAVE_COPY` selects an optional
private native-envelope fixture; missing fixtures skip honestly.

## Slot identity and revision

Offsets here refer to the decrypted **body**, excluding the four-byte envelope.
Its first `0x660` bytes are slot metadata; the following gameplay serialization
area has capacity `0x271000` bytes.

| Body offset | Representation |
| --- | --- |
| `0x660` | Little-endian `uint32` serialized length, including the revision word and excluding this length word |
| `0x664` | Little-endian `uint32` serialization revision |
| `0x668` | First native subsystem's two-byte record |
| `0x66a` | Second subsystem's main gameplay record |

Writer callback RVA `0xc813b0` writes length and revision 29, then native eligible
subsystem serializers in registry order. Load callback `0xc81570` reads the
length and delegates to `0xa92f80`. That reader uses `0xa914d0` to calculate the
exact serialization size for the supplied revision, rejects a mismatch, then
invokes the serializer. The buffer is sequential packed serialization.

Registry initialization RVA `0xa916f0` defines subsystem counts and mode flags.
The 72 factory registrations, virtual tables and pure revision-dependent size
routines were followed and independently evaluated. Eligible sizes plus the
four-byte revision word give these native results, also matching the copies:

| Qualified revision | Native serialized length |
| ---: | ---: |
| 16 | `0x214ed` (136,429 bytes) |
| 17 | `0x214ee` (136,430 bytes) |
| 29 | `0x22b5d` (142,173 bytes) |

These are native size calculations, not guessed sample signatures. Other
revisions are conservatively rejected. Unknown metadata, padding, unused
capacity and unsupported records remain unchanged.

## Gold and skill-point serialization

| Field | Body offset | Storage | Supported range |
| --- | --- | --- | --- |
| Gold | `0x69b` | Unaligned little-endian `uint32` | 0–999,999 |
| Base unspent skill points | `0xa87` | Unaligned little-endian `uint16` | 0–999 |
| DLC unspent skill points (revision 29 only) | `0x21f1a` | Little-endian `uint16` | 0–999 |

Native subsystem zero has one record, initialized at RVA `0xa91725`. Serializer
`0xaebe70` writes two bytes; size calculator `0xaebee0` returns two bytes per
record for every qualified revision. Subsystem one has one main gameplay record.
Its serializer `0xa68980` writes the first 48 bytes and one additional byte,
then the four-byte Gold member at memory offset `0x384`. Therefore its absolute
body offset is `0x660 + 4 + 4 + 2 + 0x31 = 0x69b` (plaintext file offset `0x69f`).

Factory RVA `0xb2eb50` and virtual table `0x33eb708` register the main record;
its record wrapper calls the serializer without additional record headers.
Getter/setter RVAs `0xa69e20` / `0xa69e40` and add/subtract routines `0xaacdb0` /
`0xaace90` establish the resource and cap. Merchant sell/buy paths `0x1250d50` /
`0x1251b60` connect those operations to Gold transaction prices. This establishes
disk layout and gameplay semantics without transplanting a memory address.

The main-record serializer then writes `0x384` skill-ownership bytes and `0x64`
status bytes before serializing the 16-bit skill-point member at memory offset
`0x458`. Its body offset is `0x66a + 0x31 + 4 + 0x384 + 0x64 = 0xa87`.
Getter/setter RVAs `0xa69fc0` / `0xa69ff0` and gain/spend `0xaaa3d0` / `0xaaa440`
establish the unspent counter and cap 999. Skill-purchase payment call `0x12b933b`
reads catalogue prices and spends this member; portable-item purchase call
`0x1251eb7` does likewise. Exchange payment `0x12534bc` spends points before the
Gold grant at `0x1253507`. This counter is distinct from skill ownership and the
DLC-specific point pool. Those relationships are not bulk-unlocked or silently
changed by this edit.

The DLC pool belongs to registry subsystem 31. For revision 29, native size
calculations put the subsystem at body offset `0x21ef6`. Its serializer RVA
`0xa79d30` writes the 16-bit member at memory offset `0x22` at record offset
`0x24`, giving absolute body offset `0x21f1a`. Independent execution of this pure
serializer with a generated record confirmed a 46-byte output and that exact
member placement. Native getter/setter `0xa7a900` / `0xa7a930` cap it at 999.
Skill-purchase catalogue flag bit zero at entry offset `0x1b` selects payment
from this pool instead of the base pool. Earlier supported revisions 16 and 17
have no serialized subsystem 31, so the DLC field is absent there. Other revision
layouts remain unqualified even where native version gates are known.

Edits preserve seed, length, revision, metadata and unrelated body bytes. Only
the declared field bytes and required checksum bytes can change. An unchanged value
unstages the edit; Max must not lower an unusual higher existing value. The
serialized result is reparsed and checked for localized changes.

## Existing bonds and provincial peace

All offsets below address the decrypted body, and all integers are little-endian.

| Structure | Revision 16 | Revision 17 | Revision 29 | Layout |
| --- | --- | --- | --- | --- |
| Bonds, subsystem 2 | `0x136e` | `0x136e` | `0x1436` | 101 packed records, 5 bytes each |
| Provincial peace, subsystem 23 | `0x1f64b` | `0x1f64c` | `0x1f716` | 13 `uint16` counters |

Bond serializer RVA `0xaeafa0` emits the level byte, an unknown byte, training
`uint16`, then another unknown byte. Native level getter/setter `0xaafa20` /
`0xaaf9b0` cap the level at 5. Training setter `0xaaff60` caps its counter at 999.
Only already-formed records with level 1–5 are exposed; the editor does not
manufacture bonds for all 101 capacity records. Unknown bytes are preserved.

Completion predicate `0x124f720` needs level 5 and at least three trainings,
alongside other bond, event and learned-art conditions. Level 5 alone does not
promise complete conversations, reward claims or a 100% bond achievement.
Training is a historical counter, so it is manually editable but excluded from
bulk Max. These edits preserve event, request and learned-art records.

Peace getter/setter `0xa9e350` / `0xa9e1e0` access 13 native `uint16` counters at
memory offset `0x976`; the setter clamps at 10,000 and requests a runtime map
refresh, without modifying reward claims. Serializer `0xa710f0` places those
counters at subsystem stream offset `0xd40`. The UI at `0x1276030` divides by
10,000: 100 points represent 1%, and 10,000 represents 100%. Reward claim flags
remain separate. Peace progress can affect skirmish availability in gameplay.
The province index is retained in each stable field ID.

Friendly labels follow native lookup chains. Bond catalogue slot 387, factory
`0xb3be70`, asset 4258, maps bond to character with the signed word at row `+4`.
Character catalogue asset 4234 uses 60-byte rows; getter `0xa65430` reads name
index at `+0x12`. Name slot 142 uses English localized table 5509, which native
archive selector `0x18546c0` assigns to archive 8 (`LANG/ENG`); local-index
routine `0x1854930` subtracts 5509, giving English file 0. Its 12-byte rows
contain row-relative string pointers. Stable labels exist for bonds 0–46, 48
and 99. Dynamic bond 47 and placeholder rows retain native ID labels.

Province slot 185 uses English logical table 5593, local file 84, with thirteen
8-byte rows and row-relative string pointers. Native name UI `0x13d1a70`
receives the same province index used by the peace counter.

Confidence: high for packed offsets, native bounds and direct setter behavior;
reward/event dependencies intentionally remain unchanged.

## Weapon inventory and reinforcement

| Structure | Revision 16 | Revision 17 | Revision 29 | Layout |
| --- | --- | --- | --- | --- |
| Weapon inventory, subsystem 3 | `0x1567` | `0x1567` | `0x162f` | 1,000 packed records, 27 bytes each |

Native inventory search `0xab3ac0` uses indices 0–849. Records 850–899 are
temporary and later records are reserved; those records are never edited.
Serializer RVA `0xaec5a0` emits each record as follows:

| Record offset | Type | Meaning | Editing policy |
| --- | --- | --- | --- |
| `+0` | signed `int16` | Weapon catalogue ID, 0–299; `-1` is empty | Preserve |
| `+2` | `uint8` | Reinforcement level, 0–99 | Qualified occupied weapons only |
| `+3` | Six `uint16` | Trait IDs | Inspect and preserve |
| `+15` | Six `uint8` | Trait levels | Inspect and preserve |
| `+21` | `uint32` | Instance identity | Preserve |
| `+25`, `+26` | Two bytes | Additional flags | Preserve |

Native upgrade getter/setter `0xa64c10` / `0xa64c30` and reforging routine
`0xab3400` establish the 99 cap. The game combines matching weapon IDs and
computes the sum of reinforcement levels plus one, capped at 99.

Weapon catalogue pointer slot 452 (`+0xe20`) is created by factory `0xb365b0`,
which records logical asset ID `0x10e7` (4327). Boot lookup initialization
`0x185ee10` establishes identity translation for that index. Loader `0xc28100`
reads a 16-byte header and 300 rows of 28 bytes from that installed catalogue.
Native material eligibility `0xab39e0` checks row flag bit 0 at `+0x19`.
Derived factual qualification metadata is used by the editor; game assets and
asset-encryption material are not distributed. Empty, unknown, reserved and
ineligible catalogue records are preserved.

The native forge path also records reaching +99 in profile statistics; that
achievement flag is preserved rather than granted as a side effect of editing.
Equipped weapon references, grades, traits and attack calculations remain under
the game's control. This field is reinforcement, not weapon-family proficiency.

Confidence: high for inventory encoding, direct upgrade bounds and catalogue
qualification. No weapon acquisition, trait manufacturing or proficiency editing
is enabled by this mapping.

## Weapon proficiency dependencies

Subsystem 5 has 50 records of 14 bytes. Each starts with proficiency XP
(`uint32`), followed by four equipped Battle Art IDs (`uint16`) and two bytes.
Native XP gain `0xab02d0` compares levels through threshold catalogue `+0xed8`,
then calls `0xab6910` to set moveset unlock records in subsystem 10 and grant
level/rank-derived rewards. Their exact resource semantics are not all mapped.
Additional story and DLC gates affect the cap.

This establishes why changing XP alone can produce a high displayed proficiency
with missing moves. XP, Battle Arts, rank, skill ownership and moveset records
remain unchanged until their complete transition rules are implemented. A
numeric storage ceiling is not used as a proficiency maximum.

## Persistent battle clear history

Subsystem 26 stores 1,000 completion bytes after 150 bytes of profile data and
2,000 event bytes. Serializer RVA `0xadfa80` / member helper `0xadfb20` place
the history at relative stream offset `0x866`:

| Revision | Body offset |
| --- | --- |
| 16 | `0x210a1` |
| 17 | `0x210a2` |
| 29 | `0x21365` |

Native getter `0xabc860` reads this array. Setter `0xabc780` only sets a clear
byte to 1 and requests UI refresh; the editor follows that monotonic behavior.
Existing clear entries cannot be reset. Story selection `0x12fc7bd` and
completion counting `0x124a830` read the same persistent history.

Catalogue slots 427/428 use factories `0xb389f0` / `0xb388a0` and logical assets
4590/4591: 190/270 records, each 28 bytes after the 16-byte header. The native
catalogue getter reads the signed `int16` identifier at `+0` and type byte at
`+0x11`. Types 1, 7 and 8 are counted as battles. The qualified base-game IDs are
0–15, 19, 22, 24–27, 39, 40, 42, 44, 46, 49, 51, 56, 57, 59, 62, 65 and 68.
Additional ID 70 is withheld because its content qualification is unresolved.
Only canonical 0/1 saved bytes are exposed; reserved and unusual data is preserved.

These are manual completion controls, excluded from Max. They do not finish an
active campaign, grant rewards, establish route endings or alter story-event
state. Current-run stage states are in a separate subsystem and remain unchanged.
Confidence: high for the history representation, native counted-battle IDs and
direct setter behavior; full-story completion dependencies remain unknown.

## Public evidence inspected

| Source | What it establishes | What it does not establish |
| --- | --- | --- |
| [VdustR/game-save-dwo-d4h](https://github.com/VdustR/game-save-dwo-d4h), commit `b5e853eec865417edf473eb9b39330b1cf0f74e8` | Publisher identifies `SLOT0008.dat` as an Origins Steam Dream of the 4 Heroes DLC save; README documents `%LOCALAPPDATA%\KoeiTecmo\Dynasty Warriors Origins\Savedata\<steam_user_id>\` | Native save schema, executable version, editable fields, integrity rules, independent game-load validation |
| [Kelebek1/dwo](https://github.com/Kelebek1/dwo), commit `5de9b3e615691f2280ceeb6100416275adfbe75c` | Origins LINKDATA asset and stage-script research | A save-specific decoder or save offsets |
| [Official systems overview](https://www.koeitecmoamerica.com/dw_origins/us/system/) | Weapon mastery, ranks, traits, bonds and requests are separate gameplay systems | Save offsets or numeric field limits |
| [Official DLC overview](https://www.koeitecmoamerica.com/dw_origins/us/dlc/) | Additional weapon types, Battle Arts and progression systems | Native representation or universal proficiency caps |
| [Official updates](https://www.koeitecmoamerica.com/dw_origins/us/update/) | Platform-specific changes, including post-story skill-point exchanges | Save serialization or safe editing dependencies |

`src/koei_editor/data/origins_evidence.json` contains public reference metadata only. A fingerprint
match means **exact equality to that published artifact**, not checksum validation
or schema qualification. Choosing a game never selects another game's parser
as a fallback.

## Needed samples

Use separate copies from the **same Steam game version and DLC configuration**.
Record version/build, whether DLC is installed, slot type, and the exact values
displayed in game. Keep saves and detailed reports private.

| Sample pair | Change between copies | Evidence needed before enabling edits |
| --- | --- | --- |
| Control A/B | Save twice without intentional gameplay changes | Timestamp, randomness, account binding and other background changes |
| Gold A/B | Earn or spend an exact documented amount | Additional independent game-load and re-save qualification |
| Skill points A/B | Gain/spend a known point amount | Further point-pool dependencies and independent game-load qualification |
| Level/progression A/B | One known level or experience change | XP thresholds, derived stats and rank dependencies |
| Proficiency A/B | Increase one weapon family's proficiency | Family identities, progression representation and caps |
| Weapons/equipment A/B | Acquire or equip one known item | Inventory IDs, slot references, attributes and bounds |
| Gems A/B | Acquire/equip one gem or change one level | Inventory/equipment linkage and upgrade limits |
| Horses A/B | Acquire/equip one horse or gain one level | Stable identities, equipment reference and progression |
| Battle Arts A/B | Unlock/equip one art | Ownership and equipped-slot dependencies |
| Bonds A/B | One recorded bond increase | Character IDs, thresholds and event flags |
| Story/unlocks A/B | Complete one known mission/route | Completion, unlock, reward and replay dependencies |

A fresh early-game slot, a mid-game slot, and an end-game slot remain useful.
One completed DLC save cannot map every dependency. Proficiency, gem and horse
progression, Battle Arts, bond event rewards, active story state and weapon trait
caps remain unqualified for editing. Future executable/DLC revisions require their own
serialization qualification. Never transplant another game's schema or trainer
addresses into the disk format.

Each enabled field has native identity/structure evidence, exact no-edit roundtrip,
localized-edit preservation, malformed-input rejection and native range evidence.
Independent game loading remains a separate validation step. Active-story
editing additionally needs verification of dependent flags and rewards.

## Functional copy tools

Open explicitly selected `.dat` copies outside live/Steam Cloud folders. The
workspace creates an automatic hash-verified backup and identifies the known
public reference when applicable. Save Copy As and Restore create new files and
refuse existing destinations, including races. Comparison shows byte counts and
up to 128 changed regions; totals include all regions. Reports use
`.changes.json`, contain fingerprints and sizes but no file payloads or absolute
paths, and are excluded by the repository's privacy rules.


## Named inventory inspection

The shared inspector now exposes existing qualified weapon records as searchable
rows: native slot, weapon ID, stored upgrade, six trait IDs and their individual
stored levels. The already established 27-byte stride and occupied pool are
reused; reserved records are excluded. Unknown IDs and unusual upgrade/trait
levels remain unchanged. This is inspection, not an ownership grant or a new
trait writer. Other tabs keep resources, provincial peace, bonds, training and
battle history separate. A complete public DLC save passed unchanged inspection;
procedural tests also cover high and reserved values.

## Stored proficiency inspection

The development Proficiency tab displays stored XP and equipped Battle Art IDs
without enabling writes. Both unmapped state bytes are preserved. Separate public initial,
advanced and DLC slots corroborate a 50 × 14-byte array at body `0x7F8D` for
revisions 16/17 and `0x8055` for revision 29, 174 bytes after the qualified weapon
array. A conservative original-family/Art-ID topology check gates the optional
view. Unrecognized topology produces no rows and does not reject a save that
otherwise qualifies for existing edits.

Only formed original-family and recognized DLC rows are displayed; the remaining
capacity stays opaque. Formed Art slots are present even for weapons that have
not been acquired. Their presence is never used as an ownership flag. Bow is
named where present; the other unmapped DLC family keeps its numeric identity.
The inspector does not infer levels from XP or modify the two state bytes.

Public-source provenance and precise unfinished writer requirements are in
[Origins request status](ORIGINS_REQUEST_STATUS.md). Candidate Coin body `0xA95`
remains unqualified and is not a field. Resource writes preserve the entire
proficiency area and all unqualified resource candidates byte-exact.

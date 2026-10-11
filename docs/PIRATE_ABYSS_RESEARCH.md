# Pirate Warriors 4 and Warriors: Abyss PC evidence

PW4 has a qualified native PC revision-15 editor for spendable Beli and quantities
of already obtained coins. Abyss now has a native A4 Karma Embers editor, with
its original copied Steam sidecar; the separate system category remains read-only research. No attached executable was executed. No player save, binary, unpacked
code, account identifier or private fixture is included in the distribution.

## Pirate Warriors 4

### Supported envelope and native serialization

The attached x64 executable identifies `OP4WINUSER.dat` and `OP4WINSLOT%04d.dat`.
The mapped editor accepts only native `0x27161C` PC slots; the `0x2804` system
save is excluded. Little-endian `u16` checksum and seed precede the encrypted
payload. Complete `u32` words are XORed after advancing this 32-bit LCG:

```text
state = (state * 0x5B1A7851 + 0xCE4E) modulo 2^32
```

Region advances per word are WW/JP/EA=1, AS=4 and EU/NA=3. The editor explicitly
qualifies the one-step family; three-/four-step files are rejected. The checksum
is the decrypted `u16` word sum modulo 65536. Native functions are
`0x14159DBE0`, `0x14159DD00`, `0x14159DE10`; the step table is `0x14197C140`.

A genuine, freely shared PC slot was downloaded through the public Steam guide
“Pirate Warriors 100% save data for all dlc.(it's99.9%true)”. The completion label
is its uploader's claim. Its original download address remains private under
the contributor fixture policy. The native file has the expected size and its
unchanged roundtrip is byte exact. Three-/four-step decryptions fail checksum;
WW cannot be distinguished from the identical JP/EA arithmetic. No matching
system save, controlled before/after pair or edited game-load test is available.

The native stream starts at decoded payload `0x618` (raw `0x61C`). Serializer
functions `0x14131D750` and `0x14131D960` use `0x80` object headers with `u32`
checksum, total subtree length and revision at 0/4/8. All 144 top-level subtree
lengths and **145 own-body checksums** are validated. Battle subtree index 5 has
own body `0x1D730` and a nested `0x420` child. Parent integrity excludes that
child. Native checksum function `0x1415F1150` sums own-body bytes and clears bit
31; the bounded objects cannot reach its high-word overflow threshold.

Only the demonstrated revision-15 ordered layout is accepted. The attached
writer emits revision22 and has conversion hooks; changing headers to22 is
unsafe. Unknown header/body bytes and trailing capacity remain unchanged.
Damaged native checksums are rejected even when the outer checksum is repaired.
Only an edited object's checksum and the outer checksum are recomputed.

### Proven resource mappings and dependencies

RTTI identifies profile vtable `0x14196E5D0`. Getter `0x14023D9F0` gives body
length `0x1065C`; `0x14023DA00` returns object+`0x10`. Serialization therefore
maps profile object+`0x14` to payload `0x6BC0`. Native Beli reward/update routines
`0x14132A670` and `0x1412DCA80` read/update that current balance and cap it at
**999,999,999**. They separately update lifetime earnings at object+`0x7A0`
(payload`0x734C`), capped at4,000,000,000. Lifetime earnings remain read only:
achievement/reward dependencies are not fully mapped, and setting a resource
balance does not represent earning it through gameplay.

Slot-summary renderer `0x14159EB00` reads playtime (profile+`0x10`) and completion
getters `0x1415EE250`, `0x1415EE1C0`, `0x1415EE5B0`. It does not read current
Beli. Hours/minutes and completion percentages have mirrored numeric metadata
at payload`0x600`; the reader checks agreement and preserves them during edits.

`CDataSaveCoin` vtable `0x141953A70`, constructor `0x1412FC2E0` and body getter
`0x1400B70B0` identify root-list entry9, body`0x19400`, payloadbody`0xB8988`.
The equal-sized `CDataSaveExtraAttack` is entry7 and is never substituted.
The physical coin pool has`0x840` records of stride`0x30` plus`0x800` trailing
bytes. Native reward and consume operations admit IDs0..399 and catalog type≤3.
Each coin has distinct counters at body-relative offsets0 earned,4 spent,8
current quantity, and an obtained/notification flag byte at12.

Reward function`0x1412F5D60` **unconditionally caps current quantity999** for
admitted coin IDs, separately caps cumulative earned99,999, and sets obtained
bit0. Consume function`0x1412F5CD0` floors current quantity0 and separately updates
spent history. Collection percentage function`0x14119CC90` counts earned>0,
rather than current quantity; changing quantity alone preserves that criterion.

The editor qualifies only records with both earned>0 and obtained bit0, IDs0..399.
It permits current quantity0..999, including exhausted owned records. It never
creates coins or changes earned/spent history, obtained/notification flags, DLC
ownership, rarity, growth maps or reward claims. All physical entries beyond399,
unqualified rows, unknown bits and trailing bytes remain unchanged. Native coin
names and rarity tables reside in external fixed-data assets that were not
attached; the searchable GUI truthfully labels **native coin IDs**, without
guessing character names or assigning rarity from quantity. The reviewed native
slot contains280 qualified records. Max preserves existing quantities above999
and Beli balances above999,999,999; returning to an original unusual value unstages.

The GUI exposes Resources and Owned coins, searchable native IDs, visible-record
Max, Undo, Review Changes, a read-only earned/spent/flag inspector, backups and
safe Save As. Source copies are never overwritten and changed-source snapshots
are rejected. Restores validate the exact bounded bytes being restored.

### Coverage checklist

| System | Current implementation or exact blocker |
| --- | --- |
| Spendable Beli | Implemented0..999,999,999; existing higher values preserved by Max. |
| Lifetime Beli/rewards | Read-only native mapped counter; achievements/reward thresholds remain unqualified. |
| Coin inventory | Existing obtained records' quantity0..999; read-only earned/spent/flags. Coin acquisition, exact display names, rarity/catalog types and DLC IDs need external fixed-data assets or controlled display-correlated copies. |
| Character unlocks/DLC | Missing controlled unlock pair and DLC entitlement/save relationship; no unlock action. |
| Beginning/character Growth Maps | Node states, costs and dependent stat/skill rewards require fixed-data node catalogs and controlled node-purchase copies. |
| Stats/skills | Growth-map stats may be derived; writable base values and unlock/equipment dependency layout unqualified. |
| Equipped skills/specials | Extra-attack class identified; valid ability IDs, unlock state, capacity and equipped references unmapped. |
| Soul Maps/Soul ranks | Runtime state clues are distinct from ordinary Growth Maps; absent disk/display correlation and supported revision conversion. |
| Costumes | Asset model names do not prove save ownership, equipped state or entitlement. |
| Dramatic/Free/Treasure Log | Stage IDs, rank/reward flags and result dependencies lack displayed/native correlation. Story completion stays separate from resources. |
| DLC adventures/challenges | Matching DLC/revision native copies and controlled result/reward pairs missing. |
| Gallery/movies/music/records | Coin collection criterion mapped but individual unlock bits and record/reward dependencies unqualified. |
| Weapons/fusion/mounts | Not established as PW4 save mechanics; no invented controls. |

Public sources consulted: [Glubus/oppw4-sdk](https://github.com/Glubus/oppw4-sdk)
commit`ed00f9fa0dae4ac561106c9e0d93cd2bcc44be88` and
[Glubus/oppw4-data](https://github.com/Glubus/oppw4-data)
commit`9b544c4c961db6985f5a5079c9b97aef24a1cb10`. The SDK has no located license;
no source or asset data was copied. These are runtime/asset research rather than
a disk-save editor. Documented Beli/reward function identities were independently
checked against the attached executable; several older RVAs do not describe it.

## Warriors: Abyss

The previously missing original-owner context has now been supplied with genuine
`GAMEDATA00.BIN` and `SYSTEMDATA.BIN` copies. Both decrypt and roundtrip byte
exactly. The game slot is revision`0xA4`; the system category is revision`0x77`,
which is distinct and cannot be opened by the game editor. The original standard
`steam_autocloud.vdf` supplies the private individual Steam account context.

Complete static inspection identified the seven-controller registry, bounded
A4 disk extent`0x26FE0`, owner-dependent AES-CBC framing, absence of a native
body checksum/MAC, and the Karma Embers balance at payloadoffset6. Native reward,
purchase and UI code independently agree with the official9,999,999 cap. The
editor keeps all other original plaintext, opaque native capacity and original
owner context unchanged. Its recruitment inspector reads the native flag records
without admitting linked-record ownership writes or guessing catalog names.

See [ABYSS_PC_FORMAT.md](ABYSS_PC_FORMAT.md) for the exact source geometry,
wallet proof, safe-storage/owner guards, tested features and full mechanics
checklist. Remaining inputs are controlled mechanic-specific copies and matching
catalogs; the owner/cipher prerequisite is resolved. Attached executables were
never run, and no player files or identifiers are distributed.

## Verification

`tests/test_pw4_format.py` has10 passing tests with the private genuine PW4 copy:
unchanged roundtrip; targeted Beli/coin edits in memory; all native object checks;
malformed size/region/revision/metadata rejection; qualified ownership; history,
unknown bytes and higher values preserved; staging, review, backups, source-change
protection and restores. Procedural fixtures test preservation with distinctive
unknown bytes; they are explicitly not game-load evidence. The native test uses
`PW4_SAVE_COPY` and distributes no fixture. No edited save was loaded in game.

`tests/test_pw4_review.py` adds independent adversarial coverage for exhausted
coins, unknown flags/history, higher quantities, surgical coin integrity, exact
integer snapshot seeds and backup replacement races. The focused five tests pass, including a separate GUI workflow.
`tests/test_pw4_gui.py` covers searching native coin IDs, Apply, Review, Undo,
visible Max, read-only inspection, themes, backup and Save As with procedural
data. The combined native-format, GUI and independent review run under Xvfb passes
**16/16 tests**. Both GUI workflows use procedural data; the native fixture
validates format roundtrips and targeted in-memory edits. GUI validation is
separate from game-load validation.

The candidate codec suite now also checks capacity-bound systemrevision77,
strict originalVDF context, and both supplied native Abyss categories. Body
changes are not authenticated by CBC and remain outside the read-only candidate
API. The production editor's current native serialization has no body checksum;
its declared integrity kind is`none`, with size/owner/marker/revision/geometry
checks and surgical wallet preservation. Its dedicated native/GUI/storage
coverage is described in [ABYSS_PC_FORMAT.md](ABYSS_PC_FORMAT.md). Neither title
has actual edited-game-load validation.

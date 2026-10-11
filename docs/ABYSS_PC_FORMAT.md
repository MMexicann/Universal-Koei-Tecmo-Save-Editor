# Warriors: Abyss — Windows PC

The native revision-`0xA4` gameplay profile edits **Karma Embers**, with a
9,999,999 cap and preservation of higher opened values during Max. Its inspector
searches the native persistent recruitment flag records by ID and stored value.
Hero ownership, cumulative growth, weapons, run data and rewards remain unchanged.

Use a separate `GAMEDATA00.BIN`–`GAMEDATA99.BIN` copy with its **original
`steam_autocloud.vdf`** beside it. Keep that exact original sidecar beside the
edited destination and any restore destination. Select Save As to create a new
file. The system save is a separate category and is not opened by this editor.

## Native qualification and scope

The supplied genuine gameplay slot is `0x30000` bytes and revision `0xA4`; the
supplied genuine system file is `0x2800` bytes and revision `0x77`. Both decrypt
using their original Steam sidecar and re-encrypt unchanged byte for byte. They
were inspected privately. No attached executable was run, and no player file,
identifier, original download URL, extracted asset or analysis image is included
in the repository or release.

The game uses an outer ASCII marker `470558d4d8015d9f`, followed by AES-256-CBC
ciphertext. The native IV is `e1c1c49f9a3019341ea820f99fd09a83`. Decrypted bytes
begin with `a1423bc7d48e148b`; the following payload begins with a little-endian
four-byte revision. The game's unsigned 64-bit platform owner value is XORed with
`0xFABE9C015F6E379A`, formatted as unsigned decimal ASCII and NUL-padded to 32
bytes. The original VDF's individual account value is converted through the
standard individual Steam-ID encoding before use; raw account DWORDs do not
decrypt these native samples. No owner is guessed or reassigned.

The bounded shared owner helper requires an ordinary, separate, original VDF
with exactly the native root and sole account field. It rejects oversized,
ambiguous, linked or changed metadata. Sensitive values, sidecar bytes and private
source paths are hidden from document representations and never enter review or
backup JSON. Backup context stores hashes and the standard companion basename.
The original owner and source copy are checked again after backup and immediately
before saving; restoration requires the same original owner context. A private
self-test hook can preserve the original opaque VDF in its new local test folder.
The general application rule prohibiting arbitrary metadata writes is unchanged.

## Complete category geometry

The static save service at `0x14041AEB0` uses category-selected fixed capacities.
Registration at `0x1403F7CC0` reads seven 40-byte entries from `0x141139460`: six
game controllers and one system controller. The two controller arrays are
current/backup **runtime memory**, not duplicate serialized save replicas.
Controller virtual `+0x60` calls these gameplay serializers in order:

| Registry entry | Count | Serializer | Serialized bytes per record at A4 |
| --- | ---: | --- | ---: |
| Persistent base | 1 | `0x1403E62C0` | `0x21C6B` |
| Slot information | 1 | `0x1403EC200` | `0x333` |
| Hero record pool | 298 | `0x1403E5C00` | `0x39` |
| Current run | 1 | `0x1403E9130` | `0xC40` |
| Five-byte selection records | 20 | `0x1403E8F30` | 5 |
| Five-byte additional records | 64 | `0x1403EC0D0` | 5 |

The actual disk-size initialization at `0x1403F93C0` calls virtual `+0x48`, then
`0x140410250`, then the controller's virtual `+0x58`. These are distinct from
virtual `+0x18` memcpy callbacks and their in-memory strides. At A4 the callbacks
give:

```text
run     = 15 + 25*4 + 0x25 + 0xBA8 = 0xC40
history = run + 20*5 + 64*5 + 0x12A8 = 0x208C
base    = 21*0x53B + 999*15 + 10*history + 0x2E93 = 0x21C6B
profile = 31*14 + 0x181 = 0x333
extent  = 4 + base + profile + 298*0x39 + run + 20*5 + 64*5 = 0x26FE0
```

Source functions are `0x1403E8BC0`, `0x1403E5A10`, `0x1403EB310`,
`0x1404091E0`, `0x140412670` and `0x140411D90`. The complete serialized region
fits inside the `0x2FFE0` decrypted payload; remaining capacity stays opaque and
byte exact. The older system serializer `0x1403ED250` is separately investigated
through the read-only candidate API; it is never substituted for a game slot.

## Native integrity and surgical wallet proof

Complete static inspection of the category handlers, their current-A4 nested
serializers, load service `0x14041AAD0`, pre-save `0x1403F97B0`, and post-load
copy/migration callbacks found **no native body checksum or MAC** for this
profile. The primitives copy bytes and little-endian words directly. Pre-save
updates date/run metadata and then copies runtime backup arrays; these are not
hash operations. Current-A4 reading skips legacy revision migrations. The
slot-summary path `0x1403F8570` does not mirror the Karma balance.

Accordingly the adapter declares `INTEGRITY_KIND = 'none'`. It checks complete
capacity, both encryption markers, the original owner, exact A4 revision and
the bounded native category geometry. It does not invent a checksum or claim
that CBC authenticates arbitrary body corruption. Unmodified bytes, including
unknown values and padding, are preserved in plaintext; CBC necessarily changes
subsequent ciphertext blocks after an edit. Re-encoded copies are decrypted and
checked against the exact intended payload.

`0x1403F96E0` writes the four-byte revision. `0x1403E62C0` then serializes a
two-byte field, followed by `0x140409350` copying the little-endian balance from
base object `+0x1F738`. **Karma Embers is therefore payload offset 6, four bytes.**
Reward/conversion function `0x1403F3E40`, purchase function `0x1406699C0`, and
currency UI `0x140664750` independently use that same stored balance. Reward and
purchase code clamp it to `0x98967F`, or 9,999,999. The official
[Update 4 notes](https://www.koeitecmoamerica.com/warriors_abyss/us/update4.html)
independently identify the Karma Embers cap increase from 999,999 to 9,999,999.
The chosen A4 native code has the raised cap; older gameplay revisions are rejected.

Recruitment-query function `0x140340E60` reads base `+0x204C5` indexed within
`0x33D` entries. A4 serializes these bytes immediately after the balance and the
next opaque four-byte resource, at payload offset 14. The inspector preserves
and displays native IDs and flag bytes without inventing names or admitting
unused entries for editing. Native recruitment also updates linked hero/weapon
references through `0x1404133F0`, so a standalone flag-toggle action is unsafe.

## Mechanics coverage checklist

| System | Implemented feature or precise remaining blocker |
| --- | --- |
| Karma Embers | Manual 0..9,999,999, Max preserving higher opened values, original-value unstage, Undo/Review/backup/restore/Save As. Balance changes do not claim earned rewards. |
| Persistent recruitment | Searchable read-only native flag records. Matching fixed-data ID/name catalog, DLC membership, and a controlled recruitment pair are needed for complete linked-record ownership actions. |
| Cumulative leveling | Separate from run levels; official Update 4 raises the cap through First Completion Bonuses and adds speed effects above 500. Native hero words, reward-expanded capacity and investment costs need display-correlated level-allocation/reversal pairs and matching catalog tables. |
| Transcendence/Unique Weapons | Official effects and planners distinguish these from ordinary levels. Existing ownership, first-clear rewards, trait dependencies and DLC entitlements need separately correlated copies/catalogs; no arbitrary unlock. |
| Records of Sin | Official Updates 7/8 distinguish earned records, full-inventory conversion and immediate Karma conversion. Conversion code identifies the wallet, but record naming, selected-record state, rewards and ownership are not yet completely mapped; inventory edits remain blocked. |
| Hero stats, emblems, traits, summons, Unique Tactics | Planner totals derive from hero selection and prerequisites. Runtime math is not a demonstrated persistent stat field; requires the matching native catalogs and serialized/drawn correlation. |
| Party/formation and run progression | Current run and historical run serializers are located. Valid IDs, recruited references, reward claims and safe resume-state changes still need controlled copies. |
| Traversal, bosses, story and First Completion Bonuses | Native category geometry alone does not prove unlock requirements. Official boss/Traversal requirements and clear rewards stay separate from resource editing. |
| Sealing Ceremony/customization | Official Update 6 requires first Gouma defeat; bans apply to already unlocked content, and disabled level/weapon effects do not erase ownership. Need distinct ban/effect byte mappings and controlled toggles. |
| Treasure/consumables/collections | Persistence, valid item IDs, quantity semantics and reward dependencies need display-correlated native copies; run pickups are not assumed permanent inventory. |
| DLC heroes/costumes | Tutorial, first-results grants, availability and installed entitlement differ. Requires a matching build/catalog and entitlement-correlated exports; no owner or DLC conversion. |
| System settings | Genuine revision77 decryption and unchanged roundtrip demonstrated in read-only research. Individual setting semantics/revision write rules are not qualified for editing. |

The most useful next inputs are copied slots immediately before/after one named
recruitment, one cumulative-level purchase, one Records-of-Sin conversion, and
one named customization toggle, with the same original VDF and game build/DLC
description. The required encryption context is now available; these next copies
prove mechanics and dependencies rather than redoing the cipher investigation.

## Verification

`tests/test_abyss_pc.py` exercises genuine unchanged and targeted wallet edits,
preservation outside payload6..9, native-source GUI Apply/Review/Undo/Save As,
private copied-owner self-test, backup/restoration, live-folder rejection,
symlink/hardlink rejection, changed source/owner and owner mutation after backup,
unsupported system/revision/size/marker rejection, immutable snapshots, unknown
fields, ordinary bounds and unusual higher values. Procedural cases are labeled
as such. Optional genuine copies use `ABYSS_NATIVE_COPY_DIRECTORY` locally; no
owner identifier is supplied in command-line arguments or published fixtures.

The actual edited copy has **not** been loaded in the game. Static native proof,
byte-preservation tests and real Tk workflow checks are distinct from game-load
validation. See the shared Steam-owner tests and the read-only candidate tests
for strict sidecar parsing and both supplied native categories.

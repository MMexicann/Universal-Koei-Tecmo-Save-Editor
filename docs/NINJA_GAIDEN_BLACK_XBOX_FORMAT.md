# Ninja Gaiden Black — original Xbox SYSTEM.dat

This is a **source-qualified system-file editor** for original
Xbox title `5443000D`. It restores numeric save-slot order and provides searchable
inspection of thirty stored slot times. It preserves every time value, last cursor,
settings, unlocks and story file. It does not edit Karma, Yellow Essence, inventory,
weapons or story progression.

## Qualification and sources

The MIT-licensed [complete native system writer](https://github.com/760194962/NinjaGaidenBlack-Save-Manager/tree/41db2f29ae17dd25cba295dbc430ce6d03e8899a)
provides `ngb_system_dat.py` and `docs/system-dat-research.md`. Its `edit_order`
restores active count 30 and slot indices 0 through 29; the game skips absent
slots. `build_system_dat` performs the entire range-encode, original-residue
preservation, original-seed encryption and console HMAC write. Its verification
reparses the complete intended decoded data. No decoded-body checksum is omitted
from that full system writer. The source preserves the opaque 42-byte header.

The author's documented Xemu checks distinguish system data from story data:
changing slot 5's stored frames from 1,264,136 to 251 produced the expected load-list
time and normal loading/saving; deleting and reinserting slots confirmed list-order
maintenance; removing system data reset list times and order. The source documents
native system load, validation and order-rebuilding routines. These are **upstream
author game checks**, not game-load validation performed by this project.

No genuine owner-bound `system.dat` was acquired. This profile therefore sets
`sample_verified=False`, `published_format=True` and `game_load_verified=False`.
Procedural fixtures test the complete published writer and GUI; they are never
labelled genuine saves. A genuine author-modified **story** reference independently
corroborates the shared cipher, compressor and console signing; it does not supply
system-file gameplay qualification.

Additional independently checked format sources:

- [NinjaCrypt](https://github.com/feudalnate/NinjaCrypt/tree/e0a2a42735f3ffcb0e88c1d66998a126569e2d67),
  Unlicense: both native file sizes, MT/Blowfish and non-roamable title signing.
- [Xbox EEPROM research](https://github.com/Ryzee119/xbox_eeprom/tree/a3bbedfd5f49f9508e6fd29b51c34a545a098b8e),
  GPL-2.0-or-later: mathematical SHA1 intermediate states, RC4 and protected layout.
  No foreign implementation was incorporated.
- [Original Xbox New Game Plus reference](https://github.com/real-guilty/NGB-New-Game-Plus/tree/3c9979a0e7468ca558d25d22b97f52bc2b0650e3):
  genuine author-modified `save000.dat`, slot metadata and matching console EEPROM.
  Original files and identifiers remain private. This is not a controlled pair.

All implementation is original Python. Blowfish constants were generated from the
mathematical hexadecimal digits of pi. Standard Blowfish/RC4 known answers and
true reconstruction of the genuine story ciphertext corroborate the implementation.
No game, editor binary or downloaded implementation was executed.

## Exact native system format

The system file is exactly `0x550` (1,360) bytes: HMAC-SHA1 at bytes 0–19,
little-endian original seed at bytes 20–23, and `0x538` bytes of encrypted capacity.
The complete seed/cipher region participates in the console-bound HMAC. The title
key is derived with Xbox's signing algorithm; its inner HMAC is HMACed with the
original console HD key. The copied EEPROM's protected SHA1/RC4 section must
validate uniquely before extracting that private key. Owners are never converted.

MT19937 uses title-specific tempering masks **before** shifts. Fourteen outputs
form a 56-byte Blowfish key; following outputs XOR little-endian data words.
Blowfish word pairs are also little-endian. Decryption reverses the native order.
The implementation supports only the two separately documented story/system
capacities; it does not accept arbitrary sizes or another Ninja Gaiden edition.

The bounded carryless range-coded payload is exactly `0x532` bytes: a 42-byte
header beginning with `94458ED28A4F` and containing `TeamNINJA 2003`, followed by
an `0x508`-byte system structure. Original physical residual bytes remain opaque,
including the six-byte marker at the end. Tables, intervals, EOF, decoded lengths
and compressed capacity are checked. Writes preserve the original seed and all
residual bytes after the new stream. Existing frequencies are reused where possible;
otherwise the author's game-accepted scaling rule builds a full frequency table.
Unchanged serialization returns the original native bytes exactly.

| Structure offset | Native field | Scope |
| --- | --- | --- |
| `0x000` | u32 total milliseconds | Preserved |
| `0x004` | u32[30] per-slot gameplay frames | Searchable inspection; preserved |
| `0x07C` | u32 magic `0x20030730` | Required identity |
| `0x1C6` | u8 active order count | Set to 30 only by numeric-order action |
| `0x1C7` | u8[30] slot-index order | Restore indices 0–29 only |
| `0x1E5` | u8 last cursor | Preserved, including unusual values |

Existing active order entries must be distinct and in 0–29, with count at most 30.
Unknown unused tail bytes are accepted and preserved on no-op; the explicit order
restoration replaces exactly count plus the thirty-byte table. All other decoded
bytes remain identical. The field has named choices, supports Undo and Review
Changes, and is excluded from Max. No arbitrary order-count or frame editing is
exposed.

## Copies, console context and storage

Place a copied system `.dat` and exactly one original `eeprom.bin` or
`factory_eeprom.bin` together outside live console directories. Preserve the same
original companion basename and bytes beside an edited destination. `SaveMeta.xbx`
is unrelated story metadata and is neither required nor interpreted for this
system file. Reimport the edited system copy as `system.dat` with the console save
manager. Never share EEPROMs or console keys in issues or release assets.

Live `UDATA/5443000D` and `TDATA/5443000D`, resolved aliases, hardlinks, changed
source/companions and existing destinations are rejected. Atomic new-copy writes,
automatic raw backups, source/context race rechecks and exact native-signature
restore checks apply. Backup bindings contain bounded hashes and an EEPROM
basename, never keys, raw metadata or personal paths. Object representations and
errors omit private raw data. Local CLI self-tests can copy original opaque context
only into a private output bundle, without creating or changing a console identity.

## Validation and remaining mechanics

`tests/test_ninja_gaiden_black_xbox.py` covers published-format procedural
cipher/range reconstruction, surgical order restoration, exact unknown/time/cursor
preservation, malformed inputs and context, Max exclusion, named choices, source
aliases/races, backups/restore and a real Tk open/stage/Undo/Review/Save As workflow.
`NGB_XBOX_NATIVE_DIRECTORY` optionally supplies a genuine **story** crypto reference;
`NGB_XBOX_SYSTEM_DIRECTORY` optionally supplies genuine system qualification, which
is currently skipped because that input has not been acquired. Edited game loading
has not been performed by this project.

| Mechanic | Status and specific remaining gate |
| --- | --- |
| Numeric load-list order | Source-qualified complete writer; no story/time mutation |
| Thirty-slot frames and list position | Searchable read-only inspection |
| Frame synchronization | Needs original matching story-slot context and coordinated mirror proof; current source explains game loading `max(story, system)` |
| Story Karma score | Source-backed field and genuine envelope decoding, but full decoded-story integrity is unresolved; unregistered read-only research |
| Yellow Essence, inventory and weapon upgrades | Need disk-specific records, ownership/equipped references and full story integrity |
| HP/Ninpo and permanent growth | Need persistent current/max/base distinctions and reward dependencies |
| Scarabs, costumes, difficulties and collections | Need exact ownership, completion and claimed-reward mappings; no generic unlock writes |
| Genuine system qualification | Requires original 1,360-byte system.dat and its original matching private EEPROM |

The read-only story inspector lives in
`src/koei_editor/research/ninja_gaiden_black_xbox`. Runtime trainer checksum arrays
are documented separately from serialized integrity; trainer addresses are not
transplanted into disk fields. Passing story envelope or candidate surgical-byte
tests does not establish an accepted gameplay writer.

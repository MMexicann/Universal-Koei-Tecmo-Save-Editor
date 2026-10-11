# Dead or Alive 5 — original PS3 US/EU PSN exports

The adapter targets the original **Dead or Alive 5** PlayStation 3 PSN system
save, with exact metadata identities `NPUB30893SYSTEM_SAVE` and
`NPEB01129SYSTEM_SAVE`. Ultimate, Last Round, PC, PS4 and Vita are separate
editions/platforms and are rejected. A matching PS3-decrypted native
`SAVE_SYS.DAT` and its unchanged original `PARAM.SFO` are required. PS3 PFD
extraction, reimport, encryption and resigning remain external to this editor.

## Implemented controls

The editor exposes **63 individually qualified original costume flags**, with
searchable numbered costume-flag records. Only a source-backed originally
locked byte can change from 0 to 1. An already unlocked value cannot be relocked;
unknown/nonbinary existing states are preserved and excluded from writable
controls. Max is disabled. An opened original value unstages a pending edit.

Costume names and serialized character identities remain unproved, so the GUI
uses explicit numbered flag records and native offsets. No inferred character
grouping or costume numbering is presented. Character ownership, paid DLC entitlements,
combined character/title patches, story clear states, challenge records,
records/statistics and unknown flag bytes are not edited. The [original-game unlock guide](https://www.freestepdodge.com/threads/unlockables-thread-questions-answers.1316/)
separates ordinary costumes earned from unique Arcade/Time Attack/Survival
completion, two Kasumi costumes earned through story, character unlocks,
Lab-stage unlocking and system voices earned through Command Training. Pai and
Alpha-152 have title-count unlock prerequisites (100 and 300 respectively).
These completion records, title counts and character ownership are preserved.
Normal costume unlocking, character unlocking and DLC ownership are distinct systems; these
controls do not create or install paid content. Story completion remains
separate from cosmetic controls.

Backups, Undo, Review Changes, searchable inspection, atomic Save As and restore
use the shared scalar/storage contracts. The original file remains immutable.
Save and restore require the exact original metadata digest at the destination;
metadata changes, wrong titles, damaged native bodies and changed sources reject
before gameplay writes. Backup context sidecars contain only an opaque digest.
The copied-save self-test generates a minimal public title identity, without
copying console/account/signing fields.

## Native framing, cipher and integrity

The qualified native file is exactly 43,068 bytes. It contains two big-endian
blocks, each with a 16-byte header: magic, complete block length, encrypted-body
byte sum and seed. The original profile has magic zero in both blocks.

| Offset | Complete block length | Body length |
| --- | ---: | ---: |
| `0x0000` | `0x1548` | `0x1538` |
| `0x1548` | `0x92F4` | `0x92E4` |

Each body is transformed as big-endian 32-bit words XORed with its evolving
seed. The state advances with `((state << 4) + (state >> 4)) & 0xFFFFFFFF` after
each word. Each stored integrity word equals the additive unsigned byte sum of
that block's **encrypted** body. Both sums must pass before decryption. The
first decoded 16 body bytes must match the independently observed original
revision fingerprint `00060100000100000008646464000000`.

These native sums do not authenticate the seed header words. The first seed also
has the decoded revision gate; no additional integrity word covering the second
seed was proved. Writes preserve both original seeds and all opaque headers.
PS3 PFD authentication supplies a separate console-container layer externally.

Unchanged serialization is byte-exact. A costume write changes its one encrypted
body byte and, where required, the first block's checksum. The second encrypted
block, original seeds and unrelated decoded bytes remain identical. The writer
recomputes native sums and reparses its output; malformed input is not repaired.

## Sources and independent qualification

- [Bucanero's DOA5 save decrypter](https://github.com/bucanero/save-decrypters/tree/master/doa5-decrypter)
  documents PS3/PS4/Vita native cipher and block-checksum facts, based on
  alfizari's earlier script. The project is GPL-3.0. Only mathematical/format
  facts were independently implemented; no foreign implementation, binary or
  player fixture is incorporated or redistributed.
- Apollo's original-title
  [US patch definition](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPUB30893.savepatch)
  and [EU definition](https://github.com/bucanero/apollo-patches/blob/main/PS3/NPEB01129.savepatch)
  supply explicitly labelled costume byte targets, with native decryption and
  encryption required around the patch. Only positive value-1 bytes in the
  narrow original costume patch were factually transcribed. Value-0 writes,
  the unexplained value-`0x10` target at `0x3E0`, combined `Unlock Everything`,
  broad title sweeps and Ultimate patches are deliberately excluded.
- Independently reacquired complete public original-title
  [US](https://github.com/bucanero/apollo-saves/tree/master/PS3/NPUB30893),
  [EU](https://github.com/bucanero/apollo-saves/tree/master/PS3/NPEB01129) and
  [Japanese](https://github.com/bucanero/apollo-saves/tree/master/PS3/NPJB00242)
  console exports were extracted and decrypted privately. Native sums and exact
  no-edit roundtrips pass on all three. The US decrypted/encrypted native pair
  also matches the upstream PS3 reference pair byte-for-byte. The Japanese
  metadata/profile is not accepted for gameplay writing without its own mapped
  patch provenance. These public saves and owner context are not shipped.

The public upstream encrypted/decrypted pair is labelled a reference, separately
from the independently downloaded complete console exports. The EU/Japanese
native bodies match each other, while the US body differs; this is two distinct
native copies, not three independent player histories.

## Mechanic coverage and exact remaining inputs

| Mechanic | State and precise remaining evidence |
| --- | --- |
| Original source-backed costume flags | Implemented 63 positive byte targets, binary 0-to-1 only, preserving original nonbinary states. Need independently labelled original costume unlock/equip pairs to add names or further flags. |
| Character unlocks and character identities | No writes. Need exact original serialized character IDs, individual Gen Fu/Alpha-152/Pai unlock pairs and ownership/reward dependencies. A repeated 11-byte pattern is not enough to establish ownership. |
| Other original costumes | No guessed fills or arbitrary ownership creation. Need labelled unlock pairs, original costume counts and exact native flag meanings; unexplained `0x10` values need independent interpretation. |
| DLC and later editions | Separate title/revision/platform qualification, installed-content and entitlement context. Original costume flags never manufacture paid content. |
| Titles and records | Read-only preservation. Published 99/299/300 title patches sweep hundreds of bytes and do not independently identify per-title states or reward dependencies. Need named record maps and controlled unlock pairs. |
| Story, timeline and character chapters | Preserved, no completion action. Need clear/reward/prerequisite transitions before any story feature; source cheat values alone are not a safe dependency model. |
| Difficulty unlocks, system voices and challenges | Preserved. Need individual title-native field maps, natural unlock rules and controlled completion/reward pairs. |
| Currency, growth and equipment stats | No currency, RPG level/EXP or weapon system is invented for this fighting-game profile. Any future system must be established from actual game mechanics and native storage. |
| PS3 disc original, Japanese, Ultimate, Last Round, PC, PS4, Vita | Not advertised by this adapter. Each requires title/edition-labelled genuine exports, its own complete framing/integrity and source-backed field facts. |
| Edited game loading | Not performed. Reimport/resign and actual edited load/re-save remain separate from the native byte/checksum and GUI tests. |

## Validation

The focused suite covers exact native no-op, both block sums, bad/truncated/
foreign layouts, upstream reference matching, independently acquired native
copies, each of the 63 individual field writes, preserved unrelated bytes,
unstage, invalid values, no relock, unknown states, immutable snapshots, foreign
metadata, same-title changed metadata, source protection, backup/restore and
actual Tk Open/Search/Undo/Review Changes/Save As.

The independently shared saves already have all source-backed costume bytes at
1. Native tests therefore preserve those genuine states and reject relocking;
per-field writes on explicitly labelled **constructed derivatives** check that
restoring one locked byte reproduces the exact original native output. Such
constructed derivatives and procedural fixtures are not claimed as game-made
locked samples or edited in-game validation. Optional private native checks use
`DOA5_PS3_NATIVE_DIR`; no native player bytes appear in public tests.

The scalar self-test qualification flag remains false to distinguish constructed
unlock transitions from genuine game-made locked-to-unlocked pairs; native
format/no-edit qualification is documented separately above.

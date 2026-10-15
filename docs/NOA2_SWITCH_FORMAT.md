# Nights of Azure 2: Bride of the New Moon — original Nintendo Switch

The `nights_azure2_switch` editor reduces existing **Libra**, the shop currency,
and synchronizes the native save-selection preview. It opens copied,
extensionless `SAVE_DATA_00`-style exports. The supported evidence is limited to
the observed **English Chapter 1, Chapter 7 and Clear Data profiles**, with exact
file sizes **77,509 or 91,828 bytes**. Other chapters, languages, revisions,
platforms, the original Nights of Azure and system files remain unqualified.

The qualified native outer block revision is `#USR` revision **1**. This is a
serialized block revision, **not** a claim about the installed Nintendo Switch
game update version.

## Sources and field meaning

The pinned public
[NX_Saves collection](https://github.com/Viren070/NX_Saves/tree/603dc50937246f08ed80670c1aa1d0c0607fa73d/nintendo/switch/savegames)
contains two original-title-labelled archives for Switch title
`0100628004BCE000`: a complete export and a separate modified early-game export.
They supply three distinct gameplay states and their system companions. The
archive labels say `[ESP]`; the native chapter/resource preview text in the
examined gameplay files is English. Separate independent publishers have not
been established. The modified early state does not establish natural resource
limits. Player files, metadata, external archive contents and extracted assets
are not included in the repository or downloads.

The game's official
[English manual](https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/636570/manuals/steam%28digital%29_noa-EN.pdf)
distinguishes Blood used for level growth from Libra used for purchases. These
are separate systems; the editor exposes only Libra.

Each examined native file contains an explicit `Libra: <number>` entry in its
save-selection preview. Across all three states, this number exactly matches
the little-endian unsigned 32-bit member at **current `#PLD` body + `0xAF`**.
The player block moves with preceding variable-length records, so the editor
locates it through bounded native frames instead of using a fixed file offset.
The labelled preview and its matching numeric member provide the field evidence;
runtime trainer addresses are not used as disk offsets.

Only reductions from the opened balance to zero are offered, with Max disabled.
Experimental mode cannot increase this field. Values above the qualified signed
32-bit working range are preserved without exposing a control. The writer does
not grant items, edit purchases or lifetime totals, or modify growth, rewards,
equipment, relationships, quests or ownership.

## Native framing and integrity

The fixed preview area precedes a `#USR` block at **`0x540`**. Every native block
has a twenty-byte little-endian header:

```text
signature[4], header_size, body_size, revision, checksum
```

The checksum is standard **32-bit unsigned-byte FNV-1a**, seed `0x811C9DC5` and
multiplier `0x01000193`, over precisely that block's body. High-bit bytes remain
unsigned. FAIRY TAIL's separately qualified signed-char checksum variant does
not match these files and is not reused.

The current root has these eleven ordered leaves:

| Signature | Native revision | Body extent |
| --- | --- | --- |
| `#EVD` | `0x20001` | 6,325 bytes |
| `#PRD` | `0x60001` | Bounded variable extent |
| `#QUD` | `0x10001` | Bounded variable extent |
| `#PLD` | `1` | 199 bytes |
| `#LID` | `0x10001` | Bounded variable extent |
| `#FAD` | `0x20001` | Bounded variable extent |
| `#IND` | `1` | Bounded variable extent |
| `#FID` | `0x30001` | 27,778 bytes |
| `#NFD` | `0x30001` | 1,047 bytes |
| `#CLD` | `1` | 383 bytes |
| `#EXD` | `1` | 198 bytes |

The Chapter 1 and Chapter 7 profiles additionally contain a final `#CHD`
revision-1 checkpoint, with its own complete eleven-leaf sequence and hashes.
That checkpoint remains unchanged. Unknown signatures, order, revisions,
extents, child boundaries and damaged active checksums are rejected, including
damaged inner leaves whose enclosing hashes have been recomputed.

The Clear Data profile has a shorter current root ending at **`0xA187`** and a
**50,477-byte retained inactive tail**. Its stale bytes, including an older
checkpoint, are preserved opaquely. They are outside the current root's integrity
coverage and are neither repaired nor resealed. This editor does not claim a
checksum covering every file byte. Across the three native gameplay states,
all **60 active root, leaf and checkpoint block checksums** validate.

An edit changes only the current Libra word, its visible preview, the current
`#PLD` hash and the enclosing current `#USR` hash. Preview updates retain the
fixed allocation, all bytes after the new terminator, and all bytes after the
original terminator. Chapter checkpoints, unused header bytes, other fields and
inactive tail bytes stay identical. Unchanged serialization returns the exact
original file. Every edited result is reparsed and checked against its requested
Libra value before a copy is accepted.

## Copy workflow

1. Export the original Switch save using your save manager and keep a backup.
2. Copy an extracted `SAVE_DATA_00`-style gameplay file to a separate working
   folder. Select the explicit Nights of Azure 2 **Nintendo Switch** editor.
3. Review the native preview, stage a Libra reduction and use Review Changes or
   Undo as needed.
4. Use Save As to create a new extensionless destination. Automatic backups,
   source-change checks and restoration use the shared application workflow.
5. Reimport the edited gameplay copy with your Switch save manager, preserving
   the destination slot's expected filename and export structure.

The editor handles copied gameplay bytes. Console extraction and reimport remain
with the save manager. No account or entitlement fields are created or edited.

## Validation and remaining scope

[`test_nights_azure2_switch.py`](../tests/test_nights_azure2_switch.py) covers
unsigned checksum known answers, exact profiles, nested corruption, wrong
revisions, preview/scalar disagreement, hard reduction limits in normal and
experimental modes, unusual opened values, immutable snapshots, surgical
preservation, staged Undo and Review Changes, backup/restore, new destinations
and source changes after backup. Procedural fixtures are deliberately
nonplayable and remain separate from native evidence.

Optional `NOA2_SWITCH_NATIVE_DIR` supplies the three separately copied native
gameplay states for unchanged roundtrips, individual reductions and copied-file
Save As/backup/restore tests. The actual Tk workflow covers native opening,
inspection/search, edit, Undo, Review Changes, themes, Save As and restore.
All fourteen focused tests passed with those native copies and a display.
An additional independent native audit checked active hashes, malformed nested
frames and byte preservation. **Edited saves have not been loaded or re-saved
in the actual game.**

| System | Current scope or missing qualification |
| --- | --- |
| Libra | Existing current-wallet reductions and synchronized preview |
| Blood, levels, Ability Points and Servan Points | Preview inspection only; growth, unlock and reward transitions need separate native evidence |
| Items and strengthening | Preserved; require item/instance identities, ordinary ownership, equipment references and controlled purchase/fusion pairs |
| Lilies and Servans | Preserved; friendship, recruitment, reincarnation and chapter prerequisites remain unmapped |
| Story, quests, chapter restart and clear rewards | Preserved; no checkpoint replacement, new-game initialization or reward grants |
| Other chapters, native sizes and languages | Need complete original exports and exact preview/schema qualification before widening acceptance |
| Other platforms and installed update versions | Need their own native inputs and format evidence; related engine framing does not establish compatibility |

The adapter is an independent Python implementation of the observed format and
standard hash algorithm. No external gameplay implementation, restricted item
catalog, player export or game binary has been copied into public source.

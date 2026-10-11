# Legend of Liu Bei — Traditional Chinese DOS

The `reko3_dos` adapter independently implements original 8,789-byte `.R3S`
slots for **Romance of the Three Kingdoms: Legend of Liu Bei / Sangokushi
Eiketsuden / 三國志英傑傳**. Other languages, Windows revisions and console ports
are not inferred from this profile.

## Evidence and complete native writer

The [browser editor](https://github.com/appendixisu/reko3-save-editor) contains
a complete binary reader and raw writer plus an original prologue slot reference
in `src/core/sample.ts`. Its implementation, catalogs, artwork and native sample
were not incorporated. Its source has no explicit reuse licence; only separately
verified format facts guide this original implementation.

The [independent format guide](https://www.1man.info/2020/04/blog-post.html)
corroborates the first three records, allied faction byte and class/item meaning.
It explains that class-change items require distinct classes and levels and that
items also affect troops, morale and equipment. Those systems remain read only.

The external README's count of **387** is wrong for its own reference: the
source array and native file have **384** consecutive 18-byte character records
beginning at `0x695`, ending at `0x2195`. Bytes from there to EOF belong to
other data and are preserved. No private save, owner context or game binary is
distributed. No game executable was run.

The complete native writer is a raw file write, with no encryption or checksum
transformation. This adapter changes only selected field bytes and preserves
every header, other record, opaque byte and tail byte. No-edit serialization is
byte exact. Changed output is structurally reparsed before guarded Save As.

## Controls and mechanics checklist

| System | Implemented scope or specific remaining proof |
| --- | --- |
| Existing allied current troops | Reduce the little-endian 16-bit count at record `+5` to `1..opened`; no elimination, refill or capacity inference. |
| Existing allied within-level EXP | Manual byte at `+9`, `0..99`; level byte at `+8` stays intact. No level-up, EXP-total or story action. |
| Record qualification | Existing faction `0x80`, ordinary occupied shape byte `+4=100`, class `0..18`, level `1..99`; unfamiliar records are inspection only. |
| Max | Disabled for both fields; unusual opened values are preserved and can be unstaged. |
| Characters and inventory | Search 384 records, including faction, current troops, class, level, EXP and eight native item IDs. Three independently corroborated protagonists are named; remaining IDs stay explicit. |
| Level/stat growth and troop refills | Need native maximum-troop formula, morale/current-turn mirrors and controlled level-up/healing pairs. |
| Promotion, allegiance and recruits | Need class/item prerequisites, campaign ownership and promotion/recruitment action pairs. No army transfer or class writer. |
| Items and equipment | Need acquisition/equipment/consumption rules, unique-item ownership and complete independent catalogs. No item creation, removal or replacement. |
| Money, battles and story | No qualified writable maps; need controlled spend and battle/route/reward pairs. Story stays separate from resources. |

Qualification requires the exact native length, a valid Traditional Chinese
chapter label, original protagonist faction and all 384 faction-record boundaries.
An unfamiliar shape, class or level never creates editable fields. Unknown
record bytes are not normalized.

## Validation and use

Open a separate original `MSAVE0.R3S`–`MSAVE4.R3S` copy outside the game folder.
Save As creates a new copy with automatic backup; Undo, Review Changes and
backup restore use the shared workspace. Restore verifies the exact bounded
backup bytes and rejects existing destinations or damaged/foreign input.

Procedural tests cover every editable field, untouched tail, unknown/higher
values, invalid input and edits, frozen snapshots, races, backups and restore.
`REKO3_DOS_NATIVE_COPY` selects the privately held original upstream reference
for the same full-byte checks and actual Tk editing/saving/restore workflow.
This is an upstream native reference, not a controlled in-game action pair.
Edited game-load/re-save validation has not been performed.

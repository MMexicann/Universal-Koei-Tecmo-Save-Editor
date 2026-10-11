# Atelier Totori — original PlayStation 3 US/EU

The adapter opens a separate decrypted `USR-DATA` exported as a `.bin` copy,
with its unchanged original `PARAM.SFO` beside it. It supports `BLUS30735` and
`BLES01221`. Reduce the existing spendable Cole balance and search named
character levels/EXP and complete serialized-system records. Max does not change
Cole. Reimport the edited decrypted file and rebuild console authentication with
Apollo; the application does not decrypt, encrypt or resign a PS3 archive.

## Field and complete writer proof

[The original US title patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30735.savepatch)
and its BLES01221 counterpart explicitly write the single BE32 Cole word at
`0x9554`. The patch's 9,999,999 target is not treated as a natural cap. Only
reductions from the opened value are admitted, including preserving an unusual
original word unchanged. No other gameplay bytes are modified.

The full title patch set must be considered together with Apollo's actual writer,
not interpreted as a game-native serializer. Pinned
[Apollo PS3 source d7e4d6e](https://github.com/bucanero/apollo-ps3/blob/d7e4d6ee69464db7958acb771c8ecf5de4502358/source/exec_cmd.c#L1211)
loads and decrypts the complete protected file, applies the selected title-specific
code, writes/encrypts it and invokes `PFD_CMD_UPDATE` in `patch_save` (1295–1323).
Its edited-file import path `encryptSaveFile` (1512–1547) also rebuilds PFD
authentication. Pinned
[Apollo library 864dfd86](https://github.com/bucanero/apollo-lib/blob/864dfd86c34acaf7e9a01eb3c55302b301e5cea3/source/patches.c#L4495)
reads the complete buffer, interprets the direct four-byte write and saves the
complete original-sized buffer. There is no separate hidden Totori checksum pass
in this published path. This establishes the bounded published Cole writer;
it does not establish an original game serializer or a global absence of checks.
Integrity is reported as **external**, rather than internally verified.

## Native profile

Four freely shared complete native exports independently qualify the format:
[GameFAQs US exports](https://gamefaqs.gamespot.com/ps3/991771-atelier-totori-the-adventurer-of-arland/saves)
22454, 22468 and 22816, plus a
[public EU completed-game export](https://www.savegameworld.com/ps3-atelier-totori-the-adventurer-of-arland-savegame/).
They were decrypted privately for qualification; no saves or metadata are shipped.

Each file is exactly 270,336 bytes. The 32-byte preamble is `0132b533` followed
by 28 zero bytes. From offset 32, sequential BE32 tag/BE32 body-length headers
frame tags 1–22, with these exact body sizes:

```text
33264,4908,4,3972,130956,51,57164,4,5632,1,20,
68,932,1314,8,4536,400,1812,14325,168,88,64
```

Tag 3 contains only Cole at `0x9554`. Tag 4 contains ten ordered character records
at `0x9560`, stride 396, followed by 12 preserved bytes. IDs 0–9 and their
published named level/EXP words are inspection only; Ceci, Iksel and Cordelia
are included as stored records without claiming all records are playable.
At `0x3F73B`, the terminal tag is 1024 and its declared length 10,437 includes
its eight-byte header and consumes the exact remainder. All terminal bytes are
retained. The complete order, lengths, identities and terminal frame are checked
before offering a field; foreign formats, incomplete exports and malformed
frames are rejected.

Whole original `PARAM.SFO` hashes bind opening, source-change checks, Save As,
backup restore and copied-save diagnostics. Only title-directory identity is
interpreted; account/signing values are never displayed or written into backup
manifests. Destinations require the same unchanged metadata. Saves are written
atomically to new paths and automatic backups retain exact original bytes.

## Mechanics and coverage

| System | Implemented or precise blocker |
| --- | --- |
| Spendable Cole | Individual reductions, preserving all other words; no Max or invented natural ceiling. |
| Character level/EXP | Named read-only records; level/EXP and multiple base/current/bonus stat copies require controlled growth/action pairs before writes. |
| Friendship/events | Read-only; request/event thresholds and endings cannot be inferred from a relationship cheat target. |
| Inventory, quality, traits/effects, equipment | Full native item section preserved; needs exact PS3 record-type, occupied-item, quality and equipped-reference writer qualification. PS4/Vita layouts are not transplanted. |
| Alchemy, recipes, adventurer rank/points, exploration | Preserved; point totals, rank rewards and prerequisite/claim flags need explicit native dependencies. |
| Calendar, time limit, story, endings, NG+ | Preserved; no date reset, automatic completion or reward unlock actions. |

The focused suite exercises seven genuine exports across the two original
Arland PS3 adapters, exact no-op/surgical edits, foreign-region/frame rejection,
unusual values, immutable snapshots, changed sources/metadata, guarded backups,
restore and real Tk Open/Edit/Undo/Review/Inspect/Save As/Restore workflows.
Procedural fixtures are distinguished from genuine files. **Edited in-game
load/re-save validation has not been performed.** Meruru Plus/Vita and DX PC
remain separate profiles; this original PS3 editor does not add PC support.

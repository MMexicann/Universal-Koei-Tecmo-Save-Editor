# Atelier Rorona — original PlayStation 3 US

Open a separate decrypted `USR-DATA` `.bin` export copy with unchanged original
`PARAM.SFO` beside it. The exact title is **BLUS30465**, the original 2009/2010
Rorona; **Rorona Plus, New Rorona and DX PC are separate unsupported profiles**.
Reduce existing spendable Cole and search named character raw records and
complete serialized systems. Max does not change Cole. Reimport and resign with
Apollo; this adapter does not perform PS3 archive encryption/PFD authentication.

## Exact native source and writer qualification

The original title-specific
[BLUS30465 patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/BLUS30465.savepatch)
explicitly writes one BE32 money word at `0x15453`. Its published 9,999,999 target
is not treated as a natural cap; only reductions from the opened balance are
admitted. The entire title patch set was reviewed, including its incompatible
normal-stat versus trophy-stat sections; those codes do not grant character,
relationship, trophy or progression write access.

The complete original Apollo pipeline is pinned
[Apollo PS3 d7e4d6e](https://github.com/bucanero/apollo-ps3/blob/d7e4d6ee69464db7958acb771c8ecf5de4502358/source/exec_cmd.c#L1211):
`apply_cheat_patches` decrypts complete protected USR-DATA, applies the selected
literal title code and encrypts the complete file. `patch_save` (1295–1323) then
runs `PFD_CMD_UPDATE`; edited-file `encryptSaveFile` (1512–1547) also updates PFD.
[Apollo library 864dfd86](https://github.com/bucanero/apollo-lib/blob/864dfd86c34acaf7e9a01eb3c55302b301e5cea3/source/patches.c#L4495)
reads the complete buffer, applies a direct four-byte write and saves the full
original-sized buffer. The full literal Rorona title patch set and generic
writer do not contain a hidden Rorona checksum pass. This qualifies the bounded
published money writer; it does not prove the original game serializer or a
blanket absence of checks. Integrity is **external**, rather than internally
verified, and edited game-load testing is not claimed.

## Complete observed profile

Four native gameplay exports from
[GameFAQs](https://gamefaqs.gamespot.com/ps3/958853-atelier-rorona-the-alchemist-of-arland/saves)
qualify this profile: download 21486 and three independent gameplay directories
inside 23745. Each has its original title-bearing SFO and protected USR-DATA;
qualification privately decrypted complete files without executing game/editor
binaries. Download 30676 contains only system data and is excluded. No fixture,
metadata/account value or console key is shipped.

Every gameplay file is exactly 593,920 bytes. The 32-byte preamble is `01328e29`
plus 28 zero bytes; this differs from Totori/Meruru's preamble. Sequential BE32
tag/body-length frames 1–22 have these exact sizes:

```text
23620,16,15,4,4,44,57164,74,4772,8,1274,4,20,
1748,23808,4204,1,388116,107,5600,5128,4504
```

Tag **12**, rather than tag 3 in the other Arland editors, consists only of Cole
at `0x15453`. Tag **14** starts `0x1547B` and contains seven 248-byte ordered
identity records plus 12 preserved bytes. Source-named Rorona, Sterk, Cordelia,
Iksel, Gio, Tantris and Lionela first status-code addresses match record `+8`.
The patch does not explicitly identify that word as EXP; both record `+4` and
`+8` are displayed as raw words, without asserting a level/EXP map.
At offset 520,443, terminal tag1024 declares 73,477 bytes **including** its
eight-byte header, exactly consuming the remainder. All framing, unknown
records/values, array padding and terminal bytes remain unchanged during a Cole
edit. Strict native size/header/order/length/character identity and region guards
reject Plus/DX, other Arland titles, system saves and incomplete files.

Source/destination/backup/restore checks bind both the native save hash and the
whole original SFO hash. Only public save-directory title identity is interpreted;
opaque account/signing bytes remain private. Automatic original-byte backups,
Undo, Review Changes and atomic new-path saving are retained.

## Mechanics coverage

| System | Implemented or precise blocker |
| --- | --- |
| Spendable Cole | Individual reductions; unknown/higher opened values preserved, no inferred Max. |
| Seven character records | Named raw-word inspection; EXP identity, exact stat copies, growth thresholds and level/EXP coupling still require qualification. |
| Synthesis/quality/traits/equipment | Native item section preserved; exact original PS3 record types, ordinary identities, quality width and equipped/derived dependencies required before writes. |
| Alchemy/recipes/Hom helpers | Preserved; raw EXP/level patches do not prove recipe access, growth or Hom action dependencies. |
| Trust/friendship/events | Preserved; normal and trophy-oriented patch values differ. Need controlled event/reward action pairs and exact field semantics. |
| Assignments/stars/tickets/requests | Preserved; assignment score, period conditions and reward-claim prerequisites must remain separate. |
| Calendar/time limit/story/endings/NG+ | Preserved; no date reset, automatic story completion or ending/trophy unlock action. |

The shared Arland suite covers all eleven genuine exports across original
Rorona/Totori/Meruru, exact unchanged roundtrips and surgical Cole edits, complete
foreign/malformed/region rejection, unusual values, frozen snapshots,
source/SFO races, paired backup hashes, bounded restore and copied-save
diagnostics. Real native Tk workflows open, search, stage, Undo, Review Changes,
inspect, switch theme, Save As and restore each profile. Public generated cases
are procedural, not player saves. **Edited in-game load/re-save validation has
not been performed.** Other regions require independent native qualification.

# Atelier Meruru — original PlayStation 3 US

Open a separate decrypted `USR-DATA` `.bin` export copy and retain its original
`PARAM.SFO` beside it. The exact observed title is `BLUS30941`. Reduce existing
Cole and search the thirteen named character level/EXP records and complete
serialized systems. Max leaves Cole unchanged. Reimport and resign using Apollo;
PS3 archive encryption and PFD authentication remain external.

## Proof and native profile

[The title-specific original PS3 patch](https://github.com/bucanero/apollo-patches/blob/main/PS3/BLUS30941.savepatch)
explicitly maps Cole to the BE32 word at `0xCB58`. It is supported only as a
reduction from the opened balance; the published 9,999,999 target does not prove
a natural cap. Some published character EXP addresses are inconsistent with the
observed record stride, so those patches do not grant character write access.

The complete published external writer path is pinned
[Apollo PS3 d7e4d6e](https://github.com/bucanero/apollo-ps3/blob/d7e4d6ee69464db7958acb771c8ecf5de4502358/source/exec_cmd.c#L1211)
`apply_cheat_patches` (1211–1288), `patch_save` (1295–1323), and edited-file
`encryptSaveFile` (1512–1547), plus
[Apollo library 864dfd86](https://github.com/bucanero/apollo-lib/blob/864dfd86c34acaf7e9a01eb3c55302b301e5cea3/source/patches.c#L4495).
The pipeline decrypts complete USR-DATA, applies the direct title-specific code,
writes/encrypts the complete buffer and rebuilds PFD authentication. The full
Meruru title patch set and generic interpreter have no additional hidden
Meruru checksum operation. This qualifies the bounded published Cole edit path,
not the original game serializer or a global absence of internal checks.
Integrity is reported as **external**; no checksum verification is claimed.

Three complete public
[GameFAQs original PS3 exports](https://gamefaqs.gamespot.com/ps3/625209-atelier-meruru-the-apprentice-of-arland/saves)
22467, 22479 and 22480 independently qualify this native profile. Private
qualification decrypted them without executing any game/editor binary. No saves,
account metadata or console keys are distributed.

Each decrypted file is exactly 558,080 bytes. Its preamble is `0132b533` plus
28 zero bytes. Sequential BE32 tag/body-length frames 1–24 have exact body sizes:

```text
46120,5880,4,5628,179724,121,100768,4,6968,1,8,68,
592,1588,8,3584,95968,1469,84,384,77612,4800,104,80
```

Tag 3 consists of the unique Cole word. Tag 4 begins `0xCB64`, has thirteen
432-byte ordered identity records plus 12 preserved bytes. Only named levels
and EXP are displayed, with DLC records included without manufacturing ownership.
The terminal tag 1024 starts at 531,791 and declares 26,289 bytes including its
header, consuming the exact remainder. All unknown, history, array padding and
terminal bytes remain byte identical.

This is **not** Meruru Plus Vita or DX PC. The original PS3 item writer patch uses
a 48-byte stride, while Plus/PC research uses 52; matching total file sizes are
not compatibility proof. Whole original SFO hashes and exact region identity
bind read/source/destination/backup/restore. Automatic original-byte backups and
atomic new-file saving are retained; raw metadata/account values never enter
Review Changes or backup context manifests.

## Mechanics checklist

| System | Implemented or precise blocker |
| --- | --- |
| Cole | Conservative individual reductions; opened higher/unusual values preserved, no Max. |
| Characters | Named native level/EXP inspection; need exact growth curve, base/current/derived stat roles and validated PS3 writer before changes. |
| Quality/traits/effects, basket/container, gear | Preserved; the published quality cheat modifies a byte of a floating-point representation and is not an integer quality map. Exact PS3 item types, occupied identities, width and equipped dependencies remain required. |
| Friendship/character events | Preserved; dependencies and recruitment/event thresholds remain unqualified. |
| Alchemy/recipes | Preserved; a raw level patch does not qualify EXP/recipe/growth dependencies. |
| Development/population/facilities | Preserved; development points, population thresholds, building prerequisites and rewards require controlled native action pairs. |
| Calendar/story/endings/NG+ | Preserved, separate from resources; no time reset or story-completion actions. |

Focused checks cover all three native exports, surgical money reductions with all
other bytes preserved, unchanged roundtrips, exact foreign/malformed rejection,
metadata/source races, guarded backups/restore, copied-save diagnostic and real
native Tk workflows. Public procedural fixtures are separate. **Edited game-load
and re-save validation has not been performed.** Other regions require their own
native qualification and are rejected.

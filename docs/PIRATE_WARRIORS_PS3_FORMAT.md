# One Piece: Pirate Warriors 1 and 2 — exact PS3 export profiles

These are separate, narrow editors for the first two PlayStation 3 games.
The first accepts the original US PSN `NPUB30836-00` export; the second accepts
the original European PSN `NPEB01795-00` export. Open a **decrypted `DATA.BIN`
copy beside its unchanged original `PARAM.SFO`**. Reimport and resign edited
exports with Apollo before console use. PC, Vita, later games, other regions,
and other header layouts are not qualified by these adapters.

## Published writer and native profile evidence

The published [NPUB30836 field map](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPUB30836.savepatch)
provides individually named first-game character growth patches and warns
against combining its level and combat-stat recipes. The separate
[NPEB01795 map](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPEB01795.savepatch)
provides the sequel's Berry locations, character EXP, coin and unlock recipes.
The [Apollo patch engine](https://github.com/bucanero/apollo-lib/tree/864dfd86c34acaf7e9a01eb3c55302b301e5cea3) implements
those explicit big-endian scalar patch operations; these recipes contain no
native gameplay checksum operation. Original PS3 PFD encryption and
authentication are separate external operations.

Independently retained public exports are the
[first game's NPUB30836 archive](https://github.com/bucanero/apollo-saves/tree/c6fa97f2f4ef1b3469f0421c727997108821e188/PS3/NPUB30836)
and [second game's NPEB01795 archive](https://github.com/bucanero/apollo-saves/tree/c6fa97f2f4ef1b3469f0421c727997108821e188/PS3/NPEB01795).
They describe unlocked/maximized progress; they are **modified reference states**,
not unchanged controls or controlled gameplay action pairs. Their original
SFO/PFD exports were inspected and decrypted privately using published PS3
format facts. Player bytes, ownership context, downloads and upstream source
copies stay outside the checkout and public package. No game, trainer or editor
executable was run; upstream GPL-3 implementation and patch catalogues were not copied into these independently written adapters. The pinned snapshots above supply format facts and original private qualification inputs.

| Adapter | Exact decrypted size | Required first 16 bytes |
| --- | ---: | --- |
| `pw1_ps3` | `665,600` (`0xA2800`) | `000000000000000200005CAE00000000` |
| `pw2_ps3` | `768,000` (`0xBB800`) | `00000000000000020002CA7800000000` |

The native word at `0xC` is already zero in each acquired export and remains
zero. These profiles **reject any other value**, preserve all header bytes,
and never clear a checksum, disable an integrity flag, or silently repair input.
The observed header shape is not called a proved native revision discriminator.
Exact title selection on file reads comes from the original SFO directory plus
this separately observed size/header profile.

`INTEGRITY_KIND='external'` describes these complete published patch workflows.
It does **not** claim that gameplay integrity has independently been proved
absent or that arbitrary body corruption can be detected. No native checksum
algorithm is invented from another Koei game. Additional header variants,
active native checksum formats and other editions need their own complete
serializer/loader qualification before acceptance.

## First game: named level-growth value reductions

Thirteen source-named existing character slots have four-byte big-endian
level-growth values at `0x7C + index * 0x80`: Luffy, Zoro, Nami, Usopp, Sanji,
Chopper, Robin, Franky, Brook, Ace, Hancock, Jinbe and Whitebeard.
The published recipe calls these “Max Level” values. The editor labels them
**level-growth values**, because a published scalar patch does not establish
EXP thresholds, a numeric level encoding, or a natural gameplay cap.

The editor permits `0..the opened value` and disables every Max action. Its
range is a deliberate reduction boundary, not a claim that the source's
`1,000,000` target is a natural cap. Each field has a stable character identity
and scalar storage definition. Combat-stat recipes are excluded in accordance
with the source's combination warning. Coins, coin relationships, learned
skills, story progress and all other character bytes are preserved.

Independent displayed-value captures and edited game loading remain needed
before interpreting these words as a full experience/level system or expanding
combat-stat/growth dependencies. This narrow writer reproduces the individually
published storage operation; it does not grant additional progression rewards.

## Second game: primary Berry reductions

The primary published Berry word is big-endian `u32` at `0xA614`. The second
published Berry word at `0xA618` is read only. The acquired export contains
**different values in these two words**, so they are never treated as duplicate
wallets or automatically synchronized. The secondary word's lifetime/history
role is unresolved; its bytes survive every edit unchanged.

The editable primary value permits `0..the opened value`, with Max disabled.
The patch's `999,999,999` cheat target is not adopted as a natural cap. Character
EXP, level-limit breaks, stat words, skill slots, coins, shop ownership,
character selection, Nakama records and story progress are excluded. The
first game's `0x80` character geometry is never reused for the sequel.

## Storage, tests and validation distinctions

The bound scalar adapter checks the complete pending map, rejects wrong types
and foreign documents, preserves unusual typed opened values as exact no-ops,
and verifies both the complete requested payload and scalar read-back after
serialization. Each edit changes only its declared four-byte field. No-op
serialization returns the original bytes exactly.

File reads and saves bind the **complete original SFO digest**, preserving it
opaquely. Backup/restore records also bind the original SFO and save digest.
Save As validates unchanged input and context again before atomic creation of
a new destination; existing destinations and original copies cannot be replaced.
The source SFO is never synthesized or changed by the copied-save workflow.
Save As and Restore also reopen the actual written bytes and compare their
complete original context digest after writing. A same-title companion swap
during the final write or read-back fails verification; it cannot silently bind
the new copy to different export metadata. A postwrite verification failure is
reported without deleting a destination another process may have replaced.

[Focused tests](../tests/test_pirate_warriors_ps3.py) cover both shared scalar
contracts, all mapped values, targeted byte preservation, reduction boundaries,
malformed pending maps, unusual opened values, strict title/header/size gates,
immutable documents, context races, backups/restore, and source protection.
Fault-injection checks include same-title opaque companion changes during the
final atomic write and read-back, plus a restored body changed after creation.
Procedural fixtures are generated, not player saves. Optional privately held
`PW1_PS3_NATIVE_COPY` and `PW2_PS3_NATIVE_COPY` run genuine export no-ops,
all eligible field reductions and copied Save As/backup/restore checks.

Actual edited **console load and re-save have not been tested**. Native file
qualification, published writer evidence, procedural tests and console loading
are distinct validation stages. These editors make no broader gameplay,
checksum-absence, platform-conversion, entitlement or ownership claim.

# Origins: proficiency levels and Old Coins

**Neither requested edit is implemented in v2.5.1.** The existing qualified Steam
slot revisions 16, 17 and 29 retain their documented editing scope. Experimental
numeric mode does not enable unknown fields or bypass progression dependencies.
See [native format evidence](ORIGINS_FORMAT.md).

## Weapon proficiency levels

The earlier native executable analysis establishes subsystem 5 as fifty packed
14-byte records: a 32-bit XP member, four equipped Battle Art IDs and two other
bytes. Native gain routine RVA `0xab02d0` compares threshold-table levels and
calls `0xab6910`, affecting moveset records and level/rank-derived rewards.
Story and DLC gates also affect available progression. These facts do not yet
provide a complete editable disk mapping and transition implementation.

This matters in practice. The [WeMod author/user discussion](https://community.wemod.com/t/dynasty-warriors-origins-cheats-and-trainer-for-steam/346304)
and [Steam moveset discussion](https://steamcommunity.com/app/2384580/discussions/0/597389996280785142/)
report missing moves or skill panels after proficiency changes. Those reports
support treating the dependencies seriously; a trainer address or reported XP
target does not establish a save offset or a complete fix.

A direct level control needs native family identities and serialized positions,
exact thresholds and story/DLC caps, moveset/Battle Art transitions, rank/skill
panel prerequisites, reward grants and already-claimed handling. Qualifying the
final state must cover intermediate levels and idempotent reapplication. Lowering
levels additionally needs rules for acquired moves, equipment and spent rewards.
A within-level XP adjustment also needs its own exact disk position and cap proof.
The existing native executable is not available in this workspace for further
static tracing; the acquired public slot alone cannot establish those rules.

## Old Coins

The [Game8 guide](https://game8.co/games/Dynasty-Warriors-Origins/archives/493635)
and [Shacknews guide](https://www.shacknews.com/article/142718/what-to-do-with-old-coins-dynasty-warriors-origins)
describe cumulative collection milestones and rewards at Shui Jing Retreat.
The requested inventory count must therefore be distinguished from collected
location/event flags and already-claimed reward records. The base-game final
reward threshold is not proof of the native numeric storage cap or a DLC limit.

Still needed: the exact serialized member/width for each supported revision,
a native getter/setter or controlled count-change pair establishing its meaning,
applicable limits, and how the count relates to collection and reward claims.
The current Gold or Skill Point positions cannot be reused for this field.
No offset found by searching for a plausible number has been enabled for writes.

## Evidence available this round

The published [Steam DLC reference](https://github.com/VdustR/game-save-dwo-d4h/tree/b5e853eec865417edf473eb9b39330b1cf0f74e8)
remains a complete revision-29 slot with a byte-exact unchanged codec roundtrip.
Its existing mapped fields pass copied-file and GUI checks. It is not a
controlled proficiency/Old Coin action pair. The public
[Kelebek1 asset research](https://github.com/Kelebek1/dwo/tree/5de9b3e615691f2280ceeb6100416275adfbe75c)
implements asset/stage tools and supplies no missing save writer. Obtaining the
official demo through an anonymous Steam session did not provide access; no
account credentials, game execution or unverified executable source was used.

## Unreleased research follow-up

Two independently published memory tables now agree on an **unsigned 16-bit
Old Coin member at runtime main-record +`0x45A`**, alongside the already mapped
Gold (+`0x384`) and Skill Points (+`0x458`). Sources are
[BBfox's table](https://github.com/bbfox0703/Mydev-Cheat-Engine-Tables/tree/main/DYNASTY%20WARRIORS%20ORIGINS)
and [fusigi0930's pinned table](https://github.com/fusigi0930/game_script/blob/2423aae6d8ef8afce6dbd6c755e41a7b29983cdc/pc/cheat_engine_table/DWORIGINS.CT).
They were read as static text, never executed. This establishes a stronger
runtime identity lead, **not a disk offset**. Neither table supplies the native
main-record serialization sequence or collection/reward dependency rules.
No trainer implementation is incorporated.

The complete public revision-29 slot also contains a candidate fifty-record
array at decrypted body `0x8055`, matching the native 14-byte XP/Battle Art shape
and occupied/reserved record pattern. It is a **pattern-only candidate on one
reference**, not an independently qualified map. The second table supplies
additional runtime family-order clues, but these do not prove the serialized
family indices or progression transitions. No candidate is exposed for editing,
including in experimental mode.

The [public save author's discussion](https://www.nexusmods.com/dynastywarriorsorigins/mods/28?tab=posts)
reports missing Sword Combo 4 despite full proficiency. Replies suggest replaying
level gains in-game; they are not native threshold/cap proof or a complete offline
repair algorithm. This is an observed failure mode that a proper level control
must address, rather than just storing a larger XP value.

No new release or version change accompanies this research. The requested Old
Coin and proficiency edits remain unfinished. Edited game loading and re-saving
also remain separate, outstanding validation.

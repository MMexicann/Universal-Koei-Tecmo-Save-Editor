# Origins: proficiency levels and Old Coins

**Neither requested writer is implemented.** Development remains at version
2.5.1 without a new release. The existing qualified Steam slot revisions 16, 17
and 29 retain their documented editing scope. The development inspector adds a
searchable, read-only **Proficiency** tab with stored XP and equipped Battle Art
IDs. It does not calculate levels, grant weapon ownership or change progression.
See [native format evidence](ORIGINS_FORMAT.md).

## Weapon proficiency

Native executable analysis establishes subsystem 5 as fifty packed 14-byte
records: a 32-bit XP member, four equipped Battle Art IDs and two opaque bytes.
Independent public early-game, completed and DLC slots corroborate the record
geometry at decrypted body `0x7F8D` in revisions 16/17 and `0x8055` in revision 29.
The array begins 174 bytes after the qualified weapon inventory. The inspector
requires the observed original-family/Battle Art topology; unfamiliar layouts
withhold this optional view without blocking existing resource editing.

The first ten family identities are Spear, Twin Pikes, Sword, Staff, Wheels,
Gauntlets, Podao, Crescent Blade, Lance and Halberd. Bow is recognized where the
DLC record is present; the next unknown identity retains its numeric ID.
Formed Art records also exist before those weapons are acquired, so their
presence is not an ownership flag. All remaining capacity and both opaque bytes
are preserved. The view shows raw XP, including unusual existing values.

Native gain routine RVA `0xAB02D0` compares threshold-catalogue levels and calls
`0xAB6910`, affecting subsystem-10 movesets, rank, rewards and skill panels.
Story and DLC gates affect progression. Public early-game and advanced captures
corroborate different displayed levels, but do not supply an exact universal
XP-to-level function. Different slots also combine identical stored XP with
different opaque state bytes. Setting XP alone cannot reproduce a native gain.

The [WeMod discussion](https://community.wemod.com/t/dynasty-warriors-origins-cheats-and-trainer-for-steam/346304),
[Steam moveset discussion](https://steamcommunity.com/app/2384580/discussions/0/597389996280785142/)
and [public save author's discussion](https://www.nexusmods.com/dynastywarriorsorigins/mods/28?tab=posts)
report missing moves or panels after proficiency changes. Replaying gains
in-game is an anecdotal workaround, not a complete offline repair algorithm.

A level writer still needs the exact threshold catalogue and cap gates, native
moveset/Battle Art/rank/skill transitions, reward amounts and already-claimed
handling. Tests must cover intermediate gains and idempotent reapplication.
Lowering levels additionally needs rules for acquired moves and spent rewards.
A within-level XP writer needs its own proven bounds. Experimental numeric mode
does not bypass these missing rules.

## Old Coins

Two independent static memory tables agree on an unsigned 16-bit Old Coin
member at runtime main-record **+`0x45A`**:
[BBfox](https://github.com/bbfox0703/Mydev-Cheat-Engine-Tables/tree/main/DYNASTY%20WARRIORS%20ORIGINS)
and [fusigi0930](https://github.com/fusigi0930/game_script/blob/2423aae6d8ef8afce6dbd6c755e41a7b29983cdc/pc/cheat_engine_table/DWORIGINS.CT).
They were inspected as text, never executed. A fresh review of all 22 published
BBfox table revisions found no missing native serializer instructions.

Decrypted body **`0xA95` is an unqualified candidate**, supported by plausible
values and an affine relationship to two other resource leads across the public
slots. No author supplied a positive displayed Coin count tied to these files,
a controlled coin gain/spend pair, or native serialization/getter/setter code.
It is not exposed for inspection as an identified resource or for editing.
The word immediately after serialized Skill Points instead correlates with
existing weapon indices; runtime adjacency does not establish disk adjacency.

The [Game8 guide](https://game8.co/games/Dynasty-Warriors-Origins/archives/493635)
and [Shacknews guide](https://www.shacknews.com/article/142718/what-to-do-with-old-coins-dynasty-warriors-origins)
describe collection milestones and rewards at Shui Jing Retreat. An inventory
count must be distinguished from lifetime collection, location/event flags and
claimed rewards. The final base-game reward threshold is not a native storage
cap. Placement, semantics, applicable bounds and reward relationships remain
required before enabling a writer.

## Research and validation

Eight additional genuine public Steam slots were acquired from GamerSky and 3DM,
including [initial](https://down.gamersky.com/pc/202501/1874480.shtml),
[advanced](https://down.gamersky.com/pc/202501/1875385.shtml),
[three-route](https://down.gamersky.com/pc/202502/1882167.shtml),
[first-inn](https://dl.3dmgame.com/patch/331175.html) and
[clear-slot](https://dl.3dmgame.com/patch/331177.html) references alongside the published
[VdustR DLC slot](https://github.com/VdustR/game-save-dwo-d4h/tree/b5e853eec865417edf473eb9b39330b1cf0f74e8).
All nine public slots passed envelope integrity, exact revision-length, unchanged
codec-roundtrip and guarded proficiency-inspection checks. The corpus contains
six revision-16, two revision-17 and one revision-29 slot from six publishers. Copies remain private; published artifacts and screenshots are
not treated as controlled one-action pairs. Nearly identical clear slots change
only an unrelated gameplay byte and therefore supply no Coin transition proof.

Additional ColonelRVH and Cissa90 tables supplied static equipped-art and
persistent-registry clues, but no complete save serializer, threshold catalogue
or reward transition. The [Kelebek1 asset research](https://github.com/Kelebek1/dwo/tree/5de9b3e615691f2280ceeb6100416275adfbe75c)
does not supply those missing parts. The previously inspected native executable
is no longer available in this workspace; no substitute game binary, trainer or
editor was executed.

Proficiency inspection tests cover supported revisions, unknown-layout fallback,
empty/shared Art IDs, opaque and reserved bytes, unusual XP, rejected write IDs,
existing resource-edit preservation and GUI search. Native copied-file checks
are distinct from procedural tests. **Actual edited game loading and re-saving
remain unverified.** This implementation advances inspection and qualification;
it does not complete the requested proficiency-level or Old Coin editors.

# Pirate Warriors 3 PC coverage and remaining maps

Officially released platform editions and their save-format qualification
boundaries are tracked in [Pirate Warriors edition scope](PIRATE_WARRIORS_EDITION_SCOPE.md).

The native PC adapter retains existing stat/bar/skill-slot editing, genuine
sample qualification, read-only level/EXP/Beli/costume associations and the
copy-only backup/Undo/Review Changes/Save As workflow. This pass does not enable
new currency, coin, level, story or gallery writes from uncertain correlations.

| Discovered mechanic | Current coverage or specific blocker |
| --- | --- |
| Character Health/Attack/Defense | Existing per-record edits. Published boosts can reset on level-up; natural values and reset triggers are separate from editing limits |
| Special bars and equipped skill-slot capacity | Existing 1–4 and 1–6 edits. These are not functions of level alone and do not grant skill ownership or coin upgrades |
| Character level and EXP | Read-only inspection. Level-50 progression and level-100 limit break require distinct coin/dependency states; needs one native level-up and one limit-break pair |
| Current Beli and adjacent counter | Current balance read-only. New PC runtime evidence identifies current/earned Beli in adjacent memory fields, but exact save/runtime base equivalence and legitimate cap remain uncorroborated |
| Standard coins | Published patches write two independent bytes per 0x30-byte row. Which byte is inventory, historical acquisition, coin-level or another counter remains unproved; needs one obtain/spend pair with displayed counts |
| Rare/gold coins | Published patches touch both leading bytes in each row; cannot treat them as a u16 count. Character/crew/stage prerequisites and limit-break dependencies need controlled acquisition/usage pairs |
| Skill posters, skill acquisition and ranks | Distinct from equipped slot capacity. Skill order can vary with acquisition; native ownership/rank identities and associated prerequisite rewards need controlled skill pairs |
| Kizuna/crew progression and support states | PC runtime gauge/level probes exist but are battle state, not evidence of serialized lifetime crew progression. Needs crew growth and crew-skill reward pairs |
| Characters and movesets | Only source-corroborated PC character labels are named; unknown physical slots retain numbers. Asset labels alone do not prove character-unlock state or movement/upgrade masks |
| Costumes | Existing PC asset associations are inspected only. Association/asset ID does not prove purchase, DLC ownership or equipped state; needs one costume purchase and equip pair |
| Legend Log/story/stage completion and Legend Diary objectives | No independent native unlock/clear/objective maps or reward transitions; needs one stage clear with difficulty/rank/objective labels |
| Dream Log/island progression and Nightmare difficulty | No verified native world-node/reward map; needs one island clear plus unlocked-node changes and unchanged control |
| Gallery movies, music, character/term/crew collections | Shop purchases and stage-event acquisition are separate. Completion of Legend Log alone does not unlock every event movie; needs one buy/unlock pair for each category |
| Character upgrades from coins/Beli | Raw stat changes do not recreate coin investment or upgrade purchases. Requires controlled upgrade pairs showing consumed coins and corresponding displayed upgrades |

## Additional native PC currency evidence

The PC v1.0.0.0 runtime table in
[Hexorg/CheatEngineTables](https://github.com/Hexorg/CheatEngineTables/blob/0e7092b235f62ee5af4d3942c4323eb6c414f9c6/tables/shinkansen_one_piece_pirate_warriors_3_v1000_621.ct)
(commit `0e7092b235f62ee5af4d3942c4323eb6c414f9c6`) captures the Beli-shop
instruction `mov esi,[ebx+0xBFE4]`. Its named four-byte entries are Current Beli
at base `+0xBFE4` and Earned Beli at base `+0xBFE8`. Its runtime boost writes only
Current Beli to 9,999,999. That target is not evidence of a gameplay maximum.

The native save's mapped adjacent fields are decoded payload `0xC5D4` and
`0xC5D8`. They differ from those runtime offsets by the same `0x5F0` prefix. Two
previously documented genuine PC samples contain plausible current/lifetime
pairs: 999,999,999 / 1,000,000,000 and 19,585,649 / 26,304,000. This is additional
semantic evidence; neither pair is a controlled before/after observation. No
third field tied to the same runtime base has independently established the
base equivalence. Published console patches change both values and their targets
cannot establish a legitimate PC cap. The existing currency write gate remains
closed, while existing factual observed-balance inspection is retained.

## Mechanics sources inspected

- [PC DLC asset/costume guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2306008901):
  native character/costume filename associations. Conflicting or ambiguous
  character variants remain unnamed rather than assigning every record a roster.
- [PC skill guide](https://steamcommunity.com/sharedfiles/filedetails/?id=729079419):
  acquisition-order considerations; skill capacity is distinct from acquisition.
- [Steam discussions search, max Beli](https://steamcommunity.com/app/331600/discussions/search/?q=max+beli):
  a public fully progressed-save discussion distinguishes Level 50/Beli shop from
  the Level 100 ceiling and discusses separate Dream Log, coins, movies and shop
  ownership. A gallery discussion reports all story/Legend Diary progress while
  still lacking event movies, reinforcing the separate event-acquisition model.
  Community statements are mechanics leads, not native offset or numeric-cap proof.
- [Apollo NPEB02211 patches](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPEB02211.savepatch):
  the already-correlated shared character/coin layout. PS3 big-endian values
  must not be applied directly to native PC little-endian storage.

The two public native save repositories remain outside the project tree and
public packages. No player saves, native executables, account identifiers or
third-party source implementations are distributed. Native-file roundtrips
are not actual Windows game-load validation.

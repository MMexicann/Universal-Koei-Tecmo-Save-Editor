# DW8 XL PC weapon compatibility and ally inspection

Development source additionally supports
[existing ranked attribute replacement](GAME_SPECIFIC_EXPANSION.md#dynasty-warriors-8-xl--windows-pc)
with an opened-save palette and complete pending duplicate/rank checks.

This addition uses the already qualified native Windows PC DW8 XL layout. It
adds individual and grouped edits for the four stored weapon-action aptitudes
of all 82 officer records, individual affinity edits for qualified existing weapons,
reordering of each qualified officer's two already equipped weapons, and
read-only inspection of physical ally records.
It does not introduce another game, change progression or unlock recruitment.

## Weapon compatibility

The four one-byte fields begin at decoded payload `0x7FDB + officer * 0x48`.
They follow the two-byte Health field. Native PC runtime descriptions order the
quartet as Dash, Dive, Shadow Sprint and Whirlwind. Compatibility is separate
from weapon affinity, weapon attack/attributes, officer EXP and skills.

The published native PC sample contains only 25, 50, 75 and 100 at all 328
locations. The published shared-layout “All Generals Aptitude 4-Stars” save patch
writes `64 64 64 64` at exactly these locations. The editor accepts the four
observed units, displayed with the one/two/three/four-star interpretation. It
rejects arbitrary intermediate values rather than guessing their meaning.

Group Max writes 100 only over those observed values. Other existing values,
including lower unusual values and values above 100, remain untouched. The
original value can always be restored through Undo, including an unusual value.
No officer level, EXP, leadership, equipment reference, reward, story, skill or
weapon bytes change with this action. Game recalculation of compatibility after
loading, equipping, learning skills and leveling has not been independently
validated; the editor does not assert that a direct override purchases skills.

## Existing weapon affinity

The physical weapon pool starts at decoded payload `0xE715`, stride `0x18`,
count 1,830. The stored affinity is the byte at record `+4`, following the
uint16 weapon identity at `+2`. The native PC runtime permanent weapon table
independently describes the corresponding identity, affinity, attack and six
attribute-ID/rank fields in the same order. All 1,165 qualified populated
weapons in the public native PC sample use affinity IDs 0, 1 or 2.

Weapon occupancy and attribute emptiness are separate. The existing weapon
record selector retains its native state and uint16 weapon-ID qualification.
**Empty ID 255 refers to an attribute ID byte**, not a newly introduced weapon
identity sentinel; this documentation clarification changes no parser behavior.

Only existing populated records (observed state 1/3, non-sentinel weapon ID)
whose opened affinity is 0/1/2 get this field. Unknown affinity rows remain
read-only. Individual edits accept 0/1/2; affinity is excluded from every Max
operation because the three affinities are choices, not ordered upgrades.
The mapping of numeric IDs to Heaven/Earth/Man names is not independently
corroborated, so the editor retains explicit IDs rather than guessed names.

[Steam weapon-fusion guide](https://steamcommunity.com/sharedfiles/filedetails/?id=268825547)
describes affinity changes separately from weapon attack and attribute changes.
It normally costs 50 gems and a sacrificed weapon. Direct editing changes the
existing weapon's single serialized affinity byte while retaining identity,
attack, attributes, acquisition state, inventory size and officer equipped
references. The editor does not manufacture a fusion transaction or claim an
in-game load check. Type/rank-dependent attack ceilings remain unmapped, so
weapon attack remains read-only.

## Existing two-weapon order

Officer records at `0x7FC9 + officer*0x48` contain two little-endian u16
zero-based weapon-pool references at `+0x30/+0x32`. When the opened references
are distinct, both resolve inside the 1,830-record pool, and both target existing
qualified populated weapons, a First Equipped Weapon choice offers those two
original slots. Selecting the other slot swaps both references together.
It preserves their multiset, weapon state, identities, properties and ownership;
it cannot select a third weapon or create a pool record. Unknown, duplicate,
empty or invalid original references stay unchanged. This choice is excluded
from Max, and Undo reverses the complete reorder. The original record map above
supplies the storage facts; [test_dw8_weapon_order.py](../tests/test_dw8_weapon_order.py)
covers pair preservation, qualification, surgical writes and original restoration.
Source corroboration and validation scope are detailed in the
[weapon-order proof](RICH_EDITOR_EXPANSION.md#dw8-xl-weapon-order-proof).
Edited game loading remains untested.

## Ally progression inspection

The shared published layout contains 838 physical records at decoded payload
`0x9BE9`, stride `0x0C`. The following fields are corroborated by the native PC
fixture and runtime record semantics:

| Offset from record | Width | Read-only meaning |
| --- | --- | --- |
| `+0` | 1 | Current skill level minus one |
| `+1`, `+2` | 1 each | Support-skill IDs; 255 is retained literally |
| `+4` | 2 | Skill EXP, little endian |
| `+8` | 1 | Male officer bond |
| `+9` | 1 | Female officer bond |

The inspector uses physical numbered slots. These records do not establish
recruitment, availability, officer names, battle-skill identity, maximum skill
level, strengthening prerequisites or reward state. No writable ally fields or
bulk ally action is exposed. Unknown bytes and padding remain unchanged.

## Coverage checklist

| Discovered system | Current coverage or precise blocker |
| --- | --- |
| Gold, gems, facility/weapon materials | Existing bounded edits; keep higher values during Max |
| Permanent officer Attack/Defense/Health | Existing direct edits; later stat recalculation needs controlled game reloads |
| Four weapon-action compatibilities | New validated individual/grouped edits; in-game reload untested |
| Officer level/EXP and leadership/EXP | Read-only inspection; XP threshold, reward and recalculation dependencies need controlled progression pairs |
| Existing weapon attribute ranks | Existing edits for mapped ranked IDs only; unknown/unranked IDs retained |
| Weapon affinity | New individual 0/1/2 edits on qualified existing records; excluded from Max; Heaven/Earth/Man numeric names and in-game reload untested |
| Weapon identity and attack | Read-only inspection; type/rank-specific attack limits and valid identity relationships need independent corroboration |
| Equipped weapon references | Qualified existing two-weapon pairs may be reordered atomically; selecting a third weapon still needs ownership/type compatibility and controlled equip evidence |
| Skills and rankable/enabled state | Published skill-pair patch exists; native sample has only enabled/maxed pairs, so unlock/rank dependency controls are missing |
| Ally skill/EXP/support IDs/bonds | New read-only inspection; recruitment, identity, maximum-level and reward dependencies need controlled native pairs |
| Mounts/support beasts | Published speed/breakthrough patches use cheat limits and conflicting maxima; native identities, legitimate limits and acquisition/equip dependencies remain unmapped |
| Ambition facilities | Material balances editable; invested materials/rank/supervisor/roster/capacity progression requires controlled upgrade/recruitment pairs |
| Story/stage clears, campaigns and collection/gallery state | No independent native maps or reward transitions; needs one-action native clear/unlock pairs |
| Costumes/customization | Runtime outfit byte exists; native ownership/DLC/equipped-state relationship not established |

## Evidence and validation

Inspected public factual sources, with no source implementation copied:

- [koko-tsuu/dw8xl_save_converter](https://github.com/koko-tsuu/dw8xl_save_converter/tree/8ca795108a4f4f0bee91c55d3efce0c6da78515f),
  commit `8ca795108a4f4f0bee91c55d3efce0c6da78515f`: qualified PC format and
  public native PC fixture. Its input remains outside this project's packages.
- [Apollo NPUB31449 shared-layout patch](https://github.com/bucanero/apollo-patches/blob/0ccc07ed39ea378db83e9901dbfa610b04637d7d/PS3/NPUB31449.savepatch),
  commit `0ccc07ed39ea378db83e9901dbfa610b04637d7d`: aptitude byte locations,
  four-star value and ally record spans. The existing converter independently
  establishes the shared decoded layout; console patches alone are insufficient.
- [PC runtime table v1.0.0.7](https://github.com/Hexorg/CheatEngineTables/blob/0e7092b235f62ee5af4d3942c4323eb6c414f9c6/tables/shinkansen_dynasty_warriors_8_v1007_158.ct),
  commit `0e7092b235f62ee5af4d3942c4323eb6c414f9c6`: corresponding adjacent
  permanent-stat/compatibility structure and ally semantics. Runtime addresses
  alone are not used as disk offsets.

`tests/test_dw8_compatibility.py` covers surgical edits, all four accepted values,
rejection of guessed intermediate values, higher/unusual preservation, original
unstaging, read-only ally gating and inspection. With `DW8XL_SAVE_COPY` pointing
at a privately held genuine native PC fixture it also checks exact no-op
roundtrip, edited roundtrip, native integrity and byte preservation outside
compatibility, including unchanged EXP, weapon and ally records. `tests/test_dw8_affinity.py` additionally covers qualified populated records,
unknown-affinity and stale/empty-record rejection, exclusion from Max, targeted
single-byte writes, and the GUI search/stage/Undo/Review Changes/automatic-backup/
Save As workflow. Its optional genuine-fixture test verifies one-byte affinity
changes without altered weapon properties, officer progression or allies.
These are native-file/GUI tests, not an actual Windows game-load validation.

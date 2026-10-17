# Fire Emblem: Three Houses — Switch gameplay exports

This is the tactical RPG **Fire Emblem: Three Houses**, separately registered
from Fire Emblem Warriors and Three Hopes. Open a known Three Houses
main-campaign, extensionless extracted slot/auto **copy**. The adapter uses the
existing shared GUI, staged Undo, Review Changes, automatic backups and atomic
Save As to a new destination. Keep the complete original console export intact;
console extraction, import and ownership transfer are outside this adapter.

## Identity, revision and scope

The accepted serialization profiles are independent:

| Native header version | Payload bytes | Total bytes | Character stride | Source-associated game updates |
| --- | --- | --- | --- | --- |
| 13 | `0x25400` | `0x2540C` | `0x230` | 1.0.1–1.0.2 |
| 23 | `0x25B20` | `0x25B2C` | `0x24C` | 1.1.0–1.2.0 |

These are **save-format versions**, not exact software-build or DLC identifiers.
No embedded title magic, region marker or entitlement authenticator was proved.
Title evidence comes from public extracted-export provenance and platform-specific
source; the user must select the correct adapter and a known main-campaign export.
Exact length, declared length, profile, native checksum, NPC-size marker and
inventory-record counts then qualify structure. Those checks do not authenticate
arbitrary bytes as belonging to a title. The selected adapter never tries another
parser after rejection.

Launch format 12, system format 7, suspend data, containers and padded exports
are rejected. Cindered Shadows side-story serialization is **unqualified**;
there is no proved detector for distinguishing a structurally matching side-story
payload. Do not open it as main-campaign data. Installed DLC/free-update content
and entitlement are preserved without inference or writes. Official update and
mechanics distinctions are in [THREE_HOUSES_MECHANICS.md](THREE_HOUSES_MECHANICS.md).

## Source and licence evidence

- [imouto1994/fe3h-editor](https://github.com/imouto1994/fe3h-editor/tree/5e4a73b71f28feb271ccdbc614ea934517c235b5)
  targets game 1.0.2; no licence is supplied.
- [hashcade/feth-save-editor](https://github.com/hashcade/feth-save-editor/tree/b9f53f0e01a3dd2cd24c96f97f1a829e51a1f00d)
  targets 1.2.0 and credits Falo 1.2.0 Beta1. Its MIT notice covers the author's
  original additions, expressly excluding upstream code/assets. It is not a
  blanket permission to reuse the old implementation or catalogs.
- [Falo's forum reference](https://gbatemp.net/threads/fire-emblem-three-houses-general-hacking.544144/post-8948080)
  is linked by the later source; direct access returned HTTP 403. Its contents
  are not claimed as independently read evidence.
- [Public extracted-save index](https://github.com/Viren070/NX_Saves/blob/603dc50937246f08ed80670c1aa1d0c0607fa73d/index.md)
  supplied two archives labelled Three Houses with title metadata. Completion
  and NG++ claims do not prove clean state, installed patch or DLC entitlement.

The Python codec, staging and safe writer are independently implemented from
factual storage layouts, checked against extracted candidates. No upstream
implementation, bulk catalog, player save, account identifier or game asset is
included. Public source files `Structs/Save.cs`, `Character.cs`, `Player.cs`,
`Activities.cs`, `Item.cs`, `Battalion.cs`, `Enums.cs` and the later `SaveBuffer.cs`
establish the facts below. The original source misleadingly calls header word
+4 a header size; later source and extracted files establish serialization version.

## Serialization and integrity

The 12-byte little-endian header is u32 payload-byte checksum at file +0,
u32 serialization version at +4 and u32 total file length at +8. Integrity is
`sum(file[12:declared_length]) modulo 2^32`. Every byte of the accepted payload,
including unknown data, participates. No encryption or checksum bypass is added.
The adapter rejects bad input rather than repairing it. No-edit serialization
returns the exact original bytes. A qualified edit writes only admitted scalars
and checksum bytes 0–3, then reparses the complete result.

All following offsets are **payload-relative**; add 12 for absolute file offsets.

| Structure | v13 | v23 | Record/storage facts |
| --- | --- | --- | --- |
| Convoy | `0` | `0` | 400 × 4 bytes: s16 item ID, u8 durability, u8 amount; count u32 at `0x640` |
| Characters | `0x644` | `0x644` | 60 records; strides above; six held item records at +0 |
| NPC size marker | `0x89B8` | `0x9048` | u32 `0x19DF0`, source-backed NPC serialization size |
| Player | `0x22AB9` | `0x231D9` | `0x1EC8` bytes; gold u32 at +`0x1074` |
| Activities | `0x24981` | `0x250A1` | Renown u32 +`0xC`; professor EXP u16 +`0x12` |
| Barracks | Player +`0xA30` | Player +`0xA30` | 200 × 8: s16 assigned owner, u16 EXP, u16 endurance, u8 type, u8 skill |
| Support points | Player +`0x1080` | Player +`0x1080` | 256 / 270 u16 values; pair identities/ranks unqualified |

The older Activities comment `0x2498D` uses file coordinates, unlike adjacent
payload-coordinate comments; the implementation uses `0x24981` plus the header.
The convoy count must equal occupied identities (ID != -1), and each character's
+`0x87` held count must equal occupied held IDs, at most six. Negative unknown IDs
are preserved as unknown records, never made writable.

## Writable fields and original ownership

Development source also supports
[qualified protagonist-name customization](GAME_SPECIFIC_EXPANSION.md#fire-emblem-three-houses--nintendo-switch)
in both admitted profiles, preserving original native name controls and exact
opened-name no-ops. It edits only this gameplay slot.

Gold can decrease from its opened u32 value to zero. Existing ordinary convoy
quantity can decrease to one, preserving occupancy/count and identity. Existing
ordinary finite equipment durability can decrease to zero, preserving the item,
owner, equipment references, forge identity and all other bytes. Item-specific
repair maxima, creation, purchases, forge transactions and transfers are not
implemented. Controls do not perform their gold/material/prerequisite transactions.
Convoy durability applies to the complete existing stack record. It does not
split off a single copy, merge stacks or transfer an item to another owner.

Item eligibility uses a small factual ordinary-item allowlist documented in the
adapter; it does not import a restricted catalog or accept every positive ID.
Unknown IDs, quest/relic/accessory records and unproved item categories remain
read-only. Durability **100 is the unlimited sentinel**: existing sentinel data
stays read-only and no edit may create the sentinel from a higher unusual value.
Higher/unusual values survive no-op and bulk actions. Assigning the opened value
unstages it without normalization. All controls have `maxable=False`; an opened
value used as a reduction bound is not advertised as a natural gameplay cap.

The admitted ordinary equipment IDs are 131 Brave Sword+, 132 Killing Edge+,
137 Brave Lance+, 138 Killer Lance+, 143 Brave Axe+, 144 Killer Axe+, 149 Brave
Bow+, 150 Killer Bow+, 153 Steel Gauntlets+, 154 Silver Gauntlets+, 168 Rapier+
and 175 Wo Dao+. These short identity facts come from `Database.cs`'s explicit
`EssentialItems` comments in the cited sources, not an extracted asset catalog.
Consumables and materials have no quantity controls in this implementation.

Held equipment additionally requires a unique known base-unit owner ID 0–34 at
character +`0x24`, positive stored level at +`0x4A`, and original flags at +`0xAC`
with Available and Has Joined set, Is Dead clear. `Enums.cs` labels those as
bits 0, 1 and 3. This is source-backed ownership qualification, not independently
controlled-game validation of every recruitment state. The original source's
`CHARACTER_USEABLE_COUNT` and `InitLists` establish these native unit IDs;
record position is not substituted for unit identity. DLC and other unknown
positive owner IDs remain inspected and read-only even with apparently joined
flags. Pending edits cannot
manufacture eligibility. Held byte +3 is **not exposed as quantity**: all examined
occupied held records have zero there. Convoy amount and held amount semantics
must remain separate. Recruitment and death flags are never written.

Instruction motivation is now editable at character `+0xC4` in exact steps
0/25/50/75/100 for original unique living available/joined base-unit IDs 2–34.
Byleth IDs 0/1 and unusual original values are excluded. This changes the
instruction budget only: proficiency, budding talents, supports, professor EXP
and remaining lesson activity are preserved.

Five equipped-ability bytes at `+0x7F..+0x83` now offer only originally equipped
IDs whose original learned bits are set, plus Empty (240). Original loadouts
must be distinct, nonempty and undeployed (flag bit 18 clear), with the same
qualified base-unit ownership as held equipment. Clear an ability's old slot
before moving it. Complete staged loadouts reject duplicate nonempty IDs;
ownership bits, class, personal/class-derived abilities and reward flags remain
unchanged. These choices are excluded from Max. Source facts, native checks and
remaining dependencies are detailed in
[HYRULE_FIRE_EMBLEM_DEPTH.md](HYRULE_FIRE_EMBLEM_DEPTH.md).

## Separate mechanics and remaining write evidence

Character record mappings include u16 EXP +`0x2C`, eleven u16 proficiency EXP
values +`0x32`, u16 current class EXP +`0x48`, level/class/HP +`0x4A..0x4C`, nine
stored stat bytes +`0x4E..0x56` (Strength through Charm, including Movement), combat
art ownership bytes +`0x57`, ability ownership bytes +`0x61`, equipped ability
IDs +`0x7F` and equipped combat arts +`0x84`. Eleven proficiency ranks start
+`0x88`; current mastery state is +`0x93`. Proficiency EXP mirror is +`0xFC`;
per-class EXP starts +`0x112`, 90/100 u16 counters. Rank mirrors start
+`0x1C8`/`0x1DC`; 90/100 mastery states start +`0x1D3`/`0x1E7`.

The inspector distinguishes those counters, mirrors and ownership/equipped IDs.
It does not interpret an unknown support-array index as a named pair or grant
conversations. Barracks and equipped battalion copies can naturally have differing
EXP/endurance; they remain distinct. Numeric IDs are shown without inventing a
roster/ability/class order.

| System | Exact prerequisite or input still needed for writes |
| --- | --- |
| Stats / level / EXP | Clean displayed-value and one-level-up/stat-booster/certification pairs; base versus effective stats, character caps, statue cap rewards and growth processing. |
| Proficiency / movement | Rank-threshold and budding-talent pairs, primary/mirror handling and learned spell/ability/arts rewards. Riding/Flying/Heavy Armour proficiency differs from Movement stat. |
| Class mastery | Certification/current-class/mastery transitions and reward ownership, per-class mirrors, class-dependent art use and DLC exam prerequisites. |
| Abilities / combat arts | Existing qualified equipped abilities can be cleared or rearranged using their original learned IDs. Adding unequipped abilities, changing ownership or editing combat arts still needs factual ID/applicability evidence, personal/class distinctions and crest/weapon/class prerequisites. |
| Battalions | Hire, assignment/swap, level-up and endurance loss/replenishment pairs; catalog identity, Authority/flying restrictions, equipped-copy synchronization and gambit-use semantics. |
| Repair / inventories | Known ordinary item type/use bounds, single-use/repair/trade/equip pairs and prerequisite costs; safe full transaction before repair, creation or transfer. |
| Renown / professor progression | Balance versus NG+ historical purchases/clear rewards/statue state and remaining activity points; no generic reward grants. |
| Supports | Index-to-character-pair map; gained-points versus viewed-conversation pairs, chapter/route/time windows and ending selection. Anna has no supports. |
| Recruitment / story / routes / rewards / entitlement | Separate clean qualification and controlled transitions; never implied by stats, counters or item controls. |
| Variations | Exact build/region/DLC-labelled clean exports; v12, padded, system, suspend and side-story framing plus genuine unchanged controls. |

## Genuine-file evidence and validation boundary

Two public archives yielded four exact v13 and four exact v23 gameplay slot/auto
candidates, all native checksums valid. Across them, occupied convoy/held counts
match their declared counts and occupied character IDs are unique. Some values
are high/unusual; the files are third-party examples, potentially modified, not
controlled clean exports. One additional v13 file has 1,824 zero trailer bytes;
one suspend file contains a valid slot prefix but a different outer length.
Both are rejected without truncation. Two system version-7 files are unsupported.
Private samples stay outside the checkout and public manifests.

Test results are recorded after integration in [VALIDATION.md](VALIDATION.md).
Optional `THREE_HOUSES_SAVE_COPY` selects a reviewed extensionless private slot;
`THREE_HOUSES_REVIEW_COPIES` selects multiple local copies separated by `os.pathsep`.
Procedural tests exercise malformed/foreign profiles, integrity, surgical writes,
unknown/higher values, eligibility, staging, Undo/review and guarded backups.
Genuine-file byte tests are distinct from actual console testing. **No edited
save has been imported, loaded or re-saved on a Switch.** No Windows executable
is built or released by this branch.

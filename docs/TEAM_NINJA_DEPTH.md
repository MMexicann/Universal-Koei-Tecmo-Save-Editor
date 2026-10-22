# Existing Team Ninja editors: implemented expansion and proof limits

These changes extend existing adapters without adding a game/platform or
changing their native revision profiles. No game or third-party editor binary
was executed. Edited game-load/re-save validation remains unperformed.

## Wo Long: existing battle-set custom names

The qualified PC USER revision `0x23121200` contains two separate 50-slot
serializer arrays:

- `UIData.ui_battleset_slot_data_info[i].UiBattleSetSlotInfo.str`: a JSON string
  for the slot's custom display name.
- `PlayerData.battleset_data_list[i].BattleSetData`: the loadout, including a
  boolean `enable_flag`, level, Virtues, spells and equipment references.

The [official update history](https://www.teamninja-studio.com/wolong/us/update/),
Ver1.300 (December 12, 2023), explicitly identifies custom names in the Battle
Set menu and warns:
“Changes made to custom names will not be saved if they contain characters not
supported by the game.” It separately describes automatically registered battle
set names. The independently observed serializer keeps UI names separate from
the gameplay loadout. No external implementation or catalog supplies this
writer.

The new controls select a name only when both arrays have exactly 50 slots,
both wrappers match, the name is already a string and the corresponding
`enable_flag` is the boolean `true`. Missing, unknown or malformed optional
arrays generate no name fields and remain unchanged. Editing cannot create or
enable a battle set, equip its gear, allocate its Virtues or unlock its spells.
The stable field ID is `battle_set_<zero-based-slot>_name`; the visible slot is
one-based. Storage is the existing variable-width UTF-8 JSON string token.

Manual input accepts 1..16 printable ASCII bytes. This is a conservative editor
limit, **not a recovered natural game limit**. Quotes and backslashes use JSON
escaping. Unicode and longer original names remain byte-exact on no-op; assigning
the opened string unstages an edit even when that string exceeds the input
limit. Max is disabled. Only the selected string token, body zero-padding and
native checksums change; all loadout records, other JSON spelling, owner context
and original cipher representation survive. Existing currencies and names can
be staged together with shared Review Changes, Undo, backup and Save As.

The genuine USER/BACKUP corpus confirms these arrays and wrapper shapes, but
contains **no enabled battle sets or nonempty custom names**. Genuine no-op and
currency/stack regressions validate the unchanged native profile. Enabled-set
renaming is covered by generated surgical-format and actual Tk Save As tests;
it has **not** been validated on an enabled native battle set or loaded in game.
An intact current-revision native copy with an existing named enabled set, plus
a controlled rename pair, is the precise next qualification input.

Equipment reinforcement, lock/favorite bits, Martial Arts, virtues, skill
points and Wizardry remain blocked by the specific dependencies recorded in
[TEAM_NINJA_RESEARCH.md](TEAM_NINJA_RESEARCH.md). Native nested orb/inscription
fields and suggestive names do not prove allowed categories, caps, cache updates
or prerequisites. A public unlicensed runtime-memory trainer found during the
search does not qualify a PC disk mapping; its code and catalog were not copied.
No quantity range or flag eligibility was broadened from that source.

The Wo Long safe-save path now rechecks the opened bytes after serialization
and after backup, preventing a detected source change from reaching a new
destination. Wrong selection types and non-Path forged snapshots raise the
standard save error. These changes preserve the shared safety workflow.

## Nioh 3: eleven more ordinary consumables

The first expansion added eleven factual ordinary-item IDs to the original seven
in the qualified item-box/storehouse arrays. Those eleven additions are:

| Native little-endian u16 ID | Name |
| --- | --- |
| `0x6514` | Antidote |
| `0xFA6E` | Antiparalytic Needle |
| `0x96A7` | Arrowproof Amulet |
| `0x4E22` | Daion-Jin's Sake |
| `0xE7D3` | Dung Ball |
| `0x4D66` | Fireproof Amulet |
| `0xFC7A` | Sacred Ash |
| `0x5A51` | Smoke Ball |
| `0x4C5F` | Throwing Stone |
| `0x5943` | Travel Amulet |
| `0x304E` | Water Amulet |

Each factual name/byte identity was checked against the Apache-2.0
[public editor at commit b5d0789](https://github.com/alfizari/Nioh-3-Save-Editor/tree/b5d0789791fe31d06ad325d4012aa0333c60cd8f)
and independently found in genuine native revision `0x01030001` or `0x01040000`
records with matching identity/appearance, positive quantity, zero equipment
levels/reinforcement and a nonzero instance. The
[official equipment manual](https://www.gamecity.ne.jp/manual/nioh3/eng/6300.html)
also independently identifies Throwing Stones, Antidotes and Antiparalytic
Needles as ordinary usable items. Only these small factual corroborations are
included; no external catalog, extracted game asset or source implementation
is incorporated.

The existing qualification and dependency rules remain authoritative: a unique
known record in a native item pool, original positive quantity, ordinary shape,
`1..opened quantity`, no increases, no removal, no equipment writes and no Max.
Quantity remains u16 at record `+0x04`; only those bytes and the native body
checksum change. Unusual high original quantities remain reversible. Identity,
instance, flags, shortcuts, acquisition, rewards, native seeds and ciphertext
context stay intact. Native revisions retain their exact tagged array profiles.

Generated tests edit every new item in both pools and revisions, reject
nonordinary shapes and wrong values, verify mixed changes/Undo, and compare
all changed bytes against selected quantity/checksum ranges. Genuine tests edit
eligible additions in both native revisions and verify original-file
preservation; actual Tk tests search Sacred Brush, stage/review/undo and save a copy
with an automatic backup. These are native parser/write and GUI qualifications,
not actual game-load evidence.

## Nioh 3: fourteen further ordinary consumables

The next refinement expands the supported ordinary consumables to thirty-two:

| Native little-endian u16 ID | Name |
| --- | --- |
| `0x2296` | Yokai Water Pot |
| `0x683B` | Scampuss Furball |
| `0x3F5A` | Summoner's Candle |
| `0x140F` | Righteous Jasper |
| `0xCC42` | Power Pill |
| `0x059A` | Lantern Plant Fruit |
| `0x3299` | Steel Pill |
| `0xE4AA` | Luckbringer Amulet |
| `0x3A1B` | Uchiko Powder |
| `0x9509` | Fragrant Wood |
| `0x65B4` | Healing Pill |
| `0x5EDB` | Tiger-Running Amulet |
| `0x7EA2` | Sacred Brush |
| `0xF681` | Herbal Remedy |

Each name and byte identity was rechecked online against the same pinned
Apache-2.0 [public item reference](https://github.com/alfizari/Nioh-3-Save-Editor/blob/b5d0789791fe31d06ad325d4012aa0333c60cd8f/items_little_endian.json).
Independently parsing the two genuine native USER copies finds every added
identity with matching appearance, positive quantity greater than one, a
nonzero instance and zero equipment level/pre-forge/reinforcement. Each identity
qualifies in at least one revision; this does not claim that every identity
appears in every native pool or revision. The catalog alone grants no fields,
and unknown materials, equipment, skill items and reward records remain intact.
No external catalog or implementation is shipped.

The existing deduction-only policy remains unchanged: `1..opened quantity`, no
increases, no removal and no Max. A deduction does not activate an item's
effect, recover a grave, place a Benevolent Grave, replenish abilities or update
use/history/reward state. Native tests actually reduce eligible added stacks,
reparse the result and verify that only selected quantity bytes and the body
checksum change, while the original copy stays unchanged. They require every
new identity to occur in a native positive reduction across the reviewed corpus.
Generated tests additionally cover all fourteen in both pools/revisions,
nonordinary records, duplicate identities, invalid inputs and reversible edits.
Actual edited game-load/re-save validation remains unperformed.

## Nioh 3: read-only equipment detail

The existing qualified equipment array now exposes additional numeric context
in **Inspect Data**: a source-reported u16 at record `+0x30` and seven raw
`0x18` modifier-slot tuples from `+0x38` (u16 ID at `+0`, u32 value at `+4`,
metadata bytes at `+9` and `+0x0A`). Existing level, pre-forge, reinforcement
and appearance fields remain visible. Empty modifier slots are omitted; IDs,
values and metadata are displayed as numbers without effect names or inferred
categories.

The relative sublayout is attributed as a factual research lead to the pinned
Apache-2.0 [Nioh 3 Save Editor source](https://github.com/alfizari/Nioh-3-Save-Editor/blob/b5d0789791fe31d06ad325d4012aa0333c60cd8f/main.py).
No code or effect catalog is copied. The current native profiles independently
qualify the full equipment array tags, lengths, strides and boundaries, but the
added subfields have not been mapped from a controlled equipment action pair.
They are inspection hints only: they do not create equipment fields in the
writer, and edits to balances or consumables must preserve the entire equipment
array. Category rules, native-value semantics, allowed ranges, affix
dependencies and game-load/re-save behavior remain unverified.

The generated format regression injects raw values into the first and seventh
slots, verifies numeric display, confirms `field_map` and `stage` reject these
subfields, then combines an eligible balance and stack reduction and checks the
full equipment array remains byte-identical. This is procedural writer-safety
evidence; it does not qualify the subfield layout on a genuine save or establish
an editable affix mapping.

## Original Ninja Gaiden II: audit outcome

The original Xbox 360/Xenia revision-6 parser already selects all eleven
source-named ordinary consumables/ammunition records, preserves variants and
rejects duplicate identities. Reinspection of the published source found no
additional independently proved ordinary-item mapping. Public health/Ninpo
writes normalize duplicated halfwords without proving their distinct consumers;
weapon upgrade codes likewise do not establish equipped references or learned
moves. No new stat, weapon, ownership or story writer was invented. The existing
format/native and Tk workflows are regression-tested alongside the additions;
[NINJA_GAIDEN_RESEARCH.md](NINJA_GAIDEN_RESEARCH.md) keeps those exact blockers.

## Focused validation

- `tests.test_wolong_expansion`: surgical escaped/custom-name token writes,
  enabled-set qualification, limits, original Unicode/high-value Undo, mixed
  numeric/text changes, actual Tk save/backup workflow and source-change races.
- `tests.test_nioh3_expansion`: both revisions/pools, all eleven additions,
  the fourteen further consumables, nonordinary/duplicate/unknown preservation,
  high originals, actual Tk workflow and optional genuine-file surgical edits
  covering every newly refined identity.
- Existing Wo Long/Nioh 3/NGII native and format suites, plus
  `tests.test_team_ninja_gui`, retain independent regression coverage.

Private fixtures remain outside source and bundles. Environment variables select
reviewed local copies; no player bytes, identifiers or personal paths are
published here.

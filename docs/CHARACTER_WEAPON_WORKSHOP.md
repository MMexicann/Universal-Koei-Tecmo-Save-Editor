# Character & Weapon Workshop

The source build includes a graphical workspace for planning and comparing
character and weapon builds. It is available for these qualified profiles:

- Dynasty Warriors 3 Complete Edition Remastered, Windows PC
- Dynasty Warriors 8 Xtreme Legends Complete Edition, Windows PC
- Warriors Orochi 3 Ultimate Definitive Edition, Windows PC
- Samurai Warriors 4 DX, Windows PC

The Workshop starts from each profile's existing parser fields, equipment
choices and progression dashboard. It does not add game formulas. Verified
dashboard calculations are displayed as supplied by that game's existing
projection; for example, DW8 XL aptitude stars use the established dashboard
mapping, while WO3U compatibility remains in its stored raw units. Where a
profile has no verified effective-stat formula, the Workshop shows the stored
values and says so.

## Plan, compare and export

Open a supported save copy and select **Character & Weapon Workshop**. The
initial plan is a snapshot of fields the selected profile already maps for a
character, weapon record or loadout. Choose **Duplicate for Planning…** to
make a separate proposal, double-click a planned value to change it, and use
**Add Mapped Field…** for another field supplied by the profile. Equipment
choices are listed only when the game's parser supplies qualified choices.

**Compare Builds** shows numeric A-minus-B differences for matching planned
field IDs and marks equipment choices that differ. Those differences are
plain comparisons; they are not damage, effective attack, affinity, skill
stacking or progression calculations. **Verified Stats** displays the selected
profile's existing dashboard values and evidence independently.

DW8 XL also has a **Compare Weapons** view for populated weapon records in the
opened copy. It reuses the existing weapon dashboard to compare stored attack,
affinity IDs and mapped ranked attributes side by side; it does not estimate
combat damage or elemental effectiveness.

Export a reusable `.build.json` preset to move a plan between matching game
and platform profiles. A preset contains declarative values, a name and notes;
it contains no save bytes, save path or source hash. Importing a preset only
adds it to the Workshop for planning. A preset for another game or platform
is rejected.

## Apply through the editor

Choose **Stage Plan in Editor** only when you want to send a proposal to the
opened editor. The host checks the plan's game, platform, character and field
IDs against that opened save, then uses the existing validated staging path.
DW8 XL, WO3U and SW4 DX use their registered scalar editor; DW3 translates
supported officer stats and configuration of that same mapped owned weapon
copy into its existing `stage_many` workflow. DW3 catalogue descriptions and
saved equipment references are snapshots, not editable identities.

Staging creates ordinary pending changes. The existing Undo and Review Changes
controls remain authoritative, and the game's current Save As workflow writes
the edited copy. The Workshop itself never serializes or writes a game save.

## Evidence and limits

Tests use procedural parser fixtures and verify mapped choices, dashboard
values, plan serialization, character and weapon comparisons, pending-edit
replacement behavior, rejected mismatches and the DW3 change translation. They do not establish in-game behavior. A plan is
not a promise that the game accepts the proposed build: the registered editor
revalidates every staged value against its current save and supported rules.
Unmapped weapon identities, ownership, prerequisites and formulas remain
outside the Workshop.

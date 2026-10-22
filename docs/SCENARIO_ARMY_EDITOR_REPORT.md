# Scenario and army editor report

This report records the verified scope of the graphical **Scenario View** work.
It is a read-only view of typed records already exposed by strategy-game
presentations. Existing edits continue through each adapter's staged field
editor, Review Changes and safe Save As workflow.

## Machine-readable status

```yaml
status: existing-adapters-only
view: paged-read-only-record-cards
view_data_source: presentation.inspection_tables
new_game_formats: false
new_writable_offsets: false
new_dependencies: []
new_field_write_paths: false
version_changed: false
release_published: false
map_geometry_inferred: false
ownership_or_deployment_inferred: false
```

## Current verified editing scope

| Game profile | Existing writable scope reused by the view | Records displayed | Unsupported edits |
| --- | --- | --- | --- |
| Romance of the Three Kingdoms II, DOS | Selected owned-province Gold and Rice reductions | Province owner ID, resources, population and coordinates | Ownership, army, troop configuration and scenario changes |
| Romance of the Three Kingdoms III, Traditional Chinese DOS | Existing officer abilities and selected city resources/supplies | Save slots, city records and officer records, including existing troops, training and morale | Troop counts, orders, ownership and scenario changes |
| Legend of Liu Bei (ReKO3), Traditional Chinese DOS | Reduce an existing allied character's troop count; edit within-level EXP | Character, army code, existing troops, class/level and item slots | Recruitment, transfers, class, allegiance, item and story changes |
| Romance of the Three Kingdoms XIII, original Windows PC revision 14 | Existing city money, supplies, civilian/military population, wounded troops, fealty, development and troop proficiency values | City resources, population, district reference, development and training | District/force ownership, army deployment and scenario outcomes |
| Nobunaga's Ambition, original English NES 17-fief profile | Existing active-fief Gold and Rice reductions | Fief owner, daimyo, Gold, Rice and native policy | Ownership, troop configuration and campaign changes |
| Nobunaga's Ambition: Tenshouki with Power-Up Kit, original Japanese Windows PC | Existing military-district Gold, Rice, Horse and Firearms stock reductions | Military districts, generals, castles, clans and treasures | Ownership, troop deployment, campaign and outcome changes |

These are the current registered profile scopes, not a claim that all scenarios
or all editions of the named games are supported. Their detailed format and
evidence notes are [RTK II](ROTK2_DOS_FORMAT.md), [RTK III](ROTK3_DOS_FORMAT.md),
[ReKO3](REKO3_DOS_FORMAT.md), [RTK XIII](ROTK13_FORMAT.md),
[Nobunaga NES](NOBUNAGA_AMBITION_NES_FORMAT.md), and
[Nobunaga PK PC](NOBU6_PK_PC_FORMAT.md).

## View behavior and safety

The **Scenario View** tab appears only for the six registered strategy profiles
above. It receives each presentation's existing `InspectionTable` objects and
shows their supplied titles, notes, column labels and opened values as paged
record cards. It does not read a save itself, interpret IDs, infer geography,
calculate troop formations, assign ownership, or offer staging controls. Large
tables are paged; at most 24 record cards are mounted at once.

Editable values remain in the existing **Edit Fields** tab and retain each
adapter's bounds, immutable staging, Undo, Review Changes, backup and verified
Save As behavior. This work adds no binary offsets, write dependencies, or
scenario format. Army deployment, territory transfers and scenario outcomes
remain unsupported as edits unless they are independently qualified in a
separate adapter change.

## Validation boundaries

The automated UI tests verify generic typed-table projection, paging, empty
states, presentation opt-in and read-only display behavior. They do not claim
an edited save loads in its game. The profile notes above state where genuine
copies, controlled before/after actions, or edited in-game load/re-save
validation remain outstanding. Procedural tests remain separate from native
save and game-load evidence.

## Validation run

The focused adapter and inventory regression command covered 97 tests and
finished successfully: 88 passed and 9 skipped because a graphical display or
optional private/native save samples were unavailable. Both Tk rendering
tests skipped because this environment has no `$DISPLAY`.

`python -m tools.update_supported_games --check` passed with 98 registered
profiles. `python -m tools.package_release --verify-only` verified the v3.1
package manifest with 1,188 public source files. Python compilation and
`git diff --check` also passed.

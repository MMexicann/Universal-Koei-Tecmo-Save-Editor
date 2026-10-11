# Original Atelier Ryza — Nintendo Switch

This adapter opens **original Atelier Ryza: Ever Darkness & the Secret Hideout
main-game Switch `data.dat` exports**, native header/app revision 4. It edits
existing ordinary inventory and equipment **quality 1–100**, with a searchable
record inspector. This is a conservative editor range, not a claim that 100 is
the game's natural maximum. Higher opened qualities are preserved and can be
restored to unstage an edit. Max is disabled while quality-cap progression is
unmapped. PC, DX, Ryza 2/3, system files and DLC episodes are not this profile.

## Evidence, serialization and integrity

Two freely shared native main-game slots were acquired from
[Viren070/NX_Saves](https://github.com/Viren070/NX_Saves/blob/main/index.md),
original Switch title `0100D1900EC80000`. Each has a complete 491,876-byte decoded
payload; both native XOR/additive integrity layers validate and unchanged
serialization is byte exact. Saves remain private and are excluded from source
and release assets. No game executable or downloaded editor was executed.

The existing MIT-attributed Gust envelope codec is reused; it is not a new
cross-title schema assumption. Complete root framing, unique root tags,
original preamble, header revision 4 and exact `app_ver` body `BE32(1), BE32(4)`
are checked. `FieldMix`, original Ryza map markers and the absence of Ryza 2's
`AlchemyTree`/`ruin` profile qualify title structure. The Switch item version is
`BE16(1)`, unlike the existing Ryza 2 PC version 2; Party version is `BE16(3)`.

Five inventory pools have exact capacities 200, 100, 5,000, 100 and 50, with
big-endian byte-count prefixes and 66-byte records. Nine Party records have
952-byte native framing; their eight-item equipment arrays have 528-byte
prefixes. Existing unique character identities qualify the named Ryza, Klaudia,
Lent, Tao, Empel and Lila equipment groups. Unknown record bytes remain intact.

Public [SaveWizard field research](https://github.com/sterben-Dev10/SaveWizard-Resources/blob/main/SaveWizard-Codes/Atelier%20Ryza%20Ever%20Darkness%20%26%20the%20Secret%20Hideout%20%5BSaveWizard%5D.txt)
provides a factual 66-byte-record/quality lead. It is independently corroborated
against both Switch slots; no patch implementation, item catalog or source code
was copied. Each native record stores instance ID `LE16 +0`, item ID `LE16 +2`
and quality `LE16 +4`. The adjacent word at `+6` is distinct native data,
nonzero on equipment; public DWORD quality patches would overwrite it. This
adapter admits a quality control only when the adjacent word is **zero**, then
writes only the two quality bytes. Such a write matches the published DWORD
quality writer without changing its zero high word. Nonzero adjacent values
can be related to equipment/synthesis state; their dependency is unproved and
those records stay read only. No normalization or coupled-value guess is made.

Two native instance IDs appear as byte-identical equipment aliases. Exact
aliases involving an equipment region are accepted for inspection, but **all
occurrences of an aliased instance stay read only**. Duplicate inventory-only
ownership, mismatching alias bytes, invalid IDs and unqualified layouts reject
before fields are exposed. Empty, important, zero-quality and `0xffff` sentinel
records stay read only. No item creation, movement, ownership or equip-reference
writes are performed.

Edits retain original seed/header/footer/trailer, recompute the qualified Gust
integrity and reparse the result. Safe reads and atomic Save As use the existing
copied-save guards, changed-source rejection, backups and exact restore. Direct
backups verify the source still matches the opened snapshot. Save As checks
again after encoding and after backup creation, immediately before atomic
publication of the new destination. Party
stats, synthesis-derived equipment data, traits, effects and progression remain
unchanged.

## Mechanics coverage checklist

The [official synthesis manual](https://www.koeitecmoamerica.com/manual/ryza/en/4100.html)
distinguishes recipes, material loops, elements, effects and trait-slot unlocks.
The [synthesis basics guide](https://barrelwisdom.com/ryza/synthesis-basics) records
alchemy/quality-cap dependencies. A displayed quality is distinct from effect
levels, element values, trait levels, item level and derived equipment stats.

| System | Implemented/tested or precise remaining blocker |
| --- | --- |
| Existing ordinary quality | LE16-only 1–100 edits where the adjacent word is zero; searchable native records and higher originals preserved. |
| Higher quality and Max | Requires native quality-cap progression/recipe dependency mappings and controlled synthesis pairs. A public cheat target of 999 is not that proof. |
| Inventory/equipment | Named character groups and searchable pool, slot, item/instance IDs and opened quality. Creation, movement/equip assignments require transfer/equip pairs and applicability mappings. |
| Shared equipment instances | Existing exact aliases inspected read only; controlled equip/transfer pairs needed before changing their shared data. |
| Item names and categories | Native IDs shown; an independently qualified ID/name/applicability catalog is needed. No third-party catalog copied. |
| Quantities/uses/core charge | Distinct record bytes are preserved; controlled count/use/CC action pairs and legitimate bounds needed. |
| Traits/effects/elements | Three existing trait IDs and stored levels are searchable read-only inspection. Trait-slot unlocks, recipe applicability, per-trait level caps and synthesis dependencies remain unqualified for writes; effects/elements are preserved. |
| Nonzero adjacent quality/equipment values | Read only; controlled synthesis/equip pairs needed to establish whether these are coupled, derived or independent. |
| Rebuild and equipment-derived stats | Need native synthesis/rebuild action pairs and dependency schema; quality edits do not invent derived stat recalculation. |
| Cole/gems/resources | Tagged nodes inspected privately; displayed value, preview relationships and natural bounds need controlled earn/spend pairs. |
| Character/alchemy levels and EXP | Tagged/Party leads exist; exact thresholds, stored/derived relationships and rewards remain unqualified. |
| Recipes/quests/collections/exploration | Native tags alone do not establish prerequisite, ownership or reward semantics; controlled unlock/reward pairs needed. |
| Story/events/calendar/DLC episodes | No completion or rewind controls. DLC episode header/layout profiles require separate fixtures and qualification. |

## Tests and scope

`tests/test_ryza_switch.py` uses explicitly non-playable generated buffers for
revision/identity, corruption/framing, ownership aliases, bounds, immutable
snapshots, unusual values, field exclusions, surgical writes and safe-storage
failures. Set `RYZA1_SWITCH_NATIVE_DIR` privately to a directory containing the
two reviewed main-game `data.dat` copies to additionally run native unchanged
roundtrips, all-quality-field byte-preservation edits and copied-file
Save As/backup/restore. With a display, the GUI test uses a selected native copy
and exercises open, inspector, edit, Undo, Review Changes, themes, Save As and
backup restore. Otherwise its fixture is generated and is labelled as such.

`tests/test_ryza_source_safety.py` additionally exercises source changes during
encoding and after backup creation, changed/missing direct-backup sources and
unchanged safe writes/restores for both Ryza 2 PC and Ryza 1 Switch.

These checks establish file/GUI behavior, not edited-save loading or re-saving
inside a Switch game. No game-load validation was performed. Registration,
supported-game inventory and Windows packaging must be integrated and checked
before advertising this editor in a published executable.

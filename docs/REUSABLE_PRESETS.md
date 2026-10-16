# Reusable editing presets

Editing Presets stores named resource plans and applies selected assignments to
another compatible, already opened save copy. It never writes an edited game
save automatically. The original **Edit Presets** dialog and source-bound
`.edits.json` files remain available for exact original copies.

## Create and reuse a plan

1. Open a separate qualified save copy in its exact game/platform editor. Stage
   the resource values you want to reuse.
2. In **Editing Presets**, choose that source editor as the target, then
   **Create from staged edits**. The selection lists qualified resources and
   explains why other fields are excluded. Select resources, enter a name and
   save the local preset.
3. Open another compatible save copy and refresh the target editor list. Choose
   that destination editor. Presets require the same exact game/platform and
   native revision, not the same source-file hash.
4. Choose a named preset and select the assignments to use. **Preview selected**
   shows the entire resulting pending map, including unrelated or hidden edits
   already staged in the destination editor.
5. **Apply reviewed selection** stages that batch as one Undo action. It retains
   unrelated edits. Review and use **Save As** in the destination editor when
   you want to create a separate game-save copy.

Changing the selected assignments, target session, opened source, pending edits
or native field definitions invalidates the preview. Review again before Apply.
The local library is searchable by name, profile, revision and resource field.
Select multiple library entries to export them to a folder; Import accepts up to
64 preset metadata files at once. Existing files are never overwritten. If a
disk operation fails halfway, completed and pre-existing metadata is retained
and the number of completed files is reported.

## Qualified portability

| Exact profile | Reusable fields | Boundary |
| --- | --- | --- |
| DW8 XL Complete Edition, Windows PC | Gold, gems, facility materials, weapon materials | The native PC signature must match. Officer and physical weapon records are excluded. |
| WO3 Ultimate Definitive Edition, Steam PC | Growth points, gems, 58 attribute-orb balances and 295 crafting-material balances | Fixed resource identities only. Promotions, officer allocations, items, mounts, weapons and compatibility are excluded. |
| Dynasty Warriors: Origins, Steam PC | Gold, skill points, DLC skill points where present | Native slot revisions 16, 17 and 29 are separate. The DLC pool exists only in revision 29. Bonds, weapon records, peace and battle flags are excluded. |

Other profiles retain source-bound presets. Matching offsets, field labels or
inventory indices do not prove cross-save record identity. Presets cannot create
characters, acquire items, transfer equipped references or unlock story rewards.
The qualified field list is a reviewed policy, not a rule inferred from a
resource-looking name or an editor's numeric limit.

## Validation and storage

Reusable files use the distinct `.compatible.edits.json` format. Their strict,
bounded JSON contains a name, exact profile/revision, reviewed policy identity,
selected native field-definition fingerprints and typed scalar assignments.
It contains no game-save bytes, player path, account metadata, raw patch offsets
or executable code. The original source-bound schema has not changed.

Target eligibility, current bounds and final dependencies remain authoritative.
The existing bound adapter validates the **complete** candidate pending map,
serializes it in memory and checks the reparsed native values before staging.
The source is requalified before and after preparation and Apply. Applying does
not enable experimental editing; values above supported limits require the
destination editor's existing acknowledgement and normal save confirmation.

Named presets are atomic, immutable JSON documents under the application's
configuration directory in `editing-presets`. Content hashes identify them;
changed or invalid metadata is excluded. The library supports 256 documents and
bounded scans. It stores your chosen values, so share exported presets only when
you intend to share those values and the name you supplied.

Procedural tests and copied-native checks establish file-level behavior.
Edited in-game loading and re-saving remain unverified.

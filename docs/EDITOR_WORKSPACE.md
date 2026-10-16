# Editing workspace

The portable Windows ZIP includes this guide and fourteen companion user guides
in `_internal/guides/`. The full developer documentation remains in the Source ZIP.

Choose an exact game/platform in the library, then open a separate save copy.
The editor retains its document, filters, pending edits and Undo history when
switching to another editor or a conversion/comparison workspace.

The **Open editors** selector resumes an existing session. Entries include the
edition/platform and a live pending-edit count. Choosing an entry does not open
a different file or discard changes. Game Library still provides platform,
series and name/feature search, with the existing illustrated/compact layouts.

**Progression Dashboard** opens first and shows verified opened-save cards.
Use **Edit Fields** for the existing editing controls. Dashboard field links reveal
the matching editable field without staging edits. [Coverage and use](PROGRESSION_DASHBOARDS.md).

The scalar editor's **Categories** sidebar shows the number of editable fields
in each category. `*n` marks its pending edits. A category chooses the same
backend-defined group used by the editor; it does not enable unqualified records.
The **Record** selector narrows it further. **Find fields** searches names,
stable field IDs, record labels, groups and displayed values. **Pending only**
limits the table to staged fields. Counts identify hidden pending edits.

Changed rows have a subtle background in both Light and Dark themes. Opened and
pending values remain separate columns. Use horizontal scrolling to reach wide
record names and columns. **Show editing guide** expands the selected game's
instructions. Selection guidance remains below the table.

Large choice lists have a **Find choices** search. Filtering the dropdown does
not replace the selected native value or stage an edit. Selection guidance
shows opened and current values; mixed bulk selections leave the value blank
until an explicit assignment. **Review Changes** searches names, stable field
IDs, records and raw/formatted values, and shows named choices where available.
Filtering a review does not narrow its exported JSON or CSV: the complete reviewed
snapshot retains raw typed values and stays frozen if later edits change.

**Export Review** writes a JSON change report, while **Save As...** writes an
edited game-save copy. The export dialog suggests a `.changes.json` filename.
You can type a plain name, `.json` or a save-style name such as `APP.BIN`;
the editor completes the review suffix automatically (`APP.BIN.changes.json`).
An existing report is never overwritten; choose a new name to export again.

**Edit Presets...** exports and previews reusable plans for this exact original
save. Import merges with existing pending changes and applies as one Undo action;
it never saves automatically. [Preset guide](EDIT_PRESETS.md).

Pin selected fields from the category sidebar, then use **Pinned only** to focus
on them. Pins are retained per exact game/platform and do not stage edits.
Review Changes can also export a complete typed CSV snapshot or copy selected
rows. [Pins and reviews](FIELD_PINS_AND_REVIEWS.md).

**Save Library** scans a selected copied-save folder for one explicit scalar
profile. Search and sort qualified copies or identify identical gameplay files,
then open a freshly checked copy in its normal editor. Cancelling a pending-edit
prompt preserves the editing session. [Browser guide](SAVE_LIBRARY.md).

**More options** reveals experimental editing and the encoding-limit column.
Hiding the panel does not turn an acknowledged experimental session off or
change pending values. An active experimental warning stays visible below the
table even when options are collapsed. The supported maximum remains visible. The usual
experimental warning, per-field hard constraints and Save As confirmation apply.
Max actions still honor supported limits and fields excluded from Max.

| Key | Action |
| --- | --- |
| Ctrl+F in a scalar editor | Focus and select the field search |
| Ctrl+F in Game Library | Search all platforms |
| Ctrl+F in Save Converter | Focus and select Find route; search game, region, title ID or scope |
| Escape in Find route | Clear the route search; preserve input paths and editor sessions |
| Escape in the field search | Clear search, category, record and Pending only filters; preserve edits |
| Enter in the numeric/text value entry | Apply to the selected fields through normal validation |
| Ctrl+O / Ctrl+S / Ctrl+Shift+S | Open copy / Save As / Save As |
| Ctrl+Z / Ctrl+R | Undo / Review Changes |

Native choice dropdowns, read-only inspection, Adjust Selected, Revert Selected,
Review Changes, automatic backups and new-destination Save As remain available.
DW3 retains its separate tagged editor layout and native editing workflow.

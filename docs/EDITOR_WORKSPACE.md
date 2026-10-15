# Editing workspace

Choose an exact game/platform in the library, then open a separate save copy.
The editor retains its document, filters, pending edits and Undo history when
switching to another editor or a conversion/comparison workspace.

The **Open editors** selector resumes an existing session. Entries include the
edition/platform and a live pending-edit count. Choosing an entry does not open
a different file or discard changes. Game Library still provides platform,
series and name/feature search, with the existing illustrated/compact layouts.

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
| Escape in the field search | Clear search, category, record and Pending only filters; preserve edits |
| Enter in the numeric/text value entry | Apply to the selected fields through normal validation |
| Ctrl+O / Ctrl+S / Ctrl+Shift+S | Open copy / Save As / Save As |
| Ctrl+Z / Ctrl+R | Undo / Review Changes |

Native choice dropdowns, read-only inspection, Adjust Selected, Revert Selected,
Review Changes, automatic backups and new-destination Save As remain available.
DW3 retains its separate tagged editor layout and native editing workflow.

# Field pins and review exports

The shared scalar editors include navigation tools for large saves. Their
availability does not expand the fields a game backend permits editing.

## Keep frequently used fields nearby

Select one or more field rows and click **Pin selected** below the category
list. A star marks each pinned field. **Pinned only** shows the pinned fields
that are qualified in the opened save; it combines with the category, record,
search and pending filters. **Clear** next to the search clears its text; Escape
in the field search clears every field filter, including Pinned only.

**Unpin selected** removes selected pins. Pinning and filtering do not change
save values or add Undo steps. Pending edits and their Undo history remain
available while navigating or switching game sessions.

The application remembers pins for the exact game/platform profile. A field
that is unavailable in another save stays remembered but does not appear until
that backend qualifies it again. A remembered ID never creates a field or
bypasses a game's ownership, revision or dependency checks. At most 256 fields
can be pinned per profile. Preferences contain only the theme and stable field
IDs, without source paths, hashes or save values. A settings-write failure keeps
pins usable in the current session and reports that they could not be saved.

## Share or inspect a change review

**Review Changes** takes a snapshot of all staged changes when its window opens.
Searching the review filters its display. Editing further, undoing changes or
opening another copy does not change that already-open review. Close and reopen
the review to inspect the current pending state.

- **Export Review…** writes the complete snapshot as a `.changes.json` report,
  preserving native integer and text values.
- **Export CSV…** writes the same complete snapshot as `.changes.csv`, including
  game ID, source fingerprint, field ID, group, record, label and typed opened
  and pending values. CSV uses UTF-8 with a byte-order mark for common
  spreadsheet applications and standard quoting. Textual labels that could be
  interpreted as spreadsheet formulas are prefixed with an apostrophe. The
  `opened_json` and `pending_json` columns preserve native values as JSON;
  their neighboring type columns distinguish integers from strings. Spreadsheet
  applications may round large integers on import, so use the JSON report when
  exact machine-readable values are needed.
- **Copy Selected** (or Ctrl+C in the review table) copies only selected, visible
  rows as displayed, with column headings. Filtering never narrows either file
  export.

Both file exports add their report suffix automatically, including when a save
filename was selected. They create new files and never replace an existing
report, save or other file. Reports include source fingerprints and edited
values; review their contents before sharing them publicly.

A review export is a report. Use **Save As…** in the editor to create the edited
game save, with the usual validation, automatic backup and source protection.

The exporter reads back the created report before reporting success. If that
final check fails, any completed or concurrently replaced file is retained.
Treat the export as unsuccessful and choose a new destination before retrying.

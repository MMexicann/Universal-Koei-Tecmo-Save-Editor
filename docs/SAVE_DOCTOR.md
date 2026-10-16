# Save Doctor

Save Doctor checks a separate copied gameplay file against the game and platform
you explicitly select. It shows native validation findings as searchable cards,
explains the available evidence, and exports a privacy-safe diagnostic report.
It never repairs, stages edits, creates save backups, or writes gameplay data.

## Check a copy

1. Choose **Save Doctor**, then the exact game/platform profile.
2. Select the copied gameplay file. Keep any required original companion metadata
   beside it. Archives, whole memory cards, live save folders, Steam Cloud paths,
   links and hard links are not appropriate inputs.
3. Select **Check copied save**. Bounded file reads and native parsing run in a
   background worker. **Cancel check** stops between native operations; an
   already-running codec operation finishes before cancellation takes effect.
4. Search the findings or filter **Needs attention**, **Passed**, and
   **Not established**. Select a card for its explanation and next steps.
5. **Open qualified copy** performs a complete fresh check of the source and its
   original context before using the existing editor Open workflow. The editor
   still performs its own validation and preserves its normal dirty-session,
   backup and saving protections.

A qualified copy has passed its selected native parser, a byte-exact unchanged
serialization check, and source/context freshness checks. Native acceptance
is a combined validator result: it is not a claim that every checksum, revision,
gameplay prerequisite or completion state was independently verified.

## Understand the findings

| Finding | Meaning |
| --- | --- |
| Native checksum failed | The selected validator explicitly reported a checksum failure. No guessed checksum repair is offered. Wrong profiles can also produce such failures. |
| Identity or revision rejected | The parser explicitly rejected a title/revision/layout marker. Save Doctor does not infer which other edition owns the file. |
| Required original context rejected | The validator explicitly identified required original metadata as missing or unacceptable. Do not manufacture account or signing metadata. |
| Copy did not qualify | The parser rejected the copy without an isolated cause. Damage, foreign input, unsupported revisions and missing context remain possible. |
| Native validation unavailable | A runtime or I/O error prevented completion. The file has not thereby been proved corrupt. |
| Unchanged roundtrip | Both the shared adapter and the actual native no-edit serializer preserve the exact opened bytes. DW3 retains its separate tagged parser and writer. |
| Source/context changed | Earlier native results cannot authorize opening. Finish copying/synchronizing the separate export and check again. |
| Compatibility warnings | The native parser accepted the copy with preserved unusual or unfamiliar data. The report includes a warning count, not private saved values. |
| Not established | The native contract does not expose this independent result, or actual game testing is required. Unknown is different from failed. |

Save Doctor uses all currently registered editor profiles. Scalar profiles use
their existing bound adapters. DW3 Remastered uses its own tagged schema and
native no-edit writer; its tagged properties are not relabeled as scalar fields.
No alternative parser is tried after rejection. A matching extension or size
alone never identifies a save.

## Share a diagnostic report

Select **Export diagnostic report**, then choose a new filename ending in
`.doctor.json`. Export creates the report atomically, verifies its actual bytes,
and refuses existing destinations. Report export is brief protected work;
read-only diagnosis and open requalification can be cancelled when closing.

The JSON contains the selected public game/platform, a UTC check timestamp,
file size, mapped scalar-field count where available, compatibility-warning
count where available, and catalogued findings with passed/failed/warning/unknown
states. It excludes filenames, folder paths, hashes, save bytes, saved field
values, account identifiers, companion contents, and raw exception text.

Reports describe a **historical snapshot**, even if the file later changes.
They cannot substitute for fresh opening checks, in-game load/re-save testing,
console signing, or the original export. No report states that a rejected file
can be repaired. Keep an untouched original independently.

## Developer API and validation

`koei_editor.shared.save_doctor.diagnose(game_id, path, cancel=None)` returns a
frozen metadata-only `DoctorResult`. The default single-file bound is 32 MiB;
callers can lower it but cannot raise it. `requalify(result, cancel=None)` returns
the copied path only after fresh complete qualification matches the earlier
source/context snapshot. `report(result)` returns the privacy-safe dictionary;
`export_report(result, destination)` writes it to a new `.doctor.json` file.

The core reuses Save Library's ordinary-path, bounded streaming fingerprint,
native qualification and opaque-context helpers. Windows handle/path ctime
representations are not compared across APIs. No raw document is retained in
the result. Native rejection messages are mapped conservatively to a closed
guidance catalogue; ambiguous messages stay unclassified. Parser error text is
never placed in a report.

The Tk workspace is `SaveDoctorWorkspace(root, parent, on_open=None)`, exposing
`.frame`, `.apply_theme(palette)`, `.focus_search()`, `.close()` and
`.has_pending_work()`. Workers never call Tk. Late cancelled or selection-stale
results cannot navigate into an editor. Only an in-flight atomic report export
counts as protected pending work; checking itself creates no pending edits.

Public tests exercise genuine parser/codec behavior on procedural PC, PS3 and
tagged DW3 inputs, explicit checksum and identity rejection, truncation, missing
context, source/context races, cancellation, unknown-result semantics, no-write
behavior, stale-open prevention, privacy, atomic export replacement detection,
and actual Tk worker/theme/navigation behavior. Procedural inputs are not player
saves or evidence of game loading. Optional copied native PC coverage uses
`DW7XL_SAVE_COPY`; missing copies are reported as skips.

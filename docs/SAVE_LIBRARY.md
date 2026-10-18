# Save Library

Save Library helps you find and open separate save copies without editing,
converting or reorganizing their files. Choose the exact game and platform,
then choose your copied-save folder and start a scan.

## Browse your copies

1. Keep saves outside the game's live save folder and Steam Cloud folders.
   Keep each copy's required original console or account metadata beside it.
2. Open **Save Library**, select the matching game/platform, and choose the
   folder containing your copies. Enable **Include subfolders** when needed.
3. Click **Scan copied folder**. Search by relative filename/folder, filter
   qualified or rejected results, or show identical gameplay files. Sort by
   path, date, size or duplicate group.
4. Select a qualified copy and click **Open selected copy**. The browser checks
   the save and its original context again, then the normal editor opens it.
   If anything changed, scan the copied folder again.

**Ctrl+F** focuses the copy search. Opening still respects the editor's pending
edits: cancelling its discard prompt keeps that session and leaves the browser
open. You can cancel an Open request until it is handed to the normal editor.

The results show the relative copied-file path, byte size, modification time in
UTC and validation status. The selected result explains its status and the
number of mapped editable fields. A zero-field result can still be a readable
qualified state; it does not promise additional editable fields.

This browser uses the registered scalar editor profiles. Dynasty Warriors 3's
separate document workflow is not included. A filename or extension alone does
not establish game identity. Only the selected game's normal reader qualifies a
copy; the browser never tries another game after rejection.

## Identical files

An **Identical gameplay bytes** group contains separately qualified files with
matching gameplay-file size and SHA-256. The group does not compare whole
folders, determine account ownership or establish identical original context.
For example, two files may contain identical gameplay bytes while each retains
different valid console metadata. A copy missing required metadata remains
**Not qualified**, even if its gameplay bytes match a qualified copy.

The browser never deletes, moves, repairs, merges or deduplicates files. Open a
copy through the normal editor to review and save deliberate gameplay edits.

## Scan limits and cancellation

A scan processes at most 500 candidate files and visits at most 5,000 directory
entries. Candidate files must match the selected profile's extension, including
extensionless profiles. Individual gameplay files are limited to 64 MiB; the sum
of candidate file sizes admitted for qualification is limited to 128 MiB.
Qualification may read admitted files more than once to detect changes. Files
above a limit remain unsupported by this browser even when another workflow can
open them.

Recursion is off by default and never goes deeper than three levels below the
selected folder. Linked files, hard-linked file aliases, linked directories,
Windows junctions/reparse points, special files and protected live/cloud paths
are excluded. Original context must also remain ordinary separate files. An
excluded directory may contain additional files that were not examined.

**Cancel scan** stops between bounded read/qualification operations. An active
native parser finishes its current bounded operation before cancellation takes
effect. Cancelled or limited scans are labelled **partial results**. Only fully
qualified entries completed before cancellation are retained. A partial scan
does not establish that other copies or duplicate groups are absent.

Scan results are historical metadata. They are not a live folder monitor, a
promise that the game can load an edited save, or permission to bypass normal
editor validation. Refresh the scan after changing copies or metadata.

## Diagnostic summaries

The backend's optional diagnostic summary contains profile, status counts,
limits reached and identical-gameplay-file group counts. It omits local paths,
filenames, gameplay values, file hashes, original context and account metadata.
The local file selection and table intentionally show the folder/files you
chose. Inventories retain neither save payloads nor document objects and are not
saved automatically.

## Command line

Scan copies without opening a window:

```powershell
.\UniversalKoeiTecmoSaveEditor.exe --game wo3u --scan-saves "D:\SaveCopies" --recursive
```

From an installed source checkout:

```text
python -m koei_editor --game wo3u --scan-saves ./SaveCopies
```

An explicit registered scalar game/platform profile is required. DW3 and
research workflows are excluded. `--recursive` is optional and applies only to
`--scan-saves`; the same fixed scan bounds and path protections apply as in the
browser. Run scanning separately from editing, self-tests, conversion,
comparison and list commands. It creates no gameplay outputs, backups or report
files.

The command prints the backend's diagnostic JSON summary to standard output.
It contains status counts and historical scan scope, without local paths,
filenames, file hashes, gameplay values or original context. Qualification still
requires the normal editor reader before opening or editing a selected copy.

| Exit code | Meaning |
| --- | --- |
| `0` | Traversal completed within the selected scope, with at least one candidate and every candidate qualified |
| `1` | Completed with rejected/skipped/changed/unreadable candidates or no qualified copies; also used when the scan itself fails |
| `2` | Invalid arguments, combined workflows or an unsupported profile |
| `3` | Partial traversal, such as reaching the file, directory-entry or byte limit |

A completed or partial inventory prints JSON even when its exit code is `1`
or `3`. Invocation and scan failures print a short diagnostic to standard error;
they do not fabricate an inventory. Excluded directories may contain additional
unexamined files, and a partial scan does not prove other copies are absent.

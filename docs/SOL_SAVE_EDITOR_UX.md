# Sol save-editing UX report

```yaml
report_schema: 1
status: draft_pull_request_open
base: main
base_commit: 1955b73
full_suite_base_commit: c851ee5
pull_request: 138
pull_request_url: https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/pull/138
release_or_version_change: false
registered_profiles: 98
shared_scalar_profiles: 97
dedicated_profile: dw3
```

## Scope

This change improves the shared scalar editor used by 97 registered game and
platform profiles. Dynasty Warriors 3 Remastered remains on its separate tagged
schema editor; its existing search, bulk actions, equipment controls, previews,
Undo, review and save protections remain in that workflow. The change does not
duplicate those controls or move DW3 into the scalar adapter contract.

## Changes

| Area | Behavior | Safety boundary |
| --- | --- | --- |
| Field table | Renders 250 matching fields per page, reports filtered totals and page range, and sorts the full filtered catalog before slicing. | Pending edits stay in the complete session map when hidden or off-page. |
| Search and navigation | Searches stable IDs, labels, groups, records, opened values and pending values; looks up long choice labels only when raw text does not match. Enter on an exact ID clears hiding filters, jumps to the correct page and selects the field. | Search does not grant field access; backend mapping and validation stay authoritative. |
| Bulk editing | Selected actions target selected rows. “Max Visible Fields” targets the current page, with its scope stated next to the controls. | Existing complete-batch validation and one-action Undo are retained. |
| Undo | Ctrl+Z follows the focused editor session; the existing Undo button remains available. | Undo validates the complete restored pending map before changing history. |
| Comparisons | From an opened scalar editor, Compare Saves inherits that exact profile and destination snapshot. Selected value-change rows can suggest transfer candidates. | The handoff pins the second-copy SHA-256 and uses the existing qualified transfer catalog, complete preview, source checks and one-Undo staging. Unsupported profiles have no transfer action. Comparison never writes save files. |
| Definition identity | Comparison now reuses the canonical preset field metadata fingerprint, including field class and declared storage/choice/dependency metadata while excluding value-dependent numeric limits. | Semantically different definitions are shown separately from ordinary value changes. |

## Reused infrastructure

- `BoundScalarAdapter` continues to validate the complete pending map, retain
  exact opened values as no-ops, reparse edited output and verify Save As
  read-back.
- `edit_presets` supplies canonical field metadata and complete assignment
  previews; comparison does not introduce a second preset planner.
- `save_transfer.catalogue()` remains the authority for portable identities,
  ownership and exclusions. The comparison only preselects candidates that the
  catalogue accepts.
- Existing automatic backups, Review Changes, experimental limits, source
  revalidation and new-copy writes remain in place.

## Architecture findings and remaining limits

The scalar Treeview previously rendered and sorted the entire matching result
on every refresh. Paging bounds widget work and global sorting keeps page order
consistent. Filtering still scans the mapped catalog synchronously for each
query change; very large catalogs may benefit from debounced or cached search
metadata. Existing preset preview tables can also render large imported batches.

The comparison-to-transfer path was not reachable from the application shell,
and its old field identity check did not include the full declared semantic
metadata. The application now binds the comparison workspace to the active
opened scalar session, and the comparison uses the shared preset fingerprint.
DW3 remains outside this shared path because its tagged document and audited
writer are intentionally bespoke.

## Automated evidence

| Check | Result | Notes |
| --- | --- | --- |
| Full test inventory at prior base `c851ee5` | 3,413 tests across 370 modules; 0 assertion failures; 962 skips; 2 errors | One existing `test_rotk3_dos.py` Tk test calls `tk.Tk()` without a display guard. The other is `test_universal_packaging.py::test_distinct_registered_scalar_backend_is_collected`: its fixture lacks `achievement_source`, added by merged main change #111. `tools/build_windows.py` and that test are unchanged in this branch. |
| Current-base focused integration command | 121 tests; 0 failures; 62 skips | Run after rebasing onto `1955b73`; includes comparison, transfer, presets, scalar navigation, and application shell. Tk cases need a display. |
| New paging/comparison regression modules | 13 tests; 2 passed; 11 skipped | The opened-value identity regression passed. All paging and Tk handoff/focused-Undo cases require a display. |
| New paging and Undo focus tests | 6 discovered; 6 skipped locally | Includes two retained editors sharing a root; the focused editor alone handles Ctrl+Z. See [test_scalar_field_paging.py](../tests/test_scalar_field_paging.py). |
| New comparison handoff tests | 7 discovered; 2 passed; 5 skipped locally | Backend definition-identity regressions passed; Tk integration cases require a display. See [test_comparison_transfer_experience.py](../tests/test_comparison_transfer_experience.py). |
| Package source verification | Passed; 1,220 public source files verified | Source manifest refreshed after rebasing onto the current main; no version change. |
| Supported game inventory | Passed; 98 registered profiles checked | No game or platform support changed. |
| Application smoke test | Not completed | The runner cannot create a Tk window without `$DISPLAY` or Xvfb. |

The full run report and per-module logs were written under the ignored local
`work/` directory. Native saves and private fixtures were not added to the
checkout. PR #138 is a draft for review; no release, version bump or merge was
performed.

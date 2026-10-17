# Reviewed automation and batch editing

Development source adds reusable scalar workflows and a headless automation CLI.
The published application remains v2.7; these changes do not publish a new binary.
Automation uses the same registered `BoundScalarAdapter`, native validation,
backups, read-back verification and new-destination `save_as` as the editors.
DW3's tagged patch workflow and research tools retain their existing commands;
they are excluded from this scalar automation interface.

## Build a workflow without code

Open **Workflow Builder** from the Game Library footer. Choose the exact
registered game/platform and open a separate reference save copy outside live
game and Steam Cloud folders. Search verified field IDs/labels, enter values,
and add **New set group** or **Assert current value** operations. Select a set
group and use **Add to selected set** to change dependency-related fields
together. Reorder/remove operations as needed. Native validators check each
complete set group; an assertion observes the value at its position in the
sequence. A failed assertion stops preflight.

**Preview reference** validates the sequence against the opened immutable copy.
**Preview other copies** qualifies each target using the selected native parser;
matching extensions alone never establish compatibility. Every field must exist
in each target's verified records. Unknown fields, wrong revisions, missing
original context, unsupported values and invalid native dependencies fail before
saving. Workflow fields are explicit assignments, not inventory transfers or
progression conversion. Select dynamic IDs carefully and add assertions when a
sequence relies on particular opened/current values.

**Export workflow** writes a new `.workflow.json` metadata file after a successful
reference preflight. **Export batch plan** lets you choose multiple source copies
and an output directory, assigns distinct new filenames, and validates all jobs
before writing a local `.batch.json` plan. No gameplay files or backups are
created by the builder. Batch plans contain local paths: keep them private.
Exporting does not approve a future write; review that batch through the CLI.

## Inspect, build and preview from the command line

Run from an installed source checkout (Python 3.10+) with the same package entry
point as existing tools. `--automation` must be the first option. All automation
results are JSON on stdout; help is ordinary argparse text. Examples below use
PowerShell and separate copied saves:

```powershell
python -m koei_editor --automation --help
python -m koei_editor --automation fields --game dw8xl 'D:\SaveCopies\first.dat'
python -m koei_editor --automation build --game dw8xl --name 'Set copied gold' `
  --set 'gold=12345' --assert 'gold=12345' --output 'D:\Plans\gold.workflow.json'
python -m koei_editor --automation preview 'D:\Plans\gold.batch.json'
python -m koei_editor --automation apply 'D:\Plans\gold.batch.json' --dry-run
```

Consecutive `--set` options form one dependency-validated assignment group.
Values use JSON scalar syntax: an exact whole number or a JSON string. Booleans,
floats, nonfinite numbers and unrecognized operations are rejected. Use
`fields` to discover actual IDs and bounds for the explicitly opened copy.
`build` validates the workflow structure; preview validates native eligibility
and dependencies before execution. Experimental numeric limits are excluded.

A batch embeds its workflow and explicit jobs. Paths below are relative to the
batch plan's directory; absolute paths are also accepted:

```json
{
  "schema_version": 1,
  "workflow": {
    "schema": "koei-automation-workflow",
    "version": 1,
    "name": "Set copied gold",
    "game_id": "dw8xl",
    "operations": [
      {"op": "set", "values": {"gold": 12345}},
      {"op": "assert", "field": "gold", "value": 12345}
    ]
  },
  "jobs": [
    {"id": "first", "source": "../copies/first.dat", "destination": "../results/first.dat"},
    {"id": "second", "source": "../copies/second.dat", "destination": "../results/second.dat"}
  ]
}
```

Workflows are bounded to 4 MiB, 2,000 operations and 20,000 assignments; batches
have at most 32 jobs and a 512 MiB total source budget. Unknown/duplicate JSON
properties, malformed UTF-8 and unsupported schema versions fail closed. Saves
requiring companion metadata must keep their exact original qualified context;
automation does not invent account/signing bytes or copy metadata from another
profile. Save As remains authoritative and may reject an unsupported target
context even after in-memory preview.

## Review and apply

Preview returns a `review_token`, hashes and per-job field differences. Inspect
the changes, then pass that exact token to `apply` and choose a new journal
folder. Changing a source, workflow, destination, verified field definition or
expected serialized output invalidates approval.

```powershell
$preview = python -m koei_editor --automation preview 'D:\Plans\gold.batch.json' | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $preview.success) { throw 'Preview failed' }
$preview.jobs | ConvertTo-Json -Depth 10
# After reviewing the displayed assignments:
python -m koei_editor --automation apply 'D:\Plans\gold.batch.json' `
  --review-token $preview.review_token --journal 'D:\RunLogs\gold-run-001'
if ($LASTEXITCODE -ne 0) { throw 'Inspect the JSON result and journal before retrying' }
```

Every job must pass preflight and source-freshness checks before execution starts.
Sources are rechecked during execution. Outputs must be distinct new files;
existing saves are never replaced. The executor stops on the first failure,
retains completed copies and backups, and marks later jobs `not_started`. A
batch is not a filesystem transaction: completed copies remain if a later job
fails. Inspect partial results before doing anything further.

Source-bound presets remain exact-source plans:

```powershell
python -m koei_editor --automation preset-preview 'D:\Plans\build.edits.json' `
  'D:\SaveCopies\original.dat' 'D:\Results\edited.dat'
# preset-apply takes the same paths plus --review-token and --journal.
```

They accept the original or byte-identical copies, preserving the preset's exact
profile/source checks. General workflows qualify every compatible target anew;
they do not relax the preset's binding rules.

## Failure reporting and recovery

Exit code `0` means success, `2` means rejected input/preflight, and `3` means a
stopped or ambiguous execution. Check both exit code and JSON `success`.
`error_code` is stable; raw native exception text and local paths are omitted.
Field values in previews may be private names; keep detailed review JSON local.
Do not use report redaction as permission to publish save-derived values.

Execution journals contain append-only metadata events written through existing
atomic storage, with intent before a save and completion after native read-back.
They contain job IDs and hashes, never save bytes or paths. Recovery always uses
the explicit original plan and current source qualification. An interrupted
intent is evidence of an attempted write, even when no destination exists; it
must never be silently replayed. Unknown, replaced or damaged outputs remain
blocked. Preserve the journal, source copies, backups and partial outputs.

```powershell
python -m koei_editor --automation recover 'D:\Plans\gold.batch.json' `
  --journal 'D:\RunLogs\gold-run-001'
```

This read-only command reconstructs the original review, requalifies current
sources and parses any completed destinations through their native adapters.
It reports `pending`, `completed`, `recovered` or `blocked`; a recovered output
has the exact reviewed digest but lacks a completion event. It never follows
paths from a journal, deletes partial files, or automatically resumes a write.
For genuinely unstarted jobs, create a fresh plan and new destinations, preview
again, then apply with a new journal. Keep the original run evidence intact.
Source-bound preset runs can be inspected through an equivalent explicit batch
plan; the original source/profile and assignment group must remain identical.

## Developer integration

Use `koei_editor.shared.automation.Workflow`, `Operation`, `JobSpec`, `prepare`,
`preview` and `apply`. A `set` operation holds a tuple of `(field_id, value)`
assignments; an `assert` holds one expected field/value. Build frozen operations
from reviewed IDs, then prepare all jobs with explicit source/destination paths.
`prepare` is read-only and uses the registered adapter; `apply` rederives the
complete plan, verifies its review token and delegates every save to
`BoundScalarAdapter.save_as`. Use `RunJournal` for durable execution; the CLI
requires it. Never serialize bytes directly to a save destination.

JSON workflow documents supply data only: no Python imports, scripts, arbitrary
offsets, shell commands or unvalidated converter selections. Existing
[conversion CLI and batch queues](BATCH_CONVERSION.md) remain separate scoped
workflows with their own reviewed routes. Benchmark and reproducibility guidance
is in [AUTOMATION_BENCHMARKS.md](AUTOMATION_BENCHMARKS.md). Public generated fixtures
exercise invariants; they do not establish genuine-file qualification or edited
in-game load/re-save success.

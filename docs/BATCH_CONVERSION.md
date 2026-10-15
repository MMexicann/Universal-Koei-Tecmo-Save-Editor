# Batch Converter

Batch Converter reviews up to **32 independent conversions** across the
**138 development routes** (the published v2.5.1 app has 20). Every job needs its own explicit route, separate source
and destination-template copies, and a new output folder. It preserves each
route's selected scope: DW6 has four partial scopes, from roster/horses through
persistent records, Musou run slots, gallery and challenges; DW8 XL and
Persona 5 Strikers transfer their supported common gameplay.

## Use the workspace

1. In Save Converter, choose a route and both copies, then review the conversion.
2. Select **Add reviewed job to batch…** and choose a parent plus a new folder
   name for this output. Repeat for additional conversions.
3. Open **Batch Converter** and select **Review all jobs**. Every source,
   template, original companion and output path must pass before export begins.
4. Select a job to inspect its transfer scope. **Export reviewed copies** runs
   the queue, with progress for each job, automatic input backups and actual
   destination read-back through the existing converter.
5. Optionally save the combined batch report. Completed outputs and their
   original per-copy receipts are checked again before saving that report.

Queue selections and results remain while switching workspaces. **Stop after
current copy** finishes the active verified copy and leaves remaining jobs
unstarted. If a later job fails, completed verified copies remain in their new
folders, the failed job is reported, and subsequent jobs do not start. This is
an explicit partial result; it does not claim that the whole queue succeeded.
Original gameplay files and console metadata remain unchanged.
Files from a failed job are retained and must not be imported, even if a receipt
was already created. Re-review and retry that job into a different new folder.
Completed jobs remain separate from failed output.

Save/load a private JSON plan to retain queued selections across launches.
**Plans contain local paths**, unlike the combined result report. Keep plans
private when those paths are personal. Removing or clearing jobs changes the
queue; it does not remove exported files. Existing output folders, including
empty ones, are never replaced. A completed queue needs new output folder names
to be run again.

## Headless plans

Paths can be absolute or relative to the plan file. IDs are unique, 1–64 ASCII
letters/numbers/dashes/underscores. JSON keys, route IDs and profile paths are
explicit; unknown keys, duplicate keys, overlapping output folders and oversized
plans are rejected. The plan limit is 1 MiB.

```json
{
  "schema_version": 1,
  "jobs": [
    {
      "id": "dw6-to-ps3",
      "route": "dw6-to-dw6_ps3",
      "source": "copies/pc/save.dat",
      "template": "copies/ps3/APP.BIN",
      "output_dir": "exports/dw6-ps3"
    }
  ]
}
```

```text
python -m koei_editor --batch-convert plan.json --dry-run
python -m koei_editor --batch-convert plan.json --batch-report batch-result.json
```

Dry run alone writes no files or backups. If `--batch-report` is explicitly
supplied with dry run, only the requested JSON review is written. Execution
returns a nonzero exit status for a partial/failed result. Keep the combined
report outside individual converted-save folders; its destination is checked
before exporting. Existing report/plan files are never replaced.

Input dependencies between jobs are excluded: every input must already exist
and qualify during complete preflight. Stop-at-boundary behavior is available
in the GUI; forcibly terminating a process can leave a new output folder for
inspection. Source copies remain protected, and per-copy receipts/hashes identify
verified completed outputs.

## Preservation and validation

Prepared batches bind immutable native reviews to exact routes, copied inputs
and distinct resolved destinations. Every input is rechecked before any export;
each individual converter also rechecks its own source, template and companions
around backups and actual destination writes. A changed or forged review is
rejected. Partial reports keep completed, failed and unstarted jobs distinct.
Failure reports store a category and retry guidance, excluding exception text
that could expose escaped OS paths or private backup names. Review a failed job
again for the local validation diagnosis.
The final report verifies actual completed output bytes, original target
metadata and stored per-copy receipts against frozen review hashes.

Public tests use generated data. They cover mixed DW6/DW8 XL/Persona families,
PS3/PS4 companion handling, conversion-only PS4 endpoints, relative plan
roundtrips, rejected collisions, changed inputs, late failure, stop boundaries,
forged reviews/receipts, actual Tk workers and CLI. An independently acquired
native DW6 PC/US PS3 pair also passes queued exports in both directions.

Console decryption, reimport and signing remain external. Batch conversion does
not extend a route's format coverage, qualify additional game state, establish
new scalar editors or prove that converted copies load in-game.
DW6 Xbox output includes an unchanged original CON containing old template
gameplay; apply the raw export with an external save manager before rehashing/
resigning. See [the conversion workflow](SAVE_CONVERSION.md).

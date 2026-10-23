# Command-line interface

The Toolkit CLI inspects and compares save copies, reviews conversions and runs
explicit scalar editing workflows. Commands do not open the graphical editor.
The GUI-only planning, mod and configuration workspaces are not CLI commands.

## Start

On Windows, download **UniversalKoeiTecmoGameToolkit-v1.0-CLI.exe** from the
[Toolkit 1.0 release](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/releases/tag/toolkit-v1.0).
It is a standalone console application and requires no Python installation.
Run it from PowerShell or Command Prompt:

```powershell
.\UniversalKoeiTecmoGameToolkit-v1.0-CLI.exe --help
.\UniversalKoeiTecmoGameToolkit-v1.0-CLI.exe --version
.\UniversalKoeiTecmoGameToolkit-v1.0-CLI.exe games --json
```

From an installed source checkout, use `universal-koei-toolkit` or
`python -m koei_editor.cli`. Source installation retains the application's
Python 3.10+ and Tkinter requirements; headless commands do not create a Tk
window. The examples below use `universal-koei-toolkit`; substitute the EXE
name when using the native download. No arguments show help.

The graphical editor remains available through `python -m koei_editor` and
`universal-koei-editor`. Its existing flag-based commands also remain usable.

## Inspect and compare

Use exact profile IDs from `games`. Different editions and platforms are separate
profiles; rejected files are never retried with another game's parser.

```powershell
universal-koei-toolkit games --json
universal-koei-toolkit routes --json
universal-koei-toolkit fields --game dw4hyper 'D:\SaveCopies\first.dat'
universal-koei-toolkit compare --game dw4hyper 'D:\SaveCopies\first.dat' 'D:\SaveCopies\second.dat'
universal-koei-toolkit scan --game dw4hyper 'D:\SaveCopies' --recursive
universal-koei-toolkit doctor --game dw4hyper 'D:\SaveCopies\first.dat'
universal-koei-toolkit discover --steam-root 'D:\Steam'
```

These commands do not edit saves. `compare --report NEW.json` optionally writes
a new JSON report. Save Library scans return aggregate, path-free summaries;
Save Doctor diagnoses without repairing input. Discovery observes supported
Steam installs and known save folders, not every game or launcher.

`games --json` returns the `koei-toolkit-games` schema with exact profile IDs,
editions, platforms, scope and file-qualification flags. `routes --json` returns
the `koei-toolkit-routes` schema with explicit endpoints and transfer scope.
Both use `schema_version: 1`, `read_only: true` and `in_game_verified: false`.
Game file qualification does not establish edited-save loading in the game.

Catalog searches use case-insensitive text matching. Platform names and
conversion endpoints must match the catalog exactly; misspelled selectors are
rejected. Filters preserve catalog ordering and route-specific transfer scope:

```powershell
universal-koei-toolkit games --query 'dynasty warriors' --platform 'Windows PC' --json
universal-koei-toolkit routes --from-game dw6 --to-game dw6_ps3 --query campaigns --json
universal-koei-toolkit games --query nioh --output 'D:\Reports\new-catalog.json'
```

Filtered JSON reports count the returned entries. `full_profile_count`,
`full_platform_count` and `full_route_count` retain the complete catalog totals.
An empty result is a successful search, not a new compatibility claim. Reports
record whether a query was used without retaining its raw text.
`--output NEW.json` explicitly creates a new JSON report, regardless of the
stdout format. Choose an existing ordinary folder; no directories are created.
Existing files and aliased report destinations are refused;
an export failure returns nonzero without printing a success result.

## Support diagnostics

```powershell
universal-koei-toolkit diagnostics
universal-koei-toolkit diagnostics --json --output 'D:\Reports\new-support.json'
```

The support report contains the application version, source/frozen mode, OS
family, architecture, Python version, catalog counts and allowlisted dependency
metadata. It omits personal paths, usernames, hostnames, environment values and
installed-game scans. Export is explicit and new-only.

Dependency metadata availability does not prove that native decoders import or
that every feature works. The report distinguishes metadata that is missing,
unavailable or outside the reviewed version format. Save Vault and Playthrough
Profiles require Windows even from source; that platform limitation is reported
as scope, not inferred data corruption. Destination checks still apply on
supported platforms.

## Review a conversion

Conversions need a separate source copy and a qualified destination-platform
template. Inspect the listed route's field scope before exporting:

```powershell
universal-koei-toolkit convert dw6-to-dw6_ps3 --source 'D:\SaveCopies\pc.dat' `
  --template 'D:\SaveCopies\ps3\APP.BIN' --dry-run
universal-koei-toolkit convert dw6-to-dw6_ps3 --source 'D:\SaveCopies\pc.dat' `
  --template 'D:\SaveCopies\ps3\APP.BIN' --output-dir 'D:\Results\new-copy'
universal-koei-toolkit batch-convert 'D:\Plans\conversions.json' --dry-run
```

`convert --dry-run` creates neither output nor backups. Actual exports require
a new destination and preserve native template companions. A batch's optional
`--report NEW.json` explicitly writes a review report even with `--dry-run`.
See [conversions](SAVE_CONVERSION.md) and [batch plans](BATCH_CONVERSION.md).
Console reimport, decryption and resigning remain external steps.

## Edit through a reviewed workflow

`automation` forwards to the existing workflow engine, preserving its ordered
assertions, native bounds, source-freshness checks, backups and new-copy writes.
It supports `fields`, `build`, `preview`, `apply`, `recover`, `preset-preview`
and `preset-apply`. Use `automation --help` and each command's `--help`.
The [automation guide](AUTOMATION.md) defines batch JSON and review requirements.

```powershell
universal-koei-toolkit automation preview 'D:\Plans\edits.batch.json'
universal-koei-toolkit automation apply 'D:\Plans\edits.batch.json' --dry-run
$review = universal-koei-toolkit automation preview 'D:\Plans\edits.batch.json' | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $review.success) { throw 'Preview failed' }
$review.jobs | ConvertTo-Json -Depth 10
# Review the assignments before executing:
universal-koei-toolkit automation apply 'D:\Plans\edits.batch.json' `
  --review-token $review.review_token --journal 'D:\RunLogs\new-run'
```

Apply requires the exact token from a fresh preview and a new durable journal
folder. A changed source or workflow invalidates the review. Existing
destinations are refused. Batches stop on failure; already completed copies
remain available for inspection and recovery. Experimental editing and the
separate DW3 workflow are excluded from scalar automation.

## Output and exit codes

Help, version and human inventories/diagnostics are text. `games --json`, `routes --json`,
`diagnostics --json`,
inspection, comparison, scan, diagnosis, discovery, conversion and workflow
results are JSON on stdout. Human errors use stderr; rejected automation
commands retain their structured JSON error on stdout. Do not treat a parsed
JSON document alone as success: check both the exit code and result status.

| Code | Meaning |
| --- | --- |
| `0` | Command completed; inspect diagnostic status and warnings. |
| `1` | Legacy save operation failed, or a scan found rejected/unqualified copies. |
| `2` | Invalid command arguments, or a rejected automation/field operation. |
| `3` | A scan stopped at a limit, or automation stopped with incomplete/ambiguous work. |

Save Doctor prints diagnostic JSON even when it returns `1` for a rejected or
unqualified copy. In-game loading remains unverified. Use copied saves outside live game and cloud folders.

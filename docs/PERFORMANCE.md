# Measuring application performance

The application library uses `LibraryCatalog` to normalize searchable metadata,
classify series and sort profiles once per registry snapshot. Each query scans
the indexed strings and returns the original registered game objects. Queries
are not cached, so typing new searches does not retain an unbounded history.
Rebuild the index when replacing or extending the registry; this index does not
load editors, select parsers or inspect saves. The iterable `matching_games`
helper remains available for callers that do not retain an index.

## Repeatable benchmark

From an installed source checkout, run:

```text
python -m tools.benchmark_application --samples 5 --iterations 100 --output work/performance.json
python -m tools.benchmark_application --gui --samples 5 --iterations 100 --output work/performance-gui.json
```

The GUI mode requires a real desktop or a display such as Xvfb on Linux. It uses
temporary preferences and registry metadata, never player saves. Reports include
the local source checkout path; review them before sharing.

Each sample uses a fresh interpreter. Timing runs execute with tracemalloc off;
separate memory runs measure Python allocations. The JSON report includes the
Python version, operating system, installed application's source revision,
runtime source SHA-256, query result IDs and sample count, plus median, minimum
and p95 for each metric. Five-sample p95 is simply the largest sample; increase
the count for meaningful distribution estimates. File-system caches are not
flushed, so import timings are process-cold, not disk-cold.

Measured operations:

- Application import, excluding interpreter launch and benchmark setup.
- Catalog construction and average warm query time over twelve fixed searches,
  including result-ID materialization and consistency checks.
- Catalog/search Python retained and peak allocations, excluding imports.
- Shell startup, including Tk root construction and initial idle rendering,
  excluding application import; widget and imported-module counts at that point.
- First All-platform navigation, then six warm platform switches with idle
  rendering, and the number of filter renders from six immediate text changes.
- Shell startup Python peak allocations in a separate run. Tk's native widget,
  font and image memory is not included; widget counts provide additional context.

The search burst processes the real Tk event loop for 250 ms to allow scheduled
filter updates to finish and verifies the final result. The intentional wait is
not reported as search latency. Navigation excludes editor construction and
game-specific dashboards. These measurements do not characterize parsing,
editing or save storage.

## Comparing revisions

Create a separate checkout and an isolated Python environment for the baseline,
then install that checkout with `python -m pip install -e .`. Run the **same
benchmark harness** with the baseline interpreter:

```text
python -m tools.benchmark_application --python /path/to/baseline-venv/bin/python --gui --samples 5 --output work/baseline.json
python -m tools.benchmark_application --gui --samples 5 --output work/current.json
```

On Windows, use the corresponding `Scripts/python.exe` path. The selected
interpreter must have the subject application installed; the harness imports it
normally and records its actual source path and hash. It supports older
revisions without `LibraryCatalog` by using their existing iterable search.
Compare reports only when game counts and query results agree. Use the same
machine, Python, display resolution/scaling and workload; avoid concurrent test
runs. Repeat on Windows before making Windows startup, high-DPI or EXE claims.

Retaining the search index trades a small, bounded amount of metadata memory
and one startup preprocessing pass for lower repeated-query work. Shell startup
and widget counts can remain unchanged where compatibility requires eager card
creation. Report neutral measurements and regressions alongside improvements.

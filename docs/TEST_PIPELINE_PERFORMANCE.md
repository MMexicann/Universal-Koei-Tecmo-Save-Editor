# Parallel test and build performance

The runner still discovers every test module and executes it in an isolated
process. Four Windows shards each use two workers. Scheduling hints affect
placement only: missing, overlapping, stale, failing or incomplete reports
cannot authorize a build.

## v1.8 changes

Desktop modules use one slot per job so Tk clipboard/focus operations remain
serialized. The dispatcher fills other available slots with CPU modules instead
of assigning a second desktop module that blocks while holding a worker.
Shard balancing accounts for both total worker load and serial desktop load.
Timing hints now cover every module using the complete 225-module
[v1.8 Windows validation run](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/actions/runs/38159065310).
They replace the prior official v1.72 measurements and supplemental local
estimates. Timing hints affect scheduling only; they do not authorize skipped
or omitted checks.

Packaging already validates the complete executable, metadata, archive and
privacy boundaries. The Windows build no longer performs an immediately
preceding duplicate executable scan. Packaged GUI startup and all validation
inside packaging remain required.

Source fingerprints explicitly sort relative POSIX path strings. Windows and
Linux therefore produce identical fingerprints for identical source bytes,
without altering path spelling or excluding any reviewed source.

## Measured comparison

The [official v1.72 run](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/actions/runs/38150230797)
and a [nonpublishing optimization benchmark](https://github.com/MMexicann/Universal-Koei-Tecmo-Save-Editor/actions/runs/38152421929)
used the same 212-module game/test inventory; the benchmark additionally ran
four scheduling/package regression checks. Its reports accounted for all 1,822
tests, including 424 explicit skips, with no failures or errors.

| Comparable measurement | v1.72 | Optimization benchmark |
| --- | ---: | ---: |
| Slowest test shard | 160.79 seconds | 130.08 seconds |
| Workflow start through build-job completion | 284 seconds | 258 seconds |
| Executable build, startup and packaging step | 50 seconds | 44 seconds |

The slowest shard improved by about **19%**, and the comparable pipeline portion
by about **9%**. Runner setup and queue variance affect these measurements.
The benchmark did not publish, so its 4m19s total cannot be compared directly
with v1.72's 4m58s complete publication as a pure optimization saving. Newly
added adapters also add real tests; their final release timings must be measured
separately rather than promised from this benchmark.

Meaningful regression checks cover CPU/desktop concurrency, serial desktop
exclusion, failure propagation, shard balancing, exactly-once package validation
and cross-platform fingerprint consistency. No test, integrity gate or public
fixture privacy protection was removed to obtain the improvement.

## Expanded-inventory scheduling refresh

The first complete v1.8 validation executed all 225 modules: 1,959 tests,
including 441 explicit skips, with no failures or errors. Its slowest shard
took 189.69 seconds; the other three took 155.20, 88.11 and 143.85 seconds.
The previous hints had become uneven as the suite expanded. Refreshing all
module timings from that run produces predicted shard loads of approximately
140 seconds each instead of an approximately 186-second maximum. This is a
scheduling prediction, not a measured saving; subsequent complete Windows
runs establish the actual result. The first expanded-inventory run took
287 seconds from workflow start through build-job completion and did not
publish. It is separate from the same-inventory benchmark above.

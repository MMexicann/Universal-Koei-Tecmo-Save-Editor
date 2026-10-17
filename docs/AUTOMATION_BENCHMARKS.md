# Automation regression properties and benchmarks

These developer tools exercise registered adapters and existing save/export
paths using generated fixtures. They do not accept player-save paths. Procedural
checks demonstrate invariants and performance on a known workload; they do not
establish genuine-save qualification, edited game loading or support for another
revision. The application remains v2.7.

## Reproduce the property suite

Install the checkout and the optional non-Windows crypto provider as described in
[CONTRIBUTING.md](../CONTRIBUTING.md), then run from the repository root:

```text
python -m unittest tests.test_automation_properties -v
```

The default seed is `0x4b4f4549` (`1263486281`). Failures identify the seed, game
and generated case or mutation. To explore another deterministic corpus:

```powershell
$env:KOEI_PROPERTY_SEED = '314159'
python -m unittest tests.test_automation_properties -v
Remove-Item Env:KOEI_PROPERTY_SEED
```

```sh
KOEI_PROPERTY_SEED=314159 python -m unittest tests.test_automation_properties -v
```

The suite is automatically discovered by `python -m tools.run_tests --workers 4`
and CI. It uses bounded, seeded loops with no external property-testing package
and no timing assertions. Its properties cover:

- Multi-field edit/readback sequences on DW4 Hyper, DW8 XL and Pirate Warriors 3,
  including supported boundaries, discrete scalar domains and intermediate Undo.
- Byte-identical no-ops for exact opened values; unchanged cipher seeds, immutable
  pending maps and preservation of all payload bytes outside selected fields.
- Rejection of incorrect scalar types, out-of-range values and complete pending
  maps before a destination or backup is created.
- Truncation, extra bytes, random single-bit damage under native checksum
  coverage, trailer damage and checksum-valid invalid headers/record identities.
- Three Houses dependency-invalid loadouts across two supported revisions,
  including pending maps that cannot be repaired through an opened-value shortcut.
- Actual guarded Save As, fresh on-disk readback, original-copy preservation and
  existing-destination protection.

Random bytes in an unchecksummed opaque region are not automatically corruption.
The malformed corpus deliberately chooses bytes under a verified integrity check,
known structural identities, or exact-size framing. To retain a newly discovered
failure, add a minimal procedural regression for its invariant; never commit the
player save that revealed it.

## Run repeatable benchmarks

The benchmark is a developer tool requiring the source checkout, including its
procedural test generators. It has no GUI requirement. Run:

```text
python -m tools.benchmark_automation --warmups 1 --iterations 5 --batch-size 4 --output benchmark.json
```

It prints one structured JSON report and optionally creates the same report as
a **new** file. An existing report is protected; choose another filename for the
next run. Exit status is 0 only when every requested workload completes. A failed
run retains completed timing rows and reports the workload and exception type.
Exception messages are omitted because filesystem errors can contain private paths.

Select a narrow workload while developing:

```text
python -m tools.benchmark_automation --workloads decode-large validate-large serialize-large --iterations 3
python -m tools.benchmark_automation --workloads automation-preflight automation-apply --batch-size 16 --iterations 5
python -m tools.benchmark_automation --workloads conversion-preflight conversion-export --batch-size 4 --iterations 5
```

Warmups range from 0 to 100; measured iterations range from 1 to 100; batch size
ranges from 1 to 32. All requested workloads run by default:

| Workload | Timed operation | Fixture |
| --- | --- | --- |
| `decode-small` | Registered bound decode and validation | 69,568-byte DW4 Hyper |
| `validate-small` | Frozen document validation | DW4 Hyper |
| `serialize-small` | Validated edit, native integrity, reparse and value verification | DW4 Hyper |
| `decode-large` | Registered bound cold decode and validation | 5,120,272-byte Wo Long container, 2,600 inventory records |
| `validate-large` | Frozen document validation | Wo Long |
| `serialize-large` | Token-preserving edit, native integrity, reparse and value verification | Wo Long |
| `conversion-preflight` | Complete queue preparation and validation | DW6 PC to decrypted PS3, qualified generated template/context |
| `conversion-export` | Reviewed queue export, backups, receipts and destination validation | Same conversion queue |
| `automation-preflight` | Reusable workflow validation and complete batch preparation | Independent generated DW4 Hyper copies |
| `automation-apply` | Reviewed batch apply through registered safe Save As | Same independent copies |

Each sample receives fresh nonexistent destinations. Fixture generation, filesystem
setup, conversion/batch preparation for apply/export, and temporary-file cleanup
are outside the timed region. Preflight workloads include their full preparation
inside the timer. Exports include their native safety checks and backups. This
makes read-only preparation and accepted-write costs separately visible.

Wo Long caches native qualification by immutable save bytes. `decode-large`
clears that backend qualification cache before each sample, outside the timed
region, so it measures native integrity and JSON parsing. `validate-large` keeps
the opened immutable snapshot cache and measures the normal application call.
Each scalar row declares its cache policy. Crypto-provider initialization is
warmed normally; these are steady-process measurements, not process-startup times.

The report includes workload sizes, fixture hashes, batch size, individual sample
durations, median/mean/min/max and nearest-rank p95. Machine metadata includes OS,
architecture, processor description, logical CPU count, Python version and
application version. It omits hostname, username, input/output paths and the
working directory. No private files or external fixture environment variables
are consulted. Temporary copies are deleted when each sample finishes.

## Compare results responsibly

Keep baseline and candidate JSON reports outside the tracked source tree. Use the
same machine, Python/crypto provider, batch size, fixture hashes and selected
workloads. Use at least five iterations for a first comparison and repeat if the
spread between minimum and maximum is large. For short runs, p95 is simply the
largest observation and is not a stable tail-latency estimate.

`median_mib_per_second` divides the declared bytes per operation by median time;
for conversion this counts source plus template bytes per job. It is a workload
normalization, not disk bandwidth. Cached snapshot validation can be much faster
than decoding a fresh file. These numbers measure their distinct public API calls,
not interchangeable parser implementations.

There are deliberately no universal pass/fail latency thresholds: host load,
filesystem, OS, interpreter and crypto provider vary. Treat a repeatable regression
as evidence to investigate with the owner of general application performance.
Preserve all validation and readback checks when optimizing; never replace a safe
adapter or conversion writer with a benchmark-only save-writing path.

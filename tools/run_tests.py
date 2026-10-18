"""Run the complete unittest inventory in isolated, parallel Python processes.

Examples: ``python -m tools.run_tests --workers 4 --report test-results/local.json``
or ``--shards 4 --shard-index 0 --timings tools/test_timings.json``. Every module
has its own process and log, so Tk interpreters and module mocks are not shared.
The final CI gate uses ``--verify-reports test-results`` before packaging.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import threading
import time
import unittest


SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
COUNTS = ("tests", "discovered_tests", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")


class ModuleLoader(unittest.TestLoader):
    """Use unittest's import/error handling for exactly one inventoried file.

    Default discovery also descends into packages. A parent and nested module
    sharing a basename would otherwise be run twice by separate workers. These
    small discovery hooks retain the standard loader's namespace and SkipTest
    behavior while leaving recursive inventory solely to the coordinator.
    """
    def __init__(self, path: Path):
        super().__init__()
        self.module_path = path

    def _find_tests(self, start_dir, pattern):
        suite, _ = self._find_test_path(str(self.module_path), pattern)
        if suite is not None:
            yield suite


def inventory(tests_dir: Path, pattern: str = "test*.py") -> list[str]:
    """Include every matching file, including future nested test modules."""
    if not tests_dir.is_dir():
        raise ValueError(f"Test directory does not exist: {tests_dir}")
    # Package-level hooks may synthesize tests outside the file inventory. Fail
    # explicitly instead of omitting them. Module-level load_tests is supported.
    for initializer in tests_dir.rglob("__init__.py"):
        try:
            tree = ast.parse(initializer.read_text(encoding="utf-8"))
        except SyntaxError:
            continue  # Normal worker imports report malformed packages.
        if any((isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "load_tests")
               or (isinstance(node, ast.Name) and node.id == "load_tests")
               or (isinstance(node, ast.alias) and (node.asname or node.name.rsplit(".", 1)[-1]) == "load_tests")
               for node in ast.walk(tree)):
            raise ValueError("Package-level load_tests hooks need explicit inventory support: "
                             f"{initializer.relative_to(tests_dir)}")
    paths = []
    for path in tests_dir.rglob("*.py"):
        if "__pycache__" in path.parts or not fnmatch.fnmatchcase(path.name, pattern):
            continue
        if path.is_symlink():
            raise ValueError(f"Symlinked test module is not supported: {path.name}")
        if not path.stem.isidentifier():
            raise ValueError(f"Test module is not a Python identifier: {path.name}")
        paths.append(path.relative_to(tests_dir).as_posix())
    if not paths:
        raise ValueError("Test inventory is empty")
    return sorted(paths)


def read_timings(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "durations" in data:
        data = data["durations"]
    if not isinstance(data, dict):
        raise ValueError("Timings must be a JSON object keyed by test module")
    result = {}
    for name, duration in data.items():
        if not isinstance(name, str) or not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise ValueError("Invalid timing entry")
        if not math.isfinite(duration) or duration < 0:
            raise ValueError(f"Invalid duration for {name}")
        result[name] = float(duration)
    return result


def partition(modules: list[str], shards: int, timings: dict[str, float], *,
              desktop: set[str] | None = None, workers: int = 1) -> list[list[str]]:
    """Balance CPU work and serial desktop work; never filter new modules.

    Each shard has ``workers`` isolated processes but only one shared desktop.
    Its estimated lower bound is the larger of total work / workers and desktop
    work. Timing hints affect placement only, never test discovery or results.
    """
    if shards < 1 or workers < 1 or len(modules) != len(set(modules)):
        raise ValueError("Invalid shard count or duplicate inventory")
    known = sorted(timings[name] for name in modules if name in timings)
    fallback = known[len(known) // 2] if known else 1.0
    fallback = max(fallback, 0.001)
    groups: list[list[str]] = [[] for _ in range(shards)]
    loads = [0.0] * shards
    desktop_loads = [0.0] * shards
    desktop = desktop or set()
    for module in sorted(modules, key=lambda name: (-timings.get(name, fallback), name)):
        duration = timings.get(module, fallback)
        desktop_duration = duration if module in desktop else 0.0
        target = min(range(shards), key=lambda index: (
            max((loads[index] + duration) / workers,
                desktop_loads[index] + desktop_duration),
            loads[index], len(groups[index]), index))
        groups[target].append(module)
        loads[target] += duration
        desktop_loads[target] += desktop_duration
    return groups


def desktop_modules(tests_dir: Path, modules: list[str]) -> set[str]:
    """Conservatively serialize Tk tests on each runner's shared OS desktop.

    Separate processes isolate Python/Tcl state but still share clipboard and
    focus. Follow local test-helper imports too, so a subclass/helper using Tk
    receives the same lock. Different CI shards have independent desktops.
    """
    dependencies: dict[Path, set[Path]] = {}
    direct = set()

    def inspect(path: Path):
        if path in dependencies:
            return
        dependencies[path] = set()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            direct.add(path)  # Its worker will report the actual import error.
            return
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
                names.extend(f"{node.module}.{alias.name}" if node.module else alias.name
                             for alias in node.names)
            for name in names:
                if name == "tkinter" or name.startswith("tkinter."):
                    direct.add(path)
                    continue
                parts = name.split(".")
                if parts[0] == "tests":
                    parts = parts[1:]
                if not parts or not all(part.isidentifier() for part in parts):
                    continue
                bases = [tests_dir, path.parent]
                if isinstance(node, ast.ImportFrom) and node.level:
                    base = path.parent
                    for _ in range(node.level - 1):
                        base = base.parent
                    bases = [base]
                for base in bases:
                    candidate = base.joinpath(*parts).with_suffix(".py")
                    if candidate.is_file() and candidate.is_relative_to(tests_dir):
                        dependencies[path].add(candidate)
                        inspect(candidate)

    for module in modules:
        inspect(tests_dir / module)
    affected = set(direct)
    while True:
        expanded = affected | {path for path, imports in dependencies.items() if imports & affected}
        if expanded == affected:
            return {module for module in modules if tests_dir / module in affected}
        affected = expanded


def source_fingerprint(tests_dir: Path) -> str:
    """Bind reports to the source bytes, including uncommitted working changes."""
    digest = hashlib.sha256()
    roots = [("src", ROOT / "src"), ("tools", ROOT / "tools"), ("tests", tests_dir)]
    for label, directory in roots:
        # Path objects sort case-insensitively on Windows and case-sensitively
        # on POSIX. Hash the same source bytes in one canonical order so reports
        # can be verified from either host without relaxing source validation.
        for path in sorted(directory.rglob("*"),
                           key=lambda path: path.relative_to(directory).as_posix()):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix not in {".py", ".json"}:
                continue
            digest.update(f"{label}/{path.relative_to(directory).as_posix()}\0".encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    digest.update((ROOT / "pyproject.toml").read_bytes())
    return digest.hexdigest()


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class ImmediateDiagnosticsResult(unittest.TextTestResult):
    """Flush each recorded traceback before another test can crash the worker.

    Keep unittest's final summary and diagnostics, including its result counts.
    The early copy survives even when no completed worker JSON can be written.
    """

    def _print_new(self, label, records, previous_count):
        if len(records) > previous_count:
            self.stream.writeln()
            self.printErrorList(label, records[previous_count:])
            self.stream.flush()

    def addFailure(self, test, err):
        previous_count = len(self.failures)
        super().addFailure(test, err)
        self._print_new("FAIL", self.failures, previous_count)

    def addError(self, test, err):
        previous_count = len(self.errors)
        super().addError(test, err)
        self._print_new("ERROR", self.errors, previous_count)

    def addSubTest(self, test, subtest, err):
        failures, errors = len(self.failures), len(self.errors)
        super().addSubTest(test, subtest, err)
        self._print_new("FAIL", self.failures, failures)
        self._print_new("ERROR", self.errors, errors)


def worker(tests_dir: Path, module: str, report_path: Path) -> int:
    started = time.perf_counter()
    path = tests_dir / module
    if module not in inventory(tests_dir, path.name):
        raise ValueError("Worker module is absent from inventory")
    loader = ModuleLoader(path)
    options = {}
    if path.parent != tests_dir and all(
        (parent / "__init__.py").exists()
        for parent in path.parent.parents
        if parent != tests_dir and tests_dir in parent.parents
    ) and (path.parent / "__init__.py").exists():
        options["top_level_dir"] = str(tests_dir)
    suite = loader.discover(start_dir=str(path.parent), pattern=path.name, **options)
    discovered = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2, resultclass=ImmediateDiagnosticsResult).run(suite)
    report = {
        "module": module, "duration_seconds": time.perf_counter() - started,
        "success": result.wasSuccessful() and discovered > 0,
        "tests": result.testsRun, "discovered_tests": discovered,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "discovery_errors": list(loader.errors),
    }
    if not discovered:
        report["infrastructure_error"] = "Module discovered no tests"
    write_json(report_path, report)
    return 0 if report["success"] else 1


def validate_module(record: object, module: str) -> dict:
    if not isinstance(record, dict) or record.get("module") != module:
        raise ValueError("Worker report has the wrong module")
    if type(record.get("success")) is not bool:
        raise ValueError("Worker report lacks boolean success")
    for key in COUNTS:
        if type(record.get(key)) is not int or record[key] < 0:
            raise ValueError(f"Worker report has invalid {key}")
    if record["tests"] > record["discovered_tests"]:
        raise ValueError("Executed test count exceeds discovered tests")
    duration = record.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or duration < 0:
        raise ValueError("Worker report has invalid duration")
    if not isinstance(record.get("discovery_errors"), list):
        raise ValueError("Worker report lacks discovery status")
    expected_success = not any(record[key] for key in ("failures", "errors", "unexpected_successes"))
    if record["discovery_errors"] or record.get("infrastructure_error") or not record["discovered_tests"]:
        expected_success = False
    if record["success"] != expected_success:
        raise ValueError("Worker success disagrees with failure counts")
    return record


def _execute_module(tests_dir: Path, module: str, logs_dir: Path, timeout: float) -> dict:
    # Encode the complete relative path to avoid same-name nested collisions.
    stem = hashlib.sha256(module.encode()).hexdigest()[:16]
    log_path = logs_dir / f"{stem}.log"
    worker_report = logs_dir / f"{stem}.json"
    command = [sys.executable, "-m", "tools.run_tests", "--_worker", module,
               "--tests-dir", str(tests_dir), "--report", str(worker_report)]
    started = time.perf_counter()
    try:
        worker_report.unlink(missing_ok=True)
        with log_path.open("w", encoding="utf-8") as stream:
            process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                     timeout=timeout, check=False)
        record = validate_module(json.loads(worker_report.read_text(encoding="utf-8")), module)
        if process.returncode != (0 if record["success"] else 1):
            raise ValueError(f"Worker exit {process.returncode} disagrees with report")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        record = {key: 0 for key in COUNTS}
        record.update(module=module, duration_seconds=time.perf_counter() - started,
                      success=False, discovery_errors=[], infrastructure_error=str(exc))
    record["log"] = log_path.name
    return record


def execute_module(tests_dir: Path, module: str, logs_dir: Path, timeout: float,
                   desktop_lock=None) -> dict:
    if desktop_lock is None:
        return _execute_module(tests_dir, module, logs_dir, timeout)
    with desktop_lock:
        return _execute_module(tests_dir, module, logs_dir, timeout)


def execute_modules(tests_dir: Path, modules: list[str], logs_dir: Path,
                    timeout: float, workers: int, desktop: set[str]):
    """Dispatch one desktop module at a time, keeping CPU workers available.

    Submitting every module up front lets two Tk tasks occupy both threads while
    one merely waits for the desktop lock. Select only eligible work instead;
    each module still runs once in its own subprocess with the same timeout,
    report validation and failure handling.
    """
    if workers < 1 or len(modules) != len(set(modules)):
        raise ValueError("Invalid worker count or duplicate inventory")
    pending = list(modules)
    desktop_lock = threading.Lock()
    desktop_active = False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        running = {}
        while pending or running:
            while len(running) < workers:
                eligible = next((index for index, name in enumerate(pending)
                                 if name not in desktop or not desktop_active), None)
                if eligible is None:
                    break
                name = pending.pop(eligible)
                is_desktop = name in desktop
                desktop_active |= is_desktop
                future = pool.submit(execute_module, tests_dir, name, logs_dir,
                                     timeout, desktop_lock if is_desktop else None)
                running[future] = name
            completed, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in sorted(completed, key=lambda item: running[item]):
                name = running.pop(future)
                if name in desktop:
                    desktop_active = False
                yield future.result()


def total_counts(records: list[dict]) -> dict[str, int]:
    return {key: sum(record[key] for record in records) for key in COUNTS}


def verify_reports(paths: list[Path], tests_dir: Path, pattern: str = "test*.py") -> dict:
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if not reports:
        raise ValueError("No shard reports were provided")
    if any(not isinstance(report, dict) for report in reports):
        raise ValueError("Shard reports must be JSON objects")
    modules = inventory(tests_dir, pattern)
    fingerprint = source_fingerprint(tests_dir)
    first = reports[0]
    shards = first.get("shards")
    if type(shards) is not int or shards < 1 or len(reports) != shards:
        raise ValueError("Missing or extra shard reports")
    assignments = first.get("assignments")
    if (not isinstance(assignments, list) or len(assignments) != shards
            or any(not isinstance(group, list) for group in assignments)):
        raise ValueError("Invalid shard assignments")
    planned = [module for group in assignments for module in group]
    if sorted(planned) != modules:
        raise ValueError("Shard assignments omit or duplicate test modules")
    seen_shards = set()
    records = []
    for report in reports:
        if (report.get("schema_version") != SCHEMA_VERSION or report.get("inventory") != modules
                or report.get("source_fingerprint") != fingerprint or report.get("shards") != shards
                or report.get("assignments") != assignments):
            raise ValueError("Reports have mismatched inventories, sources or assignments")
        index = report.get("shard_index")
        if type(index) is not int or index not in range(shards) or index in seen_shards:
            raise ValueError("Duplicate or invalid shard index")
        seen_shards.add(index)
        selected = report.get("modules")
        if not isinstance(selected, list) or any(not isinstance(record, dict) for record in selected):
            raise ValueError("Missing module results")
        if sorted(record.get("module", "") for record in selected) != sorted(assignments[index]):
            raise ValueError("Shard results omit or duplicate assigned modules")
        selected = [validate_module(record, record["module"]) for record in selected]
        if report.get("counts") != total_counts(selected):
            raise ValueError("Shard total counts disagree with module results")
        if (report.get("success") is not True or report.get("source_changed") is not False
                or any(not record["success"] for record in selected)):
            raise ValueError(f"Shard {index} did not pass")
        records.extend(selected)
    return {"success": True, "source_fingerprint": fingerprint, "inventory": modules,
            "counts": total_counts(records),
            "durations": {record["module"]: record["duration_seconds"] for record in records}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests-dir", type=Path, default=ROOT / "tests")
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=900.0, help="Maximum seconds per module")
    default_timings = ROOT / "tools" / "test_timings.json"
    parser.add_argument("--timings", type=Path, default=default_timings if default_timings.exists() else None)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-reports", nargs="+", type=Path)
    parser.add_argument("--_worker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        tests_dir = args.tests_dir.resolve()
        if args._worker:
            if args.report is None:
                raise ValueError("Worker needs an explicit report")
            return worker(tests_dir, args._worker, args.report)
        if args.verify_reports:
            paths = []
            for path in args.verify_reports:
                paths.extend(sorted(path.rglob("shard-*.json")) if path.is_dir() else [path])
            result = verify_reports(paths, tests_dir, args.pattern)
            if args.report:
                write_json(args.report, result)
            print(f"Verified {len(paths)} shards: {len(result['inventory'])} modules, "
                  f"{result['counts']['tests']} tests, {result['counts']['skipped']} skipped", flush=True)
            return 0
        if (args.workers < 1 or args.shards < 1 or args.shard_index not in range(args.shards)
                or not math.isfinite(args.timeout) or args.timeout <= 0):
            raise ValueError("Invalid workers, shard index/count or timeout")
        modules = inventory(tests_dir, args.pattern)
        timings = read_timings(args.timings)
        desktop = desktop_modules(tests_dir, modules)
        assignments = partition(modules, args.shards, timings,
                                desktop=desktop, workers=args.workers)
        selected = assignments[args.shard_index]
        report_path = args.report or Path(tempfile.mkdtemp(prefix="koei-tests-")) / "report.json"
        logs_dir = report_path.parent / f"logs-shard-{args.shard_index}"
        logs_dir.mkdir(parents=True, exist_ok=True)
        fingerprint = source_fingerprint(tests_dir)
        print(f"Shard {args.shard_index + 1}/{args.shards}: {len(selected)}/{len(modules)} modules, "
              f"{args.workers} isolated workers; "
              f"{len(set(selected) & desktop)} desktop modules coordinated", flush=True)
        started = time.perf_counter()
        records = []
        for record in execute_modules(tests_dir, selected, logs_dir, args.timeout,
                                      args.workers, desktop):
            records.append(record)
            status = "PASS" if record["success"] else "FAIL"
            print(f"{status} {record['module']}: {record['tests']} tests, "
                  f"{record['skipped']} skipped ({record['duration_seconds']:.2f}s)", flush=True)
            if not record["success"]:
                print(f"  Log: {logs_dir / record['log']}", flush=True)
                if record.get("infrastructure_error"):
                    print(f"  {record['infrastructure_error']}", flush=True)
        records.sort(key=lambda record: record["module"])
        source_changed = source_fingerprint(tests_dir) != fingerprint
        success = not source_changed and all(record["success"] for record in records)
        report = {"schema_version": SCHEMA_VERSION, "source_fingerprint": fingerprint,
                  "inventory": modules, "assignments": assignments, "shards": args.shards,
                  "shard_index": args.shard_index, "modules": records, "success": success,
                  "counts": total_counts(records), "duration_seconds": time.perf_counter() - started,
                  "durations": {record["module"]: record["duration_seconds"] for record in records},
                  "python": platform.python_version(), "platform": sys.platform,
                  "source_changed": source_changed, "desktop_modules": sorted(desktop)}
        write_json(report_path, report)
        counts = report["counts"]
        failed_modules = sum(not record["success"] for record in records)
        print(f"{'OK' if success else 'FAILED'}: {counts['tests']} tests, {counts['skipped']} skipped, "
              f"{counts['failures']} failures, {counts['errors']} errors, "
              f"{counts['unexpected_successes']} unexpected successes, {failed_modules} failed modules; "
              f"{report['duration_seconds']:.2f}s. Report: {report_path}", flush=True)
        if source_changed:
            print("Source files changed during tests; this run cannot qualify a build.", flush=True)
        for record in sorted(records, key=lambda record: (-record["duration_seconds"], record["module"]))[:5]:
            print(f"Slow module: {record['module']} ({record['duration_seconds']:.2f}s)", flush=True)
        return 0 if success else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Test runner error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

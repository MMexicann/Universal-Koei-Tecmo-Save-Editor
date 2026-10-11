"""Runner checks use tiny temporary suites, never recursively run this suite."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools import run_tests as runner


class ParallelRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="koei-runner-check-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tests = self.root / "cases"
        self.tests.mkdir()
        self.results = self.root / "results"

    def fixture(self, filename: str, body: str):
        path = self.tests / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def passing(self, filename="test_pass.py"):
        self.fixture(filename, "import unittest\nclass Check(unittest.TestCase):\n"
                     "    def test_pass(self): self.assertEqual(2 + 2, 4)\n"
                     "    @unittest.skip('optional fixture unavailable')\n"
                     "    def test_skip(self): pass\n")

    def invoke(self, *extra, index=0, shards=1, timeout=30):
        report = self.results / f"shard-{index}.json"
        command = [sys.executable, "-m", "tools.run_tests", "--tests-dir", str(self.tests),
                   "--workers", "2", "--shards", str(shards), "--shard-index", str(index),
                   "--report", str(report), *extra]
        process = subprocess.run(command, cwd=runner.ROOT, capture_output=True, text=True, timeout=timeout)
        data = json.loads(report.read_text()) if report.exists() else None
        return process, data, report

    def test_partition_balances_and_covers_new_modules_once(self):
        modules = ["test_heavy.py", "test_medium.py", "test_unknown.py", "test_small.py"]
        timings = {"test_heavy.py": 100, "test_medium.py": 40, "test_small.py": 10}
        groups = runner.partition(modules, 3, timings)
        self.assertEqual(sorted(item for group in groups for item in group), sorted(modules))
        self.assertEqual(groups, runner.partition(list(reversed(modules)), 3, timings))
        self.assertEqual(groups[0], ["test_heavy.py"])
        self.assertIn("test_unknown.py", [item for group in groups for item in group])
        with self.assertRaises(ValueError):
            runner.partition(["a", "a"], 2, {})

    def test_desktop_detection_follows_helpers_and_shared_lock(self):
        self.fixture("helper.py", "import tkinter as tk\n")
        self.fixture("test_gui.py", "from tests import helper\n")
        self.fixture("test_subclass.py", "from tests.test_gui import Example\n")
        self.fixture("test_cpu.py", "import unittest\n")
        affected = runner.desktop_modules(self.tests, runner.inventory(self.tests))
        self.assertEqual(affected, {"test_gui.py", "test_subclass.py"})
        lock = threading.Lock()
        self.results.mkdir()
        def inspect_lock(*args):
            self.assertTrue(lock.locked())
            return {"success": True}
        with patch.object(runner, "_execute_module", side_effect=inspect_lock):
            result = runner.execute_module(self.tests, "test_gui.py", self.results, 1, lock)
        self.assertTrue(result["success"])
        self.assertFalse(lock.locked())

    def test_nested_same_filename_inventory_and_isolated_execution(self):
        self.passing("test_same.py")
        self.passing("alpha/test_same.py")
        (self.tests / "alpha" / "__init__.py").write_text("")
        self.assertEqual(runner.inventory(self.tests), ["alpha/test_same.py", "test_same.py"])
        process, report, _ = self.invoke()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(report["counts"]["tests"], 4)
        self.assertEqual(report["counts"]["skipped"], 2)
        self.assertEqual(len({record["log"] for record in report["modules"]}), 2)

    def test_success_skips_and_full_shard_verification(self):
        self.passing("test_first.py")
        self.passing("test_second.py")
        paths = []
        for index in range(3):
            process, report, path = self.invoke(index=index, shards=3)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertTrue(report["success"])
            paths.append(path)
        result = runner.verify_reports(paths, self.tests)
        self.assertEqual(result["counts"]["tests"], 4)
        self.assertEqual(result["counts"]["skipped"], 2)
        command = [sys.executable, "-m", "tools.run_tests", "--tests-dir", str(self.tests),
                   "--verify-reports", str(self.results)]
        process = subprocess.run(command, cwd=runner.ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertIn("Verified 3 shards", process.stdout)

    def test_test_failure_and_subtest_failure_are_not_lost(self):
        self.fixture("test_fail.py", "import unittest\nclass Check(unittest.TestCase):\n"
                     "    def test_fail(self):\n"
                     "        for number in range(2):\n"
                     "            with self.subTest(number=number): self.fail('deliberate')\n")
        process, report, path = self.invoke()
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(report["counts"]["tests"], 1)
        self.assertEqual(report["counts"]["failures"], 2)
        with self.assertRaisesRegex(ValueError, "did not pass"):
            runner.verify_reports([path], self.tests)
        log = self.results / "logs-shard-0" / report["modules"][0]["log"]
        self.assertIn("deliberate", log.read_text())

    def test_import_error_causes_failure(self):
        self.fixture("test_broken.py", "raise RuntimeError('deliberate import failure')\n")
        process, report, _ = self.invoke()
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(report["counts"]["errors"], 1)
        self.assertTrue(report["modules"][0]["discovery_errors"])

    def test_empty_module_fails_but_module_and_class_skips_remain_visible(self):
        self.fixture("test_empty.py", "import unittest\n")
        process, report, _ = self.invoke()
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(report["counts"]["discovered_tests"], 0)
        self.assertEqual(report["modules"][0]["infrastructure_error"], "Module discovered no tests")
        self.fixture("test_empty.py", "import unittest\nraise unittest.SkipTest('optional module')\n")
        process, report, _ = self.invoke()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(report["counts"]["skipped"], 1)
        self.fixture("test_empty.py", "import unittest\nclass Check(unittest.TestCase):\n"
                     "    @classmethod\n"
                     "    def setUpClass(cls): raise unittest.SkipTest('optional class')\n"
                     "    def test_case(self): pass\n")
        process, report, _ = self.invoke()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(report["counts"]["tests"], 0)
        self.assertEqual(report["counts"]["discovered_tests"], 1)
        self.assertEqual(report["counts"]["skipped"], 1)

    def test_unexpected_success_fails_but_expected_failure_passes(self):
        self.fixture("test_expected.py", "import unittest\nclass Check(unittest.TestCase):\n"
                     "    @unittest.expectedFailure\n"
                     "    def test_expected(self): self.fail('expected')\n"
                     "    @unittest.expectedFailure\n"
                     "    def test_unexpected(self): pass\n")
        process, report, _ = self.invoke()
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(report["counts"]["expected_failures"], 1)
        self.assertEqual(report["counts"]["unexpected_successes"], 1)

    def test_timeout_and_silent_worker_exit_fail_closed(self):
        self.passing("test_exit.py")
        process, report, _ = self.invoke()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        for code in (0, 3):
            self.fixture("test_exit.py", f"import os\nos._exit({code})\n")
            process, report, _ = self.invoke()
            self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
            self.assertIn("infrastructure_error", report["modules"][0])
        self.fixture("test_exit.py", "import time\ntime.sleep(10)\n")
        process, report, _ = self.invoke("--timeout", "0.15")
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertIn("timed out", report["modules"][0]["infrastructure_error"])

    def test_reports_reject_missing_duplicates_stale_source_and_bad_counts(self):
        self.passing()
        process, original, path = self.invoke()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        with self.assertRaises(ValueError):
            runner.verify_reports([path, path], self.tests)
        for mutate in (
            lambda data: data["modules"].clear(),
            lambda data: data["modules"].append(data["modules"][0]),
            lambda data: data["counts"].update(tests=99),
            lambda data: data.update(source_fingerprint="old-source"),
            lambda data: data["modules"][0].update(success=False),
            lambda data: data["modules"][0].update(tests=True),
            lambda data: data.update(source_changed=True),
        ):
            data = json.loads(json.dumps(original))
            mutate(data)
            runner.write_json(path, data)
            with self.assertRaises(ValueError):
                runner.verify_reports([path], self.tests)
        runner.write_json(path, original)
        self.fixture("test_new.py", "import unittest\n")
        with self.assertRaises(ValueError):
            runner.verify_reports([path], self.tests)

    def test_timings_reject_nan_negative_and_boolean(self):
        path = self.root / "timings.json"
        for value in (float("nan"), -1, True, "slow"):
            runner.write_json(path, {"test_pass.py": value})
            with self.assertRaises(ValueError):
                runner.read_timings(path)
        runner.write_json(path, {"durations": {"test_pass.py": 2.5}, "provenance": "measured"})
        self.assertEqual(runner.read_timings(path), {"test_pass.py": 2.5})

    def test_package_load_tests_hook_fails_closed(self):
        self.passing("nested/test_pass.py")
        self.fixture("nested/__init__.py", "def load_tests(loader, tests, pattern):\n    return tests\n")
        with self.assertRaisesRegex(ValueError, "Package-level load_tests"):
            runner.inventory(self.tests)

    def test_invalid_empty_inventory_and_workers_do_not_pass(self):
        process, _, _ = self.invoke()
        self.assertEqual(process.returncode, 2)
        self.passing()
        process, _, _ = self.invoke("--workers", "0")
        self.assertEqual(process.returncode, 2)


if __name__ == "__main__":
    unittest.main()

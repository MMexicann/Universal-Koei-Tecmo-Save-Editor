"""Headless queue review/export and explicit CLI option separation."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.test_conversion import write_copy


class BatchCliTests(unittest.TestCase):
    def test_headless_dry_run_export_and_argument_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pc = write_copy(root / "pc", "dw6")
            ps3 = write_copy(root / "ps3", "dw6_ps3", 1)
            plan = root / "plan.json"
            output = root / "converted"
            plan.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "jobs": [
                            dict(
                                id="job",
                                route="dw6-to-dw6_ps3",
                                source=str(pc),
                                template=str(ps3),
                                output_dir=str(output),
                            )
                        ],
                    }
                )
            )
            command = [
                sys.executable,
                "-m",
                "koei_editor",
                "--batch-convert",
                str(plan),
            ]
            env = dict(os.environ, DISPLAY="")
            process = subprocess.run(
                command + ["--dry-run"],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(json.loads(process.stdout)["dry_run"])
            self.assertFalse(output.exists())
            self.assertFalse(any(root.rglob("*.context.json")))
            # Reject a combined report location that would collide with a per-copy receipt before exporting.
            process = subprocess.run(
                command + ["--batch-report", str(output / "conversion.json")],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output.exists())
            report = root / "batch.json"
            process = subprocess.run(
                command + ["--batch-report", str(report)],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(json.loads(process.stdout)["success"])
            self.assertEqual(json.loads(process.stdout), json.loads(report.read_text(encoding="utf-8")))
            for options in (
                ["--batch-report", str(report)],
                command[3:] + ["--game", "dw6"],
                command[3:] + ["--source", str(pc)],
                command[3:] + ["--comparison-report", str(report)],
            ):
                process = subprocess.run(
                    [sys.executable, "-m", "koei_editor", *options],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30,
                )
                self.assertNotEqual(process.returncode, 0)

"""Complete queue preflight, native exports, partial outcomes and immutable jobs."""

from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor import conversion
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import batch_conversion as batch
from tests.test_conversion import write_copy


class BatchConversionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.pc = write_copy(self.folder / "pc", "dw6")
        self.ps3 = write_copy(self.folder / "ps3", "dw6_ps3", 1)
        self.specs = (
            batch.JobSpec(
                "to-ps3", "dw6-to-dw6_ps3", self.pc, self.ps3, self.folder / "out-ps3"
            ),
            batch.JobSpec(
                "to-pc", "dw6_ps3-to-dw6", self.ps3, self.pc, self.folder / "out-pc"
            ),
        )
        self.originals = {
            path: path.read_bytes()
            for path in (self.pc, self.ps3, self.ps3.parent / "PARAM.SFO")
        }

    def assert_originals(self):
        for path, raw in self.originals.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_relative_json_plan_read_only_preflight_and_scope_report(self):
        data = {
            "schema_version": 1,
            "jobs": [
                {
                    "id": job.id,
                    "route": job.route,
                    "source": str(job.source.relative_to(self.folder)),
                    "template": str(job.template.relative_to(self.folder)),
                    "output_dir": job.output_dir.name,
                }
                for job in self.specs
            ],
        }
        path = self.folder / "plan.json"
        path.write_text(json.dumps(data))
        prepared = batch.prepare(path)
        report = batch.review_report(prepared)
        self.assertEqual(
            [row["transfer_scope"] for row in report["jobs"]], ["roster-and-horses"] * 2
        )
        self.assertTrue(report["dry_run"])
        self.assert_originals()
        self.assertFalse(any(job.output_dir.exists() for job in self.specs))
        self.assertFalse(any(self.folder.rglob("UniversalEditorBackups")))
        self.assertEqual([job.spec for job in prepared.jobs], list(self.specs))

    def test_complete_two_direction_export_preserves_context_backups_and_native_receipts(
        self,
    ):
        prepared = batch.prepare_specs(self.specs)
        progress = []
        outcomes = batch.execute(prepared, lambda *args: progress.append(args))
        report = batch.outcome_report(prepared, outcomes)
        self.assertTrue(report["success"])
        self.assertEqual(report["completed"], 2)
        for job, row in zip(prepared.jobs, report["jobs"]):
            endpoint = conversion.ENDPOINTS[job.review.route.target_id]
            self.assertEqual(
                (job.spec.output_dir / endpoint.filename).read_bytes(), job.review.raw
            )
            self.assertEqual(
                row["receipt"],
                json.loads(
                    (job.spec.output_dir / "conversion.json").read_text(
                        encoding="utf-8"
                    )
                ),
            )
        self.assertEqual(
            (self.specs[0].output_dir / "PARAM.SFO").read_bytes(),
            self.originals[self.ps3.parent / "PARAM.SFO"],
        )
        self.assertTrue(any(self.folder.rglob("*.context.json")))
        self.assertIn(("to-pc", "completed"), progress)
        self.assert_originals()
        output = batch.export_report(report, self.folder / "batch.json")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)
        self.assertNotIn(str(self.folder), output.read_text(encoding="utf-8"))

    def test_completed_report_rederives_native_output_and_rejects_forged_frozen_review(
        self,
    ):
        prepared = batch.prepare_specs(self.specs)
        outcomes = batch.execute(prepared)
        job = prepared.jobs[0]
        forged = replace(
            job, review=replace(job.review, raw=job.review.raw[:-1] + b"x")
        )
        with self.assertRaises(SaveError):
            batch.outcome_report(
                batch.PreparedBatch((forged, prepared.jobs[1])), outcomes
            )
        with self.assertRaises(SaveError):
            batch.outcome_report(batch.PreparedBatch(()), ())
        # Completed proof remains available if an original is later changed.
        self.pc.write_bytes(b"later changed input")
        self.assertTrue(batch.outcome_report(prepared, outcomes)["success"])
        receipt = json.loads(outcomes[0].receipt_json)
        receipt["unreviewed_data"] = "not permitted"
        stored = job.spec.output_dir / "conversion.json"
        stored.write_text(json.dumps(receipt), encoding="utf-8")
        bad = replace(outcomes[0], receipt_json=json.dumps(receipt))
        with self.assertRaises(SaveError):
            batch.outcome_report(prepared, (bad, outcomes[1]))

    def test_all_jobs_validate_before_any_write_or_backup(self):
        self.ps3.write_bytes(b"invalid second input")
        with (
            patch.object(conversion, "export") as exporter,
            self.assertRaises(SaveError),
        ):
            batch.prepare_specs(self.specs)
        exporter.assert_not_called()
        self.assertFalse(any(job.output_dir.exists() for job in self.specs))
        self.assertFalse(any(self.folder.rglob("UniversalEditorBackups")))

    def test_source_or_companion_changed_after_review_prevents_entire_batch(self):
        for path in (self.pc, self.ps3.parent / "PARAM.SFO"):
            prepared = batch.prepare_specs(self.specs)
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with (
                patch.object(conversion, "export") as exporter,
                self.assertRaises(SaveError),
            ):
                batch.execute(prepared)
            exporter.assert_not_called()
            path.write_bytes(original)
        self.assertFalse(any(job.output_dir.exists() for job in self.specs))

    def test_duplicate_nested_existing_or_live_cloud_destinations_and_job_ids_rejected(
        self,
    ):
        self.folder.joinpath("existing").mkdir()
        for second in (
            replace(self.specs[1], id=self.specs[0].id),
            replace(self.specs[1], output_dir=self.specs[0].output_dir),
            replace(self.specs[1], output_dir=self.specs[0].output_dir / "nested"),
            replace(self.specs[1], output_dir=self.folder / "existing"),
            replace(
                self.specs[1],
                output_dir=self.folder / "Steam/userdata/123/456/remote/new",
            ),
        ):
            with (
                self.subTest(second=second.id),
                self.assertRaises((SaveError, FileExistsError)),
            ):
                batch.prepare_specs((self.specs[0], second))
        for job in (
            replace(self.specs[0], id="../bad"),
            replace(self.specs[0], route="guessed-auto-route"),
        ):
            with self.assertRaises(SaveError):
                batch.prepare_specs((job,))

    def test_mid_queue_failure_preserves_completed_copy_and_marks_remaining_not_started(
        self,
    ):
        third = replace(self.specs[1], id="third", output_dir=self.folder / "third")
        prepared = batch.prepare_specs(self.specs + (third,))
        original = conversion.export

        def failing(review, folder):
            if folder == self.specs[1].output_dir:
                raise SaveError("Selected template changed")
            return original(review, folder)

        with patch.object(conversion, "export", side_effect=failing):
            outcomes = batch.execute(prepared)
        report = batch.outcome_report(prepared, outcomes)
        self.assertFalse(report["success"])
        self.assertEqual(
            [row.status for row in outcomes], ["completed", "failed", "not_started"]
        )
        self.assertTrue(self.specs[0].output_dir.exists())
        self.assertFalse(self.specs[1].output_dir.exists())
        self.assertEqual(
            (report["completed"], report["failed"], report["not_started"]), (1, 1, 1)
        )
        self.assert_originals()

    def test_failure_reports_omit_private_os_paths_backup_names_and_exception_text(
        self,
    ):
        prepared = batch.prepare_specs(self.specs)
        private = str(self.folder / "private-account-context" / "backup-copy")
        errors = (
            FileNotFoundError(2, "Missing copied file", private.replace("/", "\\")),
            SaveError("Changed private context: " + private),
            RuntimeError(private),
        )
        for error in errors:
            with patch.object(conversion, "export", side_effect=error):
                outcomes = batch.execute(prepared)
            report = batch.outcome_report(prepared, outcomes)
            text = json.dumps(report)
            self.assertEqual(
                [row.status for row in outcomes], ["failed", "not_started"]
            )
            self.assertNotIn(str(self.folder), text)
            self.assertNotIn("private-account-context", text)
            self.assertNotIn("backup-copy", text)
            self.assertTrue(report["jobs"][0]["error"])
            self.assertFalse(any(spec.output_dir.exists() for spec in self.specs))
        self.assert_originals()

    def test_stop_after_current_copy_keeps_verified_outputs(self):
        prepared = batch.prepare_specs(self.specs)
        stop = [False]

        def progress(_job, status):
            if status == "completed":
                stop[0] = True

        outcomes = batch.execute(prepared, progress, lambda: stop[0])
        self.assertEqual([row.status for row in outcomes], ["completed", "not_started"])
        self.assertEqual(batch.outcome_report(prepared, outcomes)["completed"], 1)
        self.assert_originals()

    def test_forged_review_job_spec_or_mapped_scope_cannot_export(self):
        prepared = batch.prepare_specs(self.specs)
        job = prepared.jobs[0]
        for forged in (
            replace(
                prepared,
                jobs=(replace(job, spec=replace(job.spec, route=self.specs[1].route)),),
            ),
            replace(
                prepared,
                jobs=(replace(job, review=replace(job.review, gameplay_bytes=1)),),
            ),
            replace(prepared, jobs=list(prepared.jobs)),
            replace(prepared, jobs=(None,)),
        ):
            with self.assertRaises(SaveError):
                batch.execute(forged)
        self.assertFalse(any(job.output_dir.exists() for job in self.specs))

    def test_changed_completed_output_or_forged_receipt_rejects_final_success_report(
        self,
    ):
        prepared = batch.prepare_specs(self.specs)
        outcomes = batch.execute(prepared)
        forged = replace(outcomes[0], receipt_json="{}")
        with self.assertRaises(SaveError):
            batch.outcome_report(prepared, (forged, outcomes[1]))
        output = self.specs[0].output_dir / "APP.BIN"
        original = output.read_bytes()
        output.write_bytes(original[:-1])
        with self.assertRaises(SaveError):
            batch.outcome_report(prepared, outcomes)
        output.write_bytes(original)
        context = self.specs[0].output_dir / "PARAM.SFO"
        context.write_bytes(context.read_bytes() + b"changed")
        with self.assertRaises(SaveError):
            batch.outcome_report(prepared, outcomes)

    def test_saved_private_plan_roundtrip_and_existing_plan_protection(self):
        path = self.folder / "saved-plan.json"
        batch.export_plan(self.specs, path)
        self.assertEqual(batch.load_plan(path), self.specs)
        self.assertNotIn(str(self.folder), path.read_text(encoding="utf-8"))
        with self.assertRaises(FileExistsError):
            batch.export_plan(self.specs, path)
        with self.assertRaises(SaveError):
            batch.export_plan(self.specs, self.specs[0].output_dir / "plan.json")
        self.assertFalse(self.specs[0].output_dir.exists())
        self.assert_originals()

    def test_mixed_game_families_and_ps4_conversion_only_endpoint_share_reviewed_queue(
        self,
    ):
        specs = [self.specs[0]]
        for source_id, target_id in (
            ("dw8xl", "dw8xl_ps4"),
            ("p5strikers_pc", "p5strikers_switch"),
        ):
            source = write_copy(self.folder / source_id, source_id)
            template = write_copy(self.folder / target_id, target_id, 1)
            specs.append(
                batch.JobSpec(
                    source_id,
                    source_id + "-to-" + target_id,
                    source,
                    template,
                    self.folder / ("out-" + target_id),
                )
            )
        prepared = batch.prepare_specs(tuple(specs))
        report = batch.review_report(prepared)
        self.assertEqual(len(report["jobs"]), 3)
        self.assertEqual(report["jobs"][0]["transfer_scope"], "roster-and-horses")
        self.assertNotEqual(report["jobs"][1]["transfer_scope"], "roster-and-horses")
        outcomes = batch.execute(prepared)
        self.assertTrue(batch.outcome_report(prepared, outcomes)["success"])
        self.assertTrue((specs[1].output_dir / "sce_sys/param.sfo").exists())
        self.assert_originals()

    @unittest.skipUnless(
        os.environ.get("DW6_SAVE") and os.environ.get("DW6_PS3_SAVE_COPIES"),
        "No private native DW6 platform pair selected",
    )
    def test_independent_native_platform_pair_queue(self):
        pc = Path(os.environ["DW6_SAVE"])
        ps3 = Path(os.environ["DW6_PS3_SAVE_COPIES"].split(os.pathsep)[0])
        original_pc, original_ps3 = pc.read_bytes(), ps3.read_bytes()
        specs = (
            batch.JobSpec(
                "native-ps3", "dw6-to-dw6_ps3", pc, ps3, self.folder / "native-ps3"
            ),
            batch.JobSpec(
                "native-pc", "dw6_ps3-to-dw6", ps3, pc, self.folder / "native-pc"
            ),
        )
        prepared = batch.prepare_specs(specs)
        outcomes = batch.execute(prepared)
        self.assertTrue(batch.outcome_report(prepared, outcomes)["success"])
        self.assertEqual(pc.read_bytes(), original_pc)
        self.assertEqual(ps3.read_bytes(), original_ps3)

    def test_bounded_schema_duplicate_keys_empty_oversize_and_unknown_keys_rejected(
        self,
    ):
        path = self.folder / "plan.json"
        for raw in (
            b"{}",
            b'{"schema_version":1,"schema_version":1,"jobs":[]}',
            b'{"schema_version":true,"jobs":[]}',
            b'{"schema_version":1,"jobs":[{}]}',
            b"\0" * (batch.MAX_PLAN_BYTES + 1),
        ):
            path.write_bytes(raw)
            with self.assertRaises(SaveError):
                batch.prepare(path)
        for specs in ((), list(self.specs), self.specs * 17):
            with self.assertRaises(SaveError):
                batch.prepare_specs(specs)

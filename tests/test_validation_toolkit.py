"""Adversarial evidence imports and controlled real-game observation transitions."""
import json
from pathlib import Path
import tempfile
import unittest

from koei_editor.game_registry import GAMES
from koei_editor.shared.validation_toolkit import (
    MAX_REPORT_BYTES, OUTCOMES, STEPS, ReportError, ValidationRecord,
)


def complete_record(provenance='genuine_file'):
    record = ValidationRecord.create('dw8xl', revision=15, provenance=provenance)
    for step in STEPS if provenance == 'genuine_file' else STEPS[:4]:
        record = record.record_step(step, 'passed')
    return record


class ValidationToolkitTests(unittest.TestCase):
    def test_every_supported_profile_retains_exact_registered_scope(self):
        for game in GAMES:
            with self.subTest(game=game.id):
                record = ValidationRecord.create(game.id)
                self.assertEqual(record.to_dict()['platform'], game.platform)
                self.assertEqual(record.to_dict()['profile_scope'], game.subtitle)
                self.assertEqual(ValidationRecord.from_json(record.to_json()), record)

    def test_fresh_record_never_claims_validation(self):
        record = ValidationRecord.create('dw8xl')
        self.assertEqual(set(record.outcomes), {'not_run'})
        self.assertTrue(record.summary()['revision_unspecified'])
        self.assertFalse(any(value for key, value in record.summary().items() if key != 'revision_unspecified'))
        self.assertEqual(record.to_dict()['attestation'], 'user_reported_unverified')

    def test_lanes_remain_distinct_even_after_all_game_steps(self):
        procedural = complete_record('procedural').summary()
        genuine = complete_record().summary()
        self.assertTrue(procedural['procedural_checks_reported'])
        self.assertFalse(procedural['genuine_file_checks_reported'])
        self.assertFalse(procedural['game_load_reported'])
        self.assertTrue(genuine['genuine_file_checks_reported'])
        self.assertTrue(genuine['game_load_reported'])
        self.assertTrue(genuine['game_resave_reported'])
        self.assertTrue(genuine['resaved_reload_reported'])
        self.assertFalse(genuine['procedural_checks_reported'])
        self.assertFalse(genuine['independently_verified'])

    def test_procedural_or_unknown_cannot_claim_game_observations(self):
        for provenance in ('procedural', 'unknown'):
            record = complete_record(provenance)
            for outcome in ('passed', 'failed'):
                with self.subTest(provenance=provenance, outcome=outcome), self.assertRaises(ReportError):
                    record.record_step('import_copy', outcome)

    def test_prerequisites_cannot_be_skipped_for_pass_or_failure(self):
        for step in STEPS[1:]:
            for outcome in ('passed', 'failed'):
                with self.subTest(step=step, outcome=outcome), self.assertRaises(ReportError):
                    ValidationRecord.create('dw8xl', provenance='genuine_file').record_step(step, outcome)

    def test_changed_earlier_step_invalidates_all_later_observations(self):
        original = complete_record()
        for outcome in OUTCOMES:
            record = original.record_step('identify_profile', outcome)
            if outcome == 'passed':
                self.assertIs(record, original)
            else:
                self.assertEqual(record.outcomes[:2], ('passed', outcome))
                self.assertEqual(set(record.outcomes[2:]), {'not_run'})
                self.assertFalse(record.summary()['game_load_reported'])
        self.assertEqual(set(original.outcomes), {'passed'})

    def test_failure_and_blocker_are_recorded_without_promoting_to_pass(self):
        record = ValidationRecord.create('dw8xl', provenance='genuine_file')
        record = record.record_step('prepare_copy', 'failed')
        record = record.record_step('game_load', 'blocked')
        self.assertFalse(record.summary()['game_load_reported'])
        self.assertEqual(ValidationRecord.from_json(record.to_json()), record)

    def test_mutable_or_malformed_workflow_rejected(self):
        for outcomes in ([], ['not_run'] * len(STEPS), ('passed',) * (len(STEPS) - 1),
                         ('not_run', 'passed') + ('not_run',) * (len(STEPS) - 2)):
            with self.subTest(outcomes=outcomes), self.assertRaises(ReportError):
                ValidationRecord('dw8xl', outcomes=outcomes)

    def test_unknown_and_private_identifiers_are_rejected_without_echo(self):
        for game_id in (None, True, [], '../private/alice.sav', 'C:\\Users\\alice\\save.dat', 'x' * 200):
            with self.subTest(game_id=game_id), self.assertRaises(ReportError) as caught:
                ValidationRecord.create(game_id)
            self.assertNotIn('alice', str(caught.exception))

    def test_revision_is_optional_unsigned_integer_and_never_free_text(self):
        for value in (None, 0, 15, 0xffffffff):
            self.assertEqual(ValidationRecord.create('dw8xl', revision=value).revision, value)
        for value in (True, False, -1, 2**32, 1.5, '15', 'alice_build', {}, []):
            with self.subTest(value=value), self.assertRaises(ReportError):
                ValidationRecord.create('dw8xl', revision=value)

    def test_strict_schema_rejects_unknown_keys_and_changed_claims(self):
        baseline = complete_record().to_dict()
        cases = [dict(baseline, path='/home/alice/private.sav'),
                 dict(baseline, schema_version=True), dict(baseline, schema_version=2),
                 dict(baseline, app_version='2.8'), dict(baseline, platform='PlayStation 3'),
                 dict(baseline, profile_scope='/home/alice/private.sav'),
                 dict(baseline, attestation='independently_verified'),
                 dict(baseline, provenance='genuine'), dict(baseline, steps={}),
                 dict(baseline, steps=dict(baseline['steps'], notes='alice'))]
        for report in cases:
            with self.subTest(report=report), self.assertRaises(ReportError):
                ValidationRecord.from_json(json.dumps(report))

    def test_import_cannot_assert_impossible_out_of_order_passes(self):
        report = complete_record().to_dict()
        report['steps']['game_load'] = 'failed'
        with self.assertRaises(ReportError):
            ValidationRecord.from_json(json.dumps(report))
        report = complete_record().to_dict()
        report['provenance'] = 'procedural'
        with self.assertRaises(ReportError):
            ValidationRecord.from_json(json.dumps(report))

    def test_json_parser_rejects_duplicate_keys_depth_nonfinite_bom_and_invalid_utf8(self):
        for data in (b'{"game_id":"dw8xl","game_id":"dw3"}', b'{"x":NaN}',
                     b'{"x":Infinity}', b'\xff', b'\xef\xbb\xbf{}',
                     '[' * 2000 + ']' * 2000, b'', '"\ud800"'):
            with self.subTest(data=str(data)[:80]), self.assertRaises(ReportError):
                ValidationRecord.from_json(data)

    def test_import_and_file_read_are_bounded(self):
        with self.assertRaises(ReportError):
            ValidationRecord.from_json(b' ' * (MAX_REPORT_BYTES + 1))
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'oversize.json'
            source.write_bytes(b' ' * (MAX_REPORT_BYTES + 1))
            with self.assertRaises(ReportError):
                ValidationRecord.load(source)

    def test_export_roundtrips_and_never_overwrites(self):
        record = complete_record()
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'report.json'
            record.export(destination)
            self.assertEqual(ValidationRecord.load(destination), record)
            old = destination.read_bytes()
            with self.assertRaises(FileExistsError):
                record.export(destination)
            self.assertEqual(destination.read_bytes(), old)
            self.assertNotIn(folder, old.decode())


if __name__ == '__main__':
    unittest.main()

"""Batch preflight and execution through real registered procedural adapters."""
from contextlib import redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor import automation_cli
from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import automation as engine, edit_presets
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.test_dw4hyper_format import procedural_raw
from tests.test_edit_presets import fixture_backend


class Journal:
    def __init__(self):
        self.events = []

    def validate_binding(self, token, jobs):
        pass

    def intent(self, job):
        self.events.append(('intent', job))

    def complete(self, job):
        self.events.append(('complete', job))


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)
        self.adapter = get_game('dw4hyper').get_scalar_adapter()
        self.sources = tuple(self.folder / f'copy-{index}.dat' for index in range(3))
        for source in self.sources:
            source.write_bytes(procedural_raw())
        self.workflow = engine.Workflow('Reviewed attack', 'dw4hyper', (
            engine.Operation('assert', (('officer_0_attack', 50),)),
            engine.Operation('set', (('officer_0_attack', 123),)),
            engine.Operation('assert', (('officer_0_attack', 123),))))
        self.specs = tuple(engine.JobSpec(f'job-{index}', source,
                                         self.folder / f'output-{index}.dat')
                           for index, source in enumerate(self.sources))

    def test_real_adapter_batch_review_apply_readback_and_source_preservation(self):
        batch = engine.prepare(self.workflow, self.specs)
        self.assertFalse(any(spec.destination.exists() for spec in self.specs))
        self.assertFalse(list(self.folder.glob('*Backups')))
        preview = engine.preview(batch)
        self.assertNotIn(str(self.folder), json.dumps(preview))
        self.assertEqual(preview['jobs'][0]['changes'],
                         [{'field': 'officer_0_attack', 'before': 50, 'after': 123}])
        journal = Journal()
        result = engine.apply(batch, batch.review_token, journal=journal)
        self.assertTrue(result['success'])
        self.assertEqual(len(journal.events), 6)
        for spec in self.specs:
            self.assertEqual(spec.source.read_bytes(), procedural_raw())
            result = self.adapter.read_save(spec.destination)
            self.assertEqual(self.adapter.field_map(result)['officer_0_attack'].value(result.payload), 123)
            self.assertEqual(hashlib.sha256(result.raw).hexdigest(), batch.jobs[0].serialized_sha256)

    def test_late_invalid_source_prevents_all_writes_and_backups(self):
        self.sources[-1].write_bytes(b'invalid')
        with self.assertRaises(SaveError):
            engine.prepare(self.workflow, self.specs)
        self.assertFalse(any(spec.destination.exists() for spec in self.specs))
        self.assertEqual(len(list(self.folder.iterdir())), 3)

    def test_changed_source_and_wrong_token_prevent_all_writes(self):
        batch = engine.prepare(self.workflow, self.specs)
        with self.assertRaises(SaveError):
            engine.apply(batch, '0' * 64)
        self.sources[-1].write_bytes(b'interrupted external copy')
        with self.assertRaises(SaveError):
            engine.apply(batch, batch.review_token)
        self.assertFalse(any(spec.destination.exists() for spec in self.specs))

    def test_ordered_assertions_fail_before_any_write(self):
        workflow = replace(self.workflow, operations=(engine.Operation('assert', (('officer_0_attack', 49),)),))
        with self.assertRaisesRegex(SaveError, 'assertion_failed'):
            engine.prepare(workflow, self.specs)
        self.assertEqual(len(list(self.folder.iterdir())), 3)

    def test_noop_preserves_native_bytes(self):
        workflow = replace(self.workflow, operations=(engine.Operation('set', (('officer_0_attack', 50),)),))
        batch = engine.prepare(workflow, self.specs[:1])
        self.assertFalse(batch.jobs[0].pending)
        self.assertEqual(batch.jobs[0].serialized_sha256, hashlib.sha256(procedural_raw()).hexdigest())
        self.assertTrue(engine.apply(batch, batch.review_token)['success'])
        self.assertEqual(self.specs[0].destination.read_bytes(), procedural_raw())

    def test_simultaneous_dependency_group_and_invalid_intermediate_group(self):
        backend, raw = fixture_backend()
        adapter = BoundScalarAdapter('preset_fixture', '.dat', backend)
        source = self.folder / 'dependency.dat'
        source.write_bytes(raw)
        specs = (engine.JobSpec('swap', source, self.folder / 'swap.dat'),)
        workflow = engine.Workflow('Swap', 'preset_fixture',
                                   (engine.Operation('set', (('left', 20), ('right', 10))),))
        batch = engine.prepare(workflow, specs, adapter=adapter)
        self.assertEqual(dict(batch.jobs[0].pending), {'left': 20, 'right': 10})
        invalid = replace(workflow, operations=(engine.Operation('set', (('left', 20),)),
                                               engine.Operation('set', (('right', 10),))))
        with self.assertRaises(SaveError):
            engine.prepare(invalid, specs, adapter=adapter)

    def test_fail_stop_keeps_first_copy_and_records_ambiguous_second(self):
        batch = engine.prepare(self.workflow, self.specs)
        original = BoundScalarAdapter.save_as
        count = 0
        def fail_second(adapter, document, pending, destination):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('private user path must never be printed')
            return original(adapter, document, pending, destination)
        journal = Journal()
        with patch.object(BoundScalarAdapter, 'save_as', fail_second):
            result = engine.apply(batch, batch.review_token, journal=journal)
        self.assertFalse(result['success'])
        self.assertEqual([row['status'] for row in result['jobs']], ['completed', 'failed', 'not_started'])
        self.assertEqual(journal.events, [('intent', 'job-0'), ('complete', 'job-0'), ('intent', 'job-1')])
        self.assertTrue(self.specs[0].destination.exists())
        self.assertFalse(self.specs[2].destination.exists())
        self.assertNotIn('private user path', json.dumps(result))

    def test_exception_after_save_never_deletes_new_output_or_retries(self):
        batch = engine.prepare(self.workflow, self.specs[:1])
        original = BoundScalarAdapter.save_as
        def ambiguous(adapter, document, pending, destination):
            original(adapter, document, pending, destination)
            raise RuntimeError('crash after native writer')
        journal = Journal()
        with patch.object(BoundScalarAdapter, 'save_as', ambiguous):
            result = engine.apply(batch, batch.review_token, journal=journal)
        self.assertFalse(result['success'])
        self.assertTrue(result['jobs'][0]['requires_inspection'])
        self.assertTrue(self.specs[0].destination.exists())
        self.assertEqual(journal.events, [('intent', 'job-0')])
        with self.assertRaises(FileExistsError):
            engine.apply(batch, batch.review_token, journal=journal)

    def test_tampered_review_rows_and_self_reported_token_cannot_bypass_workflow(self):
        batch = engine.prepare(self.workflow, self.specs[:1])
        changed = replace(batch.jobs[0], rows=(('officer_0_attack', 50, 51),))
        forged = replace(batch, jobs=(changed,))
        with self.assertRaises(SaveError):
            engine.validate(forged)
        forged = replace(forged, review_token=engine._token(forged.workflow, forged.jobs))
        with self.assertRaises(SaveError):
            engine.validate(forged)

    def test_source_bound_preset_allows_only_identical_save_copies(self):
        document = self.adapter.read_save(self.sources[0])
        preset = edit_presets.create(self.adapter, document, {'officer_0_attack': 123}, 'Exact source')
        batch = engine.prepare_preset(preset, self.specs)
        self.assertEqual(len(batch.jobs), 3)
        edited = self.adapter.serialize(document, {'officer_1_attack': 123})
        self.sources[2].write_bytes(edited)
        with self.assertRaisesRegex(SaveError, 'exact original save'):
            engine.prepare_preset(preset, self.specs)

    def test_alias_live_directory_duplicate_output_and_existing_output_rejected(self):
        duplicate = replace(self.specs[1], destination=self.specs[0].destination)
        with self.assertRaises(SaveError):
            engine.prepare(self.workflow, (self.specs[0], duplicate))
        with self.assertRaises(FileExistsError):
            engine.prepare(self.workflow, (replace(self.specs[0], destination=self.sources[0]),))
        live = replace(self.specs[0], destination=self.folder / 'Steam/userdata/1/2/remote/output.dat')
        with self.assertRaises(SaveError):
            engine.prepare(self.workflow, (live,))
        alias = self.folder / 'alias'
        try:
            alias.symlink_to(self.folder, target_is_directory=True)
        except OSError:
            self.skipTest('Directory symlinks unavailable')
        with self.assertRaises(FileExistsError):
            engine.prepare(self.workflow, (replace(self.specs[0], destination=alias / self.sources[1].name),))

    def test_strict_json_duplicate_keys_unknown_code_and_surrogates(self):
        raw = engine.dumps(self.workflow)
        self.assertEqual(engine.loads(raw), self.workflow)
        data = engine.workflow_data(self.workflow)
        for mutate in (lambda d: d.update(version=True), lambda d: d.update(extra='execute'),
                       lambda d: d.update(name='\ud800'),
                       lambda d: d.update(operations=[{'op': 'exec', 'code': 'anything'}]),
                       lambda d: d.update(operations=[{'op': 'set', 'values': {'officer_0_attack': True}}])):
            bad = json.loads(raw)
            mutate(bad)
            with self.subTest(data=repr(bad)), self.assertRaises(SaveError):
                engine.loads(json.dumps(bad).encode())
        with self.assertRaises(SaveError):
            engine.loads(raw.replace(b'"version": 1', b'"version": 1, "version": 1'))

    def cli(self, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            code = automation_cli.main(list(arguments))
        return code, json.loads(output.getvalue())

    def test_cli_relative_plan_dry_run_json_and_review_rejection(self):
        plan = self.folder / 'plan.json'
        plan.write_text(json.dumps({'schema_version': 1, 'workflow': engine.workflow_data(self.workflow),
                                    'jobs': [{'id': 'save', 'source': self.sources[0].name,
                                              'destination': 'edited.dat'}]}))
        code, result = self.cli('preview', str(plan))
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'prepared')
        self.assertNotIn(str(self.folder), json.dumps(result))
        self.assertEqual(self.cli('apply', str(plan), '--dry-run')[0], 0)
        self.assertEqual(self.cli('apply', str(plan), '--review-token', 'wrong')[0], 2)
        self.assertFalse((self.folder / 'edited.dat').exists())
        self.assertEqual(self.cli('apply', str(plan), '--review-token', result['review_token'])[0], 2)
        code, result = self.cli('fields', '--game', 'dw4hyper', str(self.sources[0]))
        self.assertEqual(code, 0)
        self.assertTrue(any(row['field'] == 'officer_0_attack' for row in result['fields']))

    def test_cli_builder_preserves_assert_order_and_groups_contiguous_sets(self):
        output = self.folder / 'workflow.json'
        code, result = self.cli('build', '--game', 'dw4hyper', '--name', 'Build',
                                '--assert', 'officer_0_attack=50',
                                '--set', 'officer_0_attack=123', '--set', 'officer_1_attack=122',
                                '--output', str(output))
        self.assertEqual(code, 0)
        workflow = engine.load(output)
        self.assertEqual([operation.op for operation in workflow.operations], ['assert', 'set'])
        self.assertEqual(len(workflow.operations[1].values), 2)
        self.assertEqual(self.cli('unknown', str(self.folder))[0], 2)

    def test_cli_apply_durable_journal_and_recover_completed_batch(self):
        plan = self.folder / 'plan.json'
        plan.write_text(json.dumps({'schema_version': 1, 'workflow': engine.workflow_data(self.workflow),
                                    'jobs': [{'id': 'save', 'source': self.sources[0].name,
                                              'destination': 'edited.dat'}]}))
        code, preview = self.cli('preview', str(plan))
        journal = self.folder / 'journal'
        code, result = self.cli('apply', str(plan), '--review-token', preview['review_token'],
                                '--journal', str(journal))
        self.assertEqual(code, 0, result)
        self.assertTrue((journal / '000002.json').is_file())
        code, recovered = self.cli('recover', str(plan), '--journal', str(journal))
        self.assertEqual(code, 0, recovered)
        self.assertEqual(recovered['jobs'], [{'id': 'save', 'status': 'completed'}])
        self.assertNotIn(str(self.folder), json.dumps(recovered))
        # Recovery never requires that existing destinations be treated as new,
        # and replay still rejects them rather than overwriting completed work.
        self.assertEqual(self.cli('apply', str(plan), '--review-token', preview['review_token'],
                                  '--journal', str(self.folder / 'another-journal'))[0], 2)

    def test_crashed_intent_inspection_blocks_absent_and_accepts_native_output(self):
        from koei_editor.shared.automation_journal import RunJournal
        batch = engine.prepare(self.workflow, self.specs[:1])
        journal = RunJournal.create(self.folder / 'journal', batch.review_token, engine.journal_jobs(batch))
        journal.intent('job-0')
        report = engine.inspect_recovery(batch, journal)
        self.assertFalse(report['success'])
        self.assertEqual(report['jobs'][0]['status'], 'blocked')
        job = batch.jobs[0]
        self.adapter.save_as(job.document, dict(job.pending), job.spec.destination)
        reopened = engine.prepare(self.workflow, self.specs[:1], allow_existing=True)
        self.assertEqual(reopened.review_token, batch.review_token)
        report = engine.inspect_recovery(reopened, journal)
        self.assertTrue(report['success'])
        self.assertEqual(report['jobs'][0]['status'], 'recovered')
        self.assertEqual(len(list((self.folder / 'journal').iterdir())), 2)

    def test_recovery_accepts_valid_output_with_changed_dynamic_field_eligibility(self):
        from koei_editor.shared.automation_journal import RunJournal
        backend, raw = fixture_backend()
        original_map = backend.field_map
        backend.field_map = lambda document: {key: field for key, field in original_map(document).items()
                                              if key != 'gold' or document.payload[2] > 0}
        adapter = BoundScalarAdapter('preset_fixture', '.dat', backend)
        source = self.folder / 'dynamic.dat'
        source.write_bytes(raw)
        specs = (engine.JobSpec('dynamic', source, self.folder / 'dynamic-output.dat'),)
        workflow = engine.Workflow('Deplete existing record', 'preset_fixture',
                                   (engine.Operation('set', (('gold', 0),)),))
        batch = engine.prepare(workflow, specs, adapter=adapter)
        journal = RunJournal.create(self.folder / 'journal', batch.review_token, engine.journal_jobs(batch))
        journal.intent('dynamic')
        # Native-like fixture writer only, production engine never writes bytes.
        specs[0].destination.write_bytes(adapter.serialize(batch.jobs[0].document, {'gold': 0}))
        self.assertNotEqual(edit_presets._profile_hash(adapter, adapter.read_save(specs[0].destination)),
                            batch.jobs[0].profile_sha256)
        report = engine.inspect_recovery(batch, journal)
        self.assertEqual(report['jobs'], [{'id': 'dynamic', 'status': 'recovered'}])

    def test_journal_binding_and_cancellation_stop_before_writes(self):
        from koei_editor.shared.automation_journal import RunJournal
        batch = engine.prepare(self.workflow, self.specs)
        journal = RunJournal.create(self.folder / 'journal', '0' * 64, engine.journal_jobs(batch))
        with self.assertRaises(SaveError):
            engine.apply(batch, batch.review_token, journal=journal)
        self.assertFalse(any(spec.destination.exists() for spec in self.specs))
        result = engine.apply(batch, batch.review_token, cancelled=lambda: True)
        self.assertEqual([row['status'] for row in result['jobs']],
                         ['cancelled', 'not_started', 'not_started'])
        self.assertFalse(any(spec.destination.exists() for spec in self.specs))

    def test_cli_preflight_failure_reports_safe_job_and_operation_context(self):
        workflow = replace(self.workflow, operations=(engine.Operation('set', (('officer_0_attack', 99999),)),))
        plan = self.folder / 'invalid.json'
        plan.write_text(json.dumps({'schema_version': 1, 'workflow': engine.workflow_data(workflow),
                                    'jobs': [{'id': 'safe-id', 'source': self.sources[0].name,
                                              'destination': 'never-created.dat'}]}))
        code, result = self.cli('preview', str(plan))
        self.assertEqual(code, 2)
        self.assertEqual(result['error_code'], 'invalid_value')
        self.assertEqual(result['job_id'], 'safe-id')
        self.assertEqual(result['operation_index'], 1)
        self.assertNotIn(str(self.folder), json.dumps(result))

    def test_bounded_malformed_workflow_documents_never_reach_native_writer(self):
        raw = engine.dumps(self.workflow)
        malformed = [b'', b'\xff', b'null', b'[]', b'1', b'"workflow"',
                     b'[' * 1200 + b']' * 1200,
                     raw.replace(b'"version": 1', b'"version": NaN'),
                     raw.replace(b'"version": 1', b'"version": Infinity')]
        mutations = [
            {'operations': None}, {'operations': []}, {'operations': {}},
            {'operations': [None]}, {'operations': [True]}, {'operations': [[]]},
            {'operations': [{'op': 'set', 'values': []}]},
            {'operations': [{'op': 'set', 'values': {}}]},
            {'operations': [{'op': 'assert', 'field': 'x', 'value': None}]},
            {'operations': [{'op': 'assert', 'field': 'x', 'value': 0, 'extra': 'execute'}]},
            {'operations': [{'op': 'set', 'values': {'x': 1.5}}]},
            {'operations': [{'op': 'set', 'values': {'x': 1 << 64}}]},
            {'operations': [{'op': 'set', 'values': {'x': 'a' * 4097}}]},
            {'game_id': '../another_parser'}, {'game_id': True}, {'name': 1}]
        for update in mutations:
            data = json.loads(raw)
            data.update(update)
            malformed.append(json.dumps(data).encode())
        for document in malformed:
            with self.subTest(document=document[:80]), self.assertRaises(SaveError):
                engine.loads(document)
        with patch.object(engine, 'MAX_BYTES', len(raw) - 1), self.assertRaises(SaveError):
            engine.loads(raw)
        self.assertFalse(any(spec.destination.exists() for spec in self.specs))

    def test_later_source_change_after_first_native_save_stops_remaining_jobs(self):
        batch = engine.prepare(self.workflow, self.specs)
        original = BoundScalarAdapter.save_as
        def save_then_external_change(adapter, document, pending, destination):
            result = original(adapter, document, pending, destination)
            self.sources[-1].write_bytes(b'changed by another process')
            return result
        with patch.object(BoundScalarAdapter, 'save_as', save_then_external_change):
            result = engine.apply(batch, batch.review_token)
        self.assertEqual([row['status'] for row in result['jobs']],
                         ['completed', 'failed', 'not_started'])
        self.assertTrue(self.specs[0].destination.exists())
        self.assertFalse(self.specs[1].destination.exists())


if __name__ == '__main__':
    unittest.main()

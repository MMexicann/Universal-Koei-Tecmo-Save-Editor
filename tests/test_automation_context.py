"""Procedural native-context identity across review, save receipts and recovery."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import automation
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.automation_journal import RunJournal
from koei_editor.shared.steam_owner import read_owner
from tests.test_berserk_vita import fixture as vita_fixture, metadata as vita_metadata
from tests.test_doa5_ps3 import fixture as ps3_fixture, metadata as ps3_metadata
from tests.test_ninja_gaiden_black_xbox import procedural as xbox_fixture
from tests import test_ps3_expansion as ps3_context
from tests.test_samurai5_pc import procedural as steam_fixture
from tests.test_steam_owner import invented_vdf
from tests.test_troy_ps3 import fixture as troy_fixture


PROFILES = ('doa5_ps3', 'troy_ps3', 'berserk_vita', 'samurai5_pc', 'ninja_gaiden_black_xbox')


def copied_case(folder, game_id):
    adapter = get_game(game_id).get_scalar_adapter()
    if game_id == 'ninja_gaiden_black_xbox':
        source = xbox_fixture(folder)
        companion = folder / 'eeprom.bin'
        changed = bytearray(companion.read_bytes())
        changed[-1] ^= 1  # Opaque original bytes outside the protected section.
        changed = bytes(changed)
    else:
        source = folder / ('source' + adapter.extension)
        if game_id == 'doa5_ps3':
            raw, relative, context = ps3_fixture(), 'PARAM.SFO', ps3_metadata()
        elif game_id == 'troy_ps3':
            raw, relative = troy_fixture(), 'PARAM.SFO'
            context = ps3_context.PS3ContextTests.metadata('BLES01183-WLOT')
        elif game_id == 'berserk_vita':
            raw, relative, context = vita_fixture(), 'sce_sys/param.sfo', vita_metadata()
        else:
            relative, context = 'steam_autocloud.vdf', invented_vdf()
            (folder / relative).write_bytes(context)
            raw = steam_fixture(read_owner(source))
        source.write_bytes(raw)
        companion = folder / relative
        companion.parent.mkdir(exist_ok=True)
        companion.write_bytes(context)
        changed = context + (b' \n' if game_id == 'samurai5_pc' else b'opaque-context-change')
    document = adapter.read_save(source)
    field = adapter.fields_for(document)[0]
    workflow = automation.Workflow('Native context regression', game_id, (
        automation.Operation('assert', ((field.id, field.value(document.payload)),)),))
    return adapter, source, companion, changed, workflow


class AutomationContextTests(unittest.TestCase):
    def test_valid_source_companion_substitution_invalidates_review_and_journal_binding(self):
        for game_id in PROFILES:
            with self.subTest(profile=game_id), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                adapter, source, companion, changed, workflow = copied_case(folder, game_id)
                specs = (automation.JobSpec('copy', source, folder / ('edited' + adapter.extension)),)
                first = automation.prepare(workflow, specs)
                journal = RunJournal.create(folder / 'journal', first.review_token, automation.journal_jobs(first))
                original = source.read_bytes()
                companion.write_bytes(changed)
                second = automation.prepare(workflow, specs)
                self.assertNotEqual(first.jobs[0].context_sha256, second.jobs[0].context_sha256)
                self.assertNotEqual(first.review_token, second.review_token)
                with self.assertRaises(SaveError):
                    automation.apply(second, first.review_token, journal=journal)
                with self.assertRaises(SaveError):
                    automation.inspect_recovery(second, journal)
                self.assertFalse(specs[0].destination.exists())
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(companion.read_bytes(), changed)

    def test_recovery_rejects_substituted_output_context_without_modifying_evidence(self):
        for game_id in PROFILES:
            with self.subTest(profile=game_id), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                adapter, source, companion, changed, workflow = copied_case(folder, game_id)
                output = folder / 'separate-output'
                output.mkdir()
                target = output / source.name
                output_companion = output / companion.relative_to(folder)
                output_companion.parent.mkdir(exist_ok=True)
                output_companion.write_bytes(companion.read_bytes())
                batch = automation.prepare(workflow, (automation.JobSpec('copy', source, target),))
                journal = RunJournal.create(folder / 'journal', batch.review_token, automation.journal_jobs(batch))
                self.assertTrue(automation.apply(batch, batch.review_token, journal=journal)['success'])
                # Local paths differ, while exact original context must agree.
                self.assertEqual(automation._native_context_digest(adapter.read_save(target)),
                                 batch.jobs[0].context_sha256)
                output_companion.write_bytes(changed)
                original, saved = source.read_bytes(), target.read_bytes()
                evidence = {path.name: path.read_bytes() for path in (folder / 'journal').iterdir()}
                with patch.object(BoundScalarAdapter, 'save_as', side_effect=AssertionError('No replay')):
                    report = automation.inspect_recovery(batch, journal)
                self.assertFalse(report['success'])
                self.assertEqual(report['jobs'], [{'id': 'copy', 'status': 'blocked'}])
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(target.read_bytes(), saved)
                self.assertEqual(output_companion.read_bytes(), changed)
                self.assertEqual(evidence, {path.name: path.read_bytes() for path in (folder / 'journal').iterdir()})

    def test_final_receipt_rejects_output_context_change_after_native_save(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            adapter, source, companion, changed, workflow = copied_case(folder, 'doa5_ps3')
            output = folder / 'separate-output'
            output.mkdir()
            target = output / source.name
            output_companion = output / companion.name
            output_companion.write_bytes(companion.read_bytes())
            batch = automation.prepare(workflow, (automation.JobSpec('copy', source, target),))
            original_save_as = BoundScalarAdapter.save_as
            def substitute_after_save(bound, *args, **kwargs):
                result = original_save_as(bound, *args, **kwargs)
                output_companion.write_bytes(changed)
                return result
            with patch.object(BoundScalarAdapter, 'save_as', substitute_after_save):
                report = automation.apply(batch, batch.review_token)
            self.assertFalse(report['success'])
            self.assertEqual(report['jobs'][0]['status'], 'verification_failed')
            self.assertTrue(target.exists())
            self.assertEqual(output_companion.read_bytes(), changed)

    def test_forged_context_digest_cannot_redefine_review_or_leak_companions(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            adapter, source, companion, _changed, workflow = copied_case(folder, 'samurai5_pc')
            batch = automation.prepare(workflow, (automation.JobSpec('copy', source, folder / 'edited.bin'),))
            forged_job = replace(batch.jobs[0], context_sha256='0' * 64)
            forged = replace(batch, jobs=(forged_job,), review_token=automation._token(workflow, (forged_job,)))
            with self.assertRaises(SaveError):
                automation.apply(forged, forged.review_token)
            report = json.dumps(automation.preview(batch))
            self.assertNotIn(str(folder), report)
            self.assertNotIn(companion.read_text(), report)
            self.assertNotIn('accountid', report)

    def test_original_steam_basename_spelling_is_bound_separately_from_owner_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            adapter, source, companion, _changed, workflow = copied_case(folder, 'samurai5_pc')
            specs = (automation.JobSpec('copy', source, folder / 'edited.bin'),)
            first = automation.prepare(workflow, specs)
            renamed = companion.with_name('STEAM_AUTOCLOUD.VDF')
            companion.rename(renamed)
            second = automation.prepare(workflow, specs)
            self.assertEqual(first.jobs[0].document.owner.raw, second.jobs[0].document.owner.raw)
            self.assertNotEqual(first.review_token, second.review_token)
            with self.assertRaises(SaveError):
                automation.apply(second, first.review_token)
            self.assertFalse(specs[0].destination.exists())


if __name__ == '__main__':
    unittest.main()

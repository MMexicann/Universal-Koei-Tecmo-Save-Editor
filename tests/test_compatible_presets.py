"""Reusable metadata cannot bypass exact-profile native edit protections."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.origins import origins_parser as origins
from koei_editor.games.wo3u import wo3u_parser as wo3
from koei_editor.shared import compatible_presets as presets, edit_presets, preset_portability
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared import verified_editor as dw8
from koei_editor.shared.preset_library import PresetLibrary
from tests.test_edit_presets import fixture_backend
from tests.test_origins_parser import fixture as origins_fixture
from tests.test_verified_editors import synthetic_raw
from tests.test_wo3u_format import procedural_raw


class CompatiblePresetTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.folder = Path(area.name).resolve()
        self.adapter = BoundScalarAdapter('origins', '.dat', origins)
        self.first = self.open_copy('first.dat', origins_fixture(gold=3456))
        self.second = self.open_copy('second.dat', origins_fixture(gold=7777))
        self.preset = presets.create(self.adapter, self.first, {'gold': 12345, 'skill_points': 456}, 'Resources')

    def open_copy(self, name, raw, adapter=None):
        path = self.folder / name
        path.write_bytes(raw)
        return (adapter or self.adapter).read_save(path)

    def test_distinct_save_compatibility_and_complete_selected_batch(self):
        self.assertNotEqual(self.first.sha256, self.second.sha256)
        pending = {'dlc_skill_points': 77}
        plan = presets.prepare(self.adapter, self.second, pending, self.preset, ('gold',))
        self.assertEqual(plan.pending, (('dlc_skill_points', 77),))
        self.assertEqual(dict(plan.result), {'gold': 12345, 'dlc_skill_points': 77})
        self.assertEqual({row.field.id for row in plan.rows}, {'gold', 'dlc_skill_points'})
        self.assertEqual(pending, {'dlc_skill_points': 77})
        self.assertEqual(presets.confirm(plan, self.adapter, self.second, pending), dict(plan.result))
        self.assertEqual(self.second.source.read_bytes(), self.second.raw)
        self.assertEqual(self.first.source.read_bytes(), self.first.raw)

    def test_source_bound_preset_remains_bound_and_separate_schema(self):
        source = edit_presets.create(self.adapter, self.first, {'gold': 12345}, 'Original')
        with self.assertRaises(SaveError):
            edit_presets.prepare(self.adapter, self.second, {}, source)
        with self.assertRaises(SaveError):
            edit_presets.loads(presets.dumps(self.preset))
        with self.assertRaises(SaveError):
            presets.loads(edit_presets.dumps(source))
        self.assertEqual(edit_presets.loads(edit_presets.dumps(source)), source)

    def test_strict_bounded_json_and_atomic_non_overwriting_metadata(self):
        raw = presets.dumps(self.preset)
        self.assertEqual(presets.loads(raw), self.preset)
        path = presets.export(self.preset, self.folder / 'resources.json')
        self.assertEqual(path.name, 'resources.compatible.edits.json')
        self.assertEqual(presets.load(path), self.preset)
        with self.assertRaises(FileExistsError):
            presets.export(self.preset, path)
        invalid = (b'', raw + b'{}', b'\xff', raw.replace(b'"version": 1', b'"version": true'),
                   raw.replace(b'"name":', b'"name": "duplicate", "name":', 1),
                   raw.replace(b'"experimental": false', b'"experimental": 0'),
                   raw.replace(b'12345', b'true'), raw.replace(b'12345', b'NaN'),
                   raw.replace(b'12345', b'12.5'), raw.replace(b'"name":', b'"unexpected": "x", "name":', 1))
        for value in invalid:
            with self.subTest(raw=value[:80]), self.assertRaises(SaveError):
                presets.loads(value)
        with self.assertRaises(SaveError):
            presets.loads(b' ' * (presets.MAX_BYTES + 1))
        for changed in (replace(self.preset, edits=self.preset.edits * 2),
                        replace(self.preset, edits=()), replace(self.preset, experimental=1),
                        replace(self.preset, name='bad\nname')):
            with self.assertRaises(SaveError):
                presets.dumps(changed)

    def test_exact_profile_native_revision_and_selected_definitions(self):
        for changed in (replace(self.preset, game_id='dw8xl'),
                        replace(self.preset, revision='steam-slot-17'),
                        replace(self.preset, policy_sha256='f' * 64),
                        replace(self.preset, edits=(replace(self.preset.edits[0], definition_sha256='e' * 64),)),
                        replace(self.preset, edits=(replace(self.preset.edits[0], value='12345'),))):
            with self.subTest(preset=changed), self.assertRaises(SaveError):
                presets.prepare(self.adapter, self.second, {}, changed)
        older = self.open_copy('older.dat', origins_fixture(revision=17))
        with self.assertRaisesRegex(SaveError, 'revision'):
            presets.prepare(self.adapter, older, {}, self.preset)
        with self.assertRaises(SaveError):
            presets.prepare(self.adapter, self.second, {}, self.preset, ())
        for selection in (('unknown',), ('gold', 'gold'), 'gold', (True,)):
            with self.subTest(selection=selection), self.assertRaises(SaveError):
                presets.prepare(self.adapter, self.second, {}, self.preset, selection)

    def test_mixed_staged_fields_require_explicit_safe_selection(self):
        adapter = BoundScalarAdapter('dw8xl', '.dat', dw8)
        document = self.open_copy('dw8.dat', synthetic_raw('dw8xl'), adapter)
        pending = {'gold': 1234, 'officer_0_attack': 123}
        with self.assertRaisesRegex(SaveError, 'portability'):
            presets.create(adapter, document, pending, 'Mixed')
        good = presets.create(adapter, document, pending, 'Resources only', ('gold',))
        self.assertEqual(tuple(edit.field for edit in good.edits), ('gold',))
        forged = replace(good, edits=good.edits + (presets.CompatibleEdit(
            'officer_0_attack', 222, edit_presets.field_definitions_sha256(adapter, document, ('officer_0_attack',))),))
        with self.assertRaisesRegex(SaveError, 'portability'):
            presets.prepare(adapter, document, {}, forged)
        plan = presets.prepare(adapter, document, {}, forged, ('gold',))
        self.assertEqual(dict(plan.result), {'gold': 1234})
        self.assertEqual(pending, {'gold': 1234, 'officer_0_attack': 123})

    def test_unqualified_profile_and_dynamic_ineligible_fields_are_rejected(self):
        adapter = BoundScalarAdapter('pw3', '.dat', dw8)
        document = self.open_copy('pw3.dat', synthetic_raw('pw3'), adapter)
        with self.assertRaisesRegex(SaveError, 'not qualified'):
            presets.create(adapter, document, {'character_0_attack': 123}, 'Not portable')
        policy = preset_portability.policy(self.adapter, self.first)
        self.assertNotIn('bond_0_level', policy.fields)
        self.assertNotIn('weapon_0000_upgrade', policy.fields)

    def test_fixed_wo3_resources_portable_between_distinct_native_style_snapshots(self):
        adapter = BoundScalarAdapter('wo3u', '.bin', wo3)
        first = self.open_copy('wo3-a.bin', procedural_raw(), adapter)
        second_raw = wo3.serialize(first, {'gems': 777})
        second = self.open_copy('wo3-b.bin', second_raw, adapter)
        plan_preset = presets.create(adapter, first, {'gems': 1234, 'orb_57': 3, 'material_6_144': 4}, 'Materials')
        plan = presets.prepare(adapter, second, {}, plan_preset)
        self.assertEqual(dict(plan.result), {'gems': 1234, 'orb_57': 3, 'material_6_144': 4})
        self.assertEqual(first.source.read_bytes(), first.raw)
        self.assertEqual(second.source.read_bytes(), second.raw)

    def test_current_experimental_ack_is_required_and_never_enabled_by_preset(self):
        experimental = replace(self.adapter, experimental=True)
        preset = presets.create(experimental, self.first, {'gold': 1000000}, 'Experimental')
        self.assertTrue(preset.experimental)
        with self.assertRaises(SaveError):
            presets.prepare(self.adapter, self.second, {}, preset)
        self.assertFalse(self.adapter.experimental)
        plan = presets.prepare(experimental, self.second, {}, preset)
        self.assertEqual(plan.experimental_count, 1)
        with self.assertRaises(SaveError):
            presets.prepare(experimental, self.second, {}, replace(preset, experimental=False))

    def test_stale_source_pending_session_or_plan_rejected(self):
        plan = presets.prepare(self.adapter, self.second, {}, self.preset)
        for adapter, doc, pending in ((replace(self.adapter), self.second, {}),
                                     (self.adapter, replace(self.second), {}),
                                     (self.adapter, self.second, {'dlc_skill_points': 12})):
            with self.assertRaises(SaveError):
                presets.confirm(plan, adapter, doc, pending)
        forged = replace(plan, result=(('gold', 999),))
        with self.assertRaises(SaveError):
            presets.confirm(forged, self.adapter, self.second, {})
        self.second.source.write_bytes(self.first.raw)
        with self.assertRaises(SaveError):
            presets.confirm(plan, self.adapter, self.second, {})

    def test_noop_assignment_unstages_target_edit_without_rewriting_source(self):
        noop = presets.create(self.adapter, self.first, {'gold': 7777}, 'Target original')
        plan = presets.prepare(self.adapter, self.second, {'gold': 99, 'skill_points': 44}, noop)
        self.assertEqual(dict(plan.result), {'skill_points': 44})
        self.assertEqual(next(row for row in plan.rows if row.field.id == 'gold').after, 7777)
        self.assertEqual(self.second.source.read_bytes(), self.second.raw)

    def test_apply_failure_restores_pending_and_undo_exactly(self):
        plan = presets.prepare(self.adapter, self.second, {'dlc_skill_points': 77}, self.preset)
        def fail_refresh():
            raise RuntimeError('UI unavailable')
        editor = SimpleNamespace(adapter=self.adapter, document=self.second,
                                 changes={'dlc_skill_points': 77}, history=[{'skill_points': 5}], refresh=fail_refresh)
        def accept(result):
            editor.history.append(dict(editor.changes))
            editor.changes = result
            editor.refresh()
        editor._accept_pending = accept
        with self.assertRaises(RuntimeError):
            presets.apply_plan(plan, editor)
        self.assertEqual(editor.changes, {'dlc_skill_points': 77})
        self.assertEqual(editor.history, [{'skill_points': 5}])

    def batch_editor(self, document, pending=None):
        editor = SimpleNamespace(adapter=self.adapter, document=document,
                                 changes=dict(pending or {}), history=[], refresh=lambda: None)
        def accept(result):
            if result != editor.changes:
                editor.history.append(dict(editor.changes))
                editor.changes = dict(result)
                editor.refresh()
        editor._accept_pending = accept
        return editor

    def test_multi_target_batch_preserves_unrelated_pending_and_each_undo(self):
        first = self.batch_editor(self.first, {'dlc_skill_points': 55})
        second = self.batch_editor(self.second, {'skill_points': 88})
        batch = presets.prepare_batch(self.preset, (('First', first), ('Second', second)), ('gold',))
        self.assertEqual(first.changes, {'dlc_skill_points': 55})
        self.assertEqual(second.changes, {'skill_points': 88})
        results = presets.apply_batch(batch)
        self.assertEqual(results, ({'gold': 12345, 'dlc_skill_points': 55}, {'gold': 12345, 'skill_points': 88}))
        self.assertEqual(first.history, [{'dlc_skill_points': 55}])
        self.assertEqual(second.history, [{'skill_points': 88}])
        self.assertEqual(first.document.source.read_bytes(), first.document.raw)
        self.assertEqual(second.document.source.read_bytes(), second.document.raw)

    def test_multi_target_stale_preview_and_mid_apply_failure_are_atomic(self):
        first, second = self.batch_editor(self.first), self.batch_editor(self.second)
        batch = presets.prepare_batch(self.preset, (('First', first), ('Second', second)))
        second.changes = {'dlc_skill_points': 77}
        with self.assertRaisesRegex(SaveError, 'Second:.*Pending edits changed'):
            presets.apply_batch(batch)
        self.assertEqual(first.changes, {})
        self.assertEqual(first.history, [])
        batch = presets.prepare_batch(self.preset, (('First', first), ('Second', second)))
        def fail():
            raise RuntimeError('Unavailable second target')
        second.refresh = fail
        with self.assertRaisesRegex(RuntimeError, 'Unavailable second target'):
            presets.apply_batch(batch)
        self.assertEqual((first.changes, first.history), ({}, []))
        self.assertEqual((second.changes, second.history), ({'dlc_skill_points': 77}, []))

    def test_batch_rejects_duplicate_copy_and_incompatible_selected_target(self):
        first, second = self.batch_editor(self.first), self.batch_editor(self.second)
        duplicate = self.batch_editor(self.first)
        for targets in ((), (('First', first), ('Again', first)), (('First', first), ('Alias', duplicate))):
            with self.assertRaises(SaveError):
                presets.prepare_batch(self.preset, targets)
        second.document = self.open_copy('older-batch.dat', origins_fixture(revision=17))
        with self.assertRaisesRegex(SaveError, 'Second:'):
            presets.prepare_batch(self.preset, (('First', first), ('Second', second)))
        self.assertEqual((first.changes, first.history), ({}, []))


class NativeDependencyPresetTests(unittest.TestCase):
    def test_target_reduction_state_and_unrelated_hidden_dependency_are_authoritative(self):
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        folder = Path(area.name).resolve()
        backend, raw = fixture_backend()
        adapter = BoundScalarAdapter('preset_fixture', '.dat', backend)
        source = folder / 'first.dat'
        source.write_bytes(raw)
        first = adapter.read_save(source)
        target = folder / 'second.dat'
        target.write_bytes(backend.serialize(first, {'gold': 5}))
        second = adapter.read_save(target)
        policy = preset_portability.PortabilityPolicy('fixture-resource-v1', 'preset_fixture',
                                                      frozenset(('gold',)), 'fixture-native-1', 'Procedural policy only')
        with patch.object(preset_portability, 'policy', return_value=policy):
            preset = presets.create(adapter, first, {'gold': 25}, 'Reduce from source')
            serialize = backend.serialize
            def reduction(document, changes):
                if changes.get('gold', 0) > document.payload[2]:
                    raise SaveError('Target resource supports reductions only')
                return serialize(document, changes)
            with patch.object(backend, 'serialize', side_effect=reduction):
                with self.assertRaisesRegex(SaveError, 'reductions only'):
                    presets.prepare(adapter, second, {}, preset)
            # Native final-map validation sees unrelated hidden pending fields.
            with self.assertRaisesRegex(SaveError, 'same physical weapon'):
                presets.prepare(adapter, second, {'left': 20}, preset)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(target.read_bytes(), second.raw)


class PresetLibraryTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.folder = Path(area.name).resolve()
        self.adapter = BoundScalarAdapter('origins', '.dat', origins)
        source = self.folder / 'copy.dat'
        source.write_bytes(origins_fixture())
        document = self.adapter.read_save(source)
        self.preset = presets.create(self.adapter, document, {'gold': 23456}, 'Named preset')
        self.library = PresetLibrary(self.folder / 'library')

    def test_named_library_idempotent_atomic_import_export_and_changed_metadata(self):
        self.assertEqual(self.library.scan().entries, ())
        first = self.library.save(self.preset)
        self.assertEqual(self.library.save(self.preset), first)
        self.assertEqual(len(self.library.scan().entries), 1)
        path = self.library.export(first, self.folder / 'export')
        self.assertEqual(self.library.import_path(path), first)
        first.path.write_bytes(presets.dumps(replace(self.preset, name='Foreign replacement')))
        scan = self.library.scan()
        self.assertEqual(scan.entries, ())
        self.assertEqual(len(scan.issues), 1)
        with self.assertRaises(SaveError):
            self.library.validate_entry(first)
        with self.assertRaises(SaveError):
            self.library.export(first, self.folder / 'second-export')

    def test_library_count_bounds_and_foreign_files_remain_untouched(self):
        first = self.library.save(self.preset)
        unrelated = self.library.directory / 'unrelated.txt'
        unrelated.write_bytes(b'Keep')
        with patch('koei_editor.shared.preset_library.MAX_PRESETS', 1):
            self.assertEqual(self.library.save(self.preset), first)
            with self.assertRaises(SaveError):
                self.library.save(replace(self.preset, name='Second'))
        self.assertEqual(unrelated.read_bytes(), b'Keep')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO unavailable')
    def test_metadata_fifo_rejected_without_blocking(self):
        path = self.folder / ('fifo' + presets.SUFFIX)
        os.mkfifo(path)
        with self.assertRaises(SaveError):
            presets.load(path)

    def test_duplicate_symlink_library_metadata_is_excluded(self):
        entry = self.library.save(self.preset)
        replacement = self.folder / 'metadata.json'
        replacement.write_bytes(entry.path.read_bytes())
        entry.path.unlink()
        try:
            entry.path.symlink_to(replacement)
        except OSError as error:
            self.skipTest(f'Symlink unavailable: {error}')
        self.assertEqual(self.library.scan().entries, ())
        with self.assertRaises(SaveError):
            self.library.save(self.preset)


if __name__ == '__main__':
    unittest.main()

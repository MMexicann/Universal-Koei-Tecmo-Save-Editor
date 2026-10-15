"""Original XL PS3 native-bound scalar workflow, ownership and context safety."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw7xl_ps3 import parser as backend
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared import ps3_copy
from tests import test_ps3_expansion as ps3_context


def editor_fixture():
    """Procedural typed records; not native gameplay or in-game evidence."""
    raw = bytearray((index * 43 + 17) & 255 for index in range(470303))
    raw[:4] = bytes.fromhex('11080200')
    raw[0xDD1F] = 0
    raw[0xC7C:0xC80] = (123456).to_bytes(4, 'big')
    for index in range(65):
        base = 0x2039 + index * 128
        for relative, value in ((6, 500), (8, 601), (10, 602), (12, 50), (14, 40),
                                (16, 0x421), (18, 0), (20, 1), (22, 0), (24, 7), (26, 1234)):
            raw[base + relative:base + relative + 2] = value.to_bytes(2, 'big')
    for index in range(1738):
        base = 0x4E39 + index * 20
        raw[base + 4:base + 6] = (0).to_bytes(2, 'big')
        raw[base + 6:base + 8] = (0).to_bytes(2, 'big')
    for index, flags, meter in ((0, 1, 432), (1, 3, 999), (2, 5, 400),
                                (3, 0, 400), (4, 1, 1001), (5, 1, 0)):
        base = 0x4E39 + index * 20
        raw[base + 4:base + 6] = flags.to_bytes(2, 'big')
        raw[base + 6:base + 8] = meter.to_bytes(2, 'big')
    return bytes(raw)


def copied_save(folder, raw=None, directory='BLUS30873-SAVEDATA'):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'APP.BIN'
    path.write_bytes(editor_fixture() if raw is None else raw)
    (folder / 'PARAM.SFO').write_bytes(ps3_context.PS3ContextTests.metadata(directory))
    return path


class DW7XLPS3EditorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.path = copied_save(self.folder / 'source')
        self.adapter = BoundScalarAdapter(backend.GAME_ID, '.bin', backend)
        self.document = self.adapter.read_save(self.path)

    def output(self, name='edited'):
        folder = self.folder / name
        folder.mkdir()
        (folder / 'PARAM.SFO').write_bytes((self.path.parent / 'PARAM.SFO').read_bytes())
        return folder / 'APP.BIN'

    def test_registered_profile_dispatch_and_shared_copied_save_self_test(self):
        from koei_editor.game_registry import get_game
        from koei_editor.shared.verified_self_test import run
        game = get_game('dw7xl_ps3')
        self.assertEqual(game.platform, 'PlayStation 3')
        self.assertEqual(game.extension, '.bin')
        self.assertIs(game.get_scalar_adapter().backend, backend)
        report = run('dw7xl_ps3', self.path, self.folder / 'self-test')
        self.assertTrue(report['success'])
        self.assertEqual(report['fields_checked'], 457)
        self.assertEqual(report['fields_changed'], 391)
        self.assertEqual(report['integrity_kind'], 'external')
        self.assertFalse(report['native_integrity_verified'])
        self.assertFalse(report['in_game_load_tested'])
        self.assertEqual((self.folder / 'self-test' / 'PARAM.SFO').read_bytes(),
                         (self.path.parent / 'PARAM.SFO').read_bytes())
        self.assertEqual(self.path.read_bytes(), self.document.raw)

    def test_complete_native_bound_fields_and_surgical_edits(self):
        fields = self.adapter.field_map(self.document)
        self.assertEqual(len(fields), 457)  # Gold + 65*7 + one unlearned meter.
        changes = {'gold': 700000, 'officer_0_health': 1000, 'officer_0_attack': 1400,
                   'officer_64_defense': 1400, 'officer_64_power': 100,
                   'officer_32_speed': 100, 'officer_64_skill_points': 9999,
                   'officer_64_active_weapon': 1, 'weapon_0_seal_meter': 0}
        pending = {}
        for key, value in changes.items():
            pending = self.adapter.stage(self.document, pending, key, value)
        self.assertEqual(pending, changes)
        raw = self.adapter.serialize(self.document, pending)
        self.assertEqual(len(raw), 470303)
        touched = {i for i, (before, after) in enumerate(zip(self.document.raw, raw)) if before != after}
        allowed = {i for key in changes for i in range(fields[key].offset, fields[key].offset + fields[key].size)}
        self.assertLessEqual(touched, allowed)
        reopened = self.adapter.decode(raw)
        for key, value in changes.items():
            self.assertEqual(fields[key].value(reopened.payload), value)
        self.assertEqual(raw[:4], self.document.raw[:4])
        self.assertEqual(raw[-0x5000:], self.document.raw[-0x5000:])
        self.assertEqual(self.path.read_bytes(), self.document.raw)

    def test_bounds_types_foreign_keys_and_full_pending_map_validation(self):
        mapping = self.adapter.field_map(self.document)
        for key in ('gold', 'officer_0_health', 'officer_0_attack', 'officer_64_skill_points'):
            field = mapping[key]
            for value in (field.minimum - 1, field.maximum + 1, True, '1', 1.0):
                with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                    self.adapter.stage(self.document, {}, key, value)
        for action in (lambda: self.adapter.serialize(self.document, {'unknown': 1}),
                       lambda: self.adapter.stage(self.document, {'unknown': 1}, 'gold', 10),
                       lambda: self.adapter.limit_values(self.document, {}, ['unknown']),
                       lambda: self.adapter.maximums(self.document, {'gold': True}),
                       lambda: self.adapter.review(self.document, {'gold': '1'})):
            with self.assertRaises(SaveError):
                action()
        self.assertEqual(self.adapter.serialize(self.document, {}), self.document.raw)
        staged = self.adapter.stage(self.document, {}, 'gold', 100)
        self.assertEqual(self.adapter.stage(self.document, staged, 'gold', 123456), {})
        self.assertEqual(staged, {'gold': 100})

    def test_max_native_caps_excludes_choices_meters_and_preserves_unusual_originals(self):
        pending = {'gold': 1, 'officer_0_health': 1, 'weapon_0_seal_meter': 2}
        result = self.adapter.maximums(self.document, pending)
        self.assertEqual(result['gold'], 999999)
        self.assertEqual(result['officer_0_health'], 1000)
        self.assertEqual(result['officer_64_attack'], 1400)
        self.assertEqual(result['weapon_0_seal_meter'], 2)
        self.assertNotIn('officer_0_active_weapon', result)
        self.assertEqual(self.adapter.maximums(self.document, {}, 'Equipment'), {})
        raw = bytearray(self.document.raw)
        raw[0xC7C:0xC80] = (4294967295).to_bytes(4, 'big')
        raw[0x2039 + 6:0x2039 + 8] = (65535).to_bytes(2, 'big')
        unusual = self.adapter.decode(bytes(raw))
        self.assertEqual(self.adapter.stage(unusual, {'gold': 100}, 'gold', 4294967295), {})
        self.assertEqual(self.adapter.stage(unusual, {'officer_0_health': 1}, 'officer_0_health', 65535), {})
        maximized = self.adapter.maximums(unusual, {})
        self.assertNotIn('gold', maximized)
        self.assertNotIn('officer_0_health', maximized)
        self.assertEqual(self.adapter.serialize(unusual, {}), bytes(raw))

    def test_experimental_signed_short_and_unsigned_gold_limits_keep_seal_and_ownership_guards(self):
        experimental = BoundScalarAdapter(backend.GAME_ID, '.bin', backend, experimental=True)
        for key, high in (('gold', 4294967295), ('officer_0_health', 32767),
                          ('officer_64_skill_points', 32767)):
            changed = experimental.stage(self.document, {}, key, high)
            self.assertEqual(changed, {key: high})
            self.assertEqual(experimental.field_map(self.document)[key].value(
                experimental.decode(experimental.serialize(self.document, changed)).payload), high)
            with self.assertRaises(SaveError):
                experimental.stage(self.document, {}, key, high + 1)
        for key, invalid in (('weapon_0_seal_meter', 433), ('officer_0_active_weapon', 2)):
            with self.assertRaises(SaveError):
                experimental.stage(self.document, {}, key, invalid)
        # No maximum or caller mode cache leaks into the ordinary adapter.
        with self.assertRaises(SaveError):
            self.adapter.stage(self.document, {}, 'officer_0_health', 32767)

    def test_active_equipment_requires_existing_owned_record_and_preserves_relationships(self):
        field = self.adapter.field_map(self.document)['officer_0_active_weapon']
        self.assertEqual([value for value, _ in backend.field_options(self.document, field)], [0, 1])
        self.assertEqual(self.adapter.stage(self.document, {}, field.id, 1), {field.id: 1})
        for reference in (2, 1738, 65535):
            raw = bytearray(self.document.raw)
            raw[0x2039 + 20:0x2039 + 22] = reference.to_bytes(2, 'big')
            if reference == 2:
                raw[0x4E39 + 2 * 20 + 4:0x4E39 + 2 * 20 + 6] = b'\0\0'
            document = self.adapter.decode(bytes(raw))
            with self.subTest(reference=reference), self.assertRaises(SaveError):
                self.adapter.stage(document, {}, field.id, 1)
            self.assertEqual([value for value, _ in backend.field_options(document, field)], [0])

    def test_only_existing_owned_unlearned_meters_edit_and_unknown_native_values_preserve(self):
        mapping = self.adapter.field_map(self.document)
        self.assertIn('weapon_0_seal_meter', mapping)
        for index in range(1, 6):
            key = f'weapon_{index}_seal_meter'
            self.assertNotIn(key, mapping)
            with self.assertRaises(SaveError):
                self.adapter.stage(self.document, {}, key, 0)
        for invalid in (-1, 433, 1000, True):
            with self.assertRaises(SaveError):
                self.adapter.stage(self.document, {}, 'weapon_0_seal_meter', invalid)
        raw = self.adapter.serialize(self.document, {'weapon_0_seal_meter': 0})
        self.assertEqual(raw[0x4E39 + 4:0x4E39 + 6], b'\0\1')
        self.assertEqual(raw[0x11BC + 0x3BE:0x11BC + 0x3FE],
                         self.document.raw[0x11BC + 0x3BE:0x11BC + 0x3FE])

    def test_suspended_battle_remains_inspectable_and_blocks_all_scalar_edits(self):
        for flag in (1, 2, 255):
            raw = bytearray(self.document.raw)
            raw[0xDD1F] = flag
            document = self.adapter.decode(bytes(raw))
            self.assertEqual(self.adapter.fields_for(document), ())
            self.assertEqual(self.adapter.serialize(document, {}), bytes(raw))
            with self.assertRaises(SaveError):
                self.adapter.stage(document, {}, 'gold', 10)
            self.assertTrue(any(row['group'] == 'Status' for row in backend.inspection_rows(document)))
            self.assertEqual(len(backend.weapons(document)), 1738)

    def test_context_bound_save_backup_restore_and_original_immutability(self):
        original_context = (self.path.parent / 'PARAM.SFO').read_bytes()
        destination = self.output()
        reopened = self.adapter.save_as(self.document, {'gold': 1}, destination)
        self.assertEqual(self.adapter.field_map(reopened)['gold'].value(reopened.payload), 1)
        self.assertEqual(reopened.context_digest, self.document.context_digest)
        self.assertEqual(self.path.read_bytes(), self.document.raw)
        self.assertEqual((destination.parent / 'PARAM.SFO').read_bytes(), original_context)
        snapshots = tuple((self.path.parent / 'UniversalEditorBackups').glob('*.BIN'))
        self.assertEqual(len(snapshots), 1)
        restored = self.adapter.restore(snapshots[0], destination.parent / 'restored.bin')
        self.assertEqual(restored.read_bytes(), self.document.raw)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, destination)
        (destination.parent / 'PARAM.SFO').write_bytes(original_context + b'changed opaque byte')
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, destination.parent / 'foreign.bin')
        with self.assertRaises(SaveError):
            self.adapter.restore(snapshots[0], destination.parent / 'foreign.bin')

    def test_stale_source_context_or_snapshot_cannot_write(self):
        for changed in ('source', 'context'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                source = copied_save(folder / 'source')
                document = self.adapter.read_save(source)
                output = copied_save(folder / 'output')
                output.unlink()
                target = source if changed == 'source' else source.parent / 'PARAM.SFO'
                target.write_bytes(target.read_bytes() + b'changed')
                with self.assertRaises(SaveError):
                    self.adapter.save_as(document, {}, output)
                self.assertFalse(output.exists())
        for fake in (replace(self.document, payload=self.document.payload[:-1] + b'x'),
                     replace(self.document, format=backend.Format()),
                     replace(self.document, context_digest=None)):
            with self.assertRaises(SaveError):
                self.adapter.serialize(fake, {})

    def test_late_context_race_retains_new_copy_and_rejects_success(self):
        destination = self.output()
        real_atomic = ps3_copy.atomic_new
        mutations = []
        def mutate_after_create(raw, path):
            result = real_atomic(raw, path)
            # Windows may spell the resolved temporary directory differently
            # (for example its long name instead of an inherited short alias).
            # Match the created file itself so the intended race always runs.
            if destination.exists() and Path(path).samefile(destination):
                (destination.parent / 'PARAM.SFO').write_bytes(
                    (destination.parent / 'PARAM.SFO').read_bytes() + b'changed')
                mutations.append(path)
            return result
        with patch.object(ps3_copy, 'atomic_new', side_effect=mutate_after_create), self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {'gold': 1}, destination)
        self.assertEqual(len(mutations), 1)
        self.assertTrue(destination.exists())
        self.assertEqual(self.path.read_bytes(), self.document.raw)

    def test_searchable_presentation_exposes_native_records_and_bound_hints(self):
        from koei_editor.games.dw7xl_ps3.editor import DW7XLPS3Presentation
        presentation = DW7XLPS3Presentation(backend, backend.GAME_ID)
        tables = presentation.inspection_tables(self.document)
        self.assertEqual([table.title for table in tables], ['Equipment', 'Purchased skills', 'Weapon inventory'])
        self.assertEqual(len(tables[0].rows), 65)
        self.assertEqual(len(tables[1].rows), 65)
        self.assertEqual(len(tables[2].rows), 1738)
        for field in self.adapter.fields_for(self.document):
            self.assertTrue(backend.field_hint(self.document, field))
        self.assertEqual(backend.record_label(65), 'Officer slot 65')

    def test_actual_tk_search_edit_review_undo_max_inspection_and_context_bound_save(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        from koei_editor.games.dw7xl_ps3.editor import Editor
        errors = []
        with patch('koei_editor.shared.verified_gui.messagebox.showerror',
                   side_effect=lambda *args: errors.append(args)), \
                patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',
                      return_value=str(self.path)):
            editor = Editor(root)
            editor.open()
            self.assertFalse(errors)
            editor.search.set('Gold')
            editor.refresh()
            self.assertEqual(editor.fields.get_children(), ('gold',))
            editor.fields.selection_set('gold')
            editor.value.set('42')
            editor.apply_selected()
            self.assertEqual(editor.changes, {'gold': 42})
            editor.review()
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.max_visible()
            self.assertEqual(editor.changes, {'gold': 999999})
            editor.undo()
            editor.stage_values({'gold': 42})
            editor.show_inspector()
            self.assertEqual(len(editor.presentation.inspection_tables(editor.document)[2].rows), 1738)
            destination = self.output('gui')
            editor.save_to(destination)
            self.assertFalse(errors)
            self.assertEqual(self.adapter.field_map(editor.document)['gold'].value(editor.document.payload), 42)
            self.assertEqual(self.path.read_bytes(), self.document.raw)

    def test_native_both_regional_exports_surgical_fields_save_and_restore_when_supplied(self):
        value = os.environ.get('DW7XL_PS3_SAVE_COPIES')
        if not value:
            self.skipTest('Set DW7XL_PS3_SAVE_COPIES to original US/EU decrypted XL exports with original PARAM.SFO.')
        references = tuple(Path(item) for item in value.split(os.pathsep) if item)
        self.assertTrue(references)
        for reference in references:
            with self.subTest(region=reference.parent.name), tempfile.TemporaryDirectory() as temporary:
                raw, metadata = reference.read_bytes(), (reference.parent / 'PARAM.SFO').read_bytes()
                folder = Path(temporary)
                source = copied_save(folder, raw)
                (folder / 'PARAM.SFO').write_bytes(metadata)
                document = self.adapter.read_save(source)
                self.assertEqual(self.adapter.serialize(document, {}), raw)
                mapping = self.adapter.field_map(document)
                pending = {}
                for key in ('gold', 'officer_0_health', 'officer_0_attack', 'officer_64_skill_points'):
                    pending = self.adapter.stage(document, pending, key, mapping[key].minimum)
                reopened = self.adapter.save_as(document, pending, folder / 'edited.bin')
                allowed = {index for key in pending for index in range(mapping[key].offset,
                           mapping[key].offset + mapping[key].size)}
                touched = {i for i, (a, b) in enumerate(zip(raw, reopened.raw)) if a != b}
                self.assertLessEqual(touched, allowed)
                for key, edited in pending.items():
                    self.assertEqual(mapping[key].value(reopened.payload), edited)
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual((folder / 'PARAM.SFO').read_bytes(), metadata)
                self.assertEqual(reference.read_bytes(), raw)
                self.assertEqual((reference.parent / 'PARAM.SFO').read_bytes(), metadata)
                self.assertEqual(document.context_digest, hashlib.sha256(metadata).hexdigest())


if __name__ == '__main__':
    unittest.main()

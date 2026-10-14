"""Procedural original PS3 DW8 checks and optional native modified public export."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw8_ps3 import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.scalar_presentation import ScalarPresentation
from tests import test_ps3_expansion as ps3_context


def procedural_raw():
    raw = bytearray((i * 31 + 19) % 256 for i in range(parser.SAVE_SIZE))
    raw[:4] = parser.SIGNATURE
    raw[0xBD:0xC1] = (123456).to_bytes(4, 'big')
    raw[0x21CF9:0x21CFD] = (321).to_bytes(2, 'big') + (987).to_bytes(2, 'big')
    return bytes(raw)


def context(folder, title=parser.TITLE_DIRECTORY):
    Path(folder).joinpath('PARAM.SFO').write_bytes(ps3_context.PS3ContextTests.metadata(title))


class OriginalDw8Ps3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'APP.BIN'; self.raw = procedural_raw(); self.source.write_bytes(self.raw)
        context(self.folder)
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)
        self.document = self.adapter.read_save(self.source)

    def test_shared_inspector_displays_export_identity_and_read_only_progression(self):
        tables = ScalarPresentation(parser, parser.GAME_ID).inspection_tables(self.document)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].columns, ('Group', 'Record / field', 'Opened value'))
        self.assertEqual(tables[0].rows, (
            ('Export identity', 'Original US PSN export', parser.TITLE_DIRECTORY),
            ('Export identity', 'Native revision', '0x13011300'),
            ('Export identity', 'Game data bytes', len(self.raw)),
            ('Progression', 'Ambition fame (read only)',
             int.from_bytes(self.raw[0x221D5:0x221D7], 'big'))))
        self.assertEqual(self.document.raw, self.raw)

    def test_exact_noop_and_every_resource_surgical_big_endian_readback(self):
        self.assertEqual(self.adapter.serialize(self.document, {}), self.raw)
        self.assertEqual(len(self.adapter.fields_for(self.document)), 3)
        for field in self.adapter.fields_for(self.document):
            value = field.value(self.raw)
            changes = self.adapter.stage(self.document, {}, field.id, value // 2)
            self.assertEqual(self.adapter.stage(self.document, changes, field.id, value), {})
            self.assertEqual(len(self.adapter.review(self.document, changes)), 1)
            output = self.adapter.serialize(self.document, changes)
            touched = {i for i, (a, b) in enumerate(zip(self.raw, output)) if a != b}
            self.assertLessEqual(touched, set(range(field.offset, field.offset + field.size)))
            self.assertEqual(output[field.offset:field.offset + field.size], (value // 2).to_bytes(field.size, 'big'))
            self.assertEqual(self.adapter.maximums(self.document, changes), changes)
            self.assertEqual(self.adapter.limit_values(self.document, changes, [field.id]), {})
        self.assertEqual(self.document.raw, self.raw)

    def test_bounds_typed_noops_pending_maps_frozen_identity_and_geometry(self):
        for value in (-1, 123457, True, 123456.0, '1', None):
            with self.subTest(value=value), self.assertRaises(SaveError):
                self.adapter.stage(self.document, {}, 'gold', value)
        for pending in ({'unknown': 1}, {'gold': True}, [], None):
            with self.assertRaises(SaveError):
                self.adapter.serialize(self.document, pending)
        for doc in (replace(self.document, format=replace(parser.FORMAT)),
                    replace(self.document, source=None),
                    replace(self.document, raw=bytearray(self.raw)),
                    replace(self.document, payload=self.raw[:-1]),
                    replace(self.document, context_digest=None)):
            with self.assertRaises(SaveError):
                self.adapter.serialize(doc, {})
        for raw in (self.raw[:-1], self.raw + b'x', b'\0' * parser.SAVE_SIZE):
            with self.assertRaises(SaveError):
                self.adapter.decode(raw)
        raw = bytearray(self.raw); raw[0xBD:0xC1] = b'\xff' * 4
        document = parser.decode(bytes(raw))
        self.assertEqual(self.adapter.stage(document, {}, 'gold', 0xFFFFFFFF), {})
        self.assertEqual(self.adapter.serialize(document, {'gold': 0xFFFFFFFF}), bytes(raw))
        with self.assertRaises(SaveError):
            parser.decode(self.raw, 'dw8xl_ps3')

    def test_required_title_context_full_digest_and_safe_storage(self):
        target = self.folder / 'edited.bin'
        saved = self.adapter.save_as(self.document, {'gold': 3}, target)
        self.assertEqual(saved.raw, target.read_bytes())
        self.assertEqual(self.source.read_bytes(), self.raw)
        backup = self.adapter.backup(self.document)
        restored = self.folder / 'restored.bin'; self.adapter.restore(backup, restored)
        self.assertEqual(restored.read_bytes(), self.raw)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, target)
        context(self.folder, 'NPUB31449-SAVEDATA')
        for action in (lambda: self.adapter.read_save(self.source),
                       lambda: self.adapter.save_as(self.document, {}, self.folder / 'foreign.bin'),
                       lambda: self.adapter.restore(backup, self.folder / 'foreign-restore.bin')):
            with self.assertRaises(SaveError): action()
        context(self.folder)
        companion = self.folder / 'PARAM.SFO'
        companion.write_bytes(companion.read_bytes() + b'opaque-unparsed-test-data')
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, self.folder / 'changed-context.bin')
        context(self.folder)
        original_backup = parser.backup
        def race(doc):
            result = original_backup(doc); self.source.write_bytes(b'x' * parser.SAVE_SIZE); return result
        with patch.object(parser, 'backup', side_effect=race), self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, self.folder / 'race.bin')
        self.assertFalse((self.folder / 'race.bin').exists())
        self.source.write_bytes(self.raw)
        (self.folder / 'PARAM.SFO').unlink()
        with self.assertRaises(SaveError): self.adapter.read_save(self.source)

    def test_source_and_context_copy_aliases_rejected(self):
        linked = self.folder / 'alias.bin'
        os.link(self.source, linked)
        with self.assertRaises(SaveError): self.adapter.read_save(linked)
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, self.folder / 'aliased-source.bin')
        linked.unlink()
        try:
            linked.symlink_to(self.source)
        except OSError:
            return
        with self.assertRaises(SaveError): self.adapter.read_save(linked)
        alias_folder = self.folder / 'directory-alias'
        alias_folder.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, alias_folder / 'edited.bin')

    def test_same_title_companion_change_after_atomic_save_is_rejected(self):
        destination_folder = self.folder / 'postwrite'
        destination_folder.mkdir()
        context(destination_folder)
        target = destination_folder / 'edited.bin'
        real_atomic_new = parser.atomic_new
        injections = []

        def change_context_after_write(raw, destination):
            result = real_atomic_new(raw, destination)
            if Path(destination).resolve() == target.resolve():
                injections.append(True)
                companion = destination_folder / 'PARAM.SFO'
                companion.write_bytes(companion.read_bytes() + b'same-title-opaque-change')
            return result

        with patch.object(parser, 'atomic_new', side_effect=change_context_after_write):
            try:
                with self.assertRaises(SaveError):
                    self.adapter.save_as(self.document, {'gold': 12}, target)
            finally:
                self.assertEqual(injections, [True], 'The postwrite context fault must be injected exactly once.')
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(target.read_bytes(), parser.serialize(self.document, {'gold': 12}))

    def test_same_title_companion_change_during_save_readback_is_rejected(self):
        destination_folder = self.folder / 'readback'
        destination_folder.mkdir()
        context(destination_folder)
        target = destination_folder / 'edited.bin'
        real_read_save = parser.read_save
        injections = []

        def change_context_before_readback(path, game_id=parser.GAME_ID):
            if Path(path).resolve() == target.resolve():
                injections.append(True)
                companion = destination_folder / 'PARAM.SFO'
                companion.write_bytes(companion.read_bytes() + b'same-title-readback-change')
            return real_read_save(path, game_id)

        with patch.object(parser, 'read_save', side_effect=change_context_before_readback):
            try:
                with self.assertRaises(SaveError):
                    self.adapter.save_as(self.document, {'gold': 12}, target)
            finally:
                self.assertEqual(injections, [True], 'The read-back context fault must be injected exactly once.')
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_same_title_companion_change_after_atomic_restore_is_rejected(self):
        from koei_editor.shared import copy_storage
        backup = self.adapter.backup(self.document)
        destination_folder = self.folder / 'postrestore'
        destination_folder.mkdir()
        context(destination_folder)
        target = destination_folder / 'restored.bin'
        real_atomic_new = copy_storage.atomic_new
        injections = []

        def change_context_after_restore(raw, destination):
            result = real_atomic_new(raw, destination)
            if Path(destination).resolve() == target.resolve():
                injections.append(True)
                companion = destination_folder / 'PARAM.SFO'
                companion.write_bytes(companion.read_bytes() + b'same-title-restore-change')
            return result

        with patch.object(copy_storage, 'atomic_new', side_effect=change_context_after_restore):
            try:
                with self.assertRaises(SaveError):
                    self.adapter.restore(backup, target)
            finally:
                self.assertEqual(injections, [True], 'The postrestore context fault must be injected exactly once.')
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(target.read_bytes(), self.raw)

    def test_actual_tk_resource_undo_review_theme_save_and_restore(self):
        import tkinter as tk
        from koei_editor.games.dw8_ps3.editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        root.withdraw()
        try:
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)), \
                 patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                editor.open(); errors.assert_not_called()
            editor.show_inspector()
            root.update()
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel): child.destroy()
            editor.fields.selection_set('gold'); editor.value.set('12'); editor.apply_selected()
            self.assertEqual(editor.changes, {'gold': 12})
            editor.undo(); self.assertEqual(editor.changes, {})
            editor.value.set('12'); editor.apply_selected(); editor.review()
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel): child.destroy()
            editor.apply_theme('Dark')
            target = self.folder / 'gui-edited.bin'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                 patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                editor.save_as(); errors.assert_not_called()
            self.assertEqual(target.read_bytes(), parser.serialize(self.document, {'gold': 12}))
            self.assertEqual(self.source.read_bytes(), self.raw)
            backup = next((self.folder / 'UniversalEditorBackups').glob('*.BIN'))
            restored = self.folder / 'gui-restored.bin'
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(backup)), \
                 patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(restored)), \
                 patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                editor.restore(); errors.assert_not_called()
            self.assertEqual(restored.read_bytes(), self.raw)
        finally:
            root.destroy()

    def test_optional_native_modified_public_export_and_all_fields(self):
        path = os.environ.get('DW8_PS3_REFERENCE_COPY')
        if not path: self.skipTest('Optional publicly modified native PS3 export.')
        document = parser.read_save(path)
        self.assertTrue(document.format.sample_verified)
        self.assertFalse(document.format.game_load_verified)
        self.assertEqual(parser.serialize(document, {}), document.raw)
        for field in parser.fields_for(document):
            output = parser.serialize(document, {field.id: 0})
            touched = {i for i, (a, b) in enumerate(zip(document.raw, output)) if a != b}
            self.assertLessEqual(touched, set(range(field.offset, field.offset + field.size)))


if __name__ == '__main__': unittest.main()

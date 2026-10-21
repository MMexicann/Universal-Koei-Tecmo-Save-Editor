"""PS4 common-core edits and context-bound file operations; procedural bytes."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl import ps4_export as p
from koei_editor.game_registry import get_game
from tests.scalar_contract import ScalarContractTests
from tests.test_dw8xl_vita import procedural_raw
from tests.test_conversion import write_copy
from koei_editor.games.p5strikers_ps4.context import title_only_sfo


class PS4ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = p.GAME_ID

    def fixture_bytes(self):
        context = self.folder / 'sce_sys' / 'param.sfo'
        context.parent.mkdir()
        context.write_bytes(title_only_sfo().replace(b'CUSA19640', b'CUSA00397'))
        return procedural_raw()[:-1] + bytes(p.SAVE_SIZE - p.PAYLOAD_SIZE)

    def test_edit_scope_dynamic_records_unstage_higher_original_and_no_max(self):
        fields = self.adapter.field_map(self.document)
        self.assertIn('weapon_0_rank_0', fields)
        self.assertNotIn('weapon_0_rank_2', fields)  # Unusual original rank is read only.
        for key, value in (('gold', 12345), ('weapon_0_rank_0', 7), ('officer_0_compatibility_0', 50)):
            pending = self.adapter.stage(self.document, {}, key, value)
            reopened = self.adapter.decode(self.adapter.serialize(self.document, pending))
            self.assertEqual(fields[key].value(reopened.payload), value)
            self.assertEqual(reopened.raw[p.PAYLOAD_SIZE:], self.document.raw[p.PAYLOAD_SIZE:])
        self.assertEqual(self.adapter.maximums(self.document, {}), {})
        higher = bytearray(self.raw)
        higher[0x105:0x109] = (12345678).to_bytes(4, 'little')
        doc = p.decode(bytes(higher))
        self.assertEqual(p.stage(doc, {'gold': 12}, 'gold', 12345678), {})
        self.assertEqual(p.serialize(doc, {}), bytes(higher))
        with self.assertRaises(SaveError):
            p.serialize(doc, {'gold': True})

    def test_metadata_required_exact_on_save_restore_and_self_test_copy(self):
        destination = self.folder / 'other' / 'APP.BIN'
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {'gold': 9}, destination)
        p.prepare_self_test_copy(self.document, destination)
        p.prepare_self_test_copy(self.document, destination)
        result = self.adapter.save_as(self.document, {'gold': 9}, destination)
        self.assertEqual(result.context_digest, self.document.context_digest)
        snapshot = self.adapter.backup(self.document)
        context = destination.parent / 'sce_sys' / 'param.sfo'
        context.write_bytes(context.read_bytes() + b'\0')
        with self.assertRaises(SaveError):
            self.adapter.restore(snapshot, destination.with_name('restore.bin'))
        with self.assertRaises(SaveError):
            p.prepare_self_test_copy(self.document, destination)
        self.assertFalse(destination.with_name('restore.bin').exists())

    def test_source_and_destination_context_races_are_detected(self):
        original_atomic = p.atomic_new
        destination = self.folder / 'raced.bin'
        metadata = self.folder / 'sce_sys' / 'param.sfo'
        def raced(raw, path):
            result = original_atomic(raw, path)
            if Path(path) == destination:
                metadata.write_bytes(metadata.read_bytes() + b'\0')
            return result
        with patch.object(p, 'atomic_new', side_effect=raced), self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {'gold': 9}, destination)
        self.assertEqual(self.source.read_bytes(), self.raw)
        with self.assertRaises(SaveError):
            p.backup(replace(self.document, context_digest=''))


class PS4GuiTests(unittest.TestCase):
    def test_registered_editor_stage_review_undo_and_actual_save(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                source = write_copy(folder / 'source', p.GAME_ID)
                original = source.read_bytes()
                editor = get_game(p.GAME_ID).create_editor(root, root)
                with patch('tkinter.filedialog.askopenfilename', return_value=str(source)):
                    editor.open()
                editor.search.set('gold')
                root.update()
                editor.fields.selection_set('gold')
                editor.selected()
                editor.value.set('12345')
                editor.apply_selected()
                self.assertEqual(editor.changes, {'gold': 12345})
                editor.review()
                for child in root.winfo_children():
                    if isinstance(child, tk.Toplevel):
                        child.destroy()
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.fields.selection_set('gold')
                editor.selected()
                editor.value.set('12345')
                editor.apply_selected()
                editor.apply_theme('Dark')
                destination = source.with_name('edited.bin')
                with patch('tkinter.filedialog.asksaveasfilename', return_value=str(destination)), \
                     patch('tkinter.messagebox.showerror') as errors:
                    editor.save_as()
                    errors.assert_not_called()
                reopened = p.read_save(destination)
                self.assertEqual(p.field_map(reopened)['gold'].value(reopened.payload), 12345)
                self.assertEqual(source.read_bytes(), original)
        finally:
            root.destroy()

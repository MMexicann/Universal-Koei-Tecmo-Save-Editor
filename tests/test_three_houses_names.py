"""Native-name framing and copy workflows; procedural fixtures are not game saves."""
import os
from pathlib import Path
import struct
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.three_houses import names, parser
from koei_editor.games.three_houses.editor import Editor
from tests.test_three_houses import procedural_slot, sealed


def named_slot(revision=23, text='Byleth', closer=b'\x1bN1'):
    result = bytearray(procedural_slot(revision))
    offset = 12 + names.OFFSETS[revision]
    encoded = b'\x1bN0' + text.encode('utf-8') + closer
    result[offset:offset + 40] = encoded.ljust(40, b'\0')
    return sealed(result)


class NameFormatTests(unittest.TestCase):
    def test_both_native_revisions_and_closing_controls_surgical_mixed_edits(self):
        for revision in (13, 23):
            for closer in (b'\x1bN0', b'\x1bN1'):
                with self.subTest(revision=revision, closer=closer):
                    raw = named_slot(revision, closer=closer)
                    document = parser.decode(raw)
                    field = parser.field_map(document)['protagonist_name']
                    self.assertEqual(field.offset, 12 + names.OFFSETS[revision])
                    self.assertEqual(field.kind, 'text')
                    self.assertFalse(field.maxable)
                    self.assertIsNone(field.experimental_maximum)
                    self.assertEqual(parser.serialize(document, {}), raw)
                    for target in ('A', 'Eight888', 'A " B\\C'):
                        pending = parser.stage(document, {'gold': 11999}, field.id, target)
                        output = parser.serialize(document, pending)
                        self.assertEqual(names.framed_name(output[field.offset:field.offset + 40]), (target, closer))
                        self.assertEqual(parser.field_map(parser.decode(output))[field.id].value(output), target)
                        gold = parser.field_map(document)['gold']
                        allowed = set(range(4)) | set(range(field.offset, field.offset + 40)) | set(range(gold.offset, gold.offset + 4))
                        self.assertLessEqual({i for i, (a, b) in enumerate(zip(raw, output)) if a != b}, allowed)
                        self.assertEqual(output, sealed(output))
                        self.assertEqual(parser.stage(document, pending, field.id, 'Byleth'), {'gold': 11999})
                        self.assertEqual(parser.maximums(document, pending), pending)
                        self.assertEqual(parser.limit_values(document, pending, [field.id]), {})
                    self.assertEqual(document.raw, raw)

    def test_existing_unicode_and_long_names_are_exact_noops_and_undo(self):
        for text in ('Byleth is longer', '先生'):
            raw = named_slot(text=text)
            document = parser.decode(raw)
            key = 'protagonist_name'
            self.assertEqual(parser.field_map(document)[key].value(raw), text)
            pending = parser.stage(document, {}, key, 'New Name')
            self.assertEqual(parser.stage(document, pending, key, text), {})
            self.assertEqual(parser.serialize(document, {key: text}), raw)
            self.assertEqual(parser.review(document, pending)[0][1:], (text, 'New Name'))

    def test_invalid_text_pending_maps_and_numeric_types_fail_closed(self):
        document = parser.decode(named_slot())
        key = 'protagonist_name'
        for value in ('', '123456789', '日本', 'A\nB', 'A\x1bB', 'A\x00B', 'A\x7fB', 5, True, b'Name', None):
            with self.subTest(value=value):
                for operation in (lambda: parser.stage(document, {}, key, value),
                                  lambda: parser.serialize(document, {key: value})):
                    with self.assertRaises(SaveError):
                        operation()
        for operation in (lambda: parser.stage(document, {key: ''}, 'gold', 0),
                          lambda: parser.review(document, {key: ''}),
                          lambda: parser.maximums(document, {key: ''}),
                          lambda: parser.stage(document, {}, 'gold', '0')):
            with self.assertRaises(SaveError):
                operation()

    def test_malformed_framing_unknown_owner_and_inactive_protagonist_are_preserved(self):
        raw = named_slot()
        offset = 12 + names.OFFSETS[23]
        variants = []
        for relative, data in ((0, b'BAD'), (3, b'\xff'), (9, b'\x1bN2'), (13, b'\x01')):
            result = bytearray(raw)
            result[offset + relative:offset + relative + len(data)] = data
            variants.append(sealed(result))
        result = bytearray(raw)
        result[offset:offset + 40] = b'\x1bN0\x1bN1' + bytes(34)
        variants.append(sealed(result))
        for owner_change in ('missing', 'duplicate', 'unjoined'):
            result = bytearray(raw)
            base = 12 + 0x644
            if owner_change == 'missing':
                struct.pack_into('<h', result, base + 0x24, 35)
            elif owner_change == 'duplicate':
                struct.pack_into('<h', result, base + 0x24C + 0x24, 1)
            else:
                struct.pack_into('<I', result, base + 0xAC, 1)
            variants.append(sealed(result))
        for variant in variants:
            document = parser.decode(variant)
            self.assertNotIn('protagonist_name', parser.field_map(document))
            self.assertEqual(parser.serialize(document, {}), variant)
            self.assertEqual(parser.serialize(document, {'gold': 1})[offset:offset + 40], variant[offset:offset + 40])
        damaged = bytearray(raw)
        damaged[offset + 3] ^= 1
        with self.assertRaises(SaveError):
            parser.decode(damaged)

    @unittest.skipUnless(os.environ.get('THREE_HOUSES_REVIEW_COPIES'), 'Private reviewed native copies absent')
    def test_native_names_both_revisions_markers_surgical_and_source_preserved(self):
        exercised = set()
        for filename in os.environ['THREE_HOUSES_REVIEW_COPIES'].split(os.pathsep):
            source = Path(filename)
            raw = source.read_bytes()
            document = parser.decode(raw)
            field = parser.field_map(document)['protagonist_name']
            opened = names.framed_name(raw[field.offset:field.offset + 40])
            self.assertEqual(parser.serialize(document, {}), raw)
            output = parser.serialize(document, {field.id: 'Editor'})
            self.assertEqual(names.framed_name(output[field.offset:field.offset + 40]), ('Editor', opened[1]))
            self.assertLessEqual({i for i, (a, b) in enumerate(zip(raw, output)) if a != b},
                                 set(range(4)) | set(range(field.offset, field.offset + 40)))
            self.assertEqual(parser.field_map(parser.decode(output))[field.id].value(output), 'Editor')
            self.assertEqual(source.read_bytes(), raw)
            exercised.add((document.profile.revision, opened[1]))
        self.assertEqual(exercised, {(13, b'\x1bN1'), (23, b'\x1bN1'), (23, b'\x1bN0')})


class NameGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.errors = []
        mocked = patch('koei_editor.shared.verified_gui.messagebox.showerror', side_effect=lambda *args: self.errors.append(args))
        mocked.start()
        self.addCleanup(mocked.stop)

    def workflow(self, raw):
        source = self.folder / 'slot-copy'
        source.write_bytes(raw)
        editor = Editor(self.root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
            editor.open()
        editor.group.set('Customization')
        editor.search.set('Protagonist name')
        editor.refresh()
        key = 'protagonist_name'
        self.assertIn(key, editor.fields.get_children())
        editor.fields.selection_set(key)
        editor.selected()
        editor.value.set('New Name')
        editor.apply_selected()
        self.assertEqual(editor.changes, {key: 'New Name'})
        editor.review()
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.fields.selection_set(key)
        editor.value.set('New Name')
        editor.apply_selected()
        editor.max_visible()
        self.assertEqual(editor.changes, {key: 'New Name'})
        editor.apply_theme('Dark')
        destination = self.folder / 'edited'
        editor.save_to(destination)
        self.assertFalse(self.errors)
        self.assertEqual(parser.field_map(parser.read_save(destination))[key].value(destination.read_bytes()), 'New Name')
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(parser.restore(editor.backup, self.folder / 'restored').read_bytes(), raw)

    def test_text_search_apply_review_undo_max_copy_backup_restore(self):
        self.workflow(named_slot())

    @unittest.skipUnless(os.environ.get('THREE_HOUSES_REVIEW_COPIES'), 'Private reviewed native copies absent')
    def test_native_text_copy_workflow(self):
        exercised = set()
        for filename in os.environ['THREE_HOUSES_REVIEW_COPIES'].split(os.pathsep):
            raw = Path(filename).read_bytes()
            document = parser.decode(raw)
            field = parser.field_map(document)['protagonist_name']
            pair = document.profile.revision, names.framed_name(raw[field.offset:field.offset + 40])[1]
            if pair in exercised:
                continue
            self.folder = self.folder / f'case-{len(exercised)}'
            self.folder.mkdir()
            self.workflow(raw)
            exercised.add(pair)
        self.assertEqual(len(exercised), 3)


if __name__ == '__main__':
    unittest.main()

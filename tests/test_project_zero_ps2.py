"""Procedural boundary checks plus opt-in, private genuine PSU qualification."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.project_zero_ps2 import parser


def header(name, size, mode):
    raw = bytearray(512)
    struct.pack_into('<H', raw, 0, mode)
    struct.pack_into('<I', raw, 4, size)
    raw[64:64 + len(name)] = name.encode('ascii')
    return bytes(raw)


def body(points=50000, tiers=(3, 2, 1), films=None):
    raw = bytearray(b'\x6d' * parser.SIZE)
    raw[:48] = bytes(48)
    struct.pack_into('<II', raw, 16, 1, 1)
    raw[parser.CAMERA:parser.CAMERA + 3] = bytes(tiers)
    struct.pack_into('<Q', raw, parser.CAMERA + 16, points)
    if films is not None:
        raw[parser.ITEMS + 1:parser.ITEMS + 5] = bytes(films)
    struct.pack_into('<I', raw, 0, sum(raw[16:]))
    return bytes(raw)


def fixture(order=(0, 1, 2), points=50000, tiers=(3, 2, 1), films=None):
    raw = bytearray(header(parser.PRODUCT + '0', 6, 0x8427)
                    + header('.', 0, 0x8427) + header('..', 0, 0x8427))
    for name, data in [('icon.sys', b'unknown-icon-metadata!')] + [
            (parser.PRODUCT + str(i), parser.EMPTY if i == 2 else body(points, tiers, films)) for i in order]:
        raw.extend(header(name, len(data), 0x8497))
        raw.extend(data)
        raw.extend(b'\xa7' * (-len(data) % 1024))
    return bytes(raw)


class ProjectZeroTests(unittest.TestCase):
    def assert_surgical(self, document, changes):
        output = parser.serialize(document, changes)
        reopened = parser.decode(output)
        fields = parser.field_map(document)
        allowed = {i for key in changes for i in range(fields[key].offset, fields[key].offset + fields[key].size)}
        allowed.update(i for entry in document.entries if entry.occupied
                       for i in range(entry.offset, entry.offset + 4))
        touched = {i for i, (a, b) in enumerate(zip(document.raw, output)) if a != b}
        self.assertLessEqual(touched, allowed)
        self.assertEqual(len(output), len(document.raw))
        self.assertEqual(reopened.payload, parser.changed_payload(document, changes))
        for key, value in changes.items():
            self.assertEqual(fields[key].value(reopened.payload), value)
        changed_items = {(fields[key].slot, int(key.rsplit('_', 1)[1]) + 1)
                         for key in changes if '_film_' in key}
        self.assertEqual(tuple(row for row in parser.item_records(document)
                               if row[:2] not in changed_items),
                         tuple(row for row in parser.item_records(reopened)
                               if row[:2] not in changed_items))
        return reopened

    def test_film_reductions_preserve_selection_ownership_and_other_items(self):
        document = parser.decode(fixture())
        raw = bytearray(document.raw)
        for entry in document.entries:
            if entry.occupied:
                raw[entry.offset + parser.ITEMS + 1:entry.offset + parser.ITEMS + 5] = bytes((30, 0, 99, 255))
                struct.pack_into('<I', raw, entry.offset, sum(raw[entry.offset + 16:entry.offset + parser.SIZE]))
        document = parser.decode(bytes(raw))
        fields = parser.field_map(document)
        self.assertIn('slot_0_film_1', fields)
        self.assertIn('slot_0_film_3', fields)
        self.assertNotIn('slot_0_film_2', fields)
        self.assertNotIn('slot_0_film_4', fields)
        self.assertFalse(fields['slot_0_film_1'].maxable)
        self.assertEqual(fields['slot_0_film_1'].label,
                         'Type-14 film stock (reduce only; retain one)')
        self.assertEqual(fields['slot_0_film_3'].label,
                         'Type-74 film stock (reduce only; retain one)')
        labeled = {row[1]: row[2] for row in parser.inventory_records(document) if row[1] in parser.FILM_LABELS}
        self.assertEqual(labeled, {1: 'Type-14 film', 2: 'Type-37 film',
                                   3: 'Type-74 film', 4: 'Type-90 film'})
        for bad in (0, -1, 31, True, 1.0):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, 'slot_0_film_1', bad)
        changes = {'slot_0_film_1': 1, 'slot_1_film_3': 2}
        reopened = self.assert_surgical(document, changes)
        self.assertEqual(parser.camera_records(document), parser.camera_records(reopened))
        self.assertEqual(parser.stage(document, changes, 'slot_0_film_1', 30), {'slot_1_film_3': 2})
        self.assertEqual(parser.limit_values(document, changes, changes), {})
        self.assertEqual(parser.inventory_records(document)[1][2], 'Type-14 film')

    def test_variable_export_order_noop_and_each_field_surgery(self):
        for order in ((0, 1, 2), (2, 0, 1)):
            document = parser.decode(fixture(order))
            self.assertEqual(parser.serialize(document, {}), document.raw)
            self.assertEqual(len(parser.fields_for(document)), 8)
            self.assertEqual(len(parser.item_records(document)), 400)
            self.assertEqual(parser.slot_records(document)[-1][1], 'Empty' if order[-1] == 2 else 'Occupied')
            for field in parser.fields_for(document):
                pending = parser.stage(document, {}, field.id, 0)
                self.assert_surgical(document, pending)
                self.assertEqual(parser.stage(document, pending, field.id, field.value(document.payload)), {})
            self.assert_surgical(document, {f.id: 0 for f in parser.fields_for(document)})

    def test_invalid_edits_max_and_unusual_values_preserved(self):
        document = parser.decode(fixture(points=2**63 + 55, tiers=(5, 255, 1)))
        self.assertNotIn('slot_0_range', parser.field_map(document))
        for bad in (True, False, -1, 2**64, '3', 3.0, None):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, 'slot_0_points', bad)
        for bad in ('slot_2_points', 'story', [], None, 5):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, bad, 1)
        for bad in (None, [], 'x'):
            with self.assertRaises(SaveError):
                parser.serialize(document, bad)
        pending = {'slot_0_points': 10}
        self.assertEqual(parser.maximums(document, pending), pending)
        self.assertEqual(parser.limit_values(document, pending, pending), {})
        self.assertEqual(parser.serialize(document, {}), document.raw)
        reopened = self.assert_surgical(document, pending)
        self.assertEqual(parser.camera_records(reopened)[0][2], 5)

    def test_container_corruption_foreign_names_modes_counts_and_truncation(self):
        raw = fixture()
        cases = [raw[:-1], raw + b'\0', bytes(len(raw)), bytearray(raw), memoryview(raw)]
        for offset, value in ((0, 0x10), (64, ord('X')), (512, 0x10), (1024, 0x10)):
            damaged = bytearray(raw); damaged[offset] = value; cases.append(bytes(damaged))
        for count in (0, 2, 129, 0xFFFFFFFF):
            damaged = bytearray(raw); struct.pack_into('<I', damaged, 4, count); cases.append(bytes(damaged))
        for damaged in cases:
            with self.subTest(kind=type(damaged).__name__, size=len(damaged)), self.assertRaises(SaveError):
                parser.decode(damaged)
        with self.assertRaises(SaveError):
            parser.decode(raw, 'dw4xl_ps2')

    def test_each_native_checksum_empty_slot_and_snapshot_forgery(self):
        document = parser.decode(fixture())
        for entry in document.entries:
            if entry.slot < 0:
                continue
            damaged = bytearray(document.raw)
            damaged[entry.offset + parser.SIZE - 1] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(bytes(damaged))
        for forged in (replace(document, raw=bytearray(document.raw)),
                       replace(document, payload=document.payload[:-1] + b'\0'),
                       replace(document, entries=()),
                       replace(document, format=replace(parser.FORMAT, id='foreign'))):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})

    def test_safe_storage_restore_corrupt_backup_aliases_and_source_race(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); source = folder / 'input.psu'; raw = fixture(); source.write_bytes(raw)
            document = parser.read_save(source)
            snapshot = parser.backup(document)
            self.assertEqual(parser.restore(snapshot, folder / 'restore.psu').read_bytes(), raw)
            saved = parser.save_as(document, {'slot_0_points': 1}, folder / 'edited.psu')
            self.assertEqual(parser.field_map(saved)['slot_0_points'].value(saved.payload), 1)
            self.assertEqual(source.read_bytes(), raw)
            with self.assertRaises(FileExistsError):
                parser.save_as(document, {}, source)
            alias = folder / 'alias.psu'
            try:
                alias.symlink_to(source)
            except OSError:
                alias = source
            with self.assertRaises(FileExistsError):
                parser.save_as(document, {}, alias)
            actual = parser.backup
            def mutate(doc):
                result = actual(doc); source.write_bytes(raw[:-1] + b'\0'); return result
            with patch.object(parser, 'backup', side_effect=mutate), self.assertRaises(SaveError):
                parser.save_as(document, {}, folder / 'race.psu')
            self.assertFalse((folder / 'race.psu').exists())
            source.write_bytes(raw)
            snapshot.write_bytes(raw[:-1] + b'\0')
            with self.assertRaises(SaveError):
                parser.restore(snapshot, folder / 'corrupt.psu')

    def test_genuine_exports_surgical_edits_safe_storage_and_self_test(self):
        setting = os.environ.get('PROJECT_ZERO_PS2_SAVE_COPIES')
        if not setting:
            self.skipTest('Private original European PSU exports are not supplied.')
        from koei_editor.shared.adapter_contract import BoundScalarAdapter
        from koei_editor.shared.verified_self_test import _run
        paths = [Path(entry) for entry in setting.split(os.pathsep)]
        hashes = set()
        for path in paths:
            original = parser.read_save(path); hashes.add(original.sha256)
            self.assertEqual(parser.serialize(original, {}), original.raw)
            for field in parser.fields_for(original):
                self.assert_surgical(original, {field.id: field.minimum})
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary); source = folder / 'native-copy.psu'; source.write_bytes(original.raw)
                document = parser.read_save(source)
                pending = {f.id: f.minimum for f in parser.fields_for(document)}
                saved = parser.save_as(document, pending, folder / 'edited.psu')
                self.assertEqual(saved.raw, self.assert_surgical(document, pending).raw)
                self.assertEqual(parser.restore(parser.backup(document), folder / 'restored.psu').read_bytes(), original.raw)
                report = _run(BoundScalarAdapter(parser.GAME_ID, '.psu', parser), parser.GAME_ID,
                              source, folder / 'self-test')
                self.assertTrue(report['success']); self.assertTrue(report['checksum_verified'])
                self.assertFalse(report['in_game_load_tested'])
                self.assertEqual(path.read_bytes(), original.raw)
        self.assertGreaterEqual(len(hashes), 2)

    def test_real_tk_inspection_search_undo_review_and_save(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as error:
            self.skipTest('Tk display unavailable: ' + type(error).__name__)
        self.addCleanup(root.destroy)
        from koei_editor.games.project_zero_ps2.editor import Editor
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); source = folder / 'gui-copy.psu'
            setting = os.environ.get('PROJECT_ZERO_PS2_SAVE_COPIES')
            source.write_bytes(Path(setting.split(os.pathsep)[0]).read_bytes()
                               if setting else fixture(films=(30, 20, 10, 5)))
            editor = Editor(root, parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            self.assertIsNotNone(editor.document)
            film = next((f for f in parser.fields_for(editor.document)
                         if '_film_' in f.id and f.maximum > 1), None)
            if not setting:
                self.assertIsNotNone(film, 'The procedural GUI case must exercise editable film stocks.')
            if film is not None:
                editor.search.set('film stock'); root.update()
                self.assertEqual(set(editor.fields.get_children()),
                                 {f.id for f in parser.fields_for(editor.document) if '_film_' in f.id})
                editor.search.set(film.label.split(' film')[0]); root.update()
                self.assertIn(film.id, editor.fields.get_children())
                editor.stage_values({film.id: 1})
                self.assertEqual(len(editor.adapter.review(editor.document, editor.changes)), 1)
                editor.undo(); self.assertEqual(editor.changes, {})
                editor.search.set(''); root.update()
            field = parser.fields_for(editor.document)[0]
            editor.stage_values({field.id: 0})
            self.assertEqual(len(editor.adapter.review(editor.document, editor.changes)), 1)
            editor.undo(); self.assertEqual(editor.changes, {})
            self.assertEqual(len(editor.presentation.inspection_tables(editor.document)), 3)
            editor.search.set('camera points'); root.update()
            self.assertGreater(len(editor.fields.get_children()), 0)
            self.assertLess(len(editor.fields.get_children()), len(parser.fields_for(editor.document)))
            editor.stage_values({field.id: 0})
            before = set(root.winfo_children())
            editor.review(); root.update()
            dialogs = [w for w in root.winfo_children() if w not in before and isinstance(w, tk.Toplevel)]
            self.assertEqual(len(dialogs), 1)
            dialogs[0].destroy()
            editor.save_to(folder / 'gui-edited.psu')
            self.assertEqual(field.value(editor.document.payload), 0)

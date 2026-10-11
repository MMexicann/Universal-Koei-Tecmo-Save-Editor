"""Procedural, native-copy, safe-storage and actual Tk checks; no game execution."""
from dataclasses import replace
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.meruru_plus_vita import parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests
from tests.test_meruru_dx_candidate import procedural_candidate as pc_candidate


def metadata(title='PCSE00296', extra=b''):
    key = b'PARENT_DIRECTORY\0'
    value = ('/' + title).encode('ascii') + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value + extra)


def fixture():
    """Distinctive generated opaque bytes, never a playable save."""
    raw = bytearray((i * 31 + 11) % 256 for i in range(parser.SAVE_SIZE))
    struct.pack_into('<I', raw, 0, 20100403)
    offset = 32
    for tag, size in enumerate(parser.CHUNK_SIZES, 1):
        struct.pack_into('<II', raw, offset, tag, size)
        offset += size + 8
    struct.pack_into('<II', raw, offset, 1024, 8091)
    struct.pack_into('<I', raw, 0xCF9C, 123456)
    for slot in range(13):
        base = 0xCFA8 + slot * 0x1B0
        # Current gauges exceed the stored bases, as in the genuine export.
        struct.pack_into('<12I', raw, base, slot, 53, 129076, 294, 337, 222,
                         89, 177, 97, 50, 42, 58)
    raw[0x3A441:0x3A441 + 2099 * 48] = b'\xFF' * (2099 * 48)
    struct.pack_into('<12I', raw, 0x3A441, 17, 22, 0x42F00000,
                     1, 2, 3, 4, 5, 10, 11, 12, 5)
    struct.pack_into('<12I', raw, 0x3A441 + 100 * 48, 24, 78, 0x42700000,
                     1, 2, 3, 4, 5, 10, 11, 12, 2)
    return bytes(raw)


def write_context(folder, raw=None):
    path = Path(folder) / 'sce_sys' / 'param.sfo'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(metadata() if raw is None else raw)
    return path


class MeruruPlusContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '', parser)
        self.raw = fixture()
        self.source = self.folder / 'USR-DATA0000'
        self.source.write_bytes(self.raw)
        write_context(self.folder)
        self.document = self.adapter.read_save(self.source)
        # The shared contract needs only the explicitly bound native extension.
        from types import SimpleNamespace
        self.game = SimpleNamespace(extension='')


class MeruruPlusFormatTests(unittest.TestCase):
    def test_every_writable_field_is_surgical_and_unusual_values_preserved(self):
        raw = fixture()
        doc = parser.decode(raw)
        self.assertEqual(parser.serialize(doc, {}), raw)
        fields = parser.fields_for(doc)
        self.assertEqual(len(fields), 118)
        for field in fields:
            original = field.value(raw)
            base_gauge = (field.group == 'Base character stats'
                          and field.id.rsplit('_', 1)[-1] in ('hp', 'mp', 'lp'))
            value = field.maximum if base_gauge else (field.minimum if original != field.minimum else field.maximum)
            pending = parser.stage(doc, {}, field.id, value)
            out = parser.serialize(doc, pending)
            allowed = set(range(field.offset, field.offset + field.size))
            changed = {i for i, (left, right) in enumerate(zip(raw, out)) if left != right}
            self.assertTrue(changed)
            self.assertLessEqual(changed, allowed)
            self.assertEqual(parser.field_map(parser.decode(out))[field.id].value(out), value)
            self.assertEqual(parser.stage(doc, pending, field.id, original), {})
        altered = bytearray(raw)
        struct.pack_into('<I', altered, 0xCF9C, 0xFFFFFFFF)
        struct.pack_into('<I', altered, 0xCFA8 + 24, 2500)
        unusual = parser.decode(bytes(altered))
        self.assertEqual(parser.maximums(unusual, {}), {})
        self.assertEqual(parser.limit_values(unusual, {}, ['cole', 'character_0_hp']), {})
        self.assertEqual(parser.serialize(unusual, {}), bytes(altered))
        self.assertEqual(parser.stage(unusual, {'cole': 5}, 'cole', 0xFFFFFFFF), {})
        self.assertEqual(parser.stage(unusual, {}, 'character_0_hp', 2500), {})
        with self.assertRaises(SaveError):
            parser.stage(unusual, {}, 'character_0_hp', 999)

    def test_exact_platform_fingerprint_all_boundaries_and_frozen_snapshot(self):
        raw = fixture()
        for invalid in (bytearray(raw), raw[:-1], raw + b'\0', bytes(len(raw)), pc_candidate()):
            with self.assertRaises(SaveError):
                parser.decode(invalid)
        offset = 32
        headers = [0]
        for size in parser.CHUNK_SIZES:
            headers.extend((offset, offset + 4))
            offset += 8 + size
        headers.extend((offset, offset + 4))
        headers.extend(0xCFA8 + slot * 0x1B0 for slot in range(13))
        for position in headers:
            altered = bytearray(raw)
            altered[position] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(bytes(altered))
        doc = parser.decode(raw)
        for forged in (replace(doc, payload=raw[:-1]), replace(doc, raw=bytearray(raw)),
                       replace(doc, format=replace(parser.FORMAT, id='meruru_dx')),
                       replace(doc, context_sha256='wrong')):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})
        with self.assertRaises(SaveError):
            parser.decode(raw, 'meruru_dx')
        # Unknown reserved/trailer bytes need not be zero and are preserved.
        altered = bytearray(raw)
        altered[4] ^= 1
        altered[-1] ^= 1
        self.assertEqual(parser.serialize(parser.decode(bytes(altered)), {}), bytes(altered))

    def test_current_gauges_are_reductions_base_stats_are_distinct_and_max_disabled(self):
        doc = parser.decode(fixture())
        pending = parser.stage(doc, {}, 'character_0_hp', 999)
        out = parser.serialize(doc, pending)
        self.assertEqual(out[0xCFA8 + 12:0xCFA8 + 24], doc.raw[0xCFA8 + 12:0xCFA8 + 24])
        self.assertEqual(out[0xCFA8 + 4:0xCFA8 + 12], doc.raw[0xCFA8 + 4:0xCFA8 + 12])
        for key in ('character_0_hp', 'character_0_mp', 'character_0_lp'):
            value = parser.field_map(doc)[key].value(doc.raw)
            with self.assertRaises(SaveError):
                parser.stage(doc, {}, key, value - 1)
            with self.assertRaises(SaveError):
                parser.serialize(doc, {key: value - 1})
            raised = parser.stage(doc, {}, key, value + 1)
            self.assertEqual(parser.stage(doc, raised, key, value), {})
        for key in ('character_0_current_hp', 'character_0_current_mp', 'character_0_current_lp'):
            field = parser.field_map(doc)[key]
            self.assertGreater(field.maximum, parser.field_map(doc)[key.replace('_current_', '_')].value(doc.raw))
            changes = parser.stage(doc, {}, key, field.minimum)
            self.assertEqual(parser.maximums(doc, changes), changes)
            for value in (field.maximum + 1, field.minimum - 1, True, '1', 1.0):
                with self.assertRaises(SaveError):
                    parser.stage(doc, {}, key, value)
        for blocked in ('character_0_level', 'character_0_exp', 'calendar', 'item_0_quality',
                        'development_points', 'character_0_equipment', 'story_complete'):
            with self.assertRaises(SaveError):
                parser.stage(doc, {}, blocked, 1)
        with self.assertRaises(SaveError):
            parser.maximums(doc, {'cole': True})
        with self.assertRaises(SaveError):
            parser.stage(doc, {'unknown': 0}, 'cole', 10)

    def test_readonly_numeric_items_and_named_characters(self):
        doc = parser.decode(fixture())
        roster = parser.character_records(doc)
        self.assertEqual(len(roster), 13)
        self.assertEqual(roster[0], ('Meruru', 53, 129076, 294, 337, 222, 89, 177, 97, 50, 42, 58))
        rows = parser.item_records(doc)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][:5], ('Basket', 1, 17, 22, '120'))
        self.assertEqual(rows[1][:5], ('Container', 1, 24, 78, '60'))
        self.assertEqual(parser.record_label(1), 'Meruru')
        self.assertEqual(parser.record_label(13), 'Pamela')

    def test_context_bounds_wrong_title_duplicates_and_nonidentity_data(self):
        good = metadata()
        self.assertEqual(parser.parent_directory(good), '/PCSE00296')
        for bad in (good[:-1], good + b'\0' * 4096, metadata('PCSG00200'), b'\0' * 64,
                    bytearray(good)):
            with self.assertRaises(SaveError):
                parser.parent_directory(bad)
        for offset, value in ((4, 0x102), (8, 0xFFFFFFFF), (12, 0), (16, 129),
                              (24, 0xFFFFFFFF), (28, 0xFFFFFFFF), (32, 0xFFFFFFFF)):
            bad = bytearray(good)
            struct.pack_into('<I', bad, offset, value)
            with self.assertRaises(SaveError):
                parser.parent_directory(bytes(bad))
        key = b'PARENT_DIRECTORY\0'
        value = b'/PCSE00296\0'
        duplicate = (struct.pack('<5I', 0x46535000, 0x101, 52, 52 + len(key), 2)
                     + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) * 2
                     + key + value)
        with self.assertRaises(SaveError):
            parser.parent_directory(duplicate)

    def test_source_and_destination_context_changes_aliases_and_restore_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'USR-DATA0000'
            source.write_bytes(fixture())
            with self.assertRaises(SaveError):
                parser.read_save(source)
            companion = write_context(folder)
            doc = parser.read_save(source)
            destination = folder / 'edited'
            saved = parser.save_as(doc, {'cole': 765432}, destination)
            self.assertEqual(parser.field_map(saved)['cole'].value(saved.raw), 765432)
            self.assertEqual(source.read_bytes(), fixture())
            snapshot = parser.backup(doc)
            self.assertEqual(parser.restore(snapshot, folder / 'restored').read_bytes(), fixture())
            other = folder / 'other'
            other.mkdir()
            write_context(other, metadata(extra=b'different opaque context'))
            for operation in (lambda: parser.save_as(doc, {}, other / 'edited'),
                              lambda: parser.restore(snapshot, other / 'restored')):
                with self.assertRaises(SaveError):
                    operation()
            self.assertFalse((other / 'edited').exists())
            self.assertFalse((other / 'restored').exists())
            companion.write_bytes(metadata(extra=b'changed'))
            with self.assertRaises(SaveError):
                parser.backup(doc)
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, folder / 'changed-context')
            companion.write_bytes(metadata())
            source.write_bytes(fixture()[:-1] + bytes([fixture()[-1] ^ 1]))
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, folder / 'changed-source')
            source.write_bytes(fixture())
            if os.name != 'nt':
                alias = folder / 'alias'
                alias.symlink_to(source)
                with self.assertRaises(FileExistsError):
                    parser.save_as(doc, {}, alias)
            forged = bytearray(fixture())
            forged[32] ^= 1
            snapshot.write_bytes(forged)
            manifest = json.loads(snapshot.with_suffix('.json').read_text())
            import hashlib
            manifest['sha256'] = hashlib.sha256(forged).hexdigest()
            snapshot.with_suffix('.json').write_text(json.dumps(manifest))
            with self.assertRaises(SaveError):
                parser.restore(snapshot, folder / 'damaged-restoration')
            self.assertFalse((folder / 'damaged-restoration').exists())

    def test_minimal_self_test_context_contains_only_public_title(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            document = parser.decode(fixture())
            path = folder / 'self-test' / 'input-copy'
            parser.prepare_self_test_copy(document, path)
            raw = (path.parent / 'sce_sys' / 'param.sfo').read_bytes()
            self.assertEqual(parser.parent_directory(raw), '/PCSE00296')
            self.assertEqual(struct.unpack_from('<I', raw, 16)[0], 1)
            self.assertNotIn(b'ACCOUNT', raw)
            self.assertNotIn(b'PARAMS', raw)
            path.write_bytes(fixture())
            copied = parser.read_save(path)
            self.assertEqual(parser.serialize(copied, {}), fixture())
            with self.assertRaises(SaveError):
                parser.backup(document)

    def test_registered_copied_self_test_and_title_only_context(self):
        from koei_editor.shared.verified_self_test import run
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'USR-DATA0000'
            source.write_bytes(fixture())
            write_context(folder, metadata(extra=b'opaque source-only metadata'))
            output = folder / 'self-test'
            report = run(parser.GAME_ID, source, output)
            self.assertTrue(report['success'])
            self.assertEqual(report['fields_checked'], 118)
            self.assertEqual(report['fields_changed'], 0)
            self.assertEqual(report['integrity_kind'], 'external')
            self.assertFalse(report['native_integrity_verified'])
            self.assertFalse(report['in_game_load_tested'])
            sfo = (output / 'sce_sys' / 'param.sfo').read_bytes()
            self.assertEqual(parser.parent_directory(sfo), '/PCSE00296')
            self.assertNotIn(b'opaque source-only metadata', sfo)
            self.assertEqual(source.read_bytes(), fixture())

    def test_optional_genuine_export_all_fields_and_safe_storage(self):
        selected = os.environ.get('MERURU_PLUS_VITA_EXPORT_COPY')
        if not selected:
            self.skipTest('No private decrypted PCSE00296 gameplay export provided.')
        original = Path(selected)
        with original.open('rb') as stream:
            raw = stream.read(parser.SAVE_SIZE + 1)
        with (original.parent / 'sce_sys' / 'param.sfo').open('rb') as stream:
            sfo = stream.read(parser.MAX_SFO_SIZE + 1)
        self.assertEqual(parser.parent_directory(sfo), '/PCSE00296')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'USR-DATA0000'
            source.write_bytes(raw)
            write_context(folder, sfo)
            doc = parser.read_save(source)
            self.assertEqual(parser.serialize(doc, {}), raw)
            self.assertEqual(len(parser.character_records(doc)), 13)
            for field in parser.fields_for(doc):
                original_value = field.value(raw)
                base_gauge = (field.group == 'Base character stats'
                              and field.id.rsplit('_', 1)[-1] in ('hp', 'mp', 'lp'))
                value = field.maximum if base_gauge else (field.minimum if original_value != field.minimum else field.maximum)
                if value == original_value or (base_gauge and value < original_value):
                    continue
                out = parser.serialize(doc, {field.id: value})
                self.assertEqual(out[:field.offset], raw[:field.offset])
                self.assertEqual(out[field.offset + field.size:], raw[field.offset + field.size:])
                self.assertEqual(parser.field_map(parser.decode(out))[field.id].value(out), value)
            saved = parser.save_as(doc, {'cole': 600000, 'character_0_attack': 123}, folder / 'edited')
            self.assertEqual(parser.read_save(saved.source).raw, saved.raw)
            snapshot = parser.backup(doc)
            self.assertEqual(parser.restore(snapshot, folder / 'restored').read_bytes(), raw)
            self.assertEqual(source.read_bytes(), raw)

    def test_actual_tk_named_controls_undo_review_save_and_backup(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as error:
            self.skipTest('Tk display unavailable: ' + type(error).__name__)
        self.addCleanup(root.destroy)
        from koei_editor.games.meruru_plus_vita.editor import Editor
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'USR-DATA0000'
            selected = os.environ.get('MERURU_PLUS_VITA_EXPORT_COPY')
            if selected:
                original = Path(selected)
                with original.open('rb') as stream:
                    raw = stream.read(parser.SAVE_SIZE + 1)
                with (original.parent / 'sce_sys' / 'param.sfo').open('rb') as stream:
                    sfo = stream.read(parser.MAX_SFO_SIZE + 1)
            else:
                raw, sfo = fixture(), metadata()
            source.write_bytes(raw)
            write_context(folder, sfo)
            editor = Editor(root, parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            self.assertEqual(len(editor.fields.get_children()), 118)
            self.assertEqual(editor.record_name(parser.field_map(editor.document)['character_0_attack']), 'Meruru')
            editor.search.set('Mimi')
            root.update()
            self.assertEqual(len(editor.fields.get_children()), 9)
            editor.search.set('')
            root.update()
            editor.stage_values({'character_0_attack': 123, 'character_0_current_hp': 200, 'cole': 345678})
            self.assertEqual(len(parser.review(editor.document, editor.changes)), 3)
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.stage_values({'character_0_attack': 123, 'cole': 345678})
            children = set(root.winfo_children())
            editor.review()
            root.update()
            review_dialogs = [child for child in root.winfo_children()
                              if child not in children and isinstance(child, tk.Toplevel)]
            self.assertEqual(len(review_dialogs), 1)
            review_dialogs[0].destroy()
            destination = folder / 'edited'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                editor.save_as()
            self.assertEqual(parser.field_map(parser.read_save(destination))['cole'].value(destination.read_bytes()), 345678)
            self.assertEqual(source.read_bytes(), raw)
            self.assertTrue(list((folder / 'UniversalEditorBackups').glob('*.json')))


if __name__ == '__main__':
    unittest.main()

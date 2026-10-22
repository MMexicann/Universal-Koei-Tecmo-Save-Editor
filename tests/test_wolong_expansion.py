"""Wo Long pending-input and changed-source protections."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wolong import wolong_parser as parser
from koei_editor.games.wolong.wolong_editor import Editor
from tests.test_wolong_format import procedural_payload
from tests.test_wolong_format import seal


def named_battle_set_payload(name='Opened set'):
    original = procedural_payload()
    root = json.loads(original[parser.JSON_OFFSET:].rstrip(b'\0'))
    root['UIData']['ui_battleset_slot_data_info'] = [
        {'UiBattleSetSlotInfo': {'str': name if index == 3 else '', 'opaque': [17, False]}}
        for index in range(50)]
    root['PlayerData']['battleset_data_list'] = [
        {'BattleSetData': {'enable_flag': index == 3, 'equipment': [999, -1],
                          'level': 50, 'xing': [10, 20, 30, 40, 50], 'unknown': '\u2603'}}
        for index in range(50)]
    body = json.dumps(root, ensure_ascii=False, separators=(', ', ': ')).encode('utf-8')
    return seal(original[:parser.JSON_OFFSET] + body + bytes(parser.SAVE_SIZE - parser.JSON_OFFSET - len(body)))


class WolongBattleSetNameTests(unittest.TestCase):
    def test_text_gui_search_review_undo_and_saved_copy(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'copy.bin'
            original = named_battle_set_payload()
            source.write_bytes(original)
            editor = Editor(root)
            errors = []
            with patch('koei_editor.shared.verified_gui.messagebox.showerror', side_effect=lambda *args: errors.append(args)), \
                    patch('koei_editor.shared.verified_gui.messagebox.showinfo'), \
                    patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
                editor.group.set('Battle set names')
                editor.search.set('Battle set 4')
                editor.refresh()
                self.assertEqual(editor.fields.get_children(), ('battle_set_3_name',))
                editor.fields.selection_set('battle_set_3_name')
                editor.selected()
                self.assertIn('Experimental custom-name edit', editor.selection_info.get())
                self.assertIn('no native enabled-set rename', editor.selection_info.get())
                self.assertFalse(editor.experimental)
                editor.value.set('Ranged set')
                editor.apply_selected()
                self.assertEqual(editor.changes, {'battle_set_3_name': 'Ranged set'})
                editor.max_visible()
                editor.review()
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.fields.selection_set('battle_set_3_name')
                editor.value.set('Ranged set')
                editor.apply_selected()
                destination = Path(directory) / 'edited.bin'
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                    editor.save_as()
                self.assertEqual(errors, [])
                self.assertEqual(source.read_bytes(), original)
                reopened = parser.read_save(destination)
                self.assertEqual(parser.field_map(reopened)['battle_set_3_name'].value(reopened.payload), 'Ranged set')
                self.assertTrue(list((source.parent / 'WarriorsEditorBackups').glob('*.bin')))

    def test_only_enabled_existing_sets_and_lexical_surgical_writer(self):
        document = parser.decode(named_battle_set_payload())
        fields = parser.field_map(document)
        names = [f for f in fields.values() if f.group == 'Battle set names']
        self.assertEqual(len(names), 1)
        field = names[0]
        self.assertEqual((field.id, field.kind, field.slot), ('battle_set_3_name', 'text', 4))
        value = 'Ranged "A"\\B'
        changes = parser.stage(document, {'sen': 123}, field.id, value)
        payload = parser.changed_payload(document, changes)
        expected = document.payload[parser.JSON_OFFSET:].rstrip(b'\0')
        for selected in sorted((fields[key] for key in changes), key=lambda f: f.offset, reverse=True):
            offset = selected.offset - parser.JSON_OFFSET
            token = json.dumps(changes[selected.id]).encode('ascii')
            expected = expected[:offset] + token + expected[offset + selected.size:]
        self.assertEqual(payload[parser.JSON_OFFSET:].rstrip(b'\0'), expected)
        reopened = parser.decode(parser.serialize(document, changes))
        self.assertEqual(parser.field_map(reopened)[field.id].value(reopened.payload), value)
        self.assertEqual(document.payload[:0x3C], reopened.payload[:0x3C])
        self.assertEqual(document.payload[0x7C:parser.JSON_OFFSET], reopened.payload[0x7C:parser.JSON_OFFSET])
        before = json.loads(document.payload[parser.JSON_OFFSET:].rstrip(b'\0'))
        after = json.loads(reopened.payload[parser.JSON_OFFSET:].rstrip(b'\0'))
        before['UIData']['ui_battleset_slot_data_info'][3]['UiBattleSetSlotInfo']['str'] = value
        before['PlayerData']['sen'] = 123
        self.assertEqual(before, after)
        self.assertEqual(parser.maximums(document, changes), changes)
        self.assertEqual(parser.limit_values(document, changes, [field.id, 'sen']), {})
        self.assertFalse(field.maxable)
        self.assertEqual([(f.id, old, new) for f, old, new in parser.review(document, {field.id: value})],
                         [(field.id, 'Opened set', value)])
        self.assertEqual(parser.stage(document, {field.id: value}, field.id, 'Opened set'), {})
        self.assertEqual(parser.serialize(document, {}), document.raw)

    def test_names_have_no_acquisition_equipment_or_stat_side_effects(self):
        document = parser.decode(named_battle_set_payload())
        for key, value in (('battle_set_2_name', 'New'), ('battle_set_3_enable_flag', True),
                           ('battle_set_3_xing', 1), ('battle_set_3_name', ''),
                           ('battle_set_3_name', 'A' * 17), ('battle_set_3_name', '\u00e9'),
                           ('battle_set_3_name', 'line\nbreak'), ('battle_set_3_name', '\0'),
                           ('battle_set_3_name', 4), ('battle_set_3_name', True)):
            with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                parser.stage(document, {}, key, value)
        changed = parser.stage(document, {}, 'battle_set_3_name', 'A' * 16)
        self.assertEqual(parser.field_map(parser.decode(parser.serialize(document, changed)))['battle_set_3_name'].maximum, 16)

    def test_unusual_original_names_restore_exactly_and_optional_schema_fails_closed(self):
        for name in ('', '\u65e5\u672c\u8a9e', 'A' * 80):
            document = parser.decode(named_battle_set_payload(name))
            self.assertEqual(parser.serialize(document, {}), document.raw)
            changes = parser.stage(document, {}, 'battle_set_3_name', 'Revised')
            self.assertEqual(parser.stage(document, changes, 'battle_set_3_name', name), {})
        original = named_battle_set_payload()
        root = json.loads(original[parser.JSON_OFFSET:].rstrip(b'\0'))
        for value in (None, {}, [], [1], root['UIData']['ui_battleset_slot_data_info'][:-1]):
            root['UIData']['ui_battleset_slot_data_info'] = value
            body = json.dumps(root).encode('utf-8')
            document = parser.decode(seal(original[:parser.JSON_OFFSET] + body + bytes(parser.SAVE_SIZE - parser.JSON_OFFSET - len(body))))
            self.assertFalse(any(f.group == 'Battle set names' for f in parser.fields_for(document)))
            self.assertEqual(parser.serialize(document, {}), document.raw)


class WolongExpansionSafetyTests(unittest.TestCase):
    def test_wrong_selection_types_fail_with_save_error(self):
        document = parser.decode(procedural_payload())
        for selection in (None, 'sen', b'sen', 1, [None], [True], [['sen']]):
            with self.subTest(selection=selection), self.assertRaises(SaveError):
                parser.limit_values(document, {}, selection)
        for key in (None, True, ['sen'], ('sen',)):
            with self.subTest(key=key), self.assertRaises(SaveError):
                parser.stage(document, {}, key, 1)
        with self.assertRaises(SaveError):
            parser.serialize(replace(document, source='copy.bin'), {})

    def test_source_change_during_serialization_prevents_save_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'copy.bin'
            source.write_bytes(procedural_payload())
            document = parser.read_save(source)
            destination = Path(directory) / 'edited.bin'
            serialize = parser.serialize
            def racing_serialize(document, changes):
                encoded = serialize(document, changes)
                source.write_bytes(document.raw[:-1])
                return encoded
            with patch.object(parser, 'serialize', side_effect=racing_serialize), \
                    patch.object(parser, 'backup') as backup:
                with self.assertRaises(SaveError):
                    parser.save_as(document, {'sen': 1}, destination)
                backup.assert_not_called()
            self.assertFalse(destination.exists())

    def test_source_change_during_backup_prevents_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'copy.bin'
            source.write_bytes(procedural_payload())
            document = parser.read_save(source)
            destination = Path(directory) / 'edited.bin'
            backup = parser.backup
            def racing_backup(document):
                snapshot = backup(document)
                source.write_bytes(document.raw[:-1])
                return snapshot
            with patch.object(parser, 'backup', side_effect=racing_backup):
                with self.assertRaises(SaveError):
                    parser.save_as(document, {'sen': 1}, destination)
            self.assertFalse(destination.exists())
            snapshots = list((source.parent / 'WarriorsEditorBackups').glob('*.bin'))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].read_bytes(), document.raw)

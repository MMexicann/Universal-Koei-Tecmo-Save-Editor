"""DW3 opt-in bounds and GUI staging; generated records contain no player data."""
import os
import struct
import tkinter as tk
import unittest
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from koei_editor.games.dw3 import gui, progression_editor as progression, save_writer as writer
from koei_editor.games.dw3.models import Change, SaveError, fields
from koei_editor.games.dw3.save_parser import ARRAY_LAYOUTS, parse_bytes, read_save
from koei_editor.shared.experimental_limits import experimental_enabled, experimental_limits
from tests.test_elixirs_v11 import synthetic_reset_save, string, tag, typename
from tests.test_elixirs_v08 import replace_top_tag


def numeric_document(*, merit=1, elixirs=3):
    document = synthetic_reset_save(progression._new_elixir_tag(elixirs))
    with experimental_limits():
        raw, _ = writer.serialize(document, [Change('officer', 0, 'SPoint', merit)])
    return parse_bytes(raw)


def item_document(*, owned=True):
    document = numeric_document()
    scope = typename('/Script/Refine')
    equipment = typename('ArrayProperty', typename('StructProperty', typename('EquipItemSaveData', scope)))
    def enum(name, family, value):
        return tag(name, typename('EnumProperty', typename(family, scope), typename('ByteProperty')), string(value))
    record = enum('EquipItemID', 'EEquipItemID', 'EEquipItemID::' + writer.ITEMS[0]['enum'] if owned else 'EEquipItemID::NUM')
    record += enum('GuardEquipItemID', 'EGuardEquipItemID', 'EGuardEquipItemID::NUM')
    record += tag('Value', typename('IntProperty'), struct.pack('<i', int(owned))) + string('None')
    replacement = tag('EquipItemDataArray', equipment, struct.pack('<i', 1) + record)
    return replace_top_tag(document, document.properties['EquipItemDataArray'], replacement)


def equipment_document():
    """Mapped synthetic inventories let real navigation consume pending edits."""
    document = numeric_document()
    scope = typename('/Script/Refine')
    def integer(name, value):
        return tag(name, typename('IntProperty'), struct.pack('<i', value))
    def enum(name, family, value):
        return tag(name, typename('EnumProperty', typename(family, scope), typename('ByteProperty')), string(value))
    def integers(name, values):
        return tag(name, typename('ArrayProperty', typename('IntProperty')),
                   struct.pack('<i', len(values)) + struct.pack('<' + 'i' * len(values), *values))
    def array(name, rows):
        kind = typename('ArrayProperty', typename('StructProperty', typename(ARRAY_LAYOUTS[name], scope)))
        return tag(name, kind, struct.pack('<i', len(rows)) + b''.join(rows))
    def equipment(*, guard_id=None, officer_id=None, value=0):
        ordinary = 'EEquipItemID::' + writer.ITEMS[officer_id]['enum'] if officer_id is not None else 'EEquipItemID::NUM'
        guard = gui.GUARD_ITEMS[guard_id]['enum'] if guard_id is not None else 'EGuardEquipItemID::NUM'
        return (enum('EquipItemID', 'EEquipItemID', ordinary) + enum('GuardEquipItemID', 'EGuardEquipItemID', guard) +
                integer('Value', value) + string('None'))
    def weapon(index, weapon_id, bonuses):
        identity = gui.GUARD_WEAPONS[weapon_id]['enum'] if weapon_id in gui.GUARD_WEAPONS else gui.WEAPONS[weapon_id]['enum']
        kind = typename('ArrayProperty', typename('StructProperty', typename('EquipItemSaveData', scope)))
        return (integer('DataID', index) + enum('ID', 'EWeaponID', identity) + enum('WeaponID', 'EWeaponID', identity) +
                tag('Attr', typename('Int64Property'), bytes(8)) + tag('GetTime', typename('DoubleProperty'), bytes(8)) +
                tag('Skill', kind, struct.pack('<i', 9) + b''.join(bonuses + [equipment()] * (9 - len(bonuses)))) + string('None'))
    rows = [equipment(guard_id=index, value=1 if metadata['kind'] == 'normal' else 0)
            for index, metadata in gui.GUARD_ITEMS.items()]
    replacements = {'GuardEquipItemDataArray': rows}
    team = (integer('SPoint', 1) + integers('BGLevels', [0] * 6) +
            enum('MemberItem', 'EGuardEquipItemID', 'EGuardEquipItemID::NUM') +
            integers('MemberWeapon', [-1] * 10) + string('None'))
    replacements['GuardDataArray'] = [team]
    replacements['GuardWeaponDataArray'] = [weapon(index, weapon_id,
        [equipment(guard_id=skill['id'], value=skill['value']) for skill in gui.GUARD_WEAPONS[weapon_id]['max_bonus_profile']])
        for index, weapon_id in enumerate((175, 178, 181, 184, 187))]
    replacements['WeaponDataArray'] = [weapon(0, 6, [equipment(officer_id=0, value=1)])]
    for name, records in replacements.items():
        document = replace_top_tag(document, document.properties[name], array(name, records))
    return document


class ExperimentalCoreBoundsTests(unittest.TestCase):
    def test_officer_authoring_requires_opt_in_and_exact_native_bounds(self):
        document = numeric_document()
        high = Change('officer', 0, 'SPoint', writer.INT32_MAX)
        with self.assertRaises(SaveError):
            writer.plan_changes(document, [high])
        with experimental_limits():
            patches = writer.plan_changes(document, [high])
            self.assertEqual(len(patches), 1)
            self.assertEqual(struct.unpack('<i', patches[0].after)[0], writer.INT32_MAX)
            for value in (-1, True, 1.0, writer.INT32_MAX + 1):
                with self.subTest(value=value), self.assertRaises(SaveError):
                    writer.plan_changes(document, [Change('officer', 0, 'SPoint', value)])
            with self.assertRaises(SaveError):
                writer.plan_changes(document, [Change('officer', 1, 'SPoint', 100000)])
            with self.assertRaises(SaveError):
                writer.plan_changes(document, [Change('officer', 0, 'WeaponDataID', 100000)])
        self.assertFalse(experimental_enabled())
        with self.assertRaises(SaveError):
            writer.plan_changes(document, [high])

    def test_opened_high_officer_value_is_an_exact_noop_in_default_mode(self):
        document = numeric_document(merit=writer.INT32_MAX)
        self.assertEqual(writer.plan_changes(document, [Change('officer', 0, 'SPoint', writer.INT32_MAX)]), [])
        with self.assertRaises(SaveError):
            writer.plan_changes(document, [Change('officer', 0, 'SPoint', writer.INT32_MAX - 1)])

    def test_elixir_counter_native_bounds_and_high_opened_preservation(self):
        document = numeric_document()
        with self.assertRaises(SaveError):
            writer.plan_changes(document, [Change('progression', 0, 'HuanglongElixirs', 1000)])
        with experimental_limits():
            change = progression.elixir_count_change(writer.INT32_MAX)
            patches = writer.plan_changes(document, [change])
            self.assertEqual(struct.unpack('<i', patches[0].after)[0], writer.INT32_MAX)
            for value in (-1, True, 3.0, writer.INT32_MAX + 1):
                with self.subTest(value=value), self.assertRaises(SaveError):
                    progression.elixir_count_change(value)
        opened = numeric_document(elixirs=writer.INT32_MAX)
        self.assertEqual(progression.elixir_state(opened)['value'], writer.INT32_MAX)
        self.assertEqual(writer.plan_changes(opened, [change]), [])
        self.assertEqual(progression.elixir_state(opened, [progression.elixir_count_change(999)])['value'], 999)

    def test_experimental_native_roundtrip_safe_save_backup_and_story_rewards(self):
        document = numeric_document()
        changes = [Change('officer', 0, 'SPoint', writer.INT32_MAX),
                   Change('progression', 0, 'HuanglongElixirs', writer.INT32_MAX)]
        with experimental_limits():
            raw, audit = writer.serialize(document, changes)
            with tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'edited.sav'
                saved, _ = writer.write_save(document, destination, changes)
                reopened = read_save(saved)
                self.assertEqual(reopened.encrypted, raw)
                backup = writer.backup_save(reopened)
                restored = writer.restore_backup(backup, Path(folder) / 'restored.sav')
                self.assertEqual(restored.read_bytes(), raw)
        reopened = parse_bytes(raw)
        self.assertEqual(fields(reopened.records('PCSaveDataArray')[0])['SPoint']['value'], writer.INT32_MAX)
        self.assertEqual(writer.serialize(reopened)[0], raw)
        self.assertEqual(len(audit['plaintext_changes']), 2)
        offset_ranges = [(row['offset'], row['offset'] + row['length']) for row in audit['plaintext_changes']]
        for offset, (before, after) in enumerate(zip(document.plaintext, reopened.plaintext)):
            if before != after:
                self.assertTrue(any(start <= offset < end for start, end in offset_ranges))
        clears = progression.musou_clear_changes(reopened, 0)
        self.assertEqual(progression.elixir_state(reopened, clears)['value'], writer.INT32_MAX)
        cleared = parse_bytes(writer.serialize(reopened, clears)[0])
        self.assertEqual(cleared.properties['BeansNum']['value'], writer.INT32_MAX)

    def test_owned_normal_item_extension_keeps_identity_and_native_bytes(self):
        document = item_document()
        change = Change('item', 0, 'Value', writer.INT32_MAX)
        with self.assertRaises(SaveError):
            writer.serialize(document, [change])
        with experimental_limits():
            raw, audit = writer.serialize(document, [change])
            for value in (0, -1, True, 1.0, writer.INT32_MAX + 1):
                with self.subTest(value=value), self.assertRaises(SaveError):
                    writer.plan_changes(document, [Change('item', 0, 'Value', value)])
        reopened = parse_bytes(raw)
        self.assertEqual(fields(reopened.records('EquipItemDataArray')[0])['Value']['value'], writer.INT32_MAX)
        self.assertEqual(writer.serialize(reopened, [change])[0], raw)
        self.assertEqual(len(audit['plaintext_changes']), 1)
        self.assertFalse(audit['resized'])
        with experimental_limits(), self.assertRaises(SaveError):
            writer.serialize(item_document(owned=False), [Change('item', 0, 'Owned', True), change])

    def test_undo_cannot_restore_experimental_history_with_mode_disabled(self):
        editor = object.__new__(gui.Editor)
        enabled = [True]
        editor.experimental_mode = SimpleNamespace(get=lambda: enabled[0])
        editor.document = numeric_document()
        editor.changes, editor.history = {}, []
        editor.refresh = Mock()
        high = Change('officer', 0, 'SPoint', 100000)
        self.assertTrue(editor.stage_many([high]))
        self.assertTrue(editor.stage_many([Change('officer', 0, 'SPoint', 1)]))
        self.assertFalse(editor.changes)
        history = list(editor.history)
        enabled[0] = False
        with patch.object(gui.messagebox, 'showinfo') as info:
            editor.undo()
        info.assert_called_once()
        self.assertIn('Enable experimental editing', info.call_args.args[1])
        self.assertFalse(editor.changes)
        self.assertEqual(editor.history, history)
        self.assertFalse(experimental_enabled())
        enabled[0] = True
        editor.undo()
        self.assertEqual(editor.changes[('officer', 0, 'SPoint')], high)
        self.assertEqual(editor.history, history[:-1])
        self.assertFalse(experimental_enabled())


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class ExperimentalCoreGuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = gui.Editor(self.root, persist_preferences=False)
        self.editor.document = numeric_document()
        self.editor.refresh = Mock()
        self.editor.selected_ok = lambda tree: True
        self.errors = []
        self.error_patch = patch.object(gui.messagebox, 'showerror', side_effect=lambda *args: self.errors.append(args))
        self.error_patch.start()

    def tearDown(self):
        self.error_patch.stop()
        self.root.destroy()

    def fill_officer(self, merit):
        for field, variable in self.editor.inputs.items():
            variable.set(str(self.editor.original_value(Change('officer', 0, field, 0))))
        self.editor.inputs['SPoint'].set(str(merit))

    def test_officer_apply_undo_and_session_scope(self):
        self.fill_officer(100000)
        self.editor.apply_officer()
        self.assertTrue(self.errors)
        self.assertFalse(self.editor.changes)
        self.errors.clear()
        self.editor.experimental_mode.set(True)
        self.editor.apply_officer()
        self.assertFalse(self.errors)
        self.assertEqual(self.editor.changes[('officer', 0, 'SPoint')].value, 100000)
        self.assertFalse(experimental_enabled())
        self.editor.undo()
        self.assertFalse(self.editor.changes)

    def test_disable_waits_for_pending_experimental_edits_and_save_can_cancel(self):
        editor = self.editor
        editor.experimental_mode.set(True)
        self.fill_officer(100000)
        editor.apply_officer()
        editor.experimental_mode.set(False)
        with patch.object(gui.messagebox, 'showinfo') as info:
            editor.toggle_experimental()
        self.assertTrue(editor.experimental_mode.get())
        info.assert_called_once()
        with patch.object(gui.messagebox, 'askyesno', return_value=False) as warning, patch.object(writer, 'write_save') as write:
            editor.save_to(Path('/tmp/procedural-dw3-edited.sav'))
        warning.assert_called_once()
        write.assert_not_called()
        self.assertTrue(editor.changes)
        editor.undo()
        editor.experimental_mode.set(False)
        editor.toggle_experimental()
        self.assertFalse(editor.experimental_mode.get())

    def test_max_preserves_high_original_and_unstages_a_pending_reduction(self):
        editor = self.editor
        editor.document = numeric_document(merit=writer.INT32_MAX)
        editor.stage_many([Change('officer', 0, 'SPoint', 1)])
        editor.max_selected()
        self.assertNotIn(('officer', 0, 'SPoint'), editor.changes)
        self.assertFalse(self.errors)
        self.assertEqual(editor.officer_maximum(0, 'SPoint'), writer.INT32_MAX)

    def test_equipment_navigation_and_actions_keep_experimental_pending_values(self):
        editor = self.editor
        editor.document = equipment_document()
        editor.refresh = gui.Editor.refresh.__get__(editor)
        editor.set_loaded(True)
        editor.refresh()
        editor.experimental_mode.set(True)
        editor.guard_items.selection_set('0')
        editor.select_guard_item()
        editor.guard_item_value.set('1000')
        editor.apply_guard_item()
        editor.guard_items.selection_set('1')
        editor.select_guard_item()
        self.assertEqual(editor.current_guard_item, 1)
        editor.max_guard_items()
        self.assertEqual(editor.changes[('guard_item', 0, 'Value')].value, 1000)
        editor.bodyguards.selection_set('0')
        editor.select_bodyguard()
        editor.bodyguard_merit.set('100000')
        editor.apply_bodyguard()
        editor.guard_weapons.selection_set('slot:0')
        editor.select_guard_weapon()
        editor.guard_bonus_values[0].set('1000')
        editor.apply_guard_bonuses()
        editor.refresh_guard_weapons()
        editor.refresh_guard_items()
        editor.refresh_guard_equipment()
        editor.apply_guard_equipment()
        editor.equip_best_guard_weapons()
        editor.guard_weapons.selection_set('slot:0')
        editor.select_guard_weapon()
        editor.max_guard_weapon()
        pending = gui.guard_editor.weapon_state
        with experimental_limits():
            rows = pending(editor.document, list(editor.changes.values()))
        self.assertEqual(rows[0]['skills'][0]['value'], 1000)
        self.assertEqual(editor.changes[('bodyguard', 0, 'SPoint')].value, 100000)
        editor.weapons.selection_set('WeaponDataArray:0')
        editor.select_weapon()
        editor.weapon_bonus_values[0].set('1000')
        editor.apply_weapon_rolls()
        editor.weapon_element.set('Lightning')
        editor.apply_weapon_element()
        self.assertFalse(self.errors)
        self.assertFalse(experimental_enabled())
        with experimental_limits():
            raw, _ = writer.serialize(editor.document, list(editor.changes.values()))
        reopened = parse_bytes(raw)
        self.assertEqual(fields(reopened.records('GuardDataArray')[0])['SPoint']['value'], 100000)
        self.assertEqual(fields(reopened.records('GuardEquipItemDataArray')[0])['Value']['value'], 1000)
        self.assertEqual(fields(fields(reopened.records('GuardWeaponDataArray')[0])['Skill']['value']['records'][0])['Value']['value'], 1000)
        self.assertEqual(fields(fields(reopened.records('WeaponDataArray')[0])['Skill']['value']['records'][0])['Value']['value'], 1000)

"""Planning callbacks enter each editor's existing pending-edit workflow."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from koei_editor.games.dw3.models import Change
from koei_editor.games.dw3 import officer_weapon_editor
from koei_editor.games.dw3.gui import Editor as DW3Editor
from koei_editor.games.dw3.workshop import character_build_plan
from koei_editor.games.dw8xl import workshop as dw8_workshop
from koei_editor.games.dw8xl.dw8xl_editor import Editor as DW8Editor
from koei_editor.shared import verified_editor
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.build_workshop import BuildPlan
from koei_editor.shared.build_workshop_gui import _display_delta
from tests.test_dw8_weapon_order import procedural_equipment
from tests.test_dw8_attribute_identities import procedural_attributes
from tests.test_elixirs_v11 import synthetic_reset_save


def _dw3_document_with_weapon():
    document = synthetic_reset_save()
    weapon = officer_weapon_editor.WEAPONS[0]
    bonus_id = next(iter(officer_weapon_editor.NORMAL_ITEMS))
    value = officer_weapon_editor.allowed_values(
        {'array': 'WeaponDataArray', 'weapon_id': 0}, bonus_id)[0]

    def prop(name, item, kind='IntProperty', size=4):
        return {'name': name, 'value': item, 'type': kind, 'data_size': size}

    skills = []
    for slot in range(9):
        item = bonus_id if slot == 0 else None
        enum = officer_weapon_editor.ITEMS[item]['enum'] if item is not None else 'NUM'
        skills.append([
            prop('EquipItemID', f'EEquipItemID::{enum}', 'EnumProperty', 0),
            prop('GuardEquipItemID', 'EGuardEquipItemID::NUM', 'EnumProperty', 0),
            prop('Value', value if item is not None else 0),
        ])
    document.properties['WeaponDataArray']['value']['records'].append([
        prop('ID', weapon['enum'], 'EnumProperty', 0),
        prop('WeaponID', weapon['enum'], 'EnumProperty', 0),
        prop('Attr', 4, 'Int64Property', 8), prop('DataID', 0),
        prop('GetTime', 0.0, 'DoubleProperty', 8),
        prop('Skill', {'records': skills}, 'ArrayProperty', 4),
    ])
    return document, bonus_id, value


class ScalarWorkshopStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = verified_editor.decode(procedural_equipment(), 'dw8xl')

    def editor(self, document=None):
        editor = object.__new__(DW8Editor)
        editor.document = self.document if document is None else document
        editor.workshop_provider = dw8_workshop
        editor.adapter = BoundScalarAdapter('dw8xl', '.dat', verified_editor)
        editor.experimental_mode = SimpleNamespace(get=lambda: False)
        editor.changes = {}
        editor.history = []
        editor.status = Mock()
        editor.refresh = Mock()
        return editor

    def plan(self):
        projection = dw8_workshop.workshop_projection(self.document)
        field = projection.fields['officer_0_attack']
        return BuildPlan('dw8xl', 'windows_pc', 'officer:0', 'Planned attack',
                         {'officer_0_attack': field.current_value + 1}, {})

    def test_record_delta_compares_only_plain_integer_display_values(self):
        self.assertEqual(_display_delta('1,250', '1,200'), '50')
        self.assertEqual(_display_delta('70', '75'), '-5')
        self.assertEqual(_display_delta('Velocity (ID 7)', 'Velocity (ID 9)'), '—')

    def test_declining_scalar_replacement_keeps_pending_values_untouched(self):
        editor = self.editor()
        editor.changes = {'officer_0_attack': 55, 'officer_0_hp': 99}
        before = dict(editor.changes)
        editor.stage_values = Mock()
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=False) as prompt:
            self.assertFalse(editor._stage_workshop_plan(self.plan()))
        prompt.assert_called_once()
        editor.stage_values.assert_not_called()
        self.assertEqual(editor.changes, before)

    def test_accepting_scalar_replacement_keeps_unrelated_pending_values(self):
        editor = self.editor()
        editor.changes = {'officer_0_attack': 55, 'officer_0_hp': 99}
        planned = self.plan()
        target = planned.values['officer_0_attack']
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=True) as prompt:
            self.assertTrue(editor._stage_workshop_plan(planned))
        prompt.assert_called_once()
        self.assertEqual(editor.changes['officer_0_attack'], target)
        self.assertEqual(editor.changes['officer_0_hp'], 99)
        self.assertEqual(editor.history[-1], {'officer_0_attack': 55, 'officer_0_hp': 99})

    def test_dw8_plan_prompts_before_replacing_a_native_side_effect_pending_field(self):
        document = verified_editor.decode(procedural_attributes(), 'dw8xl')
        editor = self.editor(document)
        first = 'weapon_0_attribute_0_identity'
        peer = 'weapon_0_attribute_1_identity'
        editor.changes = {peer: 41}
        before = dict(editor.changes)
        planned = BuildPlan('dw8xl', 'windows_pc', 'weapon:0', 'Comet swap',
                            {first: 41}, {})

        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=False) as prompt:
            self.assertFalse(editor._stage_workshop_plan(planned))
        prompt.assert_called_once()
        self.assertEqual(editor.changes, before)
        self.assertEqual(editor.history, [])

        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=True) as prompt:
            self.assertTrue(editor._stage_workshop_plan(planned))
        prompt.assert_called_once()
        self.assertEqual(editor.changes, {first: 41, peer: 7})
        self.assertEqual(editor.history[-1], before)


class DW3WorkshopStagingTests(unittest.TestCase):
    def setUp(self):
        self.document, self.bonus_id, self.original_roll = _dw3_document_with_weapon()
        self.editor = object.__new__(DW3Editor)
        self.editor.document = self.document
        from koei_editor.games.dw3 import workshop as dw3_workshop
        self.editor.workshop_provider = dw3_workshop
        self.editor.changes = {}
        self.editor.history = []
        self.editor.refresh = Mock()
        self.editor.experimental_mode = SimpleNamespace(get=lambda: False)

    def pending_weapon_roll(self):
        state = officer_weapon_editor.state(self.document, 0)
        other_id = next(item for item in officer_weapon_editor.NORMAL_ITEMS
                        if item != self.bonus_id)
        other_value = officer_weapon_editor.allowed_values(
            {'array': 'WeaponDataArray', 'weapon_id': 0}, other_id)[0]
        skills = [dict(skill) for skill in state['skills']]
        skills[1] = {'id': other_id, 'value': other_value}
        return Change('weapon_roll', 0, 'Skills', skills), other_id, other_value

    def planned_weapon_roll(self):
        plan = character_build_plan(self.document, 0)
        allowed = officer_weapon_editor.allowed_values(
            {'array': 'WeaponDataArray', 'weapon_id': 0}, self.bonus_id)
        target = next(value for value in allowed if value != self.original_roll)
        plan['equipment']['weapon_bonus_0_value'] = target
        return BuildPlan(**plan), target

    def test_declining_dw3_replacement_leaves_pending_stat_and_weapon_slot_intact(self):
        pending_roll, _other_id, _other_value = self.pending_weapon_roll()
        pending_stat = Change('officer', 0, 'SPoint', 1)
        self.editor.changes = {
            ('officer', 0, 'SPoint'): pending_stat,
            ('weapon_roll', 0, 'Skills'): pending_roll,
        }
        before = dict(self.editor.changes)
        self.editor.stage_many = Mock()
        plan, _target = self.planned_weapon_roll()
        with patch('koei_editor.games.dw3.gui.messagebox.askyesno', return_value=False) as prompt:
            self.assertFalse(self.editor.stage_workshop_plan(plan))
        prompt.assert_called_once()
        self.editor.stage_many.assert_not_called()
        self.assertEqual(self.editor.changes, before)

    def test_accepting_dw3_plan_replaces_target_and_merges_another_pending_weapon_slot(self):
        pending_roll, other_id, other_value = self.pending_weapon_roll()
        pending_stat = Change('officer', 0, 'SPoint', 1)
        unrelated = Change('progression', 0, 'HuanglongElixirs', 3)
        self.editor.changes = {
            ('officer', 0, 'SPoint'): pending_stat,
            ('progression', 0, 'HuanglongElixirs'): unrelated,
            ('weapon_roll', 0, 'Skills'): pending_roll,
        }
        before = dict(self.editor.changes)
        plan, target = self.planned_weapon_roll()
        with patch('koei_editor.games.dw3.gui.messagebox.askyesno', return_value=True) as prompt, \
                patch('koei_editor.games.dw3.gui.save_writer.plan_changes', return_value=[]) as validate:
            self.assertTrue(self.editor.stage_workshop_plan(plan))
        prompt.assert_called_once()
        validate.assert_called_once()
        self.assertNotIn(('officer', 0, 'SPoint'), self.editor.changes)
        self.assertIs(self.editor.changes[('progression', 0, 'HuanglongElixirs')], unrelated)
        staged_skills = self.editor.changes[('weapon_roll', 0, 'Skills')].value
        self.assertEqual(staged_skills[0], {'id': self.bonus_id, 'value': target})
        self.assertEqual(staged_skills[1], {'id': other_id, 'value': other_value})
        self.assertEqual(self.editor.history[-1], before)


if __name__ == '__main__':
    unittest.main()

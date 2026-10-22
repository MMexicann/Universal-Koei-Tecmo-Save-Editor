"""DW3 build snapshots reuse mapped records without changing the save."""
import copy
import unittest

from koei_editor.games.dw3.models import Change, SaveError
from koei_editor.games.dw3.save_parser import parse_bytes
from koei_editor.games.dw3 import officer_weapon_editor
from koei_editor.games.dw3.workshop import (
    character_build_plan,
    character_build_plans,
    changes_from_build_plan,
    workshop_view_data,
)
from koei_editor.shared.build_workshop import BuildPlan
from tests.test_elixirs_v11 import synthetic_reset_save


class DynastyWarriors3WorkshopTests(unittest.TestCase):
    def setUp(self):
        self.document = synthetic_reset_save()

    def test_all_mapped_officers_get_build_plan_compatible_read_only_snapshots(self):
        encrypted = self.document.encrypted
        parsed = copy.deepcopy(self.document.parsed)

        plans = character_build_plans(self.document)

        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(set(plan), {
            'game_id', 'platform_id', 'character_id', 'name', 'values', 'equipment', 'notes',
        })
        portable = BuildPlan(**plan)
        self.assertEqual(portable.character_id, '0')
        self.assertEqual(plan['game_id'], 'dw3')
        self.assertEqual(plan['platform_id'], 'windows_pc')
        self.assertEqual(plan['character_id'], '0')
        self.assertTrue(plan['name'])
        self.assertEqual(plan['values'], {
            'officer:0:SPoint': 0,
            'officer:0:MaxHealth': 0,
            'officer:0:MaxMusou': 0,
            'officer:0:Attack': 0,
            'officer:0:Defence': 0,
        })
        # A stored reference with no mapped copy stays explicit, not "empty".
        self.assertEqual(plan['equipment'], {'weapon_reference': 0})
        self.assertIn('not treated as an empty slot', plan['notes'])
        self.assertIn('no combined combat-stat formula is inferred', plan['notes'])
        self.assertNotIn('sha256', plan)
        self.assertNotIn('path', plan)
        self.assertEqual(self.document.encrypted, encrypted)
        self.assertEqual(self.document.parsed, parsed)

    def test_single_plan_accepts_native_index_or_serialized_character_id(self):
        numeric = character_build_plan(self.document, 0, 'My build')
        serialized = character_build_plan(self.document, '0', 'My build')
        self.assertEqual(numeric, serialized)
        self.assertEqual(numeric['name'], 'My build')

    def test_workshop_view_data_uses_dashboard_stats_and_stage_translator_only_maps_supported_fields(self):
        plans, metadata, stats = workshop_view_data(self.document)
        plan = plans[0]
        self.assertIn('officer:0:Attack', metadata)
        self.assertTrue(any(row['character_id'] == '0' and row['label'] == 'Attack'
                            for row in stats))
        self.assertEqual(metadata['officer:0:Attack']['current_value'], 0)

        before = copy.deepcopy(self.document.parsed)
        proposed = dict(plan, values={**plan['values'], 'officer:0:Attack': 7})
        changes = changes_from_build_plan(self.document, proposed)
        self.assertIn(Change('officer', 0, 'Attack', 7), changes)
        self.assertEqual(self.document.parsed, before)

        bad_equipment = dict(plan, equipment={**plan['equipment'], 'weapon_reference': 42})
        with self.assertRaises(SaveError):
            changes_from_build_plan(self.document, bad_equipment)

    def test_mapped_weapon_configuration_stays_separate_from_officer_stats(self):
        document = self.document
        weapon_id = 0
        weapon = officer_weapon_editor.WEAPONS[weapon_id]
        bonus_id = next(iter(officer_weapon_editor.NORMAL_ITEMS))
        bonus_value = officer_weapon_editor.allowed_values(
            {'array': 'WeaponDataArray', 'weapon_id': weapon_id}, bonus_id,
        )[0]

        def property_row(name, value, type_name='IntProperty', data_size=4):
            return {'name': name, 'value': value, 'type': type_name, 'data_size': data_size}

        skills = []
        for slot in range(9):
            item = bonus_id if slot == 0 else None
            enum = (officer_weapon_editor.ITEMS[item]['enum'] if item is not None else 'NUM')
            skills.append([
                property_row('EquipItemID', f'EEquipItemID::{enum}', 'EnumProperty', 0),
                property_row('GuardEquipItemID', 'EGuardEquipItemID::NUM', 'EnumProperty', 0),
                property_row('Value', bonus_value if item is not None else 0),
            ])
        document.properties['WeaponDataArray']['value']['records'].append([
            property_row('ID', weapon['enum'], 'EnumProperty', 0),
            property_row('WeaponID', weapon['enum'], 'EnumProperty', 0),
            property_row('Attr', 4, 'Int64Property', 8),
            property_row('DataID', 0),
            property_row('GetTime', 0.0, 'DoubleProperty', 8),
            property_row('Skill', {'records': skills}, 'ArrayProperty', 4),
        ])
        before = copy.deepcopy(document.parsed)

        plan = character_build_plan(document, 0)

        self.assertEqual(plan['values']['officer:0:Attack'], 0)
        self.assertEqual(plan['equipment']['weapon_reference'], 0)
        self.assertEqual(plan['equipment']['weapon_id'], weapon_id)
        self.assertEqual(plan['equipment']['weapon_name'], 'Iron Sword')
        self.assertEqual(plan['equipment']['weapon_rank'], 1)
        self.assertEqual(plan['equipment']['weapon_base_attack'], 16)
        self.assertEqual(plan['equipment']['weapon_element_mask'], 4)
        self.assertEqual(plan['equipment']['weapon_bonus_0_id'], bonus_id)
        self.assertEqual(plan['equipment']['weapon_bonus_0_value'], bonus_value)
        self.assertIn('separate from permanent officer Attack', plan['notes'])
        self.assertEqual(document.parsed, before)

        state = officer_weapon_editor.state(document, 0)
        alternate = next((mask for mask in officer_weapon_editor.allowed_elements(state).values()
                          if mask != state['elements']), None)
        self.assertIsNotNone(alternate)
        configured = dict(plan, equipment={**plan['equipment'], 'weapon_element_mask': alternate})
        changes = changes_from_build_plan(document, configured)
        self.assertIn(Change('weapon_element', 0, 'Elements', alternate), changes)

    def test_missing_or_invalid_officer_records_are_not_inferred_as_zero(self):
        for character_id in (-1, True, 'not-an-index', '١'):
            with self.subTest(character_id=character_id):
                with self.assertRaises(SaveError):
                    character_build_plan(self.document, character_id)
        with self.assertRaises(SaveError):
            character_build_plan(self.document, 1)
        with self.assertRaises(SaveError):
            character_build_plan(self.document, 0, '   ')

    def test_adapter_requires_a_parsed_dw3_document(self):
        with self.assertRaises(SaveError):
            character_build_plans(b'not a parsed save')
        with self.assertRaises(SaveError):
            character_build_plan(parse_bytes(self.document.encrypted), '42')


if __name__ == '__main__':
    unittest.main()

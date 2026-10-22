"""Workshop providers reuse verified opened fields and dashboard projections."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl import workshop as dw8_workshop
from koei_editor.games.wo3u import workshop as wo3_workshop
from koei_editor.games.wo3u import wo3u_equipment as wo3_equipment
from koei_editor.games.wo3u import wo3u_parser as wo3
from koei_editor.shared import verified_editor as dw8
from koei_editor.shared.build_workshop_context import (
    is_equipment_field, scalar_projection_context,
)
from tests.test_dw8_weapon_order import procedural_equipment
from tests.test_wo3u_depth import depth_raw


class DW8WorkshopProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = dw8.decode(procedural_equipment(), 'dw8xl')

    def test_projection_uses_dashboard_and_parser_field_choices(self):
        projection = dw8_workshop.workshop_projection(self.document)
        self.assertEqual((projection.game_id, projection.platform_id), ('dw8xl', 'windows_pc'))
        self.assertEqual(projection.dashboard.title, 'Dynasty Warriors 8 XL · Progression')
        attack = projection.fields['officer_0_attack']
        self.assertEqual((attack.category, attack.character_id), ('Officers', 'officer:0'))
        self.assertEqual(attack.current_value, dw8.field_map(self.document)['officer_0_attack'].value(
            self.document.payload))
        self.assertIn('docs/', attack.evidence)

        order = projection.fields['officer_0_first_weapon']
        self.assertEqual(order.category, 'Weapon order')
        self.assertEqual(order.character_id, 'officer:0')
        self.assertEqual(order.choices, dw8.field_options(self.document, order.field_id))
        self.assertEqual(tuple(value for value, _ in order.choices), (1, 2))

        compatibility = projection.fields['officer_0_compatibility_0']
        self.assertEqual(tuple(value for value, _ in compatibility.choices), (25, 50, 75, 100))
        self.assertIn('25 stored units per star', compatibility.evidence)
        stars = next(metric for section in projection.dashboard.sections
                     for card in section.cards for metric in card.metrics
                     if metric.id == 'officer_0_compatibility_1')
        self.assertEqual((stars.value, stars.current, stars.total), ('2 / 4 stars', 2, 4))

    def test_workshop_context_groups_mapped_fields_and_reuses_dashboard_calculations(self):
        projection = dw8_workshop.workshop_projection(self.document)
        plans, metadata, stats = scalar_projection_context(projection)
        officer = next(plan for plan in plans if plan.character_id == 'officer:0')
        self.assertIn('officer_0_attack', officer.values)
        self.assertIn('officer_0_first_weapon', officer.equipment)
        self.assertEqual(metadata['officer_0_first_weapon']['choices'],
                         projection.fields['officer_0_first_weapon'].choices)
        self.assertTrue(any(row['character_id'] == 'officer:0'
                            and row['label'] == 'Dash aptitude'
                            and row['value'] == '2 / 4 stars'
                            and '25 stored units per star' in row['evidence']
                            for row in stats))
        self.assertTrue(is_equipment_field('Weapon order', 'officer_0_first_weapon'))
        self.assertTrue(is_equipment_field('Weapon affinity', 'weapon_0_affinity'))
        weapon = next(plan for plan in plans if plan.character_id == 'weapon:0')
        self.assertIn('weapon_0_attribute_0_rank', weapon.values)
        self.assertIn('weapon_0_affinity', weapon.equipment)

    def test_weapon_comparison_is_side_by_side_stored_data_only(self):
        self.assertEqual(dw8_workshop.weapon_record_options(self.document), (
            (1, 'Weapon slot 0001'), (2, 'Weapon slot 0002'), (5, 'Weapon slot 0005'),
        ))
        left, right = dw8_workshop.compare_weapon_records(self.document, 1, 2)
        self.assertEqual((left.id, right.id), ('weapon_1', 'weapon_2'))
        left_metrics = {metric.id: metric for metric in left.metrics}
        right_metrics = {metric.id: metric for metric in right.metrics}
        self.assertEqual(left_metrics['attack'].label, 'Stored attack')
        self.assertEqual(left_metrics['attack'].value, '70')
        self.assertEqual(right_metrics['attack'].value, '70')
        self.assertFalse(any('damage' in metric.label.lower() for metric in left.metrics + right.metrics))
        for slots in ((0, 1), (1, 1831), (True, 2)):
            with self.subTest(slots=slots), self.assertRaises(SaveError):
                dw8_workshop.compare_weapon_records(self.document, *slots)

    def test_projection_is_read_only_immutable_and_rejects_tampered_document(self):
        original = self.document.raw
        with patch.object(dw8, 'stage', side_effect=AssertionError('workshop attempted staging')), \
                patch.object(dw8, 'serialize', side_effect=AssertionError('workshop attempted serialization')):
            projection = dw8_workshop.workshop_projection(self.document)
        self.assertEqual(self.document.raw, original)
        with self.assertRaises(TypeError):
            projection.fields['extra'] = projection.fields['officer_0_attack']
        payload = bytearray(self.document.payload)
        payload[0x105] ^= 1
        with self.assertRaises(SaveError):
            dw8_workshop.workshop_projection(replace(self.document, payload=bytes(payload)))


class WO3WorkshopProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = bytearray(depth_raw())
        for offset in wo3_equipment.MOUNT_LOADOUT_OFFSETS:
            raw[offset] = wo3_equipment.EMPTY_ITEM
        cls.document = wo3.decode(raw)

    def test_projection_reuses_officer_weapon_and_owned_equipment_data(self):
        projection = wo3_workshop.workshop_projection(self.document)
        self.assertEqual((projection.game_id, projection.platform_id), ('wo3u', 'windows_pc'))
        self.assertIn('Warriors Orochi 3 Ultimate', projection.dashboard.title)

        stats = projection.fields['officer_0_health']
        self.assertEqual((stats.category, stats.character_id), ('Officers', 'officer:0'))
        self.assertEqual(stats.current_value,
                         wo3.field_map(self.document)['officer_0_health'].value(self.document.payload))

        item = projection.fields['officer_0_equipped_item_0']
        self.assertEqual(item.choices, wo3.field_options(self.document, item.field_id))
        self.assertEqual(tuple(value for value, _ in item.choices), (255, 0, 1, 2))
        self.assertEqual(item.character_id, 'officer:0')

        mount = projection.fields['mount_loadout_0']
        self.assertEqual(mount.choices, wo3.field_options(self.document, mount.field_id))
        self.assertEqual(tuple(value for value, _ in mount.choices), (255, 0))

        weapon = projection.fields['weapon_0_rank_0']
        self.assertEqual((weapon.category, weapon.character_id), ('Weapons', 'weapon:0'))
        self.assertIn('docs/OROCHI_DYNASTY_DEPTH.md', weapon.evidence)

        plans, metadata, _stats = scalar_projection_context(projection)
        officer = next(plan for plan in plans if plan.character_id == 'officer:0')
        self.assertIn('officer_0_health', officer.values)
        self.assertIn('officer_0_equipped_item_0', officer.equipment)
        self.assertEqual(metadata['officer_0_equipped_item_0']['choices'], item.choices)

    def test_unusual_compatibility_stays_raw_and_dashboard_is_reused(self):
        raw = bytearray(self.document.raw)
        raw[wo3.WEAPON_BASE + 20:wo3.WEAPON_BASE + 24] = (1234).to_bytes(4, 'little')
        document = wo3.decode(raw)
        projection = wo3_workshop.workshop_projection(document)
        field = projection.fields['weapon_0_compatibility_reset']
        self.assertEqual(field.current_value, 1234)
        self.assertEqual(field.choices, ())
        self.assertIn('stored raw units', field.evidence)
        card = next(card for section in projection.dashboard.sections
                    for card in section.cards if card.id == 'weapon_1')
        compatibility = next(metric for metric in card.metrics if metric.id == 'compatibility')
        self.assertEqual(compatibility.value, '1,234')
        self.assertIsNone(compatibility.fraction)

    def test_projection_never_stages_or_serializes_and_rejects_tampering(self):
        original = self.document.raw
        with patch.object(wo3, 'stage', side_effect=AssertionError('workshop attempted staging')), \
                patch.object(wo3, 'serialize', side_effect=AssertionError('workshop attempted serialization')):
            projection = wo3_workshop.workshop_projection(self.document)
        self.assertEqual(self.document.raw, original)
        with self.assertRaises(TypeError):
            projection.fields['extra'] = projection.fields['officer_0_health']
        raw = bytearray(self.document.raw)
        raw[wo3.OFFICER_BASE] ^= 1
        with self.assertRaises(SaveError):
            wo3_workshop.workshop_projection(replace(self.document, raw=bytes(raw)))


if __name__ == '__main__':
    unittest.main()

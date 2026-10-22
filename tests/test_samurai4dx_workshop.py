"""Read-only SW4 DX character and weapon workshop mappings."""
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.sw4dx import samurai4dx_parser as backend
from koei_editor.games.sw4dx import workshop
from koei_editor.shared.build_workshop_context import scalar_projection_context
from tests.test_samurai4dx_format import procedural_raw


class Samurai4DXWorkshopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = backend.decode(procedural_raw())

    def test_snapshot_reuses_mapped_opened_values_without_derived_formula(self):
        before = self.document.raw
        with (patch.object(backend, 'stage', side_effect=AssertionError('staging is not read-only')),
              patch.object(backend, 'serialize', side_effect=AssertionError('serialization is not read-only'))):
            snapshot = workshop.workshop_snapshot(self.document)

        self.assertEqual(self.document.raw, before)
        self.assertIn('No derived or effective battle-stat formula is mapped', snapshot.note)
        sections = {section.title: section for section in snapshot.sections}
        self.assertIn('Officers', sections)
        self.assertIn('Equipment', sections)
        self.assertIn('Weapons', sections)
        self.assertEqual(len(sections['Officers'].cards), backend.OFFICER_COUNT)
        officer = next(card for card in sections['Officers'].cards
                       if card.subtitle == 'Record 1')
        stats = {metric.field_id for metric in officer.metrics}
        self.assertTrue({f'officer_0_{name}' for name in
                         ('health', 'attack', 'defense', 'riding', 'speed')} <= stats)
        self.assertTrue(all(metric.fraction is None
                            for section in snapshot.sections
                            for card in section.cards for metric in card.metrics))
        with self.assertRaises(FrozenInstanceError):
            snapshot.note = 'tampered'

    def test_weapon_choices_reuse_only_parser_qualified_occupied_slots(self):
        self.assertEqual(workshop.equipment_choices(self.document,
                                                     'officer_0_equipped_weapon'),
                         backend.field_options(self.document,
                                               'officer_0_equipped_weapon'))
        choices = workshop.equipment_choices(self.document, 'officer_0_equipped_weapon')
        self.assertEqual([value for value, _ in choices], [0, 1])
        self.assertTrue(all('Blaze' in label for _, label in choices))
        self.assertEqual(workshop.equipment_choices(self.document,
                                                     'weapon_0_0_skill_0_active'), ())
        self.assertEqual(workshop.field_choices(self.document,
                                                'weapon_0_0_skill_0_active'),
                         ((0, 'Locked'), (1, 'Active')))

    def test_unmapped_or_tampered_snapshots_are_rejected(self):
        with self.assertRaises(SaveError):
            workshop.equipment_choices(self.document, 'officer_99_equipped_weapon')
        corrupted = replace(self.document, payload=self.document.payload[:-1] +
                            bytes((self.document.payload[-1] ^ 1,)))
        with self.assertRaises(SaveError):
            workshop.workshop_snapshot(corrupted)

    def test_projection_builds_profiles_from_existing_parser_fields(self):
        projection = workshop.workshop_projection(self.document)
        plans, metadata, stats = scalar_projection_context(projection)
        officer = next(plan for plan in plans if plan.character_id == 'officer:0')
        self.assertIn('officer_0_health', officer.values)
        self.assertIn('officer_0_equipped_weapon', officer.equipment)
        self.assertEqual(metadata['officer_0_equipped_weapon']['choices'],
                         backend.field_options(self.document, 'officer_0_equipped_weapon'))
        self.assertTrue(any(row['character_id'] == 'officer:0'
                            and row['label'] == 'Base attack' for row in stats))


if __name__ == '__main__':
    unittest.main()

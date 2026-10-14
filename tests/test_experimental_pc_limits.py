"""Experimental PC fields retain native encoding and protected dependencies."""
from importlib import import_module
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_limits


class ExperimentalPcLimitsTests(unittest.TestCase):
    def test_dynamic_numeric_fields_survive_native_serialization(self):
        cases = (
            ('dw5special.dw5special_parser', 'dw5special_format', 'procedural_raw', 'item_0_rank'),
            ('dw9emp.dw9emp_parser', 'dw9emp_format', 'procedural_raw', 'item_0_quantity'),
            ('wo4.parser', 'wo4_pc', 'generated_raw', 'skill_orbs'),
            ('wo4_ultimate.parser', 'wo4_ultimate', 'fixture', 'skill_orbs'),
            ('origins.origins_parser', 'origins_parser', 'fixture', 'gold'),
            ('pw4.pw4_parser', 'pw4_format', 'procedural_raw', 'beli'),
        )
        for module, fixture_module, fixture_name, key in cases:
            with self.subTest(module=module, field=key):
                backend = import_module('koei_editor.games.' + module)
                fixture = import_module('tests.test_' + fixture_module)
                document = backend.decode(getattr(fixture, fixture_name)())
                field = backend.field_map(document)[key]
                target = field.maximum + 1
                with self.assertRaises(SaveError):
                    backend.stage(document, {}, key, target)
                with experimental_limits():
                    changes = backend.stage(document, {}, key, target)
                    reopened = backend.decode(backend.serialize(document, changes))
                    self.assertEqual(backend.field_map(reopened)[key].value(reopened.payload), target)
                    self.assertEqual(document.raw, backend.serialize(document, {}))
                    with self.assertRaises(SaveError):
                        backend.stage(document, {}, key, field.experimental_maximum + 1)

    def test_dw4_item_sentinel_is_not_a_level(self):
        from koei_editor.games.dw4hyper import dw4hyper_parser as backend
        field = backend.FIELD_MAP['item_0']
        with experimental_limits():
            self.assertEqual(field.encoded(255), b'\xfe')
            self.assertEqual(field.encoded(0), b'\xff')
            with self.assertRaises(SaveError):
                field.encoded(256)
            with self.assertRaises(SaveError):
                backend.FIELD_MAP['difficulty'].validate(3)
            with self.assertRaises(SaveError):
                backend.FIELD_MAP['item_19'].validate(2)

    def test_bias_and_packed_rank_have_different_storage_ceilings(self):
        from koei_editor.games.wo1_pc.wo1_parser import Field
        from koei_editor.games.sw2.sw2_parser import SkillField
        biased = Field('rank', 'Rank', 0, 1, 10, minimum=1, display_bias=1)
        packed = SkillField('skill', 'Skill', 0, 1, 3, minimum=1)
        with experimental_limits():
            self.assertEqual(biased.experimental_maximum, 256)
            self.assertEqual(biased.encoded(256), b'\xff')
            packed.validate(127)
            with self.assertRaises(SaveError):
                packed.validate(128)
            with self.assertRaises(SaveError):
                biased.encoded(257)

    def test_enum_reference_and_level_dependencies_stay_bounded(self):
        from koei_editor.shared.verified_editor import CompatibilityField
        from koei_editor.games.orochiz.orochiz_parser import Field
        from koei_editor.games.dw8xl.equipment import WeaponOrderField
        fields = (
            CompatibilityField('compatibility', 'Compatibility', 0, 1, 100, minimum=25),
            Field('officer_0_exp_within_level', 'Current level EXP', 0, 4, 999, minimum=100),
            Field('officer_0_weapon_0_attribute_slots', 'Attribute slots', 0, 1, 8),
            WeaponOrderField('weapon', 'Weapon', 0, 2, 1830, opened_slots=(1, 2)),
        )
        with experimental_limits():
            for field in fields:
                with self.subTest(field=field.id):
                    self.assertIsNone(field.experimental_maximum)
                    with self.assertRaises(SaveError):
                        field.validate(field.maximum + 1)


if __name__ == '__main__':
    unittest.main()

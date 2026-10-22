"""Portable build plans remain declarative and separate from save writes."""
import json
from pathlib import Path
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import build_workshop as workshop


def plan(name='Liu Bei · balanced', *, values=None, equipment=None,
         game_id='dw8xl', platform_id='pc', character_id='officer_0'):
    return workshop.BuildPlan(
        game_id, platform_id, character_id, name,
        values if values is not None else {'strength': 350, 'vitality': 220},
        equipment if equipment is not None else {'weapon_primary': 'green-dragon'},
        'Compare the mapped values after reviewing the intended game revision.',
    )


class BuildWorkshopModelTests(unittest.TestCase):
    def test_round_trip_is_deterministic_and_contains_no_source_identity(self):
        first = plan(values={'vitality': 220, 'strength': 350})
        second = plan(values={'strength': 350, 'vitality': 220})
        raw = workshop.encode_plan(first)

        self.assertEqual(raw, workshop.encode_plan(second))
        reopened = workshop.decode_plan(raw)
        self.assertEqual(first, reopened)
        document = json.loads(raw)
        self.assertEqual(document['schema'], workshop.SCHEMA)
        self.assertEqual(document['version'], workshop.SCHEMA_VERSION)
        self.assertFalse(any('source' in key or 'sha256' in key or 'path' in key
                             for key in document))
        with self.assertRaises(TypeError):
            reopened.values['strength'] = 1

    def test_save_and_load_create_only_the_dedicated_json_preset(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = workshop.save_plan(plan(), Path(folder) / 'my-build.json')
            self.assertEqual(destination.name, 'my-build.build.json')
            self.assertEqual(workshop.load_plan(destination), plan())
            with self.assertRaises(FileExistsError):
                workshop.save_plan(plan(), destination)
            with self.assertRaises(SaveError):
                workshop.load_plan(Path(folder) / 'game-save.dat')

    def test_plan_requires_stable_identity_and_at_least_one_assignment(self):
        with self.assertRaises(SaveError):
            workshop.BuildPlan('', 'pc', 'officer_0', 'Build', {'strength': 1})
        with self.assertRaises(SaveError):
            workshop.BuildPlan('dw8xl', 'PC', 'officer_0', 'Build', {'strength': 1})
        with self.assertRaises(SaveError):
            workshop.BuildPlan('dw8xl', 'pc', 'officer_0', 'Build')
        with self.assertRaises(SaveError):
            workshop.BuildPlan('dw8xl', 'pc', 'officer_0', 'Build', {'bad\nfield': 1})

    def test_scalar_values_are_bounded_and_finite(self):
        for value in (float('nan'), float('inf'), -(1 << 64), 1 << 64, [], {}):
            with self.subTest(value=value):
                with self.assertRaises(SaveError):
                    plan(values={'stat': value}, equipment={})
        text = 'é' * (workshop.MAX_TEXT_BYTES // 2 + 1)
        with self.assertRaises(SaveError):
            plan(values={'label': text}, equipment={})
        self.assertEqual(plan(values={'flag': True, 'empty': None}, equipment={}).values,
                         {'flag': True, 'empty': None})

    def test_decoder_rejects_duplicate_unknown_invalid_and_oversized_documents(self):
        valid = json.loads(workshop.encode_plan(plan()))
        duplicated = (b'{"schema":"koei-character-weapon-build","schema":"other"}')
        with self.assertRaises(SaveError):
            workshop.decode_plan(duplicated)
        for changed in (
            {**valid, 'unexpected': 1},
            {**valid, 'version': True},
            {**valid, 'version': 999},
            {**valid, 'values': {'stat': float('nan')}},
        ):
            with self.subTest(changed=changed):
                encoded = json.dumps(changed, allow_nan=True).encode('utf-8')
                with self.assertRaises(SaveError):
                    workshop.decode_plan(encoded)
        for invalid in (b'', b'\xff', b'null', b'[]', b' ' * (workshop.MAX_BYTES + 1)):
            with self.subTest(length=len(invalid)):
                with self.assertRaises(SaveError):
                    workshop.decode_plan(invalid)

    def test_comparison_reports_generic_left_minus_right_differences_only(self):
        left = plan(values={'strength': 300, 'speed': 1.5, 'flag': True, 'label': 'x'})
        right = plan(name='Alternate', values={'strength': 250, 'speed': 2.0,
                                               'flag': False, 'label': 'y'})

        differences = workshop.compare_build_plans(left, right)

        self.assertEqual(tuple((row.field_id, row.left_value, row.right_value, row.delta)
                               for row in differences),
                         (('speed', 1.5, 2.0, -0.5), ('strength', 300, 250, 50)))
        with self.assertRaises(SaveError):
            workshop.compare_build_plans(left, plan(values={'strength': 1}, character_id='officer_1'))
        with self.assertRaises(SaveError):
            workshop.compare_build_plans(left, object())


if __name__ == '__main__':
    unittest.main()

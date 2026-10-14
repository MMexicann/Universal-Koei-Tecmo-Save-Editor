"""Experimental numeric bounds on generated existing native records."""
import importlib
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_limits


class ExperimentalNintendoStrategyTests(unittest.TestCase):
    profiles = (
        ('hyrule_warriors', 'hyrule_formats', 'procedural_hw'),
        ('hyrule_legends', 'hyrule_legends', 'procedural_legends'),
        ('hyrule_definitive', 'hyrule_definitive', 'procedural_raw'),
        ('age_of_calamity', 'hyrule_formats', 'procedural_aoc'),
        ('fire_emblem_warriors', 'fire_emblem_warriors', 'procedural_fe'),
        ('three_hopes', 'three_hopes', 'procedural_hopes'),
        ('three_houses', 'three_houses', 'procedural_slot'),
        ('monster_rancher_ds', 'monster_rancher_ds', 'fixture'),
        ('nobunaga_ambition_nes', 'nobunaga_ambition_nes', 'procedural_raw'),
        ('nobu6_pk_pc', 'nobu6_pk_pc', 'generated_raw'),
        ('bandit_kings_mac', 'bandit_kings_mac', 'procedural_raw'),
        ('rotk2_dos', 'rotk2_dos', 'generated_raw'),
        ('rotk3_dos', 'rotk3_dos', 'generated_raw'),
        ('reko3_dos', 'reko3_dos', 'procedural_raw'),
        ('uncharted_waters2_dos', 'uncharted_waters2_dos', 'procedural_raw'),
        ('dqb2_pc', 'dqb2_pc', 'fixture'),
        ('dqb2_switch', 'dqb2_switch', 'fixture'),
        ('gemfire_nes', 'gemfire_battery', 'procedural_raw'),
        ('gemfire_snes', 'gemfire_battery', 'procedural_raw'),
    )

    def test_storage_ceiling_roundtrip_and_default_rejection(self):
        for game, fixture_module, factory in self.profiles:
            with self.subTest(game=game):
                backend = importlib.import_module('koei_editor.games.' + game + '.parser')
                fixture = getattr(importlib.import_module('tests.test_' + fixture_module), factory)
                raw = fixture('snes') if game == 'gemfire_snes' else fixture()
                document = backend.decode(raw)
                fields = backend.fields_for(document)
                field = next(f for f in fields if f.experimental_maximum is not None
                             and f.experimental_maximum > f.maximum
                             and (game != 'age_of_calamity' or f.id != 'rupees'))
                ceiling = field.experimental_maximum
                self.assertEqual(ceiling, (1 << (field.size * 8)) - 1)
                with self.assertRaises(SaveError):
                    backend.stage(document, {}, field.id, ceiling)
                with experimental_limits():
                    changes = backend.stage(document, {}, field.id, ceiling)
                    output = backend.serialize(document, changes)
                    reopened = backend.decode(output)
                    self.assertEqual(backend.field_map(reopened)[field.id].value(reopened.payload), ceiling)
                    for invalid in (ceiling + 1, -1, True, 1.0, '1'):
                        with self.assertRaises(SaveError):
                            backend.stage(document, {}, field.id, invalid)
                    self.assertEqual(backend.stage(document, changes, field.id,
                                                  field.value(document.payload)), {})
                self.assertEqual(backend.serialize(document, {}), raw)
                self.assertEqual(backend.serialize(reopened, {}), output)
                self.assertEqual(backend.field_map(reopened)[field.id].value(reopened.payload), ceiling)
                with self.assertRaises(SaveError):
                    backend.stage(document, {}, field.id, ceiling)

    def test_existing_equipment_counters_trust_and_quantities_survive_reopening(self):
        from tests.test_hyrule_fire_emblem_depth import trust_slot
        profiles = (
            ('hyrule_legends', 'hyrule_legends', 'procedural_legends',
             ('material_1924', 'map_card_2efa', 'weapon_1_stars', 'weapon_1_skill_1_kos')),
            ('hyrule_definitive', 'hyrule_definitive', 'procedural_raw',
             ('material_1afe', 'weapon_1_stars', 'weapon_1_skill_1_kos')),
            ('fire_emblem_warriors', 'fire_emblem_warriors', 'procedural_fe',
             ('material_44', 'weapon_1_stars', 'weapon_1_seal_1_kos')),
        )
        for game, fixture_module, factory, keys in profiles:
            backend = importlib.import_module('koei_editor.games.' + game + '.parser')
            fixture = getattr(importlib.import_module('tests.test_' + fixture_module), factory)
            document = backend.decode(fixture())
            for key in keys:
                with self.subTest(game=game, field=key):
                    field = backend.field_map(document)[key]
                    with experimental_limits():
                        changes = backend.stage(document, {}, key, field.experimental_maximum)
                        output = backend.serialize(document, changes)
                    reopened = backend.decode(output)
                    self.assertEqual(backend.field_map(reopened)[key].value(reopened.payload),
                                     field.experimental_maximum)
                    self.assertEqual(backend.serialize(reopened, {}), output)
        backend = importlib.import_module('koei_editor.games.hyrule_legends.parser')
        document = backend.decode(trust_slot())
        with experimental_limits():
            output = backend.serialize(document, {'fairy_1_trust': 255})
        reopened = backend.decode(output)
        self.assertEqual(backend.field_map(reopened)['fairy_1_trust'].value(reopened.payload), 255)

    def test_enumerations_packed_values_sentinels_and_history_remain_constrained(self):
        from koei_editor.games.tecmo_super_bowl_nes import parser as tecmo
        from koei_editor.games.pokemon_conquest_ds import parser as pokemon
        from koei_editor.games.three_houses import parser as houses
        from koei_editor.games.age_of_calamity import parser as calamity
        from tests.test_tecmo_super_bowl_nes import generated_raw
        from tests.test_pokemon_conquest_ds import fixture
        from tests.test_three_houses import procedural_slot
        from tests.test_hyrule_formats import procedural_aoc

        with experimental_limits():
            doc = tecmo.decode(generated_raw())
            for field in tecmo.fields_for(doc):
                self.assertIsNone(field.experimental_maximum)
                with self.assertRaises(SaveError):
                    field.validate(field.maximum + 1)
            doc = pokemon.decode(fixture())
            for field in pokemon.fields_for(doc):
                self.assertEqual(field.experimental_maximum, 31)
                with self.assertRaises(SaveError):
                    field.validate(32)
            doc = houses.decode(procedural_slot())
            for field in houses.fields_for(doc):
                if field.choices:
                    self.assertIsNone(field.experimental_maximum)
                    with self.assertRaises(SaveError):
                        field.validate(255)
                if field.forbidden:
                    with self.assertRaises(SaveError):
                        field.validate(100)
            doc = calamity.decode(procedural_aoc())
            gold = calamity.field_map(doc)['rupees']
            with self.assertRaises(SaveError):
                gold.validate(gold.structural_maximum + 1)
            for field in calamity.fields_for(doc):
                if field.group == 'Weapon protection':
                    self.assertIsNone(field.experimental_maximum)
                    with self.assertRaises(SaveError):
                        field.validate(2)

    def test_monster_stat_total_is_only_expanded_in_experimental_scope(self):
        from koei_editor.games.monster_rancher_ds import parser
        from tests.test_monster_rancher_ds import fixture
        doc = parser.decode(fixture())
        changes = {f'monster_0_stat_{index}': 65535 for index in range(6)}
        with experimental_limits():
            output = parser.serialize(doc, changes)
            reopened = parser.decode(output)
            self.assertEqual(parser._monster(reopened.payload, 0, 0)[-1], (65535,) * 6)
        self.assertEqual(parser.serialize(reopened, {}), output)
        with self.assertRaises(SaveError):
            parser.serialize(doc, changes)


if __name__ == '__main__':
    unittest.main()

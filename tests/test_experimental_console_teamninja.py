"""Opt-in numeric boundaries in console and Team Ninja native profiles."""
import importlib
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.experimental_limits import experimental_enabled, experimental_limits


NUMERIC_PROFILES = (
    ('dw7_ps3', 'test_ps3_expansion', 'fixture'),
    ('sw4_ps3', 'test_ps3_expansion', 'fixture'),
    ('dw7e_ps3', 'test_dw7e_ps3', 'fixture'),
    ('wo3u_ps3', 'test_wo3u_ps3', 'fixture'),
    ('dw8_ps3', 'test_dw8_ps3', 'procedural_raw'),
    ('dw8xl_ps3', 'test_dw8xl_ps3', 'fixture'),
    ('dw8xl_vita', 'test_dw8xl_vita', 'procedural_raw'),
    ('pw1_ps3', 'test_pirate_warriors_ps3', 'fixture'),
    ('pw2_ps3', 'test_pirate_warriors_ps3', 'fixture'),
    ('pw3_ps3', 'test_pw3_ps3', 'fixture'),
    ('bladestorm_ps3', 'test_bladestorm_ps3', 'fixture'),
    ('aot1_vita', 'test_aot1_vita', 'fixture'),
    ('berserk_vita', 'test_berserk_vita', 'fixture'),
    ('gundam3_ps3', 'test_gundam3_ps3', 'fixture'),
    ('gundam_reborn_ps3', 'test_gundam_reborn_ps3', 'fixture'),
    ('kens_rage1_ps3', 'test_kens_rage1_ps3', 'procedural_save'),
    ('trinity_ps3', 'test_trinity_ps3', 'fixture'),
    ('ninja_gaiden_ii', 'test_ninja_gaiden_ii', 'procedural_story'),
    ('nioh3', 'test_nioh3_format', 'procedural_raw'),
)


def profile(name, fixture_module, fixture_name):
    backend = importlib.import_module(f'koei_editor.games.{name}.parser')
    factory = getattr(importlib.import_module(f'tests.{fixture_module}'), fixture_name)
    raw = factory(backend) if fixture_module in ('test_ps3_expansion', 'test_pirate_warriors_ps3') else factory()
    return backend, backend.decode(raw)


class ExperimentalConsoleTeamNinjaTests(unittest.TestCase):
    def test_numeric_profile_opt_in_serializes_exact_storage_ceiling(self):
        for entry in NUMERIC_PROFILES:
            with self.subTest(profile=entry[0]):
                backend, document = profile(*entry)
                field = next(field for field in backend.fields_for(document)
                             if field.experimental_maximum is not None
                             and field.maximum < field.experimental_maximum)
                target = field.experimental_maximum
                with self.assertRaises(SaveError):
                    backend.stage(document, {}, field.id, target)
                with experimental_limits():
                    changes = backend.stage(document, {}, field.id, target)
                    output = backend.serialize(document, changes)
                    reopened = backend.decode(output)
                    self.assertEqual(field.value(reopened.payload), target)
                    self.assertEqual(len(output), len(document.raw))
                    self.assertEqual(backend.stage(document, changes, field.id,
                                                   field.value(document.payload)), {})
                    for invalid in (target + 1, field.minimum - 1, True, str(target)):
                        with self.subTest(invalid=invalid), self.assertRaises(SaveError):
                            backend.stage(document, {}, field.id, invalid)
                self.assertFalse(experimental_enabled())
                self.assertEqual(backend.serialize(document, {}), document.raw)
                # Expanded pending values remain invalid after leaving the scope.
                with self.assertRaises(SaveError):
                    backend.serialize(document, changes)

    def test_choice_and_flag_fields_keep_hard_bounds(self):
        for name in ('dw8e_ps3', 'gundam1_ps3', 'kens_rage2_ps3', 'doa5_ps3',
                     'ninja_gaiden_black_xbox'):
            backend = importlib.import_module(f'koei_editor.games.{name}.parser')
            if name == 'ninja_gaiden_black_xbox':
                fields = (backend.SORT,)
            elif name == 'kens_rage2_ps3':
                fields = backend.FIELDS
            elif name == 'gundam1_ps3':
                fields = (backend.Field('skill', 'Skill', 0, 0, 1, 0),
                          backend.EquippedField('equipped', 'Equipped', 0, 1))
            elif name == 'doa5_ps3':
                fields = (backend.Field('costume', 'Costume', 0),)
            else:
                fields = (backend.Field('slider', 'Slider', 0),)
            with experimental_limits():
                for field in fields:
                    with self.subTest(profile=name, field=field.id):
                        self.assertIsNone(field.experimental_maximum)
                        with self.assertRaises(SaveError):
                            field.validate(field.maximum + 1)

    def test_higher_rank_and_material_discovery_is_scoped_and_cache_safe(self):
        for entry, key in ((NUMERIC_PROFILES[5], 'weapon_0_rank_0'),
                           (NUMERIC_PROFILES[6], 'weapon_0_rank_0'),
                           (NUMERIC_PROFILES[12], 'material_0')):
            with self.subTest(profile=entry[0]):
                backend, document = profile(*entry)
                field = backend.field_map(document)[key]
                with experimental_limits():
                    changed = backend.stage(document, {}, key, field.experimental_maximum)
                    reopened = backend.decode(backend.serialize(document, changed))
                    self.assertIn(key, backend.field_map(reopened))
                self.assertNotIn(key, backend.field_map(reopened))
                with experimental_limits():
                    self.assertIn(key, backend.field_map(reopened))

    def test_bound_adapter_scopes_numeric_mode_through_native_readback(self):
        for entry, key in ((NUMERIC_PROFILES[5], 'weapon_0_rank_0'),
                           (NUMERIC_PROFILES[6], 'weapon_0_rank_0'),
                           (NUMERIC_PROFILES[12], 'material_0')):
            with self.subTest(profile=entry[0]):
                backend, document = profile(*entry)
                extension = '.dat' if entry[0].endswith('vita') else '.bin'
                adapter = BoundScalarAdapter(backend.GAME_ID, extension, backend, experimental=True)
                field = adapter.field_map(document)[key]
                changes = adapter.stage(document, {}, key, field.experimental_maximum)
                self.assertFalse(experimental_enabled())
                self.assertEqual(len(adapter.review(document, changes)), 1)
                output = adapter.serialize(document, changes)
                reopened = adapter.decode(output)
                self.assertEqual(adapter.field_map(reopened)[key].value(reopened.payload), field.experimental_maximum)
                self.assertFalse(experimental_enabled())
                strict = BoundScalarAdapter(backend.GAME_ID, extension, backend)
                with self.assertRaises(SaveError):
                    strict.serialize(document, changes)

    def test_nioh_existing_u64_balances_and_u16_stacks_preserve_records(self):
        from koei_editor.games.nioh3 import codec

        backend, document = profile(*NUMERIC_PROFILES[-1])
        selected = [field for field in backend.fields_for(document)
                    if field.id in ('amrita', 'gold') or field.id == 'inventory_0_quantity']
        self.assertEqual({field.size for field in selected}, {2, 8})
        changes = {}
        allowed = set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
        with experimental_limits():
            for field in selected:
                target = (1 << (8 * field.size)) - 1
                self.assertEqual(field.experimental_maximum, target)
                changes = backend.stage(document, changes, field.id, target)
                allowed.update(range(field.offset, field.offset + field.size))
            reopened = backend.decode(backend.serialize(document, changes))
            touched = {index for index, (before, after) in enumerate(zip(document.payload, reopened.payload))
                       if before != after}
            self.assertLessEqual(touched, allowed)
            for field in selected:
                self.assertEqual(field.value(reopened.payload), field.experimental_maximum)
            with self.assertRaises(SaveError):
                backend.stage(document, {}, 'inventory_0_quantity', 0)
            with self.assertRaises(SaveError):
                backend.stage(document, {}, 'inventory_999_quantity', 10)

    def test_wolong_json_widths_and_existing_stack_identity(self):
        from koei_editor.games.wolong import wolong_parser as backend
        from tests.test_wolong_format import procedural_payload, seal, root_of

        document = backend.decode(seal(procedural_payload()))
        original_root = root_of(document.payload)
        targets = {'sen': (1 << 64) - 1, 'possession_items_4_num': (1 << 32) - 1}
        for key, target in targets.items():
            with self.assertRaises(SaveError):
                backend.stage(document, {}, key, target)
        with experimental_limits():
            changes = {}
            for key, target in targets.items():
                field = backend.field_map(document)[key]
                self.assertEqual(field.experimental_maximum, target)
                changes = backend.stage(document, changes, key, target)
                with self.assertRaises(SaveError):
                    backend.stage(document, changes, key, target + 1)
            reopened = backend.decode(backend.serialize(document, changes))
            self.assertIn('possession_items_4_num', backend.field_map(reopened))
            for key, target in targets.items():
                self.assertEqual(backend.read_back_value(reopened, key), target)
            self.assertNotIn('possession_items_0_num', backend.field_map(document))
            with self.assertRaises(SaveError):
                backend.stage(document, changes, 'possession_items_4_num', 0)
        changed_root = root_of(reopened.payload)
        original_root['PlayerData']['sen'] = targets['sen']
        original_root['PossessionItemData']['possession_items'][4]['ItemObjectData']['num'] = targets['possession_items_4_num']
        self.assertEqual(changed_root, original_root)
        self.assertNotIn('possession_items_4_num', backend.field_map(reopened))
        with experimental_limits():
            self.assertIn('possession_items_4_num', backend.field_map(reopened))

"""Registered adapters reject invalid batches before Max can normalize them."""
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.sw4_ps3 import parser as sw4
from koei_editor.game_registry import get_game
from tests.test_atelier_sophie2_format import procedural_raw as sophie_raw
from tests.test_ps3_expansion import fixture as ps3_fixture
from tests.test_pw4_format import procedural_raw as pw4_raw


class BoundPendingSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapters = {game: get_game(game).get_scalar_adapter()
                        for game in ('pw4', 'atelier_sophie2', 'sw4_ps3')}
        raw = {'pw4': pw4_raw(), 'atelier_sophie2': sophie_raw(),
               'sw4_ps3': ps3_fixture(sw4)}
        cls.documents = {game: adapter.decode(raw[game]) for game, adapter in cls.adapters.items()}

    def test_invalid_existing_batch_rejected_before_stage_unstage_or_max(self):
        for game, adapter in self.adapters.items():
            document = self.documents[game]
            field = adapter.fields_for(document)[0]
            original = field.value(document.payload)
            for pending in ({'unmapped': 1}, {field.id: -1}, {field.id: True},
                            {field.id: 'bad'}, {field.id: field.maximum + 1},
                            {1: 1}, None, [], [(field.id, 1)]):
                for operation, args in (('stage', (field.id, original)),
                                        ('stage', (field.id, field.maximum)),
                                        ('maximums', ()), ('limit_values', ([field.id],))):
                    with self.subTest(game=game, operation=operation, pending=pending):
                        with self.assertRaises(SaveError):
                            getattr(adapter, operation)(document, pending, *args)

    def test_failed_second_stage_preserves_complete_first_batch(self):
        for game, adapter in self.adapters.items():
            document = self.documents[game]
            fields = adapter.fields_for(document)
            first, second = fields[:2]
            value = first.maximum if first.value(document.payload) != first.maximum else first.minimum
            pending = adapter.stage(document, {}, first.id, value)
            opened = document.raw
            for key, invalid in ((second.id, -1), (['unmapped'], 1), (None, 1)):
                with self.subTest(game=game, key=key), self.assertRaises(SaveError):
                    adapter.stage(document, pending, key, invalid)
                self.assertEqual(pending, {first.id: value})
                self.assertEqual(document.raw, opened)
            self.assertEqual(len(adapter.review(document, pending)), 1)

    def test_opened_above_limit_quantity_can_be_unstaged_without_lowering_it(self):
        adapter = self.adapters['pw4']
        document = self.documents['pw4']
        field = adapter.field_map(document)['coin_399_quantity']
        original = field.value(document.payload)
        self.assertGreater(original, field.maximum)
        self.assertEqual(adapter.stage(document, {field.id: original}, field.id, original), {})
        limits = adapter.limit_values(document, {field.id: original}, [field.id])
        self.assertNotIn(field.id, limits)
        maximums = adapter.maximums(document, {field.id: original}, 'Owned coins')
        self.assertNotIn(field.id, maximums)
        self.assertEqual(field.value(adapter.decode(adapter.serialize(document, maximums)).payload), original)

    def test_opened_value_shortcut_validates_existing_and_resulting_native_dependencies(self):
        from tests.test_hyrule_fire_emblem_depth import instruction_slot
        adapter = get_game('three_houses').get_scalar_adapter()
        document = adapter.decode(instruction_slot())
        first, third = 'character:0:ability:0', 'character:0:ability:2'
        pending = adapter.stage(document, {}, first, 240)
        pending = adapter.stage(document, pending, third, 2)
        original = dict(pending)
        # Scalar validation succeeds for ID 2, but the reopened loadout would
        # contain it twice. The opened-value shortcut cannot bypass this rule.
        with self.assertRaises(SaveError):
            adapter.stage(document, pending, first, 2)
        self.assertEqual(pending, original)
        self.assertEqual(adapter.changed_payload(document, pending)[12 + 0x644 + 0x7F], 240)
        # An already invalid complete map is also rejected before a no-op can
        # remove its offending key or touch an unrelated opened value.
        invalid = {third: 2}
        for key, value in ((third, 240), ('character:0:motivation', 50)):
            with self.subTest(key=key), self.assertRaises(SaveError):
                adapter.stage(document, invalid, key, value)
        self.assertEqual(invalid, {third: 2})

    def test_unusual_opened_text_unstages_exactly_after_variable_length_edit(self):
        from tests.test_wolong_expansion import named_battle_set_payload
        adapter = get_game('wolong').get_scalar_adapter()
        key = 'battle_set_3_name'
        for original in ('', '\u65e5\u672c\u8a9e', 'A' * 80):
            with self.subTest(original=original):
                document = adapter.decode(named_battle_set_payload(original))
                pending = adapter.stage(document, {}, key, 'Revised')
                self.assertEqual(pending, {key: 'Revised'})
                self.assertEqual(adapter.stage(document, pending, key, original), {})
                self.assertEqual(adapter.serialize(document, {key: original}), document.raw)
                with self.assertRaises(SaveError):
                    adapter.stage(document, pending, key, b'Revised')
                self.assertEqual(pending, {key: 'Revised'})

    def test_backend_cannot_silently_drop_the_requested_stage_value(self):
        from tests.test_verified_editors import synthetic_raw
        adapter = get_game('dw8xl').get_scalar_adapter()
        document = adapter.decode(synthetic_raw('dw8xl'))
        previous = {'gold': 123}
        for result in (previous, {'gold': 123, 'officer_0_attack': 99}):
            with self.subTest(result=result), \
                    patch.object(adapter.backend, 'stage', return_value=result):
                with self.assertRaisesRegex(SaveError, 'did not stage the chosen value'):
                    adapter.stage(document, previous, 'gold', 456)
            self.assertEqual(previous, {'gold': 123})
            self.assertEqual(document.raw, synthetic_raw('dw8xl'))

    def test_max_targets_retain_opened_maximum_to_unstage_a_pending_reduction(self):
        from dataclasses import replace
        from tests.test_verified_editors import synthetic_raw
        from tests.test_verified_snapshot_review import reseed
        adapter = get_game('dw8xl').get_scalar_adapter()
        document = adapter.decode(synthetic_raw('dw8xl'))
        field = adapter.field_map(document)['gold']
        payload = bytearray(document.payload)
        payload[field.offset:field.offset + field.size] = field.maximum.to_bytes(field.size, 'little')
        document = adapter.decode(reseed(replace(document, payload=bytes(payload)), document.seed))
        pending = adapter.stage(document, {}, field.id, 100)
        targets = adapter.limit_values(document, pending, [field.id])
        self.assertEqual(targets, {field.id: field.maximum})
        self.assertEqual(adapter.stage(document, pending, field.id, targets[field.id]), {})
        self.assertEqual(pending, {field.id: 100})
        self.assertEqual(adapter.maximums(document, pending, 'Resources').get(field.id), None)

    def test_max_bridge_restores_higher_opened_values_but_excludes_nonmaxable_targets(self):
        import struct
        from koei_editor.games.wo4 import parser as backend
        from tests.test_wo4_pc import generated_raw, repack
        adapter = get_game(backend.GAME_ID).get_scalar_adapter()
        document = adapter.decode(generated_raw())
        payload = bytearray(document.payload)
        struct.pack_into('<I', payload, backend.SYSTEM_GLOBAL + 0xCC, 123456789)
        document = adapter.decode(repack(payload))
        unusual = 'officer_002_skill_points'
        pending = adapter.stage(document, {}, 'gems', 100)
        pending = adapter.stage(document, pending, unusual, 10)
        self.assertEqual(adapter.limit_values(document, pending, ('gems', unusual)),
                         {'gems': 123456789, unusual: 255})
        self.assertEqual(adapter.limit_values(document, {}, ('gems', unusual)), {})
        with patch.object(backend, 'limit_values', return_value={'gems': 123456788}):
            with self.assertRaises(SaveError):
                adapter.limit_values(document, pending, ('gems',))
        with patch.object(backend, 'limit_values', return_value={'skill_orbs': 7}):
            self.assertEqual(adapter.limit_values(document, pending, ('skill_orbs',)), {})
        self.assertEqual(pending, {'gems': 100, unusual: 10})

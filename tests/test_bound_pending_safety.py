"""Registered adapters reject invalid batches before Max can normalize them."""
import unittest

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

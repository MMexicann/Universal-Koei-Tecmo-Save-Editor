"""Availability is distinct from clears, rewards and officer prerequisites."""
from pathlib import Path
import tempfile
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import availability
from koei_editor.games.dw6 import dw6_parser as pc
from koei_editor.games.dw6_ps3 import parser as ps3
from koei_editor.shared.experimental_limits import experimental_limits
from tests.test_dw6_equipment import equipped_fixture
from tests.test_dw6_ps3 import context


def fixture(backend):
    raw = bytearray(equipped_fixture(backend))
    for index in range(41):
        raw[backend.OFFICER_BASE + index * 168 + 164] = index % 2
    stages = backend.OFFICER_BASE + 41 * 168
    for index in range(45):
        raw[stages + index * 20 + 16] = index % 2
    for index in range(17):
        raw[stages + 900 + index * 4] = index % 2
    return bytes(raw)


class DW6AvailabilityTests(unittest.TestCase):
    def test_one_way_stage_and_musou_prerequisites_and_undo_dependencies(self):
        for backend in (pc, ps3):
            with self.subTest(profile=backend.GAME_ID):
                adapter = get_game(backend.GAME_ID).get_scalar_adapter()
                doc = backend.decode(fixture(backend))
                mapping = backend.field_map(doc)
                stages = [f for f in mapping.values() if f.group == availability.STAGE_GROUP]
                modes = [f for f in mapping.values() if f.group == availability.MUSOU_GROUP]
                self.assertEqual((len(stages), len(modes)), (45, 17))
                changes = adapter.stage(doc, {}, 'stage_0_available', 1)
                self.assertEqual(adapter.stage(doc, changes, 'stage_0_available', 0), {})
                raw = adapter.serialize(doc, changes)
                offset = stages[0].offset
                self.assertEqual(raw[:offset], doc.raw[:offset])
                self.assertEqual(raw[offset + 1:], doc.raw[offset + 1:])
                with self.assertRaises(SaveError):
                    adapter.stage(doc, {}, 'musou_0_available', 1)
                changes = adapter.stage(doc, {}, 'officer_0_unlocked', 1)
                changes = adapter.stage(doc, changes, 'musou_0_available', 1)
                with self.assertRaises(SaveError):
                    adapter.stage(doc, changes, 'officer_0_unlocked', 0)
                raw = adapter.serialize(doc, changes)
                permitted = {mapping[key].offset for key in changes}
                self.assertEqual({i for i, (a, b) in enumerate(zip(raw, doc.raw)) if a != b}, permitted)
                changes = adapter.stage(doc, changes, 'musou_0_available', 0)
                self.assertEqual(adapter.stage(doc, changes, 'officer_0_unlocked', 0), {})
                for key in ('stage_1_available', 'musou_1_available'):
                    with self.assertRaises(SaveError):
                        adapter.stage(doc, {}, key, 0)

    def test_limits_unknown_variants_batch_prerequisites_and_max_exclusions(self):
        for backend in (pc, ps3):
            with self.subTest(profile=backend.GAME_ID):
                adapter = get_game(backend.GAME_ID).get_scalar_adapter()
                doc = backend.decode(fixture(backend))
                for value in (-1, 2, True, '1'):
                    with experimental_limits(True), self.assertRaises(SaveError):
                        adapter.serialize(doc, {'stage_0_available': value})
                assignments = backend.musou_unlock_values(doc)
                keys = tuple(assignments)
                self.assertLess(keys.index('officer_0_unlocked'), keys.index('musou_0_available'))
                pending = {}
                for key, value in assignments.items():
                    pending = adapter.stage(doc, pending, key, value)
                self.assertEqual(pending, assignments)
                backend.serialize(doc, pending)
                self.assertEqual(len(backend.stage_unlock_values(doc)), 23)
                self.assertFalse(any(f.maxable for f in backend.fields_for(doc) if f.group in availability.GROUPS))
                self.assertFalse(any(key in backend.maximums(doc, {}) for key in assignments))
                raw = bytearray(doc.raw)
                mapping = backend.field_map(doc)
                raw[mapping['stage_0_available'].offset] = 9
                raw[mapping['musou_0_available'].offset] = 3
                raw[backend.OFFICER_BASE + 2 * 168 + 164] = 7
                unknown = backend.decode(bytes(raw))
                for key in ('stage_0_available', 'musou_0_available', 'musou_2_available'):
                    self.assertNotIn(key, backend.field_map(unknown))
                    with experimental_limits(True), self.assertRaises(SaveError):
                        adapter.serialize(unknown, {key: 1})
                self.assertEqual(adapter.serialize(unknown, {}), bytes(raw))

    def test_batch_safe_copy_preserves_every_clear_and_all_other_bytes(self):
        for backend in (pc, ps3):
            with self.subTest(profile=backend.GAME_ID), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / ('APP.BIN' if backend is ps3 else 'save.dat')
                source.write_bytes(fixture(backend))
                if backend is ps3:
                    context(root)
                adapter = get_game(backend.GAME_ID).get_scalar_adapter()
                doc = adapter.read_save(source)
                pending = {}
                for assignments in (backend.stage_unlock_values(doc), backend.musou_unlock_values(doc)):
                    for key, value in assignments.items():
                        pending = adapter.stage(doc, pending, key, value)
                actual = adapter.save_as(doc, pending, root / ('edited.bin' if backend is ps3 else 'edited.dat'))
                mapping = backend.field_map(doc)
                changed = {i for i, (a, b) in enumerate(zip(actual.raw, doc.raw)) if a != b}
                self.assertEqual(changed, {mapping[key].offset for key in pending})
                self.assertEqual(source.read_bytes(), doc.raw)
                stages = backend.OFFICER_BASE + 41 * 168
                for index in range(45):
                    self.assertEqual(actual.raw[stages + index * 20:stages + index * 20 + 16],
                                     doc.raw[stages + index * 20:stages + index * 20 + 16])
                for index in range(17):
                    offset = stages + 900 + index * 4
                    self.assertEqual(actual.raw[offset + 1:offset + 4], doc.raw[offset + 1:offset + 4])

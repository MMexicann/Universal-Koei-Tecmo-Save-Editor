"""Source-backed existing ranked-attribute replacement; no game-load claim."""
import os
from pathlib import Path
import struct
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import verified_editor as backend
from tests.test_dw8_affinity import procedural_weapons


def procedural_attributes():
    document = backend.decode(procedural_weapons(), 'dw8xl')
    payload = bytearray(document.payload)
    # Two ranked identities plus an unranked and unknown identity. The second
    # weapon witnesses a third ranked identity for a non-conflicting choice.
    start = backend.DW8_WEAPON_BASE
    payload[start + 6:start + 18] = bytes((7, 2, 1, 250, 255, 255, 4, 3, 1, 17, 0, 0))
    start += backend.DW8_WEAPON_STRIDE
    payload[start + 6:start + 18] = bytes((41, 3, 7, 255, 255, 255, 8, 11, 0, 0, 0, 0))
    inner = backend.byte_cipher(bytes(payload), document.format.inner_seed)
    return (struct.pack('<HH', backend.word_sum(inner), document.seed)
            + backend.word_cipher(inner, document.seed)
            + bytes(((sum(payload) & 255) ^ (backend.mix_word(document.seed) & 255),)))


class DW8AttributeIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = backend.decode(procedural_attributes(), 'dw8xl')

    def test_only_existing_normal_ranked_slots_and_opened_palette_are_editable(self):
        mapping = backend.field_map(self.document)
        identities = {key for key, field in mapping.items() if field.group == 'Weapon attribute identities'}
        self.assertEqual(identities, {'weapon_0_attribute_0_identity', 'weapon_0_attribute_1_identity',
                                     'weapon_1_attribute_0_identity', 'weapon_4_attribute_0_identity'})
        options = backend.field_options(self.document, 'weapon_0_attribute_0_identity')
        self.assertEqual(tuple(value for value, _ in options), (2, 7, 41))
        self.assertIn('Comet', options[2][1])
        self.assertEqual(backend.serialize(self.document, {}), self.document.raw)
        for value in (0, 1, 3, 250, 255, 256, True, '41', 41.0):
            with self.subTest(value=value), self.assertRaises(SaveError):
                backend.stage(self.document, {}, 'weapon_0_attribute_0_identity', value)
        for key in ('weapon_0_attribute_2_identity', 'weapon_0_attribute_3_identity',
                    'weapon_0_attribute_4_identity', 'weapon_1_attribute_1_identity',
                    'weapon_1_attribute_2_identity', 'weapon_2_attribute_0_identity'):
            with self.subTest(key=key), self.assertRaises(SaveError):
                backend.serialize(self.document, {key: 41})

    def test_identity_and_rank_edit_are_surgical_reparsed_and_keep_other_systems(self):
        changes = backend.stage(self.document, {}, 'weapon_0_attribute_0_identity', 41)
        changes = backend.stage(self.document, changes, 'weapon_0_attribute_0_rank', 9)
        reopened = backend.decode(backend.serialize(self.document, changes), 'dw8xl')
        expected = bytearray(self.document.payload)
        expected[backend.DW8_WEAPON_BASE + 6] = 41
        expected[backend.DW8_WEAPON_BASE + 12] = 9
        self.assertEqual(reopened.payload, bytes(expected))
        self.assertEqual(backend.weapon(reopened, 1)['attributes'],
                         ((41, 9), (2, 3), (1, 1), (250, 17), (255, 0), (255, 0)))
        self.assertEqual(backend.progressions(reopened), backend.progressions(self.document))
        self.assertEqual(backend.bodyguards(reopened), backend.bodyguards(self.document))
        self.assertEqual(reopened.seed, self.document.seed)
        self.assertEqual(backend.stage(self.document, changes, 'weapon_0_attribute_0_identity', 7),
                         {'weapon_0_attribute_0_rank': 9})

    def test_duplicate_guard_checks_complete_batch_and_unstage_dependencies(self):
        first, second = 'weapon_0_attribute_0_identity', 'weapon_0_attribute_1_identity'
        for action in (lambda: backend.stage(self.document, {}, first, 2),
                       lambda: backend.serialize(self.document, {first: 2}),
                       lambda: backend.review(self.document, {first: 2}),
                       lambda: backend.maximums(self.document, {first: 2})):
            with self.assertRaises(SaveError):
                action()
        swapped = {first: 2, second: 7}
        reopened = backend.decode(backend.serialize(self.document, swapped), 'dw8xl')
        self.assertEqual(backend.weapon(reopened, 1)['attributes'][:2], ((2, 4), (7, 3)))
        # Removing either half of a valid batch would leave a duplicate.
        for key, original in ((first, 7), (second, 2)):
            with self.subTest(key=key), self.assertRaises(SaveError):
                backend.stage(self.document, swapped, key, original)
        adapter = get_game('dw8xl').get_scalar_adapter()
        with self.assertRaises(SaveError):
            adapter.stage(self.document, swapped, first, 7)

    def test_replacements_require_a_normal_final_rank_even_in_experimental_mode(self):
        adapter = get_game('dw8xl').get_scalar_adapter(experimental=True)
        identity, rank = 'weapon_0_attribute_0_identity', 'weapon_0_attribute_0_rank'
        for value in (0, 11, 255):
            with self.subTest(value=value), self.assertRaises(SaveError):
                adapter.serialize(self.document, {identity: 41, rank: value})
        # Experimental rank-only editing remains available with unchanged identity.
        pending = adapter.stage(self.document, {}, rank, 11)
        self.assertEqual(pending, {rank: 11})
        with self.assertRaises(SaveError):
            adapter.stage(self.document, pending, identity, 41)
        pending = adapter.stage(self.document, {}, identity, 41)
        with self.assertRaises(SaveError):
            adapter.stage(self.document, pending, rank, 11)
        adapter.serialize(self.document, {identity: 41, rank: 10})

    def test_identities_are_excluded_from_all_max_actions_and_choices_are_native(self):
        keys = [key for key, field in backend.field_map(self.document).items()
                if field.group == 'Weapon attribute identities']
        self.assertEqual(backend.limit_values(self.document, {}, keys), {})
        self.assertEqual(backend.maximums(self.document, {}, 'Weapon attribute identities'), {})
        self.assertEqual(tuple(value for value, _ in backend.field_options(self.document, 'officer_0_compatibility_0')),
                         (25, 50, 75, 100))
        self.assertEqual(tuple(value for value, _ in backend.field_options(self.document, 'weapon_0_affinity')),
                         (0, 1, 2))

    def test_corrupt_original_and_unknown_original_combinations_stay_protected(self):
        corrupted = bytearray(self.document.raw)
        corrupted[1000] ^= 1
        with self.assertRaises(SaveError):
            backend.decode(bytes(corrupted), 'dw8xl')
        # A rank edit cannot make a duplicate original record eligible for ID edits.
        original = self.document
        payload = bytearray(original.payload)
        payload[backend.DW8_WEAPON_BASE + 7] = 7
        inner = backend.byte_cipher(bytes(payload), original.format.inner_seed)
        raw = (struct.pack('<HH', backend.word_sum(inner), original.seed)
               + backend.word_cipher(inner, original.seed)
               + bytes(((sum(payload) & 255) ^ (backend.mix_word(original.seed) & 255),)))
        unusual = backend.decode(raw, 'dw8xl')
        self.assertEqual(backend.serialize(unusual, {}), raw)
        self.assertFalse(any(field.slot == 1 and field.group == 'Weapon attribute identities'
                             for field in backend.fields_for(unusual)))
        self.assertIn('weapon_0_attribute_0_rank', backend.field_map(unusual))

    def test_dashboard_links_and_gui_choices_review_undo_safe_copy(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.dat'
            source.write_bytes(self.document.raw)
            editor = get_game('dw8xl').create_editor(root, root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            self.assertEqual(editor.backup.read_bytes(), self.document.raw)
            dashboard = editor.presentation.dashboard(editor.document)
            metric = next(metric for section in dashboard.sections for card in section.cards
                          for metric in card.metrics if metric.field_id == 'weapon_0_attribute_0_identity')
            self.assertIn('Velocity', metric.value)
            editor.group.set('Weapon attribute identities')
            editor.refresh()
            key = 'weapon_0_attribute_0_identity'
            editor.fields.selection_set(key)
            editor.selected()
            self.assertEqual(len(editor.value_choice.cget('values')), 3)
            self.assertIn('Duplicate', editor.selection_info.get())
            editor.choice_value.set(editor.value_choice.cget('values')[2])
            editor.selected_choice()
            editor.apply_selected()
            self.assertEqual(editor.changes, {key: 41})
            editor.review()
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.value.set('41')
            editor.apply_selected()
            destination = Path(folder) / 'edited.dat'
            editor.save_to(destination)
            self.assertEqual(backend.weapon(editor.document, 1)['attributes'][0], (41, 4))
            self.assertEqual(source.read_bytes(), self.document.raw)

    @unittest.skipUnless(os.environ.get('DW8XL_SAVE_COPY'), 'Private native DW8 XL copy not configured.')
    def test_native_copy_identity_replacement_roundtrip_and_surgical_preservation(self):
        document = backend.read_save(Path(os.environ['DW8XL_SAVE_COPY']), 'dw8xl')
        self.assertEqual(backend.serialize(document, {}), document.raw)
        field = next(field for field in backend.fields_for(document) if field.group == 'Weapon attribute identities')
        existing = {identity for identity, _ in backend.weapon(document, field.slot)['attributes']}
        choice = next(identity for identity in field.allowed_ids if identity not in existing)
        changes = backend.stage(document, {}, field.id, choice)
        reopened = backend.decode(backend.serialize(document, changes), 'dw8xl')
        differences = {i for i, (old, new) in enumerate(zip(document.payload, reopened.payload)) if old != new}
        self.assertEqual(differences, {field.offset})
        self.assertEqual(backend.progressions(reopened), backend.progressions(document))
        self.assertEqual(backend.bodyguards(reopened), backend.bodyguards(document))

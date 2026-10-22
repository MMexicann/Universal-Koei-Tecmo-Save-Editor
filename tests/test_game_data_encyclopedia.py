"""Contract and source-parity checks for the bundled reference feed."""
from copy import deepcopy
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.three_hopes.catalog import CHARACTERS, WEAPONS
from koei_editor.shared.game_data_encyclopedia import (
    ALLOWED_LICENSES,
    load_game_data_encyclopedia,
    validate_dataset,
)


class GameDataEncyclopediaTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_game_data_encyclopedia()

    def test_feed_is_scoped_to_the_registered_switch_edition(self):
        self.assertEqual([game['id'] for game in self.dataset['games']], ['three_hopes'])
        game = self.dataset['games'][0]
        profile = get_game('three_hopes')
        self.assertEqual(game['title'], profile.title)
        self.assertEqual(game['edition'], profile.subtitle)
        self.assertEqual(game['platform'], profile.platform)
        self.assertIn('only', game['scope_note'])
        self.assertEqual(
            {entity['kind'] for entity in self.dataset['entities']},
            {'character', 'weapon'},
        )

    def test_data_has_unique_stable_and_native_ids(self):
        entities = self.dataset['entities']
        self.assertEqual(len({entity['id'] for entity in entities}), len(entities))
        native_keys = {
            (entity['game_id'], entity['edition'], entity['kind'], entity['native_id'])
            for entity in entities
        }
        self.assertEqual(len(native_keys), len(entities))
        for entity in entities:
            self.assertEqual(
                entity['id'],
                f"three_hopes:{entity['kind']}:{entity['native_id']:03d}",
            )

    def test_every_entity_field_has_a_licensed_source_reference(self):
        source_map = {source['id']: source for source in self.dataset['sources']}
        self.assertIn(self.dataset['dataset_license'], ALLOWED_LICENSES)
        self.assertTrue(self.dataset['dataset_license_note'])
        self.assertEqual(len(source_map), len(self.dataset['sources']))
        for source in source_map.values():
            self.assertIn(source['license'], ALLOWED_LICENSES)
            self.assertTrue(source['attribution'])
            self.assertTrue(source['uri'].startswith('https://'))
            self.assertTrue(source['license_uri'].startswith('https://'))
            self.assertTrue(source.get('revision') or source.get('accessed_on'))
        game = self.dataset['games'][0]
        self.assertIn(game['profile_source_id'], source_map)
        self.assertEqual(source_map[game['profile_source_id']]['license'], 'MIT')
        for entity in self.dataset['entities']:
            expected_fields = {'game_id', 'edition', 'kind', 'native_id', 'name'}
            self.assertEqual(set(entity['field_sources']), expected_fields)
            self.assertTrue(set(entity['field_sources'].values()) <= set(source_map))

    def test_character_and_weapon_labels_match_pinned_source_catalog(self):
        expected = {
            ('character', native_id): name
            for native_id, name in CHARACTERS.items()
        }
        expected.update({
            ('weapon', native_id): name
            for native_id, name in WEAPONS.items()
        })
        actual = {
            (entity['kind'], entity['native_id']): entity['name']
            for entity in self.dataset['entities']
        }
        self.assertEqual(actual, expected)
        self.assertEqual(sum(entity['kind'] == 'character' for entity in self.dataset['entities']), 68)
        self.assertEqual(sum(entity['kind'] == 'weapon' for entity in self.dataset['entities']), 150)

    def test_validator_rejects_duplicate_ids_and_missing_sources(self):
        duplicate_id = deepcopy(self.dataset)
        duplicate_id['entities'][1]['id'] = duplicate_id['entities'][0]['id']
        with self.assertRaisesRegex(ValueError, 'Duplicate encyclopedia entity ID'):
            validate_dataset(duplicate_id)

        duplicate_native_id = deepcopy(self.dataset)
        duplicate_native_id['entities'][1]['native_id'] = duplicate_native_id['entities'][0]['native_id']
        with self.assertRaisesRegex(ValueError, 'Duplicate native ID'):
            validate_dataset(duplicate_native_id)

        missing_source = deepcopy(self.dataset)
        missing_source['entities'][0]['field_sources']['name'] = 'unlisted-source'
        with self.assertRaisesRegex(ValueError, 'unknown source'):
            validate_dataset(missing_source)

    def test_validator_rejects_unresolved_and_cross_edition_links(self):
        unresolved = deepcopy(self.dataset)
        unresolved['entities'][0]['relationships'] = [{
            'type': 'related-to',
            'entity_id': 'three_hopes:character:999',
            'source_id': 'few2-binary-templates',
        }]
        with self.assertRaisesRegex(ValueError, 'target does not exist'):
            validate_dataset(unresolved)

        cross_edition = deepcopy(self.dataset)
        cross_edition['entities'][0]['relationships'] = [{
            'type': 'related-to',
            'entity_id': cross_edition['entities'][1]['id'],
            'source_id': 'few2-binary-templates',
        }]
        cross_edition['games'].append({
            **cross_edition['games'][0],
            'id': 'other_edition',
            'edition': 'Other edition',
        })
        cross_edition['entities'][1]['game_id'] = 'other_edition'
        cross_edition['entities'][1]['edition'] = 'Other edition'
        with self.assertRaisesRegex(ValueError, 'crosses game editions'):
            validate_dataset(cross_edition)

    def test_validator_rejects_edition_mismatch(self):
        mismatch = deepcopy(self.dataset)
        mismatch['entities'][0]['edition'] = 'Nintendo Switch'
        with self.assertRaisesRegex(ValueError, 'mismatched edition'):
            validate_dataset(mismatch)


if __name__ == '__main__':
    unittest.main()

"""Contract and source-parity checks for the bundled reference feed."""
from copy import deepcopy
from pathlib import Path
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.hyrule_warriors.catalog import MATERIALS, SKILLS as HYRULE_SKILLS, WEAPONS as HYRULE_WEAPONS
from koei_editor.games.three_hopes.catalog import CHARACTERS, WEAPONS
from koei_editor.shared.game_data_encyclopedia import (
    ALLOWED_LICENSES,
    ALLOWED_DATASET_LICENSES,
    load_game_data_encyclopedia,
    validate_dataset,
)

EXCLUDED_HYRULE_WEAPONS = {
    60: '[unknown weapon]',
    109: "*** Ganon's Rage (Ganon) RESERVED, DO NOT USE ***",
    110: "*** Cucco's Spirit (Cucco) RESERVED, DO NOT USE ***",
    150: 'Unknown (Unk - Unk Level 1)',
    151: 'Unknown (Unk - Unk Level 2)',
    152: 'Unknown (Unk - Unk Level 3)',
}


class GameDataEncyclopediaTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_game_data_encyclopedia()

    def test_three_hopes_feed_entry_matches_registered_switch_edition(self):
        game = next(game for game in self.dataset['games'] if game['id'] == 'three_hopes')
        profile = get_game('three_hopes')
        self.assertEqual(game['title'], profile.title)
        self.assertEqual(game['edition'], profile.subtitle)
        self.assertEqual(game['platform'], profile.platform)
        self.assertIn('only', game['scope_note'])
        self.assertEqual(
            {entity['kind'] for entity in self.dataset['entities'] if entity['game_id'] == 'three_hopes'},
            {'character', 'weapon'},
        )

    def test_data_has_unique_stable_and_native_ids(self):
        entities = self.dataset['entities']
        self.assertEqual(len({entity['id'] for entity in entities}), len(entities))
        native_entities = [entity for entity in entities if 'native_id' in entity]
        native_keys = {
            (entity['game_id'], entity['edition'], entity['kind'], entity['native_id'])
            for entity in native_entities
        }
        self.assertEqual(len(native_keys), len(native_entities))
        for entity in native_entities:
            self.assertEqual(
                entity['id'],
                f"{entity['game_id']}:{entity['kind']}:{entity['native_id']:03d}",
            )

    def test_every_entity_field_has_a_licensed_source_reference(self):
        source_map = {source['id']: source for source in self.dataset['sources']}
        self.assertIn(self.dataset['dataset_license'], ALLOWED_DATASET_LICENSES)
        self.assertTrue(self.dataset['dataset_license_note'])
        self.assertEqual(len(source_map), len(self.dataset['sources']))
        for source in source_map.values():
            self.assertIn(source['license'], ALLOWED_LICENSES)
            self.assertTrue(source['attribution'])
            self.assertTrue(source['uri'].startswith('https://'))
            self.assertTrue(source['license_uri'].startswith('https://'))
            self.assertTrue(source.get('revision') or source.get('accessed_on'))
            if 'game_ids' in source:
                self.assertTrue(source['game_ids'])
                self.assertTrue(set(source['game_ids']) <= {game['id'] for game in self.dataset['games']})
            if 'claim_scopes' in source:
                self.assertTrue(source['game_ids'])
        game = next(game for game in self.dataset['games'] if game['id'] == 'three_hopes')
        self.assertIn(game['profile_source_id'], source_map)
        self.assertEqual(source_map[game['profile_source_id']]['license'], 'MIT')
        self.assertIn(game['id'], source_map[game['profile_source_id']]['game_ids'])
        for entity in self.dataset['entities']:
            expected_fields = {'game_id', 'edition', 'kind', 'name'}
            if 'native_id' in entity:
                expected_fields.add('native_id')
            if 'summary' in entity:
                expected_fields.add('summary')
            self.assertEqual(set(entity['field_sources']), expected_fields)
            self.assertTrue(set(entity['field_sources'].values()) <= set(source_map))
            for field, source_id in entity['field_sources'].items():
                source = source_map[source_id]
                if 'game_ids' in source:
                    self.assertIn(entity['game_id'], source['game_ids'])
                if 'claim_scopes' in source:
                    claim_scope = f'entity.{field}'
                    self.assertTrue(
                        claim_scope in source['claim_scopes']
                        or (field.startswith('attributes.')
                            and 'entity.attributes' in source['claim_scopes'])
                    )

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
            if entity['game_id'] == 'three_hopes'
        }
        self.assertEqual(actual, expected)
        self.assertEqual(sum(entity['kind'] == 'character' and entity['game_id'] == 'three_hopes' for entity in self.dataset['entities']), 68)
        self.assertEqual(sum(entity['kind'] == 'weapon' and entity['game_id'] == 'three_hopes' for entity in self.dataset['entities']), 150)

    def test_hyrule_mappings_match_catalog_and_exact_wii_u_profile(self):
        game = next(game for game in self.dataset['games'] if game['id'] == 'hyrule_warriors')
        profile = get_game('hyrule_warriors')
        self.assertEqual(game['title'], profile.title)
        self.assertEqual(game['edition'], profile.subtitle)
        self.assertEqual(game['platform'], profile.platform)
        self.assertEqual(game['edition'], 'Wii U · APP.BIN')
        self.assertEqual(game['platform'], 'Wii U')

        expected = {
            ('material', native_id): name for native_id, name in enumerate(MATERIALS)
        }
        expected.update({
            ('weapon', native_id): name for native_id, name in enumerate(HYRULE_WEAPONS)
            if native_id not in EXCLUDED_HYRULE_WEAPONS
        })
        expected.update({
            ('skill', native_id): name for native_id, name in enumerate(HYRULE_SKILLS)
            if native_id != 0
        })
        hyrule_entities = [
            entity for entity in self.dataset['entities']
            if entity['game_id'] == 'hyrule_warriors' and 'native_id' in entity
        ]
        actual = {
            (entity['kind'], entity['native_id']): entity['name']
            for entity in hyrule_entities
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            {entity['kind'] for entity in hyrule_entities},
            {'material', 'weapon', 'skill'},
        )
        self.assertEqual(len(hyrule_entities), len(MATERIALS) + len(HYRULE_WEAPONS)
                         - len(EXCLUDED_HYRULE_WEAPONS) + len(HYRULE_SKILLS) - 1)
        self.assertFalse(any(entity['name'] == '(blank)' for entity in hyrule_entities))
        for entity in hyrule_entities:
            if entity['kind'] == 'weapon':
                self.assertNotIn(entity['native_id'], EXCLUDED_HYRULE_WEAPONS)

    def test_excluded_catalog_placeholders_are_exact_and_documented(self):
        self.assertEqual(
            {native_id: HYRULE_WEAPONS[native_id] for native_id in EXCLUDED_HYRULE_WEAPONS},
            EXCLUDED_HYRULE_WEAPONS,
        )
        self.assertEqual(HYRULE_SKILLS[0], '(blank)')
        docs = (Path(__file__).parents[1] / 'docs/GAME_DATA_ENCYCLOPEDIA.md').read_text(encoding='utf-8')
        for native_id, label in EXCLUDED_HYRULE_WEAPONS.items():
            self.assertIn(f'| Weapon | {native_id} | `{label}` |', docs)
        self.assertIn('| Skill | 0 | `(blank)` |', docs)
        player_facing = [
            entity for entity in self.dataset['entities']
            if entity['game_id'] == 'hyrule_warriors' and 'native_id' in entity
        ]
        self.assertFalse(any(
            entity['kind'] == 'weapon' and entity['native_id'] in EXCLUDED_HYRULE_WEAPONS
            for entity in player_facing
        ))
        self.assertFalse(any(
            entity['kind'] == 'skill' and entity['native_id'] == 0
            for entity in player_facing
        ))

    def test_hyrule_provenance_covers_license_revision_access_and_mechanics(self):
        sources = {source['id']: source for source in self.dataset['sources']}
        self.assertEqual(self.dataset['dataset_license'], 'source-specific')
        self.assertIn('MIT', self.dataset['dataset_license_note'])
        self.assertIn('CC BY-SA 3.0', self.dataset['dataset_license_note'])
        mapping_source = sources['hyrule-wiiu-catalog']
        profile_source = sources['hyrule-wiiu-profile-registry']
        self.assertEqual(mapping_source['license'], 'MIT')
        self.assertEqual(mapping_source['revision'], 'b4db8cd11157c6d5ae54a0a5edc88dba82aebe9d')
        self.assertIn('Marc Robledo', mapping_source['attribution'])
        self.assertEqual(mapping_source['game_ids'], ['hyrule_warriors'])
        self.assertEqual(mapping_source['claim_scopes'], ['entity.kind', 'entity.native_id', 'entity.name'])
        self.assertEqual(profile_source['game_ids'], ['hyrule_warriors'])
        self.assertEqual(profile_source['claim_scopes'], ['game.profile', 'entity.game_id', 'entity.edition'])

        wiki_sources = {
            source_id: sources[source_id]
            for source_id in ('koeitecmo-wiki-weapon-skills', 'koeitecmo-wiki-adventure-mode')
        }
        expected_revisions = {
            'koeitecmo-wiki-weapon-skills': '525135',
            'koeitecmo-wiki-adventure-mode': '513185',
        }
        for source_id, source in wiki_sources.items():
            self.assertEqual(source['license'], 'CC BY-SA 3.0')
            self.assertEqual(source['license_uri'], 'https://creativecommons.org/licenses/by-sa/3.0/')
            self.assertEqual(source['accessed_on'], '2026-10-22')
            self.assertIn('oldid=', source['uri'])
            self.assertEqual(source['revision'], expected_revisions[source_id])
            self.assertIn(f"oldid={source['revision']}", source['uri'])
            self.assertIn('Koei Tecmo Wiki contributors', source['attribution'])
            self.assertEqual(source['game_ids'], ['hyrule_warriors'])

        mechanics = [
            entity for entity in self.dataset['entities']
            if entity['game_id'] == 'hyrule_warriors' and entity['kind'] == 'mechanic'
        ]
        self.assertEqual(len(mechanics), 3)
        for entity in mechanics:
            source = sources[entity['field_sources']['summary']]
            self.assertIn(source['id'], wiki_sources)
            self.assertEqual(source['license'], 'CC BY-SA 3.0')
            self.assertTrue(entity['summary'])

    def test_entity_sources_and_links_never_cross_game_editions(self):
        sources = {source['id']: source for source in self.dataset['sources']}
        entities = {entity['id']: entity for entity in self.dataset['entities']}
        for entity in entities.values():
            for source_id in entity['field_sources'].values():
                source = sources[source_id]
                if 'game_ids' in source:
                    self.assertIn(entity['game_id'], source['game_ids'])
            for field, source_id in entity['field_sources'].items():
                source = sources[source_id]
                if 'claim_scopes' in source:
                    self.assertIn(f'entity.{field}', source['claim_scopes'])
            for relation in entity.get('relationships', []):
                target = entities[relation['entity_id']]
                self.assertEqual((target['game_id'], target['edition']),
                                 (entity['game_id'], entity['edition']))
                relation_source = sources[relation['source_id']]
                if 'game_ids' in relation_source:
                    self.assertIn(entity['game_id'], relation_source['game_ids'])
                if 'claim_scopes' in relation_source:
                    self.assertIn('entity.relationships', relation_source['claim_scopes'])

        wrong_source = deepcopy(self.dataset)
        hyrule_item = next(
            entity for entity in wrong_source['entities']
            if entity['game_id'] == 'hyrule_warriors' and entity['kind'] == 'material'
        )
        hyrule_item['field_sources']['name'] = 'few2-binary-templates'
        with self.assertRaisesRegex(ValueError, 'not applicable to the entity game ID'):
            validate_dataset(wrong_source)

        wrong_claim = deepcopy(self.dataset)
        mechanic = next(
            entity for entity in wrong_claim['entities']
            if entity['game_id'] == 'hyrule_warriors' and entity['kind'] == 'mechanic'
        )
        mechanic['field_sources']['summary'] = 'hyrule-wiiu-catalog'
        with self.assertRaisesRegex(ValueError, 'claim scope does not cover entity.summary'):
            validate_dataset(wrong_claim)

        wrong_relationship_source = deepcopy(self.dataset)
        hyrule_entity = next(
            entity for entity in wrong_relationship_source['entities']
            if entity['game_id'] == 'hyrule_warriors' and entity['kind'] == 'material'
        )
        hyrule_entity['relationships'] = [{
            'type': 'related-to',
            'entity_id': 'hyrule_warriors:material:001',
            'source_id': 'hyrule-wiiu-catalog',
        }]
        with self.assertRaisesRegex(ValueError, 'relationship source claim scope'):
            validate_dataset(wrong_relationship_source)

    def test_v1_legacy_sources_may_omit_game_ids_and_claim_scopes(self):
        legacy = deepcopy(self.dataset)
        for source in legacy['sources']:
            if 'claim_scopes' not in source:
                source.pop('game_ids', None)
        self.assertEqual(validate_dataset(legacy), legacy)

    def test_validator_enforces_dataset_license_consistency(self):
        mixed_claim = deepcopy(self.dataset)
        mixed_claim['dataset_license'] = 'MIT'
        with self.assertRaisesRegex(ValueError, 'Mixed source licenses require'):
            validate_dataset(mixed_claim)

        wrong_uniform_claim = deepcopy(self.dataset)
        wrong_uniform_claim['dataset_license'] = 'CC BY-SA 3.0'
        for source in wrong_uniform_claim['sources']:
            source['license'] = 'MIT'
            source['license_uri'] = 'https://opensource.org/license/mit'
        with self.assertRaisesRegex(ValueError, 'must match every source license'):
            validate_dataset(wrong_uniform_claim)

    def test_validator_rejects_noncanonical_license_uri(self):
        wrong_uri = deepcopy(self.dataset)
        source = next(source for source in wrong_uri['sources'] if source['id'] == 'hyrule-wiiu-catalog')
        source['license_uri'] = 'https://creativecommons.org/licenses/by-sa/3.0/'
        with self.assertRaisesRegex(ValueError, 'license or URL is not allowed'):
            validate_dataset(wrong_uri)

    def test_validator_requires_claim_scoped_sources_to_declare_game_ids(self):
        missing_scope_ids = deepcopy(self.dataset)
        source = next(
            source for source in missing_scope_ids['sources']
            if source['id'] == 'hyrule-wiiu-catalog'
        )
        del source['game_ids']
        with self.assertRaisesRegex(ValueError, 'must declare applicable game IDs'):
            validate_dataset(missing_scope_ids)

    def test_validator_rejects_unknown_or_mismatched_registry_profiles(self):
        for field, value in (
            ('title', 'Hyrule Warriors'),
            ('edition', 'Wii U'),
            ('platform', 'Nintendo Switch'),
        ):
            with self.subTest(profile_field=field):
                mismatch = deepcopy(self.dataset)
                hyrule_profile = next(game for game in mismatch['games'] if game['id'] == 'hyrule_warriors')
                hyrule_profile[field] = value
                with self.assertRaisesRegex(ValueError, 'mismatches the registry'):
                    validate_dataset(mismatch)

        unknown_profile = deepcopy(self.dataset)
        three_hopes = next(game for game in unknown_profile['games'] if game['id'] == 'three_hopes')
        three_hopes['id'] = 'unregistered_profile'
        for source in unknown_profile['sources']:
            if source['id'] in {'local-profile-registry', 'few2-binary-templates'}:
                source.pop('game_ids', None)
        with self.assertRaisesRegex(ValueError, 'profile is not registered'):
            validate_dataset(unknown_profile)

    def test_validator_requires_strict_iso_access_dates(self):
        for invalid_date in ('20261022', '2026-2-02', '2026-02-30'):
            with self.subTest(accessed_on=invalid_date):
                invalid = deepcopy(self.dataset)
                wiki_source = next(
                    source for source in invalid['sources']
                    if source['id'] == 'koeitecmo-wiki-weapon-skills'
                )
                wiki_source['accessed_on'] = invalid_date
                with self.assertRaisesRegex(ValueError, 'ISO YYYY-MM-DD'):
                    validate_dataset(invalid)

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
        hyrule_entity = next(
            entity for entity in cross_edition['entities']
            if entity['game_id'] == 'hyrule_warriors'
        )
        hyrule_entity['relationships'] = [{
            'type': 'related-to',
            'entity_id': 'three_hopes:character:000',
            'source_id': 'koeitecmo-wiki-adventure-mode',
        }]
        relation_source = next(
            source for source in cross_edition['sources']
            if source['id'] == 'koeitecmo-wiki-adventure-mode'
        )
        relation_source['claim_scopes'].append('entity.relationships')
        with self.assertRaisesRegex(ValueError, 'crosses game editions'):
            validate_dataset(cross_edition)

    def test_validator_rejects_edition_mismatch(self):
        mismatch = deepcopy(self.dataset)
        mismatch['entities'][0]['edition'] = 'Nintendo Switch'
        with self.assertRaisesRegex(ValueError, 'mismatched edition'):
            validate_dataset(mismatch)


if __name__ == '__main__':
    unittest.main()

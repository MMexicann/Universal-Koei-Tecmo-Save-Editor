"""Index lifetime and search semantics for reusable library snapshots."""
from dataclasses import replace
from unittest import TestCase, mock

from koei_editor.game_registry import GAMES
from koei_editor.shared import library_catalog as catalog


class LibraryCatalogIndexTests(TestCase):
    def test_reuse_does_not_normalize_metadata_or_resort(self):
        index = catalog.LibraryCatalog(reversed(GAMES))
        with mock.patch.object(catalog, 'normalized', wraps=catalog.normalized) as normalize:
            self.assertEqual([g.id for g in index.matching_games('DW7 PC')], ['dw7xl'])
            self.assertEqual([g.id for g in index.matching_games('sóphie 2', 'Windows PC')],
                             ['atelier_sophie2'])
            self.assertEqual(normalize.call_args_list, [mock.call('DW7 PC'), mock.call('sóphie 2')])

    def test_generator_snapshot_preserves_original_objects_and_alphabetical_order(self):
        source = [replace(GAMES[0], id='z', title='Zulu'),
                  replace(GAMES[0], id='b', title='Álpha', subtitle='Second'),
                  replace(GAMES[0], id='a', title='Alpha', subtitle='First')]
        index = catalog.LibraryCatalog(game for game in source)
        source.clear()
        self.assertEqual([g.id for g in index.matching_games()], ['a', 'b', 'z'])
        self.assertEqual(index.matching_games(), catalog.matching_games(index))

    def test_combined_filters_and_rebuild_for_changed_registry(self):
        index = catalog.LibraryCatalog(GAMES)
        self.assertEqual([g.id for g in index.matching_games('horse', 'Windows PC',
                                                          'Dynasty Warriors')], ['dw6', 'dw8e'])
        self.assertFalse(index.matching_games('not an existing title'))
        self.assertFalse(index.matching_games('horse', 'PlayStation Vita', 'Dynasty Warriors'))
        addition = replace(GAMES[0], id='example_plugin', title='Example extension')
        updated = catalog.LibraryCatalog((*GAMES, addition))
        self.assertFalse(index.matching_games('example extension'))
        self.assertIs(updated.matching_games('example extension')[0], addition)

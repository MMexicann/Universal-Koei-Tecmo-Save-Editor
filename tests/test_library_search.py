"""Exercise finding and opening real library entries without losing sessions."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from koei_editor.application import Application
from koei_editor.game_registry import GAMES
from koei_editor.shared.library_catalog import ALL_PLATFORMS, ALL_SERIES, matching_games


class CatalogSearchTests(unittest.TestCase):
    def test_short_name_and_platform_disambiguate_editions(self):
        self.assertEqual([game.id for game in matching_games(GAMES, 'dw7')],
                         ['dw7_ps3', 'dw7xl', 'dw7e_ps3'])
        self.assertEqual([game.id for game in matching_games(GAMES, 'dw7 pc')], ['dw7xl'])
        self.assertEqual([game.id for game in matching_games(GAMES, 'sóphie 2')], ['atelier_sophie2'])

    def test_filters_combine_and_features_are_searchable(self):
        games = matching_games(GAMES, 'horse', 'Windows PC', 'Dynasty Warriors')
        self.assertEqual([game.id for game in games], ['dw6', 'dw8e'])
        self.assertFalse(matching_games(GAMES, 'hyrule', 'Windows PC'))
        self.assertEqual({game.id for game in matching_games(GAMES, 'hyrule')},
                         {'hyrule_warriors', 'hyrule_definitive', 'hyrule_legends', 'age_of_calamity'})
        self.assertFalse(matching_games(GAMES, 'game that does not exist'))

    def test_meruru_plus_vita_does_not_advertise_unqualified_dx_pc(self):
        self.assertEqual([game.id for game in matching_games(GAMES, 'meruru vita')],
                         ['meruru_plus_vita'])
        self.assertFalse(matching_games(GAMES, 'meruru', 'Windows PC'))
        self.assertEqual([game.id for game in matching_games(GAMES, 'base stats',
                                                             'PlayStation Vita', 'Atelier')],
                         ['meruru_plus_vita'])


    def test_new_native_profiles_are_exact_and_searchable(self):
        self.assertEqual([g.id for g in matching_games(GAMES, 'berserk vita')], ['berserk_vita'])
        self.assertFalse(matching_games(GAMES, 'berserk', 'Windows PC'))
        self.assertEqual([g.id for g in matching_games(GAMES, 'dead or alive', 'PlayStation 3')], ['doa5_ps3'])
        self.assertFalse(matching_games(GAMES, 'dead or alive ultimate'))
        self.assertEqual([g.id for g in matching_games(GAMES, 'pokemon', 'Nintendo DS')], ['pokemon_conquest_ds'])


class LibrarySearchGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.directory = tempfile.TemporaryDirectory()
        self.app = Application(self.root, preferences_path=Path(self.directory.name) / 'prefs.json',
                               persist_preferences=False)
        self.root.geometry('1080x820')
        self.root.update()

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()
            self.directory.cleanup()

    def test_cross_platform_search_and_enter_retain_existing_session(self):
        editor = self.app.select_game('dw7xl')
        self.app.show_library()
        self.assertEqual(self.app.game_buttons['dw7xl'].cget('text'), 'Resume Editor')
        self.app.focus_library_search()
        self.app.library_search.set('dw7 pc')
        self.root.update()
        self.assertEqual(self.app.platform_choice.get(), ALL_PLATFORMS)
        self.assertEqual([game.id for game in self.app.library_matches], ['dw7xl'])
        self.assertTrue(self.app.library_buttons[ALL_PLATFORMS]['dw7xl'].winfo_ismapped())
        self.assertFalse(self.app.library_buttons[ALL_PLATFORMS]['dw7_ps3'].winfo_ismapped())
        self.app.open_library_match()
        self.assertIs(self.app.sessions['dw7xl'][1], editor)
        self.assertEqual(self.app.active_game, 'dw7xl')

    def test_no_match_clear_filters_and_compact_toggle(self):
        self.assertFalse(self.app.compact_library.get())
        self.assertTrue(self.app.library_banners['Windows PC']['dw7xl'].winfo_ismapped())
        self.app.series_choice.set('Hyrule Warriors')
        self.app.platform_choice.set(ALL_PLATFORMS)
        self.app.library_search.set('no matching title')
        self.root.update()
        self.assertTrue(self.app.library_empty[ALL_PLATFORMS].winfo_ismapped())
        self.app.open_library_match()
        self.assertIsNone(self.app.active_game)
        self.app.clear_library_filters()
        self.root.update()
        self.assertEqual(self.app.series_choice.get(), ALL_SERIES)
        self.assertEqual(len(self.app.library_matches), len(GAMES))
        self.assertFalse(self.app.library_empty[ALL_PLATFORMS].winfo_ismapped())
        self.assertTrue(self.app.library_banners[ALL_PLATFORMS]['dw7xl'].winfo_ismapped())
        editor = self.app.select_game('dw7xl')
        self.app.show_library()
        self.app.platform_choice.set(ALL_PLATFORMS)
        self.app.show_platform()
        for theme in ('Light', 'Dark'):
            with self.subTest(theme=theme):
                self.app.apply_theme(theme)
                for compact in (True, False):
                    self.app.compact_toggle.invoke()
                    self.root.update()
                    self.assertEqual(self.app.compact_library.get(), compact)
                    self.assertEqual(len(self.app.library_matches), len(GAMES))
                    self.assertIs(self.app.sessions['dw7xl'][1], editor)
                    self.assertEqual(self.app.library_buttons[ALL_PLATFORMS]['dw7xl'].cget('text'),
                                     'Resume Editor')
                    self.assertTrue(self.app.compact_toggle.winfo_ismapped())
                    self.assertGreaterEqual(self.app.compact_toggle.winfo_rootx(), self.root.winfo_rootx())
                    self.assertLessEqual(self.app.compact_toggle.winfo_rootx() + self.app.compact_toggle.winfo_width(),
                                         self.root.winfo_rootx() + self.root.winfo_width())
                    self.assertGreaterEqual(self.app.compact_toggle.winfo_rooty(), self.root.winfo_rooty())
                    self.assertLessEqual(self.app.compact_toggle.winfo_rooty() + self.app.compact_toggle.winfo_height(),
                                         self.root.winfo_rooty() + self.root.winfo_height())
                    self.assertTrue(self.app.contact_button.winfo_ismapped())
                    for scope in ('Windows PC', ALL_PLATFORMS):
                        banner = self.app.library_banners[scope]['dw7xl']
                        self.assertEqual(banner.winfo_manager(), '' if compact else 'pack')
                self.app.library_search.set('dw7 pc')
                self.root.update()
                self.app.compact_toggle.invoke()
                self.root.update()
                self.assertEqual(self.app.library_search.get(), 'dw7 pc')
                self.assertEqual([game.id for game in self.app.library_matches], ['dw7xl'])
                self.assertTrue(self.app.library_buttons[ALL_PLATFORMS]['dw7xl'].winfo_ismapped())
                self.app.compact_toggle.invoke()
                self.app.clear_library_filters()
                self.root.update()

    def test_vita_platform_filter_opens_bound_editor_and_resumes_session(self):
        self.app.platform_choice.set('PlayStation Vita')
        self.app.series_choice.set('Atelier')
        self.app.library_search.set('meruru')
        self.root.update()
        self.assertEqual([game.id for game in self.app.library_matches], ['meruru_plus_vita'])
        self.app.open_library_match()
        self.root.update()
        self.assertEqual(self.app.active_game, 'meruru_plus_vita')
        editor = self.app.sessions['meruru_plus_vita'][1]
        self.assertEqual(editor.save_extension, '')
        self.assertEqual(editor.adapter.game_id, 'meruru_plus_vita')
        self.app.show_library()
        self.root.update()
        self.app.open_library_match()
        self.assertIs(self.app.sessions['meruru_plus_vita'][1], editor)


    def test_ds_platform_opens_bound_editor_and_resumes_session(self):
        self.app.platform_choice.set('Nintendo DS')
        self.app.library_search.set('pokemon')
        self.root.update()
        self.assertEqual([g.id for g in self.app.library_matches], ['pokemon_conquest_ds'])
        self.app.open_library_match()
        self.root.update()
        editor = self.app.sessions['pokemon_conquest_ds'][1]
        self.assertEqual(self.app.active_game, 'pokemon_conquest_ds')
        self.assertEqual(editor.save_extension, '.sav')
        self.assertEqual(editor.adapter.game_id, 'pokemon_conquest_ds')
        self.app.show_library()
        self.root.update()
        self.app.open_library_match()
        self.assertIs(self.app.sessions['pokemon_conquest_ds'][1], editor)


if __name__ == '__main__':
    unittest.main()

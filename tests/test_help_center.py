import sys
import tkinter as tk
import unittest

from koei_editor.game_registry import GAMES
from koei_editor.shared.compatibility_center import compatibility_entries, search_compatibility
from koei_editor.shared.help_content import help_articles, search_articles, preparation_guide


class CompatibilityTests(unittest.TestCase):
    def test_inventory_is_exact_and_does_not_load_parsers(self):
        before = set(sys.modules)
        entries = compatibility_entries()
        self.assertEqual({entry.game_id for entry in entries}, {game.id for game in GAMES})
        self.assertEqual(len(entries), len(GAMES))
        self.assertFalse(any(name.endswith('.parser') for name in set(sys.modules) - before))
        for entry, game in zip(entries, GAMES):
            self.assertEqual(entry.revision_scope, game.subtitle)
            self.assertEqual(entry.platform, game.platform)
            self.assertEqual(entry.functionality, game.description)
            self.assertIn('No game-load', entry.game_validation)

    def test_search_combines_platform_revision_and_functionality(self):
        entries = compatibility_entries()
        results = search_compatibility(entries, 'DW7 seal', 'Windows PC')
        self.assertEqual([entry.game_id for entry in results], ['dw7xl'])
        self.assertFalse(search_compatibility(entries, 'DW7 seal', 'NES'))
        self.assertTrue(search_compatibility(entries, 'Pokémon', 'Nintendo DS'))
        self.assertFalse(search_compatibility(entries, 'zznomatchingprofilezz'))

    def test_help_translation_and_search(self):
        english, german = help_articles(), help_articles('de')
        self.assertEqual([article.id for article in english], [article.id for article in german])
        self.assertTrue(all(en.body != de.body for en, de in zip(english, german)))
        self.assertTrue(search_articles(english, 'companion rejected'))
        self.assertTrue(search_articles(german, 'Tastaturbedienung'))
        self.assertFalse(search_articles(english, 'unknown nonexistent query'))

    def test_platform_guides_preserve_console_context_and_external_signing(self):
        self.assertIn('PARAM.SFO', preparation_guide('PlayStation 3'))
        self.assertIn('PSU', preparation_guide('PlayStation 2'))
        self.assertIn('EEPROM', preparation_guide('Original Xbox'))
        self.assertIn('raw battery SRAM', preparation_guide('Nintendo DS'))
        self.assertIn('Steam/cloud', preparation_guide('Windows PC'))
        for platform in {game.platform for game in GAMES}:
            for language in ('en', 'de'):
                guide = preparation_guide(platform, language)
                self.assertIn('1.', guide)
                self.assertIn('6.', guide)


class HelpCenterGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.geometry('1000x780')
        from koei_editor.shared.help_center import HelpCenter
        self.center = HelpCenter(self.root, self.root)
        self.center.frame.pack(fill='both', expand=True)
        self.root.update()

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()

    def test_matrix_keyboard_search_and_help_empty_state(self):
        self.center.show_tab('compatibility')
        self.center.compatibility_query.set('dw7 seal')
        self.root.update()
        self.assertIn('dw7xl', self.center.matrix.get_children())
        self.center.platform.set('NES')
        self.center._filter_compatibility()
        self.assertFalse(self.center.matrix.get_children())
        self.assertIn('No matching', self.center.compatibility_detail.get('1.0', 'end'))
        self.center.show_tab('help')
        self.center.help_query.set('nonexistent topic')
        self.assertIn('No matching', self.center.article_detail.get('1.0', 'end'))
        self.center.help_query.set('field explanations')
        self.assertEqual(self.center.article_list.get_children(), ('fields',))

    def test_guides_and_theme_preserve_selection(self):
        from koei_editor.shared.appearance import THEMES
        self.center.show_tab('workflows')
        self.center.guide_platform.set('PlayStation Vita')
        self.center._show_guide()
        self.center.apply_theme(THEMES['Dark'])
        self.assertIn('param.sfo', self.center.guide_detail.get('1.0', 'end'))
        self.assertEqual(self.center.guide_platform.get(), 'PlayStation Vita')
        self.assertFalse(self.center._panels)

    def test_versions_tab_loads_tracker_lazily_and_preserves_language_search(self):
        self.assertNotIn('versions', self.center._panels)
        self.center.show_tab('versions')
        panel = self.center._panels['versions']
        self.assertEqual(panel._scan_thread, None)
        self.assertIsNotNone(panel.search_entry)

        self.center.set_language('de')
        self.assertEqual(panel.language, 'de')
        self.assertEqual(panel.search_label.cget('text'), 'Installierte Spiele filtern')
        self.center.focus_search()
        self.root.update()
        self.assertEqual(self.root.focus_get(), panel.search_entry)


if __name__ == '__main__':
    unittest.main()

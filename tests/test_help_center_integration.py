"""Independent shell-center checks across validation, themes and plugin approvals."""
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from koei_editor.game_registry import GAMES
from koei_editor.shared.appearance import THEMES


def integration_manifest():
    """Inert test content; no scripts, game files or private diagnostics."""
    return {
        'schema': 1, 'api': '1', 'id': 'community.integration',
        'title': 'Integration guidance', 'version': '1.0.0',
        'author': 'Test contributor', 'description': 'Declarative integration test.',
        'capabilities': ['help', 'commands', 'workflows'],
        'contributions': [
            {'kind': 'help', 'id': 'english-help', 'title': 'Controlled EN guidance',
             'locale': 'en', 'game_ids': ['dw8xl'], 'body': 'EnglishCommunityMarker original-copy guidance.'},
            {'kind': 'commands', 'id': 'english-command', 'title': 'Show EN guidance',
             'locale': 'en', 'game_ids': ['dw8xl'], 'target': 'english-help'},
            {'kind': 'help', 'id': 'german-help', 'title': 'Kontrollierte DE Anleitung',
             'locale': 'de', 'game_ids': ['dw8xl'], 'body': 'DeutscherCommunityMarker Kopie behalten.'},
            {'kind': 'commands', 'id': 'german-command', 'title': 'DE Anleitung zeigen',
             'locale': 'de', 'game_ids': ['dw8xl'], 'target': 'german-help'},
            {'kind': 'workflows', 'id': 'english-workflow', 'title': 'EN preparation steps',
             'locale': 'en', 'game_ids': ['dw8xl'], 'platforms': ['Windows PC'],
             'steps': ['EnglishWorkflowMarker: preserve an original copy.', 'Review one controlled change.']},
        ],
    }


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class HelpCenterIntegrationTests(unittest.TestCase):
    def setUp(self):
        from koei_editor.shared.help_center import HelpCenter
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.center = HelpCenter(self.root, self.root)
        self.center.frame.pack(fill='both', expand=True)
        self.root.update()

    def open_plugin_directory(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        manifest_path = Path(temporary.name) / 'integration.plugin.json'
        manifest_path.write_text(json.dumps(integration_manifest()), encoding='utf-8')
        self.center.show_tab('plugins')
        panel = self.center._panels['plugins']
        self.assertTrue(panel.load_directory(temporary.name))
        self.assertEqual(len(panel.catalog.entries), 1)
        self.assertFalse(panel.catalog.entries[0].error)
        return panel

    @staticmethod
    def approve(panel):
        panel.reviewed.set(True)
        panel.enable_selected()

    def test_optional_tabs_are_lazy_and_late_validation_receives_theme(self):
        self.assertEqual(self.center._panels, {})
        self.center.apply_theme(THEMES['Dark'])
        self.center.show_tab('validation')
        self.assertEqual(set(self.center._panels), {'validation'})
        validation = self.center._panels['validation']
        self.assertEqual(validation.preview.cget('background'), THEMES['Dark']['surface'])
        self.assertFalse(validation.record.summary()['independently_verified'])
        self.center.show_tab('validation')
        self.assertIs(self.center._panels['validation'], validation)
        self.center.show_tab('feedback')
        self.assertEqual(set(self.center._panels), {'validation', 'feedback'})
        feedback = self.center._panels['feedback']
        self.assertEqual(feedback.preview.cget('foreground'), THEMES['Dark']['text'])
        self.assertEqual(feedback.report['transmission'], 'local_review_only')
        self.assertEqual(feedback.report['diagnostics'], {})

    def test_center_language_change_preserves_workflow_pending_choices_and_palette(self):
        self.center.show_tab('validation')
        panel = self.center._panels['validation']
        panel.revision.set('0x10')
        panel.provenance.set(panel.text['sources'][2])
        panel.record = panel.record.record_step('prepare_copy', 'passed')
        panel.step.set(panel.text['steps'][1])
        panel.outcome.set(panel.text['outcomes'][2])
        record = panel.record
        scope = record.to_dict()['profile_scope']
        self.center.apply_theme(THEMES['Dark'])
        self.center.set_language('de')
        self.assertIs(self.center._panels['validation'], panel)
        self.assertIs(panel.record, record)
        self.assertEqual(panel.record.to_dict()['profile_scope'], scope)
        self.assertEqual(panel.language, 'de')
        self.assertEqual(panel.revision.get(), '0x10')
        self.assertEqual(panel.step.get(), panel.text['steps'][1])
        self.assertEqual(panel.outcome.get(), panel.text['outcomes'][2])
        self.assertEqual(panel.preview.cget('background'), THEMES['Dark']['surface'])
        self.assertEqual(self.center.notebook.tab(self.center.tabs['validation'], 'text'), 'Validierung')
        self.center.show_tab('feedback')
        self.assertEqual(self.center._panels['feedback'].report['locale'], 'de')
        self.center.set_language('en')
        self.assertIs(panel.record, record)
        self.assertEqual(self.center._panels['feedback'].report['locale'], 'en')

    def test_plugin_discovery_is_inert_until_review_then_disable_revokes_every_surface(self):
        inventory = tuple(GAMES)
        entries = self.center.entries
        panel = self.open_plugin_directory()
        self.assertEqual(self.center.plugin_commands(), ())
        self.assertFalse(any(a.id.startswith('community.integration:') for a in self.center.articles))
        self.assertFalse(self.center.open_plugin_command('community.integration:english-command'))
        self.approve(panel)
        commands = self.center.plugin_commands()
        self.assertEqual([item[0] for item in commands], ['community.integration:english-command'])
        self.center.help_query.set('EnglishCommunityMarker')
        self.assertEqual(self.center.article_list.get_children(), ('community.integration:english-help',))
        self.assertIn('Community plugin', self.center.article_detail.get('1.0', 'end'))
        self.center.guide_platform.set('Windows PC')
        self.center._show_guide()
        self.assertIn('EnglishWorkflowMarker', self.center.guide_detail.get('1.0', 'end'))
        self.assertTrue(self.center.open_plugin_command(commands[0][0]))
        self.assertIn('EnglishCommunityMarker', panel.preview.get('1.0', 'end'))
        panel.tree.selection_set('0')
        panel._select()
        panel.disable_selected()
        self.assertEqual(self.center.plugin_commands(), ())
        self.assertFalse(self.center.article_list.get_children())
        self.assertNotIn('EnglishWorkflowMarker', self.center.guide_detail.get('1.0', 'end'))
        self.assertFalse(self.center.open_plugin_command(commands[0][0]))
        self.assertEqual(tuple(GAMES), inventory)
        self.assertIs(self.center.entries, entries)

    def test_plugin_approval_survives_locale_change_and_filters_commands_by_language(self):
        panel = self.open_plugin_directory()
        self.approve(panel)
        candidate = panel.catalog.entries[0].candidate
        self.center.set_language('de')
        self.assertIs(self.center._panels['plugins'], panel)
        self.assertTrue(panel.catalog.entries[0].enabled)
        self.assertIs(panel.catalog.entries[0].candidate, candidate)
        self.assertEqual([item[0] for item in self.center.plugin_commands()],
                         ['community.integration:german-command'])
        self.center.help_query.set('DeutscherCommunityMarker')
        self.assertEqual(self.center.article_list.get_children(), ('community.integration:german-help',))
        self.assertFalse(self.center.open_plugin_command('community.integration:english-command'))
        self.assertTrue(self.center.open_plugin_command('community.integration:german-command'))
        self.assertIn('DeutscherCommunityMarker', panel.preview.get('1.0', 'end'))
        self.center.set_language('en')
        self.assertTrue(panel.catalog.entries[0].enabled)
        self.assertEqual([item[0] for item in self.center.plugin_commands()],
                         ['community.integration:english-command'])

    def test_plugin_enable_disable_cannot_reset_validation_or_promote_compatibility_evidence(self):
        self.center.show_tab('validation')
        validation = self.center._panels['validation']
        validation.provenance.set(validation.text['sources'][2])
        validation.record = validation.record.record_step('prepare_copy', 'passed')
        record = validation.record
        compatibility = self.center.entries
        panel = self.open_plugin_directory()
        self.approve(panel)
        self.assertIs(validation.record, record)
        self.assertIs(self.center.entries, compatibility)
        panel.disable_selected()
        self.assertIs(validation.record, record)
        self.assertIs(self.center.entries, compatibility)
        self.assertFalse(validation.record.summary()['game_load_reported'])


if __name__ == '__main__':
    unittest.main()

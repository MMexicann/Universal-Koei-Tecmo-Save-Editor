"""Real Tk interaction proves workflow resets, local report review and DE labels."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.shared.appearance import THEMES
from koei_editor.shared.validation_gui import FeedbackPanel, ValidationPanel
from koei_editor.shared.validation_toolkit import STEPS, ValidationRecord


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class ValidationGuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def test_notebook_locale_changes_preserve_tab_position_options_selection_and_state(self):
        for panel_type in (ValidationPanel, FeedbackPanel):
            with self.subTest(panel=panel_type.__name__):
                notebook = ttk.Notebook(self.root)
                notebook.pack()
                first = ttk.Frame(notebook)
                notebook.add(first, text='First')
                panel = panel_type(self.root, notebook)
                notebook.add(panel.frame, text='Toolkit', padding=6, sticky='nsew')
                notebook.select(panel.frame)
                padding = notebook.tab(panel.frame, 'padding')
                if panel_type is ValidationPanel:
                    panel.revision.set('15')
                    panel.provenance.set(panel.text['sources'][2])
                    panel.record = panel.record.record_step(STEPS[0], 'passed')
                    expected = panel.record
                else:
                    panel.category.set(panel.text['categories'][3])
                    expected = panel.report['category']
                for language in ('de', 'en'):
                    previous = panel.frame
                    panel.set_language(language)
                    self.assertEqual(len(notebook.tabs()), 2)
                    self.assertEqual(notebook.index(panel.frame), 1)
                    self.assertEqual(notebook.select(), str(panel.frame))
                    self.assertEqual(notebook.tab(panel.frame, 'text'), 'Toolkit')
                    self.assertEqual(notebook.tab(panel.frame, 'padding'), padding)
                    self.assertFalse(previous.winfo_exists())
                    if panel_type is ValidationPanel:
                        self.assertEqual(panel.record, expected)
                    else:
                        self.assertEqual(panel.report['category'], expected)
                notebook.destroy()

    def test_out_of_order_click_shows_generic_error_and_keeps_report_unverified(self):
        panel = ValidationPanel(self.root, self.root)
        panel.step.set(panel.text['steps'][5])
        panel.outcome.set(panel.text['outcomes'][1])
        with patch('koei_editor.shared.validation_gui.messagebox.showerror') as error:
            panel.record_outcome()
        error.assert_called_once()
        self.assertEqual(set(panel.record.outcomes), {'not_run'})
        self.assertIn('user_reported_unverified', panel.preview.get('1.0', 'end'))

    def test_profile_revision_and_source_changes_clear_downstream_observations(self):
        panel = ValidationPanel(self.root, self.root)
        for variable, value in ((panel.revision, '15'),
                                (panel.provenance, panel.text['sources'][2]),
                                (panel.game, list(panel._games)[1])):
            panel.record = ValidationRecord.create(panel._games[panel.game.get()], provenance='genuine_file')
            for step in STEPS:
                panel.record = panel.record.record_step(step, 'passed')
            variable.set(value)
            self.assertEqual(set(panel.record.outcomes), {'not_run'})

    def test_invalid_revision_discards_previous_preview_and_cannot_export(self):
        panel = ValidationPanel(self.root, self.root)
        panel.revision.set('/private/example/secret.sav')
        self.assertIsNone(panel.record)
        self.assertEqual(panel.preview.get('1.0', 'end').strip(), '')
        self.assertNotIn('alice', panel.status.get())
        with patch('koei_editor.shared.validation_gui.messagebox.showerror'), \
                patch('koei_editor.shared.validation_gui.filedialog.asksaveasfilename') as dialog:
            panel.export()
        dialog.assert_not_called()

    def test_hex_revision_and_german_guidance_and_dark_theme(self):
        panel = ValidationPanel(self.root, self.root, language='de')
        panel.revision.set('0x01040000')
        self.assertEqual(panel.record.revision, 0x01040000)
        self.assertEqual(panel.text['title'], 'Validierung im Spiel')
        panel.step.set(panel.text['steps'][4])
        self.assertIn('Begleitdateien', panel.guidance.get())
        panel.apply_theme(THEMES['Dark'])
        self.assertEqual(panel.preview.cget('background'), THEMES['Dark']['surface'])

    def test_cancelled_import_and_export_do_not_change_report(self):
        panel = ValidationPanel(self.root, self.root)
        record = panel.record
        with patch('koei_editor.shared.validation_gui.filedialog.askopenfilename', return_value=''):
            panel.load()
        with patch('koei_editor.shared.validation_gui.filedialog.asksaveasfilename', return_value=''):
            panel.export()
        self.assertIs(panel.record, record)

    def test_import_preview_export_and_existing_destination_preservation(self):
        panel = ValidationPanel(self.root, self.root, language='de')
        record = ValidationRecord.create('dw8xl', revision=15, provenance='genuine_file')
        record = record.record_step('prepare_copy', 'passed')
        with tempfile.TemporaryDirectory() as folder:
            source, destination = Path(folder) / 'input.json', Path(folder) / 'output.json'
            record.export(source)
            with patch('koei_editor.shared.validation_gui.filedialog.askopenfilename', return_value=str(source)):
                panel.load()
            self.assertEqual(panel.record, record)
            self.assertIn('"format_revision": 15', panel.preview.get('1.0', 'end'))
            with patch('koei_editor.shared.validation_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                panel.export()
                self.assertEqual(ValidationRecord.load(destination), record)
                with patch('koei_editor.shared.validation_gui.messagebox.showerror') as error:
                    panel.export()
                error.assert_called_once()
            self.assertEqual(ValidationRecord.load(destination), record)

    def test_feedback_preview_updates_before_local_export_and_has_no_paths(self):
        panel = FeedbackPanel(self.root, self.root, language='de')
        panel.category.set(panel.text['categories'][3])
        panel.game.set(list(panel._games)[1])
        self.assertEqual(panel.report['category'], 'compatibility')
        self.assertEqual(panel.report['locale'], 'de')
        preview = panel.preview.get('1.0', 'end')
        self.assertIn('local_review_only', preview)
        self.assertIn('compatibility', preview)
        self.assertEqual(panel.report['diagnostics'], {})
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'feedback.json'
            with patch('koei_editor.shared.validation_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                panel.export()
            self.assertEqual(destination.read_text(encoding='utf-8'), preview.rstrip() + '\n')
            self.assertNotIn(folder, destination.read_text(encoding='utf-8'))

    def test_runtime_locale_change_preserves_incomplete_workflow_and_layout(self):
        panel = ValidationPanel(self.root, self.root)
        panel.frame.pack(fill='both', expand=True)
        panel.revision.set('0x10')
        panel.provenance.set(panel.text['sources'][2])
        panel.record = panel.record.record_step('prepare_copy', 'passed')
        panel.step.set(panel.text['steps'][1])
        panel.outcome.set(panel.text['outcomes'][2])  # Unsubmitted choice also survives.
        record = panel.record
        panel.apply_theme(THEMES['Dark'])
        old_frame = panel.frame
        panel.set_language('de')
        self.assertFalse(old_frame.winfo_exists())
        self.assertIs(panel.record, record)
        self.assertEqual(panel.revision.get(), '0x10')
        self.assertEqual(panel.provenance.get(), panel.text['sources'][2])
        self.assertEqual(panel.step.get(), panel.text['steps'][1])
        self.assertEqual(panel.outcome.get(), panel.text['outcomes'][2])
        self.assertEqual(panel.frame.winfo_manager(), 'pack')
        self.assertEqual(panel.preview.cget('background'), THEMES['Dark']['surface'])
        self.assertEqual(panel.text['title'], 'Validierung im Spiel')
        panel.set_language('en')
        self.assertIs(panel.record, record)
        self.assertEqual(panel.text['title'], 'Real-game validation')

    def test_runtime_feedback_locale_change_preserves_controlled_choices(self):
        panel = FeedbackPanel(self.root, self.root)
        panel.frame.grid(row=0, column=0, sticky='nsew')
        panel.game.set(list(panel._games)[1])
        panel.category.set(panel.text['categories'][3])
        panel.error_code.set(panel.text['errors'][2])
        game_id = panel.report['game_id']
        panel.set_language('de')
        self.assertEqual(panel.report['game_id'], game_id)
        self.assertEqual(panel.report['category'], 'compatibility')
        self.assertEqual(panel.report['error_code'], 'operation_failed')
        self.assertEqual(panel.report['locale'], 'de')
        self.assertEqual(panel.frame.winfo_manager(), 'grid')
        self.assertEqual(panel.category.get(), 'Kompatibilität')


if __name__ == '__main__':
    unittest.main()

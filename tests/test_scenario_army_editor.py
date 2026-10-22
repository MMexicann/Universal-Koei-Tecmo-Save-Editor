"""Shared-editor integration for opt-in, display-only strategy tables."""
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import call, patch

from koei_editor.games.dw8xl.dw8xl_editor import Editor as DW8XLEditor
from koei_editor.games.nobunaga_ambition_nes.editor import Editor as NobunagaEditor
from koei_editor.shared.scalar_presentation import InspectionTable
from tests.test_nobunaga_ambition_nes import procedural_raw


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class ScenarioArmyEditorIntegrationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def make_editor(self, editor_type):
        host = ttk.Frame(self.root)
        host.pack(fill='both', expand=True)
        return editor_type(self.root, parent=host)

    def test_scenario_view_is_opt_in_and_renders_presentation_tables_read_only(self):
        strategy = self.make_editor(NobunagaEditor)
        self.assertIsNotNone(strategy.scenario_view)
        strategy_tabs = tuple(strategy.workspace_tabs.tab(tab, 'text')
                              for tab in strategy.workspace_tabs.tabs())
        self.assertIn('Scenario View', strategy_tabs)

        ordinary = self.make_editor(DW8XLEditor)
        self.assertIsNone(ordinary.scenario_view)
        ordinary_tabs = tuple(ordinary.workspace_tabs.tab(tab, 'text')
                              for tab in ordinary.workspace_tabs.tabs())
        self.assertNotIn('Scenario View', ordinary_tabs)

        # Use a procedural copy only to exercise the shared display pipeline;
        # this test makes no claims about game load or unsupported writes.
        first_document = strategy.adapter.decode(procedural_raw())
        replacement_document = strategy.adapter.decode(procedural_raw())
        strategy.document = first_document
        provided = (InspectionTable(
            'Provided records', ('Region', 'Stored value'), (('Test region', 7),),
            'Read-only table supplied by the presentation.'),)
        replacement = (InspectionTable(
            'Replacement records', ('Region', 'Stored value'), (('Another region', 12),),
            'Refreshed from the replacement document.'),)
        with patch.object(strategy.presentation, 'inspection_tables',
                          side_effect=(provided, replacement)) as inspection_tables:
            strategy.refresh()

            view = strategy.scenario_view
            self.assertEqual(view.sections, ('Provided records',))
            self.assertEqual(len(view.cards), 1)
            self.assertEqual(view.cards[0].cget('text'), 'Record 1')
            rendered = {child.cget('text') for child in view.cards[0].winfo_children()
                        if isinstance(child, ttk.Label)}
            self.assertEqual(rendered, {'Region:', 'Test region', 'Stored value:', '7'})

            # The same immutable document is cached across redraws; a distinct
            # document identity requests a fresh projection and replaces cards.
            strategy.refresh()
            self.assertEqual(inspection_tables.call_args_list, [call(first_document)])
            strategy.document = replacement_document
            strategy.refresh()
            self.assertEqual(inspection_tables.call_args_list,
                             [call(first_document), call(replacement_document)])
            self.assertEqual(view.sections, ('Replacement records',))
            self.assertEqual(len(view.cards), 1)
            replacement_cells = {
                child.cget('text') for child in view.cards[0].winfo_children()
                if isinstance(child, ttk.Label)
            }
            self.assertEqual(replacement_cells,
                             {'Region:', 'Another region', 'Stored value:', '12'})

        self.assertEqual(strategy.changes, {})

        # The scenario view only exposes table selection and page navigation;
        # save editing remains available only through the separate editor tab.
        for callback in ('stage', 'stage_values', 'apply_selected', 'save_as', 'save_to'):
            self.assertFalse(callable(getattr(view, callback, None)), callback)
        self.assertFalse(hasattr(view, 'adapter'))
        button_labels = {widget.cget('text') for widget in descendants(view)
                         if isinstance(widget, ttk.Button)}
        self.assertEqual(button_labels, {'Previous', 'Next'})


if __name__ == '__main__':
    unittest.main()

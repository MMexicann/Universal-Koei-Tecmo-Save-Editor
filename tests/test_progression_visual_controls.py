"""Independent regressions for evidence-aware visual filtering and comparisons."""
from dataclasses import replace
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock

from koei_editor.shared.progression import (
    DashboardCard as Card, DashboardMetric as Metric,
    DashboardSection as Section, ProgressionDashboard as Dashboard,
)
from koei_editor.shared.progression_view import ProgressionView


def visual_snapshot():
    return Dashboard('Verified display', (Section('characters', 'Characters', (
        Card('unknown', 'Zulu', metrics=(Metric('xp', 'XP', '999999'),)),
        Card('complete', 'Bravo', metrics=(
            Metric('c', 'Mapped gallery', '10', current=10, total=10),)),
        Card('mixed', 'Alpha', metrics=(
            Metric('first', 'Mapped gallery', '10', current=10, total=10),
            Metric('second', 'Bond', '0', current=0, total=5),)),
        Card('partial', 'Delta', metrics=(
            Metric('p', 'Bond', '2', current=2, total=5),)),
        Card('unusual', 'Charlie', metrics=(
            Metric('u', 'Stored level', '101', current=101, total=100),)),
    )),), 'Only explicitly mapped ranges have denominators.')


class ProgressionVisualControlsTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.geometry('1180x820')
        self.navigate = Mock()
        self.original = visual_snapshot()
        self.view = ProgressionView(self.root, self.original, on_navigate=self.navigate)
        self.view.pack(fill='both', expand=True)
        self.root.update()

    def visible_ids(self):
        return tuple(card.id for card in self.view._filtered_cards)

    def test_completed_filter_requires_every_mapped_range_without_promoting_unknown_values(self):
        expected = {
            'With verified ranges': ('complete', 'mixed', 'partial'),
            'Ranges in progress': ('mixed', 'partial'),
            'Ranges complete': ('complete',),
            'No verified range': ('unknown', 'unusual'),
        }
        self.assertEqual(self.view._overview_counts, (5, 6, 4, 2))
        for choice, ids in expected.items():
            with self.subTest(choice=choice):
                self.view.range_filter.set(choice)
                self.assertEqual(self.visible_ids(), ids)
        self.assertFalse(self.view.canvas.find_withtag('progress-track'))
        self.assertEqual(self.original, visual_snapshot())
        self.navigate.assert_not_called()

    def test_numeric_sort_uses_valid_fraction_and_keeps_unknown_values_last_in_both_directions(self):
        self.view.sort_order.set('First range: low to high')
        self.assertEqual(self.visible_ids(), ('partial', 'complete', 'mixed', 'unknown', 'unusual'))
        self.view.sort_order.set('First range: high to low')
        self.assertEqual(self.visible_ids(), ('complete', 'mixed', 'partial', 'unknown', 'unusual'))
        self.view.sort_order.set('Name A–Z')
        self.assertEqual(self.visible_ids(), ('mixed', 'complete', 'unusual', 'partial', 'unknown'))
        self.view.sort_order.set('Original order')
        self.assertEqual(self.visible_ids(), ('unknown', 'complete', 'mixed', 'partial', 'unusual'))
        self.assertEqual(self.original, visual_snapshot())
        self.navigate.assert_not_called()

    def test_comparison_does_not_pair_ambiguous_labels_or_different_units(self):
        reference = Card('reference', 'Reference', metrics=(
            Metric('a', 'Attack', '10', unit='points'),
            Metric('b', 'Attack', '20', unit='points'),
            Metric('c', 'Health', '50', unit='points'),
            Metric('d', 'Level', '7'),
        ))
        selected = Card('selected', 'Selected', metrics=(
            Metric('e', 'Attack', '99', unit='points', field_id='attack'),
            Metric('f', 'Health', '5', unit='percent'),
            Metric('g', 'Level', '8', field_id='level'),
        ))
        self.view.set_dashboard(Dashboard('Comparison', (Section('s', 'Records', (reference, selected)),)))
        self.view.compare_button.invoke()
        self.view.select_card('selected')
        self.root.update()
        entries = self.view._comparison_entries
        self.assertEqual([entry.get() for entry in entries], [
            'Reference: no unique matching metric',
            'Reference: no unique matching metric',
            'Reference: 7',
        ])
        for entry in entries:
            self.assertTrue(entry.instate(['readonly']))
            before = entry.get()
            entry.delete(0, 'end')
            self.assertEqual(entry.get(), before)
        self.navigate.assert_not_called()
        self.view._metric_buttons[-1][1].invoke()
        self.navigate.assert_called_once_with('level')

    def test_replaced_snapshot_refreshes_pinned_values_and_drops_missing_reference(self):
        self.view.select_card('complete')
        self.view.compare_button.invoke()
        self.assertIs(self.view._pinned_card, self.original.sections[0].cards[1])
        updated = replace(self.original.sections[0].cards[1], metrics=(
            Metric('c', 'Mapped gallery', '3', current=3, total=10),))
        self.view.set_dashboard(Dashboard('Reopened snapshot', (
            Section('characters', 'Characters', (updated, self.original.sections[0].cards[2])),)))
        self.view.select_card('mixed')
        self.assertIs(self.view._pinned_card, updated)
        self.assertEqual(self.view._comparison_entries[0].get(), 'Reference: 3')
        self.view.set_dashboard(Dashboard('Empty snapshot'))
        self.assertIsNone(self.view._pinned_card)
        self.assertFalse(self.view._comparison_entries)
        self.navigate.assert_not_called()

    def test_comparison_and_navigation_remain_reachable_in_compact_application(self):
        from koei_editor.application import Application
        from tests.test_origins_parser import fixture
        self.view.destroy()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'copy.dat'
            raw = fixture()
            source.write_bytes(raw)
            app = Application(self.root, preferences_path=folder / 'prefs.json', persist_preferences=False)
            self.root.minsize(650, 500)
            editor = app.select_game('origins')
            self.assertTrue(editor.open_path(source))
            editor.stage_values({'gold': 4567})
            before = editor.changes, list(editor.history)
            editor.workspace_tabs.select(editor.dashboard_page)
            view = editor.dashboard_view
            view.section.set('characters')
            for theme in ('Light', 'Dark'):
                app.apply_theme(theme)
                self.root.geometry('800x650')
                self.root.update()
                view.compare_button.invoke()
                self.root.update()
                self.assertIsNotNone(view._pinned_card)
                self.assertTrue(view._comparison_entries)
                for control in (view.next, view.compare_button, view.detail_toggle):
                    with self.subTest(theme=theme, control=control):
                        self.assertTrue(control.winfo_viewable())
                        self.assertLessEqual(control.winfo_rooty() + control.winfo_height(),
                                             self.root.winfo_rooty() + 650)
                self.assertGreater(view.canvas.winfo_height(), 60)
                self.assertEqual((editor.changes, editor.history), before)
                view.compare_button.invoke()
                view.detail_toggle.invoke()
            self.assertEqual(source.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()

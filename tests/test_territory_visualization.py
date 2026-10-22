"""Read-only and paged record visualization tests."""
import tkinter as tk
from tkinter import ttk
import unittest

from koei_editor.shared.scalar_presentation import InspectionTable
from koei_editor.shared.territory_visualization import project_tables, project_table_page


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class TerritoryProjectionTests(unittest.TestCase):
    def test_projects_arbitrary_typed_tables_without_interpreting_columns(self):
        officers = InspectionTable(
            'Officers', ('Name', 'Loyalty', 'Unit configuration'),
            (('Zhou Yu', 97, 'Commander'), ('Sun Quan', 86, 'Ruler')),
            'Mapped officer fields from the opened record.',
        )
        cities = InspectionTable('Cities', ('City ID', 'Money', 'Supplies'), ((3, 12000, 600),))
        result = project_tables((officers, cities))

        self.assertEqual(tuple(table.title for table in result), ('Officers', 'Cities'))
        self.assertEqual(result[0].note, officers.note)
        self.assertIs(result[0].rows, officers.rows)
        page, = project_table_page(result[0], 0, page_size=1)
        self.assertEqual(page.title, 'Record 1')
        self.assertEqual(page.values, (('Name', 'Zhou Yu'), ('Loyalty', '97'),
                                       ('Unit configuration', 'Commander')))
        self.assertEqual(project_table_page(result[0], 1, page_size=1)[0].values[0],
                         ('Name', 'Sun Quan'))

    def test_empty_or_missing_tables_project_to_an_empty_state(self):
        self.assertEqual(project_tables(None), ())
        self.assertEqual(project_tables(()), ())
        self.assertEqual(project_tables((None, object())), ())
        empty = InspectionTable('Fiefs', ('Fief', 'Gold'), ())
        projected, = project_tables((empty,))
        self.assertEqual(project_table_page(projected, 0), ())

    def test_malformed_rows_are_rejected_and_duplicate_labels_remain_positional(self):
        broken_row = InspectionTable('Broken', ('Fief', 'Gold'), ((1,),))
        with self.assertRaisesRegex(ValueError, 'match its columns'):
            project_tables((broken_row,))
        duplicate_column = InspectionTable('Broken', ('Fief', 'Fief'), ((1, 2),))
        projected, = project_tables((duplicate_column,))
        record, = project_table_page(projected, 0)
        self.assertEqual(record.values, (('Fief', '1'), ('Fief', '2')))

    def test_page_bounds_and_types_are_validated(self):
        table = InspectionTable('Many', ('ID',), tuple((index,) for index in range(50)))
        projected, = project_tables((table,))
        self.assertEqual(len(project_table_page(projected, 0, page_size=24)), 24)
        self.assertEqual(len(project_table_page(projected, 2, page_size=24)), 2)
        with self.assertRaises(ValueError):
            project_table_page(projected, -1)


class TerritoryOverviewGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def test_table_selection_paging_theme_and_read_only_cards(self):
        from koei_editor.shared.territory_visualization import TerritoryOverview

        fiefs = InspectionTable(
            'Existing fiefs', ('Fief', 'Daimyo', 'Gold', 'Rice', 'Native policy'),
            tuple((index + 1, 'Oda', 12000 + index, 80 + index, index % 6)
                  for index in range(50)),
            'The row projection preserves native ownership and policy labels.',
        )
        officers = InspectionTable('Officers', ('Name', 'Role'), (('Nobunaga', 'Daimyo'),))
        view = TerritoryOverview(self.root, theme='Light')
        view.pack(fill='both', expand=True)

        self.assertFalse(view.set_tables(()))
        self.assertIn('Open a supported save copy', view._body.winfo_children()[0].cget('text'))
        self.assertTrue(view.set_tables((fiefs, officers)))
        self.root.update_idletasks()
        self.assertEqual(view.sections, ('Existing fiefs', 'Officers'))
        self.assertEqual(len(view.cards), view.page_size)
        self.assertIn('Page 1 of 3', view.page_status.get())
        self.assertIn(fiefs.note, [widget.cget('text') for widget in descendants(view._body)
                                   if isinstance(widget, ttk.Label)])
        self.assertIn('Record 1', [card.cget('text') for card in view.cards])
        self.assertIn('Daimyo:', [widget.cget('text') for widget in descendants(view.cards[0])
                                  if isinstance(widget, ttk.Label)])
        self.assertFalse(any(isinstance(widget, ttk.Button)
                             and widget.cget('text') not in ('Previous', 'Next')
                             for widget in descendants(view)))

        view.next_button.invoke()
        view.next_button.invoke()
        self.assertEqual(len(view.cards), 2)
        self.assertIn('Page 3 of 3', view.page_status.get())
        view.table_selector.current(1)
        view.table_selector.event_generate('<<ComboboxSelected>>')
        self.root.update_idletasks()
        self.assertEqual(len(view.cards), 1)
        self.assertEqual(view.sections, ('Existing fiefs', 'Officers'))
        view.apply_theme('Dark')
        self.assertEqual(view._theme, 'Dark')
        self.assertEqual(len(view.cards), 1)


    def _scrollable_view(self):
        from koei_editor.shared.territory_visualization import TerritoryOverview
        self.root.geometry('900x500')
        self.root.deiconify()
        outside = ttk.Label(self.root, text='Outside the record viewport')
        outside.pack(side='bottom')
        view = TerritoryOverview(self.root)
        view.pack(fill='both', expand=True)
        rows = tuple((index, 'Native owner', 1000, 2000) for index in range(60))
        view.set_tables((InspectionTable('Cities', ('ID', 'Owner', 'Gold', 'Rice'), rows),
                         InspectionTable('Fiefs', ('ID', 'Owner', 'Gold', 'Rice'), rows)))
        self.root.update()
        self.assertLess(view._canvas.yview()[1], 1.0)
        return view, outside

    def test_wheel_events_on_record_children_scroll_only_their_view(self):
        view, outside = self._scrollable_view()
        card = view.cards[0]
        label = next(widget for widget in descendants(card) if isinstance(widget, ttk.Label))
        for target in (view._body, card, label):
            for sequence, arguments in (('<MouseWheel>', {'delta': -120}),
                                        ('<Button-5>', {})):
                with self.subTest(widget=type(target).__name__, sequence=sequence):
                    view._canvas.yview_moveto(0)
                    self.root.update()
                    before = view._canvas.yview()[0]
                    target.event_generate(sequence, **arguments)
                    self.root.update()
                    self.assertGreater(view._canvas.yview()[0], before)
        before = view._canvas.yview()
        outside.event_generate('<MouseWheel>', delta=-120)
        outside.event_generate('<Button-5>')
        self.root.update()
        self.assertEqual(view._canvas.yview(), before)

    def test_page_table_and_replacement_reset_the_viewport_to_first_records(self):
        view, _outside = self._scrollable_view()
        view._canvas.yview_moveto(1)
        self.root.update()
        self.assertGreater(view._canvas.yview()[0], 0.1)
        view.next_button.invoke()
        self.root.update()
        self.assertIn('Page 2 of 3', view.page_status.get())
        self.assertLess(view._canvas.yview()[0], 0.01)
        self.assertEqual(view.cards[0].cget('text'), 'Record 25')
        view._canvas.yview_moveto(1)
        view.previous_button.invoke()
        self.root.update()
        self.assertLess(view._canvas.yview()[0], 0.01)
        view._canvas.yview_moveto(1)
        view.table_selector.current(1)
        view.table_selector.event_generate('<<ComboboxSelected>>')
        self.root.update()
        self.assertLess(view._canvas.yview()[0], 0.01)
        view._canvas.yview_moveto(1)
        tables = (InspectionTable('Replacement', ('ID',), tuple((i,) for i in range(60))),)
        view.set_tables(tables)
        self.root.update()
        self.assertLess(view._canvas.yview()[0], 0.01)


if __name__ == '__main__':
    unittest.main()

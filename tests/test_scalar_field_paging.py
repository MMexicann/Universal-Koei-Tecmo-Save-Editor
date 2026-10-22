"""Paged field views and bulk edits stay bounded across scalar adapters."""
from dataclasses import dataclass
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

from koei_editor.game_registry import get_game
from tests.test_origins_parser import fixture as origins_fixture


@dataclass(frozen=True)
class SyntheticField:
    """Large, harmless mapped catalog used to exercise field paging."""
    id: str
    label: str
    offset: int
    group: str = 'Synthetic fields'
    slot: int = 1
    minimum: int = 0
    maximum: int = 99
    size: int = 1
    maxable: bool = True
    kind: str = 'int'
    encoding: str = 'little'

    def value(self, _payload):
        return 0

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            from koei_editor.games.dw3.models import SaveError
            raise SaveError(f'{self.label} requires a whole number from {self.minimum} to {self.maximum}.')


class ScalarFieldPagingTests(unittest.TestCase):
    field_count = 800

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)
        self.source = self.folder / 'origins.dat'
        self.source.write_bytes(origins_fixture())
        self.editor = get_game('origins').create_editor(self.root, self.root)
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertTrue(self.editor.open_path(self.source))
        errors.assert_not_called()

        self.fields = tuple(
            SyntheticField(f'field_{index:04d}', f'Generated field {index:04d}', 16 + index)
            for index in range(self.field_count)
        )
        self.field_map = MappingProxyType({field.id: field for field in self.fields})
        self.backend_patches = (
            patch.object(self.editor.backend, 'fields_for', return_value=self.fields),
            patch.object(self.editor.backend, 'field_map', return_value=self.field_map),
            patch.object(self.editor.backend, 'stage', side_effect=self.stage_synthetic),
            patch.object(self.editor.backend, 'limit_values', side_effect=self.limit_synthetic),
            patch.object(self.editor.backend, 'changed_payload', return_value=self.editor.document.payload),
        )
        for item in self.backend_patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.backend_patches)])
        self.editor.refresh()
        self.root.update()

    def stage_synthetic(self, _document, changes, key, value):
        field = self.field_map[key]
        field.validate(value)
        result = dict(changes)
        if value == field.value(self.editor.document.payload):
            result.pop(key, None)
        else:
            result[key] = value
        return result

    def limit_synthetic(self, _document, changes, keys):
        return {key: self.field_map[key].maximum for key in keys
                if self.field_map[key].maxable
                and changes.get(key, self.field_map[key].value(self.editor.document.payload))
                != self.field_map[key].maximum}

    def set_filter_toggle(self, variable, selected):
        widgets = [self.root]
        while widgets:
            widget = widgets.pop()
            widgets.extend(widget.winfo_children())
            if (isinstance(widget, ttk.Checkbutton)
                    and str(widget.cget('variable')) == str(variable)):
                if variable.get() != selected:
                    widget.invoke()
                self.assertEqual(variable.get(), selected)
                return
        self.fail('The field-filter checkbutton was not found.')

    def test_catalog_is_paged_with_total_matching_count_and_last_page_bounds(self):
        editor = self.editor
        page_size = editor.field_page_size
        self.assertEqual(page_size, 250)
        self.assertEqual(editor._field_page, 0)
        self.assertEqual(len(editor.fields.get_children()), page_size)
        self.assertIn(f'{self.field_count:,}', editor.page_info.get())
        self.assertIn(f'1–{page_size:,}', editor.page_info.get())

        editor.change_field_page(1)
        self.assertEqual(editor._field_page, 1)
        self.assertEqual(len(editor.fields.get_children()), page_size)
        self.assertIn(f'{page_size + 1:,}–{page_size * 2:,}', editor.page_info.get())
        editor.change_field_page(1)
        editor.change_field_page(1)
        self.assertEqual(editor._field_page, 3)
        self.assertEqual(len(editor.fields.get_children()), self.field_count - page_size * 3)
        self.assertIn(f'{self.field_count:,} of {self.field_count:,}', editor.page_info.get())
        self.assertEqual(str(editor.next_field_page['state']), 'disabled')
        editor.change_field_page(1)
        self.assertEqual(editor._field_page, 3)
        editor.change_field_page(-1)
        self.assertEqual(editor._field_page, 2)
        self.assertEqual(str(editor.previous_field_page['state']), 'normal')

    def test_search_and_native_filters_recount_matches_without_dropping_pending_edits(self):
        editor = self.editor
        editor.stage_values({'field_0799': 42, 'field_0001': 17})
        editor.search.set('field_07')
        self.set_filter_toggle(editor.pending_only, True)
        self.root.update()
        self.assertEqual(editor._filtered_field_ids, ('field_0799',))
        self.assertEqual(editor.fields.get_children(), ('field_0799',))
        self.assertIn('1', editor.page_info.get())
        self.assertIn('2 pending edits', editor.field_count.get())
        self.assertIn('1 hidden', editor.field_count.get())
        self.assertEqual(editor.changes, {'field_0799': 42, 'field_0001': 17})

        self.set_filter_toggle(editor.pending_only, False)
        editor.pinned_fields = frozenset(('field_0798', 'field_0799'))
        self.set_filter_toggle(editor.pinned_only, True)
        self.root.update()
        self.assertEqual(set(editor._filtered_field_ids), {'field_0798', 'field_0799'})
        self.assertEqual(set(editor.fields.get_children()), {'field_0798', 'field_0799'})
        self.assertIn('of 2', editor.page_info.get())

    def test_exact_field_id_enter_clears_hiding_filters_and_selects_correct_page(self):
        editor = self.editor
        editor.stage_values({'field_0001': 17})
        editor.configure_pins(('field_0002',))
        editor.group.set('Synthetic fields')
        self.set_filter_toggle(editor.pending_only, True)
        self.set_filter_toggle(editor.pinned_only, True)
        editor.search.set('field_0799')
        self.root.update()
        self.assertEqual(editor.fields.get_children(), ())

        self.root.deiconify()
        editor.workspace_tabs.select(editor.edit_page)
        self.root.update()
        editor.search_entry.focus_force()
        self.root.update()
        self.assertTrue(editor.search_entry.winfo_ismapped())
        editor.search_entry.event_generate('<Return>')
        self.root.update()
        self.assertEqual(editor.search.get(), '')
        self.assertEqual(editor.group.get(), 'All fields')
        self.assertFalse(editor.pending_only.get())
        self.assertFalse(editor.pinned_only.get())
        self.assertEqual(editor._field_page, 3)
        self.assertEqual(editor.fields.selection(), ('field_0799',))
        self.assertTrue(editor.fields.exists('field_0799'))
        self.assertEqual(editor.changes, {'field_0001': 17})

    def test_page_navigation_isolates_selection_and_max_visible_bulk_edit(self):
        editor = self.editor
        first_page = tuple(editor.fields.get_children())
        editor.fields.selection_set(first_page[0])
        editor.change_field_page(1)
        self.assertFalse(set(editor.fields.selection()) & set(first_page))
        second_page = tuple(editor.fields.get_children())
        editor.fields.selection_set(second_page[0])
        editor.max_selected()
        self.assertEqual(set(editor.changes), {second_page[0]})
        editor.undo()
        self.assertEqual(editor.changes, {})

        editor.max_visible()
        self.assertEqual(set(editor.changes), set(second_page))
        self.assertTrue(set(editor.changes).isdisjoint(first_page))
        editor.undo()
        self.assertEqual(editor.changes, {})
        self.assertEqual(self.source.read_bytes(), self.editor.document.raw)

    def test_global_field_sort_precedes_page_slicing(self):
        editor = self.editor
        # The synthetic catalog is stored in ascending ID order. Reverse sorting
        # by the visible field column should reverse the full catalog, not just
        # reorder the first 250 already-rendered rows.
        editor.sort_fields('field')
        self.root.update()
        # After two heading activations the full catalog must be descending.
        editor.sort_fields('field')
        self.root.update()
        self.assertEqual(set(editor.fields.get_children()),
                         {field.id for field in self.fields[-editor.field_page_size:]})
        visible = tuple(editor.fields.get_children())
        labels = tuple(editor.fields.set(key, 'field') for key in visible)
        self.assertEqual(labels, tuple(sorted(labels, key=str.casefold, reverse=True)))
        editor.change_field_page(1)
        next_labels = tuple(editor.fields.set(key, 'field') for key in editor.fields.get_children())
        self.assertTrue(next_labels)
        self.assertLessEqual(next_labels[0].casefold(), labels[-1].casefold())


class ScalarUndoFocusTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.source = Path(self.area.name) / 'origins.dat'
        self.source.write_bytes(origins_fixture())

        game = get_game('origins')
        self.editors = []
        for name in ('first', 'second'):
            host = tk.Frame(self.root, name=f'{name}_editor_host')
            host.pack(fill='both', expand=True)
            editor = game.create_editor(self.root, host)
            self.assertTrue(editor.open_path(self.source))
            self.editors.append(editor)

    def test_control_z_only_undos_the_focused_retained_editor(self):
        first, second = self.editors
        first.stage_values({'gold': 5000})
        second.stage_values({'gold': 6000})

        # Each retained editor registers a root-wide shortcut callback. Pass
        # the actual focused widget through both callbacks, as Tk does, and
        # verify only the callback whose editor host contains it handles Undo.
        focused_second = SimpleNamespace(widget=second.search_entry)
        self.assertIsNone(first._undo_shortcut(focused_second))
        self.assertEqual(second._undo_shortcut(focused_second), 'break')
        self.assertEqual(first.changes, {'gold': 5000})
        self.assertEqual(second.changes, {})

        focused_first = SimpleNamespace(widget=first.search_entry)
        self.assertEqual(first._undo_shortcut(focused_first), 'break')
        self.assertIsNone(second._undo_shortcut(focused_first))
        self.assertEqual(first.changes, {})
        self.assertEqual(second.changes, {})


if __name__ == '__main__':
    unittest.main()

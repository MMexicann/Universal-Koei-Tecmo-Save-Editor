"""Endpoint filters retain explicit scope and never choose a hidden conversion."""
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest

from koei_editor import conversion
from koei_editor.shared.conversion_gui import ConversionWorkspace
from tests.test_conversion import write_copy


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class ConversionEndpointFilterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.gui = ConversionWorkspace(self.root, self.root, on_queue=lambda _review: None)
        self.gui.frame.pack(fill='both', expand=True)

    def wait(self):
        deadline = time.monotonic() + 30
        while self.gui.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.gui.busy, 'Conversion worker did not finish.')
        self.root.update_idletasks()

    def choose(self, route_id):
        route = conversion.get_route(route_id)
        source = write_copy(self.folder / 'source', route.source_id)
        target = write_copy(self.folder / 'target', route.target_id, 1)
        self.gui.source_filter.set(conversion.ENDPOINTS[route.source_id].label)
        self.gui.target_filter.set(conversion.ENDPOINTS[route.target_id].label)
        self.gui.route.set(route.label)
        self.gui.source.set(str(source))
        self.gui.template.set(str(target))
        return route

    def test_exact_source_filter_finds_one_way_ps4_scopes_without_auto_selection(self):
        label = conversion.ENDPOINTS['wo3u_ps4'].label
        self.assertIn(label, self.gui.source_selector['values'])
        self.assertNotIn(label, self.gui.target_selector['values'])
        self.gui.source_filter.set(label)
        route = conversion.get_route('wo3u_ps4-to-wo3u-ps4-materials')
        expected = tuple(item.label for item in conversion.ROUTES if item.source_id == 'wo3u_ps4')
        self.assertEqual(tuple(self.gui.route_selector['values']), expected)
        self.assertEqual(self.gui.route_count.get(), f'2 of {len(conversion.ROUTES)} routes')
        self.assertEqual(self.gui.route.get(), '')
        self.assertIn('disabled', self.gui.review_button.state())
        self.assertIn('disabled', self.gui.swap_button.state())
        self.gui.route_search.set('CUSA00588')
        self.assertEqual(tuple(self.gui.route_selector['values']), expected)
        self.gui.route.set(route.label)
        self.assertIn('disabled', self.gui.swap_button.state())

    def test_matching_filters_retain_review_but_incompatible_destination_clears_it(self):
        route = self.choose('wo3u_ps4-to-wo3u-ps4-materials')
        self.gui.review()
        for widget in (self.gui.search_entry, self.gui.source_selector, self.gui.target_selector,
                       self.gui.route_selector):
            self.assertIn('disabled', widget.state())
        self.wait()
        prepared, revision = self.gui.prepared, self.gui._revision
        self.assertIsNotNone(prepared)
        self.assertEqual(prepared.gameplay_bytes, 355)
        self.assertIn('readonly', self.gui.source_selector.state())
        self.assertIn('readonly', self.gui.target_selector.state())
        self.gui.route_search.set('CUSA00588')
        self.gui.target_filter.set(self.gui._all_targets)
        self.gui.source_filter.set(self.gui._all_sources)
        self.assertIs(self.gui.prepared, prepared)
        self.assertEqual(self.gui._revision, revision)
        self.assertEqual(self.gui.route.get(), route.label)
        self.assertNotIn('disabled', self.gui.export_button.state())
        self.gui.source_filter.set(conversion.ENDPOINTS['wo3u_ps4'].label)
        self.gui.target_filter.set(conversion.ENDPOINTS['dw8xl'].label)
        self.assertEqual(tuple(self.gui.route_selector['values']), ())
        self.assertEqual(self.gui.route_count.get(), f'0 of {len(conversion.ROUTES)} routes')
        self.assertEqual(self.gui.route.get(), '')
        self.assertIsNone(self.gui.prepared)
        for button in (self.gui.review_button, self.gui.export_button, self.gui.queue_button,
                       self.gui.swap_button, self.gui.route_selector):
            self.assertIn('disabled', button.state())
        self.assertEqual(self.gui.requirements.get(), '')
        self.gui.target_filter.set(self.gui._all_targets)
        self.assertEqual(tuple(self.gui.route_selector['values']),
                         (route.label, conversion.get_route('wo3u_ps4-to-wo3u-ps4-stats-materials').label))
        self.assertEqual(self.gui.route.get(), '')
        self.assertIsNone(self.gui.prepared)

    def test_unknown_programmatic_endpoint_does_not_broaden_the_filter(self):
        self.gui.source_filter.set('unknown endpoint')
        self.assertEqual(tuple(self.gui.route_selector['values']), ())
        self.gui.source_filter.set(self.gui._all_sources)
        self.gui.target_filter.set('unknown endpoint')
        self.assertEqual(tuple(self.gui.route_selector['values']), ())
        self.assertEqual(self.gui.route.get(), '')

    def test_reverse_clears_every_filter_swaps_copies_and_requires_fresh_review(self):
        self.choose('dw8xl-to-dw8xl_vita')
        self.gui.route_search.set('common')
        self.gui.review()
        self.wait()
        self.assertIsNotNone(self.gui.prepared)
        source, template = self.gui.source.get(), self.gui.template.get()
        self.gui.reverse_route()
        self.assertEqual(self.gui.source_filter.get(), self.gui._all_sources)
        self.assertEqual(self.gui.target_filter.get(), self.gui._all_targets)
        self.assertEqual(self.gui.route_search.get(), '')
        self.assertEqual(self.gui.route.get(), conversion.get_route('dw8xl_vita-to-dw8xl').label)
        self.assertEqual((self.gui.source.get(), self.gui.template.get()), (template, source))
        self.assertIsNone(self.gui.prepared)
        self.assertIn('disabled', self.gui.export_button.state())
        self.assertIn('disabled', self.gui.queue_button.state())
        self.assertEqual(len(self.gui.route_selector['values']), len(conversion.ROUTES))

    def test_compact_layout_and_keyboard_filter_reset_keep_controls_reachable(self):
        self.root.geometry('640x520')
        self.root.deiconify()
        self.root.update()
        self.assertLess(self.gui.source_selector.winfo_y(), self.gui.target_selector.winfo_y())
        for widget in (self.gui.search_entry, self.gui.source_selector, self.gui.target_selector,
                       self.gui.route_selector):
            self.assertGreater(widget.winfo_width(), 20)
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())
        self.gui.source_filter.set(conversion.ENDPOINTS['wo3u_ps4'].label)
        self.gui.source_selector.focus_force()
        self.root.update()
        self.gui.source_selector.event_generate('<Escape>')
        self.root.update()
        self.assertEqual(self.gui.source_filter.get(), self.gui._all_sources)
        self.gui.target_filter.set(conversion.ENDPOINTS['wo3u'].label)
        self.gui.target_selector.focus_force()
        self.root.update()
        self.gui.target_selector.event_generate('<Escape>')
        self.root.update()
        self.assertEqual(self.gui.target_filter.get(), self.gui._all_targets)
        self.gui.search_entry.focus_force()
        self.root.update()
        self.gui.search_entry.event_generate('<Return>')
        self.root.update()
        self.assertIs(self.root.focus_get(), self.gui.route_selector)

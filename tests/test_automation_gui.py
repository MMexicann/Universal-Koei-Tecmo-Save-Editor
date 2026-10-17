"""Code-free workflow construction, grouped dependencies and read-only native preview."""
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.game_registry import get_game
from koei_editor.shared import automation
from koei_editor.shared.automation_gui import WorkflowWorkspace
from koei_editor.shared.appearance import THEMES
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.test_dw4hyper_format import procedural_raw


class WorkflowGuiTests(unittest.TestCase):
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
        self.source = self.folder / 'save.dat'
        self.raw = procedural_raw()
        self.source.write_bytes(self.raw)
        self.workspace = WorkflowWorkspace(self.root, self.root)
        self.addCleanup(self.workspace.close)
        label = next(label for label, game in self.workspace.games.items() if game.id == 'dw4hyper')
        self.workspace.game.set(label)
        self.adapter = get_game('dw4hyper').get_scalar_adapter()
        self.workspace.set_source(self.adapter, self.adapter.read_save(self.source))

    def field(self, key, value):
        self.workspace.search.set(key)
        label = next(label for label, field in self.workspace._field_labels.items() if field == key)
        self.workspace.field.set(label)
        self.workspace.value.set(str(value))

    def finish(self):
        end = time.monotonic() + 20
        while self.workspace.busy and time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.workspace.busy)

    def test_native_preview_export_and_load_without_writing_gameplay(self):
        field = next(field for field in self.workspace._fields.values() if getattr(field, 'maxable', True))
        value = field.minimum if field.value(self.workspace.document.payload) != field.minimum else field.maximum
        self.field(field.id, value)
        self.workspace.add_operation('set')
        self.workspace.add_operation('assert')
        self.workspace.preview_reference()
        self.finish()
        self.assertIn('review_token', self.workspace.summary.get('1.0', 'end'))
        destination = self.folder / 'reusable.workflow.json'
        with patch('koei_editor.shared.automation_gui.filedialog.asksaveasfilename', return_value=str(destination)):
            self.workspace.export()
            self.finish()
        workflow = automation.load(destination)
        self.assertEqual([op.op for op in workflow.operations], ['set', 'assert'])
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(set(self.folder.iterdir()), {self.source, destination})
        with patch('koei_editor.shared.automation_gui.filedialog.askopenfilename', return_value=str(destination)):
            self.workspace.load()
            self.finish()
        self.assertIsNone(self.workspace.document)
        self.assertEqual(tuple(self.workspace.operations), workflow.operations)

    def test_preview_and_exports_keep_native_reads_and_serialization_off_tk_thread(self):
        self.workspace.operations = [automation.Operation('assert', (('officer_0_attack', 50),))]
        tk_thread = threading.get_ident()
        calls = []
        def checked(method):
            def invoke(bound, *args, **kwargs):
                calls.append((method.__name__, threading.get_ident()))
                self.assertNotEqual(threading.get_ident(), tk_thread,
                                    'Native validation returned to the Tk thread.')
                return method(bound, *args, **kwargs)
            return invoke
        workflow_path = self.folder / 'thread-safe.workflow.json'
        batch_path = self.folder / 'thread-safe.batch.json'
        output = self.folder / 'output'
        output.mkdir()
        with (
            patch.object(BoundScalarAdapter, 'read_save', checked(BoundScalarAdapter.read_save)),
            patch.object(BoundScalarAdapter, 'serialize', checked(BoundScalarAdapter.serialize)),
            patch('koei_editor.shared.automation_gui.messagebox.showerror') as error,
        ):
            self.workspace.preview_reference()
            self.finish()
            with patch('koei_editor.shared.automation_gui.filedialog.asksaveasfilename', return_value=str(workflow_path)):
                self.workspace.export()
                self.finish()
            with (
                patch('koei_editor.shared.automation_gui.filedialog.askopenfilenames', return_value=(str(self.source),)),
                patch('koei_editor.shared.automation_gui.filedialog.askdirectory', return_value=str(output)),
                patch('koei_editor.shared.automation_gui.filedialog.asksaveasfilename', return_value=str(batch_path)),
            ):
                self.workspace.export_batch()
                self.finish()
        error.assert_not_called()
        self.assertTrue(workflow_path.exists())
        self.assertTrue(batch_path.exists())
        self.assertIn('review_token', self.workspace.summary.get('1.0', 'end'))
        self.assertTrue(calls)
        self.assertEqual({name for name, _thread in calls}, {'read_save', 'serialize'})
        self.assertTrue(all(thread != tk_thread for _name, thread in calls))

    def test_group_reorder_remove_exact_text_and_invalid_value_rejection(self):
        fields = list(self.workspace._fields.values())[:2]
        for field in fields:
            self.field(field.id, field.value(self.workspace.document.payload))
            self.workspace.add_operation('set')
        self.workspace.table.selection_set('0')
        self.field(fields[1].id, fields[1].value(self.workspace.document.payload))
        self.workspace.extend_set()
        self.assertEqual(len(self.workspace.operations[0].values), 2)
        self.workspace.move(1)
        self.assertEqual(len(self.workspace.operations[1].values), 2)
        self.workspace.remove()
        self.assertEqual(len(self.workspace.operations), 1)
        self.field(fields[0].id, 'not an integer')
        with patch('koei_editor.shared.automation_gui.messagebox.showerror') as error:
            self.workspace.add_operation('set')
        error.assert_called_once()
        self.assertEqual(len(self.workspace.operations), 1)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_source_change_worker_failure_and_busy_mutations_preserve_workflow(self):
        field = next(iter(self.workspace._fields.values()))
        self.field(field.id, field.value(self.workspace.document.payload))
        self.workspace.add_operation('assert')
        self.workspace.busy = True
        self.workspace.remove()
        self.workspace.move(1)
        self.assertEqual(len(self.workspace.operations), 1)
        self.workspace.busy = False
        self.source.write_bytes(b'corrupt after open')
        with patch('koei_editor.shared.automation_gui.messagebox.showerror') as error:
            self.workspace.preview_reference()
            self.finish()
        error.assert_called_once()
        self.assertEqual(len(self.workspace.operations), 1)
        self.assertIn('failed', self.workspace.status.get())

    def test_batch_plan_export_needs_no_json_editing_and_preserves_copies(self):
        field = next(iter(self.workspace._fields.values()))
        self.field(field.id, field.value(self.workspace.document.payload))
        self.workspace.add_operation('assert')
        other = self.folder / 'second.dat'
        other.write_bytes(self.raw)
        output = self.folder / 'results'
        output.mkdir()
        plan = self.folder / 'reviewed.batch.json'
        with (
            patch('koei_editor.shared.automation_gui.filedialog.askopenfilenames',
                  return_value=(str(self.source), str(other))),
            patch('koei_editor.shared.automation_gui.filedialog.askdirectory', return_value=str(output)),
            patch('koei_editor.shared.automation_gui.filedialog.asksaveasfilename', return_value=str(plan)),
        ):
            self.workspace.export_batch()
            self.finish()
        workflow, specs = automation.load_batch(plan)
        self.assertEqual(len(specs), 2)
        self.assertTrue(automation.preview(automation.prepare(workflow, specs))['success'])
        self.assertEqual(tuple(output.iterdir()), ())
        self.assertEqual(other.read_bytes(), self.raw)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_valid_source_replacement_requires_reopening_reference(self):
        field = next(field for field in self.workspace._fields.values()
                     if field.minimum != field.value(self.workspace.document.payload))
        self.field(field.id, field.minimum)
        self.workspace.add_operation('set')
        self.source.write_bytes(self.adapter.serialize(self.workspace.document, {field.id: field.minimum}))
        with patch('koei_editor.shared.automation_gui.messagebox.showerror') as error:
            self.workspace.preview_reference()
            self.finish()
        error.assert_called_once()
        self.assertIn('failed', self.workspace.status.get())

    def test_batch_plan_metadata_cannot_occupy_planned_save_destination(self):
        field = next(iter(self.workspace._fields.values()))
        self.field(field.id, field.value(self.workspace.document.payload))
        self.workspace.add_operation('assert')
        output = self.folder / 'results'
        output.mkdir()
        colliding = output / ('copy-1-' + self.source.name)
        with (
            patch('koei_editor.shared.automation_gui.filedialog.askopenfilenames', return_value=(str(self.source),)),
            patch('koei_editor.shared.automation_gui.filedialog.askdirectory', return_value=str(output)),
            patch('koei_editor.shared.automation_gui.filedialog.asksaveasfilename', return_value=str(colliding)),
            patch('koei_editor.shared.automation_gui.messagebox.showerror') as error,
        ):
            self.workspace.export_batch()
            self.finish()
        error.assert_called_once()
        self.assertEqual(tuple(output.iterdir()), ())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_native_preview_validation_stays_off_tk_thread(self):
        field = next(iter(self.workspace._fields.values()))
        self.field(field.id, field.value(self.workspace.document.payload))
        self.workspace.add_operation('assert')
        ui_thread = threading.get_ident()
        calls = []
        preview = automation.preview
        def validate_in_worker(batch):
            calls.append(threading.get_ident())
            return preview(batch)
        with patch('koei_editor.shared.automation_gui.automation.preview', side_effect=validate_in_worker):
            self.workspace.preview_reference()
            self.finish()
        self.assertTrue(calls)
        self.assertTrue(all(thread != ui_thread for thread in calls))
        self.assertIn('review_token', self.workspace.summary.get('1.0', 'end'))

    def test_application_retains_builder_and_respects_busy_close(self):
        app = Application(self.root, persist_preferences=False)
        app.show_workflow_builder()
        builder = app.workflow_builder
        self.addCleanup(builder.close)
        builder.name.set('Retained workflow')
        for theme in THEMES:
            app.apply_theme(theme)
        app.show_library()
        app.show_workflow_builder()
        self.assertIs(app.workflow_builder, builder)
        self.assertEqual(builder.name.get(), 'Retained workflow')
        builder.busy = True
        with patch('tkinter.messagebox.showinfo') as notice:
            app.close()
        notice.assert_called_once()
        builder.busy = False
        self.assertTrue(self.root.winfo_exists())

    def test_real_application_builder_controls_fit_or_scroll_into_view_at_minimum_and_large_sizes(self):
        app = Application(self.root, preferences_path=self.folder / 'preferences.json',
                          persist_preferences=False)
        app.show_workflow_builder()
        builder = app.workflow_builder
        self.addCleanup(builder.close)
        self.root.deiconify()

        def inside(widget, boundary):
            self.assertTrue(widget.winfo_ismapped(), str(widget))
            self.assertGreater(widget.winfo_width(), 1, str(widget))
            self.assertGreater(widget.winfo_height(), 1, str(widget))
            for coordinate, extent in (('x', 'width'), ('y', 'height')):
                start = getattr(widget, 'winfo_root' + coordinate)()
                lower = getattr(boundary, 'winfo_root' + coordinate)()
                self.assertGreaterEqual(start, lower, (str(widget), coordinate))
                self.assertLessEqual(start + getattr(widget, 'winfo_' + extent)(),
                                     lower + getattr(boundary, 'winfo_' + extent)(),
                                     (str(widget), coordinate))

        for geometry in ('780x680', '1180x930', '780x680'):
            with self.subTest(geometry=geometry):
                self.root.geometry(geometry)
                for _ in range(3):
                    self.root.update()
                self.assertEqual((self.root.winfo_width(), self.root.winfo_height()),
                                 tuple(map(int, geometry.split('x'))))
                self.assertEqual(self.root.minsize(), (780, 680))
                inside(builder.canvas, self.root)
                inside(builder.scrollbar, self.root)
                footer = [control for control in builder.controls if control.master is builder.actions]
                self.assertEqual(len(footer), 7)
                for control in footer:
                    inside(control, builder.actions)
                    inside(control, self.root)
                builder.canvas.yview_moveto(0)
                self.root.update()
                # Top selectors are truly inside the viewport, not merely
                # mapped in an off-canvas window or clipped by another row.
                inside(builder.game_choice, builder.canvas)
                for control in builder.controls + [builder.table, builder.summary]:
                    if control.master is builder.actions:
                        continue
                    control.focus_force()
                    self.root.update()
                    self.assertIs(self.root.focus_get(), control)
                    inside(control, builder.canvas)
                    inside(control, control.master)
                if geometry == '780x680':
                    self.assertGreater(builder.canvas.yview()[0], 0)
                    self.assertGreater(builder.content.winfo_height(), builder.canvas.winfo_height())
                # Scrolling up from the review area restores the source row.
                builder.canvas.yview_moveto(0)
                self.root.update()
                inside(builder.game_choice, builder.canvas)
                # Wheel scrolling stays scoped to this builder rather than
                # capturing input from retained workspaces elsewhere.
                # The canvas also provides a wheel target outside child controls.
                builder.canvas.event_generate('<MouseWheel>', delta=-120)
                self.root.update()
                if builder.content.winfo_height() > builder.canvas.winfo_height():
                    self.assertGreater(builder.canvas.yview()[0], 0)
                builder.game_choice.focus_force()
                self.root.update()
                inside(builder.game_choice, builder.canvas)

    def test_real_application_minimum_builder_can_add_preview_and_export_from_visible_controls(self):
        app = Application(self.root, preferences_path=self.folder / 'preferences.json',
                          persist_preferences=False)
        app.show_workflow_builder()
        builder = app.workflow_builder
        self.addCleanup(builder.close)
        self.root.deiconify()
        self.root.geometry('780x680')
        self.root.update()
        builder.game.set(next(label for label, game in builder.games.items() if game.id == 'dw4hyper'))
        builder.set_source(self.adapter, self.adapter.read_save(self.source))
        builder.search.set('officer_0_attack')
        builder.field.set(next(label for label, key in builder._field_labels.items() if key == 'officer_0_attack'))
        builder.value.set('123')
        buttons = {control.cget('text'): control for control in builder.controls
                   if control.winfo_class() == 'TButton'}
        add = buttons['New set group']
        add.focus_force()
        self.root.update()
        self.assertGreaterEqual(add.winfo_rooty(), builder.canvas.winfo_rooty())
        self.assertLessEqual(add.winfo_rooty() + add.winfo_height(),
                             builder.canvas.winfo_rooty() + builder.canvas.winfo_height())
        add.invoke()
        self.assertEqual(builder.operations, [automation.Operation('set', (('officer_0_attack', 123),))])

        def finish_builder():
            deadline = time.monotonic() + 20
            while builder.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.01)
            self.assertFalse(builder.busy)

        destination = self.folder / 'minimum.workflow.json'
        with patch('koei_editor.shared.automation_gui.messagebox.showerror') as error:
            buttons['Preview reference'].invoke()
            finish_builder()
            self.assertIn('review_token', builder.summary.get('1.0', 'end'))
            with patch('koei_editor.shared.automation_gui.filedialog.asksaveasfilename',
                       return_value=str(destination)):
                buttons['Export workflow…'].invoke()
                finish_builder()
        error.assert_not_called()
        self.assertEqual(automation.load(destination).operations, tuple(builder.operations))
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(set(self.folder.iterdir()), {self.source, destination})

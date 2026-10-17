"""Code-free workflow construction, grouped dependencies and read-only native preview."""
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.game_registry import get_game
from koei_editor.shared import automation
from koei_editor.shared.automation_gui import WorkflowWorkspace
from koei_editor.shared.appearance import THEMES
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

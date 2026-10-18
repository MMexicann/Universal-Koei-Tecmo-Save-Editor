"""Visual construction of declarative workflows; saves use the automation engine."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.game_registry import GAMES
from koei_editor.shared import automation
from koei_editor.shared.edit_presets import validate_source
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.appearance import ui_font


class WorkflowWorkspace:
    """Retained, code-free workflow builder with explicit copied-save preflight."""
    def __init__(self, root, parent):
        self.root = root
        self.frame = ttk.Frame(parent, padding=(28, 16))
        self.workflow = None
        self.document = None
        self.adapter = None
        self.operations = []
        self.busy = False
        self._future = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='workflow-review')
        self._closed = False
        self._fields = {}
        self.games = {f'{game.title} [{game.id}]': game for game in GAMES if game.scalar_backend}
        # Reserve actions before the expanding viewport. The shell may leave
        # considerably less height than this form's natural requested size.
        self.actions = ttk.Frame(self.frame)
        self.actions.pack(side='bottom', fill='x', pady=(8, 0))
        viewport = ttk.Frame(self.frame)
        viewport.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(viewport, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(viewport, orient='vertical', command=self.canvas.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ttk.Frame(self.canvas, padding=(0, 0, 8, 0))
        self._content_window = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        self._button_rows = {}
        self._button_layouts = {}
        self._button_frames = {}
        self._guidance_labels = []
        body = self.content
        ttk.Label(body, text='WORKFLOW BUILDER', font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        description = ttk.Label(body, text='Build reusable edits and checks using verified native fields. '
                                'Preview each copied save before exporting a workflow.', wraplength=700)
        description.pack(anchor='w', pady=(6, 12))
        self._guidance_labels.append(description)
        self.game = tk.StringVar(root)
        self.game_choice = ttk.Combobox(body, textvariable=self.game, values=tuple(self.games),
                                        state='readonly', width=1)
        self.game_choice.pack(fill='x')
        self.game_choice.bind('<<ComboboxSelected>>', self.reset_source)
        self.controls = [self.game_choice]
        source_actions = ttk.Frame(body)
        source_actions.pack(fill='x', pady=(4, 0))
        self._button(source_actions, 'Open reference copy…', self.open_source)
        self._button(source_actions, 'Load workflow…', self.load)
        self.name = tk.StringVar(root, value='My workflow')
        naming = ttk.Frame(body)
        naming.pack(fill='x', pady=10)
        ttk.Label(naming, text='Workflow name').pack(side='left', padx=(0, 10))
        self.name_entry = ttk.Entry(naming, textvariable=self.name, width=1)
        self.name_entry.pack(side='left', fill='x', expand=True)
        self.controls.append(self.name_entry)
        self.source_label = tk.StringVar(root, value='Choose an exact game/platform, then a separate reference copy.')
        source_label = ttk.Label(body, textvariable=self.source_label, wraplength=700)
        source_label.pack(anchor='w')
        self._guidance_labels.append(source_label)
        entry = ttk.Frame(body)
        entry.pack(fill='x', pady=(12, 4))
        self.search = tk.StringVar(root)
        ttk.Label(entry, text='Find field').pack(side='left')
        self.search_entry = ttk.Entry(entry, textvariable=self.search, width=1)
        self.search_entry.pack(side='left', fill='x', expand=True, padx=(8, 0))
        self.search.trace_add('write', lambda *_: self.filter_fields())
        self.field = tk.StringVar(root)
        self.field_choice = ttk.Combobox(body, textvariable=self.field, state='readonly', width=1)
        self.field_choice.pack(fill='x')
        self.field_choice.bind('<<ComboboxSelected>>', self.select_field)
        self.controls += [self.search_entry, self.field_choice]
        editing = ttk.Frame(body)
        editing.pack(fill='x', pady=(8, 4))
        ttk.Label(editing, text='Value').pack(side='left')
        self.value = tk.StringVar(root)
        self.value_entry = ttk.Entry(editing, textvariable=self.value, width=1)
        self.value_entry.pack(side='left', fill='x', expand=True, padx=(8, 0))
        self.controls.append(self.value_entry)
        edit_actions = ttk.Frame(body)
        edit_actions.pack(fill='x', pady=(0, 8))
        self._button(edit_actions, 'New set group', lambda: self.add_operation('set'))
        self._button(edit_actions, 'Add to selected set', self.extend_set)
        self._button(edit_actions, 'Assert current value', lambda: self.add_operation('assert'))
        table_frame = ttk.Frame(body)
        table_frame.pack(fill='both', expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, columns=('operation', 'values'), show='headings', height=8, selectmode='browse')
        self.table.heading('operation', text='Operation')
        self.table.heading('values', text='Verified field assignments / expected values')
        self.table.column('operation', width=100, stretch=False)
        self.table.column('values', width=700)
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self._button(self.actions, 'Move up', lambda: self.move(-1))
        self._button(self.actions, 'Move down', lambda: self.move(1))
        self._button(self.actions, 'Remove operation', self.remove)
        self._button(self.actions, 'Preview reference', self.preview_reference)
        self._button(self.actions, 'Preview other copies…', self.preview_copies)
        self._button(self.actions, 'Export workflow…', self.export)
        self._button(self.actions, 'Export batch plan…', self.export_batch)
        self.summary = tk.Text(body, height=7, width=1, wrap='word', state='disabled')
        self.summary.pack(fill='x', pady=(10, 0))
        self.status = tk.StringVar(root, value='Set groups validate together. Assertions check values at their position in the sequence.')
        status = ttk.Label(body, textvariable=self.status, wraplength=700)
        status.pack(anchor='w', pady=8)
        self._guidance_labels.append(status)
        self.canvas.bind('<Configure>', self._resize_body)
        self.content.bind('<Configure>', self._resize_body)
        self._bind_viewport_controls(body)
        self.canvas.bind('<MouseWheel>', self._scroll_body)
        self.canvas.bind('<Button-4>', self._scroll_body)
        self.canvas.bind('<Button-5>', self._scroll_body)

    def _button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        self.controls.append(button)
        if parent not in self._button_rows:
            self._button_rows[parent] = []
            self._button_frames[parent] = []
            parent.bind('<Configure>', lambda _event, row=parent: self._layout_buttons(row))
        self._button_rows[parent].append(button)
        self._layout_buttons(parent)
        return button

    def _layout_buttons(self, parent):
        width = parent.winfo_width()
        row = column = used = 0
        layout = []
        for button in self._button_rows[parent]:
            required = button.winfo_reqwidth() + 8
            if column and used + required > width:
                row += 1
                column = used = 0
            layout.append((button, row, column))
            column += 1
            used += required
        if self._button_layouts.get(parent) != layout:
            frames = self._button_frames[parent]
            while len(frames) <= row:
                frames.append(ttk.Frame(parent))
            for button in self._button_rows[parent]:
                button.pack_forget()
            for index, line in enumerate(frames):
                if index <= row:
                    line.pack(fill='x')
                else:
                    line.pack_forget()
            # Independent row frames prevent grid column widths from making
            # one wrapped row exceed the measured available width of another.
            for button, row, _column in layout:
                button.pack(in_=frames[row], side='left', padx=(0, 8), pady=3)
            self._button_layouts[parent] = layout

    def _resize_body(self, _event=None):
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        for label in self._guidance_labels:
            label.configure(wraplength=max(1, width - 8))
        self.canvas.itemconfigure(self._content_window, width=width,
                                  height=max(self.content.winfo_reqheight(), self.canvas.winfo_height()))
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _bind_viewport_controls(self, parent):
        for widget in parent.winfo_children():
            widget.bind('<FocusIn>', lambda _event, target=widget: self._reveal(target), add='+')
            # Keep native field menus, operation scrolling and review-text
            # scrolling local to those widgets; other controls scroll the form.
            if not isinstance(widget, (ttk.Combobox, ttk.Treeview, tk.Text)):
                widget.bind('<MouseWheel>', self._scroll_body, add='+')
                widget.bind('<Button-4>', self._scroll_body, add='+')
                widget.bind('<Button-5>', self._scroll_body, add='+')
            self._bind_viewport_controls(widget)

    def _scroll_body(self, event):
        if getattr(event, 'num', None) in (4, 5):
            units = -1 if event.num == 4 else 1
        else:
            delta = getattr(event, 'delta', 0)
            units = (-1 if delta > 0 else 1) * max(1, abs(delta) // 120)
        self.canvas.yview_scroll(units * 3, 'units')
        return 'break'

    def _reveal(self, widget):
        top = widget.winfo_rooty() - self.content.winfo_rooty()
        bottom = top + widget.winfo_height()
        start = self.canvas.canvasy(0)
        height = self.canvas.winfo_height()
        extent = max(1, self.content.winfo_height())
        if top < start:
            self.canvas.yview_moveto(top / extent)
        elif bottom > start + height:
            self.canvas.yview_moveto((bottom - height) / extent)

    def _run(self, work, done):
        if self.busy or self._closed:
            return
        self.busy = True
        for control in self.controls:
            control.configure(state='disabled')
        self.status.set('Validating copied saves…')
        self._future = self._executor.submit(work)
        def poll():
            if self._closed:
                return
            if not self._future.done():
                self.root.after(30, poll)
                return
            self.busy = False
            for control in self.controls:
                control.configure(state='readonly' if isinstance(control, ttk.Combobox) else 'normal')
            try:
                result = self._future.result()
                done(result)
            except Exception as error:
                self.status.set('Validation failed. No gameplay copies were written.')
                messagebox.showerror('Workflow validation', str(error), parent=self.root)
        self.root.after(30, poll)

    def reset_source(self, _event=None):
        if self.busy:
            return
        self.document = self.adapter = None
        self._fields = {}
        self.field_choice.configure(values=())
        self.field.set('')
        self.source_label.set('Open a reference copy for this game/platform. Existing operations require a fresh preview.')
        self._show('')

    def open_source(self):
        if self.busy:
            return
        game = self.games.get(self.game.get())
        if game is None:
            messagebox.showerror('Workflow', 'Choose an exact game/platform first.', parent=self.root)
            return
        path = filedialog.askopenfilename(parent=self.root, title='Open separate reference save copy')
        if not path:
            return
        adapter = game.get_scalar_adapter()
        self._run(lambda: adapter.read_save(Path(path)), lambda document: self.set_source(adapter, document))

    def set_source(self, adapter, document):
        self.adapter, self.document = adapter, document
        self._fields = adapter.field_map(document)
        self.source_label.set(f'Reference: {document.source.name} · {len(self._fields):,} verified fields. '
                              'Search narrows the first 1,000 displayed matches.')
        self.filter_fields()
        self.status.set('Reference qualified. Choose fields, values and operation order.')

    def filter_fields(self):
        query = self.search.get().casefold()
        self._field_labels = {f'{key} — {getattr(field, "label", key)}': key
                              for key, field in self._fields.items()
                              if query in f'{key} {getattr(field, "label", key)}'.casefold()}
        # Search narrows very large record sets without creating an oversized Tk menu.
        labels = tuple(self._field_labels)[:1000]
        self.field_choice.configure(values=labels)
        if self.field.get() not in labels:
            self.field.set(labels[0] if labels else '')
            self.select_field()

    def select_field(self, _event=None):
        key = getattr(self, '_field_labels', {}).get(self.field.get())
        if key in self._fields:
            self.value.set(str(self._fields[key].value(self.document.payload)))

    def assignment(self):
        key = getattr(self, '_field_labels', {}).get(self.field.get())
        if key not in self._fields:
            raise ValueError('Choose a verified field from the opened reference copy.')
        field = self._fields[key]
        value = self.value.get() if getattr(field, 'kind', 'int') == 'text' else int(self.value.get(), 10)
        if not (type(value) is type(field.value(self.document.payload)) and value == field.value(self.document.payload)):
            field.validate(value)
        return key, value

    def add_operation(self, kind):
        if self.busy:
            return
        try:
            pair = self.assignment()
            self.operations.append(automation.Operation(kind, (pair,)))
            self.render()
        except (ValueError, TypeError) as error:
            messagebox.showerror('Workflow operation', str(error), parent=self.root)

    def extend_set(self):
        if self.busy:
            return
        selected = self.table.selection()
        try:
            if not selected or self.operations[int(selected[0])].op != 'set':
                raise ValueError('Select a set group to add dependent assignments together.')
            index = int(selected[0])
            values = dict(self.operations[index].values)
            key, value = self.assignment()
            values[key] = value
            self.operations[index] = automation.Operation('set', tuple(values.items()))
            self.render(index)
        except (ValueError, TypeError) as error:
            messagebox.showerror('Workflow operation', str(error), parent=self.root)

    def render(self, selected=None):
        self.table.delete(*self.table.get_children())
        for index, operation in enumerate(self.operations):
            self.table.insert('', 'end', iid=str(index), values=(operation.op,
                '; '.join(f'{key} = {value!r}' for key, value in operation.values)))
        if selected is not None and 0 <= selected < len(self.operations):
            self.table.selection_set(str(selected))
        self._show('Operations changed. Preview again to validate the complete sequence.')

    def move(self, delta):
        if self.busy:
            return
        selected = self.table.selection()
        if selected:
            index = int(selected[0])
            target = index + delta
            if 0 <= target < len(self.operations):
                self.operations[index], self.operations[target] = self.operations[target], self.operations[index]
                self.render(target)

    def remove(self):
        if not self.busy and self.table.selection():
            del self.operations[int(self.table.selection()[0])]
            self.render()

    def build(self):
        game = self.games.get(self.game.get())
        if game is None or self.document is None or self.adapter.game_id != game.id:
            raise ValueError('Open a reference copy for the selected game/platform.')
        workflow = automation.Workflow(self.name.get(), game.id, tuple(self.operations))
        automation.validate_workflow(workflow)
        return workflow

    def _show(self, text):
        self.summary.configure(state='normal')
        self.summary.delete('1.0', 'end')
        self.summary.insert('end', text)
        self.summary.configure(state='disabled')

    def _prepare(self, paths):
        workflow = self.build()
        jobs = tuple(automation.JobSpec(f'copy-{index + 1}', Path(path),
                         Path(path).with_name(Path(path).stem + '-workflow-preview' + Path(path).suffix))
                     for index, path in enumerate(paths))
        return workflow, jobs

    @staticmethod
    def _preview_report(batch):
        # Preview requalifies every native source. Keep that work and potentially
        # large JSON formatting on the worker, before the Tk callback runs.
        import json
        return json.dumps(automation.preview(batch), indent=2, ensure_ascii=False)

    def _review(self, report):
        self._show(report)
        self.status.set('Preview passed; no saves or backups were written. Export this workflow for reviewed batch execution with --automation.')

    def _prepare_batch(self, workflow, jobs):
        validate_source(self.adapter, self.document)
        return automation.prepare(workflow, jobs)

    def preview_reference(self):
        if self.busy:
            return
        try:
            _workflow, jobs = self._prepare((self.document.source,) if self.document else ())
            self._run(lambda: self._preview_report(self._prepare_batch(_workflow, jobs)), self._review)
        except (ValueError, TypeError) as error:
            messagebox.showerror('Workflow preview', str(error), parent=self.root)

    def preview_copies(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(parent=self.root, title='Choose compatible save copies for preflight')
        if not paths:
            return
        try:
            workflow, jobs = self._prepare(paths)
            self._run(lambda: self._preview_report(self._prepare_batch(workflow, jobs)), self._review)
        except (ValueError, TypeError) as error:
            messagebox.showerror('Workflow preview', str(error), parent=self.root)

    def export(self):
        if self.busy:
            return
        try:
            workflow, jobs = self._prepare((self.document.source,) if self.document else ())
            path = filedialog.asksaveasfilename(parent=self.root, title='Export validated reusable workflow',
                                               defaultextension='.workflow.json', filetypes=(('Workflow', '*.workflow.json'),))
            if not path:
                return
            destination = safe_path(path)
            def work():
                batch = self._prepare_batch(workflow, jobs)
                atomic_new(automation.dumps(workflow), destination)
                return self._preview_report(batch)
            self._run(work, lambda report: (self._review(report), self.status.set('Validated workflow exported. Existing files are never replaced.')))
        except (ValueError, TypeError, OSError) as error:
            messagebox.showerror('Workflow export', str(error), parent=self.root)

    def load(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title='Load reusable workflow', filetypes=(('Workflow', '*.workflow.json'), ('JSON', '*.json')))
        if not path:
            return
        def done(workflow):
            choice = next((name for name, game in self.games.items() if game.id == workflow.game_id), None)
            if choice is None:
                raise ValueError('Workflow requires an editable registered game/platform.')
            self.game.set(choice)
            self.reset_source()
            self.name.set(workflow.name)
            self.operations = list(workflow.operations)
            self.render()
            self.status.set('Workflow loaded. Open a reference copy and preview before export or execution.')
        self._run(lambda: automation.load(path), done)

    def export_batch(self):
        """Choose sources and new destinations without hand-editing JSON."""
        if self.busy:
            return
        try:
            workflow = self.build()
            paths = filedialog.askopenfilenames(parent=self.root, title='Choose compatible source copies')
            if not paths:
                return
            folder = filedialog.askdirectory(parent=self.root, title='Choose a separate output folder for new copies')
            if not folder:
                return
            destination = filedialog.asksaveasfilename(parent=self.root, title='Save local batch plan (contains local paths)',
                                                      defaultextension='.batch.json')
            if not destination:
                return
            specs = tuple(automation.JobSpec(f'copy-{index + 1}', Path(path),
                          Path(folder) / (f'copy-{index + 1}-' + Path(path).name))
                          for index, path in enumerate(paths))
            def work():
                import json
                batch = self._prepare_batch(workflow, specs)
                plan_path = safe_path(destination)
                for job in batch.jobs:
                    for path in (job.spec.source, job.spec.destination):
                        if plan_path == path or plan_path in path.parents or path in plan_path.parents:
                            raise ValueError('Choose a metadata plan path separate from all save inputs and outputs.')
                data = {'schema_version': 1, 'workflow': automation.workflow_data(workflow),
                        'jobs': [{'id': job.spec.id, 'source': str(job.spec.source),
                                  'destination': str(job.spec.destination)} for job in batch.jobs]}
                atomic_new((json.dumps(data, indent=2, ensure_ascii=True) + '\n').encode('utf-8'), plan_path)
                return self._preview_report(batch)
            self._run(work, lambda report: (self._review(report), self.status.set(
                'Validated batch plan exported. Keep it private: it contains local paths. Run --automation preview before apply.')))
        except (ValueError, TypeError, OSError) as error:
            messagebox.showerror('Batch plan export', str(error), parent=self.root)

    def apply_theme(self, palette):
        self.canvas.configure(background=palette['background'])
        for row in self._button_rows:
            self._layout_buttons(row)
        self.summary.configure(background=palette['background'], foreground=palette['text'])

    def close(self):
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)

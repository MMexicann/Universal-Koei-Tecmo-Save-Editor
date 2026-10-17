"""Reusable resource preset library, explicit target preview and staged Apply."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import compatible_presets as presets
from koei_editor.shared import edit_presets, preset_portability
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.preset_library import PresetLibrary


class CompatiblePresetWorkspace:
    """Retained workspace; injected existing sessions own every save operation."""

    def __init__(self, root, parent, session_provider=None):
        self.root = root
        self.session_provider = session_provider or (lambda: ())
        self.library = PresetLibrary()
        self.entries = ()
        self._sessions = {}
        self._entry = self._plan = self._target = None
        self._closed = False
        self._populating = False
        self.frame = ttk.Frame(parent, padding=(24, 16))
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(3, weight=1)
        self.search = tk.StringVar(root)
        self.target = tk.StringVar(root)
        self.status = tk.StringVar(root, value='Create or import a named resource preset, then choose an opened target save.')
        self.summary = tk.StringVar(root, value='Reusable resources across compatible save copies')
        self.count = tk.StringVar(root, value='No preset selected')
        self._build()
        self.search.trace_add('write', self.filter_library)
        self.target.trace_add('write', self._target_changed)
        self.refresh_sessions()
        self.refresh_library()

    def _build(self):
        heading = ttk.Frame(self.frame)
        heading.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        ttk.Label(heading, text='EDITING PRESETS', font=(ui_font(self.root), 23, 'bold')).pack(anchor='w')
        ttk.Label(heading, textvariable=self.summary, style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
        form = ttk.Frame(self.frame)
        form.grid(row=1, column=0, sticky='ew')
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='Target editor').grid(row=0, column=0, sticky='w', padx=(0, 12))
        self.target_selector = ttk.Combobox(form, textvariable=self.target, state='readonly')
        self.target_selector.grid(row=0, column=1, sticky='ew', pady=(0, 8))
        ttk.Button(form, text='Refresh editors', command=self.refresh_sessions).grid(row=0, column=2, padx=(10, 0), pady=(0, 8))
        ttk.Label(form, text='Find presets').grid(row=1, column=0, sticky='w', padx=(0, 12))
        self.search_entry = ttk.Entry(form, textvariable=self.search)
        self.search_entry.grid(row=1, column=1, sticky='ew')
        ttk.Button(form, text='Clear', command=lambda: self.search.set('')).grid(row=1, column=2, padx=(10, 0))
        self.search_entry.bind('<Escape>', lambda _event: self.search.set(''))
        actions = ttk.Frame(self.frame)
        actions.grid(row=2, column=0, sticky='ew', pady=12)
        ttk.Button(actions, text='Create from staged edits...', command=self.create_dialog).pack(side='left')
        ttk.Button(actions, text='Import...', command=self.import_dialog).pack(side='left', padx=8)
        self.export_button = ttk.Button(actions, text='Export selected...', command=self.export_dialog, state='disabled')
        self.export_button.pack(side='left')
        ttk.Button(actions, text='Source-bound presets...', command=self.open_source_presets).pack(side='right')
        self.bulk_button = ttk.Button(actions, text='Apply to multiple editors...', command=self.bulk_dialog,
                                      state='disabled')
        self.bulk_button.pack(side='left', padx=8)
        body = ttk.Panedwindow(self.frame, orient='horizontal')
        body.grid(row=3, column=0, sticky='nsew')
        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text='NAMED PRESETS', style='Muted.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 8))
        self.catalog = ttk.Treeview(left, columns=('profile', 'count'), show='tree headings', selectmode='extended', height=12)
        self.catalog.heading('#0', text='Preset name')
        self.catalog.heading('profile', text='Game / platform')
        self.catalog.heading('count', text='Fields')
        self.catalog.column('#0', width=200, minwidth=120)
        self.catalog.column('profile', width=95, minwidth=60)
        self.catalog.column('count', width=50, minwidth=40, stretch=False)
        self.catalog.grid(row=1, column=0, sticky='nsew')
        catalog_scroll = ttk.Scrollbar(left, orient='vertical', command=self.catalog.yview)
        catalog_scroll.grid(row=1, column=1, sticky='ns')
        self.catalog.configure(yscrollcommand=catalog_scroll.set)
        self.catalog.bind('<<TreeviewSelect>>', self._catalog_selected)
        body.add(left, weight=2)
        right = ttk.Frame(body, padding=(16, 0, 0, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        self.detail_heading = ttk.Label(right, text='Select a preset', font=(ui_font(self.root), 15, 'bold'))
        self.detail_heading.grid(row=0, column=0, sticky='w')
        ttk.Label(right, textvariable=self.count, style='Muted.TLabel', wraplength=650).grid(row=1, column=0, sticky='w', pady=(4, 10))
        self.tabs = ttk.Notebook(right)
        self.tabs.grid(row=2, column=0, sticky='nsew')
        assignments_page, preview_page = ttk.Frame(self.tabs), ttk.Frame(self.tabs)
        self.tabs.add(assignments_page, text='Choose assignments')
        self.tabs.add(preview_page, text='Complete target preview')
        self.assignments = self._table(assignments_page, ('field', 'value'),
                                       ('Resource field', 'Preset value'), selectmode='extended')
        self.assignments.bind('<<TreeviewSelect>>', self._assignments_changed)
        self.preview = self._table(preview_page, ('field', 'opened', 'before', 'after', 'effect'),
                                   ('Field / record', 'Opened', 'Currently staged', 'After apply', 'Effect'))
        controls = ttk.Frame(right)
        controls.grid(row=3, column=0, sticky='ew', pady=(10, 0))
        ttk.Button(controls, text='Select all', command=self.select_all).pack(side='left')
        ttk.Button(controls, text='Select none', command=lambda: self.assignments.selection_remove(*self.assignments.selection())).pack(side='left', padx=8)
        self.preview_button = ttk.Button(controls, text='Preview selected', command=self.prepare_preview, state='disabled')
        self.preview_button.pack(side='left')
        self.apply_button = ttk.Button(controls, text='Apply reviewed selection', command=self.apply_preview, state='disabled')
        self.apply_button.pack(side='right', padx=(10, 0))
        body.add(right, weight=4)
        footer = ttk.Frame(self.frame)
        footer.grid(row=4, column=0, sticky='ew', pady=(12, 0))
        self.status_label = ttk.Label(footer, textvariable=self.status, wraplength=1100)
        self.status_label.pack(anchor='w')
        self.guidance = ttk.Label(footer, text='Apply stages one Undo action. Save As in the target editor writes a separate game copy. '
                                  'Only explicitly qualified fixed resources are reusable; inventory, equipment and story records are excluded.',
                                  wraplength=1100, style='Muted.TLabel')
        self.guidance.pack(anchor='w', pady=(6, 0))
        self.frame.bind('<Configure>', self._resize, add='+')

    @staticmethod
    def _table(parent, columns, titles, selectmode='browse'):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        table = ttk.Treeview(parent, columns=columns, show='headings', selectmode=selectmode)
        for index, (key, title) in enumerate(zip(columns, titles)):
            table.heading(key, text=title)
            table.column(key, width=220 if index == 0 else 120, minwidth=80)
        table.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(parent, orient='vertical', command=table.yview)
        horizontal = ttk.Scrollbar(parent, orient='horizontal', command=table.xview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        return table

    def _resize(self, event):
        if event.widget is self.frame:
            width = max(160, event.width - 48)
            self.status_label.configure(wraplength=width)
            self.guidance.configure(wraplength=width)

    def apply_theme(self, palette):
        # All controls use the application's active ttk palette; field values
        # and staging state are deliberately independent of visual appearance.
        self.frame.configure(style='TFrame')

    def focus_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, 'end')
        return 'break'

    def close(self):
        self._plan = None
        self._closed = True

    def on_show(self):
        self._closed = False
        self.refresh_sessions()
        self.refresh_library()

    def has_pending_work(self):
        return False  # Draft creation is modal; saved presets and previews are not pending game edits.

    def _error(self, title, error):
        self.status.set(str(error))
        messagebox.showerror(title, str(error), parent=self.root)
        return False

    def refresh_sessions(self):
        self._invalidate()
        try:
            supplied = self.session_provider()
            if isinstance(supplied, dict):
                supplied = tuple(supplied.items())
            elif hasattr(supplied, 'adapter'):
                supplied = ((supplied.layout.title, supplied),)
            sessions = {}
            for index, item in enumerate(supplied):
                label, editor = item
                if not hasattr(editor, 'adapter') or getattr(editor, 'document', None) is None:
                    continue
                name = str(label)
                if name in sessions:
                    name += f' [{index + 1}]'
                sessions[name] = editor
            self._sessions = sessions
            self.target_selector.configure(values=tuple(sessions))
            if self.target.get() not in sessions:
                self.target.set(next(iter(sessions), ''))
        except Exception as error:
            self._sessions = {}
            self.target_selector.configure(values=())
            self.target.set('')
            self.status.set('Could not list target editors: ' + str(error))

    def _editor(self):
        editor = self._sessions.get(self.target.get())
        if editor is None or editor.document is None:
            raise SaveError('Open a separate save copy in an editor and refresh the target list.')
        return editor

    def _target_changed(self, *_args):
        self._invalidate()

    def _invalidate(self):
        self._plan = self._target = None
        if hasattr(self, 'apply_button'):
            self.apply_button.configure(state='disabled')
        if hasattr(self, 'preview'):
            self.preview.delete(*self.preview.get_children())

    def refresh_library(self, selected_id=None):
        try:
            snapshot = self.library.scan()
            self.entries = snapshot.entries
            self.filter_library()
            if selected_id is not None and self.catalog.exists(selected_id):
                self.catalog.selection_set(selected_id)
                self._catalog_selected()
            if snapshot.issues:
                self.status.set(f'{len(snapshot.issues)} invalid or changed local metadata files were excluded.')
        except Exception as error:
            self.entries = ()
            self.filter_library()
            self.status.set('Preset library unavailable: ' + str(error))

    def filter_library(self, *_args):
        selected = self.catalog.selection()
        self.catalog.delete(*self.catalog.get_children())
        tokens = self.search.get().casefold().split()
        for entry in self.entries:
            text = ' '.join((entry.preset.name, entry.preset.game_id, entry.preset.revision,
                             *(edit.field for edit in entry.preset.edits))).casefold()
            if all(token in text for token in tokens):
                self.catalog.insert('', 'end', iid=entry.id, text=entry.preset.name,
                                    values=(entry.preset.game_id, len(entry.preset.edits)))
        retained = tuple(identity for identity in selected if self.catalog.exists(identity))
        if retained:
            self.catalog.selection_set(retained)
        elif selected:
            self._set_entry(None)

    def _catalog_selected(self, _event=None):
        selected = self.catalog.selection()
        self.export_button.configure(text=f'Export {len(selected)} selected...' if len(selected) > 1 else 'Export selected...')
        entry = next((entry for entry in self.entries if selected and entry.id == selected[0]), None)
        if entry != self._entry:
            self._set_entry(entry)

    def _set_entry(self, entry):
        self._invalidate()
        self._entry = entry
        self._populating = True
        try:
            self.assignments.delete(*self.assignments.get_children())
            self.detail_heading.configure(text=entry.preset.name if entry else 'Select a preset')
            self.export_button.configure(state='normal' if entry else 'disabled')
            self.preview_button.configure(state='normal' if entry else 'disabled')
            self.bulk_button.configure(state='normal' if entry else 'disabled')
            if entry:
                self.count.set(f'{entry.preset.game_id} · {entry.preset.revision} · {len(entry.preset.edits)} assignments')
                for edit in entry.preset.edits:
                    self.assignments.insert('', 'end', iid=edit.field, values=(edit.field, str(edit.value)))
                self.assignments.selection_set(self.assignments.get_children())
            else:
                self.count.set('No preset selected')
        finally:
            self._populating = False

    def _assignments_changed(self, _event=None):
        if self._plan is not None and tuple(sorted(self.assignments.selection())) != self._plan.selected:
            self._invalidate()

    def select_all(self):
        self.assignments.selection_set(self.assignments.get_children())

    def create_from_staged(self, name, selected=None):
        editor = self._editor()
        preset = presets.create(editor.adapter, editor.document, dict(editor.changes), name, selected)
        entry = self.library.save(preset)
        self.search.set('')
        self.refresh_library(entry.id)
        self.status.set('Named resource preset saved locally. Choose a target and preview its selected assignments.')
        return entry

    def create_dialog(self):
        try:
            editor = self._editor()
            if not editor.changes:
                raise SaveError('Stage resource edits in the target editor before creating a preset.')
            policy = preset_portability.policy(editor.adapter, editor.document)
            mapping = editor.adapter.field_map(editor.document)
            original_adapter, original_document, original_pending = editor.adapter, editor.document, dict(editor.changes)
            eligible = set(policy.fields).intersection(editor.changes)
            if not eligible:
                raise SaveError('None of the staged fields has verified resource portability. '
                                'Use Source-bound presets for other edits.')
            window = tk.Toplevel(self.root)
            window.title('Create reusable resource preset')
            window.geometry('760x520')
            window.transient(self.root)
            window.columnconfigure(0, weight=1)
            window.rowconfigure(2, weight=1)
            ttk.Label(window, text='Select staged resources to include. Other staged edits stay in the editor.',
                      padding=12, wraplength=700).grid(row=0, column=0, sticky='w')
            name = tk.StringVar(window, value='My resource preset')
            ttk.Entry(window, textvariable=name).grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 8))
            holder = ttk.Frame(window, padding=(12, 0))
            holder.grid(row=2, column=0, sticky='nsew')
            table = self._table(holder, ('field', 'value', 'status'), ('Staged field', 'Value', 'Portability'), 'extended')
            for key, value in sorted(editor.changes.items()):
                table.insert('', 'end', iid=key, values=(key, str(value), preset_portability.exclusion_reason(policy, mapping[key])))
            table.selection_set(tuple(sorted(eligible)))
            footer = ttk.Frame(window, padding=12)
            footer.grid(row=3, column=0, sticky='ew')
            def save():
                try:
                    if (self._editor() is not editor or editor.adapter is not original_adapter
                            or editor.document is not original_document or editor.changes != original_pending):
                        raise SaveError('The target editor or staged values changed. Create the preset again.')
                    self.create_from_staged(name.get(), tuple(table.selection()))
                    window.destroy()
                except Exception as error:
                    self._error('Cannot Create Preset', error)
            ttk.Button(footer, text='Save selected resources', command=save).pack(side='left')
            ttk.Button(footer, text='Cancel', command=window.destroy).pack(side='right')
            window.grab_set()
            return window
        except Exception as error:
            return self._error('Cannot Create Preset', error)

    def import_path(self, path):
        entry = self.library.import_path(path)
        self.search.set('')
        self.refresh_library(entry.id)
        self.status.set('Preset imported as local JSON metadata. No target save was changed; preview is required.')
        return entry

    def import_dialog(self):
        paths = filedialog.askopenfilenames(parent=self.root, title='Import reusable resource presets',
                                          filetypes=[('Reusable editing presets', '*' + presets.SUFFIX)])
        if paths:
            try:
                self.import_paths(tuple(paths))
            except Exception as error:
                return self._error('Cannot Import Preset', error)

    def import_paths(self, paths):
        if type(paths) not in (tuple, list) or not 0 < len(paths) <= 64:
            raise SaveError('Import between 1 and 64 preset metadata files at a time.')
        prepared = tuple(presets.load(path) for path in paths)
        saved = []
        try:
            for preset in prepared:
                saved.append(self.library.save(preset))
        except Exception as error:
            self.refresh_library()
            raise SaveError(f'Import stopped after {len(saved)} local preset documents were saved. '
                            'Existing and completed metadata was retained.\n\n' + str(error)) from error
        self.search.set('')
        self.refresh_library(saved[-1].id)
        self.status.set(f'{len(saved)} resource presets imported. No target save was changed.')
        return tuple(saved)

    def export_dialog(self):
        try:
            if self._entry is None:
                raise SaveError('Select a named preset to export.')
            selected = self.catalog.selection()
            entries = tuple(entry for entry in self.entries if entry.id in selected)
            if len(entries) > 1:
                folder = filedialog.askdirectory(parent=self.root, title='Export selected preset metadata to folder')
                if not folder:
                    return False
                self.export_entries(entries, folder)
                return True
            entry = self._entry
            path = filedialog.asksaveasfilename(parent=self.root, title='Export reusable resource preset',
                                              initialfile='resource-preset' + presets.SUFFIX,
                                              defaultextension=presets.SUFFIX, confirmoverwrite=False,
                                              filetypes=[('Reusable editing presets', '*' + presets.SUFFIX)])
            if not path:
                return False
            destination = self.library.export(entry, path)
            self.status.set('Reusable preset exported: ' + destination.name)
            return True
        except Exception as error:
            return self._error('Cannot Export Preset', error)

    def export_entries(self, entries, directory):
        if type(entries) not in (tuple, list) or not 0 < len(entries) <= 64:
            raise SaveError('Export between 1 and 64 selected presets at a time.')
        completed = []
        try:
            for entry in entries:
                destination = Path(directory) / (entry.preset.game_id + '-' + entry.id[:12] + presets.SUFFIX)
                completed.append(self.library.export(entry, destination))
        except Exception as error:
            raise SaveError(f'Export stopped after {len(completed)} metadata files. '
                            'Existing and completed files were retained.\n\n' + str(error)) from error
        self.status.set(f'{len(completed)} reusable preset documents exported. No game save was written.')
        return tuple(completed)

    def prepare_preview(self):
        self._invalidate()
        try:
            if self._entry is None:
                raise SaveError('Select a named preset first.')
            editor = self._editor()
            self.library.validate_entry(self._entry)
            plan = presets.prepare(editor.adapter, editor.document, dict(editor.changes),
                                   self._entry.preset, tuple(self.assignments.selection()))
            before, after = dict(plan.pending), dict(plan.result)
            for index, row in enumerate(plan.rows):
                field = row.field
                effect = ('Keep existing edit' if not row.imported else
                          'No change' if type(row.before) is type(row.after) and row.before == row.after else
                          'Revert to opened' if field.id not in after else 'Stage preset value')
                self.preview.insert('', 'end', iid=str(index), values=(
                    field.label + ' / ' + editor.record_name(field),
                    editor.display_value(field, row.opened, changes={}),
                    editor.display_value(field, row.before, changes=before),
                    editor.display_value(field, row.after, changes=after), effect))
            self._plan, self._target = plan, editor
            self.tabs.select(1)
            self.apply_button.configure(state='normal' if plan.pending != plan.result else 'disabled')
            warning = f' Experimental values: {plan.experimental_count}.' if plan.experimental_count else ''
            self.status.set(f'{len(plan.selected)} selected assignments; {len(plan.rows)} complete preview rows, '
                            f'including unrelated pending edits. No save file written.' + warning)
            return True
        except Exception as error:
            return self._error('Cannot Preview Preset', error)

    def apply_preview(self):
        try:
            plan, editor = self._plan, self._editor()
            if (plan is None or editor is not self._target or self._entry is None
                    or self._entry.preset != plan.preset
                    or tuple(sorted(self.assignments.selection())) != plan.selected):
                raise SaveError('Preset selection or target changed. Preview the complete result again.')
            self.library.validate_entry(self._entry)
            presets.apply_plan(plan, editor)
            editor.status.set('Reusable resource preset staged. Undo reverses this batch; Save As writes a new copy.')
            self._invalidate()
            self.status.set('Reviewed selection staged as one Undo action. No game file was written.')
            return True
        except Exception as error:
            self._invalidate()
            return self._error('Cannot Apply Preset', error)

    def open_source_presets(self):
        try:
            from koei_editor.shared.preset_gui import open_presets
            return open_presets(self._editor())
        except Exception as error:
            return self._error('Cannot Open Source-bound Presets', error)

    def bulk_dialog(self):
        try:
            if self._entry is None:
                raise SaveError('Select a named preset and its assignments first.')
            selected = tuple(sorted(self.assignments.selection()))
            if not selected:
                raise SaveError('Select at least one preset assignment.')
            self.library.validate_entry(self._entry)
            return BulkPresetDialog(self, self._entry, selected)
        except Exception as error:
            return self._error('Cannot Open Bulk Preset', error)


class BulkPresetDialog:
    """Explicit target selection and complete per-copy previews before staging."""

    def __init__(self, workspace, entry, selected):
        self.workspace, self.entry, self.selected = workspace, entry, selected
        self.sessions = dict(workspace._sessions)
        self.batch = None
        self.window = tk.Toplevel(workspace.root)
        self.window.title('Apply preset to selected save copies')
        self.window.geometry('1100x700')
        self.window.transient(workspace.root)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(2, weight=1)
        self.status = tk.StringVar(self.window, value='Select target editors. Every selected copy must pass validation.')
        ttk.Label(self.window, text=entry.preset.name + f' · {len(selected)} selected assignments',
                  padding=12).grid(row=0, column=0, sticky='w')
        targets_holder = ttk.Frame(self.window, padding=(12, 0))
        targets_holder.grid(row=1, column=0, sticky='ew')
        self.targets = workspace._table(targets_holder, ('target', 'profile'), ('Target editor', 'Game / platform'), 'extended')
        self.targets.configure(height=5)
        for index, (label, editor) in enumerate(self.sessions.items()):
            self.targets.insert('', 'end', iid=str(index), values=(label, editor.adapter.game_id))
        self.targets.bind('<<TreeviewSelect>>', self.invalidate)
        preview_holder = ttk.Frame(self.window, padding=12)
        preview_holder.grid(row=2, column=0, sticky='nsew')
        self.preview = workspace._table(preview_holder, ('target', 'field', 'opened', 'before', 'after', 'effect'),
                                        ('Target', 'Field / record', 'Opened', 'Currently staged', 'After apply', 'Effect'))
        controls = ttk.Frame(self.window, padding=12)
        controls.grid(row=3, column=0, sticky='ew')
        ttk.Button(controls, text='Preview selected editors', command=self.prepare).pack(side='left')
        self.apply_button = ttk.Button(controls, text='Apply reviewed batch', command=self.apply, state='disabled')
        self.apply_button.pack(side='left', padx=8)
        ttk.Button(controls, text='Close', command=self.window.destroy).pack(side='right')
        ttk.Label(self.window, textvariable=self.status, wraplength=1020, padding=(12, 0, 12, 8)).grid(row=4, column=0, sticky='w')
        ttk.Label(self.window, text='Each changed editor receives one Undo action. Review and Save As separately in each editor.',
                  padding=(12, 0, 12, 12)).grid(row=5, column=0, sticky='w')
        self.window.grab_set()

    def invalidate(self, _event=None):
        self.batch = None
        self.apply_button.configure(state='disabled')
        self.preview.delete(*self.preview.get_children())

    def chosen_targets(self):
        items = tuple(self.sessions.items())
        return tuple(items[int(identity)] for identity in self.targets.selection())

    def prepare(self):
        self.invalidate()
        try:
            self.workspace.library.validate_entry(self.entry)
            batch = presets.prepare_batch(self.entry.preset, self.chosen_targets(), self.selected)
            for target in batch.targets:
                before, after = dict(target.plan.pending), dict(target.plan.result)
                for row in target.plan.rows:
                    editor, field = target.editor, row.field
                    effect = ('Keep existing edit' if not row.imported else
                              'No change' if type(row.before) is type(row.after) and row.before == row.after else
                              'Revert to opened' if field.id not in after else 'Stage preset value')
                    self.preview.insert('', 'end', values=(target.label,
                        field.label + ' / ' + editor.record_name(field),
                        editor.display_value(field, row.opened, changes={}),
                        editor.display_value(field, row.before, changes=before),
                        editor.display_value(field, row.after, changes=after), effect))
            self.batch = batch
            changed = sum(target.plan.pending != target.plan.result for target in batch.targets)
            experimental = sum(target.plan.experimental_count for target in batch.targets)
            self.apply_button.configure(state='normal' if changed else 'disabled')
            self.status.set(f'{len(batch.targets)} validated editors; {changed} will change; '
                            f'{experimental} experimental values. Review every target row before Apply.')
            return True
        except Exception as error:
            self.invalidate()
            self.status.set(str(error))
            return self.workspace._error('Cannot Preview Bulk Preset', error)

    def apply(self):
        try:
            if (self.batch is None
                    or tuple((target.label, target.editor) for target in self.batch.targets) != self.chosen_targets()):
                raise SaveError('Target selection changed. Preview all selected copies again.')
            self.workspace.library.validate_entry(self.entry)
            count = len(self.batch.targets)
            presets.apply_batch(self.batch)
            self.invalidate()
            self.workspace._invalidate()
            self.status.set(f'Preset staged in {count} editors. Undo in each changed editor reverses its batch. No save file written.')
            return True
        except Exception as error:
            self.invalidate()
            self.status.set(str(error))
            return self.workspace._error('Cannot Apply Bulk Preset', error)

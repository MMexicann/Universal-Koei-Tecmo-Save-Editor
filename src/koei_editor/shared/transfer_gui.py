"""Select a separate source copy, review selected semantic values, stage once."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_transfer
from koei_editor.shared.table_tools import attach_sorting


class TransferDialog:
    def __init__(self, editor, *, source_path=None, selected_ids=(),
                 comparison_selection_count=None, comparison_skipped_rows=(),
                 expected_source_sha256=None):
        self.editor = editor
        self.adapter, self.target = editor.adapter, editor.document
        self.source = self.available = self.plan = None
        self.selected = set()
        self.expected_source_sha256 = expected_source_sha256
        self.window = tk.Toplevel(editor.root)
        self.window.title('Selective Save-to-Save Transfer')
        self.window.geometry('1140x720')
        self.window.minsize(800, 500)
        self.window.transient(editor.root)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        ttk.Label(self.window, text='Destination: the opened save copy. Choose a separate source from the same '
                  'qualified game/platform and native revision. Select individual values, then preview. '
                  'Original saves and ownership are preserved.', wraplength=1080, padding=15).pack(anchor='w')
        bar = ttk.Frame(self.window, padding=(15, 0, 15, 10))
        bar.pack(fill='x')
        ttk.Button(bar, text='Open Source Copy...', command=self.choose_source).pack(side='left')
        self.source_name = tk.StringVar(self.window, value='No source selected')
        ttk.Label(bar, textvariable=self.source_name).pack(side='left', padx=10)
        self.summary = tk.StringVar(self.window, value='Supported: reviewed fixed resources, Conquest gallery statistics, '
                                    'WO3U mount equipment references, and Gundam named-pilot skills/loadouts.')
        ttk.Label(self.window, textvariable=self.summary, wraplength=1080, padding=(15, 0, 15, 10)).pack(anchor='w')
        self.tabs = ttk.Notebook(self.window)
        self.tabs.pack(fill='both', expand=True, padx=15)
        fields = ttk.Frame(self.tabs)
        self.tabs.add(fields, text='Select values')
        search = ttk.Frame(fields, padding=(0, 8))
        search.pack(fill='x')
        ttk.Label(search, text='Find').pack(side='left')
        self.query = tk.StringVar(self.window)
        ttk.Entry(search, textvariable=self.query).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(search, text='Select Visible', command=self.select_visible).pack(side='left')
        ttk.Button(search, text='Clear Selection', command=self.clear_selection).pack(side='left', padx=8)
        self.choices = self._table(fields, ('category', 'field', 'source', 'target'),
                                    ('Category', 'Native field / record', 'Source value', 'Destination opened'))
        preview = ttk.Frame(self.tabs)
        self.tabs.add(preview, text='Complete preview')
        self.preview = self._table(preview, ('field', 'opened', 'current', 'after', 'effect'),
                                   ('Destination field', 'Opened', 'Current pending', 'After transfer', 'Effect'))
        excluded = ttk.Frame(self.tabs)
        self.tabs.add(excluded, text='Exclusions')
        self.exclusions = self._table(excluded, ('field', 'reason'), ('Field / record', 'Reason excluded'))
        footer = ttk.Frame(self.window, padding=15)
        footer.pack(fill='x')
        self.preview_button = ttk.Button(footer, text='Preview Selected Values', command=self.prepare_preview, state='disabled')
        self.preview_button.pack(side='left')
        self.apply_button = ttk.Button(footer, text='Apply Reviewed Transfer', command=self.apply_preview, state='disabled')
        self.apply_button.pack(side='left', padx=10)
        ttk.Button(footer, text='Close', command=self.close).pack(side='right')
        self.count = tk.StringVar(self.window, value='0 selected')
        ttk.Label(footer, textvariable=self.count).pack(side='left')
        ttk.Label(self.window, text='Apply stages the reviewed result as one Undo action. No game file is written. '
                  'Review Changes and Save As remain available in the editor.', padding=(15, 0, 15, 12)).pack(anchor='w')
        self.query.trace_add('write', self.filter_rows)
        self.choices.bind('<<TreeviewSelect>>', self.selection_changed)
        editor.apply_theme(editor.theme_name.get())
        if source_path is not None:
            self.load_source(source_path, selected_ids=selected_ids,
                             comparison_selection_count=comparison_selection_count,
                             comparison_skipped_rows=comparison_skipped_rows)

    def _table(self, parent, columns, headings):
        body = ttk.Frame(parent)
        body.pack(fill='both', expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        tree = ttk.Treeview(body, columns=columns, show='headings', selectmode='extended')
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=260 if column in ('field', 'reason') else 150, minwidth=100)
        tree.grid(row=0, column=0, sticky='nsew')
        y = ttk.Scrollbar(body, orient='vertical', command=tree.yview)
        y.grid(row=0, column=1, sticky='ns')
        x = ttk.Scrollbar(body, orient='horizontal', command=tree.xview)
        x.grid(row=1, column=0, sticky='ew')
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        attach_sorting(tree)
        return tree

    def close(self):
        self.window.destroy()

    def _session(self):
        if self.editor.adapter is not self.adapter or self.editor.document is not self.target:
            raise SaveError('The destination editor session changed. Open Transfer again.')

    def _clear_preview(self):
        self.plan = None
        self.preview.delete(*self.preview.get_children())
        self.apply_button.configure(state='disabled')

    def choose_source(self):
        path = filedialog.askopenfilename(parent=self.window, title='Open Separate Transfer Source Copy',
                initialdir=self.target.source.parent, filetypes=[('Selected profile save copy', '*' + self.adapter.extension)])
        if path:
            # A manually chosen source begins a fresh transfer selection and
            # is no longer constrained to the earlier comparison snapshot.
            self.expected_source_sha256 = None
            return self.load_source(path)
        return False

    def load_source(self, path, *, selected_ids=(), comparison_selection_count=None,
                    comparison_skipped_rows=()):
        self._clear_preview()
        for key in getattr(self, '_choice_ids', ()):
            if self.choices.exists(key):
                self.choices.delete(key)
        self.exclusions.delete(*self.exclusions.get_children())
        self._choice_ids = []
        self.source = self.available = None
        self.selected.clear()
        self.count.set('0 selected')
        self.preview_button.configure(state='disabled')
        try:
            if not isinstance(selected_ids, (tuple, list, set, frozenset)):
                raise SaveError('Comparison handoff must contain distinct mapped field IDs.')
            requested = tuple(selected_ids)
            if (any(type(key) is not str for key in requested)
                    or len(requested) != len(set(requested))):
                raise SaveError('Comparison handoff must contain distinct mapped field IDs.')
            if (comparison_selection_count is not None
                    and (type(comparison_selection_count) is not int
                         or comparison_selection_count < len(requested))):
                raise SaveError('The comparison selection count is invalid.')
            if (not isinstance(comparison_skipped_rows, (tuple, list))
                    or any(not isinstance(row, (tuple, list)) or len(row) != 2
                           or type(row[0]) is not str or type(row[1]) is not str
                           or not row[0] or row[1] not in ('definition_changed', 'available_in_first',
                                                          'available_in_second')
                           for row in comparison_skipped_rows)):
                raise SaveError('Skipped comparison rows must retain their mapped IDs and non-value-change status.')
            skipped = tuple(comparison_skipped_rows)
            if len({row[0] for row in skipped}) != len(skipped):
                raise SaveError('Skipped comparison rows must contain distinct field IDs.')
            if set(row[0] for row in skipped).intersection(requested):
                raise SaveError('A comparison field cannot be both a value-change candidate and a skipped row.')
            self._session()
            source = self.adapter.read_save(path)
            if (self.expected_source_sha256 is not None
                    and source.sha256 != self.expected_source_sha256):
                raise SaveError('The comparison source changed after review. Compare the copies again.')
            available = save_transfer.catalogue(self.adapter, source, self.target)
            self.source, self.available = source, available
            choice_ids = {choice.id for choice in available.choices}
            eligible = set(requested).intersection(choice_ids)
            for choice in available.choices:
                label = choice.target_field.label + ' / ' + self.editor.record_name(choice.target_field)
                self.choices.insert('', 'end', iid=choice.id, values=(choice.category, label, choice.source_value, choice.target_value))
                self._choice_ids.append(choice.id)
            for item in available.exclusions:
                self.exclusions.insert('', 'end', values=(item.field, item.reason))
            for key in sorted(set(requested).difference(choice_ids)):
                reason = next((item.reason for item in available.exclusions
                               if item.field == key or item.field.endswith(' ' + key)),
                              'This field ID is not present in the reviewed transfer catalogue.')
                self.exclusions.insert('', 'end', values=('Comparison selection · ' + key, reason))
            skipped_labels = {'definition_changed': 'Record definition changed',
                              'available_in_first': 'Available in first',
                              'available_in_second': 'Available in second'}
            for key, status in skipped:
                self.exclusions.insert(
                    '', 'end',
                    values=(f'Comparison selection · {key} ({skipped_labels[status]})',
                            'This row is not an ordinary value change, so it was not sent to the transfer catalogue or preselected.'))
            self.source_name.set(source.source.name)
            comparison_exclusions = len(set(requested).difference(choice_ids)) + len(skipped)
            summary = (f'{len(available.choices):,} compatible values; {len(available.exclusions) + comparison_exclusions:,} exclusions. '
                       'Equipment entries transfer existing references only. Select the fields to copy.')
            if comparison_selection_count is not None:
                value_changes = len(requested)
                unsupported_rows = len(skipped)
                if comparison_selection_count != value_changes + unsupported_rows:
                    raise SaveError('Selected comparison rows do not match their handoff candidates and exclusions.')
                summary += (f' Comparison handoff: {comparison_selection_count:,} rows selected; '
                            f'{value_changes:,} value-change IDs checked; {len(eligible):,} IDs approved by the transfer catalogue and preselected; '
                            f'{value_changes - len(eligible):,} candidates excluded. '
                            f'{unsupported_rows:,} non-value-change rows were not considered for transfer. '
                            'The catalogue and complete transfer preview control every staged value.')
            self.preview_button.configure(state='normal')
            self.filter_rows()
            if eligible:
                self._selection(eligible)
                self.choices.selection_set(tuple(eligible & set(self.choices.get_children())))
            return True
        except Exception as error:
            self.source_name.set('No source selected')
            messagebox.showerror('Cannot Open Transfer Source', str(error), parent=self.window)
            return False

    def _selection(self, selected):
        selected = set(selected)
        if selected != self.selected:
            self._clear_preview()
        self.selected = selected
        self.count.set(f'{len(selected):,} selected')

    def selection_changed(self, _event=None):
        visible = set(self.choices.get_children())
        self._selection((self.selected - visible) | set(self.choices.selection()))

    def select_visible(self):
        self._selection(self.selected | set(self.choices.get_children()))
        self.choices.selection_add(self.choices.get_children())

    def clear_selection(self):
        self._selection(())
        self.choices.selection_remove(self.choices.selection())

    def filter_rows(self, *_args):
        self.selection_changed()
        tokens = self.query.get().casefold().split()
        for key in getattr(self, '_choice_ids', ()):
            text = (key + ' ' + ' '.join(map(str, self.choices.item(key, 'values')))).casefold()
            if all(token in text for token in tokens):
                self.choices.move(key, '', 'end')
            else:
                self.choices.detach(key)
        # Tk drops detached rows from selection(). Keep the explicit selection
        # independently and project only its visible members into the widget.
        self.choices.selection_set(tuple(self.selected & set(self.choices.get_children())))

    def prepare_preview(self):
        self._clear_preview()
        try:
            self._session()
            plan = save_transfer.prepare(self.adapter, self.source, self.target, dict(self.editor.changes),
                                          tuple(self.selected))
            for row in plan.rows:
                effect = ('Keep existing edit' if not row.imported else
                          'No change' if type(row.before) is type(row.after) and row.before == row.after else
                          'Revert to opened value' if row.field.id not in dict(plan.result) else 'Transfer selected value')
                self.preview.insert('', 'end', values=(row.field.label + ' / ' + self.editor.record_name(row.field),
                        self.editor.display_value(row.field, row.opened, changes={}),
                        self.editor.display_value(row.field, row.before, changes=dict(plan.pending)),
                        self.editor.display_value(row.field, row.after, changes=dict(plan.result)), effect))
            self.plan = plan
            self.summary.set(f'{len(plan.selected):,} selected values; {len(plan.result):,} total staged edits afterward. '
                             'The complete result passed native dependency checks and serialized read-back. '
                             'Review every row before applying.' +
                             (f' EXPERIMENTAL: {plan.experimental_count:,} values above supported limits.'
                              if plan.experimental_count else ''))
            self.apply_button.configure(state='normal' if plan.pending != plan.result else 'disabled')
            self.tabs.select(1)
            return True
        except Exception as error:
            messagebox.showerror('Cannot Preview Transfer', str(error), parent=self.window)
            return False

    def apply_preview(self):
        try:
            self._session()
            if self.plan is None or tuple(sorted(self.selected)) != self.plan.selected:
                raise SaveError('The selection changed. Prepare a fresh transfer preview.')
            result = save_transfer.confirm(self.plan, self.editor.adapter, self.editor.document, dict(self.editor.changes))
            original, history = dict(self.editor.changes), [dict(item) for item in self.editor.history]
            try:
                self.editor._accept_pending(result)
                save_transfer.validate_sources(self.plan)
            except Exception:
                self.editor.changes = original
                self.editor.history[:] = history
                try:
                    self.editor.refresh()
                except Exception:
                    pass
                self.editor.status.set('Transfer was not staged. Original pending edits and Undo history were retained.')
                raise
        except Exception as error:
            self._clear_preview()
            messagebox.showerror('Cannot Apply Transfer', str(error), parent=self.window)
            return False
        self._clear_preview()
        self.editor.status.set('Transfer staged. Undo reverses the whole transfer. Use Save As... to write a new copy.')
        self.summary.set('Transfer staged as one Undo action. No game file was written. Review Changes or Save As in the editor.')
        return True


def open_transfer(editor, *, source_path=None, selected_ids=(),
                  comparison_selection_count=None, comparison_skipped_rows=(),
                  expected_source_sha256=None):
    if editor.document is None:
        messagebox.showinfo('Save Transfer', 'Open a separate destination save copy first.', parent=editor.root)
        return None
    return TransferDialog(editor, source_path=source_path, selected_ids=selected_ids,
                          comparison_selection_count=comparison_selection_count,
                          comparison_skipped_rows=comparison_skipped_rows,
                          expected_source_sha256=expected_source_sha256)

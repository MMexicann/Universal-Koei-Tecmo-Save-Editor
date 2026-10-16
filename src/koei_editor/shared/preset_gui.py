"""A reviewed, deliberately confirmed preset workflow for scalar editors."""
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import edit_presets
from koei_editor.shared.table_tools import attach_sorting, sort_table


class PresetDialog:
    """Use the editor's bound adapter and single-action pending/Undo commit."""

    def __init__(self, editor):
        self.editor = editor
        self.plan = None
        self.rows = []
        self.window = tk.Toplevel(editor.root)
        self.window.title('Reviewed Edit Presets')
        self.window.geometry('1120x650')
        self.window.minsize(760, 450)
        self.window.transient(editor.root)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.scope = tk.StringVar(self.window, value=(
            'Presets reuse staged edits on the exact original save, including a byte-identical copy. '
            'They cannot transfer inventory or progress to a different save.'))
        ttk.Label(self.window, textvariable=self.scope, padding=15, wraplength=1050).pack(anchor='w')
        bar = ttk.Frame(self.window, padding=(15, 0, 15, 10))
        bar.pack(fill='x')
        ttk.Button(bar, text='Import Preset...', command=self.import_preset).pack(side='left')
        ttk.Button(bar, text='Export All Staged Edits...', command=self.export_staged).pack(side='left', padx=8)
        ttk.Label(bar, text='JSON plans only. Use Save As... to create an edited game save.',
                  style='Muted.TLabel').pack(side='left', padx=8)
        self.summary = tk.StringVar(self.window, value='Import a preset to preview its complete result before staging.')
        ttk.Label(self.window, textvariable=self.summary, padding=(15, 0, 15, 10),
                  wraplength=1050).pack(anchor='w')
        search_bar = ttk.Frame(self.window, padding=(15, 0, 15, 8))
        search_bar.pack(fill='x')
        ttk.Label(search_bar, text='Find fields').pack(side='left', padx=(0, 8))
        self.query = tk.StringVar(self.window)
        self.search_entry = ttk.Entry(search_bar, textvariable=self.query)
        self.search_entry.pack(side='left', fill='x', expand=True)
        ttk.Button(search_bar, text='Clear', command=lambda: self.query.set('')).pack(side='left', padx=8)
        self.count = tk.StringVar(self.window, value='0 fields')
        ttk.Label(search_bar, textvariable=self.count).pack(side='left')
        body = ttk.Frame(self.window, padding=(15, 0))
        body.pack(fill='both', expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(body, columns=('field', 'opened', 'before', 'after', 'action'), show='headings')
        for key, title, width in (('field', 'Field / record', 340), ('opened', 'Opened value', 150),
                                  ('before', 'Currently staged', 150), ('after', 'After import', 150),
                                  ('action', 'Effect', 190)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=100, stretch=key != 'field')
        attach_sorting(self.tree)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(body, orient='vertical', command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(body, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        ttk.Label(self.window, text='Apply stages the complete preview as one Undo action, including fields hidden '
                  'by this filter. Existing edits outside the preset are kept. No game file is written.',
                  padding=(15, 10, 15, 0), wraplength=1050).pack(anchor='w')
        footer = ttk.Frame(self.window, padding=15)
        footer.pack(fill='x')
        self.apply_button = ttk.Button(footer, text='Apply Preview to Staged Edits', state='disabled',
                                       command=self.apply_preview)
        self.apply_button.pack(side='left')
        ttk.Button(footer, text='Close', command=self.close).pack(side='right')
        self.query.trace_add('write', self.filter_rows)
        self.window.bind('<Control-f>', self.focus_search)
        self.search_entry.bind('<Escape>', self.clear_search)
        self.window.bind('<Escape>', lambda _event: self.close())
        editor.apply_theme(editor.theme_name.get())

    def close(self):
        self.window.destroy()

    def focus_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, 'end')
        return 'break'

    def clear_search(self, _event=None):
        self.query.set('')
        return 'break'

    def _clear_preview(self):
        self.plan = None
        self.rows = []
        self.tree.delete(*self.tree.get_children())
        # Detached filtered rows must also be removed before another import.
        for identity in getattr(self, '_all_identities', ()):
            if self.tree.exists(identity):
                self.tree.delete(identity)
        self._all_identities = []
        self.apply_button.configure(state='disabled')
        self.count.set('0 fields')
        self.summary.set('Import a preset to preview its complete result before staging.')

    def import_preset(self):
        path = filedialog.askopenfilename(parent=self.window, title='Import Reviewed Edit Preset',
            initialdir=self.editor.document.source.parent if self.editor.document else None,
            filetypes=[('Reviewed edit presets', '*.edits.json')])
        if path:
            self.load_path(path)

    def load_path(self, path):
        self._clear_preview()
        try:
            if self.editor.document is None:
                raise SaveError('Open a separate save copy before importing a preset.')
            preset = edit_presets.load(path)
            plan = edit_presets.prepare(self.editor.adapter, self.editor.document,
                                        dict(self.editor.changes), preset)
            self._show_plan(plan)
        except Exception as error:
            self._clear_preview()
            messagebox.showerror('Cannot Import Preset', str(error), parent=self.window)
            return False
        return True

    def _show_plan(self, plan):
        before, after = dict(plan.pending), dict(plan.result)
        self.plan = plan
        warning = (f'\nEXPERIMENTAL: {plan.experimental_count:,} values above supported limits. '
                   'The save or game may break; the existing Save As confirmation still applies.'
                   if plan.experimental_count else '')
        changed = sum(row.before != row.after or type(row.before) is not type(row.after) for row in plan.rows)
        self.summary.set(f'{plan.preset.name} — {plan.adapter.get_format().title}\n'
                         f'{len(plan.preset.edits):,} imported assignments; {changed:,} pending values change; '
                         f'{len(after):,} total staged edits afterward.\n'
                         f'Exact original SHA-256: {plan.preset.source_sha256}' + warning)
        for row in plan.rows:
            field = row.field
            label = field.label + ' / ' + self.editor.record_name(field)
            opened = self.editor.display_value(field, row.opened, changes={})
            current = self.editor.display_value(field, row.before, changes=before)
            final = self.editor.display_value(field, row.after, changes=after)
            if not row.imported:
                effect = 'Keep existing edit'
            elif row.before == row.after and type(row.before) is type(row.after):
                effect = 'No change'
            elif field.id not in after:
                effect = 'Revert to opened value'
            else:
                effect = 'Stage preset value'
            identity = self.tree.insert('', 'end', values=(label, opened, current, final, effect))
            self.rows.append((identity, ' '.join((label, opened, current, final, effect, field.id,
                                                  field.group, str(row.opened), str(row.before),
                                                  str(row.after))).casefold()))
        self._all_identities = [identity for identity, _text in self.rows]
        self.filter_rows()
        self.apply_button.configure(state='normal' if before != after else 'disabled')

    def filter_rows(self, *_args):
        tokens = self.query.get().casefold().split()
        visible = 0
        for identity, text in self.rows:
            if all(token in text for token in tokens):
                self.tree.move(identity, '', 'end')
                visible += 1
            else:
                self.tree.detach(identity)
        sort_table(self.tree)
        self.count.set(f'{visible:,} of {len(self.rows):,} fields')

    def apply_preview(self):
        try:
            result = edit_presets.confirm(self.plan, self.editor.adapter, self.editor.document,
                                          dict(self.editor.changes))
            # Preserve the complete session if a presentation refresh fails
            # after the shared pending validator accepts the candidate.
            original = dict(self.editor.changes)
            history = [dict(snapshot) for snapshot in self.editor.history]
            try:
                self.editor._accept_pending(result)
                edit_presets.validate_source(self.plan.adapter, self.plan.document)
            except Exception:
                self.editor.changes = original
                self.editor.history[:] = history
                try:
                    self.editor.refresh()
                except Exception:
                    pass  # Keep the original state even if presentation is unavailable.
                self.editor.status.set('Preset was not staged. Original pending edits and Undo history were retained.')
                raise
        except Exception as error:
            self._clear_preview()
            messagebox.showerror('Cannot Apply Preset', str(error), parent=self.window)
            return False
        self.editor.status.set(f'Preset staged: {self.plan.preset.name}. '
                               'Undo reverses the whole import. Use Save As... to write a new game copy.')
        self._clear_preview()
        self.summary.set('Preset applied to staged edits. No game file was written. '
                         'You can close this window, review, Undo, or save a new copy in the editor.')
        return True

    def export_staged(self):
        try:
            if self.editor.document is None:
                raise SaveError('Open a separate save copy before exporting a preset.')
            if not self.editor.changes:
                raise SaveError('Stage at least one field edit before exporting a preset.')
            name = simpledialog.askstring('Name Edit Preset',
                'Name this plan. It contains all staged fields, including hidden edits and editable names.',
                parent=self.window, initialvalue='My edit plan')
            if name is None:
                return False
            adapter, document = self.editor.adapter, self.editor.document
            pending = dict(self.editor.changes)
            preset = edit_presets.create(adapter, document, pending, name)
            path = filedialog.asksaveasfilename(parent=self.window, title='Export Reviewed Edit Preset',
                initialdir=document.source.parent, initialfile=document.source.stem + edit_presets.SUFFIX,
                defaultextension=edit_presets.SUFFIX, filetypes=[('Reviewed edit presets', '*.edits.json')],
                confirmoverwrite=False)
            if not path:
                return False
            if (self.editor.adapter is not adapter or self.editor.document is not document
                    or self.editor.changes != pending):
                raise SaveError('The editor changed while choosing a destination. Export the preset again.')
            destination = edit_presets.export(preset, adapter, document, path)
            self.editor.status.set('Edit preset exported: ' + destination.name)
            self.summary.set('Edit preset exported: ' + destination.name
                             + '\nThis JSON plan is bound to the original copy. It is not an edited game save.')
            return True
        except Exception as error:
            messagebox.showerror('Cannot Export Preset', str(error), parent=self.window)
            return False


def open_presets(editor):
    """Entry point wired by the scalar workspace; DW3's bespoke editor is separate."""
    if editor.document is None:
        messagebox.showinfo('Edit Presets', 'Open a separate save copy first.', parent=editor.root)
        return None
    return PresetDialog(editor)

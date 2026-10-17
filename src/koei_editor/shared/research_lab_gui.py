"""Retained read-only research workspace built on the copied-save comparison UI."""
from pathlib import Path
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared import research_lab as lab
from koei_editor.shared import save_comparison
from koei_editor.shared.comparison_gui import ComparisonWorkspace
from koei_editor.shared.scrollable_panel import ScrollablePanel


class _SourcesChanged(lab.SaveError):
    """A worker could not requalify the original save/metadata snapshots."""


class ResearchLabWorkspace(ComparisonWorkspace):
    def __init__(self, root, parent):
        self.viewport = ScrollablePanel(parent)
        super().__init__(root, self.viewport.content, scrollable=False)
        content = self.frame
        content.pack(fill='both', expand=True)
        for child in self.frame.winfo_children():
            if isinstance(child, ttk.Label) and child.cget('text') == 'COMPARE SAVES':
                child.configure(text='SAVE RESEARCH LAB')
        self.compare_button.configure(text='Compare for research')
        self.export_button.configure(text='Export for Codex…')
        self.table.configure(height=5)
        self.annotations, self.last_query, self.last_offset, self.last_length = (), None, None, 8
        self.offset, self.span = tk.StringVar(root, value='0x0'), tk.StringVar(root, value='64')
        self.tabs = ttk.Notebook(self.frame)
        self.tabs.pack(fill='both', expand=True, pady=(10, 0))
        runs_tab, offset_tab, candidates_tab, notes_tab = [ttk.Frame(self.tabs, padding=8) for _ in range(4)]
        for tab, title in ((runs_tab, 'Decoded changes'), (offset_tab, 'Offset analysis'),
                           (candidates_tab, 'Candidate discovery'), (notes_tab, 'Annotations')):
            self.tabs.add(tab, text=title)
        self.run_status = tk.StringVar(root, value='Compare copies to inspect decoded changes.')
        ttk.Label(runs_tab, textvariable=self.run_status).pack(anchor='w')
        self.runs = self._tree(runs_tab, ('offset', 'length', 'before', 'after', 'mapped'),
                               ('Decoded offset', 'Length', 'First hex (up to 32 bytes)',
                                'Second hex (up to 32 bytes)', 'Mapped storage overlap'))
        self.runs.bind('<Double-1>', self.jump_run)
        form = ttk.Frame(offset_tab); form.pack(fill='x')
        for title, variable, width in (('Decoded offset', self.offset, 14), ('Window bytes (1–4096)', self.span, 8)):
            ttk.Label(form, text=title).pack(side='left', padx=(0, 8))
            ttk.Entry(form, textvariable=variable, width=width).pack(side='left', padx=(0, 12))
        self.inspect_button = ttk.Button(form, text='Inspect offset', command=self.inspect)
        self.inspect_button.pack(side='left'); self.controls.append(self.inspect_button)
        self.offset_summary = tk.StringVar(root, value='Offsets address decoded payloads, not native encrypted files.')
        ttk.Label(offset_tab, textvariable=self.offset_summary, wraplength=1000).pack(anchor='w', pady=6)
        self.hex_rows = self._tree(offset_tab, ('offset', 'first', 'second', 'changed'),
                                   ('Offset', 'First decoded hex', 'Second decoded hex', 'Changed byte indexes'))
        self.interpretations = self._tree(offset_tab, ('side', 'width', 'order', 'unsigned', 'signed', 'float'),
                                          ('Copy', 'Bytes', 'Byte order', 'Unsigned integer', 'Signed integer', 'Float'), height=3)
        self.table.bind('<Double-1>', self.jump_field)
        ttk.Label(candidates_tab, text='Exact numeric correlations are unverified hypotheses. Use a controlled '
                  'game action, repeat with independent pairs and unchanged controls.', wraplength=1000).pack(anchor='w')
        candidate_form = ttk.Frame(candidates_tab); candidate_form.pack(fill='x', pady=6)
        self.observed_before, self.observed_after = tk.StringVar(root), tk.StringVar(root)
        self.byteorder, self.widths = tk.StringVar(root, value='little'), tk.StringVar(root, value='1,2,4,8')
        self.alignment = tk.StringVar(root, value='1')
        self.signed = tk.BooleanVar(root, value=False)
        for index, (title, variable, width) in enumerate((('Before', self.observed_before, 12), ('After', self.observed_after, 12),
                                       ('Widths', self.widths, 9), ('Alignment', self.alignment, 5))):
            row, column = index // 2, (index % 2) * 2
            ttk.Label(candidate_form, text=title).grid(row=row, column=column, sticky='w', padx=(0, 6), pady=3)
            ttk.Entry(candidate_form, textvariable=variable, width=width).grid(row=row, column=column + 1, sticky='w', padx=(0, 10), pady=3)
        ttk.Combobox(candidate_form, textvariable=self.byteorder, values=('little', 'big'),
                     state='readonly', width=7).grid(row=2, column=0, sticky='w', pady=3)
        ttk.Checkbutton(candidate_form, text='Signed', variable=self.signed).grid(row=2, column=1, sticky='w', padx=8, pady=3)
        self.find_button = ttk.Button(candidate_form, text='Find candidates', command=self.find_candidates)
        self.find_button.grid(row=2, column=2, columnspan=2, sticky='w', pady=3); self.controls.append(self.find_button)
        self.candidate_status = tk.StringVar(root, value='Searches both qualified decoded payloads; no edit action is available.')
        ttk.Label(candidates_tab, textvariable=self.candidate_status).pack(anchor='w')
        self.candidates = self._tree(candidates_tab, ('offset', 'width', 'before', 'after', 'mapped'),
                                     ('Decoded offset', 'Bytes', 'Before hex', 'After hex', 'Mapped storage overlap'))
        self.candidates.bind('<Double-1>', self.jump_candidate)
        note_form = ttk.Frame(notes_tab); note_form.pack(fill='x')
        self.note_title, self.note_observation, self.note_evidence = tk.StringVar(root), tk.StringVar(root), tk.StringVar(root)
        self.action = tk.StringVar(root)
        for row, (title, variable) in enumerate((('Controlled action / unchanged control', self.action),
                       ('Annotation title', self.note_title), ('Observation / hypothesis', self.note_observation),
                       ('Evidence / next experiment', self.note_evidence))):
            ttk.Label(note_form, text=title).grid(row=row, column=0, sticky='w', padx=(0, 10))
            ttk.Entry(note_form, textvariable=variable).grid(row=row, column=1, sticky='ew', pady=2)
        note_form.columnconfigure(1, weight=1)
        buttons = ttk.Frame(notes_tab); buttons.pack(fill='x', pady=4)
        ttk.Button(buttons, text='Annotate current offset/window', command=self.add_annotation).pack(side='left')
        ttk.Button(buttons, text='Remove selected annotation', command=self.remove_annotation).pack(side='left', padx=8)
        self.notes = self._tree(notes_tab, ('offset', 'length', 'title', 'observation', 'evidence'),
                                ('Decoded offset', 'Length', 'Title', 'Observation / hypothesis', 'Evidence / next experiment'), height=3)
        ttk.Label(self.frame, text='Read-only. Export contains decoded byte excerpts, scalar values and notes. '
                  'Review private research before sharing it with Codex or others.',
                  style='Muted.TLabel', wraplength=1000).pack(anchor='w', pady=6)
        self.content, self.canvas, self.frame = content, self.viewport.canvas, self.viewport.frame

    def apply_theme(self, palette):
        self.canvas.configure(background=ttk.Style(self.root).lookup('TFrame', 'background'))

    def focus_search(self):
        pending = list(self.content.winfo_children())
        while pending:
            widget = pending.pop()
            if isinstance(widget, ttk.Entry) and str(widget.cget('textvariable')) == str(self.search):
                self.canvas.yview_moveto(0)
                widget.focus_set(); widget.selection_range(0, 'end')
                return True
            pending.extend(widget.winfo_children())
        return False

    @staticmethod
    def _tree(parent, columns, titles, height=5):
        frame = ttk.Frame(parent); frame.pack(fill='both', expand=True)
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=height)
        for key, title in zip(columns, titles):
            tree.heading(key, text=title); tree.column(key, width=170, minwidth=60)
        vertical = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        frame.columnconfigure(0, weight=1); frame.rowconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew'); vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        return tree

    def invalidate(self, *_args):
        super().invalidate(*_args)
        if hasattr(self, 'notes'):
            self.annotations, self.last_query, self.last_offset, self.last_length = (), None, None, 8
            self.action.set('')
            for tree in (self.runs, self.hex_rows, self.interpretations, self.candidates, self.notes):
                tree.delete(*tree.get_children())
            self.run_status.set('Selections changed. Compare the copies again.')
            self.candidate_status.set('No candidate search for this pair.')

    @staticmethod
    def _mapped(row):
        return ', '.join(dict.fromkeys(item['id'] for item in row['mapped_spans'])) or 'Unmapped storage'

    def _error(self, error):
        self.status.set('Research failed: ' + str(error))
        messagebox.showerror('Save Research Lab', str(error), parent=self.root)

    def _poll(self):
        try:
            revision, kind, result, error = self._results.get_nowait()
        except queue.Empty:
            self.root.after(30, self._poll); return
        self.busy = False
        for control in self.controls:
            control.configure(state='readonly' if control is self.selector else 'normal')
        if revision != self._revision:
            self.status.set('Selections changed. Compare the copies again.'); return
        if error is not None:
            if kind == 'compare' or isinstance(error, _SourcesChanged):
                self.invalidate()
            self.export_button.configure(state='normal' if self.prepared else 'disabled')
            self._error(error); return
        if kind == 'compare':
            self.prepared, runs = result
            self.refresh()
            self.runs.delete(*self.runs.get_children())
            for index, row in enumerate(runs['runs']):
                self.runs.insert('', 'end', iid=str(index), values=(hex(row['offset']), row['length'],
                    row['first_hex'], row['second_hex'], self._mapped(row)))
            self.run_status.set(f"{runs['total_runs']:,} decoded change runs; first {len(runs['runs']):,} shown. "
                                'Double-click a run or mapped field to inspect its offset.')
            self.status.set(f'{len(self.prepared.rows):,} mapped field differences; '
                            f'{self.prepared.changed_payload_bytes:,} decoded bytes differ; '
                            f'{self.prepared.outside_field_bytes:,} outside editable storage spans.')
        elif kind == 'offset':
            analysis, windows = result
            self.last_offset, self.last_length = analysis['offset'], analysis['length']
            self.offset.set(hex(self.last_offset))
            self.hex_rows.delete(*self.hex_rows.get_children())
            self.interpretations.delete(*self.interpretations.get_children())
            for row in windows:
                self.hex_rows.insert('', 'end', values=(hex(row['offset']), row['first_hex'],
                                     row['second_hex'], ', '.join(map(str, row['changed_indexes']))))
            for row in analysis['interpretations']:
                self.interpretations.insert('', 'end', values=tuple(row.get(key, '') for key in
                                            ('side', 'width', 'byteorder', 'unsigned', 'signed', 'float')))
            self.offset_summary.set(f"Decoded {hex(analysis['offset'])}; XOR: {analysis['xor_hex']}; "
                                    f"{analysis['changed_bits']} changed bits in {analysis['xor_common_bytes']} common bytes. "
                                    'Interpretations are hypotheses; no field mapping is implied.')
            self.tabs.select(1); self.status.set('Decoded offset inspected.')
        elif kind == 'candidates':
            query, matches = result; self.last_query = query
            self.candidates.delete(*self.candidates.get_children())
            for index, row in enumerate(matches['candidates']):
                self.candidates.insert('', 'end', iid=str(index), values=(hex(row['offset']), row['length'],
                    row['first_hex'], row['second_hex'], self._mapped(row)))
            self.candidate_status.set(f"{matches['total_candidates']:,} unverified hypotheses; "
                                      f"first {len(matches['candidates']):,} shown. Correlation does not establish a mapping.")
            self.status.set('Controlled numeric search complete.'); self.tabs.select(2)
        else:
            self.status.set('Private research report saved: ' + Path(result).name)
        self.export_button.configure(state='normal' if self.prepared else 'disabled')

    def compare(self):
        if self.busy:
            return
        game_id = self._games.get(self.game.get())
        if not game_id or not self.first.get() or not self.second.get():
            messagebox.showinfo('Save Research Lab', 'Choose the exact profile and both copied saves.', parent=self.root); return
        first, second = self.first.get(), self.second.get()
        self.invalidate()
        def operation():
            comparison = save_comparison.prepare(game_id, first, second)
            return comparison, lab.changed_runs(comparison)
        self._start(operation, 'compare')

    def _inspect(self, offset, length, field_id=None):
        comparison = self.prepared
        def operation():
            nonlocal offset, length
            if not 1 <= length <= lab.MAX_WINDOW:
                raise lab.SaveError(f'Window bytes must be between 1 and {lab.MAX_WINDOW}.')
            if field_id is not None:
                adapter = save_comparison.adapter_for(comparison.game_id)
                field = adapter.field_map(comparison.right).get(field_id) or adapter.field_map(comparison.left)[field_id]
                offset = field.offset
            length = min(length, max(len(comparison.left.payload), len(comparison.right.payload)) - offset)
            return lab.inspect_offset(comparison, offset, min(length, 8)), lab.byte_window(comparison, offset, length)
        self._start(operation, 'offset')
        self.status.set('Inspecting decoded offset…')

    def inspect(self):
        if self.busy or self.prepared is None:
            return
        try:
            offset, length = int(self.offset.get(), 0), int(self.span.get(), 0)
            self._inspect(offset, length)
        except (ValueError, TypeError) as error:
            self._error(error)

    def jump_run(self, _event=None):
        if not self.busy and self.runs.selection():
            values = self.runs.item(self.runs.selection()[0], 'values')
            self.offset.set(values[0]); self.inspect()

    def jump_candidate(self, _event=None):
        if not self.busy and self.candidates.selection():
            values = self.candidates.item(self.candidates.selection()[0], 'values')
            self.offset.set(values[0]); self.inspect()

    def jump_field(self, _event=None):
        if not self.busy and self.prepared is not None and self.table.selection():
            key = self.prepared.rows[int(self.table.selection()[0])].id
            self._inspect(0, 64, key)

    def find_candidates(self):
        if self.busy or self.prepared is None:
            return
        try:
            query = lab.CandidateQuery(int(self.observed_before.get(), 0), int(self.observed_after.get(), 0),
                    tuple(int(width.strip()) for width in self.widths.get().split(',')), self.byteorder.get(),
                    self.signed.get(), alignment=int(self.alignment.get(), 0))
        except (ValueError, TypeError) as error:
            self._error(error); return
        comparison = self.prepared
        self._start(lambda: (query, lab.discover_candidates(comparison, query)), 'candidates')
        self.status.set('Searching controlled before/after numeric hypotheses…')

    def add_annotation(self):
        if self.busy or self.prepared is None:
            return
        try:
            note = lab.Annotation(int(self.offset.get(), 0), int(self.span.get(), 0), self.note_title.get(),
                                  self.note_observation.get(), self.note_evidence.get())
            self.annotations = lab.validate_annotations(self.prepared, self.annotations + (note,))
        except (ValueError, TypeError, lab.SaveError) as error:
            self._error(error); return
        self._refresh_notes()

    def remove_annotation(self):
        if not self.busy and self.notes.selection():
            index = int(self.notes.selection()[0])
            self.annotations = self.annotations[:index] + self.annotations[index + 1:]
            self._refresh_notes()

    def _refresh_notes(self):
        self.notes.delete(*self.notes.get_children())
        for index, note in enumerate(self.annotations):
            self.notes.insert('', 'end', iid=str(index), values=(hex(note.offset), note.length,
                              note.title, note.observation, note.evidence))

    def export(self):
        if self.busy or self.prepared is None:
            return
        path = filedialog.asksaveasfilename(parent=self.root, title='Export private research for Codex',
                    defaultextension='.json', filetypes=[('Research report', '*.json')], initialfile='SaveResearch.json')
        if path:
            comparison, notes, query = self.prepared, self.annotations, self.last_query
            action, offset, length = self.action.get(), self.last_offset, self.last_length
            def operation():
                try:
                    return lab.export(comparison, path, annotations=notes, query=query,
                                      action=action, offset=offset, length=length)
                except Exception:
                    # Ordinary destination/validation errors must retain notes.
                    # Native qualification stays in this worker, away from Tk.
                    try:
                        save_comparison.validate_sources(comparison)
                    except Exception as error:
                        raise _SourcesChanged(str(error)) from error
                    raise
            self._start(operation, 'research_export')
            self.status.set('Writing private research report…')

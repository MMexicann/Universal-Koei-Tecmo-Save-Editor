"""Asynchronous, read-only discovery with an explicit separate-copy import action."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared import save_detection as backend
from koei_editor.shared.appearance import ui_font

LABELS = {'qualified': 'Ready to import', 'no_saves': 'Installed · no located save',
          'rejected': 'Not qualified', 'ambiguous': 'Choose one installation'}


class SaveDetectionWorkspace:
    def __init__(self, root, parent, on_open=None):
        self.root, self.on_open = root, on_open
        self.frame = ttk.Frame(parent, padding=(26, 18))
        self.busy, self.is_importing, self._closed = False, False, False
        self._revision, self._poll_id = 0, None
        self._cancel, self._results = threading.Event(), queue.SimpleQueue()
        self.prepared = None
        self.page, self.page_size = 0, 100
        self.steam_root, self.search = tk.StringVar(root), tk.StringVar(root)
        self.filter = tk.StringVar(root, value='All supported games')
        self.status = tk.StringVar(root, value='Scan your Steam installation to find supported games and safely qualify captured saves.')
        self.detail = tk.StringVar(root, value='Discovery never edits, repairs, moves or backs up your original live files.')
        ttk.Label(self.frame, text='FIND YOUR SAVES', font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        ttk.Label(self.frame, text='Installed games / verified captured copies / your editor',
                  style='Muted.TLabel').pack(anchor='w', pady=(4, 14))
        form = ttk.Frame(self.frame)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='Steam installation').grid(row=0, column=0, sticky='w', padx=(0, 12))
        self.root_entry = ttk.Entry(form, textvariable=self.steam_root)
        self.root_entry.grid(row=0, column=1, sticky='ew')
        self.browse_button = ttk.Button(form, text='Choose folder...', command=self.browse)
        self.browse_button.grid(row=0, column=2, padx=(10, 0))
        ttk.Label(form, text='Leave blank to use detected Steam installations. Custom libraries listed in libraryfolders.vdf are included.',
                  style='Muted.TLabel', wraplength=1000).grid(row=1, column=1, columnspan=2, sticky='w', pady=(4, 12))
        actions = ttk.Frame(self.frame)
        actions.pack(fill='x')
        self.scan_button = ttk.Button(actions, text='Discover supported saves', style='Primary.TButton', command=self.scan)
        self.scan_button.pack(side='left')
        self.cancel_button = ttk.Button(actions, text='Cancel', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=10)
        self.import_button = ttk.Button(actions, text='Import selected copy...', command=self.import_selected, state='disabled')
        self.import_button.pack(side='left')
        self.controls = (self.root_entry, self.browse_button, self.scan_button)
        self.summary = tk.StringVar(root, value=f'{len(backend.PROFILES)} curated Steam profiles · native validation · separate copies only')
        ttk.Label(self.frame, textvariable=self.summary, style='Section.TLabel').pack(anchor='w', pady=(18, 6))
        ttk.Label(self.frame, textvariable=self.status, wraplength=1000).pack(anchor='w', pady=(0, 10))
        filters = ttk.Frame(self.frame)
        filters.pack(fill='x', pady=(0, 10))
        ttk.Label(filters, text='Search games or files').pack(side='left', padx=(0, 10))
        self.search_entry = ttk.Entry(filters, textvariable=self.search)
        self.search_entry.pack(side='left', fill='x', expand=True)
        ttk.Combobox(filters, textvariable=self.filter, state='readonly',
                     values=('All supported games', 'Ready to import', 'Installed without located saves', 'Not qualified'),
                     width=30).pack(side='left', padx=(10, 0))
        footer = ttk.Frame(self.frame)
        footer.pack(side='bottom', fill='x', pady=(10, 0))
        self.detail_label = ttk.Label(footer, textvariable=self.detail, wraplength=1000, style='Muted.TLabel')
        self.detail_label.pack(anchor='w')
        paging = ttk.Frame(footer)
        paging.pack(fill='x', pady=(8, 0))
        self.previous = ttk.Button(paging, text='Previous', command=lambda: self.change_page(-1), state='disabled')
        self.previous.pack(side='left')
        self.next = ttk.Button(paging, text='Next', command=lambda: self.change_page(1), state='disabled')
        self.next.pack(side='left', padx=10)
        self.page_info = tk.StringVar(root, value='No scan yet')
        ttk.Label(paging, textvariable=self.page_info).pack(side='left')
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill='both', expand=True)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, columns=('game', 'status', 'revision', 'source'),
                                  show='headings', selectmode='browse', height=12)
        for name, label, width in (('game', 'Supported Steam game', 260), ('status', 'Evidence status', 200),
                ('revision', 'Save version', 150), ('source', 'Located original file', 360)):
            self.table.heading(name, text=label)
            self.table.column(name, width=width, minwidth=95, stretch=name in ('game', 'source'))
        self.table.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.bind('<<TreeviewSelect>>', self.selection_changed)
        self.steam_root.trace_add('write', self.invalidate)
        self.search.trace_add('write', self.refilter)
        self.filter.trace_add('write', self.refilter)
        self.frame.bind('<Destroy>', self._destroyed, add='+')
        self.frame.bind('<Configure>', self._resize, add='+')

    def apply_theme(self, palette):
        # All widgets use application ttk styles. Explicit tags make qualification
        # readable without making color the only evidence-status indicator.
        if isinstance(palette, dict):
            self.table.tag_configure('qualified', foreground=palette.get('text', '#243142'))
            self.table.tag_configure('rejected', foreground=palette.get('muted', '#586879'))

    def focus_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, 'end')
        return 'break'

    def has_pending_work(self):
        return self.busy and self.is_importing

    def close(self):
        self._closed = True
        self._cancel.set()
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

    def _destroyed(self, event):
        if event.widget is self.frame:
            self.close()

    def _resize(self, event):
        if event.widget is self.frame:
            self.detail_label.configure(wraplength=max(120, event.width - 52))

    def browse(self):
        path = filedialog.askdirectory(parent=self.root, title='Choose a Steam installation or library', mustexist=True)
        if path:
            self.steam_root.set(path)

    def invalidate(self, *_args):
        self._revision += 1
        self._cancel.set()
        self.prepared = None
        self.page = 0
        self.refresh()

    def refilter(self, *_args):
        self.page = 0
        self.refresh()

    def change_page(self, direction):
        self.page = max(0, self.page + direction)
        self.refresh()

    def refresh(self):
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        entries = () if self.prepared is None else self.prepared.entries
        query, choice = self.search.get().strip().casefold(), self.filter.get()
        visible = []
        for index, entry in enumerate(entries):
            if choice == 'Ready to import' and entry.status != 'qualified':
                continue
            if choice == 'Installed without located saves' and entry.status != 'no_saves':
                continue
            if choice == 'Not qualified' and entry.status not in ('rejected', 'ambiguous'):
                continue
            haystack = f'{entry.title} {entry.source or ""} {entry.game_id} {entry.app_id} {entry.revision}'.casefold()
            if all(token in haystack for token in query.split()):
                visible.append((index, entry))
        self.page = min(self.page, max(0, (len(visible) - 1) // self.page_size))
        start = self.page * self.page_size
        for index, entry in visible[start:start + self.page_size]:
            self.table.insert('', 'end', iid=str(index), values=(entry.title, LABELS[entry.status],
                entry.revision or 'Not qualified', str(entry.source) if entry.source is not None else 'No located save'), tags=(entry.status,))
        if selected and self.table.exists(selected[0]):
            self.table.selection_set(selected[0])
        self.previous.configure(state='normal' if self.page else 'disabled')
        self.next.configure(state='normal' if start + self.page_size < len(visible) else 'disabled')
        self.page_info.set(f'{start + 1 if visible else 0}-{min(start + self.page_size, len(visible))} of {len(visible)} results')
        self.selection_changed()

    def selected_entry(self):
        selected = self.table.selection()
        if self.prepared is None or len(selected) != 1:
            return None
        try:
            return self.prepared.entries[int(selected[0])]
        except (ValueError, IndexError):
            return None

    def selection_changed(self, *_args):
        entry = self.selected_entry()
        self.import_button.configure(state='normal' if entry is not None and entry.status == 'qualified' and not self.busy else 'disabled')
        self.detail.set('Select a result to inspect its evidence status.' if entry is None else entry.summary +
                        (f' {entry.mapped_fields:,} mapped editable fields.' if entry.status == 'qualified' else ''))

    def scan(self):
        text = self.steam_root.get().strip()
        roots = (Path(text),) if text else None
        self._start('scan', lambda cancel: backend.discover(steam_roots=roots, cancel=cancel))

    def import_selected(self):
        entry = self.selected_entry()
        if entry is None or entry.status != 'qualified' or self.busy:
            return
        destination = filedialog.askdirectory(parent=self.root, title='Choose a separate folder for the imported copy', mustexist=True)
        if destination:
            self._start('import', lambda cancel: (entry.game_id, backend.import_copy(entry, destination, cancel)))

    def cancel(self):
        self._cancel.set()
        if self.busy:
            self.status.set('Cancelling safely. Any completed new copies are retained; originals are untouched.')
            self.cancel_button.configure(state='disabled')

    def _start(self, kind, operation):
        if self.busy or self._closed:
            return
        self.busy, self.is_importing = True, kind == 'import'
        revision = self._revision
        self._cancel = cancel = threading.Event()
        for control in self.controls:
            control.configure(state='disabled')
        self.import_button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.status.set('Reading Steam metadata and qualifying separate temporary captures…' if kind == 'scan' else
                        'Rechecking originals, creating a new separate import and validating actual copied bytes…')
        results = self._results
        def worker():
            try:
                results.put((revision, kind, operation(cancel), None, cancel.is_set()))
            except Exception as error:
                results.put((revision, kind, None, error, cancel.is_set()))
        threading.Thread(target=worker, daemon=True).start()
        self._poll_id = self.root.after(30, self._poll)

    def _poll(self):
        self._poll_id = None
        if self._closed:
            return
        try:
            revision, kind, result, error, cancelled = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.root.after(30, self._poll)
            return
        self.busy, self.is_importing = False, False
        for control in self.controls:
            control.configure(state='normal')
        self.cancel_button.configure(state='disabled')
        if cancelled or revision != self._revision:
            self.status.set('Operation cancelled or selections changed. Any newly created imports were retained; originals are untouched.')
        elif error is not None:
            self.status.set('Operation could not complete. Originals are untouched; any newly created copies were retained.')
            messagebox.showerror('Cannot Discover or Import Save', str(error), parent=self.root)
        elif kind == 'scan':
            self.prepared = result
            qualified = sum(entry.status == 'qualified' for entry in result.entries)
            installed = len({entry.app_id for entry in result.entries})
            self.summary.set(f'{installed} installed supported games · {qualified} qualified save copies')
            self.status.set(f'Scan {result.stop_reason}. {len(result.warnings)} metadata/path warnings. '
                            'Choose a qualified result to import a new separate copy.')
            if not result.entries:
                self.status.set('No enabled supported installations were found. Choose the Steam installation folder, '
                                'or use Save Library for existing separate copies. Other stores and Proton paths are not probed.')
            self.refresh()
        else:
            game_id, path = result
            try:
                accepted = self.on_open(game_id, path) if self.on_open is not None else False
            except Exception:
                accepted = False
            self.status.set(f'Imported and opened a separate copy: {path}' if accepted else
                            f'Imported a validated separate copy: {path}. Your current editor session was preserved.')
        self.selection_changed()

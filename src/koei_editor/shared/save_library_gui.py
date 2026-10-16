"""Copied-save browser. Workers perform I/O; only the Tk thread updates widgets."""
from datetime import datetime, timezone
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared import save_library as backend
from koei_editor.shared.appearance import ui_font

STATUS_LABELS = {'qualified': 'Qualified', 'rejected': 'Not qualified', 'unsafe': 'Unsafe path',
                 'oversized': 'Too large', 'changed': 'Changed', 'unreadable': 'Unreadable'}
SORTS = ('Path A-Z', 'Newest first', 'Oldest first', 'Largest first', 'Smallest first', 'Identical files first')


class SaveLibraryWorkspace:
    def __init__(self, root, parent, on_open):
        self.root, self.on_open = root, on_open
        self.frame = ttk.Frame(parent, padding=(28, 16))
        self.busy, self.prepared, self._revision = False, None, 0
        self._closed, self._poll_id = False, None
        self._cancel = threading.Event()
        self._results = queue.SimpleQueue()
        self.page, self.page_size = 0, 100
        self._wrapped_labels = []
        self._games = {game.title + ' · ' + game.subtitle + ' [' + game.platform + ']': game.id
                       for game in backend.LIBRARY_GAMES}
        self.controls = []
        ttk.Label(self.frame, text='SAVE LIBRARY', font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        introduction = ttk.Label(self.frame, text='Find, validate and open your copied saves for one game and platform.',
                                 style='Muted.TLabel', wraplength=1000)
        introduction.pack(anchor='w', pady=(4, 14))
        self._wrapped_labels.append(introduction)
        form = ttk.Frame(self.frame)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        self.game, self.folder = tk.StringVar(root), tk.StringVar(root)
        self.recursive = tk.BooleanVar(root, value=False)
        ttk.Label(form, text='Game and platform').grid(row=0, column=0, sticky='w', padx=(0, 14))
        self.selector = ttk.Combobox(form, textvariable=self.game, values=tuple(self._games), state='readonly')
        self.selector.grid(row=0, column=1, columnspan=2, sticky='ew', pady=6)
        self.controls.append(self.selector)
        ttk.Label(form, text='Copied-save folder').grid(row=1, column=0, sticky='w', padx=(0, 14))
        self.folder_entry = ttk.Entry(form, textvariable=self.folder)
        self.folder_entry.grid(row=1, column=1, sticky='ew', pady=6)
        self.browse_button = ttk.Button(form, text='Browse...', command=self.browse)
        self.browse_button.grid(row=1, column=2, padx=(10, 0))
        self.recursive_button = ttk.Checkbutton(form, text='Include subfolders (up to 3 levels)', variable=self.recursive)
        self.recursive_button.grid(row=2, column=1, sticky='w', pady=(4, 8))
        self.controls.extend((self.folder_entry, self.browse_button, self.recursive_button))
        context_note = ttk.Label(self.frame, text='Keep required original console or account metadata beside each copy. '
                                'Live save folders, Steam Cloud paths, linked files and linked folders are excluded.',
                                style='Muted.TLabel', wraplength=1000)
        context_note.pack(anchor='w', pady=(6, 10))
        self._wrapped_labels.append(context_note)
        actions = ttk.Frame(self.frame)
        actions.pack(fill='x')
        self.scan_button = ttk.Button(actions, text='Scan copied folder', command=self.scan)
        self.scan_button.pack(side='left')
        self.controls.append(self.scan_button)
        self.cancel_button = ttk.Button(actions, text='Cancel scan', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=10)
        self.open_button = ttk.Button(actions, text='Open selected copy', command=self.open_selected, state='disabled')
        self.open_button.pack(side='left')
        self.status = tk.StringVar(root, value='Choose an exact game/platform and a folder containing separate save copies.')
        status_label = ttk.Label(self.frame, textvariable=self.status, wraplength=1000)
        status_label.pack(anchor='w', pady=(12, 8))
        self._wrapped_labels.append(status_label)
        filters = ttk.Frame(self.frame)
        filters.pack(fill='x', pady=(2, 8))
        ttk.Label(filters, text='Find a copy').pack(side='left', padx=(0, 8))
        self.search = tk.StringVar(root)
        self.search_entry = ttk.Entry(filters, textvariable=self.search)
        self.search_entry.pack(side='left', fill='x', expand=True)
        self.filter = tk.StringVar(root, value='All results')
        ttk.Combobox(filters, textvariable=self.filter, values=('All results', 'Qualified', 'Not qualified', 'Identical gameplay files'),
                     state='readonly', width=24).pack(side='left', padx=8)
        self.sort = tk.StringVar(root, value=SORTS[0])
        ttk.Combobox(filters, textvariable=self.sort, values=SORTS, state='readonly', width=22).pack(side='left')
        # Reserve navigation and guidance before the expanding viewport. Tk's
        # pack order otherwise lets the table consume their space at the
        # application's minimum window size.
        self.footer = ttk.Frame(self.frame)
        self.footer.pack(side='bottom', fill='x')
        self.detail = tk.StringVar(root, value='Select a result to see its validation summary.')
        self.detail_label = ttk.Label(self.footer, textvariable=self.detail, wraplength=1000)
        self.detail_label.pack(anchor='w', pady=(8, 4))
        paging = ttk.Frame(self.footer)
        paging.pack(fill='x', pady=(4, 6))
        self.previous = ttk.Button(paging, text='Previous', command=lambda: self.change_page(-1), state='disabled')
        self.previous.pack(side='left')
        self.next = ttk.Button(paging, text='Next', command=lambda: self.change_page(1), state='disabled')
        self.next.pack(side='left', padx=10)
        self.page_info = tk.StringVar(root, value='No scan yet')
        self.page_label = ttk.Label(paging, textvariable=self.page_info)
        self.page_label.pack(side='left')
        self.guidance_label = ttk.Label(self.footer, text='Browse without changing your files. Identical-file groups '
                                       'compare the save files; their original console or account metadata may differ.',
                                       style='Muted.TLabel', wraplength=1000)
        self.guidance_label.pack(anchor='w', pady=(4, 0))
        self._wrapped_labels.extend((self.detail_label, self.guidance_label))
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table_frame, columns=('path', 'size', 'modified', 'status', 'duplicates'),
                                  show='headings', selectmode='browse', height=12)
        for name, title, width in (('path', 'Copied file / relative folder', 330), ('size', 'Bytes', 100),
                ('modified', 'Modified (UTC)', 160), ('status', 'Validation', 150),
                ('duplicates', 'Identical gameplay bytes', 190)):
            self.table.heading(name, text=title)
            self.table.column(name, width=width, minwidth=75, stretch=name == 'path')
        vertical = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.table.bind('<<TreeviewSelect>>', self.selection_changed)
        self.table.bind('<Double-1>', lambda _event: self.open_selected())
        for variable in (self.game, self.folder, self.recursive):
            variable.trace_add('write', self.invalidate)
        for variable in (self.search, self.filter, self.sort):
            variable.trace_add('write', self.refilter)
        self.frame.bind('<Destroy>', self._on_destroy, add='+')
        self.frame.bind('<Configure>', self._resize_guidance, add='+')

    def _resize_guidance(self, event):
        if event.widget is self.frame:
            available = max(120, event.width - 56)
            for label in self._wrapped_labels:
                if int(label.cget('wraplength')) != available:
                    label.configure(wraplength=available)

    def apply_theme(self, palette):
        pass  # Shared ttk styles supply both themes.

    def focus_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, 'end')
        return 'break'

    def _on_destroy(self, event):
        if event.widget is self.frame:
            self.close()

    def close(self):
        self._closed = True
        self._cancel.set()
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

    def invalidate(self, *_args):
        self._revision += 1
        self._cancel.set()
        self.prepared = None
        self.page = 0
        self.refresh()
        if not self.busy:
            self.status.set('Selections changed. Scan the copied folder again.')

    def browse(self):
        path = filedialog.askdirectory(parent=self.root, title='Choose a separate copied-save folder', mustexist=True)
        if path:
            self.folder.set(path)

    def cancel(self):
        if self.busy:
            self._cancel.set()
            self.cancel_button.configure(state='disabled')
            self.status.set('Cancelling after the current file check...')

    def refilter(self, *_args):
        self.page = 0
        self.refresh()

    def change_page(self, direction):
        self.page = max(0, self.page + direction)
        self.refresh()

    @staticmethod
    def _modified(value):
        try:
            return datetime.fromtimestamp(value / 1_000_000_000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OSError, OverflowError):
            return 'Unavailable'

    def refresh(self):
        self.table.delete(*self.table.get_children())
        query, choice = self.search.get().strip().casefold(), self.filter.get()
        entries = () if self.prepared is None else self.prepared.entries
        visible = []
        for index, entry in enumerate(entries):
            if choice == 'Qualified' and entry.status != 'qualified':
                continue
            if choice == 'Not qualified' and entry.status == 'qualified':
                continue
            if choice == 'Identical gameplay files' and not entry.duplicate_group:
                continue
            if query and query not in (entry.relative_path + ' ' + STATUS_LABELS[entry.status]).casefold():
                continue
            visible.append((index, entry))
        order = self.sort.get()
        if order == 'Newest first':
            key = lambda pair: (-pair[1].modified_ns, pair[1].relative_path.casefold())
        elif order == 'Oldest first':
            key = lambda pair: (pair[1].modified_ns, pair[1].relative_path.casefold())
        elif order == 'Largest first':
            key = lambda pair: (-pair[1].size_bytes, pair[1].relative_path.casefold())
        elif order == 'Smallest first':
            key = lambda pair: (pair[1].size_bytes, pair[1].relative_path.casefold())
        elif order == 'Identical files first':
            key = lambda pair: (not bool(pair[1].duplicate_group), pair[1].duplicate_group, pair[1].relative_path.casefold())
        else:
            key = lambda pair: pair[1].relative_path.casefold()
        visible.sort(key=key)
        self.page = min(self.page, max(0, (len(visible) - 1) // self.page_size))
        start = self.page * self.page_size
        end = min(start + self.page_size, len(visible))
        for index, entry in visible[start:end]:
            self.table.insert('', 'end', iid=str(index), values=(entry.relative_path, f'{entry.size_bytes:,}',
                self._modified(entry.modified_ns), STATUS_LABELS[entry.status],
                'Group ' + str(entry.duplicate_group) if entry.duplicate_group else '-'))
        self.previous.configure(state='normal' if self.page else 'disabled')
        self.next.configure(state='normal' if end < len(visible) else 'disabled')
        self.page_info.set(f'{start + 1 if visible else 0:,}-{end:,} of {len(visible):,} matching results')
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
        self.open_button.configure(state='normal' if not self.busy and entry is not None and entry.status == 'qualified' else 'disabled')
        self.detail.set('Select a result to see its validation summary.' if entry is None else
                        entry.summary + (f' {entry.mapped_fields:,} mapped editable fields.' if entry.status == 'qualified' else ''))

    def _start(self, kind, operation):
        if self.busy or self._closed:
            return
        self.busy = True
        revision = self._revision
        self._cancel = cancel = threading.Event()
        for control in self.controls:
            control.configure(state='disabled')
        self.open_button.configure(state='disabled')
        self.cancel_button.configure(state='normal', text='Cancel scan' if kind == 'scan' else 'Cancel open')
        self.status.set('Scanning and qualifying copied saves...' if kind == 'scan' else 'Rechecking the selected save and its original context...')
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
        self.busy = False
        for control in self.controls:
            control.configure(state='readonly' if control is self.selector else 'normal')
        self.cancel_button.configure(state='disabled')
        if revision != self._revision:
            self.status.set('Selections changed. Scan the copied folder again.')
            self.selection_changed()
            return
        # A successful worker result may already be queued when the user
        # cancels, before Tk's next poll. Its captured flag is then stale.
        if kind == 'open' and (cancelled or self._cancel.is_set()):
            self.status.set('Opening cancelled; no editor was opened.')
            self.selection_changed()
            return
        if error is not None:
            self.prepared = None
            self.refresh()
            # Backend exceptions can contain private metadata or local paths;
            # retain a useful generic user message, never an opaque repr.
            message = ('The selected folder could not be scanned safely. Choose ordinary copies outside live/cloud folders.'
                       if kind == 'scan' else 'This copy or its original context changed or could not be requalified. Scan the copied folder again.')
            self.status.set(message)
            messagebox.showerror('Save Library', message, parent=self.root)
            return
        if kind == 'scan':
            self.prepared = result
            self.page = 0
            self.refresh()
            reason = {'complete': 'Scan finished', 'cancelled': 'Scan cancelled (partial results)',
                      'file_limit': 'File limit reached (partial results)', 'entry_limit': 'Directory-entry limit reached (partial results)',
                      'byte_limit': 'Data limit reached (partial results)'}[result.stop_reason]
            self.status.set(f'{reason}: {result.qualified_count:,} qualified of {len(result.entries):,} candidate files; '
                            f'{result.excluded_directories:,} directories excluded. Qualification is specific to the chosen profile.')
        else:
            game_id, path = result
            self.status.set('Copy requalified. Opening through the normal game editor...')
            self.selection_changed()
            try:
                opened = self.on_open(game_id, path)
            except Exception:
                # The application/editor owns its normal open validation.
                # A failed callback must not escape Tk or expose private data.
                message = 'The editor could not open this copy. Check its original context and scan the copied folder again.'
                self.status.set(message)
                messagebox.showerror('Save Library', message, parent=self.root)
                return
            if opened is False:
                self.status.set('Opening cancelled or rejected by the editor. Your previous editor session was kept.')
            elif opened is True:
                self.status.set('Copy opened in its game editor. The original file is unchanged.')
            else:
                self.status.set('Open request sent to the game editor.')

    def scan(self):
        if self.busy:
            return
        game_id = self._games.get(self.game.get())
        if game_id is None or not self.folder.get().strip():
            messagebox.showinfo('Save Library', 'Choose a game/platform and a folder containing separate save copies.', parent=self.root)
            return
        folder, recursive = self.folder.get(), self.recursive.get()
        self.prepared = None
        self.refresh()
        self._start('scan', lambda cancel: backend.scan(game_id, folder, recursive=recursive, cancel=cancel))

    def open_selected(self):
        if self.busy:
            return
        entry = self.selected_entry()
        if entry is None or entry.status != 'qualified':
            return
        prepared = self.prepared
        def operation(cancel):
            document = backend.requalify(prepared, entry, cancel=cancel)
            return prepared.game_id, Path(document.source)
        self._start('open', operation)

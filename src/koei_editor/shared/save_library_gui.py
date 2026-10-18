"""Copied-save browser. Workers perform I/O; only the Tk thread updates widgets."""
from datetime import datetime, timezone
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared import save_library as backend
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.scrollable_panel import ScrollablePanel

STATUS_LABELS = {'qualified': 'Qualified', 'rejected': 'Not qualified', 'unsafe': 'Unsafe path',
                 'oversized': 'Too large', 'changed': 'Changed', 'unreadable': 'Unreadable'}
SORTS = ('Path A-Z', 'Newest first', 'Oldest first', 'Largest first', 'Smallest first', 'Identical files first', 'Validation status')


class SaveLibraryWorkspace:
    def __init__(self, root, parent, on_open, on_manage=None):
        self.root, self.on_open, self.on_manage = root, on_open, on_manage
        self._selected, self._visible, self._rendering = set(), (), False
        self.check_results = {}
        self.management = None
        self._palette = None
        self.frame = ttk.Frame(parent, padding=(28, 12))
        self.busy, self.prepared, self._revision = False, None, 0
        self._closed, self._poll_id, self._layout_id = False, None, None
        self._cancel = threading.Event()
        self._results = queue.SimpleQueue()
        self.page, self.page_size = 0, 100
        self._wrapped_labels = []
        self._games = {game.title + ' · ' + game.subtitle + ' [' + game.platform + ']': game.id
                       for game in backend.LIBRARY_GAMES}
        self.controls = []
        self._action_columns = {}
        self.header = ScrollablePanel(self.frame)
        self.header.frame.pack(fill='x')
        self.header.frame.grid_propagate(False)
        ttk.Label(self.header.content, text='SAVE LIBRARY', font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        introduction = ttk.Label(self.header.content, text='Find, validate and open your copied saves for one game and platform.',
                                 style='Muted.TLabel', wraplength=1000)
        introduction.pack(anchor='w', pady=(2, 6))
        self._wrapped_labels.append(introduction)
        form = ttk.Frame(self.header.content)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        self.game, self.folder = tk.StringVar(root), tk.StringVar(root)
        self.recursive = tk.BooleanVar(root, value=False)
        ttk.Label(form, text='Game and platform').grid(row=0, column=0, sticky='w', padx=(0, 14))
        self.selector = ttk.Combobox(form, textvariable=self.game, values=tuple(self._games), state='readonly')
        self.selector.grid(row=0, column=1, columnspan=2, sticky='ew', pady=3)
        self.controls.append(self.selector)
        ttk.Label(form, text='Copied-save folder').grid(row=1, column=0, sticky='w', padx=(0, 14))
        self.folder_entry = ttk.Entry(form, textvariable=self.folder)
        self.folder_entry.grid(row=1, column=1, sticky='ew', pady=3)
        self.browse_button = ttk.Button(form, text='Browse...', command=self.browse)
        self.browse_button.grid(row=1, column=2, padx=(10, 0))
        self.recursive_button = ttk.Checkbutton(form, text='Include subfolders (up to 3 levels)', variable=self.recursive)
        self.recursive_button.grid(row=2, column=1, sticky='w', pady=(2, 4))
        self.controls.extend((self.folder_entry, self.browse_button, self.recursive_button))
        context_note = ttk.Label(self.header.content, text='Keep required original console or account metadata beside each copy. '
                                'Live save folders, Steam Cloud paths, linked files and linked folders are excluded.',
                                style='Muted.TLabel', wraplength=1000)
        context_note.pack(anchor='w', pady=(4, 6))
        self._wrapped_labels.append(context_note)
        self.header_actions_frame = actions = ttk.Frame(self.header.content)
        actions.pack(fill='x')
        self.scan_button = ttk.Button(actions, text='Scan copied folder', command=self.scan)
        self.controls.append(self.scan_button)
        self.cancel_button = ttk.Button(actions, text='Cancel scan', command=self.cancel, state='disabled')
        self.open_button = ttk.Button(actions, text='Open selected copy', command=self.open_selected, state='disabled')
        self.management_button = ttk.Button(actions, text='Save Doctor / Detection / Vault', command=self.show_management)
        self.controls.append(self.management_button)
        self._header_actions = (self.scan_button, self.cancel_button, self.open_button, self.management_button)
        self._arrange_actions(actions, self._header_actions)
        self.status = tk.StringVar(root, value='Choose an exact game/platform and a folder containing separate save copies.')
        status_label = ttk.Label(self.header.content, textvariable=self.status, wraplength=1000)
        status_label.pack(anchor='w', pady=(6, 4))
        self._wrapped_labels.append(status_label)
        self.filters = filters = ttk.Frame(self.header.content)
        filters.pack(fill='x', pady=(2, 4))
        self.query_label = ttk.Label(filters, text='Find a copy')
        self.search = tk.StringVar(root)
        self.search_entry = ttk.Entry(filters, textvariable=self.search)
        self.filter = tk.StringVar(root, value='All results')
        self.status_filter = ttk.Combobox(filters, textvariable=self.filter, values=('All results', 'Qualified', 'Not qualified', 'Identical gameplay files',
                             'No identical file found', 'Unsafe path', 'Too large', 'Changed', 'Unreadable'),
                     state='readonly', width=24)
        self.subfolder = tk.StringVar(root, value='All folders')
        self.folder_filter = ttk.Combobox(filters, textvariable=self.subfolder, values=('All folders',), state='readonly', width=16)
        self.sort = tk.StringVar(root, value=SORTS[0])
        self.sort_selector = ttk.Combobox(filters, textvariable=self.sort, values=SORTS, state='readonly', width=22)
        self.filters.columnconfigure(1, weight=1)
        self._narrow_filters = None
        self._arrange_filters(False)
        # Reserve navigation and guidance before the expanding viewport. Tk's
        # pack order otherwise lets the table consume their space at the
        # application's minimum window size.
        self.footer = ttk.Frame(self.frame)
        self.footer.pack(side='bottom', fill='x')
        self.detail = tk.StringVar(root, value='Select a result to see its validation summary.')
        self.detail_label = ttk.Label(self.footer, textvariable=self.detail, wraplength=1000)
        self.detail_label.pack(anchor='w', pady=(6, 2))
        self.batch_actions_frame = batch = ttk.Frame(self.footer)
        batch.pack(fill='x', pady=2)
        self.select_matches_button = ttk.Button(batch, text='Select qualified matches', command=self.select_matches)
        self.clear_button = ttk.Button(batch, text='Clear selection', command=self.clear_selection)
        self.recheck_button = ttk.Button(batch, text='Recheck selected', command=self.recheck_selected, state='disabled')
        self.manage_button = ttk.Button(batch, text='Manage selected copies', command=self.manage_selected, state='disabled')
        self.controls.extend((self.select_matches_button, self.clear_button))
        self._batch_actions = (self.select_matches_button, self.clear_button, self.recheck_button, self.manage_button)
        self._arrange_actions(batch, self._batch_actions)
        paging = ttk.Frame(self.footer)
        paging.pack(fill='x', pady=(2, 4))
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
        self.guidance_label.pack(anchor='w', pady=(2, 0))
        self._wrapped_labels.extend((self.detail_label, self.guidance_label))
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table_frame, columns=('path', 'size', 'modified', 'status', 'duplicates'),
                                  show='headings', selectmode='extended', height=12)
        for name, title, width in (('path', 'Copied file / relative folder', 330), ('size', 'Bytes', 100),
                ('modified', 'Modified (UTC)', 160), ('status', 'Validation', 150),
                ('duplicates', 'Identical gameplay bytes', 190)):
            self.table.heading(name, text=title)
            self.table.column(name, width=width, minwidth=75, stretch=name == 'path')
        vertical = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        self.horizontal_scrollbar = horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1, minsize=100)
        self.table.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.table.bind('<<TreeviewSelect>>', self.selection_changed)
        self.table.bind('<Double-1>', lambda _event: self.open_selected())
        for variable in (self.game, self.folder, self.recursive):
            variable.trace_add('write', self.invalidate)
        for variable in (self.search, self.filter, self.subfolder):
            variable.trace_add('write', self.refilter)
        self.sort.trace_add('write', lambda *_args: self.refilter(clear=False))
        self.frame.bind('<Destroy>', self._on_destroy, add='+')
        self.frame.bind('<Configure>', self._schedule_layout, add='+')
        self.header.canvas.bind('<Configure>', self._schedule_layout, add='+')
        self.header.content.bind('<Configure>', self._schedule_layout, add='+')
        self.footer.bind('<Configure>', self._schedule_layout, add='+')
        for button in (*self._header_actions, *self._batch_actions):
            button.bind('<Configure>', self._schedule_layout, add='+')
        self._schedule_layout()

    def _arrange_actions(self, frame, buttons):
        required = sum(button.winfo_reqwidth() for button in buttons) + 8 * (len(buttons) - 1)
        columns = 2 if required > frame.winfo_width() else 4
        if self._action_columns.get(frame) == columns:
            return
        self._action_columns[frame] = columns
        for index, button in enumerate(buttons):
            button.grid(row=index // columns, column=index % columns, sticky='w',
                        padx=(0, 8) if index % columns < columns - 1 else 0,
                        pady=(0, 4) if index + columns < len(buttons) else 0)

    def _arrange_filters(self, narrow):
        if narrow == self._narrow_filters:
            return
        self._narrow_filters = narrow
        self.query_label.grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.search_entry.grid(row=0, column=1, sticky='ew')
        self.status_filter.grid(row=0, column=2, sticky='ew', padx=(8, 0 if narrow else 8))
        self.folder_filter.grid(row=1 if narrow else 0, column=0 if narrow else 3,
                                columnspan=2 if narrow else 1, sticky='ew',
                                padx=(0, 8), pady=(4, 0) if narrow else 0)
        self.sort_selector.grid(row=1 if narrow else 0, column=2 if narrow else 4,
                                sticky='ew', pady=(4, 0) if narrow else 0)

    def _schedule_layout(self, _event=None):
        if not self._closed and self._layout_id is None:
            self._layout_id = self.root.after_idle(self._layout_header)

    def _layout_header(self):
        self._layout_id = None
        if self._closed:
            return
        header_width = max(120, self.header.canvas.winfo_width())
        self._arrange_filters(header_width < 850)
        self._arrange_actions(self.header_actions_frame, self._header_actions)
        self._arrange_actions(self.batch_actions_frame, self._batch_actions)
        footer_width = max(120, self.frame.winfo_width() - 56)
        for label in self._wrapped_labels:
            width = header_width if label.master is self.header.content else footer_width
            if int(label.cget('wraplength')) != width:
                label.configure(wraplength=width)
        # The ordinary layout shows the full header. Smaller windows scroll
        # only the form; keep the result table and its footer on screen.
        required = self.header.content.winfo_reqheight()
        available = (self.frame.winfo_height() - 24 - self.footer.winfo_reqheight()
                     - 100 - self.horizontal_scrollbar.winfo_reqheight())
        height = max(1, min(required, available))
        if self.header.frame.winfo_reqheight() != height:
            self.header.frame.configure(height=height)
        self.header.refresh()
        if height >= required:
            self.header.canvas.yview_moveto(0)

    def apply_theme(self, palette):
        self._palette = palette
        if 'background' in palette:
            self.header.apply_theme(palette)
        if self.management is not None and not getattr(self.management, '_closed', False):
            self.management.apply_theme(palette)

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
        if self._layout_id is not None:
            self.root.after_cancel(self._layout_id)
            self._layout_id = None
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
        self._selected.clear()
        self.check_results.clear()
        self._rendering = True
        self.table.selection_remove(*self.table.selection())
        self._rendering = False
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

    def refilter(self, *_args, clear=True):
        if clear:
            self._selected.clear()
            self._rendering = True
            self.table.selection_remove(*self.table.selection())
            self._rendering = False
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

    def matching_indices(self):
        if self.prepared is None:
            return ()
        choice = self.filter.get()
        status = {'Qualified': 'qualified', 'Not qualified': 'not_qualified',
                  'Unsafe path': 'unsafe', 'Too large': 'oversized', 'Changed': 'changed',
                  'Unreadable': 'unreadable'}.get(choice, 'all')
        duplicates = {'Identical gameplay files': 'grouped', 'No identical file found': 'ungrouped'}.get(choice, 'all')
        folder = '' if self.subfolder.get() == 'All folders' else self.subfolder.get()
        return backend.browse(self.prepared, query=self.search.get()[:4096], status=status,
                              duplicates=duplicates, folder=folder,
                              sort=backend.BROWSE_SORTS[SORTS.index(self.sort.get())])

    def _capture_selection(self):
        if not self._rendering:
            self._selected.difference_update(self._visible)
            self._selected.update(int(item) for item in self.table.selection())

    def refresh(self):
        self._capture_selection()
        self._rendering = True
        try:
            self.table.delete(*self.table.get_children())
            visible = self.matching_indices()
            entries = () if self.prepared is None else self.prepared.entries
            self.page = min(self.page, max(0, (len(visible) - 1) // self.page_size))
            start = self.page * self.page_size
            end = min(start + self.page_size, len(visible))
            self._visible = visible[start:end]
            for index in self._visible:
                entry = entries[index]
                checked = self.check_results.get(entry.relative_path)
                label = ('Rechecked' if checked == 'qualified' else 'Recheck failed') if checked else STATUS_LABELS[entry.status]
                self.table.insert('', 'end', iid=str(index), values=(entry.relative_path, f'{entry.size_bytes:,}',
                    self._modified(entry.modified_ns), label,
                    'Group ' + str(entry.duplicate_group) if entry.duplicate_group else '-'))
            self.table.selection_set(tuple(str(index) for index in self._visible if index in self._selected))
            self.previous.configure(state='normal' if self.page else 'disabled')
            self.next.configure(state='normal' if end < len(visible) else 'disabled')
            self.page_info.set(f'{start + 1 if visible else 0:,}-{end:,} of {len(visible):,} matching results')
        finally:
            self._rendering = False
        self.selection_changed()

    def selected_entries(self):
        self._capture_selection()
        if self.prepared is None:
            return ()
        return tuple(self.prepared.entries[index] for index in sorted(self._selected)
                     if 0 <= index < len(self.prepared.entries))

    def select_matches(self):
        if self.busy or self.prepared is None:
            return
        self._capture_selection()
        self._selected.update(index for index in self.matching_indices()
                              if self.prepared.entries[index].status == 'qualified')
        self._rendering = True
        self.table.selection_set(tuple(str(index) for index in self._visible if index in self._selected))
        self._rendering = False
        self.selection_changed()

    def clear_selection(self):
        self._selected.clear()
        self.table.selection_remove(*self.table.selection())
        self.selection_changed()

    def selected_entry(self):
        entries = self.selected_entries()
        return entries[0] if len(entries) == 1 else None

    def selection_changed(self, *_args):
        if self._rendering:
            return
        entries = self.selected_entries()
        entry = entries[0] if len(entries) == 1 else None
        qualified = bool(entries) and all(item.status == 'qualified' for item in entries)
        self.open_button.configure(state='normal' if not self.busy and entry is not None and qualified else 'disabled')
        for button in (self.recheck_button, self.manage_button):
            button.configure(state='normal' if not self.busy and qualified else 'disabled')
        if len(entries) > 1:
            self.detail.set(f'{len(entries):,} copies selected across all pages. '
                            'Batch actions require qualified copies; changing search or filters clears the selection.')
        else:
            self.detail.set('Select copies to recheck or manage; Ctrl/Shift selects several.' if entry is None else
                            f'Selected copy: {entry.relative_path}. ' + entry.summary + (f' {entry.mapped_fields:,} mapped editable fields.' if entry.status == 'qualified' else '') +
                            (' Latest recheck: ' + self.check_results[entry.relative_path].replace('_', ' ') + '.'
                             if entry.relative_path in self.check_results else ''))

    def show_management(self):
        if self.busy:
            return
        self._show_management(self._games.get(self.game.get()), ())

    def manage_selected(self):
        if self.busy:
            return
        entries = self.selected_entries()
        if not entries or any(entry.status != 'qualified' for entry in entries):
            return
        if self.on_manage is not None:
            self.on_manage(self.prepared, entries)
        else:
            self._show_management(self.prepared.game_id,
                                  tuple(self.prepared.folder / entry.relative_path for entry in entries))

    def _show_management(self, game_id, paths):
        if self.management is None or getattr(self.management, '_closed', False):
            from koei_editor.shared.save_management_gui import SaveManagementWindow
            self.management = SaveManagementWindow(self.root, game_id=game_id, paths=paths)
            if self._palette is not None:
                self.management.apply_theme(self._palette)
        else:
            self.management.show(game_id=game_id, paths=paths)

    def recheck_selected(self):
        if self.busy:
            return
        entries = self.selected_entries()
        if not entries or any(entry.status != 'qualified' for entry in entries):
            return
        prepared = self.prepared
        for entry in entries:
            self.check_results.pop(entry.relative_path, None)
        self.refresh()
        self._start('recheck', lambda cancel: backend.requalify_many(prepared, entries, cancel=cancel))

    def _start(self, kind, operation):
        if self.busy or self._closed:
            return
        self.busy = True
        revision = self._revision
        self._cancel = cancel = threading.Event()
        for control in self.controls:
            control.configure(state='disabled')
        self.open_button.configure(state='disabled')
        self.recheck_button.configure(state='disabled')
        self.manage_button.configure(state='disabled')
        self.cancel_button.configure(state='normal', text={'scan': 'Cancel scan', 'open': 'Cancel open', 'recheck': 'Cancel recheck'}[kind])
        self.status.set('Scanning and qualifying copied saves...' if kind == 'scan' else 'Rechecking selected saves and their original context...')
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
            self._rendering = True
            self.table.selection_remove(*self.table.selection())
            self._rendering = False
            self.prepared = result
            self._selected.clear()
            self.check_results.clear()
            folders = sorted({parent.as_posix() for entry in result.entries
                              for parent in Path(entry.relative_path).parents if parent != Path('.')}, key=str.casefold)
            self.folder_filter.configure(values=('All folders', *folders))
            self.subfolder.set('All folders')
            self.page = 0
            self.refresh()
            reason = {'complete': 'Scan finished', 'cancelled': 'Scan cancelled (partial results)',
                      'file_limit': 'File limit reached (partial results)', 'entry_limit': 'Directory-entry limit reached (partial results)',
                      'byte_limit': 'Data limit reached (partial results)'}[result.stop_reason]
            self.status.set(f'{reason}: {result.qualified_count:,} qualified of {len(result.entries):,} candidate files; '
                            f'{result.excluded_directories:,} directories excluded. Qualification is specific to the chosen profile.')
        elif kind == 'recheck':
            self.check_results.update((entry.relative_path, entry.status) for entry in result.entries)
            self.refresh()
            reason = 'Recheck cancelled (partial results)' if result.stop_reason == 'cancelled' else 'Recheck finished'
            self.status.set(f'{reason}: {result.qualified_count:,} qualified of {len(result.entries):,} checked; '
                            f'{result.requested_count:,} selected. Files are unchanged; later actions revalidate again.')
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
        self._selected.clear()
        self.check_results.clear()
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

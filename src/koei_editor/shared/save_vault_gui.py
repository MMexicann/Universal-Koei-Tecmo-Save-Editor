"""Local Save Vault workspace. Qualification and file operations run off Tk."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from koei_editor.shared import save_vault
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.save_library import LIBRARY_GAMES


class SaveVaultWorkspace:
    def __init__(self, root, parent, on_open=None, *, vault_root=None, auto_capture=None):
        self.root, self.on_open = root, on_open
        self.vault_root = Path(save_vault.default_root() if vault_root is None else vault_root)
        self.frame = ttk.Frame(parent, padding=(24, 16))
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(5, weight=1)
        self.busy = self._writing = self._closed = False
        self._poll_id = None
        self._results = queue.SimpleQueue()
        self._rows, self._visible = (), ()
        self._compare_first = None
        self._page, self.page_size = 0, 100
        self._controls = []
        self._games = {f'{game.title} · {game.subtitle} [{game.platform}]': game.id for game in LIBRARY_GAMES}
        self.game = tk.StringVar(root, value=next(iter(self._games)))
        self.search = tk.StringVar(root)
        self.collection = tk.StringVar(root, value='All collections')
        self.branch = tk.StringVar(root, value='All branches')
        self.status = tk.StringVar(root, value='Private local history for qualified scalar save copies. DW3 keeps its existing backup workflow.')
        self.page_text = tk.StringVar(root, value='No snapshots loaded')
        ttk.Label(self.frame, text='SAVE VAULT', font=(ui_font(root), 23, 'bold')).grid(row=0, column=0, sticky='w')
        self.intro = ttk.Label(self.frame, text='Organize original copies into collections and branches, compare mapped progress, and restore to new folders. '
            'Your original saves and staged edits remain untouched.', wraplength=950, style='Muted.TLabel')
        self.intro.grid(row=1, column=0, sticky='ew', pady=(4, 12))
        form = ttk.Frame(self.frame)
        form.grid(row=2, column=0, sticky='ew')
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='Import profile').grid(row=0, column=0, sticky='w', padx=(0, 12))
        selector = ttk.Combobox(form, textvariable=self.game, values=tuple(self._games), state='readonly')
        selector.grid(row=0, column=1, sticky='ew')
        self._controls.append(selector)
        self.location = ttk.Label(form, text='Local storage: ' + str(self.vault_root), wraplength=850, style='Muted.TLabel')
        self.location.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(7, 5))
        actions = ttk.Frame(self.frame)
        actions.grid(row=3, column=0, sticky='ew', pady=(5, 10))
        for text, command in (('Refresh', self.refresh), ('New collection', self.create_collection),
                ('Import copy…', self.import_copy), ('Verify', self.verify_selected),
                ('History', self.show_history), ('Compare two', self.compare_selected),
                ('Restore / export…', self.export_selected)):
            button = ttk.Button(actions, text=text, command=command)
            button.pack(side='left', padx=(0, 5))
            self._controls.append(button)
        filters = ttk.Frame(self.frame)
        filters.grid(row=4, column=0, sticky='ew', pady=(0, 8))
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text='Find snapshots').grid(row=0, column=0, padx=(0, 8))
        self.search_entry = ttk.Entry(filters, textvariable=self.search)
        self.search_entry.grid(row=0, column=1, sticky='ew')
        self.collections = ttk.Combobox(filters, textvariable=self.collection, state='readonly', width=22,
                                      values=('All collections',))
        self.collections.grid(row=0, column=2, padx=8)
        self.branches = ttk.Combobox(filters, textvariable=self.branch, state='readonly', width=18,
                                   values=('All branches',))
        self.branches.grid(row=0, column=3)
        table = ttk.Frame(self.frame)
        table.grid(row=5, column=0, sticky='nsew')
        table.columnconfigure(0, weight=1); table.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=('label', 'profile', 'collection', 'branch', 'created', 'parent'),
                                show='headings', selectmode='extended')
        for key, title, width in (('label', 'Snapshot', 190), ('profile', 'Game / platform profile', 130),
                ('collection', 'Collection', 135), ('branch', 'Branch', 90), ('created', 'Created UTC', 170),
                ('parent', 'Parent', 80)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky='ns'); self.tree.configure(yscrollcommand=scroll.set)
        horizontal = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew'); self.tree.configure(xscrollcommand=horizontal.set)
        footer = ttk.Frame(self.frame)
        footer.grid(row=6, column=0, sticky='ew', pady=(8, 0))
        self.previous = ttk.Button(footer, text='Previous', command=lambda: self.change_page(-1))
        self.previous.pack(side='left')
        ttk.Label(footer, textvariable=self.page_text).pack(side='left', padx=12)
        self.next = ttk.Button(footer, text='Next', command=lambda: self.change_page(1))
        self.next.pack(side='left')
        pin = ttk.Button(footer, text='Pin first comparison snapshot', command=self.pin_comparison)
        pin.pack(side='left', padx=12); self._controls.append(pin)
        if on_open is not None:
            button = ttk.Button(footer, text='Export and open…', command=lambda: self.export_selected(open_after=True))
            button.pack(side='right'); self._controls.append(button)
        self.status_label = ttk.Label(self.frame, textvariable=self.status, wraplength=950)
        self.status_label.grid(row=7, column=0, sticky='ew', pady=(8, 0))
        if auto_capture is not None:
            ttk.Checkbutton(self.frame, text='Capture original backups this session', variable=auto_capture).grid(row=8, column=0, sticky='w')
        for variable in (self.search, self.collection, self.branch):
            variable.trace_add('write', self._filter_changed)
        self.frame.bind('<Destroy>', self._destroyed, add='+')
        self._render()
        # Merely opening this workspace never creates storage or imports saves.
        if self.vault_root.exists():
            self.refresh()

    def _run(self, operation, callback, *, writing=False):
        if self.busy or self._closed:
            return False
        self.busy, self._writing = True, writing
        self.status.set('Working locally… Completed outputs are retained if a later check fails.')
        for control in self._controls:
            control.configure(state='disabled')
        def work():
            try:
                result = operation()
                self._results.put((True, result, callback))
            except Exception as error:
                # Native messages may include personal paths; keep status generic.
                self._results.put((False, type(error).__name__, callback))
        threading.Thread(target=work, daemon=False).start()
        self._poll_id = self.frame.after(40, self._poll)
        return True

    def _poll(self):
        self._poll_id = None
        try:
            success, result, callback = self._results.get_nowait()
        except queue.Empty:
            if not self._closed:
                self._poll_id = self.frame.after(40, self._poll)
            return
        self.busy = self._writing = False
        if self._closed:
            return
        for control in self._controls:
            control.configure(state='readonly' if isinstance(control, ttk.Combobox) else 'normal')
        if success:
            callback(result)
        else:
            self.status.set('Operation failed (' + result + '). No existing file was overwritten. '
                'Keep completed output copies. Check the selected profile, original context, integrity and ordinary local paths; '
                'an interrupted .writer-lock requires manual recovery after all writers close.')

    def refresh(self):
        def read():
            vault = save_vault.Vault(self.vault_root)
            return vault.snapshots(), vault.collections()
        def loaded(result):
            self._rows, collections = result
            self.collections.configure(values=('All collections', *collections))
            self.branches.configure(values=('All branches', *sorted({row['branch'] for row in self._rows})))
            self._page = 0; self._render()
            self.status.set(f'{len(self._rows):,} snapshots loaded. Select two rows to compare, or one to verify, trace history or restore.')
        self._run(read, loaded)

    def create_collection(self):
        if self.busy:
            return
        label = simpledialog.askstring('New collection', 'Collection label:', parent=self.root)
        if label is not None:
            self._run(lambda: save_vault.Vault(self.vault_root).create_collection(label), lambda _: self.refresh(), writing=True)

    def _selected(self, count=1):
        ids = self.tree.selection()
        if len(ids) != count:
            self.status.set(f'Select exactly {count} snapshot' + ('s.' if count != 1 else '.'))
            return None
        mapping = {row['id']: row for row in self._rows}
        return tuple(mapping[key] for key in ids if key in mapping)

    def import_copy(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title='Import a qualified separate save copy')
        if not path:
            return
        label = simpledialog.askstring('Snapshot label', 'Name this snapshot:', parent=self.root)
        if label is None:
            return
        collection = simpledialog.askstring('Collection', 'Collection label:', initialvalue=(
            self.collection.get() if self.collection.get() != 'All collections' else 'Backups'), parent=self.root)
        if collection is None:
            return
        branch = simpledialog.askstring('Branch', 'Branch label:', initialvalue='main', parent=self.root)
        if branch is None:
            return
        selected = self.tree.selection()
        parent = selected[0] if len(selected) == 1 else None
        if parent is not None and not messagebox.askyesno('Parent snapshot',
                'Link the new snapshot to the selected parent? Choose No to create an independent root.', parent=self.root):
            parent = None
        game_id = self._games[self.game.get()]
        self._run(lambda: save_vault.Vault(self.vault_root).import_copy(game_id, path, label,
            collection=collection, branch=branch, parent_id=parent), lambda _: self.refresh(), writing=True)

    def verify_selected(self):
        rows = self._selected()
        if rows:
            self._run(lambda: save_vault.Vault(self.vault_root).verify(rows[0]['id']),
                lambda _: self.status.set('Gameplay bytes, opaque context, catalog chain and selected native profile verified. In-game loading is not established.'))

    def show_history(self):
        rows = self._selected()
        if rows:
            self._run(lambda: save_vault.Vault(self.vault_root).history(rows[0]['id']),
                lambda chain: self._show_rows('Parent history', ('Snapshot', 'Branch', 'Created UTC'),
                    tuple((row['label'], row['branch'], row['created_utc']) for row in chain)))

    def compare_selected(self):
        ids = self.tree.selection()
        if len(ids) == 1 and self._compare_first is not None and ids[0] != self._compare_first:
            mapping = {row['id']: row for row in self._rows}
            rows = (mapping[self._compare_first], mapping[ids[0]]) if self._compare_first in mapping else None
        else:
            rows = self._selected(2)
        if rows:
            def shown(comparison):
                self._show_rows('Mapped snapshot differences', ('Group', 'Record', 'Field', 'First', 'Second', 'Status'),
                    tuple((row.group, row.record, row.label, row.left, row.right, row.status) for row in comparison.rows),
                    f'First: {rows[0]["label"]}; Second: {rows[1]["label"]}. '
                    f'{comparison.unchanged_fields:,} unchanged mapped fields; {comparison.outside_field_bytes:,} changed bytes outside editable spans. No changes applied.')
            self._run(lambda: save_vault.Vault(self.vault_root).compare(rows[0]['id'], rows[1]['id']), shown)

    def pin_comparison(self):
        rows = self._selected()
        if rows:
            self._compare_first = rows[0]['id']
            self.status.set('First comparison snapshot: ' + rows[0]['label']
                + '. Select another snapshot on any page, then choose Compare two.')

    def export_selected(self, *, open_after=False):
        if self.busy:
            return
        rows = self._selected()
        if not rows:
            return
        parent = filedialog.askdirectory(parent=self.root, title='Choose a safe parent for a new restored-copy folder')
        if not parent:
            return
        name = simpledialog.askstring('New output folder', 'New folder name (must not exist):', parent=self.root)
        if not name:
            return
        if Path(name).name != name or '/' in name or '\\' in name or name in ('.', '..'):
            self.status.set('Use a single new folder name.'); return
        row = rows[0]
        def exported(path):
            self.status.set('Verified new copy exported with unchanged original context; existing saves were not replaced.')
            if open_after and self.on_open is not None:
                self.on_open(row['game_id'], path)
        self._run(lambda: save_vault.Vault(self.vault_root).export(row['id'], Path(parent) / name), exported, writing=True)

    def _show_rows(self, title, columns, rows, note=''):
        dialog = tk.Toplevel(self.root); dialog.title(title); dialog.geometry('1050x580')
        dialog.columnconfigure(0, weight=1); dialog.rowconfigure(1, weight=1)
        ttk.Label(dialog, text=note or 'Read-only local snapshot history.', wraplength=950).grid(row=0, column=0, sticky='ew', padx=14, pady=12)
        table = ttk.Treeview(dialog, columns=columns, show='headings')
        for column in columns:
            table.heading(column, text=column); table.column(column, width=160, minwidth=80)
        table.grid(row=1, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(dialog, orient='vertical', command=table.yview)
        scrollbar.grid(row=1, column=1, sticky='ns'); table.configure(yscrollcommand=scrollbar.set)
        # Tables are bounded to one viewport page; large comparisons remain
        # accessible with explicit pagination instead of thousands of Tk rows.
        page = [0]
        def render():
            table.delete(*table.get_children())
            for row in rows[page[0] * 100:(page[0] + 1) * 100]:
                table.insert('', 'end', values=tuple('' if v is None else v for v in row))
            info.configure(text=f'Page {page[0] + 1} of {max(1, (len(rows) + 99) // 100)}')
        def move(delta):
            page[0] = max(0, min(max(0, (len(rows) - 1) // 100), page[0] + delta)); render()
        footer = ttk.Frame(dialog); footer.grid(row=2, column=0, sticky='ew', padx=14, pady=12)
        ttk.Button(footer, text='Previous', command=lambda: move(-1)).pack(side='left')
        info = ttk.Label(footer); info.pack(side='left', padx=12)
        ttk.Button(footer, text='Next', command=lambda: move(1)).pack(side='left')
        ttk.Button(footer, text='Close', command=dialog.destroy).pack(side='right'); render()

    def _filter_changed(self, *_args):
        self._page = 0; self._render()

    def _render(self):
        tokens = self.search.get().casefold().split()
        rows = tuple(row for row in self._rows
            if (self.collection.get() == 'All collections' or row['collection'] == self.collection.get())
            and (self.branch.get() == 'All branches' or row['branch'] == self.branch.get())
            and all(token in ' '.join((row['label'], row['game_id'], row['branch'], row['collection'])).casefold() for token in tokens))
        self._page = min(self._page, max(0, (len(rows) - 1) // self.page_size))
        self._visible = rows[self._page * self.page_size:(self._page + 1) * self.page_size]
        self.tree.delete(*self.tree.get_children())
        for row in self._visible:
            self.tree.insert('', 'end', iid=row['id'], values=(row['label'], row['game_id'], row['collection'],
                row['branch'], row['created_utc'], row['parent'][:8] if row['parent'] else 'Root'))
        self.previous.configure(state='normal' if self._page else 'disabled')
        self.next.configure(state='normal' if (self._page + 1) * self.page_size < len(rows) else 'disabled')
        self.page_text.set(f'{len(rows):,} snapshots · Page {self._page + 1} of {max(1, (len(rows) + self.page_size - 1) // self.page_size)}')

    def change_page(self, delta):
        self._page = max(0, self._page + delta); self._render()

    def apply_theme(self, palette):
        # ttk widgets inherit the application's Light/Dark styles.
        self.palette = dict(palette)

    def focus_search(self):
        self.search_entry.focus_set()

    def has_pending_work(self):
        return self.busy

    def close(self):
        if self.busy:
            return False
        self._closed = True
        if self._poll_id is not None:
            self.frame.after_cancel(self._poll_id); self._poll_id = None
        return True

    def _destroyed(self, event):
        if event.widget is self.frame:
            self._closed = True
            if self._poll_id is not None:
                self.frame.after_cancel(self._poll_id); self._poll_id = None

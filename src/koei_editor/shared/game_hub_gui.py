"""Installed-game hub built on the existing bounded Steam discovery service."""
from datetime import datetime, timezone
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser

from koei_editor.game_registry import get_game
from koei_editor.shared import game_hub
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.save_discovery import STEAM_MAPPINGS


class GameHubWorkspace:
    def __init__(self, root, parent, *, preferences_path=None):
        self.root = root
        self.notes = game_hub.GameHubNotes(game_hub.notes_path(preferences_path))
        self.mappings = tuple(sorted(STEAM_MAPPINGS,
                                     key=lambda item: (get_game(item.game_id).title.casefold(), item.app_id)))
        self._games = {mapping.app_id: get_game(mapping.game_id) for mapping in self.mappings}
        self._installed = {}
        self._local_notes = self.notes.load()
        self._result = None
        self._row_installations = {}
        self._closed = False
        self._shown = False
        self.busy = False
        self._cancel = threading.Event()
        self._results = queue.SimpleQueue()
        self._poll_id = None
        self._palette = None

        self.frame = ttk.Frame(parent, padding=(28, 16))
        ttk.Label(self.frame, text='GAME HUB', font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        ttk.Label(self.frame,
                  text='Find your tracked Koei Tecmo Steam installs, review build information, add local notes, and launch games.',
                  style='Muted.TLabel', wraplength=1050).pack(anchor='w', pady=(2, 10))

        scan_row = ttk.Frame(self.frame)
        scan_row.pack(fill='x', pady=(0, 8))
        scan_row.columnconfigure(1, weight=1)
        ttk.Label(scan_row, text='Steam root (optional)').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.steam_root = tk.StringVar(root)
        self.steam_root_entry = ttk.Entry(scan_row, textvariable=self.steam_root)
        self.steam_root_entry.grid(row=0, column=1, sticky='ew')
        self.browse_button = ttk.Button(scan_row, text='Browse…', command=self.browse_root)
        self.browse_button.grid(row=0, column=2, padx=(8, 0))
        self.refresh_button = ttk.Button(scan_row, text='Refresh installations', command=self.discover)
        self.refresh_button.grid(row=0, column=3, padx=(8, 0))
        self.cancel_button = ttk.Button(scan_row, text='Cancel', command=self.cancel, state='disabled')
        self.cancel_button.grid(row=0, column=4, padx=(8, 0))
        self.controls = [self.steam_root_entry, self.browse_button, self.refresh_button]

        filter_row = ttk.Frame(self.frame)
        filter_row.pack(fill='x', pady=(0, 6))
        ttk.Label(filter_row, text='Find a game').pack(side='left', padx=(0, 8))
        self.query = tk.StringVar(root)
        self.search_entry = ttk.Entry(filter_row, textvariable=self.query)
        self.search_entry.pack(side='left', fill='x', expand=True)
        ttk.Label(filter_row, text='Show').pack(side='left', padx=(12, 6))
        self.status_filter = tk.StringVar(root, value='All tracked games')
        self.status_selector = ttk.Combobox(filter_row, textvariable=self.status_filter,
                                            values=('All tracked games', 'Installed', 'Not detected'),
                                            state='readonly', width=19)
        self.status_selector.pack(side='left')

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table_frame,
                                  columns=('status', 'build', 'updated', 'size', 'notes'),
                                  show='tree headings', selectmode='browse', height=10)
        self.table.heading('#0', text='Game')
        self.table.column('#0', width=300, minwidth=170, stretch=True)
        for name, title, width, minimum in (
                ('status', 'Installation', 125, 90), ('build', 'Steam build ID', 120, 90),
                ('updated', 'Last updated (UTC)', 155, 120), ('size', 'Install size', 110, 80),
                ('notes', 'Local note', 220, 100)):
            self.table.heading(name, text=title)
            self.table.column(name, width=width, minwidth=minimum, stretch=name in ('notes', 'build'))
        vertical = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.table.bind('<<TreeviewSelect>>', self.selection_changed)

        detail_frame = ttk.LabelFrame(self.frame, text='Installation information', padding=10)
        detail_frame.pack(fill='x', pady=(10, 6))
        self.details = tk.Text(detail_frame, height=6, wrap='word', state='disabled',
                               font=(ui_font(root), 9), borderwidth=0, highlightthickness=0)
        self.details.pack(fill='x', expand=True)
        actions = ttk.Frame(self.frame)
        actions.pack(fill='x')
        self.launch_button = ttk.Button(actions, text='Launch through Steam', command=self.launch_selected,
                                         state='disabled')
        self.launch_button.pack(side='left', padx=(0, 8))
        self.folder_button = ttk.Button(actions, text='Open install folder', command=self.open_selected_folder,
                                        state='disabled')
        self.folder_button.pack(side='left', padx=(0, 8))
        self.note_button = ttk.Button(actions, text='Edit local note…', command=self.edit_note,
                                      state='disabled')
        self.note_button.pack(side='left', padx=(0, 8))
        self.controls.extend((self.status_selector, self.search_entry))
        self.status = tk.StringVar(root, value=f'{len(self.mappings)} Steam-mapped game profiles. Open this page to scan installed titles.')
        ttk.Label(self.frame, textvariable=self.status, wraplength=1050,
                  style='Muted.TLabel').pack(anchor='w', pady=(8, 0))

        self.query.trace_add('write', lambda *_args: self.render())
        self.status_filter.trace_add('write', lambda *_args: self.render())
        self.frame.bind('<Destroy>', self._on_destroy, add='+')
        self.render()

    def on_show(self):
        if not self._shown:
            self._shown = True
            self.discover()

    def _set_details(self, value):
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', value)
        self.details.configure(state='disabled')

    @staticmethod
    def _size(size):
        if type(size) is not int or size < 0:
            return 'Unknown'
        amount = float(size)
        for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
            if amount < 1000 or unit == 'TB':
                return f'{amount:.0f} {unit}' if unit == 'B' else f'{amount:.1f} {unit}'
            amount /= 1000
        return 'Unknown'

    @staticmethod
    def _updated(timestamp):
        if (type(timestamp) is str and timestamp.isascii()
                and timestamp.isdecimal() and len(timestamp) <= 12):
            timestamp = int(timestamp)
        if type(timestamp) is not int or timestamp <= 0:
            return 'Unknown'
        try:
            return datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d %H:%M')
        except (OverflowError, OSError, ValueError):
            return 'Unknown'

    def browse_root(self):
        selected = filedialog.askdirectory(parent=self.root, title='Choose a Steam installation folder',
                                           mustexist=True)
        if selected:
            self.steam_root.set(selected)

    def discover(self):
        if self.busy or self._closed:
            return
        entered = self.steam_root.get().strip()
        roots = [entered] if entered else None
        self.busy = True
        self._cancel = threading.Event()
        self._set_busy(True)
        self.status.set('Scanning Steam library metadata…')

        def worker():
            try:
                result = game_hub.discover_installations(steam_roots=roots, cancel=self._cancel)
            except Exception:
                self._results.put((False, None))
            else:
                self._results.put((True, result))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_id = self.root.after(30, self._poll)

    def cancel(self):
        if self.busy:
            self._cancel.set()
            self.status.set('Cancelling Steam scan…')

    def _set_busy(self, busy):
        for control in self.controls:
            try:
                control.configure(state='disabled' if busy else 'normal')
            except tk.TclError:
                pass
        self.status_selector.configure(state='disabled' if busy else 'readonly')
        self.refresh_button.configure(state='disabled' if busy else 'normal')
        self.cancel_button.configure(state='normal' if busy else 'disabled')
        if busy:
            self.launch_button.configure(state='disabled')
            self.folder_button.configure(state='disabled')
            self.note_button.configure(state='disabled')
        else:
            self.selection_changed()

    def _poll(self):
        self._poll_id = None
        if self._closed:
            return
        try:
            success, value = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.root.after(30, self._poll)
            return
        self.busy = False
        self._set_busy(False)
        if not success:
            if self._result is None:
                self.status.set('Steam detection failed. Check the selected root and metadata access.')
            else:
                self.status.set('Steam refresh failed. Previous results remain displayed. Check the selected root and metadata access.')
            messagebox.showerror('Game Hub', self.status.get(), parent=self.root)
            return
        self._result = value
        self._installed = {}
        for item in value.installed_games:
            self._installed.setdefault(item.app_id, []).append(item)
        count = len(value.installed_games)
        complete = value.stop_reason == 'complete'
        summary = f'Detected {count} installation(s) across {len(self.mappings)} tracked Steam game profiles.'
        if value.stop_reason == 'cancelled':
            summary = (f'Scan cancelled after detecting {count} installation(s) across '
                       f'{len(self.mappings)} tracked Steam game profiles.')
        elif not complete:
            reason = value.stop_reason.removesuffix('_limit').replace('_', ' ')
            summary += f' Scan stopped at the {reason} limit.'
        if value.issues:
            summary += f' {len(value.issues)} metadata issue(s) were skipped.'
        self.status.set(summary)
        self.render()

    def _matching(self, mapping, game, status):
        terms = (game.title, game.subtitle, game.id, mapping.app_id,
                 status, *self._installed_note(mapping.app_id).split())
        query = self.query.get().strip().casefold()
        return not query or query in ' '.join(terms).casefold()

    def _installed_note(self, app_id):
        return self._local_notes.get(app_id, '')

    def render(self):
        if not hasattr(self, 'table'):
            return
        previous = self.table.selection()
        self.table.delete(*self.table.get_children())
        self._row_installations = {}
        mode = self.status_filter.get()
        for mapping in self.mappings:
            game = self._games[mapping.app_id]
            installations = self._installed.get(mapping.app_id, ())
            if installations:
                for ordinal, installed in enumerate(installations):
                    note = self._installed_note(mapping.app_id)
                    if not self._matching(mapping, game, 'Installed') or (mode == 'Not detected'):
                        continue
                    row_id = f'{mapping.app_id}:{ordinal}'
                    self.table.insert('', 'end', iid=row_id, text=game.title,
                                      values=('Installed', installed.build_id or 'Unknown',
                                              self._updated(installed.last_updated),
                                              self._size(getattr(installed, 'size_on_disk', None)), note[:70]))
                    self._row_installations[row_id] = installed
            else:
                status = self._not_detected_status()
                if mode == 'Installed' or not self._matching(mapping, game, status):
                    continue
                note = self._installed_note(mapping.app_id)
                row_id = f'{mapping.app_id}:missing'
                self.table.insert('', 'end', iid=row_id, text=game.title,
                                  values=(status, '—', '—', '—', note[:70]))
                self._row_installations[row_id] = None
        if previous and self.table.exists(previous[0]):
            self.table.selection_set(previous[0])
        elif self.table.get_children():
            self.table.selection_set(self.table.get_children()[0])
        self.selection_changed()

    def _not_detected_status(self):
        if self._result is None:
            return 'Not scanned'
        if self._result.stop_reason == 'complete':
            return 'Not detected'
        return 'Not detected (partial scan)'

    def _selected_row(self):
        selected = self.table.selection()
        return selected[0] if selected else None

    def selection_changed(self, _event=None):
        row_id = self._selected_row()
        if row_id is None:
            self._set_details('Select a game to review its installation information.')
            self.launch_button.configure(state='disabled')
            self.folder_button.configure(state='disabled')
            self.note_button.configure(state='disabled')
            return
        app_id = row_id.split(':', 1)[0]
        game = self._games[app_id]
        installed = self._row_installations.get(row_id)
        note = self._installed_note(app_id)
        if installed is None:
            state = self._not_detected_status()
            detail = (f'{game.title} · {game.subtitle} [{game.platform}]\n'
                      f'Steam App ID: {app_id}\nInstallation: {state}\n'
                      'A missing row means no matching install was found in the scanned Steam libraries.')
        else:
            library = getattr(installed, 'library_path', None)
            if library is None:
                try:
                    library = installed.install_path.parents[2]
                except IndexError:
                    library = None
            detail = (f'{game.title} · {game.subtitle} [{game.platform}]\n'
                      f'Steam App ID: {app_id}\nSteam library: {library or "Unknown"}\n'
                      f'Install folder: {installed.install_path}\n'
                      f'Steam build ID: {installed.build_id or "Unknown"} (Steam metadata, not an in-game patch number)\n'
                      f'Last updated: {self._updated(installed.last_updated)} UTC · Install size: {self._size(getattr(installed, "size_on_disk", None))}')
        detail += f'\nLocal note: {note or "None"}'
        self._set_details(detail)
        enabled = installed is not None and not self.busy
        state = 'normal' if enabled else 'disabled'
        self.launch_button.configure(state=state)
        self.folder_button.configure(state=state)
        self.note_button.configure(state='normal' if not self.busy else 'disabled')

    def launch_selected(self):
        row_id = self._selected_row()
        installed = self._row_installations.get(row_id) if row_id else None
        if installed is None:
            return
        try:
            opened = game_hub.launch_via_steam(installed.app_id)
        except (OSError, ValueError, webbrowser.Error) as error:
            messagebox.showerror('Game Hub', f'Could not open Steam for this game. {error}', parent=self.root)
            return
        if not opened:
            messagebox.showinfo('Game Hub', 'The system could not open Steam. Check that Steam is installed and its game links are registered.',
                                parent=self.root)

    def open_selected_folder(self):
        row_id = self._selected_row()
        installed = self._row_installations.get(row_id) if row_id else None
        if installed is None:
            return
        try:
            game_hub.open_install_folder(installed.install_path)
        except (OSError, ValueError) as error:
            messagebox.showerror('Game Hub', f'Could not open the installation folder. {error}', parent=self.root)

    def edit_note(self):
        row_id = self._selected_row()
        if row_id is None:
            return
        app_id = row_id.split(':', 1)[0]
        game = self._games[app_id]
        previous = self._installed_note(app_id)
        note = simpledialog.askstring('Game Hub note',
                                      f'Local note for {game.title}. This does not change Steam installation data.',
                                      initialvalue=previous, parent=self.root)
        if note is None:
            return
        try:
            if len(note) > game_hub.MAX_NOTE_LENGTH:
                raise ValueError(f'Keep notes to {game_hub.MAX_NOTE_LENGTH} characters or fewer.')
            saved = self.notes.set_note(app_id, note)
            if saved:
                self._local_notes[app_id] = saved
            else:
                self._local_notes.pop(app_id, None)
        except (OSError, ValueError) as error:
            messagebox.showerror('Game Hub', str(error), parent=self.root)
            return
        self.render()

    def apply_theme(self, palette):
        self._palette = palette
        if 'background' in palette:
            self.details.configure(background=palette['background'], foreground=palette.get('text', '#222222'))

    def close(self):
        self._closed = True
        self._cancel.set()
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

    def _on_destroy(self, event):
        if event.widget is self.frame:
            self.close()

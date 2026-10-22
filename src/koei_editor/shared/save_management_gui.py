"""Save tools reached from Save Library; filesystem work stays off the Tk thread."""
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.game_registry import GAMES


class SaveManagementWindow:
    def __init__(self, root, *, game_id=None, paths=()):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title('Save Doctor · Detection · Save Vault')
        self.window.geometry('1000x780')
        self.window.minsize(820, 650)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.busy, self._closed, self._poll_id = False, False, None
        self.profile_window = None
        self._reverting_vault_path = False
        self._palette = {'background': ttk.Style(root).lookup('TFrame', 'background') or '#ffffff',
                         'text': ttk.Style(root).lookup('TLabel', 'foreground') or '#222222'}
        self._results, self._cancel = queue.SimpleQueue(), threading.Event()
        self._games = {f'{g.title} · {g.subtitle} [{g.platform}]': g.id for g in GAMES}
        self.frame = ttk.Frame(self.window, padding=16)
        self.frame.pack(fill='both', expand=True)
        ttk.Label(self.frame, text='Save management', font=('TkDefaultFont', 18, 'bold')).pack(anchor='w')
        ttk.Label(self.frame, text='Diagnose copied saves, find installed games, and keep verified local history.',
                  style='Muted.TLabel').pack(anchor='w', pady=(4, 12))
        self.game = tk.StringVar(self.window)
        self.selector = ttk.Combobox(self.frame, textvariable=self.game, values=tuple(self._games), state='readonly')
        self.selector.pack(fill='x', pady=(0, 10))
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill='both', expand=True)
        self.controls = [self.selector]
        self.doctor_tab, self.discovery_tab, self.vault_tab = [ttk.Frame(self.notebook, padding=12) for _ in range(3)]
        for frame, title in ((self.doctor_tab, 'Save Doctor'), (self.discovery_tab, 'Automatic Detection'), (self.vault_tab, 'Save Vault')):
            self.notebook.add(frame, text=title)
        self._doctor_form()
        self._discovery_form()
        self._vault_form()
        self.apply_theme(self._palette)
        self.status = tk.StringVar(self.window, value='Choose a game/platform and separate save copies.')
        ttk.Label(self.frame, textvariable=self.status, wraplength=900).pack(anchor='w', pady=(10, 4))
        self.show(game_id=game_id, paths=paths)
        self.window.bind('<Destroy>', self._destroyed, add='+')

    def _button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side='left', padx=(0, 8), pady=6)
        self.controls.append(button)
        return button

    def _path_row(self, parent, caption, variable, *, directory=False):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text=caption, width=18).pack(side='left')
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side='left', fill='x', expand=True)
        def choose():
            selected = (filedialog.askdirectory(parent=self.window, mustexist=True) if directory else
                        filedialog.askopenfilename(parent=self.window))
            if selected:
                variable.set(selected)
        self._button(row, 'Browse…', choose)
        self.controls.append(entry)

    @staticmethod
    def _output(parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, pady=(8, 0))
        text = tk.Text(frame, wrap='word', height=10, state='disabled')
        bar = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=bar.set)
        text.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        return text

    @staticmethod
    def _set_output(widget, value):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', value)
        widget.configure(state='disabled')

    def _doctor_form(self):
        self.paths = ()
        self.copy_path = tk.StringVar(self.window)
        self._path_row(self.doctor_tab, 'Separate save copy', self.copy_path)
        self.expected = tk.StringVar(self.window)
        row = ttk.Frame(self.doctor_tab)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text='Expected SHA-256', width=18).pack(side='left')
        entry = ttk.Entry(row, textvariable=self.expected)
        entry.pack(side='left', fill='x', expand=True)
        self.controls.append(entry)
        ttk.Label(self.doctor_tab, text='An optional known digest checks file identity. Native validation uses only the selected profile. '
                  'No repairs are made. Game-load validation remains separate.', wraplength=850, style='Muted.TLabel').pack(anchor='w', pady=8)
        actions = ttk.Frame(self.doctor_tab)
        actions.pack(fill='x')
        self.diagnose_button = self._button(actions, 'Diagnose copy / selected copies', self.diagnose)
        self.export_button = self._button(actions, 'Export last report…', self.export_doctor)
        self.doctor_output = self._output(self.doctor_tab)
        self.doctor_reports = ()

    def _discovery_form(self):
        self.steam_root = tk.StringVar(self.window)
        self._path_row(self.discovery_tab, 'Steam root (optional)', self.steam_root, directory=True)
        ttk.Label(self.discovery_tab, text='Finds reviewed game installs and candidate save folders using bounded, read-only checks. '
                  'Candidate locations are not validated saves. Copy saves and required original metadata to a separate folder before diagnosis or editing.',
                  wraplength=850, style='Muted.TLabel').pack(anchor='w', pady=8)
        actions = ttk.Frame(self.discovery_tab)
        actions.pack(fill='x')
        self.discovery_button = self._button(actions, 'Detect installed games and saves', self.discover)
        self.cancel_button = ttk.Button(actions, text='Cancel detection', command=lambda: self._cancel.set(), state='disabled')
        self.cancel_button.pack(side='left')
        self.discovery_output = self._output(self.discovery_tab)

    def _vault_form(self):
        self.vault_path = tk.StringVar(self.window)
        self._path_row(self.vault_tab, 'Local vault folder', self.vault_path, directory=True)
        actions = ttk.Frame(self.vault_tab)
        actions.pack(fill='x')
        self._button(actions, 'Create vault…', self.create_vault)
        self._button(actions, 'Load history', self.load_vault)
        self._button(actions, 'Verify all', self.verify_vault)
        self._button(actions, 'Snapshot selected copies', self.snapshot)
        options = ttk.Frame(self.vault_tab)
        options.pack(fill='x')
        self.branch_name, self.snapshot_label = tk.StringVar(self.window, value='main'), tk.StringVar(self.window)
        for label, variable in (('Branch', self.branch_name), ('Label', self.snapshot_label)):
            ttk.Label(options, text=label).pack(side='left', padx=(0, 6))
            entry = ttk.Entry(options, textvariable=variable, width=24)
            entry.pack(side='left', padx=(0, 14))
            self.controls.append(entry)
        history_frame = ttk.Frame(self.vault_tab)
        history_frame.pack(fill='x', pady=8)
        self.history = ttk.Treeview(history_frame, columns=('game', 'filename', 'created_utc', 'branch', 'label'),
                                   show='tree headings', height=6, selectmode='extended')
        self.history.heading('#0', text='Snapshot ID')
        self.history.column('#0', width=210, minwidth=150)
        for name, title, width, minimum in (('game', 'Game', 110, 70), ('filename', 'Gameplay file', 150, 110),
                                           ('created_utc', 'Created (UTC)', 230, 150),
                                           ('branch', 'Branch', 90, 70), ('label', 'Label', 130, 90)):
            self.history.heading(name, text=title)
            self.history.column(name, width=width, minwidth=minimum)
        self.history_scrollbar = ttk.Scrollbar(history_frame, orient='vertical', command=self.history.yview)
        self.history_horizontal_scrollbar = ttk.Scrollbar(history_frame, orient='horizontal', command=self.history.xview)
        self.history.configure(yscrollcommand=self.history_scrollbar.set,
                               xscrollcommand=self.history_horizontal_scrollbar.set)
        history_frame.columnconfigure(0, weight=1)
        self.history.grid(row=0, column=0, sticky='nsew')
        self.history_scrollbar.grid(row=0, column=1, sticky='ns')
        self.history_horizontal_scrollbar.grid(row=1, column=0, sticky='ew')
        actions = ttk.Frame(self.vault_tab)
        actions.pack(fill='x')
        self._button(actions, 'Restore to new folder…', self.restore)
        self._button(actions, 'Compare two', self.compare)
        self._button(actions, 'Branch from selected', self.branch)
        self._button(actions, 'Update label', self.relabel)
        self._button(actions, 'Remove history entry…', self.delete)
        profile_actions = ttk.Frame(self.vault_tab)
        profile_actions.pack(fill='x', pady=(3, 0))
        self._button(profile_actions, 'Smart Playthrough Profiles…', self.open_playthrough_profiles)
        ttk.Label(profile_actions,
                  text='Compose verified snapshots with exact-version metadata and optional manager exports.',
                  style='Muted.TLabel').pack(side='left', padx=(4, 0))
        ttk.Label(self.vault_tab, text='Restores create a new directory and verify its exact bytes and original context. '
                  'Snapshots preserve local backups; live saves and existing destinations stay protected.',
                  wraplength=850, style='Muted.TLabel').pack(anchor='w')
        self.vault_output = self._output(self.vault_tab)
        self.vault_path.trace_add('write', self._vault_changed)

    def _vault_changed(self, *_args):
        if self._reverting_vault_path:
            return
        profile_window = self.profile_window
        selected_vault_path = self.vault_path.get().strip()
        if profile_window is not None and not getattr(profile_window, '_closed', False):
            if profile_window.busy:
                if selected_vault_path != profile_window.vault_path:
                    self._reverting_vault_path = True
                    try:
                        self.vault_path.set(profile_window.vault_path)
                    finally:
                        self._reverting_vault_path = False
                    messagebox.showinfo(
                        'Profile operation running',
                        'Wait for the current profile operation to finish before changing Save Vaults.',
                        parent=self.window,
                    )
                return
            if selected_vault_path != profile_window.vault_path:
                profile_window.close()
                self.profile_window = None
                self.status.set('Vault changed. Reopen Smart Playthrough Profiles to use the selected Vault.')
        self.history.delete(*self.history.get_children())
        self._set_output(self.vault_output, 'Load this vault to view its history.')

    def _profile_operation_busy(self):
        profile_window = self.profile_window
        return (profile_window is not None
                and not getattr(profile_window, '_closed', False)
                and bool(getattr(profile_window, 'busy', False)))

    def show(self, *, game_id=None, paths=()):
        if self._closed:
            return
        if not self.busy:
            if game_id:
                self.game.set(next((label for label, value in self._games.items() if value == game_id), ''))
            self.paths = tuple(Path(path) for path in paths)
            if self.paths:
                self.copy_path.set(str(self.paths[0]))
        self.window.deiconify()
        self.window.lift()

    def _selected_paths(self):
        entered = self.copy_path.get().strip()
        if self.paths and entered == str(self.paths[0]):
            return self.paths
        if not entered:
            raise ValueError('Choose a separate save copy first.')
        return (Path(entered),)

    def _game_id(self):
        if self.game.get() not in self._games:
            raise ValueError('Choose an exact game/platform first.')
        return self._games[self.game.get()]

    def _start(self, operation, on_success, *, detecting=False):
        if self.busy or self._closed:
            return
        self.busy = True
        self._cancel = threading.Event()
        for control in self.controls:
            control.configure(state='disabled')
        self.cancel_button.configure(state='normal' if detecting else 'disabled')
        self.status.set('Checking save data…' if not detecting else 'Detecting installed games and save locations…')
        def worker():
            try:
                result = operation()
            except Exception:
                self._results.put((False, None, on_success))
            else:
                self._results.put((True, result, on_success))
        threading.Thread(target=worker, daemon=True).start()
        self._poll_id = self.window.after(30, self._poll)

    def _poll(self):
        self._poll_id = None
        if self._closed:
            return
        try:
            success, value, callback = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.window.after(30, self._poll)
            return
        self.busy = False
        for control in self.controls:
            control.configure(state='readonly' if control is self.selector else 'normal')
        self.cancel_button.configure(state='disabled')
        if success:
            callback(value)
            self.status.set('Operation finished. Review the result below.')
        else:
            self.status.set('Operation failed. Check the selected profile, separate copy, vault integrity and destination.')
            messagebox.showerror('Save management', self.status.get(), parent=self.window)

    def _invoke(self, prepare):
        if self.busy:
            return
        try:
            prepare()
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror('Save management', str(error), parent=self.window)

    @staticmethod
    def _json(value):
        def convert(item):
            if is_dataclass(item):
                return asdict(item)
            raise TypeError('Unsupported report value.')
        return json.dumps(value, indent=2, ensure_ascii=True, default=convert)

    def diagnose(self):
        def prepare():
            from koei_editor.shared.save_doctor import inspect_save
            game, paths, digest = self._game_id(), self._selected_paths(), self.expected.get().strip() or None
            if digest and len(paths) != 1:
                raise ValueError('A known SHA-256 digest applies to one selected copy at a time.')
            def complete(reports):
                self.doctor_reports = reports
                self._set_output(self.doctor_output, '\n\n'.join(f'Copy {index + 1}: {paths[index].name}\n{report.to_text()}' for index, report in enumerate(reports)))
            self._start(lambda: tuple(inspect_save(game, path, expected_sha256=digest) for path in paths), complete)
        self._invoke(prepare)

    def export_doctor(self):
        if not self.doctor_reports:
            return
        path = filedialog.asksaveasfilename(parent=self.window, title='New diagnostic report', defaultextension='.json', filetypes=(('JSON report', '*.json'),))
        if not path:
            return
        def prepare():
            from koei_editor.shared.copy_storage import atomic_new
            from koei_editor.shared.save_safety import safe_path
            from koei_editor.shared.save_library import _checked_path
            reports = tuple(report.to_dict() for report in self.doctor_reports)
            encoded = (json.dumps(reports, indent=2, ensure_ascii=True) + '\n').encode('utf-8')
            def export():
                if Path(path).suffix.lower() != '.json':
                    raise ValueError('Choose a new .json diagnostic report.')
                _checked_path(Path(path).absolute().parent, directory=True)
                destination = safe_path(path)
                return atomic_new(encoded, destination)
            self._start(export, lambda _result: None)
        self._invoke(prepare)

    def discover(self):
        from koei_editor.shared.save_discovery import discover_saves, report
        roots = [self.steam_root.get().strip()] if self.steam_root.get().strip() else None
        def complete(result):
            lines = [self._json(report(result)), '\nCandidate locations on this computer:']
            lines.extend(f'{item.game_id}: {item.path} ({item.source})' for item in result.locations)
            self._set_output(self.discovery_output, '\n'.join(lines))
        self._start(lambda: discover_saves(steam_roots=roots, cancel=self._cancel), complete, detecting=True)

    def _ids(self, count):
        selected = self.history.selection()
        if len(selected) != count:
            raise ValueError(f'Select exactly {count} snapshot(s).')
        return selected

    def _history_result(self, snapshots):
        selected = self.history.selection()
        self.history.delete(*self.history.get_children())
        for item in snapshots:
            self.history.insert('', 'end', iid=item.id, text=item.id,
                                values=(item.game_id, item.filename, item.created_utc, item.branch, item.label))
        self.history.selection_set(tuple(item for item in selected if self.history.exists(item)))
        self._set_output(self.vault_output, f'{len(snapshots)} local snapshots. Select a snapshot to restore or manage it.')

    def create_vault(self):
        if self._profile_operation_busy():
            messagebox.showinfo(
                'Profile operation running',
                'Wait for the current profile operation to finish before creating or loading a Vault.',
                parent=self.window,
            )
            return
        parent = filedialog.askdirectory(parent=self.window, title='Choose parent folder for a NEW SaveVault directory', mustexist=True)
        if not parent:
            return
        destination = Path(parent) / 'SaveVault'
        destination_text = str(destination)
        self.vault_path.set(destination_text)
        if (self._profile_operation_busy()
                or self.vault_path.get().strip() != destination_text):
            return
        def prepare():
            if (self._profile_operation_busy()
                    or self.vault_path.get().strip() != destination_text):
                return
            from koei_editor.shared.save_vault import SaveVault
            self._start(lambda: SaveVault.create(destination).list_snapshots(), self._history_result)
        self._invoke(prepare)

    def load_vault(self):
        if self._profile_operation_busy():
            messagebox.showinfo(
                'Profile operation running',
                'Wait for the current profile operation to finish before creating or loading a Vault.',
                parent=self.window,
            )
            return
        selected_vault_path = self.vault_path.get().strip()
        def prepare():
            if self._profile_operation_busy():
                return
            path = self.vault_path.get().strip()
            if path != selected_vault_path:
                return
            if not path:
                raise ValueError('Choose a local vault folder first.')
            from koei_editor.shared.save_vault import SaveVault
            self._start(lambda: SaveVault(path).list_snapshots(), self._history_result)
        self._invoke(prepare)

    def _vault_action(self, action):
        def prepare():
            path = self.vault_path.get().strip()
            if not path:
                raise ValueError('Choose a local vault folder first.')
            from koei_editor.shared.save_vault import SaveVault
            def run():
                vault = SaveVault(path)
                return action(vault), vault.list_snapshots()
            def complete(result):
                outcome, snapshots = result
                self._history_result(snapshots)
                self._set_output(self.vault_output, self._json(outcome))
            self._start(run, complete)
        self._invoke(prepare)

    def verify_vault(self):
        self._vault_action(lambda vault: vault.verify())

    def snapshot(self):
        def prepare():
            game, paths = self._game_id(), self._selected_paths()
            branch, label, vault_path = self.branch_name.get().strip(), self.snapshot_label.get(), self.vault_path.get().strip()
            if not branch or not vault_path:
                raise ValueError('Choose a vault and branch first.')
            from koei_editor.shared.save_vault import SaveVault
            def capture():
                vault = SaveVault(vault_path)
                completed = []
                for index, path in enumerate(paths):
                    try:
                        item = vault.snapshot(game, path, branch=branch, label=label)
                    except (OSError, ValueError, TypeError):
                        completed.append({'copy': index + 1, 'saved': False})
                    else:
                        completed.append({'copy': index + 1, 'saved': True, 'snapshot_id': item.id})
                return completed, vault.list_snapshots()
            def complete(result):
                outcomes, snapshots = result
                self._history_result(snapshots)
                self._set_output(self.vault_output, self._json(outcomes))
            self._start(capture, complete)
        self._invoke(prepare)

    def restore(self):
        def prepare():
            snapshot_id, = self._ids(1)
            parent = filedialog.askdirectory(parent=self.window, title='Parent folder for a NEW restored-save directory', mustexist=True)
            if parent:
                destination = Path(parent) / ('Restored-' + snapshot_id)
                self._vault_action(lambda vault: (vault.restore(snapshot_id, destination), {'restored': True})[1])
        self._invoke(prepare)

    def compare(self):
        self._invoke(lambda: self._compare_selected())

    def _compare_selected(self):
        first, second = self._ids(2)
        self._vault_action(lambda vault: vault.compare(first, second))

    def branch(self):
        def prepare():
            snapshot_id, = self._ids(1)
            name = self.branch_name.get().strip()
            if not name:
                raise ValueError('Enter a new branch name first.')
            self._vault_action(lambda vault: (vault.branch(name, snapshot_id), {'branched': True, 'branch': name})[1])
        self._invoke(prepare)

    def relabel(self):
        def prepare():
            snapshot_id, = self._ids(1)
            label = self.snapshot_label.get()
            self._vault_action(lambda vault: vault.relabel(snapshot_id, label))
        self._invoke(prepare)

    def delete(self):
        def prepare():
            snapshot_id, = self._ids(1)
            if messagebox.askyesno('Remove history entry', 'Remove this leaf snapshot from visible history? Stored backup bytes are retained. This cannot be undone.', parent=self.window):
                self._vault_action(lambda vault: (vault.delete(snapshot_id), {'deleted': True})[1])
        self._invoke(prepare)

    def open_playthrough_profiles(self):
        if self.busy:
            return
        vault_path = self.vault_path.get().strip()
        if not vault_path:
            messagebox.showerror('Smart Playthrough Profiles', 'Choose or create a Save Vault first.', parent=self.window)
            return
        selected = self.history.selection()
        selected_snapshot_id = selected[0] if len(selected) == 1 else None
        if self.profile_window is not None and not getattr(self.profile_window, '_closed', False):
            if self.profile_window.vault_path == vault_path:
                self.profile_window.show(selected_snapshot_id)
                return
            if self.profile_window.busy:
                messagebox.showinfo(
                    'Profile operation running',
                    'Wait for the current profile operation to finish before changing Save Vaults.',
                    parent=self.window,
                )
                return
            self.profile_window.close()
            self.profile_window = None
        from koei_editor.shared.playthrough_profiles_gui import PlaythroughProfilesWindow
        self.profile_window = PlaythroughProfilesWindow(
            self.window, vault_path=vault_path, selected_snapshot_id=selected_snapshot_id,
            palette=self._palette,
        )

    def _destroyed(self, event):
        if event.widget is self.window:
            self._closed = True
            self._cancel.set()

    def apply_theme(self, palette):
        if self._closed:
            return
        self._palette = dict(palette)
        for widget in (self.doctor_output, self.discovery_output, self.vault_output):
            widget.configure(background=palette['background'], foreground=palette['text'],
                             insertbackground=palette['text'])
        if self.profile_window is not None and not getattr(self.profile_window, '_closed', False):
            self.profile_window.apply_theme(palette)

    def close(self):
        if self._closed:
            return
        if self.busy:
            self._cancel.set()
            messagebox.showinfo('Save management', 'Wait for the current save operation to finish before closing.', parent=self.window)
            return
        if (self.profile_window is not None and not getattr(self.profile_window, '_closed', False)
                and self.profile_window.busy):
            messagebox.showinfo('Save management', 'Wait for the playthrough profile operation to finish before closing.', parent=self.window)
            return
        self._closed = True
        self._cancel.set()
        if self._poll_id is not None:
            self.window.after_cancel(self._poll_id)
            self._poll_id = None
        if self.profile_window is not None and not getattr(self.profile_window, '_closed', False):
            self.profile_window.close()
        self.window.destroy()

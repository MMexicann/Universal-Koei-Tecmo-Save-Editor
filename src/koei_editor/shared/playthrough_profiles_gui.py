"""Safe local Smart Playthrough profile management.

Manager exports stay inert JSON snapshots. This window can preview exact game
version compatibility and prepare a new isolated environment, but it does not
launch a game or apply mods, settings, builds, or saves to a live location.
"""
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.game_registry import GAMES


_COMPONENTS = (
    ('mod_configuration', 'Mod Manager snapshot'),
    ('game_settings', 'Configuration Manager snapshot'),
    ('character_build', 'Character Workshop snapshot'),
)


class PlaythroughProfilesWindow:
    def __init__(self, parent, *, vault_path, selected_snapshot_id=None, palette=None):
        self.parent = parent
        self.vault_path = str(vault_path)
        self.window = tk.Toplevel(parent)
        self.window.title('Smart Playthrough Profiles')
        self.window.geometry('1040x760')
        self.window.minsize(860, 660)
        self.window.transient(parent)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.busy = False
        self._closed = False
        self._poll_id = None
        self._results = queue.SimpleQueue()
        self._cancel = threading.Event()
        self._palette = palette or {
            'background': ttk.Style(parent).lookup('TFrame', 'background') or '#ffffff',
            'text': ttk.Style(parent).lookup('TLabel', 'foreground') or '#222222',
        }
        self.snapshots = {}
        self.profiles = {}
        self.last_preview = None
        self.current_report = None
        self.controls = []

        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Smart Playthrough Profiles',
                  font=('TkDefaultFont', 18, 'bold')).pack(anchor='w')
        ttk.Label(
            frame,
            text=('Combine a verified Save Vault snapshot with exact game-version compatibility and '
                  'optional manager exports. Imported mod, settings, and build files stay inert; '
                  'this editor does not launch a game or apply them.'),
            wraplength=950, style='Muted.TLabel',
        ).pack(anchor='w', pady=(4, 12))

        self.notebook = ttk.Notebook(frame)
        self.notebook.pack(fill='both', expand=True)
        self.create_tab = ttk.Frame(self.notebook, padding=12)
        self.library_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.create_tab, text='Create profile')
        self.notebook.add(self.library_tab, text='Preview and prepare')
        self._create_form(selected_snapshot_id)
        self._library_form()

        self.status = tk.StringVar(self.window, value='Loading verified Save Vault snapshots and local profiles…')
        ttk.Label(frame, textvariable=self.status, wraplength=950).pack(anchor='w', pady=(10, 2))
        self.apply_theme(self._palette)
        self.window.bind('<Destroy>', self._destroyed, add='+')
        self._refresh()

    def _path_row(self, parent, caption, variable, *, kind):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=caption, width=31).pack(side='left')
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side='left', fill='x', expand=True)
        self.controls.append(entry)

        def choose():
            if kind == 'file':
                selected = filedialog.askopenfilename(
                    parent=self.window, title='Import manager JSON snapshot',
                    filetypes=(('Playthrough component JSON', '*.json'), ('JSON files', '*.json')),
                )
            else:
                selected = filedialog.askdirectory(parent=self.window, title='Choose parent for a NEW isolated environment',
                                                   mustexist=True)
            if selected:
                variable.set(selected)

        button = ttk.Button(row, text='Browse…', command=choose)
        button.pack(side='left', padx=(8, 0))
        self.controls.append(button)
        return entry

    def _button(self, parent, label, callback):
        button = ttk.Button(parent, text=label, command=callback)
        button.pack(side='left', padx=(0, 8), pady=4)
        self.controls.append(button)
        return button

    @staticmethod
    def _output(parent, height=9):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill='both', expand=True, pady=(8, 0))
        widget = tk.Text(wrapper, wrap='word', height=height, state='disabled')
        scrollbar = ttk.Scrollbar(wrapper, orient='vertical', command=widget.yview)
        widget.configure(yscrollcommand=scrollbar.set)
        widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        return widget

    @staticmethod
    def _set_output(widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')

    def _create_form(self, selected_snapshot_id):
        self.profile_name = tk.StringVar(self.window)
        self.profile_game_version = tk.StringVar(self.window)
        self.snapshot_choice = tk.StringVar(self.window)
        name_row = ttk.Frame(self.create_tab)
        name_row.pack(fill='x', pady=3)
        ttk.Label(name_row, text='Profile name', width=31).pack(side='left')
        name_entry = ttk.Entry(name_row, textvariable=self.profile_name)
        name_entry.pack(side='left', fill='x', expand=True)
        self.controls.append(name_entry)

        row = ttk.Frame(self.create_tab)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text='Verified Save Vault snapshot', width=31).pack(side='left')
        self.snapshot_selector = ttk.Combobox(row, textvariable=self.snapshot_choice, state='readonly')
        self.snapshot_selector.pack(side='left', fill='x', expand=True)
        self.controls.append(self.snapshot_selector)
        refresh = ttk.Button(row, text='Refresh', command=self._refresh)
        refresh.pack(side='left', padx=(8, 0))
        self.controls.append(refresh)

        version_row = ttk.Frame(self.create_tab)
        version_row.pack(fill='x', pady=3)
        ttk.Label(version_row, text='Exact game version', width=31).pack(side='left')
        version_entry = ttk.Entry(version_row, textvariable=self.profile_game_version)
        version_entry.pack(side='left', fill='x', expand=True)
        self.controls.append(version_entry)
        ttk.Label(self.create_tab,
                  text='Compatibility is an exact version match. Enter the game build you intend to use; an unknown version is not inferred.',
                  wraplength=920, style='Muted.TLabel').pack(anchor='w', pady=(3, 8))

        self.component_paths = {}
        ttk.Label(self.create_tab, text='Optional manager snapshots', font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=(6, 2))
        for component, caption in _COMPONENTS:
            variable = tk.StringVar(self.window)
            self.component_paths[component] = variable
            self._path_row(self.create_tab, caption + ' (JSON)', variable, kind='file')
        ttk.Label(
            self.create_tab,
            text=('Each import must be an exported component snapshot for the same game and exact game version. '
                  'The Mod Manager is available separately, but no profile export/apply adapter connects it here. '
                  'Configuration Manager and Character Workshop profile adapters are not connected either. '
                  'Imported components stay inert JSON and never control a manager.'),
            wraplength=920, style='Muted.TLabel',
        ).pack(anchor='w', pady=(5, 8))
        actions = ttk.Frame(self.create_tab)
        actions.pack(fill='x')
        self.create_button = self._button(actions, 'Create from selected snapshot', self.create_profile)
        self.create_output = self._output(self.create_tab, height=6)
        if selected_snapshot_id:
            self.snapshot_choice.set(selected_snapshot_id)

    def _library_form(self):
        self.library_tab.columnconfigure(0, weight=1)
        self.library_tab.rowconfigure(1, weight=1)
        self.library_tab.rowconfigure(7, weight=1)
        ttk.Label(self.library_tab, text='Local profiles', font=('TkDefaultFont', 10, 'bold')).grid(
            row=0, column=0, sticky='w')
        tree_frame = ttk.Frame(self.library_tab)
        tree_frame.grid(row=1, column=0, sticky='nsew', pady=(5, 8))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.profile_tree = ttk.Treeview(
            tree_frame, columns=('game', 'version', 'snapshot', 'components'),
            show='tree headings', height=6, selectmode='browse',
        )
        self.profile_tree.heading('#0', text='Profile')
        self.profile_tree.column('#0', width=210, minwidth=140)
        for name, title, width, minimum in (
            ('game', 'Game/platform', 210, 140), ('version', 'Exact game version', 130, 90),
            ('snapshot', 'Save Vault snapshot', 260, 160), ('components', 'Manager snapshots', 140, 100),
        ):
            self.profile_tree.heading(name, text=title)
            self.profile_tree.column(name, width=width, minwidth=minimum)
        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.profile_tree.yview)
        self.profile_tree.configure(yscrollcommand=scroll.set)
        self.profile_tree.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        self.controls.append(self.profile_tree)

        version_row = ttk.Frame(self.library_tab)
        version_row.grid(row=2, column=0, sticky='ew', pady=4)
        ttk.Label(version_row, text='Installed game version (enter manually)', width=36).pack(side='left')
        self.installed_game_version = tk.StringVar(self.window)
        version_entry = ttk.Entry(version_row, textvariable=self.installed_game_version)
        version_entry.pack(side='left', fill='x', expand=True)
        self.controls.append(version_entry)

        active_row = ttk.Frame(self.library_tab)
        active_row.grid(row=3, column=0, sticky='ew', pady=4)
        ttk.Label(active_row, text='Optional separate save copy to back up', width=36).pack(side='left')
        self.active_save_copy = tk.StringVar(self.window)
        active_entry = ttk.Entry(active_row, textvariable=self.active_save_copy)
        active_entry.pack(side='left', fill='x', expand=True)
        self.controls.append(active_entry)
        active_browse = ttk.Button(active_row, text='Browse…', command=self._browse_active_save)
        active_browse.pack(side='left', padx=(8, 0))
        self.controls.append(active_browse)

        destination_row = ttk.Frame(self.library_tab)
        destination_row.grid(row=4, column=0, sticky='ew', pady=4)
        ttk.Label(destination_row, text='Parent folder for a NEW environment', width=36).pack(side='left')
        self.destination_parent = tk.StringVar(self.window)
        destination_entry = ttk.Entry(destination_row, textvariable=self.destination_parent)
        destination_entry.pack(side='left', fill='x', expand=True)
        self.controls.append(destination_entry)
        destination_browse = ttk.Button(destination_row, text='Browse…', command=self._browse_destination_parent)
        destination_browse.pack(side='left', padx=(8, 0))
        self.controls.append(destination_browse)

        ttk.Label(
            self.library_tab,
            text=('The Game Version Tracker reports Steam build IDs, but Playthrough Profiles needs the game product version shown in-game. '
                  'Enter that product version manually; tracker build IDs are not used as substitutes. '
                  'Optional backup accepts only an independent copied save; live and cloud paths are rejected. '
                  'Preparing a profile restores the selected Vault snapshot into a brand-new isolated environment. '
                  'Existing folders are never replaced and live saves/configuration are never written.'),
            wraplength=920, style='Muted.TLabel',
        ).grid(row=5, column=0, sticky='w', pady=(3, 5))
        actions = ttk.Frame(self.library_tab)
        actions.grid(row=6, column=0, sticky='ew')
        self._button(actions, 'Preview compatibility', self.preview_profile)
        self.prepare_button = self._button(actions, 'Prepare isolated environment…', self.prepare_environment)
        self._button(actions, 'Export visible report…', self.export_report)
        output_frame = ttk.Frame(self.library_tab)
        output_frame.grid(row=7, column=0, sticky='nsew', pady=(8, 0))
        self.library_output = self._output(output_frame, height=7)
        self.profile_tree.bind('<<TreeviewSelect>>', self._profile_selected)

    def _browse_active_save(self):
        path = filedialog.askopenfilename(parent=self.window, title='Choose a separate copied save to back up')
        if path:
            self.active_save_copy.set(path)

    def _browse_destination_parent(self):
        path = filedialog.askdirectory(parent=self.window, title='Parent folder for a NEW isolated environment',
                                       mustexist=True)
        if path:
            self.destination_parent.set(path)

    def _profile_selected(self, _event=None):
        self.last_preview = None
        self.current_report = None
        self._set_output(self.library_output, 'Preview the selected profile against the exact installed game version before preparing an environment.')

    def _selected_profile_id(self):
        selected = self.profile_tree.selection()
        if len(selected) != 1:
            raise ValueError('Select one playthrough profile first.')
        return selected[0]

    def _start(self, operation, on_success, *, label='Working…'):
        if self.busy or self._closed:
            return
        self.busy = True
        self._cancel = threading.Event()
        for control in self.controls:
            try:
                control.configure(state='disabled')
            except tk.TclError:
                pass
        self.status.set(label)

        def worker():
            try:
                value = operation()
            except Exception as error:
                self._results.put((False, str(error), on_success))
            else:
                self._results.put((True, value, on_success))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_id = self.window.after(30, self._poll)

    def _poll(self):
        self._poll_id = None
        if self._closed:
            return
        try:
            succeeded, value, callback = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.window.after(30, self._poll)
            return
        self.busy = False
        for control in self.controls:
            try:
                if control is self.snapshot_selector:
                    control.configure(state='readonly')
                elif control is self.profile_tree:
                    control.configure(state='normal')
                else:
                    control.configure(state='normal')
            except tk.TclError:
                pass
        if succeeded:
            previous_status = self.status.get()
            callback(value)
            if self.status.get() == previous_status:
                self.status.set('Operation finished. Review the result below.')
        else:
            self.status.set('Operation failed. No live save, mod, settings, or build data was applied.')
            messagebox.showerror('Smart Playthrough Profiles', value, parent=self.window)

    def _refresh(self):
        def operation():
            from koei_editor.shared.save_vault import SaveVault
            from koei_editor.shared.playthrough_profiles import PlaythroughProfileStore
            vault = SaveVault(self.vault_path)
            snapshots = vault.list_snapshots()
            verified = {item.snapshot_id: item.valid for item in vault.verify()}
            visible = tuple(item for item in snapshots if verified.get(item.id, False))
            return visible, PlaythroughProfileStore(vault).list_profiles(), len(snapshots) - len(visible)

        def complete(result):
            snapshots, profiles, rejected = result
            self.snapshots = {item.id: item for item in snapshots}
            self.profiles = {item.id: item for item in profiles}
            current = self.snapshot_choice.get()
            snapshot_values = tuple(
                f'{item.id} · {item.game_id} · {item.filename} · {item.branch}'
                for item in snapshots
            )
            self._snapshot_labels = {label.split(' · ', 1)[0]: label for label in snapshot_values}
            self.snapshot_selector.configure(values=snapshot_values)
            selected_id = current.split(' · ', 1)[0] if current else ''
            if selected_id not in self.snapshots:
                selected_id = next(iter(self.snapshots), '')
            if selected_id:
                self.snapshot_choice.set(self._snapshot_labels[selected_id])
            else:
                self.snapshot_choice.set('')

            selected_profiles = self.profile_tree.selection()
            self.profile_tree.delete(*self.profile_tree.get_children())
            game_labels = {game.id: f'{game.title} · {game.platform}' for game in GAMES}
            for profile in profiles:
                self.profile_tree.insert(
                    '', 'end', iid=profile.id, text=profile.name,
                    values=(game_labels.get(profile.game_id, profile.game_id), profile.game_version,
                            profile.save_snapshot_id, ', '.join(component.component for component in profile.components) or 'Save only'),
                )
            if selected_profiles and self.profile_tree.exists(selected_profiles[0]):
                self.profile_tree.selection_set(selected_profiles[0])
            self.last_preview = None
            self.current_report = None
            hidden = f' {rejected} invalid snapshot(s) hidden.' if rejected else ''
            self._set_output(self.create_output, f'{len(snapshots)} verified Save Vault snapshots available.{hidden}')
            self._set_output(self.library_output, f'{len(profiles)} local playthrough profiles. Select one to preview exact version compatibility.')

        self._start(operation, complete, label='Loading verified snapshots and profiles…')

    def create_profile(self):
        name = self.profile_name.get().strip()
        version = self.profile_game_version.get().strip()
        choice = self.snapshot_choice.get().strip()
        if not name or not version or not choice:
            messagebox.showerror('Smart Playthrough Profiles', 'Enter a profile name and exact game version, then choose a verified Save Vault snapshot.', parent=self.window)
            return
        snapshot_id = choice.split(' · ', 1)[0]
        snapshot = self.snapshots.get(snapshot_id)
        if snapshot is None:
            messagebox.showerror('Smart Playthrough Profiles', 'Refresh and choose an available Save Vault snapshot.', parent=self.window)
            return
        component_paths = {kind: variable.get().strip() for kind, variable in self.component_paths.items() if variable.get().strip()}

        def operation():
            from koei_editor.shared.playthrough_profiles import (
                PlaythroughProfileStore, load_component_snapshot,
            )
            from koei_editor.shared.save_vault import SaveVault
            vault = SaveVault(self.vault_path)
            components = tuple(load_component_snapshot(path) for path in component_paths.values())
            for component in components:
                if component.game_id != snapshot.game_id or component.game_version != version:
                    raise ValueError('Imported manager snapshots must match the selected save game and exact version.')
            return PlaythroughProfileStore(vault).create_profile(
                name, snapshot.game_id, version, snapshot_id, components=components,
            )

        def complete(profile):
            self.profile_name.set('')
            for variable in self.component_paths.values():
                variable.set('')
            self._set_output(self.create_output, json.dumps({
                'created': True, 'profile_id': profile.id, 'game_id': profile.game_id,
                'game_version': profile.game_version, 'save_snapshot_id': profile.save_snapshot_id,
                'components': [component.component for component in profile.components],
            }, indent=2, ensure_ascii=True))
            self.notebook.select(self.library_tab)
            self._refresh()

        self._start(operation, complete, label='Verifying snapshot and creating profile…')

    def preview_profile(self):
        try:
            profile_id = self._selected_profile_id()
        except ValueError as error:
            messagebox.showerror('Smart Playthrough Profiles', str(error), parent=self.window)
            return
        installed = self.installed_game_version.get().strip()
        if not installed:
            messagebox.showerror('Smart Playthrough Profiles', 'Enter the exact installed game version before previewing compatibility.', parent=self.window)
            return

        def operation():
            from koei_editor.shared.playthrough_profiles import PlaythroughProfileStore
            from koei_editor.shared.save_vault import SaveVault
            return PlaythroughProfileStore(SaveVault(self.vault_path)).preview(profile_id, installed)

        def complete(preview):
            self.last_preview = (profile_id, installed, preview)
            self.current_report = preview.report
            self._set_output(self.library_output, json.dumps(preview.report, indent=2, ensure_ascii=True))
            if preview.compatible:
                self.status.set('Compatible. Preparing will restore only to a new isolated folder.')
            else:
                self.status.set('Compatibility checks failed. Preparing this profile is blocked.')

        self._start(operation, complete, label='Verifying profile snapshot, component hashes, and exact game version…')

    def export_report(self):
        if self.current_report is None:
            messagebox.showerror('Smart Playthrough Profiles', 'Preview a profile or prepare an environment before exporting its report.', parent=self.window)
            return
        destination = filedialog.asksaveasfilename(
            parent=self.window, title='Export AI-readable playthrough report',
            defaultextension='.json', filetypes=(('JSON report', '*.json'),),
        )
        if not destination:
            return
        report = self.current_report

        def operation():
            from koei_editor.shared.copy_storage import atomic_new
            path = Path(destination)
            encoded = (json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + '\n').encode('ascii')
            return atomic_new(encoded, path)

        def complete(path):
            self.status.set(f'AI-readable report exported to {path}.')

        self._start(operation, complete, label='Exporting a new AI-readable report file…')

    def prepare_environment(self):
        try:
            profile_id = self._selected_profile_id()
        except ValueError as error:
            messagebox.showerror('Smart Playthrough Profiles', str(error), parent=self.window)
            return
        installed = self.installed_game_version.get().strip()
        parent = self.destination_parent.get().strip()
        if not installed or not parent:
            messagebox.showerror('Smart Playthrough Profiles', 'Enter the exact installed game version and choose a parent folder for a NEW environment.', parent=self.window)
            return
        if not self.last_preview or self.last_preview[:2] != (profile_id, installed):
            messagebox.showerror('Smart Playthrough Profiles', 'Preview this selected profile against the current exact game version before preparing it.', parent=self.window)
            return
        if not self.last_preview[2].compatible:
            messagebox.showerror('Smart Playthrough Profiles', 'This profile is not compatible with the entered exact game version.', parent=self.window)
            return
        profile = self.profiles.get(profile_id)
        if profile is None:
            messagebox.showerror('Smart Playthrough Profiles', 'Refresh and select an existing local profile.', parent=self.window)
            return
        destination = Path(parent) / ('Playthrough-' + profile.id[:8])
        current_copy = self.active_save_copy.get().strip() or None
        if not messagebox.askyesno(
            'Prepare isolated playthrough environment',
            f'Create a new environment at:\n{destination}\n\n'
            'The selected Vault snapshot will be restored into that new folder. '
            'An optional separate save copy will be backed up first. No live save, mod, setting, or build file will be written.',
            parent=self.window,
        ):
            return

        def operation():
            from koei_editor.shared.playthrough_profiles import PlaythroughProfileStore
            from koei_editor.shared.save_vault import SaveVault
            return PlaythroughProfileStore(SaveVault(self.vault_path)).prepare_environment(
                profile_id, destination, installed, active_save_copy=current_copy,
            )

        def complete(result):
            self.last_preview = None
            self.current_report = result.report
            self._set_output(self.library_output, json.dumps(result.report, indent=2, ensure_ascii=True))
            messagebox.showinfo(
                'Environment prepared',
                f"Isolated environment created. Restored save copy:\n{result.save_path}\n\n"
                f"AI-readable report:\n{result.report_path}\n\n"
                'No live save or configuration was written.',
                parent=self.window,
            )

        self._start(operation, complete, label='Backing up the separate current copy and preparing an isolated environment…')

    def apply_theme(self, palette):
        self._palette = dict(palette)
        if self._closed:
            return
        for widget in (getattr(self, 'create_output', None), getattr(self, 'library_output', None)):
            if widget is not None:
                widget.configure(background=palette['background'], foreground=palette['text'],
                                 insertbackground=palette['text'])

    def _destroyed(self, event):
        if event.widget is self.window:
            self._closed = True
            self._cancel.set()

    def show(self, selected_snapshot_id=None):
        if self._closed:
            return
        if selected_snapshot_id and selected_snapshot_id in self.snapshots:
            self.snapshot_choice.set(self._snapshot_labels.get(selected_snapshot_id, selected_snapshot_id))
        self.window.deiconify()
        self.window.lift()

    def close(self):
        if self._closed:
            return
        if self.busy:
            messagebox.showinfo('Smart Playthrough Profiles', 'Wait for the current profile operation to finish before closing.', parent=self.window)
            return
        self._closed = True
        self._cancel.set()
        if self._poll_id is not None:
            self.window.after_cancel(self._poll_id)
            self._poll_id = None
        self.window.destroy()

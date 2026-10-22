"""Tk workspace for emulator discovery, saved launches, and copied-save handoff."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import emulator_hub, emulator_hub_preferences


class EmulatorHubWorkspace:
    def __init__(self, parent, workspace, open_saved_copy, preferences_path=None):
        self.parent = parent
        self.open_saved_copy = open_saved_copy
        self.preferences_path = emulator_hub_preferences.preferences_path(preferences_path)
        self.settings = emulator_hub_preferences.load(self.preferences_path)
        self.providers = emulator_hub.providers()
        self.provider_by_label = {f'{item.name} [{item.id}]': item for item in self.providers}
        self.installations = ()
        self.installation_by_label = {}
        self.profile_by_id = {profile.id: profile for profile in self.settings.profiles}
        self._protected_root_by_provider = {}
        self._active_export_provider_id = None
        self.export_result = None
        self.export_game_id = None
        self._export_busy = False
        self._export_cancel = threading.Event()
        self._export_queue = queue.SimpleQueue()
        self._export_poll_id = None
        self._closed = False

        self.frame = ttk.Frame(workspace, padding=18)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(2, weight=1)
        ttk.Label(self.frame, text='Emulator Integration Hub', font=('TkDefaultFont', 18, 'bold')).grid(
            row=0, column=0, sticky='w', pady=(0, 4))
        ttk.Label(self.frame, text=(
            'Discover emulator installs, associate a supported game with content, and launch a saved profile. '
            'Save checks inspect exported copies only; encrypted or signed console saves keep their existing requirements.'),
            wraplength=1120, justify='left').grid(row=1, column=0, sticky='ew', pady=(0, 12))

        self.tabs = ttk.Notebook(self.frame)
        self.tabs.grid(row=2, column=0, sticky='nsew')
        self.launch_tab = ttk.Frame(self.tabs, padding=12)
        self.export_tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.launch_tab, text='Installations and launch profiles')
        self.tabs.add(self.export_tab, text='Exported save copies')
        self._build_launch_tab()
        self._build_export_tab()
        self.frame.bind('<Destroy>', self._on_destroy, add='+')
        self.apply_theme({'background': '#f4f4f4', 'foreground': '#1a1a1a', 'muted': '#555555',
                           'accent': '#c6443d', 'selection': '#dce8f4'})
        self.refresh_installations()
        self._refresh_profiles()

    def _build_launch_tab(self):
        tab = self.launch_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        actions = ttk.Frame(tab)
        actions.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Button(actions, text='Discover installations', command=self.refresh_installations).pack(side='left')
        ttk.Button(actions, text='Add executable…', command=self.add_installation).pack(side='left', padx=(8, 0))
        ttk.Label(actions, text='Discovery checks PATH and bounded standard locations; portable installs can be added manually.',
                  style='Muted.TLabel').pack(side='left', padx=12)

        install_box = ttk.LabelFrame(tab, text='Detected emulator installations', padding=8)
        install_box.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        install_box.columnconfigure(0, weight=1)
        self.install_tree = ttk.Treeview(install_box,
                                         columns=('provider', 'path', 'config', 'data', 'found'),
                                         show='headings', height=4)
        for col, title, width in (('provider', 'Emulator', 160), ('path', 'Executable', 290),
                                  ('config', 'Configuration candidates', 270), ('data', 'Data root candidates', 270),
                                  ('found', 'Discovery', 95)):
            self.install_tree.heading(col, text=title)
            self.install_tree.column(col, width=width, anchor='w')
        self.install_tree.grid(row=0, column=0, sticky='ew')
        install_scroll = ttk.Scrollbar(install_box, orient='vertical', command=self.install_tree.yview)
        install_scroll.grid(row=0, column=1, sticky='ns')
        install_xscroll = ttk.Scrollbar(install_box, orient='horizontal', command=self.install_tree.xview)
        install_xscroll.grid(row=1, column=0, sticky='ew')
        self.install_tree.configure(yscrollcommand=install_scroll.set, xscrollcommand=install_xscroll.set)

        body = ttk.Frame(tab)
        body.grid(row=2, column=0, sticky='nsew')
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        form = ttk.LabelFrame(body, text='Create a game launch profile', padding=10)
        form.grid(row=0, column=0, sticky='new', padx=(0, 8))
        form.columnconfigure(1, weight=1)
        self.provider_var = tk.StringVar()
        self.install_var = tk.StringVar()
        self.game_var = tk.StringVar()
        self.content_var = tk.StringVar()
        ttk.Label(form, text='Emulator').grid(row=0, column=0, sticky='w', pady=3)
        self.provider_combo = ttk.Combobox(form, textvariable=self.provider_var, state='readonly',
                                            values=tuple(self.provider_by_label), width=30)
        self.provider_combo.grid(row=0, column=1, sticky='ew', pady=3)
        self.provider_combo.bind('<<ComboboxSelected>>', self._provider_changed)
        ttk.Label(form, text='Installation').grid(row=1, column=0, sticky='w', pady=3)
        self.install_combo = ttk.Combobox(form, textvariable=self.install_var, state='readonly')
        self.install_combo.grid(row=1, column=1, sticky='ew', pady=3)
        ttk.Label(form, text='Game/platform').grid(row=2, column=0, sticky='w', pady=3)
        self.game_combo = ttk.Combobox(form, textvariable=self.game_var, state='readonly')
        self.game_combo.grid(row=2, column=1, sticky='ew', pady=3)
        ttk.Label(form, text='Game content').grid(row=3, column=0, sticky='w', pady=3)
        ttk.Entry(form, textvariable=self.content_var).grid(row=3, column=1, sticky='ew', pady=3)
        content_buttons = ttk.Frame(form)
        content_buttons.grid(row=4, column=1, sticky='e', pady=(2, 6))
        ttk.Button(content_buttons, text='Choose file…', command=self.choose_content_file).pack(side='left')
        ttk.Button(content_buttons, text='Choose folder…', command=self.choose_content_folder).pack(side='left', padx=(6, 0))
        ttk.Button(form, text='Save launch profile', command=self.save_profile).grid(
            row=5, column=1, sticky='e', pady=(4, 0))
        ttk.Label(form, text=(
            'Only documented launch arguments are used. The hub does not copy extra arguments or custom data-root '
            'overrides from desktop shortcuts; configure the root in the emulator itself. '
            'GUI-only emulators open without receiving the game path; Vita3K checks app-folder shape here and '
            'enforces actual installation membership itself.'),
                  style='Muted.TLabel', wraplength=430, justify='left').grid(
            row=6, column=0, columnspan=2, sticky='ew', pady=(8, 0))

        profile_box = ttk.LabelFrame(body, text='Saved launch profiles', padding=8)
        profile_box.grid(row=0, column=1, rowspan=2, sticky='nsew', padx=(8, 0))
        profile_box.columnconfigure(0, weight=1)
        profile_box.rowconfigure(0, weight=1)
        self.profile_tree = ttk.Treeview(profile_box, columns=('game', 'emulator', 'content'), show='headings', height=10)
        for col, title, width in (('game', 'Game/platform', 240), ('emulator', 'Emulator', 150), ('content', 'Game content', 300)):
            self.profile_tree.heading(col, text=title)
            self.profile_tree.column(col, width=width, anchor='w')
        self.profile_tree.grid(row=0, column=0, sticky='nsew')
        profile_scroll = ttk.Scrollbar(profile_box, orient='vertical', command=self.profile_tree.yview)
        profile_scroll.grid(row=0, column=1, sticky='ns')
        self.profile_tree.configure(yscrollcommand=profile_scroll.set)
        profile_buttons = ttk.Frame(profile_box)
        profile_buttons.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        ttk.Button(profile_buttons, text='Launch selected', command=self.launch_selected).pack(side='left')
        ttk.Button(profile_buttons, text='Remove selected', command=self.remove_selected_profile).pack(side='left', padx=(8, 0))
        self.profile_tree.bind('<<TreeviewSelect>>', self._profile_selected)

        if self.providers:
            self.provider_var.set(next(iter(self.provider_by_label)))
            self._provider_changed()

    def _build_export_tab(self):
        tab = self.export_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        ttk.Label(tab, text=(
            'Choose a folder of separate exported save copies, then select the exact existing game/platform editor profile. '
            'The scan is read-only, bounded, and does not decrypt, resign, extract, or rewrite emulator-managed data.'),
            wraplength=1080, justify='left').grid(row=0, column=0, sticky='ew', pady=(0, 12))
        controls = ttk.Frame(tab)
        controls.grid(row=1, column=0, sticky='ew', pady=(0, 8))
        for column in (1, 2, 3, 5):
            controls.columnconfigure(column, weight=1)
        self.export_provider_var = tk.StringVar()
        self.export_game_var = tk.StringVar()
        self.export_folder_var = tk.StringVar()
        ttk.Label(controls, text='Emulator').grid(row=0, column=0, sticky='w')
        self.export_provider_combo = ttk.Combobox(controls, textvariable=self.export_provider_var,
                                                  values=tuple(self.provider_by_label), state='readonly', width=24)
        self.export_provider_combo.grid(row=0, column=1, padx=(6, 14), sticky='ew')
        self.export_provider_combo.bind('<<ComboboxSelected>>', self._export_provider_changed)
        ttk.Label(controls, text='Editor profile').grid(row=0, column=2, sticky='w')
        self.export_game_combo = ttk.Combobox(controls, textvariable=self.export_game_var, state='readonly', width=32)
        self.export_game_combo.grid(row=0, column=3, padx=(6, 14), sticky='ew')
        ttk.Label(controls, text='Export copies').grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.export_folder_entry = ttk.Entry(controls, textvariable=self.export_folder_var)
        self.export_folder_entry.grid(row=1, column=1, columnspan=3,
                                      sticky='ew', padx=(6, 6), pady=(8, 0))
        ttk.Button(controls, text='Choose folder…', command=self.choose_export_folder).grid(
            row=1, column=4, padx=(0, 6), pady=(8, 0))
        self.scan_export_button = ttk.Button(controls, text='Scan copies', command=self.scan_exports)
        self.scan_export_button.grid(
            row=1, column=5, sticky='e', pady=(8, 0))
        self.cancel_export_button = ttk.Button(controls, text='Cancel', command=self.cancel_export,
                                               state='disabled')
        self.cancel_export_button.grid(row=1, column=6, sticky='e', padx=(6, 0), pady=(8, 0))
        ttk.Label(controls, text='Active emulator data root to protect').grid(
            row=2, column=0, sticky='w', pady=(8, 0))
        self.protected_root_var = tk.StringVar()
        self.protected_root_entry = ttk.Entry(controls, textvariable=self.protected_root_var)
        self.protected_root_entry.grid(
            row=2, column=1, columnspan=3, sticky='ew', padx=(6, 6), pady=(8, 0))
        ttk.Button(controls, text='Choose data folder…', command=self.choose_protected_root).grid(
            row=2, column=4, padx=(0, 6), pady=(8, 0))
        ttk.Label(controls, text=(
            'Choose the active data folder for this emulator before every scan. Discovery paths are hints; '
            'enter custom emulator overrides here. Keep exported copies outside all listed and selected roots.'),
                  style='Muted.TLabel', wraplength=640, justify='left').grid(
            row=3, column=0, columnspan=6, sticky='ew', pady=(6, 0))
        results = ttk.LabelFrame(tab, text='Compatibility results', padding=8)
        results.grid(row=2, column=0, sticky='nsew')
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.export_tree = ttk.Treeview(results, columns=('path', 'status', 'size', 'fields'), show='headings', height=12)
        for col, title, width in (('path', 'Relative file', 480), ('status', 'Qualification', 170),
                                  ('size', 'Size', 100), ('fields', 'Mapped fields', 120)):
            self.export_tree.heading(col, text=title)
            self.export_tree.column(col, width=width, anchor='w')
        self.export_tree.grid(row=0, column=0, sticky='nsew')
        export_scroll = ttk.Scrollbar(results, orient='vertical', command=self.export_tree.yview)
        export_scroll.grid(row=0, column=1, sticky='ns')
        self.export_tree.configure(yscrollcommand=export_scroll.set)
        self.export_tree.bind('<<TreeviewSelect>>', self._export_selected)
        foot = ttk.Frame(results)
        foot.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        self.export_status = tk.StringVar(value='No copied-save scan has run.')
        ttk.Label(foot, textvariable=self.export_status, style='Muted.TLabel').pack(side='left', fill='x', expand=True)
        self.open_export_button = ttk.Button(foot, text='Open qualified copy in editor',
                                             command=self.open_export_selected, state='disabled')
        self.open_export_button.pack(side='right')
        if self.providers:
            self.export_provider_var.set(next(iter(self.provider_by_label)))
            self._export_provider_changed()

    def _provider_changed(self, _event=None):
        provider = self.provider_by_label.get(self.provider_var.get())
        self.game_by_label = {}
        if provider is not None:
            self.game_by_label = {f'{game.title} · {game.subtitle} [{game.id}]': game
                                  for game in emulator_hub.games_for_provider(provider.id)}
        values = tuple(self.game_by_label)
        self.game_combo.configure(values=values)
        self.game_var.set(values[0] if values else '')
        self._refresh_install_options()

    def _export_provider_changed(self, _event=None):
        if self._export_busy:
            return
        if self._active_export_provider_id is not None:
            self._protected_root_by_provider[self._active_export_provider_id] = self.protected_root_var.get().strip()
        provider = self.provider_by_label.get(self.export_provider_var.get())
        self.export_game_by_label = {}
        if provider is not None:
            self._active_export_provider_id = provider.id
            self.protected_root_var.set(self._protected_root_by_provider.get(provider.id, ''))
            self.export_game_by_label = {
                f'{game.title} · {game.subtitle} [{game.id}]': game
                for game in emulator_hub.games_for_provider(provider.id, editors_only=True)}
        values = tuple(self.export_game_by_label)
        self.export_game_combo.configure(values=values)
        self.export_game_var.set(values[0] if values else '')

    def _refresh_install_options(self):
        provider = self.provider_by_label.get(self.provider_var.get())
        compatible = tuple(item for item in self.installations
                           if provider is not None and item.provider_id == provider.id)
        self.installation_by_label = {f'{provider_by_id(item.provider_id).name} — {item.executable} [{item.discovered_by}]': item
                                      for item in compatible}
        values = tuple(self.installation_by_label)
        self.install_combo.configure(values=values)
        self.install_var.set(values[0] if values else '')

    def refresh_installations(self):
        try:
            found = list(emulator_hub.discover_installations())
            existing = {item.id for item in found}
            for profile in self.settings.profiles:
                if profile.id in self.profile_by_id and Path(profile.executable).is_file():
                    try:
                        item = emulator_hub.manual_installation(profile.provider_id, profile.executable)
                    except Exception:
                        continue
                    if item.id not in existing:
                        found.append(item)
                        existing.add(item.id)
            self.installations = tuple(found)
            if hasattr(self, 'install_tree'):
                self.install_tree.delete(*self.install_tree.get_children())
                for item in self.installations:
                    self.install_tree.insert('', 'end', iid=item.id,
                                             values=(provider_by_id(item.provider_id).name, item.executable,
                                                     '; '.join(item.configuration_paths),
                                                     '; '.join(item.protected_data_paths),
                                                     item.discovered_by))
                self._refresh_install_options()
        except Exception as error:
            messagebox.showerror('Emulator discovery failed', str(error), parent=self.parent)

    def add_installation(self):
        provider = self.provider_by_label.get(self.provider_var.get())
        if provider is None:
            messagebox.showinfo('Choose an emulator', 'Choose the emulator family before adding its executable.', parent=self.parent)
            return
        path = filedialog.askopenfilename(parent=self.parent, title='Choose emulator executable',
                                          filetypes=(('Programs', '*.exe;*.app'), ('All files', '*')))
        if not path:
            return
        try:
            item = emulator_hub.manual_installation(provider.id, path)
            self.installations = tuple(existing for existing in self.installations if existing.id != item.id) + (item,)
            if not self.install_tree.exists(item.id):
                self.install_tree.insert('', 'end', iid=item.id,
                                         values=(provider.name, item.executable, '; '.join(item.configuration_paths),
                                                 '; '.join(item.protected_data_paths), 'manual'))
            self._refresh_install_options()
            self.install_var.set(next((label for label, value in self.installation_by_label.items()
                                       if value.id == item.id), ''))
        except Exception as error:
            messagebox.showerror('Cannot add emulator', str(error), parent=self.parent)

    def choose_content_file(self):
        path = filedialog.askopenfilename(parent=self.parent, title='Choose game content')
        if path:
            self.content_var.set(path)

    def choose_content_folder(self):
        path = filedialog.askdirectory(parent=self.parent, title='Choose game content folder')
        if path:
            self.content_var.set(path)

    def save_profile(self):
        provider = self.provider_by_label.get(self.provider_var.get())
        installation = self.installation_by_label.get(self.install_var.get())
        game = self.game_by_label.get(self.game_var.get())
        if provider is None or installation is None or game is None:
            messagebox.showinfo('Incomplete launch profile',
                                'Choose a detected installation and a registered game/platform supported by it.',
                                parent=self.parent)
            return
        try:
            content_path = self.content_var.get().strip()
            if not content_path or not Path(content_path).exists():
                raise ValueError('Choose an existing game file or content folder.')
            profile = emulator_hub.create_launch_profile(provider.id, installation.executable,
                                                          game.id, content_path)
            self.settings = emulator_hub_preferences.add_profile(self.settings, profile)
            if not emulator_hub_preferences.save(self.settings, self.preferences_path):
                raise OSError('The local launch profile could not be saved.')
            self._refresh_profiles()
            self.profile_tree.selection_set(profile.id)
            self.profile_tree.focus(profile.id)
        except Exception as error:
            messagebox.showerror('Cannot save launch profile', str(error), parent=self.parent)

    def _refresh_profiles(self):
        self.profile_by_id = {profile.id: profile for profile in self.settings.profiles}
        if not hasattr(self, 'profile_tree'):
            return
        self.profile_tree.delete(*self.profile_tree.get_children())
        for profile in self.settings.profiles:
            game = get_game(profile.game_id)
            provider = provider_by_id(profile.provider_id)
            self.profile_tree.insert('', 'end', iid=profile.id,
                                     values=(f'{game.title} · {game.platform}', provider.name, profile.content_path))

    def _profile_selected(self, _event=None):
        selected = self.profile_tree.selection()
        profile = self.profile_by_id.get(selected[0]) if selected else None
        if profile is not None:
            self.provider_var.set(next(label for label, value in self.provider_by_label.items()
                                       if value.id == profile.provider_id))
            self._provider_changed()
            self.install_var.set(next((label for label, value in self.installation_by_label.items()
                                      if value.executable == profile.executable), ''))
            self.game_var.set(next((label for label, value in self.game_by_label.items()
                                   if value.id == profile.game_id), ''))
            self.content_var.set(profile.content_path)

    def launch_selected(self):
        selected = self.profile_tree.selection()
        profile = self.profile_by_id.get(selected[0]) if selected else None
        if profile is None:
            messagebox.showinfo('Choose a launch profile', 'Select a saved launch profile first.', parent=self.parent)
            return
        try:
            plan, _process = emulator_hub.launch(profile)
            if not plan.content_passed:
                messagebox.showinfo('Emulator opened', plan.note or
                                    'The emulator opened without a game path. Select the associated game in its library.',
                                    parent=self.parent)
        except Exception as error:
            messagebox.showerror('Cannot launch emulator', str(error), parent=self.parent)

    def remove_selected_profile(self):
        selected = self.profile_tree.selection()
        if not selected:
            return
        self.settings = emulator_hub_preferences.remove_profile(self.settings, selected[0])
        if not emulator_hub_preferences.save(self.settings, self.preferences_path):
            messagebox.showerror('Cannot remove launch profile', 'The local profile file could not be updated.',
                                 parent=self.parent)
            self.settings = emulator_hub_preferences.load(self.preferences_path)
        self._refresh_profiles()

    def choose_export_folder(self):
        path = filedialog.askdirectory(parent=self.parent, title='Choose a folder of copied exported saves')
        if path:
            self.export_folder_var.set(path)

    def choose_protected_root(self):
        path = filedialog.askdirectory(parent=self.parent, title='Choose emulator-managed save data folder')
        if path:
            self.protected_root_var.set(path)

    def scan_exports(self):
        if self._export_busy:
            return
        provider = self.provider_by_label.get(self.export_provider_var.get())
        game = self.export_game_by_label.get(self.export_game_var.get())
        folder = self.export_folder_var.get().strip()
        self.export_result = None
        self.export_game_id = None
        self.export_tree.delete(*self.export_tree.get_children())
        self.open_export_button.configure(state='disabled')
        if provider is None or game is None or not folder:
            self.export_status.set('Choose an emulator, an exact editor profile, and a copied-save folder.')
            return
        active_root = self.protected_root_var.get().strip()
        if not active_root:
            self.export_status.set('Choose the active emulator data folder to protect before scanning.')
            return
        roots = tuple(path for item in self.installations if item.provider_id == provider.id
                      for path in item.protected_data_paths)
        self.export_game_id = game.id
        self._start_export_operation(
            'scan', lambda cancel: emulator_hub.scan_export_folder(
                game.id, folder, provider_id=provider.id, active_data_root=active_root,
                protected_roots=roots, cancel=cancel))

    def _start_export_operation(self, kind, operation):
        if self._export_busy or self._closed:
            return
        self._export_busy = True
        self._export_cancel = cancel = threading.Event()
        for widget in (self.export_provider_combo, self.export_game_combo, self.export_folder_entry,
                       self.scan_export_button, self.protected_root_entry, self.open_export_button):
            widget.configure(state='disabled')
        self.export_tree.state(('disabled',))
        self.cancel_export_button.configure(state='normal')
        self.export_status.set('Scanning and qualifying copied saves...' if kind == 'scan'
                               else 'Rechecking the selected copy and its original context...')

        def worker():
            try:
                self._export_queue.put((kind, operation(cancel), None, cancel.is_set()))
            except Exception as error:
                self._export_queue.put((kind, None, error, cancel.is_set()))

        threading.Thread(target=worker, daemon=True).start()
        try:
            self._export_poll_id = self.parent.after(30, self._poll_export_operation)
        except tk.TclError:
            self._on_destroy()

    def _poll_export_operation(self):
        self._export_poll_id = None
        if self._closed:
            return
        try:
            kind, result, error, cancelled = self._export_queue.get_nowait()
        except queue.Empty:
            try:
                self._export_poll_id = self.parent.after(30, self._poll_export_operation)
            except tk.TclError:
                self._on_destroy()
            return
        self._export_busy = False
        if kind == 'scan':
            self._clear_active_root_confirmation()
        self.export_provider_combo.configure(state='readonly')
        self.export_game_combo.configure(state='readonly')
        self.export_folder_entry.configure(state='normal')
        self.protected_root_entry.configure(state='normal')
        self.scan_export_button.configure(state='normal')
        self.open_export_button.configure(state='disabled')
        self.export_tree.state(('!disabled',))
        self.cancel_export_button.configure(state='disabled')
        if error is not None:
            if cancelled or self._export_cancel.is_set():
                self.export_status.set('Operation cancelled; no editor was opened.')
                self._export_selected()
                return
            message = str(error) if isinstance(error, SaveError) else (
                'The selected folder could not be safely scanned or rechecked.')
            self.export_status.set(message)
            messagebox.showerror('Exported-save check failed', message, parent=self.parent)
            self._export_selected()
            return
        if kind == 'scan':
            self.export_result = result
            self.export_tree.delete(*self.export_tree.get_children())
            for index, entry in enumerate(result.entries):
                self.export_tree.insert('', 'end', iid=str(index), values=(entry.relative_path,
                    entry.status.title(), f'{entry.size_bytes:,}',
                    entry.mapped_fields if entry.status == 'qualified' else ''))
            reason = result.stop_reason.replace('_', ' ')
            self.export_status.set(
                f'{result.qualified_count} qualified copy/copies · {len(result.entries)} candidates · {reason}')
            if not result.entries and not cancelled:
                self.export_status.set('No compatible copied saves were found.')
            self._export_selected()
            return
        if cancelled or self._export_cancel.is_set():
            self.export_status.set('Opening cancelled; no editor was opened.')
            self._export_selected()
            return
        try:
            opened = self.open_saved_copy(self.export_game_id, result)
            if opened:
                self.export_status.set('Opened through the selected game profile’s normal editor path.')
            elif opened is False:
                self.export_status.set('The editor did not open this copy.')
            else:
                self.export_status.set('Open request sent to the selected game profile editor.')
        except Exception:
            self.export_status.set('The normal game editor could not open this copy.')
            messagebox.showerror('Cannot hand off exported save',
                                 'The normal game editor could not open this copy.', parent=self.parent)
        self._export_selected()

    def _clear_active_root_confirmation(self):
        if self._active_export_provider_id is not None:
            self._protected_root_by_provider[self._active_export_provider_id] = ''
        self.protected_root_var.set('')

    def cancel_export(self):
        if self._export_busy:
            self._export_cancel.set()
            self.export_status.set('Cancelling the copied-save operation...')

    def _on_destroy(self, event=None):
        if event is not None and event.widget is not self.frame:
            return
        self._closed = True
        self._export_cancel.set()
        if self._export_poll_id is not None:
            try:
                self.parent.after_cancel(self._export_poll_id)
            except tk.TclError:
                pass
            self._export_poll_id = None

    def _export_selected(self, _event=None):
        enabled = False
        if not self._export_busy and self.export_result is not None:
            selected = self.export_tree.selection()
            try:
                entry = self.export_result.entries[int(selected[0])] if selected else None
                enabled = entry is not None and entry.status == 'qualified'
            except (ValueError, IndexError):
                enabled = False
        self.open_export_button.configure(state='normal' if enabled else 'disabled')

    def open_export_selected(self):
        if self._export_busy or self.export_result is None or not self.export_game_id:
            return
        selected = self.export_tree.selection()
        if not selected:
            return
        try:
            entry = self.export_result.entries[int(selected[0])]
            result = self.export_result
            game_id = self.export_game_id

            def operation(cancel):
                document = emulator_hub.qualify_export(result, entry, cancel=cancel)
                del document
                return result.folder.joinpath(*Path(entry.relative_path).parts)

            self._start_export_operation('open', operation)
        except Exception as error:
            messagebox.showerror('Cannot hand off exported save', str(error), parent=self.parent)

    def apply_theme(self, palette):
        self.frame.configure(style='Workspace.TFrame')
        style = ttk.Style(self.parent)
        style.configure('Muted.TLabel', foreground=palette.get('muted', '#555555'))
        style.configure('Treeview', rowheight=25)


def provider_by_id(provider_id):
    return emulator_hub.provider_for(provider_id)

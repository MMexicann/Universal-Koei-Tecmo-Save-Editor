"""Tk workspace for explicit game-specific PC mod installation methods."""
from collections.abc import Mapping
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from koei_editor.shared.preferences import preference_path
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.mod_manager import (ModManager, archive_game_id, get_mod_adapter,
                                              mod_manager_host_capabilities, review_archive, supported_mod_games)


class ModManagerWorkspace:
    """Retained UI for game selection, profiles, and managed mod operations.

    The service owns validation and filesystem safety. This view only accepts a
    user-selected, explicitly scoped PC root and passes archive paths to the service for
    validation; it never implements file installation itself.
    """

    def __init__(self, root, parent, manager=None, state_dir=None):
        self.root = root
        if manager is None:
            state_dir = Path(state_dir) if state_dir is not None else preference_path().parent / 'mod_manager'
            manager = ModManager(state_dir, game_root=None)
        self.manager = manager
        self._managers = {manager.game_id: manager}
        self._state_base_dir = manager.state_base_dir
        self._adapter_labels = {adapter.title: adapter.game_id for adapter in supported_mod_games()}
        self._closed = False
        self._nexus_poll_id = None
        self._profiles = {}
        self._profile_labels = {}
        self._selected_profile_id = None
        self._mods = {}
        self._theme = 'Light'
        self._recovery_blocked = False
        self._recovery_blocked_root = None

        self.frame = ttk.Frame(parent, padding=(12, 8))
        self.frame.bind('<Destroy>', self._on_frame_destroy, add='+')
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        self.content_canvas = tk.Canvas(self.frame, highlightthickness=0, borderwidth=0)
        self.content_canvas.grid(row=0, column=0, sticky='nsew')
        self.content_scrollbar = ttk.Scrollbar(self.frame, orient='vertical', command=self.content_canvas.yview)
        self.content_scrollbar.grid(row=0, column=1, sticky='ns')
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)
        self.content = ttk.Frame(self.content_canvas, padding=(12, 8))
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(3, weight=1)
        self._content_window = self.content_canvas.create_window(0, 0, anchor='nw', window=self.content)
        self.content_canvas.bind('<Configure>', self._responsive_layout)
        self.content.bind('<Configure>', self._content_resized)

        heading = ttk.Frame(self.content)
        heading.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        ttk.Label(heading, text='MOD MANAGER', font=(ui_font(root), 22, 'bold')).pack(anchor='w')
        ttk.Label(heading, text='Select a documented installation method. Each game keeps its own library and profiles.',
                  style='Muted.TLabel').pack(anchor='w', pady=(3, 0))

        target = ttk.LabelFrame(self.content, text='Game and installation', padding=(10, 7))
        target.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        target.columnconfigure(1, weight=1)
        ttk.Label(target, text='Game').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.game_choice = tk.StringVar(root, value=self.manager.adapter.title)
        self.game_selector = ttk.Combobox(target, textvariable=self.game_choice,
                                         values=tuple(self._adapter_labels), state='readonly')
        self.game_selector.grid(row=0, column=1, sticky='ew', pady=(0, 6))
        self.game_selector.bind('<<ComboboxSelected>>', self._game_changed)
        self.capability_text = tk.StringVar(root)
        ttk.Button(target, text='Choose Game Folder…', command=self.choose_game_root).grid(
            row=1, column=0, sticky='w', padx=(0, 10))
        self.game_root_text = tk.StringVar(root, value='No game folder selected')
        ttk.Label(target, textvariable=self.game_root_text, style='Muted.TLabel',
                  wraplength=760).grid(row=1, column=1, sticky='ew')
        self.loader_confirmed = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(target,
                        text='I have configured the required loader and closed the game.',
                        variable=self.loader_confirmed).grid(row=2, column=0, columnspan=2,
                                                             sticky='w', pady=(7, 0))
        ttk.Label(target, textvariable=self.capability_text, style='Muted.TLabel',
                  wraplength=1050).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(6, 0))

        profile_bar = ttk.LabelFrame(self.content, text='Separate mod profiles', padding=(10, 7))
        profile_bar.grid(row=2, column=0, sticky='ew', pady=(0, 10))
        profile_bar.columnconfigure(1, weight=1)
        ttk.Label(profile_bar, text='Profile').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.profile_choice = tk.StringVar(root)
        self.profile_selector = ttk.Combobox(profile_bar, textvariable=self.profile_choice,
                                             state='readonly', width=28)
        self.profile_selector.grid(row=0, column=1, sticky='ew')
        self.profile_selector.bind('<<ComboboxSelected>>', self._profile_changed)
        self.active_profile_text = tk.StringVar(root, value='No active profile')
        ttk.Label(profile_bar, textvariable=self.active_profile_text, style='Muted.TLabel').grid(
            row=0, column=2, sticky='e', padx=(10, 14))
        self.profile_actions = ttk.Frame(profile_bar)
        self.profile_actions.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0))
        self.create_profile_button = ttk.Button(self.profile_actions, text='Create', command=self.create_profile)
        self.create_profile_button.grid(row=0, column=3, padx=2)
        self.rename_profile_button = ttk.Button(self.profile_actions, text='Rename', command=self.rename_profile)
        self.rename_profile_button.grid(row=0, column=4, padx=2)
        self.delete_profile_button = ttk.Button(self.profile_actions, text='Delete', command=self.delete_profile)
        self.delete_profile_button.grid(row=0, column=5, padx=2)
        self.apply_profile_button = ttk.Button(self.profile_actions, text='Apply Profile', style='Primary.TButton',
                                               command=self.apply_profile)
        self.apply_profile_button.grid(row=0, column=6, padx=(8, 0))

        body = ttk.Panedwindow(self.content, orient='horizontal')
        body.grid(row=3, column=0, sticky='nsew')
        mods_panel = ttk.Frame(body)
        mods_panel.columnconfigure(0, weight=1)
        mods_panel.rowconfigure(1, weight=1)
        ttk.Label(mods_panel, text='MOD LIBRARY', style='Muted.TLabel').grid(
            row=0, column=0, sticky='w', pady=(0, 6))
        self.mod_table = ttk.Treeview(mods_panel,
                                      columns=('version', 'installed', 'enabled'),
                                      show='tree headings', selectmode='browse', height=6)
        self.mod_table.heading('#0', text='Mod')
        self.mod_table.heading('version', text='Version')
        self.mod_table.heading('installed', text='Installed')
        self.mod_table.heading('enabled', text='In Profile')
        self.mod_table.column('#0', width=260, minwidth=140)
        self.mod_table.column('version', width=90, minwidth=70, stretch=False)
        self.mod_table.column('installed', width=78, minwidth=65, stretch=False)
        self.mod_table.column('enabled', width=88, minwidth=70, stretch=False)
        self.mod_table.grid(row=1, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(mods_panel, orient='vertical', command=self.mod_table.yview)
        scrollbar.grid(row=1, column=1, sticky='ns')
        self.mod_table.configure(yscrollcommand=scrollbar.set)
        self.mod_table.bind('<<TreeviewSelect>>', self._mod_selected)
        body.add(mods_panel, weight=3)

        details = ttk.LabelFrame(body, text='Selected profile checks', padding=(10, 8))
        details.columnconfigure(0, weight=1)
        details.rowconfigure(1, weight=1)
        self.profile_summary = tk.StringVar(root, value='Create a profile or select one to inspect its mod set.')
        ttk.Label(details, textvariable=self.profile_summary, style='Muted.TLabel',
                  wraplength=360).grid(row=0, column=0, sticky='ew', pady=(0, 8))
        self.issues = tk.Text(details, height=5, width=24, wrap='word', relief='flat',
                              borderwidth=0, padx=8, pady=7, state='disabled')
        self.issues.grid(row=1, column=0, sticky='nsew')
        details_scroll = ttk.Scrollbar(details, orient='vertical', command=self.issues.yview)
        details_scroll.grid(row=1, column=1, sticky='ns')
        self.issues.configure(yscrollcommand=details_scroll.set)
        body.add(details, weight=2)

        actions = ttk.Frame(self.frame)
        self.actions = actions
        actions.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        self.import_button = ttk.Button(actions, text='Add Mod ZIP…', command=self.import_archive)
        self.import_button.grid(row=0, column=0, padx=(0, 6))
        self.install_button = ttk.Button(actions, text='Install', command=self.install_mod)
        self.install_button.grid(row=0, column=1, padx=3)
        self.uninstall_button = ttk.Button(actions, text='Uninstall', command=self.uninstall_mod)
        self.uninstall_button.grid(row=0, column=2, padx=3)
        self.toggle_enabled_button = ttk.Button(actions, text='Enable in Profile', command=self.toggle_profile_mod)
        self.toggle_enabled_button.grid(row=0, column=3, padx=(9, 3))
        self.remove_button = ttk.Button(actions, text='Remove from Library', command=self.remove_mod)
        self.remove_button.grid(row=0, column=4, padx=3)
        ttk.Button(actions, text='Refresh', command=self.refresh).grid(row=0, column=5, padx=(9, 0))
        self.status = tk.StringVar(root,
            value='Choose a game and its folder. Import a ZIP, review its profile checks, then apply explicitly.')
        ttk.Label(self.content, textvariable=self.status, wraplength=1100).grid(
            row=5, column=0, sticky='ew', pady=(9, 0))
        ttk.Label(self.content,
                  text='Profiles store independent enable lists. Apply writes only the service-verified managed mod area; '
                       'original game files remain outside manager ownership.',
                  style='Muted.TLabel', wraplength=1100).grid(row=6, column=0, sticky='ew', pady=(4, 0))

        self._wrap_labels = []
        def remember_labels(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Label):
                    self._wrap_labels.append(child)
                    child.bind('<Configure>', self._label_resized, add='+')
                if not isinstance(child, (tk.Text, ttk.Treeview, ttk.Combobox, ttk.Scrollbar)):
                    child.bind('<MouseWheel>', self._scroll_form, add='+')
                    child.bind('<Button-4>', self._scroll_form, add='+')
                    child.bind('<Button-5>', self._scroll_form, add='+')
                remember_labels(child)
        remember_labels(self.content)
        self._action_buttons = tuple(self.actions.winfo_children())
        self._profile_action_buttons = tuple(self.profile_actions.winfo_children())
        self._responsive_layout()
        self.refresh()
        self._schedule_nexus_download_poll()

    @staticmethod
    def _flow_buttons(buttons, width):
        if not buttons:
            return
        parent = buttons[0].master
        rows = getattr(parent, '_mod_flow_rows', [])
        parent._mod_flow_rows = rows
        # Each row needs its own grid. A shared grid uses the widest button
        # in each column across every row, which can overflow after wrapping.
        for button in buttons:
            button.grid_forget()
        row = column = occupied = 0
        for button in buttons:
            requested = button.winfo_reqwidth() + 10
            if column and occupied + requested > width:
                row += 1
                column = occupied = 0
            if row == len(rows):
                rows.append(ttk.Frame(parent))
            rows[row].grid(row=row, column=0, sticky='w')
            button.grid_configure(in_=rows[row], row=0, column=column,
                                  padx=(0, 8), pady=(0, 4), sticky='w')
            column += 1
            occupied += requested
        for unused in rows[row + 1:]:
            unused.grid_remove()

    def _responsive_layout(self, event=None):
        if self._closed:
            return
        width = max(120, event.width if event is not None else
                    (self.frame.winfo_width() if self.frame.winfo_width() > 1 else 1100))
        if event is not None:
            self.content_canvas.itemconfigure(self._content_window, width=width)
        available = max(100, width - 48)
        for label in getattr(self, '_wrap_labels', ()):
            # Label parents may be narrower panes; constrain them separately.
            parent_width = label.master.winfo_width()
            wrap = min(available, max(100, parent_width - 32)) if parent_width > 1 else available
            if self.root.winfo_pixels(label.cget('wraplength') or '0') != wrap:
                label.configure(wraplength=wrap)
        self._flow_buttons(getattr(self, '_action_buttons', ()), available)
        self._flow_buttons(getattr(self, '_profile_action_buttons', ()), available)
        self._content_resized()

    def _scroll_form(self, event):
        if self._closed:
            return
        direction = -1 if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0 else 1
        self.content_canvas.yview_scroll(direction * 3, 'units')
        return 'break'

    def _label_resized(self, event):
        if self._closed or event.width < 2:
            return
        wrap = max(40, event.width - 4)
        if self.root.winfo_pixels(event.widget.cget('wraplength') or '0') != wrap:
            event.widget.configure(wraplength=wrap)

    def _content_resized(self, _event=None):
        if self._closed:
            return
        # A small viewport scrolls the form; the action bar always stays outside.
        height = max(self.content.winfo_reqheight(), self.content_canvas.winfo_height())
        if int(float(self.content_canvas.itemcget(self._content_window, 'height'))) != height:
            self.content_canvas.itemconfigure(self._content_window, height=height)
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox('all'))

    def _on_frame_destroy(self, event):
        if event.widget is self.frame:
            self.close()

    def close(self):
        """Stop view polling without waiting on or changing manager jobs."""
        if self._closed:
            return
        self._closed = True
        poll_id = self._nexus_poll_id
        self._nexus_poll_id = None
        if poll_id is not None:
            try:
                self.root.after_cancel(poll_id)
            except tk.TclError:
                pass

    def apply_theme(self, palette):
        """Record the current theme; all widgets follow the shell's ttk styles."""
        from koei_editor.shared.appearance import THEMES
        self._theme = next((name for name, value in THEMES.items() if value == palette), self._theme)
        self.content_canvas.configure(background=palette['background'])
        self._responsive_layout()

    def _error(self, title, error):
        self.status.set(f'{title}: {error}')
        messagebox.showerror(title, str(error), parent=self.root)

    def _run(self, title, action):
        try:
            return action()
        except Exception as error:
            try:
                self._update_controls()
            except Exception:
                pass
            self._error(title, error)
            return None

    @staticmethod
    def _root_identity(path):
        if path is None:
            return None
        try:
            return str(Path(path).expanduser().resolve(strict=False)).casefold()
        except (OSError, RuntimeError, TypeError, ValueError):
            return str(path).casefold()

    def _mark_recovery_blocked(self, game_root):
        self._recovery_blocked = True
        self._recovery_blocked_root = self._root_identity(game_root)

    def _clear_recovery_block_if_resolved(self, game_root):
        if (self._recovery_blocked
                and self._root_identity(game_root) == self._recovery_blocked_root):
            self._recovery_blocked = False
            self._recovery_blocked_root = None

    @staticmethod
    def _value(item, name, default=None):
        if isinstance(item, Mapping):
            return item.get(name, default)
        return getattr(item, name, default)

    @staticmethod
    def _format_issue(issue):
        if isinstance(issue, str):
            return issue
        if isinstance(issue, Mapping):
            parts = [issue.get(key) for key in ('severity', 'code', 'message')]
        else:
            parts = [getattr(issue, key, None) for key in ('severity', 'code', 'message')]
        return ': '.join(str(part) for part in parts if part not in (None, '')) or str(issue)

    def _selected_mod_id(self):
        selection = self.mod_table.selection()
        return selection[0] if selection else None

    def _selected_mod(self):
        identity = self._selected_mod_id()
        return self._mods.get(identity) if identity is not None else None

    def _profile_enabled_ids(self, profile):
        values = self._value(profile, 'enabled_mods', ()) or ()
        if isinstance(values, Mapping):
            return {str(key) for key, enabled in values.items() if enabled}
        return {str(value) for value in values}

    def _populate_profile_issues(self):
        profile = self._profiles.get(self._selected_profile_id)
        if profile is None:
            self.profile_summary.set('Create a profile or select one to inspect its mod set.')
            content = 'No profile is selected.'
        else:
            enabled = self._profile_enabled_ids(profile)
            name = self._value(profile, 'name', self._selected_profile_id)
            self.profile_summary.set(f'{name} · {len(enabled)} mod(s) enabled')
            report = self.manager.profile_issues(self._selected_profile_id)
            if isinstance(report, Mapping):
                report = report.get('issues', report.get('errors', report.get('warnings', ())))
            if report is None:
                report = ()
            if isinstance(report, str):
                report = (report,)
            content = '\n'.join('• ' + self._format_issue(issue) for issue in report) or 'No profile issues.'
        self.issues.configure(state='normal')
        self.issues.delete('1.0', 'end')
        self.issues.insert('1.0', content)
        self.issues.configure(state='disabled')

    def refresh(self):
        """Refresh displayed service state without changing the selected profile."""
        def perform():
            previous_profile = self._selected_profile_id
            previous_mod = self._selected_mod_id()
            if self.manager.current_game_root is not None:
                try:
                    self.manager.recover_pending_transaction()
                except Exception:
                    self._mark_recovery_blocked(self.manager.current_game_root)
                    raise
                self._clear_recovery_block_if_resolved(self.manager.current_game_root)
            adapter = self.manager.adapter
            inactive = ('Disabled mods use the documented folder suffix.' if adapter.disable_policy == 'folder_suffix'
                        else 'Enable in Profile, then Apply Profile to install. Disable through Apply Profile removes the deployed copy; the library copy is retained.')
            self.capability_text.set(adapter.scope + ' ' + inactive +
                                     ' ' + str(mod_manager_host_capabilities()['message']))
            game_root = self.manager.current_game_root
            self.game_root_text.set(str(game_root) if game_root else f'No {self.manager.adapter.title} folder selected')

            profiles = tuple(self.manager.profiles())
            self._profiles = {str(self._value(profile, 'id')): profile for profile in profiles}
            active_id_value = self.manager.active_profile_id
            active_id = str(active_id_value) if active_id_value is not None else None
            if previous_profile in self._profiles:
                self._selected_profile_id = previous_profile
            elif active_id in self._profiles:
                self._selected_profile_id = active_id
            else:
                self._selected_profile_id = next(iter(self._profiles), None)

            self._profile_labels = {}
            labels = []
            for profile in profiles:
                profile_id = str(self._value(profile, 'id'))
                name = str(self._value(profile, 'name', profile_id))
                label = name + ('  · active' if profile_id == active_id else '')
                if label in self._profile_labels:
                    label += f'  [{str(profile_id)[:8]}]'
                labels.append(label)
                self._profile_labels[label] = profile_id
                if profile_id == self._selected_profile_id:
                    self.profile_choice.set(label)
            if self._selected_profile_id is None:
                self.profile_choice.set('')
            self.profile_selector.configure(values=labels)
            active = self._profiles.get(active_id)
            active_name = self._value(active, 'name', active_id) if active is not None else None
            self.active_profile_text.set(f'Active: {active_name}' if active_name else 'No active profile')

            self._mods = {str(self._value(mod, 'id')): mod for mod in self.manager.mods()}
            enabled = self._profile_enabled_ids(self._profiles.get(self._selected_profile_id, {}))
            self.mod_table.delete(*self.mod_table.get_children())
            for mod_id, mod in sorted(self._mods.items(), key=lambda entry: str(self._value(entry[1], 'name', entry[0])).casefold()):
                name = str(self._value(mod, 'name', mod_id))
                version = str(self._value(mod, 'version', ''))
                installed = bool(self._value(mod, 'installed', False))
                is_enabled = mod_id in enabled if self._profiles else bool(self._value(mod, 'enabled', False))
                self.mod_table.insert('', 'end', iid=str(mod_id), text=name,
                                      values=(version, 'Yes' if installed else 'No',
                                              'Yes' if is_enabled else 'No'))
            if previous_mod is not None and self.mod_table.exists(str(previous_mod)):
                self.mod_table.selection_set(str(previous_mod))
            self._populate_profile_issues()
            self._update_controls()
            return True

        return self._run('Cannot Refresh Mod Manager', perform)

    def _update_controls(self):
        selected = self._selected_mod()
        profile_exists = self._selected_profile_id in self._profiles
        installed = bool(self._value(selected, 'installed', False)) if selected is not None else False
        recovery_blocked = self._recovery_blocked or bool(self.manager.has_pending_transaction)
        mutation_state = 'disabled' if recovery_blocked else 'normal'
        deployment_state = mutation_state if mod_manager_host_capabilities()['documented_game_deployment'] else 'disabled'
        self.create_profile_button.configure(state=mutation_state)
        self.rename_profile_button.configure(state=mutation_state if profile_exists else 'disabled')
        self.delete_profile_button.configure(state=mutation_state if profile_exists else 'disabled')
        self.apply_profile_button.configure(state=deployment_state if profile_exists else 'disabled')
        current_root = self.manager.current_game_root
        self.toggle_enabled_button.configure(state=mutation_state if selected is not None and profile_exists else 'disabled')
        self.import_button.configure(state=mutation_state)
        self.install_button.configure(state=deployment_state if selected is not None and current_root is not None
                                       and not installed and self.manager.adapter.disable_policy == 'folder_suffix' else 'disabled')
        self.uninstall_button.configure(state=deployment_state if selected is not None and current_root is not None
                                         and installed and self.manager.adapter.disable_policy == 'folder_suffix' else 'disabled')
        self.remove_button.configure(state=mutation_state if selected is not None and not installed else 'disabled')

    def select_game(self, game_id):
        """Select one explicit adapter without mixing its state or queued imports."""
        adapter = get_mod_adapter(game_id)
        if adapter.game_id == self.manager.game_id:
            self.game_choice.set(adapter.title)
            return True
        if self._recovery_blocked or self.manager.has_pending_transaction:
            self.game_choice.set(self.manager.adapter.title)
            raise ValueError('Resolve the current game transaction before switching games.')
        manager = self._managers.get(adapter.game_id)
        if manager is None:
            manager = ModManager(self._state_base_dir, game_id=adapter.game_id)
            self._managers[adapter.game_id] = manager
        self.manager = manager
        self.game_choice.set(adapter.title)
        self.loader_confirmed.set(False)
        self._selected_profile_id = None
        self._profiles = {}
        self._mods = {}
        self.mod_table.delete(*self.mod_table.get_children())
        self.status.set(f'Selected {adapter.title}. Choose its game folder and review loader requirements.')
        return self.refresh()

    def _game_changed(self, _event=None):
        def perform():
            try:
                return self.select_game(self._adapter_labels[self.game_choice.get()])
            except Exception:
                self.game_choice.set(self.manager.adapter.title)
                raise
        return self._run('Cannot Select Mod Game', perform)

    def _profile_changed(self, _event=None):
        def perform():
            self._selected_profile_id = self._profile_labels.get(self.profile_choice.get())
            return self.refresh()
        return self._run('Cannot Select Profile', perform)

    def _mod_selected(self, _event=None):
        return self._run('Cannot Select Mod', self._update_controls)

    def choose_game_root(self):
        def perform():
            initial = self.manager.current_game_root
            selected = filedialog.askdirectory(parent=self.root, title=f'Choose {self.manager.adapter.title} Game Folder',
                                               initialdir=str(initial) if initial else None, mustexist=True)
            if not selected:
                return False
            try:
                self.manager.set_game_root(selected)
            except Exception:
                # set_game_root restores its prior context, so ask about the
                # candidate root before deciding whether recovery remains blocked.
                pending_check = getattr(self.manager, 'has_pending_transaction_for', None)
                try:
                    if pending_check is not None and pending_check(selected):
                        self._mark_recovery_blocked(selected)
                except Exception:
                    self._mark_recovery_blocked(selected)
                raise
            self._clear_recovery_block_if_resolved(self.manager.current_game_root or selected)
            self.loader_confirmed.set(False)
            self.status.set(f'{self.manager.adapter.title} folder selected. Confirm the documented loader before changes.')
            self.refresh()
            return True
        return self._run('Cannot Select Game Folder', perform)

    def create_profile(self):
        def perform():
            name = simpledialog.askstring('Create Mod Profile', 'Profile name:', parent=self.root)
            if name is None:
                return False
            profile = self.manager.create_profile(name, copy_from=self._selected_profile_id)
            self._selected_profile_id = self._value(profile, 'id')
            self.status.set(f'Created profile: {self._value(profile, "name", name)}')
            self.refresh()
            return True
        return self._run('Cannot Create Profile', perform)

    def rename_profile(self):
        def perform():
            profile = self._profiles.get(self._selected_profile_id)
            if profile is None:
                raise ValueError('Select a profile to rename.')
            current_name = str(self._value(profile, 'name', ''))
            name = simpledialog.askstring('Rename Mod Profile', 'New profile name:', initialvalue=current_name,
                                          parent=self.root)
            if name is None:
                return False
            self.manager.rename_profile(self._selected_profile_id, name)
            self.status.set(f'Renamed profile to {name}.')
            self.refresh()
            return True
        return self._run('Cannot Rename Profile', perform)

    def delete_profile(self):
        def perform():
            profile = self._profiles.get(self._selected_profile_id)
            if profile is None:
                raise ValueError('Select a profile to delete.')
            name = str(self._value(profile, 'name', self._selected_profile_id))
            if not messagebox.askyesno('Delete Mod Profile',
                                       f'Delete the profile “{name}” and its enable list?', parent=self.root):
                return False
            self.manager.delete_profile(self._selected_profile_id)
            self._selected_profile_id = None
            self.status.set(f'Deleted profile: {name}')
            self.refresh()
            return True
        return self._run('Cannot Delete Profile', perform)

    def apply_profile(self):
        def perform():
            self._require_game_root()
            self._require_loader_confirmation()
            profile = self._profiles.get(self._selected_profile_id)
            if profile is None:
                raise ValueError('Select a profile to apply.')
            name = str(self._value(profile, 'name', self._selected_profile_id))
            if not messagebox.askyesno('Apply Mod Profile',
                                       f'Apply “{name}” to the selected {self.manager.adapter.title} mod-loader area?', parent=self.root):
                return False
            self.manager.apply_profile(self._selected_profile_id,
                                       loader_confirmed=bool(self.loader_confirmed.get()))
            self.status.set(f'Applied profile: {name}')
            self.refresh()
            return True
        return self._run('Cannot Apply Profile', perform)

    def import_archive_path(self, archive, game_id=None):
        """Validate and route one user-selected ZIP to its isolated library only."""
        if self._closed:
            raise ValueError('The Mod Manager workspace is closed.')
        selected = game_id if game_id is not None else archive_game_id(archive, default=self.manager.game_id)
        review_archive(archive, game_id=selected)
        if not self.select_game(selected):
            raise ValueError('The selected game workspace could not be refreshed.')
        mod = self.manager.import_archive(archive)
        self.status.set(f'Added {mod.name} to {self.manager.adapter.title}. Review its profile before applying.')
        self.refresh()
        self.mod_table.selection_set(mod.id)
        self._update_controls()
        return mod

    def import_archive(self):
        def perform():
            archive = filedialog.askopenfilename(parent=self.root, title=f'Add {self.manager.adapter.title} Mod ZIP',
                                                 filetypes=(('ZIP archives', '*.zip'), ('All files', '*.*')))
            if not archive:
                return False
            mod = self.import_archive_path(archive)
            name = self._value(mod, 'name', self._value(mod, 'id', Path(archive).name))
            self.status.set(f'Added mod archive: {name}')
            self.refresh()
            return True
        return self._run('Cannot Add Mod Archive', perform)

    def enqueue_nexus_download(self, request, downloader):
        """Expose the manager service's same-process Nexus download handoff."""
        if self._closed:
            return False
        enqueue = getattr(self.manager, 'enqueue_nexus_download', None)
        accepted = bool(callable(enqueue) and enqueue(request, downloader))
        self.status.set(
            f'Nexus download queued for {self.manager.adapter.title}. The ZIP will be validated before library import.'
            if accepted else
            'The Mod Manager could not queue this Nexus download.'
        )
        return accepted

    def _schedule_nexus_download_poll(self):
        if self._closed or self._nexus_poll_id is not None:
            return
        if callable(getattr(self.manager, 'poll_nexus_download_results', None)):
            try:
                self._nexus_poll_id = self.root.after(500, self._poll_nexus_download_results)
            except tk.TclError:
                pass

    def _poll_nexus_download_results(self):
        self._nexus_poll_id = None
        if self._closed:
            return
        poll = getattr(self.manager, 'poll_nexus_download_results', None)
        if callable(poll):
            try:
                results = poll()
                if results:
                    self.status.set(str(results[-1].message))
                    self.refresh()
            except tk.TclError:
                return
            except Exception:
                self.status.set('The Mod Manager could not read Nexus download results.')
        self._schedule_nexus_download_poll()

    def install_mod(self):
        def perform():
            self._require_game_root()
            self._require_loader_confirmation()
            mod_id = self._selected_mod_id()
            mod = self._selected_mod()
            if mod_id is None or mod is None:
                raise ValueError('Select a mod to install.')
            name = str(self._value(mod, 'name', mod_id))
            if not messagebox.askyesno('Install Mod',
                                       f'Install “{name}” in the documented {self.manager.adapter.title} mod area?', parent=self.root):
                return False
            self.manager.install_mod(mod_id, loader_confirmed=bool(self.loader_confirmed.get()))
            self.status.set(f'Installed mod: {name}')
            self.refresh()
            return True
        return self._run('Cannot Install Mod', perform)

    def uninstall_mod(self):
        def perform():
            self._require_game_root()
            self._require_loader_confirmation()
            mod_id = self._selected_mod_id()
            mod = self._selected_mod()
            if mod_id is None or mod is None:
                raise ValueError('Select an installed mod to uninstall.')
            name = str(self._value(mod, 'name', mod_id))
            if not messagebox.askyesno('Uninstall Mod',
                                       f'Remove manager-owned files for “{name}” from the verified mod area?',
                                       parent=self.root):
                return False
            self.manager.uninstall_mod(mod_id, loader_confirmed=bool(self.loader_confirmed.get()))
            self.status.set(f'Uninstalled mod: {name}')
            self.refresh()
            return True
        return self._run('Cannot Uninstall Mod', perform)

    def remove_mod(self):
        def perform():
            mod_id = self._selected_mod_id()
            mod = self._selected_mod()
            if mod_id is None or mod is None:
                raise ValueError('Select a mod to remove from the library.')
            name = str(self._value(mod, 'name', mod_id))
            if bool(self._value(mod, 'installed', False)):
                raise ValueError('Uninstall this mod before removing it from the library.')
            if not messagebox.askyesno('Remove Mod', f'Remove “{name}” from the local mod library?', parent=self.root):
                return False
            self.manager.remove_mod(mod_id)
            self.status.set(f'Removed mod from library: {name}')
            self.refresh()
            return True
        return self._run('Cannot Remove Mod', perform)

    def toggle_profile_mod(self):
        def perform():
            mod_id = self._selected_mod_id()
            mod = self._selected_mod()
            profile = self._profiles.get(self._selected_profile_id)
            if mod_id is None or mod is None:
                raise ValueError('Select a mod to enable or disable.')
            if profile is None:
                raise ValueError('Select a profile first.')
            enabled = mod_id not in self._profile_enabled_ids(profile)
            self.manager.set_profile_mod_enabled(self._selected_profile_id, mod_id, enabled)
            name = str(self._value(mod, 'name', mod_id))
            self.status.set(f'{"Enabled" if enabled else "Disabled"} {name} in the selected profile.')
            self.refresh()
            return True
        return self._run('Cannot Change Profile Mod', perform)

    def _require_game_root(self):
        if not self.manager.current_game_root:
            raise ValueError(f'Choose the {self.manager.adapter.title} game folder first.')

    def _require_loader_confirmation(self):
        if not mod_manager_host_capabilities()['documented_game_deployment']:
            raise ValueError(str(mod_manager_host_capabilities()['message']))
        if not self.loader_confirmed.get():
            raise ValueError(f'Confirm the required loader is configured and {self.manager.adapter.title} is closed.')

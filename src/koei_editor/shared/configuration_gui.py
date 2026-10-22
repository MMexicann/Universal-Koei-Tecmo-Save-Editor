"""Tk workspace for the exact, evidence-backed PC settings formats."""
from pathlib import Path
from types import MappingProxyType
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from koei_editor.shared import configuration_manager as backend
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.scrollable_panel import ScrollablePanel


class ConfigurationWorkspace:
    """Inspect, compare, profile, back up and safely edit supported settings."""

    def __init__(self, root, parent):
        self.root = root
        self.frame = ttk.Frame(parent, padding=(28, 14))
        self.document = None
        self.staged = MappingProxyType({})
        self.history = ()
        self._fields = {}
        self._field_labels = {}
        self._profiles = {}
        self._profile_id_by_label = {}
        self._backups = {}
        self._formats = {item.id: item for item in backend.SUPPORTED_FORMATS}
        self._games = {game.title + ' · ' + game.platform: game.id
                       for game in backend.SUPPORTED_GAMES}
        self._game_labels = {value: key for key, value in self._games.items()}
        self._game_label_to_id = self._games
        self._format_labels = {item.label: item.id for item in backend.SUPPORTED_FORMATS}
        self._format_id_to_label = {value: key for key, value in self._format_labels.items()}
        self._palette = None
        self._selection_reverting = False

        self.viewport = ScrollablePanel(self.frame)
        self.viewport.frame.pack(fill='both', expand=True)
        body = self.viewport.content
        ttk.Label(body, text='GAME CONFIGURATION MANAGER',
                  font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        ttk.Label(body,
                  text='Manage only documented settings in supported Koei Tecmo PC configuration files. '
                       'Unknown keys and unsupported files are preserved or left untouched.',
                  style='Muted.TLabel', wraplength=1040).pack(anchor='w', pady=(3, 12))

        self.path = tk.StringVar(root)
        self.game = tk.StringVar(root, value=next(iter(self._games)))
        self.status = tk.StringVar(root, value='Choose an exact game profile and its settings file.')
        file_row = ttk.Frame(body)
        file_row.pack(fill='x', pady=(0, 5))
        file_row.columnconfigure(1, weight=1)
        ttk.Label(file_row, text='Game / PC profile').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.game_selector = ttk.Combobox(file_row, textvariable=self.game,
                                          values=tuple(self._games), state='readonly')
        self.game_selector.grid(row=0, column=1, sticky='ew', pady=3)
        ttk.Label(file_row, text='Configuration file').grid(row=1, column=0, sticky='w', padx=(0, 10))
        self.path_entry = ttk.Entry(file_row, textvariable=self.path)
        self.path_entry.grid(row=1, column=1, sticky='ew', pady=3)
        self.path.trace_add('write', self._selection_changed)
        self.game_selector.bind('<<ComboboxSelected>>', self._selection_changed)
        self.browse_button = ttk.Button(file_row, text='Browse…', command=self.browse)
        self.browse_button.grid(row=1, column=2, padx=(8, 0), pady=3)
        self.open_button = ttk.Button(file_row, text='Open and inspect', command=self.open_file)
        self.open_button.grid(row=1, column=3, padx=(8, 0), pady=3)
        ttk.Label(body, textvariable=self.status, wraplength=1040).pack(anchor='w', pady=(4, 10))

        self.settings = ttk.Treeview(body, columns=('category', 'value', 'pending', 'access'),
                                     show='tree headings', height=9, selectmode='browse')
        self.settings.heading('#0', text='Setting')
        self.settings.heading('category', text='Category')
        self.settings.heading('value', text='Current value')
        self.settings.heading('pending', text='Pending value')
        self.settings.heading('access', text='Access')
        self.settings.column('#0', width=240, minwidth=140)
        self.settings.column('category', width=120, minwidth=90)
        self.settings.column('value', width=260, minwidth=120)
        self.settings.column('pending', width=260, minwidth=120)
        self.settings.column('access', width=120, minwidth=90)
        self.settings.pack(fill='both', expand=True, pady=(0, 8))
        self.settings.bind('<<TreeviewSelect>>', self.select_setting)

        edit_row = ttk.Frame(body)
        edit_row.pack(fill='x', pady=(0, 8))
        ttk.Label(edit_row, text='Selected supported setting').pack(side='left', padx=(0, 8))
        self.value_choice = tk.StringVar(root)
        self.choice_selector = ttk.Combobox(edit_row, textvariable=self.value_choice,
                                            state='disabled', width=28)
        self.choice_selector.pack(side='left', padx=(0, 8))
        self.stage_button = ttk.Button(edit_row, text='Stage value', command=self.stage_value,
                                       state='disabled')
        self.stage_button.pack(side='left')
        actions = self.edit_actions = ttk.Frame(body)
        actions.pack(fill='x', pady=(0, 8))
        self.undo_button = ttk.Button(actions, text='Undo', command=self.undo, state='disabled')
        self.undo_button.pack(side='left', padx=(8, 0))
        self.review_button = ttk.Button(actions, text='Review Changes', command=self.review,
                                        state='disabled')
        self.review_button.pack(side='left', padx=(8, 0))
        self.save_button = ttk.Button(actions, text='Save staged settings', command=self.save,
                                      state='disabled')
        self.save_button.pack(side='right')
        self.backup_button = ttk.Button(actions, text='Create backup', command=self.create_backup,
                                        state='disabled')
        self.backup_button.pack(side='right', padx=(0, 8))

        profile_frame = ttk.LabelFrame(body, text='Settings profiles', padding=8)
        profile_frame.pack(fill='x', pady=5)
        profile_frame.columnconfigure(1, weight=1)
        ttk.Label(profile_frame, text='Saved profiles').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.profile_choice = tk.StringVar(root)
        self.profile_selector = ttk.Combobox(profile_frame, textvariable=self.profile_choice,
                                             state='readonly')
        self.profile_selector.grid(row=0, column=1, sticky='ew')
        ttk.Button(profile_frame, text='Save current as profile…', command=self.create_profile).grid(
            row=0, column=2, padx=(8, 0))
        ttk.Button(profile_frame, text='Stage selected profile', command=self.apply_profile).grid(
            row=0, column=3, padx=(8, 0))
        ttk.Button(profile_frame, text='Delete selected', command=self.delete_profile).grid(
            row=0, column=4, padx=(8, 0))
        ttk.Label(profile_frame,
                  text='Applying a profile stages its compatible writable values. Review them above, then save.',
                  style='Muted.TLabel', wraplength=1000).grid(row=1, column=0, columnspan=5,
                                                              sticky='w', pady=(6, 0))

        backup_frame = ttk.LabelFrame(body, text='Backups', padding=8)
        backup_frame.pack(fill='x', pady=5)
        backup_frame.columnconfigure(1, weight=1)
        ttk.Label(backup_frame, text='Saved backups').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.backup_choice = tk.StringVar(root)
        self.backup_selector = ttk.Combobox(backup_frame, textvariable=self.backup_choice,
                                            state='readonly')
        self.backup_selector.grid(row=0, column=1, sticky='ew')
        self.restore_button = ttk.Button(backup_frame, text='Restore selected backup…',
                                         command=self.restore_backup, state='disabled')
        self.restore_button.grid(row=0, column=2, padx=(8, 0))
        ttk.Label(backup_frame,
                  text='Restore makes an automatic backup of the current file and verifies exact bytes after writing.',
                  style='Muted.TLabel', wraplength=1000).grid(row=1, column=0, columnspan=3,
                                                              sticky='w', pady=(6, 0))

        check_frame = ttk.LabelFrame(body, text='Compatibility check', padding=8)
        check_frame.pack(fill='x', pady=5)
        ttk.Label(check_frame, text='Target game').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.target_game = tk.StringVar(root, value=self.game.get())
        self.target_game_selector = ttk.Combobox(check_frame, textvariable=self.target_game,
                                                 values=tuple(self._games), state='readonly', width=42)
        self.target_game_selector.grid(row=0, column=1, sticky='w', padx=(0, 12))
        ttk.Label(check_frame, text='Target format').grid(row=0, column=2, sticky='w', padx=(0, 8))
        first_format = next(iter(self._format_labels))
        self.target_format = tk.StringVar(root, value=first_format)
        self.target_format_selector = ttk.Combobox(check_frame, textvariable=self.target_format,
                                                   values=tuple(self._format_labels), state='readonly', width=34)
        self.target_format_selector.grid(row=0, column=3, sticky='w', padx=(0, 8))
        ttk.Button(check_frame, text='Check loaded file', command=self.check_compatibility).grid(
            row=0, column=4)
        ttk.Label(check_frame,
                  text='A compatibility result checks the selected game and exact settings format. It does not validate game installation or runtime behavior.',
                  style='Muted.TLabel', wraplength=1000).grid(row=1, column=0, columnspan=5,
                                                              sticky='w', pady=(6, 0))

        compare_frame = ttk.LabelFrame(body, text='Compare two configurations', padding=8)
        compare_frame.pack(fill='x', pady=5)
        compare_frame.columnconfigure(1, weight=1)
        ttk.Label(compare_frame, text='Other file').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.compare_path = tk.StringVar(root)
        self.compare_entry = ttk.Entry(compare_frame, textvariable=self.compare_path)
        self.compare_entry.grid(row=0, column=1, sticky='ew')
        ttk.Label(compare_frame, text='Its game').grid(row=0, column=2, sticky='w', padx=(12, 8))
        self.compare_game = tk.StringVar(root, value=self.game.get())
        self.compare_game_selector = ttk.Combobox(compare_frame, textvariable=self.compare_game,
                                                  values=tuple(self._games), state='readonly', width=42)
        self.compare_game_selector.grid(row=0, column=3, sticky='ew')
        ttk.Button(compare_frame, text='Browse…', command=self.browse_compare).grid(row=0, column=4, padx=8)
        ttk.Button(compare_frame, text='Compare', command=self.compare).grid(row=0, column=5)
        self.comparison_status = tk.StringVar(root, value='Open a configuration and choose a second supported file to compare.')
        ttk.Label(compare_frame, textvariable=self.comparison_status, wraplength=1000).grid(
            row=1, column=0, columnspan=6, sticky='w', pady=(6, 4))
        self.differences = ttk.Treeview(compare_frame, columns=('category', 'left', 'right'),
                                        show='tree headings', height=5)
        self.differences.heading('#0', text='Setting')
        self.differences.heading('category', text='Category')
        self.differences.heading('left', text='Loaded file')
        self.differences.heading('right', text='Other file')
        self.differences.column('#0', width=240, minwidth=140)
        self.differences.column('category', width=120, minwidth=80)
        self.differences.column('left', width=260, minwidth=120)
        self.differences.column('right', width=260, minwidth=120)
        self.differences.grid(row=2, column=0, columnspan=6, sticky='ew', pady=(4, 0))

    @property
    def selected_game_id(self):
        return self._game_label_to_id.get(self.game.get())

    def apply_theme(self, palette):
        self._palette = palette
        self.viewport.apply_theme(palette)

    def browse(self):
        filename = filedialog.askopenfilename(
            title='Choose a supported settings file',
            filetypes=[(item.label + ' (' + item.filename + ')', item.filename)
                       for item in backend.SUPPORTED_FORMATS] + [('All files', '*')])
        if filename:
            self.path.set(filename)
            if self.path.get() == filename:
                self.open_file()

    def browse_compare(self):
        filename = filedialog.askopenfilename(
            title='Choose another supported settings file',
            filetypes=[(item.label + ' (' + item.filename + ')', item.filename)
                       for item in backend.SUPPORTED_FORMATS] + [('All files', '*')])
        if filename:
            self.compare_path.set(filename)

    def _set_status(self, message):
        self.status.set(message)

    def _selection_changed(self, *_args):
        if self._selection_reverting or self.document is None:
            return
        current_path = self.path.get().strip()
        selected_game = self.selected_game_id
        try:
            same_path = Path(current_path).absolute() == self.document.path.absolute()
        except (OSError, ValueError):
            same_path = False
        if same_path and selected_game == self.document.game_id:
            return
        if not self.dirty_ok():
            self._selection_reverting = True
            try:
                self.path.set(str(self.document.path))
                self.game.set(self._game_labels[self.document.game_id])
            finally:
                self._selection_reverting = False
            return
        self.document = None
        self.staged = MappingProxyType({})
        self.history = ()
        self._clear_settings()
        self._refresh_records()
        self._set_status('The selected game or path changed. Open and inspect that exact file before continuing.')

    def _clear_settings(self):
        self.settings.delete(*self.settings.get_children())
        self._fields.clear()
        self._field_labels.clear()
        self.choice_selector.configure(state='disabled', values=())
        self.stage_button.configure(state='disabled')
        self.undo_button.configure(state='disabled')
        self.review_button.configure(state='disabled')
        self.save_button.configure(state='disabled')
        self.backup_button.configure(state='disabled')
        self.restore_button.configure(state='disabled')

    def dirty_ok(self):
        if not self.staged:
            return True
        return messagebox.askyesno(
            "Discard staged settings?",
            "Discard the pending configuration changes? Choose No to keep them and save first.",
            parent=self.root)

    def open_file(self):
        if not self.dirty_ok():
            return
        self.document = None
        self.staged = MappingProxyType({})
        self.history = ()
        self._clear_settings()
        game_id = self.selected_game_id
        if not game_id or not self.path.get().strip():
            self._set_status('Choose an exact game profile and settings file.')
            self._refresh_records()
            return
        try:
            self.document = backend.inspect_config(Path(self.path.get().strip()), game_id)
        except backend.ConfigurationError as error:
            self._set_status('Not opened: ' + str(error))
            self._refresh_records()
            return
        self.target_game.set(self.game.get())
        self.compare_game.set(self.game.get())
        self.target_format.set(self._format_id_to_label[self.document.format_id])
        fields = backend.supported_settings(self.document)
        for field in fields:
            self._fields[field.id] = field
            self._field_labels[field.id] = {value: label for value, label in field.choices}
            self.settings.insert('', 'end', iid=field.id,
                                 text=field.label,
                                 values=(field.category.title(), field.display_value, '',
                                         'Editable' if field.writable else 'Read-only'))
        self._set_status(f'Opened {self.document.filename} for {self.document.game_title}. '
                         f'{len(fields)} documented settings found; all other bytes remain opaque.')
        self._refresh_records()

    def select_setting(self, _event=None):
        selection = self.settings.selection()
        if not selection or self.document is None:
            self.choice_selector.configure(state='disabled', values=())
            self.stage_button.configure(state='disabled')
            return
        field = self._fields.get(selection[0])
        if field is None or not field.writable:
            self.choice_selector.configure(state='disabled', values=())
            self.stage_button.configure(state='disabled')
            return
        values = [label for _value, label in field.choices]
        current = self.staged.get(field.id, field.value)
        self.value_choice.set(self._field_labels[field.id].get(current, str(current)))
        self.choice_selector.configure(state='readonly', values=values)
        self.stage_button.configure(state='normal')

    def stage_value(self):
        selection = self.settings.selection()
        if not selection:
            return
        field = self._fields.get(selection[0])
        choices = {label: value for value, label in field.choices} if field else {}
        if not field or not field.writable or self.value_choice.get() not in choices:
            return
        number = choices[self.value_choice.get()]
        if number == field.value:
            candidate = dict(self.staged)
            candidate.pop(field.id, None)
        else:
            candidate = dict(self.staged)
            candidate[field.id] = number
        self._accept_staged(candidate)

    def _render_staged(self):
        for field_id, field in self._fields.items():
            pending = self._field_labels[field_id].get(self.staged.get(field_id), '')
            self.settings.set(field_id, 'pending', pending)
        self.save_button.configure(state='normal' if self.document and self.staged else 'disabled')
        self.undo_button.configure(state='normal' if self.document and self.history else 'disabled')
        self.review_button.configure(state='normal' if self.document and self.staged else 'disabled')

    def _accept_staged(self, candidate):
        """Validate and atomically replace the immutable pending map."""
        if self.document is None:
            return False
        try:
            candidate = dict(candidate)
            # Pure serialization validates the complete request, including
            # unknown/read-only fields and exact value types, before staging.
            backend.serialize_config(self.document, candidate)
        except (backend.ConfigurationError, TypeError, ValueError) as error:
            self._set_status('Settings were not staged: ' + str(error))
            return False
        candidate = {field_id: value for field_id, value in candidate.items()
                     if self._fields[field_id].value != value}
        if candidate != dict(self.staged):
            self.history = (*self.history, tuple(self.staged.items()))
            self.staged = MappingProxyType(candidate)
        self._render_staged()
        self._set_status(f'{len(self.staged)} documented setting(s) staged. Review them before saving.')
        return True

    def undo(self):
        if self.document is None or not self.history:
            return False
        previous = dict(self.history[-1])
        try:
            backend.serialize_config(self.document, previous)
        except backend.ConfigurationError as error:
            self._set_status('Undo was not applied: ' + str(error))
            return False
        self.history = self.history[:-1]
        self.staged = MappingProxyType(previous)
        self._render_staged()
        self._set_status(f'Undo complete. {len(self.staged)} documented setting(s) remain staged.')
        return True

    def review(self):
        """Show the validated pending changes without writing the source file."""
        if self.document is None or not self.staged:
            self._set_status('Stage at least one supported setting before reviewing changes.')
            return None
        document = self.document
        pending = dict(self.staged)
        try:
            backend.serialize_config(document, pending)
        except backend.ConfigurationError as error:
            self._set_status('Review unavailable: ' + str(error))
            return None

        dialog = tk.Toplevel(self.root)
        dialog.title('Review Configuration Changes')
        dialog.geometry('760x380')
        dialog.configure(background=ttk.Style(dialog).lookup('TFrame', 'background')
                         or self.root.cget('background'))
        ttk.Label(dialog, text=f'{document.game_title}\n{document.filename} · {len(pending)} staged setting(s)',
                  padding=14, wraplength=720).pack(anchor='w')
        ttk.Label(dialog, text='No file has been written. Save only after reviewing these values.',
                  padding=(14, 0, 14, 10), style='Muted.TLabel').pack(anchor='w')
        # Reserve the footer before the expanding tree at native row heights.
        ttk.Button(dialog, text='Close', command=dialog.destroy).pack(side='bottom', pady=12)
        scroll = ttk.Scrollbar(dialog, orient='vertical')
        scroll.pack(side='right', fill='y', padx=(0, 14))
        tree = ttk.Treeview(dialog, columns=('category', 'opened', 'pending'),
                            show='tree headings', height=9)
        tree.heading('#0', text='Setting')
        tree.heading('category', text='Category')
        tree.heading('opened', text='Opened value')
        tree.heading('pending', text='Pending value')
        tree.column('#0', width=240, minwidth=140)
        tree.column('category', width=120, minwidth=90)
        tree.column('opened', width=160, minwidth=100)
        tree.column('pending', width=160, minwidth=100)
        tree.pack(fill='both', expand=True, padx=(14, 0))
        tree.configure(yscrollcommand=scroll.set)
        scroll.configure(command=tree.yview)
        for field_id, value in pending.items():
            field = self._fields[field_id]
            labels = self._field_labels[field_id]
            tree.insert('', 'end', iid=field_id, text=field.label,
                        values=(field.category.title(), labels.get(field.value, str(field.value)),
                                labels.get(value, str(value)))
                        )
        return dialog

    def save(self):
        if self.document is None or not self.staged:
            return
        try:
            saved = backend.save_config(self.document, dict(self.staged))
        except backend.ConfigurationError as error:
            self._set_status('Save failed; no settings were reported as saved: ' + str(error))
            return
        changed = len(self.staged)
        self.document = saved
        self.staged = MappingProxyType({})
        self.history = ()
        self.open_file()
        self._set_status(f'Saved and read back {changed} documented setting(s). A verified backup was created.')

    def create_profile(self):
        if self.document is None:
            return
        name = simpledialog.askstring('Save settings profile', 'Profile name:', parent=self.root)
        if name is None:
            return
        try:
            profile = backend.create_profile(self.document, name)
        except backend.ConfigurationError as error:
            self._set_status('Profile was not saved: ' + str(error))
            return
        self._refresh_records()
        self.profile_choice.set(self._profile_labels.get(profile.id, ''))
        self._set_status(f'Saved path-free profile “{profile.name}” for {self.document.game_title}.')

    def _refresh_records(self):
        try:
            profiles = backend.list_profiles()
        except backend.ConfigurationError as error:
            profiles = ()
            self._set_status('Could not load profiles: ' + str(error))
        self._profiles = {profile.id: profile for profile in profiles}
        profile_bases = {
            profile.id: f'{profile.name} · {self._game_labels.get(profile.game_id, profile.game_id)} · '
                        f'{self._format_id_to_label.get(profile.format_id, profile.format_id)}'
            for profile in profiles
        }
        base_counts = {}
        for label in profile_bases.values():
            base_counts[label] = base_counts.get(label, 0) + 1
        self._profile_labels = {
            profile.id: (label if base_counts[label] == 1 else f'{label} [{profile.id}]')
            for profile in profiles for label in (profile_bases[profile.id],)
        }
        self._profile_id_by_label = {label: profile_id for profile_id, label in self._profile_labels.items()}
        self.profile_selector.configure(values=tuple(self._profile_labels.values()))
        if self.profile_choice.get() not in self._profile_labels.values():
            self.profile_choice.set('')
        game_id = self.selected_game_id
        try:
            backups = backend.list_backups(game_id=game_id) if game_id else ()
        except backend.ConfigurationError as error:
            backups = ()
            self._set_status('Could not load backups: ' + str(error))
        self._backups = {backup.id: backup for backup in backups}
        self._backup_labels = {backup.id: f'{backup.created_utc} · {backup.filename} · {backup.sha256[:12]}'
                               for backup in backups}
        self.backup_selector.configure(values=tuple(self._backup_labels.values()))
        if self.backup_choice.get() not in self._backup_labels.values():
            self.backup_choice.set('')
        self.backup_button.configure(state='normal' if self.document is not None else 'disabled')
        self.restore_button.configure(state='normal' if self.document and self._backups else 'disabled')

    def _profile_by_selection(self):
        profile_id = self._profile_id_by_label.get(self.profile_choice.get())
        return self._profiles.get(profile_id)

    def apply_profile(self):
        if self.document is None:
            return
        profile = self._profile_by_selection()
        if profile is None:
            self._set_status('Select a saved profile first.')
            return
        try:
            assignments = backend.apply_profile(self.document, profile)
        except backend.ConfigurationError as error:
            self._set_status('Profile is incompatible: ' + str(error))
            return
        if self._accept_staged({**self.staged, **assignments}):
            self._set_status(f'Profile “{profile.name}” staged. Review pending values before saving.')

    def delete_profile(self):
        profile = self._profile_by_selection()
        if profile is None:
            self._set_status('Select a saved profile first.')
            return
        try:
            backend.delete_profile(profile.id)
        except backend.ConfigurationError as error:
            self._set_status('Profile was not deleted: ' + str(error))
            return
        self.profile_choice.set('')
        self._refresh_records()
        self._set_status(f'Deleted profile “{profile.name}”.')

    def create_backup(self):
        if self.document is None:
            return
        try:
            backup = backend.create_backup(self.document)
        except backend.ConfigurationError as error:
            self._set_status('Backup failed: ' + str(error))
            return
        self._refresh_records()
        self.backup_choice.set(self._backup_labels.get(backup.id, ''))
        self._set_status(f'Backed up exact source bytes ({backup.size_bytes} bytes, SHA-256 {backup.sha256}).')

    def _backup_by_selection(self):
        label = self.backup_choice.get()
        backup_id = next((key for key, value in self._backup_labels.items() if value == label), None)
        return self._backups.get(backup_id)

    def restore_backup(self):
        if self.document is None:
            return
        backup = self._backup_by_selection()
        if backup is None:
            self._set_status('Select a saved backup first.')
            return
        accepted = messagebox.askyesno(
            'Restore configuration backup',
            f'Restore {backup.filename} from {backup.created_utc}?\n\n'
            'The current file will be backed up first. The exact restored bytes will be verified.',
            parent=self.root)
        if not accepted:
            return
        try:
            self.document = backend.restore_backup(self.document, backup.id)
        except backend.ConfigurationError as error:
            self._set_status('Restore failed: ' + str(error))
            return
        self.staged = MappingProxyType({})
        self.history = ()
        self.open_file()
        self._set_status(f'Restored {backup.filename}; exact bytes were verified after writing.')

    def check_compatibility(self):
        if self.document is None:
            self._set_status('Open a supported file before checking compatibility.')
            return
        target_game = self._game_label_to_id.get(self.target_game.get())
        target_format = self._format_labels.get(self.target_format.get())
        fmt = self._formats.get(target_format)
        result = backend.compatibility_check(
            self.document, target_game, target_format,
            fmt.version if fmt is not None else None)
        state = 'Compatible' if result.compatible else 'Incompatible'
        self._set_status(f'{state}: {result.message}')

    def compare(self):
        if self.document is None:
            self.comparison_status.set('Open the first supported file before comparing.')
            return
        game_id = self._game_label_to_id.get(self.compare_game.get())
        path = self.compare_path.get().strip()
        if not game_id or not path:
            self.comparison_status.set('Choose the second file and its exact game profile.')
            return
        try:
            other = backend.inspect_config(Path(path), game_id)
            result = backend.compare_configs(self.document, other)
        except backend.ConfigurationError as error:
            self.differences.delete(*self.differences.get_children())
            self.comparison_status.set('Comparison unavailable: ' + str(error))
            return
        self.differences.delete(*self.differences.get_children())
        if not result.compatible:
            self.comparison_status.set(result.message)
            return
        for difference in result.changed_fields:
            first = self._display_difference(difference.field_id, difference.left_value, self.document)
            second = self._display_difference(difference.field_id, difference.right_value, other)
            self.differences.insert('', 'end', text=difference.label,
                                    values=(difference.category.title(), first, second))
        opaque = 'Opaque, unrecognized bytes differ.' if result.opaque_difference else 'Opaque bytes match.'
        scope = 'same game' if result.same_game else 'same verified format across titles'
        count = len(result.changed_fields)
        self.comparison_status.set(f'{result.message} {count} documented difference(s); {opaque} Scope: {scope}.')

    def _display_difference(self, field_id, value, document):
        if value is None:
            return '(missing)'
        field = next((item for item in document.fields if item.id == field_id), None)
        if field is not None:
            return dict(field.choices).get(value, str(value))
        return str(value)

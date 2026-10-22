"""Tk workspace for app-owned controller profile templates."""
from dataclasses import replace
from pathlib import Path
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.game_registry import GAMES
from koei_editor.shared import controller_profiles as profiles


PC_GAMES = tuple(sorted((game for game in GAMES if game.platform == 'Windows PC'),
                        key=lambda game: (game.title.casefold(), game.subtitle.casefold(), game.id)))
GAME_LABELS = {f'{game.title} · {game.subtitle}': game.id for game in PC_GAMES}
GAME_BY_ID = {game.id: game for game in PC_GAMES}
PRESET_LABELS = {
    'blank': 'Blank profile',
    'keyboard_wasd': 'Keyboard WASD starter',
    'keyboard_arrows': 'Keyboard arrows starter',
    'controller_xbox': 'Xbox label starter',
    'controller_playstation': 'PlayStation label starter',
    'controller_nintendo': 'Nintendo label starter',
}
_TEXTS = {
    'title': ('Controller & Input Profiles', 'Controller- und Eingabeprofile'),
    'intro': ('These profiles are saved by this app. They do not change game files or Steam Input. '
              'Starter templates are suggestions; verify every binding in the selected game.',
              'Diese Profile speichert nur diese App. Sie ändern weder Spieldateien noch Steam Input. '
              'Vorlagen sind Vorschläge; überprüfe jede Tastenbelegung im ausgewählten Spiel.'),
    'game_profile': ('Game / profile', 'Spiel / Profil'),
    'find_profile': ('Find a profile', 'Profil suchen'),
    'saved_profiles': ('Saved app profiles', 'Gespeicherte App-Profile'),
    'profile': ('Profile', 'Profil'),
    'layout_labels': ('Layout labels', 'Layout-Bezeichnungen'),
    'starter': ('Starter', 'Vorlage'),
    'bindings_title': ('Bindings in selected profile', 'Belegungen im ausgewählten Profil'),
    'action_label': ('Action label', 'Aktionsname'),
    'keyboard': ('Keyboard', 'Tastatur'),
    'controller': ('Controller', 'Controller'),
    'action_note': ('Action names are user supplied and are not read from the game.',
                    'Aktionsnamen gibst du selbst ein; sie werden nicht aus dem Spiel gelesen.'),
    'new': ('New from starter…', 'Neu aus Vorlage…'),
    'edit': ('Edit', 'Bearbeiten'),
    'delete': ('Delete', 'Löschen'),
    'import': ('Import profile…', 'Profil importieren…'),
    'export': ('Export selected…', 'Ausgewähltes exportieren…'),
    'backup': ('Back up profiles', 'Profile sichern'),
    'restore': ('Restore latest backup…', 'Letzte Sicherung wiederherstellen…'),
    'status': ('These profiles are saved by this app. They do not change game files or Steam Input. '
               'Starter templates are suggestions; verify every binding in the selected game.',
               'Diese Profile speichert nur diese App. Sie ändern weder Spieldateien noch Steam Input. '
               'Vorlagen sind Vorschläge; überprüfe jede Tastenbelegung im ausgewählten Spiel.'),
}
_DIALOG_TEXTS = {
    'edit_title': ('Edit controller profile', 'Controllerprofil bearbeiten'),
    'new_title': ('New controller profile', 'Neues Controllerprofil'),
    'blank_profile_name': ('Blank profile', 'Leeres Profil'),
    'profile_name': ('Profile name', 'Profilname'),
    'starter_preset': ('Starter preset', 'Startvorlage'),
    'controller_labels': ('Controller labels', 'Controller-Beschriftungen'),
    'binding_prompt': ('Bindings · use the action names and button labels shown in your game.',
                       'Belegungen · Verwende Aktionsnamen und Tastenbezeichnungen aus dem Spiel.'),
    'action_label': ('Action label', 'Aktionsname'),
    'keyboard_input': ('Keyboard input', 'Tastatureingabe'),
    'controller_button': ('Controller button', 'Controller-Taste'),
    'action': ('Action', 'Aktion'),
    'keyboard': ('Keyboard', 'Tastatur'),
    'controller': ('Controller', 'Controller'),
    'add_update': ('Add / update binding', 'Belegung hinzufügen/aktualisieren'),
    'remove_selected': ('Remove selected binding', 'Ausgewählte Belegung entfernen'),
    'invalid_binding': ('Invalid binding', 'Ungültige Belegung'),
    'duplicate_action': ('Duplicate action', 'Doppelte Aktion'),
    'unique_action': ('Use a unique action label.', 'Verwende einen eindeutigen Aktionsnamen.'),
    'save_error': ('Could not save profile', 'Profil konnte nicht gespeichert werden'),
    'starter_note': ('Starter bindings are suggestions, not game-confirmed defaults.',
                     'Vorlagen sind Vorschläge, keine im Spiel bestätigten Standardbelegungen.'),
    'cancel': ('Cancel', 'Abbrechen'),
    'save': ('Save profile', 'Profil speichern'),
    'layout_generic': ('Generic', 'Allgemein'),
    'layout_xbox': ('Xbox labels', 'Xbox-Beschriftungen'),
    'layout_playstation': ('PlayStation labels', 'PlayStation-Beschriftungen'),
    'layout_nintendo': ('Nintendo labels', 'Nintendo-Beschriftungen'),
    'layout_custom': ('Custom', 'Benutzerdefiniert'),
}


class ControllerProfileWorkspace:
    """Reusable profile workspace; native game and Steam files are never opened."""

    def __init__(self, root, parent, store=None, language='en'):
        self.root = root
        self.store = store or profiles.ProfileStore()
        self.language = 'de' if language == 'de' else 'en'
        self._localized_widgets = []
        self.game_id = PC_GAMES[0].id if PC_GAMES else None
        self.profile_by_tree_id = {}
        self.frame = ttk.Frame(parent, padding=(28, 18))
        self._build()
        self._load_profiles()

    def _build(self):
        self.title_label = self._label(self.frame, 'title', font=('Segoe UI', 17, 'bold'))
        self.title_label.pack(anchor='w')
        self.status = tk.StringVar(self.root, value=self._tr('intro'))
        ttk.Label(self.frame, textvariable=self.status, style='Muted.TLabel',
                  wraplength=960, justify='left').pack(anchor='w', pady=(6, 14))

        game_row = ttk.Frame(self.frame)
        game_row.pack(fill='x', pady=(0, 12))
        self._label(game_row, 'game_profile').pack(side='left', padx=(0, 10))
        self.game_choice = tk.StringVar(self.root)
        self.game_selector = ttk.Combobox(game_row, textvariable=self.game_choice,
                                          values=tuple(GAME_LABELS), state='readonly', width=75)
        self.game_selector.pack(side='left', fill='x', expand=True)
        if self.game_id:
            self.game_choice.set(self._game_label(self.game_id))
        self.game_selector.bind('<<ComboboxSelected>>', self._select_game)

        search_row = ttk.Frame(self.frame)
        search_row.pack(fill='x', pady=(0, 10))
        self._label(search_row, 'find_profile').pack(side='left', padx=(0, 10))
        self.profile_search = tk.StringVar(self.root)
        self.search_entry = ttk.Entry(search_row, textvariable=self.profile_search)
        self.search_entry.pack(side='left', fill='x', expand=True)
        self.profile_search.trace_add('write', lambda *_args: self._load_profiles())

        columns = ttk.Panedwindow(self.frame, orient='horizontal')
        columns.pack(fill='both', expand=True)
        left = ttk.Frame(columns, padding=(0, 0, 12, 0))
        right = ttk.Frame(columns)
        columns.add(left, weight=1)
        columns.add(right, weight=1)

        self._label(left, 'saved_profiles').pack(anchor='w', pady=(0, 5))
        self.profile_tree = ttk.Treeview(left, columns=('layout', 'preset'), show='tree headings',
                                         selectmode='browse', height=10, style='ControllerProfile.Treeview')
        self.profile_tree.heading('#0', text=self._tr('profile'))
        self.profile_tree.heading('layout', text=self._tr('layout_labels'))
        self.profile_tree.heading('preset', text=self._tr('starter'))
        self.profile_tree.column('#0', width=220, stretch=True)
        self.profile_tree.column('layout', width=130, stretch=False)
        self.profile_tree.column('preset', width=150, stretch=True)
        self.profile_tree.pack(fill='both', expand=True)
        self.profile_tree.bind('<<TreeviewSelect>>', self._select_profile)
        actions = ttk.Frame(left)
        actions.pack(fill='x', pady=(8, 0))
        self._button(actions, 'new', self.new_profile).pack(side='left')
        self._button(actions, 'edit', self.edit_profile).pack(side='left', padx=(6, 0))
        self._button(actions, 'delete', self.delete_profile).pack(side='left', padx=(6, 0))

        self._label(right, 'bindings_title').pack(anchor='w', pady=(0, 5))
        self.binding_tree = ttk.Treeview(right, columns=('keyboard', 'controller'), show='tree headings',
                                         height=10, style='ControllerProfile.Treeview')
        self.binding_tree.heading('#0', text=self._tr('action_label'))
        self.binding_tree.heading('keyboard', text=self._tr('keyboard'))
        self.binding_tree.heading('controller', text=self._tr('controller'))
        self.binding_tree.column('#0', width=180, stretch=True)
        self.binding_tree.column('keyboard', width=105, stretch=True)
        self.binding_tree.column('controller', width=120, stretch=True)
        self.binding_tree.pack(fill='both', expand=True)
        self._label(right, 'action_note', style='Muted.TLabel', wraplength=480).pack(anchor='w', pady=(6, 0))

        utility = ttk.Frame(self.frame)
        utility.pack(fill='x', pady=(14, 0))
        self._button(utility, 'import', self.import_profile).pack(side='left')
        self._button(utility, 'export', self.export_profile).pack(side='left', padx=(6, 0))
        self._button(utility, 'backup', self.backup_profiles).pack(side='left', padx=(16, 0))
        self._button(utility, 'restore', self.restore_profiles).pack(side='left', padx=(6, 0))

    def _tr(self, key):
        value = _TEXTS[key]
        return value[1] if self.language == 'de' else value[0]

    def _dialog_text(self, key):
        value = _DIALOG_TEXTS[key]
        return value[1] if self.language == 'de' else value[0]

    def _layout_label(self, layout_id):
        return self._dialog_text(f'layout_{layout_id}')

    def _layout_id_from_label(self, label):
        return next((key for key in profiles.LAYOUTS if self._layout_label(key) == label), 'generic')

    def _label(self, parent, key, **kwargs):
        widget = ttk.Label(parent, text=self._tr(key), **kwargs)
        self._localized_widgets.append((widget, key))
        return widget

    def _button(self, parent, key, command):
        widget = ttk.Button(parent, text=self._tr(key), command=command)
        self._localized_widgets.append((widget, key))
        return widget

    def set_language(self, language):
        """Update retained workspace labels for the app's English/German setting."""
        selected = self._selected_profile()
        selected_id = selected.profile_id if selected else None
        self.language = 'de' if language == 'de' else 'en'
        for widget, key in self._localized_widgets:
            try:
                widget.configure(text=self._tr(key))
            except tk.TclError:
                # Dialogs may have closed since their controls were registered.
                continue
        self.profile_tree.heading('#0', text=self._tr('profile'))
        self.profile_tree.heading('layout', text=self._tr('layout_labels'))
        self.profile_tree.heading('preset', text=self._tr('starter'))
        self.binding_tree.heading('#0', text=self._tr('action_label'))
        self.binding_tree.heading('keyboard', text=self._tr('keyboard'))
        self.binding_tree.heading('controller', text=self._tr('controller'))
        self._load_profiles(selected_id)

    def _game_label(self, game_id):
        game = GAME_BY_ID.get(game_id)
        return f'{game.title} · {game.subtitle}' if game else ''

    def _select_game(self, _event=None):
        self.game_id = GAME_LABELS.get(self.game_choice.get())
        self._load_profiles()

    def _load_profiles(self, select_id=None):
        self.profile_by_tree_id.clear()
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)
        for item in self.binding_tree.get_children():
            self.binding_tree.delete(item)
        if not self.game_id:
            return
        try:
            items = self.store.list_profiles(self.game_id)
        except profiles.ProfileError as error:
            self.status.set(str(error))
            return
        query = self.profile_search.get().strip().casefold()
        for profile in items:
            searchable = ' '.join((profile.name, profiles.LAYOUTS[profile.layout],
                                   self._preset_label(profile.preset_id),
                                   *(value for binding in profile.bindings
                                     for value in (binding.action, binding.keyboard, binding.controller))))
            if query and query not in searchable.casefold():
                continue
            tree_id = f'{profile.game_id}:{profile.profile_id}'
            self.profile_by_tree_id[tree_id] = profile
            self.profile_tree.insert('', 'end', iid=tree_id,
                                     text=profile.name,
                                     values=(profiles.LAYOUTS[profile.layout],
                                             self._preset_label(profile.preset_id)))
        if select_id:
            tree_id = f'{self.game_id}:{select_id}'
            if tree_id in self.profile_by_tree_id:
                self.profile_tree.selection_set(tree_id)
                self.profile_tree.focus(tree_id)
                self._show_bindings(self.profile_by_tree_id[tree_id])
                return
        if self.profile_by_tree_id:
            first = next(iter(self.profile_by_tree_id))
            self.profile_tree.selection_set(first)
            self._show_bindings(self.profile_by_tree_id[first])
        self.status.set(self._tr('status'))

    def _selected_profile(self):
        selected = self.profile_tree.selection()
        return self.profile_by_tree_id.get(selected[0]) if selected else None

    def _select_profile(self, _event=None):
        profile = self._selected_profile()
        if profile:
            self._show_bindings(profile)

    def _show_bindings(self, profile):
        for item in self.binding_tree.get_children():
            self.binding_tree.delete(item)
        for index, binding in enumerate(profile.bindings):
            self.binding_tree.insert('', 'end', iid=str(index), text=binding.action,
                                     values=(binding.keyboard, binding.controller))
        if self.language == 'de':
            self.status.set(f'{profile.name} · {profiles.LAYOUTS[profile.layout]}. '
                            'Dieses App-Profil ändert das Spiel nicht; prüfe die Steuerung im Spiel.')
        else:
            self.status.set(f'{profile.name} · {profiles.LAYOUTS[profile.layout]}. '
                            'This app stores the profile only; verify the controls in game.')

    def focus_search(self):
        """Focus profile search when the main shell routes Ctrl+F here."""
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, 'end')

    def _preset_label(self, preset_id):
        label = PRESET_LABELS.get(preset_id, 'Custom')
        if self.language != 'de':
            return label
        translated = {
            'Blank profile': 'Leeres Profil',
            'Keyboard WASD starter': 'Tastaturvorlage WASD',
            'Keyboard arrows starter': 'Tastaturvorlage Pfeile',
            'Xbox label starter': 'Xbox-Beschriftungsvorlage',
            'PlayStation label starter': 'PlayStation-Beschriftungsvorlage',
            'Nintendo label starter': 'Nintendo-Beschriftungsvorlage',
            'Custom': 'Benutzerdefiniert',
        }
        return translated[label]

    def new_profile(self):
        if not self.game_id:
            return
        self._edit_dialog(None)

    def edit_profile(self):
        profile = self._selected_profile()
        if profile:
            self._edit_dialog(profile)

    def _edit_dialog(self, existing):
        dialog = tk.Toplevel(self.root)
        dialog.title(self._dialog_text('edit_title' if existing else 'new_title'))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry('720x600')
        body = ttk.Frame(dialog, padding=18)
        body.pack(fill='both', expand=True)
        name = tk.StringVar(dialog, value=existing.name if existing else
                            self._dialog_text('blank_profile_name'))
        preset_id = existing.preset_id if existing else 'blank'
        preset_label = self._preset_label(preset_id)
        preset_choice = tk.StringVar(dialog, value=preset_label)
        layout = tk.StringVar(dialog, value=self._layout_label(existing.layout if existing else 'generic'))
        header = ttk.Frame(body)
        header.pack(fill='x')
        ttk.Label(header, text=self._dialog_text('profile_name')).grid(row=0, column=0, sticky='w')
        ttk.Entry(header, textvariable=name, width=34).grid(row=1, column=0, sticky='ew', padx=(0, 12))
        ttk.Label(header, text=self._dialog_text('starter_preset')).grid(row=0, column=1, sticky='w')
        preset_values = tuple(self._preset_label(key) for key in PRESET_LABELS)
        if existing and preset_label not in preset_values:
            preset_values += (preset_label,)
        preset_selector = ttk.Combobox(header, textvariable=preset_choice, values=preset_values,
                                       state='readonly', width=28)
        if existing:
            preset_selector.configure(state='disabled')
        preset_selector.grid(row=1, column=1, sticky='ew', padx=(0, 12))
        ttk.Label(header, text=self._dialog_text('controller_labels')).grid(row=0, column=2, sticky='w')
        layout_selector = ttk.Combobox(header, textvariable=layout,
                                       values=tuple(self._layout_label(key) for key in profiles.LAYOUTS),
                                       state='readonly', width=24)
        layout_selector.grid(row=1, column=2, sticky='ew')
        for column in range(3):
            header.columnconfigure(column, weight=1)

        ttk.Label(body, text=self._dialog_text('binding_prompt')).pack(
            anchor='w', pady=(14, 5))
        rows = list(existing.bindings) if existing else []
        tree = ttk.Treeview(body, columns=('keyboard', 'controller'), show='tree headings', height=11,
                            selectmode='browse')
        tree.heading('#0', text=self._dialog_text('action_label'))
        tree.heading('keyboard', text=self._dialog_text('keyboard_input'))
        tree.heading('controller', text=self._dialog_text('controller_button'))
        tree.column('#0', width=210)
        tree.column('keyboard', width=140)
        tree.column('controller', width=150)
        tree.pack(fill='both', expand=True)
        action = tk.StringVar(dialog)
        keyboard = tk.StringVar(dialog)
        controller = tk.StringVar(dialog)
        fields = ttk.Frame(body)
        fields.pack(fill='x', pady=(8, 0))
        field_labels = (self._dialog_text('action'), self._dialog_text('keyboard'),
                        self._dialog_text('controller'))
        for column, (label, variable, width) in enumerate(zip(
                field_labels, (action, keyboard, controller), (22, 16, 18))):
            ttk.Label(fields, text=label).grid(row=0, column=column, sticky='w')
            ttk.Entry(fields, textvariable=variable, width=width).grid(row=1, column=column,
                                                                        sticky='ew', padx=(0, 8))
            fields.columnconfigure(column, weight=1)

        def redraw(select=None):
            for item in tree.get_children():
                tree.delete(item)
            for index, binding in enumerate(rows):
                tree.insert('', 'end', iid=str(index), text=binding.action,
                            values=(binding.keyboard, binding.controller))
            if select is not None:
                tree.selection_set(str(select))
                tree.focus(str(select))

        def select_row(_event=None):
            selected = tree.selection()
            if not selected:
                return
            binding = rows[int(selected[0])]
            action.set(binding.action)
            keyboard.set(binding.keyboard)
            controller.set(binding.controller)

        def upsert_row():
            try:
                updated = profiles.Binding(action.get(), keyboard.get(), controller.get())
                # Validate the row with a temporary one-action profile.
                profiles.create_profile(self.game_id, name.get().strip() or 'Profile',
                                        layout=self._layout_id_from_label(layout.get()), bindings=(updated,))
            except profiles.ProfileError as error:
                messagebox.showerror(self._dialog_text('invalid_binding'), str(error), parent=dialog)
                return
            selected = tree.selection()
            if selected:
                index = int(selected[0])
                rows[index] = updated
                redraw(index)
            else:
                if any(row.action.casefold() == updated.action.casefold() for row in rows):
                    messagebox.showerror(self._dialog_text('duplicate_action'),
                                         self._dialog_text('unique_action'), parent=dialog)
                    return
                rows.append(updated)
                redraw(len(rows) - 1)
            action.set('')
            keyboard.set('')
            controller.set('')

        def remove_row():
            selected = tree.selection()
            if selected:
                rows.pop(int(selected[0]))
                redraw()
                action.set('')
                keyboard.set('')
                controller.set('')

        tree.bind('<<TreeviewSelect>>', select_row)
        row_buttons = ttk.Frame(body)
        row_buttons.pack(fill='x', pady=(8, 0))
        ttk.Button(row_buttons, text=self._dialog_text('add_update'), command=upsert_row).pack(side='left')
        ttk.Button(row_buttons, text=self._dialog_text('remove_selected'), command=remove_row).pack(
            side='left', padx=(6, 0))
        if existing:
            redraw()
        else:
            preset_selector.bind('<<ComboboxSelected>>', lambda _event: self._apply_preset_to_dialog(
                preset_choice, layout, rows, redraw))
            self._apply_preset_to_dialog(preset_choice, layout, rows, redraw)

        def save():
            try:
                selected_preset = (existing.preset_id if existing else
                                   self._preset_id_from_label(preset_choice.get()))
                profile = profiles.create_profile(
                    self.game_id, name.get(), layout=self._layout_id_from_label(layout.get()),
                    bindings=tuple(rows),
                    preset_id=selected_preset,
                    profile_id=existing.profile_id if existing else None)
                self.store.save_profile(profile)
            except profiles.ProfileError as error:
                messagebox.showerror(self._dialog_text('save_error'), str(error), parent=dialog)
                return
            dialog.destroy()
            self._load_profiles(profile.profile_id)

        footer = ttk.Frame(body)
        footer.pack(fill='x', pady=(12, 0))
        ttk.Label(footer, text=self._dialog_text('starter_note'),
                  style='Muted.TLabel').pack(side='left')
        ttk.Button(footer, text=self._dialog_text('cancel'), command=dialog.destroy).pack(side='right')
        ttk.Button(footer, text=self._dialog_text('save'), command=save).pack(side='right', padx=(0, 6))

    def _apply_preset_to_dialog(self, preset_choice, layout, rows, redraw):
        preset_id = self._preset_id_from_label(preset_choice.get())
        preset = profiles.PRESETS[preset_id]
        layout.set(self._layout_label(preset['layout']))
        rows[:] = list(preset['bindings'])
        redraw()

    def _preset_id_from_label(self, label):
        return next((key for key in PRESET_LABELS if self._preset_label(key) == label), 'blank')

    def delete_profile(self):
        profile = self._selected_profile()
        if not profile:
            messagebox.showinfo('Delete profile', 'Select an app profile first.', parent=self.root)
            return
        if not messagebox.askyesno('Delete profile',
                                   f'Delete the app profile “{profile.name}”? This does not change game files.',
                                   parent=self.root):
            return
        try:
            self.store.delete_profile(profile.game_id, profile.profile_id)
        except profiles.ProfileError as error:
            messagebox.showerror('Could not delete profile', str(error), parent=self.root)
            return
        self._load_profiles()

    def import_profile(self):
        source = filedialog.askopenfilename(
            parent=self.root, title='Import app profile',
            filetypes=[('Koei Tecmo input profile', '*.ktinput.json'), ('JSON files', '*.json')])
        if not source:
            return
        try:
            profile = self.store.import_profile(source)
            if profile.game_id != self.game_id:
                raise profiles.ProfileError('This profile belongs to a different registered game.')
            # Imports are always added as a new profile; an existing identity is never replaced.
            profile = replace(profile, profile_id=uuid.uuid4().hex)
            self.store.save_profile(profile)
        except profiles.ProfileError as error:
            messagebox.showerror('Could not import profile', str(error), parent=self.root)
            return
        self._load_profiles(profile.profile_id)

    def export_profile(self):
        profile = self._selected_profile()
        if not profile:
            messagebox.showinfo('Export profile', 'Select an app profile first.', parent=self.root)
            return
        destination = filedialog.asksaveasfilename(
            parent=self.root, title='Export app profile',
            defaultextension='.ktinput.json', initialfile='controller-profile.ktinput.json',
            filetypes=[('Koei Tecmo input profile', '*.ktinput.json'), ('JSON files', '*.json')])
        if not destination:
            return
        try:
            self.store.export_profile(profile, destination)
        except profiles.ProfileError as error:
            messagebox.showerror('Could not export profile', str(error), parent=self.root)
            return
        messagebox.showinfo('Profile exported', 'The app profile was exported. No game or Steam files were changed.',
                            parent=self.root)

    def backup_profiles(self):
        try:
            created = self.store.create_backup()
        except profiles.ProfileError as error:
            messagebox.showerror('Could not back up profiles', str(error), parent=self.root)
            return
        messagebox.showinfo('Back up profiles',
                            ('A copy of the current app profile store was saved.' if created else
                             'There are no saved profiles to back up.'), parent=self.root)

    def restore_profiles(self):
        if not self.store.backup_path.exists():
            messagebox.showinfo('Restore profiles', 'No app profile backup is available yet.', parent=self.root)
            return
        if not messagebox.askyesno(
                'Restore app profiles',
                'Restore the latest app profile backup? The current store will become the new backup. '
                'Game files and Steam Input will not be changed.', parent=self.root):
            return
        try:
            restored = self.store.restore_backup()
        except profiles.ProfileError as error:
            messagebox.showerror('Could not restore profiles', str(error), parent=self.root)
            return
        self._load_profiles()
        messagebox.showinfo('Profiles restored', f'Restored {len(restored)} app profile(s).', parent=self.root)

    def apply_theme(self, palette):
        """Keep the manager surface aligned with the main app theme."""
        self.frame.configure(style='TFrame')
        style = ttk.Style(self.root)
        style.configure('ControllerProfile.Treeview', background=palette['surface'],
                        fieldbackground=palette['surface'], foreground=palette['text'])
        style.map('ControllerProfile.Treeview',
                  background=[('selected', palette['accent'])],
                  foreground=[('selected', '#ffffff')])

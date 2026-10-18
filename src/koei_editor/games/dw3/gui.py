"""Small Tkinter editor; decoding and validated writes live in separate modules."""
from koei_editor.resources import read_json
from pathlib import Path
from functools import wraps
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from koei_editor.games.dw3.models import Change, fields
from koei_editor.games.dw3.save_parser import read_save, safe_path
import koei_editor.games.dw3.save_writer as save_writer
import koei_editor.games.dw3.bodyguard_editor as guard_editor
import koei_editor.games.dw3.bodyguard_growth as growth
import koei_editor.games.dw3.officer_weapon_editor as weapon_editor
import koei_editor.games.dw3.weapon_collection as weapon_collection
import koei_editor.games.dw3.progression_editor as progression
import koei_editor.games.dw3.bodyguard_customization as customization
import koei_editor.games.dw3.collection_editor as collections
import koei_editor.games.dw3.musou_slots as musou_slots

VERSION = '3.0'
DISCORD_USERNAME = 'mexicannn'
STEAM_PROFILE = 'https://steamcommunity.com/id/theonlyjuandeagingmexican/'
NAMES = read_json('officer_names.json')
METADATA = read_json('game_metadata.json')
ITEMS = {row['id']: row for row in METADATA['items']}
ITEM_ENUMS = {row['enum']: row for row in METADATA['items']}
WEAPONS = {row['id']: row for row in METADATA['weapons']}
WEAPON_ENUMS = {row['enum'].split('::')[-1]: row for row in METADATA['weapons'] if row.get('enum')}
CAPS = save_writer.CAPS
ITEM_CAPS = getattr(save_writer, 'ITEM_CAPS', {})
UNIQUE_WEAPONS = getattr(save_writer, 'UNIQUE_WEAPONS', {})
LABELS = {'SPoint': 'Merit', 'MaxHealth': 'Life / HP', 'MaxMusou': 'Musou', 'Attack': 'Attack', 'Defence': 'Defense'}
GUARD_ITEMS = guard_editor.GUARD_ITEMS
GUARD_WEAPONS = guard_editor.GUARD_WEAPONS
from koei_editor.shared.appearance import THEMES, Appearance, ui_font
import koei_editor.shared.preferences as preferences
from koei_editor.shared.experimental_limits import (
    experimental_limits, experimental_enabled, within_numeric_limits,
    EXPERIMENTAL_WARNING as SHARED_EXPERIMENTAL_WARNING,
)

INT32_MAX = save_writer.INT32_MAX
EXPERIMENTAL_WARNING = (
    SHARED_EXPERIMENTAL_WARNING.rsplit('\n\n', 1)[0] + '\n\n'
    'Numeric stats, Merit, normal item values, existing normal weapon bonuses, '
    'and Huanglong Elixirs use signed 32-bit storage: maximum 2,147,483,647. '
    'Supported maxima are shown beside each field. Max presets use supported maxima. '
    'Bodyguard growth table caps, equipment identities, ownership and dependencies still apply.'
)


def experimental_session(action):
    """Keep numeric policy inside this editor callback and its nested calls."""
    @wraps(action)
    def scoped(self, *args, **kwargs):
        mode = getattr(self, 'experimental_mode', None)
        with experimental_limits(enabled=bool(mode.get()) if mode is not None else False):
            return action(self, *args, **kwargs)
    return scoped


def weapon_bonus_label(item):
    """Name the weapon stat while retaining the underlying item ID."""
    if item['kind'] != 'normal':
        return item['name']
    effect = (item.get('effect') or item['name']).strip()
    return {'Max HP': 'Life', 'Max Musou': 'Musou',
            'Mounted Def.': 'Mounted Defense'}.get(effect, effect)


class Editor(Appearance):
    def __init__(self, root, parent=None, theme=None, on_theme=None,
                 preferences_path=None, persist_preferences=True):
        self.root = root
        self.on_theme = on_theme
        self.preferences_path = preferences_path
        self._persist_theme = parent is None and persist_preferences
        if theme is None:
            theme = preferences.load_theme(preferences_path) if parent is None else 'Light'
        host = parent if parent is not None else root
        embedded = parent is not None
        self.document = None
        self.experimental_mode = tk.BooleanVar(root, value=False)
        self.changes = {}
        self.history = []
        self.current_officer = self.current_item = self.current_bodyguard = 0
        self.current_guard_item = 0
        self.current_guard_weapon = next(iter(GUARD_WEAPONS))
        self.guard_weapon_slot = None
        self.guard_bonus_editable = False
        self.loading_guard_form = False
        self.loading_weapon_form = False
        self.current_weapon_data_id = None
        self.weapon_rows = {}
        self.backup = None
        self.buttons = []
        self.scroll_areas = []
        if not embedded:
            root.title(f'Dynasty Warriors 3 Remastered Save Editor — v{VERSION}')
            root.geometry('1140x870')
            root.minsize(1040, 740)
        self.style = ttk.Style(root)
        self.style.theme_use('clam')
        self.theme_name = tk.StringVar(root, value=theme)
        self.font_family = ui_font(root)
        root.option_add('*Font', (self.font_family, 10))
        self.apply_theme(theme)
        banner = tk.Frame(host, background='#202a37', padx=20, pady=12)
        banner.pack(fill='x')
        brand = tk.Frame(banner, background='#202a37')
        brand.pack(side='left')
        tk.Label(brand, text='DYNASTY WARRIORS 3', font=(self.font_family, 16, 'bold'),
                 background='#202a37', foreground='#e6c379').pack(anchor='w')
        tk.Label(brand, text='COMPLETE EDITION REMASTERED', font=(self.font_family, 9),
                 background='#202a37', foreground='#c4cddb').pack(anchor='w')
        credits = tk.Frame(banner, background='#202a37')
        credits.pack(side='right')
        tk.Label(credits, text=f'SAVE EDITOR  ·  v{VERSION}', font=(self.font_family, 10, 'bold'),
                 background='#202a37', foreground='#ffffff').pack(anchor='e')
        self.author_label = tk.Label(credits, text='Made by Mexican', font=(self.font_family, 10),
                                     background='#202a37', foreground='#d2d9e2')
        self.author_label.pack(anchor='e')
        appearance = ttk.Frame(credits, style='Header.TFrame')
        appearance.pack(anchor='e', pady=(8, 0))
        ttk.Label(appearance, text='Appearance', style='Header.TLabel').pack(side='left', padx=(0, 7))
        self.theme_selector = ttk.Combobox(appearance, textvariable=self.theme_name,
                                           values=tuple(THEMES), state='readonly', width=7)
        self.theme_selector.pack(side='left')
        self.theme_selector.bind('<<ComboboxSelected>>', lambda _event: self.apply_theme(self.theme_name.get()))
        outer = ttk.Frame(host, padding=15)
        outer.pack(fill='both', expand=True)
        bar = ttk.Frame(outer)
        bar.pack(fill='x')
        ttk.Button(bar, text='Open Save Copy', command=self.open, style='Primary.TButton').pack(side='left', padx=(0, 7))
        for text, command in [('Backup Save', self.make_backup), ('Save As…', self.save_as), ('Save Changes', self.save_changes), ('Restore Backup…', self.restore)]:
            button = ttk.Button(bar, text=text, command=command, style='Primary.TButton' if text == 'Save As…' else 'TButton')
            button.pack(side='left', padx=(0, 7))
            if text != 'Restore Backup…': self.buttons.append(button)
        locations_button = ttk.Button(bar, text='File Locations', command=self.show_file_locations)
        locations_button.pack(side='right')
        self.buttons.append(locations_button)
        ttk.Button(bar, text='Contact', command=self.show_contact).pack(side='right', padx=(0, 7))
        mode_bar = ttk.Frame(outer)
        mode_bar.pack(fill='x', pady=(8, 0))
        ttk.Checkbutton(mode_bar, text='Experimental: allow above supported maxima',
                        variable=self.experimental_mode, command=self.toggle_experimental).pack(side='left')
        self.experimental_note = tk.StringVar(value='Supported limits active. Max presets use supported maxima.')
        ttk.Label(mode_bar, textvariable=self.experimental_note, style='Muted.TLabel', wraplength=520).pack(side='right')
        self.filename = tk.StringVar(value='Open a copy of GameStatusData.sav to begin.')
        self.backup_label = tk.StringVar(value='An untouched backup is created automatically when a copy opens.')
        ttk.Label(outer, textvariable=self.filename, wraplength=990).pack(fill='x', pady=(12, 3))
        ttk.Label(outer, textvariable=self.backup_label, wraplength=990, style='Muted.TLabel').pack(fill='x', pady=(0, 10))
        self.compatibility_label = tk.StringVar()
        ttk.Label(outer, textvariable=self.compatibility_label, wraplength=990, style='Muted.TLabel').pack(fill='x')
        # Long forms scroll instead of enlarging the window's requested height.
        self.notebook = ttk.Notebook(outer, height=360)
        self.notebook.pack(fill='both', expand=True)
        self.tabs = {}
        for name in ('Dashboard', 'Officers', 'Items', 'Weapons', 'Bodyguards', 'Unlocks', 'Collections', 'Musou Saves'):
            tab = ttk.Frame(self.notebook, padding=12)
            self.notebook.add(tab, text=name)
            self.tabs[name] = tab
        self.build_dashboard()
        self.build_officers()
        self.build_items()
        self.build_weapons()
        self.build_bodyguards()
        self.build_unlocks()
        self.build_collections()
        self.build_musou_saves()
        self.bind_form_scrolling()
        bottom = ttk.Frame(outer)
        bottom.pack(side='bottom', fill='x', pady=(12, 0), before=self.notebook)
        self.status = tk.StringVar(value='No save open.')
        ttk.Label(bottom, textvariable=self.status, wraplength=560).pack(side='left')
        for text, command in [('Review Changes', self.review), ('Discard Changes', self.discard), ('Undo', self.undo)]:
            button = ttk.Button(bottom, text=text, command=command)
            button.pack(side='right', padx=(7, 0))
            self.buttons.append(button)
        self.set_loaded(False)
        for shortcut, command in (('<Control-o>', self.open), ('<Control-s>', self.save_changes),
                                  ('<Control-Shift-S>', self.save_as), ('<Control-z>', self.undo),
                                  ('<Control-r>', self.review)):
            def invoke(_event, action=command):
                action()
                return 'break'
            if not embedded:
                root.bind(shortcut, invoke)
        if not embedded:
            root.protocol('WM_DELETE_WINDOW', self.close)

    def toggle_experimental(self):
        if self.experimental_mode.get():
            if not messagebox.askyesno('Enable Experimental Editing', EXPERIMENTAL_WARNING):
                self.experimental_mode.set(False)
        elif self.document is not None and self.changes:
            try:
                with experimental_limits(enabled=False):
                    save_writer.plan_changes(self.document, list(self.changes.values()))
            except (ValueError, KeyError, TypeError, IndexError):
                self.experimental_mode.set(True)
                messagebox.showinfo('Experimental Changes Pending',
                                    'Undo, discard, or reduce the experimental values before disabling experimental editing.')
        enabled = self.experimental_mode.get()
        self.experimental_note.set('Experimental active: above-max values may break your save or game.' if enabled else
                                   'Supported limits active. Max presets use supported maxima.')
        self.refresh()
        if self.document is not None:
            self.select_item(); self.select_guard_item(); self.select_bodyguard(); self.select_weapon(); self.select_guard_weapon()

    def apply_theme(self, name):
        super().apply_theme(name)
        self.theme_dashboard(name)
        if self.on_theme is not None:
            self.on_theme(name)

    def theme_dashboard(self, name):
        view = getattr(self, 'dashboard_view', None)
        if view is not None:
            view.apply_theme(name)

    def build_dashboard(self):
        from koei_editor.shared.progression import ProgressionDashboard
        from koei_editor.shared.progression_view import ProgressionView
        self._dashboard_document = None
        self.dashboard_view = ProgressionView(
            self.tabs['Dashboard'], ProgressionDashboard(
                'Dynasty Warriors 3 Remastered', note='Open a copied save to explore verified progression.'),
            on_navigate=self.navigate_dashboard, theme=self.theme_name.get())
        self.dashboard_view.pack(fill='both', expand=True)

    def refresh_dashboard(self):
        from koei_editor.shared.progression import ProgressionDashboard
        if self.document is None:
            self.dashboard_view.set_dashboard(ProgressionDashboard(
                'Dynasty Warriors 3 Remastered', note='Open a copied save to explore verified progression.'))
            self._dashboard_document = None
            return
        if self.document is self._dashboard_document:
            return
        from koei_editor.games.dw3.progression_dashboard import dashboard
        try:
            data = dashboard(self.document)
        except Exception:
            data = ProgressionDashboard('Dynasty Warriors 3 Remastered',
                                        note='Dashboard unavailable for this layout. Existing editing forms remain available.')
        self.dashboard_view.set_dashboard(data)
        self._dashboard_document = self.document

    @experimental_session
    def navigate_dashboard(self, field_id):
        """Select the existing editing form without applying or clearing edits."""
        if self.document is None or not isinstance(field_id, str):
            return False
        try:
            category, index_text, field = field_id.split(':')
            index = int(index_text)
        except (ValueError, TypeError):
            return False
        if category == 'officer' and field in self.inputs and index in self.officer_indices():
            self.notebook.select(self.tabs['Officers'])
            self.current_officer = index
            self.officer_filter.set('')
            self.refresh_officers()
            self.officer_entries[field].focus_set()
        elif category == 'weapon' and field == 'Skills':
            if not any(row['data_id'] == index for row in weapon_editor.states(self.document, list(self.changes.values()))):
                return False
            self.notebook.select(self.tabs['Weapons'])
            self.weapon_filter.set('')
            self.refresh_weapons()
            key = next((key for key, row in self.weapon_rows.items() if row['data_id'] == index), None)
            if key is not None:
                self.weapons.selection_set(key)
                self.weapons.focus(key)
                self.weapons.see(key)
                self.select_weapon()
        elif category == 'item' and field == 'Value' and index in dict(self.item_rows()):
            self.notebook.select(self.tabs['Items'])
            self.current_item = index
            self.item_filter.set('')
            self.refresh_items()
            self.item_entry.focus_set()
        elif category == 'progression' and index == 0 and field == 'HuanglongElixirs':
            self.notebook.select(self.tabs['Unlocks'])
            self.elixir_entry.focus_set()
        elif category == 'story' and field == 'MusouCleared':
            name = next((name for name, identity in self.story_officer_choices.items() if identity == index), None)
            if name is None or index not in self.officer_indices():
                return False
            self.notebook.select(self.tabs['Unlocks'])
            self.story_officer.set(name)
            self.refresh_story_status()
            self.story_officer_box.focus_set()
        elif category == 'collection':
            key = f'{field}:{index}'
            if field not in ('music', 'movies') or not any(
                    row['id'] == index for row in collections.DATA[field]['rows']):
                return False
            self.notebook.select(self.tabs['Collections'])
            self.collection_filter.set('')
            self.refresh_collections()
            if not self.collection_tree.exists(key):
                return False
            self.collection_tree.selection_set(key)
            self.collection_tree.focus(key)
            self.collection_tree.see(key)
        else:
            return False
        return True

    @experimental_session
    def set_loaded(self, loaded):
        if not loaded:
            from koei_editor.shared.progression import ProgressionDashboard
            self.dashboard_view.set_dashboard(ProgressionDashboard(
                'Dynasty Warriors 3 Remastered', note='Open a copied save to explore verified progression.'))
            self._dashboard_document = None
        elif self.document is not None:
            self.refresh_dashboard()
        for button in self.buttons: button.configure(state='normal' if loaded else 'disabled')
        self.max_items_button.configure(state='normal' if loaded and ITEM_CAPS else 'disabled')
        self.guard_bonus_button.configure(state='normal' if loaded and self.guard_weapon_slot is not None and self.guard_bonus_editable else 'disabled')
        if not loaded:
            self.clear_weapon_form()
            self.elixir_input.set('')
            self.elixir_note.set('Open a save copy to view your Elixirs.')
            self.elixir_entry.configure(state='disabled')
        else:
            selected = self.weapons.selection()
            row = self.weapon_rows.get(selected[0]) if selected else None
            self.weapon_roll_button.configure(state='normal' if row and row['editable'] else 'disabled')
            self.weapon_max_button.configure(state='normal' if row and row['editable'] else 'disabled')
            if row:self.select_weapon()
            else:self.clear_weapon_form()
            self.refresh_elixirs()
            self.refresh_collections()
            self.refresh_musou_saves()

    def action(self, frame, text, command):
        button = ttk.Button(frame, text=text, command=command)
        button.pack(fill='x', pady=4)
        self.buttons.append(button)
        return button

    def make_tree(self, frame, columns, title, widths):
        tree = ttk.Treeview(frame, columns=tuple(name for name, _ in columns), selectmode='browse', height=6)
        tree.heading('#0', text=title)
        tree.column('#0', width=widths[0], minwidth=120)
        for (name, title), width in zip(columns, widths[1:]):
            tree.heading(name, text=title)
            tree.column(name, width=width, minwidth=50, anchor='center')
        scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        return tree

    def add_search(self, frame, variable, callback):
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 9))
        ttk.Label(bar, text='Find:').pack(side='left', padx=(0, 7))
        ttk.Entry(bar, textvariable=variable).pack(side='left', fill='x', expand=True)
        variable.trace_add('write', lambda *_: callback())

    def panels(self, tab):
        left = ttk.Frame(tab)
        left.pack(side='left', fill='both', expand=True)
        shell = ttk.Frame(tab, padding=(18, 0, 0, 0))
        shell.pack(side='right', fill='y')
        right = self.scroll_content(shell)
        return left, right

    def scroll_content(self, parent, width=220):
        """Keep long forms reachable when the window is short or text scales."""
        shell = ttk.Frame(parent)
        shell.pack(fill='both', expand=True)
        canvas = tk.Canvas(shell, width=width, height=200, highlightthickness=0,
                           background=THEMES[self.theme_name.get()]['background'])
        scroll = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        content = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=content, anchor='nw')
        def resized(_event=None):
            canvas.configure(scrollregion=canvas.bbox('all'), width=max(width, content.winfo_reqwidth()))
        content.bind('<Configure>', resized)
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=max(event.width, content.winfo_reqwidth())))
        self.scroll_areas.append((canvas, content))
        return content

    def bind_form_scrolling(self):
        for canvas, content in self.scroll_areas:
            def wheel(event, area=canvas):
                if area.yview() == (0.0, 1.0): return
                units = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
                area.yview_scroll(units, 'units')
                return 'break'
            def focus(event, area=canvas, body=content):
                height = max(body.winfo_height(), 1)
                top = area.canvasy(0)
                y = event.widget.winfo_rooty() - body.winfo_rooty()
                bottom = y + event.widget.winfo_height()
                if y < top: area.yview_moveto(y / height)
                elif bottom > top + area.winfo_height():
                    area.yview_moveto((bottom - area.winfo_height()) / height)
            stack = [content, canvas]
            while stack:
                widget = stack.pop()
                stack.extend(widget.winfo_children())
                if isinstance(widget, (ttk.Combobox, ttk.Spinbox, ttk.Treeview)): continue
                widget.bind('<MouseWheel>', wheel, add='+')
                widget.bind('<FocusIn>', focus, add='+')

    def build_officers(self):
        left, right = self.panels(self.tabs['Officers'])
        self.officer_filter = tk.StringVar()
        self.add_search(left, self.officer_filter, self.refresh_officers)
        self.officers = self.make_tree(left, [('merit', 'Merit'), ('hp', 'HP'), ('musou', 'Musou'), ('attack', 'Attack'), ('defense', 'Defense')], 'Officer', [155, 80, 65, 65, 65, 65])
        self.officers.bind('<<TreeviewSelect>>', self.select_officer)
        self.selected = tk.StringVar(value='Select an officer')
        ttk.Label(right, textvariable=self.selected, font=(self.font_family, 11, 'bold')).pack(anchor='w', pady=(0, 12))
        self.inputs = {}
        self.officer_entries = {}
        for field, label in LABELS.items():
            cap = CAPS.get(field)
            ttk.Label(right, text=f'{label} (supported max {cap:,})' if cap is not None else f'{label} (view only)').pack(anchor='w')
            variable = tk.StringVar()
            self.inputs[field] = variable
            entry = ttk.Entry(right, textvariable=variable, width=24, state='normal' if cap is not None else 'readonly')
            entry.pack(anchor='w', pady=(3, 8))
            self.officer_entries[field] = entry
        for text, command in [('Apply Officer Changes', self.apply_officer), ('Max Selected Officer', self.max_selected), ('Max All Officers', self.max_all), ('99,999 Merit for All', self.merit_all)]: self.action(right, text, command)
        ttk.Label(right, text='Experimental storage maximum: 2,147,483,647.', wraplength=220).pack(anchor='w', pady=6)
        ttk.Label(right, text='Apply your entries before selecting another officer.\n\nChanges stay in the editor until you save. Story completion is separate.', wraplength=200).pack(anchor='w', pady=10)

    def build_items(self):
        left, right = self.panels(self.tabs['Items'])
        self.item_filter = tk.StringVar()
        self.add_search(left, self.item_filter, self.refresh_items)
        self.items = self.make_tree(left, [('kind', 'Type'), ('value', 'Value'), ('owned', 'Owned')], 'Item', [245, 90, 80, 70])
        self.items.bind('<<TreeviewSelect>>', self.select_item)
        self.item_selected = tk.StringVar(value='Select an item')
        self.item_detail = tk.StringVar()
        self.item_owned = tk.BooleanVar()
        self.item_value = tk.StringVar()
        ttk.Label(right, textvariable=self.item_selected, font=(self.font_family, 11, 'bold'), wraplength=220).pack(anchor='w', pady=(0, 12))
        ttk.Label(right, textvariable=self.item_detail, wraplength=220).pack(anchor='w', pady=(0, 12))
        ttk.Checkbutton(right, text='Owned', variable=self.item_owned).pack(anchor='w', pady=6)
        ttk.Label(right, text='Normal item value').pack(anchor='w', pady=(10, 3))
        self.item_entry = ttk.Entry(right, textvariable=self.item_value, width=24, state='disabled')
        self.item_entry.pack(anchor='w', pady=(0, 10))
        self.action(right, 'Apply Item Changes', self.apply_item)
        self.max_items_button = self.action(right, 'Max All Normal Items', self.max_items)
        self.action(right, 'Unlock All Rare Items', lambda: self.unlock_items('rare'))
        self.action(right, 'Unlock All Items', lambda: self.unlock_items())
        ttk.Label(right, text='New values use verified normal drop limits. Max actions preserve existing higher values.', wraplength=220).pack(anchor='w', pady=12)

    def build_weapons(self):
        tab = self.tabs['Weapons']
        ttk.Label(tab, text='Edit owned weapon bonuses and elements using verified transfer rules. Base attack, hit count and equipped references are preserved. Save to write your applied changes.', wraplength=950).pack(anchor='w', pady=(0, 9))
        actions = ttk.Frame(tab); actions.pack(fill='x', pady=(0, 10))
        for text, command in [('Unlock Selected Unique Weapon', self.unlock_selected_weapon), ('Unlock All Supported Unique Weapons', self.unlock_weapons)]:
            button = ttk.Button(actions, text=text, command=command); button.pack(side='left', padx=(0, 8)); self.buttons.append(button)
        button = ttk.Button(actions, text='Max All Owned Bonus Rolls', command=self.max_all_weapon_rolls)
        button.pack(side='left', padx=(0, 8)); self.buttons.append(button)
        extras=ttk.Frame(tab);extras.pack(fill='x')
        for text,command in [('Complete Weapon Collection',self.collect_all_weapons),('Unlock Tactics Costumes',self.unlock_tactics_costumes)]:
            button=ttk.Button(extras,text=text,command=command);button.pack(side='left',padx=(0,8));self.buttons.append(button)
        ttk.Label(tab, text='Unique unlocks include Ziluan and use stock properties. Collection fills the weapon gallery; regular owned copies stay unchanged. Tactics unlocks Lu Bu and Sun Shangxiang’s costumes separately from DLC.', wraplength=1000).pack(anchor='w', pady=(6, 8))
        left, right = self.panels(tab)
        self.weapon_filter = tk.StringVar()
        self.add_search(left, self.weapon_filter, self.refresh_weapons)
        self.weapons = self.make_tree(left, [('kind', 'Inventory'), ('data', 'Copy / Owned'), ('power', 'Base attack')], 'Weapon', [230, 105, 95, 75])
        self.weapons.bind('<<TreeviewSelect>>', self.select_weapon)
        self.weapon_selected = tk.StringVar(value='Select a weapon')
        self.weapon_detail = tk.StringVar(value='Select a weapon to see its bonuses.')
        ttk.Label(right, textvariable=self.weapon_selected, font=(self.font_family, 11, 'bold'), wraplength=370).pack(anchor='w', pady=(0, 6))
        ttk.Label(right, textvariable=self.weapon_detail, wraplength=370).pack(anchor='w', pady=(0, 8))
        element_form=ttk.Frame(right);element_form.pack(fill='x',pady=(0,8))
        ttk.Label(element_form,text='Element:').pack(side='left',padx=(0,6))
        self.weapon_element=tk.StringVar(value='None')
        self.weapon_element_choices={}
        self.weapon_element_box=ttk.Combobox(element_form,textvariable=self.weapon_element,width=13,state='disabled')
        self.weapon_element_box.pack(side='left',padx=(0,8))
        self.weapon_element_button=ttk.Button(element_form,text='Apply Element',command=self.apply_weapon_element)
        self.weapon_element_button.pack(side='left');self.buttons.append(self.weapon_element_button)
        self.weapon_element_visible_button=self.action(right,'Apply Element to Visible Owned Copies',self.apply_visible_weapon_elements)
        ttk.Label(right, text='Uses the Find filter to select owned copies. View-only copies are preserved.', wraplength=370).pack(anchor='w', pady=(0, 7))
        bulk_element_form = ttk.Frame(right)
        bulk_element_form.pack(fill='x')
        ttk.Label(bulk_element_form, text='All owned unique weapons:').pack(side='left', padx=(0, 6))
        self.unique_weapon_element = tk.StringVar(value='Lightning')
        self.unique_element_choices = {label: mask for label, mask in weapon_editor.ELEMENTS.items() if mask}
        self.unique_weapon_element_box = ttk.Combobox(bulk_element_form, textvariable=self.unique_weapon_element,
                                                     values=tuple(self.unique_element_choices), state='readonly', width=12)
        self.unique_weapon_element_box.pack(side='left')
        self.weapon_element_all_button=self.action(right,'Apply Element to All Owned Unique Weapons',self.apply_unique_weapon_elements)
        form = ttk.Frame(right); form.pack(fill='x')
        ttk.Label(form, text='Bonus').grid(row=0, column=1, sticky='w', pady=(0, 4))
        ttk.Label(form, text='Value').grid(row=0, column=2, sticky='w', pady=(0, 4))
        self.weapon_bonus_names, self.weapon_bonus_values = [], []
        self.weapon_bonus_boxes, self.weapon_bonus_value_boxes = [], []
        self.weapon_bonus_choices = {'None':None}
        self.weapon_bonus_choices.update({weapon_bonus_label(row):index for index,row in ITEMS.items() if row['kind']=='normal'})
        self.weapon_bonus_choices.update({ITEMS[index]['name']:index for index in weapon_editor.RARE_ITEMS})
        for index in range(9):
            name, value = tk.StringVar(value='None'), tk.StringVar()
            self.weapon_bonus_names.append(name); self.weapon_bonus_values.append(value)
            ttk.Label(form, text=str(index+1)).grid(row=index+1, column=0, padx=(0, 7))
            box = ttk.Combobox(form, textvariable=name, width=27, state='disabled', values=tuple(self.weapon_bonus_choices))
            box.grid(row=index+1, column=1, sticky='w', padx=(0, 8), pady=3)
            valuebox = ttk.Combobox(form, textvariable=value, width=7, state='disabled')
            valuebox.grid(row=index+1, column=2, sticky='w', pady=3)
            self.weapon_bonus_boxes.append(box); self.weapon_bonus_value_boxes.append(valuebox)
            box.bind('<<ComboboxSelected>>', lambda _event, slot=index: self.change_weapon_bonus(slot))
        self.weapon_roll_button = self.action(right, 'Apply Weapon Bonuses', self.apply_weapon_rolls)
        self.weapon_max_button = self.action(right, 'Max Selected Existing Bonus Rolls', self.max_selected_weapon_rolls)
        ttk.Label(right, text='Copy bonuses from an owned copy:', wraplength=370).pack(anchor='w', pady=(10, 4))
        self.weapon_bonus_source = tk.StringVar()
        self.weapon_bonus_sources = {}
        self.weapon_bonus_source_box = ttk.Combobox(right, textvariable=self.weapon_bonus_source,
                                                   state='disabled', width=44)
        self.weapon_bonus_source_box.pack(fill='x')
        self.weapon_copy_button = self.action(right, 'Copy Bonuses to Selected Weapon', self.copy_weapon_bonuses)
        ttk.Label(right, text='Copies applied bonuses only. The destination must support every copied value and bonus count. Review Changes shows the complete layout before saving.', wraplength=370).pack(anchor='w', pady=7)
        ttk.Label(right, text='Max raises existing normal rolls. One rare bonus is allowed, with no numeric value. Replace existing rare bonuses or elements; removing them is unsupported.', wraplength=370).pack(anchor='w', pady=7)
        ttk.Label(right, text='Dropdown values show supported rolls. Experimental maximum: 2,147,483,647 for an existing normal bonus in its saved slot.', wraplength=370).pack(anchor='w', pady=7)

    def build_bodyguards(self):
        tab = self.tabs['Bodyguards']
        ttk.Label(tab, text='Growth is shared by each team. Bodyguard items and weapons use their own inventory; equipment choices apply to the selected team.', wraplength=930).pack(fill='x', pady=(0, 10))
        left = ttk.Frame(tab, width=225); left.pack(side='left', fill='y'); left.pack_propagate(False)
        right = ttk.Frame(tab, padding=(15, 0, 0, 0)); right.pack(side='left', fill='both', expand=True)
        self.bodyguards = self.make_tree(left, [('merit', 'Merit')], 'Team', [125, 85])
        self.bodyguards.bind('<<TreeviewSelect>>', self.select_bodyguard)
        self.bodyguard_selected = tk.StringVar(value='Select a bodyguard team')
        self.bodyguard_merit = tk.StringVar()
        self.bodyguard_limit = tk.StringVar(value='Merit (supported 0–99,999; experimental max 2,147,483,647)')
        ttk.Label(right, textvariable=self.bodyguard_selected, font=(self.font_family, 11, 'bold')).pack(anchor='w', pady=(0, 8))
        self.guard_tabs = ttk.Notebook(right); self.guard_tabs.pack(fill='both', expand=True)
        pages = {}
        for name in ('Growth', 'Team Equipment', 'BG Items', 'BG Weapons', 'Appearance Unlocks'):
            page = ttk.Frame(self.guard_tabs, padding=10); self.guard_tabs.add(page, text=name); pages[name] = page
        page = self.scroll_content(pages['Growth'], width=640)
        form = ttk.Frame(page); form.pack(fill='x')
        ttk.Label(form, textvariable=self.bodyguard_limit, wraplength=320).grid(row=0, column=0, sticky='w', pady=4)
        ttk.Entry(form, textvariable=self.bodyguard_merit, width=14).grid(row=0, column=1, sticky='w', padx=12, pady=4)
        self.guard_growth_inputs = {}
        self.guard_growth_boxes = {}
        ttk.Label(page, text='Growth levels retain their table caps and shared points budget in experimental mode.', wraplength=600).pack(anchor='w', pady=(5, 0))
        for rownum, index in enumerate(growth.ALLOCATED_SLOTS, 1):
            variable = tk.StringVar(); self.guard_growth_inputs[index] = variable
            ttk.Label(form, text=f'{growth.LEVEL_NAMES[index]} growth (0–{growth.LEVEL_CAPS[index]})').grid(row=rownum, column=0, sticky='w', pady=4)
            box=ttk.Spinbox(form, textvariable=variable, from_=0, to=growth.LEVEL_CAPS[index], width=12)
            box.grid(row=rownum, column=1, sticky='w', padx=12, pady=4)
            self.guard_growth_boxes[index]=box
            variable.trace_add('write', lambda *_: self.preview_growth())
        self.bodyguard_merit.trace_add('write', lambda *_: self.preview_growth())
        self.guard_budget = tk.StringVar(); self.guard_automatic = tk.StringVar(); self.guard_stats = tk.StringVar()
        ttk.Label(page, textvariable=self.guard_budget, font=(self.font_family, 10, 'bold'), wraplength=640).pack(anchor='w', pady=(10, 4))
        ttk.Label(page, textvariable=self.guard_automatic, wraplength=640).pack(anchor='w', pady=4)
        ttk.Label(page, textvariable=self.guard_stats, wraplength=640).pack(anchor='w', pady=4)
        self.action(page, 'Apply Team Growth', self.apply_bodyguard)
        presetbar = ttk.Frame(page); presetbar.pack(fill='x', pady=(5, 0))
        for mode, label in growth.PRESET_NAMES.items():
            button = ttk.Button(presetbar, text=f'Max: {label}', command=lambda mode=mode: self.max_bodyguard(mode)); button.pack(side='left', padx=(0, 5)); self.buttons.append(button)
        self.action(page, 'Max All Teams — Balanced Growth', self.max_bodyguards)
        ttk.Label(page, text='Life, Attack, Defense and Bow / Moveset share at most 25 points. Count and AI advance automatically with Merit. The preview shows growth base stats before equipment and battle modifiers.', wraplength=640).pack(anchor='w', pady=9)
        self.build_guard_equipment(self.scroll_content(pages['Team Equipment'], width=640))
        self.build_guard_items(pages['BG Items'])
        self.build_guard_weapons(self.scroll_content(pages['BG Weapons'], width=640))
        self.build_guard_customization(pages['Appearance Unlocks'])

    def build_guard_customization(self, page):
        ttk.Label(page,text='Bodyguard appearance and color availability',font=(self.font_family,11,'bold')).pack(anchor='w',pady=(0,8))
        footer=ttk.Frame(page);footer.pack(side='bottom',fill='x',pady=(8,0))
        bar=ttk.Frame(footer);bar.pack(fill='x',pady=(0,6))
        for text,command in (('Unlock Selected',self.unlock_selected_guard_customization),('Unlock All Bodyguard Options',self.unlock_guard_customization)):
            button=ttk.Button(bar,text=text,command=command);button.pack(side='left',padx=(0,8));self.buttons.append(button)
        self.yellow_uniform_button=ttk.Button(bar,text='Unlock Yellow Uniform',command=self.unlock_yellow_uniform)
        self.yellow_uniform_button.pack(side='left',padx=(0,8));self.buttons.append(self.yellow_uniform_button)
        self.guard_customization_note=tk.StringVar(value='Open a save copy to view appearance unlocks.')
        ttk.Label(footer,textvariable=self.guard_customization_note,wraplength=640).pack(anchor='w')
        table=ttk.Frame(page);table.pack(fill='both',expand=True)
        self.guard_customization_tree=self.make_tree(table,[('kind','Type'),('owned','Available')],'Option',[250,120,100])

    def refresh_guard_customization(self):
        if self.document is None:return
        selected=self.guard_customization_tree.selection()
        self.guard_customization_tree.delete(*self.guard_customization_tree.get_children())
        state=customization.customization_state(self.document,list(self.changes.values()))
        for family,kind in (('appearances','Appearance'),('outfits','Color')):
            for row in state[family]:
                available='Default' if row['available_by_default'] else 'Yes' if row['unlocked'] else 'No' if row['unlocked'] is False else 'View only'
                self.guard_customization_tree.insert('', 'end',iid=f'{family}:{row["id"]}',text=row['name'],values=(kind,available))
        if selected and self.guard_customization_tree.exists(selected[0]):self.guard_customization_tree.selection_set(selected[0])
        yellow=next(row for row in state['outfits'] if row['id']==5)
        self.yellow_uniform_button.configure(state='normal' if yellow['editable'] else 'disabled')
        self.guard_customization_note.set(state['reason'] or 'The Yellow uniform is in the Color list. Unlocks both Nanman models and yellow, white, black and pink colors. Equipped appearances, team growth and story completion are preserved.')

    def guard_customization_changes(self):
        state=customization.customization_state(self.document)
        supported={(field,row['id']) for field,family in (('AppearanceUnlocked','appearances'),('OutfitUnlocked','outfits')) for row in state[family] if row['editable']}
        return [change for change in customization.customization_unlock_changes() if (change.field,change.index) in supported]

    def unlock_guard_customization(self):
        if self.require_save():self.stage_many(self.guard_customization_changes())

    def unlock_yellow_uniform(self):
        if not self.require_save():return
        row=next(row for row in customization.customization_state(self.document)['outfits'] if row['id']==5)
        if not row['editable']:
            messagebox.showerror('Cannot Unlock Yellow Uniform',row['reason']);return
        self.stage_many(customization.customization_unlock_changes('outfit',5))

    def unlock_selected_guard_customization(self):
        if not self.selected_ok(self.guard_customization_tree):return
        family,identity=self.guard_customization_tree.selection()[0].split(':');identity=int(identity)
        state=customization.customization_state(self.document,list(self.changes.values()))
        row=next(row for row in state[family] if row['id']==identity)
        if row['available_by_default']:
            messagebox.showinfo('Already Available','This choice is available by default.');return
        if not row['editable']:
            messagebox.showerror('Cannot Unlock Option',row['reason']);return
        self.stage_many(customization.customization_unlock_changes('appearance' if family=='appearances' else 'outfit',identity))

    def build_guard_equipment(self, page):
        ttk.Label(page, text='Choose one owned bodyguard item and a weapon for each family. Only equipment already owned or applied in this editor is available.', wraplength=640).pack(anchor='w', pady=(0, 10))
        form = ttk.Frame(page); form.pack(fill='x')
        self.guard_equip_item = tk.StringVar(); self.guard_equip_weapons = {}
        self.guard_equip_item_choices = {}; self.guard_equip_weapon_choices = {}
        ttk.Label(form, text='Bodyguard item').grid(row=0, column=0, sticky='w', pady=6)
        self.guard_equip_item_box = ttk.Combobox(form, textvariable=self.guard_equip_item, state='readonly', width=44)
        self.guard_equip_item_box.grid(row=0, column=1, sticky='ew', padx=10, pady=6)
        self.guard_equip_weapon_boxes = {}
        for index, family in enumerate(guard_editor.FAMILY_NAMES):
            variable = tk.StringVar(); self.guard_equip_weapons[index] = variable
            ttk.Label(form, text=family).grid(row=index+1, column=0, sticky='w', pady=6)
            box = ttk.Combobox(form, textvariable=variable, state='readonly', width=44); box.grid(row=index+1, column=1, sticky='ew', padx=10, pady=6)
            self.guard_equip_weapon_boxes[index] = box
        form.columnconfigure(1, weight=1)
        self.action(page, 'Apply Team Equipment', self.apply_guard_equipment)
        self.action(page, 'Equip Best Owned Weapons for This Team', self.equip_best_guard_weapons)
        ttk.Label(page, text='Equip Best selects the highest available weapon tier and bonuses. Item selection is preserved. Bodyguard weapon family selection in battle remains an officer setting.', wraplength=640).pack(anchor='w', pady=12)

    def build_guard_items(self, page):
        left, right = self.panels(page)
        self.guard_items = self.make_tree(left, [('value','Value'),('owned','Owned')], 'Bodyguard item', [185, 65, 60])
        self.guard_items.bind('<<TreeviewSelect>>', self.select_guard_item)
        self.guard_item_selected = tk.StringVar(value='Select an item'); self.guard_item_detail = tk.StringVar()
        self.guard_item_owned = tk.BooleanVar(); self.guard_item_value = tk.StringVar()
        ttk.Label(right, textvariable=self.guard_item_selected, font=(self.font_family,10,'bold'), wraplength=205).pack(anchor='w', pady=(0,8))
        ttk.Label(right, textvariable=self.guard_item_detail, wraplength=205).pack(anchor='w', pady=(0,8))
        ttk.Checkbutton(right, text='Owned', variable=self.guard_item_owned).pack(anchor='w', pady=5)
        self.guard_item_entry = ttk.Entry(right, textvariable=self.guard_item_value, width=20); self.guard_item_entry.pack(anchor='w', pady=8)
        self.action(right, 'Apply BG Item Changes', self.apply_guard_item)
        self.action(right, 'Unlock All BG Items', self.unlock_guard_items)
        self.action(right, 'Max All BG Items', self.max_guard_items)
        ttk.Label(right, text='Bodyguard item limits differ from officer items. An equipped item must remain owned.', wraplength=205).pack(anchor='w', pady=10)

    def build_guard_weapons(self, page):
        ttk.Label(page,text='Max applies Life, Defense and Attack bonuses (Bow Attack for bows and crossbows) to all owned copies of the selected weapon. Equipped choices stay as they are.',wraplength=640).pack(fill='x',pady=(0,7))
        actions = ttk.Frame(page); actions.pack(fill='x', pady=(0,8))
        for label, command in [('Unlock Selected', self.unlock_guard_weapon), ('Max Selected Copies', self.max_guard_weapon), ('Unlock All', self.unlock_guard_weapons), ('Max All Bonuses', self.max_guard_weapons)]:
            button = ttk.Button(actions, text=label, command=command); button.pack(side='left', padx=(0,5)); self.buttons.append(button)
        self.guard_weapon_detail = tk.StringVar(value='Select a weapon or an owned copy to see its bonuses.')
        ttk.Label(page, textvariable=self.guard_weapon_detail, wraplength=640).pack(side='bottom', fill='x', pady=(8,0))
        bonuspanel = ttk.LabelFrame(page,text='Bonuses on the selected owned copy',padding=7); bonuspanel.pack(side='bottom',fill='x',pady=(8,0))
        self.guard_bonus_items = []; self.guard_bonus_values = []; self.guard_bonus_boxes = []; self.guard_bonus_value_boxes = []
        self.guard_bonus_choices = {'None':None}
        for index in range(3):
            itemvar = tk.StringVar(value='None'); valuevar = tk.StringVar()
            box = ttk.Combobox(bonuspanel,textvariable=itemvar,state='readonly',width=31)
            box.grid(row=index,column=0,sticky='ew',pady=2,padx=(0,8))
            valuebox = ttk.Combobox(bonuspanel,textvariable=valuevar,state='readonly',width=10)
            valuebox.grid(row=index,column=1,sticky='w',pady=2)
            itemvar.trace_add('write',lambda *_, index=index: self.guard_bonus_item_changed(index))
            self.guard_bonus_items.append(itemvar); self.guard_bonus_values.append(valuevar)
            self.guard_bonus_boxes.append(box); self.guard_bonus_value_boxes.append(valuebox)
        self.guard_bonus_button = ttk.Button(bonuspanel,text='Apply Copy Bonuses',command=self.apply_guard_bonuses,state='disabled')
        self.guard_bonus_button.grid(row=0,column=2,rowspan=3,padx=(10,0)); self.buttons.append(self.guard_bonus_button)
        ttk.Label(bonuspanel,text='Dropdown values show supported rolls for this tier. Experimental maximum: 2,147,483,647 for an existing normal bonus in its saved slot.',wraplength=600).grid(row=3,column=0,columnspan=3,sticky='w',pady=(4,0))
        self.guard_weapons = self.make_tree(page, [('tier','Tier'),('owned','Owned copies'),('power','Base attack')], 'Bodyguard weapon', [300,55,85,85])
        self.guard_weapons.bind('<<TreeviewSelect>>', self.select_guard_weapon)

    def build_unlocks(self):
        tab = self.tabs['Unlocks']
        tab.columnconfigure(0,weight=1,uniform='unlock');tab.columnconfigure(1,weight=1,uniform='unlock')
        tab.rowconfigure(0,weight=1)
        left=ttk.Frame(tab,padding=(0,0,18,0));left.grid(row=0,column=0,sticky='nsew')
        right=ttk.Frame(tab,padding=(18,0,0,0));right.grid(row=0,column=1,sticky='nsew')
        left=self.scroll_content(left,width=440);right=self.scroll_content(right,width=440)
        ttk.Label(left,text='Content availability',font=(self.font_family,11,'bold')).pack(anchor='w',pady=(0,10))
        self.action(left, 'Unlock All Playable Officers', lambda: self.unlock('CanUseCharaArray', 42))
        self.action(left, 'Unlock All 108 Playable Stages', lambda: self.unlock('CanUseScenarioArray', 108))
        self.action(left,'Unlock All Side Stories',self.unlock_side_stories)
        ttk.Label(left,text='Side stories unlock the three rulers’ side campaigns and their Free Mode variants. They are not marked completed.',wraplength=440).pack(anchor='w',pady=8)
        ttk.Separator(left).pack(fill='x',pady=10)
        ttk.Label(left,text='Musou completion — separate action',font=(self.font_family,10,'bold')).pack(anchor='w')
        self.story_officer_choices={NAMES.get(str(i),f'Officer {i}'):i for i,row in progression.ROUTES.items() if row['route_length']}
        self.story_officer=tk.StringVar(value=next(iter(self.story_officer_choices)))
        self.story_officer_box=ttk.Combobox(left,textvariable=self.story_officer,values=tuple(self.story_officer_choices),state='readonly')
        self.story_officer_box.pack(fill='x',pady=8)
        self.story_status=tk.StringVar()
        self.story_officer_box.bind('<<ComboboxSelected>>',lambda *_:self.refresh_story_status())
        ttk.Label(left,textvariable=self.story_status,wraplength=440).pack(anchor='w')
        self.action(left,'Mark Selected Musou Cleared',self.complete_selected_musou)
        self.action(left,'Mark All Supported Musou Cleared',self.complete_all_musou)
        ttk.Label(left,text='Sets clear flags and route progress. Awards 3 Huanglong Elixirs per first clear, capped at 999. Existing saved runs and battle records are preserved.',wraplength=440).pack(anchor='w',pady=8)
        ttk.Label(right,text='Grind presets',font=(self.font_family,11,'bold')).pack(anchor='w',pady=(0,10))
        self.action(right, 'Remove The Grind', self.remove_grind)
        ttk.Label(right, text='Max permanent officer stats and Merit, normal item rolls, rare items, all unique weapons and supported bodyguard growth/equipment inventories. Equipped choices and story completion are preserved.', wraplength=440).pack(anchor='w', pady=8)
        self.action(right, 'Unlock Everything Supported', self.unlock_everything)
        ttk.Label(right, text='Adds officers, stages, side stories, bodyguard appearance options, the weapon collection, Tactics costumes and music/movie galleries. Story completion and saved runs have separate controls.', wraplength=440).pack(anchor='w', pady=8)
        ttk.Separator(right).pack(fill='x', pady=12)
        ttk.Label(right, text='Huanglong Elixirs', font=(self.font_family, 11, 'bold')).pack(anchor='w')
        ttk.Label(right, text=f'Supported balance: 0–{progression.ELIXIR_MAX}. Experimental storage maximum: {INT32_MAX:,}.', wraplength=440).pack(anchor='w', pady=(5, 7))
        self.elixir_input = tk.StringVar()
        self.elixir_entry = ttk.Entry(right, textvariable=self.elixir_input, width=16)
        self.elixir_entry.pack(anchor='w', fill='x')
        self.elixir_entry.bind('<Return>', lambda *_: self.apply_elixirs())
        self.elixir_apply_button = self.action(right, 'Apply Elixir Count', self.apply_elixirs)
        self.elixir_max_button = self.action(right, 'Max Huanglong Elixirs', self.max_elixirs)
        self.elixir_note = tk.StringVar(value='Open a save copy to view your Elixirs.')
        ttk.Label(right, textvariable=self.elixir_note, wraplength=440).pack(anchor='w', pady=(5, 0))
        ttk.Label(right, text='An applied count includes any pending Musou clear rewards.', wraplength=440).pack(anchor='w', pady=5)
        ttk.Label(right,text='Changes remain pending until you save. Review Changes shows each action. Opening a copy creates a backup automatically.',wraplength=440).pack(anchor='w',pady=12)

    def build_collections(self):
        page = self.tabs['Collections']
        ttk.Label(page, text='Music & movie galleries', style='Section.TLabel').pack(anchor='w', pady=(0, 5))
        ttk.Label(page, text='Unlock the in-game collection entries. Your sound settings, story progress and saved campaigns stay as they are.',
                  wraplength=960, style='Muted.TLabel').pack(anchor='w', pady=(0, 12))
        actions = ttk.Frame(page)
        actions.pack(fill='x', pady=(0, 10))
        self.music_unlock_button = ttk.Button(actions, text='Unlock All Music', command=self.unlock_music)
        self.music_unlock_button.pack(side='left', padx=(0, 8))
        self.movie_unlock_button = ttk.Button(actions, text='Unlock All Movies', command=self.unlock_movies)
        self.movie_unlock_button.pack(side='left')
        self.collection_selected_button = ttk.Button(actions, text='Unlock Selected Entries', command=self.unlock_selected_collections)
        self.collection_selected_button.pack(side='left', padx=(8, 0))
        self.buttons.extend((self.music_unlock_button, self.movie_unlock_button, self.collection_selected_button))
        self.gallery_note = tk.StringVar(value='Open a save copy to view your collections.')
        ttk.Label(page, textvariable=self.gallery_note, wraplength=960).pack(anchor='w', pady=(0, 10))
        self.collection_filter = tk.StringVar()
        self.add_search(page, self.collection_filter, self.refresh_collections)
        self.collection_tree = self.make_tree(page, [('kind', 'Gallery'), ('id', 'Entry ID'), ('owned', 'Unlocked')],
                                              'Collection entry', [520, 130, 90, 100])
        self.collection_tree.configure(selectmode='extended')
        self.collection_tree.bind('<<TreeviewSelect>>', lambda *_: self.select_collection_entries())

    def build_musou_saves(self):
        page=self.tabs['Musou Saves']
        ttk.Label(page,text='Between-stage Musou campaign saves',font=(self.font_family,11,'bold')).pack(anchor='w',pady=(0,6))
        ttk.Label(page,text='Remove a saved run to free a campaign slot. This does not reset officer stats, unlocks or Musou completion. Changes apply to your opened copy only when you save.',wraplength=960).pack(anchor='w',pady=(0,12))
        self.musou_saves_tree=self.make_tree(page,[('officer','Officer'),('stage','Saved progress'),('date','Saved at')],'Slot',[150,210,200,250])
        self.musou_saves_tree.bind('<<TreeviewSelect>>',lambda *_:self.select_musou_save())
        bar=ttk.Frame(page);bar.pack(fill='x',pady=10)
        self.remove_musou_button=ttk.Button(bar,text='Remove Selected Run',command=self.remove_musou_save)
        self.remove_musou_button.pack(side='left',padx=(0,8));self.buttons.append(self.remove_musou_button)
        self.remove_all_musou_button=ttk.Button(bar,text='Remove All Saved Runs',command=self.remove_all_musou_saves)
        self.remove_all_musou_button.pack(side='left');self.buttons.append(self.remove_all_musou_button)
        self.musou_saves_note=tk.StringVar(value='Open a save copy to view your saved runs.')
        ttk.Label(page,textvariable=self.musou_saves_note,wraplength=960).pack(anchor='w')

    def refresh_collections(self):
        if self.document is None:return
        selected = self.collection_tree.selection()
        state=collections.collection_state(self.document,list(self.changes.values()))
        notes=[]
        for key,title,button in (('music','Music',self.music_unlock_button),('movies','Movies',self.movie_unlock_button)):
            row=state[key]
            notes.append(f'{title}: {row["owned"]}/{row["total"]} unlocked.' if row['editable'] else title+': '+row['reason'])
            button.configure(state='normal' if row['editable'] else 'disabled')
        self.gallery_note.set(' '.join(notes))
        self.collection_tree.delete(*self.collection_tree.get_children())
        search = self.collection_filter.get().strip().casefold()
        for key, title in (('music', 'Music'), ('movies', 'Movie')):
            for row in state[key]['rows']:
                if search and search not in f'{title} {row["name"]} {row["id"]}'.casefold():
                    continue
                self.collection_tree.insert('', 'end', iid=f'{key}:{row["id"]}', text=row['name'],
                                            values=(title, row['id'], 'Yes' if row['unlocked'] else 'No'))
        retained = [key for key in selected if self.collection_tree.exists(key)]
        if retained:
            self.collection_tree.selection_set(retained)
        self.select_collection_entries()

    def select_collection_entries(self):
        selected = self.collection_tree.selection()
        state = collections.collection_state(self.document) if self.document else {}
        supported = bool(selected) and all(state.get(key.split(':')[0], {}).get('editable') for key in selected)
        self.collection_selected_button.configure(state='normal' if supported else 'disabled')

    def unlock_selected_collections(self):
        if not self.selected_ok(self.collection_tree):return
        try:
            groups = {}
            for key in self.collection_tree.selection():
                gallery, index = key.split(':')
                groups.setdefault(gallery, []).append(int(index))
            changes = [change for gallery, indices in groups.items()
                       for change in collections.unlock_entry_changes(self.document, gallery, indices)]
            self.stage_many(changes)
        except (ValueError, TypeError) as error:
            messagebox.showerror('Cannot Unlock Selected Entries', str(error))

    def unlock_music(self):
        if self.require_save():
            try:self.stage_many(collections.unlock_music_changes(self.document))
            except ValueError as error:messagebox.showerror('Cannot Unlock Music',str(error))

    def unlock_movies(self):
        if self.require_save():
            try:self.stage_many(collections.unlock_movie_changes(self.document))
            except ValueError as error:messagebox.showerror('Cannot Unlock Movies',str(error))

    def refresh_musou_saves(self):
        if self.document is None:return
        selected=self.musou_saves_tree.selection()
        self.musou_saves_tree.delete(*self.musou_saves_tree.get_children())
        state=musou_slots.slot_state(self.document,list(self.changes.values()))
        for row in state['slots']:
            title=f'Slot {row["index"]+1}'
            values=(row['officer_name'],f'{"Side story" if row["side_story"] else "Musou"} progress {row["stage"]}',row['saved_at']) if row['active'] else ('Empty','—','—')
            self.musou_saves_tree.insert('', 'end',iid=str(row['index']),text=title,values=values)
        if selected and self.musou_saves_tree.exists(selected[0]):self.musou_saves_tree.selection_set(selected[0])
        self.musou_saves_note.set(state['reason'] or f'{state["active_count"]} saved runs. Removal keeps the slot layout intact; Undo restores pending removals.')
        self.remove_all_musou_button.configure(state='normal' if any(row['active'] and row['editable'] for row in state['slots']) else 'disabled')
        self.select_musou_save()

    def select_musou_save(self):
        selected=self.musou_saves_tree.selection()
        state=musou_slots.slot_state(self.document,list(self.changes.values())) if self.document else {'slots':[]}
        row=next((r for r in state['slots'] if selected and str(r['index'])==selected[0]),None)
        self.remove_musou_button.configure(state='normal' if row and row['active'] and row['editable'] else 'disabled')
        if row and row['active'] and not row['editable']:self.musou_saves_note.set(row['reason'])

    def remove_musou_save(self):
        if not self.selected_ok(self.musou_saves_tree):return
        index=int(self.musou_saves_tree.selection()[0])
        row=next(row for row in musou_slots.slot_state(self.document,list(self.changes.values()))['slots'] if row['index']==index)
        if not row['active'] or not row['editable']:return
        if not messagebox.askyesno('Remove Saved Musou Run',f'Remove slot {index+1} ({row["officer_name"]}) from the opened copy? This removes its between-stage campaign progress. Officer stats and completion flags stay unchanged. You can Undo before saving.'):return
        self.stage_many([musou_slots.remove_slot_change(index)])

    def remove_all_musou_saves(self):
        if not self.require_save():return
        if not messagebox.askyesno('Remove All Saved Musou Runs','Remove all supported between-stage campaign runs from the opened copy? Officer stats, unlocks and completion flags stay unchanged. You can Undo before saving.'):return
        self.stage_many(musou_slots.remove_all_changes(self.document))

    def require_save(self):
        if self.document is None:
            messagebox.showinfo('Open a Save', 'Open a save copy first.')
            return False
        return True

    def dirty_ok(self):
        return not self.changes or messagebox.askyesno('Unsaved Changes', 'Discard the pending changes? They have not been written to a file.')

    def open(self):
        if not self.dirty_ok(): return
        path = filedialog.askopenfilename(title='Open a Save Copy', filetypes=[('Game save', '*.sav')])
        if not path: return
        state_names=('document','backup','changes','history','current_officer','current_item',
                     'current_bodyguard','current_guard_item','current_guard_weapon','guard_weapon_slot',
                     'current_weapon_data_id','weapon_rows')
        previous={name:getattr(self,name) for name in state_names}
        previous_status=self.status.get()
        previous_experimental = self.experimental_mode.get()
        previous_experimental_note = self.experimental_note.get()
        try:
            document = read_save(Path(path))
            # Prove the display can interpret weapon rows before replacing
            # the current document and its pending edits.
            list(weapon_editor.states(document))
            backup = save_writer.backup_save(document)
            self.document, self.backup = document, backup
            self.changes, self.history = {}, []
            self.experimental_mode.set(False)
            self.experimental_note.set('Supported limits active. Max presets use supported maxima.')
            self.current_officer = self.current_item = self.current_bodyguard = 0
            self.current_guard_item = 0; self.current_guard_weapon = next(iter(GUARD_WEAPONS)); self.guard_weapon_slot = None
            self.update_paths()
            self.set_loaded(True)
            self.refresh()
            self.status.set('Save copy opened. An untouched backup is ready.')
        except Exception as error:
            for name,value in previous.items():setattr(self,name,value)
            self.experimental_mode.set(previous_experimental)
            self.experimental_note.set(previous_experimental_note)
            if self.document is not None:
                self.update_paths()
            else:
                self.filename.set('No save open.')
                self.backup_label.set('No backup selected.')
            self.set_loaded(self.document is not None)
            try:self.refresh()
            except Exception:self.set_loaded(False)
            self.status.set(previous_status)
            messagebox.showerror('Cannot Open Save', str(error))

    def update_paths(self):
        self.filename.set(f'Opened copy: {self.document.source.name}')
        self.backup_label.set(f'Original backup: {self.backup.name}' if self.backup else 'No backup selected.')
        warnings = self.document.compatibility_warnings
        self.compatibility_label.set(f'Compatibility notes: {len(warnings)}. Saved values outside normal drop ranges are preserved. Use Review Changes for details.' if warnings else '')

    def show_file_locations(self):
        if self.require_save():
            messagebox.showinfo('Save and Backup Locations',
                                f'Opened copy:\n{self.document.source}\n\nOriginal backup:\n{self.backup or "No backup selected."}')

    def show_contact(self):
        window = tk.Toplevel(self.root)
        window.title('Contact Mexican')
        window.resizable(False, False)
        panel = ttk.Frame(window, padding=22)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Made by Mexican', font=(self.font_family, 14, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='Report a bug, suggest a feature or get in touch.', style='Muted.TLabel').pack(anchor='w', pady=(5, 18))
        ttk.Label(panel, text='Discord username', style='Section.TLabel').pack(anchor='w')
        discord_row = ttk.Frame(panel)
        discord_row.pack(fill='x', pady=(5, 16))
        window.discord_name = tk.StringVar(window, value=DISCORD_USERNAME)
        ttk.Entry(discord_row, textvariable=window.discord_name, state='readonly', width=33).pack(side='left', padx=(0, 8))
        copied = tk.StringVar(window)
        def copy_discord():
            window.clipboard_clear()
            window.clipboard_append(DISCORD_USERNAME)
            copied.set('Discord username copied.')
        ttk.Button(discord_row, text='Copy', command=copy_discord).pack(side='left')
        ttk.Label(panel, text='Steam', style='Section.TLabel').pack(anchor='w')
        ttk.Label(panel, text='Leave a comment on my Steam profile.', style='Muted.TLabel').pack(anchor='w', pady=(5, 6))
        ttk.Button(panel, text='Open Steam Profile', command=lambda: webbrowser.open(STEAM_PROFILE)).pack(anchor='w')
        ttk.Label(panel, textvariable=copied, style='Muted.TLabel').pack(anchor='w', pady=(15, 0))
        self.theme_widgets(window)

    def officer_indices(self):
        return range(min(42,len(self.document.records('PCSaveDataArray'))))

    def item_rows(self):
        count=len(self.document.records('EquipItemDataArray'))
        return ((i,row) for i,row in ITEMS.items() if i<count)

    def editable_item_rows(self):
        for i,row in self.item_rows():
            record=fields(self.document.records('EquipItemDataArray')[i])
            if (record['EquipItemID']['value'] in ('EEquipItemID::NUM','EEquipItemID::'+row['enum'])
                    and record['GuardEquipItemID']['value']=='EGuardEquipItemID::NUM'):
                yield i,row

    @experimental_session
    def original_value(self, change):
        if change.category in collections.CATEGORIES:return collections.original_value(self.document,change)
        if change.category in musou_slots.CATEGORIES:return musou_slots.original_value(self.document,change)
        if change.category in customization.CATEGORIES:
            family='appearances' if change.field=='AppearanceUnlocked' else 'outfits'
            return next(row['unlocked'] for row in customization.customization_state(self.document)[family] if row['id']==change.index)
        if change.category in weapon_collection.CATEGORIES:return weapon_collection.original_value(self.document,change)
        if change.category in progression.CATEGORIES:
            if change.field == 'HuanglongElixirs':
                return progression.elixir_state(self.document)['saved_value']
            state=progression.progression_state(self.document)
            rows=state['officers'] if change.field=='MusouCleared' else state['side_stories']
            key='officer_id' if change.field=='MusouCleared' else 'id'
            row=next((r for r in rows if r[key]==change.index),None)
            if not row:return False
            if change.field=='MusouCleared':return row['cleared'] and row['progress']>=row['route_length']
            ruler_flags=self.document.properties['CanUseCharaArray']['value']['values']
            return row['unlocked'] and row['free_mode_unlocked'] and row['ruler_id']<len(ruler_flags) and bool(ruler_flags[row['ruler_id']])
        if change.category == 'unlock': return self.document.properties[change.field]['value']['values'][change.index]
        if change.category == 'bodyguard': return guard_editor.team_state(self.document, change.index, [])[change.field]
        if change.category == 'guard_item':
            row = guard_editor.item_state(self.document, [])[change.index]
            return row['owned'] if change.field == 'Owned' else row['value']
        if change.category == 'guard_weapon':
            if change.field == 'MaxBonuses': return False
            return any(row['weapon_id'] == change.index for row in guard_editor.weapon_state(self.document, []))
        if change.category == 'guard_weapon_slot': return guard_editor.weapon_state(self.document, [])[change.index]['skills']
        if change.category == 'weapon_roll': return weapon_editor.original_skills(self.document,change.index)
        if change.category == 'weapon_element':
            array,index=weapon_editor._location(self.document,change.index)
            if index>=len(self.document.records(array)):return 0
            return fields(self.document.records(array)[index])['Attr']['value'] & weapon_editor.ELEMENT_MASK
        if change.category == 'unique_weapon':
            index = UNIQUE_WEAPONS[change.index]['unique_save_index']
            return index < len(self.document.records('UniqueWeaponDataArray')) and fields(self.document.records('UniqueWeaponDataArray')[index])['WeaponID']['value'] != 'EWeaponID::NUM'
        array = {'officer': 'PCSaveDataArray', 'item': 'EquipItemDataArray', 'bodyguard': 'GuardDataArray'}[change.category]
        record = fields(self.document.records(array)[change.index])
        if change.category == 'item' and change.field == 'Owned': return record['EquipItemID']['value'] != 'EEquipItemID::NUM'
        return record[change.field]['value']

    @experimental_session
    def value(self, category, index, field):
        if category == 'bodyguard': return guard_editor.team_state(self.document, index, list(self.changes.values()))[field]
        change = self.changes.get((category, index, field))
        result = change.value if change else self.original_value(Change(category, index, field, 0))
        if category == 'item' and field == 'Value':
            if not self.value('item', index, 'Owned'): return 0
            if ITEMS[index]['kind'] == 'normal' and result == 0 and ('item',index,'Owned') in self.changes:return 1
        return result

    def field_value(self, index, field): return self.value('officer', index, field)

    @experimental_session
    def stage_many(self, changes):
        before = self.changes.copy()
        changes = list(changes)
        try:
            maximum_ids = {change.index for change in changes if change.category=='guard_weapon' and change.field=='MaxBonuses' and change.value is True}
            if maximum_ids:
                for row in guard_editor.weapon_state(self.document,list(self.changes.values())):
                    key = ('guard_weapon_slot', row['slot'], 'Skills')
                    if row['weapon_id'] in maximum_ids and key in self.changes:
                        skills = guard_editor.max_skills(row['weapon_id'], row['skills'], row['preservation_baseline'])
                        self.changes[key] = Change('guard_weapon_slot', row['slot'], 'Skills', skills)
            for change in changes:
                key = (change.category, change.index, change.field)
                if change.category in ('item','guard_item') and change.field == 'Owned' and change.value is False:
                    self.changes.pop((change.category, change.index, 'Value'), None)
                if change.category == 'progression' and change.field == 'HuanglongElixirs':
                    baseline = progression.elixir_state(self.document, [c for k, c in self.changes.items() if k != key])
                    if baseline['editable'] and change.value == baseline['value']: self.changes.pop(key, None)
                    else: self.changes[key] = change
                elif change.value == self.original_value(change): self.changes.pop(key, None)
                else: self.changes[key] = change
            # Validate the complete pending batch before changing any UI state.
            save_writer.plan_changes(self.document, list(self.changes.values()))
        except (ValueError,KeyError,TypeError,IndexError) as error:
            self.changes = before
            messagebox.showerror('Cannot Apply Changes',str(error))
            return False
        if self.changes != before: self.history.append(before)
        self.refresh()
        return True

    def restore_selection(self, tree, index):
        children = tree.get_children()
        key = str(index) if str(index) in children else (children[0] if children else None)
        if key is not None:
            tree.selection_set(key)
            tree.focus(key)
            tree.see(key)
        return key

    def refresh_officers(self):
        if self.document is None: return
        self.officers.delete(*self.officers.get_children())
        query = self.officer_filter.get().strip().casefold()
        for index in self.officer_indices():
            name = NAMES.get(str(index), f'Officer {index}')
            if not query or query in name.casefold(): self.officers.insert('', 'end', iid=str(index), text=name, values=[self.field_value(index, field) for field in LABELS])
        if self.restore_selection(self.officers, self.current_officer) is None:
            self.selected.set('No matching officers')
            for variable in self.inputs.values(): variable.set('')
        else: self.select_officer()

    def item_cap(self, index): return ITEM_CAPS.get(index, ITEM_CAPS.get(str(index)))

    def refresh_items(self):
        if self.document is None: return
        self.items.delete(*self.items.get_children())
        query = self.item_filter.get().strip().casefold()
        for index, row in self.item_rows():
            if query and query not in f'{row["name"]} {row["kind"]} {row.get("effect", "")}'.casefold(): continue
            owned = self.value('item', index, 'Owned')
            value = self.value('item', index, 'Value')
            self.items.insert('', 'end', iid=str(index), text=row['name'], values=(row['kind'].title(), value if row['kind'] == 'normal' else '—', 'Yes' if owned else 'No'))
        if self.restore_selection(self.items, self.current_item) is None:
            self.item_selected.set('No matching items'); self.item_detail.set(''); self.item_value.set(''); self.item_owned.set(False)
            self.item_entry.configure(state='disabled')
        else: self.select_item()

    @experimental_session
    def refresh_weapons(self):
        if self.document is None: return
        selected = self.weapons.selection()
        self.weapons.delete(*self.weapons.get_children())
        changes = list(self.changes.values())
        states = list(weapon_editor.states(self.document, changes))
        self.weapon_element_all_button.configure(state='normal' if any(row['array']=='UniqueWeaponDataArray' and row['element_editable'] for row in states) else 'disabled')
        self.weapon_bonus_sources = {
            f'{row["metadata"].get("name") or "Weapon"} [copy {row["data_id"]}]': row['data_id']
            for row in states if row['editable']}
        by_data = {row['data_id']:row for row in states}
        self.weapon_rows = {}
        query = self.weapon_filter.get().strip().casefold()
        for row in states:
            if row['array'] != 'WeaponDataArray': continue
            metadata = row['metadata']; name = metadata.get('name') or metadata.get('weapon_name') or f'Weapon {row["weapon_id"]}'
            if query and query not in f'{name} regular {row["data_id"]}'.casefold(): continue
            key = f'WeaponDataArray:{row["index"]}'
            self.weapon_rows[key] = row
            self.weapons.insert('', 'end', iid=key, text=name, values=('Regular',f'Copy {row["index"]+1}',metadata.get('base_power','—')))
        for weapon_id, weapon in UNIQUE_WEAPONS.items():
            owned = self.value('unique_weapon', weapon_id, 'Owned')
            name = f'{weapon["weapon_name"]} — {weapon["officer_name"]}'
            if query and query not in f'{name} unique {weapon["tier"]}th'.casefold(): continue
            key = f'unique:{weapon_id}'
            row = by_data.get(10000+weapon['unique_save_index'])
            if row: self.weapon_rows[key] = row
            self.weapons.insert('', 'end', iid=key, text=name, values=(f'{weapon["tier"]}th weapon','Yes' if owned else 'No',weapon['base_power']))
        self.weapon_element_visible_button.configure(state='normal' if any(row['element_editable'] for row in self.weapon_rows.values()) else 'disabled')
        if selected and self.weapons.exists(selected[0]):
            self.weapons.selection_set(selected[0]); self.weapons.focus(selected[0]); self.weapons.see(selected[0])
            self.select_weapon()
        else:
            children = self.weapons.get_children()
            if children:
                self.weapons.selection_set(children[0]); self.weapons.focus(children[0]); self.select_weapon()
            else:
                self.clear_weapon_form(); self.weapon_selected.set('No matching weapons')

    def describe_skill(self, item, value):
        if item['kind'] == 'normal': return f'{weapon_bonus_label(item)} +{value}'
        return item['name']

    @experimental_session
    def select_weapon(self, event=None):
        selected = self.weapons.selection()
        if not selected or self.document is None: return
        source, index = selected[0].split(':'); index = int(index)
        row = self.weapon_rows.get(selected[0])
        if row is None and source == 'unique':
            metadata = UNIQUE_WEAPONS[index]
            self.clear_weapon_form()
            self.weapon_selected.set(metadata['weapon_name'])
            bonuses = [self.describe_skill(ITEMS[s['item_id']],s['value']) for s in metadata['skill_slots'] if s['item_id'] in ITEMS]
            self.weapon_detail.set(f'Base attack {metadata["base_power"]}. Not owned.\nStock bonuses on acquisition: {", ".join(bonuses) or "None"}')
            return
        if row is None: self.clear_weapon_form(); return
        self.current_weapon_data_id = row['data_id']
        metadata = row['metadata']
        name = metadata.get('name') or metadata.get('weapon_name') or self.weapons.item(selected[0],'text')
        self.weapon_selected.set(name)
        flags = self.weapon_attribute_text(row['attr'])
        reason = f'{row.get("blue_minimum",0)}–{row["blue_limit"]} normal bonuses; at most one rare.' if row['editable'] else row.get('reason','This copy is view-only.')
        self.weapon_detail.set(f'Base attack {metadata.get("base_power","unknown")} • Copy ID {row["data_id"]}\n{flags}\n{reason}')
        self.weapon_element_choices=weapon_editor.allowed_elements(row)
        if row['elements'] not in self.weapon_element_choices.values():
            self.weapon_element_choices['Existing (preserved)']=row['elements']
        self.weapon_element.set(next(label for label,mask in self.weapon_element_choices.items() if mask==row['elements']))
        self.weapon_element_box.configure(values=tuple(self.weapon_element_choices),state='readonly' if row['element_editable'] else 'disabled')
        self.weapon_element_button.configure(state='normal' if row['element_editable'] else 'disabled')
        self.weapon_element_visible_button.configure(state='normal' if row['element_editable'] and any(
            target['element_editable'] for target in self.weapon_rows.values()) else 'disabled')
        self.loading_weapon_form = True
        try:
            for name,value,box,valuebox in zip(self.weapon_bonus_names,self.weapon_bonus_values,self.weapon_bonus_boxes,self.weapon_bonus_value_boxes):
                name.set('None');value.set('');box.configure(state='disabled');valuebox.configure(state='disabled',values=())
            for slot, skill in enumerate(row['skills'][:9]):
                item = ITEMS.get(skill['id'])
                label = weapon_bonus_label(item) if item else ('None' if skill['id'] is None else f'Unknown bonus {skill["id"]}')
                self.weapon_bonus_names[slot].set(label)
                self.weapon_bonus_values[slot].set(str(skill['value']) if skill['id'] in weapon_editor.NORMAL_ITEMS else '—' if skill['id'] is not None else '')
                protected = skill['id'] is not None and skill['id'] not in weapon_editor.NORMAL_ITEMS and skill['id'] not in weapon_editor.RARE_ITEMS
                self.weapon_bonus_boxes[slot].configure(values=(label,) if protected else tuple(self.weapon_bonus_choices),state='readonly' if row['editable'] and not protected else 'disabled')
                self.change_weapon_bonus(slot)
        finally: self.loading_weapon_form = False
        self.weapon_roll_button.configure(state='normal' if row['editable'] else 'disabled')
        self.weapon_max_button.configure(state='normal' if row['editable'] else 'disabled')
        sources = tuple(label for label, data_id in self.weapon_bonus_sources.items() if data_id != row['data_id'])
        if self.weapon_bonus_source.get() not in sources:
            self.weapon_bonus_source.set(sources[0] if sources else '')
        enabled = row['editable'] and bool(sources)
        self.weapon_bonus_source_box.configure(values=sources, state='readonly' if enabled else 'disabled')
        self.weapon_copy_button.configure(state='normal' if enabled else 'disabled')

    def clear_weapon_form(self):
        self.current_weapon_data_id = None
        self.weapon_selected.set('Select a weapon')
        self.weapon_detail.set('Select an owned copy to edit its bonuses and element.')
        self.weapon_element.set('None');self.weapon_element_choices={}
        self.weapon_element_box.configure(state='disabled',values=())
        self.weapon_element_button.configure(state='disabled')
        self.weapon_element_visible_button.configure(state='disabled')
        for name,value,box,valuebox in zip(self.weapon_bonus_names,self.weapon_bonus_values,self.weapon_bonus_boxes,self.weapon_bonus_value_boxes):
            name.set('None'); value.set(''); box.configure(state='disabled'); valuebox.configure(state='disabled',values=())
        self.weapon_roll_button.configure(state='disabled'); self.weapon_max_button.configure(state='disabled')
        self.weapon_bonus_source.set('')
        self.weapon_bonus_source_box.configure(state='disabled', values=())
        self.weapon_copy_button.configure(state='disabled')

    def weapon_attribute_text(self, attr):
        labels = ['6-hit flag'] if attr & 2 else ['5-hit flag'] if attr & 1 else []
        labels.extend(name for bit,name in ((4,'Fire'),(8,'Lightning'),(16,'Steel'),(32,'Wind')) if attr & bit)
        return 'Weapon properties: '+(', '.join(labels) if labels else 'no hit or element flags')

    def officer_bonus_text(self, skills):
        return ', '.join(self.describe_skill(ITEMS[skill['id']],skill['value']) if skill['id'] in ITEMS else f'Bonus {skill["id"]} +{skill["value"]}' for skill in skills if skill['id'] is not None) or 'No bonuses'

    @experimental_session
    def change_weapon_bonus(self, slot):
        if self.current_weapon_data_id is None: return
        row = weapon_editor.state(self.document,self.current_weapon_data_id,list(self.changes.values()))
        if not 0<=slot<min(len(row['skills']),len(self.weapon_bonus_names)):return
        original = row['skills'][slot]
        item = ITEMS.get(original['id'])
        if original['id'] is not None and original['id'] not in weapon_editor.NORMAL_ITEMS and original['id'] not in weapon_editor.RARE_ITEMS:
            self.weapon_bonus_value_boxes[slot].configure(values=(),state='disabled')
            return
        item_id = self.weapon_bonus_choices.get(self.weapon_bonus_names[slot].get())
        if item_id in weapon_editor.RARE_ITEMS:
            self.weapon_bonus_values[slot].set('—')
            self.weapon_bonus_value_boxes[slot].configure(values=(),state='disabled')
            return
        values = sorted(weapon_editor.allowed_values(row,item_id)) if item_id is not None else []
        saved=weapon_editor.original_skills(self.document,self.current_weapon_data_id)[slot]
        if item_id is not None and saved['id']==item_id and saved['value']>0:
            values=sorted(set(values+[saved['value']]))
        enabled = row['editable'] and bool(values)
        extended = (experimental_enabled() and row.get('experimental_existing', False)
                    and item_id in weapon_editor.NORMAL_ITEMS and item_id == saved['id'])
        self.weapon_bonus_value_boxes[slot].configure(values=tuple(values),state=('normal' if extended else 'readonly') if enabled else 'disabled')
        if item_id is None: self.weapon_bonus_values[slot].set('')
        elif not extended and not self.loading_weapon_form and self.weapon_bonus_values[slot].get() not in {str(value) for value in values}:
            self.weapon_bonus_values[slot].set(str(values[-1]) if values else '')

    @experimental_session
    def apply_weapon_rolls(self):
        if not self.require_save() or self.current_weapon_data_id is None: return
        try:
            row = weapon_editor.state(self.document,self.current_weapon_data_id,list(self.changes.values()))
            if not row['editable']: raise ValueError(row.get('reason','This copy cannot be edited safely.'))
            skills = []
            for slot, original in enumerate(row['skills']):
                item = ITEMS.get(original['id'])
                if original['id'] is not None and original['id'] not in weapon_editor.NORMAL_ITEMS and original['id'] not in weapon_editor.RARE_ITEMS:
                    skills.append(original.copy()); continue
                label = self.weapon_bonus_names[slot].get()
                if label not in self.weapon_bonus_choices: raise ValueError(f'Choose a supported bonus in slot {slot+1}.')
                item_id = self.weapon_bonus_choices[label]
                value = (original['value'] if item_id==original['id'] else 0) if item_id in weapon_editor.RARE_ITEMS else int(self.weapon_bonus_values[slot].get()) if item_id is not None else 0
                saved=weapon_editor.original_skills(self.document,self.current_weapon_data_id)[slot]
                preserved=item_id==saved['id'] and value==saved['value'] and value>0
                extended = False
                if item_id in weapon_editor.NORMAL_ITEMS:
                    low, supported_maximum, storage_maximum = weapon_editor.skill_numeric_limits(row, item_id)
                    extended = (row.get('experimental_existing', False) and item_id == saved['id'] and value > supported_maximum
                                and within_numeric_limits(value, low, supported_maximum, storage_maximum=storage_maximum))
                    if value not in weapon_editor.allowed_values(row,item_id) and not (preserved or extended):
                        raise ValueError(f'Slot {slot+1}: choose a supported roll up to {supported_maximum}; experimental maximum {storage_maximum:,} applies to its saved bonus.')
                skills.append({'id':item_id,'value':value})
            normal = [skill['id'] for skill in skills if skill['id'] in ITEMS and ITEMS[skill['id']]['kind']=='normal']
            if len(normal)>row['blue_limit']: raise ValueError(f'This weapon supports at most {row["blue_limit"]} normal bonuses.')
            if len(normal)!=len(set(normal)): raise ValueError('Choose each normal bonus at most once.')
            skills = weapon_editor.validate_skills(row,skills)
            self.stage_many([Change('weapon_roll',self.current_weapon_data_id,'Skills',skills)])
        except (ValueError,TypeError) as error: messagebox.showerror('Cannot Apply Weapon Bonuses',str(error))

    @experimental_session
    def apply_weapon_element(self):
        if not self.require_save() or self.current_weapon_data_id is None:return
        try:
            row=weapon_editor.state(self.document,self.current_weapon_data_id,list(self.changes.values()))
            label=self.weapon_element.get()
            if label not in self.weapon_element_choices:raise ValueError('Choose a supported weapon element.')
            mask=weapon_editor.validate_elements(row,self.weapon_element_choices[label])
            self.stage_many([Change('weapon_element',self.current_weapon_data_id,'Elements',mask)])
        except (ValueError,TypeError) as error:messagebox.showerror('Cannot Apply Weapon Element',str(error))

    @experimental_session
    def copy_weapon_bonuses(self):
        if not self.require_save() or self.current_weapon_data_id is None:return
        try:
            source = self.weapon_bonus_sources[self.weapon_bonus_source.get()]
            changes = weapon_editor.copy_bonus_changes(self.document, source, [self.current_weapon_data_id],
                                                       list(self.changes.values()))
            self.stage_many(changes)
        except (ValueError, TypeError, KeyError) as error:
            messagebox.showerror('Cannot Copy Weapon Bonuses', str(error))

    @experimental_session
    def apply_visible_weapon_elements(self):
        if not self.require_save():return
        try:
            label = self.weapon_element.get()
            mask = self.weapon_element_choices[label]
            targets = [row['data_id'] for row in self.weapon_rows.values() if row['element_editable']]
            changes = weapon_editor.element_changes(self.document, targets, mask, list(self.changes.values()))
            if self.stage_many(changes):
                self.status.set(f'{label} applied to {len(targets)} visible owned copies. Save to write the changes.')
        except (ValueError, TypeError, KeyError) as error:
            messagebox.showerror('Cannot Apply Visible Weapon Elements', str(error))

    @experimental_session
    def max_selected_weapon_rolls(self):
        if not self.require_save() or self.current_weapon_data_id is None: return
        try:
            skills = weapon_editor.max_existing_skills(self.document,self.current_weapon_data_id,list(self.changes.values()))
            self.stage_many([Change('weapon_roll',self.current_weapon_data_id,'Skills',skills)])
        except (ValueError,TypeError) as error: messagebox.showerror('Cannot Max Weapon Bonuses',str(error))

    @experimental_session
    def apply_unique_weapon_elements(self):
        if not self.require_save(): return
        try:
            label = self.unique_weapon_element.get()
            mask = self.unique_element_choices[label]
            changes = weapon_editor.owned_unique_element_changes(self.document, mask, list(self.changes.values()))
            if self.stage_many(changes):
                self.status.set(f'{label} applied to {len(changes)} owned unique weapons. Save to write the changes.')
        except (ValueError, TypeError, KeyError) as error:
            messagebox.showerror('Cannot Apply Unique Weapon Elements', str(error))

    @experimental_session
    def max_all_weapon_rolls(self):
        if not self.require_save(): return
        try:
            changes = list(self.changes.values())
            rows = list(weapon_editor.states(self.document,changes))
            maximum = [Change('weapon_roll',row['data_id'],'Skills',weapon_editor.max_existing_skills(self.document,row['data_id'],changes)) for row in rows if row['editable']]
            self.stage_many(maximum)
            skipped = sum(not row['editable'] for row in rows)
            self.status.set(f'Maximum normal rolls applied to {len(maximum)} owned copies. {skipped} view-only copies preserved. Save to write the changes.')
        except (ValueError,TypeError) as error: messagebox.showerror('Cannot Max Weapon Bonuses',str(error))

    @experimental_session
    def refresh_bodyguards(self):
        self.bodyguards.delete(*self.bodyguards.get_children())
        for index, record in enumerate(self.document.records('GuardDataArray')):
            row = fields(record)
            names = row.get('UnitNameLang', {}).get('value', {}).get('values', [])
            name = next((name for name in names if isinstance(name, str) and name.strip()), f'Team {index + 1}')
            self.bodyguards.insert('', 'end', iid=str(index), text=name, values=(self.value('bodyguard', index, 'SPoint'),))
        if self.restore_selection(self.bodyguards, self.current_bodyguard) is not None: self.select_bodyguard()
        else:
            self.bodyguard_selected.set('No saved bodyguard teams')
            self.guard_stats.set('');self.guard_budget.set('');self.guard_automatic.set('')
        self.refresh_guard_items(); self.refresh_guard_weapons()

    @experimental_session
    def refresh_guard_items(self):
        self.guard_items.delete(*self.guard_items.get_children())
        for index, state in guard_editor.item_state(self.document, list(self.changes.values())).items():
            metadata = GUARD_ITEMS[index]
            self.guard_items.insert('', 'end', iid=str(index), text=metadata['name'], values=(state['value'] if metadata['kind']=='normal' else '—', 'Yes' if state['owned'] else 'No'))
        if self.restore_selection(self.guard_items, self.current_guard_item) is not None: self.select_guard_item()

    @experimental_session
    def refresh_guard_weapons(self):
        selected = self.guard_weapons.selection()
        self.guard_weapons.delete(*self.guard_weapons.get_children())
        rows = guard_editor.weapon_state(self.document, list(self.changes.values()))
        for weapon_id, metadata in GUARD_WEAPONS.items():
            owned = [row for row in rows if row['weapon_id']==weapon_id]
            parent = f'weapon:{weapon_id}'
            self.guard_weapons.insert('', 'end', iid=parent, text=metadata['name'], values=(metadata['tier'],len(owned),metadata['base_power']))
            for row in owned:
                label = f'Owned copy {row["slot"]+1}'
                self.guard_weapons.insert(parent, 'end', iid=f'slot:{row["slot"]}', text=label, values=(metadata['tier'],'Yes',metadata['base_power']))
        key = selected[0] if selected and self.guard_weapons.exists(selected[0]) else f'weapon:{self.current_guard_weapon}'
        if self.guard_weapons.exists(key):
            self.guard_weapons.selection_set(key); self.guard_weapons.focus(key)
            parent = self.guard_weapons.parent(key)
            if parent: self.guard_weapons.item(parent, open=True)
            self.select_guard_weapon()

    @experimental_session
    def refresh_guard_equipment(self):
        changes = list(self.changes.values())
        state = guard_editor.team_state(self.document, self.current_bodyguard, changes)
        item_choices = {'None':None}
        for index, item in guard_editor.item_state(self.document, changes).items():
            if item['owned'] and item['editable']:
                metadata = GUARD_ITEMS[index]
                label = metadata['name'] + (f' +{item["value"]}' if metadata['kind']=='normal' else '')
                item_choices[label] = index
        if state['MemberItem'] is not None and state['MemberItem'] not in item_choices.values():
            item_choices[f'Existing item reference {state["MemberItem"]} (preserved)']=state['MemberItem']
        self.guard_equip_item_choices = item_choices
        self.guard_equip_item_box.configure(values=tuple(item_choices))
        self.guard_equip_item.set(next((label for label,index in item_choices.items() if index==state['MemberItem']), 'None'))
        rows = guard_editor.weapon_state(self.document, changes)
        known_layout=len(state['MemberWeapon'])==10
        for family_index in range(5):
            choices = {'None':-1}
            for row in rows:
                if row['weapon_id'] is None or not row['identity_valid']: continue
                metadata = GUARD_WEAPONS[row['weapon_id']]
                if metadata['family_index']==family_index:
                    choices[f'{metadata["name"]} — copy {row["slot"]+1}'] = row['data_id']
            self.guard_equip_weapon_choices[family_index] = choices
            self.guard_equip_weapon_boxes[family_index].configure(values=tuple(choices),state='readonly' if known_layout else 'disabled')
            current = state['MemberWeapon'][family_index] if family_index<len(state['MemberWeapon']) else None
            label=next((label for label,index in choices.items() if index==current), f'Existing reference {current} (preserved)' if current is not None else 'Unknown layout')
            # Retain unknown saved choices when applying a different family.
            if current is not None and label not in choices:choices[label]=current
            self.guard_equip_weapons[family_index].set(label)

    @experimental_session
    def refresh(self):
        self.refresh_dashboard()
        if self.document is None: return
        self.refresh_officers(); self.refresh_items(); self.refresh_weapons(); self.refresh_bodyguards()
        self.refresh_story_status()
        self.refresh_guard_customization()
        self.refresh_collections()
        self.refresh_musou_saves()
        self.refresh_elixirs()
        self.status.set(f'{len(self.changes)} pending changes. Applied in the editor; use Save As or Save Changes to write them.')

    @experimental_session
    def refresh_story_status(self):
        if self.document is None:self.story_status.set('');return
        try:
            state=progression.progression_state(self.document)
            selected=self.story_officer_choices.get(self.story_officer.get())
            row=next((r for r in state['officers'] if r['officer_id']==selected),None)
            if not row:self.story_status.set('This officer record is absent from the save.');return
            pending=self.changes.get(('progression',selected,'MusouCleared'))
            cleared=row['cleared'] or bool(pending)
            self.story_status.set(f'{"Cleared" if cleared else "Not cleared"}{" (pending)" if pending else ""}; saved progress {row["progress"]}/{row["route_length"]}.')
        except (ValueError,KeyError,TypeError):self.story_status.set('This save’s story structures are view-only.')

    @experimental_session
    def refresh_elixirs(self):
        if self.document is None:
            return
        state = progression.elixir_state(self.document, list(self.changes.values()))
        editable = state['editable']
        self.elixir_entry.configure(state='normal' if editable else 'disabled')
        for button in (self.elixir_apply_button, self.elixir_max_button):
            button.configure(state='normal' if editable else 'disabled')
        self.elixir_input.set(str(state['value']) if state['value'] is not None else '')
        if not editable:
            self.elixir_note.set(state['reason'])
        elif state['value'] != state['saved_value'] or ('progression', 0, 'HuanglongElixirs') in self.changes:
            self.elixir_note.set(f"Saved: {state['saved_value']} · Final pending balance: {state['value']}")
        else:
            self.elixir_note.set(f"Saved balance: {state['saved_value']}")

    @experimental_session
    def apply_elixirs(self):
        if not self.require_save():
            return
        try:
            value = int(self.elixir_input.get().strip())
            change = (Change('progression', 0, 'HuanglongElixirs', value)
                      if value == progression.elixir_state(self.document)['saved_value'] else
                      progression.elixir_count_change(value))
        except (ValueError, TypeError):
            maximum = INT32_MAX if experimental_enabled() else progression.ELIXIR_MAX
            messagebox.showerror('Cannot Apply Elixirs', f'Enter a whole number from 0 to {maximum:,}. Supported maximum: {progression.ELIXIR_MAX}.')
            return
        self.stage_many([change])

    @experimental_session
    def max_elixirs(self):
        if self.require_save():
            state = progression.elixir_state(self.document, list(self.changes.values()))
            value = max(progression.ELIXIR_MAX, state['saved_value'], state['value'])
            self.stage_many([Change('progression', 0, 'HuanglongElixirs', value)])

    def select_officer(self, event=None):
        selected = self.officers.selection()
        if not selected or self.document is None: return
        self.current_officer = int(selected[0]); self.selected.set(NAMES.get(selected[0], selected[0]))
        for field, variable in self.inputs.items(): variable.set(str(self.field_value(self.current_officer, field)))

    def select_item(self, event=None):
        selected = self.items.selection()
        if not selected or self.document is None: return
        self.current_item = int(selected[0]); row = ITEMS[self.current_item]; cap = self.item_cap(self.current_item)
        self.item_selected.set(row['name'])
        self.item_detail.set(f'{row.get("effect", "")}\nSupported drop maximum: {cap}\nExperimental storage maximum: {INT32_MAX:,}' if cap is not None else ('Rare item — ownership only.' if row['kind'] == 'rare' else 'Roll limit is still being verified.'))
        self.item_owned.set(self.value('item', self.current_item, 'Owned')); self.item_value.set(str(self.value('item', self.current_item, 'Value')))
        self.item_entry.configure(state='normal' if cap is not None and row['kind'] == 'normal' else 'disabled')

    @experimental_session
    def select_bodyguard(self, event=None):
        selected = self.bodyguards.selection()
        if not selected or self.document is None: return
        self.current_bodyguard = int(selected[0]); self.bodyguard_selected.set(self.bodyguards.item(selected[0], 'text'))
        state = guard_editor.team_state(self.document, self.current_bodyguard, list(self.changes.values()))
        self.loading_guard_form = True
        try:
            self.bodyguard_limit.set('Merit (supported 0–99,999; experimental max 2,147,483,647)')
            self.bodyguard_merit.set(str(state['SPoint']))
            for index, variable in self.guard_growth_inputs.items():
                variable.set(str(state['BGLevels'][index]) if index<len(state['BGLevels']) else '')
                self.guard_growth_boxes[index].configure(state='normal' if state['growth_editable'] else 'disabled')
        finally: self.loading_guard_form = False
        if state['growth_editable']:self.preview_growth()
        else:
            self.guard_budget.set('Saved growth is view-only: '+state['growth_reason'])
            self.guard_automatic.set('Existing values are preserved.');self.guard_stats.set('')
        self.refresh_guard_equipment()

    @experimental_session
    def growth_form(self):
        merit = int(self.bodyguard_merit.get())
        opened_merit = self.original_value(Change('bodyguard', self.current_bodyguard, 'SPoint', 0))
        table_merit = min(merit, growth.MERIT_CAP) if merit == opened_merit and not experimental_enabled() else merit
        caps = growth.earned_caps(table_merit)
        levels = [0,0,0,caps[3],0,caps[5]]
        for index, variable in self.guard_growth_inputs.items(): levels[index] = int(variable.get())
        growth.validate_growth(table_merit, levels)
        return merit, levels

    @experimental_session
    def preview_growth(self):
        if self.document is None or self.loading_guard_form: return
        try:
            state=guard_editor.team_state(self.document,self.current_bodyguard,list(self.changes.values()))
            merit=int(self.bodyguard_merit.get())
            same_allocation=all(int(variable.get())==state['BGLevels'][index] for index,variable in self.guard_growth_inputs.items())
            if same_allocation and merit>=state['SPoint']:
                levels=state['BGLevels'] if merit==state['SPoint'] else growth.advance_automatic_levels(merit,state['BGLevels'])
            else:merit,levels=self.growth_form()
            stats = growth.derive_stats(levels)
            self.guard_budget.set(f'Growth points: {growth.spent(levels)} / {growth.budget(min(merit, growth.MERIT_CAP))} used')
            self.guard_automatic.set(f'Automatic growth: Count {levels[3]} (team capacity {stats["member_count"]})   •   AI {levels[5]}')
            self.guard_stats.set(f'Growth base: Life {stats["base_hp"]}   Musou {stats["base_musou"]}   Attack {stats["base_attack"]}   Defense {stats["base_defense"]}\nMove {stats["move"]}   Jump {stats["jump"]}   Bow strength {stats["bow_percent"]}%   Moveset {stats["motion_level"]}')
        except (ValueError, TypeError) as error:
            self.guard_budget.set(f'Check growth: {error}')
            self.guard_automatic.set('Count and AI follow the entered Merit.'); self.guard_stats.set('Enter a legal allocation to preview base stats.')

    @experimental_session
    def select_guard_item(self, event=None):
        selected = self.guard_items.selection()
        if not selected or self.document is None: return
        self.current_guard_item = int(selected[0]); metadata = GUARD_ITEMS[self.current_guard_item]
        state = guard_editor.item_state(self.document, list(self.changes.values()))[self.current_guard_item]
        self.guard_item_selected.set(metadata['name'])
        self.guard_item_detail.set(f'{metadata.get("effect", "").strip()}\nSupported drop maximum: {metadata["max_value"]}\nExperimental storage maximum: {INT32_MAX:,}' if metadata['kind']=='normal' else 'Rare bodyguard item — ownership only.')
        self.guard_item_owned.set(state['owned']); self.guard_item_value.set(str(state['value'] or 1))
        self.guard_item_entry.configure(state='normal' if metadata['kind']=='normal' else 'disabled')

    def guard_bonus_text(self, skills):
        labels = []
        for skill in skills:
            if skill['id'] is None: continue
            metadata = GUARD_ITEMS.get(skill['id'])
            if metadata: labels.append(self.describe_skill(metadata, skill['value']))
        return ', '.join(labels) or 'No bonuses'

    @experimental_session
    def select_guard_weapon(self, event=None):
        selected = self.guard_weapons.selection()
        if not selected or self.document is None: return
        kind, index = selected[0].split(':'); index = int(index)
        rows = guard_editor.weapon_state(self.document, list(self.changes.values()))
        row = rows[index] if kind=='slot' else next((row for row in rows if row['weapon_id']==index),None)
        self.current_guard_weapon = row['weapon_id'] if kind=='slot' else index
        self.guard_weapon_slot = index if kind=='slot' else None
        metadata = GUARD_WEAPONS[self.current_guard_weapon]
        detail = self.guard_bonus_text(row['skills']) if row else 'Not owned; unlocking creates a legal stock copy.'
        self.guard_bonus_editable = kind=='slot' and row is not None and row['editable']
        if row is not None and not row['editable']: detail += '\n' + row['reason']
        self.guard_weapon_detail.set(f'{metadata["name"]} | {guard_editor.FAMILY_NAMES[metadata["family_index"]]} tier {metadata["tier"]} | Base attack {metadata["base_power"]}\n{detail}')
        self.guard_bonus_choices = {'None':None}
        self.guard_bonus_choices.update({weapon_bonus_label(GUARD_ITEMS[index]):index for index in metadata['allowed_skill_ids']})
        if row is not None and not row['editable']:
            self.guard_bonus_choices.update({weapon_bonus_label(GUARD_ITEMS[s['id']]):s['id'] for s in row['skills']})
        self.loading_guard_form = True
        try:
            for index in range(3):
                skill = row['skills'][index] if row and index<len(row['skills']) else None
                self.guard_bonus_boxes[index].configure(values=tuple(self.guard_bonus_choices),state='readonly' if self.guard_bonus_editable else 'disabled')
                self.guard_bonus_items[index].set(next((label for label,item in self.guard_bonus_choices.items() if skill and item==skill['id']),'None'))
                self.guard_bonus_values[index].set(str(skill['value']) if skill else '')
        finally: self.loading_guard_form = False
        for index in range(3): self.guard_bonus_item_changed(index)
        self.guard_bonus_button.configure(state='normal' if self.guard_bonus_editable else 'disabled')

    @experimental_session
    def guard_bonus_item_changed(self,index):
        if self.loading_guard_form: return
        if not getattr(self,'guard_bonus_editable',False):
            self.guard_bonus_value_boxes[index].configure(values=(),state='disabled')
            return
        item = self.guard_bonus_choices.get(self.guard_bonus_items[index].get())
        extended = False
        values = list(GUARD_WEAPONS[self.current_guard_weapon]['allowed_values_by_guard_item_id'].get(str(item),[])) if item is not None else []
        if self.guard_weapon_slot is not None:
            pending=guard_editor.weapon_state(self.document,list(self.changes.values()))[self.guard_weapon_slot]
            saved=pending.get('preservation_baseline',guard_editor.weapon_state(self.document)[self.guard_weapon_slot]['skills'])
            if index<len(saved) and saved[index] is not None and item is not None and saved[index]['id']==item and saved[index]['value']>0:
                values=sorted(set(values+[saved[index]['value']]))
                extended = experimental_enabled() and GUARD_ITEMS[item]['kind'] == 'normal'
        self.guard_bonus_value_boxes[index].configure(values=tuple(values),state=('normal' if extended else 'readonly') if values and self.guard_weapon_slot is not None else 'disabled')
        current = self.guard_bonus_values[index].get()
        if not extended and current not in [str(value) for value in values]: self.guard_bonus_values[index].set(str(values[-1]) if values else '')

    @experimental_session
    def apply_guard_bonuses(self):
        if not self.require_save() or self.guard_weapon_slot is None: return
        try:
            skills = []
            for itemvar,valuevar in zip(self.guard_bonus_items,self.guard_bonus_values):
                item = self.guard_bonus_choices[itemvar.get()]
                if item is not None: skills.append({'id':item,'value':int(valuevar.get())})
            if not skills: raise ValueError('Choose at least one bonus. Generated bodyguard weapons always have a bonus.')
            pending=guard_editor.weapon_state(self.document,list(self.changes.values()))[self.guard_weapon_slot]
            skills = guard_editor.validate_skills(self.current_guard_weapon,skills,original_skills=pending.get('preservation_baseline',guard_editor.weapon_state(self.document)[self.guard_weapon_slot]['skills']))
            self.stage_many([Change('guard_weapon_slot',self.guard_weapon_slot,'Skills',skills)])
        except (ValueError,KeyError) as error: messagebox.showerror('Invalid Weapon Bonuses',str(error))

    def selected_ok(self, tree): return self.require_save() and bool(tree.selection())

    @experimental_session
    def apply_officer(self):
        if not self.selected_ok(self.officers): return
        try:
            changes = []
            for field, variable in self.inputs.items():
                if field not in CAPS: continue
                value = int(variable.get()); low = 1 if field in ('MaxHealth', 'MaxMusou') else 0
                unchanged = value == self.original_value(Change('officer', self.current_officer, field, value))
                if not within_numeric_limits(value, low, CAPS[field], storage_maximum=INT32_MAX) and not unchanged:
                    raise ValueError(f'{LABELS[field]}: supported {low}–{CAPS[field]:,}; experimental maximum {INT32_MAX:,}.')
                changes.append(Change('officer', self.current_officer, field, value))
            self.stage_many(changes)
        except ValueError as error: messagebox.showerror('Invalid Value', str(error))

    def max_selected(self):
        if self.selected_ok(self.officers): self.stage_many([Change('officer', self.current_officer, field, self.officer_maximum(self.current_officer, field)) for field in CAPS])

    def max_all(self):
        if self.require_save(): self.stage_many([Change('officer', index, field, self.officer_maximum(index, field)) for index in self.officer_indices() for field in CAPS])

    def merit_all(self):
        if self.require_save(): self.stage_many([Change('officer', index, 'SPoint', self.officer_maximum(index, 'SPoint')) for index in self.officer_indices()])

    def officer_maximum(self, index, field):
        return max(CAPS[field], self.original_value(Change('officer', index, field, 0)), self.field_value(index, field))

    @experimental_session
    def apply_item(self):
        if not self.selected_ok(self.items): return
        try:
            index = self.current_item; changes = [Change('item', index, 'Owned', self.item_owned.get())]; cap = self.item_cap(index)
            if self.item_owned.get() and cap is not None and ITEMS[index]['kind'] == 'normal':
                value = int(self.item_value.get())
                if value == 0: value = 1
                unchanged=self.original_value(Change('item',index,'Owned',True)) and value==self.original_value(Change('item',index,'Value',value)) and value>0
                if not within_numeric_limits(value, 1, cap, storage_maximum=INT32_MAX) and not unchanged:
                    raise ValueError(f'{ITEMS[index]["name"]}: supported 1–{cap}; experimental maximum {INT32_MAX:,}, or its unchanged saved value.')
                changes.append(Change('item', index, 'Value', value))
            self.stage_many(changes)
        except ValueError as error: messagebox.showerror('Invalid Value', str(error))

    @experimental_session
    def max_items(self):
        if not self.require_save() or not ITEM_CAPS: return
        changes = []
        for index, row in self.editable_item_rows():
            cap = self.item_cap(index)
            if row['kind'] == 'normal' and cap is not None: changes.extend([Change('item', index, 'Owned', True), Change('item', index, 'Value', weapon_editor.max_item_value(self.document,index,list(self.changes.values())))])
        self.stage_many(changes)

    def unlock_items(self, kind=None):
        if self.require_save(): self.stage_many([Change('item', index, 'Owned', True) for index, row in self.editable_item_rows() if kind is None or row['kind'] == kind])

    @experimental_session
    def apply_bodyguard(self):
        if not self.selected_ok(self.bodyguards): return
        try:
            merit = int(self.bodyguard_merit.get())
            unchanged = merit == self.original_value(Change('bodyguard', self.current_bodyguard, 'SPoint', merit))
            if not within_numeric_limits(merit, 0, 99999, storage_maximum=INT32_MAX) and not unchanged:
                raise ValueError(f'Bodyguard Merit: supported 0–99,999; experimental maximum {INT32_MAX:,}.')
            state = guard_editor.team_state(self.document,self.current_bodyguard,list(self.changes.values()))
            allocation_changed = any(int(variable.get())!=state['BGLevels'][index] for index,variable in self.guard_growth_inputs.items())
            changes = [Change('bodyguard', self.current_bodyguard, 'SPoint', merit)]
            if allocation_changed:
                _,levels=self.growth_form()
                changes.append(Change('bodyguard', self.current_bodyguard, 'BGLevels', levels))
            self.stage_many(changes)
        except ValueError as error: messagebox.showerror('Invalid Value', str(error))

    @experimental_session
    def max_bodyguard(self, mode='balanced'):
        if self.selected_ok(self.bodyguards): self.stage_many([Change('bodyguard', self.current_bodyguard, 'SPoint', max(99999, self.value('bodyguard', self.current_bodyguard, 'SPoint'), self.original_value(Change('bodyguard', self.current_bodyguard, 'SPoint', 0)))),Change('bodyguard', self.current_bodyguard, 'BGLevels', growth.safe_preset(99999,mode))])

    def max_bodyguards(self):
        if self.require_save(): self.stage_many(self.guard_growth_changes())

    @experimental_session
    def guard_growth_changes(self):
        return [Change('bodyguard',index,field,value) for index in range(len(self.document.records('GuardDataArray')))
                if guard_editor.team_state(self.document,index)['growth_editable']
                for field,value in [('SPoint',max(99999,self.value('bodyguard',index,'SPoint'),self.original_value(Change('bodyguard',index,'SPoint',0)))),('BGLevels',growth.safe_preset())]]

    @experimental_session
    def apply_guard_equipment(self):
        if not self.selected_ok(self.bodyguards): return
        try:
            item = self.guard_equip_item_choices[self.guard_equip_item.get()]
            state = guard_editor.team_state(self.document, self.current_bodyguard, list(self.changes.values()))
            weapons = state['MemberWeapon'].copy()
            changes=[Change('bodyguard',self.current_bodyguard,'MemberItem',item)]
            if len(weapons)==10:
                for family, variable in self.guard_equip_weapons.items(): weapons[family] = self.guard_equip_weapon_choices[family][variable.get()]
                changes.append(Change('bodyguard',self.current_bodyguard,'MemberWeapon',weapons))
            self.stage_many(changes)
        except (ValueError, KeyError) as error: messagebox.showerror('Cannot Apply Equipment', str(error))

    @experimental_session
    def equip_best_guard_weapons(self):
        if not self.selected_ok(self.bodyguards): return
        try:
            state = guard_editor.team_state(self.document, self.current_bodyguard, list(self.changes.values()))
            weapons = state['MemberWeapon'].copy()
            if len(weapons)!=10:raise ValueError('This team has an unfamiliar weapon-choice layout. Its references are view-only.')
            weapons[:5] = guard_editor.best_weapon_refs(self.document, list(self.changes.values()))
            self.stage_many([Change('bodyguard',self.current_bodyguard,'MemberWeapon',weapons)])
        except ValueError as error: messagebox.showerror('Cannot Equip Weapons',str(error))

    @experimental_session
    def apply_guard_item(self):
        if not self.selected_ok(self.guard_items): return
        try:
            index = self.current_guard_item; metadata = GUARD_ITEMS[index]
            owned = self.guard_item_owned.get()
            if not owned:
                for team in range(len(self.document.records('GuardDataArray'))):
                    if guard_editor.team_state(self.document,team,list(self.changes.values()))['MemberItem']==index:
                        raise ValueError('This item is equipped by a bodyguard team. Choose another item or None on Team Equipment first.')
            changes = [Change('guard_item',index,'Owned',owned)]
            if owned and metadata['kind']=='normal':
                value = int(self.guard_item_value.get())
                original=guard_editor.item_state(self.document)[index]
                unchanged=original['owned'] and value==original['value'] and value>0
                if not within_numeric_limits(value, 1, metadata['max_value'], storage_maximum=INT32_MAX) and not unchanged:
                    raise ValueError(f'{metadata["name"]}: supported 1–{metadata["max_value"]}; experimental maximum {INT32_MAX:,}, or its unchanged saved value.')
                changes.append(Change('guard_item',index,'Value',value))
            self.stage_many(changes)
        except ValueError as error: messagebox.showerror('Invalid BG Item',str(error))

    @experimental_session
    def guard_item_changes(self, maximum=False):
        changes = []
        for index, metadata in GUARD_ITEMS.items():
            state=guard_editor.item_state(self.document).get(index)
            if state is None or not state['editable']:continue
            changes.append(Change('guard_item',index,'Owned',True))
            if maximum and metadata['kind']=='normal': changes.append(Change('guard_item',index,'Value',guard_editor.max_item_value(self.document,index,list(self.changes.values()))))
        return changes

    def unlock_guard_items(self):
        if self.require_save(): self.stage_many(self.guard_item_changes())

    def max_guard_items(self):
        if self.require_save(): self.stage_many(self.guard_item_changes(True))

    def guard_weapon_changes(self, maximum=False):
        changes = []
        for index in GUARD_WEAPONS:
            changes.append(Change('guard_weapon',index,'Owned',True))
            if maximum: changes.append(Change('guard_weapon',index,'MaxBonuses',True))
        return changes

    def unlock_guard_weapon(self):
        if self.selected_ok(self.guard_weapons): self.stage_many([Change('guard_weapon',self.current_guard_weapon,'Owned',True)])

    def max_guard_weapon(self):
        if self.selected_ok(self.guard_weapons): self.stage_many([Change('guard_weapon',self.current_guard_weapon,'Owned',True),Change('guard_weapon',self.current_guard_weapon,'MaxBonuses',True)])

    def unlock_guard_weapons(self):
        if self.require_save(): self.stage_many(self.guard_weapon_changes())

    def max_guard_weapons(self):
        if self.require_save(): self.stage_many(self.guard_weapon_changes(True))

    def unlock(self, field, count):
        if self.require_save(): self.stage_many([Change('unlock', index, field, True) for index in range(min(count,len(self.document.properties[field]['value']['values'])))])

    def weapon_changes(self):
        return [Change('unique_weapon', weapon_id, 'Owned', True) for weapon_id in UNIQUE_WEAPONS]

    def unlock_selected_weapon(self):
        if not self.selected_ok(self.weapons): return
        selected = self.weapons.selection()[0]
        if selected.startswith('unique:'): self.stage_many([Change('unique_weapon', int(selected.split(':')[1]), 'Owned', True)])
        else: messagebox.showinfo('Select a Unique Weapon', 'Select a 4th or 5th weapon row to unlock it.')

    def unlock_weapons(self):
        if self.require_save(): self.stage_many(self.weapon_changes())

    def collect_all_weapons(self):
        if self.require_save():self.stage_many(weapon_collection.all_collection_changes())

    def unlock_tactics_costumes(self):
        if self.require_save():self.stage_many(weapon_collection.tactics_costume_changes())

    def unlock_side_stories(self):
        if self.require_save():self.stage_many(progression.side_story_changes())

    def complete_selected_musou(self):
        if not self.require_save():return
        if not messagebox.askyesno('Mark Musou Cleared','Mark this officer’s Musou story cleared and advance its saved progress? First clears add 3 Huanglong Elixirs. This is separate from max stats.'):return
        try:self.stage_many(progression.musou_clear_changes(self.document,self.story_officer_choices[self.story_officer.get()]))
        except (ValueError,KeyError) as error:messagebox.showerror('Cannot Mark Story Cleared',str(error))

    def complete_all_musou(self):
        if not self.require_save():return
        if not messagebox.askyesno('Mark All Musou Cleared','Mark all supported officer stories cleared and advance their saved progress? First clears add 3 Huanglong Elixirs each. Existing saved runs remain.'):return
        try:self.stage_many(progression.musou_clear_changes(self.document))
        except ValueError as error:messagebox.showerror('Cannot Mark Stories Cleared',str(error))

    @experimental_session
    def grind_changes(self):
        changes = [Change('officer', index, field, self.officer_maximum(index, field)) for index in self.officer_indices() for field in CAPS]
        for index, item in self.editable_item_rows():
            cap = self.item_cap(index)
            if item['kind'] == 'rare': changes.append(Change('item', index, 'Owned', True))
            elif cap is not None: changes.extend([Change('item', index, 'Owned', True), Change('item', index, 'Value', weapon_editor.max_item_value(self.document,index,list(self.changes.values())))])
        changes.extend(self.guard_growth_changes())
        changes.extend(self.guard_item_changes(True))
        changes.extend(self.guard_weapon_changes(True))
        changes.extend(self.weapon_changes())
        return changes

    def remove_grind(self):
        if self.require_save(): self.stage_many(self.grind_changes())

    @experimental_session
    def unlock_everything(self):
        if self.require_save():
            changes = self.grind_changes()
            changes.extend(self.guard_customization_changes())
            changes.extend(progression.side_story_changes())
            changes.extend(weapon_collection.all_collection_changes())
            changes.extend(weapon_collection.tactics_costume_changes())
            state=collections.collection_state(self.document)
            if state['music']['editable']:changes.extend(collections.unlock_music_changes(self.document))
            if state['movies']['editable']:changes.extend(collections.unlock_movie_changes(self.document))
            changes.extend(Change('unlock', index, field, True) for field, count in [('CanUseCharaArray', 42), ('CanUseScenarioArray', 108)] for index in range(min(count,len(self.document.properties[field]['value']['values']))))
            self.stage_many(changes)

    @experimental_session
    def undo(self):
        if not self.history:
            return
        previous = self.history[-1]
        try:
            save_writer.plan_changes(self.document, list(previous.values()))
        except (ValueError, KeyError, TypeError, IndexError) as error:
            if not experimental_enabled():
                messagebox.showinfo('Experimental Changes in Undo',
                                    'Enable experimental editing before restoring these historical changes. '
                                    'Your current changes and Undo history are preserved.\n\n' + str(error))
            else:
                messagebox.showerror('Cannot Undo', str(error))
            return
        self.changes = self.history.pop()
        self.refresh()

    def discard(self):
        if self.changes and self.dirty_ok(): self.changes, self.history = {}, []; self.refresh()

    def review(self):
        if not self.require_save(): return
        window = tk.Toplevel(self.root); window.title('Review Pending Changes'); window.geometry('900x520')
        ttk.Label(window, text=f'{len(self.changes)} pending changes. Save to write them into your copy.', padding=12).pack(fill='x')
        if self.experimental_mode.get():
            ttk.Label(window, text='Experimental editing active. Above-max values may break your save or game. Signed 32-bit numeric storage maximum: 2,147,483,647.', wraplength=850, padding=(12, 0, 12, 8)).pack(fill='x')
        pages = ttk.Notebook(window)
        pages.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        changes_page = ttk.Frame(pages, padding=8)
        pages.add(changes_page, text='Pending Changes')
        tree = self.make_tree(changes_page, [('field', 'Setting'), ('before', 'Saved'), ('after', 'Pending')],
                              'Officer / item / content', [310, 165, 155, 155])
        for change in self.changes.values():
            label, fieldname, before, after = self.review_change(change)
            tree.insert('', 'end', text=label, values=(fieldname, before, after))
        if not self.changes:
            ttk.Label(changes_page, text='No pending changes. Your copy has not been edited.').pack(anchor='w', pady=(8, 0))
        if self.document.compatibility_warnings:
            notes_page = ttk.Frame(pages, padding=8)
            pages.add(notes_page, text=f'Saved-value Notes ({len(self.document.compatibility_warnings)})')
            ttk.Label(notes_page, text='These notes describe values already in your save. They are preserved unless you apply a supported change.',
                      wraplength=800).pack(fill='x', pady=(0, 8))
            text = tk.Text(notes_page, wrap='word', padx=10, pady=8, background='#ffffff', relief='flat')
            scroll = ttk.Scrollbar(notes_page, orient='vertical', command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right', fill='y')
            text.pack(fill='both', expand=True)
            for warning in self.document.compatibility_warnings:
                text.insert('end', f'{warning}\n\n')
            text.configure(state='disabled')
        self.theme_widgets(window)

    @experimental_session
    def review_change(self, change):
        before, after = self.original_value(change), change.value
        labels = {'BGLevels':'Growth (Life / Attack / Defense / Count / Bow / AI)','MemberItem':'Equipped item','MemberWeapon':'Equipped weapon families','MaxBonuses':'Legal maximum bonuses','Skills':'Copy bonuses','Owned':'Owned','Value':'Value'}
        fieldname = LABELS.get(change.field,labels.get(change.field,change.field))
        if change.category=='officer': label = NAMES.get(str(change.index),f'Officer {change.index}')
        elif change.category=='item': label = ITEMS[change.index]['name']
        elif change.category=='unique_weapon': label = UNIQUE_WEAPONS[change.index]['weapon_name']
        elif change.category in collections.CATEGORIES:
            family='music' if change.field=='Music' else 'movies'
            row=next(row for row in collections.collection_state(self.document)[family]['rows'] if row['id']==change.index)
            label=row['name'];fieldname='Collection available'
        elif change.category in musou_slots.CATEGORIES:
            row=next(row for row in musou_slots.slot_state(self.document)['slots'] if row['index']==change.index)
            label=f'Musou save slot {change.index+1} ({row["officer_name"]})';fieldname='Remove saved run'
        elif change.category in customization.CATEGORIES:
            family='appearances' if change.field=='AppearanceUnlocked' else 'outfits'
            row=next(row for row in customization.customization_state(self.document)[family] if row['id']==change.index)
            label='Bodyguard '+row['name'];fieldname='Available'
        elif change.category in weapon_collection.CATEGORIES:
            label='Weapon gallery' if change.field=='CollectAll' else 'Lu Bu / Sun Shangxiang'
            fieldname='Complete collection' if change.field=='CollectAll' else 'Tactics costumes'
        elif change.category in progression.CATEGORIES:
            if change.field == 'HuanglongElixirs':
                label, fieldname = 'Huanglong Elixirs', 'Final balance'
            else:
                label=progression.ROUTES[change.index]['officer'] if change.field=='MusouCleared' else progression.SIDE_STORIES[change.index]['name']
                fieldname='Musou cleared / route progress / first-clear Elixirs' if change.field=='MusouCleared' else 'Side story and Free Mode available'
        elif change.category in weapon_editor.CATEGORIES:
            row = weapon_editor.state(self.document,change.index,list(self.changes.values()))
            label = f'{row["metadata"].get("name") or row["metadata"].get("weapon_name") or "Weapon"} copy ID {change.index}'
            if change.category=='weapon_roll':before,after=self.officer_bonus_text(before),self.officer_bonus_text(after)
            else:
                def element_text(mask):return ', '.join(label for label,bit in weapon_editor.ELEMENTS.items() if bit and mask & bit) or 'None'
                before,after=element_text(before),element_text(after);fieldname='Element'
        elif change.category=='guard_item': label = GUARD_ITEMS[change.index]['name']
        elif change.category=='guard_weapon': label = GUARD_WEAPONS[change.index]['name']
        elif change.category=='guard_weapon_slot':
            row = guard_editor.weapon_state(self.document,list(self.changes.values()))[change.index]
            label = f'{GUARD_WEAPONS[row["weapon_id"]]["name"]} copy {change.index+1}'
            before, after = self.guard_bonus_text(before),self.guard_bonus_text(after)
        elif change.category=='bodyguard':
            label = f'Team {change.index+1}'
            if change.field=='MemberItem':
                before = GUARD_ITEMS[before]['name'] if before is not None else 'None'; after = GUARD_ITEMS[after]['name'] if after is not None else 'None'
            elif change.field=='MemberWeapon':
                oldpool,newpool = guard_editor.weapon_state(self.document,[]),guard_editor.weapon_state(self.document,list(self.changes.values()))
                def names(refs,pool):
                    result=[]
                    for ref in refs[:5]:
                        row=next((row for row in pool if row['data_id']==ref and row['weapon_id'] is not None),None)
                        result.append(GUARD_WEAPONS[row['weapon_id']]['name'] if row else 'None')
                    return ', '.join(result)
                before, after = names(before,oldpool),names(after,newpool)
        else:
            label = f'Playable {"officer" if change.field=="CanUseCharaArray" else "stage"} {change.index+1}'; fieldname='Available'
        if change.field=='MaxBonuses': before,after='Current bonuses','Verified maximum profile'
        if isinstance(before,bool): before='Yes' if before else 'No'
        if isinstance(after,bool): after='Yes' if after else 'No'
        return label,fieldname,before,after

    def make_backup(self):
        if not self.require_save(): return
        try:
            self.backup = save_writer.backup_save(self.document); self.update_paths()
            self.status.set('Opened-copy backup created. Pending changes are kept in the editor.')
        except Exception as error: messagebox.showerror('Backup Failed', str(error))

    @experimental_session
    def save_to(self, path, overwrite=False):
        if self.experimental_mode.get() and self.changes:
            if not messagebox.askyesno('Save Experimental Changes', EXPERIMENTAL_WARNING + '\n\nWrite this edited copy?'):
                return
        self.set_loaded(False)
        self.status.set('Saving and validating the edited copy…')
        self.root.configure(cursor='wait' if sys.platform == 'win32' else 'watch')
        self.root.update_idletasks()
        try:
            try:
                saved, audit = save_writer.write_save(self.document, Path(path), list(self.changes.values()), overwrite)
            except Exception as error:
                self.status.set('Save failed. Pending changes remain available to review.')
                messagebox.showerror('Cannot Save', str(error))
                return
            self.changes, self.history = {}, []
            try:
                self.document = read_save(saved)
                self.update_paths(); self.refresh()
            except Exception as error:
                self.document = None
                self.filename.set(f'Saved copy: {saved}')
                self.status.set('Saved, but could not reopen the output. Use Open Save Copy to reopen it manually.')
                messagebox.showwarning('Save Written', f'The edited copy and change report were saved. The editor could not reopen the output.\n\n{saved}\n\n{error}')
                return
            self.status.set(f'Saved {len(audit["plaintext_changes"])} changed fields. A byte-change report was created beside the save.')
        finally:
            self.root.configure(cursor='')
            self.set_loaded(self.document is not None)

    def save_as(self):
        if not self.require_save(): return
        path = filedialog.asksaveasfilename(title='Save Edited Copy', defaultextension='.sav', initialdir=self.document.source.parent, initialfile='GameStatusData.edited.sav', filetypes=[('Game save', '*.sav')], confirmoverwrite=False)
        if not path: return
        try: destination = safe_path(Path(path))
        except Exception as error:
            messagebox.showerror('Cannot Save', str(error)); return
        exists = destination.exists()
        if exists and not messagebox.askyesno('Replace Existing Copy', f'Replace this existing save copy?\n\n{destination}\n\nAn untouched backup of that file will be created first.'): return
        self.save_to(destination, exists)

    def save_changes(self):
        if self.require_save() and messagebox.askyesno('Replace Opened Copy', f'Write {len(self.changes)} pending changes into this opened copy?\n\n{self.document.source}\n\nAn additional untouched backup will be created first.'): self.save_to(self.document.source, True)

    def restore(self):
        path = filedialog.askopenfilename(title='Choose Editor Backup', initialdir=self.backup.parent if self.backup else Path.home(), filetypes=[('Save backup', '*.sav')])
        if not path: return
        destination = filedialog.asksaveasfilename(title='Restore to a New Copy', defaultextension='.sav', initialfile='GameStatusData.restored.sav')
        if not destination: return
        try:
            save_writer.restore_backup(Path(path), Path(destination)); self.status.set('Backup restored to a new copy. Use Open Save Copy to inspect it.')
        except Exception as error: messagebox.showerror('Cannot Restore', str(error))

    def close(self):
        if self.dirty_ok(): self.root.destroy()


def main():
    if not any(flag in sys.argv for flag in ('--smoke-test', '--self-test', '--compatibility-test')):
        from koei_editor.application import main as application_main
        return application_main()
    root = tk.Tk()
    if any(flag in sys.argv for flag in ('--smoke-test','--self-test','--compatibility-test')): root.withdraw()
    editor = Editor(root, persist_preferences=False)
    if '--self-test' in sys.argv or '--compatibility-test' in sys.argv:
        compatibility='--compatibility-test' in sys.argv
        index = sys.argv.index('--compatibility-test' if compatibility else '--self-test')
        arguments = sys.argv[index + 1:]
        if len(arguments) != 2:
            root.destroy(); raise SystemExit(2)
        try:
            if compatibility:from koei_editor.games.dw3.compatibility_self_test import run
            else:from koei_editor.app_self_test import run
            result = run(editor, Path(arguments[0]), Path(arguments[1]))
        except Exception:
            raise SystemExit(1)
        finally:
            root.destroy()
        raise SystemExit(1 if result is False else 0)
    elif '--smoke-test' in sys.argv:
        root.update_idletasks(); root.destroy(); print('GUI widgets initialized successfully.')
    else: root.mainloop()


if __name__ == '__main__': main()

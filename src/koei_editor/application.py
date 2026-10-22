"""Universal Dynasty Warriors application shell, with retained game sessions."""
import argparse
import sys
from dataclasses import replace
import tkinter as tk
from tkinter import ttk
from koei_editor.shared.appearance import Appearance, THEMES
from koei_editor.game_registry import GAMES, ALL_ADAPTERS, get_game
from koei_editor.supported_games import SUPPORTED_GAMES
from koei_editor.shared.library_catalog import ALL_PLATFORMS, ALL_SERIES, LibraryCatalog, matching_games, series_for
import koei_editor.shared.preferences as preferences
from koei_editor.shared import shell_preferences
from koei_editor.shared.localization import CATALOGS, LANGUAGES, translate
from koei_editor.shared.command_palette import CommandEntry, CommandPalette

VERSION = '3.1'


class Application(Appearance):
    def __init__(self, root, preferences_path=None, persist_preferences=True):
        self.root = root
        self.preferences_path = preferences_path
        self._persist_theme = persist_preferences
        self.shell_preferences_path = shell_preferences.shell_path(preferences_path)
        self.shell_settings = shell_preferences.load(self.shell_preferences_path)
        self.language = self.shell_settings.language
        self.command_palette = None
        self.help_center = None
        self._translated_widgets = []
        self._search_after = None
        self._navigation_after = None
        self._editor_width_after = None
        self._shell_controls_expanded = False
        initial_theme = preferences.load_theme(preferences_path)
        self.style = ttk.Style(root)
        self.style.theme_use('clam')
        self.theme_name = tk.StringVar(root, value=initial_theme)
        self.sessions = {}
        self.active_game = None
        self.converter = None
        self.comparison = None
        self.batch = None
        self.save_library = None
        self.mod_manager = None
        self.game_configuration = None
        self.editing_presets = None
        self.research_lab = None
        self.research_import = None
        self.asset_explorer = None
        self.workflow_builder = None
        self.emulator_hub = None
        self.mod_workshop_window = None
        self.nexus_mods = None
        # A Mod Manager integration may attach its typed Nexus handoff here.
        self.mod_manager_download_handoff = None
        self.troubleshooting = None
        root.title(f'Universal Koei Tecmo Save Editor — v{VERSION}')
        root.geometry('1180x930')
        root.minsize(780, 680)
        self._owned_minimum = (780, 680)
        self.tools_menu_bar = tk.Menu(root)
        self.editing_tools_menu = tk.Menu(self.tools_menu_bar, tearoff=False)
        self._editing_tools_menu_commands = {}
        self._add_editing_tools_menu_command('editing_presets', self.show_editing_presets)
        self._add_editing_tools_menu_command('transfer', self.show_transfer)
        self._add_editing_tools_menu_command('game_configuration', self.show_game_configuration)
        self.editing_tools_menu.add_separator()
        self._add_editing_tools_menu_command('mod_manager', self.show_mod_manager)
        self.editing_tools_menu.add_separator()
        self._add_editing_tools_menu_command('research_lab', self.show_research_lab)
        self._add_editing_tools_menu_command('research_import', self.show_research_import)
        self._add_editing_tools_menu_command('nexus_mods', self.show_nexus_mods)
        self._add_editing_tools_menu_command('emulator_hub', self.show_emulator_hub)
        self._add_editing_tools_menu_command('asset_explorer', self.show_asset_explorer)
        self.tools_menu_bar.add_cascade(label=self.tr('editing_and_research'), menu=self.editing_tools_menu)
        root.configure(menu=self.tools_menu_bar)
        self.apply_theme(initial_theme)
        root.option_add('*Font', (self.font_family, 10))
        top = ttk.Frame(root, padding=(18, 10))
        top.pack(fill='x')
        self._shell_top = top
        top.columnconfigure(0, weight=1)
        self.command_button = self._translated(ttk.Button(top, command=self.open_command_palette), 'commands')
        self.command_button.grid(row=0, column=0, sticky='ew', padx=(0, 16))
        settings = ttk.Frame(top)
        settings.grid(row=0, column=1, sticky='e')
        self._shell_settings_frame = settings
        for column, key in enumerate(('appearance', 'language', 'text_size')):
            self._translated(ttk.Label(settings, style='Muted.TLabel'), key).grid(row=0, column=column, sticky='w')
        self.theme_selector = ttk.Combobox(settings, values=tuple(THEMES), textvariable=self.theme_name,
                                          state='readonly', width=7)
        self.theme_selector.grid(row=1, column=0)
        self.theme_selector.bind('<<ComboboxSelected>>', lambda _event: self.apply_theme(self.theme_name.get()))
        self.language_choice = tk.StringVar(root, value=LANGUAGES[self.language])
        self.language_selector = ttk.Combobox(settings, values=tuple(LANGUAGES.values()),
                                              textvariable=self.language_choice, state='readonly', width=8)
        self.language_selector.grid(row=1, column=1, padx=8)
        self.language_selector.bind('<<ComboboxSelected>>', self.change_language)
        self.text_size_choice = tk.StringVar(root, value=f'{self.shell_settings.text_size}%')
        self.text_size_selector = ttk.Combobox(settings, values=('100%', '120%', '140%'),
                                              textvariable=self.text_size_choice, state='readonly', width=5)
        self.text_size_selector.grid(row=1, column=2)
        self.text_size_selector.bind('<<ComboboxSelected>>', self.change_text_size)
        self.navigation = ttk.Frame(top)
        self.navigation.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self.home_button = self._translated(ttk.Button(self.navigation, command=self.show_library), 'library')
        self.converter_button = self._translated(ttk.Button(self.navigation, command=self.show_converter), 'converter')
        self.compare_button = self._translated(ttk.Button(self.navigation, command=self.show_comparison), 'comparison')
        self.batch_button = self._translated(ttk.Button(self.navigation, command=self.show_batch), 'batch')
        self.save_library_button = self._translated(ttk.Button(self.navigation, command=self.show_save_library), 'save_library')
        self.troubleshooting_button = self._translated(
            ttk.Button(self.navigation, command=self.show_troubleshooting), 'troubleshooting')
        self.help_button = self._translated(ttk.Menubutton(self.navigation), 'help')
        self.help_menu = tk.Menu(self.help_button, tearoff=False)
        self.help_button.configure(menu=self.help_menu)
        self._navigation_buttons = (self.home_button, self.converter_button, self.compare_button,
                                    self.batch_button, self.save_library_button,
                                    self.troubleshooting_button, self.help_button)
        self.navigation.bind('<Configure>', self._schedule_navigation)
        self._layout_navigation()
        location = ttk.Frame(top)
        self._shell_location = location
        location.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        self.breadcrumb = tk.StringVar(root, value=self.tr('choose'))
        self.breadcrumb_label = ttk.Label(location, textvariable=self.breadcrumb, style='Muted.TLabel', width=1)
        self.breadcrumb_label.pack(side='left', fill='x', expand=True)
        self.author_label = ttk.Label(location, text='Made by Mexican', style='Muted.TLabel')
        self.author_label.pack(side='right')
        self.compact_home_button = ttk.Button(top, command=self.show_library)
        self.compact_help_button = ttk.Button(top, command=self.show_help)
        self.shell_controls_button = ttk.Button(top, command=self._toggle_shell_controls)
        self.breadcrumb.trace_add('write', self._workspace_changed)
        self._rebuild_help_menu()
        top.bind('<Configure>', self._schedule_navigation)
        root.bind('<Configure>', lambda event: self._schedule_navigation()
                  if event.widget is root else None, add='+')
        root.bind('<Destroy>', self._cancel_shell_callbacks, add='+')
        self.session_bar = ttk.Frame(root, padding=(18, 0, 18, 8))
        self.session_caption = tk.StringVar(root, value='Open editors')
        self.session_caption_label = ttk.Label(self.session_bar, textvariable=self.session_caption, style='Muted.TLabel')
        self.session_caption_label.pack(side='left', padx=(0, 10))
        self.session_choice = tk.StringVar(root)
        self.session_selector = ttk.Combobox(self.session_bar, textvariable=self.session_choice, state='readonly', width=1)
        self.session_selector.pack(side='left', fill='x', expand=True)
        self.session_selector.bind('<<ComboboxSelected>>', self.resume_session)
        self._session_labels = {}
        self._session_order = []
        self.workspace = ttk.Frame(root)
        self.workspace.pack(fill='both', expand=True)
        self.library = ttk.Frame(self.workspace, padding=(38, 20))
        self.library.pack(fill='both', expand=True)
        ttk.Label(self.library, text='KOEI TECMO', font=(self.font_family, 27, 'bold')).pack(anchor='w', pady=(8, 0))
        ttk.Label(self.library, text='SAVE EDITOR', font=(self.font_family, 17), style='Muted.TLabel').pack(anchor='w')
        self.library_games = tuple(GAMES)
        self._library_catalog = LibraryCatalog(self.library_games)
        platforms = tuple(dict.fromkeys(game.platform for game in self.library_games))
        platform_bar = ttk.Frame(self.library)
        platform_bar.pack(fill='x', pady=(12, 12))
        platform_bar.columnconfigure(0, weight=1)
        platform_bar.columnconfigure(1, weight=1)
        self._translated(ttk.Label(platform_bar, font=(self.font_family, 12)), 'platform').grid(row=0, column=0, sticky='w')
        self.platform_choice = tk.StringVar(root, value='Windows PC')
        self.platform_selector = ttk.Combobox(platform_bar, textvariable=self.platform_choice,
                                             values=(ALL_PLATFORMS,) + platforms, state='readonly', width=20)
        self.platform_selector.grid(row=1, column=0, sticky='ew', padx=(0, 16), pady=(4, 0))
        self.platform_selector.bind('<<ComboboxSelected>>', self.show_platform)
        self._translated(ttk.Label(platform_bar, style='Muted.TLabel'), 'series').grid(row=0, column=1, sticky='w')
        self.series_choice = tk.StringVar(root, value=ALL_SERIES)
        self.series_selector = ttk.Combobox(platform_bar, textvariable=self.series_choice,
                                             values=(ALL_SERIES,) + tuple(sorted({series_for(game) for game in self.library_games})),
                                             state='readonly', width=24)
        self.series_selector.grid(row=1, column=1, sticky='ew', pady=(4, 0))
        self.series_selector.bind('<<ComboboxSelected>>', self.show_platform)
        search_bar = ttk.Frame(self.library)
        search_bar.pack(fill='x', pady=(0, 10))
        self._translated(ttk.Label(search_bar, style='Muted.TLabel'), 'find').pack(side='left', padx=(0, 12))
        self.library_search = tk.StringVar(root)
        self.library_search_entry = ttk.Entry(search_bar, textvariable=self.library_search)
        self.library_search_entry.pack(side='left', fill='x', expand=True)
        self.library_search_entry.bind('<Return>', self.open_library_match)
        self.library_search_entry.bind('<Escape>', self.clear_library_filters)
        self._translated(ttk.Button(search_bar, command=self.clear_library_filters), 'clear').pack(side='left', padx=10)
        self.compact_library = tk.BooleanVar(root, value=False)
        self.compact_toggle = ttk.Checkbutton(
            search_bar, text=self.tr('compact'), style='LibraryDensity.TCheckbutton',
            variable=self.compact_library, command=self.update_library_density)
        self.compact_toggle.pack(side='right', padx=(8, 0))
        self._translated_widgets.append((self.compact_toggle, 'compact'))
        self.library_hint = tk.StringVar(root)
        self.library_hint_label = ttk.Label(self.library, textvariable=self.library_hint,
                                            style='Muted.TLabel', wraplength=1000)
        self.library_hint_label.pack(anchor='w', pady=(0, 18))
        # Reserve the footer before the expanding cards so its controls remain
        # reachable at the minimum window size.
        self.library_footer = ttk.Frame(self.library)
        self.library_footer.pack(side='bottom', fill='x', pady=(16, 0))
        self.library_footer_label = self._translated(ttk.Label(self.library_footer, style='Muted.TLabel', wraplength=1000), 'footer')
        self.library_footer_label.pack(anchor='w')
        self.library.bind('<Configure>', lambda event: [widget.configure(wraplength=max(200, event.width - 76))
                                                       for widget in (self.library_hint_label, self.library_footer_label)])
        footer_buttons = ttk.Frame(self.library_footer)
        footer_buttons.pack(fill='x', pady=(12, 0))
        self.contact_button = self._translated(ttk.Button(footer_buttons, command=self.contact), 'contact')
        self.contact_button.pack(side='left')
        self.workflow_button = self._translated(ttk.Button(footer_buttons, command=self.show_workflow_builder), 'workflow_builder')
        self.workflow_button.pack(side='left', padx=10)
        self.mod_workshop_button = self._translated(
            ttk.Button(footer_buttons, command=self.show_mod_workshop), 'mod_workshop'
        )
        self.mod_workshop_button.pack(side='left', padx=(8, 0))
        cards = ttk.Frame(self.library)
        cards.pack(fill='both', expand=True)
        self.platform_frames = {platform: ttk.Frame(cards) for platform in (ALL_PLATFORMS,) + platforms}
        self.platform_canvases = {}
        self._library_contents = {}
        self._library_windows = {}
        self._library_columns = {}
        for platform, frame in self.platform_frames.items():
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            canvas = tk.Canvas(frame, width=1, height=1, highlightthickness=0,
                               background=THEMES[self.theme_name.get()]['background'])
            canvas.grid(row=0, column=0, sticky='nsew')
            scrollbar = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
            if platform == ALL_PLATFORMS or sum(game.platform == platform for game in self.library_games) > 4:
                scrollbar.grid(row=0, column=1, sticky='ns', padx=(8, 0))
            canvas.configure(yscrollcommand=scrollbar.set)
            content = ttk.Frame(canvas)
            self.platform_canvases[platform] = canvas
            self._library_contents[platform] = content
            self._library_windows[platform] = canvas.create_window(0, 0, anchor='nw', window=content)
            canvas.bind('<Configure>', lambda _event, name=platform: self.resize_library_cards(name))
            content.bind('<Configure>', lambda _event, name=platform: self.resize_library_cards(name))
        self.game_buttons = {}
        self.library_cards = {}
        self.library_buttons = {}
        self.library_banners = {}
        self.library_matches = ()
        self._library_filter_key = None
        self.library_empty = {scope: self._translated(ttk.Label(content, style='Muted.TLabel'), 'empty')
                              for scope, content in self._library_contents.items()}
        for platform in platforms:
            self.create_library_cards(platform)
        self.library_search.trace_add('write', self.schedule_library_search)
        root.bind('<Control-f>', self.focus_library_search, add='+')
        root.bind('<Control-k>', self.open_command_palette, add='+')
        root.bind('<Control-K>', self.open_command_palette, add='+')
        root.bind('<F1>', lambda _event: self.show_help(), add='+')
        self.show_platform()
        root.bind('<MouseWheel>', self.scroll_library, add='+')
        root.bind('<Button-4>', lambda event: self.scroll_library(event, -1), add='+')
        root.bind('<Button-5>', lambda event: self.scroll_library(event, 1), add='+')
        for shortcut, method in (('<Control-o>', 'open'), ('<Control-s>', 'save_changes'),
                                 ('<Control-Shift-S>', 'save_as'), ('<Control-z>', 'undo'), ('<Control-r>', 'review')):
            root.bind(shortcut, lambda _event, name=method: self.dispatch(name))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self._apply_text_size()

    def tr(self, key, **values):
        return translate(key, self.language, **values)

    def _translated(self, widget, key):
        widget.configure(text=self.tr(key))
        self._translated_widgets.append((widget, key))
        return widget

    def _save_shell_settings(self):
        if self._persist_theme:
            shell_preferences.save(self.shell_settings, self.shell_preferences_path)

    def _remember_workspace(self, command_id):
        updated = shell_preferences.remember(self.shell_settings, command_id)
        if updated != self.shell_settings:
            self.shell_settings = updated
            self._save_shell_settings()

    def _toggle_favorite(self, command_id):
        self.shell_settings = shell_preferences.toggle_favorite(self.shell_settings, command_id)
        self._save_shell_settings()
        return self.shell_settings.favorites

    def change_language(self, _event=None):
        self.language = next(key for key, value in LANGUAGES.items() if value == self.language_choice.get())
        self.shell_settings = replace(self.shell_settings, language=self.language)
        for widget, key in self._translated_widgets:
            widget.configure(text=self.tr(key))
        self._rebuild_help_menu()
        self.tools_menu_bar.entryconfigure('end', label=self.tr('editing_and_research'))
        self._refresh_editing_menu_labels()
        if self.nexus_mods is not None:
            self.nexus_mods.set_language(self.language)
        self.refresh_sessions()
        self.show_platform()
        if self.active_game is None:
            visible = next((key for key in ('converter', 'comparison', 'batch', 'save_library',
                                            'troubleshooting', 'game_configuration', 'editing_presets',
                                            'mod_manager', 'research_lab', 'research_import', 'nexus_mods',
                                            'emulator_hub', 'asset_explorer', 'workflow_builder', 'game_hub')
                            if getattr(self, key, None) is not None
                            and getattr(self, key).frame.winfo_manager()), None)
            if visible is None and self.help_center is not None and self.help_center.frame.winfo_manager():
                visible = self.help_center.selected_tab()
            self.breadcrumb.set(self.tr(visible or 'choose'))
        if self.help_center is not None:
            set_language = getattr(self.help_center, 'set_language', None)
            if callable(set_language):
                set_language(self.language)
        if self.asset_explorer is not None:
            set_language = getattr(self.asset_explorer, 'set_language', None)
            if callable(set_language):
                set_language(self.language)
        if self.troubleshooting is not None:
            self.troubleshooting.set_language(self.language)
        self._layout_navigation()
        self._save_shell_settings()

    def _refresh_editing_menu_labels(self):
        """Translate menu commands through their stable Tk command tokens."""
        commands = getattr(self, '_editing_tools_menu_commands', None)
        if commands:
            for key in commands:
                index = self._editing_tools_menu_index(key)
                if index is not None:
                    self.editing_tools_menu.entryconfigure(index, label=self.tr(key))
            return
        labels = {label: key for catalog in CATALOGS.values() for key, label in catalog.items()}
        last_index = self.editing_tools_menu.index('end')
        if last_index is None:
            return
        for index in range(last_index + 1):
            try:
                label = self.editing_tools_menu.entrycget(index, 'label')
            except tk.TclError:
                # Separators do not expose a label option on a real Tk menu.
                continue
            key = labels.get(label)
            if key is not None:
                self.editing_tools_menu.entryconfigure(index, label=self.tr(key))

    def change_text_size(self, _event=None):
        self.shell_settings = replace(self.shell_settings, text_size=int(self.text_size_choice.get().rstrip('%')))
        self._apply_text_size()
        self._layout_navigation()
        self._save_shell_settings()

    def _apply_text_size(self):
        # Keep Tk's native DPI scaling. Point fonts automatically respect it;
        # this additional preference is a user-selected readability adjustment.
        size = round(10 * self.shell_settings.text_size / 100)
        self.root.option_add('*Font', (self.font_family, size))
        self.style.configure('.', font=(self.font_family, size))
        self.style.configure('Treeview', rowheight=max(29, size * 2 + 9))
        for tool in self._tool_workspaces():
            set_text_size = getattr(tool, 'set_text_size', None)
            if callable(set_text_size):
                set_text_size(size, self.font_family)
        self._schedule_editor_width()

    def _workspace_changed(self, *_args):
        self._schedule_navigation()
        self._schedule_editor_width()

    def _schedule_editor_width(self, _event=None):
        if self._editor_width_after is None:
            self._editor_width_after = self.root.after_idle(self._defer_editor_fit)

    def _defer_editor_fit(self):
        # Finish native style/geometry idle work before measuring, without
        # recursively draining the event loop from inside a layout callback.
        self._editor_width_after = self.root.after(0, self._fit_editor_actions)

    def _fit_editor_actions(self):
        try:
            self._measure_editor_actions()
        finally:
            self._editor_width_after = None

    def _measure_editor_actions(self):
        # Embedding bypasses the standalone editors' minimum sizes. Reserve
        # measured file-action and viewport space without overriding an explicit
        # caller-selected minimum (including compact dashboard qualification).
        if self.root.minsize() != self._owned_minimum:
            return
        width = 780
        height = 680
        if self.active_game is not None:
            editor = self.sessions[self.active_game][1]
            buttons = getattr(editor, 'save_buttons', ()) or getattr(editor, 'buttons', ())
            if buttons:
                row = buttons[0].master
                width = row.winfo_reqwidth()
                ancestor = row.master
                while ancestor is not self.root:
                    if 'padding' in ancestor.keys():
                        padding = tuple(ancestor.winfo_pixels(value) for value in
                                        self.root.tk.splitlist(ancestor.cget('padding')))
                        if padding:
                            width += padding[0] + (padding[2] if len(padding) > 2 else padding[0])
                    ancestor = ancestor.master
                width = max(780, width)
            fields = getattr(editor, 'fields', None)
            dashboard = getattr(getattr(editor, 'dashboard_view', None), 'canvas', None)
            # Native resize events update actual ancestor/viewport sizes at
            # different times. Requested sizes describe one consistent layout
            # and avoid feeding partially applied resizes into the minimum.
            if fields is not None and fields.winfo_viewable():
                # Seven styled rows plus their native heading remain usable
                # when platform DPI increases the surrounding controls.
                row_height = int(self.style.lookup(fields.cget('style') or 'Treeview', 'rowheight') or 29)
                viewport_height = max(224, fields.winfo_reqheight()
                                      + (7 - int(fields.cget('height'))) * row_height)
                height = max(height, self._viewport_minimum_height(fields, viewport_height))
            elif dashboard is not None and dashboard.winfo_viewable():
                height = max(height, self._viewport_minimum_height(dashboard, 150))
        minimum = (width, height)
        if minimum != self._owned_minimum:
            self._owned_minimum = minimum
            self.root.minsize(*minimum)

    def _viewport_minimum_height(self, viewport, height):
        child = viewport
        while child is not self.root:
            parent = child.master
            allocated = child.winfo_reqheight()
            if isinstance(parent, ttk.Notebook):
                allocated = max(parent.nametowidget(tab).winfo_reqheight()
                                for tab in parent.tabs() if parent.tab(tab, 'state') != 'hidden')
            elif child.winfo_manager() == 'grid':
                # Parallel scrolling panes can shrink with the viewport; their
                # larger requested rows must not become fixed toolbar space.
                allocated = max(widget.winfo_reqheight()
                                for widget in parent.grid_slaves(row=child.grid_info()['row']))
            height += parent.winfo_reqheight() - allocated
            child = parent
        return height

    def _schedule_navigation(self, _event=None):
        if self._navigation_after is None:
            self._navigation_after = self.root.after_idle(self._layout_navigation)

    def _toggle_shell_controls(self):
        self._shell_controls_expanded = not self._shell_controls_expanded
        self._layout_navigation()

    def _cancel_shell_callbacks(self, event):
        if event.widget is self.root:
            for name in ('_navigation_after', '_editor_width_after', '_search_after'):
                pending = getattr(self, name, None)
                if pending is not None:
                    self.root.after_cancel(pending)
                    setattr(self, name, None)

    def _set_active_game(self, game_id):
        self.active_game = game_id
        self._layout_navigation()

    def _layout_navigation(self):
        if self._navigation_after is not None:
            self.root.after_cancel(self._navigation_after)
        self._navigation_after = None
        self._schedule_editor_width()
        compact = (hasattr(self, 'shell_controls_button') and self.active_game is not None
                   and self.root.winfo_height() < 900)
        self._compact_editor_shell = compact
        self.command_button.configure(text=self.tr('commands_compact' if compact else 'commands'))
        if hasattr(self, '_shell_location'):
            self._shell_top.configure(padding=(12, 2) if compact else (18, 4))
            for column in range(5):
                self._shell_top.columnconfigure(column, weight=1 if column == (3 if compact else 0) else 0)
            if compact:
                self.command_button.grid(row=0, column=0, columnspan=1, padx=(0, 8))
                self.compact_home_button.configure(text=self.tr('library_short'))
                self.compact_home_button.grid(row=0, column=1, padx=(0, 8))
                self.compact_help_button.configure(text=self.tr('help'))
                self.compact_help_button.grid(row=0, column=2, padx=(0, 8))
                self.shell_controls_button.configure(text=self.tr(
                    'hide_shell_controls' if self._shell_controls_expanded else 'shell_controls'))
                self.shell_controls_button.grid(row=0, column=4, sticky='e')
                if hasattr(self, 'session_bar'):
                    self._layout_compact_sessions()
                if not self._shell_controls_expanded:
                    # Keep Home, Help, commands and retained sessions available;
                    # the full navigation/settings drawer stays one click away.
                    for widget in (self._shell_settings_frame, self.navigation, self._shell_location):
                        widget.grid_remove()
                    return
                self._shell_settings_frame.grid(row=1, column=0, columnspan=5, sticky='e', pady=(6, 0))
                self.navigation.grid(row=2, column=0, columnspan=5, sticky='ew', pady=(6, 0))
                self._shell_location.grid(row=3, column=0, columnspan=5, sticky='ew', pady=(8, 0))
            else:
                self.compact_home_button.grid_remove()
                self.compact_help_button.grid_remove()
                self.shell_controls_button.grid_remove()
                if hasattr(self, 'session_bar'):
                    self.session_bar.grid_forget()
                    self.session_bar.configure(padding=(18, 0, 18, 8))
                    self.session_selector.configure(width=1)
                    self.session_caption_label.pack(side='left', padx=(0, 10), before=self.session_selector)
                needed = self.command_button.winfo_reqwidth() + self._shell_settings_frame.winfo_reqwidth() + 16
                stacked = self._shell_top.winfo_width() < needed
                self.command_button.grid(row=0, column=0, columnspan=2 if stacked else 1, padx=(0, 16))
                self._shell_settings_frame.grid(row=1 if stacked else 0, column=0 if stacked else 1,
                                               columnspan=2 if stacked else 1, sticky='e',
                                               pady=(6, 0) if stacked else 0)
                self.navigation.grid(row=2 if stacked else 1, column=0, columnspan=2, pady=(6, 0))
                self._shell_location.grid(row=3 if stacked else 2, column=0, columnspan=2)
        available = max(1, self.navigation.winfo_width())
        requested = sum(button.winfo_reqwidth() + 8 for button in self._navigation_buttons)
        columns = 3 if available < requested else 6
        for index, button in enumerate(self._navigation_buttons):
            row, column = divmod(index, columns)
            button.grid(row=row, column=column, sticky='ew', padx=(0, 8), pady=(0, 4))
        for column in range(6):
            self.navigation.columnconfigure(column, weight=1 if column < columns else 0)
        if hasattr(self, 'session_bar'):
            self.refresh_sessions()

    def _layout_compact_sessions(self):
        self.session_bar.pack_forget()
        self.session_bar.configure(padding=0)
        self.session_caption_label.pack_forget()
        self.session_selector.configure(width=6)
        self.session_bar.grid(in_=self._shell_top, row=0, column=3, sticky='ew', padx=(0, 8))

    def _rebuild_help_menu(self):
        self.help_menu.delete(0, 'end')
        for tab in ('help', 'compatibility', 'versions', 'workflows', 'feedback', 'validation', 'plugins'):
            self.help_menu.add_command(label=self.tr(tab), command=lambda name=tab: self.show_help(name))

    def _optional_tool_routes(self):
        """Discover retained tools supplied by the parallel integration PRs."""
        return {key: method for key, name in (
            ('editing_presets', 'show_editing_presets'), ('transfer', 'show_transfer'),
            ('mod_manager', 'show_mod_manager'),
            ('game_configuration', 'show_game_configuration'),
            ('research_lab', 'show_research_lab'), ('research_import', 'show_research_import'),
            ('nexus_mods', 'show_nexus_mods'), ('emulator_hub', 'show_emulator_hub'),
            ('asset_explorer', 'show_asset_explorer'), ('workflow_builder', 'show_workflow_builder'),
            ('game_hub', 'show_game_hub'))
                if callable(method := getattr(self, name, None))}

    def command_entries(self):
        entries = [CommandEntry('game:' + game.id, game.title + ' · ' + game.subtitle,
                                'game', game.platform, game.id + ' ' + game.description)
                   for game in self.library_games]
        for key in ('library', 'converter', 'comparison', 'batch', 'save_library',
                    'troubleshooting', 'help', 'compatibility', 'versions', 'workflows', 'feedback',
                    'validation', 'plugins'):
            entries.append(CommandEntry('tool:' + key, self.tr(key), 'tool', keywords=key))
        listed_tools = {entry.id.removeprefix('tool:') for entry in entries if entry.id.startswith('tool:')}
        for key in self._optional_tool_routes():
            if key not in listed_tools:
                catalog = CATALOGS.get(self.language, CATALOGS['en'])
                label = self.tr(key) if key in catalog else key
                entries.append(CommandEntry('tool:' + key, label, 'tool', keywords=key))
        for key in ('theme_light', 'theme_dark', 'search_fields', 'language_en', 'language_de',
                    'text_size_100', 'text_size_120', 'text_size_140'):
            entries.append(CommandEntry('command:' + key, self.tr(key), 'command', keywords=key))
        if self.active_game is not None:
            for key in ('open_copy', 'save_copy', 'save_as', 'undo', 'review'):
                entries.append(CommandEntry('command:' + key, self.tr(key), 'command', keywords=key))
        if self.help_center is not None:
            plugin_commands = getattr(self.help_center, 'plugin_commands', None)
            if callable(plugin_commands):
                for key, title, description in plugin_commands():
                    entries.append(CommandEntry('plugin:' + key, title, 'plugin', description, 'plugin community'))
        favorite_words = self.tr('favorites') + ' favorites favorite'
        recent_words = self.tr('recent') + ' recent workspace'
        return tuple(replace(entry, keywords=entry.keywords
                             + (' ' + favorite_words if entry.id in self.shell_settings.favorites else '')
                             + (' ' + recent_words if entry.id in self.shell_settings.recent else ''))
                     for entry in entries)

    def open_command_palette(self, _event=None):
        if self.command_palette is not None and self.command_palette.window.winfo_exists():
            self.command_palette.close()
            return 'break'
        # Respect an existing safety/review dialog rather than stealing its grab.
        if self.root.grab_current() is not None:
            return 'break'
        self.command_palette = CommandPalette(
            self.root, self.command_entries(), self.execute_command,
            favorites=self.shell_settings.favorites, recent=self.shell_settings.recent,
            on_favorite=self._toggle_favorite, language=self.language,
            palette=THEMES[self.theme_name.get()])
        return 'break'

    def execute_command(self, command_id):
        # Only IDs in the current catalog may resolve to actions. Preferences
        # and community metadata never provide Python callbacks or imports.
        if command_id not in {entry.id for entry in self.command_entries()}:
            return
        category, key = command_id.split(':', 1)
        if category == 'plugin':
            self.show_help('plugins')
            return self.help_center.open_plugin_command(key)
        if category == 'game':
            return self.select_game(key)
        if category == 'tool':
            methods = {'library': self.show_library, 'converter': self.show_converter,
                       'comparison': self.show_comparison, 'batch': self.show_batch,
                       'save_library': self.show_save_library,
                       'troubleshooting': self.show_troubleshooting}
            methods.update(self._optional_tool_routes())
            if key in methods:
                result = methods[key]()
                self._remember_workspace(command_id)
                return result
            return self.show_help(key)
        if key in ('theme_light', 'theme_dark'):
            return self.apply_theme('Light' if key == 'theme_light' else 'Dark')
        if key in ('language_en', 'language_de'):
            self.language_choice.set(LANGUAGES[key.removeprefix('language_')])
            return self.change_language()
        if key in ('text_size_100', 'text_size_120', 'text_size_140'):
            self.text_size_choice.set(key.removeprefix('text_size_') + '%')
            return self.change_text_size()
        if key == 'search_fields':
            return self.focus_library_search()
        methods = {'open_copy': 'open', 'save_copy': 'save_changes', 'save_as': 'save_as',
                   'undo': 'undo', 'review': 'review'}
        if key in methods:
            return self.dispatch(methods[key])

    def show_help(self, tab='help'):
        from koei_editor.shared.help_center import HelpCenter
        if self.help_center is None:
            self.help_center = HelpCenter(self.root, self.workspace, initial_tab=tab, language=self.language,
                                          preferences_path=self.preferences_path,
                                          on_tab_changed=self._help_tab_changed)
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self._set_active_game(None)
        self.help_center.show_tab(tab)
        self.help_center.frame.pack(fill='both', expand=True)
        self.help_center.apply_theme(THEMES[self.theme_name.get()])
        self.help_center.set_text_size(round(10 * self.shell_settings.text_size / 100), self.font_family)
        self.breadcrumb.set(self.tr(tab))
        self._remember_workspace('tool:' + tab)
        return 'break'

    def _help_tab_changed(self, tab):
        if self.help_center is not None and self.help_center.frame.winfo_manager():
            self.breadcrumb.set(self.tr(tab))
            self._remember_workspace('tool:' + tab)

    def schedule_library_search(self, *_args):
        self._flush_library_search()
        self._search_after = self.root.after_idle(self.show_platform)

    def _flush_library_search(self):
        if self._search_after is not None:
            self.root.after_cancel(self._search_after)
            self._search_after = None

    def refresh_sessions(self):
        if not hasattr(self, 'session_bar'):
            return
        ordered = [key for key in self._session_order if key in self.sessions]
        ordered += [key for key in self.sessions if key not in ordered]
        labels = {}
        current = None
        for key in ordered:
            game = get_game(key)
            editor = self.sessions[key][1]
            count = len(editor.changes)
            label = f'{game.title} - {game.subtitle}' + (' [' + self.tr('pending', count=f'{count:,}') + ']' if count else '')
            labels[label] = key
            if key == self.active_game:
                current = label
        previous = self._session_labels.get(self.session_choice.get())
        self._session_labels = labels
        self.session_selector.configure(values=tuple(labels))
        self.session_caption.set(self.tr('open_editors', count=len(labels)))
        self.session_choice.set(current or next((label for label, key in labels.items() if key == previous),
                                                next(iter(labels), '')))
        if self.active_game is not None and self._compact_editor_shell:
            self._layout_compact_sessions()
        elif labels and not self.session_bar.winfo_manager():
            self.session_bar.pack(fill='x', before=self.workspace)

    def resume_session(self, _event=None):
        key = self._session_labels.get(self.session_choice.get())
        if key in self.sessions:
            self.select_game(key)
        return 'break'

    def create_library_cards(self, scope):
        if scope in self.library_cards:
            return
        self.library_cards[scope] = {}
        self.library_buttons[scope] = {}
        self.library_banners[scope] = {}
        games = tuple(game for game in self.library_games
                      if scope == ALL_PLATFORMS or game.platform == scope)
        for index, game in enumerate(games):
            platform_games = games
            compact = len(platform_games) > 3
            columns = 3 if len(platform_games) > 4 else len(platform_games)
            row, column = divmod(index, columns)
            platform_frame = self._library_contents[scope]
            platform_frame.columnconfigure(column, weight=1, uniform='cards')
            platform_frame.rowconfigure(row, weight=1, uniform='cards')
            card = ttk.Frame(platform_frame, padding=16 if compact else 20, relief='solid')
            card.grid(row=row, column=column, sticky='nsew',
                      padx=(0, 14) if column < columns - 1 else (0, 0),
                      pady=(0, 14) if row < (len(platform_games) - 1) // columns else (0, 0))
            # Reserve the action before decorative and descriptive content.
            button = ttk.Button(card, text='Open Editor',
                                style='Primary.TButton', command=lambda game_id=game.id: self.select_game(game_id))
            button.pack(anchor='w', side='bottom')
            self.library_cards[scope][game.id] = card
            self.library_buttons[scope][game.id] = button
            if scope != ALL_PLATFORMS:
                self.game_buttons[game.id] = button
            button.bind('<FocusIn>', lambda _event, game_id=game.id, name=scope: self.reveal_game_button(game_id, name))
            banner = tk.Canvas(card, width=240, height=140, background='#202a37', highlightthickness=0)
            banner._decorative = True
            self.library_banners[scope][game.id] = banner
            if not self.compact_library.get():
                banner.pack(fill='x', pady=(0, 16))
            # Original vector decoration; no copyrighted game images bundled.
            def paint(_event=None, canvas=banner, entry=game):
                canvas.delete('all')
                width = canvas.winfo_width()
                height = canvas.winfo_height()
                canvas.create_polygon(0, height, width * .4, height * .15, width * .72, height, fill=entry.accent, outline='')
                canvas.create_polygon(width * .33, height, width * .75, height * .34, width, height * .84, width, height,
                                      fill='#314151', outline='')
                canvas.create_line(22, height * .76, width - 22, height * .76, fill='#e6c379', width=2)
                canvas.create_text(25, height * .61, anchor='w', text=entry.emblem,
                                   font=(self.font_family, 28, 'bold'), fill='#ffffff')
                canvas.create_text(25, height * .88, anchor='w', text='SAVE EDITOR', font=(self.font_family, 9), fill='#e6c379')
            banner.bind('<Configure>', paint)
            # Prevent global canvas appearance from erasing the decorative background.
            banner.configure(background='#202a37')
            labels = [ttk.Label(card, text=game.title, font=(self.font_family, 13 if compact else 14, 'bold'), wraplength=265),
                      ttk.Label(card, text=(game.platform + ' · ' if scope == ALL_PLATFORMS and game.platform.casefold() not in game.subtitle.casefold() else '') + game.subtitle, style='Muted.TLabel', wraplength=265),
                      ttk.Label(card, text=game.description, wraplength=265, justify='left')]
            for label, padding in zip(labels, ((0, 0), (5, 10), (0, 0))):
                label.pack(anchor='w', pady=padding)
            def wrap_labels(event, widgets=labels, padding=40 if compact else 48):
                width = max(140, event.width - padding)
                for index, widget in enumerate(widgets):
                    widget.configure(wraplength=min(265, width) if index == 0 else width)
            card.bind('<Configure>', wrap_labels)

    def apply_theme(self, name):
        super().apply_theme(name)
        palette = THEMES[name]
        self.style.configure('LibraryDensity.TCheckbutton',
                             font=(self.font_family, 12, 'bold'), padding=(12, 8),
                             indicatormargin=(0, 0, 8, 0), background=palette['surface'],
                             foreground=palette['text'])
        self.style.map('LibraryDensity.TCheckbutton',
                       background=[('active', palette['hover'])])
        for _frame, editor in self.sessions.values():
            editor.theme_name.set(name)
            # Canvas items keep their own colors outside ttk's shared styles.
            # Repaint retained dashboards without calling editor.apply_theme,
            # whose application callback would recurse into this method.
            theme_dashboard = getattr(editor, 'theme_dashboard', None)
            if callable(theme_dashboard):
                theme_dashboard(name)
        for tool in self._tool_workspaces():
            tool.apply_theme(palette)
        if self.command_palette is not None and self.command_palette.window.winfo_exists():
            self.command_palette.apply_theme(palette)
        self._apply_text_size()

    def resize_library_cards(self, platform):
        canvas = self.platform_canvases[platform]
        content = self._library_contents[platform]
        if platform == self.platform_choice.get() and platform in self.library_cards:
            columns = min(3, max(1, len(self.library_matches)), max(1, canvas.winfo_width() // 280))
            if self._library_columns.get(platform) != columns:
                self._arrange_library_matches(platform, columns)
        height = max(canvas.winfo_height(), content.winfo_reqheight())
        canvas.itemconfigure(self._library_windows[platform], width=canvas.winfo_width(), height=height)
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), height))

    def scroll_library(self, event, units=None):
        if self.active_game is not None or not self.library.winfo_ismapped():
            return
        platform = self.platform_choice.get()
        frame = self.platform_frames.get(platform)
        widget = event.widget
        while widget is not None and widget != frame:
            widget = getattr(widget, 'master', None)
        if widget is None:
            return
        canvas = self.platform_canvases[platform]
        if not canvas.winfo_ismapped() or canvas.yview() == (0.0, 1.0):
            return
        if units is None:
            if not event.delta:
                return
            units = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
        canvas.yview_scroll(units, 'units')
        return 'break'

    def reveal_game_button(self, game_id, scope=None):
        if self.active_game is not None or not self.library.winfo_ismapped():
            return
        platform = scope or get_game(game_id).platform
        canvas = self.platform_canvases[platform]
        if not canvas.winfo_ismapped():
            return
        canvas.update_idletasks()
        button = self.library_buttons[platform][game_id]
        content = self._library_contents[platform]
        top = button.winfo_rooty() - content.winfo_rooty()
        bottom = top + button.winfo_height()
        visible_top = canvas.canvasy(0)
        visible_bottom = visible_top + canvas.winfo_height()
        if top - 12 < visible_top:
            canvas.yview_moveto(max(0, top - 12) / content.winfo_height())
        elif bottom + 12 > visible_bottom:
            canvas.yview_moveto((bottom + 12 - canvas.winfo_height()) / content.winfo_height())

    def _session_editor(self, game):
        """Create a retained editor without changing the visible workspace."""
        game_id = game.id
        if game_id not in self.sessions:
            frame = ttk.Frame(self.workspace)
            try:
                editor = game.create_editor(self.root, frame, self.theme_name.get(), self.apply_theme)
                configure_pins = getattr(editor, 'configure_pins', None)
                if callable(configure_pins):
                    on_change = (lambda ids: preferences.save_pins(game_id, ids, self.preferences_path)
                                 ) if self._persist_theme else None
                    configure_pins(preferences.load_pins(game_id, self.preferences_path), on_change)
            except Exception:
                frame.destroy()
                raise
            self.sessions[game_id] = frame, editor
            for viewport in (getattr(editor, 'fields', None),
                             getattr(getattr(editor, 'dashboard_view', None), 'canvas', None)):
                if viewport is not None:
                    viewport.bind('<Configure>', self._schedule_editor_width, add='+')
            status = getattr(editor, 'status', None)
            if hasattr(status, 'trace_add'):
                status.trace_add('write', lambda *_args: self.refresh_sessions())
            self.refresh_sessions()
        return self.sessions[game_id][1]

    def select_game(self, game_id):
        game = get_game(game_id)
        if game in GAMES:
            self.platform_choice.set(game.platform)
            self.show_platform()
        self._session_editor(game)
        if hasattr(self, '_session_order'):
            self._session_order = [game_id] + [key for key in self._session_order if key != game_id]
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        frame, editor = self.sessions[game_id]
        frame.pack(fill='both', expand=True)
        self._set_active_game(game_id)
        self._remember_workspace('game:' + game_id)
        self.refresh_sessions()
        self.breadcrumb.set(game.title + ' · ' + game.subtitle)
        self.apply_theme(self.theme_name.get())
        return editor

    def show_library(self):
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self.library.pack(fill='both', expand=True)
        self._set_active_game(None)
        self.breadcrumb.set(self.tr('choose'))
        self._remember_workspace('tool:library')
        self.show_platform()

    def show_converter(self):
        from koei_editor.shared.conversion_gui import ConversionWorkspace
        if self.converter is None:
            self.converter = ConversionWorkspace(self.root, self.workspace, self.queue_conversion)
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self._set_active_game(None)
        self.converter.frame.pack(fill='both', expand=True)
        self.breadcrumb.set(self.tr('converter'))
        self._remember_workspace('tool:converter')
        self.converter.apply_theme(THEMES[self.theme_name.get()])

    def show_comparison(self):
        from koei_editor.shared.comparison_gui import ComparisonWorkspace
        if self.comparison is None:
            self.comparison = ComparisonWorkspace(self.root, self.workspace)
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self._set_active_game(None)
        self.comparison.frame.pack(fill='both', expand=True)
        self.breadcrumb.set(self.tr('comparison'))
        self._remember_workspace('tool:comparison')
        self.comparison.apply_theme(THEMES[self.theme_name.get()])

    def _tool_workspaces(self):
        return tuple(tool for name in ('converter', 'comparison', 'batch', 'save_library',
                                       'troubleshooting', 'game_configuration', 'mod_manager',
                                       'editing_presets', 'research_lab', 'research_import', 'nexus_mods',
                                       'asset_explorer', 'workflow_builder', 'emulator_hub',
                                       'game_hub', 'help_center')
                     if (tool := getattr(self, name, None)) is not None)

    def _opened_scalar_editors(self):
        return tuple((get_game(key).title + ' · ' + get_game(key).subtitle, editor)
                     for key, (_frame, editor) in self.sessions.items()
                     if getattr(editor, 'document', None) is not None and hasattr(editor, 'adapter'))

    def show_editing_presets(self):
        from koei_editor.shared.compatible_preset_gui import CompatiblePresetWorkspace
        if self.editing_presets is None:
            self.editing_presets = CompatiblePresetWorkspace(self.root, self.workspace,
                                                             self._opened_scalar_editors)
        self.editing_presets.on_show()
        self._show_editing_tool(self.editing_presets, self.tr('editing_presets'))
        self._remember_workspace('tool:editing_presets')
        return self.editing_presets

    def show_mod_manager(self):
        from koei_editor.shared.mod_manager_gui import ModManagerWorkspace
        if self.mod_manager is None:
            self.mod_manager = ModManagerWorkspace(self.root, self.workspace)
        attach_handoff = getattr(self, 'set_mod_manager_download_handoff', None)
        if callable(attach_handoff):
            attach_handoff(self.mod_manager)
        self._show_editing_tool(self.mod_manager, self.tr('mod_manager'))
        self._remember_workspace('tool:mod_manager')
        return self.mod_manager

    def _add_editing_tools_menu_command(self, key, callback):
        self.editing_tools_menu.add_command(label=self.tr(key), command=callback)
        self._editing_tools_menu_commands[key] = self.editing_tools_menu.entrycget('end', 'command')

    def _editing_tools_menu_index(self, key):
        command = self._editing_tools_menu_commands.get(key)
        end = self.editing_tools_menu.index('end')
        if command is None or end is None:
            return None
        for index in range(end + 1):
            if (self.editing_tools_menu.type(index) == 'command'
                    and self.editing_tools_menu.entrycget(index, 'command') == command):
                return index
        return None

    def show_game_configuration(self):
        """Open the isolated, evidence-backed PC configuration workspace."""
        from koei_editor.shared.configuration_gui import ConfigurationWorkspace
        if self.game_configuration is None:
            self.game_configuration = ConfigurationWorkspace(self.root, self.workspace)
        self._show_editing_tool(self.game_configuration, self.tr('game_configuration'))
        self._remember_workspace('tool:game_configuration')
        return self.game_configuration

    def show_transfer(self):
        from tkinter import messagebox
        if self.active_game is None:
            messagebox.showinfo('Selective Save Transfer', 'Open the destination save in its exact editor first.',
                                parent=self.root)
            return None
        editor = self.sessions[self.active_game][1]
        if getattr(editor, 'document', None) is None or not hasattr(editor, 'adapter'):
            messagebox.showinfo('Selective Save Transfer', 'Open a qualified scalar save copy in the destination editor.',
                                parent=self.root)
            return None
        from koei_editor.shared.transfer_gui import open_transfer
        return open_transfer(editor)

    def show_research_lab(self):
        from koei_editor.shared.research_lab_gui import ResearchLabWorkspace
        if self.research_lab is None:
            self.research_lab = ResearchLabWorkspace(self.root, self.workspace)
        self._show_editing_tool(self.research_lab, self.tr('research_lab'))
        self._remember_workspace('tool:research_lab')
        return self.research_lab

    def show_research_import(self):
        from koei_editor.shared.research_import_gui import ResearchImportWorkspace
        if self.research_import is None:
            self.research_import = ResearchImportWorkspace(self.root, self.workspace)
        self._show_editing_tool(self.research_import, self.tr('research_import'))
        self._remember_workspace('tool:research_import')
        return self.research_import

    def show_asset_explorer(self):
        from koei_editor.research.asset_explorer.gui import AssetExplorerWorkspace
        if self.asset_explorer is None:
            self.asset_explorer = AssetExplorerWorkspace(self.root, self.workspace, language=self.language)
        self.asset_explorer.set_language(self.language)
        self._show_editing_tool(self.asset_explorer, self.tr('asset_explorer'))
        self._remember_workspace('tool:asset_explorer')
        return self.asset_explorer

    def _show_editing_tool(self, tool, title):
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self.active_game = None
        tool.frame.pack(fill='both', expand=True)
        self.breadcrumb.set(title)
        tool.apply_theme(THEMES[self.theme_name.get()])

    def _hide_tools(self):
        self._set_active_game(None)
        for tool in self._tool_workspaces():
            tool.frame.pack_forget()

    def _batch_workspace(self):
        if self.batch is None:
            from koei_editor.shared.batch_conversion_gui import BatchWorkspace
            self.batch = BatchWorkspace(self.root, self.workspace)
        return self.batch

    def show_batch(self):
        batch = self._batch_workspace()
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self._set_active_game(None)
        batch.frame.pack(fill='both', expand=True)
        self.breadcrumb.set(self.tr('batch'))
        self._remember_workspace('tool:batch')
        batch.apply_theme(THEMES[self.theme_name.get()])

    def show_save_library(self):
        from koei_editor.shared.save_library_gui import SaveLibraryWorkspace
        if self.save_library is None:
            self.save_library = SaveLibraryWorkspace(self.root, self.workspace, self.open_saved_copy)
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self._set_active_game(None)
        self.save_library.frame.pack(fill='both', expand=True)
        self.breadcrumb.set(self.tr('save_library'))
        self._remember_workspace('tool:save_library')
        self.save_library.apply_theme(THEMES[self.theme_name.get()])

    def show_emulator_hub(self):
        from koei_editor.shared.emulator_hub_gui import EmulatorHubWorkspace
        if self.emulator_hub is None:
            self.emulator_hub = EmulatorHubWorkspace(self.root, self.workspace, self.open_saved_copy,
                                                     preferences_path=self.preferences_path)
        self._show_editing_tool(self.emulator_hub, self.tr('emulator_hub'))
        self._remember_workspace('tool:emulator_hub')
        return self.emulator_hub

    def show_troubleshooting(self):
        from koei_editor.shared.game_troubleshooting_gui import TroubleshootingWorkspace
        if self.troubleshooting is None:
            self.troubleshooting = TroubleshootingWorkspace(
                self.root, self.workspace, language=self.language)
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self._set_active_game(None)
        self.troubleshooting.frame.pack(fill='both', expand=True)
        self.breadcrumb.set(self.tr('troubleshooting'))
        self._remember_workspace('tool:troubleshooting')
        self.troubleshooting.apply_theme(THEMES[self.theme_name.get()])
        size = round(10 * self.shell_settings.text_size / 100)
        self.troubleshooting.set_text_size(size, self.font_family)
        return self.troubleshooting

    def show_workflow_builder(self):
        from koei_editor.shared.automation_gui import WorkflowWorkspace
        if self.workflow_builder is None:
            self.workflow_builder = WorkflowWorkspace(self.root, self.workspace)
        self.library.pack_forget()
        self._hide_tools()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self.active_game = None
        self.workflow_builder.frame.pack(fill='both', expand=True)
        self.breadcrumb.set(self.tr('workflow_builder'))
        self._remember_workspace('tool:workflow_builder')
        self.workflow_builder.apply_theme(THEMES[self.theme_name.get()])

    def show_nexus_mods(self):
        from koei_editor.mods.nexus_browser import NexusModsWorkspace
        if self.nexus_mods is None:
            self.nexus_mods = NexusModsWorkspace(
                self.root, self.workspace,
                application_name='Universal Koei Tecmo Save Editor',
                application_version=VERSION,
                language=self.language,
                game_id=self.active_game,
                download_handoff=self.mod_manager_download_handoff,
            )
        else:
            self.nexus_mods.set_download_handoff(self.mod_manager_download_handoff)
        self._show_editing_tool(self.nexus_mods, self.tr('nexus_mods'))
        self._remember_workspace('tool:nexus_mods')
        return self.nexus_mods

    def set_mod_manager_download_handoff(self, handoff):
        """Attach the Mod Manager's Nexus queue capability when that component is present."""
        self.mod_manager_download_handoff = handoff
        if self.nexus_mods is not None:
            self.nexus_mods.set_download_handoff(handoff)

    def open_saved_copy(self, game_id, path):
        """Open a browser result through that profile's ordinary guarded editor."""
        from tkinter import messagebox
        try:
            game = get_game(game_id)
            if game not in GAMES or game.scalar_backend is None:
                raise ValueError('Choose an editable game/platform profile from Save Library.')
            editor = self._session_editor(game)
            open_path = getattr(editor, 'open_path', None)
            if not callable(open_path):
                raise ValueError('This editor cannot open a Save Library result.')
            accepted = open_path(path)
        except Exception as error:
            messagebox.showerror('Cannot Open Save Copy', str(error), parent=self.root)
            return False
        if accepted:
            self.select_game(game_id)
            return True
        return False

    def queue_conversion(self, prepared):
        if self._batch_workspace().add_review(prepared):
            self.show_batch()

    def show_platform(self, _event=None):
        self._flush_library_search()
        for frame in self.platform_frames.values():
            frame.pack_forget()
        scope = self.platform_choice.get()
        if scope not in self.platform_frames:
            return
        self.create_library_cards(scope)
        self.platform_frames[scope].pack(fill='both', expand=True)
        self.library_matches = matching_games(self._library_catalog, self.library_search.get(),
                                              scope, self.series_choice.get())
        columns = min(3, max(1, len(self.library_matches)), max(1, self.platform_canvases[scope].winfo_width() // 280))
        self._arrange_library_matches(scope, columns)
        count = len(self.library_matches)
        self.library_hint.set(self.tr('hint', count=count, scope=scope))
        filter_key = (scope, self.library_search.get(), self.series_choice.get(), self.compact_library.get())
        if filter_key != self._library_filter_key:
            self.platform_canvases[scope].yview_moveto(0)
        self._library_filter_key = filter_key
        self.resize_library_cards(scope)

    def _arrange_library_matches(self, scope, columns):
        self._library_columns[scope] = columns
        content = self._library_contents[scope]
        for card in self.library_cards[scope].values():
            card.grid_remove()
        for row in range(len(self.library_games)):
            content.rowconfigure(row, weight=0, uniform='')
        for column in range(3):
            content.columnconfigure(column, weight=1 if column < columns else 0,
                                    uniform='cards' if column < columns else '')
        self.library_empty[scope].grid_remove()
        if not self.library_matches:
            self.library_empty[scope].grid(row=0, column=0, sticky='w', pady=20)
        for index, game in enumerate(self.library_matches):
            row, column = divmod(index, columns)
            card = self.library_cards[scope][game.id]
            card.grid(row=row, column=column, sticky='nsew',
                      padx=(0, 14) if column < columns - 1 else (0, 0), pady=(0, 14))
            self.library_buttons[scope][game.id].configure(
                text=self.tr('resume') if game.id in self.sessions else self.tr('open'))

    def update_library_density(self):
        for scope, banners in self.library_banners.items():
            for game_id, banner in banners.items():
                banner.pack_forget()
                if not self.compact_library.get():
                    card = self.library_cards[scope][game_id]
                    labels = [child for child in card.winfo_children() if isinstance(child, ttk.Label)]
                    banner.pack(fill='x', pady=(0, 16), before=labels[0])
        self.show_platform()

    def clear_library_filters(self, _event=None):
        self.series_choice.set(ALL_SERIES)
        self.library_search.set('')
        self.show_platform()
        self.library_search_entry.focus_set()
        return 'break'

    def focus_library_search(self, _event=None):
        if self.active_game is not None:
            editor = self.sessions[self.active_game][1]
            focus = getattr(editor, 'focus_field_search', None)
            return focus() if focus is not None else None
        if self.help_center is not None and self.help_center.frame.winfo_manager():
            return self.help_center.focus_search()
        game_hub = getattr(self, 'game_hub', None)
        if game_hub is not None and game_hub.frame.winfo_manager():
            focus_search = getattr(game_hub, 'focus_search', None)
            return focus_search() if callable(focus_search) else 'break'
        for tool in (self.editing_presets, self.mod_manager, self.research_lab, self.research_import,
                     self.nexus_mods, self.asset_explorer):
            if tool is not None and tool.frame.winfo_manager():
                focus = getattr(tool, 'focus_search', None)
                return focus() if callable(focus) else 'break'
        if self.converter is not None and self.converter.frame.winfo_manager():
            return self.converter.focus_route_search()
        if self.save_library is not None and self.save_library.frame.winfo_manager():
            focus_search = getattr(self.save_library, 'focus_search', None)
            return focus_search() if callable(focus_search) else 'break'
        if self.workflow_builder is not None and self.workflow_builder.frame.winfo_manager():
            self.workflow_builder.search_entry.focus_set()
            self.workflow_builder.search_entry.selection_range(0, 'end')
            return 'break'
        if ((self.comparison is not None and self.comparison.frame.winfo_manager())
                or (self.batch is not None and self.batch.frame.winfo_manager())):
            return
        if (self.troubleshooting is not None
                and self.troubleshooting.frame.winfo_manager()):
            return 'break'
        self.platform_choice.set(ALL_PLATFORMS)
        self.show_platform()
        self.library_search_entry.focus_set()
        self.library_search_entry.selection_range(0, 'end')
        return 'break'

    def open_library_match(self, _event=None):
        if self._search_after is not None:
            self.show_platform()
        if len(self.library_matches) == 1:
            self.select_game(self.library_matches[0].id)
        return 'break'

    def dispatch(self, method):
        if self.active_game is not None:
            getattr(self.sessions[self.active_game][1], method)()
        return 'break'

    def contact(self):
        from koei_editor.games.dw3.gui import Editor
        # Reuse the existing author dialog without starting a DW3 game session.
        Editor.show_contact(self)

    def show_mod_workshop(self):
        """Open the independent mod project workspace without selecting a save editor."""
        if self.mod_workshop_window is not None and self.mod_workshop_window.window.winfo_exists():
            self.mod_workshop_window.window.deiconify()
            self.mod_workshop_window.window.lift()
            return self.mod_workshop_window
        from koei_editor.shared.mod_workshop.gui import ModWorkshopWindow
        self.mod_workshop_window = ModWorkshopWindow(self.root)
        return self.mod_workshop_window

    def close(self):
        tools = self._tool_workspaces()
        management = getattr(getattr(self, 'save_library', None), 'management', None)
        if management is not None:
            tools += (management,)
            profile_window = getattr(management, 'profile_window', None)
            if profile_window is not None and not getattr(profile_window, '_closed', False):
                tools += (profile_window,)
        troubleshooting = getattr(self, 'troubleshooting', None)
        if any(
                getattr(tool, 'busy', False)
                and not (
                    tool is troubleshooting
                    and getattr(tool, 'shutdown_safe_while_busy', False)
                )
                for tool in tools):
            from tkinter import messagebox
            messagebox.showinfo(
                'Operation running',
                'Wait for any copied-save operation or playthrough profile operation to finish before closing.',
                parent=self.root,
            )
            return
        if (all(editor.dirty_ok() for _frame, editor in self.sessions.values())
                and all(tool.dirty_ok() for tool in tools if callable(getattr(tool, 'dirty_ok', None)))):
            for tool in tools:
                close = getattr(tool, 'close', None)
                if callable(close):
                    close()
            self.root.destroy()


def _smoke_progression_views(app):
    """Exercise populated vector graphics without reading or editing a save.

    These explicit renderer samples exist only during --smoke-test. They have
    no mapped field links and make no claim about any game's progression.
    """
    from koei_editor.shared.progression import (
        DashboardCard, DashboardMetric, DashboardSection, ProgressionDashboard,
    )
    sample = ProgressionDashboard('Internal renderer smoke sample', (
        DashboardSection('smoke-section', 'Renderer sample', (
            DashboardCard('smoke-progress', 'Sample progress', metrics=(
                DashboardMetric('sample-count', 'Synthetic renderer units', '5 / 10',
                                current=5, total=10),)),
            DashboardCard('smoke-value', 'Sample value', metrics=(
                DashboardMetric('sample-value', 'Synthetic text', 'Read only'),)),
        )),
    ), note='Internal graphics sample only; no save or game data.')
    views = []
    for _frame, editor in app.sessions.values():
        view = getattr(editor, 'dashboard_view', None)
        if view is None:
            continue
        views.append((view, view.dashboard))
        view.set_dashboard(sample)
        view.section.set('smoke-section')
        if not view.select_card('smoke-value') or not view.select_card('smoke-progress'):
            raise RuntimeError('A progression renderer could not select its sample cards.')
        if not view.canvas.find_withtag('progress-track') or not view.canvas.find_withtag('progress-fill'):
            raise RuntimeError('A populated progression renderer did not draw its sample progress bar.')
        if editor.document is not None or editor.changes or editor.history:
            raise RuntimeError('Rendering a progression sample changed an empty editor session.')
    if not views:
        raise RuntimeError('No progression dashboards were initialized.')
    for name in ('Dark', 'Light'):
        app.apply_theme(name)
        app.root.update_idletasks()
        if any(view.palette != THEMES[name] for view, _snapshot in views):
            raise RuntimeError('A retained progression renderer missed an appearance change.')
    for view, snapshot in views:
        view.set_dashboard(snapshot)
    return len(views)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--automation':
        from koei_editor.automation_cli import main as automation_main
        raise SystemExit(automation_main(sys.argv[2:]))
    parser = argparse.ArgumentParser(description='Universal Koei Tecmo Save Editor')
    parser.epilog = 'Use --automation --help for reviewed batch editing and workflow commands.'
    parser.add_argument('--game', choices=[game.id for game in ALL_ADAPTERS], help='Open a registered editor or research tool.')
    parser.add_argument('--smoke-test', action='store_true', help='Initialize all registered interfaces and check switching.')
    parser.add_argument('--list-games', action='store_true', help='Print supported games, platforms and features.')
    # Existing DW3 private file workflow remains available in the same executable.
    tests = parser.add_mutually_exclusive_group()
    tests.add_argument('--self-test', nargs=2, metavar=('INPUT', 'OUTPUT'))
    tests.add_argument('--compatibility-test', nargs=2, metavar=('INPUT', 'OUTPUT'))
    tests.add_argument('--convert', metavar='ROUTE', help='Convert an explicit supported route; requires --source, --template and --output-dir.')
    tests.add_argument('--batch-convert', metavar='PLAN', help='Review or export an explicit JSON conversion queue.')
    parser.add_argument('--batch-report', help='Optional new .json summary for --batch-convert.')
    tests.add_argument('--compare', nargs=2, metavar=('FIRST', 'SECOND'), help='Compare two copied saves using an explicit --game profile; no gameplay files are written.')
    tests.add_argument('--scan-saves', metavar='FOLDER', help='Inspect a copied-save folder using an explicit --game profile; print a path-free read-only JSON summary.')
    parser.add_argument('--recursive', action='store_true', help='Include subfolders within the fixed Save Library depth limit; requires --scan-saves.')
    parser.add_argument('--comparison-report', help='Optional new .json report for --compare.')
    tests.add_argument('--list-conversions', action='store_true', help='Print supported platform conversion routes.')
    parser.add_argument('--source', help='Separate source save copy for conversion.')
    parser.add_argument('--template', help='Separate destination-platform save copy for conversion.')
    parser.add_argument('--output-dir', help='New folder for the converted save and local receipt.')
    parser.add_argument('--dry-run', action='store_true', help='Validate and review conversion without writing files or backups.')
    from koei_editor.shared import save_management_cli
    save_management_cli.add_arguments(parser, tests)
    arguments = parser.parse_args()
    if save_management_cli.handle(parser, arguments):
        return
    if arguments.recursive and arguments.scan_saves is None:
        parser.error('--recursive requires --scan-saves.')
    if arguments.scan_saves is not None:
        from koei_editor.shared import save_library
        import json
        if (not arguments.game or arguments.scan_saves == '' or arguments.smoke_test
                or arguments.list_games or arguments.dry_run
                or any(value is not None for value in (arguments.source, arguments.template,
                    arguments.output_dir, arguments.batch_report, arguments.comparison_report))):
            parser.error('--scan-saves requires a separate --game profile and copied folder; other workflow options do not apply.')
        try:
            save_library.adapter_for(arguments.game)
        except (ValueError, TypeError):
            parser.error('Save Library requires a registered scalar game/platform profile; the separate DW3 and research workflows are unsupported.')
        try:
            scanned = save_library.scan(arguments.game, arguments.scan_saves, recursive=arguments.recursive)
            report = save_library.report(scanned)
        except (OSError, ValueError, TypeError):
            # Native and filesystem exception messages can contain private local
            # filenames or original context. The public summary omits them too.
            parser.exit(1, 'Save Library scan failed. Check the copied folder and selected profile.\n')
        print(json.dumps(report, indent=2, ensure_ascii=True))
        if report['stop_reason'] != 'complete':
            parser.exit(3)
        if (not report['statuses']['qualified']
                or report['statuses']['qualified'] != report['candidate_files']):
            parser.exit(1)
        return
    if arguments.batch_convert:
        from koei_editor.shared import batch_conversion
        import json
        if (arguments.game or arguments.smoke_test or arguments.list_games or arguments.source
                or arguments.template or arguments.output_dir or arguments.comparison_report):
            parser.error('Use --batch-convert separately from editor, comparison and individual conversion options.')
        try:
            prepared = batch_conversion.prepare(arguments.batch_convert)
            if arguments.batch_report:
                batch_conversion.check_report_destination(prepared, arguments.batch_report)
            if arguments.dry_run:
                report = batch_conversion.review_report(prepared)
            else:
                outcomes = batch_conversion.execute(prepared)
                report = batch_conversion.outcome_report(prepared, outcomes)
            if arguments.batch_report:
                batch_conversion.export_report(report, arguments.batch_report)
            print(json.dumps(report, indent=2, ensure_ascii=True))
            if not arguments.dry_run and not report['success']:
                parser.exit(1)
        except (OSError, ValueError) as error:
            parser.exit(1, 'Batch conversion failed: ' + str(error) + '\n')
        return
    if arguments.batch_report:
        parser.error('--batch-report requires --batch-convert.')
    if arguments.compare:
        from koei_editor.shared import save_comparison
        import json
        if not arguments.game or arguments.smoke_test or arguments.list_games:
            parser.error('--compare requires a separate explicit --game profile.')
        if arguments.source or arguments.template or arguments.output_dir or arguments.dry_run:
            parser.error('Conversion options do not apply to --compare.')
        try:
            prepared = save_comparison.prepare(arguments.game, *arguments.compare)
            result = save_comparison.report(prepared)
            if arguments.comparison_report:
                save_comparison.export(prepared, arguments.comparison_report)
            print(json.dumps(result, indent=2, ensure_ascii=True))
        except (OSError, ValueError) as error:
            parser.exit(1, 'Comparison failed: ' + str(error) + '\n')
        return
    if arguments.comparison_report:
        parser.error('--comparison-report requires --compare.')
    if arguments.convert or arguments.list_conversions:
        from koei_editor import conversion
        import json
        if arguments.game or arguments.smoke_test or arguments.list_games:
            parser.error('Use conversion separately from game editor commands.')
        if arguments.list_conversions:
            if arguments.source or arguments.template or arguments.output_dir or arguments.dry_run:
                parser.error('--list-conversions does not take conversion paths or --dry-run.')
            for route in conversion.ROUTES:
                # Redirected Windows terminals commonly use cp1252; keep the
                # route listing portable even with a strict ASCII stdout.
                print(route.id + ': ' + route.label.replace('→', '->').replace('·', '-'))
            return
        if not arguments.source or not arguments.template or (not arguments.dry_run and not arguments.output_dir):
            parser.error('--convert requires --source, --template and --output-dir (unless --dry-run).')
        try:
            prepared = conversion.prepare(arguments.convert, arguments.source, arguments.template)
            report = {'route': prepared.route.id, 'gameplay_bytes': prepared.gameplay_bytes,
                      'transfer_scope': prepared.route.transfer_scope, 'scope_description': prepared.route.scope_description,
                      'gameplay_sha256': prepared.gameplay_sha256, 'notes': prepared.notes,
                      'dry_run': arguments.dry_run, 'game_load_verified': False}
            if not arguments.dry_run:
                destination, _backups, receipt = conversion.export(prepared, arguments.output_dir)
                report.update(receipt)
                report['output_file'] = destination.name
            print(json.dumps(report, indent=2))
        except (OSError, ValueError) as error:
            parser.exit(1, 'Conversion failed: ' + str(error) + '\n')
        return
    if arguments.source or arguments.template or arguments.output_dir or arguments.dry_run:
        parser.error('Conversion paths and --dry-run require --convert.')
    if arguments.list_games:
        for game in SUPPORTED_GAMES:
            print(f'{game.id}: {game.title} — {game.edition} [{game.platform}]\n  {game.features}')
        return
    selected_game = get_game(arguments.game or 'dw3')
    if arguments.self_test and selected_game.scalar_backend is not None:
        from koei_editor.shared.verified_self_test import run
        report = run(arguments.game, *arguments.self_test)
        status = ('Candidate copy checks passed; independent qualification pending'
                  if not report['format_sample_verified'] else 'Copied-save self-test passed')
        print(f"{arguments.game}: {status}. {report['fields_checked']} fields checked. In-game loading remains untested.")
        return
    if arguments.self_test or arguments.compatibility_test:
        if arguments.game not in (None, 'dw3'):
            parser.error('The fixture self-test and compatibility-test are DW3 workflows.')
        from koei_editor.games.dw3.gui import main as dw3_main
        original_argv = sys.argv
        flag = '--self-test' if arguments.self_test else '--compatibility-test'
        values = arguments.self_test or arguments.compatibility_test
        try:
            # The legacy DW3 runner expects only the flag and its two values.
            sys.argv = [original_argv[0], flag, *values]
            return dw3_main()
        finally:
            sys.argv = original_argv
    root = tk.Tk()
    if arguments.smoke_test:
        root.withdraw()
    app = Application(root, persist_preferences=not arguments.smoke_test)
    if arguments.smoke_test:
        for game in ALL_ADAPTERS:
            editor = app.select_game(game.id)
            root.update_idletasks()
            if editor.document is not None or editor.changes:
                raise RuntimeError('A fresh editor unexpectedly contains save data.')
        dashboards = _smoke_progression_views(app)
        app.apply_theme('Dark')
        app.show_converter()
        app.show_comparison()
        app.show_batch()
        app.show_save_library()
        app.show_game_configuration()
        app.show_editing_presets()
        app.show_mod_manager()
        app.show_research_lab()
        app.show_research_import()
        app.show_nexus_mods()
        app.show_library()
        app.nexus_mods.close()
        app.select_game('dw3')
        app.apply_theme('Light')
        workshop = app.show_mod_workshop()
        root.update_idletasks()
        workshop.close()
        root.update_idletasks()
        root.destroy()
        print(f'Platform library, all registered interfaces, {dashboards} populated progression dashboards, '
              'themes and switching initialized successfully.')
    else:
        if arguments.game:
            app.select_game(arguments.game)
        root.mainloop()


if __name__ == '__main__':
    main()

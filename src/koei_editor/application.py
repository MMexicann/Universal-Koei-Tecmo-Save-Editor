"""Universal Dynasty Warriors application shell, with retained game sessions."""
import argparse
import sys
import tkinter as tk
from tkinter import ttk
from koei_editor.shared.appearance import Appearance, THEMES
from koei_editor.game_registry import GAMES, ALL_ADAPTERS, get_game
from koei_editor.supported_games import SUPPORTED_GAMES
from koei_editor.shared.library_catalog import ALL_PLATFORMS, ALL_SERIES, matching_games, series_for
import koei_editor.shared.preferences as preferences

VERSION = '1.71'


class Application(Appearance):
    def __init__(self, root, preferences_path=None, persist_preferences=True):
        self.root = root
        self.preferences_path = preferences_path
        self._persist_theme = persist_preferences
        initial_theme = preferences.load_theme(preferences_path)
        self.style = ttk.Style(root)
        self.style.theme_use('clam')
        self.theme_name = tk.StringVar(root, value=initial_theme)
        self.sessions = {}
        self.active_game = None
        root.title(f'Universal Koei Tecmo Save Editor — v{VERSION}')
        root.geometry('1180x930')
        root.minsize(1080, 820)
        self.apply_theme(initial_theme)
        root.option_add('*Font', (self.font_family, 10))
        top = ttk.Frame(root, padding=(18, 10))
        top.pack(fill='x')
        self.home_button = ttk.Button(top, text='‹ Game Library', command=self.show_library)
        self.home_button.pack(side='left')
        self.breadcrumb = tk.StringVar(root, value='Choose your game')
        ttk.Label(top, textvariable=self.breadcrumb, style='Muted.TLabel').pack(side='left', padx=14)
        self.theme_selector = ttk.Combobox(top, values=tuple(THEMES), textvariable=self.theme_name,
                                          state='readonly', width=7)
        self.theme_selector.pack(side='right')
        self.theme_selector.bind('<<ComboboxSelected>>', lambda _event: self.apply_theme(self.theme_name.get()))
        ttk.Label(top, text='Appearance', style='Muted.TLabel').pack(side='right', padx=9)
        ttk.Label(top, text='Made by Mexican', style='Muted.TLabel').pack(side='right', padx=20)
        self.workspace = ttk.Frame(root)
        self.workspace.pack(fill='both', expand=True)
        self.library = ttk.Frame(self.workspace, padding=(38, 20))
        self.library.pack(fill='both', expand=True)
        ttk.Label(self.library, text='KOEI TECMO', font=(self.font_family, 27, 'bold')).pack(anchor='w', pady=(8, 0))
        ttk.Label(self.library, text='SAVE EDITOR', font=(self.font_family, 17), style='Muted.TLabel').pack(anchor='w')
        self.library_games = tuple(GAMES)
        platforms = tuple(dict.fromkeys(game.platform for game in self.library_games))
        platform_bar = ttk.Frame(self.library)
        platform_bar.pack(fill='x', pady=(12, 12))
        ttk.Label(platform_bar, text='Choose your platform', font=(self.font_family, 12)).pack(side='left', padx=(0, 12))
        self.platform_choice = tk.StringVar(root, value='Windows PC')
        self.platform_selector = ttk.Combobox(platform_bar, textvariable=self.platform_choice,
                                             values=(ALL_PLATFORMS,) + platforms, state='readonly', width=20)
        self.platform_selector.pack(side='left')
        self.platform_selector.bind('<<ComboboxSelected>>', self.show_platform)
        ttk.Label(platform_bar, text='Series', style='Muted.TLabel').pack(side='left', padx=(20, 8))
        self.series_choice = tk.StringVar(root, value=ALL_SERIES)
        self.series_selector = ttk.Combobox(platform_bar, textvariable=self.series_choice,
                                             values=(ALL_SERIES,) + tuple(sorted({series_for(game) for game in self.library_games})),
                                             state='readonly', width=24)
        self.series_selector.pack(side='left')
        self.series_selector.bind('<<ComboboxSelected>>', self.show_platform)
        search_bar = ttk.Frame(self.library)
        search_bar.pack(fill='x', pady=(0, 10))
        ttk.Label(search_bar, text='Find a game', style='Muted.TLabel').pack(side='left', padx=(0, 12))
        self.library_search = tk.StringVar(root)
        self.library_search_entry = ttk.Entry(search_bar, textvariable=self.library_search)
        self.library_search_entry.pack(side='left', fill='x', expand=True)
        self.library_search_entry.bind('<Return>', self.open_library_match)
        self.library_search_entry.bind('<Escape>', self.clear_library_filters)
        ttk.Button(search_bar, text='Clear filters', command=self.clear_library_filters).pack(side='left', padx=10)
        self.compact_library = tk.BooleanVar(root, value=False)
        self.compact_toggle = ttk.Checkbutton(
            search_bar, text='Compact cards', style='LibraryDensity.TCheckbutton',
            variable=self.compact_library, command=self.update_library_density)
        self.compact_toggle.pack(side='right', padx=(8, 0))
        self.library_hint = tk.StringVar(root)
        ttk.Label(self.library, textvariable=self.library_hint,
                  style='Muted.TLabel', wraplength=1000).pack(anchor='w', pady=(0, 18))
        # Reserve the footer before the expanding cards so its controls remain
        # reachable at the minimum window size.
        self.library_footer = ttk.Frame(self.library)
        self.library_footer.pack(side='bottom', fill='x', pady=(16, 0))
        ttk.Label(self.library_footer, text='Always work with a separate copy. Your game sessions stay open when you switch games.',
                  style='Muted.TLabel', wraplength=1000).pack(anchor='w')
        footer_buttons = ttk.Frame(self.library_footer)
        footer_buttons.pack(fill='x', pady=(12, 0))
        self.contact_button = ttk.Button(footer_buttons, text='Contact Mexican', command=self.contact)
        self.contact_button.pack(side='left')
        cards = ttk.Frame(self.library)
        cards.pack(fill='both', expand=True)
        self.platform_frames = {platform: ttk.Frame(cards) for platform in (ALL_PLATFORMS,) + platforms}
        self.platform_canvases = {}
        self._library_contents = {}
        self._library_windows = {}
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
        self.library_empty = {scope: ttk.Label(content, text='No games match. Try another name or clear the filters.',
                                               style='Muted.TLabel')
                              for scope, content in self._library_contents.items()}
        for platform in platforms:
            self.create_library_cards(platform)
        self.library_search.trace_add('write', lambda *_args: self.show_platform())
        root.bind('<Control-f>', self.focus_library_search, add='+')
        self.show_platform()
        root.bind('<MouseWheel>', self.scroll_library, add='+')
        root.bind('<Button-4>', lambda event: self.scroll_library(event, -1), add='+')
        root.bind('<Button-5>', lambda event: self.scroll_library(event, 1), add='+')
        for shortcut, method in (('<Control-o>', 'open'), ('<Control-s>', 'save_changes'),
                                 ('<Control-Shift-S>', 'save_as'), ('<Control-z>', 'undo'), ('<Control-r>', 'review')):
            root.bind(shortcut, lambda _event, name=method: self.dispatch(name))
        root.protocol('WM_DELETE_WINDOW', self.close)

    def create_library_cards(self, scope):
        if scope in self.library_cards:
            return
        self.library_cards[scope] = {}
        self.library_buttons[scope] = {}
        self.library_banners[scope] = {}
        games = tuple(game for game in self.library_games
                      if scope == ALL_PLATFORMS or game.platform == scope)
        for game in games:
            platform_games = games
            index = platform_games.index(game)
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

    def resize_library_cards(self, platform):
        canvas = self.platform_canvases[platform]
        content = self._library_contents[platform]
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

    def select_game(self, game_id):
        game = get_game(game_id)
        if game in GAMES:
            self.platform_choice.set(game.platform)
            self.show_platform()
        if game_id not in self.sessions:
            frame = ttk.Frame(self.workspace)
            try:
                editor = game.create_editor(self.root, frame, self.theme_name.get(), self.apply_theme)
            except Exception:
                frame.destroy()
                raise
            self.sessions[game_id] = frame, editor
        self.library.pack_forget()
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        frame, editor = self.sessions[game_id]
        frame.pack(fill='both', expand=True)
        self.active_game = game_id
        self.breadcrumb.set(game.title + ' · ' + game.subtitle)
        self.apply_theme(self.theme_name.get())
        return editor

    def show_library(self):
        for frame, _editor in self.sessions.values():
            frame.pack_forget()
        self.library.pack(fill='both', expand=True)
        self.active_game = None
        self.breadcrumb.set('Choose your game')
        self.show_platform()

    def show_platform(self, _event=None):
        for frame in self.platform_frames.values():
            frame.pack_forget()
        scope = self.platform_choice.get()
        if scope not in self.platform_frames:
            return
        self.create_library_cards(scope)
        self.platform_frames[scope].pack(fill='both', expand=True)
        self.library_matches = matching_games(self.library_games, self.library_search.get(),
                                              scope, self.series_choice.get())
        content = self._library_contents[scope]
        for card in self.library_cards[scope].values():
            card.grid_remove()
        for row in range(len(self.library_games)):
            content.rowconfigure(row, weight=0, uniform='')
        columns = min(3, max(1, len(self.library_matches)))
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
                text='Resume Editor' if game.id in self.sessions else 'Open Editor')
        count = len(self.library_matches)
        noun = 'editor' if count == 1 else 'editors'
        self.library_hint.set(f'{count} {noun} · {scope}. Search by game, edition, platform or feature. '
                              'Enter opens a single match; Ctrl+F searches across platforms.')
        filter_key = (scope, self.library_search.get(), self.series_choice.get(), self.compact_library.get())
        if filter_key != self._library_filter_key:
            self.platform_canvases[scope].yview_moveto(0)
        self._library_filter_key = filter_key
        self.resize_library_cards(scope)

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
            return
        self.platform_choice.set(ALL_PLATFORMS)
        self.show_platform()
        self.library_search_entry.focus_set()
        self.library_search_entry.selection_range(0, 'end')
        return 'break'

    def open_library_match(self, _event=None):
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

    def close(self):
        if all(editor.dirty_ok() for _frame, editor in self.sessions.values()):
            self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='Universal Koei Tecmo Save Editor')
    parser.add_argument('--game', choices=[game.id for game in ALL_ADAPTERS], help='Open a registered editor or research tool.')
    parser.add_argument('--smoke-test', action='store_true', help='Initialize all registered interfaces and check switching.')
    parser.add_argument('--list-games', action='store_true', help='Print supported games, platforms and features.')
    # Existing DW3 private file workflow remains available in the same executable.
    tests = parser.add_mutually_exclusive_group()
    tests.add_argument('--self-test', nargs=2, metavar=('INPUT', 'OUTPUT'))
    tests.add_argument('--compatibility-test', nargs=2, metavar=('INPUT', 'OUTPUT'))
    arguments = parser.parse_args()
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
        app.apply_theme('Dark')
        app.show_library()
        app.select_game('dw3')
        app.apply_theme('Light')
        root.update_idletasks()
        root.destroy()
        print('Platform library, all registered interfaces, themes and switching initialized successfully.')
    else:
        if arguments.game:
            app.select_game(arguments.game)
        root.mainloop()


if __name__ == '__main__':
    main()

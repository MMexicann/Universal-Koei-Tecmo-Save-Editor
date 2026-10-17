"""Searchable, keyboard-operable command surface independent of game editors."""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
import unicodedata

from koei_editor.shared.localization import translate


@dataclass(frozen=True)
class CommandEntry:
    id: str
    title: str
    category: str
    detail: str = ''
    keywords: str = ''


def _normalize(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(char))


def search_commands(entries, query='', favorites=(), recent=()):
    """AND search with deterministic favorite/recent ordering; no side effects."""
    tokens = _normalize(query[:512]).split()
    favorite_set = set(favorites)
    recent_order = {key: index for index, key in enumerate(recent)}
    result = []
    for entry in entries:
        corpus = _normalize(' '.join((entry.id, entry.title, entry.category, entry.detail, entry.keywords)))
        if all(token in corpus for token in tokens):
            result.append(entry)
    return tuple(sorted(result, key=lambda entry: (
        entry.id not in favorite_set, recent_order.get(entry.id, len(recent_order)),
        _normalize(entry.title), entry.id)))


class CommandPalette:
    """One transient dialog; callbacks resolve stable IDs in the owning shell."""
    def __init__(self, root, entries, execute, favorites=(), recent=(), on_favorite=None, language='en', palette=None):
        self.root = root
        self.entries = tuple(entries)
        self.execute = execute
        self.favorites = tuple(favorites)
        self.recent = tuple(recent)
        self.on_favorite = on_favorite
        self.language = language
        self.previous_focus = root.focus_get()
        self.previous_grab = root.grab_current()
        self.window = tk.Toplevel(root)
        self.window.title(self.tr('palette_title'))
        self.window.transient(root)
        self.window.minsize(440, 320)
        self.window.geometry('760x470')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        content = ttk.Frame(self.window, padding=18)
        content.pack(fill='both', expand=True)
        ttk.Label(content, text=self.tr('palette_search'), style='Section.TLabel').pack(anchor='w')
        self.query = tk.StringVar(root)
        self.entry = ttk.Entry(content, textvariable=self.query)
        self.entry.pack(fill='x', pady=(10, 12))
        results = ttk.Frame(content)
        results.pack(fill='both', expand=True)
        self.results = ttk.Treeview(results, columns=('category', 'detail'), show='tree headings', selectmode='browse', height=10)
        self.results.heading('#0', text=self.tr('palette_title'))
        self.results.heading('category', text=self.tr('command'))
        self.results.heading('detail', text=self.tr('platform'))
        self.results.column('#0', width=360, minwidth=180)
        self.results.column('category', width=100, minwidth=70, stretch=False)
        self.results.column('detail', width=180, minwidth=100)
        scrollbar = ttk.Scrollbar(results, orient='vertical', command=self.results.yview)
        self.results.configure(yscrollcommand=scrollbar.set)
        self.results.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.status = tk.StringVar(root)
        ttk.Label(content, textvariable=self.status, style='Muted.TLabel').pack(anchor='w', pady=(8, 0))
        ttk.Label(content, text=self.tr('palette_hint'), style='Muted.TLabel', wraplength=700).pack(anchor='w', pady=(5, 8))
        self.favorite_button = ttk.Button(content, text=self.tr('favorite'), command=self.toggle_favorite)
        self.favorite_button.pack(anchor='e')
        self.query.trace_add('write', lambda *_args: self.refresh())
        for sequence in ('<Escape>', '<Control-k>', '<Control-K>'):
            self.window.bind(sequence, self.close)
        self.window.bind('<Return>', self.activate)
        self.window.bind('<Control-d>', self.toggle_favorite)
        self.window.bind('<Control-D>', self.toggle_favorite)
        self.entry.bind('<Down>', lambda _event: self.move(1))
        self.entry.bind('<Up>', lambda _event: self.move(-1))
        self.results.bind('<Double-1>', self.activate)
        self.refresh()
        if palette is not None:
            self.apply_theme(palette)
        self.window.update_idletasks()
        width = min(760, root.winfo_screenwidth() - 40)
        height = min(470, root.winfo_screenheight() - 60)
        x = max(0, root.winfo_rootx() + (root.winfo_width() - width) // 2)
        y = max(0, root.winfo_rooty() + 90)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
        self.window.grab_set()
        self.entry.focus_set()

    def tr(self, key, **values):
        return translate(key, self.language, **values)

    def refresh(self):
        previous = self.results.selection()
        self.matches = search_commands(self.entries, self.query.get(), self.favorites, self.recent)
        self.results.delete(*self.results.get_children())
        for command in self.matches:
            title = ('★ ' if command.id in self.favorites else '') + command.title
            category = self.tr(command.category)
            if command.id in self.recent:
                category += ' · ' + self.tr('recent_tag')
            self.results.insert('', 'end', iid=command.id, text=title, values=(category, command.detail))
        if self.matches:
            selected = previous[0] if previous and self.results.exists(previous[0]) else self.matches[0].id
            self.results.selection_set(selected)
            self.results.focus(selected)
            self.results.see(selected)
        self.status.set(self.tr('results', count=len(self.matches)) if self.matches else self.tr('palette_empty'))
        self.favorite_button.configure(state='normal' if self.matches else 'disabled')

    def move(self, delta):
        rows = self.results.get_children()
        if rows:
            selection = self.results.selection()
            index = rows.index(selection[0]) if selection else 0
            selected = rows[max(0, min(len(rows) - 1, index + delta))]
            self.results.selection_set(selected)
            self.results.focus(selected)
            self.results.see(selected)
        return 'break'

    def activate(self, _event=None):
        selection = self.results.selection()
        if selection:
            command_id = selection[0]
            self.close(restore_focus=False)
            self.execute(command_id)
        return 'break'

    def toggle_favorite(self, _event=None):
        selection = self.results.selection()
        if selection and self.on_favorite is not None:
            self.favorites = tuple(self.on_favorite(selection[0]))
            self.refresh()
        return 'break'

    def apply_theme(self, palette):
        self.window.configure(background=palette['background'])

    def close(self, _event=None, restore_focus=True):
        if not self.window.winfo_exists():
            return 'break'
        self.window.grab_release()
        self.window.destroy()
        if self.previous_grab is not None and self.previous_grab.winfo_exists():
            self.previous_grab.grab_set()
        if restore_focus and self.previous_focus is not None and self.previous_focus.winfo_exists():
            self.previous_focus.focus_set()
        return 'break'

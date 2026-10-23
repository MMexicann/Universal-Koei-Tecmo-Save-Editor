"""Discoverable navigation with explicit feature and platform boundaries."""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class ToolEntry:
    command_id: str
    title: str
    group: str
    scope: str
    description: str


def matching_tools(entries, query='', group='All tools'):
    terms = query.casefold().split()
    return tuple(entry for entry in entries
                 if (group == 'All tools' or entry.group == group)
                 and all(term in ' '.join((entry.title, entry.group, entry.scope,
                                           entry.description)).casefold() for term in terms))


class ToolDirectoryWorkspace:
    """A retained directory; opening a tool never opens or modifies player data."""

    def __init__(self, root, parent, entries, on_open, language='en'):
        self.root, self.entries, self.on_open = root, tuple(entries), on_open
        self.language = language
        self._group_names = {}
        self.frame = ttk.Frame(parent, padding=18)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(3, weight=1)
        self.title_label = ttk.Label(self.frame, text='Toolkit tools', style='Section.TLabel')
        self.title_label.grid(row=0, column=0, sticky='w')
        self.intro = ttk.Label(self.frame, wraplength=1000, text=(
            'Choose a tool to see its scope. Save-platform support, mod installation and '
            'application operating systems have separate compatibility requirements.'))
        self.intro.grid(row=1, column=0, sticky='ew', pady=(8, 12))
        filters = ttk.Frame(self.frame)
        filters.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        filters.columnconfigure(1, weight=1)
        self.query_label = ttk.Label(filters, text='Find a tool')
        self.query_label.grid(row=0, column=0, padx=(0, 8))
        self.query = tk.StringVar(root)
        self.search_entry = ttk.Entry(filters, textvariable=self.query)
        self.search_entry.grid(row=0, column=1, sticky='ew')
        self.group = tk.StringVar(root, value='All tools')
        self.group_selector = ttk.Combobox(filters, textvariable=self.group, state='readonly',
                                         values=('All tools',) + tuple(sorted({e.group for e in self.entries})))
        self.group_selector.grid(row=0, column=2, padx=(8, 0))
        table = ttk.Frame(self.frame)
        table.grid(row=3, column=0, sticky='nsew')
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=('group', 'scope'), show='tree headings',
                                 selectmode='browse', height=12)
        self.tree.heading('#0', text='Tool')
        self.tree.heading('group', text='Category')
        self.tree.heading('scope', text='Available scope')
        self.tree.column('#0', width=240, minwidth=150)
        self.tree.column('group', width=120, minwidth=80)
        self.tree.column('scope', width=370, minwidth=120)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=scroll.set)
        self.detail = tk.StringVar(root, value='Select a tool to read its capabilities and limits.')
        self.detail_label = ttk.Label(self.frame, textvariable=self.detail, wraplength=1000, justify='left')
        self.detail_label.grid(row=4, column=0, sticky='ew', pady=12)
        actions = ttk.Frame(self.frame)
        actions.grid(row=5, column=0, sticky='ew')
        self.open_button = ttk.Button(actions, text='Open selected tool', command=self.open_selected, state='disabled')
        self.open_button.pack(side='left')
        self.count = tk.StringVar(root)
        ttk.Label(actions, textvariable=self.count).pack(side='right')
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.tree.bind('<Double-1>', self.open_selected)
        self.tree.bind('<Return>', self.open_selected)
        self.query.trace_add('write', lambda *_: self.refresh())
        self.group_selector.bind('<<ComboboxSelected>>', self.refresh)
        self.frame.bind('<Configure>', self._resize)
        self.set_language(language)

    def _resize(self, event):
        width = max(200, event.width - 40)
        self.detail_label.configure(wraplength=width)
        self.intro.configure(wraplength=width)

    def refresh(self, _event=None):
        previous = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self._visible = {entry.command_id: entry for entry in matching_tools(
            self.entries, self.query.get(), self._group_names.get(self.group.get(), 'All tools'))}
        for entry in self._visible.values():
            self.tree.insert('', 'end', iid=entry.command_id, text=entry.title,
                             values=(self._display_group(entry.group), entry.scope))
        if previous and previous[0] in self._visible:
            self.tree.selection_set(previous[0])
        self.count.set(f'{len(self._visible)} ' + ('Werkzeuge' if self.language == 'de' else 'tools'))
        self.select()

    def select(self, _event=None):
        selected = self.tree.selection()
        entry = self._visible.get(selected[0]) if selected else None
        self.open_button.configure(state='normal' if entry else 'disabled')
        self.detail.set(f'{entry.title}\n{entry.scope}\n\n{entry.description}' if entry
                        else ('Wähle ein Werkzeug, um seine Funktionen und Grenzen zu lesen.'
                              if self.language == 'de' else 'Select a tool to read its capabilities and limits.'))

    def open_selected(self, _event=None):
        selected = self.tree.selection()
        if selected and selected[0] in self._visible:
            return self.on_open(selected[0])

    def focus_search(self):
        self.search_entry.focus_set()
        return 'break'

    def set_language(self, language):
        previous = self._group_names.get(self.group.get(), 'All tools')
        self.language = language
        german = language == 'de'
        self.title_label.configure(text='Toolkit-Werkzeuge' if language == 'de' else 'Toolkit tools')
        self.query_label.configure(text='Werkzeug suchen' if german else 'Find a tool')
        self.intro.configure(text=(
            'Wähle ein Werkzeug, um seinen Funktionsumfang zu sehen. Spielstände, '
            'Mod-Installation und Betriebssysteme haben jeweils eigene Kompatibilitätsgrenzen.'
            if german else 'Choose a tool to see its scope. Save-platform support, mod installation and '
            'application operating systems have separate compatibility requirements.'))
        self.open_button.configure(text='Ausgewähltes Werkzeug öffnen' if german else 'Open selected tool')
        self.tree.heading('#0', text='Werkzeug' if german else 'Tool')
        self.tree.heading('group', text='Kategorie' if german else 'Category')
        self.tree.heading('scope', text='Verfügbarer Umfang' if german else 'Available scope')
        self._group_names = {self._display_group(group): group for group in
                             ('All tools',) + tuple(sorted({entry.group for entry in self.entries}))}
        self.group_selector.configure(values=tuple(self._group_names))
        self.group.set(self._display_group(previous))
        self.refresh()

    def _display_group(self, group):
        return ({'All tools': 'Alle Werkzeuge', 'Saves': 'Spielstände', 'Games': 'Spiele',
                 'Mods': 'Mods', 'Research': 'Forschung', 'Support': 'Hilfe'}.get(group, group)
                if self.language == 'de' else group)

    def apply_theme(self, _palette):
        pass

    def close(self):
        pass

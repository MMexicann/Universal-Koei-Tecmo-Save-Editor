"""Lazy global documentation, compatibility and community workspace."""
import tkinter as tk
from tkinter import ttk

from koei_editor.shared.compatibility_center import compatibility_entries, search_compatibility
from koei_editor.shared.help_content import Article, help_articles, search_articles, preparation_guide


class HelpCenter:
    def __init__(self, root, parent, initial_tab='help', language='en'):
        self.root = root
        self.language = language if language in ('en', 'de') else 'en'
        self.frame = ttk.Frame(parent, padding=16)
        self.busy = False
        self._panels = {}
        self._palette = None
        de = self.language == 'de'
        self.title_label = ttk.Label(self.frame, text='Hilfe & Community' if de else 'Help & Community',
                                     style='Section.TLabel')
        self.title_label.pack(anchor='w', pady=(0, 8))
        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill='both', expand=True)
        self.tabs = {}
        labels = (('compatibility', 'Kompatibilität' if de else 'Compatibility'),
                  ('help', 'Hilfe' if de else 'Help'),
                  ('workflows', 'Anleitungen' if de else 'Guides'),
                  ('validation', 'Validierung' if de else 'Validation'),
                  ('feedback', 'Feedback'), ('plugins', 'Plugins'))
        for key, label in labels:
            self.tabs[key] = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(self.tabs[key], text=label)
        self.notebook.bind('<<NotebookTabChanged>>', self._tab_changed)
        self.entries = compatibility_entries()
        self._build_compatibility()
        self._build_help()
        self._build_guides()
        self.show_tab(initial_tab)

    def _text(self, parent, height=12):
        holder = ttk.Frame(parent)
        holder.pack(fill='both', expand=True, pady=(8, 0))
        text = tk.Text(holder, height=height, wrap='word', state='disabled',
                       padx=12, pady=12, takefocus=True, relief='flat')
        scroll = ttk.Scrollbar(holder, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)
        return text

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', value)
        widget.configure(state='disabled')

    def _build_compatibility(self):
        de = self.language == 'de'
        parent = self.tabs['compatibility']
        bar = ttk.Frame(parent)
        bar.pack(fill='x')
        self.search_label = ttk.Label(bar, text='Suche' if de else 'Search')
        self.search_label.pack(side='left', padx=(0, 8))
        self.compatibility_query = tk.StringVar(self.root)
        self.compatibility_search = ttk.Entry(bar, textvariable=self.compatibility_query)
        self.compatibility_search.pack(side='left', fill='x', expand=True)
        self.platform = tk.StringVar(self.root, value='')
        selector = ttk.Combobox(bar, textvariable=self.platform, state='readonly', width=22,
                               values=('',) + tuple(sorted({entry.platform for entry in self.entries})))
        selector.pack(side='left', padx=(8, 0))
        selector.bind('<<ComboboxSelected>>', self._filter_compatibility)
        self.compatibility_count = tk.StringVar(self.root)
        ttk.Label(parent, textvariable=self.compatibility_count, style='Muted.TLabel').pack(anchor='w', pady=6)
        table = ttk.Frame(parent)
        table.pack(fill='both', expand=True)
        self.matrix = ttk.Treeview(table, columns=('title', 'platform', 'revision', 'evidence'), show='headings', height=8)
        headings = ('Spiel' if de else 'Game', 'Plattform' if de else 'Platform',
                    'Edition / Revision', 'Dateinachweis' if de else 'File evidence')
        for column, title, width in zip(self.matrix['columns'], headings, (260, 130, 320, 220)):
            self.matrix.heading(column, text=title)
            self.matrix.column(column, width=width, minwidth=80)
        self.matrix.grid(row=0, column=0, sticky='nsew')
        ttk.Scrollbar(table, orient='vertical', command=self.matrix.yview).grid(row=0, column=1, sticky='ns')
        vertical = table.grid_slaves(row=0, column=1)[0]
        self.matrix.configure(yscrollcommand=vertical.set)
        horizontal = ttk.Scrollbar(table, orient='horizontal', command=self.matrix.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.matrix.configure(xscrollcommand=horizontal.set)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.compatibility_detail = self._text(parent, height=10)
        self.matrix.bind('<<TreeviewSelect>>', self._show_compatibility)
        self.compatibility_query.trace_add('write', lambda *_: self._filter_compatibility())
        self.compatibility_search.bind('<Return>', lambda _e: self.matrix.focus_set())
        self.compatibility_search.bind('<Escape>', lambda _e: self.compatibility_query.set(''))
        self._filter_compatibility()

    def _filter_compatibility(self, _event=None):
        previous = self.matrix.selection()
        self.matrix.delete(*self.matrix.get_children())
        matches = search_compatibility(self.entries, self.compatibility_query.get(), self.platform.get())
        for entry in matches:
            self.matrix.insert('', 'end', iid=entry.game_id, values=(entry.title, entry.platform,
                               entry.revision_scope, entry.file_evidence))
        self.compatibility_count.set(f'{len(matches)} / {len(self.entries)} ' +
                                     ('unterstützte Profile' if self.language == 'de' else 'supported profiles'))
        selected = previous[0] if previous and self.matrix.exists(previous[0]) else matches[0].game_id if matches else None
        if selected:
            self.matrix.selection_set(selected)
            self.matrix.focus(selected)
        self._show_compatibility()

    def _show_compatibility(self, _event=None):
        selected = self.matrix.selection()
        entry = next((entry for entry in self.entries if selected and entry.game_id == selected[0]), None)
        if entry is None:
            self._set_text(self.compatibility_detail, 'Keine Treffer.' if self.language == 'de' else 'No matching profiles.')
            return
        de = self.language == 'de'
        body = (f'{entry.title}\n{entry.platform} · {entry.revision_scope}\n\n'
                + ('Funktionen' if de else 'Functionality') + f'\n{entry.functionality}\n\n'
                + ('Dateinachweis' if de else 'File qualification') + f'\n{entry.file_evidence}\n{entry.evidence}\n\n'
                + ('Weitere Prüfung' if de else 'Remaining validation') + f'\n{entry.remaining_validation}\n\n'
                + ('Spielvalidierung' if de else 'Game validation') + f'\n{entry.game_validation}\n\n'
                + ('Exakte Software-Builds nur verwenden, wenn ausdrücklich dokumentiert.' if de else
                   'Exact software builds are supported only where explicitly documented.'))
        self._set_text(self.compatibility_detail, body)

    def _build_help(self):
        parent = self.tabs['help']
        de = self.language == 'de'
        self.help_label = ttk.Label(parent, text='Dokumentation durchsuchen' if de else 'Search documentation')
        self.help_label.pack(anchor='w')
        self.help_query = tk.StringVar(self.root)
        self.help_search = ttk.Entry(parent, textvariable=self.help_query)
        self.help_search.pack(fill='x', pady=(4, 8))
        self.article_list = ttk.Treeview(parent, columns=('title',), show='headings', height=6)
        self.article_list.heading('title', text='Thema' if de else 'Topic')
        self.article_list.pack(fill='x')
        self.article_detail = self._text(parent)
        self.articles = help_articles(self.language)
        self.help_query.trace_add('write', lambda *_: self._filter_help())
        self.article_list.bind('<<TreeviewSelect>>', self._show_article)
        self.help_search.bind('<Return>', lambda _e: self.article_list.focus_set())
        self.help_search.bind('<Escape>', lambda _e: self.help_query.set(''))
        self._filter_help()

    def _filter_help(self):
        self.article_list.delete(*self.article_list.get_children())
        articles = search_articles(self.articles, self.help_query.get())
        for article in articles:
            self.article_list.insert('', 'end', iid=article.id, values=(article.title,))
        if articles:
            self.article_list.selection_set(articles[0].id)
            self.article_list.focus(articles[0].id)
        self._show_article()

    def _show_article(self, _event=None):
        selected = self.article_list.selection()
        article = next((article for article in self.articles if selected and article.id == selected[0]), None)
        self._set_text(self.article_detail, article.title + '\n\n' + article.body if article else
                       'Keine Treffer.' if self.language == 'de' else 'No matching documentation.')

    def _build_guides(self):
        parent = self.tabs['workflows']
        de = self.language == 'de'
        self.guide_label = ttk.Label(parent, text='Plattformspezifische Vorbereitung und Import/Export' if de else
                                     'Platform-specific preparation and import/export')
        self.guide_label.pack(anchor='w')
        platforms = tuple(sorted({entry.platform for entry in self.entries}))
        self.guide_platform = tk.StringVar(self.root, value='Windows PC')
        selector = ttk.Combobox(parent, textvariable=self.guide_platform, values=platforms, state='readonly')
        selector.pack(fill='x', pady=8)
        self.guide_detail = self._text(parent)
        selector.bind('<<ComboboxSelected>>', self._show_guide)
        self._show_guide()

    def _show_guide(self, _event=None):
        text = preparation_guide(self.guide_platform.get(), self.language)
        panel = self._panels.get('plugins')
        if panel is not None:
            from koei_editor.shared.plugin_gui import contribution_text
            for item in panel.catalog.search(kind='workflows', locale=self.language):
                if self.guide_platform.get() in item.platforms:
                    text += '\n\nCommunity plugin · ' + contribution_text(item)
        self._set_text(self.guide_detail, text)

    def show_tab(self, name):
        self.notebook.select(self.tabs.get(name, self.tabs['help']))
        self._ensure_panel(name)

    def _tab_changed(self, _event=None):
        selected = self.notebook.select()
        for name, tab in self.tabs.items():
            if str(tab) == selected:
                self._ensure_panel(name)
                break

    def _ensure_panel(self, name):
        if name in self._panels or name not in ('validation', 'feedback', 'plugins'):
            return
        if name == 'plugins':
            from koei_editor.shared.plugin_gui import PluginPanel
            panel = PluginPanel(self.root, self.tabs[name], language=self.language,
                                on_change=self._plugins_changed)
        else:
            from koei_editor.shared.validation_gui import ValidationPanel, FeedbackPanel
            panel_type = ValidationPanel if name == 'validation' else FeedbackPanel
            panel = panel_type(self.root, self.tabs[name], language=self.language)
        self._panels[name] = panel
        panel.frame.pack(fill='both', expand=True)
        if self._palette is not None:
            panel.apply_theme(self._palette)

    def _plugins_changed(self, _catalog=None):
        self.articles = help_articles(self.language)
        panel = self._panels.get('plugins')
        if panel is not None:
            self.articles += tuple(Article(item.id, 'Community plugin · ' + item.title, item.body)
                                   for item in panel.catalog.search(kind='help', locale=self.language))
        self._filter_help()
        self._show_guide()

    def plugin_commands(self):
        panel = self._panels.get('plugins')
        if panel is None:
            return ()
        return tuple((item.id, item.title, 'Community plugin · ' + ', '.join(item.game_ids))
                     for item in panel.catalog.search(kind='commands', locale=self.language))

    def open_plugin_command(self, command_id):
        from koei_editor.shared.community_plugins import PluginError
        from koei_editor.shared.plugin_gui import contribution_text
        panel = self._panels.get('plugins')
        if panel is None:
            return False
        try:
            item = panel.catalog.resolve_command(command_id)
        except PluginError:
            return False
        if item.locale != self.language:
            return False
        self.show_tab('plugins')
        panel._show('Community plugin\n\n' + contribution_text(item))
        return True

    def apply_theme(self, palette):
        self._palette = palette
        for widget in (self.compatibility_detail, self.article_detail, self.guide_detail):
            widget.configure(background=palette['surface'], foreground=palette['text'],
                             insertbackground=palette['text'], selectbackground=palette['accent'],
                             selectforeground='#ffffff')
        for panel in self._panels.values():
            panel.apply_theme(palette)

    def set_language(self, language):
        """Relabel in place so unfinished validation and plugin approvals survive."""
        self.language = language if language in ('en', 'de') else 'en'
        de = self.language == 'de'
        self.title_label.configure(text='Hilfe & Community' if de else 'Help & Community')
        self.search_label.configure(text='Suche' if de else 'Search')
        self.help_label.configure(text='Dokumentation durchsuchen' if de else 'Search documentation')
        self.guide_label.configure(text='Plattformspezifische Vorbereitung und Import/Export' if de else
                                   'Platform-specific preparation and import/export')
        titles = ('Kompatibilität', 'Hilfe', 'Anleitungen', 'Validierung', 'Feedback', 'Plugins') if de else (
                  'Compatibility', 'Help', 'Guides', 'Validation', 'Feedback', 'Plugins')
        for tab, title in zip(self.tabs.values(), titles):
            self.notebook.tab(tab, text=title)
        headings = ('Spiel', 'Plattform', 'Edition / Revision', 'Dateinachweis') if de else (
                    'Game', 'Platform', 'Edition / Revision', 'File evidence')
        for column, title in zip(self.matrix['columns'], headings):
            self.matrix.heading(column, text=title)
        self.article_list.heading('title', text='Thema' if de else 'Topic')
        self._plugins_changed()
        self._filter_compatibility()
        self._show_guide()
        for panel in self._panels.values():
            if hasattr(panel, 'set_language'):
                panel.set_language(self.language)

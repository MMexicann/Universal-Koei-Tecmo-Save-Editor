"""Explicit directory discovery and session-only approval of data-only plugins."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared.appearance import ui_font
from koei_editor.shared.community_plugins import API_VERSION, PluginCatalog, PluginError, discover_plugins


_LABELS = {
    'en': {
        'title': 'Community plugins',
        'policy': 'Choose a directory to inspect data-only plugins. Nothing is enabled automatically. '
                  'Community text is not verified game support. No plugin code runs.',
        'browse': 'Inspect directory…', 'search': 'Search plugins and declarations',
        'name': 'Plugin', 'state': 'Status', 'disabled': 'Disabled', 'enabled': 'Enabled for this session',
        'invalid': 'Rejected', 'reviewed': 'I reviewed this snapshot and its capabilities',
        'enable': 'Enable reviewed snapshot', 'disable': 'Disable selected plugin',
        'empty': 'Choose a directory containing *.plugin.json manifests. Approval resets when '
                 'you inspect another directory or restart the application.',
        'none': 'No matching plugins.', 'error': 'Plugin inspection failed',
        'api': 'API', 'author': 'Author', 'capabilities': 'Capabilities',
        'community': 'Community declaration — not an application compatibility claim',
        'snapshot': 'Read-only discovery snapshot. File changes require a new inspection and approval.',
    },
    'de': {
        'title': 'Community-Plugins',
        'policy': 'Verzeichnis zur Prüfung deklarativer Plugins auswählen. Nichts wird automatisch aktiviert. '
                  'Community-Texte bestätigen keine Spielunterstützung. Es wird kein Plugin-Code ausgeführt.',
        'browse': 'Verzeichnis prüfen…', 'search': 'Plugins und Deklarationen durchsuchen',
        'name': 'Plugin', 'state': 'Status', 'disabled': 'Deaktiviert', 'enabled': 'Für diese Sitzung aktiviert',
        'invalid': 'Abgelehnt', 'reviewed': 'Ich habe diese Momentaufnahme und ihre Berechtigungen geprüft',
        'enable': 'Geprüfte Momentaufnahme aktivieren', 'disable': 'Ausgewähltes Plugin deaktivieren',
        'empty': 'Verzeichnis mit *.plugin.json-Dateien auswählen. Die Freigabe gilt bis zum Neustart '
                 'oder bis ein anderes Verzeichnis geprüft wird.',
        'none': 'Keine passenden Plugins.', 'error': 'Plugin-Prüfung fehlgeschlagen',
        'api': 'API', 'author': 'Autor', 'capabilities': 'Berechtigungen',
        'community': 'Community-Deklaration — keine Kompatibilitätsbestätigung der Anwendung',
        'snapshot': 'Schreibgeschützte Momentaufnahme. Dateiänderungen erfordern erneute Prüfung und Freigabe.',
    },
}


def contribution_text(item):
    """Plain-text content shared with help/palette hosts; never render as HTML."""
    scope = ', '.join(item.game_ids) or 'Global'
    text = [item.title, item.id, f'{item.kind} · {item.locale} · {scope}']
    if item.body:
        text.extend(('', item.body))
    if item.platforms:
        text.extend(('', ', '.join(item.platforms)))
    if item.steps:
        text.extend(('', *(f'{index}. {step}' for index, step in enumerate(item.steps, 1))))
    if item.target:
        text.extend(('', '→ ' + item.target))
    return '\n'.join(text)


class PluginPanel:
    def __init__(self, root, parent, language='en', on_change=None):
        self.root = root
        self.language = language if language in _LABELS else 'en'
        self.on_change = on_change
        self.catalog = PluginCatalog()
        self.frame = ttk.Frame(parent, padding=16)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(5, weight=1)
        self.title_label = ttk.Label(self.frame, style='Section.TLabel')
        self.title_label.grid(row=0, column=0, sticky='w')
        self.policy_label = ttk.Label(self.frame, wraplength=760)
        self.policy_label.grid(row=1, column=0, sticky='ew', pady=(6, 12))
        toolbar = ttk.Frame(self.frame)
        toolbar.grid(row=2, column=0, sticky='ew')
        toolbar.columnconfigure(1, weight=1)
        self.browse_button = ttk.Button(toolbar, command=self.browse)
        self.browse_button.grid(row=0, column=0, sticky='w', padx=(0, 12))
        self.search = tk.StringVar(root)
        self.search_label = ttk.Label(toolbar)
        self.search_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=(10, 3))
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search)
        self.search_entry.grid(row=2, column=0, columnspan=2, sticky='ew')
        self.search_entry.bind('<Escape>', lambda _event: self.search.set(''))
        results = ttk.Frame(self.frame)
        results.grid(row=3, column=0, sticky='nsew', pady=10)
        results.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(results, columns=('state',), show='tree headings', selectmode='browse', height=5)
        self.tree.column('#0', width=270, minwidth=100)
        self.tree.column('state', width=170, minwidth=80)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(results, orient='vertical', command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<<TreeviewSelect>>', self._select)
        actions = ttk.Frame(self.frame)
        actions.grid(row=4, column=0, sticky='ew')
        self.reviewed = tk.BooleanVar(root, value=False)
        self.review_check = ttk.Checkbutton(actions, variable=self.reviewed, command=self._buttons)
        self.review_check.grid(row=0, column=0, columnspan=2, sticky='w')
        self.enable_button = ttk.Button(actions, command=self.enable_selected, state='disabled')
        self.enable_button.grid(row=1, column=0, sticky='w', pady=6)
        self.disable_button = ttk.Button(actions, command=self.disable_selected, state='disabled')
        self.disable_button.grid(row=1, column=1, sticky='w', padx=10, pady=6)
        preview_frame = ttk.Frame(self.frame)
        preview_frame.grid(row=5, column=0, sticky='nsew', pady=(6, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview = tk.Text(preview_frame, height=10, wrap='word', state='disabled', relief='flat',
                               padx=12, pady=10, font=(ui_font(root), 10), takefocus=True)
        self.preview.grid(row=0, column=0, sticky='nsew')
        preview_scroll = ttk.Scrollbar(preview_frame, orient='vertical', command=self.preview.yview)
        preview_scroll.grid(row=0, column=1, sticky='ns')
        self.preview.configure(yscrollcommand=preview_scroll.set)
        self.search.trace_add('write', self._refresh)
        self._selected = None
        self.set_language(self.language)

    def set_language(self, language):
        self.language = language if language in _LABELS else 'en'
        labels = _LABELS[self.language]
        self.title_label.configure(text=labels['title'])
        self.policy_label.configure(text=labels['policy'])
        self.browse_button.configure(text=labels['browse'])
        self.search_label.configure(text=labels['search'])
        self.tree.heading('#0', text=labels['name'])
        self.tree.heading('state', text=labels['state'])
        self.review_check.configure(text=labels['reviewed'])
        self.enable_button.configure(text=labels['enable'])
        self.disable_button.configure(text=labels['disable'])
        self._refresh()

    def apply_theme(self, palette):
        self.preview.configure(background=palette['surface'], foreground=palette['text'],
                               insertbackground=palette['text'], selectbackground=palette['accent'],
                               selectforeground='#ffffff')

    def browse(self):
        directory = filedialog.askdirectory(parent=self.root, title=_LABELS[self.language]['browse'])
        if directory:
            self.load_directory(directory)

    def load_directory(self, directory):
        from koei_editor.game_registry import ALL_ADAPTERS
        try:
            candidates = discover_plugins(directory, known_game_ids=(game.id for game in ALL_ADAPTERS))
            catalog = PluginCatalog(candidates, reserved_ids=(game.id for game in ALL_ADAPTERS))
        except PluginError as error:
            messagebox.showerror(_LABELS[self.language]['error'], str(error), parent=self.root)
            return False
        self.catalog = catalog
        self._selected = None
        self._refresh()
        self._notify()
        return True

    def _notify(self):
        if self.on_change is not None:
            self.on_change(self.catalog)

    def _refresh(self, *_args):
        previous = self._selected
        self.tree.delete(*self.tree.get_children())
        labels = _LABELS[self.language]
        terms = self.search.get()[:256].casefold().split()
        for index, entry in enumerate(self.catalog.entries):
            manifest = entry.candidate.manifest
            title = manifest.title if manifest else entry.candidate.filename
            text = ' '.join((title, manifest.id, manifest.description,
                             *(contribution_text(item) for item in manifest.contributions))) if manifest else title
            searchable = text.casefold()
            if not all(term in searchable for term in terms):
                continue
            state = labels['invalid' if entry.error else 'enabled' if entry.enabled else 'disabled']
            self.tree.insert('', 'end', iid=str(index), text=title, values=(state,))
        visible = self.tree.get_children()
        if previous is not None and str(previous) in visible:
            self.tree.selection_set(str(previous))
        elif visible:
            self.tree.selection_set(visible[0])
        else:
            self._selected = None
            self.reviewed.set(False)
            self._show(labels['none'] if self.catalog.entries else labels['empty'])
            self._buttons()
        self._select()

    def _select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            self._selected = None
            self.reviewed.set(False)
            self._buttons()
            return
        index = int(selection[0])
        self._selected = index
        self.reviewed.set(False)
        entry = self.catalog.entries[index]
        candidate = entry.candidate
        manifest = candidate.manifest
        labels = _LABELS[self.language]
        if manifest is None:
            content = candidate.filename + '\n\n' + entry.error
        else:
            content = '\n'.join((manifest.title + ' ' + manifest.version, manifest.id,
                                 f"{labels['api']}: {manifest.api} / {API_VERSION}",
                                 f"{labels['author']}: {manifest.author}",
                                 f"{labels['capabilities']}: {', '.join(manifest.capabilities)}",
                                 'SHA-256: ' + candidate.sha256, '', manifest.description, '',
                                 labels['community'], labels['snapshot'], entry.error, '',
                                 '\n\n'.join(contribution_text(item) for item in manifest.contributions)))
        self._show(content)
        self._buttons()

    def _show(self, content):
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', content)
        self.preview.configure(state='disabled')

    def show_content(self, item):
        """Show inert command content without retaining manifest approval controls.

        A command may belong to a different plugin from the selected candidate.
        Its text must never replace a manifest preview while approval still
        refers to that candidate. Queued selection events also see no selection.
        """
        self.tree.selection_remove(*self.tree.selection())
        self._selected = None
        self.reviewed.set(False)
        self._buttons()
        self._show(_LABELS[self.language]['community'] + '\n\n' + contribution_text(item))
        self.preview.yview_moveto(0)

    def _buttons(self):
        entry = self.catalog.entries[self._selected] if self._selected is not None else None
        valid = entry is not None and not entry.error
        self.review_check.configure(state='normal' if valid and not entry.enabled else 'disabled')
        self.enable_button.configure(state='normal' if valid and not entry.enabled and self.reviewed.get() else 'disabled')
        self.disable_button.configure(state='normal' if valid and entry.enabled else 'disabled')

    def enable_selected(self):
        if self._selected is None or not self.reviewed.get():
            return
        entry = self.catalog.entries[self._selected]
        manifest = entry.candidate.manifest
        if entry.error or manifest is None:
            return
        self.catalog.approve(manifest.id, sha256=entry.candidate.sha256, capabilities=manifest.capabilities)
        self._refresh()
        self._notify()

    def disable_selected(self):
        if self._selected is None:
            return
        manifest = self.catalog.entries[self._selected].candidate.manifest
        if manifest is not None:
            self.catalog.disable(manifest.id)
            self._refresh()
            self._notify()

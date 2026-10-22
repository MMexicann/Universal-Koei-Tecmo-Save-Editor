"""Tk workspace for read-only Nexus discovery and manager handoff."""

from concurrent.futures import ThreadPoolExecutor
import queue
import tkinter as tk
from tkinter import ttk
import webbrowser

from koei_editor.mods.nexus_api import (
    NexusApiClient,
    NexusApiError,
    SUPPORTED_NEXUS_GAMES,
    build_download_request,
    mod_page_url,
    nexus_game_for_id,
    search_loaded_mods,
)
from koei_editor.shared.localization import translate


_SORT_FIELDS = ('trending', 'popular', 'new', 'updated', 'endorsements')


class NexusModsWorkspace:
    """Dedicated mod browser; archive downloads and installation stay with a manager."""

    def __init__(self, root, parent, *, application_name, application_version,
                 language='en', game_id=None, download_handoff=None, transport=None):
        self.root = root
        self.application_name = application_name
        self.application_version = application_version
        self.language = language
        self.download_handoff = download_handoff
        self._transport = transport
        self._client = self._new_client(None)
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='nexus-mods')
        self._result_queue = queue.Queue()
        self._poll_id = None
        self._closed = False
        self._request_generation = 0
        self._loaded_mods = []
        self._shown_mods = {}
        self._selected_summary = None
        self._selected_details = None
        self._files = {}
        self._versions = {}
        self._selected_file_id = None
        self._selected_version = None
        self._page = 0
        self._total_count = 0
        self._loaded_game_domain = None
        self._loaded_sort_field = None
        self._busy = 0
        self._game_by_label = {}
        for game in SUPPORTED_NEXUS_GAMES:
            if game.domain in {item.domain for item in self._game_by_label.values()}:
                continue
            self._game_by_label[game.title] = game

        self.frame = ttk.Frame(parent, padding=18)
        self._build_ui()
        self._select_initial_game(game_id)
        self.set_language(language)
        self._poll_id = self.frame.after(100, self._poll_results)

    def _new_client(self, api_key):
        return NexusApiClient(api_key=api_key, application_name=self.application_name,
                              application_version=self.application_version,
                              transport=self._transport)

    def tr(self, key, **values):
        return translate(key, self.language, **values)

    def _build_ui(self):
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(3, weight=1)
        self.title_label = ttk.Label(self.frame, style='Section.TLabel')
        self.title_label.grid(row=0, column=0, sticky='w')
        self.intro_label = ttk.Label(self.frame, style='Muted.TLabel', wraplength=1100, justify='left')
        self.intro_label.grid(row=1, column=0, sticky='ew', pady=(4, 12))

        controls = ttk.Frame(self.frame)
        controls.grid(row=2, column=0, sticky='ew', pady=(0, 10))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)
        self.game_label = ttk.Label(controls, style='Muted.TLabel')
        self.game_label.grid(row=0, column=0, sticky='w')
        self.sort_label = ttk.Label(controls, style='Muted.TLabel')
        self.sort_label.grid(row=0, column=1, sticky='w', padx=(10, 0))
        self.game_var = tk.StringVar(self.root)
        self.game_selector = ttk.Combobox(controls, textvariable=self.game_var,
                                          values=tuple(self._game_by_label), state='readonly')
        self.game_selector.grid(row=1, column=0, sticky='ew', pady=(3, 8))
        self.game_selector.bind('<<ComboboxSelected>>', self._on_game_changed)
        self.sort_var = tk.StringVar(self.root)
        self.sort_selector = ttk.Combobox(controls, textvariable=self.sort_var, state='readonly', width=18)
        self.sort_selector.grid(row=1, column=1, sticky='ew', padx=(10, 0), pady=(3, 8))
        self.sort_selector.bind('<<ComboboxSelected>>', lambda _event: self._sync_sort())
        self.load_button = ttk.Button(controls, command=self.load_first_page)
        self.load_button.grid(row=1, column=2, sticky='ew', padx=(10, 0), pady=(3, 8))

        self.api_key_label = ttk.Label(controls, style='Muted.TLabel')
        self.api_key_label.grid(row=2, column=0, sticky='w')
        self.key_controls = ttk.Frame(controls)
        self.key_controls.grid(row=3, column=0, columnspan=2, sticky='ew')
        self.key_controls.columnconfigure(0, weight=1)
        self.api_key_var = tk.StringVar(self.root)
        self.api_key_entry = ttk.Entry(self.key_controls, textvariable=self.api_key_var, show='•')
        self.api_key_entry.grid(row=0, column=0, sticky='ew')
        self.api_key_entry.bind('<Return>', self.apply_api_key)
        self.apply_key_button = ttk.Button(self.key_controls, command=self.apply_api_key)
        self.apply_key_button.grid(row=0, column=1, padx=(8, 0))
        self.api_key_note = ttk.Label(controls, style='Muted.TLabel')
        self.api_key_note.grid(row=4, column=0, columnspan=2, sticky='w', pady=(3, 8))

        self.filter_label = ttk.Label(controls, style='Muted.TLabel')
        self.filter_label.grid(row=2, column=2, sticky='w', padx=(10, 0))
        self.filter_var = tk.StringVar(self.root)
        self.filter_entry = ttk.Entry(controls, textvariable=self.filter_var)
        self.filter_entry.grid(row=3, column=2, sticky='ew', padx=(10, 0))
        self.filter_entry.bind('<Escape>', lambda _event: self.filter_var.set(''))
        self.filter_var.trace_add('write', lambda *_args: self._refresh_mod_list())
        self.load_more_button = ttk.Button(controls, command=self.load_next_page, state='disabled')
        self.load_more_button.grid(row=4, column=2, sticky='ew', padx=(10, 0), pady=(3, 8))

        content = ttk.Panedwindow(self.frame, orient='horizontal')
        content.grid(row=3, column=0, sticky='nsew')
        left = ttk.Frame(content, padding=(0, 0, 10, 0))
        right = ttk.Frame(content, padding=(10, 0, 0, 0))
        content.add(left, weight=2)
        content.add(right, weight=3)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.mod_tree = ttk.Treeview(left, columns=('version', 'author', 'updated'),
                                     show='tree headings', selectmode='browse')
        self.mod_tree.heading('#0', text='Mod')
        self.mod_tree.heading('version', text='Version')
        self.mod_tree.heading('author', text='Author')
        self.mod_tree.heading('updated', text='Updated')
        self.mod_tree.column('#0', width=260, minwidth=160)
        self.mod_tree.column('version', width=80, minwidth=60, stretch=False)
        self.mod_tree.column('author', width=110, minwidth=80)
        self.mod_tree.column('updated', width=105, minwidth=85, stretch=False)
        mod_scroll = ttk.Scrollbar(left, orient='vertical', command=self.mod_tree.yview)
        self.mod_tree.configure(yscrollcommand=mod_scroll.set)
        self.mod_tree.grid(row=0, column=0, sticky='nsew')
        mod_scroll.grid(row=0, column=1, sticky='ns')
        self.mod_tree.bind('<<TreeviewSelect>>', self._select_mod)

        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        action_row = ttk.Frame(right)
        action_row.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        self.open_page_button = ttk.Button(action_row, command=self.open_mod_page, state='disabled')
        self.open_page_button.pack(side='left')
        self.manager_button = ttk.Button(action_row, command=self.handoff_selected_version,
                                         state='disabled')
        self.manager_button.pack(side='left', padx=(8, 0))
        self.manager_hint = ttk.Label(action_row, style='Muted.TLabel')
        self.manager_hint.pack(side='left', padx=10)

        self.tabs = ttk.Notebook(right)
        self.tabs.grid(row=1, column=0, sticky='nsew')
        description_frame = ttk.Frame(self.tabs, padding=8)
        description_frame.rowconfigure(0, weight=1)
        description_frame.columnconfigure(0, weight=1)
        self.description_text = tk.Text(description_frame, wrap='word', height=15,
                                        borderwidth=0, padx=8, pady=8, state='disabled')
        description_scroll = ttk.Scrollbar(description_frame, orient='vertical',
                                           command=self.description_text.yview)
        self.description_text.configure(yscrollcommand=description_scroll.set)
        self.description_text.grid(row=0, column=0, sticky='nsew')
        description_scroll.grid(row=0, column=1, sticky='ns')
        self.tabs.add(description_frame)

        versions_frame = ttk.Frame(self.tabs, padding=8)
        versions_frame.rowconfigure(1, weight=1)
        versions_frame.columnconfigure(0, weight=1)
        self.files_label = ttk.Label(versions_frame, style='Muted.TLabel')
        self.files_label.grid(row=0, column=0, sticky='w')
        files_split = ttk.Panedwindow(versions_frame, orient='vertical')
        files_split.grid(row=1, column=0, sticky='nsew', pady=(5, 0))
        file_panel = ttk.Frame(files_split)
        version_panel = ttk.Frame(files_split)
        file_panel.rowconfigure(0, weight=1)
        file_panel.columnconfigure(0, weight=1)
        version_panel.rowconfigure(0, weight=1)
        version_panel.columnconfigure(0, weight=1)
        files_split.add(file_panel, weight=1)
        files_split.add(version_panel, weight=2)
        self.file_tree = ttk.Treeview(file_panel, columns=('file_id',), show='tree headings', height=5,
                                      selectmode='browse')
        self.file_tree.heading('#0', text='File')
        self.file_tree.heading('file_id', text='ID')
        self.file_tree.column('#0', width=250, minwidth=160)
        self.file_tree.column('file_id', width=95, minwidth=70, stretch=False)
        self.file_tree.grid(row=0, column=0, sticky='nsew')
        self.file_tree.bind('<<TreeviewSelect>>', self._select_file)
        self.versions_tree = ttk.Treeview(version_panel, columns=('version', 'category', 'uploaded'),
                                          show='tree headings', selectmode='browse')
        self.versions_tree.heading('#0', text='Version name')
        self.versions_tree.heading('version', text='Version')
        self.versions_tree.heading('category', text='File type')
        self.versions_tree.heading('uploaded', text='Uploaded')
        self.versions_tree.column('#0', width=180, minwidth=120)
        self.versions_tree.column('version', width=90, minwidth=65, stretch=False)
        self.versions_tree.column('category', width=90, minwidth=65, stretch=False)
        self.versions_tree.column('uploaded', width=110, minwidth=90, stretch=False)
        self.versions_tree.grid(row=0, column=0, sticky='nsew')
        self.versions_tree.bind('<<TreeviewSelect>>', self._select_version)
        self.tabs.add(versions_frame)

        dependencies_frame = ttk.Frame(self.tabs, padding=8)
        dependencies_frame.rowconfigure(0, weight=1)
        dependencies_frame.columnconfigure(0, weight=1)
        self.dependencies_text = tk.Text(dependencies_frame, wrap='word', height=15,
                                         borderwidth=0, padx=8, pady=8, state='disabled')
        dependencies_scroll = ttk.Scrollbar(dependencies_frame, orient='vertical',
                                            command=self.dependencies_text.yview)
        self.dependencies_text.configure(yscrollcommand=dependencies_scroll.set)
        self.dependencies_text.grid(row=0, column=0, sticky='nsew')
        dependencies_scroll.grid(row=0, column=1, sticky='ns')
        self.tabs.add(dependencies_frame)

        self.status_var = tk.StringVar(self.root)
        self.status_label = ttk.Label(self.frame, textvariable=self.status_var,
                                      style='Muted.TLabel', wraplength=1100)
        self.status_label.grid(row=4, column=0, sticky='ew', pady=(9, 0))

    def set_language(self, language):
        self.language = language
        self.title_label.configure(text=self.tr('nexus_title'))
        self.intro_label.configure(text=self.tr('nexus_intro'))
        self.game_label.configure(text=self.tr('nexus_game'))
        self.sort_label.configure(text=self.tr('nexus_sort'))
        self.api_key_label.configure(text=self.tr('nexus_api_key'))
        self.api_key_note.configure(text=self.tr('nexus_key_note'))
        self.apply_key_button.configure(text=self.tr('nexus_use_key'))
        self.load_button.configure(text=self.tr('nexus_load'))
        self.filter_label.configure(text=self.tr('nexus_filter'))
        self.load_more_button.configure(text=self.tr('nexus_load_more'))
        self.open_page_button.configure(text=self.tr('nexus_open_page'))
        self.manager_button.configure(text=self.tr('nexus_send_manager'))
        ready = callable(getattr(self.download_handoff, 'enqueue_nexus_download', None))
        self.manager_hint.configure(text='' if ready else self.tr('nexus_manager_missing'))
        self.mod_tree.heading('#0', text=self.tr('nexus_mod'))
        self.mod_tree.heading('version', text=self.tr('nexus_version'))
        self.mod_tree.heading('author', text=self.tr('nexus_author'))
        self.mod_tree.heading('updated', text=self.tr('nexus_updated'))
        self.tabs.tab(0, text=self.tr('nexus_description'))
        self.tabs.tab(1, text=self.tr('nexus_files_versions'))
        self.tabs.tab(2, text=self.tr('nexus_dependencies'))
        self.files_label.configure(text=self.tr('nexus_files'))
        self.file_tree.heading('#0', text=self.tr('nexus_file'))
        self.file_tree.heading('file_id', text='ID')
        self.versions_tree.heading('#0', text=self.tr('nexus_version_name'))
        self.versions_tree.heading('version', text=self.tr('nexus_version'))
        self.versions_tree.heading('category', text=self.tr('nexus_file_type'))
        self.versions_tree.heading('uploaded', text=self.tr('nexus_uploaded'))
        sort_labels = tuple(self.tr('nexus_sort_' + sort) for sort in _SORT_FIELDS)
        selected_sort = self._sort_field if hasattr(self, '_sort_field') else 'trending'
        self._sort_label_to_field = dict(zip(sort_labels, _SORT_FIELDS))
        self.sort_selector.configure(values=sort_labels)
        self.sort_var.set(self.tr('nexus_sort_' + selected_sort))
        if not self.status_var.get():
            self.status_var.set(self.tr('nexus_status_initial'))

    def apply_theme(self, palette):
        for widget in (self.description_text, self.dependencies_text):
            widget.configure(background=palette['surface'], foreground=palette['text'],
                             insertbackground=palette['text'], selectbackground=palette['accent'],
                             selectforeground='#ffffff')

    def set_download_handoff(self, handoff):
        """Attach a Mod Manager provided implementation without adding install logic here."""
        self.download_handoff = handoff
        ready = callable(getattr(handoff, 'enqueue_nexus_download', None))
        self.manager_hint.configure(text='' if ready else self.tr('nexus_manager_missing'))
        self._sync_manager_button()

    def _select_initial_game(self, game_id):
        selected = nexus_game_for_id(game_id) if game_id else None
        if selected is None and self._game_by_label:
            selected = next(iter(self._game_by_label.values()))
        if selected is not None:
            label = next(label for label, game in self._game_by_label.items()
                         if game.domain == selected.domain)
            self.game_var.set(label)
        self._sort_field = 'trending'

    def _selected_game(self):
        return self._game_by_label.get(self.game_var.get())

    def _sync_sort(self):
        self._sort_field = self._sort_label_to_field.get(self.sort_var.get(), 'trending')

    def _on_game_changed(self, _event=None):
        self._request_generation += 1
        self._loaded_mods = []
        self._page = 0
        self._total_count = 0
        self._loaded_game_domain = None
        self._loaded_sort_field = None
        self._clear_current_selection()
        self._clear_tree(self.mod_tree)
        self._shown_mods = {}
        self.load_more_button.configure(state='disabled')
        self.status_var.set(self.tr('nexus_status_initial'))

    def _clear_current_selection(self):
        self._selected_summary = None
        self._selected_details = None
        self._selected_file_id = None
        self._selected_version = None
        self._files = {}
        self._versions = {}
        self._clear_tree(self.file_tree)
        self._clear_tree(self.versions_tree)
        self._write_text(self.description_text, '')
        self._write_text(self.dependencies_text, '')
        self._sync_selection_actions()

    def apply_api_key(self, _event=None):
        key = self.api_key_var.get().strip()
        self._client = self._new_client(key or None)
        self.api_key_var.set('')
        self.status_var.set(self.tr('nexus_key_set' if key else 'nexus_key_cleared'))
        if self._selected_summary is not None:
            self._request_generation += 1
            self._select_current_summary()
        return 'break'

    def load_first_page(self):
        game = self._selected_game()
        if game is None:
            self.status_var.set(self.tr('nexus_choose_game'))
            return
        self._request_generation += 1
        generation = self._request_generation
        self._loaded_mods = []
        self._page = 0
        self._total_count = 0
        self._loaded_game_domain = game.domain
        self._loaded_sort_field = self._sort_field
        self._clear_current_selection()
        self._refresh_mod_list()
        client = self._client
        sort = self._sort_field
        self.status_var.set(self.tr('nexus_loading'))
        self._submit(lambda: client.search_mods(game.domain, sort=sort, page=1, page_size=30),
                     self._accept_page, generation=generation)

    def load_next_page(self):
        game = self._selected_game()
        if game is None:
            return
        if self._page >= 100:
            return
        if (not self._page
                or self._loaded_game_domain != game.domain
                or self._loaded_sort_field != self._sort_field):
            self.load_first_page()
            return
        next_page = self._page + 1
        self.status_var.set(self.tr('nexus_loading'))
        client = self._client
        sort = self._sort_field
        generation = self._request_generation
        self._submit(lambda: client.search_mods(game.domain, sort=sort, page=next_page, page_size=30),
                     self._accept_page, generation=generation)

    def _accept_page(self, page):
        if page.page == 1:
            self._loaded_mods = list(page.mods)
        else:
            known = {mod.mod_id for mod in self._loaded_mods}
            self._loaded_mods.extend(mod for mod in page.mods if mod.mod_id not in known)
        self._page = page.page
        self._total_count = page.total_count
        self.load_more_button.configure(state='normal' if page.has_more else 'disabled')
        self._refresh_mod_list()
        self.status_var.set(self.tr('nexus_status_loaded', count=len(self._loaded_mods),
                                    total=self._total_count, pages=self._page))

    def _refresh_mod_list(self):
        visible = search_loaded_mods(self._loaded_mods, self.filter_var.get())
        selected_id = self._selected_summary.mod_id if self._selected_summary else None
        for item in self.mod_tree.get_children():
            self.mod_tree.delete(item)
        self._shown_mods = {}
        for mod in visible:
            self._shown_mods[mod.mod_id] = mod
            self.mod_tree.insert('', 'end', iid=mod.mod_id,
                                 text=mod.name, values=(mod.version, mod.author, mod.updated_at[:10]))
        if selected_id in self._shown_mods:
            self.mod_tree.selection_set(selected_id)
        elif selected_id is not None:
            self._request_generation += 1
            self._clear_current_selection()
        else:
            self._sync_selection_actions()
        if self._loaded_mods and not visible:
            self.status_var.set(self.tr('nexus_no_results'))

    def _select_mod(self, _event=None):
        selection = self.mod_tree.selection()
        if not selection:
            return
        summary = self._shown_mods.get(selection[0])
        if summary is None:
            return
        self._request_generation += 1
        self._selected_summary = summary
        self._selected_details = None
        self._selected_file_id = None
        self._selected_version = None
        self._files = {}
        self._versions = {}
        self._clear_tree(self.file_tree)
        self._clear_tree(self.versions_tree)
        self._write_text(self.dependencies_text, self.tr('nexus_select_version_dependencies'))
        self._sync_selection_actions()
        self._write_text(self.description_text, f'{summary.name}\n{summary.version}\n\n{summary.summary}')
        self._select_current_summary()

    def _select_current_summary(self):
        summary = self._selected_summary
        if summary is None:
            return
        client = self._client
        self.status_var.set(self.tr('nexus_loading'))
        if not client.has_api_key:
            self._write_text(self.description_text,
                             f'{summary.name}\n{summary.version}\n\n{summary.summary}\n\n'
                             + self.tr('nexus_key_required'))
            self.status_var.set(self.tr('nexus_key_required'))
            return
        generation = self._request_generation
        self._submit(lambda: (client.get_mod(summary.game_domain, summary.game_scoped_id),
                              client.get_files(summary.mod_id)),
                     self._accept_mod_details, generation=generation)

    def _accept_mod_details(self, result):
        details, files = result
        self._selected_details = details
        self._files = {item.file_id: item for item in files}
        text = f'{details.name}\n{self.tr("nexus_version")}: {details.version}\n'
        if details.category:
            text += f'{self.tr("nexus_category")}: {details.category}\n'
        text += '\n' + (details.description or self.tr('nexus_no_description'))
        self._write_text(self.description_text, text)
        self._clear_tree(self.file_tree)
        self._clear_tree(self.versions_tree)
        self._selected_version = None
        for file in files:
            self.file_tree.insert('', 'end', iid=file.file_id, text=file.name, values=(file.file_id,))
        if files:
            first = files[0].file_id
            self.file_tree.selection_set(first)
            self.file_tree.focus(first)
            self._load_versions(first)
        else:
            self._selected_file_id = None
            self._write_text(self.dependencies_text, self.tr('nexus_no_files'))
        self.status_var.set(self.tr('nexus_details_loaded'))

    def _select_file(self, _event=None):
        selection = self.file_tree.selection()
        if selection and selection[0] != self._selected_file_id:
            self._load_versions(selection[0])

    def _load_versions(self, file_id):
        self._request_generation += 1
        client = self._client
        generation = self._request_generation
        self._selected_file_id = file_id
        self._selected_version = None
        self._versions = {}
        self._clear_tree(self.versions_tree)
        self._sync_manager_button()
        self._write_text(self.dependencies_text, self.tr('nexus_select_version_dependencies'))
        self._submit(lambda: (file_id, client.get_versions(file_id)),
                     self._accept_versions, generation=generation)

    def _accept_versions(self, result):
        file_id, versions = result
        self._versions = {version.version_id: version for version in versions}
        self._selected_version = None
        self._clear_tree(self.versions_tree)
        for version in versions:
            self.versions_tree.insert('', 'end', iid=version.version_id,
                                      text=version.name, values=(version.version, version.category,
                                                                  version.uploaded_at[:10]))
        if versions:
            first = versions[0].version_id
            self._selected_version = versions[0]
            self.versions_tree.selection_set(first)
            self.versions_tree.focus(first)
            self._sync_manager_button()
            self._load_dependencies(first)
        else:
            self._write_text(self.dependencies_text, self.tr('nexus_no_versions'))
        self._sync_manager_button()

    def _select_version(self, _event=None):
        selection = self.versions_tree.selection()
        if not selection:
            if self._selected_version is not None:
                self._request_generation += 1
                self._write_text(self.dependencies_text,
                                 self.tr('nexus_select_version_dependencies'))
            self._selected_version = None
            self._sync_manager_button()
            return
        version_id = selection[0]
        if self._selected_version is not None and self._selected_version.version_id == version_id:
            return
        self._selected_version = self._versions.get(version_id)
        self._sync_manager_button()
        if self._selected_version is not None:
            self._request_generation += 1
            self._load_dependencies(version_id)

    def _load_dependencies(self, version_id):
        client = self._client
        generation = self._request_generation
        self._submit(lambda: client.get_dependencies(version_id), self._accept_dependencies,
                     generation=generation)

    def _accept_dependencies(self, dependencies):
        lines = []
        for index, definition in enumerate(dependencies.definitions, start=1):
            lines.append(self.tr('nexus_dependency_group', index=index))
            if not definition.alternatives:
                lines.append('  ' + self.tr('nexus_dependency_no_candidates'))
            for item in definition.alternatives:
                bounds = item.minimum_version or self.tr('nexus_unknown_version')
                if item.maximum_version:
                    bounds += ' – ' + item.maximum_version
                elif item.minimum_version:
                    bounds += ' ' + self.tr('nexus_or_later')
                lines.append(f'  {item.mod_name} / {item.file_name} — {bounds}')
        for index, definition in enumerate(dependencies.dlc_definitions, start=1):
            lines.append(self.tr('nexus_dlc_group', index=index))
            lines.extend('  ' + name for name in definition.alternatives)
        if not lines:
            lines.append(self.tr('nexus_no_dependencies'))
        self._write_text(self.dependencies_text, '\n'.join(lines))

    def open_mod_page(self):
        summary = self._selected_summary
        game = self._selected_game()
        if (summary is None or game is None or summary.game_domain != game.domain
                or summary.mod_id not in self._shown_mods):
            return
        webbrowser.open(mod_page_url(summary.game_domain, summary.game_scoped_id))

    def _sync_manager_button(self):
        ready = callable(getattr(self.download_handoff, 'enqueue_nexus_download', None))
        game = self._selected_game()
        selection = self.file_tree.selection()
        file_matches = (self._selected_version is not None
                        and self._selected_file_id == self._selected_version.file_id
                        and selection == (self._selected_version.file_id,))
        same_game = (self._selected_summary is not None and game is not None
                     and self._selected_summary.game_domain == game.domain)
        visible_mod = (self._selected_summary is not None
                       and self._selected_summary.mod_id in self._shown_mods)
        state = ('normal' if ready and file_matches and same_game and visible_mod else 'disabled')
        self.manager_button.configure(state=state)

    def _sync_selection_actions(self):
        game = self._selected_game()
        summary = self._selected_summary
        visible_mod = summary is not None and summary.mod_id in self._shown_mods
        same_game = summary is not None and game is not None and summary.game_domain == game.domain
        self.open_page_button.configure(state='normal' if visible_mod and same_game else 'disabled')
        self._sync_manager_button()

    def focus_search(self):
        self.filter_entry.focus_set()
        self.filter_entry.selection_range(0, 'end')
        return 'break'

    def handoff_selected_version(self):
        summary = self._selected_summary
        version = self._selected_version
        handoff = self.download_handoff
        if (summary is None or version is None or handoff is None
                or summary.game_domain != (self._selected_game().domain if self._selected_game() else None)
                or summary.mod_id not in self._shown_mods
                or self._selected_file_id != version.file_id
                or self.file_tree.selection() != (version.file_id,)):
            return False
        request = build_download_request(summary, version)
        enqueue = getattr(handoff, 'enqueue_nexus_download', None)
        if not callable(enqueue):
            self.status_var.set(self.tr('nexus_manager_invalid'))
            return False
        try:
            accepted = enqueue(request)
        except Exception:
            self.status_var.set(self.tr('nexus_manager_error'))
            return False
        self.status_var.set(self.tr('nexus_manager_accepted' if accepted else 'nexus_manager_rejected'))
        return bool(accepted)

    def _submit(self, operation, on_success, *, generation):
        if self._closed:
            return
        self._busy += 1
        future = self._executor.submit(operation)

        def finished(completed):
            self._result_queue.put((completed, on_success, generation))

        future.add_done_callback(finished)

    def _poll_results(self):
        self._poll_id = None
        if self._closed:
            return
        while True:
            try:
                future, on_success, generation = self._result_queue.get_nowait()
            except queue.Empty:
                break
            self._busy = max(0, self._busy - 1)
            if generation != self._request_generation:
                continue
            try:
                result = future.result()
            except NexusApiError as error:
                self.status_var.set(str(error))
            except Exception:
                self.status_var.set(self.tr('nexus_request_failed'))
            else:
                on_success(result)
        self._poll_id = self.frame.after(100, self._poll_results)

    @staticmethod
    def _clear_tree(tree):
        for item in tree.get_children():
            tree.delete(item)

    @staticmethod
    def _write_text(widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._poll_id is not None:
            try:
                self.frame.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        self._executor.shutdown(wait=False, cancel_futures=True)

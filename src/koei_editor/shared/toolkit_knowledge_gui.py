"""Read-only encyclopedia and explicit-snapshot comparison workspaces.

These desktop surfaces use the same bundled provenance and comparison contracts
as the source tools. They never discover or modify a game installation.
"""

from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.game_data_encyclopedia import load_game_data_encyclopedia
from koei_editor.shared.game_compatibility import (
    analyze_snapshots, load_json, render_markdown,
)


_TEXT = {
    'en': {
        'encyclopedia': 'Game Data Encyclopedia',
        'scope': 'Read-only reference for Three Hopes (Switch) and Hyrule Warriors (Wii U). Coverage is limited to the bundled, source-attributed records; it does not establish ownership, unlocks or game compatibility.',
        'find': 'Find records', 'game': 'Game / edition', 'kind': 'Record kind',
        'all': 'All', 'name': 'Name', 'native_id': 'Native ID',
        'details': 'Record details and sources', 'select': 'Select a record to read its exact edition, sources and license.',
        'results': '{count} matching records · {total} bundled records',
        'analyzer': 'Game Patch & Compatibility Analyzer',
        'analyzer_intro': 'Compare explicit before/after snapshot JSON files and optional declared requirements. This does not scan installations or certify that a game, mod or save will load.',
        'analyzer_intro_compact': 'Compare explicit snapshots; results do not verify that games, mods or saves load.',
        'baseline': 'Baseline snapshot', 'candidate': 'Candidate snapshot',
        'requirements': 'Requirements (optional)', 'browse': 'Browse…', 'clear': 'Clear',
        'compare': 'Compare snapshots', 'export_json': 'Export JSON…',
        'export_md': 'Export Markdown…', 'ready': 'Choose baseline and candidate snapshot files.',
        'busy': 'Reading and comparing the selected snapshots…',
        'complete': 'Comparison complete. Review the evidence and interpretation below.',
        'changed': 'Inputs changed. Compare again before exporting.',
        'missing': 'Choose both a baseline and a candidate snapshot.',
        'failed': 'Comparison could not be completed.', 'saved': 'A new report was exported. Input files were unchanged.',
        'error': 'Report error',
    },
    'de': {
        'encyclopedia': 'Spieldaten-Enzyklopädie',
        'scope': 'Schreibgeschützte Referenz für Three Hopes (Switch) und Hyrule Warriors (Wii U). Enthalten sind nur die belegten Datensätze; Besitz, Freischaltungen und Spielkompatibilität werden daraus nicht abgeleitet.',
        'find': 'Datensätze suchen', 'game': 'Spiel / Edition', 'kind': 'Datensatztyp',
        'all': 'Alle', 'name': 'Name', 'native_id': 'Native ID',
        'details': 'Datensatzdetails und Quellen', 'select': 'Wähle einen Datensatz, um Edition, Quellen und Lizenz zu lesen.',
        'results': '{count} passende Datensätze · {total} enthaltene Datensätze',
        'analyzer': 'Spielpatch- und Kompatibilitätsanalyse',
        'analyzer_intro': 'Vergleiche explizite Vorher-/Nachher-Snapshot-JSON-Dateien und optionale Anforderungen. Installationen werden nicht geprüft; die Ladefähigkeit von Spielen, Mods oder Spielständen wird nicht bestätigt.',
        'analyzer_intro_compact': 'Vergleiche explizite Snapshots; keine Prüfung der Ladefähigkeit im Spiel.',
        'baseline': 'Ausgangs-Snapshot', 'candidate': 'Neuer Snapshot',
        'requirements': 'Anforderungen (optional)', 'browse': 'Durchsuchen…', 'clear': 'Leeren',
        'compare': 'Snapshots vergleichen', 'export_json': 'JSON exportieren…',
        'export_md': 'Markdown exportieren…', 'ready': 'Wähle den Ausgangs-Snapshot und den neuen Snapshot.',
        'busy': 'Ausgewählte Snapshots werden gelesen und verglichen…',
        'complete': 'Vergleich abgeschlossen. Prüfe die Belege und ihre Interpretation unten.',
        'changed': 'Eingaben geändert. Vor dem Export erneut vergleichen.',
        'missing': 'Wähle beide Snapshot-Dateien.', 'failed': 'Vergleich konnte nicht abgeschlossen werden.',
        'saved': 'Ein neuer Bericht wurde exportiert. Eingabedateien blieben unverändert.',
        'error': 'Berichtsfehler',
    },
}


def filter_encyclopedia(data, query='', game_id=None, kind=None):
    """Return reference rows matching all words, without altering the feed."""
    games = {row['id']: row for row in data['games']}
    words = str(query).casefold().split()
    rows = []
    for row in data['entities']:
        if game_id is not None and row['game_id'] != game_id:
            continue
        if kind is not None and row['kind'] != kind:
            continue
        game = games[row['game_id']]
        searchable = ' '.join((
            row['id'], row['name'], row['kind'], str(row.get('native_id', '')),
            row.get('summary', ''), game['title'], game['edition'], game['platform'],
            json.dumps(row.get('attributes', {}), ensure_ascii=False, sort_keys=True),
        )).casefold()
        if all(word in searchable for word in words):
            rows.append(row)
    return tuple(sorted(rows, key=lambda row: (games[row['game_id']]['title'].casefold(),
                                             row['kind'], row['name'].casefold(), row['id'])))


def encyclopedia_details(data, entity_id):
    """Render exact profile context and field-level attribution together."""
    row = next((row for row in data['entities'] if row['id'] == entity_id), None)
    if row is None:
        raise ValueError('Unknown encyclopedia record.')
    game = next(game for game in data['games'] if game['id'] == row['game_id'])
    sources = {source['id']: source for source in data['sources']}
    lines = [row['name'], f"{game['title']} · {game['platform']}", game['edition'],
             f"Record: {row['id']}", f"Kind: {row['kind']}"]
    if 'native_id' in row:
        lines.append(f"Native ID: {row['native_id']}")
    lines.extend(('', game['scope_note']))
    if 'summary' in row:
        lines.extend(('', row['summary']))
    if row.get('attributes'):
        lines.extend(('', 'Attributes:', json.dumps(row['attributes'], ensure_ascii=False, indent=2, sort_keys=True)))
    if row.get('relationships'):
        lines.extend(('', 'Source-backed relationships:'))
        for relation in row['relationships']:
            lines.append(f"{relation['type']}: {relation['entity_id']}")
    fields_by_source = {}
    for field, source_id in row['field_sources'].items():
        fields_by_source.setdefault(source_id, []).append(field)
    fields_by_source.setdefault(game['profile_source_id'], []).append('game.profile')
    for relation in row.get('relationships', ()):
        fields_by_source.setdefault(relation['source_id'], []).append('relationships')
    lines.extend(('', 'Sources and licenses:'))
    for source_id, fields in sorted(fields_by_source.items()):
        source = sources[source_id]
        lines.extend(('', source['title'], f"Fields: {', '.join(sorted(set(fields)))}",
                      source['uri'], f"License: {source['license']} · {source['license_uri']}",
                      f"Attribution: {source['attribution']}", f"Scope: {source['scope']}"))
        if source.get('revision'):
            lines.append(f"Revision: {source['revision']}")
        if source.get('accessed_on'):
            lines.append(f"Accessed: {source['accessed_on']}")
    lines.extend(('', data['dataset_license_note']))
    return '\n'.join(lines)


def analyze_snapshot_files(baseline, candidate, requirements=None):
    """Read explicit bounded JSON inputs and invoke the existing analyzer."""
    before = load_json(baseline)
    after = load_json(candidate)
    required = load_json(requirements) if requirements else None
    return analyze_snapshots(before, after, required)


def export_compatibility_report(report, destination):
    """Export to a new JSON or Markdown file using exclusive publication."""
    destination = Path(destination)
    if destination.suffix.casefold() == '.json':
        content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    elif destination.suffix.casefold() == '.md':
        content = render_markdown(report)
    else:
        raise ValueError('Choose a new .json or .md report filename.')
    return atomic_new(content.encode('utf-8'), destination)


class _KnowledgeWorkspace:
    shutdown_safe_while_busy = True

    def __init__(self, root, parent, language):
        self.root = root
        self.language = 'de' if str(language).lower().startswith('de') else 'en'
        self.frame = ttk.Frame(parent, padding=16)
        self._labels = []
        self._wrapped_labels = []
        self._text_widgets = []
        self._closed = False
        self._poll_id = None
        self.busy = False
        self.frame.bind('<Destroy>', self._destroyed, add='+')
        self.frame.bind('<Configure>', self._resize_labels, add='+')

    def tr(self, key, **values):
        return _TEXT[self.language][key].format(**values)

    def _label(self, parent, key, **options):
        widget = ttk.Label(parent, text=self.tr(key), **options)
        self._labels.append((widget, key))
        if 'wraplength' in options:
            self._wrapped_labels.append((widget, key))
        return widget

    def _button(self, parent, key, command, **options):
        widget = ttk.Button(parent, text=self.tr(key), command=command, **options)
        self._labels.append((widget, key))
        return widget

    def _text_panel(self, parent):
        host = ttk.Frame(parent)
        text = tk.Text(host, wrap='word', height=10, state='disabled', padx=10, pady=8)
        scrollbar = ttk.Scrollbar(host, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        text.pack(fill='both', expand=True)
        self._text_widgets.append(text)
        return host, text

    @staticmethod
    def _set_text(widget, content):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.configure(state='disabled')

    def apply_theme(self, palette):
        for widget in self._text_widgets:
            widget.configure(background=palette['surface'], foreground=palette['text'],
                             insertbackground=palette['text'], selectbackground=palette['accent'])

    def set_text_size(self, size, font_family):
        for widget in self._text_widgets:
            widget.configure(font=(font_family, max(8, size)))

    def apply_font(self, font_family, size):
        self.set_text_size(size, font_family)

    def set_language(self, language):
        self.language = 'de' if str(language).lower().startswith('de') else 'en'
        for widget, key in self._labels:
            widget.configure(text=self.tr(key))
        self._resize_labels()

    def _resize_labels(self, event=None):
        if self._closed or (event is not None and event.widget is not self.frame):
            return
        width = max(200, self.frame.winfo_width() - 32)
        compact = self.frame.winfo_height() < 500
        for widget, key in self._wrapped_labels:
            widget.configure(wraplength=width)
            if key == 'analyzer_intro':
                widget.configure(text=self.tr('analyzer_intro_compact' if compact else key))

    def _destroyed(self, event):
        if event.widget is self.frame:
            self.close()

    def close(self):
        self._closed = True
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

    shutdown = close


class EncyclopediaWorkspace(_KnowledgeWorkspace):
    """Search the bundled reference feed while preserving its exact scope."""

    def __init__(self, root, parent, language='en'):
        super().__init__(root, parent, language)
        self.data = load_game_data_encyclopedia()
        self._games = {game['id']: game for game in self.data['games']}
        self._entities = {row['id']: row for row in self.data['entities']}
        self._game_ids = (None, *sorted(self._games, key=lambda key: self._games[key]['title']))
        self._kinds = (None, *sorted({row['kind'] for row in self.data['entities']}))
        self._label(self.frame, 'encyclopedia', style='Title.TLabel').pack(anchor='w')
        self._label(self.frame, 'scope', wraplength=1000).pack(anchor='w', fill='x', pady=(6, 12))
        filters = ttk.Frame(self.frame)
        filters.pack(fill='x', pady=(0, 10))
        filters.columnconfigure(0, weight=2)
        filters.columnconfigure(1, weight=2)
        filters.columnconfigure(2, weight=1)
        self._label(filters, 'find').grid(row=0, column=0, sticky='w')
        self._label(filters, 'game').grid(row=0, column=1, sticky='w', padx=8)
        self._label(filters, 'kind').grid(row=0, column=2, sticky='w')
        self.search = tk.StringVar(root)
        self.search_entry = ttk.Entry(filters, textvariable=self.search)
        self.search_entry.grid(row=1, column=0, sticky='ew')
        self.game_selector = ttk.Combobox(filters, state='readonly', width=32)
        self.game_selector.grid(row=1, column=1, sticky='ew', padx=8)
        self.kind_selector = ttk.Combobox(filters, state='readonly', width=15)
        self.kind_selector.grid(row=1, column=2, sticky='ew')
        self._update_selectors()
        self.game_selector.current(0)
        self.kind_selector.current(0)
        self.status = tk.StringVar(root)
        ttk.Label(self.frame, textvariable=self.status).pack(anchor='w', pady=(0, 6))
        # Side-by-side panes retain useful height for both records and sources
        # when the shared shell leaves a short viewport at large text sizes.
        panes = ttk.Panedwindow(self.frame, orient='horizontal')
        panes.pack(fill='both', expand=True)
        table_host = ttk.Frame(panes)
        self.table = ttk.Treeview(table_host, columns=('name', 'game', 'kind', 'native_id'), show='headings', height=4)
        for name, width in (('name', 180), ('game', 190), ('kind', 80), ('native_id', 60)):
            self.table.column(name, width=width, minwidth=60, stretch=True)
        vertical = ttk.Scrollbar(table_host, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(table_host, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table_host.rowconfigure(0, weight=1)
        table_host.columnconfigure(0, weight=1)
        self.table.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        panes.add(table_host, weight=1)
        details_host = ttk.Frame(panes)
        self._label(details_host, 'details').pack(anchor='w', pady=(6, 4))
        details_panel, self.details = self._text_panel(details_host)
        self.details.configure(width=38)
        details_panel.pack(fill='both', expand=True)
        panes.add(details_host, weight=1)
        self.search.trace_add('write', lambda *_: self.refresh())
        self.game_selector.bind('<<ComboboxSelected>>', lambda *_: self.refresh())
        self.kind_selector.bind('<<ComboboxSelected>>', lambda *_: self.refresh())
        self.table.bind('<<TreeviewSelect>>', self._selected)
        self._refresh_headings()
        self.refresh()

    def _update_selectors(self):
        self.game_selector.configure(values=(self.tr('all'), *(f"{self._games[key]['title']} · {self._games[key]['platform']}" for key in self._game_ids[1:])))
        self.kind_selector.configure(values=(self.tr('all'), *self._kinds[1:]))

    def _refresh_headings(self):
        for column in ('name', 'game', 'kind', 'native_id'):
            self.table.heading(column, text=self.tr(column))

    def refresh(self):
        selected = self.table.selection()
        game_index = max(0, self.game_selector.current())
        kind_index = max(0, self.kind_selector.current())
        self.rows = filter_encyclopedia(self.data, self.search.get(), self._game_ids[game_index], self._kinds[kind_index])
        children = self.table.get_children()
        if children:
            self.table.delete(*children)
        for row in self.rows:
            game = self._games[row['game_id']]
            self.table.insert('', 'end', iid=row['id'], values=(row['name'], f"{game['title']} · {game['platform']}", row['kind'], row.get('native_id', '')))
        self.status.set(self.tr('results', count=len(self.rows), total=len(self.data['entities'])))
        if selected and self.table.exists(selected[0]):
            self.table.selection_set(selected[0])
            self._selected()
        else:
            self._set_text(self.details, self.tr('select'))

    def _selected(self, _event=None):
        selected = self.table.selection()
        if selected:
            self._set_text(self.details, encyclopedia_details(self.data, selected[0]))

    def set_language(self, language):
        game_index, kind_index = self.game_selector.current(), self.kind_selector.current()
        super().set_language(language)
        self._update_selectors()
        self.game_selector.current(max(0, game_index))
        self.kind_selector.current(max(0, kind_index))
        self._refresh_headings()
        self.refresh()


class PatchCompatibilityWorkspace(_KnowledgeWorkspace):
    """Compare explicit snapshots asynchronously, then export new reports."""

    def __init__(self, root, parent, language='en'):
        super().__init__(root, parent, language)
        self.report = None
        self._revision = 0
        self._results = queue.SimpleQueue()
        self._controls = []
        self._status_key = 'ready'
        self._label(self.frame, 'analyzer', style='Title.TLabel').pack(anchor='w')
        self._intro_label = self._label(self.frame, 'analyzer_intro', wraplength=1000)
        self._intro_label.pack(anchor='w', fill='x', pady=(6, 12))
        self.paths = {}
        self._form = form = ttk.Frame(self.frame)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        for index, key in enumerate(('baseline', 'candidate', 'requirements')):
            self._label(form, key).grid(row=index, column=0, sticky='w', padx=(0, 12), pady=4)
            variable = tk.StringVar(root)
            self.paths[key] = variable
            entry = ttk.Entry(form, textvariable=variable)
            entry.grid(row=index, column=1, sticky='ew', pady=4)
            button = self._button(form, 'browse', lambda field=key: self.browse(field))
            button.grid(row=index, column=2, padx=(8, 0), pady=4)
            clear = self._button(form, 'clear', lambda field=key: self.paths[field].set(''))
            clear.grid(row=index, column=3, padx=(8, 0), pady=4)
            self._controls.extend((entry, button, clear))
            variable.trace_add('write', self._inputs_changed)
        self._action_row = actions = ttk.Frame(self.frame)
        actions.pack(fill='x', pady=10)
        self.compare_button = self._button(actions, 'compare', self.compare, style='Primary.TButton')
        self.compare_button.pack(side='left')
        self._controls.append(self.compare_button)
        self.json_button = self._button(actions, 'export_json', lambda: self.export('.json'), state='disabled')
        self.json_button.pack(side='left', padx=8)
        self.markdown_button = self._button(actions, 'export_md', lambda: self.export('.md'), state='disabled')
        self.markdown_button.pack(side='left')
        self.status = tk.StringVar(root, value=self.tr('ready'))
        self._status_label = ttk.Label(self.frame, textvariable=self.status)
        self._status_label.pack(anchor='w', pady=(0, 8))
        panel, self.preview = self._text_panel(self.frame)
        panel.pack(fill='both', expand=True)
        self._set_text(self.preview, self.tr('ready'))

    def _resize_labels(self, event=None):
        super()._resize_labels(event)
        if self._closed or not hasattr(self, '_status_label'):
            return
        compact = self.frame.winfo_height() < 500
        self.frame.configure(padding=8 if compact else 16)
        self._intro_label.pack_configure(pady=(2, 2) if compact else (6, 12))
        for widget in self._form.grid_slaves():
            widget.grid_configure(pady=0 if compact else 4)
        self._action_row.pack_configure(pady=1 if compact else 10)
        self._status_label.pack_configure(pady=(0, 2) if compact else (0, 8))

    def _status(self, key):
        self._status_key = key
        self.status.set(self.tr(key))

    def _inputs_changed(self, *_args):
        self._revision += 1
        self.report = None
        if hasattr(self, 'json_button'):
            self.json_button.configure(state='disabled')
            self.markdown_button.configure(state='disabled')
            self._set_text(self.preview, self.tr('changed'))
            self._status('changed')

    def browse(self, field):
        path = filedialog.askopenfilename(parent=self.root, title=self.tr(field),
                                          filetypes=(('JSON', '*.json'), ('All files', '*')))
        if path:
            self.paths[field].set(path)

    def _set_busy(self, value):
        self.busy = value
        for widget in self._controls:
            widget.configure(state='disabled' if value else 'normal')
        for widget in (self.json_button, self.markdown_button):
            widget.configure(state='normal' if not value and self.report is not None else 'disabled')

    def compare(self):
        if self.busy or self._closed:
            return
        inputs = {key: variable.get().strip() for key, variable in self.paths.items()}
        if not inputs['baseline'] or not inputs['candidate']:
            self._status('missing')
            return
        self.report = None
        revision = self._revision
        self._set_busy(True)
        self._status('busy')
        self._set_text(self.preview, self.tr('busy'))

        def worker():
            try:
                report = analyze_snapshot_files(inputs['baseline'], inputs['candidate'], inputs['requirements'] or None)
                self._results.put((revision, report, render_markdown(report), None))
            except (OSError, ValueError, SaveError, RecursionError) as error:
                self._results.put((revision, None, None, str(error)))

        threading.Thread(target=worker, daemon=True, name='toolkit-patch-comparison').start()
        self._poll_id = self.root.after(40, self._poll)

    def _poll(self):
        self._poll_id = None
        if self._closed:
            return
        try:
            revision, report, markdown, error = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.root.after(40, self._poll)
            return
        if revision != self._revision:
            self._set_busy(False)
            self._status('changed')
            return
        self.report = report
        self._set_busy(False)
        self._status('failed' if error else 'complete')
        self._set_text(self.preview, error if error else markdown)

    def export(self, suffix):
        if self.busy or self.report is None:
            return
        destination = filedialog.asksaveasfilename(parent=self.root, defaultextension=suffix,
            initialfile='GameCompatibilityReport' + suffix,
            filetypes=(('JSON', '*.json'),) if suffix == '.json' else (('Markdown', '*.md'),))
        if not destination:
            return
        try:
            export_compatibility_report(self.report, destination)
        except (OSError, ValueError, SaveError) as error:
            messagebox.showerror(self.tr('error'), str(error), parent=self.root)
            return
        self._status('saved')

    def set_language(self, language):
        super().set_language(language)
        self._status(self._status_key)
        if self.report is None and not self.busy:
            self._set_text(self.preview, self.tr(self._status_key))

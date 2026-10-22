"""Read-only installed-build and exact-build compatibility workspace."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from koei_editor.game_registry import GAMES
from koei_editor.shared import version_tracker


_TEXT = {
    'en': {
        'title': 'Game Version & Compatibility Tracker',
        'scope': ('Scans reviewed Steam app manifests only. It does not launch games, inspect save files, '
                  'or read Steam user data. Detected Steam build IDs are separate from save-format revisions.'),
        'scan': 'Scan Steam installs', 'refresh': 'Refresh history', 'search': 'Filter installed games',
        'privacy': ('Build history is saved locally without install paths, Steam account IDs, or save data.'),
        'installed': 'Installed builds', 'compat': 'Current compatibility', 'build_history': 'Build history',
        'compat_history': 'Compatibility history', 'game': 'Game', 'platform': 'Platform', 'build': 'Steam Build ID',
        'updated': 'Steam Last Updated (Unix seconds)', 'artifact': 'Tool or format', 'kind': 'Type', 'status': 'Status',
        'version': 'Reviewed artifact version', 'checked': 'Checked', 'previous': 'Previous build', 'observed': 'Observed build',
        'date': 'Observed at', 'event': 'Change', 'details': 'Details', 'loading': 'Reading reviewed Steam manifests…',
        'no_installs': ('No reviewed Steam installation was detected. Non-Steam stores and unmapped game editions '
                        'are not detected by this scan.'),
        'clean_scan': 'Scan complete. No game was launched and no save or account data was read.',
        'scan_issue': ('Some Steam metadata was unreadable or malformed and was ignored. '
                       'The displayed scan may be incomplete.'),
        'scan_stopped': 'The bounded scan stopped early; displayed results may be incomplete.',
        'scan_error': 'The Steam manifest scan could not complete. No tracker history was changed.',
        'history_error': ('Local tracker history is unavailable or invalid. The current scan is still shown, '
                          'but history was not overwritten.'),
        'select_build': 'Select an installed build to review its exact-build compatibility records.',
        'select_record': 'Select a compatibility row to read its explanation and evidence.',
        'select_history': 'Select a history row to review the recorded build change.',
        'no_history': 'No build changes have been recorded on this computer.',
        'no_compat_history': 'No reviewed compatibility history is recorded for this game profile.',
        'unknown_build': 'No Steam build ID was present in the reviewed manifest.',
        'unknown': 'Unknown', 'first_seen': 'First detected', 'build_changed': 'Build ID changed',
        'not_checked': 'Not checked', 'verified': 'Verified', 'unsupported': 'Unsupported',
        'unknown_status': 'Unknown', 'kind_save_editor': 'Save editor', 'kind_mod': 'Mod',
        'kind_config_tool': 'Configuration tool', 'kind_asset_format': 'Asset format',
        'source': 'Detection source', 'confidence': 'Confidence', 'app_id': 'Steam app ID',
        'evidence': 'Evidence', 'reason': 'Reason code', 'next_steps': 'Next steps',
        'file_scope': ('Profile scope and genuine-file qualification remain available in Compatibility Center. '
                       'They do not verify this installed game build.'),
        'history_saved': 'New build observation saved locally.', 'history_unchanged': 'No new build changes were found.',
    },
    'de': {
        'title': 'Spielversionen und Kompatibilität',
        'scope': ('Es werden nur geprüfte Steam-Appmanifeste gelesen. Spiele werden nicht gestartet; Spielstände '
                  'und Steam-Benutzerdaten werden nicht geöffnet. Steam-Build-IDs sind keine Spielstandrevisionen.'),
        'scan': 'Steam-Installationen prüfen', 'refresh': 'Verlauf aktualisieren', 'search': 'Installierte Spiele filtern',
        'privacy': ('Der Build-Verlauf wird lokal ohne Installationspfade, Steam-Konto-IDs oder Spielstanddaten gespeichert.'),
        'installed': 'Installierte Builds', 'compat': 'Aktuelle Kompatibilität', 'build_history': 'Build-Verlauf',
        'compat_history': 'Kompatibilitätsverlauf', 'game': 'Spiel', 'platform': 'Plattform', 'build': 'Steam-Build-ID',
        'updated': 'Steam-Updatezeit (Unix-Sekunden)', 'artifact': 'Werkzeug oder Format', 'kind': 'Typ', 'status': 'Status',
        'version': 'Geprüfte Artefaktversion', 'checked': 'Geprüft', 'previous': 'Vorheriger Build', 'observed': 'Erkannter Build',
        'date': 'Erkannt am', 'event': 'Änderung', 'details': 'Details', 'loading': 'Geprüfte Steam-Manifeste werden gelesen…',
        'no_installs': ('Keine geprüfte Steam-Installation erkannt. Andere Stores und nicht zugeordnete Editionen '
                        'werden bei dieser Suche nicht erkannt.'),
        'clean_scan': 'Prüfung abgeschlossen. Kein Spiel wurde gestartet und keine Spielstand- oder Kontodaten gelesen.',
        'scan_issue': ('Einige Steam-Metadaten waren fehlerhaft oder unlesbar und wurden ignoriert. '
                       'Die Ergebnisse können unvollständig sein.'),
        'scan_stopped': 'Die begrenzte Suche wurde vorzeitig beendet; Ergebnisse können unvollständig sein.',
        'scan_error': 'Steam-Manifeste konnten nicht vollständig geprüft werden. Der Verlauf wurde nicht geändert.',
        'history_error': ('Der lokale Verlauf ist ungültig oder nicht verfügbar. Der aktuelle Scan wird gezeigt, '
                          'der Verlauf wurde nicht überschrieben.'),
        'select_build': 'Installierten Build auswählen, um seine exakten Kompatibilitätseinträge zu prüfen.',
        'select_record': 'Kompatibilitätseintrag auswählen, um Erklärung und Nachweise zu lesen.',
        'select_history': 'Verlaufseintrag auswählen, um die Build-Änderung anzusehen.',
        'no_history': 'Auf diesem Computer wurden keine Build-Änderungen erfasst.',
        'no_compat_history': 'Für dieses Spielprofil ist kein geprüfter Kompatibilitätsverlauf erfasst.',
        'unknown_build': 'Das geprüfte Manifest enthielt keine Steam-Build-ID.',
        'unknown': 'Unbekannt', 'first_seen': 'Erstmals erkannt', 'build_changed': 'Build-ID geändert',
        'not_checked': 'Nicht geprüft', 'verified': 'Bestätigt', 'unsupported': 'Nicht unterstützt',
        'unknown_status': 'Unbekannt', 'kind_save_editor': 'Spielstand-Editor', 'kind_mod': 'Mod',
        'kind_config_tool': 'Konfigurationswerkzeug', 'kind_asset_format': 'Asset-Format',
        'source': 'Erkennungsquelle', 'confidence': 'Sicherheit', 'app_id': 'Steam-App-ID',
        'evidence': 'Nachweise', 'reason': 'Grundcode', 'next_steps': 'Nächste Schritte',
        'file_scope': ('Profilumfang und Prüfung echter Dateien stehen weiterhin im Kompatibilitätszentrum. '
                       'Sie bestätigen nicht diesen installierten Build.'),
        'history_saved': 'Neue Build-Beobachtung lokal gespeichert.', 'history_unchanged': 'Keine neuen Build-Änderungen gefunden.',
    },
}


class VersionTrackerPanel:
    """Tk panel for exact Steam build observations and reviewed tool records."""

    def __init__(self, root, parent, language='en', preferences_path=None):
        self.root = root
        self.language = language if language in _TEXT else 'en'
        self.history_path = version_tracker.tracker_history_path(preferences_path)
        self.frame = ttk.Frame(parent, padding=12)
        self._scan_queue = queue.Queue(maxsize=1)
        self._scan_thread = None
        self._observations = ()
        self._observation_by_iid = {}
        self._compatibility_by_iid = {}
        self._compat_history_by_iid = {}
        self._history = ()
        self._palette = None
        self._text_size = 10
        self._font_family = 'Helvetica'

        self.title_label = ttk.Label(self.frame, text=self._t('title'), style='Section.TLabel')
        self.title_label.pack(anchor='w')
        self.scope_label = ttk.Label(self.frame, text=self._t('scope'), style='Muted.TLabel', wraplength=1000)
        self.scope_label.pack(anchor='w', pady=(4, 10))
        self.privacy_label = ttk.Label(self.frame, text=self._t('privacy'), style='Muted.TLabel', wraplength=1000)
        self.privacy_label.pack(anchor='w', pady=(0, 8))

        controls = ttk.Frame(self.frame)
        controls.pack(fill='x')
        self.scan_button = ttk.Button(controls, text=self._t('scan'), command=self.scan)
        self.scan_button.pack(side='left')
        self.refresh_button = ttk.Button(controls, text=self._t('refresh'), command=self.refresh_history)
        self.refresh_button.pack(side='left', padx=(8, 0))
        self.status = tk.StringVar(self.root, value='')
        self.status_label = ttk.Label(self.frame, textvariable=self.status, style='Muted.TLabel', wraplength=1000)
        self.status_label.pack(anchor='w', pady=(6, 8))

        search_bar = ttk.Frame(self.frame)
        search_bar.pack(fill='x', pady=(0, 6))
        self.search_label = ttk.Label(search_bar, text=self._t('search'))
        self.search_label.pack(side='left', padx=(0, 8))
        self.search_value = tk.StringVar(self.root)
        self.search_entry = ttk.Entry(search_bar, textvariable=self.search_value)
        self.search_entry.pack(side='left', fill='x', expand=True)
        self.search_value.trace_add('write', lambda *_: self._render_builds())

        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill='both', expand=True)
        self.build_tab = ttk.Frame(self.notebook, padding=6)
        self.compatibility_tab = ttk.Frame(self.notebook, padding=6)
        self.history_tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.build_tab, text=self._t('installed'))
        self.notebook.add(self.compatibility_tab, text=self._t('compat'))
        self.notebook.add(self.history_tab, text=self._t('build_history'))

        self._build_builds()
        self._build_compatibility()
        self._build_history()
        self._load_history()
        self._show_empty_build()

    def _t(self, key):
        return _TEXT[self.language][key]

    @staticmethod
    def _text_widget(parent, height=8):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, pady=(6, 0))
        widget = tk.Text(frame, height=height, wrap='word', state='disabled', padx=10, pady=8,
                         relief='flat', takefocus=True)
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=widget.yview)
        scrollbar.pack(side='right', fill='y')
        widget.pack(side='left', fill='both', expand=True)
        widget.configure(yscrollcommand=scrollbar.set)
        return widget

    @staticmethod
    def _set_text(widget, content):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.configure(state='disabled')

    @staticmethod
    def _table(parent, columns, headings, widths, height=5):
        holder = ttk.Frame(parent)
        holder.pack(fill='both', expand=True)
        table = ttk.Treeview(holder, columns=columns, show='headings', height=height)
        for column, heading, width in zip(columns, headings, widths):
            table.heading(column, text=heading)
            table.column(column, width=width, minwidth=70, stretch=True)
        vertical = ttk.Scrollbar(holder, orient='vertical', command=table.yview)
        horizontal = ttk.Scrollbar(holder, orient='horizontal', command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        return table

    def _build_builds(self):
        self.builds = self._table(
            self.build_tab, ('game', 'platform', 'build', 'updated'),
            tuple(self._t(key) for key in ('game', 'platform', 'build', 'updated')),
            (300, 150, 150, 190), height=6)
        self.build_detail = self._text_widget(self.build_tab, height=8)
        self.builds.bind('<<TreeviewSelect>>', self._select_build)

    def _build_compatibility(self):
        self.compatibility = self._table(
            self.compatibility_tab, ('artifact', 'kind', 'status', 'version', 'checked'),
            tuple(self._t(key) for key in ('artifact', 'kind', 'status', 'version', 'checked')),
            (280, 135, 120, 130, 170), height=5)
        self.compatibility_detail = self._text_widget(self.compatibility_tab, height=7)
        self.compatibility.bind('<<TreeviewSelect>>', self._select_compatibility)
        self.compatibility_history = self._table(
            self.compatibility_tab, ('build', 'artifact', 'status', 'checked'),
            tuple(self._t(key) for key in ('build', 'artifact', 'status', 'checked')),
            (150, 260, 120, 170), height=3)
        self.compatibility_history.bind('<<TreeviewSelect>>', self._select_compatibility_history)
        self.compat_history_detail = self._text_widget(self.compatibility_tab, height=4)

    def _build_history(self):
        self.history = self._table(
            self.history_tab, ('game', 'platform', 'previous', 'observed', 'date', 'event'),
            tuple(self._t(key) for key in ('game', 'platform', 'previous', 'observed', 'date', 'event')),
            (280, 140, 130, 130, 190, 140), height=8)
        self.history_detail = self._text_widget(self.history_tab, height=7)
        self.history.bind('<<TreeviewSelect>>', self._select_history)

    def scan(self):
        if self._scan_thread is not None and self._scan_thread.is_alive():
            return
        self.scan_button.configure(state='disabled')
        self.status.set(self._t('loading'))
        self._scan_queue = queue.Queue(maxsize=1)

        def worker():
            try:
                result = version_tracker.scan_installed_builds()
            except Exception:
                # Scanner/storage exceptions can contain local paths. Keep them local.
                payload = ('error', None, (), self._history, False)
            else:
                events = ()
                history = self._history
                history_error = False
                try:
                    events = version_tracker.record_scan(result.observations, self.history_path)
                    history = version_tracker.load_history(self.history_path)
                except Exception:
                    # Keep valid scan observations visible even if local history cannot be read or saved.
                    history_error = True
                payload = ('ok', result, events, history, history_error)
            try:
                self._scan_queue.put_nowait(payload)
            except queue.Full:
                pass

        self._scan_thread = threading.Thread(target=worker, name='steam-build-scan', daemon=True)
        self._scan_thread.start()
        self.root.after(80, self._poll_scan)

    def _poll_scan(self):
        if self._scan_thread is not None and self._scan_thread.is_alive():
            self.root.after(80, self._poll_scan)
            return
        self.scan_button.configure(state='normal')
        try:
            result = self._scan_queue.get_nowait()
        except queue.Empty:
            self.status.set(self._t('scan_error'))
            return
        if result[0] != 'ok':
            self.status.set(self._t('scan_error'))
            return
        _status, scan, new_events, history, history_error = result
        self._observations = tuple(scan.observations)
        self._history = tuple(history)
        self._render_builds()
        self._render_history()
        if new_events:
            self.status.set(self._t('history_saved'))
        elif self._observations:
            self.status.set(self._t('clean_scan'))
        else:
            self.status.set(self._t('no_installs'))
        if scan.issues:
            self.status.set(self.status.get() + ' ' + self._t('scan_issue'))
        if scan.stop_reason != 'complete':
            self.status.set(self.status.get() + ' ' + self._t('scan_stopped'))
        if history_error:
            self.status.set(self.status.get() + ' ' + self._t('history_error'))

    def refresh_history(self):
        self._load_history()
        self._render_history()
        self._render_compatibility_history()

    def _load_history(self):
        try:
            self._history = version_tracker.load_history(self.history_path)
        except ValueError:
            self._history = ()
            self.status.set(self._t('history_error'))

    def _render_builds(self):
        selected = self.builds.selection()
        keep = selected[0] if selected else None
        self.builds.delete(*self.builds.get_children())
        self._observation_by_iid.clear()
        query = self.search_value.get().casefold().strip()
        names = {game.id: (game.title, game.platform) for game in GAMES}
        for observation in self._observations:
            title, platform = names[observation.game_id]
            values = (title, platform, observation.build_id or self._t('unknown'),
                      observation.last_updated or self._t('unknown'))
            if query and query not in ' '.join((observation.game_id, title, platform, *values)).casefold():
                continue
            iid = f'{observation.game_id}:{observation.app_id}'
            self._observation_by_iid[iid] = observation
            self.builds.insert('', 'end', iid=iid, values=values)
        chosen = keep if keep in self._observation_by_iid else next(iter(self._observation_by_iid), None)
        if chosen:
            self.builds.selection_set(chosen)
            self.builds.focus(chosen)
            self._select_build()
        else:
            self._show_empty_build()

    def _show_empty_build(self):
        self._set_text(self.build_detail, self._t('select_build'))
        self.compatibility.delete(*self.compatibility.get_children())
        self._compatibility_by_iid.clear()
        self.compatibility_history.delete(*self.compatibility_history.get_children())
        self._compat_history_by_iid.clear()
        self._set_text(self.compatibility_detail, self._t('select_record'))
        self._set_text(self.compat_history_detail, self._t('no_compat_history'))

    def _select_build(self, _event=None):
        selected = self.builds.selection()
        observation = self._observation_by_iid.get(selected[0]) if selected else None
        if observation is None:
            self._show_empty_build()
            return
        rows = version_tracker.compatibility_for(observation)
        self.compatibility.delete(*self.compatibility.get_children())
        self._compatibility_by_iid.clear()
        for item in rows:
            iid = f'{item.artifact_kind}:{item.artifact_id}'
            self._compatibility_by_iid[iid] = item
            self.compatibility.insert('', 'end', iid=iid, values=(
                item.artifact_name, self._t('kind_' + item.artifact_kind), self._status_label(item.status),
                item.artifact_version or self._t('unknown'),
                self._t('not_checked') if self._is_unreviewed(item) else item.checked_at))
        if self.compatibility.get_children():
            iid = self.compatibility.get_children()[0]
            self.compatibility.selection_set(iid)
            self.compatibility.focus(iid)
            self._select_compatibility()
        self._render_compatibility_history(observation.game_id, observation.app_id)
        title = next(game.title for game in GAMES if game.id == observation.game_id)
        detail = (f'{title} · {observation.platform}\n\n'
                  f'{self._t("app_id")}: {observation.app_id}\n'
                  f'{self._t("build")}: {observation.build_id or self._t("unknown")}\n'
                  f'{self._t("updated")}: {observation.last_updated or self._t("unknown")}\n'
                  f'{self._t("source")}: {observation.source}\n'
                  f'{self._t("confidence")}: {observation.confidence}\n\n{self._t("file_scope")}')
        if observation.evidence:
            detail += '\n\n' + self._t('evidence') + '\n' + '\n'.join(observation.evidence)
        current_event = next((event for event in reversed(self._history)
                              if event.game_id == observation.game_id and event.app_id == observation.app_id
                              and event.build_id == observation.build_id), None)
        if current_event is not None and current_event.warning:
            detail += '\n\n' + current_event.warning
        elif observation.build_id is None:
            detail += '\n\n' + self._t('unknown_build')
        self._set_text(self.build_detail, detail)

    def _select_compatibility(self, _event=None):
        selected = self.compatibility.selection()
        record = self._compatibility_by_iid.get(selected[0]) if selected else None
        if record is None:
            self._set_text(self.compatibility_detail, self._t('select_record'))
            return
        body = (f'{record.artifact_name}\n{self._status_label(record.status)} · {record.reason_code}\n'
                f'{self._t("game")}: {record.game_id} · {record.platform} · {self._t("app_id")}: {record.app_id} · '
                f'{self._t("build")}: {record.build_id or self._t("unknown")}\n\n'
                f'{record.explanation}\n\n{self._t("version")}: {record.artifact_version or self._t("unknown")}\n'
                f'{self._t("checked")}: {self._t("not_checked") if self._is_unreviewed(record) else record.checked_at}')
        if record.evidence:
            body += '\n\n' + self._t('evidence') + '\n' + '\n'.join(record.evidence)
        if record.next_step_ids:
            body += '\n\n' + self._t('next_steps') + '\n' + ', '.join(record.next_step_ids)
        self._set_text(self.compatibility_detail, body)

    def _render_compatibility_history(self, game_id=None, app_id=None):
        if game_id is None:
            selected = self.builds.selection()
            observation = self._observation_by_iid.get(selected[0]) if selected else None
            game_id = observation.game_id if observation is not None else None
            app_id = observation.app_id if observation is not None else None
        self.compatibility_history.delete(*self.compatibility_history.get_children())
        self._compat_history_by_iid.clear()
        records = version_tracker.compatibility_history(game_id, app_id=app_id) if game_id else ()
        for index, record in enumerate(records):
            iid = f'{record.build_id}:{record.artifact_kind}:{record.artifact_id}:{index}'
            self._compat_history_by_iid[iid] = record
            self.compatibility_history.insert('', 'end', iid=iid, values=(
                record.build_id, record.artifact_name, self._status_label(record.status), record.checked_at))
        if records:
            self._set_text(self.compat_history_detail, self._t('select_record'))
        else:
            self._set_text(self.compat_history_detail, self._t('no_compat_history'))

    def _select_compatibility_history(self, _event=None):
        selected = self.compatibility_history.selection()
        record = self._compat_history_by_iid.get(selected[0]) if selected else None
        if record is None:
            return
        self._set_text(self.compat_history_detail,
                       f'{record.artifact_name}\n{record.app_id} · {record.build_id} · '
                       f'{self._status_label(record.status)}\n\n'
                       f'{record.explanation}\n\n{self._t("version")}: {record.artifact_version or self._t("unknown")}\n'
                       f'{self._t("reason")}: {record.reason_code}\n'
                       f'{self._t("checked")}: {record.checked_at}'
                       + (('\n\n' + self._t('evidence') + '\n' + '\n'.join(record.evidence))
                          if record.evidence else ''))

    def _status_label(self, status):
        key = {'verified': 'verified', 'unsupported': 'unsupported', 'unknown': 'unknown_status'}.get(status)
        return self._t(key) if key is not None else status

    @staticmethod
    def _is_unreviewed(record):
        return record.status == 'unknown' and record.artifact_id.startswith(('unverified_', 'unlisted_'))

    def _render_history(self):
        selected = self.history.selection()
        keep = selected[0] if selected else None
        self.history.delete(*self.history.get_children())
        rows = []
        for index, event in enumerate(self._history):
            title = next(game.title for game in GAMES if game.id == event.game_id)
            change = self._t(event.event_kind) if event.event_kind in ('first_seen', 'build_changed') else event.event_kind
            iid = f'{event.game_id}:{event.app_id}:{index}'
            rows.append((iid, event, title, change))
        for iid, event, title, change in rows:
            self.history.insert('', 'end', iid=iid, values=(
                title, event.platform, event.previous_build_id or '—', event.build_id or self._t('unknown'),
                event.observed_at, change))
        chosen = keep if keep and self.history.exists(keep) else (rows[-1][0] if rows else None)
        if chosen:
            self.history.selection_set(chosen)
            self.history.focus(chosen)
            self._select_history()
        else:
            self._set_text(self.history_detail, self._t('no_history'))

    def _select_history(self, _event=None):
        selected = self.history.selection()
        if not selected:
            self._set_text(self.history_detail, self._t('no_history'))
            return
        try:
            index = int(selected[0].rsplit(':', 1)[1])
            event = self._history[index]
        except (ValueError, IndexError):
            self._set_text(self.history_detail, self._t('select_history'))
            return
        body = (f'{event.game_id} · {event.platform}\n'
                f'{self._t("previous")}: {event.previous_build_id or "—"}\n'
                f'{self._t("observed")}: {event.build_id or self._t("unknown")}\n'
                f'{self._t("date")}: {event.observed_at}')
        if event.warning:
            body += '\n\n' + event.warning
        self._set_text(self.history_detail, body)

    def set_language(self, language):
        self.language = language if language in _TEXT else 'en'
        self.title_label.configure(text=self._t('title'))
        self.scope_label.configure(text=self._t('scope'))
        self.privacy_label.configure(text=self._t('privacy'))
        self.scan_button.configure(text=self._t('scan'))
        self.refresh_button.configure(text=self._t('refresh'))
        self.search_label.configure(text=self._t('search'))
        for tab, key in ((self.build_tab, 'installed'), (self.compatibility_tab, 'compat'),
                         (self.history_tab, 'build_history')):
            self.notebook.tab(tab, text=self._t(key))
        self._set_headings(self.builds, ('game', 'platform', 'build', 'updated'))
        self._set_headings(self.compatibility, ('artifact', 'kind', 'status', 'version', 'checked'))
        self._set_headings(self.compatibility_history, ('build', 'artifact', 'status', 'checked'))
        self._set_headings(self.history, ('game', 'platform', 'previous', 'observed', 'date', 'event'))
        self._render_builds()
        self._render_history()

    def _set_headings(self, table, keys):
        for column, key in zip(table['columns'], keys):
            table.heading(column, text=self._t(key))

    def apply_theme(self, palette):
        self._palette = palette
        for widget in (self.build_detail, self.compatibility_detail, self.compat_history_detail,
                       self.history_detail):
            widget.configure(background=palette['surface'], foreground=palette['text'],
                             insertbackground=palette['text'], selectbackground=palette['accent'],
                             selectforeground='#ffffff')

    def set_text_size(self, size, family):
        self._text_size, self._font_family = size, family
        for widget in (self.build_detail, self.compatibility_detail, self.compat_history_detail,
                       self.history_detail):
            widget.configure(font=(family, size))

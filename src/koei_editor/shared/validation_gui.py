"""Keyboard-accessible local validation and feedback panels for the global shell."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.game_registry import GAMES
from koei_editor.shared.community_feedback import (
    CATEGORIES, ERROR_CODES, build_bug_report, export_bug_report, review_json,
)
from koei_editor.shared.validation_toolkit import (
    OUTCOMES, PROVENANCES, STEPS, ReportError, ValidationRecord,
)


_TEXT = {
    'en': {
        'title': 'Real-game validation', 'game': 'Exact game / platform / edition',
        'revision': 'Numeric format revision (decimal or 0x; blank = unspecified)',
        'provenance': 'Source evidence', 'step': 'Controlled step', 'outcome': 'Observed outcome',
        'record': 'Record outcome', 'load': 'Load report…', 'export': 'Export reviewed report…',
        'preview': 'Review report', 'reset': 'Reset workflow',
        'warning': 'Manual observations remain unverified. Procedural tests, genuine-file checks and '
                   'actual game load / re-save are separate. This tool never opens saves or runs games.',
        'changed': 'Profile, revision or source changed; downstream observations have been reset.',
        'saved': 'Report exported locally. Nothing was transmitted.',
        'loaded': 'Imported user report. Its claims have not been independently verified.',
        'error': 'Report operation failed. Check the selected options, prerequisites and file permissions. '
                 'Export requires a new filename. Reports must match this application’s bounded schema.',
        'feedback': 'Community feedback', 'privacy': 'Only the visible controlled choices are included. '
                    'No paths, save contents, account IDs, environment variables, logs or exception text '
                    'are collected. Review the JSON before exporting it. Nothing is sent automatically.',
        'category': 'Problem category', 'error_code': 'Observed symptom', 'none': 'No game selected',
        'ready': 'Choose a step, perform it on a separate copy, then record what you observed.',
        'outcomes': ('Not run', 'Passed', 'Failed', 'Blocked'),
        'sources': ('Unknown / not established', 'Procedural fixture', 'Genuine player-save copy'),
        'categories': ('Navigation', 'Accessibility', 'Localization', 'Compatibility', 'Save workflow', 'Other'),
        'errors': ('No error', 'Input rejected', 'Operation failed', 'UI unresponsive', 'Unexpected result'),
        'steps': (
            '1. Prepare separate copy', '2. Confirm exact profile and revision',
            '3. Check unchanged roundtrip', '4. Reparse one controlled edit',
            '5. Import through platform tools', '6. Load edited copy in game',
            '7. Observe intended field', '8. Save again in game', '9. Reload game-written save',
        ),
        'guides': (
            'Close the game and cloud sync. Preserve an untouched original and use a separate working copy.',
            'Confirm game, edition, region and numeric format revision against adapter documentation. '
            'Leave the revision blank if unknown; this does not certify it.',
            'Use the existing copied-save self-test where available. Confirm byte-exact unchanged '
            'roundtrip, input preservation and backup restore. Synthetic success is procedural evidence only.',
            'Use the editor to change one mapped field only; review, Save As to a new copy and re-open '
            'it in the same explicit adapter. Keep an unchanged control. Record failure if rejected.',
            'For consoles, preserve required original companion files and use your authorized save manager '
            'for external import/signing. Never fabricate account or signing metadata. PC: use the game’s '
            'documented copied-save import procedure. This toolkit does not perform imports.',
            'Only a genuine edited copy can establish this observation. Start the exact game/build and '
            'confirm the edited slot loads without a corruption or recovery warning.',
            'Compare the intended field with the unchanged control in the game. Check related behavior; '
            'a successful parse alone does not confirm gameplay semantics.',
            'Save normally inside the game to a test slot. Preserve the unchanged control and original. '
            'A load success alone does not establish re-save success.',
            'Restart the game and load the game-written test slot. Confirm the expected value remains. '
            'Keep private evidence locally; export only this path-free checklist.',
        ),
    },
    'de': {
        'title': 'Validierung im Spiel', 'game': 'Genaues Spiel / Plattform / Edition',
        'revision': 'Numerische Formatversion (dezimal oder 0x; leer = unbekannt)',
        'provenance': 'Herkunft des Nachweises', 'step': 'Kontrollierter Schritt', 'outcome': 'Beobachtetes Ergebnis',
        'record': 'Ergebnis erfassen', 'load': 'Bericht laden…', 'export': 'Geprüften Bericht exportieren…',
        'preview': 'Bericht prüfen', 'reset': 'Ablauf zurücksetzen',
        'warning': 'Manuelle Beobachtungen bleiben ungeprüft. Synthetische Tests, Prüfungen echter '
                   'Dateien und Laden / erneutes Speichern im Spiel sind getrennte Nachweise. '
                   'Dieses Werkzeug öffnet keine Spielstände und startet keine Spiele.',
        'changed': 'Profil, Version oder Herkunft geändert; nachfolgende Beobachtungen wurden zurückgesetzt.',
        'saved': 'Bericht lokal exportiert. Es wurde nichts übertragen.',
        'loaded': 'Nutzerbericht importiert. Die Angaben wurden nicht unabhängig geprüft.',
        'error': 'Bericht konnte nicht verarbeitet werden. Auswahl, Voraussetzungen und Dateirechte prüfen. '
                 'Beim Export ist ein neuer Dateiname erforderlich. Berichte müssen dem begrenzten Schema entsprechen.',
        'feedback': 'Community-Rückmeldung', 'privacy': 'Nur die sichtbaren Auswahlwerte werden aufgenommen. '
                    'Keine Pfade, Spielstandinhalte, Kontokennungen, Umgebungsvariablen, Protokolle oder '
                    'Ausnahmetexte werden erfasst. JSON vor dem Export prüfen. Es wird nichts automatisch gesendet.',
        'category': 'Problemkategorie', 'error_code': 'Beobachtetes Symptom', 'none': 'Kein Spiel ausgewählt',
        'ready': 'Schritt wählen, an einer separaten Kopie ausführen und die Beobachtung erfassen.',
        'outcomes': ('Nicht ausgeführt', 'Bestanden', 'Fehlgeschlagen', 'Blockiert'),
        'sources': ('Unbekannt / nicht belegt', 'Synthetische Testdatei', 'Kopie eines echten Spielstands'),
        'categories': ('Navigation', 'Barrierefreiheit', 'Übersetzung', 'Kompatibilität', 'Spielstandablauf', 'Sonstiges'),
        'errors': ('Kein Fehler', 'Eingabe abgelehnt', 'Vorgang fehlgeschlagen', 'Oberfläche reagiert nicht', 'Unerwartetes Ergebnis'),
        'steps': (
            '1. Separate Kopie vorbereiten', '2. Profil und Version bestätigen',
            '3. Unveränderten Rundlauf prüfen', '4. Einzelne Änderung erneut einlesen',
            '5. Mit Plattformwerkzeug importieren', '6. Geänderte Kopie im Spiel laden',
            '7. Zielfeld im Spiel prüfen', '8. Im Spiel erneut speichern', '9. Neu gespeicherten Stand laden',
        ),
        'guides': (
            'Spiel und Cloud-Synchronisierung schließen. Ein unverändertes Original aufbewahren und '
            'eine separate Arbeitskopie verwenden.',
            'Spiel, Edition, Region und numerische Formatversion anhand der Adapter-Dokumentation prüfen. '
            'Unbekannte Version leer lassen; dies ist keine Zertifizierung.',
            'Wenn verfügbar, den bestehenden Selbsttest für Spielstandkopien verwenden. Bytegenauen '
            'Rundlauf, Originalerhalt und Sicherungswiederherstellung prüfen. Synthetische Daten bleiben synthetisch.',
            'Genau ein zugeordnetes Feld ändern, Änderungen prüfen, als neue Kopie speichern und mit '
            'demselben Adapter erneut öffnen. Unveränderte Kontrollkopie behalten. Ablehnung als Fehler erfassen.',
            'Bei Konsolen originale Begleitdateien beibehalten und ein autorisiertes Werkzeug für externen '
            'Import / Signierung verwenden. Keine Konto- oder Signaturdaten erfinden. Am PC dem dokumentierten '
            'Importablauf des Spiels folgen. Dieses Werkzeug führt keinen Import aus.',
            'Nur eine echte bearbeitete Kopie kann diese Beobachtung belegen. Genaues Spiel / Build starten '
            'und den Teststand ohne Beschädigungs- oder Wiederherstellungswarnung laden.',
            'Zielfeld im Spiel mit unveränderter Kontrollkopie vergleichen und abhängiges Verhalten prüfen. '
            'Erfolgreiches Einlesen allein bestätigt keine Spielmechanik.',
            'Im Spiel regulär in einen Testplatz speichern. Original und Kontrollkopie aufbewahren. '
            'Erfolgreiches Laden belegt kein erfolgreiches erneutes Speichern.',
            'Spiel neu starten und den vom Spiel geschriebenen Teststand laden. Zielwert erneut prüfen. '
            'Private Nachweise lokal behalten; nur diese pfadfreie Checkliste exportieren.',
        ),
    },
}


class _Panel:
    def _setup(self, root, parent, language):
        self.root = root
        self.language = 'de' if str(language).lower().startswith('de') else 'en'
        self.text = _TEXT[self.language]
        self.frame = ttk.Frame(parent, padding=12)
        self._palette = None
        self._wrapping = []
        self.frame.bind('<Configure>', self._resize, add='+')
        self.status = tk.StringVar(root)
        self._games = {f'{g.title} · {g.subtitle} [{g.platform}]': g.id for g in GAMES}

    def _label(self, key, parent=None):
        label = ttk.Label(parent or self.frame, text=self.text[key], wraplength=700)
        label.pack(anchor='w', pady=(8, 3))
        self._wrapping.append(label)
        return label

    def _resize(self, event):
        for label in self._wrapping:
            label.configure(wraplength=max(180, event.width - 24))

    def _preview(self):
        holder = ttk.Frame(self.frame)
        holder.pack(fill='both', expand=True, pady=8)
        self.preview = tk.Text(holder, height=8, wrap='word', state='disabled', takefocus=True)
        scroll = ttk.Scrollbar(holder, orient='vertical', command=self.preview.yview)
        self.preview.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.preview.pack(fill='both', expand=True)
        ttk.Label(self.frame, textvariable=self.status, wraplength=700).pack(anchor='w')

    def _show(self, content):
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', content)
        self.preview.configure(state='disabled')

    def _error(self):
        self.status.set(self.text['error'])
        messagebox.showerror(self.text['title'], self.text['error'], parent=self.root)

    def apply_theme(self, palette):
        # ttk follows the shared theme; native Text needs explicit colors.
        self._palette = palette
        bg = palette.get('surface', palette.get('background', '#ffffff'))
        fg = palette.get('text', palette.get('fg', '#222222'))
        self.preview.configure(background=bg, foreground=fg, insertbackground=fg)

    def _rebuild(self, language):
        old_frame = self.frame
        parent, root = old_frame.master, self.root
        manager, palette = old_frame.winfo_manager(), self._palette
        layout = getattr(old_frame, manager + '_info')() if manager else None
        self.__init__(root, parent, language=language)
        if manager:
            getattr(self.frame, manager)(**layout)
        if palette is not None:
            self.apply_theme(palette)
        old_frame.destroy()


class ValidationPanel(_Panel):
    def __init__(self, root, parent, language='en'):
        self._setup(root, parent, language)
        self.record = None
        self._loading = False
        self._label('title')
        self._label('warning')
        self._label('game')
        self.game = tk.StringVar(root, value=next(iter(self._games)))
        ttk.Combobox(self.frame, textvariable=self.game, values=tuple(self._games), state='readonly').pack(fill='x')
        form = ttk.Frame(self.frame)
        form.pack(fill='x')
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        self.revision = tk.StringVar(root)
        self.provenance = tk.StringVar(root, value=self.text['sources'][0])
        ttk.Label(form, text=self.text['revision'], wraplength=350).grid(row=0, column=0, sticky='w', pady=(8, 3))
        ttk.Label(form, text=self.text['provenance']).grid(row=0, column=1, sticky='w', padx=(8, 0))
        ttk.Entry(form, textvariable=self.revision).grid(row=1, column=0, sticky='ew')
        ttk.Combobox(form, textvariable=self.provenance, values=self.text['sources'], state='readonly').grid(row=1, column=1, sticky='ew', padx=(8, 0))
        self.step = tk.StringVar(root, value=self.text['steps'][0])
        self.outcome = tk.StringVar(root, value=self.text['outcomes'][0])
        ttk.Label(form, text=self.text['step']).grid(row=2, column=0, sticky='w', pady=(8, 3))
        ttk.Label(form, text=self.text['outcome']).grid(row=2, column=1, sticky='w', padx=(8, 0))
        ttk.Combobox(form, textvariable=self.step, values=self.text['steps'], state='readonly').grid(row=3, column=0, sticky='ew')
        ttk.Combobox(form, textvariable=self.outcome, values=self.text['outcomes'], state='readonly').grid(row=3, column=1, sticky='ew', padx=(8, 0))
        self.guidance = tk.StringVar(root)
        guidance_label = ttk.Label(self.frame, textvariable=self.guidance, wraplength=700)
        guidance_label.pack(anchor='w', pady=8)
        self._wrapping.append(guidance_label)
        actions = ttk.Frame(self.frame)
        actions.pack(fill='x')
        for column in range(2):
            actions.columnconfigure(column, weight=1)
        for index, (key, command) in enumerate((('record', self.record_outcome), ('reset', self.reset), ('load', self.load), ('export', self.export))):
            ttk.Button(actions, text=self.text[key], command=command).grid(
                row=index // 2, column=index % 2, sticky='ew', padx=(0, 6), pady=2)
        self._preview()
        for variable in (self.game, self.revision, self.provenance):
            variable.trace_add('write', self.reset)
        self.step.trace_add('write', self._step_changed)
        self.reset()
        self._step_changed()
        self.status.set(self.text['ready'])

    def set_language(self, language):
        language = 'de' if str(language).lower().startswith('de') else 'en'
        if language == self.language:
            return
        record = self.record
        game, revision = self.game.get(), self.revision.get()
        source = self.text['sources'].index(self.provenance.get())
        step = self.text['steps'].index(self.step.get())
        outcome = self.text['outcomes'].index(self.outcome.get())
        self._rebuild(language)
        self._loading = True
        try:
            self.game.set(game)
            self.revision.set(revision)
            self.provenance.set(self.text['sources'][source])
            self.record = record
            self.step.set(self.text['steps'][step])
            self.outcome.set(self.text['outcomes'][outcome])
        finally:
            self._loading = False
        self._show('' if record is None else record.to_json())
        self.status.set(self.text['error'] if record is None else self.text['ready'])

    def _step_changed(self, *_):
        index = self.text['steps'].index(self.step.get())
        self.guidance.set(self.text['guides'][index])
        outcome = 'not_run' if self.record is None else self.record.outcomes[index]
        self.outcome.set(self.text['outcomes'][OUTCOMES.index(outcome)])

    def reset(self, *_):
        if self._loading:
            return
        try:
            value = self.revision.get().strip()
            if len(value) > 10 or (value and not (value.isascii() and
                    (value.isdecimal() or (value.startswith('0x') and len(value) > 2 and
                     all(c in '0123456789abcdefABCDEF' for c in value[2:]))))):
                raise ReportError('Use a numeric revision.')
            revision = None if not value else int(value, 16 if value.startswith('0x') else 10)
            self.record = ValidationRecord.create(
                self._games[self.game.get()], revision=revision,
                provenance=PROVENANCES[self.text['sources'].index(self.provenance.get())])
            self._show(self.record.to_json())
            self.status.set(self.text['changed'])
        except (ValueError, KeyError):
            self.record = None
            self._show('')
            self.status.set(self.text['error'])
        self._step_changed()

    def record_outcome(self):
        try:
            if self.record is None:
                raise ReportError('Select a valid report profile.')
            step = STEPS[self.text['steps'].index(self.step.get())]
            outcome = OUTCOMES[self.text['outcomes'].index(self.outcome.get())]
            self.record = self.record.record_step(step, outcome)
            self._show(self.record.to_json())
            self.status.set(self.text['ready'])
        except ValueError:
            self._error()

    def load(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('JSON', '*.json')])
        if not path:
            return
        try:
            record = ValidationRecord.load(path)
            self._loading = True
            try:
                self.game.set(next(label for label, game_id in self._games.items() if game_id == record.game_id))
                self.revision.set('' if record.revision is None else str(record.revision))
                self.provenance.set(self.text['sources'][PROVENANCES.index(record.provenance)])
            finally:
                self._loading = False
            self.record = record
            self._show(record.to_json())
            self._step_changed()
            self.status.set(self.text['loaded'])
        except (OSError, ValueError):
            self._error()

    def export(self):
        if self.record is None:
            self._error()
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                                          initialfile='validation-report.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                self.record.export(path)
                self.status.set(self.text['saved'])
            except (OSError, ValueError):
                self._error()


class FeedbackPanel(_Panel):
    def __init__(self, root, parent, language='en'):
        self._setup(root, parent, language)
        self._label('feedback')
        self._label('privacy')
        self._label('game')
        self.game = tk.StringVar(root, value=self.text['none'])
        ttk.Combobox(self.frame, textvariable=self.game, values=(self.text['none'],) + tuple(self._games), state='readonly').pack(fill='x')
        self._label('category')
        self.category = tk.StringVar(root, value=self.text['categories'][0])
        ttk.Combobox(self.frame, textvariable=self.category, values=self.text['categories'], state='readonly').pack(fill='x')
        self._label('error_code')
        self.error_code = tk.StringVar(root, value=self.text['errors'][0])
        ttk.Combobox(self.frame, textvariable=self.error_code, values=self.text['errors'], state='readonly').pack(fill='x')
        ttk.Button(self.frame, text=self.text['export'], command=self.export).pack(anchor='w', pady=8)
        self._preview()
        for variable in (self.game, self.category, self.error_code):
            variable.trace_add('write', self.refresh)
        self.refresh()

    def set_language(self, language):
        language = 'de' if str(language).lower().startswith('de') else 'en'
        if language == self.language:
            return
        game_id = self._games.get(self.game.get())
        category = self.text['categories'].index(self.category.get())
        error = self.text['errors'].index(self.error_code.get())
        self._rebuild(language)
        self.game.set(next((label for label, value in self._games.items() if value == game_id), self.text['none']))
        self.category.set(self.text['categories'][category])
        self.error_code.set(self.text['errors'][error])
        self.refresh()

    def refresh(self, *_):
        self.report = build_bug_report(
            game_id=self._games.get(self.game.get()),
            category=CATEGORIES[self.text['categories'].index(self.category.get())],
            error_code=ERROR_CODES[self.text['errors'].index(self.error_code.get())],
            locale=self.language)
        self._show(review_json(self.report))

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json',
                                          initialfile='community-report.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                export_bug_report(self.report, path)
                self.status.set(self.text['saved'])
            except (OSError, ValueError):
                self._error()

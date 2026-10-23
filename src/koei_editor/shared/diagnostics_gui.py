"""Lazy local diagnostics panel shared with the headless support-report command."""
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared.copy_storage import ChildPublishedUncertainError
from koei_editor.shared.toolkit_diagnostics import collect_diagnostics, export_report, report_json

_TEXT = {
    'en': {'title': 'Toolkit diagnostics', 'refresh': 'Refresh', 'copy': 'Copy report',
           'export': 'Export new JSON…', 'summary': 'Runtime and dependency metadata only. Review the JSON before sharing. No saves, installation paths, account data or logs are collected; nothing is sent automatically.',
           'ready': 'Report collected locally. Platform support still requires destination-specific checks.',
           'copied': 'The visible JSON was copied to the clipboard.', 'saved': 'The reviewed JSON was exported to a new local file.',
           'uncertain': 'The report may already exist. Inspect the selected folder before trying another export.',
           'error': 'The operation could not complete. Export needs a new filename in an existing folder outside live save or cloud folders.'},
    'de': {'title': 'Toolkit-Diagnose', 'refresh': 'Aktualisieren', 'copy': 'Bericht kopieren',
           'export': 'Neue JSON exportieren…', 'summary': 'Nur Laufzeit- und Paketmetadaten. JSON vor dem Teilen prüfen. Keine Spielstände, Installationspfade, Kontodaten oder Protokolle werden erfasst; es wird nichts automatisch gesendet.',
           'ready': 'Bericht lokal erstellt. Plattformunterstützung erfordert weiterhin zielbezogene Dateisystemprüfungen.',
           'copied': 'Die sichtbare JSON wurde in die Zwischenablage kopiert.', 'saved': 'Die geprüfte JSON wurde als neue lokale Datei exportiert.',
           'uncertain': 'Der Bericht kann bereits vorhanden sein. Den gewählten Ordner vor einem weiteren Export prüfen.',
           'error': 'Vorgang nicht abgeschlossen. Der Export benötigt einen neuen Dateinamen außerhalb aktiver Spielstand- oder Cloud-Ordner.'},
}


class DiagnosticsPanel:
    def __init__(self, root, parent, language='en'):
        self.root = root
        self.language = 'de' if language == 'de' else 'en'
        self.frame = ttk.Frame(parent, padding=10)
        self._closed = False
        self.frame.bind('<Destroy>', self._destroyed, add='+')
        self.title = ttk.Label(self.frame, style='Section.TLabel')
        self.title.pack(anchor='w')
        self.summary = ttk.Label(self.frame, wraplength=640)
        self.summary.pack(fill='x', pady=(8, 10))
        actions = self.actions = ttk.Frame(self.frame)
        self._button_columns = 3
        actions.pack(fill='x')
        self.refresh_button = ttk.Button(actions, command=self.refresh)
        self.copy_button = ttk.Button(actions, command=self.copy_report)
        self.export_button = ttk.Button(actions, command=self.export)
        for index, button in enumerate((self.refresh_button, self.copy_button, self.export_button)):
            button.grid(row=0, column=index, sticky='ew', padx=(0, 8 if index < 2 else 0))
            actions.columnconfigure(index, weight=1)
        holder = ttk.Frame(self.frame)
        holder.pack(fill='both', expand=True, pady=(10, 6))
        self.preview = tk.Text(holder, wrap='word', height=12, state='disabled', takefocus=True)
        scroll = ttk.Scrollbar(holder, orient='vertical', command=self.preview.yview)
        self.preview.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.preview.pack(side='left', fill='both', expand=True)
        self.status = tk.StringVar(root)
        self.status_label = ttk.Label(self.frame, textvariable=self.status, wraplength=640)
        self.status_label.pack(fill='x')
        self.frame.bind('<Configure>', self._resize, add='+')
        self.set_language(self.language)
        self.refresh()

    def _destroyed(self, event):
        if event.widget is self.frame:
            self._closed = True

    def _alive(self):
        if self._closed:
            return False
        try:
            return bool(self.frame.winfo_exists() and self.root.winfo_exists())
        except tk.TclError:
            return False

    def _resize(self, event):
        if not self._alive():
            return
        width = max(180, event.width - 24)
        self.summary.configure(wraplength=width)
        columns = 3 if event.width >= 620 else 1
        if columns != self._button_columns:
            self._button_columns = columns
            for index, button in enumerate((self.refresh_button, self.copy_button, self.export_button)):
                button.grid_configure(row=index // columns, column=index % columns,
                                      padx=(0, 8 if columns == 3 and index < 2 else 0),
                                      pady=(0, 5 if columns == 1 and index < 2 else 0))
                self.actions.columnconfigure(index, weight=1 if index < columns else 0)
        self.status_label.configure(wraplength=width)

    def refresh(self):
        if not self._alive():
            return
        from koei_editor.application import VERSION
        report = collect_diagnostics(VERSION)
        if not self._alive():
            return
        self.report = report
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', report_json(self.report))
        self.preview.configure(state='disabled')
        self.status.set(self.text['ready'])

    def _error(self):
        if not self._alive():
            return
        self.status.set(self.text['error'])
        messagebox.showerror(self.text['title'], self.text['error'], parent=self.root)

    def copy_report(self):
        if not self._alive():
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(report_json(self.report))
        except (tk.TclError, ValueError):
            self._error()
            return
        if self._alive():
            self.status.set(self.text['copied'])

    def export(self):
        if not self._alive():
            return
        try:
            # Native dialogs run a nested event loop. Freeze the reviewed
            # snapshot before it opens; a refresh must not change this export.
            reviewed = json.loads(report_json(self.report))
        except ValueError:
            self._error()
            return
        try:
            destination = filedialog.asksaveasfilename(
                parent=self.root, title=self.text['export'], initialfile='toolkit-diagnostics.json',
                defaultextension='.json', filetypes=(('JSON report', '*.json'),), confirmoverwrite=False)
        except tk.TclError:
            self._error()
            return
        if not destination or not self._alive():
            return
        try:
            export_report(reviewed, destination)
        except ChildPublishedUncertainError:
            if self._alive():
                self.status.set(self.text['uncertain'])
                messagebox.showerror(self.text['title'], self.text['uncertain'], parent=self.root)
            return
        except (OSError, ValueError, RuntimeError):
            self._error()
            return
        if self._alive():
            self.status.set(self.text['saved'])

    def apply_theme(self, palette):
        if not self._alive():
            return
        self.preview.configure(background=palette['surface'], foreground=palette['text'],
                               insertbackground=palette['text'], selectbackground=palette['accent'],
                               selectforeground='#ffffff')

    def set_language(self, language):
        if not self._alive():
            return
        self.language = 'de' if language == 'de' else 'en'
        self.text = _TEXT[self.language]
        self.title.configure(text=self.text['title'])
        self.summary.configure(text=self.text['summary'])
        for button, key in ((self.refresh_button, 'refresh'), (self.copy_button, 'copy'),
                            (self.export_button, 'export')):
            button.configure(text=self.text[key])
        self.status.set(self.text['ready'])

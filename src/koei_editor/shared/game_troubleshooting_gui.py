"""Read-only, retained UI for the Koei Tecmo Game Troubleshooting Center."""

from pathlib import Path
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.game_registry import GAMES
from koei_editor.shared.game_troubleshooting import CATEGORY_ORDER, SCHEMA_VERSION, diagnose_game
from koei_editor.shared.scrollable_panel import ScrollablePanel


_TEXT = {
    "en": {
        "title": "Game Troubleshooting Center",
        "intro": "Run bounded, read-only checks for one Windows PC game. The center only reads folders you select; it never changes an installation, configuration, or mod folder.",
        "safety": "No repair is performed. Review each recommendation and decide whether to follow it yourself.",
        "game": "Game / platform / edition",
        "choose_game": "Choose a game",
        "installation": "Installation folder",
        "configuration": "Configuration folder (optional)",
        "mods": "Mod folder (optional; defaults to installation folder)",
        "browse": "Browse…",
        "browse_installation": "Choose the game installation folder",
        "browse_configuration": "Choose the game's configuration folder",
        "browse_mods": "Choose the mod folder",
        "clear": "Clear",
        "scan": "Scan selected folders",
        "export": "Export JSON report…",
        "no_report": "Select a game, choose any folders you want checked, then run a scan. No folder is inspected until you select Scan.",
        "read_only": "Folders are inspected read-only. The report excludes absolute paths, configuration values, file contents, hashes, and timestamps.",
        "overall": "Overall status: {status}",
        "audit_key": "Audit key: schema {schema_version} · ruleset {ruleset_version}",
        "status_ready": "Ready to scan.",
        "status_busy": "Reading the selected folders…",
        "status_complete": "Scan complete: {count} findings. No selected file was changed.",
        "status_changed": "Selections changed. Run the scan again to refresh the report.",
        "status_error": "The scan could not be completed. Check that the selected folders are accessible, then try again.",
        "status_saved": "JSON report exported locally. Nothing was transmitted.",
        "status_export_error": "The JSON report could not be exported. Choose a new filename and check its folder permissions.",
        "status_export_exists": "Choose a new filename. Existing report files are not overwritten.",
        "no_game": "Choose a game before scanning.",
        "scan_error_title": "Game Troubleshooting Center",
        "export_error_title": "Report export",
        "status_passed": "Passed",
        "status_warning": "Warning",
        "status_failed": "Failed",
        "status_unknown": "Unknown",
        "status_not_checked": "Not checked",
        "status_partial": "Partial",
        "severity_info": "Information",
        "severity_warning": "Warning",
        "severity_error": "Error",
        "category_installation": "Installation",
        "category_configuration": "Configuration",
        "category_mods": "Mods",
        "category_prerequisites": "Prerequisites",
        "category_compatibility": "Compatibility",
        "finding_id": "Finding ID: {id}",
        "evidence": "Observed evidence",
        "recommendation": "Suggested next step",
        "source": "Source",
        "report": "Deterministic JSON report preview",
        "empty_category": "No findings in this category.",
        "export_initial": "GameTroubleshootingReport.json",
        "export_dialog": "Export a new troubleshooting report",
        "json_file": "JSON report",
    },
    "de": {
        "title": "Koei-Tecmo-Spielhilfe",
        "intro": "Führe begrenzte, schreibgeschützte Prüfungen für ein Windows-PC-Spiel aus. Es werden nur ausgewählte Ordner gelesen; Installationen, Konfigurationen und Mods werden nicht verändert.",
        "safety": "Es werden keine Reparaturen ausgeführt. Prüfe jede Empfehlung und entscheide selbst, ob du ihr folgst.",
        "game": "Spiel / Plattform / Edition",
        "choose_game": "Spiel auswählen",
        "installation": "Installationsordner",
        "configuration": "Konfigurationsordner (optional)",
        "mods": "Mod-Ordner (optional; standardmäßig Installationsordner)",
        "browse": "Durchsuchen…",
        "browse_installation": "Installationsordner des Spiels auswählen",
        "browse_configuration": "Konfigurationsordner des Spiels auswählen",
        "browse_mods": "Mod-Ordner auswählen",
        "clear": "Leeren",
        "scan": "Ausgewählte Ordner prüfen",
        "export": "JSON-Bericht exportieren…",
        "no_report": "Spiel auswählen, gewünschte Ordner angeben und die Prüfung starten. Ordner werden erst nach Auswahl von „Prüfen“ untersucht.",
        "read_only": "Ordner werden schreibgeschützt geprüft. Der Bericht enthält keine absoluten Pfade, Konfigurationswerte, Dateiinhalte, Prüfsummen oder Zeitstempel.",
        "overall": "Gesamtstatus: {status}",
        "audit_key": "Prüfschlüssel: Schema {schema_version} · Regelsatz {ruleset_version}",
        "status_ready": "Bereit zur Prüfung.",
        "status_busy": "Ausgewählte Ordner werden gelesen…",
        "status_complete": "Prüfung abgeschlossen: {count} Befunde. Keine ausgewählte Datei wurde verändert.",
        "status_changed": "Auswahl geändert. Bericht durch erneute Prüfung aktualisieren.",
        "status_error": "Prüfung fehlgeschlagen. Zugänglichkeit der ausgewählten Ordner prüfen und erneut versuchen.",
        "status_saved": "JSON-Bericht lokal exportiert. Es wurde nichts übertragen.",
        "status_export_error": "JSON-Bericht konnte nicht exportiert werden. Neuen Dateinamen und Ordnerrechte prüfen.",
        "status_export_exists": "Neuen Dateinamen wählen. Vorhandene Berichte werden nicht überschrieben.",
        "no_game": "Vor der Prüfung ein Spiel auswählen.",
        "scan_error_title": "Koei-Tecmo-Spielhilfe",
        "export_error_title": "Berichtsexport",
        "status_passed": "Bestanden",
        "status_warning": "Warnung",
        "status_failed": "Fehlgeschlagen",
        "status_unknown": "Unbekannt",
        "status_not_checked": "Nicht geprüft",
        "status_partial": "Teilweise",
        "severity_info": "Information",
        "severity_warning": "Warnung",
        "severity_error": "Fehler",
        "category_installation": "Installation",
        "category_configuration": "Konfiguration",
        "category_mods": "Mods",
        "category_prerequisites": "Voraussetzungen",
        "category_compatibility": "Kompatibilität",
        "finding_id": "Befund-ID: {id}",
        "evidence": "Erfasste Hinweise",
        "recommendation": "Möglicher nächster Schritt",
        "source": "Quelle",
        "report": "Deterministische JSON-Vorschau",
        "empty_category": "Keine Befunde in dieser Kategorie.",
        "export_initial": "GameTroubleshootingReport.json",
        "export_dialog": "Neuen Diagnosebericht exportieren",
        "json_file": "JSON-Bericht",
    },
}

_STATUS = {
    "passed": "status_passed",
    "warning": "status_warning",
    "failed": "status_failed",
    "unknown": "status_unknown",
    "not_checked": "status_not_checked",
    "partial": "status_partial",
}


def export_json_report(report, destination):
    """Write a deterministic report to a new JSON file and verify its bytes."""
    destination = Path(destination)
    if destination.suffix.casefold() != ".json":
        raise ValueError("Troubleshooting reports require a .json filename.")
    content = report.to_json().encode("utf-8")
    identity = None
    try:
        with destination.open("xb") as stream:
            info = os.fstat(stream.fileno())
            identity = (info.st_dev, info.st_ino)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if destination.read_bytes() != content:
            raise OSError("Troubleshooting report read-back differed.")
    except Exception:
        if identity is not None:
            try:
                current = destination.lstat()
                if (current.st_dev, current.st_ino) == identity:
                    destination.unlink()
            except OSError:
                pass
        raise
    return destination


class TroubleshootingWorkspace:
    """A lazy shell workspace that presents reports without exposing local paths."""

    def __init__(self, root, parent, language="en"):
        self.root = root
        self.language = "de" if str(language).lower().startswith("de") else "en"
        self.text = _TEXT[self.language]
        self._palette = None
        self._closed = False
        self._poll_id = None
        self._revision = 0
        self._loading = True
        self._font_widgets = []
        self._font_family = None
        self._font_size = None
        self._wrap_labels = []
        self._control_widgets = []
        self._label_keys = []
        self._button_keys = []
        self._status_key = "status_ready"
        self._status_values = {}
        self.report = None
        self.busy = False
        self._results = queue.SimpleQueue()
        self._game_labels = {}
        self._games = {}
        for game in sorted((item for item in GAMES if item.platform == "Windows PC"),
                           key=lambda item: (item.title.casefold(), item.subtitle.casefold(), item.id)):
            label = f"{game.title} · {game.subtitle} [{game.platform}]"
            self._games[label] = game.id
            self._game_labels[game.id] = label

        self.frame = ttk.Frame(parent)
        self.viewport = ScrollablePanel(self.frame)
        self.viewport.frame.pack(fill="both", expand=True)
        content = self.viewport.content
        content.configure(padding=(22, 12))
        content.columnconfigure(0, weight=1)
        content.bind("<Configure>", self._resize_labels, add="+")
        self.frame.bind("<Destroy>", self._on_destroy, add="+")

        self.title_label = ttk.Label(content, text=self.text["title"], style="Section.TLabel")
        self.title_label.pack(anchor="w")
        self._register_font(self.title_label, weight="bold", delta=4)
        self.intro_label = self._label(content, "intro")
        self.safety_label = self._label(content, "safety", muted=True)
        self._label(content, "game")
        self.game = tk.StringVar(root, value=self.text["choose_game"])
        self.game_selector = ttk.Combobox(content, textvariable=self.game,
                                          values=(self.text["choose_game"], *self._games), state="readonly")
        self.game_selector.pack(fill="x", pady=(0, 5))
        self._control_widgets.append(self.game_selector)

        self.installation_path = tk.StringVar(root, value="")
        self.config_path = tk.StringVar(root, value="")
        self.mods_path = tk.StringVar(root, value="")
        self._path_inputs = {
            "installation": self.installation_path,
            "configuration": self.config_path,
            "mods": self.mods_path,
        }
        self._path_entries = {}
        self._browse_buttons = {}
        self._clear_buttons = {}
        for key, variable in self._path_inputs.items():
            self._add_path_row(content, key, variable)

        self.read_only_label = self._label(content, "read_only", muted=True)
        actions = ttk.Frame(content)
        actions.pack(fill="x", pady=(8, 6))
        self.scan_button = self._button(actions, "scan", self.scan, primary=True)
        self.export_button = self._button(actions, "export", self.export, side="left")
        self.export_button.configure(state="disabled")
        self.status = tk.StringVar(root, value=self.text[self._status_key])
        self.status_label = ttk.Label(content, textvariable=self.status, wraplength=900)
        self.status_label.pack(anchor="w", pady=(0, 6))
        self._register_font(self.status_label, weight="bold", delta=1)
        self._wrap_labels.append(self.status_label)

        self.overall = tk.StringVar(root, value="")
        self.overall_label = ttk.Label(content, textvariable=self.overall, style="Section.TLabel")
        self.overall_label.pack(anchor="w", pady=(4, 5))
        self._register_font(self.overall_label, weight="bold", delta=1)
        self.audit_key = tk.StringVar(root, value="")
        self.audit_label = ttk.Label(content, textvariable=self.audit_key, style="Muted.TLabel")
        self.audit_label.pack(anchor="w", pady=(0, 5))
        self._register_font(self.audit_label)
        self._wrap_labels.append(self.audit_label)

        self.findings_frame = ttk.Frame(content)
        self.findings_frame.pack(fill="x", expand=True)
        self._show_no_report()

        self.report_heading = ttk.Label(content, text=self.text["report"], style="Section.TLabel")
        self.report_heading.pack(anchor="w", pady=(12, 4))
        self._register_font(self.report_heading, weight="bold", delta=1)
        preview_holder = ttk.Frame(content)
        preview_holder.pack(fill="both", expand=True)
        self.preview = tk.Text(preview_holder, height=14, wrap="word", state="disabled",
                               takefocus=True, undo=False)
        self.preview_scrollbar = ttk.Scrollbar(preview_holder, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=self.preview_scrollbar.set)
        self.preview_scrollbar.pack(side="right", fill="y")
        self.preview.pack(fill="both", expand=True)
        self._register_font(self.preview)

        for variable in (self.game, self.installation_path, self.config_path, self.mods_path):
            variable.trace_add("write", self._selection_changed)
        self._loading = False

    def _register_font(self, widget, weight="normal", delta=0):
        self._font_widgets.append((widget, weight, delta))
        if self._font_family is not None and self._font_size is not None:
            widget.configure(font=(self._font_family, max(8, self._font_size + delta), weight))

    def _label(self, parent, key, muted=False):
        label = ttk.Label(parent, text=self.text[key], wraplength=900,
                          style="Muted.TLabel" if muted else "TLabel")
        label.pack(anchor="w", pady=(5, 2))
        self._label_keys.append((label, key))
        self._wrap_labels.append(label)
        self._register_font(label)
        return label

    def _button(self, parent, key, command, side="left", primary=False):
        button = ttk.Button(parent, text=self.text[key], command=command,
                            style="Primary.TButton" if primary else "TButton")
        button.pack(side=side, padx=(0, 8), pady=2)
        self._button_keys.append((button, key))
        self._register_font(button)
        return button

    def _add_path_row(self, parent, key, variable):
        self._label(parent, key)
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 2))
        row.columnconfigure(0, weight=1)
        entry = ttk.Entry(row, textvariable=variable)
        entry.grid(row=0, column=0, sticky="ew")
        browse = ttk.Button(row, text=self.text["browse"], command=lambda name=key: self.browse(name))
        self._button_keys.append((browse, "browse"))
        self._register_font(browse)
        browse.grid(row=0, column=1, padx=(8, 0))
        clear = ttk.Button(row, text=self.text["clear"], command=lambda name=key: self.clear(name))
        self._button_keys.append((clear, "clear"))
        self._register_font(clear)
        clear.grid(row=0, column=2, padx=(4, 0))
        self._path_entries[key] = entry
        self._browse_buttons[key] = browse
        self._clear_buttons[key] = clear
        self._control_widgets.extend((entry, browse, clear))

    def _tr(self, key, **values):
        return self.text[key].format(**values)

    def _status(self, key, **values):
        self._status_key = key
        self._status_values = values
        self.status.set(self._tr(key, **values))

    def _on_destroy(self, event):
        if event.widget is self.frame:
            self.close()

    def _selection_changed(self, *_args):
        if self._loading:
            return
        self._revision += 1
        if self.report is not None:
            self.report = None
            self.overall.set("")
            self.audit_key.set("")
            self._show_no_report()
            self._set_preview("")
            self.export_button.configure(state="disabled")
            self._status("status_changed")
        elif not self.busy:
            self._status("status_ready")

    def _game_id(self):
        return self._games.get(self.game.get())

    def browse(self, key):
        variable = self._path_inputs[key]
        path = filedialog.askdirectory(parent=self.root, title=self._tr("browse_" + key), mustexist=True)
        if path:
            variable.set(path)

    def clear(self, key):
        self._path_inputs[key].set("")

    def _set_busy(self, value):
        self.busy = value
        for widget in self._control_widgets:
            if widget is self.game_selector:
                widget.configure(state="disabled" if value else "readonly")
            else:
                widget.configure(state="disabled" if value else "normal")
        self.scan_button.configure(state="disabled" if value else "normal")
        self.export_button.configure(state="disabled" if value or self.report is None else "normal")

    def scan(self):
        if self.busy:
            return
        game_id = self._game_id()
        if not game_id:
            messagebox.showinfo(self.text["title"], self.text["no_game"], parent=self.root)
            return
        paths = {
            "installation_path": self.installation_path.get().strip() or None,
            "config_path": self.config_path.get().strip() or None,
            "mods_path": self.mods_path.get().strip() or None,
        }
        revision = self._revision
        self.report = None
        self.overall.set("")
        self.audit_key.set("")
        self._show_no_report()
        self._set_preview("")
        self._set_busy(True)
        self._status("status_busy")

        def worker():
            try:
                result = diagnose_game(game_id, **paths)
                self._results.put((revision, result, None))
            except Exception:
                # The UI deliberately avoids exposing filesystem paths or raw
                # exception text in the report or dialog.
                self._results.put((revision, None, True))

        threading.Thread(target=worker, daemon=True, name="game-troubleshooting-scan").start()
        self._poll_id = self.root.after(30, self._poll)

    def _poll(self):
        if self._closed:
            self._poll_id = None
            return
        try:
            revision, result, failed = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.root.after(30, self._poll)
            return
        self._poll_id = None
        self._set_busy(False)
        if revision != self._revision:
            self.report = None
            self._status("status_changed")
            return
        if failed:
            self.report = None
            self.overall.set("")
            self.audit_key.set("")
            self._show_no_report()
            self._set_preview("")
            self._status("status_error")
            return
        self.report = result
        self._render_findings()
        self._set_preview(self.report.to_json())
        status = _STATUS.get(self.report.overall_status, "status_unknown")
        self.overall.set(self._tr("overall", status=self._tr(status)))
        self.audit_key.set(self._tr("audit_key", schema_version=SCHEMA_VERSION,
                                    ruleset_version=self.report.ruleset_version))
        self._status("status_complete", count=len(self.report.findings))
        self.export_button.configure(state="normal")

    def _show_no_report(self):
        for widget in self.findings_frame.winfo_children():
            widget.destroy()
        self._wrap_labels = [item for item in self._wrap_labels if item.winfo_exists()]
        self._font_widgets = [item for item in self._font_widgets if item[0].winfo_exists()]
        label = ttk.Label(self.findings_frame, text=self.text["no_report"], wraplength=900,
                          style="Muted.TLabel")
        label.pack(anchor="w", pady=(4, 8))
        self._wrap_labels.append(label)
        self._register_font(label)

    def _render_findings(self):
        for widget in self.findings_frame.winfo_children():
            widget.destroy()
        self._wrap_labels = [item for item in self._wrap_labels if item.winfo_exists()]
        self._font_widgets = [item for item in self._font_widgets if item[0].winfo_exists()]
        for category in CATEGORY_ORDER:
            findings = [item for item in self.report.findings if item.category == category]
            group = ttk.LabelFrame(self.findings_frame, style="Troubleshooting.TLabelframe",
                                   text=self._tr("category_" + category), padding=(10, 7))
            group.pack(fill="x", expand=True, pady=(0, 7))
            if not findings:
                self._add_finding_label(group, self.text["empty_category"], muted=True)
                continue
            for index, finding in enumerate(findings):
                if index:
                    ttk.Separator(group, orient="horizontal").pack(fill="x", pady=5)
                status_key = _STATUS.get(finding.status, "status_unknown")
                severity_key = "severity_" + finding.severity
                heading = ttk.Label(group,
                    text=f"{self._tr(status_key)} · {finding.title} · {self._tr(severity_key)}",
                    style="Section.TLabel", wraplength=900)
                heading.pack(anchor="w", pady=(2, 1))
                self._wrap_labels.append(heading)
                self._register_font(heading, weight="bold")
                self._add_finding_label(group, finding.summary)
                self._add_finding_label(group, self._tr("finding_id", id=finding.id), muted=True)
                if finding.evidence:
                    self._add_finding_label(group, self.text["evidence"], muted=True, bold=True)
                    for evidence in finding.evidence:
                        self._add_finding_label(group, "• " + evidence)
                self._add_finding_label(group, self.text["recommendation"], muted=True, bold=True)
                self._add_finding_label(group, finding.recommendation)
                if finding.source:
                    self._add_finding_label(group, self.text["source"] + ": " + finding.source,
                                            muted=True)

    def _add_finding_label(self, parent, text, muted=False, bold=False):
        label = ttk.Label(parent, text=text, wraplength=900,
                          style="Muted.TLabel" if muted else "TLabel")
        label.pack(anchor="w", pady=(2, 1))
        self._wrap_labels.append(label)
        self._register_font(label, weight="bold" if bold else "normal")
        return label

    def _set_preview(self, text):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if text:
            self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def export(self):
        if self.busy or self.report is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title=self.text["export_dialog"],
            defaultextension=".json",
            initialfile=self.text["export_initial"],
            filetypes=((self.text["json_file"], "*.json"),),
        )
        if not path:
            return
        try:
            export_json_report(self.report, path)
        except FileExistsError:
            self._status("status_export_exists")
            messagebox.showerror(self.text["export_error_title"], self.text["status_export_exists"],
                                 parent=self.root)
            return
        except (OSError, ValueError):
            self._status("status_export_error")
            messagebox.showerror(self.text["export_error_title"], self.text["status_export_error"],
                                 parent=self.root)
            return
        self._status("status_saved")

    def apply_theme(self, palette):
        self._palette = palette
        self.viewport.apply_theme(palette)
        self.preview.configure(background=palette["surface"], foreground=palette["text"],
                               insertbackground=palette["text"], selectbackground=palette["accent"],
                               selectforeground="#ffffff")

    def set_text_size(self, size, font_family):
        self._font_size = size
        self._font_family = font_family
        ttk.Style(self.root).configure("Troubleshooting.TLabelframe.Label",
                                       font=(font_family, max(8, size + 1), "bold"))
        for widget, weight, delta in tuple(self._font_widgets):
            if widget.winfo_exists():
                widget.configure(font=(font_family, max(8, size + delta), weight))

    def set_language(self, language):
        language = "de" if str(language).lower().startswith("de") else "en"
        if language == self.language:
            return
        game_id = self._game_id()
        self._loading = True
        self.language = language
        self.text = _TEXT[language]
        self.title_label.configure(text=self.text["title"])
        self.report_heading.configure(text=self.text["report"])
        for widget, key in self._label_keys:
            if widget.winfo_exists():
                widget.configure(text=self.text[key])
        for widget, key in self._button_keys:
            if widget.winfo_exists():
                widget.configure(text=self.text[key])
        self.game_selector.configure(values=(self.text["choose_game"], *self._games))
        if game_id:
            self.game.set(self._game_labels[game_id])
        else:
            self.game.set(self.text["choose_game"])
        self._loading = False
        self._render_findings() if self.report is not None else self._show_no_report()
        if self.report is not None:
            status = _STATUS.get(self.report.overall_status, "status_unknown")
            self.overall.set(self._tr("overall", status=self._tr(status)))
            self.audit_key.set(self._tr("audit_key", schema_version=SCHEMA_VERSION,
                                        ruleset_version=self.report.ruleset_version))
            self._status("status_complete", count=len(self.report.findings))
            self.export_button.configure(state="disabled" if self.busy else "normal")
        elif self.busy:
            self._status("status_busy")
        else:
            self.audit_key.set("")
            self._status("status_ready")
        if self._palette is not None:
            self.apply_theme(self._palette)
        self._resize_labels()

    def _resize_labels(self, event=None):
        width = max(180, (event.width if event is not None else self.viewport.canvas.winfo_width()) - 52)
        for label in self._wrap_labels:
            try:
                if label.winfo_exists():
                    label.configure(wraplength=width)
            except tk.TclError:
                pass

    def close(self):
        self._closed = True
        self._revision += 1
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

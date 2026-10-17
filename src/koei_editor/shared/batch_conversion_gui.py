"""Retained conversion queue with reviewed scopes and worker progress."""

from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from koei_editor import conversion
from koei_editor.shared import batch_conversion as backend
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.scrollable_panel import ScrollablePanel


class BatchWorkspace:
    def __init__(self, root, parent):
        self.root, self.frame = root, ttk.Frame(parent, padding=(28, 16))
        self.actions = ttk.Frame(self.frame)
        self.actions.pack(side='bottom', fill='x', pady=(8, 0))
        for column in range(2):
            self.actions.columnconfigure(column, weight=1)
        self.viewport = ScrollablePanel(self.frame)
        self.viewport.frame.pack(fill='both', expand=True)
        body = self.viewport.content
        self.specs = []
        self.prepared = None
        self.last_report = None
        self.busy = False
        self.finished_batch = None
        self.finished_outcomes = None
        self._revision = 0
        self._counter = 0
        self._results = queue.SimpleQueue()
        self._stop = threading.Event()
        self._statuses = {}
        ttk.Label(
            body, text="BATCH CONVERTER", font=(ui_font(root), 23, "bold")
        ).pack(anchor="w")
        ttk.Label(
            body,
            text="Review several conversions, then create separate verified copies.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 12))
        ttk.Label(
            body,
            text="Add a reviewed job from Save Converter, or load a schema-1 JSON plan. "
            "Every job uses an explicit supported route and a new output folder. All jobs pass preflight before any copy is written.",
            wraplength=980,
        ).pack(anchor="w", pady=(0, 14))
        bar = self.actions
        self.controls = []
        for text, callback in (
            ("Load plan…", self.load),
            ("Save plan…", self.save_plan),
            ("Review all jobs", self.review),
            ("Remove selected", self.remove),
            ("Clear queue", self.clear),
        ):
            button = ttk.Button(bar, text=text, command=callback)
            index = len(self.controls)
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 8), pady=3)
            self.controls.append(button)
        self.export_button = ttk.Button(
            bar, text="Export reviewed copies", command=self.export, state="disabled"
        )
        self.export_button.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=3)
        self.stop_button = ttk.Button(
            bar, text="Stop after current copy", command=self.stop, state="disabled"
        )
        self.stop_button.grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=3)
        self.status = tk.StringVar(
            root, value="The queue is empty. Add a reviewed conversion or load a plan."
        )
        ttk.Label(body, textvariable=self.status, wraplength=980).pack(
            anchor="w", pady=(14, 8)
        )
        table = ttk.Frame(body)
        table.pack(fill="both", expand=True)
        self.table = ttk.Treeview(
            table,
            columns=("id", "route", "source", "template", "output", "status"),
            show="headings",
            height=10,
        )
        for key, text, width in (
            ("id", "Job", 80),
            ("route", "Conversion", 290),
            ("source", "Source", 120),
            ("template", "Template", 120),
            ("output", "New folder", 140),
            ("status", "Status", 100),
        ):
            self.table.heading(key, text=text)
            self.table.column(key, width=width, minwidth=70)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        scroll.pack(side="right", fill="y")
        horizontal.pack(side="bottom", fill="x")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.show_scope)
        self.scope = tk.StringVar(
            root, value="Select a job to review its transfer scope."
        )
        detail = ttk.Frame(body)
        detail.pack(fill="x", pady=12)
        self.scope_preview = tk.Text(
            detail,
            height=5,
            width=1,
            wrap="word",
            relief="flat",
            state="disabled",
            padx=8,
            pady=6,
        )
        detail_scroll = ttk.Scrollbar(
            detail, orient="vertical", command=self.scope_preview.yview
        )
        self.scope_preview.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side="right", fill="y")
        self.scope_preview.pack(side="left", fill="x", expand=True)
        self.scope.trace_add("write", self._render_scope)
        self._render_scope()
        self.report_button = ttk.Button(
            self.actions,
            text="Save batch report…",
            command=self.save_report,
            state="disabled",
        )
        self.report_button.grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=3)
        ttk.Label(
            body,
            text="A later failure or stop retains completed verified copies. Remaining jobs are not started. "
            "Console reimport/signing and in-game testing remain external.",
            style="Muted.TLabel",
            wraplength=980,
        ).pack(anchor="w", pady=(10, 0))

        body.bind('<Configure>',self._resize_guidance,add='+')

    def _resize_guidance(self, event):
        for widget in self.viewport.content.winfo_children():
            if isinstance(widget, ttk.Label):
                widget.configure(wraplength=max(1, event.width - 8))


    def _render_scope(self, *_args):
        self.scope_preview.configure(state="normal")
        self.scope_preview.delete("1.0", "end")
        self.scope_preview.insert("1.0", self.scope.get())
        self.scope_preview.configure(state="disabled")

    def apply_theme(self, palette):
        self.viewport.apply_theme(palette)
        self.scope_preview.configure(
            background=palette["surface"],
            foreground=palette["text"],
            insertbackground=palette["text"],
        )

    def invalidate(self):
        self._revision += 1
        self.prepared = None
        self.last_report = None
        self.finished_batch = None
        self.finished_outcomes = None
        self._statuses = {}
        self.export_button.configure(state="disabled")
        self.report_button.configure(state="disabled")
        self.render()

    def render(self):
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        for spec in self.specs:
            route = conversion.get_route(spec.route)
            self.table.insert(
                "",
                "end",
                iid=spec.id,
                values=(
                    spec.id,
                    route.label,
                    spec.source.name,
                    spec.template.name,
                    spec.output_dir.name,
                    self._statuses.get(spec.id, "Queued"),
                ),
            )
        if selected and self.table.exists(selected[0]):
            self.table.selection_set(selected[0])

    def show_scope(self, _event=None):
        selected = self.table.selection()
        if not selected:
            return
        spec = next((spec for spec in self.specs if spec.id == selected[0]), None)
        if spec is None:
            return
        route = conversion.get_route(spec.route)
        text = route.scope_description
        if self.prepared:
            review = next(
                job.review for job in self.prepared.jobs if job.spec.id == spec.id
            )
            text += "\n\n" + "\n".join(review.notes)
        self.scope.set(text)

    def add_review(self, review):
        if self.busy:
            messagebox.showinfo(
                "Batch Converter",
                "Wait for the current queue operation.",
                parent=self.root,
            )
            return False
        parent = filedialog.askdirectory(
            parent=self.root, title="Choose a parent for this job’s new output folder"
        )
        if not parent:
            return False
        name = simpledialog.askstring(
            "New batch output folder",
            "Name the new output folder:",
            initialvalue="Converted-" + review.route.target_id,
            parent=self.root,
        )
        if not name:
            return False
        if (
            name in (".", "..")
            or "/" in name
            or "\\" in name
            or Path(name).name != name
        ):
            messagebox.showerror(
                "New output folder",
                "Enter one new folder name without a path.",
                parent=self.root,
            )
            return False
        self._counter += 1
        while any(spec.id == "copy-" + str(self._counter) for spec in self.specs):
            self._counter += 1
        spec = backend.JobSpec(
            "copy-" + str(self._counter),
            review.route.id,
            review.source.document.source,
            review.template.document.source,
            Path(parent) / name,
        )
        try:
            specs = backend._specs(tuple(self.specs) + (spec,))
        except (OSError, ValueError) as error:
            messagebox.showerror("Batch Converter", str(error), parent=self.root)
            return False
        self.specs = list(specs)
        self.invalidate()
        self.table.selection_set(spec.id)
        self.show_scope()
        self.status.set(
            f"{len(self.specs)} queued job(s). Review all jobs before exporting."
        )
        return True

    def remove(self):
        if self.busy:
            return
        selected = set(self.table.selection())
        self.specs = [spec for spec in self.specs if spec.id not in selected]
        self.invalidate()
        self.status.set("Queue changed. Review all remaining jobs.")

    def clear(self):
        if self.busy:
            return
        self.specs = []
        self.invalidate()
        self.scope.set("Select a job to review its transfer scope.")
        self.status.set("The queue is empty.")

    def _start(self, kind, operation):
        if self.busy:
            return
        self.busy = True
        revision = self._revision
        self._stop.clear()
        for control in self.controls:
            control.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.report_button.configure(state="disabled")
        self.stop_button.configure(state="normal" if kind == "export" else "disabled")
        self.status.set(
            {
                "load": "Loading conversion plan…",
                "review": "Checking every copied input, template and output…",
                "export": "Exporting reviewed copies…",
                "report": "Verifying outputs and writing the batch report…",
                "plan": "Writing a private batch plan…",
            }[kind]
        )

        def progress(job, status):
            self._results.put(("progress", revision, (job, status), None))

        def worker():
            try:
                self._results.put((kind, revision, operation(progress), None))
            except Exception as error:
                self._results.put((kind, revision, None, error))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(40, self._poll)

    def _poll(self):
        while True:
            try:
                kind, revision, result, error = self._results.get_nowait()
            except queue.Empty:
                self.root.after(40, self._poll)
                return
            if kind == "progress":
                if revision == self._revision:
                    job, status = result
                    self._statuses[job] = status.replace("_", " ").title()
                    self.render()
                continue
            break
        self.busy = False
        for control in self.controls:
            control.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if revision != self._revision:
            self.status.set("Queue changed. Review it again.")
            return
        if error is not None:
            if kind in ("report", "plan"):
                self.report_button.configure(
                    state="normal" if self.last_report else "disabled"
                )
                self.export_button.configure(
                    state="normal" if self.prepared else "disabled"
                )
            else:
                self.prepared = None
                self.last_report = None
            self.status.set("Queue operation failed: " + str(error))
            messagebox.showerror("Batch Converter", str(error), parent=self.root)
            return
        if kind == "load":
            self.specs = list(result)
            self._counter = max(self._counter, len(self.specs))
            self.invalidate()
            self.status.set("Plan loaded. Review all jobs before exporting.")
        elif kind == "review":
            self.prepared = result
            self.last_report = None
            self.export_button.configure(state="normal")
            self.status.set(
                f"All {len(result.jobs)} jobs reviewed. Select a job to inspect its scope."
            )
            self.show_scope()
        elif kind == "export":
            self.finished_batch, self.finished_outcomes, self.last_report = result
            result = self.last_report
            self.prepared = None
            self.report_button.configure(state="normal")
            for row in result["jobs"]:
                self._statuses[row["id"]] = row["status"].replace("_", " ").title()
            self.render()
            self.status.set(
                f"{result['completed']} completed; {result['failed']} failed; {result['not_started']} not started. Completed copies remain in their new folders."
            )
        elif kind == "plan":
            self.status.set("Private batch plan saved: " + Path(result).name)
            if self.prepared:
                self.export_button.configure(state="normal")
            if self.last_report:
                self.report_button.configure(state="normal")
        else:
            self.status.set("Batch report saved: " + Path(result).name)
            if self.last_report:
                self.report_button.configure(state="normal")

    def load(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Load a copied conversion plan",
            filetypes=[("Batch plan", "*.json")],
        )
        if path:
            self._start(
                "load", lambda _progress: backend._specs(backend.load_plan(path))
            )

    def save_plan(self):
        if self.busy:
            return
        if not self.specs:
            messagebox.showinfo(
                "Batch Converter",
                "Add conversion jobs before saving a plan.",
                parent=self.root,
            )
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save a new private batch plan",
            defaultextension=".json",
            filetypes=[("Batch plan", "*.json")],
            initialfile="ConversionPlan.json",
        )
        if path:
            specs = tuple(self.specs)
            self._start("plan", lambda _progress: backend.export_plan(specs, path))

    def review(self):
        if self.busy:
            return
        if not self.specs:
            messagebox.showinfo(
                "Batch Converter",
                "Add a reviewed conversion from Save Converter or load a plan.",
                parent=self.root,
            )
            return
        specs = tuple(self.specs)
        self.prepared = None
        self.last_report = None
        self._start("review", lambda progress: backend.prepare_specs(specs, progress))

    def export(self):
        if self.busy or self.prepared is None:
            return
        prepared = self.prepared

        def perform(progress):
            outcomes = backend.execute(prepared, progress, self._stop.is_set)
            return prepared, outcomes, backend.outcome_report(prepared, outcomes)

        self._start("export", perform)

    def stop(self):
        if self.busy:
            self._stop.set()
            self.stop_button.configure(state="disabled")
            self.status.set(
                "Stopping after the current verified copy. Completed outputs will remain."
            )

    def save_report(self):
        if self.busy or self.last_report is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save a new private batch report",
            defaultextension=".json",
            filetypes=[("Batch report", "*.json")],
            initialfile="ConversionBatch.json",
        )
        if path:
            prepared, outcomes = self.finished_batch, self.finished_outcomes
            self._start(
                "report",
                lambda _progress: backend.export_report(
                    backend.outcome_report(prepared, outcomes), path
                ),
            )

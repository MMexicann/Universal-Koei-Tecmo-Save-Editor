"""Planning-only character and weapon build workspace.

The view consumes a provider's already-qualified values and never reads or
writes a game save. Import/export handles only portable build-plan JSON. The
only route into an editor is the injected callback, which must stage values
through that editor's ordinary validation and review workflow.
"""

from collections.abc import Mapping
from dataclasses import replace
import math
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import build_workshop as plan_model
from koei_editor.shared.build_workshop_context import is_equipment_field


_NO_VALUE = object()


def _as_mapping(value):
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    names = ("label", "name", "category", "character_id", "character_label", "slot_id",
             "current_value", "opened_value", "value", "display_value", "choices", "evidence",
             "source", "formula", "value_type")
    return {name: getattr(value, name) for name in names if hasattr(value, name)}


def _display(value):
    if value is _NO_VALUE:
        return "—"
    if value is None:
        return "None"
    if type(value) is bool:
        return "Yes" if value else "No"
    if type(value) is int:
        return f"{value:,}"
    if type(value) is float:
        return format(value, ".12g")
    return str(value)


def _parse_scalar(text, original, value_type=None):
    """Parse an inert JSON scalar while preserving its known native type."""
    if value_type == "boolean" or type(original) is bool:
        normalized = text.strip().casefold()
        if normalized in ("true", "yes", "1"):
            return True
        if normalized in ("false", "no", "0"):
            return False
        raise SaveError("Enter Yes or No for this planned value.")
    if value_type == "integer" or type(original) is int:
        candidate = text.strip()
        if "," in candidate:
            sign = candidate[0] if candidate.startswith(("+", "-")) else ""
            groups = candidate[len(sign):].split(",")
            if (not groups[0] or len(groups[0]) > 3
                    or any(len(group) != 3 for group in groups[1:])
                    or any(not group.isdecimal() for group in groups)):
                raise SaveError("Enter a whole number for this planned value.")
            candidate = sign + "".join(groups)
        try:
            return int(candidate, 10)
        except ValueError as error:
            raise SaveError("Enter a whole number for this planned value.") from error
    if value_type == "number" or type(original) is float:
        try:
            value = float(text.strip())
        except ValueError as error:
            raise SaveError("Enter a number for this planned value.") from error
        if not math.isfinite(value):
            raise SaveError("Enter a finite number for this planned value.")
        return value
    if value_type == "string" or type(original) is str or original is _NO_VALUE:
        return text
    if original is None:
        # A provider may identify a type for fields whose current value is
        # unavailable. Without one, accept text only; the editor validates it.
        return text
    raise SaveError("This planned value has an unsupported scalar type.")


def _choice_pairs(meta):
    """Normalize only choices explicitly supplied by a game provider."""
    result = []
    for choice in meta.get("choices", ()) or ():
        if isinstance(choice, Mapping):
            if "value" not in choice:
                continue
            value = choice["value"]
            label = choice.get("label", _display(value))
        elif isinstance(choice, (tuple, list)) and len(choice) == 2:
            value, label = choice
        else:
            continue
        if (type(value) in (bool, int, float, str) or value is None) and type(label) is str:
            result.append((value, label))
    return tuple(result)


class BuildWorkshopView(ttk.Frame):
    """Plan, compare, and export builds without editing save bytes.

    Args:
        game_id/platform_id: Exact registered profile identity.
        plans: Provider-created plans from existing verified records and/or
            portable plans already imported by the host.
        field_metadata: Mapping of stable field/slot IDs to display metadata.
            Supported keys include ``label``, ``category``, ``character_id``,
            ``character_label``, ``current_value``/``opened_value``,
            ``value_type``, ``slot_id`` and ``choices``. Each choice is a
            ``(native_value, display_label)`` pair; choices are never inferred.
        verified_stats: Provider-calculated/displayed rows with ``label``,
            ``value`` and ``evidence`` (or ``source``). These rows are shown
            verbatim and kept separate from generic plan deltas.
        on_stage: Callback invoked only after the user selects "Stage Plan in
            Editor". It should call the editor's ordinary ``stage_values``
            path and leave Review Changes/Save As to that editor.
    """

    def __init__(self, master, *, game_id, platform_id, plans=(),
                 field_metadata=None, verified_stats=(), on_stage=None,
                 on_compare_records=None, record_options=(),
                 theme="Light"):
        super().__init__(master)
        self.game_id = game_id
        self.platform_id = platform_id
        self.field_metadata = {
            key: _as_mapping(value) for key, value in (field_metadata or {}).items()
        }
        self.verified_stats = tuple(_as_mapping(row) for row in (verified_stats or ()))
        self.on_stage = on_stage
        self.on_compare_records = on_compare_records
        self._pending_record_options = tuple(record_options or ())
        self.theme = theme
        self._plans = []
        self._selected_index = None
        self._comparison_index = None
        self._row_keys = {}
        self._comparison_choices = {}

        for plan in plans:
            normalized = self._coerce_plan(plan)
            if (normalized.game_id, normalized.platform_id) == (game_id, platform_id):
                self._plans.append(normalized)
        self._provider_plan_ids = {id(plan) for plan in self._plans}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self._build()
        if self.on_compare_records is not None:
            self._build_record_compare_page()
            self.set_record_options(self._pending_record_options)
        self._refresh()

    def _coerce_plan(self, plan):
        if type(plan) is plan_model.BuildPlan:
            return plan
        if isinstance(plan, Mapping):
            try:
                return plan_model.BuildPlan(
                    plan["game_id"], plan["platform_id"], plan["character_id"],
                    plan["name"], plan.get("values", {}), plan.get("equipment", {}),
                    plan.get("notes", ""),
                )
            except (KeyError, TypeError) as error:
                raise SaveError("The workshop provider returned an incomplete build plan.") from error
        raise SaveError("The workshop provider returned an unsupported build plan.")

    def _build(self):
        header = ttk.Frame(self, padding=(18, 12, 18, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Character & Weapon Workshop",
                  style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header,
                  text="Plan and compare mapped values. Nothing changes until you stage a plan in the editor.",
                  style="Muted.TLabel", wraplength=900).grid(row=1, column=0, sticky="w", pady=(4, 0))

        toolbar = ttk.Frame(self, padding=(18, 4, 18, 10))
        toolbar.grid(row=1, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)
        ttk.Label(toolbar, text="Build plan").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.plan_choice = tk.StringVar(self)
        self.plan_selector = ttk.Combobox(toolbar, textvariable=self.plan_choice,
                                          state="readonly", width=36)
        self.plan_selector.grid(row=0, column=1, sticky="ew")
        self.plan_selector.bind("<<ComboboxSelected>>", self._choose_plan)
        self.duplicate_button = ttk.Button(toolbar, text="Duplicate for Planning…",
                                           command=self.duplicate_plan)
        self.duplicate_button.grid(row=0, column=2, padx=(8, 0))
        self.add_field_button = ttk.Button(toolbar, text="Add Mapped Field…",
                                           command=self.add_field)
        self.add_field_button.grid(row=0, column=3, padx=(8, 0))
        self.import_button = ttk.Button(toolbar, text="Import Build…", command=self.import_plan)
        self.import_button.grid(row=0, column=4, padx=(8, 0))
        self.export_button = ttk.Button(toolbar, text="Export Build…", command=self.export_plan)
        self.export_button.grid(row=0, column=5, padx=(8, 0))

        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.stats_page = ttk.Frame(self.tabs, padding=12)
        self.build_page = ttk.Frame(self.tabs, padding=12)
        self.compare_page = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.stats_page, text="Verified Stats")
        self.tabs.add(self.build_page, text="Planned Build")
        self.tabs.add(self.compare_page, text="Compare Builds")
        self._build_stats_page()
        self._build_plan_page()
        self._build_compare_page()

        footer = ttk.Frame(self, padding=(18, 0, 18, 12))
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.status = tk.StringVar(self, value="Select a mapped build or import a reusable build preset.")
        ttk.Label(footer, textvariable=self.status, style="Muted.TLabel",
                  wraplength=800).grid(row=0, column=0, sticky="w")
        self.stage_button = ttk.Button(footer, text="Stage Plan in Editor",
                                       style="Primary.TButton", command=self.stage_plan)
        self.stage_button.grid(row=0, column=1, padx=(8, 0))
        if self.on_stage is None:
            self.stage_button.configure(state="disabled")

    def _build_stats_page(self):
        self.stats_page.columnconfigure(0, weight=1)
        self.stats_page.rowconfigure(0, weight=1)
        self.stats_tree = ttk.Treeview(self.stats_page,
            columns=("value", "evidence"), show="tree headings", selectmode="browse")
        self.stats_tree.heading("#0", text="Verified stat")
        self.stats_tree.heading("value", text="Opened / calculated value")
        self.stats_tree.heading("evidence", text="Formula or mapping evidence")
        self.stats_tree.column("#0", width=260, minwidth=150)
        self.stats_tree.column("value", width=160, minwidth=100, stretch=False)
        self.stats_tree.column("evidence", width=520, minwidth=180)
        self.stats_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self.stats_page, orient="vertical", command=self.stats_tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.stats_tree.configure(yscrollcommand=scroll.set)
        self.stats_note = tk.StringVar(self.stats_page,
            value="Rows come from the selected game's verified provider; the Workshop does not recalculate them.")
        ttk.Label(self.stats_page, textvariable=self.stats_note,
                  style="Muted.TLabel", wraplength=900).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _build_plan_page(self):
        self.build_page.columnconfigure(0, weight=1)
        self.build_page.rowconfigure(0, weight=1)
        self.plan_tree = ttk.Treeview(self.build_page,
            columns=("category", "opened", "planned", "evidence"), show="tree headings",
            selectmode="browse")
        self.plan_tree.heading("#0", text="Mapped field / equipment slot")
        self.plan_tree.heading("category", text="Category")
        self.plan_tree.heading("opened", text="Opened value")
        self.plan_tree.heading("planned", text="Planned value")
        self.plan_tree.heading("evidence", text="Mapping")
        self.plan_tree.column("#0", width=300, minwidth=180)
        self.plan_tree.column("category", width=120, minwidth=90, stretch=False)
        self.plan_tree.column("opened", width=140, minwidth=95, stretch=False)
        self.plan_tree.column("planned", width=150, minwidth=100, stretch=False)
        self.plan_tree.column("evidence", width=260, minwidth=140)
        self.plan_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self.build_page, orient="vertical", command=self.plan_tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.plan_tree.configure(yscrollcommand=scroll.set)
        self.plan_tree.bind("<Double-1>", self._edit_selected_cell)
        ttk.Label(self.build_page,
                  text="Double-click a planned value to edit it. Supplied choices are shown exactly as mapped; the editor validates any staged values.",
                  style="Muted.TLabel", wraplength=900).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _build_compare_page(self):
        bar = ttk.Frame(self.compare_page)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="Compare with").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.compare_choice = tk.StringVar(self)
        self.compare_selector = ttk.Combobox(bar, state="readonly", width=36,
                                             textvariable=self.compare_choice)
        self.compare_selector.grid(row=0, column=1, sticky="ew")
        self.compare_selector.bind("<<ComboboxSelected>>", self._choose_comparison)
        self.compare_page.columnconfigure(0, weight=1)
        self.compare_page.rowconfigure(1, weight=1)
        self.compare_tree = ttk.Treeview(self.compare_page,
            columns=("category", "left", "right", "delta"), show="tree headings")
        for key, title, width in (("#0", "Mapped value", 300), ("category", "Category", 120),
                                  ("left", "Selected plan", 150), ("right", "Comparison plan", 150),
                                  ("delta", "A − B comparison delta", 170)):
            if key == "#0":
                self.compare_tree.heading(key, text=title)
                self.compare_tree.column(key, width=width, minwidth=180)
            else:
                self.compare_tree.heading(key, text=title)
                self.compare_tree.column(key, width=width, minwidth=100, stretch=key == "category")
        self.compare_tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self.compare_page, orient="vertical", command=self.compare_tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.compare_tree.configure(yscrollcommand=scroll.set)
        self.compare_note = tk.StringVar(self.compare_page,
            value="Comparison deltas are plain differences between planned values, not game formulas.")
        ttk.Label(self.compare_page, textvariable=self.compare_note,
                  style="Muted.TLabel", wraplength=900).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _build_record_compare_page(self):
        self.record_page = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.record_page, text="Compare Weapons")
        self.record_page.columnconfigure(0, weight=1)
        self.record_page.rowconfigure(1, weight=1)
        controls = ttk.Frame(self.record_page)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text="Weapon A").pack(side="left", padx=(0, 6))
        self.record_left = ttk.Combobox(controls, state="readonly", width=28)
        self.record_left.pack(side="left", padx=(0, 12))
        ttk.Label(controls, text="Weapon B").pack(side="left", padx=(0, 6))
        self.record_right = ttk.Combobox(controls, state="readonly", width=28)
        self.record_right.pack(side="left")
        self.record_left.bind("<<ComboboxSelected>>", self._choose_record_comparison)
        self.record_right.bind("<<ComboboxSelected>>", self._choose_record_comparison)
        self.record_tree = ttk.Treeview(self.record_page,
            columns=("left", "right", "delta", "evidence"), show="tree headings")
        for key, title, width in (("#0", "Stored weapon field", 240),
                                  ("left", "Weapon A", 150), ("right", "Weapon B", 150),
                                  ("delta", "Stored A − B", 130), ("evidence", "Mapping evidence", 330)):
            self.record_tree.heading(key, text=title)
            self.record_tree.column(key, width=width, minwidth=90,
                                    stretch=key in ("#0", "evidence"))
        self.record_tree.grid(row=1, column=0, sticky="nsew")
        self.record_note = tk.StringVar(self.record_page,
            value="This view compares values from the existing weapon dashboard. It does not model combat damage.")
        ttk.Label(self.record_page, textvariable=self.record_note,
                  style="Muted.TLabel", wraplength=900).grid(row=2, column=0, sticky="w", pady=(8, 0))
        self._record_options = ()

    def set_record_options(self, record_options):
        """Refresh the available mapped record pairs without changing plans."""
        normalized = []
        for item in record_options or ():
            if isinstance(item, Mapping):
                key, label = item.get("id"), item.get("label")
            else:
                try:
                    key, label = item
                except (TypeError, ValueError):
                    continue
            if type(key) not in (str, int) or type(key) is bool or not isinstance(label, str):
                continue
            normalized.append((key, label))
        old = (self.record_left.get(), self.record_right.get())
        labels = [label for _key, label in normalized]
        self.record_left.configure(values=labels)
        self.record_right.configure(values=labels)
        self._record_options = tuple(normalized)
        for selector, previous, fallback in ((self.record_left, old[0], 0),
                                             (self.record_right, old[1], 1)):
            if previous in labels:
                selector.set(previous)
            elif len(labels) > fallback:
                selector.current(fallback)
            else:
                selector.set("")
        self._render_record_comparison()

    def _choose_record_comparison(self, _event=None):
        self._render_record_comparison()

    def _render_record_comparison(self):
        self.record_tree.delete(*self.record_tree.get_children())
        left_label, right_label = self.record_left.get(), self.record_right.get()
        left_id = next((key for key, label in self._record_options if label == left_label), None)
        right_id = next((key for key, label in self._record_options if label == right_label), None)
        if left_id is None or right_id is None or left_id == right_id:
            return
        try:
            left, right = self.on_compare_records(left_id, right_id)
        except Exception as error:
            self.record_note.set("Mapped weapon comparison is unavailable: " + str(error))
            return
        left_metrics = {metric.id: metric for metric in left.metrics}
        right_metrics = {metric.id: metric for metric in right.metrics}
        ordered = list(left_metrics)
        ordered.extend(key for key in right_metrics if key not in left_metrics)
        for index, key in enumerate(ordered):
            left_metric, right_metric = left_metrics.get(key), right_metrics.get(key)
            label = (left_metric or right_metric).label
            left_value = left_metric.value if left_metric else "—"
            right_value = right_metric.value if right_metric else "—"
            notes = [metric.note for metric in (left_metric, right_metric)
                     if metric is not None and metric.note]
            evidence = " · ".join(dict.fromkeys(notes)) or "Existing mapped weapon dashboard field."
            self.record_tree.insert("", "end", iid=f"record:{index}", text=label,
                                    values=(left_value, right_value,
                                            _display_delta(left_value, right_value), evidence))
        self.record_note.set(
            "Values come from the existing mapped weapon dashboard. Stored A − B is a generic comparison, "
            "not a combat-damage formula.")

    def _plan_label(self, plan, index):
        label = self.field_metadata.get(plan.character_id, {}).get("character_label", "")
        character = label or f"Character {plan.character_id}"
        base = f"{character} · {plan.name}"
        if sum(1 for item in self._plans if item.name == plan.name and item.character_id == plan.character_id) > 1:
            base += f" (#{index + 1})"
        return base

    def _refresh(self):
        labels = tuple(self._plan_label(plan, index) for index, plan in enumerate(self._plans))
        self.plan_selector.configure(values=labels)
        if not self._plans:
            self._selected_index = None
            self.plan_choice.set("")
            self.plan_selector.configure(state="disabled")
            self.duplicate_button.configure(state="disabled")
            self.add_field_button.configure(state="disabled")
            self.export_button.configure(state="disabled")
            self.stage_button.configure(state="disabled")
            self._render_empty()
            return
        self.plan_selector.configure(state="readonly")
        if self._selected_index is None or not 0 <= self._selected_index < len(self._plans):
            self._selected_index = 0
        self.plan_choice.set(labels[self._selected_index])
        self.duplicate_button.configure(state="normal")
        self.add_field_button.configure(state="normal" if self.field_metadata else "disabled")
        self.export_button.configure(state="normal")
        self.stage_button.configure(state="normal" if self.on_stage is not None else "disabled")
        self._refresh_current()
        self._refresh_stats()
        self._refresh_comparison_choices()

    def _render_empty(self):
        self.plan_tree.delete(*self.plan_tree.get_children())
        self.stats_tree.delete(*self.stats_tree.get_children())
        self.compare_tree.delete(*self.compare_tree.get_children())
        self._row_keys.clear()
        self.status.set("No mapped build is available. Open a supported save copy or import a reusable build preset.")
        self.stats_note.set("Verified stats appear when a game provider supplies mapped read-only rows.")
        self.compare_note.set("Import or duplicate a mapped build to create a plan for comparison.")
        self.compare_selector.configure(values=(), state="disabled")
        self.compare_choice.set("")

    @property
    def selected_plan(self):
        if self._selected_index is None:
            return None
        return self._plans[self._selected_index]

    def _choose_plan(self, _event=None):
        selected = self.plan_selector.current()
        if selected < 0 or selected >= len(self._plans):
            return
        self._selected_index = selected
        self._comparison_index = None
        self._refresh()

    def _meta(self, key):
        return self.field_metadata.get(key, {})

    def _choice_display(self, key, value):
        for native, label in _choice_pairs(self._meta(key)):
            if type(native) is type(value) and native == value:
                return f'{label} ({_display(value)})'
        return _display(value)

    def _refresh_current(self):
        plan = self.selected_plan
        if plan is None:
            return
        self.plan_tree.delete(*self.plan_tree.get_children())
        self._row_keys.clear()
        entries = []
        for field_id, value in plan.values.items():
            entries.append((field_id, "values", value))
        for slot_id, value in plan.equipment.items():
            entries.append((slot_id, "equipment", value))
        entries.sort(key=lambda item: (self._meta(item[0]).get("category", item[1]),
                                       self._meta(item[0]).get("label", item[0])))
        for index, (key, kind, value) in enumerate(entries):
            meta = self._meta(key)
            label = meta.get("label", key)
            category = str(meta.get("category", "equipment" if kind == "equipment" else "stat"))
            opened = meta.get("current_value", meta.get("opened_value", _NO_VALUE))
            evidence = meta.get("evidence", meta.get("source", ""))
            iid = f"plan:{index}"
            self.plan_tree.insert("", "end", iid=iid, text=str(label), values=(
                category, self._choice_display(key, opened),
                self._choice_display(key, value), str(evidence)))
            self._row_keys[iid] = (kind, key)
        if plan.notes:
            self.status.set(plan.notes)
        else:
            self.status.set(f"Planning {self._plan_label(plan, self._selected_index)}. No save data has changed.")
        self._refresh_comparison()

    def _refresh_stats(self):
        plan = self.selected_plan
        self.stats_tree.delete(*self.stats_tree.get_children())
        visible = []
        for row in self.verified_stats:
            identity = row.get("character_id")
            if identity is not None and str(identity) != plan.character_id:
                continue
            visible.append(row)
        for index, row in enumerate(visible):
            label = row.get("label", row.get("name", f"Verified stat {index + 1}"))
            value = row.get("value", row.get("display_value", "—"))
            evidence = row.get("evidence", row.get("source", ""))
            formula = row.get("formula")
            if formula:
                evidence = f"{evidence} · {formula}" if evidence else str(formula)
            self.stats_tree.insert("", "end", iid=f"stat:{index}", text=str(label),
                                   values=(str(value), str(evidence)))
        if visible:
            self.stats_note.set("These values are supplied by the game's verified mapping. The Workshop does not recompute formulas.")
        else:
            self.stats_note.set("No verified stat rows are available for this character in the selected profile.")

    def _refresh_comparison_choices(self):
        plan = self.selected_plan
        candidates = [(index, item) for index, item in enumerate(self._plans)
                      if index != self._selected_index
                      and (item.game_id, item.platform_id, item.character_id)
                      == (plan.game_id, plan.platform_id, plan.character_id)]
        self._comparison_choices = {self._plan_label(item, index): index for index, item in candidates}
        labels = tuple(self._comparison_choices)
        self.compare_selector.configure(values=labels, state="readonly" if labels else "disabled")
        if self._comparison_index not in {index for index, _ in candidates}:
            self._comparison_index = candidates[0][0] if candidates else None
        if self._comparison_index is None:
            self.compare_choice.set("")
            self.compare_note.set("Import another plan for this same game, platform, and character to compare.")
        else:
            label = next(label for label, index in self._comparison_choices.items()
                         if index == self._comparison_index)
            self.compare_choice.set(label)
            self._refresh_comparison()

    def _choose_comparison(self, _event=None):
        self._comparison_index = self._comparison_choices.get(self.compare_choice.get())
        self._refresh_comparison()

    def _refresh_comparison(self):
        self.compare_tree.delete(*self.compare_tree.get_children())
        plan = self.selected_plan
        if plan is None or self._comparison_index is None:
            return
        other = self._plans[self._comparison_index]
        labels = {}
        all_keys = sorted(set(plan.values) | set(other.values))
        numeric_deltas = {delta.field_id: delta for delta in plan_model.compare_build_plans(plan, other)}
        row = 0
        for field_id in all_keys:
            left = plan.values.get(field_id, _NO_VALUE)
            right = other.values.get(field_id, _NO_VALUE)
            delta = numeric_deltas.get(field_id)
            meta = self._meta(field_id)
            self.compare_tree.insert("", "end", iid=f"compare:{row}", text=meta.get("label", field_id),
                values=(meta.get("category", "stat"), self._choice_display(field_id, left),
                        self._choice_display(field_id, right),
                        _display(delta.delta) if delta else "—"))
            row += 1
        all_slots = sorted(set(plan.equipment) | set(other.equipment))
        for slot_id in all_slots:
            left = plan.equipment.get(slot_id, _NO_VALUE)
            right = other.equipment.get(slot_id, _NO_VALUE)
            if left == right:
                continue
            meta = self._meta(slot_id)
            self.compare_tree.insert("", "end", iid=f"compare:{row}", text=meta.get("label", slot_id),
                values=(meta.get("category", "equipment"), self._choice_display(slot_id, left),
                        self._choice_display(slot_id, right),
                        "Choice differs"))
            row += 1
        self.compare_note.set(
            "A − B is a generic planned-value difference, not a gameplay formula. "
            "Verified stat rows remain on the Verified Stats tab. Equipment rows show mapped choice differences."
        )

    def duplicate_plan(self):
        plan = self.selected_plan
        if plan is None:
            return False
        name = simpledialog.askstring("Duplicate Build Plan", "Name the planned build:",
                                      initialvalue=f"{plan.name} (planned)", parent=self.winfo_toplevel())
        if name is None:
            return False
        try:
            duplicate = replace(plan, name=name)
        except Exception as error:
            messagebox.showerror("Cannot Create Build Plan", str(error), parent=self.winfo_toplevel())
            return False
        self._plans.append(duplicate)
        self._selected_index = len(self._plans) - 1
        self._comparison_index = None
        self._refresh()
        return True

    def _edit_selected_cell(self, event=None):
        if self.plan_tree.identify("region", event.x, event.y) != "cell":
            return
        if self.plan_tree.identify_column(event.x) != "#3":
            return
        iid = self.plan_tree.identify_row(event.y)
        entry = self._row_keys.get(iid)
        if entry:
            self.edit_value(*entry)

    def edit_value(self, kind, key, raw_text=None):
        """Edit one in-memory value; actual game validation remains in editor."""
        plan = self.selected_plan
        if plan is None:
            return False
        values = dict(plan.values if kind == "values" else plan.equipment)
        original = values.get(key, _NO_VALUE)
        meta = self._meta(key)
        choices = _choice_pairs(meta)
        if choices:
            self._choice_dialog(kind, key, original, choices)
            return True
        if raw_text is None:
            raw_text = simpledialog.askstring("Plan Build Value", "Planned value:",
                initialvalue="" if original is _NO_VALUE else _display(original),
                parent=self.winfo_toplevel())
            if raw_text is None:
                return False
        try:
            value = _parse_scalar(raw_text, original, meta.get("value_type"))
            values[key] = value
            updated = replace(plan, **{"values" if kind == "values" else "equipment": values})
        except Exception as error:
            messagebox.showerror("Invalid Planned Value", str(error), parent=self.winfo_toplevel())
            return False
        self._plans[self._selected_index] = updated
        self._refresh()
        self.tabs.select(self.build_page)
        return True

    def _choice_dialog(self, kind, key, original, choices):
        window = tk.Toplevel(self.winfo_toplevel())
        window.title("Choose Mapped Equipment")
        window.transient(self.winfo_toplevel())
        window.resizable(True, False)
        ttk.Label(window, text="Choose a value supplied by this game's verified mapping.",
                  padding=(14, 12, 14, 8)).pack(anchor="w")
        selector = ttk.Combobox(window, state="readonly", width=48,
                                values=tuple(label for _, label in choices))
        selector.pack(fill="x", padx=14)
        chosen = next((index for index, (value, _) in enumerate(choices) if value == original), 0)
        selector.current(chosen)
        footer = ttk.Frame(window, padding=14)
        footer.pack(fill="x")
        def accept():
            index = selector.current()
            if index < 0:
                return
            self._store_value(kind, key, choices[index][0])
            window.destroy()
        ttk.Button(footer, text="Use Choice", command=accept,
                   style="Primary.TButton").pack(side="right")
        ttk.Button(footer, text="Cancel", command=window.destroy).pack(side="right", padx=8)
        selector.focus_set()
        window.bind("<Return>", lambda _event: accept())
        window.bind("<Escape>", lambda _event: window.destroy())

    def _store_value(self, kind, key, value):
        plan = self.selected_plan
        values = dict(plan.values if kind == "values" else plan.equipment)
        values[key] = value
        try:
            updated = replace(plan, **{"values" if kind == "values" else "equipment": values})
        except Exception as error:
            messagebox.showerror("Invalid Planned Value", str(error), parent=self.winfo_toplevel())
            return False
        self._plans[self._selected_index] = updated
        self._refresh()
        self.tabs.select(self.build_page)
        return True

    def add_field(self):
        plan = self.selected_plan
        if plan is None:
            return False
        taken = set(plan.values) | set(plan.equipment)
        candidates = []
        for key, meta in self.field_metadata.items():
            if key in taken:
                continue
            owner = meta.get("character_id")
            if owner is not None and str(owner) != plan.character_id:
                continue
            candidates.append((key, meta))
        if not candidates:
            self.status.set("No additional mapped fields are available for this character.")
            return False

        window = tk.Toplevel(self.winfo_toplevel())
        window.title("Add Mapped Build Field")
        window.transient(self.winfo_toplevel())
        window.resizable(True, False)
        window.columnconfigure(0, weight=1)
        ttk.Label(window, text="Select a field mapped for this character.",
                  padding=(14, 12, 14, 6)).grid(row=0, column=0, sticky="w")
        labels = tuple(f"{meta.get('label', key)} · {meta.get('category', 'stat')}" for key, meta in candidates)
        selector = ttk.Combobox(window, state="readonly", values=labels, width=52)
        selector.grid(row=1, column=0, sticky="ew", padx=14)
        selector.current(0)
        ttk.Label(window, text="New planned value", padding=(14, 10, 14, 4)).grid(row=2, column=0, sticky="w")
        entry = ttk.Entry(window)
        entry.grid(row=3, column=0, sticky="ew", padx=14)
        preview = ttk.Label(window, style="Muted.TLabel")
        preview.grid(row=4, column=0, sticky="w", padx=14, pady=(4, 0))
        def update_field(_event=None):
            index = selector.current()
            if index < 0:
                return
            _key, meta = candidates[index]
            opened = meta.get("current_value", meta.get("opened_value", _NO_VALUE))
            choices = _choice_pairs(meta)
            if choices:
                preview.configure(text=f"{len(choices)} mapped choices are available; choose one after adding.")
            elif opened is not _NO_VALUE:
                entry.delete(0, "end")
                entry.insert(0, _display(opened))
                preview.configure(text=f"Opened type: {type(opened).__name__}; final bounds are checked by the editor.")
            else:
                preview.configure(text="Enter a scalar target; the editor validates it when staged.")
        selector.bind("<<ComboboxSelected>>", update_field)
        update_field()
        footer = ttk.Frame(window, padding=14)
        footer.grid(row=5, column=0, sticky="ew")
        def accept():
            index = selector.current()
            if index < 0:
                return
            key, meta = candidates[index]
            opened = meta.get("current_value", meta.get("opened_value", _NO_VALUE))
            if _choice_pairs(meta):
                # Add the opened choice only if it is a known, provider-mapped
                # option; otherwise ask the user to add another stat field.
                choice_values = [value for value, _ in _choice_pairs(meta)]
                if opened not in choice_values:
                    messagebox.showerror("Choose a Mapped Value",
                        "This equipment selection has no known opened choice. No option was invented.",
                        parent=window)
                    return
                value = opened
            else:
                try:
                    value = _parse_scalar(entry.get(), opened, meta.get("value_type"))
                except Exception as error:
                    messagebox.showerror("Invalid Planned Value", str(error), parent=window)
                    return
            category = str(meta.get("category", "stat"))
            if is_equipment_field(category, key):
                slot = meta.get("slot_id", key)
                result = self._store_value("equipment", str(slot), value)
            else:
                result = self._store_value("values", key, value)
            if result:
                window.destroy()
        ttk.Button(footer, text="Add to Plan", command=accept,
                   style="Primary.TButton").pack(side="right")
        ttk.Button(footer, text="Cancel", command=window.destroy).pack(side="right", padx=8)
        entry.focus_set()
        window.bind("<Return>", lambda _event: accept())
        window.bind("<Escape>", lambda _event: window.destroy())
        return True

    def import_plan(self):
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(),
            title="Import Character & Weapon Build", filetypes=[
                ("Character and weapon build presets", "*.build.json"), ("JSON files", "*.json")])
        if not path:
            return False
        return self.load_plan(path)

    def load_plan(self, path):
        try:
            plan = plan_model.load_plan(path)
            if (plan.game_id, plan.platform_id) != (self.game_id, self.platform_id):
                raise SaveError("This build preset belongs to a different game or platform.")
        except Exception as error:
            messagebox.showerror("Cannot Import Build", str(error), parent=self.winfo_toplevel())
            return False
        self._plans.append(plan)
        self._selected_index = len(self._plans) - 1
        self._comparison_index = None
        self._refresh()
        self.status.set("Build preset imported for planning only. Review its fields before staging.")
        return True

    def export_plan(self):
        plan = self.selected_plan
        if plan is None:
            return False
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(),
            title="Export Character & Weapon Build", initialfile=f"{plan.name}.build.json",
            defaultextension=".build.json", filetypes=[
                ("Character and weapon build presets", "*.build.json")])
        if not path:
            return False
        return self.save_plan(path)

    def save_plan(self, path):
        plan = self.selected_plan
        if plan is None:
            return False
        try:
            result = plan_model.save_plan(plan, path)
        except Exception as error:
            messagebox.showerror("Cannot Export Build", str(error), parent=self.winfo_toplevel())
            return False
        self.status.set(f"Build preset exported to {result}. No game save was written.")
        return True

    def stage_plan(self):
        plan = self.selected_plan
        if plan is None or self.on_stage is None:
            return False
        try:
            if (plan.game_id, plan.platform_id) != (self.game_id, self.platform_id):
                raise SaveError("This plan does not match the open editor profile.")
            # The host is responsible for calling its existing validated
            # staging API. The Workshop never writes or serializes save bytes.
            accepted = self.on_stage(plan)
            if accepted is False:
                return False
        except Exception as error:
            messagebox.showerror("Cannot Stage Build Plan", str(error), parent=self.winfo_toplevel())
            return False
        self.status.set("Plan values were sent to the editor's staging workflow. Review Changes before saving a separate copy.")
        return True

    def set_provider_data(self, plans, field_metadata=None, verified_stats=(), record_options=()):
        """Refresh native snapshots while retaining plans the user changed/imported."""
        current = self.selected_plan
        old_provider_ids = self._provider_plan_ids
        custom = [plan for plan in self._plans if id(plan) not in old_provider_ids]
        normalized = []
        for plan in plans:
            item = self._coerce_plan(plan)
            if (item.game_id, item.platform_id) == (self.game_id, self.platform_id):
                normalized.append(item)
        self._plans = normalized + custom
        self._provider_plan_ids = {id(plan) for plan in normalized}
        self.field_metadata = {
            key: _as_mapping(value) for key, value in (field_metadata or {}).items()
        }
        self.verified_stats = tuple(_as_mapping(row) for row in (verified_stats or ()))
        if self.on_compare_records is not None:
            self.set_record_options(record_options)
        self._selected_index = None
        if current is not None:
            current_was_provider = id(current) in old_provider_ids
            if current_was_provider:
                self._selected_index = next((index for index, item in enumerate(self._plans)
                    if id(item) in self._provider_plan_ids
                    and (item.character_id, item.name) == (current.character_id, current.name)), None)
            else:
                self._selected_index = next((index for index, item in enumerate(self._plans)
                    if item is current), None)
        self._comparison_index = None
        self._refresh()

    def set_plans(self, plans):
        """Replace provider plans after a host refresh, preserving selection."""
        current = self.selected_plan
        normalized = [self._coerce_plan(plan) for plan in plans]
        self._plans = [plan for plan in normalized
                       if (plan.game_id, plan.platform_id) == (self.game_id, self.platform_id)]
        self._provider_plan_ids = {id(plan) for plan in self._plans}
        if current is not None:
            match = next((i for i, plan in enumerate(self._plans)
                          if (plan.character_id, plan.name) == (current.character_id, current.name)), None)
            self._selected_index = match
        else:
            self._selected_index = None
        self._comparison_index = None
        self._refresh()


def _display_delta(left, right):
    """Compare exact integer display strings without inferring a game formula."""
    def parse(value):
        if not isinstance(value, str):
            return None
        text = value.strip()
        if "," in text:
            negative = text.startswith("-")
            digits = text[1:] if negative else text
            groups = digits.split(",")
            if not groups[0].isdecimal() or any(
                    not group.isdecimal() or len(group) != 3 for group in groups[1:]):
                return None
            text = ("-" if negative else "") + "".join(groups)
        if text not in ("", "-") and text.lstrip("-").isdecimal():
            return int(text)
        return None
    left_number, right_number = parse(left), parse(right)
    return str(left_number - right_number) if left_number is not None and right_number is not None else "—"


__all__ = ["BuildWorkshopView"]

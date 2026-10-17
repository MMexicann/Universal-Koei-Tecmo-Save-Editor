"""Read-only, bounded graphical presentation of verified progression snapshots.

The view never reads a save or stages an edit. Field links reveal mapped fields
in the existing editor; report export uses the same immutable display snapshot.
"""

import tkinter as tk
from tkinter import font, ttk

from koei_editor.shared.appearance import THEMES, ui_font


PAGE_SIZE = 24
CARD_METRICS = 6
DETAIL_PAGE_SIZE = 6
RANGE_FILTERS = ("All records", "With verified ranges", "Ranges in progress",
                 "Ranges complete", "No verified range")
SORT_ORDERS = ("Original order", "Name A–Z", "First range: high to low",
               "First range: low to high")


def _ranges(card):
    return tuple(metric for metric in card.metrics if metric.fraction is not None)


def _matches_range_filter(card, choice):
    ranges = _ranges(card)
    if choice == "With verified ranges":
        return bool(ranges)
    if choice == "Ranges in progress":
        return any(metric.current < metric.total for metric in ranges)
    if choice == "Ranges complete":
        return bool(ranges) and all(metric.current == metric.total for metric in ranges)
    if choice == "No verified range":
        return not ranges
    return True


def _progress(metric):
    """Return a drawable ratio only for an explicit, internally valid range."""
    return metric.fraction


def _value(metric):
    value = str(metric.value)
    return f"{value} {metric.unit}" if metric.unit else value


def _percentage(metric):
    ratio = _progress(metric)
    if metric.current == metric.total:
        return "100%"
    if metric.current == 0:
        return "0%"
    rounded = f"{ratio * 100:.2f}"
    if rounded == "100.00":
        return "<100%"
    if rounded == "0.00":
        return "<0.01%"
    return rounded.rstrip("0").rstrip(".") + "%"


class ProgressionView(ttk.Frame):
    """Searchable section cards with a keyboard-accessible record inspector."""

    def __init__(self, master, dashboard, on_navigate=None, theme=None):
        super().__init__(master)
        self.on_navigate = on_navigate
        self.dashboard = dashboard
        self.palette = THEMES["Light"]
        self._font_family = ui_font(self)
        self._fonts = {
            "title": font.Font(self, family=self._font_family, size=18, weight="bold"),
            "card": font.Font(self, family=self._font_family, size=12, weight="bold"),
            "body": font.Font(self, family=self._font_family, size=10),
            "small": font.Font(self, family=self._font_family, size=9),
            "number": font.Font(self, family=self._font_family, size=11, weight="bold"),
        }
        self.search = tk.StringVar(self)
        self.section = tk.StringVar(self, "All sections")
        self.range_filter = tk.StringVar(self, RANGE_FILTERS[0])
        self.sort_order = tk.StringVar(self, SORT_ORDERS[0])
        self._pinned_card = None
        self._filters_expanded = False
        self._overview_counts = (0, 0, 0, 0)
        self.card_choice = tk.StringVar(self)
        self.result_text = tk.StringVar(self)
        self.detail_title = tk.StringVar(self, "Select a card to explore its mapped fields")
        self.detail_note = tk.StringVar(self)
        self.page_text = tk.StringVar(self)
        self.detail_page_text = tk.StringVar(self)
        self._page = 0
        self._detail_page = 0
        self._details_expanded = False
        self._detail_layout_signature = None
        self._selected_id = None
        self._visible_cards = ()
        self._filtered_cards = ()
        self._card_choices = ()
        self._metric_buttons = []
        self._metric_value_entries = []
        self._resize_job = None
        self._search_job = None
        self._columns = 1
        self._section_buttons = []
        self._context_note = dashboard.note
        self._build()
        self.search.trace_add("write", self._search_changed)
        self.section.trace_add("write", self._section_changed)
        self.range_filter.trace_add("write", self._section_changed)
        self.sort_order.trace_add("write", self._section_changed)
        self.bind("<Destroy>", self._destroyed, add="+")
        self.bind("<Configure>", self._resize, add="+")
        self.apply_theme(theme)
        self.set_dashboard(dashboard)

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.heading = tk.Frame(self, padx=20, pady=15)
        self.heading.grid(row=0, column=0, sticky="ew")
        self.heading.columnconfigure(0, weight=1)
        self.title_label = tk.Label(self.heading, anchor="w", font=self._fonts["title"])
        self.title_label.grid(row=0, column=0, sticky="ew")
        self.badge = tk.Label(self.heading, text="OPENED SAVE  /  READ ONLY", padx=10,
                              pady=6, font=(self._font_family, 8, "bold"))
        self.badge.grid(row=0, column=1, padx=(12, 0))
        self.note_label = tk.Label(self.heading, anchor="w", justify="left",
                                   font=self._fonts["small"], wraplength=900)
        self.note_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.overview = tk.Canvas(self.heading, height=58, highlightthickness=0)
        self.overview._decorative = True
        self.overview.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.overview.bind("<Configure>", lambda _event: self._draw_overview())

        toolbar = self.toolbar = ttk.Frame(self, padding=(20, 8))
        toolbar.grid(row=1, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)
        ttk.Label(toolbar, text="Search", style="Muted.TLabel").grid(row=0, column=0, padx=(0, 8))
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<Escape>", lambda _event: self.search.set(""))
        ttk.Button(toolbar, text="Clear", width=6, command=lambda: self.search.set("")).grid(row=0, column=2, padx=(6, 16))
        self.selector_label = ttk.Label(toolbar, text="Select record", style="Muted.TLabel")
        self.selector_label.grid(row=0, column=3, padx=(0, 8))
        self.filter_button = ttk.Button(toolbar, text="Filters / report", command=self._toggle_filters)
        self.card_selector = ttk.Combobox(toolbar, state="readonly", width=28,
                                         textvariable=self.card_choice)
        self.card_selector.grid(row=0, column=4, sticky="ew")
        self.card_selector.bind("<<ComboboxSelected>>", self._choose_card)
        self.filterbar = ttk.Frame(toolbar)
        self.filterbar.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        self.filterbar.columnconfigure(4, weight=1)
        ttk.Label(self.filterbar, text="Show", style="Muted.TLabel").grid(row=0, column=0, padx=(0, 6))
        self.range_selector = ttk.Combobox(self.filterbar, state="readonly", width=22,
                                          textvariable=self.range_filter, values=RANGE_FILTERS)
        self.range_selector.grid(row=0, column=1)
        ttk.Label(self.filterbar, text="Sort", style="Muted.TLabel").grid(row=0, column=2, padx=(14, 6))
        self.sort_selector = ttk.Combobox(self.filterbar, state="readonly", width=26,
                                         textvariable=self.sort_order, values=SORT_ORDERS)
        self.sort_selector.grid(row=0, column=3)
        self.report_button = ttk.Button(self.filterbar, text="HTML report…", command=self._export_report)
        self.report_button.grid(row=0, column=5, padx=(12, 0), sticky="e")

        body = ttk.Frame(self, padding=(20, 0, 20, 0))
        body.grid(row=2, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        rail_frame = ttk.Frame(body, width=178)
        rail_frame.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        rail_frame.grid_propagate(False)
        rail_frame.columnconfigure(0, weight=1)
        rail_frame.rowconfigure(0, weight=1)
        self.rail = tk.Canvas(rail_frame, width=156, highlightthickness=0)
        self.rail._decorative = True
        self.rail.grid(row=0, column=0, sticky="nsew")
        rail_scroll = ttk.Scrollbar(rail_frame, orient="vertical", command=self.rail.yview)
        rail_scroll.grid(row=0, column=1, sticky="ns")
        self.rail.configure(yscrollcommand=rail_scroll.set)
        self.rail_content = tk.Frame(self.rail)
        self.rail_content.columnconfigure(0, weight=1)
        self._rail_window = self.rail.create_window(0, 0, anchor="nw", window=self.rail_content)
        self.rail_content.bind("<Configure>", lambda _event: self.rail.configure(scrollregion=self.rail.bbox("all")))
        self.rail.bind("<Configure>", lambda event: self.rail.itemconfigure(self._rail_window, width=event.width))
        self.rail.bind("<MouseWheel>", lambda event: self._rail_wheel(event))
        self.rail.bind("<Button-4>", lambda _event: self.rail.yview_scroll(-3, "units"))
        self.rail.bind("<Button-5>", lambda _event: self.rail.yview_scroll(3, "units"))
        self.grid_frame = ttk.Frame(body)
        self.grid_frame.grid(row=0, column=1, sticky="nsew")
        self.grid_frame.columnconfigure(0, weight=1)
        self.grid_frame.rowconfigure(1, weight=1)
        self.results = ttk.Label(self.grid_frame, textvariable=self.result_text,
                                 style="Muted.TLabel")
        self.results.grid(row=0, column=0, columnspan=2, sticky="w", pady=(2, 9))
        self.canvas = tk.Canvas(self.grid_frame, highlightthickness=0, takefocus=True)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas._decorative = True
        self.scrollbar = ttk.Scrollbar(self.grid_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=1, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda _event: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda _event: self.canvas.yview_scroll(3, "units"))
        self.canvas.bind("<Up>", lambda _event: self._move_selection(-self._columns))
        self.canvas.bind("<Down>", lambda _event: self._move_selection(self._columns))
        self.canvas.bind("<Left>", lambda _event: self._move_selection(-1))
        self.canvas.bind("<Right>", lambda _event: self._move_selection(1))
        self.canvas.bind("<Return>", lambda _event: self._toggle_details())
        self.canvas.bind("<Home>", lambda _event: self._move_selection(-PAGE_SIZE))
        self.canvas.bind("<End>", lambda _event: self._move_selection(PAGE_SIZE))
        pager = self.pager = ttk.Frame(self.grid_frame, padding=(0, 6))
        pager.grid(row=2, column=0, columnspan=2, sticky="ew")
        pager.columnconfigure(1, weight=1)
        self.previous = ttk.Button(pager, text="Previous", command=lambda: self._change_page(-1))
        self.previous.grid(row=0, column=0)
        ttk.Label(pager, textvariable=self.page_text, anchor="center", style="Muted.TLabel").grid(row=0, column=1, sticky="ew")
        self.next = ttk.Button(pager, text="Next", command=lambda: self._change_page(1))
        self.next.grid(row=0, column=2)

        self.detail = tk.Frame(self, padx=20, pady=10)
        self.detail.grid(row=3, column=0, sticky="ew")
        self.detail.columnconfigure(0, weight=1)
        self.detail_heading = tk.Label(self.detail, textvariable=self.detail_title,
                                        anchor="w", font=self._fonts["card"])
        self.detail_heading.grid(row=0, column=0, sticky="ew")
        self.detail_toggle = ttk.Button(self.detail, text="Show fields", command=self._toggle_details)
        self.detail_toggle.grid(row=0, column=2, sticky="e", padx=(8, 0))
        self.compare_button = ttk.Button(self.detail, text="Pin comparison", command=self._pin_comparison)
        self.compare_button.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.detail_note_label = tk.Label(self.detail, textvariable=self.detail_note,
                                          anchor="w", justify="left", font=self._fonts["small"],
                                          wraplength=950)
        self.detail_note_label.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(3, 5))
        self.detail_metrics = ttk.Frame(self.detail)
        self.detail_metrics.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.detail_metrics.columnconfigure((0, 1), weight=1)
        detail_pager = ttk.Frame(self.detail)
        detail_pager.grid(row=3, column=0, columnspan=3, sticky="e", pady=(5, 0))
        self.detail_previous = ttk.Button(detail_pager, text="Previous fields",
                                           command=lambda: self._change_detail_page(-1))
        self.detail_previous.grid(row=0, column=0)
        ttk.Label(detail_pager, textvariable=self.detail_page_text,
                  style="Muted.TLabel").grid(row=0, column=1, padx=10)
        self.detail_next = ttk.Button(detail_pager, text="Next fields",
                                       command=lambda: self._change_detail_page(1))
        self.detail_next.grid(row=0, column=2)
        self._detail_pager = detail_pager
        self._show_details()

    def set_dashboard(self, dashboard):
        """Replace a frozen opened-save snapshot, retaining compatible UI choices."""
        self.dashboard = dashboard
        if self._pinned_card is not None:
            self._pinned_card = next((card for section in dashboard.sections
                                      for card in section.cards if card.id == self._pinned_card.id), None)
        self.title_label.configure(text=dashboard.title)
        self.report_button.configure(state="normal" if any(section.cards for section in dashboard.sections) else "disabled")
        self.note_label.configure(text=dashboard.note)
        section_ids = {section.id for section in dashboard.sections}
        if self.section.get() not in section_ids:
            self.section.set("All sections")
        for child in self.rail_content.winfo_children():
            child.destroy()
        self._section_buttons = []
        self._add_section_button("All sections", "Overview", sum(len(s.cards) for s in dashboard.sections))
        for section in dashboard.sections:
            self._add_section_button(section.id, section.title, len(section.cards))
        self._filter()

    def _add_section_button(self, section_id, title, count):
        button = tk.Button(self.rail_content, text=f"{title}\n{count:,} records", anchor="w",
                           justify="left", relief="flat", borderwidth=0, padx=12,
                           pady=12, font=(self._font_family, 10), wraplength=130,
                           command=lambda: self.section.set(section_id))
        button.grid(row=len(self._section_buttons), column=0, sticky="ew", pady=(0, 5))
        button.bind("<MouseWheel>", self._rail_wheel)
        button.bind("<Button-4>", lambda _event: self.rail.yview_scroll(-3, "units"))
        button.bind("<Button-5>", lambda _event: self.rail.yview_scroll(3, "units"))
        button.bind("<FocusIn>", lambda _event, target=button: self._reveal_section(target))
        self._section_buttons.append((section_id, button))

    def _search_changed(self, *_args):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(100, self._search_now)

    def _search_now(self):
        self._search_job = None
        self._page = 0
        self._filter()

    def _section_changed(self, *_args):
        self._page = 0
        self._filter()

    def _filter(self):
        tokens = self.search.get().casefold().split()
        selected = self.section.get()
        section_note = next((section.note for section in self.dashboard.sections
                             if section.id == selected), "")
        self._context_note = "\n".join(note for note in (self.dashboard.note, section_note) if note)
        self.note_label.configure(text=("Read only · " if self.winfo_height() < 560 else "") + self._context_note)
        cards = []
        for section in self.dashboard.sections:
            if selected not in ("All sections", section.id):
                continue
            for card in section.cards:
                haystack = " ".join((card.title, card.subtitle, card.search_text,
                                     *(str(m.label) + " " + _value(m) for m in card.metrics))).casefold()
                if all(token in haystack for token in tokens) and _matches_range_filter(card, self.range_filter.get()):
                    cards.append(card)
        order = self.sort_order.get()
        if order == "Name A–Z":
            cards.sort(key=lambda card: card.title.casefold())
        elif order in SORT_ORDERS[2:]:
            # Unknown ranges always stay last. Fractions are used only when a
            # presentation supplies an explicit, valid mechanic denominator.
            reverse = order == SORT_ORDERS[2]
            def range_key(card):
                ranges = _ranges(card)
                return (not bool(ranges), (-1 if reverse else 1) * (ranges[0].fraction if ranges else 0))
            cards.sort(key=range_key)
        self._filtered_cards = tuple(cards)
        ranges = tuple(metric for card in cards for metric in _ranges(card))
        self._overview_counts = (len(cards), sum(len(card.metrics) for card in cards),
                                 len(ranges), sum(metric.current == metric.total for metric in ranges))
        self._draw_overview()
        self._page = min(self._page, max(0, (len(cards) - 1) // PAGE_SIZE))
        selected_index = next((i for i, card in enumerate(cards) if card.id == self._selected_id), None)
        if selected_index is None:
            self._selected_id = cards[0].id if cards else None
            self._detail_page = 0
            self._page = 0
        else:
            self._page = selected_index // PAGE_SIZE
        self._render()
        self._render_details()

    def _render(self):
        cards = self._filtered_cards
        self._visible_cards = cards[self._page * PAGE_SIZE:(self._page + 1) * PAGE_SIZE]
        # Selector mirrors the bounded page: thousands of equipment records do
        # not create an unbounded native combobox popup on Windows.
        self._card_choices = self._visible_cards
        labels = tuple(f"{self._page * PAGE_SIZE + i + 1}. {card.title}" for i, card in enumerate(self._card_choices))
        self.card_selector.configure(values=labels, state="readonly" if labels else "disabled")
        chosen = next((i for i, card in enumerate(self._card_choices) if card.id == self._selected_id), None)
        self.card_choice.set(labels[chosen] if chosen is not None else "")
        count = len(cards)
        self.result_text.set(f"{count:,} mapped records  ·  Select to inspect  ·  ↗ opens the existing editor")
        pages = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page_text.set(f"Page {self._page + 1} of {pages}" if count else "No matching records")
        self.previous.configure(state="normal" if self._page else "disabled")
        self.next.configure(state="normal" if self._page + 1 < pages else "disabled")
        self._style_sections()
        self._draw_cards()

    def _draw_cards(self):
        canvas, p = self.canvas, self.palette
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        self._columns = max(1, min(4, (width + 14) // 290))
        gap = 14
        card_width = (width - gap * (self._columns - 1) - 4) / self._columns
        if not self._visible_cards:
            canvas.create_text(width / 2, 64, text="No mapped records to show", fill=p["text"], font=self._fonts["card"])
            canvas.create_text(width / 2, 94, text="Try another section or clear your search.", fill=p["muted"], font=self._fonts["body"])
            canvas.configure(scrollregion=(0, 0, width, 150))
            return
        y = 2
        for row_start in range(0, len(self._visible_cards), self._columns):
            row = self._visible_cards[row_start:row_start + self._columns]
            height = max(self._card_height(card) for card in row)
            for col, card in enumerate(row):
                self._draw_card(card, 2 + col * (card_width + gap), y, card_width, height)
            y += height + gap
        canvas.configure(scrollregion=(0, 0, width, y))

    @staticmethod
    def _card_height(card):
        # A compact two-column stat grid keeps inventories scannable while the
        # paged inspector retains every exact opened value and field link.
        metrics = card.metrics[:CARD_METRICS]
        rows = [metrics[index:index + 2] for index in range(0, len(metrics), 2)]
        return 112 + sum(74 if any(_progress(m) is not None for m in row) else 56
                         for row in rows) + (24 if len(card.metrics) > CARD_METRICS else 0)

    def _rounded_box(self, canvas, x, y, box_width, height, radius=12, **options):
        points = (x + radius, y, x + box_width - radius, y, x + box_width, y,
                  x + box_width, y + radius, x + box_width, y + height - radius,
                  x + box_width, y + height, x + box_width - radius, y + height,
                  x + radius, y + height, x, y + height, x, y + height - radius,
                  x, y + radius, x, y)
        return canvas.create_polygon(points, smooth=True, splinesteps=12, **options)

    def _draw_card(self, card, x, y, width, height):
        canvas, p = self.canvas, self.palette
        tag = "card:" + card.id
        selected = card.id == self._selected_id
        self._rounded_box(canvas, x, y + 3, width, height, fill=p["hover"], outline="", tags=(tag,))
        self._rounded_box(canvas, x, y, width, height, fill=p["surface"],
                          outline=p["tab_text"] if selected else p["border"],
                          width=2 if selected else 1, tags=(tag, "surface:" + card.id))
        ranges = _ranges(card)
        # The ring always describes one named metric; it is never an overall
        # completion estimate or an average of unrelated mechanic ranges.
        hero = ranges[0] if ranges else None
        canvas.create_oval(x + 14, y + 16, x + 58, y + 60, fill=p["hover"], outline="", tags=(tag,))
        if hero is not None:
            canvas.create_oval(x + 15, y + 17, x + 57, y + 59, outline=p["border"], width=3, tags=(tag,))
            if hero.fraction:
                canvas.create_arc(x + 15, y + 17, x + 57, y + 59, start=90,
                                  extent=-359.99 * hero.fraction, style="arc", width=3,
                                  outline=p["tab_text"], tags=(tag, "range-ring"))
        initials = "".join(part[0] for part in card.title.split()[:2]).upper() or "·"
        canvas.create_text(x + 36, y + 38, text=initials, fill=p["tab_text"],
                           font=self._fonts["card"], tags=(tag,))
        canvas.create_text(x + 70, y + 29, text=self._elide(card.title, width - 86, "card"),
                           anchor="w", fill=p["text"], font=self._fonts["card"], tags=(tag,))
        canvas.create_text(x + 70, y + 49, text=self._elide(card.subtitle, width - 86, "small"),
                           anchor="w", fill=p["muted"], font=self._fonts["small"], tags=(tag,))
        status = (f"{hero.label} · {_percentage(hero)}" if hero else "Opened values · no verified range")
        canvas.create_text(x + 16, y + 80, text=self._elide(status, width - 32, "small"),
                           anchor="w", fill=p["tab_text"] if hero else p["muted"],
                           font=self._fonts["small"], tags=(tag,))
        metric_y = y + 104
        metrics = card.metrics[:CARD_METRICS]
        cell_width = (width - 42) / 2
        for row_start in range(0, len(metrics), 2):
            row = metrics[row_start:row_start + 2]
            row_height = 74 if any(_progress(m) is not None for m in row) else 56
            for column, metric in enumerate(row):
                index = row_start + column
                left = x + 16 + column * (cell_width + 10)
                link_tag = f"{tag}:metric:{index}"
                linked = metric.field_id is not None and self.on_navigate is not None
                canvas.create_text(left, metric_y, text=self._elide(metric.label, cell_width, "small"),
                                   anchor="w", fill=p["muted"], font=self._fonts["small"], tags=(tag,))
                canvas.create_text(left, metric_y + 21, text=self._elide(_value(metric), cell_width, "number"),
                                   anchor="w", fill=p["tab_text"] if linked else p["text"],
                                   font=self._fonts["number"], tags=(tag, link_tag))
                ratio = _progress(metric)
                if ratio is not None:
                    canvas.create_rectangle(left, metric_y + 35, left + cell_width, metric_y + 39,
                                            fill=p["hover"], outline="", tags=(tag, "progress-track"))
                    if ratio:
                        canvas.create_rectangle(left, metric_y + 35, left + cell_width * ratio,
                                                metric_y + 39, fill=p["tab_text"], outline="", tags=(tag, "progress-fill"))
                    # Keep full counts accessible in the inspector; the canvas
                    # retains the exact annotation even when space is tight.
                    annotation = f"{metric.current:,} / {metric.total:,}  ·  {_percentage(metric)}"
                    canvas.create_text(left, metric_y + 52, text=annotation,
                                       anchor="w", width=cell_width, fill=p["muted"],
                                       font=self._fonts["small"], tags=(tag, "range-annotation"))
                if linked:
                    canvas.tag_bind(link_tag, "<Button-1>", lambda _event, m=metric: self._navigate(m))
                    canvas.tag_bind(link_tag, "<Enter>", lambda _event: canvas.configure(cursor="hand2"))
                    canvas.tag_bind(link_tag, "<Leave>", lambda _event: canvas.configure(cursor=""))
            metric_y += row_height
        if len(card.metrics) > CARD_METRICS:
            canvas.create_text(x + 16, y + height - 17, text=f"Explore all {len(card.metrics):,} fields  →",
                               anchor="w", fill=p["tab_text"], font=self._fonts["small"], tags=(tag,))
        canvas.tag_bind(tag, "<Button-1>", lambda _event, card_id=card.id: self._card_clicked(card_id))
        canvas.tag_bind(tag, "<Enter>", lambda _event, card_id=card.id: self._hover_card(card_id, True))
        canvas.tag_bind(tag, "<Leave>", lambda _event, card_id=card.id: self._hover_card(card_id, False))

    def _draw_overview(self):
        canvas, p = self.overview, self.palette
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        counts = self._overview_counts
        captions = ("MATCHING RECORDS", "OPENED VALUES", "VERIFIED RANGES", "RANGES AT TARGET")
        for index, (count, caption) in enumerate(zip(counts, captions)):
            x = index * width / 4
            if index:
                canvas.create_line(x - 12, 7, x - 12, 47, fill=p["border"])
            canvas.create_text(x, 15, anchor="w", text=f"{count:,}",
                               font=self._fonts["title"], fill=p["text"])
            canvas.create_text(x, 41, anchor="w", text=caption,
                               font=(self._font_family, 8), fill=p["muted"])

    def _toggle_filters(self):
        self._filters_expanded = not self._filters_expanded
        self._resize()

    def _export_report(self):
        from koei_editor.shared.progression_report import show_report_dialog
        show_report_dialog(self, self.dashboard, theme=self.palette)

    def _pin_comparison(self):
        if self._pinned_card is not None:
            self._pinned_card = None
        else:
            self._pinned_card = next((card for card in self._filtered_cards
                                      if card.id == self._selected_id), None)
            self._details_expanded = True
        self._render_details()

    def _hover_card(self, card_id, active):
        if card_id != self._selected_id:
            self.canvas.itemconfigure("surface:" + card_id,
                                      outline=self.palette["tab_text"] if active else self.palette["border"])

    def _reveal_card(self, card_id):
        bounds = self.canvas.bbox("card:" + card_id)
        if bounds is None:
            return
        top = self.canvas.canvasy(0)
        bottom = top + self.canvas.winfo_height()
        _, y1, _, y2 = bounds
        region = self.canvas.cget("scrollregion").split()
        total = max(1, float(region[3]))
        if y1 < top or y2 - y1 > self.canvas.winfo_height():
            self.canvas.yview_moveto(max(0, y1 - 4) / total)
        elif y2 > bottom:
            self.canvas.yview_moveto((y2 - self.canvas.winfo_height() + 4) / total)

    def _card_clicked(self, card_id):
        self.canvas.focus_set()
        self.select_card(card_id)

    def _elide(self, value, width, face):
        text = str(value).replace("\n", " ")
        measure = self._fonts[face].measure
        if measure(text) <= width:
            return text
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if measure(text[:middle] + "…") <= width:
                low = middle
            else:
                high = middle - 1
        return text[:low] + "…"

    def select_card(self, card_id):
        """Select a visible search result without invoking an editor action."""
        index = next((i for i, card in enumerate(self._filtered_cards) if card.id == card_id), None)
        if index is None:
            return False
        self._selected_id = card_id
        self._detail_page = 0
        self._page = index // PAGE_SIZE
        self._render()
        self._render_details()
        self._reveal_card(card_id)
        return True

    def _choose_card(self, _event=None):
        index = self.card_selector.current()
        if 0 <= index < len(self._card_choices):
            self.select_card(self._card_choices[index].id)

    def _move_selection(self, delta):
        if self._filtered_cards:
            index = next((i for i, card in enumerate(self._filtered_cards) if card.id == self._selected_id), 0)
            target = max(0, min(len(self._filtered_cards) - 1, index + delta))
            self.select_card(self._filtered_cards[target].id)
        return "break"

    def _change_page(self, delta):
        target = self._page + delta
        if 0 <= target <= (len(self._filtered_cards) - 1) // PAGE_SIZE:
            self._page = target
            self._selected_id = self._filtered_cards[target * PAGE_SIZE].id
            self._detail_page = 0
            self.canvas.yview_moveto(0)
            self._render()
            self._render_details()

    def _render_details(self):
        for child in self.detail_metrics.winfo_children():
            child.destroy()
        self._metric_buttons = []
        self._metric_value_entries = []
        self._comparison_entries = []
        columns, page_size, wrap = self._detail_layout()
        self._detail_layout_signature = (columns, page_size, wrap)
        self.detail_metrics.columnconfigure(1, weight=1 if columns == 2 else 0)
        card = next((card for card in self._filtered_cards if card.id == self._selected_id), None)
        if card is None:
            self.detail_title.set("Select a card to explore its mapped fields")
            self.detail_note.set("Only verified information in the opened save is shown.")
            self._detail_pager.grid_remove()
            self.detail_toggle.configure(state="disabled")
            self.compare_button.configure(state="normal" if self._pinned_card else "disabled",
                                          text="Clear comparison" if self._pinned_card else "Pin comparison")
            return
        self.detail_toggle.configure(state="normal")
        self.compare_button.configure(state="normal", text="Clear comparison" if self._pinned_card else "Pin comparison")
        self._update_detail_title()
        note = card.subtitle or "Field links reveal the original editor; dashboard controls never change the save."
        if self._pinned_card is not None:
            if self.winfo_height() < 420:
                note = f"Reference: {self._pinned_card.title} · Unique labels and units must match."
            else:
                note += f"  ·  Comparing with {self._pinned_card.title}. Only matching metric labels and units are paired."
        self.detail_note.set(note)
        pages = max(1, (len(card.metrics) + page_size - 1) // page_size)
        self._detail_page = min(self._detail_page, pages - 1)
        metrics = card.metrics[self._detail_page * page_size:(self._detail_page + 1) * page_size]
        for index, metric in enumerate(metrics):
            frame = ttk.Frame(self.detail_metrics, padding=(0, 2, 14, 2))
            frame.grid(row=index // columns, column=index % columns, sticky="ew")
            frame.columnconfigure(0, weight=1)
            caption = metric.label + (f" · {metric.note}" if metric.note else "")
            ratio = _progress(metric)
            if ratio is not None:
                caption += f"  ({metric.current:,} / {metric.total:,})"
            ttk.Label(frame, text=caption, style="Muted.TLabel", wraplength=wrap).grid(row=0, column=0, sticky="w")
            entry = ttk.Entry(frame, width=18)
            entry.insert(0, _value(metric))
            entry.state(["readonly"])
            entry.grid(row=0, column=1, sticky="e", padx=(6, 0))
            self._metric_value_entries.append(entry)
            if self._pinned_card is not None:
                candidates = [m for m in self._pinned_card.metrics
                              if m.label == metric.label and m.unit == metric.unit]
                # Ambiguous duplicate labels never imply a matched identity.
                unique_current = sum(m.label == metric.label and m.unit == metric.unit for m in card.metrics) == 1
                baseline = candidates[0] if len(candidates) == 1 and unique_current else None
                text = ("Reference: " + _value(baseline)) if baseline else "Reference: no unique matching metric"
                reference = ttk.Entry(frame, width=18)
                reference.insert(0, text)
                reference.state(["readonly"])
                if self.winfo_height() < 420:
                    reference.grid(row=0, column=3, sticky="e", padx=(6, 0))
                else:
                    reference.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(3, 2))
                self._comparison_entries.append(reference)
            if metric.field_id is not None and self.on_navigate is not None:
                button = ttk.Button(frame, text="↗", width=3, command=lambda m=metric: self._navigate(m))
                button.grid(row=0, column=2, sticky="e", padx=(4, 0))
                self._metric_buttons.append((metric.field_id, button))
        if pages > 1:
            self._detail_pager.grid()
        else:
            self._detail_pager.grid_remove()
        self.detail_page_text.set(f"Fields {self._detail_page + 1} / {pages}")
        self.detail_previous.configure(state="normal" if self._detail_page else "disabled")
        self.detail_next.configure(state="normal" if self._detail_page + 1 < pages else "disabled")
        self._show_details()

    def _toggle_details(self):
        self._details_expanded = not self._details_expanded
        self._show_details()

    def _show_details(self):
        self.detail_toggle.configure(text="Hide fields" if self._details_expanded else "Show fields")
        if self._details_expanded:
            if self._pinned_card is not None and self.winfo_height() < 420:
                self.detail_note_label.grid_remove()
            else:
                self.detail_note_label.grid()
            self.detail_metrics.grid()
            card = next((card for card in self._filtered_cards if card.id == self._selected_id), None)
            if card is not None and len(card.metrics) > self._detail_layout()[1]:
                self._detail_pager.grid()
        else:
            self.detail_note_label.grid_remove()
            self.detail_metrics.grid_remove()
            self._detail_pager.grid_remove()

    def _change_detail_page(self, delta):
        self._detail_page = max(0, self._detail_page + delta)
        self._render_details()

    def _navigate(self, metric):
        if metric.field_id is not None and self.on_navigate is not None:
            self.on_navigate(metric.field_id)
        return "break"

    def _resize(self, _event=None):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after_idle(self._redraw)

    def _redraw(self):
        self._resize_job = None
        self.note_label.configure(wraplength=max(300, self.winfo_width() - 50))
        self.detail_note_label.configure(wraplength=max(300, self.winfo_width() - 50))
        self._update_detail_title()
        if self._detail_layout_signature != self._detail_layout():
            self._render_details()
        compact = self.winfo_width() < 760
        short = self.winfo_height() < 560
        self.heading.configure(pady=4 if short else 15)
        self.toolbar.configure(padding=(20, 2 if short else 8))
        self.detail.configure(pady=3 if short else 10)
        self.pager.configure(padding=(0, 0 if short else 6))
        self.note_label.grid_configure(pady=0 if short else (6, 0))
        if short:
            self.title_label.grid_remove()
            self.badge.grid_remove()
            self.note_label.configure(text="Read only · " + self._context_note)
        else:
            self.title_label.grid()
            self.badge.grid()
            self.badge.grid_configure(row=1 if compact else 0, column=1, sticky="e")
            self.note_label.configure(text=self._context_note)
        if compact:
            self.note_label.grid_configure(row=1 if short else 2)
            self.selector_label.grid_configure(row=1, column=0, pady=(6, 0), sticky="w")
            self.card_selector.grid_configure(row=1, column=1, columnspan=2, pady=(6, 0), sticky="ew")
        else:
            self.note_label.grid_configure(row=1)
            self.selector_label.grid_configure(row=0, column=3, pady=0)
            self.card_selector.grid_configure(row=0, column=4, columnspan=1, pady=0)
        if self.winfo_height() < 620 or compact:
            self.overview.grid_remove()
        else:
            self.overview.grid()
        self.filterbar.grid_configure(row=2 if compact else 1)
        if compact:
            self.report_button.grid_configure(row=1, column=3, pady=(5, 0))
            self.range_selector.configure(width=19)
            self.sort_selector.configure(width=22)
        else:
            self.report_button.grid_configure(row=0, column=5, pady=0)
            self.range_selector.configure(width=22)
            self.sort_selector.configure(width=26)
        if short:
            self.selector_label.grid_remove()
            self.filter_button.grid(row=1 if compact else 0, column=0 if compact else 3,
                                    padx=(0, 8), pady=(6, 0) if compact else 0)
            if self._filters_expanded:
                self.filterbar.grid()
            else:
                self.filterbar.grid_remove()
        else:
            self.filter_button.grid_remove()
            self.selector_label.grid()
            self.filterbar.grid()
        self._draw_overview()
        self._draw_cards()

    def _update_detail_title(self):
        card = next((card for card in self._filtered_cards if card.id == self._selected_id), None)
        title = card.title if card is not None else "Select a card to explore its mapped fields"
        if card is not None and self._pinned_card is not None and self.winfo_height() < 420:
            title += " / " + self._pinned_card.title
        self.detail_title.set(self._elide(title, max(80, self.winfo_width() - 340), "card"))

    def _detail_layout(self):
        width = max(300, self.winfo_width())
        tiny_comparison = self._pinned_card is not None and self.winfo_height() < 420
        columns = 2 if width >= 760 and not tiny_comparison else 1
        compact_detail = self.winfo_height() < (620 if self._pinned_card is not None else 460)
        page_size = 1 if tiny_comparison else 2 if compact_detail else DETAIL_PAGE_SIZE
        entry_space = 410 if tiny_comparison else 230
        wrap = max(80, ((width - 40) // columns - entry_space) // 20 * 20)
        return columns, page_size, wrap

    def _wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _rail_wheel(self, event):
        if event.delta:
            self.rail.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _reveal_section(self, target):
        top = self.rail.canvasy(0)
        bottom = top + self.rail.winfo_height()
        y, height = target.winfo_y(), target.winfo_height()
        total = max(1, self.rail_content.winfo_height())
        if y < top:
            self.rail.yview_moveto(y / total)
        elif y + height > bottom:
            self.rail.yview_moveto(max(0, (y + height - self.rail.winfo_height()) / total))

    def _style_sections(self):
        p = self.palette
        for section_id, button in self._section_buttons:
            active = self.section.get() == section_id
            button.configure(background=p["surface"] if active else p["background"],
                             foreground=p["tab_text"] if active else p["muted"],
                             activebackground=p["hover"], activeforeground=p["text"],
                             highlightbackground=p["border"], highlightcolor=p["tab_text"])

    def apply_theme(self, theme=None):
        """Repaint vectors and native labels without changing selection or data."""
        if isinstance(theme, dict):
            self.palette = theme
        elif theme is not None:
            self.palette = THEMES[theme]
        p = self.palette
        for widget in (self.heading, self.detail):
            widget.configure(background=p["surface"])
        self.rail.configure(background=p["background"])
        self.rail_content.configure(background=p["background"])
        self.canvas.configure(background=p["background"])
        self.overview.configure(background=p["surface"])
        self._draw_overview()
        for widget in (self.title_label, self.detail_heading):
            widget.configure(background=p["surface"], foreground=p["text"])
        for widget in (self.note_label, self.detail_note_label):
            widget.configure(background=p["surface"], foreground=p["muted"])
        self.badge.configure(background=p["hover"], foreground=p["tab_text"])
        self._style_sections()
        self._draw_cards()

    def _destroyed(self, event):
        if event.widget is self:
            for job in (self._resize_job, self._search_job):
                if job is not None:
                    self.after_cancel(job)
            self._resize_job = self._search_job = None

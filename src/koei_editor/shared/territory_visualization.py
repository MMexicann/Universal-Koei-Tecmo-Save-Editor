"""Read-only record cards for verified scalar inspection tables.

The view consumes existing data-only ``InspectionTable`` projections. It does
not read saves, infer relationships or geographic positions, or provide edits.
"""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from koei_editor.shared.appearance import THEMES


@dataclass(frozen=True)
class RecordCardData:
    title: str
    values: tuple


@dataclass(frozen=True)
class TableViewData:
    title: str
    note: str
    columns: tuple
    rows: tuple


def _format_value(value):
    if type(value) is int:
        return f'{value:,}'
    if type(value) is float:
        return f'{value:,.2f}'.rstrip('0').rstrip('.')
    if value is None:
        return '—'
    return str(value)


def project_tables(tables):
    """Convert typed inspection tables to immutable display-only records.

    Empty or missing table collections return an empty tuple. Every supplied
    table is rendered generically from its title, note, columns, and row cells;
    no field label or value is interpreted as a game relationship.
    """
    if tables is None:
        return ()
    if not isinstance(tables, tuple):
        try:
            tables = tuple(tables)
        except TypeError:
            return ()
    result = []
    for table in tables:
        if table is None:
            continue
        title = getattr(table, 'title', None)
        columns = getattr(table, 'columns', None)
        rows = getattr(table, 'rows', None)
        note = getattr(table, 'note', '')
        if not isinstance(title, str) or not isinstance(columns, tuple) or not isinstance(rows, tuple):
            continue
        if not all(isinstance(column, str) for column in columns):
            raise ValueError('InspectionTable column labels must be text.')
        for row in rows:
            if not isinstance(row, tuple) or len(row) != len(columns):
                raise ValueError('Every InspectionTable row must match its columns.')
        result.append(TableViewData(title, note if isinstance(note, str) else '', columns, rows))
    return tuple(result)


def project_table_page(table, page, page_size=24):
    """Project only one bounded page to card data, even for large tables."""
    if not isinstance(table, TableViewData):
        raise TypeError('A projected InspectionTable is required.')
    if type(page) is not int or page < 0 or type(page_size) is not int or page_size < 1:
        raise ValueError('Page and page size must be non-negative/positive whole numbers.')
    start = page * page_size
    cards = []
    for index, row in enumerate(table.rows[start:start + page_size], start + 1):
        values = tuple((label, _format_value(value)) for label, value in zip(table.columns, row))
        cards.append(RecordCardData(f'Record {index}', values))
    return tuple(cards)


class TerritoryOverview(ttk.Frame):
    """Display arbitrary ``InspectionTable`` rows as a paged card grid."""

    def __init__(self, master, theme='Light', *, columns=3, **kwargs):
        super().__init__(master, **kwargs)
        if type(columns) is not int or columns < 1:
            raise ValueError('The card column count must be a positive whole number.')
        self.card_columns = columns
        self.page_size = 24
        self._theme = theme
        self._tables = ()
        self._selected_table = 0
        self._page = 0
        self.title = ttk.Label(self, text='Scenario and territory records', style='Section.TLabel')
        self.title.grid(row=0, column=0, sticky='w', padx=10, pady=(8, 0))
        self.note = ttk.Label(self, text=(
            'Read-only record view. Cards show the supplied columns and values without inferring '
            'geographic positions, ownership, army, or scenario relationships.'),
            style='Muted.TLabel', wraplength=900)
        self.note.grid(row=1, column=0, columnspan=2, sticky='w', padx=10, pady=(2, 8))
        navigation = ttk.Frame(self, padding=(10, 2))
        navigation.grid(row=2, column=0, columnspan=2, sticky='ew')
        ttk.Label(navigation, text='Table').pack(side='left', padx=(0, 6))
        self.table_selector = ttk.Combobox(navigation, state='readonly', width=38)
        self.table_selector.pack(side='left', fill='x', expand=True)
        self.table_selector.bind('<<ComboboxSelected>>', self._select_table)
        self.previous_button = ttk.Button(navigation, text='Previous', command=lambda: self._move_page(-1))
        self.previous_button.pack(side='left', padx=(8, 0))
        self.next_button = ttk.Button(navigation, text='Next', command=lambda: self._move_page(1))
        self.next_button.pack(side='left', padx=(6, 0))
        self.page_status = tk.StringVar(self, value='No table selected')
        ttk.Label(navigation, textvariable=self.page_status, style='Muted.TLabel').pack(side='left', padx=8)
        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self._scrollbar = ttk.Scrollbar(self, orient='vertical', command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.grid(row=3, column=0, sticky='nsew')
        self._scrollbar.grid(row=3, column=1, sticky='ns')
        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)
        self._body = ttk.Frame(self._canvas, padding=8, style='RecordOverview.TFrame')
        self._body_window = self._canvas.create_window((0, 0), window=self._body, anchor='nw')
        self._body.bind('<Configure>', self._sync_scrollregion)
        self._canvas.bind('<Configure>', self._sync_body_width)
        self._bind_mousewheel(self._canvas)
        self.cards = ()
        self.sections = ()
        self.apply_theme(theme)
        self.set_tables(())

    def _sync_scrollregion(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))

    def _sync_body_width(self, event):
        self._canvas.itemconfigure(self._body_window, width=max(1, event.width))
        self._sync_scrollregion()

    def _bind_mousewheel(self, widget):
        # Widget-local handlers cover the embedded cards without capturing
        # wheel events from another editor, page or application workspace.
        widget.bind('<MouseWheel>', self._mousewheel)
        widget.bind('<Button-4>', self._mousewheel_linux)
        widget.bind('<Button-5>', self._mousewheel_linux)
        for child in widget.winfo_children():
            self._bind_mousewheel(child)

    def _finish_page(self):
        # Every direct child is newly created by _draw_page. Bind each new
        # subtree once; do not accumulate callbacks on the retained body.
        for child in self._body.winfo_children():
            self._bind_mousewheel(child)
        self._body.update_idletasks()
        self._sync_scrollregion()
        self._canvas.yview_moveto(0)

    def _mousewheel(self, event):
        if event.delta:
            self._canvas.yview_scroll(int(-event.delta / 120), 'units')
        return 'break'

    def _mousewheel_linux(self, event):
        self._canvas.yview_scroll(-1 if event.num == 4 else 1, 'units')
        return 'break'

    def _select_table(self, _event=None):
        selected = self.table_selector.current()
        if selected >= 0:
            self._selected_table = selected
            self._page = 0
            self._draw_page()

    def _move_page(self, amount):
        if not self._tables:
            return
        table = self._tables[self._selected_table]
        page_count = max(1, (len(table.rows) + self.page_size - 1) // self.page_size)
        self._page = min(max(0, self._page + amount), page_count - 1)
        self._draw_page()

    def _draw_page(self):
        for child in self._body.winfo_children():
            child.destroy()
        self.cards = ()
        if not self._tables:
            ttk.Label(self._body, text='Open a supported save copy to see its mapped record tables.',
                      style='Muted.TLabel').grid(row=0, column=0, sticky='w', padx=8, pady=8)
            self.page_status.set('No table selected')
            self.previous_button.configure(state='disabled')
            self.next_button.configure(state='disabled')
            self._finish_page()
            return False

        table = self._tables[self._selected_table]
        page_count = max(1, (len(table.rows) + self.page_size - 1) // self.page_size)
        self._page = min(self._page, page_count - 1)
        start = self._page * self.page_size
        end = min(start + self.page_size, len(table.rows))
        self.page_status.set(f'Page {self._page + 1} of {page_count} · records {start + 1}–{end}'
                             if table.rows else 'No records')
        self.previous_button.configure(state='normal' if self._page else 'disabled')
        self.next_button.configure(state='normal' if self._page + 1 < page_count else 'disabled')
        ttk.Label(self._body, text=table.title, style='Section.TLabel').grid(
            row=0, column=0, columnspan=self.card_columns, sticky='w', padx=5, pady=(0, 2))
        if table.note:
            ttk.Label(self._body, text=table.note, style='Muted.TLabel', wraplength=900).grid(
                row=1, column=0, columnspan=self.card_columns, sticky='w', padx=5, pady=(0, 6))
        if not table.rows:
            ttk.Label(self._body, text='No records in this table.', style='Muted.TLabel').grid(
                row=2, column=0, sticky='w', padx=8, pady=6)
            self._finish_page()
            return False

        cards = []
        for index, record in enumerate(project_table_page(table, self._page, self.page_size)):
            card = ttk.LabelFrame(self._body, text=record.title, padding=(10, 7))
            card.grid(row=2 + index // self.card_columns, column=index % self.card_columns,
                      sticky='nsew', padx=5, pady=5)
            for value_index, (label, value) in enumerate(record.values):
                ttk.Label(card, text=f'{label}:', style='Muted.TLabel').grid(
                    row=value_index, column=0, sticky='nw', padx=(0, 6), pady=1)
                ttk.Label(card, text=value, wraplength=220).grid(
                    row=value_index, column=1, sticky='nw', pady=1)
            card.columnconfigure(1, weight=1)
            cards.append(card)
        for index in range(self.card_columns):
            self._body.columnconfigure(index, weight=1, uniform='record-card')
        self.cards = tuple(cards)
        self._finish_page()
        return bool(cards)

    def set_tables(self, tables):
        """Set available tables and show the first bounded page of the first one."""
        projected = project_tables(tables)
        self._tables = projected
        self._selected_table = 0
        self._page = 0
        values = tuple(f'{index + 1}. {table.title} ({len(table.rows)} records)'
                       for index, table in enumerate(projected))
        self.table_selector.configure(values=values)
        self.table_selector.set(values[0] if values else '')
        self.sections = tuple(table.title for table in projected)
        return self._draw_page()

    def apply_theme(self, theme='Light'):
        """Apply a palette without changing the displayed records."""
        if theme not in THEMES:
            raise ValueError('Unsupported appearance.')
        self._theme = theme
        palette = THEMES[theme]
        self._canvas.configure(background=palette['background'])
        style = ttk.Style(self)
        style.configure('RecordOverview.TFrame', background=palette['background'])
        style.configure('Muted.TLabel', foreground=palette['muted'])
        self.title.configure(foreground=palette['text'])
        self.note.configure(foreground=palette['muted'])
        self._sync_scrollregion()
        return theme

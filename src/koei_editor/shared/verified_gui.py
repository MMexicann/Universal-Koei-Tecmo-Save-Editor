"""Shared scalar save editor with retained independent sessions."""
import csv
import io
import json
import os
import stat
import unicodedata
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from koei_editor.shared.appearance import Appearance, THEMES
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.preferences import normalize_pins
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.scalar_presentation import ScalarPresentation
from koei_editor.shared.table_tools import attach_sorting, sort_table, copy_selected
from koei_editor.shared.experimental_limits import (
    EXPERIMENTAL_WARNING, above_supported, experimental_maximum, experimental_operation)
import koei_editor.shared.verified_editor as backend


def _review_csv(records):
    """Encode a frozen scalar review as safe, typed UTF-8 spreadsheet rows."""
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(('game_id', 'source_sha256', 'experimental', 'field_id',
                     'group', 'record', 'label', 'opened_type', 'opened_json',
                     'pending_type', 'pending_json'))
    def text_cell(value):
        # Spreadsheet applications may ignore leading spaces/control characters
        # before interpreting a label as a formula. Only labels are escaped;
        # native values use reversible JSON, with genuine integers unquoted.
        start = 0
        while start < len(value) and (value[start].isspace()
                or unicodedata.category(value[start]) in ('Cc', 'Cf')):
            start += 1
        return "'" + value if value[start:].startswith(('=', '+', '-', '@')) else value
    for values in records:
        line = [text_cell(str(value)) for value in values[:8]]
        line += [values[8] if type(values[8]) is int else json.dumps(values[8], ensure_ascii=False),
                 text_cell(values[9]),
                 values[10] if type(values[10]) is int else json.dumps(values[10], ensure_ascii=False)]
        writer.writerow(line)
    return stream.getvalue().encode('utf-8-sig')


def _export_review(data, destination):
    """Create a report and verify its actual bounded bytes; never roll back files."""
    result = atomic_new(data, destination)
    descriptor = None
    try:
        # Frozen history does not require an unchanged source. Verify only the
        # actual new report, retaining any concurrently replaced output.
        # atomic_new returns a canonical path. A replacement must not select
        # a different baseline by resolving a newly introduced alias.
        checked = Path(result)
        def ordinary(info):
            return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and not (getattr(info, 'st_file_attributes', 0)
                             & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)))
        path_opened = checked.lstat()
        if not checked.is_absolute() or not ordinary(path_opened) or safe_path(checked) != checked:
            raise SaveError('The newly created change review is no longer an ordinary matching file.')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        descriptor = os.open(checked, flags)
        def identity(info):
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        opened = os.fstat(descriptor)
        # CPython Windows path stat preserves creation time as st_ctime,
        # while fstat can report FILE_BASIC_INFO.ChangeTime. Keep each full
        # token within its own API; bind the APIs with their common identity.
        if identity(opened)[:-1] != identity(path_opened)[:-1]:
            raise SaveError('The newly created change review changed before read-back.')
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or opened.st_size != len(data):
            raise SaveError('The newly created change review is no longer an ordinary matching file.')
        offset = 0
        while offset < len(data):
            block = os.read(descriptor, min(65536, len(data) - offset))
            if not block or block != data[offset:offset + len(block)]:
                raise SaveError('The newly created change review changed during read-back.')
            offset += len(block)
        if os.read(descriptor, 1) or identity(os.fstat(descriptor)) != identity(opened):
            raise SaveError('The newly created change review changed during read-back.')
        os.close(descriptor)
        descriptor = None
        final_path = checked.lstat()
        if (not ordinary(final_path) or safe_path(result) != checked
                or identity(final_path) != identity(path_opened)):
            raise SaveError('The newly created change review was replaced during read-back.')
    except Exception as error:
        raise SaveError('Change review verification did not finish after creation. '
                        'The file was retained; do not use it. Choose a new destination.\n\n'
                        + str(error)) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return result


class Editor(Appearance):
    game_id = None
    backend = backend
    save_extension = '.dat'
    subtitle = 'Windows PC save editor'
    limit_heading = 'Supported maximum'
    summary = ''
    presentation_type = ScalarPresentation

    def __init__(self, root, parent=None, theme='Light', on_theme=None):
        self.root, self.on_theme = root, on_theme
        self.adapter = BoundScalarAdapter(self.game_id, self.save_extension, self.backend)
        self.layout = self.adapter.get_format()
        self.presentation = self.presentation_type(self.backend, self.game_id)
        self.style = ttk.Style(root)
        self.theme_name = tk.StringVar(root, value=theme)
        self.document, self.backup = None, None
        self.changes, self.history = {}, []
        self.pinned_fields = frozenset()
        self._on_pins = None
        self.experimental_mode = tk.BooleanVar(root, value=False)
        self.apply_theme(theme)
        host = parent if parent is not None else root
        header = ttk.Frame(host, padding=(18, 10))
        header.pack(fill='x')
        ttk.Label(header, text=self.layout.title, font=(self.font_family, 18, 'bold')).pack(anchor='w')
        ttk.Label(header, text=self.subtitle, style='Muted.TLabel').pack(anchor='w', pady=(5, 0))
        summary = self.summary or 'Edit save values and review changes.'
        self.details_visible = tk.BooleanVar(root, value=False)
        self.details_toggle = ttk.Checkbutton(header, text='Show editing guide',
            variable=self.details_visible, command=self.toggle_details)
        self.details_toggle.pack(anchor='w', pady=(5, 0))
        self.details_label = ttk.Label(header, text=summary, wraplength=990)
        bar = ttk.Frame(host, padding=(18, 0))
        bar.pack(fill='x')
        ttk.Button(bar, text='Open Save Copy', command=self.open, style='Primary.TButton').pack(side='left')
        self.save_buttons = []
        for label, callback in (('Save As...', self.save_as), ('Backup Save', self.make_backup),
                                ('Review Changes', self.review), ('Undo', self.undo),
                                ('Edit Presets...', self.show_presets)):
            button = ttk.Button(bar, text=label, command=callback, state='disabled')
            button.pack(side='left', padx=(8, 0))
            self.save_buttons.append(button)
        ttk.Button(bar, text='Restore Backup...', command=self.restore).pack(side='left', padx=8)
        self.filename = tk.StringVar(root, value=f'Open a separate {self.save_extension or "save"} copy to begin.')
        ttk.Label(host, textvariable=self.filename, padding=(18, 8), wraplength=1000).pack(anchor='w')
        filter_bar = ttk.Frame(host, padding=(18, 0))
        filter_bar.pack(fill='x')
        ttk.Label(filter_bar, text='Find fields').pack(side='left', padx=(0, 8))
        self.search = tk.StringVar(root)
        self.search_entry = ttk.Entry(filter_bar, textvariable=self.search, width=40)
        self.search_entry.pack(side='left', fill='x', expand=True)
        self.search_entry.bind('<Escape>', lambda _event: self.clear_field_filters())
        ttk.Button(filter_bar, text='Clear', command=lambda: self.search.set('')).pack(side='left', padx=(8, 0))
        self.pending_only = tk.BooleanVar(root, value=False)
        ttk.Checkbutton(filter_bar, text='Pending only', variable=self.pending_only,
                        command=self.refresh).pack(side='left', padx=(12, 0))
        self.pinned_only = tk.BooleanVar(root, value=False)
        self.pin_count = tk.StringVar(root, value='Pinned only (0)')
        ttk.Checkbutton(filter_bar, textvariable=self.pin_count, variable=self.pinned_only,
                        command=self.refresh).pack(side='left', padx=(12, 0))
        navigation = ttk.Frame(host, padding=(18, 6, 18, 0))
        navigation.pack(fill='x')
        ttk.Label(navigation, text='Record').pack(side='left', padx=(0, 8))
        self.record = tk.StringVar(root, value='All records')
        self.record_selector = ttk.Combobox(navigation, textvariable=self.record,
                                           values=('All records',), state='readonly', width=35)
        self.record_selector.pack(side='left')
        self.record_selector.bind('<<ComboboxSelected>>', lambda _event: self.refresh())
        self._record_keys = {}
        self.field_count = tk.StringVar(root, value='No save opened.')
        ttk.Label(navigation, textvariable=self.field_count, style='Muted.TLabel').pack(side='left', padx=12)
        self.options_visible = tk.BooleanVar(root, value=False)
        self.options_toggle = ttk.Checkbutton(navigation, text='More options',
            variable=self.options_visible, command=self.toggle_options)
        self.options_toggle.pack(side='right')
        self.options_panel = ttk.Frame(host, padding=(18, 5))
        risk_bar = self.options_panel
        self.experimental_toggle = ttk.Checkbutton(
            risk_bar, text='Experimental: allow above supported limits',
            variable=self.experimental_mode, command=self.toggle_experimental, state='disabled')
        self.experimental_toggle.pack(side='left')
        self.limit_status = tk.StringVar(root, value='Supported limits apply. Max uses supported limits.')
        ttk.Label(risk_bar, textvariable=self.limit_status, wraplength=600).pack(side='left', padx=12)
        tools = ttk.Frame(host, padding=(18, 6))
        self.tools_bar = tools
        tools.pack(fill='x')
        self.group = tk.StringVar(root, value='All fields')
        groups = ('All fields',) + tuple(dict.fromkeys(field.group for field in self.layout.fields))
        groups += self.presentation.extra_groups
        select = ttk.Combobox(tools, textvariable=self.group, values=groups, state='readonly', width=18)
        self.group_selector = select
        # Category navigation lives beside the fields; keep the variable and
        # selector available to existing presentations and session callbacks.
        select.bind('<<ComboboxSelected>>', lambda _event: self.refresh())
        ttk.Label(tools, text='Value').pack(side='left', padx=(0, 8))
        self.value = tk.StringVar(root)
        value_frame = ttk.Frame(tools)
        value_frame.pack(side='left')
        self.value_entry = ttk.Entry(value_frame, textvariable=self.value, width=15)
        self.value_entry.pack(side='left')
        self.value_entry.bind('<Return>', lambda _event: self.apply_selected())
        self.choice_value = tk.StringVar(root)
        self.value_choice = ttk.Combobox(value_frame, textvariable=self.choice_value,
                                         width=30, state='readonly')
        self._choice_values = {}
        self.value_choice.bind('<<ComboboxSelected>>', self.selected_choice)
        self._choice_selection = ()
        self.edit_buttons = []
        for label, callback in (('Apply Selected', self.apply_selected),
                                ('Max Selected', self.max_selected), ('Max Visible Fields', self.max_visible)):
            button = ttk.Button(tools, text=label, command=callback, state='disabled')
            button.pack(side='left', padx=(8, 0))
            self.edit_buttons.append(button)
        inspect = ttk.Button(tools, text='Inspect Data', command=self.show_inspector, state='disabled')
        inspect.pack(side='right', padx=4)
        self.edit_buttons.append(inspect)
        self.choice_tools = ttk.Frame(host, padding=(18, 0, 18, 6))
        ttk.Label(self.choice_tools, text='Find choices').pack(side='left', padx=(0, 8))
        self.choice_search = tk.StringVar(root)
        self.choice_search_entry = ttk.Entry(self.choice_tools, textvariable=self.choice_search, width=38)
        self.choice_search_entry.pack(side='left', fill='x', expand=True)
        self.choice_search_entry.bind('<Escape>', self.clear_choice_search)
        ttk.Button(self.choice_tools, text='Clear', command=self.clear_choice_search).pack(side='left', padx=8)
        self.choice_count = tk.StringVar(root)
        ttk.Label(self.choice_tools, textvariable=self.choice_count, style='Muted.TLabel').pack(side='left')
        self.choice_search.trace_add('write', self.filter_choices)
        bulk = ttk.Frame(host, padding=(18, 0, 18, 6))
        self.bulk_bar = bulk
        bulk.pack(fill='x')
        for label, callback in (('Adjust Selected...', self.adjust_selected),
                                ('Revert Selected', self.revert_selected)):
            button = ttk.Button(bulk, text=label, command=callback, state='disabled')
            button.pack(side='left', padx=(0, 8))
            self.edit_buttons.append(button)
        ttk.Label(bulk, text='Adjust adds or subtracts from each value; Revert restores opened values.',
                  style='Muted.TLabel').pack(side='left')
        # Reserve field guidance and status before the expanding table.
        feedback = ttk.Frame(host)
        feedback.pack(side='bottom', fill='x')
        self.mode_banner = ttk.Label(feedback, textvariable=self.limit_status, wraplength=1000,
                                     padding=(18, 5), style='Muted.TLabel')
        self.selection_info = tk.StringVar(root, value='Select a record to inspect its values.')
        self.selection_label = ttk.Label(feedback, textvariable=self.selection_info, wraplength=1000,
                                         padding=(18, 6), style='Muted.TLabel')
        self.selection_label.pack(anchor='w')
        self.status = tk.StringVar(root, value='Copy-only editing. The opened file is never overwritten.')
        self.status_label = ttk.Label(feedback, textvariable=self.status, padding=(18, 8), wraplength=1000)
        self.status_label.pack(anchor='w')
        frame = ttk.Frame(host, padding=(18, 0))
        frame.pack(fill='both', expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        category_frame = ttk.Frame(frame, width=190)
        category_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        category_frame.rowconfigure(1, weight=1)
        category_frame.columnconfigure(0, weight=1)
        ttk.Label(category_frame, text='Categories (* pending)', style='Section.TLabel').grid(
            row=0, column=0, sticky='w', pady=(0, 5))
        self.categories = ttk.Treeview(category_frame, show='tree', selectmode='browse')
        self.categories.column('#0', width=180, minwidth=130, stretch=True)
        self.categories.grid(row=1, column=0, sticky='nsew')
        category_scroll = ttk.Scrollbar(category_frame, orient='vertical', command=self.categories.yview)
        category_scroll.grid(row=1, column=1, sticky='ns')
        self.categories.configure(yscrollcommand=category_scroll.set)
        self.categories.bind('<<TreeviewSelect>>', self.choose_category)
        pin_tools = ttk.Frame(category_frame)
        pin_tools.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        ttk.Button(pin_tools, text='Pin selected', command=self.pin_selected).pack(fill='x')
        ttk.Button(pin_tools, text='Unpin selected', command=self.unpin_selected).pack(fill='x', pady=(4, 0))
        self._category_groups = {}
        self._updating_categories = False
        table_frame = ttk.Frame(frame)
        table_frame.grid(row=0, column=1, sticky='nsew')
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.fields = ttk.Treeview(table_frame, columns=('slot', 'field', 'original', 'pending', 'limit', 'storage'),
                                  displaycolumns=('slot', 'field', 'original', 'pending', 'limit'),
                                  show='headings', selectmode='extended')
        for column, label, width in (('slot', 'Record', 145), ('field', 'Field', 255),
                                     ('original', 'Opened value', 130), ('pending', 'Pending value', 130),
                                     ('limit', self.limit_heading, 135), ('storage', 'Encoding limit', 140)):
            self.fields.heading(column, text=label)
            self.fields.column(column, width=width, minwidth=85)
        self.fields.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.fields.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self.field_horizontal_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.fields.xview)
        self.field_horizontal_scroll.grid(row=1, column=0, sticky='ew')
        self.fields.configure(yscrollcommand=scroll.set, xscrollcommand=self.field_horizontal_scroll.set)
        self.fields._pending_edits_style = True
        self._style_pending_rows()
        attach_sorting(self.fields)
        self.fields.bind('<<TreeviewSelect>>', self.selected)
        self.search.trace_add('write', lambda *_args: self.refresh())
        if parent is None:
            root.bind('<Control-f>', self.focus_field_search, add='+')
            root.title(self.layout.title + ' — Save Editor')
            root.protocol('WM_DELETE_WINDOW', self.close)

    def focus_field_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, 'end')
        return 'break'

    def toggle_details(self):
        if self.details_visible.get():
            self.details_label.pack(anchor='w', pady=(6, 0))
        else:
            self.details_label.pack_forget()

    def toggle_options(self):
        if self.options_visible.get():
            self.options_panel.pack(fill='x', before=self.tools_bar)
        else:
            self.options_panel.pack_forget()
        self.fields.configure(displaycolumns=('slot', 'field', 'original', 'pending', 'limit', 'storage')
                              if self.options_visible.get() else ('slot', 'field', 'original', 'pending', 'limit'))

    def clear_field_filters(self):
        self.group.set('All fields')
        self.record.set('All records')
        self.pending_only.set(False)
        self.pinned_only.set(False)
        self.search.set('')
        self.refresh()
        return 'break'

    def configure_pins(self, field_ids=(), on_change=None):
        """Inject exact-game navigation preferences without touching staged edits.

        The application supplies persistence; standalone editors can use the
        same callback. IDs absent from a particular save remain remembered.
        A false callback result reports optional settings storage failure.
        """
        pins = frozenset(normalize_pins(field_ids))
        if on_change is not None and not callable(on_change):
            raise TypeError('The pin persistence callback must be callable.')
        self.pinned_fields, self._on_pins = pins, on_change
        self.refresh()

    def _set_selected_pins(self, remove=False):
        if self.document is None:
            return
        selected = set(self.fields.selection()).intersection(self.fields.get_children())
        if not selected:
            self.status.set('Select visible fields to pin or unpin.')
            return
        candidate = self.pinned_fields.difference(selected) if remove else self.pinned_fields.union(selected)
        try:
            pins = frozenset(normalize_pins(candidate))
        except ValueError as error:
            messagebox.showerror('Cannot Pin Fields', str(error))
            return
        if pins == self.pinned_fields:
            return
        self.pinned_fields = pins
        stored = True
        if self._on_pins is not None:
            try:
                stored = self._on_pins(tuple(sorted(pins))) is not False
            except Exception:
                stored = False
        self.refresh()
        self.status.set('Field pins updated. Pins never change save values.' if stored else
                        'Pins updated for this session; preferences could not be saved.')

    def pin_selected(self):
        self._set_selected_pins()

    def unpin_selected(self):
        self._set_selected_pins(remove=True)

    def choose_category(self, _event=None):
        if self._updating_categories:
            return
        selected = self.categories.selection()
        if not selected:
            return
        group = self._category_groups.get(selected[0])
        if group is not None and group != self.group.get():
            self.group.set(group)
            self.record.set('All records')
            self.refresh()

    def _refresh_categories(self, fields):
        counts = {'All fields': len(fields)}
        pending = {'All fields': len(self.changes)}
        for field in fields:
            counts[field.group] = counts.get(field.group, 0) + 1
            pending[field.group] = pending.get(field.group, 0) + int(field.id in self.changes)
        self._updating_categories = True
        try:
            self._category_groups = {f'category_{index}': group for index, group in enumerate(counts)}
            keep = tuple(self._category_groups)
            obsolete = [key for key in self.categories.get_children() if key not in keep]
            if obsolete:
                self.categories.delete(*obsolete)
            for key, group in self._category_groups.items():
                text = f'{group} ({counts[group]:,})' + (f' *{pending[group]:,}' if pending.get(group) else '')
                if self.categories.exists(key):
                    self.categories.item(key, text=text)
                else:
                    self.categories.insert('', 'end', iid=key, text=text)
                if group == self.group.get():
                    self.categories.selection_set(key)
            self.category_counts = counts
        finally:
            self._updating_categories = False

    def _style_pending_rows(self):
        if hasattr(self, 'fields'):
            palette = THEMES[self.theme_name.get()]
            self.fields.tag_configure('pending', background=palette['hover'], foreground=palette['text'])

    def apply_theme(self, name):
        super().apply_theme(name)
        self._style_pending_rows()
        if self.on_theme is not None:
            self.on_theme(name)

    def dirty_ok(self):
        return not self.changes or messagebox.askyesno('Pending Edits', 'Discard pending edits and continue?')

    def update_filename(self, prefix):
        text = prefix + self.document.source.name + self.presentation.filename_suffix(self.document)
        self.filename.set(text)

    def open(self):
        path = filedialog.askopenfilename(title='Open a Separate Save Copy',
                                          filetypes=[(self.layout.title + ' save copy', '*' + self.save_extension)])
        if not path:
            return False
        return self.open_path(path)

    def open_path(self, path):
        """Open an explicitly selected copy through the normal guarded workflow."""
        try:
            document = self.adapter.read_save(path, self.game_id)
            if not self.dirty_ok():
                return False
            backup = self.adapter.backup(document)
        except Exception as error:
            messagebox.showerror('Cannot Open Save', str(error))
            return False
        self.document, self.backup = document, backup
        self.adapter = replace(self.adapter, experimental=False)
        self.experimental_mode.set(False)
        self.experimental_toggle.configure(state='normal')
        self.changes, self.history = {}, []
        self.record.set('All records')
        self.pending_only.set(False)
        self.choice_search.set('')
        self._choice_selection = ()
        for button in self.save_buttons + self.edit_buttons:
            button.configure(state='normal')
        self.update_filename('Opened copy: ')
        self.status.set('Opened save copy. Automatic backup: ' + backup.name)
        self.refresh()
        return True

    def show_presets(self):
        from koei_editor.shared.preset_gui import open_presets
        return open_presets(self)

    @property
    def experimental(self):
        return self.adapter.experimental

    @experimental_operation
    def refresh(self):
        selected = self.fields.selection()
        focus = self.fields.focus()
        position = self.fields.yview()[0]
        self.fields.delete(*self.fields.get_children())
        self.selection_info.set('Select a record to inspect its values.')
        self.value_choice.pack_forget()
        self.value_entry.pack(side='left')
        self._choice_values = {}
        if self.document is None:
            return
        fields = self.adapter.fields_for(self.document)
        available_pins = self.pinned_fields.intersection(field.id for field in fields)
        self.pin_count.set(f'Pinned only ({len(available_pins):,})')
        groups = ('All fields',) + tuple(dict.fromkeys(field.group for field in fields))
        self.group_selector.configure(values=groups)
        if self.group.get() not in groups:
            self.group.set('All fields')
        self._refresh_categories(fields)
        records = {}
        for field in fields:
            if self.group.get() in ('All fields', field.group):
                # Include the native group and slot even if two groups use the
                # same display name. Labels never act as editable identities.
                identity = (field.group, field.slot)
                records.setdefault(identity, f'{self.record_name(field)} · {field.group} [{field.slot}]')
        self._record_keys = {label: identity for identity, label in records.items()}
        self.record_selector.configure(values=('All records',) + tuple(self._record_keys))
        if self.record.get() not in self._record_keys:
            self.record.set('All records')
        record_key = self._record_keys.get(self.record.get())
        tokens = self.search.get().casefold().split()
        for field in fields:
            if self.group.get() not in ('All fields', field.group):
                continue
            if record_key is not None and (field.group, field.slot) != record_key:
                continue
            if self.pending_only.get() and field.id not in self.changes:
                continue
            if self.pinned_only.get() and field.id not in self.pinned_fields:
                continue
            original = field.value(self.document.payload)
            record = self.record_name(field)
            opened = self.display_value(field, original, changes={})
            pending = self.display_value(field, self.changes[field.id]) if field.id in self.changes else '-'
            searchable = (f'{field.label} {field.group} {record} {field.id} {opened} {pending} '
                          f'{original} {self.changes.get(field.id, "")}').casefold()
            if any(token not in searchable for token in tokens):
                continue
            self.fields.insert('', 'end', iid=field.id, tags=('pending',) if field.id in self.changes else (),
                               values=(record, ('* ' if field.id in self.pinned_fields else '') + field.label, opened, pending,
                                       f'{field.maximum:,} bytes' if getattr(field, 'kind', 'int') == 'text'
                                        else f'{field.maximum:,}',
                                        self.storage_display(field)))
        self.fields.selection_set([key for key in selected if self.fields.exists(key)])
        sort_table(self.fields)
        if focus and self.fields.exists(focus):
            self.fields.focus(focus)
        self.fields.yview_moveto(position)
        visible = self.fields.get_children()
        hidden = len(set(self.changes).difference(visible))
        self.field_count.set(f'{len(visible):,} visible fields · {len(self.changes):,} pending edits'
                             + (f' ({hidden:,} hidden)' if hidden else ''))
        count = len(self.experimental_changes())
        self.limit_status.set(
            f'EXPERIMENTAL: save or game may break. {count:,} pending edits above supported limits.'
            if self.experimental_mode.get() else 'Supported limits apply. Max uses supported limits.')
        if self.experimental_mode.get():
            self.mode_banner.pack(fill='x', before=self.selection_label)
        else:
            self.mode_banner.pack_forget()
        self.selected()

    def storage_display(self, field):
        maximum = experimental_maximum(field)
        return f'{maximum:,}' if maximum is not None else 'Required choices/structure'

    def experimental_changes(self):
        if self.document is None:
            return {}
        fields = self.adapter.field_map(self.document)
        return {key: value for key, value in self.changes.items()
                if key in fields and above_supported(fields[key], value)
                and value != fields[key].value(self.document.payload)}

    def toggle_experimental(self):
        requested = self.experimental_mode.get()
        if requested and not self.adapter.experimental:
            if not messagebox.askyesno('Experimental Editing Warning', EXPERIMENTAL_WARNING):
                self.experimental_mode.set(False)
                return
        candidate = replace(self.adapter, experimental=requested)
        try:
            if self.document is not None:
                candidate.changed_payload(self.document, self.changes)
        except Exception as error:
            self.experimental_mode.set(self.adapter.experimental)
            messagebox.showerror('Experimental Edits Remain',
                                 'Revert or save edits above supported limits before disabling experimental editing.\n\n'
                                 + str(error))
            return
        self.adapter = candidate
        self.refresh()

    @experimental_operation
    def field_options(self, field, *, changes=None):
        if self.document is not None and hasattr(self.backend, 'field_options_for_changes'):
            pending = self.changes if changes is None else changes
            return tuple(self.backend.field_options_for_changes(self.document, pending, field.id))
        if self.document is not None and hasattr(self.backend, 'field_options'):
            return tuple(self.backend.field_options(self.document, field.id))
        return ()

    def display_value(self, field, value, *, changes=None):
        if type(value) is not int:
            return str(value)
        label = dict(self.field_options(field, changes=changes)).get(value)
        return f'{value:,} · {label}' if label is not None else f'{value:,}'

    def selected_choice(self, _event=None):
        if self.choice_value.get() in self._choice_values:
            self.value.set(str(self._choice_values[self.choice_value.get()]))

    def clear_choice_search(self, _event=None):
        self.choice_search.set('')
        return 'break'

    def filter_choices(self, *_args):
        tokens = self.choice_search.get().casefold().split()
        labels = tuple(label for label in self._choice_values
                       if all(token in label.casefold() for token in tokens))
        self.value_choice.configure(values=labels)
        self.choice_count.set(f'{len(labels):,} of {len(self._choice_values):,} choices')

    @experimental_operation
    def selected(self, _event=None):
        keys = self.fields.selection()
        if tuple(keys) != self._choice_selection:
            self._choice_selection = tuple(keys)
            self.choice_search.set('')
        self.choice_tools.pack_forget()
        if keys and self.document:
            fields = self.adapter.field_map(self.document)
            field = fields[keys[0]]
            values = {self.changes.get(key, fields[key].value(self.document.payload)) for key in keys}
            value = next(iter(values)) if len(values) == 1 else None
            self.value.set(str(value) if value is not None else '')
            hint = self.presentation.field_hint(self.document, field)
            if len(keys) == 1:
                opened = self.display_value(field, field.value(self.document.payload), changes={})
                current = self.display_value(field, value)
                hint = (f'{self.record_name(field)} / {field.label}. Opened: {opened}; current: {current}. '
                        + hint)
            else:
                hint = (f'{len(keys):,} selected fields; '
                        + ('mixed current values. Choose a value to assign to all. ' if value is None
                           else f'current value: {self.display_value(field, value)}. Apply assigns to all. ')
                        + hint)
            maximum = experimental_maximum(field)
            if maximum is not None:
                hint += (f' Supported maximum: {field.maximum:,}; encoding limit: {maximum:,}.'
                         ' Above the supported maximum is experimental and may break the save or game.')
            self.selection_info.set(hint)
            options = self.field_options(field)
            if options and all(self.field_options(fields[key]) == options for key in keys):
                self._choice_values = {f'{number} · {label}': number for number, label in options}
                opened = {fields[key].value(self.document.payload) for key in keys}
                if len(opened) == 1:
                    number = next(iter(opened))
                    if number not in self._choice_values.values():
                        # A valid copy may contain an unusual original enum.
                        # Expose its exact no-op without assigning that value
                        # to other records whose opened values are different.
                        self._choice_values[f'{number} · Opened value (preserved)'] = number
                self.filter_choices()
                self.choice_value.set(next((label for label, number in self._choice_values.items()
                                           if number == value), ''))
                self.value_entry.pack_forget()
                self.value_choice.pack(side='left')
                if len(self._choice_values) > 10:
                    self.choice_tools.pack(fill='x', before=self.bulk_bar)
            else:
                self._choice_values = {}
                self.value_choice.pack_forget()
                self.value_entry.pack(side='left')
        else:
            self.value.set('')
            self.choice_value.set('')
            self._choice_values = {}
            self.value_choice.pack_forget()
            self.value_entry.pack(side='left')
            self.selection_info.set('Select a record to inspect its values.')

    @experimental_operation
    def record_name(self, field):
        return self.presentation.record_name(field)

    @experimental_operation
    def show_inspector(self):
        if self.document is None:
            return
        document = self.document
        dialog = tk.Toplevel(self.root)
        dialog.title('Mapped Save Data - Read Only')
        dialog.geometry('1000x600')
        ttk.Label(dialog, text='Opened data: progression and content associations. Pending edits appear in the main editor.',
                  padding=12, wraplength=960).pack(anchor='w')
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill='both', expand=True, padx=12, pady=8)
        def table(title, columns, rows, note):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            tools = ttk.Frame(frame, padding=(6, 6))
            tools.pack(fill='x')
            ttk.Label(tools, text='Find records').pack(side='left', padx=(0, 8))
            query = tk.StringVar(dialog)
            ttk.Entry(tools, textvariable=query).pack(side='left', fill='x', expand=True)
            if note:
                ttk.Label(frame, text=note, padding=8, wraplength=950).pack(side='bottom', anchor='w')
            body = ttk.Frame(frame)
            body.pack(fill='both', expand=True)
            view = ttk.Treeview(body, columns=columns, show='headings')
            for column in columns:
                view.heading(column, text=column)
                view.column(column, width=180)
            attach_sorting(view)
            ttk.Button(tools, text='Copy Selected', command=lambda: copy_selected(view)).pack(side='left', padx=(8, 0))
            view.grid(row=0, column=0, sticky='nsew')
            body.rowconfigure(0, weight=1)
            body.columnconfigure(0, weight=1)
            scroll = ttk.Scrollbar(body, orient='vertical', command=view.yview)
            scroll.grid(row=0, column=1, sticky='ns')
            horizontal = ttk.Scrollbar(body, orient='horizontal', command=view.xview)
            horizontal.grid(row=1, column=0, sticky='ew')
            view.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
            records = tuple((view.insert('', 'end', values=row),
                             ' '.join(str(value) for value in row).casefold()) for row in rows)
            def filter_rows(*_args):
                tokens = query.get().casefold().split()
                for identity, text in records:
                    if all(token in text for token in tokens):
                        view.move(identity, '', 'end')
                    else:
                        view.detach(identity)
                sort_table(view)
            query.trace_add('write', filter_rows)
            return view
        for content in self.presentation.inspection_tables(document):
            table(content.title, content.columns, content.rows, content.note)
        ttk.Button(dialog, text='Close', command=dialog.destroy).pack(pady=10)
        self.apply_theme(self.theme_name.get())

    def stage_values(self, values):
        if self.document is None:
            return
        try:
            result = dict(self.changes)
            for key, value in values.items():
                result = self.adapter.stage(self.document, result, key, value)
            self._accept_pending(result)
        except Exception as error:
            messagebox.showerror('Cannot Stage Edit', str(error))

    def _accept_pending(self, result):
        # Native dependencies apply to the final batch, including side effects
        # of backend staging (for example an equipped-slot swap). Reject the
        # entire action before changing the pending map or its Undo history.
        self.adapter.changed_payload(self.document, result)
        if result != self.changes:
            self.history.append(dict(self.changes))
            self.changes = result
            self.refresh()
        self.status.set(f'{len(self.changes)} pending field edits. Review changes before saving a new copy.')

    def apply_selected(self):
        keys = self.fields.selection()
        if not keys or self.document is None:
            return
        fields = self.adapter.field_map(self.document)
        kinds = {getattr(fields[key], 'kind', 'int') for key in keys}
        if kinds == {'text'}:
            self.stage_values({key: self.value.get() for key in keys})
            return
        if 'text' in kinds:
            messagebox.showerror('Mixed Field Types', 'Select text fields or numeric fields separately for a bulk edit.')
            return
        try:
            value = int(self.value.get())
        except ValueError:
            messagebox.showerror('Invalid Value', 'Enter a whole number.')
            return
        self.stage_values({key: value for key in keys})

    def max_selected(self):
        self._max_fields(self.fields.selection())

    def _max_fields(self, keys):
        if self.document is None:
            return
        try:
            values = self.adapter.limit_values(self.document, self.changes, keys)
            self.stage_values(values)
        except Exception as error:
            messagebox.showerror('Cannot Max Fields', str(error))

    def adjust_selected(self):
        keys = self.fields.selection()
        if not keys or self.document is None:
            return
        fields = self.adapter.field_map(self.document)
        if any(type(fields[key].value(self.document.payload)) is not int
               or self.field_options(fields[key]) for key in keys):
            messagebox.showerror('Cannot Adjust Selection',
                                 'Select numeric quantities or stats. Use Apply Selected for names and choices.')
            return
        delta = simpledialog.askinteger('Adjust Selected',
                                        f'Add to each of the {len(keys)} selected values.\n'
                                        'Enter a negative number to subtract. Each game\n'
                                        'validates the complete batch before staging it.',
                                        parent=self.root)
        if delta is None or delta == 0:
            return
        self.stage_values({key: self.changes.get(key, fields[key].value(self.document.payload)) + delta
                           for key in keys})

    def revert_selected(self):
        if self.document is None:
            return
        selected = set(self.fields.selection())
        result = {key: value for key, value in self.changes.items() if key not in selected}
        try:
            # Restore the whole selection in one transaction. Sequentially
            # unstaging a reordered loadout can create a transient duplicate
            # even when the final original loadout is valid.
            self._accept_pending(result)
        except Exception as error:
            messagebox.showerror('Cannot Revert Selection', str(error))

    def max_visible(self):
        self._max_fields(self.fields.get_children())

    def undo(self):
        if self.history:
            try:
                self.adapter.changed_payload(self.document, self.history[-1])
            except Exception as error:
                messagebox.showerror('Cannot Undo',
                                     'Enable experimental editing to restore edits above supported limits.\n\n'
                                     + str(error))
                return
            self.changes = self.history.pop()
            self.refresh()
            self.status.set(f'Undo complete. {len(self.changes)} pending edits.')

    def review(self):
        if self.document is None:
            return
        document = self.document
        pending = dict(self.changes)
        try:
            rows = tuple(self.adapter.review(document, pending))
            source_sha256, game_id = document.sha256, self.game_id
        except Exception as error:
            messagebox.showerror('Cannot Review Changes', str(error))
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('Review Changes')
        dialog.geometry('1000x520')
        experimental_count = len(self.experimental_changes())
        warning = (f'\nEXPERIMENTAL: {experimental_count} edits above supported limits; save/game may break.'
                   if experimental_count else '')
        ttk.Label(dialog, text=f'{self.layout.title}\n{len(rows)} staged field edits' + warning,
                  padding=15, wraplength=660).pack(anchor='w')
        search_bar = ttk.Frame(dialog, padding=(15, 0, 15, 8))
        search_bar.pack(fill='x')
        ttk.Label(search_bar, text='Find changes').pack(side='left', padx=(0, 8))
        query = tk.StringVar(dialog)
        query_entry = ttk.Entry(search_bar, textvariable=query)
        query_entry.pack(side='left', fill='x', expand=True)
        ttk.Button(search_bar, text='Clear', command=lambda: query.set('')).pack(side='left', padx=8)
        count = tk.StringVar(dialog, value=f'{len(rows):,} of {len(rows):,} changes')
        ttk.Label(search_bar, textvariable=count, style='Muted.TLabel').pack(side='left')
        body = ttk.Frame(dialog)
        body.pack(fill='both', expand=True, padx=15)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        tree = ttk.Treeview(body, columns=('field', 'before', 'after'), show='headings')
        for column, label in (('field', 'Field / record'), ('before', 'Opened value'), ('after', 'Pending value')):
            tree.heading(column, text=label)
        attach_sorting(tree)
        from tkinter.font import Font
        label_font = Font(root=dialog, font=self.style.lookup('Treeview', 'font') or 'TkDefaultFont')
        label_width = 300
        value_widths = [140, 140]
        records = []
        # Freeze both native values and human labels now. Later edits, opening
        # another copy and filtering this window must not alter either export.
        csv_records = []
        for field, before, after in rows:
            record = self.record_name(field)
            label = field.label + (f' / {record}' if field.slot else '')
            label_width = max(label_width, label_font.measure(label) + 24)
            displayed = (label, self.display_value(field, before, changes={}),
                         self.display_value(field, after, changes=pending))
            for index, value in enumerate(displayed[1:]):
                value_widths[index] = max(value_widths[index], min(420, label_font.measure(value) + 24))
            identity = tree.insert('', 'end', values=displayed)
            records.append((identity, (' '.join(displayed)
                                       + f' {field.id} {field.group} {before} {after}').casefold()))
            csv_records.append((game_id, source_sha256, bool(experimental_count),
                                field.id, field.group, record, field.label,
                                type(before).__name__, before, type(after).__name__, after))
        def filter_rows(*_args):
            tokens = query.get().casefold().split()
            visible = 0
            for identity, text in records:
                if all(token in text for token in tokens):
                    tree.move(identity, '', 'end')
                    visible += 1
                else:
                    tree.detach(identity)
            sort_table(tree)
            count.set(f'{visible:,} of {len(rows):,} changes')
        query.trace_add('write', filter_rows)
        def focus_search(_event):
            query_entry.focus_set()
            query_entry.selection_range(0, 'end')
            return 'break'
        def clear_search(_event):
            query.set('')
            return 'break'
        dialog.bind('<Control-f>', focus_search)
        query_entry.bind('<Escape>', clear_search)
        dialog.review_query, dialog.review_tree = query, tree
        tree.column('field', width=label_width, minwidth=300, stretch=False)
        tree.column('before', width=value_widths[0], minwidth=100)
        tree.column('after', width=value_widths[1], minwidth=100)
        tree.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(body, orient='vertical', command=tree.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(body, orient='horizontal', command=tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        footer = ttk.Frame(dialog)
        footer.pack(side='bottom', fill='x', before=body)
        ttk.Label(dialog, text='Exports include all changes from when this review opened. '
                  'Copy Selected copies the visible selection. Use Save As... in the editor '
                  'to save an edited game file.', wraplength=950).pack(
                      side='bottom', anchor='w', before=body, padx=15, pady=(8, 0))
        def export(csv_format=False):
            extension = '.changes.csv' if csv_format else '.changes.json'
            path = filedialog.asksaveasfilename(
                parent=dialog, title='Export Change Review', defaultextension=extension,
                initialdir=document.source.parent, initialfile=document.source.stem + extension,
                filetypes=[('Change review (CSV)' if csv_format else 'Change review (JSON)', '*' + extension)],
                confirmoverwrite=False)
            if path:
                report = {'game_id': game_id, 'source_sha256': source_sha256,
                          'experimental': bool(experimental_count),
                          'changes': [{'field': field.id, 'before': before, 'after': after}
                                      for field, before, after in rows]}
                try:
                    destination = Path(path)
                    name = destination.name
                    if not name.lower().endswith(extension):
                        suffix = '.csv' if csv_format else '.json'
                        if name.lower().endswith(suffix):
                            name = name[:-len(suffix)]
                        if not name.lower().endswith('.changes'):
                            name += '.changes'
                        destination = destination.with_name(name + suffix)
                    if csv_format:
                        data = _review_csv(csv_records)
                    else:
                        data = json.dumps(report, indent=2).encode('utf-8')
                    destination = _export_review(data, destination)
                    self.status.set('Change review exported: ' + destination.name)
                except Exception as error:
                    messagebox.showerror('Cannot Export Review', str(error))
        ttk.Button(dialog, text='Export Review...', command=export).pack(in_=footer, side='left', padx=15, pady=12)
        ttk.Button(dialog, text='Export CSV...', command=lambda: export(True)).pack(in_=footer, side='left', pady=12)
        ttk.Button(dialog, text='Copy Selected', command=lambda: copy_selected(tree)).pack(
            in_=footer, side='left', padx=15, pady=12)
        ttk.Button(dialog, text='Close', command=dialog.destroy).pack(in_=footer, side='right', padx=15)
        self.apply_theme(self.theme_name.get())

    def save_changes(self):
        self.save_as()

    def save_as(self):
        if self.document is None:
            return
        path = filedialog.asksaveasfilename(title='Save Edited Copy As', defaultextension=self.save_extension,
                                           initialdir=self.document.source.parent,
                                           initialfile=self.document.source.stem + ('.edited' + self.save_extension if self.save_extension else '-edited'), confirmoverwrite=False)
        if path:
            self.save_to(path)

    def save_to(self, path):
        try:
            count = len(self.experimental_changes())
            if count and not messagebox.askyesno(
                    'Save Experimental Copy?',
                    f'{count} pending edits exceed supported limits. The save file or game may break, '
                    'or the game may reset these values. Your original and backup are preserved.\n\n'
                    'Save this experimental copy?'):
                return
            document = self.adapter.save_as(self.document, self.changes, path)
        except Exception as error:
            messagebox.showerror('Cannot Save Copy', str(error))
            return
        self.document = document
        self.changes, self.history = {}, []
        self.update_filename('Opened edited copy: ')
        self.refresh()
        self.status.set('Edited copy saved. Original snapshot backed up.')

    def make_backup(self):
        if self.document:
            try:
                self.backup = self.adapter.backup(self.document)
                self.status.set('Opened bytes backed up: ' + self.backup.name)
            except Exception as error:
                messagebox.showerror('Backup Failed', str(error))

    def restore(self):
        path = filedialog.askopenfilename(title='Choose a Backup for This Game',
                                          filetypes=[('Save backup', '*' + self.save_extension)])
        if not path:
            return
        destination = filedialog.asksaveasfilename(title='Restore to a New Copy',
                                                  defaultextension=self.save_extension, confirmoverwrite=False)
        if destination:
            try:
                self.adapter.restore(path, destination, self.game_id)
                self.status.set('Backup restored to a new copy.')
            except Exception as error:
                messagebox.showerror('Restore Failed', str(error))

    def close(self):
        if self.dirty_ok():
            self.root.destroy()

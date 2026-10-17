"""A retained conversion workspace; codecs and file operations stay outside Tk."""
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor import conversion
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.scrollable_panel import ScrollablePanel


class ConversionWorkspace:
    def __init__(self, root, parent, on_queue=None):
        self.root = root
        self.on_queue = on_queue
        self.queue_button = None
        self.frame = ttk.Frame(parent, padding=(28, 16))
        self.actions = ttk.Frame(self.frame)
        self.actions.pack(side='bottom', fill='x', pady=(8, 0))
        for column in range(2):
            self.actions.columnconfigure(column, weight=1)
        self.viewport = ScrollablePanel(self.frame)
        self.viewport.frame.pack(fill='both', expand=True)
        body = self.viewport.content
        self.prepared = None
        self.busy = False
        self._revision = 0
        self._results = queue.SimpleQueue()
        self._labels = {route.label: route.id for route in conversion.ROUTES}
        font_family = ui_font(root)
        ttk.Label(body, text='SAVE CONVERTER', font=(font_family, 23, 'bold')).pack(anchor='w')
        ttk.Label(body, text='Move a copied save to another platform',
                  style='Muted.TLabel').pack(anchor='w', pady=(2, 14))
        ttk.Label(body, text='Choose the exact game editions and transfer scope supported by your copies. '
                  'Each route lists what will move and what stays in the destination template.',
                  wraplength=980).pack(anchor='w', pady=(0, 12))
        form = ttk.Frame(body)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        self.route_search = tk.StringVar(root)
        self.route_count = tk.StringVar(root)
        self.route = tk.StringVar(root, value=next(iter(self._labels)))
        self.source = tk.StringVar(root)
        self.template = tk.StringVar(root)
        self.controls = []
        ttk.Label(form, text='Find route').grid(row=0, column=0, sticky='w', padx=(0, 14), pady=8)
        self.search_entry = ttk.Entry(form, textvariable=self.route_search, width=1)
        self.search_entry.grid(row=0, column=1, sticky='ew', pady=8)
        ttk.Label(form, textvariable=self.route_count, style='Muted.TLabel').grid(
            row=0, column=2, sticky='w', padx=(10, 0))
        self.search_entry.bind('<Escape>', lambda _event: self.route_search.set(''))
        self.controls.append(self.search_entry)
        ttk.Label(form, text='Conversion').grid(row=1, column=0, sticky='w', padx=(0, 14), pady=8)
        self.route_selector = ttk.Combobox(form, textvariable=self.route, values=tuple(self._labels), state='readonly', width=1)
        self.route_selector.grid(row=1, column=1, columnspan=2, sticky='ew', pady=8)
        self.controls.append(self.route_selector)
        self.scope = tk.StringVar(root)
        self.scope_label = ttk.Label(form, textvariable=self.scope, wraplength=500, style='Muted.TLabel')
        self.scope_label.grid(row=2, column=1, columnspan=2, sticky='ew')
        self.scope_label.bind('<Configure>', lambda event: self.scope_label.configure(wraplength=max(1, event.width)))
        for row, label, variable, kind in ((3, 'Source copy', self.source, 'source'),
                                           (4, 'Destination template', self.template, 'template')):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', padx=(0, 14), pady=8)
            entry = ttk.Entry(form, textvariable=variable, width=1)
            entry.grid(row=row, column=1, sticky='ew', pady=8)
            button = ttk.Button(form, text='Browse…', command=lambda k=kind: self.browse(k))
            button.grid(row=row, column=2, padx=(10, 0), pady=8)
            self.controls.extend((entry, button))
        ttk.Label(body, text='First create a save in the destination game and copy/export its save folder. '
                  'The template supplies the destination encryption and original console metadata. '
                  'For PS3, keep PARAM.SFO beside APP.BIN; for PS4, keep sce_sys/param.sfo. '
                  'Console inputs must already be exported/decrypted.',
                  style='Muted.TLabel', wraplength=980).pack(anchor='w', pady=(10, 14))
        buttons = self.actions
        self.review_button = ttk.Button(buttons, text='Review conversion', command=self.review)
        self.review_button.grid(row=0, column=0, sticky='ew', padx=(0, 8), pady=3)
        self.export_button = ttk.Button(buttons, text='Export to new folder…', command=self.export, state='disabled')
        self.export_button.grid(row=0, column=1, sticky='ew', pady=3)
        self.controls.append(self.review_button)
        if on_queue is not None:
            self.queue_button = ttk.Button(buttons, text='Add reviewed job to batch…', command=self.queue_review, state='disabled')
            self.queue_button.grid(row=1, column=0, columnspan=2, sticky='ew', pady=3)
        self.status = tk.StringVar(root, value='Choose separate source and destination-template copies, then review.')
        ttk.Label(body, textvariable=self.status, wraplength=980).pack(anchor='w', pady=(14, 8))
        self.preview = tk.Text(body, height=15, width=1, wrap='word', relief='flat', padx=14, pady=12,
                               state='disabled', font=(font_family, 10))
        self.preview.pack(fill='both', expand=True)
        for variable in (self.route, self.source, self.template):
            variable.trace_add('write', self.invalidate)
        self.route_search.trace_add('write', self._filter_routes)
        self._filter_routes()
        self.invalidate()

        body.bind('<Configure>',self._resize_guidance,add='+')

    def _resize_guidance(self, event):
        for widget in self.viewport.content.winfo_children():
            if isinstance(widget, ttk.Label):
                widget.configure(wraplength=max(1, event.width - 8))


    def _filter_routes(self, *_args):
        terms = self.route_search.get().casefold().split()
        labels = []
        for route in conversion.ROUTES:
            endpoints = [conversion.ENDPOINTS[key] for key in (route.source_id, route.target_id)]
            text = ' '.join((route.label, route.id, route.scope_description,
                             *(endpoint.import_note for endpoint in endpoints))).casefold()
            if all(term in text for term in terms):
                labels.append(route.label)
        self.route_selector.configure(values=tuple(labels))
        self.route_count.set(f'{len(labels)} of {len(self._labels)} routes')
        # Filtering must never silently choose a different direction/scope for
        # the retained input paths or keep an invisible reviewed selection.
        if self.route.get() not in labels:
            self.route.set('')
        if not self.busy:
            self.route_selector.configure(state='readonly' if labels else 'disabled')
            self.review_button.configure(state='normal' if self.route.get() in self._labels else 'disabled')

    def invalidate(self, *_args):
        route_id = self._labels.get(self.route.get())
        self.scope.set(conversion.get_route(route_id).scope_description if route_id else 'Choose a supported route.')
        self._revision += 1
        self.prepared = None
        self.export_button.configure(state='disabled')
        if self.queue_button is not None:
            self.queue_button.configure(state='disabled')
        self._show('')
        if not self.busy:
            self.review_button.configure(state='normal' if route_id else 'disabled')
            self.status.set('Selections changed. Review the conversion before exporting.')

    def _show(self, text):
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', text)
        self.preview.configure(state='disabled')

    def focus_route_search(self):
        if not self.busy:
            self.search_entry.focus_set()
            self.search_entry.selection_range(0, 'end')
        return 'break'

    def apply_theme(self, palette):
        self.viewport.apply_theme(palette)
        self.preview.configure(background=palette['surface'], foreground=palette['text'],
                               insertbackground=palette['text'])

    def browse(self, kind):
        route_id = self._labels.get(self.route.get())
        if not route_id:
            messagebox.showerror('Choose a conversion', 'Choose an exact conversion route first.', parent=self.root)
            return
        route = conversion.get_route(route_id)
        endpoint = conversion.ENDPOINTS[route.source_id if kind == 'source' else route.target_id]
        suffix = Path(endpoint.filename).suffix
        filters = [(endpoint.label, '*' + suffix), ('All files', '*')] if suffix else [('All files', '*')]
        path = filedialog.askopenfilename(parent=self.root, title='Choose ' + kind + ' copy', filetypes=filters)
        if path:
            (self.source if kind == 'source' else self.template).set(path)

    def _start(self, operation, kind):
        self.busy = True
        revision = self._revision
        for control in self.controls:
            control.configure(state='disabled')
        self.export_button.configure(state='disabled')
        if self.queue_button is not None:
            self.queue_button.configure(state='disabled')
        self.status.set('Checking copied saves…' if kind == 'review' else 'Backing up and exporting the converted copy…')
        def worker():
            try:
                self._results.put((kind, revision, operation(), None))
            except Exception as error:
                self._results.put((kind, revision, None, error))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(80, self._poll)

    def _poll(self):
        try:
            kind, revision, result, error = self._results.get_nowait()
        except queue.Empty:
            self.root.after(80, self._poll)
            return
        self.busy = False
        for control in self.controls:
            control.configure(state='readonly' if control is self.route_selector else 'normal')
        self._filter_routes()
        if kind == 'review' and revision != self._revision:
            self.status.set('Selections changed during review. Review the current copies again.')
            return
        if error is not None:
            self.prepared = None
            self._show('')
            self.status.set(str(error))
            messagebox.showerror('Conversion could not finish', str(error), parent=self.root)
            return
        if kind == 'review':
            self.prepared = result
            text = (result.route.label + '\n\n'
                    + f'{result.gameplay_bytes:,} mapped gameplay bytes will be transferred.\n'
                    + f'Output: {conversion.ENDPOINTS[result.route.target_id].filename}\n\n'
                    + '\n\n'.join(result.notes)
                    + '\n\nBoth inputs receive automatic backups. Export creates a new folder with a local conversion receipt.')
            self._show(text)
            self.status.set('Review complete. Ready to export a separate copy.')
            self.export_button.configure(state='normal')
            if self.queue_button is not None:
                self.queue_button.configure(state='normal')
        else:
            destination, _backups, _receipt = result
            self.status.set('Exported: ' + str(destination))
            self.export_button.configure(state='normal' if self.prepared is not None else 'disabled')
            if self.queue_button is not None:
                self.queue_button.configure(state='normal' if self.prepared is not None else 'disabled')
            messagebox.showinfo('Conversion exported', 'Saved a separate converted copy with backups.\n\n'
                                + str(destination) + '\n\nTest the copy in-game. Console imports require your save manager.', parent=self.root)

    def review(self):
        if self.busy:
            return
        route_id = self._labels.get(self.route.get())
        if not route_id:
            messagebox.showerror('Choose a conversion', 'Choose an exact conversion route first.', parent=self.root)
            return
        if not self.source.get().strip() or not self.template.get().strip():
            messagebox.showerror('Choose both copies', 'Choose a source copy and a destination-template copy.', parent=self.root)
            return
        source, template = self.source.get(), self.template.get()
        self.prepared = None
        self._show('')
        self._start(lambda: conversion.prepare(route_id, source, template), 'review')

    def queue_review(self):
        if not self.busy and self.prepared is not None and self.on_queue is not None:
            self.on_queue(self.prepared)

    def export(self):
        if self.busy or self.prepared is None:
            return
        parent = filedialog.askdirectory(parent=self.root, title='Choose a parent folder for a new converted-save folder')
        if not parent:
            return
        from tkinter import simpledialog
        name = simpledialog.askstring('New export folder', 'Name the new output folder:',
                                      initialvalue='Converted-' + self.prepared.route.target_id, parent=self.root)
        if not name:
            return
        if name in ('.', '..') or '/' in name or '\\' in name or Path(name).name != name:
            messagebox.showerror('Choose a folder name', 'Enter one new folder name, without a path.', parent=self.root)
            return
        prepared = self.prepared
        self._start(lambda: conversion.export(prepared, Path(parent) / name), 'export')

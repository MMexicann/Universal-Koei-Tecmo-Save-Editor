"""A retained conversion workspace; codecs and file operations stay outside Tk."""
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor import conversion
from koei_editor.shared.appearance import ui_font


class ConversionWorkspace:
    def __init__(self, root, parent):
        self.root = root
        self.frame = ttk.Frame(parent, padding=(28, 16))
        self.prepared = None
        self.busy = False
        self._revision = 0
        self._results = queue.SimpleQueue()
        self._labels = {route.label: route.id for route in conversion.ROUTES}
        font_family = ui_font(root)
        ttk.Label(self.frame, text='SAVE CONVERTER', font=(font_family, 23, 'bold')).pack(anchor='w')
        ttk.Label(self.frame, text='Move a copied save to another platform',
                  style='Muted.TLabel').pack(anchor='w', pady=(2, 14))
        ttk.Label(self.frame, text='DW8 XL: PC / US PS3 PSN / Vita. Persona 5 Strikers: English PC / PS4 / Switch. '
                  'Other games and revisions need their own conversion mapping.',
                  wraplength=980).pack(anchor='w', pady=(0, 12))
        form = ttk.Frame(self.frame)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        self.route = tk.StringVar(root, value=next(iter(self._labels)))
        self.source = tk.StringVar(root)
        self.template = tk.StringVar(root)
        self.controls = []
        ttk.Label(form, text='Conversion').grid(row=0, column=0, sticky='w', padx=(0, 14), pady=8)
        self.route_selector = ttk.Combobox(form, textvariable=self.route, values=tuple(self._labels), state='readonly')
        self.route_selector.grid(row=0, column=1, columnspan=2, sticky='ew', pady=8)
        self.controls.append(self.route_selector)
        for row, label, variable, kind in ((1, 'Source copy', self.source, 'source'),
                                           (2, 'Destination template', self.template, 'template')):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', padx=(0, 14), pady=8)
            entry = ttk.Entry(form, textvariable=variable)
            entry.grid(row=row, column=1, sticky='ew', pady=8)
            button = ttk.Button(form, text='Browse…', command=lambda k=kind: self.browse(k))
            button.grid(row=row, column=2, padx=(10, 0), pady=8)
            self.controls.extend((entry, button))
        ttk.Label(self.frame, text='First create a save in the destination game and copy/export its save folder. '
                  'The template supplies the destination encryption and original console metadata. '
                  'For PS3, keep PARAM.SFO beside APP.BIN; for PS4, keep sce_sys/param.sfo. '
                  'Console inputs must already be exported/decrypted.',
                  style='Muted.TLabel', wraplength=980).pack(anchor='w', pady=(10, 14))
        buttons = ttk.Frame(self.frame)
        buttons.pack(fill='x')
        self.review_button = ttk.Button(buttons, text='Review conversion', command=self.review)
        self.review_button.pack(side='left')
        self.export_button = ttk.Button(buttons, text='Export to new folder…', command=self.export, state='disabled')
        self.export_button.pack(side='left', padx=10)
        self.controls.append(self.review_button)
        self.status = tk.StringVar(root, value='Choose separate source and destination-template copies, then review.')
        ttk.Label(self.frame, textvariable=self.status, wraplength=980).pack(anchor='w', pady=(14, 8))
        self.preview = tk.Text(self.frame, height=15, wrap='word', relief='flat', padx=14, pady=12,
                               state='disabled', font=(font_family, 10))
        self.preview.pack(fill='both', expand=True)
        for variable in (self.route, self.source, self.template):
            variable.trace_add('write', self.invalidate)

    def invalidate(self, *_args):
        self._revision += 1
        self.prepared = None
        self.export_button.configure(state='disabled')
        self._show('')
        if not self.busy:
            self.status.set('Selections changed. Review the conversion before exporting.')

    def _show(self, text):
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', text)
        self.preview.configure(state='disabled')

    def apply_theme(self, palette):
        self.preview.configure(background=palette['surface'], foreground=palette['text'],
                               insertbackground=palette['text'])

    def browse(self, kind):
        route = conversion.get_route(self._labels[self.route.get()])
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
                    + f'{result.gameplay_bytes:,} shared gameplay bytes will be preserved.\n'
                    + f'Output: {conversion.ENDPOINTS[result.route.target_id].filename}\n\n'
                    + '\n\n'.join(result.notes)
                    + '\n\nBoth inputs receive automatic backups. Export creates a new folder with a local conversion receipt.')
            self._show(text)
            self.status.set('Review complete. Ready to export a separate copy.')
            self.export_button.configure(state='normal')
        else:
            destination, _backups, _receipt = result
            self.status.set('Exported: ' + str(destination))
            self.export_button.configure(state='normal')
            messagebox.showinfo('Conversion exported', 'Saved a separate converted copy with backups.\n\n'
                                + str(destination) + '\n\nTest the copy in-game. Console imports require your save manager.', parent=self.root)

    def review(self):
        if self.busy:
            return
        if not self.source.get().strip() or not self.template.get().strip():
            messagebox.showerror('Choose both copies', 'Choose a source copy and a destination-template copy.', parent=self.root)
            return
        route_id = self._labels[self.route.get()]
        source, template = self.source.get(), self.template.get()
        self.prepared = None
        self._show('')
        self._start(lambda: conversion.prepare(route_id, source, template), 'review')

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

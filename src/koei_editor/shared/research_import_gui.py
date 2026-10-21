"""Retained asynchronous candidate inspection with no save-writing actions."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.research import imports
from koei_editor.shared.appearance import ui_font
from koei_editor.shared.scrollable_panel import ScrollablePanel


class ResearchImportWorkspace:
    def __init__(self, root, parent):
        self.root = root
        self.frame = ttk.Frame(parent, padding=(20, 14))
        actions = ttk.Frame(self.frame)
        actions.pack(side='bottom', fill='x', pady=(10, 0))
        self.viewport = ScrollablePanel(self.frame)
        self.viewport.frame.pack(fill='both', expand=True)
        body = self.viewport.content
        self.busy = False
        self.result = None
        self._revision = 0
        self._results = queue.SimpleQueue()
        self._labels = {profile.label: profile.id for profile in imports.PROFILES.values()}
        self.search = tk.StringVar(root)
        self.profile = tk.StringVar(root, value=next(iter(self._labels)))
        self.source = tk.StringVar(root)
        self.guidance = tk.StringVar(root)
        self.status = tk.StringVar(root, value='Choose a separate native copy and its exact research profile.')
        ttk.Label(body, text='RESEARCH IMPORT', font=(ui_font(root), 23, 'bold')).pack(anchor='w')
        ttk.Label(body, text=imports.WARNING, wraplength=950).pack(anchor='w', pady=(4, 8))
        ttk.Label(body, text='Inspect additional game candidates without adding them to the supported editor library. '
                  'No editing, repair, save export or conversion is available here. Reports can contain private values; '
                  'nothing is uploaded.', style='Muted.TLabel', wraplength=950).pack(anchor='w', pady=(0, 12))
        form = ttk.Frame(body)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='Find candidate').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.search_entry = ttk.Entry(form, textvariable=self.search)
        self.search_entry.grid(row=0, column=1, columnspan=2, sticky='ew', pady=4)
        self.search_entry.bind('<Escape>', lambda _event: self.search.set(''))
        ttk.Label(form, text='Exact candidate').grid(row=1, column=0, sticky='w', padx=(0, 10))
        self.selector = ttk.Combobox(form, textvariable=self.profile, values=tuple(self._labels), state='readonly', width=1)
        self.selector.grid(row=1, column=1, columnspan=2, sticky='ew', pady=4)
        ttk.Label(form, text='Copied native file').grid(row=2, column=0, sticky='w', padx=(0, 10))
        self.source_entry = ttk.Entry(form, textvariable=self.source)
        self.source_entry.grid(row=2, column=1, sticky='ew', pady=4)
        self.browse_button = ttk.Button(form, text='Browse…', command=self.browse)
        self.browse_button.grid(row=2, column=2, padx=(8, 0))
        self.guidance_label = ttk.Label(body, textvariable=self.guidance, wraplength=950, style='Muted.TLabel')
        self.guidance_label.pack(anchor='w', fill='x', pady=(8, 10))
        self.inspect_button = ttk.Button(actions, text='Inspect copied file', command=self.inspect)
        self.inspect_button.pack(side='left')
        self.clear_button = ttk.Button(actions, text='Clear import', command=self.clear)
        self.clear_button.pack(side='left', padx=8)
        ttk.Label(body, textvariable=self.status, wraplength=950).pack(anchor='w', pady=6)
        holder = ttk.Frame(body)
        holder.pack(fill='both', expand=True)
        self.report = tk.Text(holder, state='disabled', wrap='word', width=1, height=24,
                              relief='flat', padx=12, pady=10, font=(ui_font(root), 10))
        scroll = ttk.Scrollbar(holder, orient='vertical', command=self.report.yview)
        self.report.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.report.pack(fill='both', expand=True)
        self.controls = (self.search_entry, self.selector, self.source_entry,
                         self.browse_button, self.inspect_button, self.clear_button)
        self.search.trace_add('write', self.filter_candidates)
        for variable in (self.profile, self.source):
            variable.trace_add('write', self.invalidate)
        body.bind('<Configure>', self._resize, add='+')
        self.invalidate()

    def _resize(self, event):
        for widget in self.viewport.content.winfo_children():
            if isinstance(widget, ttk.Label):
                widget.configure(wraplength=max(1, event.width - 8))

    def _show(self, text):
        self.report.configure(state='normal')
        self.report.delete('1.0', 'end')
        self.report.insert('1.0', text)
        self.report.configure(state='disabled')

    def filter_candidates(self, *_args):
        terms = self.search.get().casefold().split()
        labels = tuple(profile.label for profile in imports.PROFILES.values()
                       if all(term in (profile.label + ' ' + profile.id + ' ' + profile.guidance).casefold()
                              for term in terms))
        self.selector.configure(values=labels)
        if self.profile.get() not in labels:
            self.profile.set('')
        if not self.busy:
            self.selector.configure(state='readonly' if labels else 'disabled')
            self.inspect_button.configure(state='normal' if self.profile.get() in self._labels else 'disabled')

    def invalidate(self, *_args):
        self._revision += 1
        self.result = None
        self._show('')
        key = self._labels.get(self.profile.get())
        if key:
            profile = imports.get_profile(key)
            self.guidance.set('Required: ' + profile.filename
                              + (' + ' + profile.companion if profile.companion else '')
                              + '\n' + profile.guidance)
        else:
            self.guidance.set('Choose an explicit candidate. Another parser is never tried after rejection.')
        if not self.busy:
            self.inspect_button.configure(state='normal' if key else 'disabled')
            self.status.set('Selections changed. Inspect the selected copy again.')

    def clear(self):
        if not self.busy:
            self.source.set('')
            self.invalidate()

    def browse(self):
        key = self._labels.get(self.profile.get())
        if not key or self.busy:
            return
        profile = imports.get_profile(key)
        suffix = Path(profile.filename).suffix
        filetypes = [(profile.filename, '*' + suffix), ('All files', '*')] if suffix else [('All files', '*')]
        path = filedialog.askopenfilename(parent=self.root, title='Choose separate research copy', filetypes=filetypes)
        if path:
            self.source.set(path)

    def inspect(self):
        key = self._labels.get(self.profile.get())
        if self.busy or not key:
            return
        source, revision = self.source.get(), self._revision
        self.busy = True
        self.result = None
        self._show('')
        for control in self.controls:
            control.configure(state='disabled')
        self.status.set('Inspecting the selected native copy and original context…')
        def worker():
            try:
                self._results.put((revision, imports.inspect_copy(key, source), None))
            except Exception as error:
                self._results.put((revision, None, error))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(60, self._poll)

    def _poll(self):
        if not self.frame.winfo_exists():
            return
        try:
            revision, result, error = self._results.get_nowait()
        except queue.Empty:
            self.root.after(60, self._poll)
            return
        self.busy = False
        for control in self.controls:
            control.configure(state='readonly' if control is self.selector else 'normal')
        self.filter_candidates()
        if revision != self._revision:
            self.status.set('Selections changed during inspection. Inspect the current copy again.')
        elif error is not None:
            self.status.set('The selected candidate rejected this copy; no alternate parser was tried.')
            messagebox.showerror('Research import rejected', str(error), parent=self.root)
        else:
            self.result = result
            self._show(result.report_json)
            self.status.set(f'Read-only inspection complete: {result.size_bytes:,} bytes. No game file was written. '
                            'The report describes this snapshot; inspect again after any file or metadata change.')

    def focus_search(self):
        if not self.busy:
            self.search_entry.focus_set()
            self.search_entry.selection_range(0, 'end')
        return 'break'

    def apply_theme(self, palette):
        self.viewport.apply_theme(palette)
        self.report.configure(background=palette['surface'], foreground=palette['text'],
                              insertbackground=palette['text'])

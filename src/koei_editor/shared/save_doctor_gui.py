"""Asynchronous, read-only Save Doctor workspace with safe report export."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from koei_editor.shared import save_doctor as backend
from koei_editor.shared.appearance import THEMES, ui_font


STATE_LABELS = {'passed': 'Passed', 'failed': 'Needs attention', 'warning': 'Warning',
                'unknown': 'Not established', 'cancelled': 'Cancelled'}


class SaveDoctorWorkspace:
    """Only workers touch copied files; only the Tk thread touches widgets."""
    def __init__(self, root, parent, on_open=None):
        self.root, self.on_open = root, on_open
        self.frame = ttk.Frame(parent, padding=(24, 16))
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(5, weight=1)
        self.busy, self.prepared = False, None
        self._operation, self._revision, self._closed, self._poll_id = '', 0, False, None
        self._animation_id = None
        self._cancel, self._results = threading.Event(), queue.SimpleQueue()
        self.palette = THEMES['Light']
        self._cards, self._wrapped, self._selected = [], [], None
        self._games = {f'{game.title} · {game.subtitle} [{game.platform}]': game.id
                       for game in backend.DOCTOR_GAMES}
        self.game, self.path = tk.StringVar(root), tk.StringVar(root)
        self.search, self.filter = tk.StringVar(root), tk.StringVar(root, value='All checks')
        self.status = tk.StringVar(root, value='Choose an exact game/platform and a separate gameplay-file copy.')
        family = ui_font(root)
        self._font_family = family
        heading = ttk.Frame(self.frame)
        heading.grid(row=0, column=0, sticky='ew')
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text='SAVE DOCTOR', font=(family, 23, 'bold')).grid(row=0, column=0, sticky='w')
        ttk.Label(heading, text='READ ONLY', style='Muted.TLabel').grid(row=0, column=1, sticky='e')
        description = ttk.Label(self.frame, text='Understand why a copied save qualifies, fails, or needs more evidence. '
                                'Check safely, inspect findings and share a private-data-free report.',
                                style='Muted.TLabel', wraplength=1000)
        description.grid(row=1, column=0, sticky='ew', pady=(5, 14))
        self._wrapped.append(description)
        form = ttk.Frame(self.frame)
        form.grid(row=2, column=0, sticky='ew')
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='Game / platform').grid(row=0, column=0, sticky='w', padx=(0, 14))
        self.selector = ttk.Combobox(form, textvariable=self.game, values=tuple(self._games), state='readonly')
        self.selector.grid(row=0, column=1, columnspan=2, sticky='ew', pady=4)
        ttk.Label(form, text='Copied save').grid(row=1, column=0, sticky='w', padx=(0, 14))
        self.file_entry = ttk.Entry(form, textvariable=self.path)
        self.file_entry.grid(row=1, column=1, sticky='ew', pady=4)
        self.browse_button = ttk.Button(form, text='Browse…', command=self.browse)
        self.browse_button.grid(row=1, column=2, padx=(10, 0))
        actions = ttk.Frame(self.frame)
        actions.grid(row=3, column=0, sticky='ew', pady=(9, 8))
        self.check_button = ttk.Button(actions, text='Check copied save', command=self.diagnose,
                                       style='Primary.TButton')
        self.check_button.pack(side='left')
        self.cancel_button = ttk.Button(actions, text='Cancel check', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=10)
        self.open_button = ttk.Button(actions, text='Open qualified copy', command=self.open_copy, state='disabled')
        self.open_button.pack(side='left')
        self.export_button = ttk.Button(actions, text='Export diagnostic report', command=self.export, state='disabled')
        self.export_button.pack(side='right')
        self.progress = ttk.Progressbar(actions, mode='indeterminate', length=100)
        self.progress.pack(side='right', padx=12)
        # Own the animation timer: ttk's internal Autoincrement timer can
        # survive direct root destruction after its widget command disappears.
        self.progress.bind('<Destroy>', lambda _event: self._stop_progress(), add='+')
        summary = self.summary = tk.Frame(self.frame, padx=16, pady=12)
        summary.grid(row=4, column=0, sticky='ew', pady=(0, 12))
        summary.columnconfigure(0, weight=1)
        self.summary_title = tk.Label(summary, text='A check never changes your save', anchor='w',
                                      font=(family, 13, 'bold'))
        self.summary_title.grid(row=0, column=0, sticky='ew')
        self.summary_status = tk.Label(summary, textvariable=self.status, anchor='w', justify='left',
                                       font=(family, 10), wraplength=1000)
        self.summary_status.grid(row=1, column=0, sticky='ew', pady=(4, 0))
        self._wrapped.append(self.summary_status)
        self.counts = tk.Label(summary, text='No diagnostic snapshot', anchor='w', font=(family, 10, 'bold'))
        self.counts.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        body = self.body = ttk.Frame(self.frame)
        body.grid(row=5, column=0, sticky='nsew')
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(body)
        toolbar.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 8))
        toolbar.columnconfigure(1, weight=1)
        ttk.Label(toolbar, text='Find a check', style='Muted.TLabel').grid(row=0, column=0, padx=(0, 8))
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search)
        self.search_entry.grid(row=0, column=1, sticky='ew')
        self.search_entry.bind('<Escape>', lambda _event: self.search.set(''))
        self.filter_selector = ttk.Combobox(toolbar, textvariable=self.filter,
            values=('All checks', 'Needs attention', 'Passed', 'Not established'), state='readonly', width=20)
        self.filter_selector.grid(row=0, column=2, padx=(10, 0))
        viewport = ttk.Frame(body)
        viewport.grid(row=1, column=0, sticky='nsew')
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(viewport, highlightthickness=0)
        self.canvas._decorative = True
        self.canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(viewport, orient='vertical', command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.card_frame = tk.Frame(self.canvas)
        self.card_frame.columnconfigure(0, weight=1)
        self._canvas_window = self.canvas.create_window(0, 0, anchor='nw', window=self.card_frame)
        self.card_frame.bind('<Configure>', lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', self._canvas_resize)
        self.canvas.bind('<MouseWheel>', self._wheel)
        self.canvas.bind('<Button-4>', lambda _event: self.canvas.yview_scroll(-3, 'units'))
        self.canvas.bind('<Button-5>', lambda _event: self.canvas.yview_scroll(3, 'units'))
        detail_frame = self.detail_frame = ttk.Frame(body, padding=(18, 0, 0, 0))
        detail_frame.grid(row=1, column=1, sticky='nsew')
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1)
        self.detail_title = tk.StringVar(root, value='What does this check mean?')
        self.detail_heading = ttk.Label(detail_frame, textvariable=self.detail_title,
                                        style='Section.TLabel', wraplength=320)
        self.detail_heading.grid(row=0, column=0, sticky='ew', pady=(2, 8))
        self.detail = tk.Text(detail_frame, wrap='word', relief='flat', padx=13, pady=13,
                              width=32, height=8, font=(family, 10), state='disabled', takefocus=True)
        self.detail.grid(row=1, column=0, sticky='nsew')
        detail_scroll = ttk.Scrollbar(detail_frame, orient='vertical', command=self.detail.yview)
        detail_scroll.grid(row=1, column=1, sticky='ns')
        self.detail.configure(yscrollcommand=detail_scroll.set)
        self._set_detail('Select a finding to read its evidence and next steps.\n\n'
                         'Save Doctor does not repair, normalize, grant progress, change signing metadata, '
                         'or replace native game-load testing. Original save bytes stay untouched.')
        footer = ttk.Label(self.frame, text='Keep original companion metadata beside console exports. '
                           'Reports omit private paths, filenames, hashes, account context and save values.',
                           style='Muted.TLabel', wraplength=1000)
        footer.grid(row=6, column=0, sticky='ew', pady=(12, 0))
        self._wrapped.append(footer)
        self.controls = (self.selector, self.file_entry, self.browse_button, self.check_button)
        for variable in (self.game, self.path):
            variable.trace_add('write', self.invalidate)
        for variable in (self.search, self.filter):
            variable.trace_add('write', self.refresh_findings)
        self.frame.bind('<Configure>', self._resize)
        self.frame.bind('<Destroy>', self._destroyed, add='+')
        self.apply_theme(self.palette)
        self.refresh_findings()

    def _set_detail(self, text):
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', text)
        self.detail.configure(state='disabled')

    def _resize(self, event):
        if event.widget is not self.frame:
            return
        for label in self._wrapped:
            label.configure(wraplength=max(180, event.width - 85))
        self.detail_heading.configure(wraplength=max(180, self.detail_frame.winfo_width() - 30))

    def _canvas_resize(self, event):
        self.canvas.itemconfigure(self._canvas_window, width=event.width)
        for label in self._cards:
            label.configure(wraplength=max(100, event.width - 44))

    def _wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def apply_theme(self, palette):
        self.palette = palette
        for widget in (self.summary, self.card_frame, self.canvas):
            widget.configure(background=palette['surface'] if widget is self.summary else palette['background'])
        for label in (self.summary_title, self.summary_status, self.counts):
            label.configure(background=palette['surface'], foreground=palette['text'])
        self.summary_status.configure(foreground=palette['muted'])
        self.detail.configure(background=palette['surface'], foreground=palette['text'],
                              insertbackground=palette['text'], selectbackground=palette['accent'],
                              selectforeground='#ffffff')
        self.refresh_findings()

    def focus_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, 'end')
        return 'break'

    def has_pending_work(self):
        # Read-only checks/open requalification are cancellable on app close.
        return self.busy and self._operation == 'export'

    def _destroyed(self, event):
        if event.widget is self.frame:
            self.close()

    def close(self):
        self._closed = True
        self._cancel.set()
        self._stop_progress()
        if self._poll_id is not None:
            try:
                self.root.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

    def _stop_progress(self):
        if self._animation_id is not None:
            try:
                self.root.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None

    def _animate_progress(self):
        self._animation_id = None
        if not self._closed and self.busy:
            self.progress.step(4)
            self._animation_id = self.root.after(60, self._animate_progress)

    def invalidate(self, *_args):
        self._revision += 1
        self._cancel.set()
        self.prepared, self._selected = None, None
        self.status.set('Selection changed. Check the copied save again.')
        self.summary_title.configure(text='No current diagnostic snapshot')
        self.counts.configure(text='No diagnostic snapshot')
        self._set_detail('Selection changed. Run a new check to inspect findings for the selected copy.')
        self._buttons()
        self.refresh_findings()

    def _buttons(self):
        for control in self.controls:
            control.configure(state=('disabled' if self.busy else
                                     'readonly' if control is self.selector else 'normal'))
        self.cancel_button.configure(state='normal' if self.busy and self._operation != 'export' else 'disabled')
        self.export_button.configure(state='normal' if not self.busy and self.prepared is not None else 'disabled')
        self.open_button.configure(state='normal' if not self.busy and self.on_open is not None
                                   and self.prepared is not None and self.prepared.qualified else 'disabled')

    def refresh_findings(self, *_args):
        if self._closed:
            return
        for child in self.card_frame.winfo_children():
            child.destroy()
        self._cards = []
        findings = () if self.prepared is None else self.prepared.findings
        query, choice = self.search.get().casefold().split(), self.filter.get()
        visible = []
        for item in findings:
            haystack = ' '.join((item.code, item.title, item.detail, item.guidance, STATE_LABELS[item.state])).casefold()
            if not all(token in haystack for token in query):
                continue
            if choice == 'Needs attention' and item.state not in ('failed', 'warning', 'cancelled'):
                continue
            if choice == 'Passed' and item.state != 'passed':
                continue
            if choice == 'Not established' and item.state != 'unknown':
                continue
            visible.append(item)
        self.visible_findings = tuple(visible)
        if not visible:
            empty = tk.Label(self.card_frame, text='No matching checks.' if findings else 'Your diagnostic cards will appear here.',
                             anchor='w', justify='left', padx=14, pady=20,
                             background=self.palette['background'], foreground=self.palette['muted'])
            empty.grid(row=0, column=0, sticky='ew')
        for row, item in enumerate(visible):
            card = tk.Frame(self.card_frame, background=self.palette['surface'], padx=14, pady=11,
                            highlightbackground=self.palette['accent'] if item.code == self._selected else self.palette['border'],
                            highlightthickness=1)
            card.grid(row=row, column=0, sticky='ew', pady=(0, 8))
            card.columnconfigure(0, weight=1)
            badge = tk.Label(card, text=STATE_LABELS[item.state].upper(), anchor='w',
                              font=(self._font_family, 8, 'bold'), background=self.palette['surface'],
                              foreground=self.palette['text'] if item.state == 'passed' else self.palette['muted'])
            badge.grid(row=0, column=0, sticky='ew')
            button = tk.Button(card, text=item.title, anchor='w', justify='left', relief='flat', borderwidth=0,
                               font=(self._font_family, 11, 'bold'), padx=0, pady=5,
                               background=self.palette['surface'], foreground=self.palette['text'],
                               activebackground=self.palette['hover'], activeforeground=self.palette['text'],
                               command=lambda finding=item: self.select_finding(finding))
            button.grid(row=1, column=0, sticky='ew')
            text = tk.Label(card, text=item.detail, anchor='w', justify='left',
                             font=(self._font_family, 9), background=self.palette['surface'],
                             foreground=self.palette['muted'], wraplength=max(100, self.canvas.winfo_width() - 44))
            text.grid(row=2, column=0, sticky='ew')
            self._cards.extend((button, text))
            for widget in (card, badge, button, text):
                widget.bind('<MouseWheel>', self._wheel)
                widget.bind('<Button-4>', lambda _event: self.canvas.yview_scroll(-3, 'units'))
                widget.bind('<Button-5>', lambda _event: self.canvas.yview_scroll(3, 'units'))
            for widget in (card, badge, text):
                widget.bind('<Button-1>', lambda _event, finding=item: self.select_finding(finding))

    def select_finding(self, finding):
        self._selected = finding.code
        self.detail_title.set(finding.title)
        self._set_detail(STATE_LABELS[finding.state] + '\n\n' + finding.detail +
                         ('\n\nNext steps\n' + finding.guidance if finding.guidance else '') +
                         '\n\nDiagnostic code: ' + finding.code)
        self.refresh_findings()

    def browse(self):
        if self.busy:
            return
        game_id = self._games.get(self.game.get())
        game = next((game for game in backend.DOCTOR_GAMES if game.id == game_id), None)
        extension = game.extension if game else '*'
        selected = filedialog.askopenfilename(parent=self.root, title='Choose a separate copied gameplay file',
                      filetypes=(('Copied gameplay file', '*' + extension), ('All files', '*.*')))
        if selected:
            self.path.set(selected)

    def cancel(self):
        if self.busy and self._operation != 'export':
            self._cancel.set()
            self.cancel_button.configure(state='disabled')
            self.status.set('Cancelling after the current bounded/native operation…')

    def _start(self, operation, function):
        if self.busy or self._closed:
            return
        self.busy, self._operation = True, operation
        self._cancel = threading.Event()
        event, revision = self._cancel, self._revision
        self._animate_progress()
        self._buttons()
        def worker():
            try:
                value, failed = function(event), False
            except Exception:
                value, failed = None, True
            self._results.put((revision, event, operation, value, failed))
        threading.Thread(target=worker, daemon=True, name='SaveDoctor-' + operation).start()
        self._poll_id = self.root.after(35, self._poll)

    def _poll(self):
        self._poll_id = None
        if self._closed:
            return
        try:
            revision, event, operation, value, failed = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.root.after(35, self._poll)
            return
        self.busy, self._operation = False, ''
        self._stop_progress()
        if revision != self._revision:
            self.status.set('Selection changed. Check the copied save again.')
        elif event.is_set():
            self.prepared = None
            self.status.set('Check cancelled. No partial result authorizes opening.')
        elif failed:
            if operation != 'export':
                self.prepared = None
            self.status.set('Operation could not finish. Check the stable copied file, its original context, and access permissions.')
            messagebox.showerror('Save Doctor', 'The operation could not finish safely. '
                                 'No gameplay file was changed. Diagnose again before opening.', parent=self.root)
        elif operation == 'diagnose':
            self.prepared = value
            titles = {'qualified': 'Native copy qualified', 'attention': 'Qualified with compatibility warnings',
                      'rejected': 'Copy did not qualify', 'unsafe': 'Choose a safe separate copy',
                      'unreadable': 'Copy could not be read', 'changed': 'Copy changed during checking',
                      'cancelled': 'Check cancelled', 'incomplete': 'Evidence is incomplete'}
            self.summary_title.configure(text=titles[value.status])
            self.status.set('Historical file-level snapshot. Review each finding; opening always rechecks the copy and its original context.')
            counts = {state: sum(item.state == state for item in value.findings) for state in STATE_LABELS}
            self.counts.configure(text=f'{counts["passed"]} passed  ·  '
                                  f'{counts["failed"] + counts["warning"]} need attention  ·  '
                                  f'{counts["unknown"]} not established')
            important = next((item for item in value.findings if item.state in ('failed', 'warning')), value.findings[0])
            self.select_finding(important)
        elif operation == 'open':
            try:
                accepted = self.on_open(self.prepared.game_id, value)
            except Exception:
                self.status.set('The normal editor could not finish opening this copy. Use the editor Open command to retry.')
            else:
                self.status.set('Qualified copy sent through the normal editor open workflow.' if accepted is not False
                                else 'Editor kept its current session. The diagnosed copy was not opened.')
        elif operation == 'export':
            self.status.set('Privacy-safe historical diagnostic report exported to a new file.')
        self._buttons()
        self.refresh_findings()

    def diagnose(self):
        game_id, selected = self._games.get(self.game.get()), self.path.get().strip()
        if self.busy or self._closed:
            return
        if game_id is None or not selected:
            self.status.set('Choose an exact game/platform and an existing separate gameplay-file copy.')
            return
        self.prepared, self._selected = None, None
        self.summary_title.configure(text='Checking your copied save…')
        self.status.set('Bounded native checks run in a background worker. No backup, repair or save write is performed.')
        self.counts.configure(text='Checking…')
        self.refresh_findings()
        self._start('diagnose', lambda event: backend.diagnose(game_id, Path(selected), cancel=event))

    def open_copy(self):
        if self.busy or self.prepared is None or not self.prepared.qualified or self.on_open is None:
            return
        result = self.prepared
        self.status.set('Rechecking the complete copied snapshot and original context before opening…')
        self._start('open', lambda event: backend.requalify(result, cancel=event))

    def export(self):
        if self.busy or self.prepared is None:
            return
        selected = filedialog.asksaveasfilename(parent=self.root, title='Export privacy-safe Save Doctor report',
                    defaultextension='.doctor.json', initialfile='SaveDoctor-report.doctor.json',
                    filetypes=(('Diagnostic report', '*.doctor.json'),))
        if not selected:
            return
        result = self.prepared
        self.status.set('Writing the diagnostic report atomically to a new file…')
        self._start('export', lambda _event: backend.export_report(result, Path(selected)))

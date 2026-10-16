"""Compact keyboard-accessible navigation for retained application workspaces."""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class WorkspaceAction:
    id: str
    title: str
    description: str
    command: object


class WorkspaceMenu:
    """A bounded two-column tool palette; actions retain their public buttons."""

    def __init__(self, root, actions, auto_capture=None, capture_status=None):
        self.root = root
        self.actions = tuple(actions)
        self.buttons = {}
        self._focus_job = None
        self._previous_focus = None
        self._anchor = None
        # An in-window overlay keeps focus and shortcuts in the application and
        # creates no hidden dialog/window when the application starts.
        self.window = tk.Frame(root, borderwidth=1, relief='solid')
        self.frame = ttk.Frame(self.window, padding=16, relief='solid', borderwidth=1)
        self.frame.pack(fill='both', expand=True)
        self.frame.columnconfigure((0, 1), weight=1)
        heading = ttk.Frame(self.frame)
        heading.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 12))
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text='Your save workspace', style='Section.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Button(heading, text='Close', width=6, command=self.dismiss).grid(row=0, column=1)
        for index, action in enumerate(self.actions):
            cell = ttk.Frame(self.frame, padding=(0, 5, 12, 8))
            cell.grid(row=1 + index // 2, column=index % 2, sticky='nsew')
            button = ttk.Button(cell, text=action.title, width=23,
                                command=lambda entry=action: self._invoke(entry))
            button.pack(anchor='w', fill='x')
            ttk.Label(cell, text=action.description, style='Muted.TLabel',
                      wraplength=244, justify='left').pack(anchor='w', pady=(5, 0))
            self.buttons[action.id] = button
            button.bind('<Up>', lambda _event, i=index: self._focus_action(i - 2))
            button.bind('<Down>', lambda _event, i=index: self._focus_action(i + 2))
            button.bind('<Left>', lambda _event, i=index: self._focus_action(i - 1))
            button.bind('<Right>', lambda _event, i=index: self._focus_action(i + 1))
        footer_row = 1 + (len(self.actions) + 1) // 2
        ttk.Separator(self.frame).grid(row=footer_row, column=0, columnspan=2, sticky='ew', pady=(4, 10))
        if auto_capture is not None:
            ttk.Checkbutton(self.frame, text='Capture opened and saved copies in Save Vault this session',
                            variable=auto_capture).grid(row=footer_row + 1, column=0, columnspan=2, sticky='w')
            ttk.Label(self.frame, text='Off by default. Validated copies only; pending edits stay in the editor.',
                      style='Muted.TLabel', wraplength=500).grid(row=footer_row + 2, column=0, columnspan=2,
                                                               sticky='w', pady=(3, 0))
        if capture_status is not None:
            ttk.Label(self.frame, textvariable=capture_status, style='Muted.TLabel',
                      wraplength=500).grid(row=footer_row + 3, column=0, columnspan=2, sticky='w', pady=(5, 0))
        self.window.bind('<Escape>', self.dismiss)
        self.window.bind('<Destroy>', self._destroyed, add='+')
        self._outside_binding = root.bind('<Button-1>', self._outside_click, add='+')
        self._escape_binding = root.bind('<Escape>', self._escape, add='+')
        self._focus_binding = root.bind('<FocusOut>', self._focus_left, add='+')

    @property
    def visible(self):
        return bool(self.window.winfo_viewable())

    def toggle(self, anchor):
        if self.visible:
            self.dismiss()
        else:
            self.show(anchor)

    def show(self, anchor):
        self._previous_focus = self.root.focus_get()
        self._anchor = anchor
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        x = min(anchor.winfo_rootx() - self.root.winfo_rootx(),
                max(0, self.root.winfo_width() - width - 8))
        y = min(anchor.winfo_rooty() - self.root.winfo_rooty() + anchor.winfo_height() + 5,
                max(0, self.root.winfo_height() - height - 8))
        self.window.place(x=max(0, x), y=max(0, y))
        self.window.lift()
        self._focus_action(0)

    def _focus_action(self, index):
        if self.actions:
            self.buttons[self.actions[max(0, min(len(self.actions) - 1, index))].id].focus_set()
        return 'break'

    def _invoke(self, action):
        self.dismiss(restore_focus=False)
        action.command()

    def dismiss(self, _event=None, restore_focus=True):
        self.window.place_forget()
        if restore_focus and self._previous_focus is not None:
            try:
                if self._previous_focus.winfo_exists():
                    self._previous_focus.focus_set()
            except tk.TclError:
                pass
        return 'break'

    def _focus_left(self, _event=None):
        if not self.visible:
            return
        if self._focus_job is not None:
            self.window.after_cancel(self._focus_job)
        self._focus_job = self.window.after_idle(self._check_focus)

    def _check_focus(self):
        self._focus_job = None
        focus = self.root.focus_get()
        while focus is not None:
            if focus is self.window:
                return
            focus = getattr(focus, 'master', None)
        self.dismiss(restore_focus=False)

    def _outside_click(self, event):
        if not self.visible:
            return
        if event.widget is self._anchor:
            return
        widget = event.widget
        while widget is not None:
            if widget is self.window:
                return
            widget = getattr(widget, 'master', None)
        self.dismiss(restore_focus=False)

    def _escape(self, event):
        return self.dismiss(event) if self.visible else None

    def apply_theme(self, palette):
        self.window.configure(background=palette['border'])

    def _destroyed(self, event):
        if event.widget is self.window:
            if self._focus_job is not None:
                self.window.after_cancel(self._focus_job)
                self._focus_job = None
            for event_name, binding in (('<Button-1>', self._outside_binding),
                                         ('<Escape>', self._escape_binding),
                                         ('<FocusOut>', self._focus_binding)):
                self.root.unbind(event_name, binding)

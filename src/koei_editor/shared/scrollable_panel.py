"""A scoped vertical viewport for long global forms, preserving their state."""
import tkinter as tk
from tkinter import ttk


class ScrollablePanel:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.frame, width=1, height=1, highlightthickness=0,
                                takefocus=False, borderwidth=0,
                                background=ttk.Style(parent).lookup('TFrame', 'background'))
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.scrollbar = ttk.Scrollbar(self.frame, orient='vertical', command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky='ns')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window(0, 0, anchor='nw', window=self.content)
        self._tag = f'GlobalPanelScroll:{id(self)}'
        self._pending = None
        self._focus_pending = None
        self.canvas.bind('<Configure>', self._schedule)
        self.content.bind('<Configure>', self._schedule)
        self.frame.bind('<Destroy>', self._destroy, add='+')
        for event in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.frame.bind_class(self._tag, event, self._wheel)
        self.frame.bind_class(self._tag, '<FocusIn>', self._focus)
        self.frame.bind_class(self._tag, '<Configure>', self._schedule)
        self.frame.bind_class(self._tag, '<Prior>', lambda event: self._page(event, -1))
        self.frame.bind_class(self._tag, '<Next>', lambda event: self._page(event, 1))
        self.frame.bind_class(self._tag, '<Control-Home>', lambda event: self._edge(event, 0))
        self.frame.bind_class(self._tag, '<Control-End>', lambda event: self._edge(event, 1))

    def _schedule(self, _event=None):
        if self._pending is None:
            self._pending = self.frame.after_idle(self.refresh)

    def refresh(self):
        if self._pending is not None:
            self.frame.after_cancel(self._pending)
        self._pending = None
        if not self.frame.winfo_exists():
            return
        width = max(1, self.canvas.winfo_width())
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        self.canvas.itemconfigure(self._window, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        pending = [self.content, self.canvas]
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            tags = widget.bindtags()
            if self._tag not in tags:
                widget.bindtags((tags[0], self._tag, *tags[1:]))

    @staticmethod
    def _has_own_scroll(widget):
        return isinstance(widget, (tk.Text, tk.Listbox, ttk.Treeview, ttk.Combobox))

    def apply_theme(self, palette):
        self.canvas.configure(background=palette['background'])

    def _wheel(self, event):
        if self._has_own_scroll(event.widget) or self.canvas.yview() == (0.0, 1.0):
            return
        number = getattr(event, 'num', None)
        if number in (4, 5):
            units = -1 if number == 4 else 1
        else:
            delta = getattr(event, 'delta', 0)
            if not delta:
                return
            units = -int(delta / 120) or (-1 if delta > 0 else 1)
        self.canvas.yview_scroll(units, 'units')
        return 'break'

    def _page(self, event, direction):
        if self._has_own_scroll(event.widget):
            return
        self.canvas.yview_scroll(direction, 'pages')
        return 'break'

    def _edge(self, event, fraction):
        if self._has_own_scroll(event.widget):
            return
        self.canvas.yview_moveto(fraction)
        return 'break'

    def _focus(self, event):
        if self._focus_pending is not None:
            self.frame.after_cancel(self._focus_pending)
        self._focus_pending = self.frame.after_idle(lambda: self.reveal(event.widget))

    def reveal(self, widget):
        self._focus_pending = None
        if not widget.winfo_exists() or not self.frame.winfo_ismapped():
            return
        top = widget.winfo_rooty() - self.content.winfo_rooty()
        bottom = top + widget.winfo_height()
        visible_top = self.canvas.canvasy(0)
        visible_bottom = visible_top + self.canvas.winfo_height()
        height = max(1, self.content.winfo_height())
        if top - 8 < visible_top:
            self.canvas.yview_moveto(max(0, top - 8) / height)
        elif bottom + 8 > visible_bottom:
            self.canvas.yview_moveto((bottom + 8 - self.canvas.winfo_height()) / height)

    def _destroy(self, event):
        if event.widget is not self.frame:
            return
        for callback in (self._pending, self._focus_pending):
            if callback is not None:
                self.frame.after_cancel(callback)
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>', '<FocusIn>', '<Configure>',
                         '<Prior>', '<Next>', '<Control-Home>', '<Control-End>'):
            self.frame.unbind_class(self._tag, sequence)

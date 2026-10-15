"""Shared appearance for the application and game-specific editors."""
import tkinter as tk
from tkinter import font
from tkinter import ttk
import koei_editor.shared.preferences as preferences


def ui_font(root):
    families = {name.lower() for name in font.families(root)}
    return 'Segoe UI' if 'segoe ui' in families else 'Helvetica'

THEMES = {
    'Light': {
        'background': '#f3f5f7', 'surface': '#ffffff', 'text': '#243142',
        'muted': '#586879', 'border': '#d8dfe6', 'hover': '#e7ecf1',
        'disabled': '#edf0f3', 'disabled_text': '#7b8590',
        'accent': '#92353b', 'accent_hover': '#76282e', 'tab_text': '#92353b',
    },
    'Dark': {
        'background': '#18212d', 'surface': '#232f3e', 'text': '#e9eef5',
        'muted': '#b4c1d0', 'border': '#405065', 'hover': '#2e3c4f',
        'disabled': '#293444', 'disabled_text': '#8b9bad',
        'accent': '#a83c46', 'accent_hover': '#bb4953', 'tab_text': '#efacaf',
    },
}


class Appearance:
    def apply_theme(self, name):
        """Change appearance without rebuilding forms or touching pending edits."""
        if name not in THEMES:
            raise ValueError('Unsupported appearance.')
        previous = getattr(self, '_applied_theme', None)
        palette = THEMES[name]
        self.font_family = ui_font(self.root)
        self.theme_name.set(name)
        style = self.style
        style.configure('.', font=(self.font_family, 10), background=palette['background'],
                        foreground=palette['text'], bordercolor=palette['border'],
                        lightcolor=palette['border'], darkcolor=palette['border'],
                        troughcolor=palette['background'])
        style.configure('TButton', padding=(9, 6), background=palette['surface'])
        style.map('TButton', background=[('disabled', palette['disabled']), ('active', palette['hover'])],
                  foreground=[('disabled', palette['disabled_text'])])
        style.configure('Primary.TButton', background=palette['accent'], foreground='#ffffff')
        style.map('Primary.TButton', background=[('disabled', palette['disabled']), ('active', palette['accent_hover'])],
                  foreground=[('disabled', palette['disabled_text']), ('!disabled', '#ffffff')])
        style.configure('TNotebook', tabmargins=(0, 5, 0, 0))
        style.configure('TNotebook.Tab', padding=(12, 7))
        style.map('TNotebook.Tab', background=[('selected', palette['surface']), ('active', palette['hover'])],
                  foreground=[('selected', palette['tab_text'])])
        style.configure('Section.TLabel', font=(self.font_family, 11, 'bold'))
        style.configure('Muted.TLabel', foreground=palette['muted'])
        style.configure('Header.TFrame', background='#202a37')
        style.configure('Header.TLabel', background='#202a37', foreground='#d2d9e2', font=(self.font_family, 9))
        style.configure('TLabelframe', relief='solid')
        style.configure('TLabelframe.Label', font=(self.font_family, 11, 'bold'))
        for fieldstyle in ('TEntry', 'TCombobox', 'TSpinbox'):
            style.configure(fieldstyle, fieldbackground=palette['surface'], foreground=palette['text'],
                            background=palette['surface'], insertcolor=palette['text'], padding=5,
                            selectbackground=palette['accent'], selectforeground='#ffffff')
            style.map(fieldstyle,
                      fieldbackground=[('disabled', palette['disabled']), ('readonly', palette['surface'])],
                      foreground=[('disabled', palette['disabled_text']), ('readonly', palette['text'])])
        for control in ('TCheckbutton', 'TRadiobutton'):
            style.map(control, background=[('active', palette['background'])],
                      foreground=[('disabled', palette['disabled_text'])],
                      indicatorbackground=[('disabled', palette['disabled']), ('selected', palette['accent']),
                                           ('!selected', palette['surface'])])
        style.configure('Treeview', rowheight=29, background=palette['surface'], fieldbackground=palette['surface'])
        style.configure('Treeview.Heading', font=(self.font_family, 10, 'bold'), background=palette['hover'], padding=(6, 7))
        style.map('Treeview.Heading', background=[('active', palette['border'])])
        style.map('Treeview', background=[('selected', palette['accent'])], foreground=[('selected', '#ffffff')])
        style.configure('TScrollbar', background=palette['hover'], arrowcolor=palette['muted'])
        style.map('TScrollbar', background=[('active', palette['border'])])
        self.root.option_add('*TCombobox*Listbox.background', palette['surface'])
        self.root.option_add('*TCombobox*Listbox.foreground', palette['text'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', palette['accent'])
        self.root.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        self.theme_widgets(self.root)
        self._applied_theme = name
        if getattr(self, '_persist_theme', False) and previous is not None and previous != name:
            preferences.save_theme(name, getattr(self, 'preferences_path', None))

    def theme_widgets(self, parent):
        """Apply colors to the small number of widgets outside ttk's styling."""
        palette = THEMES[self.theme_name.get()]
        stack = [parent]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if isinstance(widget, (tk.Tk, tk.Toplevel, tk.Canvas)) and not getattr(widget, '_decorative', False):
                widget.configure(background=palette['background'])
            elif isinstance(widget, tk.Text):
                widget.configure(background=palette['surface'], foreground=palette['text'],
                                 insertbackground=palette['text'], selectbackground=palette['accent'],
                                 selectforeground='#ffffff')
            elif isinstance(widget, ttk.Treeview) and getattr(widget, '_pending_edits_style', False):
                widget.tag_configure('pending', background=palette['hover'], foreground=palette['text'])
            elif isinstance(widget, ttk.Combobox):
                # Tk keeps dropdown listboxes after their first use. The option
                # database covers new ones; recolor any already-created popup.
                listbox = f'{widget}.popdown.f.l'
                if widget.tk.call('winfo', 'exists', listbox):
                    widget.tk.call(listbox, 'configure', '-background', palette['surface'],
                                   '-foreground', palette['text'], '-selectbackground', palette['accent'],
                                   '-selectforeground', '#ffffff')

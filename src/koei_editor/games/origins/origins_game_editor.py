"""Origins presentation; all decoding and writing live in origins_parser."""
from tkinter import messagebox, simpledialog, ttk

import koei_editor.games.origins.origins_parser as backend
from koei_editor.games.origins.origins_presentation import OriginsPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor
from koei_editor.shared.experimental_limits import experimental_operation


class Editor(ScalarEditor):
    game_id = 'origins'
    backend = backend
    presentation_type = OriginsPresentation
    subtitle = 'Steam PC slot saves · native revisions 16, 17 and 29'
    summary = ('Edit Gold, Skill Points, existing bonds, provincial peace and eligible '
               'weapon upgrades up to +99. Battle clear history is separate from your '
               'current campaign. Choose a category or search for a field, review '
               'your changes and use Save As. Open a copied SLOT0000–SLOT0008.dat; '
               'USER.dat is system data.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tools = ttk.Frame(self.edit_page, padding=(18, 0, 18, 6))
        tools.pack(fill='x', before=self.bulk_bar)
        self.peace_button = ttk.Button(tools, text='Set Peace %...',
                                       command=self.set_peace_percent, state='disabled')
        self.peace_button.pack(side='left', padx=(0, 8))
        self.training_button = ttk.Button(tools, text='Training Count at Least 3',
                                          command=self.meet_training_count, state='disabled')
        self.training_button.pack(side='left')
        ttk.Label(tools, text='Selected peace or training fields only; reward claims stay separate.',
                  style='Muted.TLabel').pack(side='left', padx=12)

    def selected(self, event=None):
        super().selected(event)
        if not hasattr(self, 'peace_button'):
            return
        keys = self.fields.selection() if self.document else ()
        self.peace_button.configure(state='normal' if keys and all(
            key.startswith('peace_') for key in keys) else 'disabled')
        self.training_button.configure(state='normal' if keys and all(
            key.startswith('bond_') and key.endswith('_training') for key in keys) else 'disabled')

    @experimental_operation
    def set_peace_percent(self):
        if self.document is None:
            return
        keys = self.fields.selection()
        if not keys:
            return
        percent = simpledialog.askstring(
            'Provincial Peace', 'Peace percentage (0–100; up to two decimal places).\n'
            'Applies to the selected provinces. Reward claims remain unchanged.', parent=self.root)
        if percent is None:
            return
        try:
            values = backend.peace_percent_values(self.document, self.changes, keys, percent)
            self.stage_values(values)
        except Exception as error:
            messagebox.showerror('Cannot Set Provincial Peace', str(error))

    @experimental_operation
    def meet_training_count(self):
        if self.document is None:
            return
        try:
            values = backend.bond_training_values(self.document, self.changes, self.fields.selection())
            self.stage_values(values)
            self.status.set(f'{len(self.changes)} pending edits. Training count condition only; '
                            'bond events, learned arts and rewards remain separate.')
        except Exception as error:
            messagebox.showerror('Cannot Set Training Count', str(error))

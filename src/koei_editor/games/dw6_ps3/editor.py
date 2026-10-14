"""Original US PS3 DW6 workspace with shared staging, review and safe copying."""
from koei_editor.games.dw6_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor
from koei_editor.games.dw6.dw6_editor import DW6Presentation
from tkinter import ttk


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = DW6Presentation
    save_extension = '.bin'
    subtitle = 'Original US PS3 · BLUS30110 · decrypted APP.BIN'
    summary = ('Named playable unlocks, equipment skills, horse stats/elements and own-inventory weapon selection. '
               'Keep original PARAM.SFO. Reimport and resign with Apollo Save Tool.')

    def __init__(self, root, parent=None, theme='Light', on_theme=None):
        super().__init__(root, parent, theme, on_theme)
        content = ttk.Frame(parent if parent is not None else root, padding=(22, 4))
        content.pack(fill='x', before=self.search_entry.master)
        self.unlock_button = ttk.Button(content, text='Unlock All Qualified Officers', command=self.unlock_all, state='disabled')
        self.unlock_button.pack(side='left')
        self.edit_buttons.append(self.unlock_button)
        ttk.Label(content, text='Content unlock action; story progression stays unchanged.', style='Muted.TLabel').pack(side='left', padx=12)

    def unlock_all(self):
        if self.document is not None:
            self.stage_values(self.backend.unlock_values(self.document))

"""Named DW6 PC unlocks, horse stats and existing weapon element choices."""
from tkinter import Menu, ttk

from koei_editor.games.dw6 import dw6_parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class DW6Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        rows = self.backend.inspection_rows(document)
        notes = {'Officers': 'Level, EXP, title, outfit, kills and skill-tree dependencies remain read only.',
                 'Weapons': 'Search by officer, weapon name or ID. Choose the element of an existing known weapon; manual stored damage bonuses and named skill toggles are also editable. Select an equipped weapon from the same officer’s existing inventory.',
                 'Horses': 'Qualified existing combat stats, named skill toggles and elements are writable. EXP, type and growth descriptors remain read only.'}
        return tuple(InspectionTable(group, ('Record', 'Opened data'),
                                     tuple((row['label'], row['value']) for row in rows if row['group'] == group),
                                     notes[group]) for group in notes)


class Editor(ScalarEditor):
    game_id = 'dw6'
    save_extension = '.dat'
    backend = dw6_parser
    presentation_type = DW6Presentation
    subtitle = 'Windows PC save editor'
    summary = 'Playable officers, Free Mode stages and Musou availability; horse stats/elements, weapon bonuses/skills and own-inventory weapon selection. Completion and officer growth stay separate.'

    def __init__(self, root, parent=None, theme='Light', on_theme=None):
        super().__init__(root, parent, theme, on_theme)
        host = parent if parent is not None else root
        content = ttk.Frame(host, padding=(22, 4))
        content.pack(fill='x', before=self.search_entry.master)
        self.unlock_button = ttk.Button(content, text='Unlock All Qualified Officers',
                                        command=self.unlock_all, state='disabled')
        self.unlock_button.pack(side='left')
        self.edit_buttons.append(self.unlock_button)
        self.more_unlocks = ttk.Menubutton(content, text='More unlocks', state='disabled')
        menu = Menu(self.more_unlocks, tearoff=False)
        menu.add_command(label='Unlock All Stages', command=self.unlock_stages)
        menu.add_command(label='Unlock All Musou Modes', command=self.unlock_musou)
        self.more_unlocks.configure(menu=menu)
        self.more_unlocks.pack(side='left', padx=(8, 0))
        self.edit_buttons.append(self.more_unlocks)
        ttk.Label(content, text='Availability only; completion and battle history stay unchanged.',
                  style='Muted.TLabel').pack(side='left', padx=12)

    def unlock_all(self):
        if self.document is not None:
            self.stage_values(self.backend.unlock_values(self.document))

    def unlock_stages(self):
        if self.document is not None:
            self.stage_values(self.backend.stage_unlock_values(self.document))

    def unlock_musou(self):
        if self.document is not None:
            self.stage_values(self.backend.musou_unlock_values(self.document))


def read_save(path):
    return dw6_parser.read_save(path)

"""Original DOA5 PS3 costume workspace with shared safe copied-save operations."""
from koei_editor.games.doa5_ps3 import parser
from koei_editor.games.doa5_ps3.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.dat'
    subtitle = 'Original US/EU PSN PS3 SAVE_SYS.DAT; original PARAM.SFO required'
    summary = ('Unlock source-backed original costume flags and search their records. '
               'Character ownership, story, titles and paid DLC remain unchanged. '
               'Native integrity, backups, Undo and Review Changes are maintained.')


def read_save(path):
    return parser.read_save(path)

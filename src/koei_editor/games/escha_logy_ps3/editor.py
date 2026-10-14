"""Original EU PSN Escha & Logy scalar workspace."""
from koei_editor.games.escha_logy_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = ''
    subtitle = 'Original EU PS3 PSN · NPEB01945 · USR-DATA'
    summary = 'Manual Cole editing and read-only named character/alchemy inspection. Original PARAM.SFO required; assignments and calendar stay unchanged.'

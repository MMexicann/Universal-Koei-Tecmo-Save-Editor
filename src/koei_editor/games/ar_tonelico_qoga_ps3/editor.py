"""US Ar tonelico Qoga scalar workspace."""
from koei_editor.games.ar_tonelico_qoga_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = ''
    subtitle = 'Original US PS3 · BLUS30639 · USR-DATA'
    summary = 'Manual Leaf editing and separate named progression/dive-point inspection. Original PARAM.SFO required; story and system gallery stay unchanged.'

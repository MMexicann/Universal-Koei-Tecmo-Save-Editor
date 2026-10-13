"""One Piece: Pirate Warriors 2 PS3 safe scalar workspace."""
from koei_editor.games.pw2_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    subtitle = 'NPEB01795 · decrypted DATA.BIN + original PARAM.SFO'
    summary = 'Published primary Berry reductions; secondary Berry word inspected separately; use a separate exported save copy.'

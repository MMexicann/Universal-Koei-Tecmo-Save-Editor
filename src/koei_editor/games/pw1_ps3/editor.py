"""One Piece: Pirate Warriors PS3 safe scalar workspace."""
from koei_editor.games.pw1_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    subtitle = 'NPUB30836 · decrypted DATA.BIN + original PARAM.SFO'
    summary = 'Published named character level-growth word reductions; use a separate exported save copy.'

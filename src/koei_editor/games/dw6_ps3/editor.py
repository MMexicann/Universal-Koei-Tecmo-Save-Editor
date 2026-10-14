"""Original US PS3 DW6 workspace with shared staging, review and safe copying."""
from koei_editor.games.dw6_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    subtitle = 'Original US PS3 · BLUS30110 · decrypted APP.BIN'
    summary = ('Existing horse speed, attack, jump and destruction; weapon stored damage bonuses and elements. '
               'Keep original PARAM.SFO. Reimport and resign with Apollo Save Tool.')

"""Original US PS3 DW6 workspace with shared staging, review and safe copying."""
from koei_editor.games.dw6_ps3 import parser
from koei_editor.games.dw6.dw6_editor import Editor as DW6Editor


class Editor(DW6Editor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    subtitle = 'Original US PS3 · BLUS30110 · decrypted APP.BIN'
    summary = ('Playable officers, Free Mode stages and Musou availability; equipment skills, horse stats/elements and own-inventory weapon selection. '
               'Keep original PARAM.SFO. Reimport and resign with Apollo Save Tool.')

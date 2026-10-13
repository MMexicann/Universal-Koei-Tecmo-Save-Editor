"""Original EU PlayStation 3 Bladestorm published resource controls."""
from koei_editor.games.bladestorm_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    subtitle = 'Original European PS3 · BLES00113 · decrypted PLAYDATA copy'
    summary = 'Reduce primary money and existing book SP; inspect secondary money without changing it.'

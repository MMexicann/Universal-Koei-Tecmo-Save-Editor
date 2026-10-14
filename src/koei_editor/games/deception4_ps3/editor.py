"""US PSN Deception IV scalar workspace."""
from koei_editor.games.deception4_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    subtitle = 'Blood Ties · US PS3 PSN · NPUB31442'
    summary = 'Manual Warl editing and separate read-only ability experience. Keep original PARAM.SFO beside decrypted DATA.BIN.'

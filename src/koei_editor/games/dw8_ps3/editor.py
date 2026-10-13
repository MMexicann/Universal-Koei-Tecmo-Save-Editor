"""Original PS3 Dynasty Warriors 8 resource workspace."""
from koei_editor.games.dw8_ps3 import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    subtitle = 'Original US PS3 PSN · NPUB31234 · PFD-decrypted APP.BIN'
    summary = 'Gold and Ambition facility/weapon material reductions; original PARAM.SFO required.'

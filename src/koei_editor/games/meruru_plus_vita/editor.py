"""Dedicated Vita Plus workspace in the common scalar interface."""
from koei_editor.games.meruru_plus_vita import parser
from koei_editor.games.meruru_plus_vita.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = ''
    subtitle = 'PS Vita US decrypted PCSE00296 — save-manager reimport required'
    summary = ('Cole, named base ATK/DEF/speed, base HP/MP/LP increases and current-gauge reductions; searchable '
               'character and numeric inventory inspection. Keep original sce_sys/param.sfo with your copied save.')

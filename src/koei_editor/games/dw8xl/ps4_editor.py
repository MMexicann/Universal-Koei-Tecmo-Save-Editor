"""Common-core CUSA00397 PS4 editing through the bound scalar contract."""
from koei_editor.games.dw8xl import ps4_export as parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    subtitle = 'PlayStation 4 · CUSA00397 · decrypted zero-extension profile'
    summary = ('Resources, 82 officers’ stored stats, weapon-action aptitudes and '
               'existing ranked attributes. Keep original sce_sys/param.sfo beside '
               'opened and saved copies. PS4 reimport/resigning stays external; '
               'edited game loading remains unverified.')

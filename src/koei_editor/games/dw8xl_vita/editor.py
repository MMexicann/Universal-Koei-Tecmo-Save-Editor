"""Vita native export workspace with shared copy-save protection."""
from koei_editor.games.dw8xl_vita import parser
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.dat'
    subtitle = 'PlayStation Vita — exported plaintext MainData00.dat'
    summary = ('Gold, gems, materials, 82 officer records, four weapon-action aptitudes '
               'and existing weapon attribute ranks. Native checksum verification; '
               'reimport the edited copy with your Vita save-management tool.')

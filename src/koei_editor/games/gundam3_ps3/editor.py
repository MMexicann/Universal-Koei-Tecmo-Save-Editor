"""Gundam 3 shared money workspace and searchable native inspection."""
from koei_editor.games.gundam3_ps3 import parser
from koei_editor.shared.scalar_presentation import ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    extra_groups = ('Laboratory', 'Licenses')


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    presentation_type = Presentation
    subtitle = 'PS3 US · decrypted DATA.BIN + original PARAM.SFO · Apollo resign required'
    summary = ('Reduce spendable money; search Mobile Suit Laboratory EXP and license-bit storage. '
               'Undo, Review Changes, backups and Save As are available.')


def read_save(path):
    return parser.read_save(path)

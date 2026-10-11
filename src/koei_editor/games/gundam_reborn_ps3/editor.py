"""Reborn resource workspace with shared searchable scalar inspection."""
from koei_editor.games.gundam_reborn_ps3 import parser
from koei_editor.shared.scalar_presentation import ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    extra_groups = ('Pilots', 'Money history', 'Material storage')


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    presentation_type = Presentation
    subtitle = 'PS3 EU/Japan · decrypted DATA.BIN + PARAM.SFO · Apollo resign required'
    summary = ('Reduce spendable money and existing Amuro/Kamille Team Points. '
               'Search pilot EXP, levels, stat words, lifetime earnings and material storage. '
               'Undo, Review Changes, backups and Save As are available.')


def read_save(path):
    return parser.read_save(path)

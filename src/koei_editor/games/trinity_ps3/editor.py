"""Trinity shared resource workspace and searchable character inspection."""
from koei_editor.games.trinity_ps3 import parser
from koei_editor.shared.scalar_presentation import ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    extra_groups = ('Skill Points', 'Characters')


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.dat'
    presentation_type = Presentation
    subtitle = 'PS3 US · decrypted PLAY.DAT + original PARAM.SFO · Apollo resign required'
    summary = ('Reduce spendable money; search SP storage and Areus, Dagda and Selene stat words. '
               'Undo, Review Changes, backups and Save As are available.')


def read_save(path):
    return parser.read_save(path)

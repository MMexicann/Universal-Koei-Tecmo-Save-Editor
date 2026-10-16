"""Shared copied-save workspace for the qualified original European Troy profile."""
from koei_editor.games.troy_ps3 import parser
from koei_editor.shared.scalar_presentation import ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    extra_groups = ('Music collection', 'Item records')


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = ''
    presentation_type = Presentation
    subtitle = 'European PS3 · populated revision-38 PROFILE + original PARAM.SFO'
    summary = ('Reduce saved Kleos; search native music and item records. '
               'Undo, Review Changes, backups and Save As are available. '
               'PS3 reimport and signing remain external.')


def read_save(path):
    return parser.read_save(path)

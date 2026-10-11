"""Original Steam DQB2 workspace in the common safe scalar interface."""
from koei_editor.games.dqb2_pc import parser
from koei_editor.games.dqb2_pc.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.bin'
    subtitle = 'Original Steam PC — copied CMNDAT.BIN'
    summary = ('Reduce existing named medicine and seed stacks; searchable pockets, bag and '
               'player/equipment status. Keep all other original exported save files together.')

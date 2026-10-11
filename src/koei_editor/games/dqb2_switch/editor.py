"""Explicit original Switch DQB2 editor; no automatic platform conversion."""
from koei_editor.games.dqb2_switch import parser
from koei_editor.games.dqb2_pc.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = parser.EXTENSION
    subtitle = 'Original Nintendo Switch — extracted CMNDAT.BIN'
    summary = ('Reduce existing named medicine and seed stacks; searchable pockets, bag and '
               'player/equipment status. Retain all original slot companions and reimport '
               'through your console save manager.')

"""Ultimate PC workspace using the shared safe editor workflow."""
from koei_editor.games.wo4_ultimate import parser
from koei_editor.games.wo4_ultimate.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.bin'
    subtitle = 'Windows PC — Ultimate native save'
    summary = ('Spendable Gems, Crystals, Growth Points, officer Skill Points and Upgrade Stones, existing Skill Orbs and attribute-element quantities. '
               'Searchable officer progression, weapon and attribute inventory; lifetime earnings, progression and equipment stay intact.')

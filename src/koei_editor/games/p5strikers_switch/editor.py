"""Native English Switch export workspace with shared safe editing controls."""
from koei_editor.games.p5strikers_switch import parser
from koei_editor.games.p5strikers_pc.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = ''
    subtitle = 'Nintendo Switch — English savedata export'
    summary = ('Occupied save-slot money, Persona points, unspent BOND points and named existing '
               'consumables, cooking ingredients, incenses, remedies and selected skill cards. '
               'Searchable character/Persona inspection; Switch save-manager reimport required.')

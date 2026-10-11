"""Native English PS4 export workspace with shared safe editing controls."""
from koei_editor.games.p5strikers_ps4 import parser
from koei_editor.games.p5strikers_pc.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.bin'
    subtitle = 'PlayStation 4 — English decrypted APP.BIN export'
    summary = ('Occupied save-slot money, Persona points, unspent BOND points and named existing '
               'consumables, cooking ingredients, incenses, remedies and selected skill cards. '
               'Searchable character/Persona inspection; Original sce_sys/param.sfo required; PS4 save-manager reimport is external.')

"""Dedicated Nintendo DS gallery workspace using shared safe editing controls."""
from koei_editor.games.pokemon_conquest_ds import parser
from koei_editor.games.pokemon_conquest_ds.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.sav'
    subtitle = 'North American Nintendo DS — raw .sav exports'
    summary = ('Existing gallery Pokémon IV components and Speed IV, selected or bulk Max, '
               'and searchable gallery records. Both native banks remain separate.')

"""US DS Monster Rancher workspace using the shared safe GUI."""
from koei_editor.games.monster_rancher_ds import parser
from koei_editor.games.monster_rancher_ds.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = parser.EXTENSION
    subtitle = 'US Nintendo DS — separate raw .sav export'
    summary = ('Edit existing current/frozen monster stats and lifespan, ASCII names and gold '
               'reductions. Search monster, inventory and ranch records. Max respects ordinary '
               'stat limits and preserves Overdrive values; both matching replicas stay consistent.')

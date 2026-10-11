"""Warriors: Abyss in the shared copy-only scalar workspace."""
from koei_editor.games.abyss_pc import parser
from koei_editor.games.abyss_pc.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.bin'
    subtitle = 'Windows PC — copied revision-A4 gameplay slot'
    summary = ('Edit Karma Embers. Keep the original steam_autocloud.vdf beside the copied '
               'slot and the edited destination. Recruitment, hero growth, run state and '
               'collections are preserved.')

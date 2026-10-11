"""SW5 workspace with backups, Undo, review and current-checkpoint resources."""
from koei_editor.games.samurai5_pc import parser
from koei_editor.games.samurai5_pc.presentation import Presentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor

class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.bin'
    subtitle = 'Windows PC — native My Castle slot-zero save'
    summary = ('Gold, stock EXP, shared skill points, stock weapon mastery, lumber, mineral and fabric. '
               'Searchable checkpoint, weapon, officer, mount and progression inspection. '
               'Keep the original steam_autocloud.vdf beside source and destination save copies.')

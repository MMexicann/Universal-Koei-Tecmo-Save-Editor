"""Original Xbox system load-list workspace."""
from koei_editor.shared.verified_gui import Editor as ScalarEditor
from . import parser
from .presentation import Presentation

class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    save_extension = '.dat'
    subtitle = 'Original Xbox — copied Ninja Gaiden Black SYSTEM.dat'
    summary = ('Restore numeric save-slot order and inspect stored play times. Keep one original '
               'eeprom.bin or factory_eeprom.bin beside the system copy and its destination. '
               'Reimport as system.dat with your console save manager.')

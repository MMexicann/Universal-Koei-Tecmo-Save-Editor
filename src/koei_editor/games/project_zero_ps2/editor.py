"""Original European PS2 camera editor and separate native-record inspectors."""
from koei_editor.games.project_zero_ps2 import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (
            InspectionTable('Save slots', ('Slot', 'State', 'Mission', 'Room', 'Play time',
                                           'Photographs taken', 'Camera points'),
                            parser.slot_records(document),
                            'Mission, room, history and empty slots are read only.'),
            InspectionTable('Camera functions', ('Slot', 'Stored function', 'Value'),
                            parser.camera_records(document),
                            'Special abilities and equipped references stay unchanged.'),
            InspectionTable('Inventory', ('Slot', 'Native item record', 'Stored quantity/status'),
                            parser.item_records(document),
                            'Record positions are not named item IDs. Films, consumables and key-item '
                            'semantics require separate proof before editing.'),
        )


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = parser.EXTENSION
    presentation_type = Presentation
    subtitle = 'Original European PlayStation 2 · SLES-50821 · PSU exports'
    summary = 'Camera points and existing base-upgrade reductions; searchable slots, functions and inventory.'

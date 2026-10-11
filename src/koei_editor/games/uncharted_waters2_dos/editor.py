"""English DOS New Horizons in the shared safe copied-save workspace."""
from koei_editor.games.uncharted_waters2_dos import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (
            InspectionTable('Save slots', ('Slot', 'Protagonist', 'Date', 'Gold (coins)',
                                           'Navigation level', 'Battle level',
                                           'Fame: trade/piracy/adventure'),
                            self.backend.slot_records(document),
                            'Empty slots are inspection only. Levels and fame remain read only.'),
            InspectionTable('Existing protagonist records',
                            ('Slot', 'Sailor ID', 'Name', *parser.ATTRIBUTES,
                             'Navigation level', 'Battle level', 'Navigation EXP', 'Battle EXP'),
                            self.backend.sailor_records(document),
                            'Only the selected slot protagonist has editable attributes. '
                            'Experience stores progress toward the next level, not lifetime totals.'),
        )


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.dat'
    presentation_type = Presentation
    subtitle = 'Original English DOS · KOUKAI2.DAT copies'
    summary = 'Existing-slot carried gold and eight named protagonist attributes; searchable save records.'

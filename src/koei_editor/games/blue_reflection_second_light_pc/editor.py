"""Second Light workspace with the common safe-copy scalar editor."""
from koei_editor.games.blue_reflection_second_light_pc import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        inventory,party,sections = self.backend.inspection_rows(document)
        return (
            InspectionTable('Existing inventory',
                            ('Location','Record','Instance','Item ID','Stored quantity byte'),
                            inventory,'Only uniquely identified ordinary-container records with opened '
                            'positive counts above 1 qualify for reductions. Other records stay read-only.'),
            InspectionTable('Party records',('Record','Native character ID','Native bytes'),party,
                            'Original Second Light fifteen-record profile; empty/DLC slots are retained.'),
            InspectionTable('Native sections',('Section','Native bytes'),sections,
                            'Coins, Talents/TP, Fragments, crafting unlocks, dates, facilities and story '
                            'have no writable mapping. The terminal Guide bytes remain exact and opaque.'),
        )


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    subtitle = 'Original Steam PC · native checksum-protected gameplay profile'
    summary = 'Reduce existing container quantities to at least 1. Max disabled; ownership preserved.'

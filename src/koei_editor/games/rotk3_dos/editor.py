"""Existing TC DOS records in the shared copied-save workspace."""
from koei_editor.games.rotk3_dos import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    scenario_view_title = 'Scenario View'

    def inspection_tables(self, document):
        return (
            InspectionTable('Save slots', ('Slot', 'Status', 'Year', 'Month', 'Scenario',
                                           'City ID', 'Native ruler glyphs'),
                            self.backend.slot_records(document),
                            'Empty slots remain empty. Native names use custom glyph IDs.'),
            InspectionTable('Existing cities', ('Slot', 'City record', 'Native glyphs', 'Mayor ID',
                                                'Gold', 'Rice', 'Development', 'Cultivation',
                                                'Irrigation', 'Flood control', 'Civil loyalty'),
                            self.backend.city_records(document),
                            'Record IDs identify existing table rows; city links and ownership stay intact.'),
            InspectionTable('Existing officers', ('Slot', 'Officer record', 'Native glyphs',
                                                  'Land command', 'Naval command', 'War',
                                                  'Intelligence', 'Politics', 'Charisma',
                                                  'Troops', 'Location ID', 'Ruler ID',
                                                  'Training', 'Morale'),
                            self.backend.officer_records(document),
                            'Unusual abilities, troop/order state, treasure and progression remain read only.'),
        )


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.sav'
    presentation_type = Presentation
    subtitle = 'Original Traditional Chinese DOS · native SANGOKU3.SAV copies'
    summary = 'Existing officer abilities and city resource reductions; searchable slot/city/officer records.'

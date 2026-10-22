"""City quantities in the shared copied-save workspace."""
from koei_editor.games.rotk13 import parser as backend
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class XIIIPresentation(ScalarPresentation):
    scenario_view_title = 'Scenario View'

    def inspection_tables(self, document):
        cities = backend.cities(document)
        rows = tuple((row['id'],
                      'Unset' if row['district_reference'] == backend.EMPTY_DISTRICT
                      else row['district_reference'],
                      row['money'], row['supplies'], row['civilian_population'],
                      row['military_population'], row['wounded']) for row in cities)
        development = tuple((row['id'], row['fealty'], row['commerce'], row['farming'],
                             row['culture'], row['spear_proficiency'], row['horse_proficiency'],
                             row['bow_proficiency']) for row in cities)
        return (InspectionTable('Existing cities',
                                ('City ID', 'District reference', 'Money', 'Supplies',
                                 'Civilian population', 'Military population', 'Wounded troops'), rows,
                                'Search by city ID. The district reference is read only; '
                                'force ownership is indirect. Population components are stored separately.'),
                InspectionTable('City development and training',
                                ('City ID', 'Fealty', 'Commerce', 'Farming', 'Culture',
                                 'Spear proficiency', 'Horse proficiency', 'Bow proficiency'),
                                development, 'Current stored quantities. Derived caps are separate.'))


class Editor(ScalarEditor):
    game_id = backend.GAME_ID
    save_extension = '.s13'
    backend = backend
    presentation_type = XIIIPresentation
    subtitle = 'Original Windows PC revision-14 campaign editor'
    summary = 'City resources, population, wounded troops, fealty, commerce, farming, culture and troop proficiencies.'


def read_save(path):
    return backend.read_save(path)

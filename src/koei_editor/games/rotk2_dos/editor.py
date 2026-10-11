"""Original Chinese DOS ROTK II province resources in the shared safe workspace."""
from koei_editor.games.rotk2_dos import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable('Existing provinces',
                                ('Record', 'Owner ID (255 unclaimed)', 'Gold', 'Rice',
                                 'Population (people)', 'Grid X', 'Grid Y'),
                                self.backend.province_records(document),
                                'Record numbers are table positions, not named province IDs. '
                                'Unclaimed provinces, population, coordinates and ownership are read only.'),)


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = ''
    presentation_type = Presentation
    subtitle = 'Original Chinese DOS · raw save files'
    summary = 'Owned-province gold and rice reductions; searchable province records.'

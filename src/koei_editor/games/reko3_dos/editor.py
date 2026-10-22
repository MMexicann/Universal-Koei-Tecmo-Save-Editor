"""Chinese DOS Legend of Liu Bei in the standard safe editing workspace."""
from koei_editor.games.reko3_dos import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    scenario_view_title = 'Scenario View'

    def inspection_tables(self, document):
        return (InspectionTable('Characters and carried items',
                                ('ID', 'Character', 'Army code', 'Current troops',
                                 'Class code', 'Level', 'Within-level EXP', 'Eight item slots'),
                                parser.character_records(document),
                                'Classes, allegiance, levels and carried items are inspection only.'),)


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.r3s'
    presentation_type = Presentation
    subtitle = 'Original Traditional Chinese DOS · MSAVE0–4.R3S copies'
    summary = 'Existing allied troops and within-level EXP; searchable character and carried-item records.'

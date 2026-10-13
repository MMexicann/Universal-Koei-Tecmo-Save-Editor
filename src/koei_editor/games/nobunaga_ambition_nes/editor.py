"""Original NES 17-fief resource workspace."""
from koei_editor.games.nobunaga_ambition_nes import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable('Existing fiefs', ('Fief', 'Owner ID', 'Daimyo', 'Gold', 'Rice', 'Native policy'),
                                self.backend.province_records(document),
                                'Original English 17-fief profile. Inactive fiefs remain inspection only.'),)


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.sav'
    presentation_type = Presentation
    subtitle = 'Original English NES · 8 KiB battery bank · 17-fief scenario'
    summary = 'Existing fief Gold and Rice reductions; searchable ownership and native policy records.'

"""Attack on Titan EU Vita existing resources and numbered material records."""
from koei_editor.games.aot1_vita import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable('Material storage', ('Native record', 'Quantity', 'Editing scope'),
                                parser.material_records(document),
                                'Native indices have no assumed item names; zero rows and ownership are preserved.'),)


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.dat'
    presentation_type = Presentation
    subtitle = 'Original EU PlayStation Vita · PCSB00898 · decrypted app0000.dat'
    summary = 'Reduce money and positive existing numbered material quantities; inspect all material rows.'

"""Nights of Azure 2 original Switch scalar workspace."""
from koei_editor.games.nights_azure2_switch import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable('Native save preview', ('Record', 'Stored value'),
                                self.backend.inspection_rows(document),
                                'Libra is shop currency. Growth, story and chapter checkpoints remain read-only.'),)


class Editor(ScalarEditor):
    save_extension = parser.EXTENSION
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    subtitle = 'Original Nintendo Switch · qualified English-preview gameplay exports'
    summary = 'Reduce existing Libra with synchronized preview and native hashes. Max disabled.'

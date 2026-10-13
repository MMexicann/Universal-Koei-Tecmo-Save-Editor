"""Existing PS3 Pirate Warriors 3 character stats and read-only progression."""
from koei_editor.games.pw3_ps3 import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable('Character records',
                                ('Record', 'State', 'Stored level index', 'XP', 'HP', 'Attack', 'Defense'),
                                parser.character_records(document),
                                'Native record numbers are not named character identities. Levels and XP are read only.'),)


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.bin'
    presentation_type = Presentation
    subtitle = 'Original EU PS3 PSN · NPEB02211 · decrypted DATA.BIN'
    summary = 'Reduce stored HP, Attack and Defense on existing progressed character records; inspect currency.'

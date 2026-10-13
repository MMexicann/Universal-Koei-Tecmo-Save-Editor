"""Searchable original Macintosh save data-fork records."""
from koei_editor.games.bandit_kings_mac import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (
            InspectionTable('Prefectures', ('Record', 'Name', 'Ruler hero ID', 'Gold', 'Food', 'Metal', 'Fur'),
                            self.backend.prefecture_records(document),
                            'Unclaimed prefectures remain inspection only; names are read from the opened data fork.'),
            InspectionTable('Active heroes', ('Hero ID', 'Name', 'Prefecture', 'Liege ID', 'Strength',
                                              'Dexterity', 'Wisdom', 'Body', 'Maximum body', 'Men', 'Native flags'),
                            self.backend.hero_records(document),
                            'Existing hero abilities can be reduced. Loyalty, persona, body, troop counts and membership stay read only.'),
        )


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    save_extension = '.cim'
    presentation_type = Presentation
    subtitle = 'Original English Macintosh · SUI0/SUI1 raw data-fork copies'
    summary = 'Existing prefecture Gold/Food/Metal/Fur and active hero Strength/Dexterity/Wisdom reductions.'

"""Original Firis workspace with shared staging and safe-copy saving."""
from koei_editor.games.firis_pc import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        rows = tuple((label,slot,instance,identity,quality,'Yes' if editable else 'No')
                     for _key,label,slot,_offset,instance,identity,quality,editable
                     in self.backend.item_records(document))
        return (
            InspectionTable('Existing inventory',
                            ('Location','Record','Instance','Item ID','Stored quality','Ordinary pool'),
                            rows,'Occupied native 52-byte records. Unknown IDs stay numeric. '
                            'Important pools, fractional qualities and ambiguous instances have no quality control.'),
            InspectionTable('Alchemy progression',('Record','Stored value'),
                            self.backend.progression_rows(document),
                            'Read-only levels and EXP; no recipe, skill or reward change is inferred.'),
        )


class Editor(ScalarEditor):
    save_extension = parser.EXTENSION
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = Presentation
    subtitle = 'Original Steam PC · native tagged GAMEDATA profile'
    summary = 'Reduce Cole and existing whole-number basket/container quality. Max disabled.'

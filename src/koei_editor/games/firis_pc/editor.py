"""Original Firis workspace with shared staging and safe-copy saving."""
from koei_editor.games.firis_pc import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        fields = self.backend.field_map(document)
        rows = tuple((label,slot,instance,identity,quality,
                      'Reduce only' if f'{key}_{slot}_quality' in fields else 'Read only')
                     for key,label,slot,_offset,instance,identity,quality,_editable
                     in self.backend.item_records(document))
        return (
            InspectionTable('Existing inventory',
                            ('Location','Record','Instance','Item ID','Stored quality','Quality editing'),
                            rows,'Occupied native 52-byte records. Unknown IDs stay numeric. '
                            'Important pools, records beyond the active capacity, fractional qualities '
                            'and ambiguous instances have no quality control.'),
            InspectionTable('Inventory capacities',('Location','Opened active limit','Physical records'),
                            self.backend.inventory_capacity_rows(document),
                            'Stored capacity and physical allocation differ. Limits are read-only; '
                            'spare physical records do not authorize ownership or capacity increases.'),
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

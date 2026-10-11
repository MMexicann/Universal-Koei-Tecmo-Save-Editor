"""Original revision-0 Switch Ryza 2 session; PC/DX profiles remain separate."""
from koei_editor.games.ryza.editor import Ryza2Editor
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class SwitchPresentation(ScalarPresentation):
    def inspection_tables(self, document):
        editable = {(field.group, field.slot) for field in self.backend.fields_for(document)
                    if field.id != 'skill_points'}
        rows = tuple((record['group'], record['label'], record['item_id'],
                      record['instance_id'], record['quality'], record['neighbor'],
                      'Editable 1–100' if (record['group'], record['slot']) in editable else 'Read only')
                     for record in self.backend.item_records(document))
        return (InspectionTable('Existing inventory and equipment',
                                ('Location', 'Slot', 'Item ID', 'Instance ID', 'Quality',
                                 'Adjacent raw u16', 'Quality control'), rows,
                                'Nonzero adjacent synthesis values, empty and important records are read only. '
                                'Stored IDs are shown; item names and coupled-value dependencies are not mapped.'),)


class Editor(Ryza2Editor):
    game_id = 'atelier_ryza2_switch'
    presentation_type = SwitchPresentation
    subtitle = 'Original Nintendo Switch · revision-0 main-game export'
    summary = ('Unspent skill-tree SP reductions and existing zero-adjacent ordinary quality (1–100). '
               'Searchable inventory/equipment records; learned skills remain unchanged.')

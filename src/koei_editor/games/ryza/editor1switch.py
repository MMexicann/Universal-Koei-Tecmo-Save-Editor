"""Original Switch Ryza 1 session; PC/DX and DLC episode profiles are excluded."""
from koei_editor.games.ryza.editor import Editor as RyzaEditor
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class SwitchPresentation(ScalarPresentation):
    def inspection_tables(self, document):
        editable = {(field.group, field.slot) for field in self.backend.fields_for(document)}
        rows = tuple((record['group'], record['label'], record['item_id'],
                      record['instance_id'], record['quality'], record['neighbor'],
                      'Editable 1–100' if (record['group'], record['slot']) in editable else 'Read only',
                      *(f'ID {trait_id} / level {level}' for trait_id, level in record['traits']))
                     for record in self.backend.item_records(document))
        return (InspectionTable('Existing inventory and equipment',
                                ('Location', 'Slot', 'Item ID', 'Instance ID', 'Quality',
                                 'Adjacent raw u16', 'Quality control', 'Trait slot 1', 'Trait slot 2', 'Trait slot 3'), rows,
                                'Important/no-quality records, shared instances and nonzero adjacent-value records are read only. '
                                'Adjacent synthesis data and trait slots are read only. Item/trait names are not mapped.'),)


class Editor(RyzaEditor):
    game_id = 'atelier_ryza_switch'
    presentation_type = SwitchPresentation
    subtitle = 'Original Switch · revision-4 main-game export'
    summary = ('Existing ordinary inventory and equipment quality (1–100), with '
               'searchable records. Higher quality caps and shared equipment instances '
               'are read only.')

"""Original Steam Ryza sessions using the shared Undo/review/safe-saving UI."""
from koei_editor.games.ryza_pc import parser
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation
from koei_editor.shared.verified_gui import Editor as ScalarEditor


class RyzaPresentation(ScalarPresentation):
    def inspection_tables(self, document):
        rows = tuple((r['group'], r['label'], r['item_id'], r['instance_id'], r['quality'], r['neighbor'])
                     for r in self.backend.item_records(document))
        return (InspectionTable('Existing inventory and equipment',
                                ('Location', 'Slot', 'Item ID', 'Instance ID', 'Quality', 'Adjacent raw u16'),
                                rows, 'Opened records. Important items and unknown adjacent values are read only.'),)


class Editor(ScalarEditor):
    game_id = parser.GAME_ID
    backend = parser
    presentation_type = RyzaPresentation
    subtitle = 'Original Steam PC · native 66-byte item layout'
    summary = 'Reduce existing ordinary item/equipment quality. Max disabled; opaque terminal data preserved.'

"""Named ordinary stacks with separate read-only player/equipment status."""
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (
            InspectionTable('Pockets and bag',
                            ('Container', 'Slot', 'Item ID', 'Item', 'Stored quantity', 'Editing'),
                            self.backend.item_records(document),
                            'Reduce existing named ordinary medicine/seed stacks; keep at least one. '
                            'Unknown, empty, single-item and unusual records remain unchanged.'),
            InspectionTable('Player and equipment — inspection only', ('Stored field', 'Value'),
                            self.backend.player_records(document),
                            'Growth, HP, equipment references, world data and ownership are preserved.'),
        )

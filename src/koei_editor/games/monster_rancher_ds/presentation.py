"""Monster and item inspectors separate stored stats from progression."""
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class Presentation(ScalarPresentation):
    def record_name(self, field):
        return field.record

    def inspection_tables(self, document):
        monsters, items, status = self.backend.inspection_tables_data(document)
        return (
            InspectionTable('Monsters', ('Replica', 'Record', 'Name', 'Species ID', 'Age',
                'Remaining lifespan', 'Power', 'Intelligence', 'Skill', 'Speed', 'Defense', 'Life', 'Editing'),
                monsters, 'Matching occupied records update together. Frozen monsters do not lose lifespan '
                'while stored. Age, rank, techniques and breeding history are preserved.'),
            InspectionTable('Inventory — inspection only', ('Replica', 'Slot', 'Item ID', 'Item'), items,
                'Inventory stores individual item IDs, not stack quantities. Usable capacity depends on '
                'house upgrades. Ordinary items, farm effects, combination and event items remain intact.'),
            InspectionTable('Ranch and calendar — inspection only', ('Replica', 'Stored field', 'Value'), status,
                'Spendable gold and lifetime money won are separate. Save-counter ordering is not inferred; '
                'unknown differences between replicas remain intact.'),
        )

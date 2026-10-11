"""Named character records and searchable read-only numeric inventory."""
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (
            InspectionTable('Characters',
                            ('Character', 'Level', 'EXP', 'Current HP', 'Current MP', 'Current LP',
                             'Base HP', 'Base MP', 'Base LP', 'Base attack', 'Base defense', 'Base speed'),
                            self.backend.character_records(document),
                            'Effective maxima include equipment effects. Levels and EXP are inspection only.'),
            InspectionTable('Existing item records',
                            ('Pool', 'Slot', 'Serial', 'Item ID', 'Float quality lead',
                             'Trait ID leads', 'Effect ID leads', 'Quantity/use word lead'),
                            self.backend.item_records(document),
                            'Numeric inventory leads are read only; item identities, traits, quality and uses are preserved.'),
        )

"""Searchable material controls and separate read-only character status."""
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (
            InspectionTable('Materials', ('Slot', 'Material', 'Stored quantity', 'Edit availability'),
                            self.backend.material_records(document),
                            'Only existing ordinary material records have quantity controls.'),
            InspectionTable('Character status — inspection only',
                            ('Character', 'EXP', 'Vitality', 'Attack', 'Defense', 'Technique', 'Unknown stat'),
                            self.backend.character_records(document),
                            'Levels and equipment dependencies are unproved. Later four native character names remain unqualified.'),
        )

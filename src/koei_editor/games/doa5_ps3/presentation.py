"""Searchable source-backed costume records; unmapped names remain explicit."""
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable('Original costume flags',
                                ('Costume flag record', 'Control', 'Native offset', 'State', 'Stored value'),
                                self.backend.costume_rows(document),
                                'Only qualified 0-to-1 costume transitions are writable. '
                                'Other status values, character ownership, DLC and story are preserved.'),)

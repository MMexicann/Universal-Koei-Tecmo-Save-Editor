"""Searchable gallery records without exposing player names or scenario data."""
from koei_editor.shared.scalar_presentation import InspectionTable, ScalarPresentation


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (InspectionTable('Gallery Pokémon',
                    ('Bank', 'Generation', 'Record', 'Pokémon', 'Species ID',
                     'IV component 1', 'IV component 2', 'IV component 3', 'Speed IV', 'Editing'),
                    self.backend.gallery_records(document),
                    'Gallery banks retain distinct original records. Numbered components are '
                    'HP/attack/defense IVs without a claimed individual ordering. '
                    'Current scenario Pokémon and story are preserved.'),)

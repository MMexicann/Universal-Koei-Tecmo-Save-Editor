"""Separate system load-list order from story progression and mirrored times."""
from koei_editor.shared.scalar_presentation import ScalarPresentation, InspectionTable

class Presentation(ScalarPresentation):
    def field_hint(self, document, field):
        return ('Choose Sort slots numerically to order the load list by slot number. '
                'The game skips absent slots. All stored play times, unlocks and settings are preserved.')
    def inspection_tables(self, document):
        return (InspectionTable('Load-list slots and stored time',
                                ('Slot', 'Stored frames (60 per second)', 'Opened active-list position'),
                                self.backend.inspection_rows(document)),)

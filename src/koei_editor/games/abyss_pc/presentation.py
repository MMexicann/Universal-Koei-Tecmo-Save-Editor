"""Keep the native recruitment bytes distinct from editable currency."""
from koei_editor.shared.scalar_presentation import ScalarPresentation, InspectionTable


class Presentation(ScalarPresentation):
    def inspection_tables(self, document):
        return (
            InspectionTable('Permanent resources', ('Resource', 'Opened value'),
                            (('Karma Embers', self.backend.KARMA.value(document.payload)),)),
            InspectionTable('Native recruitment flags — inspection only',
                            ('Native record ID', 'Stored flag', 'Editing'),
                            self.backend.recruitment_records(document),
                            'Search native record IDs and stored flags. Names and unused IDs '
                            'need the matching game catalog; recruitment is preserved.'),
        )

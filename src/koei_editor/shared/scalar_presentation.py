"""Optional data-only presentation hooks for the shared scalar workspace."""
from dataclasses import dataclass


@dataclass(frozen=True)
class InspectionTable:
    title: str
    columns: tuple
    rows: tuple
    note: str = ''


class ScalarPresentation:
    """Default hooks use optional backend hints; they never parse or write files."""
    extra_groups = ()
    scenario_view_title = None

    def __init__(self, backend, game_id):
        self.backend, self.game_id = backend, game_id

    def filename_suffix(self, document):
        return ''

    def record_name(self, field):
        if hasattr(self.backend, 'record_label'):
            return self.backend.record_label(field.slot, field.group)
        return f'{field.group} record {field.slot}' if field.slot else field.group

    def field_hint(self, document, field):
        if hasattr(self.backend, 'field_hint'):
            return self.backend.field_hint(document, field.id)
        return (f'Edit range: {field.minimum:,} to {field.maximum:,}. '
                'Max preserves higher existing values.')

    def dashboard(self, document):
        """Project opened values only; game presentations may add verified context."""
        from koei_editor.shared.progression_generic import generic_dashboard
        return generic_dashboard(document, self.backend, self)

    def inspection_tables(self, document):
        if hasattr(self.backend, 'inspection_rows'):
            rows = tuple((row['group'], row['label'], row['value'])
                         for row in self.backend.inspection_rows(document))
        else:
            rows = tuple((field.group, field.label, field.value(document.payload))
                         for field in self.backend.fields_for(document))
        return (InspectionTable('Mapped records', ('Group', 'Record / field', 'Opened value'), rows),)

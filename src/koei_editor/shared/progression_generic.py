"""Read-only cards for scalar profiles without a bespoke dashboard projection.

Only fields returned for the opened document are included. Editor ranges and
storage widths deliberately do not supply progression bars or completion data.
"""
from collections import defaultdict
import json

from koei_editor.shared.progression import (
    DashboardCard, DashboardMetric, DashboardSection, ProgressionDashboard,
)


# Limit the height of individual cards, rather than dropping wide records or
# imposing a global field limit. The dashboard renderer paginates the cards.
METRICS_PER_CARD = 12


def _identity(*parts):
    """Unambiguous IDs even when labels contain separators or are repeated."""
    return json.dumps(parts, ensure_ascii=False, separators=(',', ':'))


def generic_dashboard(document, backend, presentation):
    """Project every mapped opened value without staging or serializing edits.

    Native group names remain visible: an equipment reference, a historical
    counter and an ownership field must not become interchangeable just because
    their labels look alike. Slots identify records even when names repeat.
    """
    groups = {}
    occurrences = defaultdict(int)
    for field in backend.fields_for(document):
        group = field.group
        records = groups.setdefault(group, {})
        record = records.setdefault(field.slot, [])
        value = field.value(document.payload)
        display = f'{value:,}' if type(value) is int else str(value)
        occurrence = occurrences[field.id]
        occurrences[field.id] += 1
        metric = DashboardMetric(
            id=_identity('field', field.id, occurrence),
            label=field.label, value=display, field_id=field.id,
        )
        record.append((field, metric))

    sections = []
    for group, records in groups.items():
        title = group or 'Mapped fields'
        cards = []
        for slot, entries in records.items():
            name = presentation.record_name(entries[0][0]) or title
            part_count = (len(entries) + METRICS_PER_CARD - 1) // METRICS_PER_CARD
            for part in range(part_count):
                chunk = entries[part * METRICS_PER_CARD:(part + 1) * METRICS_PER_CARD]
                subtitle = f'Record {slot}' if slot else 'Opened save values'
                if part_count > 1:
                    subtitle += f' · Part {part + 1} of {part_count}'
                metrics = tuple(metric for _, metric in chunk)
                cards.append(DashboardCard(
                    id=_identity('record', group, slot, part), title=name,
                    subtitle=subtitle, metrics=metrics, section=title,
                    search_text=' '.join((title, name, str(slot), *(text
                        for metric in metrics
                        for text in (metric.label, metric.field_id, metric.value)))),
                ))
        sections.append(DashboardSection(
            id=_identity('group', group), title=title, cards=tuple(cards),
        ))

    layout = document.format
    title = getattr(layout, 'title', None) or getattr(layout, 'name', None) or 'Verified save'
    return ProgressionDashboard(
        title=title, sections=tuple(sections),
        note=('Read-only opened save values. Select a mapped value to find its editable field. '
              'Storage limits and edit ranges do not establish progression or completion.'),
    )

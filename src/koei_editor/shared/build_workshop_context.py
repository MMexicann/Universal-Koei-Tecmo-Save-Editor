"""Translate a game's verified read-only projection into workshop rows.

The context builder only groups native scalar values and existing dashboard
metrics. It never derives gameplay values, stores a save identity, or stages
an edit.
"""
from collections import defaultdict
from collections.abc import Mapping

from koei_editor.shared.build_workshop import BuildPlan


_EQUIPMENT_CATEGORIES = frozenset((
    'equipment', 'mount equipment', 'weapon order', 'weapon affinity',
    'weapon attribute identities',
))


def _mapping(value):
    if isinstance(value, Mapping):
        return value
    names = ('field_id', 'label', 'category', 'character_id', 'current_value',
             'choices', 'evidence')
    return {name: getattr(value, name) for name in names if hasattr(value, name)}


def _scalar(value):
    return type(value) in (bool, int, float, str) or value is None


def is_equipment_field(category, field_id):
    text = str(category).casefold()
    identity = str(field_id).casefold()
    return (text in _EQUIPMENT_CATEGORIES
            or '_equipped_' in identity
            or identity.endswith('_active')
            or '_identity' in identity
            or 'mount_loadout' in identity)


def _card_owners(dashboard, fields):
    """Associate dashboard cards with owners through exact mapped field IDs."""
    owners = {}
    for section in getattr(dashboard, 'sections', ()):
        for card in getattr(section, 'cards', ()):
            linked = set()
            for metric in getattr(card, 'metrics', ()):
                field_id = getattr(metric, 'field_id', None)
                field = fields.get(field_id) if isinstance(field_id, str) else None
                owner = getattr(field, 'character_id', None)
                if owner and owner != 'save':
                    linked.add(str(owner))
            if len(linked) == 1:
                owners[card.id] = next(iter(linked))
    return owners


def scalar_projection_context(projection):
    """Return native-field plans, field metadata, and dashboard stat rows.

    ``projection`` must be a provider result carrying ``fields`` and the
    game's existing immutable ``dashboard``. Values remain attached to their
    provider's stable IDs; equipment-like fields are grouped separately.
    """
    if not isinstance(getattr(projection, 'fields', None), Mapping):
        raise TypeError('A workshop projection must expose mapped fields.')
    fields = projection.fields
    dashboard = projection.dashboard
    owners_by_card = _card_owners(dashboard, fields)
    assignments = defaultdict(lambda: {'values': {}, 'equipment': {}})
    labels = {}
    metadata = {}

    for field_id, raw_field in fields.items():
        field = _mapping(raw_field)
        owner = field.get('character_id')
        if not isinstance(owner, str) or not owner or owner == 'save':
            continue
        value = field.get('current_value')
        if not _scalar(value):
            # Arrays and structured values stay in their existing editor forms.
            continue
        category = str(field.get('category', 'stat'))
        label = field.get('label', field_id)
        bucket = 'equipment' if is_equipment_field(category, field_id) else 'values'
        assignments[owner][bucket][field_id] = value
        metadata[field_id] = {
            'label': label,
            'category': category,
            'character_id': owner,
            'current_value': value,
            'value_type': ('boolean' if type(value) is bool else
                           'integer' if type(value) is int else
                           'number' if type(value) is float else
                           'string' if type(value) is str else None),
            'choices': tuple(field.get('choices') or ()),
            'evidence': field.get('evidence', ''),
        }

    for section in getattr(dashboard, 'sections', ()):
        for card in getattr(section, 'cards', ()):
            owner = owners_by_card.get(card.id)
            if owner and owner not in labels:
                labels[owner] = card.title
    for owner in assignments:
        if owner in labels:
            continue
        kind, _, suffix = owner.partition(':')
        record = suffix if suffix else owner
        labels[owner] = f'{kind.replace("_", " ").title()} {record}'

    plans = []
    for owner in sorted(assignments):
        grouped = assignments[owner]
        if not grouped['values'] and not grouped['equipment']:
            continue
        plans.append(BuildPlan(
            projection.game_id,
            projection.platform_id,
            owner,
            f'Opened snapshot · {labels[owner]}',
            grouped['values'],
            grouped['equipment'],
            'Snapshot of mapped values from the opened save. The Workshop adds no game formulas.',
        ))

    stats = []
    evidence_fallback = '; '.join(getattr(projection, 'evidence', ()) or ())
    for section in getattr(dashboard, 'sections', ()):
        for card in getattr(section, 'cards', ()):
            owner = owners_by_card.get(card.id)
            if not owner:
                continue
            for metric in getattr(card, 'metrics', ()):
                field_id = getattr(metric, 'field_id', None)
                field = fields.get(field_id) if isinstance(field_id, str) else None
                evidence = getattr(field, 'evidence', '') if field is not None else ''
                note = getattr(metric, 'note', '')
                evidence = ' · '.join(part for part in (evidence, note or evidence_fallback) if part)
                stats.append({
                    'character_id': owner,
                    'label': metric.label,
                    'value': metric.value,
                    'evidence': evidence,
                })
    return tuple(plans), metadata, tuple(stats)


def assignments_from_plan(plan, *, game_id, platform_id, field_metadata):
    """Validate an imported/edited plan against one opened profile context."""
    if (plan.game_id, plan.platform_id) != (game_id, platform_id):
        from koei_editor.games.dw3.models import SaveError
        raise SaveError('This build plan belongs to a different game or platform.')
    assignments = {}
    for group in (plan.values, plan.equipment):
        for field_id, value in group.items():
            if field_id in assignments:
                from koei_editor.games.dw3.models import SaveError
                raise SaveError(f'The build plan assigns {field_id} more than once.')
            field = field_metadata.get(field_id)
            if field is None or field.get('character_id') != plan.character_id:
                from koei_editor.games.dw3.models import SaveError
                raise SaveError(f'{field_id} is not a mapped field for this character in the opened save.')
            assignments[field_id] = value
    if not assignments:
        from koei_editor.games.dw3.models import SaveError
        raise SaveError('This build plan contains no mapped fields to stage.')
    return assignments


__all__ = ['assignments_from_plan', 'is_equipment_field', 'scalar_projection_context']

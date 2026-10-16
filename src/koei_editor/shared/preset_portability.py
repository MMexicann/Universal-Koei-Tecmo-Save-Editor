"""Reviewed portability of fixed resource identities, never physical records.

The registry profile binds game/platform; these explicit policies further bind
the native revision and identify only static resource fields. Ownership,
inventory/equipped references, story flags and character-slot associations do
not become portable merely because their offsets or labels happen to match.
"""
from dataclasses import dataclass
import hashlib
import json

from koei_editor.games.dw3.models import SaveError


@dataclass(frozen=True)
class PortabilityPolicy:
    id: str
    game_id: str
    fields: frozenset[str]
    revision: str
    note: str


def policy(adapter, document):
    """Return a fail-closed policy after exact native document qualification."""
    adapter.validate_document(document)
    if adapter.game_id == 'dw8xl':
        fields = frozenset(('gold', 'gems', 'facility_materials', 'weapon_materials'))
        return PortabilityPolicy('dw8xl-fixed-resources-v1', adapter.game_id, fields,
                                 'pc-' + document.payload[:5].hex(),
                                 'Fixed PC resource balances only; officers, weapons and equipment are excluded.')
    if adapter.game_id == 'wo3u':
        from koei_editor.games.wo3u.wo3u_parser import FORMAT
        fields = frozenset(field.id for field in FORMAT.fields if field.group in
                           ('Resources', 'Attribute orbs', 'Crafting materials'))
        return PortabilityPolicy('wo3u-steam-fixed-resources-v1', adapter.game_id, fields,
                                 'steam-packed-' + document.payload[:4].hex(),
                                 'Fixed growth, gem, attribute-orb and crafting-material balances only; '
                                 'officer allocations, promotions, equipment and compatibility are excluded.')
    if adapter.game_id == 'origins':
        return PortabilityPolicy('origins-steam-resources-v1', adapter.game_id,
                                 frozenset(('gold', 'skill_points', 'dlc_skill_points')),
                                 f'steam-slot-{document.revision}',
                                 'Fixed resource pools within the exact native slot revision only; '
                                 'bonds, weapons, peace and battle flags are excluded.')
    raise SaveError('Reusable editing presets are not qualified for this game/platform. '
                    'Its existing source-bound Edit Presets remain available.')


def identity(policy):
    """Fingerprint the reviewed policy, not mutable save values or private data."""
    raw = json.dumps((policy.id, policy.game_id, policy.revision, sorted(policy.fields)),
                     ensure_ascii=True, separators=(',', ':')).encode('ascii')
    return hashlib.sha256(raw).hexdigest()


def eligible_fields(adapter, document):
    selected = policy(adapter, document)
    mapping = adapter.field_map(document)
    return tuple(field for key, field in mapping.items() if key in selected.fields)


def require_fields(policy, field_ids):
    if any(key not in policy.fields for key in field_ids):
        raise SaveError('A selected field has no verified cross-save portability. '
                        'Use a source-bound preset for records, equipment, ownership or progression flags.')


def exclusion_reason(policy, field):
    if field.id in policy.fields:
        return 'Qualified fixed resource'
    group = field.group.casefold()
    if any(word in group for word in ('weapon', 'equipment', 'mount', 'item')):
        return 'Excluded: inventory identity, ownership or equipment dependency is not portable'
    if any(word in group for word in ('officer', 'character', 'upgrade')):
        return 'Excluded: officer-slot identity or allocation dependency is not portable'
    return 'Excluded: progression, reward or field identity has no cross-save qualification'

"""Read-only character and weapon planning data for WO3 Ultimate PC.

The provider projects the existing qualified parser and dashboard. Compatibility
stays in native raw units, and attribute identities/ranks remain separate; no
damage, fusion, promotion or story formula is inferred here.
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo3u import wo3u_parser
from koei_editor.games.wo3u.dashboard import dashboard


GAME_ID = 'wo3u'
PLATFORM_ID = 'windows_pc'
EVIDENCE = (
    'docs/PROGRESSION_DASHBOARDS.md: WO3U Definitive Edition PC mapped opened-save stats, weapons and inventory.',
    'docs/OROCHI_DYNASTY_DEPTH.md: native PC loadouts, ownership/rank rules, attribute limits and parser evidence.',
    'docs/OROCHI_RESEARCH.md: qualified serialized weapon, attribute and item mappings.',
)


@dataclass(frozen=True)
class WorkshopField:
    """One field the WO3U editor already maps for the opened snapshot."""

    field_id: str
    label: str
    category: str
    character_id: str
    current_value: object
    choices: tuple[tuple[object, str], ...] = ()
    evidence: str = ''


@dataclass(frozen=True)
class WorkshopProjection:
    game_id: str
    platform_id: str
    title: str
    dashboard: object
    fields: Mapping[str, WorkshopField]
    evidence: tuple[str, ...]


def _character_id(field):
    if field.group in ('Officers', 'Equipment', 'Upgrade stones'):
        return f'officer:{field.slot - 1}'
    if field.group in ('Weapons', 'Weapon compatibility'):
        return f'weapon:{field.slot - 1}'
    if field.group == 'Mount equipment':
        return f'mount_loadout:{field.slot - 1}'
    return 'save'


def _field_evidence(field):
    if field.group == 'Weapon compatibility':
        return (EVIDENCE[1] + ' Compatibility is shown as stored raw units; no star or damage formula is applied.')
    if field.group in ('Weapons', 'Equipment', 'Mount equipment'):
        return EVIDENCE[1]
    return EVIDENCE[0] + ' Values are stored parser fields; no gameplay formula is applied.'


def workshop_projection(document, backend=wo3u_parser):
    """Return the validated dashboard and current fields/options for planning.

    Dynamic item and mount choices come directly from the parser's original-
    ownership-aware `field_options` hook. The projection cannot stage or save.
    """
    backend.validate_document(document)
    if document.format.id != GAME_ID:
        raise SaveError('The WO3U workshop requires its qualified Definitive Edition PC document.')

    projected = {}
    for field in backend.fields_for(document):
        has_choices = (field.group == 'Mount equipment'
                       or '_equipped_item_' in field.id)
        choices = tuple(backend.field_options(document, field.id)) if has_choices else ()
        projected[field.id] = WorkshopField(
            field_id=field.id,
            label=field.label,
            category=field.group,
            character_id=_character_id(field),
            current_value=field.value(document.payload),
            choices=choices,
            evidence=_field_evidence(field),
        )

    view = dashboard(backend, document)
    return WorkshopProjection(
        GAME_ID, PLATFORM_ID, view.title, view,
        MappingProxyType(projected), EVIDENCE,
    )


def is_mapped_field(document, field_id, backend=wo3u_parser):
    """Check a proposed preset field against this exact opened document."""
    backend.validate_document(document)
    if document.format.id != GAME_ID or type(field_id) is not str:
        return False
    return field_id in backend.field_map(document)

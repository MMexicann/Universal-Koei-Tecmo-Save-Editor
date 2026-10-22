"""Read-only workshop projections for the qualified Samurai Warriors 4 DX PC save.

The workshop intentionally reuses the parser's mapped fields and occupied
weapon choices. SW4 DX has verified stored officer base stats and weapon skill
slots; it does not have a verified derived battle-stat formula here.
"""
from dataclasses import dataclass, replace
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.sw4dx import samurai4dx_parser as backend
from koei_editor.shared.scalar_presentation import ScalarPresentation


PLATFORM_ID = 'windows_pc'
EVIDENCE = (
    'docs/SAMURAI_RESEARCH.md: qualified SW4 DX PC parser, stored officer stats, equipment and attached weapon skills.',
    'docs/PROGRESSION_DASHBOARDS.md: Samurai Warriors 4 DX opened-save dashboard values.',
)


@dataclass(frozen=True)
class WorkshopField:
    field_id: str
    label: str
    category: str
    character_id: str
    current_value: object
    choices: tuple = ()
    evidence: str = ''


@dataclass(frozen=True)
class WorkshopProjection:
    game_id: str
    platform_id: str
    title: str
    dashboard: object
    fields: object
    evidence: tuple


def workshop_snapshot(document):
    """Return the existing immutable projection of verified opened values."""
    backend.validate_document(document)
    presentation = ScalarPresentation(backend, backend.GAME_ID)
    snapshot = presentation.dashboard(document)
    note = ('SW4 DX exposes stored officer base stats and existing weapon skills. '
            'No derived or effective battle-stat formula is mapped.')
    return replace(snapshot, note=f'{snapshot.note} {note}'.strip())


def workshop_projection(document, backend=backend):
    """Expose only parser-mapped values and parser-qualified field choices."""
    backend.validate_document(document)
    projected = {}
    for field in backend.fields_for(document):
        if field.group in ('Officers', 'Equipment', 'Unlocks'):
            character_id = f'officer:{field.slot - 1}'
        elif field.group == 'Weapons':
            character_id = f'weapon:{field.slot - 1}'
        else:
            character_id = 'save'
        choices = tuple(backend.field_options(document, field.id))
        projected[field.id] = WorkshopField(
            field.id, field.label, field.group, character_id,
            field.value(document.payload), choices,
            EVIDENCE[0] if field.group in ('Officers', 'Equipment', 'Weapons')
            else EVIDENCE[1] + ' Stored parser field; no gameplay formula is applied.',
        )
    snapshot = workshop_snapshot(document)
    return WorkshopProjection(backend.GAME_ID, PLATFORM_ID, snapshot.title,
                              snapshot, MappingProxyType(projected), EVIDENCE)


def equipment_choices(document, field_id):
    """Return only existing occupied own-pool weapon slots for an officer.

    The parser performs the authoritative qualification used by its current
    editor, preserving native choices and labels without a second ID catalog.
    Other field choices (skill activation and unlocks) are not equipment.
    """
    backend.validate_document(document)
    field = backend.field_map(document).get(field_id)
    if field is None:
        raise SaveError('Choose a mapped Samurai Warriors 4 DX field.')
    if field.group != 'Equipment':
        return ()
    return backend.field_options(document, field_id)


def field_choices(document, field_id):
    """Expose any existing parser-qualified choices for planned field values."""
    backend.validate_document(document)
    if field_id not in backend.field_map(document):
        raise SaveError('Choose a mapped Samurai Warriors 4 DX field.')
    return backend.field_options(document, field_id)

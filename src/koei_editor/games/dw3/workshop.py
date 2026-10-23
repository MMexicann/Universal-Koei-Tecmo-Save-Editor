"""Read-only, BuildPlan-compatible snapshots for the DW3 character workshop.

This module projects values already exposed by the DW3 progression dashboard
and verified weapon metadata. It does not calculate an overall combat stat,
stage edits, or retain the save document.
"""
from __future__ import annotations

from collections.abc import Mapping

from koei_editor.games.dw3 import officer_weapon_editor, progression_dashboard, save_writer
from koei_editor.games.dw3.models import Change, SaveDocument, SaveError, fields


GAME_ID = 'dw3'
PLATFORM_ID = 'windows_pc'
_STAT_METRICS = {'SPoint', 'MaxHealth', 'MaxMusou', 'Attack', 'Defence'}
_STAT_LABELS = {
    'SPoint': 'Merit',
    'MaxHealth': 'Life / HP',
    'MaxMusou': 'Musou',
    'Attack': 'Attack',
    'Defence': 'Defense',
}
_OFFICER_COUNT = 42


def character_build_plans(document: SaveDocument) -> tuple[dict, ...]:
    """Return saved build snapshots for mapped playable officer records.

    The result contains only JSON-compatible values and can be passed to the
    shared ``BuildPlan`` constructor. It omits absent/unsupported values and
    records their status in ``notes`` instead of replacing them with zero.
    """
    _require_document(document)
    dashboard = progression_dashboard.dashboard(document)
    character_section = next((section for section in dashboard.sections
                              if section.id == 'characters'), None)
    if character_section is None:
        raise SaveError('The opened save has no mapped officer dashboard.')
    equipment_section = next((section for section in dashboard.sections
                              if section.id == 'equipment'), None)
    equipment_cards = {
        card.id: card for card in (equipment_section.cards if equipment_section else ())
    }
    weapons = {row['data_id']: row for row in officer_weapon_editor.states(document)}
    count = min(_OFFICER_COUNT, len(document.records('PCSaveDataArray')))
    plans = []
    for card in character_section.cards:
        if not card.id.startswith('officer-'):
            continue
        try:
            officer_id = int(card.id.removeprefix('officer-'))
        except ValueError:
            continue
        if not 0 <= officer_id < count:
            continue
        plans.append(_character_build_plan(
            document, officer_id, card.title, card.metrics, equipment_cards, weapons,
            name=f'Opened build · {card.title}',
        ))
    return tuple(plans)


def character_build_plan(document: SaveDocument, character_id: int | str,
                         name: str = 'Opened build') -> dict:
    """Return one officer's current build in the shared preset shape.

    ``character_id`` is the native playable-officer record index. The returned
    values reference existing stable DW3 field IDs; equipment records describe
    the saved reference and mapped weapon configuration only.
    """
    _require_document(document)
    officer_id = _officer_index(character_id)
    if officer_id >= min(_OFFICER_COUNT, len(document.records('PCSaveDataArray'))):
        raise SaveError('Choose a mapped playable officer record present in this save.')
    if not isinstance(name, str) or not name.strip():
        raise SaveError('A build plan needs a non-empty name.')

    dashboard = progression_dashboard.dashboard(document)
    character_section = next((section for section in dashboard.sections
                              if section.id == 'characters'), None)
    if character_section is None:
        raise SaveError('The opened save has no mapped officer dashboard.')
    card = next((item for item in character_section.cards
                 if item.id == f'officer-{officer_id}'), None)
    if card is None:
        raise SaveError('This officer has no mapped dashboard record.')
    equipment_section = next((section for section in dashboard.sections
                              if section.id == 'equipment'), None)
    equipment_cards = {
        item.id: item for item in (equipment_section.cards if equipment_section else ())
    }
    weapons = {row['data_id']: row for row in officer_weapon_editor.states(document)}
    return _character_build_plan(
        document, officer_id, card.title, card.metrics, equipment_cards, weapons,
        name=name,
    )


def _character_build_plan(document, officer_id, character_name, metrics,
                          equipment_cards: Mapping[str, object], weapons: Mapping[int, dict],
                          *, name: str) -> dict:
    values = {}
    notes = [
        f'Mapped character: {character_name} (officer record {officer_id}).',
        'Read-only snapshot from the opened Dynasty Warriors 3 Remastered save.',
        'Permanent officer stats and weapon/item effects are separate; no combined combat-stat formula is inferred.',
        'Stat evidence: existing DW3 progression dashboard and verified native officer fields.',
    ]

    present_stats = set()
    for metric in metrics:
        field_id = getattr(metric, 'field_id', None)
        if not isinstance(field_id, str):
            continue
        prefix = f'officer:{officer_id}:'
        if not field_id.startswith(prefix):
            continue
        stat_id = field_id[len(prefix):]
        if stat_id not in _STAT_METRICS:
            continue
        # The existing dashboard displays the mapped saved integer directly.
        # Reject any unexpected rendering rather than parsing a guessed value.
        display = getattr(metric, 'value', None)
        if not isinstance(display, str) or not display.lstrip('-').isdigit():
            notes.append(f'Unavailable: {_STAT_LABELS[stat_id]} is not a supported integer in this record.')
            continue
        values[field_id] = int(display)
        present_stats.add(stat_id)

    for stat_id, label in _STAT_LABELS.items():
        if stat_id not in present_stats:
            notes.append(f'Unavailable: {label} is not exposed for this saved officer record.')

    equipment = {}
    officer = fields(document.records('PCSaveDataArray')[officer_id])
    reference_prop = officer.get('WeaponDataID')
    reference = reference_prop.get('value') if isinstance(reference_prop, dict) else None
    if type(reference) is int:
        equipment['weapon_reference'] = reference
        weapon_card = equipment_cards.get(f'weapon-{reference}')
        if weapon_card is None or reference not in weapons:
            notes.append(
                f'Weapon reference {reference} is saved but does not resolve to a mapped owned weapon copy; '
                'it is retained as a reference and is not treated as an empty slot.'
            )
        else:
            _add_weapon_config(equipment, notes, weapons[reference])
    else:
        notes.append('Unavailable: this officer record has no supported integer weapon reference.')

    return {
        'game_id': GAME_ID,
        'platform_id': PLATFORM_ID,
        'character_id': str(officer_id),
        'name': name.strip(),
        'values': values,
        'equipment': equipment,
        'notes': '; '.join(notes),
    }


def _add_weapon_config(equipment, notes, row):
    """Copy only weapon data already mapped by the existing DW3 dashboard."""
    data_id = row.get('data_id')
    if type(data_id) is int:
        equipment['weapon_copy_data_id'] = data_id
    weapon_id = row.get('weapon_id')
    if type(weapon_id) is int:
        equipment['weapon_id'] = weapon_id
    metadata = row.get('metadata')
    metadata = metadata if isinstance(metadata, dict) else {}
    weapon_name = metadata.get('name') or metadata.get('weapon_name')
    if isinstance(weapon_name, str) and weapon_name:
        equipment['weapon_name'] = weapon_name
    else:
        notes.append(f'Weapon copy {row.get("data_id")} has no verified catalogue name.')

    rank = row.get('rank')
    if type(rank) is int:
        equipment['weapon_rank'] = rank
    else:
        notes.append(f'Weapon copy {row.get("data_id")} has no verified rank value.')

    base_power = metadata.get('base_power')
    if type(base_power) is int:
        equipment['weapon_base_attack'] = base_power
        notes.append('Catalogue base attack is separate from permanent officer Attack.')
    else:
        notes.append(f'Weapon copy {row.get("data_id")} has no mapped catalogue base attack.')

    elements = row.get('elements')
    if row.get('element_editable') is True and type(elements) is int:
        equipment['weapon_element_mask'] = elements
    else:
        notes.append(f'Weapon copy {row.get("data_id")} element configuration is unavailable for planning.')

    skills = row.get('skills')
    if not isinstance(skills, (list, tuple)):
        notes.append(f'Weapon copy {row.get("data_id")} bonus slots are unavailable.')
        return
    mapped = 0
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            notes.append(f'Weapon bonus slot {index + 1} is unavailable.')
            continue
        item_id = skill.get('id')
        value = skill.get('value')
        if item_id is None and value == 0:
            continue
        if type(item_id) is not int or type(value) is not int or item_id not in officer_weapon_editor.ITEMS:
            notes.append(f'Weapon bonus slot {index + 1} has an unmapped identity or value and is omitted.')
            continue
        equipment[f'weapon_bonus_{index}_id'] = item_id
        equipment[f'weapon_bonus_{index}_value'] = value
        mapped += 1
    if mapped:
        notes.append('Weapon bonus identities and rolls use the existing mapped weapon records.')


def workshop_view_data(document):
    """Return plans and display metadata for the DW3 graphical workspace."""
    plans = character_build_plans(document)
    dashboard = progression_dashboard.dashboard(document)
    labels = {
        'weapon_reference': 'Saved officer weapon reference',
        'weapon_copy_data_id': 'Mapped weapon copy ID',
        'weapon_id': 'Weapon identity ID',
        'weapon_name': 'Weapon catalogue name',
        'weapon_rank': 'Weapon rank',
        'weapon_base_attack': 'Catalogue base attack',
        'weapon_element_mask': 'Weapon element mask',
    }
    metadata = {}
    for plan in plans:
        character_id = plan['character_id']
        for field_id, value in plan['values'].items():
            stat = field_id.rsplit(':', 1)[-1]
            metadata[field_id] = {
                'label': _STAT_LABELS.get(stat, field_id),
                'category': 'Officer stats',
                'character_id': character_id,
                'current_value': value,
                'value_type': 'integer',
                'evidence': 'Existing mapped DW3 permanent officer field; weapon bonuses stay separate.',
            }
        for slot_id, value in plan['equipment'].items():
            label = labels.get(slot_id)
            if label is None and slot_id.startswith('weapon_bonus_'):
                parts = slot_id.split('_')
                if len(parts) == 4 and parts[2].isdigit():
                    label = (f'Weapon bonus {int(parts[2]) + 1} '
                             + ('identity ID' if parts[3] == 'id' else 'roll'))
            if label is None:
                label = slot_id.replace('_', ' ').title()
            metadata[slot_id] = {
                'label': label,
                'category': 'Weapon configuration',
                'character_id': character_id,
                'current_value': value,
                'value_type': 'integer' if type(value) is int else 'string',
                'evidence': 'Existing mapped owned weapon reference or configuration; editor validates changes.',
            }

    plans_by_weapon = {
        plan['equipment'].get('weapon_copy_data_id'): plan['character_id']
        for plan in plans if type(plan['equipment'].get('weapon_copy_data_id')) is int
    }
    verified = []
    for section in dashboard.sections:
        for card in section.cards:
            owner = None
            if card.id.startswith('officer-'):
                owner = card.id.removeprefix('officer-')
            elif card.id.startswith('weapon-'):
                suffix = card.id.removeprefix('weapon-')
                if suffix.isascii() and suffix.isdecimal():
                    owner = plans_by_weapon.get(int(suffix))
            if owner is None:
                continue
            for metric in card.metrics:
                verified.append({
                    'character_id': owner,
                    'label': metric.label,
                    'value': metric.value,
                    'evidence': metric.note or
                        'Existing DW3 progression dashboard or verified weapon catalogue data.',
                })
    return plans, metadata, tuple(verified)


def changes_from_build_plan(document: SaveDocument, plan, pending=()) -> list[Change]:
    """Translate supported DW3 values into the existing validated change API.

    The editor still submits the complete result to ``stage_many``. This
    function does not stage, serialize or write save bytes.
    """
    _require_document(document)
    if isinstance(plan, Mapping):
        get = plan.get
    else:
        get = lambda name, default=None: getattr(plan, name, default)
    if get('game_id') != GAME_ID or get('platform_id') != PLATFORM_ID:
        raise SaveError('This build plan belongs to a different game or platform.')
    character_id = _officer_index(get('character_id'))
    baseline = character_build_plan(document, character_id)
    expected_prefix = f'officer:{character_id}:'
    values = get('values', {})
    equipment = get('equipment', {})
    if not isinstance(values, Mapping) or not isinstance(equipment, Mapping):
        raise SaveError('The DW3 build plan has invalid assignments.')

    changes = []
    for field_id, value in values.items():
        if not isinstance(field_id, str) or not field_id.startswith(expected_prefix):
            raise SaveError('The build plan contains a stat for a different officer.')
        field = field_id[len(expected_prefix):]
        if field not in save_writer.OFFICER_FIELDS:
            raise SaveError(f'{field_id} is not a supported permanent officer field.')
        changes.append(Change('officer', character_id, field, value))

    descriptor_fields = {
        'weapon_reference', 'weapon_copy_data_id', 'weapon_id', 'weapon_name',
        'weapon_rank', 'weapon_base_attack',
    }
    supported_equipment = descriptor_fields | {'weapon_element_mask'}
    for index in range(9):
        supported_equipment.update((f'weapon_bonus_{index}_id', f'weapon_bonus_{index}_value'))
    if set(equipment) - supported_equipment:
        raise SaveError('The build plan contains an unknown DW3 weapon configuration field.')
    for field_id in descriptor_fields:
        if (field_id in equipment
                and equipment[field_id] != baseline['equipment'].get(field_id)):
            raise SaveError(f'{field_id} identifies saved equipment and cannot be changed in the workshop.')

    configurable = {'weapon_element_mask'}
    configurable.update(f'weapon_bonus_{index}_{suffix}'
                        for index in range(9) for suffix in ('id', 'value'))
    planned_config = {key: value for key, value in equipment.items() if key in configurable}
    if planned_config:
        data_id = baseline['equipment'].get('weapon_copy_data_id')
        if type(data_id) is not int:
            raise SaveError('The opened officer has no mapped owned weapon copy to configure.')
        state = officer_weapon_editor.state(document, data_id, pending)
        if not state['editable']:
            raise SaveError(state['reason'])
        if ('weapon_element_mask' in planned_config
                and planned_config['weapon_element_mask'] != state['elements']):
            changes.append(Change('weapon_element', data_id, 'Elements',
                                  planned_config['weapon_element_mask']))
        planned_bonus_fields = {key: value for key, value in planned_config.items()
                                if key.startswith('weapon_bonus_')}
        if planned_bonus_fields:
            skills = [dict(skill) for skill in state['skills']]
            for index in range(9):
                item_key = f'weapon_bonus_{index}_id'
                value_key = f'weapon_bonus_{index}_value'
                if item_key in planned_bonus_fields:
                    skills[index]['id'] = planned_bonus_fields[item_key]
                if value_key in planned_bonus_fields:
                    skills[index]['value'] = planned_bonus_fields[value_key]
            if skills != state['skills']:
                changes.append(Change('weapon_roll', data_id, 'Skills', skills))
    return changes


def _officer_index(value):
    if type(value) is int:
        if value < 0:
            raise SaveError('Officer record IDs must be nonnegative integers.')
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise SaveError('Officer record IDs must be nonnegative integer indexes.')


def _require_document(document):
    if not isinstance(document, SaveDocument):
        raise SaveError('A parsed Dynasty Warriors 3 Remastered save is required.')

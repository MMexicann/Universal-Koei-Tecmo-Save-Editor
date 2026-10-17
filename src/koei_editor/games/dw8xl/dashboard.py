"""Read-only projections of the qualified DW8 XL PC snapshot.

Only aptitude has a verified progress denominator. Physical records do not
establish recruitment, story completion or inventory capacity.
"""
from koei_editor.games.dw3.game_content import DW8_ATTRIBUTE_NAMES, record_label
from koei_editor.shared.progression import (
    DashboardCard, DashboardMetric, DashboardSection, ProgressionDashboard,
)


def _metric(identity, label, value, **kwargs):
    displayed = f'{value:,}' if type(value) is int else str(value)
    return DashboardMetric(identity, label, displayed, **kwargs)


def dashboard(backend, document):
    backend.validate_document(document)
    fields = {field.id: field for field in backend.fields_for(document)}

    def opened(key, label=None):
        field = fields[key]
        return _metric(key, label or field.label,
                               field.value(document.payload), field_id=key)

    def link(key):
        return key if key in fields else None

    weapons = backend.weapons(document)
    weapon_map = {row['slot']: row for row in weapons}
    characters = []
    actions = ('Dash', 'Dive', 'Shadow Sprint', 'Whirlwind')
    compatibility = backend.compatibilities(document)
    progressions = backend.progressions(document)
    references = {}
    for index, progress in enumerate(progressions):
        for position, weapon_slot in enumerate(progress['weapon_slots']):
            references.setdefault(weapon_slot, []).append(f'Officer {index + 1} · weapon {position + 1}')
    for index, progress in enumerate(progressions):
        slot = index + 1
        metrics = [_metric('level', 'Level', progress['level']),
                   _metric('experience', 'Experience', progress['experience'],
                                   note='XP thresholds are not mapped; no level percentage is inferred.'),
                   *(opened(f'officer_{index}_{key}') for key in ('hp', 'attack', 'defense'))]
        for action_index, (action, units) in enumerate(zip(actions, compatibility[index])):
            key = f'officer_{index}_compatibility_{action_index}'
            known = units in (25, 50, 75, 100)
            metrics.append(_metric(
                key, f'{action} aptitude', f'{units // 25} / 4 stars' if known else f'{units} stored units',
                field_id=link(key), current=units // 25 if known else None,
                total=4 if known else None,
                note='25 stored units per star.' if known else 'Unusual opened value; no star count inferred.'))
        metrics.extend((_metric('leadership', 'Leadership', progress['leadership']),
                        _metric('leadership_xp', 'Leadership XP', progress['leadership_experience'])))
        for position, weapon_slot in enumerate(progress['weapon_slots']):
            record = weapon_map.get(weapon_slot)
            value = (f'Slot {weapon_slot:04} · ID {record["id"]} · attack {record["attack"]}' if record is not None
                     else f'Slot {weapon_slot:04} · unqualified reference')
            metrics.append(_metric(
                f'equipped_{position}', f'Equipped weapon {position + 1}', value,
                field_id=link(f'officer_{index}_first_weapon') if position == 0 else None))
        characters.append(DashboardCard(
            f'officer_{slot}', record_label('dw8xl', slot, 'Officers'),
            f'Level {progress["level"]} · Physical officer record {slot}',
            tuple(metrics), section='Characters', search_text=f'officer {slot}'))

    equipment = []
    for row in weapons:
        index = row['slot'] - 1
        metrics = [_metric('identity', 'Weapon ID', row['id']),
                   _metric('attack', 'Stored attack', row['attack']),
                   _metric('affinity', 'Affinity ID', row['affinity'],
                                   field_id=link(f'weapon_{index}_affinity'),
                                   note='Native identity; Heaven/Earth/Man names are not mapped.')]
        usages = references.get(row['slot'], ())
        metrics.append(_metric('references', 'Saved equipped references', '; '.join(usages) or 'None',
                               note='References are shown independently from weapon ownership and compatibility.'))
        for attribute, (identity, rank) in enumerate(row['attributes']):
            if identity == 255:
                continue
            name = DW8_ATTRIBUTE_NAMES.get(identity, f'Attribute ID {identity}')
            metrics.append(_metric(
                f'attribute_{attribute}', name, rank,
                field_id=link(f'weapon_{index}_attribute_{attribute}_rank'),
                note=f'Native attribute ID {identity}; stored rank.'))
        equipment.append(DashboardCard(
            f'weapon_{row["slot"]}', f'Weapon slot {row["slot"]:04}',
            f'ID {row["id"]} · Stored attack {row["attack"]}', tuple(metrics),
            section='Equipment', search_text=' '.join((*usages, *(metric.label for metric in metrics)))))

    resources = tuple(DashboardCard(key, fields[key].label,
                                   metrics=(opened(key),), section='Resources')
                      for key in ('gold', 'gems', 'facility_materials', 'weapon_materials'))
    allies = tuple(DashboardCard(
        f'ally_{row["slot"]}', f'Ally physical slot {row["slot"]}',
        'Recruitment and ownership are not mapped',
        (_metric('skill_level', 'Skill level', row['skill_level']),
         _metric('skill_xp', 'Skill XP', row['skill_experience']),
         _metric('support_ids', 'Support skill IDs', ', '.join(map(str, row['support_skill_ids']))),
         _metric('male_bond', 'Male bond (stored)', row['male_bond']),
         _metric('female_bond', 'Female bond (stored)', row['female_bond'])),
        section='Allies') for row in backend.bodyguards(document))
    completion = (DashboardCard(
        'mapped_records', 'Mapped snapshot coverage',
        'Record counts are separate from game completion',
        (_metric('officers', 'Physical officer records', len(characters)),
         _metric('weapons', 'Populated weapon records', len(equipment)),
         _metric('story', 'Story / character unlock completion', 'Not mapped',
                         note='No completion percentage or recruitment state is inferred.')),
        section='Completion'),)
    known_aptitudes = [units for row in compatibility for units in row if units in (25, 50, 75, 100)]
    unresolved = sum(slot not in weapon_map for row in progressions for slot in row['weapon_slots'])
    overview = (
        DashboardCard('officer-snapshot', 'Officer snapshot', 'Physical records · unlock state unavailable',
                      (_metric('records', 'Officer records', len(characters)),
                       _metric('level-range', 'Stored level range',
                               f'{min(row["level"] for row in progressions)}–{max(row["level"] for row in progressions)}')),
                      section='Overview'),
        DashboardCard('equipment-snapshot', 'Weapon inventory', 'Qualified populated records',
                      (_metric('records', 'Weapon records', len(equipment)),
                       _metric('identities', 'Distinct weapon IDs', len({row['id'] for row in weapons})),
                       _metric('unresolved', 'Unresolved equipped references', unresolved,
                               note='Unknown and empty references are retained; no weapon is created or assigned.')),
                      section='Overview'),
        DashboardCard('aptitude-snapshot', 'Weapon-action aptitude', 'Verified star encoding only',
                      (_metric('four-stars', 'Four-star action records', known_aptitudes.count(100)),
                       _metric('unusual', 'Unusual stored action values',
                               sum(len(row) for row in compatibility) - len(known_aptitudes),
                               note='Only stored units 25, 50, 75 and 100 map to stars.')),
                      section='Overview'),
    )
    return ProgressionDashboard(
        'Dynasty Warriors 8 XL · Progression',
        (DashboardSection('overview', 'Overview', overview,
                          'Snapshot counts describe mapped records, not collection capacity or campaign completion.'),
         DashboardSection('characters', 'Characters', tuple(characters),
                          'Numbered officer identities are verified physical records, not unlock states.'),
         DashboardSection('equipment', 'Equipment', tuple(equipment),
                          'Existing populated records only; the physical pool is not inventory capacity.'),
         DashboardSection('resources', 'Resources', resources,
                          'Opened balances; editing bounds are not completion targets.'),
         DashboardSection('allies', 'Allies', allies,
                          'Read-only physical records; names, recruitment and reward dependencies are unmapped.'),
         DashboardSection('completion', 'Completion', completion)),
        'Opened save values only. Dashboard navigation never stages edits.')

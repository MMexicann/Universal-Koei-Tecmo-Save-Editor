"""Read-only projections of the Remastered tagged schema and reviewed metadata."""
from koei_editor.games.dw3.models import SaveDocument, SaveError, fields
from koei_editor.games.dw3 import collection_editor, officer_weapon_editor, progression_editor, save_writer
from koei_editor.resources import read_json
from koei_editor.shared.progression import DashboardMetric as Metric, DashboardCard as Card
from koei_editor.shared.progression import DashboardSection as Section, ProgressionDashboard

NAMES = read_json('officer_names.json')
LABELS = {'SPoint': 'Merit', 'MaxHealth': 'Life / HP', 'MaxMusou': 'Musou',
          'Attack': 'Attack', 'Defence': 'Defense'}


def dashboard(document):
    """Display the opened document only; pending Change objects are never applied."""
    if not isinstance(document, SaveDocument):
        raise SaveError('A parsed Dynasty Warriors 3 Remastered save is required.')
    characters = []
    weapon_states = tuple(officer_weapon_editor.states(document))
    weapon_by_id = {row['data_id']: row for row in weapon_states}
    unlocked = document.properties['CanUseCharaArray']['value']['values']
    weapon_references = {}
    for index, record in enumerate(document.records('PCSaveDataArray')[:42]):
        row = fields(record)
        metrics = []
        for key, label in LABELS.items():
            prop = row.get(key)
            if prop is None or prop.get('type') != 'IntProperty' or type(prop.get('value')) is not int:
                continue
            value = prop['value']
            metrics.append(Metric(key, label, str(value), field_id=f'officer:{index}:{key}',
                                  note='Verified permanent base stat; equipment bonuses are separate.' if key != 'SPoint' else
                                  'Stored Merit; a character level is not inferred.'))
        reference = row.get('WeaponDataID', {}).get('value')
        if type(reference) is int:
            equipped = weapon_by_id.get(reference)
            title = _weapon_name(equipped) if equipped else 'Unresolved inventory reference'
            weapon_references.setdefault(reference, []).append(NAMES.get(str(index), f'Officer {index}'))
            metrics.append(Metric('equipped-weapon', 'Equipped weapon reference',
                                  f'{reference} · {title}',
                                  note='Reference is displayed as saved; an unresolved reference does not imply an empty slot.'))
        availability = ('Unlocked' if unlocked[index] else 'Locked') if index < len(unlocked) else 'Unlock flag unavailable'
        characters.append(Card(f'officer-{index}', NAMES.get(str(index), f'Officer {index}'),
                               availability, tuple(metrics),
                               search_text=f'officer {index} {availability}'))

    equipment = []
    for row in weapon_states:
        elements = ', '.join(name for name, mask in officer_weapon_editor.ELEMENTS.items()
                             if mask and row['elements'] & mask == mask)
        metrics = [Metric('rank', 'Weapon rank', str(row.get('rank', 'Unmapped'))),
                   Metric('elements', 'Weapon elements', elements or ('None' if row['elements'] == 0 else 'Unmapped'),
                          note=f"Stored mapped element mask: {row['elements']}.")]
        references = weapon_references.get(row['data_id'], ())
        metrics.append(Metric('references', 'Saved equipped references', ', '.join(references) or 'None',
                              note='Saved officer references; permanent officer stats and weapon bonuses remain separate.'))
        power = row['metadata'].get('base_power')
        if power is not None:
            metrics.append(Metric('base-attack', 'Catalogue base attack', str(power),
                                  note='Verified weapon metadata; separate from permanent officer attack.'))
        for index, skill in enumerate(row['skills']):
            if skill['id'] is None:
                continue
            metadata = officer_weapon_editor.ITEMS.get(skill['id'], {})
            metrics.append(Metric(f'bonus-{index}', metadata.get('name', f"Bonus ID {skill['id']}"),
                                  str(skill['value']), field_id=f"weapon:{row['data_id']}:Skills"))
        equipment.append(Card(f"weapon-{row['data_id']}", _weapon_name(row),
                              f"Owned {'unique' if row['array'] == 'UniqueWeaponDataArray' else 'regular'} copy · reference {row['data_id']}",
                              tuple(metrics), section='Equipment',
                              search_text=' '.join((*references, elements,
                                                    'unique' if row['array'] == 'UniqueWeaponDataArray' else 'regular'))))
    for index, record in enumerate(document.records('EquipItemDataArray')):
        metadata = save_writer.ITEMS.get(index)
        if metadata is None:
            continue
        row = fields(record)
        identity = row.get('EquipItemID', {}).get('value')
        if identity != 'EEquipItemID::' + metadata['enum']:
            continue  # Empty and foreign identities are not owned officer items.
        value = row.get('Value', {}).get('value')
        item_metrics = [Metric('ownership', 'Saved ownership', 'Owned')]
        if type(value) is int and metadata['kind'] == 'normal':
            item_metrics.append(Metric('roll', 'Saved item roll', str(value),
                                       field_id=f'item:{index}:Value'))
        equipment.append(Card(f'item-{index}', metadata['name'],
                              f"Owned {metadata['kind']} officer item", tuple(item_metrics), section='Equipment'))

    elixirs = progression_editor.elixir_state(document)
    resources = () if elixirs['value'] is None else (Card(
        'elixirs', 'Huanglong Elixirs', metrics=(Metric('elixirs', 'Saved balance', str(elixirs['value']),
                                                     field_id='progression:0:HuanglongElixirs' if elixirs['editable'] else None,
                                                     note=elixirs['reason']),), section='Resources'),)

    completion = []
    try:
        story = progression_editor.progression_state(document)
    except (SaveError, KeyError, TypeError, IndexError):
        story = None
    if story is not None:
        for row in story['officers']:
            if not row['has_musou_route']:
                continue
            current, total = row['progress'], row['route_length']
            bounded = 0 <= current <= total
            completion.append(Card(f"route-{row['officer_id']}", NAMES.get(str(row['officer_id']), f"Officer {row['officer_id']}"),
                                   'Musou route', (
                                       Metric('route-progress', 'Saved route progress', f'{current} / {total}',
                                              current=current if bounded else None, total=total if bounded else None,
                                              field_id=f"story:{row['officer_id']}:MusouCleared",
                                              note='Route progress and its separate cleared flag are displayed independently.'),
                                       Metric('cleared', 'Saved cleared flag',
                                              ('Cleared' if row['cleared'] else 'Not cleared') if row['can_clear'] else 'Unavailable'),
                                   ), section='Completion'))
        for row in story['side_stories']:
            completion.append(Card(f"side-{row['id']}", row['name'], 'Side story availability', (
                Metric('available', 'Musou availability', 'Unlocked' if row['unlocked'] else 'Locked'),
                Metric('free-mode', 'Free Mode stages', 'Unlocked' if row['free_mode_unlocked'] else 'Not all unlocked'),
            ), section='Completion'))
    else:
        completion.append(Card('story-unavailable', 'Musou progression', 'Mapping unavailable for this layout', (
            Metric('story', 'Story progression', 'Unavailable',
                   note='Missing or unsupported route records are not treated as zero completion.'),
        ), section='Completion'))
    collections = collection_editor.collection_state(document)
    for key, row in collections.items():
        if not row['editable']:
            continue  # Missing/unsupported arrays are not zero-percent collections.
        label = collection_editor.DATA[key]['label']
        completion.append(Card(f'collection-{key}', label, 'Mapped gallery entries only', (
            Metric('unlocked', 'Unlocked entries', f"{row['owned']} / {row['total']}",
                   current=row['owned'], total=row['total'], field_id=f'collection:0:{key}'),
            *(Metric(f"entry-{item['id']}", item['name'], 'Unlocked' if item['unlocked'] else 'Locked',
                     field_id=f"collection:{item['id']}:{key}")
              for item in row['rows']),
        ), section='Completion'))

    known_unlocks = unlocked[:len(characters)]
    overview = [Card('character-snapshot', 'Character roster', 'Mapped playable officer flags', (
        Metric('unlocked', 'Unlocked mapped officers', f'{sum(bool(value) for value in known_unlocks)} / {len(known_unlocks)}',
               current=sum(bool(value) for value in known_unlocks), total=len(known_unlocks),
               note='Only available saved flags for the displayed officer records; separate from Musou completion.'),
        Metric('records', 'Displayed officer records', str(len(characters))),
    ), section='Overview'), Card('equipment-snapshot', 'Owned equipment', 'Saved inventory copies', (
        Metric('weapons', 'Owned weapon copies', str(len(weapon_states))),
        Metric('items', 'Owned mapped officer items', str(len(equipment) - len(weapon_states))),
        Metric('unresolved', 'Unresolved equipped references',
               str(sum(len(names) for reference, names in weapon_references.items() if reference not in weapon_by_id)),
               note='Unresolved references remain visible and never become an inferred empty slot.'),
    ), section='Overview')]
    if story is not None:
        routes = [row for row in story['officers'] if row['has_musou_route'] and row['can_clear']]
        cleared = sum(row['cleared'] for row in routes)
        overview.append(Card('route-snapshot', 'Musou clear history', 'Saved route-cleared flags', (
            Metric('cleared', 'Cleared mapped routes', f'{cleared} / {len(routes)}',
                   current=cleared, total=len(routes),
                   note='Counts only routes with an available saved cleared flag. Route stage counts are shown separately.'),
        ), section='Overview'))
    for key, row in collections.items():
        if row['editable']:
            overview.append(Card(f'gallery-{key}', collection_editor.DATA[key]['label'], 'Mapped gallery ownership', (
                Metric('unlocked', 'Unlocked mapped entries', f'{row["owned"]} / {row["total"]}',
                       current=row['owned'], total=row['total'], field_id=f'collection:0:{key}',
                       note='Gallery entries only; inventory copies and gallery ownership are independent.'),
            ), section='Overview'))

    return ProgressionDashboard('Dynasty Warriors 3 Remastered', (
        Section('overview', 'Overview', tuple(overview),
                'Verified roster, route flags and gallery records; no overall game completion percentage.'),
        Section('characters', 'Characters', tuple(characters),
                'Stored Merit and permanent base stats. No character levels are inferred.'),
        Section('equipment', 'Equipment', tuple(equipment),
                'Owned inventory and saved equipped references. Collection gallery ownership is separate.'),
        Section('resources', 'Resources', resources,
                '' if resources else 'The saved resource balance is unavailable for this layout.'),
        Section('completion', 'Completion', tuple(completion),
                'Individual mapped routes and galleries only; no overall game completion percentage.'),
    ), note='Opened-save snapshot. Pending edits remain in the editor and are not reflected here.')


def _weapon_name(row):
    metadata = row['metadata']
    return metadata.get('name') or metadata.get('weapon_name') or f"Weapon ID {row['weapon_id']}"

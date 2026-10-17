"""Native Steam WO3U progression, inventory and resource projections.

These are opened snapshot values, using the same offsets and identities as the
existing parser/inspector. XP, promotions and record counts imply no unlocks.
"""
from koei_editor.games.wo3u import wo3u_equipment as equipment
from koei_editor.shared.progression import (
    DashboardCard, DashboardMetric, DashboardSection, ProgressionDashboard,
)


def _metric(identity, label, value, **kwargs):
    displayed = f'{value:,}' if type(value) is int else str(value)
    return DashboardMetric(identity, label, displayed, **kwargs)


def dashboard(backend, document):
    backend.validate_document(document)
    payload = document.payload
    fields = {field.id: field for field in backend.fields_for(document)}

    def link(key):
        return key if key in fields else None

    def number(offset, size):
        return int.from_bytes(payload[offset:offset + size], 'little')

    def opened(key, label=None):
        field = fields[key]
        return _metric(key, label or field.label, field.value(payload), field_id=key)

    inventory = backend.item_inventory(document)
    items_by_id = {row['id']: row for row in inventory}
    characters, internal = [], []
    for index in range(backend.SERIALIZED_OFFICER_COUNT):
        base = backend.OFFICER_BASE + index * backend.OFFICER_STRIDE
        level, experience = payload[base + 17] + 1, number(base + 26, 4)
        playable = index < backend.OFFICER_COUNT
        metrics = [_metric('level', 'Stored level', level),
                   _metric('experience', 'Experience', experience,
                                   note='XP thresholds are not mapped; no level percentage is inferred.'),
                   _metric('promotions', 'Promotions', payload[base + 62],
                                   note='Read only; promotion dependencies are preserved.'),
                   _metric('upgrade_stones', 'Unallocated upgrade stones',
                                   number(base + backend.UPGRADE_STONE_OFFSET, 2),
                                   field_id=link(f'officer_{index}_upgrade_stones'))]
        if playable:
            metrics.extend(opened(f'officer_{index}_{key}', label)
                           for key, label in (('health', 'Health'), ('musou', 'Musou'),
                                              ('attack', 'Attack'), ('defense', 'Defense'), ('speed', 'Speed')))
            count = payload[base + equipment.ITEM_SLOT_COUNT_OFFSET]
            metrics.append(_metric('item_slots', 'Stored item slot count', count,
                                           note='A stored count does not establish unlock or promotion completion.'))
            # The serializer has six references. Preserve and display unusual
            # opened selectors; only qualified references receive edit links.
            for item_slot in range(6):
                identity = payload[base + equipment.EQUIPPED_ITEM_OFFSET + item_slot]
                key = f'officer_{index}_equipped_item_{item_slot}'
                value = 'Unequipped' if identity == equipment.EMPTY_ITEM else f'Item ID {identity}'
                metrics.append(_metric(
                    f'item_{item_slot}', f'Item reference {item_slot + 1}', value,
                    field_id=link(key), note='Stored reference; ownership and rank appear separately in Equipment.'))
                item = items_by_id.get(identity)
                if item is not None:
                    metrics.append(_metric(
                        f'item_{item_slot}_state', f'Item {item_slot + 1} inventory state',
                        f'{"Owned" if item["owned"] else "Not owned"} · stored rank {item["rank"]}',
                        note='Ownership is read from the saved mask, independently from the equipped reference.'))
        card = DashboardCard(
            f'officer_{index + 1}', f'Officer {index + 1}' if playable else f'Internal record {index + 1}',
            f'Level {level} · {payload[base + 62]} promotions' if playable else 'Read-only serialized record',
            tuple(metrics), section='Characters' if playable else 'Internal records',
            search_text=f'officer {index + 1} promotions {payload[base + 62]}')
        (characters if playable else internal).append(card)

    weapon_cards, weapon_ids = [], set()
    for index in range(backend.WEAPON_COUNT):
        base = backend.WEAPON_BASE + index * backend.WEAPON_STRIDE
        identity = number(base, 2)
        if identity == 65535:
            continue
        weapon_ids.add(identity)
        owner, local_slot = index // 16 + 1, index % 16 + 1
        metrics = [_metric('identity', 'Weapon ID', identity),
                   _metric('officer-record', 'Officer weapon-pool record', owner,
                           note='Physical pool assignment; does not establish recruitment or equipped status.'),
                   _metric('slots', 'Stored attribute slots', payload[base + 2],
                                   field_id=link(f'weapon_{index}_slots')),
                   _metric('reinforcement', 'Reinforcement', payload[base + 3],
                                   field_id=link(f'weapon_{index}_reinforcement')),
                   _metric('compatibility', 'Compatibility (stored raw units)', number(base + 20, 4),
                                   field_id=link(f'weapon_{index}_compatibility_reset'),
                                   note='Grade descriptors are unavailable; no displayed stars, attack or maximum is inferred.')]
        for attribute in range(8):
            attribute_id = payload[base + 4 + attribute]
            if attribute_id == 255:
                continue
            name = backend.ATTRIBUTE_NAMES.get(attribute_id, f'Attribute ID {attribute_id}')
            metrics.append(_metric(
                f'attribute_{attribute}', name, payload[base + 12 + attribute],
                field_id=link(f'weapon_{index}_rank_{attribute}'),
                note=f'Native attribute ID {attribute_id}; stored rank.'))
        weapon_cards.append(DashboardCard(
            f'weapon_{index + 1}', f'Officer {owner} · Weapon {local_slot}',
            f'Weapon ID {identity}', tuple(metrics), section='Equipment',
            search_text=f'officer {owner} reinforcement {payload[base + 3]} ' +
                        ' '.join(metric.label for metric in metrics)))

    item_cards = tuple(DashboardCard(
        f'item_{row["id"]}', f'{row["kind"]} ID {row["id"]}',
        'Owned' if row['owned'] else 'Not owned',
        (_metric('owned', 'Ownership flag', 'Owned' if row['owned'] else 'Not owned'),
         _metric('rank', 'Stored rank', row['rank']),
         _metric('references', 'Equipped references', '; '.join(row['references']) or 'None')),
        section='Equipment', search_text=f'{row["kind"]} {"owned" if row["owned"] else "unowned"} ' +
                                        ' '.join(row['references'])) for row in inventory)
    mount_cards = []
    for index, offset in enumerate(equipment.MOUNT_LOADOUT_OFFSETS):
        selector = payload[offset]
        value = ('Unequipped' if selector == equipment.EMPTY_ITEM else
                 f'Mount item ID {equipment.MOUNT_ITEM_IDS[selector]}'
                 if selector < len(equipment.MOUNT_ITEM_IDS) else f'Unknown selector {selector}')
        mount_cards.append(DashboardCard(
            f'mount_loadout_{index}', f'Mount loadout {index + 1}', 'Stored mount reference',
            (_metric('mount', 'Equipped mount', value, field_id=link(f'mount_loadout_{index}')),),
            section='Equipment'))

    resources = []
    for field in fields.values():
        if field.group not in ('Resources', 'Attribute orbs', 'Crafting materials'):
            continue
        title = field.label
        if field.id.startswith('orb_'):
            identity = int(field.id.split('_')[1])
            title = f'{backend.ATTRIBUTE_NAMES.get(identity, f"Attribute ID {identity}")} orbs'
        resources.append(DashboardCard(
            field.id, title, field.group, (opened(field.id, 'Opened balance'),),
            section='Resources', search_text=f'{field.id} {field.label}'))

    completion = []
    for identity, kind, title in (('ordinary', 'Ordinary item', 'Mapped ordinary item ownership'),
                                  ('mount', 'Mount', 'Mapped mount ownership')):
        rows = tuple(row for row in inventory if row['kind'] == kind)
        owned = sum(row['owned'] for row in rows)
        completion.append(DashboardCard(
            f'ownership_{identity}', title, 'Ownership flags in the mapped inventory',
            (_metric('ownership', 'Mapped item records owned', f'{owned} / {len(rows)}',
                             current=owned, total=len(rows),
                             note='Coverage of these mapped inventory records only; separate from rank and equipped references.'),),
            section='Completion'))
    completion.append(DashboardCard(
        'story', 'Story and character unlocks', 'Completion mappings unavailable',
        (_metric('completion', 'Game completion', 'Not mapped',
                         note='Stored levels, promotions and physical records do not establish story or unlock completion.'),),
        section='Completion'))
    levels = [payload[backend.OFFICER_BASE + index * backend.OFFICER_STRIDE + 17] + 1
              for index in range(backend.OFFICER_COUNT)]
    overview = (
        DashboardCard('officer-snapshot', 'Officer snapshot', 'Mapped records · recruitment unavailable',
                      (_metric('records', 'Mapped officer records', len(characters)),
                       _metric('levels', 'Stored level range', f'{min(levels)}–{max(levels)}'),
                       _metric('internal', 'Separate internal records', len(internal))), section='Overview'),
        DashboardCard('weapon-snapshot', 'Weapon pools', 'Populated physical records',
                      (_metric('weapons', 'Populated weapon records', len(weapon_cards)),
                       _metric('identities', 'Distinct weapon IDs', len(weapon_ids))),
                      section='Overview'),
        DashboardCard('item-snapshot', 'Item collection', 'Verified ownership flags',
                      tuple(_metric(f'owned-{kind}', f'Owned {kind.lower()} records',
                                    sum(row['owned'] for row in inventory if row['kind'] == kind))
                            for kind in ('Ordinary item', 'Mount')), section='Overview'),
    )
    return ProgressionDashboard(
        'Warriors Orochi 3 Ultimate · Progression',
        (DashboardSection('overview', 'Overview', overview,
                          'Snapshot totals keep officer records, weapon pools, item ownership and story completion separate.'),
         DashboardSection('characters', 'Characters', tuple(characters),
                          '145 mapped officer records; numbered identities do not imply character unlocks.'),
         DashboardSection('equipment', 'Equipment', tuple(mount_cards) + tuple(weapon_cards) + item_cards,
                          'Weapons, ordinary items and mount references are distinct from acquisition and ranks.'),
         DashboardSection('resources', 'Resources', tuple(resources),
                          'Opened balances; published edit limits are not natural completion targets.'),
         DashboardSection('completion', 'Completion', tuple(completion),
                          'Percentages cover only the explicitly mapped item ownership records.'),
         DashboardSection('internal', 'Internal records', tuple(internal),
                          'Five additional serialized records remain read only and are excluded from officer totals.')),
        'Opened save values only. XP, compatibility and promotions have no inferred progress targets.')

"""Native PC DW4 Hyper layout, independently implemented from facts.

Reference: talkative-platano/dw4hyper-save-editor, commit
3638c8dc23d2607b862a1105bfc9806e69d9e871 (README.md). No third-party code or
save is included. A publicly shared native PC save qualifies identity and
integrity; edited game loading remains untested. The format
is unencrypted, with a byte-sum checksum, and is distinct from PS2 DW4 XL.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.save_safety import safe_path


GAME_ID = 'dw4hyper'
SAVE_SIZE = 0x10FC0
CHECKSUM_OFFSET = 0x10FA8
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xB8, 24, 42
WEAPON_EXP_BASE = 0x798
ITEM_BASE = 0x7F6
TEAM_BASE, TEAM_STRIDE = 0x508, 96
CUSTOM_BASE, CUSTOM_STRIDE = 0x688, 0x40

OFFICER_NAMES = (
    'Zhao Yun', 'Guan Yu', 'Zhang Fei', 'Xiahou Dun', 'Dian Wei',
    'Xu Zhu', 'Zhou Yu', 'Lu Xun', 'Taishi Ci', 'Diao Chan',
    'Zhuge Liang', 'Cao Cao', 'Lu Bu', 'Sun Shang Xiang', 'Liu Bei',
    'Sun Jian', 'Sun Quan', 'Dong Zhuo', 'Yuan Shao', 'Ma Chao',
    'Huang Zhong', 'Xiahou Yuan', 'Zhang Liao', 'Sima Yi', 'Lu Meng',
    'Gan Ning', 'Jiang Wei', 'Zhang Jiao', 'Xu Huang', 'Zhang He',
    'Zhen Ji', 'Huang Gai', 'Sun Ce', 'Wei Yan', 'Pang Tong',
    'Meng Huo', 'Zhu Rong', 'Da Qiao', 'Xiao Qiao', 'Cao Ren',
    'Zhou Tai', 'Yue Ying',
)
ITEM_NAMES = (
    'Peacock Urn', 'Dragon Amulet', 'Tiger Amulet', 'Tortoise Amulet',
    'Speed Scroll', 'Wing Boots', "Huang's Bow", 'Nanman Armor',
    'Horned Helm', 'Cavalry Armor', 'Seven Star Sash', 'Elixir',
    'Herbal Remedy', 'Fire Orb', 'Lightning Orb', 'Vorpal Orb',
    'Ice Orb', 'Blast Orb', 'Poison Orb', 'Red Hare Harness',
    'Hex Mark Harness', 'Storm Harness', 'Shadow Harness', 'Elephant Harness',
    'Art of War', 'Survival Guide', 'Bodyguard Manual', 'Way of Musou',
    'Power Scroll', 'Wind Scroll', 'Fire Arrows', 'Charge Bracer',
)


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str = 'Options'
    slot: int = 0
    minimum: int = 0
    storage: str = 'unsigned'
    maxable: bool = True
    kind: str = 'int'
    mirrors: tuple = ()

    def value(self, payload):
        value = int.from_bytes(payload[self.offset:self.offset + self.size], 'little')
        if self.storage == 'item-level':
            return 0 if value == 0xFF else value + 1
        return value

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from '
                            f'{self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        stored = (0xFF if value == 0 else value - 1) if self.storage == 'item-level' else value
        return stored.to_bytes(self.size, 'little')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True


_fields = [Field('difficulty', 'Difficulty (0 Easy / 1 Normal / 2 Hard)',
                 0x9A, 1, 2, maxable=False)]
for _index, _name in enumerate(OFFICER_NAMES):
    for _key, _label, _relative, _size, _maximum in (
            ('unlocked', 'Playable (0 locked / 1 unlocked)', 0, 1, 1),
            ('life', 'Life', 1, 1, 255), ('musou', 'Musou', 2, 1, 255),
            ('attack', 'Attack', 3, 1, 255), ('defense', 'Defense', 4, 1, 255),
            ('experience', 'Character EXP', 16, 2, 65535)):
        _fields.append(Field(f'officer_{_index}_{_key}', f'{_name}: {_label}',
                             OFFICER_BASE + OFFICER_STRIDE * _index + _relative,
                             _size, _maximum, 'Officers', _index + 1,
                             maxable=_key == 'unlocked'))
    _fields.append(Field(f'officer_{_index}_weapon_experience', f'{_name}: Weapon EXP',
                         WEAPON_EXP_BASE + 2 * _index, 2, 36001, 'Weapons', _index + 1))
    for _key, _label, _relative in (('harness', 'Harness', 8), ('orb', 'Orb', 9)):
        _fields.append(Field(f'officer_{_index}_{_key}', f'{_name}: {_label}',
                             OFFICER_BASE + OFFICER_STRIDE * _index + _relative,
                             1, 32, 'Equipment', _index + 1, maxable=False))
for _index, _name in enumerate(ITEM_NAMES):
    _maximum = 20 if _index < 13 else 4 if _index < 19 else 1
    _label = _name + (' ownership (0 locked / 1 owned)' if _index >= 19 else ' level (0 locked)')
    _fields.append(Field(f'item_{_index}', _label, ITEM_BASE + _index, 1,
                         _maximum, 'Items', storage='item-level'))
for _index in range(4):
    _fields.append(Field(f'team_{_index}_points', f'Bodyguard team {_index + 1}: Points',
                         TEAM_BASE + TEAM_STRIDE * _index + 94, 2, 65535,
                         'Bodyguards', _index + 1, maxable=False))

FORMAT = Format(
    GAME_ID, 'Dynasty Warriors 4 Hyper (PC)', SAVE_SIZE, tuple(_fields),
    'Open a separate native PC save.dat copy. '
    'Standard officers, character/weapon EXP, playable flags, items, bodyguard '
    'points, difficulty and existing custom-character stats and appearance. '
    'Item level 0 means locked; rare items use ownership 0/1. '
    'Owned harnesses/orbs can be equipped; occupied known-owned general slots allow replacement/unequip. Empty general slots, custom '
    'creation/model/moveset/gender, suspended battles and rankings remain read only.'
)
FIELD_MAP = MappingProxyType({field.id: field for field in FORMAT.fields})


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    seed: int = 0

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('This parser handles native PC DW4 Hyper only.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    layout = get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SAVE_SIZE:
        raise SaveError(f'DW4 Hyper PC requires exactly {SAVE_SIZE:,} bytes.')
    raw = bytes(raw)
    if raw[CHECKSUM_OFFSET + 4:] != bytes(20):
        raise SaveError('DW4 Hyper PC trailer does not match the required format.')
    payload = raw[:CHECKSUM_OFFSET]
    if int.from_bytes(raw[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4], 'little') != sum(payload):
        raise SaveError('DW4 Hyper PC byte-sum checksum failed.')
    if payload[0x9A] not in (0, 1, 2):
        raise SaveError('DW4 Hyper PC difficulty must be between 0 and 2.')
    for index in range(OFFICER_COUNT):
        if payload[OFFICER_BASE + OFFICER_STRIDE * index + 5] != index:
            raise SaveError('DW4 Hyper PC officer identities do not match this save layout.')
    return Document(layout, Path(source), raw, payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native PC .dat save copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.seed) is not int):
        raise SaveError('A frozen registered DW4 Hyper document is required.')
    original = decode(document.raw, GAME_ID, document.source)
    if original.payload != document.payload or document.seed != 0:
        raise SaveError('The opened DW4 Hyper snapshot was changed outside the edit workflow.')


def field_map(document):
    validate_document(document)
    return MappingProxyType({field.id: field for field in _fields_for_payload(document.payload)})


def fields_for(document):
    validate_document(document)
    return _fields_for_payload(document.payload)


def _qualified_custom(payload, slot):
    """Require an existing identified appearance; never create a record."""
    appearance = CUSTOM_BASE + CUSTOM_STRIDE * slot
    record = payload[appearance:appearance + CUSTOM_STRIDE]
    return (record[0] == 1 and record[0x18] == 0x60 + slot
            and record[0x1B] == record[0x1C] and record[0x1B] in (0x2A, 0x2B))


def _qualified_custom_pair(payload, slot):
    """Do not reconcile an appearance template with different grown roster data."""
    appearance = CUSTOM_BASE + CUSTOM_STRIDE * slot
    roster = OFFICER_BASE + OFFICER_STRIDE * (OFFICER_COUNT + slot)
    record = payload[appearance:appearance + CUSTOM_STRIDE]
    return (_qualified_custom(payload, slot)
            and record[:24] == payload[roster:roster + 24]
            and record[5] == record[0x2D] and record[5] in (0x2A, 0x2B, 0x2C, 0x2E)
            and record[3:5] == record[0x20:0x22])


@lru_cache(maxsize=4)
def _fields_for_payload(payload):
    fields = list(FORMAT.fields)
    for officer in range(OFFICER_COUNT):
        base = OFFICER_BASE + officer * OFFICER_STRIDE
        for slot in range(2, 8):
            identity = payload[base + 8 + slot]
            if identity in _general_items() and payload[ITEM_BASE + identity] != 255:
                fields.append(Field(f'officer_{officer}_general_item_{slot}',
                                    f'{OFFICER_NAMES[officer]}: Existing general slot {slot - 1}',
                                    base + 8 + slot, 1, 32, 'General equipment',
                                    officer + 1, maxable=False))
    for slot in range(4):
        if not _qualified_custom(payload, slot):
            continue
        appearance = CUSTOM_BASE + CUSTOM_STRIDE * slot
        roster = OFFICER_BASE + OFFICER_STRIDE * (OFFICER_COUNT + slot)
        for key, label, relative, size, ceiling in (
                ('life', 'Life', 1, 1, 255), ('musou', 'Musou', 2, 1, 255),
                ('attack', 'Attack', 3, 1, 255), ('defense', 'Defense', 4, 1, 255),
                ('experience', 'Character EXP', 16, 2, 65535)):
            if not _qualified_custom_pair(payload, slot):
                continue
            mirrors = (roster + relative,)
            if key in ('attack', 'defense'):
                mirrors += (appearance + (0x20 if key == 'attack' else 0x21),)
            fields.append(Field(f'custom_{slot}_{key}', f'Custom slot {slot + 1}: {label}',
                                appearance + relative, size, ceiling, 'Custom characters',
                                slot + 1, maxable=False, mirrors=mirrors))
        for key, label, relative, ceiling in (
                ('color', 'Color (0 Blue / 1 Red / 2 Green / 3 Purple / 4 White / 5 Yellow)', 0x1D, 5),
                ('head', 'Head', 0x30, 2), ('chest', 'Chest', 0x31, 2),
                ('arms', 'Arms and legs', 0x32, 2), ('hip', 'Hip', 0x33, 2)):
            # Unusual cosmetics are inspected without interpreting unknown enums.
            if payload[appearance + relative] <= ceiling:
                fields.append(Field(f'custom_{slot}_{key}', f'Custom slot {slot + 1}: {label}',
                                    appearance + relative, 1, ceiling, 'Custom characters',
                                    slot + 1, maxable=False))
    return tuple(fields)


def _general_items():
    return (*range(13), *range(24, 32))


def record_label(slot, group='Officers'):
    """Published names for UI labels, without guessing custom or scenario IDs."""
    if group in ('Officers', 'Weapons') and type(slot) is int and 1 <= slot <= OFFICER_COUNT:
        return OFFICER_NAMES[slot - 1]
    if group in ('Equipment', 'General equipment') and type(slot) is int and 1 <= slot <= OFFICER_COUNT:
        return OFFICER_NAMES[slot - 1]
    if group == 'Bodyguards' and type(slot) is int and 1 <= slot <= 4:
        return f'Bodyguard team {slot}'
    if group == 'Custom characters' and type(slot) is int and 1 <= slot <= 4:
        return f'Custom slot {slot}'
    return group if not slot else f'{group} record {slot}'


def changed_payload(document, changes):
    mapped = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapped:
            raise SaveError('The requested field is not mapped for this native PC save.')
        field = mapped[key]
        encoded = field.encoded(value)
        for offset in (field.offset, *field.mirrors):
            result[offset:offset + field.size] = encoded
    for key, value in changes.items():
        field = mapped[key]
        if field.group == 'General equipment' and value != field.value(document.payload):
            if value != 32 and (value not in _general_items() or document.payload[ITEM_BASE + value] == 255
                               or result[ITEM_BASE + value] == 255):
                raise SaveError('Replace with an originally owned general item, or choose Empty.')
            officer = field.slot - 1
            base = OFFICER_BASE + officer * OFFICER_STRIDE
            if result[WEAPON_EXP_BASE + officer * 2:WEAPON_EXP_BASE + officer * 2 + 2] != document.payload[WEAPON_EXP_BASE + officer * 2:WEAPON_EXP_BASE + officer * 2 + 2]:
                raise SaveError('Preserve weapon EXP while replacing an existing general equipment slot.')
            equipped = [item for item in result[base + 10:base + 16] if item != 32]
            if len(equipped) != len(set(equipped)):
                raise SaveError('An officer cannot equip the same general item in multiple slots.')
        if key.endswith(('_harness', '_orb')) and value != 32:
            allowed = range(19, 24) if key.endswith('_harness') else range(13, 19)
            if value not in allowed or result[ITEM_BASE + value] == 0xFF:
                raise SaveError('Equip an owned item of the correct category, or choose 32 for Empty.')
        if key.startswith('item_') and value == 0 and mapped[key].value(document.payload) > 0:
            identity = int(key.split('_')[1])
            for index in range(OFFICER_COUNT + 4):
                base = OFFICER_BASE + OFFICER_STRIDE * index
                if index >= OFFICER_COUNT and not result[base]:
                    continue
                if identity in result[base + 8:base + 16]:
                    raise SaveError('Unequip this item from every officer before locking it.')
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = payload + sum(payload).to_bytes(4, 'little') + document.raw[CHECKSUM_OFFSET + 4:]
    if decode(raw, GAME_ID, document.source).payload != payload:
        raise SaveError('DW4 Hyper edited copy verification failed.')
    return raw


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    changed_payload(document, changes)
    mapped = field_map(document)
    if key not in mapped:
        raise SaveError('The requested field is not mapped for this native PC save.')
    field = mapped[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    changed_payload(document, result)
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    changed_payload(document, changes)
    mapped = field_map(document)
    result = {}
    for key in keys:
        if key not in mapped:
            raise SaveError('The requested field is not mapped for this native PC save.')
        field = mapped[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and type(current) is int and field.minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changes = normalize_pending_values(document, changes, field_map(document))
    result = dict(changes)
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    with safe_path(document.source).open('rb') as stream:
        current = stream.read(SAVE_SIZE + 1)
    if current != document.raw:
        raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def _name(payload, offset):
    # Read-only decoding never changes undecodable or noncanonical name bytes.
    return payload[offset:offset + 9].split(b'\0', 1)[0].decode('ascii', errors='replace')


def progression(document, slot):
    validate_document(document)
    if type(slot) is not int or not 1 <= slot <= OFFICER_COUNT:
        raise SaveError('Choose one of the 42 standard PC DW4 Hyper officers.')
    index = slot - 1
    return {'level': None, 'observed_health': None, 'name': OFFICER_NAMES[index],
            'experience': FIELD_MAP[f'officer_{index}_experience'].value(document.payload),
            'weapon_experience': FIELD_MAP[f'officer_{index}_weapon_experience'].value(document.payload)}


def progressions(document):
    return tuple(progression(document, slot) for slot in range(1, OFFICER_COUNT + 1))


def inspection_rows(document):
    """Read-only named equipment, bodyguard names and custom character presence."""
    validate_document(document)
    rows = [{'group': 'Options', 'label': 'Difficulty',
             'value': ('Easy', 'Normal', 'Hard')[document.payload[0x9A]]}]
    for index, name in enumerate(OFFICER_NAMES):
        offset = OFFICER_BASE + OFFICER_STRIDE * index
        equipment = []
        for identity in document.payload[offset + 8:offset + 16]:
            equipment.append('Empty' if identity == 32 else ITEM_NAMES[identity]
                             if identity < 32 else f'Unknown item ID {identity}')
        character_exp = int.from_bytes(document.payload[offset + 16:offset + 18], 'little')
        weapon_exp = int.from_bytes(document.payload[WEAPON_EXP_BASE + 2 * index:
                                                    WEAPON_EXP_BASE + 2 * index + 2], 'little')
        rows.append({'group': 'Officers', 'label': name,
                     'value': f'Character EXP {character_exp:,}; weapon EXP {weapon_exp:,}; '
                              'equipped item IDs: ' + ', '.join(equipment)})
    for team in range(4):
        offset = TEAM_BASE + TEAM_STRIDE * team
        rows.append({'group': 'Bodyguard names', 'label': f'Team {team + 1}',
                     'value': _name(document.payload, offset)})
        rows.extend({'group': 'Bodyguard names', 'label': f'Team {team + 1}, guard {guard + 1}',
                     'value': _name(document.payload, offset + 9 + 9 * guard)}
                    for guard in range(8))
    for slot in range(4):
        offset = CUSTOM_BASE + CUSTOM_STRIDE * slot
        record = document.payload[offset:offset + CUSTOM_STRIDE]
        qualified = _qualified_custom_pair(document.payload, slot)
        rows.append({'group': 'Custom characters', 'label': f'Custom slot {slot + 1}',
                     'value': f'Created byte {record[0]}; '
                              f'name {_name(document.payload, offset + 0x34)}; '
                              + ('paired stats qualified' if qualified else 'differing stats templates preserved')})
        if record[0] == 1:
            gender = {0x2A: 'Male', 0x2B: 'Female'}.get(record[0x1B], f'Unknown {record[0x1B]}')
            motion = record[0x1E]
            moveset = (OFFICER_NAMES[motion] if motion < OFFICER_COUNT else
                       {42: 'Great Sword', 43: 'Rapier'}.get(motion, f'Unknown {motion}'))
            rows.append({'group': 'Custom characters', 'label': f'Custom slot {slot + 1}: Appearance',
                         'value': f'{gender}; moveset {moveset}; color ID {record[0x1D]}; '
                                  f'head/chest/arms/hip IDs {tuple(record[0x30:0x34])}. '
                                  'Gender, moveset and model are read only.'})
    for challenge, label in enumerate(('Endurance', 'Time Attack', 'Bridge Melee', 'Demolition')):
        for rank in range(10):
            index = challenge * 10 + rank
            identity = document.payload[0xBA0 + index]
            name = (OFFICER_NAMES[identity] if identity < OFFICER_COUNT else
                    f'Custom slot {identity - 41}' if identity < 46 else f'Unknown roster ID {identity}')
            score = int.from_bytes(document.payload[0xBC8 + 4 * index:0xBCC + 4 * index], 'little')
            value = f'{name}; {score:,} ' + ('frames at 60 fps' if challenge == 1 else 'points')
            rows.append({'group': 'Challenge rankings', 'label': f'{label}, rank {rank + 1}', 'value': value})
    total = int.from_bytes(document.payload[0xB170:0xB174], 'little')
    if total:
        elapsed = int.from_bytes(document.payload[0xB16C:0xB170], 'little')
        mirror = int.from_bytes(document.payload[0xD888:0xD88C], 'little')
        rows.append({'group': 'Suspended battle', 'label': 'Timer snapshot (read only)',
                     'value': f'Elapsed {elapsed:,}; total {total:,} frames at 60 fps; '
                              f'elapsed mirror {mirror:,}. Phase byte {document.payload[0xB17C]} '
                              'can change within a battle; it is not a story-clear flag.'})
    return tuple(rows)


def field_hint(document, field):
    fields = field_map(document)
    key = field.id if isinstance(field, Field) else field
    if key not in fields:
        raise SaveError('The requested field is not mapped for this native PC save.')
    mapped = fields[key]
    if mapped.group == 'General equipment':
        return ('Replace or unequip an originally occupied known-owned general slot. Empty '
                'slots cannot be filled; weapon EXP must remain unchanged in this batch. '
                'Targets must already be owned and cannot duplicate another general slot. Max excludes choices.')
    if mapped.group == 'Equipment':
        return ('Equip owned items only: harness IDs 19 Red Hare, 20 Hex Mark, 21 Storm, '
                '22 Shadow, 23 Elephant; orb IDs 13 Fire, 14 Lightning, 15 Vorpal, '
                '16 Ice, 17 Blast, 18 Poison. 32 means Empty. Grant ownership in Items '
                'before equipping. General slot availability remains unchanged. Bulk Max is disabled.')
    if mapped.group == 'Custom characters':
        if key.endswith(('_life', '_musou', '_attack', '_defense', '_experience')):
            return ('Only an existing consistent custom record is editable. Stats/EXP keep '
                    'the roster and appearance copies synchronized, including duplicate Attack/Defense. '
                    '255 and 65535 are manual storage bounds; bulk Max is disabled. '
                    'Gender, moveset, model, names and creation metadata are preserved.')
        if key.endswith('_color'):
            return 'Color: 0 Blue, 1 Red, 2 Green, 3 Purple, 4 White, 5 Yellow. Bulk Max is disabled.'
        slot = mapped.slot - 1
        female = document.payload[CUSTOM_BASE + CUSTOM_STRIDE * slot + 0x1B] == 0x2B
        middle = {'head': ('Turban', 'Ponytail'), 'chest': ('Chest Plate', 'Dancer Garb'),
                  'arms': ('Leather Guards', 'Dancer Garb'), 'hip': ('Sash', 'Dancer Garb')}
        part = key.rsplit('_', 1)[1]
        first = {'head': 'Short Hair', 'chest': 'Battle Garb',
                 'arms': 'Cloth Guards', 'hip': 'Battle Garb'}[part]
        return f'0 {first}, 1 {middle[part][female]}, 2 ' + ('Helmet' if part == 'head' else 'Armor') + '. Bulk Max is disabled.'
    if key == 'difficulty':
        return 'Easy=0, Normal=1, Hard=2. Difficulty is excluded from bulk Max.'
    if mapped.group == 'Weapons':
        return ('Weapon level is EXP-derived: normal play 0..36000; 36001 is the special '
                'Lv.10 weapon. Hyper has no Lv.11 weapon. Higher existing EXP is preserved by Max.')
    if mapped.group == 'Items':
        return ('0 means locked. Leveled items use 1..20, orbs 1..4, ownership items 1 means owned. '
                'Equipped item references are inspected separately and remain unchanged.')
    if mapped.group == 'Bodyguards':
        return ('Bodyguard team stats and unlocked guard count derive from points. '
                '65535 is the storage bound. '
                'Points are excluded from bulk Max. Names and other team bytes remain unchanged.')
    return ('Standard officer stats, EXP and playable flags. Stat 255 and character EXP '
            '65535 are storage bounds; those fields are excluded from bulk Max. '
            'Equipped items, identity and unknown bytes are preserved.')


def field_options(document, key):
    """Named categorical choices; numeric validation still belongs to the writer."""
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('Choose a qualified field for this save copy.')
    if key == 'difficulty':
        return tuple(enumerate(('Easy', 'Normal', 'Hard')))
    if field.group == 'Equipment':
        identities = range(19, 24) if key.endswith('_harness') else range(13, 19)
        return ((32, 'Empty'),) + tuple((index, ITEM_NAMES[index]) for index in identities)
    if field.group == 'General equipment':
        base = OFFICER_BASE + (field.slot - 1) * OFFICER_STRIDE
        other = {document.payload[base + relative] for relative in range(10, 16)
                 if base + relative != field.offset}
        return ((32, 'Empty'),) + tuple((index, ITEM_NAMES[index]) for index in _general_items()
                                       if document.payload[ITEM_BASE + index] != 255 and index not in other)
    if field.group == 'Custom characters' and key.endswith('_color'):
        return tuple(enumerate(('Blue', 'Red', 'Green', 'Purple', 'White', 'Yellow')))
    if field.group == 'Custom characters' and key.rsplit('_', 1)[-1] in ('head', 'chest', 'arms', 'hip'):
        female = document.payload[CUSTOM_BASE + CUSTOM_STRIDE * (field.slot - 1) + 0x1B] == 0x2B
        names = {'head': ('Short Hair', 'Ponytail' if female else 'Turban', 'Helmet'),
                 'chest': ('Battle Garb', 'Dancer Garb' if female else 'Chest Plate', 'Armor'),
                 'arms': ('Cloth Guards', 'Dancer Garb' if female else 'Leather Guards', 'Armor'),
                 'hip': ('Battle Garb', 'Dancer Garb' if female else 'Sash', 'Armor')}
        return tuple(enumerate(names[key.rsplit('_', 1)[-1]]))
    return ()

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'

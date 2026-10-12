"""Independent USA PS2 DW4 XL PSU editor based on published format facts.

Reference: talkative-platano/dw4xl-save-editor, commit
b3ea895c6e854accd6860fd51ce69aeb024f53e9 (README.md). No third-party code or
sample saves are included. Two independent publicly shared USA game saves were
privately archive-converted and qualified; console loading remains untested.
Only the USA BASLUS-20812 inner file in a PSU export is accepted. Metadata,
icons, directory records, file padding and unknown inner bytes are preserved.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.save_safety import safe_path


GAME_ID = 'dw4xl_ps2'
PRODUCT_NAME = 'BASLUS-20812'
INNER_SIZE = 34064
# A resource bound for variable-size exports, not a fixed native save size.
MAX_CONTAINER_SIZE = 8 * 1024 * 1024
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xB8, 24, 42
WEAPON_EXP_BASE, ITEM_BASE = 0x798, 0x7F6
TEAM_BASE, TEAM_STRIDE = 0x508, 96

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
    'Power Rune', 'Code of Chivalry', 'Meat Bun Sack', 'Musou Armor',
    'Master of Musou', 'War Drum', 'Secret of Orbs', 'Helm of Might', 'Horseshoes',
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

    def value(self, payload):
        stored = int.from_bytes(payload[self.offset:self.offset + self.size], 'little')
        return (0 if stored == 255 else stored + 1) if self.storage == 'item-level' else stored

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from '
                            f'{self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        stored = (255 if value == 0 else value - 1) if self.storage == 'item-level' else value
        return stored.to_bytes(self.size, 'little')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    inner_size: int = INNER_SIZE


_fields = [Field('difficulty', 'Difficulty (0 Novice / 1 Easy / 2 Normal / 3 Hard / 4 Expert)',
                 0x9A, 1, 4, maxable=False)]
for _index, _name in enumerate(OFFICER_NAMES):
    for _key, _label, _relative, _size, _maximum in (
            ('life', 'Life', 1, 1, 255), ('musou', 'Musou', 2, 1, 255),
            ('attack', 'Attack', 3, 1, 255), ('defense', 'Defense', 4, 1, 255),
            ('points', 'Character points', 16, 2, 65535)):
        _fields.append(Field(f'officer_{_index}_{_key}', f'{_name}: {_label}',
                             OFFICER_BASE + OFFICER_STRIDE * _index + _relative,
                             _size, _maximum, 'Officers', _index + 1, maxable=False))
    _fields.append(Field(f'officer_{_index}_weapon_experience', f'{_name}: Weapon EXP',
                         WEAPON_EXP_BASE + 2 * _index, 2, 36002, 'Weapons', _index + 1))
    for _key, _label, _relative in (('harness', 'Harness', 8), ('orb', 'Orb', 9)):
        _fields.append(Field(f'officer_{_index}_{_key}', f'{_name}: {_label}',
                             OFFICER_BASE + OFFICER_STRIDE * _index + _relative,
                             1, 41, 'Equipment', _index + 1, maxable=False))
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
    GAME_ID, 'Dynasty Warriors 4: Xtreme Legends (PS2, USA)', MAX_CONTAINER_SIZE, tuple(_fields),
    'Published PS2 USA SLUS-20812 format, opened only through a .psu export. '
    'The gameplay file is BASLUS-20812, exactly 34,064 bytes; its offset depends on '
    'the export contents. Export and import through a suitable PS2 memory-card tool. '
    'Standard officer stats/points, weapon EXP, items, bodyguard '
    'points, difficulty, owned harness/orb assignments and occupied known-owned general-slot replacements are editable; empty general '
    'equipment slots and names are inspected without changing them. PSU metadata/icons/padding and unrelated gameplay bytes are '
    'preserved. The 8 MiB container limit is an input read cap, not the save size.'
)
FIELD_MAP = MappingProxyType({field.id: field for field in FORMAT.fields})


@dataclass(frozen=True)
class Entry:
    name: str
    header_offset: int
    data_offset: int
    size: int
    is_directory: bool


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    payload_offset: int
    entries: tuple
    seed: int = 0

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('This parser handles PS2 USA DW4 Xtreme Legends PSU exports only.')
    return FORMAT


def _entry_name(raw, offset):
    stored = raw[offset + 64:offset + 96].split(b'\0', 1)[0]
    try:
        name = stored.decode('ascii')
    except UnicodeDecodeError as error:
        raise SaveError('PSU directory names do not match the supported ASCII export format.') from error
    if not name or any(character in name for character in '/\\:') or any(ord(c) < 32 for c in name):
        raise SaveError('PSU contains an invalid directory entry name.')
    return name


def _container(raw):
    if len(raw) < 512:
        raise SaveError('PSU export is missing its directory header.')
    root_mode = int.from_bytes(raw[:2], 'little')
    root_name = _entry_name(raw, 0)
    if not root_mode & 0x20 or root_mode & 0x10 or not root_name.startswith(PRODUCT_NAME):
        raise SaveError('PSU root does not identify the USA BASLUS-20812 game directory.')
    count = int.from_bytes(raw[4:8], 'little')
    # Every entry needs its own 512-byte header. The two special directory
    # entries and at least one gameplay file must be represented.
    if not 3 <= count <= (len(raw) - 512) // 512:
        raise SaveError('PSU directory entry count is invalid.')
    position, entries, names, payload_offset = 512, [], set(), None
    for index in range(count):
        if position + 512 > len(raw):
            raise SaveError('PSU export has a truncated directory entry.')
        header = position
        mode = int.from_bytes(raw[header:header + 2], 'little')
        size = int.from_bytes(raw[header + 4:header + 8], 'little')
        name = _entry_name(raw, header)
        directory, regular = bool(mode & 0x20), bool(mode & 0x10)
        if directory == regular or name in names:
            raise SaveError('PSU has an invalid mode or ambiguous duplicate entry.')
        names.add(name)
        position += 512
        if directory:
            if index > 1 or name != ('.' if index == 0 else '..'):
                raise SaveError('PSU nested directories are outside the supported export format.')
        else:
            if index < 2 or name in ('.', '..'):
                raise SaveError('PSU is missing its special directory entries.')
            padded_size = ((size + 1023) // 1024) * 1024
            if size > MAX_CONTAINER_SIZE or position + padded_size > len(raw):
                raise SaveError('PSU file size or 1024-byte file padding is truncated.')
            if name == PRODUCT_NAME:
                if size != INNER_SIZE:
                    raise SaveError('BASLUS-20812 must contain exactly 34,064 gameplay bytes.')
                payload_offset = position
        entries.append(Entry(name, header, position, size, directory))
        if regular:
            position += padded_size
    if position != len(raw):
        raise SaveError('PSU contains trailing data outside the declared export entries.')
    if payload_offset is None:
        raise SaveError('The exact BASLUS-20812 gameplay file is missing; .sys and .ico are metadata.')
    return payload_offset, tuple(entries)


def decode(raw, game_id=GAME_ID, source=Path('copy.psu')):
    layout = get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or not 0 < len(raw) <= MAX_CONTAINER_SIZE:
        raise SaveError('Choose a nonempty PSU export no larger than the 8 MiB input read cap.')
    raw = bytes(raw)
    offset, entries = _container(raw)
    payload = raw[offset:offset + INNER_SIZE]
    if int.from_bytes(payload[2:4], 'little') != 3:
        raise SaveError('DW4 XL USA inner save version must be 0x0003.')
    if int.from_bytes(payload[:2], 'little') != sum(payload[4:]) & 0xFFFF:
        raise SaveError('DW4 XL PS2 inner byte-sum checksum failed.')
    if payload[0x9A] not in range(5):
        raise SaveError('DW4 XL difficulty must be between 0 and 4.')
    for index in range(OFFICER_COUNT):
        base = OFFICER_BASE + OFFICER_STRIDE * index
        if payload[base] != 1 or payload[base + 5] != index:
            raise SaveError('DW4 XL officer record markers do not match the USA save layout.')
    return Document(layout, Path(source), raw, payload, offset, entries)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.psu':
        raise SaveError('Open a separate USA PS2 .psu export copy; .sys files are metadata.')
    with path.open('rb') as stream:
        raw = stream.read(MAX_CONTAINER_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.seed) is not int or type(document.payload_offset) is not int
            or type(document.entries) is not tuple):
        raise SaveError('Unregistered DW4 XL PS2 document.')
    original = decode(document.raw, GAME_ID, document.source)
    if (original.payload != document.payload or original.payload_offset != document.payload_offset
            or original.entries != document.entries or document.seed != 0):
        raise SaveError('The opened DW4 XL export snapshot was changed outside the edit workflow.')


def field_map(document):
    validate_document(document)
    return MappingProxyType({field.id: field for field in fields_for(document)})


def fields_for(document):
    validate_document(document)
    fields = list(FORMAT.fields)
    for officer in range(OFFICER_COUNT):
        base = OFFICER_BASE + officer * OFFICER_STRIDE
        for slot in range(2, 8):
            identity = document.payload[base + 8 + slot]
            if identity in _general_items() and document.payload[ITEM_BASE + identity] != 255:
                fields.append(Field(f'officer_{officer}_general_item_{slot}',
                                    f'{OFFICER_NAMES[officer]}: Existing general slot {slot - 1}',
                                    base + 8 + slot, 1, 41, 'General equipment',
                                    officer + 1, maxable=False))
    return tuple(fields)


def _general_items():
    return (*range(13), *range(24, 41))


def record_label(slot, group='Officers'):
    if group in ('Officers', 'Weapons', 'Equipment', 'General equipment') and type(slot) is int and 1 <= slot <= OFFICER_COUNT:
        return OFFICER_NAMES[slot - 1]
    if group == 'Bodyguards' and type(slot) is int and 1 <= slot <= 4:
        return f'Bodyguard team {slot}'
    return group if not slot else f'{group} record {slot}'


def changed_payload(document, changes):
    validate_document(document)
    mapped = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapped:
            raise SaveError('The requested field is not mapped for PS2 USA DW4 XL.')
        field = mapped[key]
        result[field.offset:field.offset + field.size] = field.encoded(value)
    for key, value in changes.items():
        field = mapped[key]
        if field.group == 'General equipment' and value != field.value(document.payload):
            if value != 41 and (value not in _general_items() or document.payload[ITEM_BASE + value] == 255
                               or result[ITEM_BASE + value] == 255):
                raise SaveError('Replace with an originally owned general item, or choose Empty.')
            officer = field.slot - 1
            base = OFFICER_BASE + officer * OFFICER_STRIDE
            if result[WEAPON_EXP_BASE + officer * 2:WEAPON_EXP_BASE + officer * 2 + 2] != document.payload[WEAPON_EXP_BASE + officer * 2:WEAPON_EXP_BASE + officer * 2 + 2]:
                raise SaveError('Preserve weapon EXP while replacing an existing general equipment slot.')
            equipped = [item for item in result[base + 10:base + 16] if item != 41]
            if len(equipped) != len(set(equipped)):
                raise SaveError('An officer cannot equip the same general item in multiple slots.')
        if key.endswith(('_harness', '_orb')) and value != 41:
            allowed = range(19, 24) if key.endswith('_harness') else range(13, 19)
            if value not in allowed or result[ITEM_BASE + value] == 0xFF:
                raise SaveError('Equip an owned item of the correct category, or choose 41 for Empty.')
        if key.startswith('item_') and value == 0 and mapped[key].value(document.payload) > 0:
            identity = int(key.split('_')[1])
            for index in range(OFFICER_COUNT):
                base = OFFICER_BASE + OFFICER_STRIDE * index
                if identity in result[base + 8:base + 16]:
                    raise SaveError('Unequip this item from every officer before locking it.')
    result[:2] = (sum(result[4:]) & 0xFFFF).to_bytes(2, 'little')
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    offset = document.payload_offset
    raw = document.raw[:offset] + payload + document.raw[offset + INNER_SIZE:]
    verified = decode(raw, GAME_ID, document.source)
    if verified.payload != payload or verified.entries != document.entries:
        raise SaveError('Edited DW4 XL PSU export verification failed.')
    return raw


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    changed_payload(document, changes)
    mapped = field_map(document)
    if key not in mapped:
        raise SaveError('The requested field is not mapped for PS2 USA DW4 XL.')
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
            raise SaveError('The requested field is not mapped for PS2 USA DW4 XL.')
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
    if destination.suffix.lower() != '.psu':
        raise SaveError('Choose a new .psu export destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    with safe_path(document.source).open('rb') as stream:
        current = stream.read(MAX_CONTAINER_SIZE + 1)
    if current != document.raw:
        raise SaveError('The opened export changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.psu', MAX_CONTAINER_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def _name(payload, offset):
    return payload[offset:offset + 9].split(b'\0', 1)[0].decode('ascii', errors='replace')


def inspection_rows(document):
    validate_document(document)
    rows = [{'group': 'Container', 'label': 'Platform / region', 'value': 'PS2 / USA SLUS-20812'},
            {'group': 'Container', 'label': 'Gameplay file',
             'value': f'{PRODUCT_NAME}, {INNER_SIZE:,} bytes at offset 0x{document.payload_offset:X}'}]
    rows.extend({'group': 'Container files', 'label': entry.name,
                 'value': 'Directory record (unchanged)' if entry.is_directory
                 else f'{entry.size:,} bytes' + (' (gameplay)' if entry.name == PRODUCT_NAME else ' (unchanged)')}
                for entry in document.entries)
    for index, name in enumerate(OFFICER_NAMES):
        offset = OFFICER_BASE + OFFICER_STRIDE * index
        equipment = []
        for identity in document.payload[offset + 8:offset + 16]:
            equipment.append('Empty' if identity == 41 else ITEM_NAMES[identity]
                             if identity < 41 else f'Unknown item ID {identity}')
        points = int.from_bytes(document.payload[offset + 16:offset + 18], 'little')
        weapon_exp = int.from_bytes(document.payload[WEAPON_EXP_BASE + 2 * index:
                                                    WEAPON_EXP_BASE + 2 * index + 2], 'little')
        rows.append({'group': 'Officers', 'label': name,
                     'value': f'Character points {points:,}; weapon EXP {weapon_exp:,}; '
                              'equipped items: ' + ', '.join(equipment)})
    for team in range(4):
        offset = TEAM_BASE + TEAM_STRIDE * team
        rows.append({'group': 'Bodyguard names', 'label': f'Team {team + 1}',
                     'value': _name(document.payload, offset)})
        rows.extend({'group': 'Bodyguard names', 'label': f'Team {team + 1}, guard {guard + 1}',
                     'value': _name(document.payload, offset + 9 + 9 * guard)}
                    for guard in range(8))
    return tuple(rows)


def field_hint(document, field):
    validate_document(document)
    key = field.id if isinstance(field, Field) else field
    fields = field_map(document)
    if key not in fields:
        raise SaveError('The requested field is not mapped for PS2 USA DW4 XL.')
    mapped = fields[key]
    if mapped.group == 'General equipment':
        return ('Replace or unequip an originally occupied known-owned general slot. Empty '
                'slots cannot be filled; weapon EXP must remain unchanged in this batch. '
                'Targets must already be owned and cannot duplicate another general slot. Max excludes choices.')
    if mapped.group == 'Equipment':
        return ('Equip owned items only: harness IDs 19 Red Hare, 20 Hex Mark, 21 Storm, '
                '22 Shadow, 23 Elephant; orb IDs 13 Fire, 14 Lightning, 15 Vorpal, '
                '16 Ice, 17 Blast, 18 Poison. 41 means Empty. Grant ownership in Items '
                'before equipping. General slot availability remains unchanged. Bulk Max is disabled.')
    if key == 'difficulty':
        return 'Novice=0, Easy=1, Normal=2, Hard=3, Expert=4. Difficulty is excluded from bulk Max.'
    if mapped.group == 'Weapons':
        return ('Weapon EXP: normal play 0..36000, special Lv.10=36001 and '
                'Lv.11=36002. Max uses Lv.11; higher existing values remain unchanged.')
    if mapped.group == 'Items':
        return ('0 means locked; normal leveled items use 1..20, orbs 1..4, ownership items '
                '1 means owned. Equipped references remain unchanged; empty equipment ID is 41.')
    if mapped.group == 'Bodyguards':
        return ('Team stats and unlocked guard count derive from points. '
                '65535 is the storage bound, and points are excluded from bulk Max. '
                'Names and other team bytes remain unchanged.')
    return ('Officer stats 255 and character points 65535 are storage bounds; '
            'these fields are excluded from bulk Max. Equipment, '
            'record identities and unknown bytes remain unchanged.')

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'


def field_options(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('Choose a qualified field for this export.')
    if key == 'difficulty':
        return tuple(enumerate(('Novice', 'Easy', 'Normal', 'Hard', 'Expert')))
    if field.group == 'Equipment':
        identities = range(19, 24) if key.endswith('_harness') else range(13, 19)
        return ((41, 'Empty'),) + tuple((index, ITEM_NAMES[index]) for index in identities)
    if field.group == 'General equipment':
        base = OFFICER_BASE + (field.slot - 1) * OFFICER_STRIDE
        other = {document.payload[base + relative] for relative in range(10, 16)
                 if base + relative != field.offset}
        return ((41, 'Empty'),) + tuple((index, ITEM_NAMES[index]) for index in _general_items()
                                       if document.payload[ITEM_BASE + index] != 255 and index not in other)
    return ()

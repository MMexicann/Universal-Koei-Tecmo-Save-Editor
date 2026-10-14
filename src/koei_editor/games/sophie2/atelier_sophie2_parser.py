"""Copy-only adapter for the published Atelier Sophie 2 Steam 1.08 layout.

Format facts: Tartarshia/Sophie2SaveEditor, commit
93d807072a852c73799394af4d32fb164841cd3e, sophie2_model.py and self_test.py.
The upstream MIT codec is credited separately. No genuine save is distributed;
independent genuine-file and in-game qualification remain pending.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

import koei_editor.games.sophie2.atelier_sophie2_codec as codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_enabled, within_numeric_limits
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.save_safety import safe_path


GAME_ID = 'atelier_sophie2'
MAX_FILE_SIZE = codec.MAX_FILE_SIZE
RECORD_SIZE = 0x2C
CHARACTER_NAMES = ('Sophie', 'Plachta', 'Ramizel', 'Alette', 'Olias', 'Diebold')
EQUIPMENT_SLOTS = ('Weapon', 'Armor', 'Accessory 1', 'Accessory 2',
                   'Battle item 1', 'Battle item 2', 'Battle item 3', 'Battle item 4')
INVENTORY_GROUPS = (
    ('materials', 'Material container', b'm_unitContainer\0', b'm_unitContainerImportant\0', 9999),
    ('important', 'Important items', b'm_unitContainerImportant\0', b'm_unitContainerExpendable\0', 150),
    ('expendable', 'Consumable container', b'm_unitContainerExpendable\0', b'limitSize\0', 50),
    ('exploration', 'Gathering tools', b'explore_equip_item\0', b'adventure_equip_item\0', 15),
    ('adventure', 'Adventure equipment', b'adventure_equip_item\0', b'bonus\0', 25),
)


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str
    slot: int = 0
    minimum: int = 0
    maxable: bool = True
    kind: str = 'int'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    @property
    def experimental_maximum(self):
        return 0x7FFFFFFF if self.group == 'Alchemy' else (1 << (8 * self.size)) - 1

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from '
                            f'{self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = False


FORMAT = Format(
    GAME_ID, 'Atelier Sophie 2: The Alchemist of the Mysterious Dream (Steam PC)',
    MAX_FILE_SIZE, (),
    'Published Steam PC 1.08 layout; independent genuine-file and in-game checks pending. '
    'Edit existing inventory/equipment quality (0–999), qualified battle-item uses, '
    'and Sophie/Plachta alchemy EXP. '
    'EXP uses the published storage bound and is excluded from Max. '
    'Item identities, traits/effects, raw levels, m_mixGem and story data remain unchanged.'
)


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    seed: int
    header: bytes
    trailer: bytes
    footer: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('This parser handles the published Atelier Sophie 2 Steam PC layout only.')
    return FORMAT


def _unique(payload, marker, start=0, end=None):
    end = len(payload) if end is None else end
    position = payload.find(marker, start, end)
    if position < 0 or payload.find(marker, position + len(marker), end) >= 0:
        raise SaveError(f'Missing or ambiguous Sophie 2 tag: {marker[:-1].decode(errors="replace")}.')
    return position


@lru_cache(maxsize=4)
def _structure(payload):
    """Qualify the complete published layout before exposing any writable field."""
    groups = []
    regions = []
    for key, label, marker, following, capacity in INVENTORY_GROUPS:
        position = _unique(payload, marker)
        start = position + len(marker) + 4
        end = _unique(payload, following) - 4
        if end <= start or end - start != capacity * RECORD_SIZE:
            raise SaveError(f'Sophie 2 {label} does not match the published 1.08 record layout.')
        groups.append((key, label, start, capacity))
        regions.append((start, end))

    party_start = _unique(payload, b'party\0')
    squad_start = _unique(payload, b'm_squad\0')
    if squad_start <= party_start:
        raise SaveError('Sophie 2 party block is misplaced.')
    positions = []
    position = party_start
    while True:
        position = payload.find(b'Party\0', position, squad_start)
        if position < 0:
            break
        positions.append(position)
        position += 6
    if len(positions) != 6 or any(b - a != 0x314 for a, b in zip(positions, positions[1:])):
        raise SaveError('Sophie 2 requires six published 0x314-byte Party records.')
    equipment = {}
    for position in positions:
        if position + 0x314 > squad_start:
            raise SaveError('Sophie 2 Party record is truncated.')
        identity = struct.unpack_from('<i', payload, position + 9)[0]
        if identity not in range(6) or identity in equipment:
            raise SaveError('Sophie 2 playable character identities are invalid or duplicated.')
        start = position + 0x176
        equipment[identity] = start
        regions.append((start, start + 8 * RECORD_SIZE))
    if set(equipment) != set(range(6)):
        raise SaveError('Sophie 2 playable character equipment is incomplete.')
    ordered = sorted(regions)
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        raise SaveError('Sophie 2 item record regions overlap.')

    alchemy_start = _unique(payload, b'mix_lv\0')
    alchemy_end = min(len(payload), alchemy_start + 0x180)
    alchemy = {}
    # These exact offsets follow the published named-value reader. Raw lv is
    # deliberately not writable: its relationship to EXP is not established.
    plachta_exp_position = _unique(payload, b'plachta_exp\0', alchemy_start, alchemy_end)
    for key, marker in (('sophie_exp', b'exp\0'), ('plachta_exp', b'plachta_exp\0')):
        # The shorter exp tag is also a suffix of plachta_exp. Its scope ends
        # before the latter tag, so suffixes cannot be mistaken for a second node.
        end = plachta_exp_position if key == 'sophie_exp' else alchemy_end
        position = _unique(payload, marker, alchemy_start, end)
        offset = position + len(marker) + 3
        if offset + 4 > alchemy_end or any(a < offset + 4 and offset < b for a, b in regions):
            raise SaveError('Sophie 2 alchemy field is truncated or overlaps an item record.')
        alchemy[key] = offset
    if alchemy['sophie_exp'] >= alchemy['plachta_exp']:
        raise SaveError('Sophie 2 alchemy fields are out of order.')
    # Plachta's distinctive tagged alchemy fields, five exact record pools and
    # six Party identities distinguish this published layout from other Gust saves.
    plachta_lv = _unique(payload, b'plachta_lv\0', alchemy_start, alchemy_end) + 14
    if plachta_lv + 4 > alchemy_end:
        raise SaveError('Sophie 2 Plachta raw level field is truncated.')
    gem = _unique(payload, b'm_mixGem\0')
    following = _unique(payload, b'm_mixMistList\0')
    if gem < 4 or following <= gem or struct.unpack_from('<I', payload, gem - 4)[0] != following - gem:
        raise SaveError('Sophie 2 m_mixGem tag distance does not match the published layout.')
    gem_offset = gem + 12
    if gem_offset + 4 > following - 4:
        raise SaveError('Sophie 2 m_mixGem field is truncated.')
    # Check whole scalar ranges, including values beginning immediately before
    # an item record. A tag match must never grant access to item identity bytes.
    scalar_regions = [(offset, offset + 4) for offset in alchemy.values()]
    scalar_regions.extend(((plachta_lv, plachta_lv + 4), (gem_offset, gem_offset + 4)))
    if any(a < end and start < b for start, end in scalar_regions for a, b in regions):
        raise SaveError('Sophie 2 scalar field overlaps an item record.')
    ordered_scalars = sorted(scalar_regions)
    if any(left[1] > right[0] for left, right in zip(ordered_scalars, ordered_scalars[1:])):
        raise SaveError('Sophie 2 scalar fields overlap each other.')
    return tuple(groups), tuple(sorted(equipment.items())), tuple(alchemy.items()), plachta_lv, gem_offset


@lru_cache(maxsize=4)
def _decode_snapshot(raw):
    try:
        header, payload, details = codec.decode_file(raw)
    except (codec.SaveFormatError, IndexError, struct.error) as error:
        raise SaveError(f'Sophie 2 save integrity/codec check failed: {error}.') from error
    _structure(payload)
    return header, payload, details, raw[codec.HEADER_SIZE + details.padded_size:]


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or not codec.HEADER_SIZE < len(raw) <= MAX_FILE_SIZE:
        raise SaveError('Sophie 2 save size is outside the processing bounds.')
    raw = bytes(raw)
    header, payload, details, trailer = _decode_snapshot(raw)
    return Document(FORMAT, Path(source), raw, payload, details.seed, header, trailer, details.footer)


def _copy_path(path):
    # The shared policy also protects Steam userdata and resolved symlinks.
    original = str(path).replace('\\', '/').casefold()
    resolved = safe_path(path)
    for text in (original, str(resolved).replace('\\', '/').casefold()):
        if '/koeitecmo/atelier sophie 2/' in text or text.endswith('/koeitecmo/atelier sophie 2'):
            raise SaveError('Use a separate copy outside the live Atelier Sophie 2 save folder.')
    return resolved


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    if path.suffix.casefold() != '.dat':
        raise SaveError('Open a separate Steam PC data.dat save copy.')
    with path.open('rb') as stream:
        raw = stream.read(MAX_FILE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if not isinstance(document, Document) or document.format != FORMAT:
        raise SaveError('Unregistered Atelier Sophie 2 document.')
    if (any(type(getattr(document, name)) is not bytes
            for name in ('raw', 'payload', 'header', 'trailer', 'footer'))
            or type(document.seed) is not int):
        raise SaveError('The opened Sophie 2 snapshot must contain immutable native bytes.')
    original = decode(document.raw, GAME_ID, document.source)
    if (document.payload, document.seed, document.header, document.trailer, document.footer) != (
            original.payload, original.seed, original.header, original.trailer, original.footer):
        raise SaveError('The opened Sophie 2 snapshot changed outside the edit workflow.')


@lru_cache(maxsize=4)
def _field_index(payload, experimental=False):
    groups, equipment, alchemy, _, _ = _structure(payload)
    fields = [Field(key, f'{"Sophie" if key == "sophie_exp" else "Plachta"}: Alchemy EXP',
                    offset, 4, 0x7FFFFFFF, 'Alchemy', maxable=False)
              for key, offset in alchemy]
    for key, label, start, count in groups:
        for index in range(count):
            offset = start + index * RECORD_SIZE
            item_id = struct.unpack_from('<h', payload, offset + 4)[0]
            if item_id >= 0:
                fields.append(Field(f'{key}_{index}_quality', f'Quality (item ID {item_id})',
                                    offset + 6, 2, 999, label, index + 1))
                if key == 'expendable':
                    _usage_field(fields, payload, offset, f'{key}_{index}', label, index + 1,
                                 experimental=experimental)
    for identity, start in equipment:
        for index, slot in enumerate(EQUIPMENT_SLOTS):
            offset = start + index * RECORD_SIZE
            item_id = struct.unpack_from('<h', payload, offset + 4)[0]
            if item_id >= 0:
                fields.append(Field(f'character_{identity}_{index}_quality',
                                    f'{slot}: Quality (item ID {item_id})', offset + 6, 2, 999,
                                    CHARACTER_NAMES[identity] + ' equipment', index + 1))
                if index >= 4:
                    _usage_field(fields, payload, offset, f'character_{identity}_{index}',
                                 CHARACTER_NAMES[identity] + ' equipment', index + 1, slot,
                                 experimental=experimental)
    return MappingProxyType({field.id: field for field in fields})


def _usage_field(fields, payload, offset, key, group, slot, label='Battle item', *, experimental=False):
    # Published ItemRecord: current uses at +0x24, saved capacity at +0x25.
    # Capacity belongs to this existing item, not a guessed universal maximum.
    # Unusual/inconsistent records stay visible in inspection without writes.
    current, capacity = payload[offset + 0x24:offset + 0x26]
    if 0 < capacity and (current <= capacity or experimental):
        fields.append(Field(key + '_uses', f'{label}: Remaining uses (capacity {capacity})',
                            offset + 0x24, 1, capacity, group, slot))


def item_records(document):
    """Inspect occupied records without interpreting unknown IDs as item names."""
    validate_document(document)
    groups, equipment, _, _, _ = _structure(document.payload)
    regions = [(label, index + 1, start + index * RECORD_SIZE, '')
               for _, label, start, count in groups for index in range(count)]
    regions.extend((CHARACTER_NAMES[identity] + ' equipment', index + 1,
                    start + index * RECORD_SIZE, slot)
                   for identity, start in equipment for index, slot in enumerate(EQUIPMENT_SLOTS))
    records = []
    for group, slot, offset, label in regions:
        item_id = struct.unpack_from('<h', document.payload, offset + 4)[0]
        if item_id < 0:
            continue
        records.append({
            'group': group, 'slot': slot, 'label': label or f'Slot {slot}',
            'item_id': item_id, 'instance_id': struct.unpack_from('<H', document.payload, offset)[0],
            'quality': struct.unpack_from('<H', document.payload, offset + 6)[0],
            'traits': struct.unpack_from('<hhh', document.payload, offset + 0x0A),
            'effects': struct.unpack_from('<hhhh', document.payload, offset + 0x10),
            'uses': document.payload[offset + 0x24], 'capacity': document.payload[offset + 0x25],
            'stat_bytes': tuple(document.payload[offset + 0x27:offset + 0x2C]),
        })
    return tuple(records)


def field_map(document):
    validate_document(document)
    return _field_index(document.payload, experimental_enabled())


def fields_for(document):
    return tuple(field_map(document).values())


def record_label(slot, group='Alchemy'):
    return f'{group} slot {slot}' if slot else group


def changed_payload(document, changes):
    fields = field_map(document)
    output = bytearray(document.payload)
    for key, value in changes.items():
        if key not in fields:
            raise SaveError('The requested Sophie 2 field is not mapped or the item slot is empty.')
        field = fields[key]
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(output)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    try:
        raw = codec.encode_file(document.header, payload, document.seed, document.footer) + document.trailer
    except codec.SaveFormatError as error:
        raise SaveError(f'Sophie 2 output encoding failed: {error}.') from error
    result = decode(raw, GAME_ID, document.source)
    if (result.payload, result.seed, result.header, result.trailer, result.footer) != (
            payload, document.seed, document.header, document.trailer, document.footer):
        raise SaveError('Sophie 2 edited copy failed full decode read-back verification.')
    return raw


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    fields = field_map(document)
    if key not in fields:
        raise SaveError('The requested Sophie 2 field is not mapped or the item slot is empty.')
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    fields = field_map(document)
    result = {}
    for key in keys:
        if key not in fields:
            raise SaveError('The requested Sophie 2 field is not mapped.')
        field = fields[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and type(current) is int and current <= field.maximum:
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
    source = _copy_path(document.source)
    folder = _copy_path(source.parent / 'WarriorsEditorBackups')
    return snapshot_backup(document.raw, source, GAME_ID, folder)


def save_as(document, changes, destination):
    destination = _copy_path(destination)
    if destination.suffix.casefold() != '.dat':
        raise SaveError('Choose a new .dat destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    with _copy_path(document.source).open('rb') as stream:
        current = stream.read(MAX_FILE_SIZE + 1)
    if current != document.raw:
        raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = _copy_path(backup_path), _copy_path(destination)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', MAX_FILE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def inspection_rows(document):
    validate_document(document)
    groups, equipment, alchemy, plachta_lv, gem_offset = _structure(document.payload)
    rows = [{'group': 'Alchemy', 'label': 'Plachta: raw level field (read only)',
             'value': int.from_bytes(document.payload[plachta_lv:plachta_lv + 4], 'little')},
            {'group': 'Resources', 'label': 'm_mixGem (raw field; read only)',
             'value': int.from_bytes(document.payload[gem_offset:gem_offset + 4], 'little')}]
    for key, offset in alchemy:
        rows.append({'group': 'Alchemy', 'label': key,
                     'value': int.from_bytes(document.payload[offset:offset + 4], 'little')})
    for _, label, start, count in groups:
        occupied = sum(struct.unpack_from('<h', document.payload, start + i * RECORD_SIZE + 4)[0] >= 0
                       for i in range(count))
        rows.append({'group': 'Inventory', 'label': label,
                     'value': f'{occupied} existing items in {count} physical records'})
    for identity, start in equipment:
        values = [str(struct.unpack_from('<h', document.payload, start + i * RECORD_SIZE + 4)[0])
                  for i in range(8)]
        rows.append({'group': 'Equipment', 'label': CHARACTER_NAMES[identity] + ' item IDs (read only)',
                     'value': ', '.join(values)})
    return tuple(rows)


def field_hint(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('The requested Sophie 2 field is not mapped.')
    if field.group == 'Alchemy':
        return ('Alchemy EXP. 2,147,483,647 is a storage bound; '
                'use a known EXP value. Excluded from Max.')
    if key.endswith('_uses'):
        return ('Remaining uses of this existing battle item. Max refills to its opened '
                'saved capacity; capacity, identity, traits and effects stay unchanged. '
                'Inconsistent or zero-capacity records are inspection only.')
    return ('Existing item quality, edit limit 999. Higher existing values survive Max. '
            'Item/instance IDs, ownership, traits/effects and every other item byte are preserved.')

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'

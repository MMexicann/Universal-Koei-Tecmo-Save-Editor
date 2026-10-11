"""Surgical quality editing for qualified original Ryza PC/Switch profiles.

See docs/RYZA_FORMATS.md and docs/RYZA_SWITCH_FORMAT.md for factual profiles, mechanics
and limits. Tagged node lengths are little endian; array sizes are big endian;
item quality is little-endian u16. PS4 DWORD quality cheats are not copied.
"""
from dataclasses import dataclass
from functools import lru_cache
from collections import Counter
from collections.abc import Mapping
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.ryza import codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'atelier_ryza'
SWITCH_GAME_ID = 'atelier_ryza_switch'
RYZA2_SWITCH_GAME_ID = 'atelier_ryza2_switch'
MAX_FILE_SIZE = codec.MAX_FILE_SIZE
INTEGRITY_KIND = 'checksum'
CHARACTERS = {
    GAME_ID: ('Ryza', 'Klaudia', 'Lent', 'Tao', 'Empel', 'Lila'),
    SWITCH_GAME_ID: ('Ryza', 'Klaudia', 'Lent', 'Tao', 'Empel', 'Lila'),
    RYZA2_SWITCH_GAME_ID: ('Ryza', 'Character ID 1', 'Character ID 2', 'Character ID 3',
                         'Character ID 4', 'Character ID 5', 'Character ID 6'),
    'atelier_ryza2': ('Ryza', 'Character ID 1', 'Character ID 2', 'Character ID 3',
                      'Character ID 4', 'Character ID 5', 'Character ID 6'),
}
POOLS = (('basket', b'm_unitBasket', 'Basket'),
         ('important_basket', b'm_unitBasketImportant', 'Important basket'),
         ('container', b'm_unitContainer', 'Container'),
         ('important', b'm_unitContainerImportant', 'Important items'),
         ('expendable', b'm_unitContainerExpendable', 'Consumable container'))
SLOTS = ('Weapon', 'Armor', 'Accessory 1', 'Accessory 2',
         'Core item 1', 'Core item 2', 'Core item 3', 'Core item 4')


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    group: str
    slot: int
    maxable: bool = True
    size: int = 2
    minimum: int = 1
    kind: str = 'int'
    byteorder: str = 'little'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], self.byteorder)

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from {self.minimum} to {self.maximum}.')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    note: str
    size: int = MAX_FILE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False


FORMATS = {
    GAME_ID: Format(GAME_ID, 'Atelier Ryza: Ever Darkness & the Secret Hideout (Steam PC)',
                    'Unregistered complete-layout candidate. Available native copies have an '
                    'incomplete final plant array and are rejected before writes.', sample_verified=False),
    SWITCH_GAME_ID: Format(SWITCH_GAME_ID, 'Atelier Ryza: Ever Darkness & the Secret Hideout (Switch)',
                          'Original complete revision-4 main-game export. Existing ordinary item/equipment '
                          'quality 1–100; higher cap unlocks remain unmapped and Max is disabled. '
                          'Two native main-game slots checked; edited game loading is untested.'),
    RYZA2_SWITCH_GAME_ID: Format(RYZA2_SWITCH_GAME_ID,
                             'Atelier Ryza 2: Lost Legends & the Secret Fairy (Switch)',
                             'Original complete revision-0 Switch main-game export. Existing quality '
                             '1–100 on zero-adjacent records; unspent skill-tree SP reductions only. '
                             'Modified public starter reference checked; game loading is untested.',
                             sample_verified=True),
    'atelier_ryza2': Format('atelier_ryza2', 'Atelier Ryza 2: Lost Legends & the Secret Fairy (Steam PC)',
                           'Original native 100-byte-item layout. Existing ordinary item/equipment '
                           'quality 1–100; excluded from Max until higher skill caps are mapped. '
                           'Qualified unspent skill-tree SP reductions; learned skills preserved. '
                           'Genuine early-game autosave checked; game loading remains untested.'),
}


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    header: bytes
    seed: int
    footer: bytes
    trailer: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


@dataclass(frozen=True)
class Node:
    name: bytes
    start: int
    body: int
    end: int


def get_format(game_id=GAME_ID):
    if game_id not in FORMATS:
        raise SaveError('Select a qualified original Ryza game/platform adapter; DX is not supported.')
    return FORMATS[game_id]


def _nodes(payload, start, end):
    result = []
    while start < end:
        if start + 5 > end:
            raise SaveError('Truncated Ryza tagged node.')
        size = struct.unpack_from('<I', payload, start)[0]
        node_end = start + size
        zero = payload.find(b'\0', start + 4, min(node_end, start + 85, end))
        if not start + 5 <= node_end <= end or zero < 0:
            raise SaveError('Invalid Ryza tagged node length/name.')
        name = payload[start + 4:zero]
        if not name or any(value < 32 or value > 126 for value in name):
            raise SaveError('Invalid Ryza tagged node name.')
        result.append(Node(name, start, zero + 1, node_end))
        start = node_end
    return tuple(result)


def _unique(nodes, name):
    matches = [node for node in nodes if node.name == name]
    if len(matches) != 1:
        raise SaveError(f'Missing or ambiguous Ryza node: {name.decode()}.')
    return matches[0]


@lru_cache(maxsize=4)
def _structure(payload, game_id):
    get_format(game_id)
    if payload[:32] != bytes.fromhex('013379c9') + bytes(28):
        raise SaveError('Unqualified Ryza native preamble.')
    root = _nodes(payload, 32, len(payload))
    if len({node.name for node in root}) != len(root):
        raise SaveError('Duplicate Ryza root node.')
    info = _unique(root, b'info')
    app = _unique(_nodes(payload, info.body, info.end), b'app_ver')
    expected_app = struct.pack('>II', 1, {GAME_ID: 0, SWITCH_GAME_ID: 4, 'atelier_ryza2': 1, RYZA2_SWITCH_GAME_ID: 0}[game_id])
    if payload[app.body:app.end] != expected_app:
        raise SaveError('Unqualified original Ryza app_ver profile; do not use a DX save.')
    fieldmap = _unique(root, b'fieldmap')
    names = {node.name for node in root}
    if game_id in (GAME_ID, SWITCH_GAME_ID):
        if b'FieldMix' not in names or b'AlchemyTree' in names or b'ruin' in names:
            raise SaveError('This is not the qualified original Ryza 1 gameplay layout.')
        markers = (b'_I_HOUSE_KLAUDIA_01\0', b'_T_BODEN\0')
        stride, count, party_size, item_id_offset, quality_offset = 66, 9, 0x3B8, 2, 4
        capacities = (200, 100, 5000, 100, 50)
    else:
        if not {b'AlchemyTree', b'ruin', b'Feeding'} <= names or b'FieldMix' in names:
            raise SaveError('This is not the qualified original Ryza 2 gameplay layout.')
        markers = (b'_I_HOUSE_ABELHEIM\0', b'_T_CENTRAL\0')
        stride, count, party_size, item_id_offset, quality_offset = 100, 10, 0x514, 4, 6
        capacities = (200, 150, 5000, 150, 50)
    if any(payload.find(marker, fieldmap.body, fieldmap.end) < 0 for marker in markers):
        raise SaveError('Native Ryza title-specific map schema is missing.')
    item = _unique(root, b'item')
    children = _nodes(payload, item.body, item.end)
    item_version = _unique(children, b'version')
    expected_item_version = b'\0\1' if game_id == SWITCH_GAME_ID else b'\0\2'
    if payload[item_version.body:item_version.end] != expected_item_version:
        raise SaveError('Unqualified Ryza item layout version.')
    regions = []
    for (key, tag, label), capacity in zip(POOLS, capacities):
        node = _unique(children, tag)
        if (node.body + 4 + capacity * stride != node.end
                or struct.unpack_from('>I', payload, node.body)[0] != capacity * stride):
            raise SaveError('Ryza inventory capacity/stride does not match the native profile.')
        regions.append((key, label, node.body + 4, capacity, None))
    party = _unique(root, b'party')
    if party.body + 4 > party.end:
        raise SaveError('Truncated Ryza Party version node.')
    version_end = party.body + struct.unpack_from('<I', payload, party.body)[0]
    if not party.body + 5 <= version_end <= party.end:
        raise SaveError('Invalid Ryza Party version framing.')
    version = _unique(_nodes(payload, party.body, version_end), b'version')
    if payload[version.body:version.end] != b'\0\3':
        raise SaveError('Unqualified Ryza Party layout version.')
    if version_end + 4 > party.end or struct.unpack_from('>I', payload, version_end)[0] != count:
        raise SaveError('Ryza Party array count is invalid.')
    array_end = version_end + 4 + count * party_size
    if array_end > party.end:
        raise SaveError('Ryza Party array is truncated.')
    members = _nodes(payload, version_end + 4, array_end)
    _nodes(payload, array_end, party.end)
    if any(node.name != b'Party' for node in members):
        raise SaveError('Ryza Party array contains a foreign record.')
    if len(members) != count or any(node.end - node.start != party_size for node in members):
        raise SaveError('Ryza Party count/stride does not match the native profile.')
    identities = []
    for node in members:
        identity = struct.unpack_from('>i', payload, node.body)[0]
        if identity == -1:
            continue
        if identity not in range(len(CHARACTERS[game_id])) or identity in identities:
            raise SaveError('Invalid or duplicate Ryza Party identity.')
        identities.append(identity)
        # Array prefix is native and independently observed in both titles.
        prefix = node.start + 4 + 0x192
        start = prefix + 4
        if (start + 8 * stride > node.end
                or struct.unpack_from('>I', payload, prefix)[0] != 8 * stride):
            raise SaveError('Ryza equipment array framing is invalid.')
        regions.append((f'character_{identity}', CHARACTERS[game_id][identity] + ' equipment', start, 8, identity))
    if not identities or 0 not in identities:
        raise SaveError('The Ryza gameplay save lacks its protagonist record.')
    seen = {}
    records = []
    for key, label, start, capacity, identity in regions:
        for slot in range(capacity):
            offset = start + slot * stride
            serial = struct.unpack_from('<H', payload, offset)[0]
            item_id = struct.unpack_from('<h', payload, offset + item_id_offset)[0]
            if item_id == -1 and (serial == 0xFFFF or (identity is not None and serial == identity * 8 + slot)):
                continue
            if item_id < 0 or serial == 0xFFFF:
                raise SaveError('Ryza item ownership is malformed; no writes are allowed.')
            if serial in seen:
                previous_offset, previous_identity = seen[serial]
                # Two native Switch slots contain byte-identical equipment aliases.
                # Keep all alias occurrences read only until transfer/equip pairs
                # establish how the game updates their shared instance.
                if (game_id != SWITCH_GAME_ID
                        or (identity is None and previous_identity is None)
                        or payload[offset:offset + stride] != payload[previous_offset:previous_offset + stride]):
                    raise SaveError('Ryza item ownership is malformed or ambiguously duplicated.')
            else:
                seen[serial] = (offset, identity)
            records.append((key, label, slot + 1, offset, item_id, serial, identity))
    return tuple(records), quality_offset


@lru_cache(maxsize=4)
def _snapshot(raw, game_id):
    try:
        header, payload, details = codec.decode_file(raw)
    except (codec.SaveFormatError, struct.error, IndexError) as error:
        raise SaveError(f'Ryza native integrity/codec check failed: {error}.') from error
    # Header is native framing, not a title discriminator.
    revision = {GAME_ID: 0, SWITCH_GAME_ID: 4, 'atelier_ryza2': 1, RYZA2_SWITCH_GAME_ID: 0}[game_id]
    if (header[:40] != b'\x01' + bytes(39)
            or header[40:48] != struct.pack('<II', 1, revision)):
        raise SaveError('Unqualified Ryza game/platform native header.')
    _structure(payload, game_id)
    return header, payload, details, raw[codec.HEADER_SIZE + details.padded_size:]


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    layout = get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or not codec.HEADER_SIZE < len(raw) <= MAX_FILE_SIZE:
        raise SaveError('Ryza file size exceeds the processing bounds.')
    raw = bytes(raw)
    header, payload, details, trailer = _snapshot(raw, game_id)
    return Document(layout, Path(source), raw, payload, header, details.seed, details.footer, trailer)


def validate_document(document):
    if (type(document) is not Document or type(document.format) is not Format
            or type(document.format.id) is not str
            or document.format is not get_format(document.format.id) or type(document.seed) is not int):
        raise SaveError('Unregistered Ryza snapshot.')
    original = decode(document.raw, document.format.id, document.source)
    if document != original or any(type(getattr(document, key)) is not bytes
                                   for key in ('raw', 'payload', 'header', 'footer', 'trailer')):
        raise SaveError('Ryza opened snapshot changed outside the staged edit workflow.')


def _copy_path(path):
    resolved = safe_path(path)
    for text in (str(path), str(resolved)):
        text = text.replace('\\', '/').casefold().rstrip('/')
        if any('/koeitecmo/' + name + '/' in text + '/'
               for name in ('atelier ryza', 'atelier ryza 2', 'atelier ryza 3',
                            'atelier ryza dx', 'atelier ryza 2 dx', 'atelier ryza 3 dx')):
            raise SaveError('Use a separate copy outside live Atelier Ryza save folders.')
    return resolved


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    if path.suffix.casefold() != '.dat':
        raise SaveError('Open a separate native .dat gameplay copy for the selected game/platform.')
    with path.open('rb') as stream:
        raw = stream.read(MAX_FILE_SIZE + 1)
    return decode(raw, game_id, path)


@lru_cache(maxsize=4)
def _fields(payload, game_id):
    records, quality_offset = _structure(payload, game_id)
    result = {}
    occurrences = Counter(record[5] for record in records)
    for key, label, slot, offset, item_id, _serial, identity in records:
        quality = struct.unpack_from('<H', payload, offset + quality_offset)[0]
        if key.startswith('important') or quality in (0, 0xFFFF) or occurrences[_serial] > 1:
            continue  # Important/no-quality records do not inherit ordinary item rules.
        if (game_id in (SWITCH_GAME_ID, RYZA2_SWITCH_GAME_ID)
                and struct.unpack_from('<H', payload, offset + quality_offset + 2)[0] != 0):
            continue  # Unproved coupled equipment/synthesis value; no DWORD normalization.
        maximum = 999 if game_id == GAME_ID else 100
        title = SLOTS[slot - 1] if identity is not None else f'Item ID {item_id}'
        field = Field(f'{key}_{slot - 1}_quality', title + ': Quality', offset + quality_offset,
                      maximum, label, slot, game_id == GAME_ID)
        result[field.id] = field
    if game_id in ('atelier_ryza2', RYZA2_SWITCH_GAME_ID):
        field = _skill_point_field(payload)
        if field is not None:
            result[field.id] = field
    return MappingProxyType(result)


def _skill_point_field(payload):
    """Observed Ryza 2 AlchemyTree tag/four-byte unspent SP scalar.

    Unknown tree revisions/absent scalar remain preserved without a control.
    SkillState is separate ownership data and is never rewritten. Reductions
    only avoid claiming an unproved acquisition/cap or unlocking any skill.
    """
    tree = _unique(_nodes(payload, 32, len(payload)), b'AlchemyTree')
    try:
        children = _nodes(payload, tree.body, tree.end)
    except SaveError:
        return None  # The old item profile did not qualify tree child framing.
    versions = [node for node in children if node.name == b'ver']
    points = [node for node in children if node.name == b'SkillPoint']
    if (len(versions) != 1 or len(points) != 1
            or payload[versions[0].body:versions[0].end] != bytes.fromhex('000000020004')):
        return None
    scalar = points[0]
    if (scalar.end - scalar.body != 8
            or payload[scalar.body:scalar.body + 4] != b'\0\0\0\4'):
        return None
    offset = scalar.body + 4
    original = int.from_bytes(payload[offset:offset + 4], 'big', signed=True)
    if original < 0:
        return None
    return Field('skill_points', 'Unspent skill-tree SP (reduce only)', offset,
                 original, 'Skill-tree resources', 0, maxable=False, size=4,
                 minimum=0, byteorder='big')


def field_map(document):
    validate_document(document)
    return _fields(document.payload, document.format.id)


def fields_for(document):
    return tuple(field_map(document).values())


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str:
        raise SaveError('Unmapped Ryza field, empty record or important item.')
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('Unmapped Ryza field, empty record or important item.')
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    return result


def changed_payload(document, changes):
    fields = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('Ryza staged changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unmapped Ryza field, empty record or important item.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, field.byteorder)
    return bytes(output)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = codec.encode_file(document.header, payload, document.seed, document.footer) + document.trailer
    reopened = decode(raw, document.format.id, document.source)
    if (reopened.payload, reopened.seed, reopened.header, reopened.footer, reopened.trailer) != (
            payload, document.seed, document.header, document.footer, document.trailer):
        raise SaveError('Ryza edited copy failed native read-back verification.')
    return raw


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    fields = field_map(document)
    result = {}
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('Unmapped Ryza field.')
        field = fields[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and type(current) is int and current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    result = dict(changes)
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def _validate_source(document):
    source = _copy_path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(MAX_FILE_SIZE + 1)
    except OSError as error:
        raise SaveError('The opened copy is unavailable; reopen before saving or backing up.') from error
    if current != document.raw:
        raise SaveError('The opened copy changed on disk; reopen before saving or backing up.')
    return source


def backup(document):
    validate_document(document)
    source = _validate_source(document)
    return snapshot_backup(document.raw, source, document.format.id,
                           _copy_path(source.parent / 'WarriorsEditorBackups'))


def save_as(document, changes, destination):
    validate_document(document)
    destination = _copy_path(destination)
    if destination.suffix.casefold() != '.dat':
        raise SaveError('Choose a new .dat destination.')
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    _validate_source(document)
    raw = serialize(document, changes)
    backup(document)
    # Encoding and backup creation can take time: reject a source changed
    # during either operation immediately before publishing the new copy.
    _validate_source(document)
    atomic_new(raw, destination)
    return decode(raw, document.format.id, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(_copy_path(backup_path), _copy_path(destination), game_id, '.dat', MAX_FILE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group):
    return f'{group}, slot {slot}'


def item_records(document):
    validate_document(document)
    records, quality_offset = _structure(document.payload, document.format.id)
    return tuple({'group': label, 'slot': slot, 'item_id': item_id, 'instance_id': serial,
                  'quality': struct.unpack_from('<H', document.payload, offset + quality_offset)[0],
                  'neighbor': struct.unpack_from('<H', document.payload, offset + quality_offset + 2)[0],
                  'label': SLOTS[slot - 1] if identity is not None else f'Slot {slot}',
                  'traits': tuple((struct.unpack_from('<H', document.payload, offset + 22 + index * 2)[0],
                                   document.payload[offset + 28 + index]) for index in range(3))
                            if document.format.id == SWITCH_GAME_ID else ()}
                 for _, label, slot, offset, item_id, serial, identity in records)


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unmapped Ryza field.')
    if key == 'skill_points':
        return ('Reduce the opened unspent skill-tree SP balance only. Max is disabled. '
                'Learned recipes/skills, prerequisite nodes, quality caps and quest rewards remain unchanged.')
    note = 'Existing item quality only; adjacent synthesis data, traits, effects, ownership and equipment remain intact.'
    if document.format.id != GAME_ID:
        note += ' Quality edits stop at 100; higher progression caps are unmapped. Excluded from Max.'
    if document.format.id in (SWITCH_GAME_ID, RYZA2_SWITCH_GAME_ID):
        note += ' Only records with zero adjacent synthesis word and no shared instance gain a control.'
    return note

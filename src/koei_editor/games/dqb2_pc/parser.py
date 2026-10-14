"""Bounded Steam CMNDAT stack deductions, independently implemented.

Published DQB2 writers establish zlib framing and ordinary item records.
No world, quest, equipment, player-growth or ownership values are writable.
See docs/DQB2_PC_FORMAT.md for native evidence and licence boundaries.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import struct
from types import MappingProxyType
import zlib

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'dqb2_pc'
EXTENSION = '.bin'
HEADER_SIZE = 0x2A444
BODY_SIZE = 5627194
PADDED_SIZE = HEADER_SIZE + BODY_SIZE
MAX_SIZE = PADDED_SIZE
USED_LENGTH_OFFSET = 0x10
POCKET_BASE, POCKET_COUNT = 0x55B28D, 15
BAG_BASE, BAG_COUNT = 0x55B2C9, 420
INTEGRITY_KIND = 'checksum'
# These are twenty individually reviewed factual ID/name pairs, not an import
# of an upstream catalog. Unknown items remain inspectable and unchanged.
ORDINARY_ITEMS = MappingProxyType({
    2: 'Medicinal herb', 6: 'Antidotal herb',
    16: 'Angel brew', 17: 'Moonwort bulb', 47: 'Yggdrasil leaf',
    198: 'Strong medicine', 740: 'Yggdrasil dew',
    1819: 'Wheat seed', 1820: 'Bean seed', 1821: 'Cabbage seed',
    1823: 'Corn seed', 1824: 'Chilli pepper seed',
    1825: 'Sugarcane seed', 1826: 'Strawberry seed',
    1827: 'Coffee bean', 1828: 'Leek seed', 1829: 'Potato seed',
    1830: 'Pumpkin seed', 1831: 'Tomato seed', 1836: 'Wasabi seed',
})


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    group: str
    slot: int
    size: int = 2
    minimum: int = 1
    maxable: bool = False
    kind: str = 'int'

    @property
    def experimental_maximum(self):
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        return struct.unpack_from('<H', payload, self.offset)[0]

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label}: reduce the existing quantity to a whole number '
                            f'from {self.minimum} to {self.maximum}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Dragon Quest Builders 2 (original Steam PC CMNDAT)'
    size: int = MAX_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Original Steam CMNDAT.BIN copies: reduce existing named ordinary '
                 'medicine/seed stacks, preserving at least one item. Pockets, bag and '
                 'player/equipment status are searchable. Keep all other original save '
                 'files together; this does not modify island/world data or save ownership.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the original Steam Dragon Quest Builders 2 profile.')
    return FORMAT


@lru_cache(maxsize=4)
def _decoded(raw):
    """Bounded EOF/Adler validation; unused native capacity is opaque data."""
    if type(raw) is not bytes or not HEADER_SIZE + 8 <= len(raw) <= MAX_SIZE:
        raise SaveError('Requires a complete bounded original Steam CMNDAT.BIN copy.')
    if (raw[:4] != b'aerC'
            or raw[4:8] not in (bytes.fromhex('00010002'), bytes.fromhex('02010002'))
            or struct.unpack_from('<I', raw, 8)[0] not in (0x40003, 0x40004)
            or raw[12:16] != bytes.fromhex('02020000')):
        raise SaveError('Unsupported Dragon Quest Builders 2 CMNDAT revision/profile.')
    used = struct.unpack_from('<I', raw, USED_LENGTH_OFFSET)[0]
    if not HEADER_SIZE + 8 <= used <= len(raw):
        raise SaveError('CMNDAT used length is outside the complete copied file.')
    if len(raw) != used and len(raw) != PADDED_SIZE:
        raise SaveError('CMNDAT must be compact or use the qualified native padded capacity.')
    decoder = zlib.decompressobj()
    try:
        body = decoder.decompress(raw[HEADER_SIZE:used], BODY_SIZE + 1)
    except zlib.error as error:
        raise SaveError('CMNDAT compressed data or its native Adler checksum is damaged.') from error
    if (len(body) != BODY_SIZE or not decoder.eof
            or decoder.unused_data or decoder.unconsumed_tail):
        raise SaveError('CMNDAT requires exactly one complete bounded native zlib body.')
    return body


def decode(raw, game_id=GAME_ID, source=Path('CMNDAT.BIN')):
    get_format(game_id)
    # Reject mutable aliases before the cache can hash or retain their data.
    if type(raw) is not bytes:
        raise SaveError('A frozen native CMNDAT byte snapshot is required.')
    return Document(FORMAT, Path(source), raw, _decoded(raw))


def _copy_path(path):
    original = Path(path)
    path = safe_path(original)
    for candidate in (original, original.absolute(), path):
        normalized = str(candidate).replace('\\', '/').casefold()
        if re.search(r'/my games/(?:dragon quest builders (?:ii|2)|'
                     r'ドラゴンクエストビルダーズ[２2])(?:/|$)', normalized):
            raise SaveError('Use a separate copy outside the live Dragon Quest Builders 2 save folder.')
        if re.search(r'/dragon quest builders (?:ii|2)/(?:steam|savedata|save)(?:/|$)', normalized):
            raise SaveError('Use a separate copy outside the live Dragon Quest Builders 2 save folder.')
    if path.suffix.lower() != EXTENSION:
        raise SaveError('Choose a separate CMNDAT .bin copy, outside the live save folder.')
    return path


def read_save(path, game_id=GAME_ID):
    path = _copy_path(path)
    with path.open('rb') as stream:
        raw = stream.read(MAX_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or _decoded(document.raw) != document.payload):
        raise SaveError('A frozen qualified original CMNDAT snapshot is required.')


def _records(payload):
    for group, base, count in (('Pockets', POCKET_BASE, POCKET_COUNT),
                               ('Bag', BAG_BASE, BAG_COUNT)):
        for index in range(count):
            offset = base + index * 4
            item_id, quantity = struct.unpack_from('<HH', payload, offset)
            yield group, index + 1, offset, item_id, quantity


@lru_cache(maxsize=4)
def _fields(payload):
    return tuple(Field(f'{group.lower()}_{slot}', f'{ORDINARY_ITEMS[item_id]} quantity',
                       offset + 2, quantity, group, slot)
                 for group, slot, offset, item_id, quantity in _records(payload)
                 if item_id in ORDINARY_ITEMS and quantity >= 1)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('CMNDAT edits must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only existing qualified ordinary pocket/bag quantities can be reduced.')
        field = mapping[key]
        field.validate(value)
        struct.pack_into('<H', output, field.offset, value)
    return bytes(output)


def serialize(document, changes):
    body = changed_payload(document, changes)
    if body == document.payload:
        return document.raw
    compressed = zlib.compress(body, level=6)
    used = HEADER_SIZE + len(compressed)
    original_used = struct.unpack_from('<I', document.raw, USED_LENGTH_OFFSET)[0]
    header = bytearray(document.raw[:HEADER_SIZE])
    struct.pack_into('<I', header, USED_LENGTH_OFFSET, used)
    if len(document.raw) == original_used:
        result = bytes(header) + compressed
    else:
        # Original unused native capacity can contain stale nonzero data. Keep
        # every such byte at its original absolute position; never normalize it.
        if used > original_used:
            raise SaveError('Edited CMNDAT would overwrite original unused data; this edit cannot be saved safely.')
        result = bytes(header) + compressed + document.raw[used:]
    if _decoded(result) != body:
        raise SaveError('Edited CMNDAT did not pass its complete native framing/checksum check.')
    return result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('This CMNDAT record is inspection only.')
    mapping[key].validate(value)
    pending = dict(changes)
    if value == mapping[key].value(document.payload):
        pending.pop(key, None)
    else:
        pending[key] = value
    return pending


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapping = field_map(document)
    if (type(keys) not in (list, tuple, set, frozenset)
            or any(type(key) is not str or key not in mapping for key in keys)):
        raise SaveError('This CMNDAT record is inspection only.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def _source(document):
    validate_document(document)
    source = _copy_path(document.source)
    with source.open('rb') as stream:
        if stream.read(MAX_SIZE + 1) != document.raw:
            raise SaveError('The original CMNDAT copy changed. Reopen it before saving.')
    return source


def backup(document):
    source = _source(document)
    return snapshot_backup(document.raw, source, GAME_ID, source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    source = _source(document)
    destination = _copy_path(destination)
    if destination == source or destination.exists():
        raise FileExistsError('Choose a new file; original and existing saves are never replaced.')
    raw = serialize(document, changes)
    backup(document)
    _source(document)
    atomic_new(raw, destination)
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(_copy_path(backup_path), _copy_path(destination), GAME_ID, EXTENSION,
                            MAX_SIZE, validate_raw=lambda raw: decode(raw))


def record_label(slot, group='Bag'):
    return f'{group} slot {slot}'


def item_records(document):
    validate_document(document)
    return tuple((group, slot, item_id, ORDINARY_ITEMS.get(item_id, 'Empty' if item_id == 0 else 'Unmapped item'),
                  quantity, 'Quantity reduction' if item_id in ORDINARY_ITEMS and 2 <= quantity <= 999
                  else 'Inspection only')
                 for group, slot, _offset, item_id, quantity in _records(document.payload))


def player_records(document):
    validate_document(document)
    body = document.payload
    # Labels mirror separately published stored words. No derived stat, level,
    # HP or EXP dependency is inferred or changed here.
    words = [('Stored level', 0x6A9CF, 1), ('Stored EXP', 0x6A9D1, 4),
             ('Stored HP', 0x6A890, 2), ('Stored HP bonus', 0x6A892, 2),
             ('Stored fullness (hundredths)', 0x6A896, 2),
             ('Stored attack', 0x6A898, 2), ('Stored defense', 0x6A89A, 2),
             ('Weapon item ID', 0x55B959, 2), ('Hammer item ID', 0x55B95D, 2),
             ('Shield item ID', 0x55B985, 2), ('Armor item ID', 0x55B989, 2)]
    return tuple((name, int.from_bytes(body[offset:offset + size], 'little'))
                 for name, offset, size in words)

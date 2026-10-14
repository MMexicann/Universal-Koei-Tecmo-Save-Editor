"""Decrypted Atelier Ayesha PS3 copies; PFD authentication remains external.

Three public native exports qualify the framing and inventory capacities. Two
Japanese files independently match published literal money values. Only money
and conservative existing-stack reductions are writable; qualities and all
properties, item identities and progression words stay byte-identical.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import math
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_enabled, within_numeric_limits
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.ps3_export import validate_optional_context
from koei_editor.shared.save_safety import safe_path

GAME_ID, EXTENSION, SAVE_SIZE = 'ayesha_ps3', '.bin', 742400
INTEGRITY_KIND = 'external'
TITLE_IDS = ('BLUS31152', 'BLJM60486')
HEADER = bytes.fromhex('0132dc5700000000')
GOLD_OFFSET = 0xBD4C
POOLS = (('Basket', 0x392BC, 120), ('Container', 0x3A1C0, 10000))
RECORD_SIZE = 32


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str = 'Resources'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'big')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Atelier Ayesha (PS3, US/Japanese decrypted export)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Observed US/Japanese decrypted PS3 USR-DATA profile. Individual '
                 'Cole edits and existing ordinary stack reductions; qualities, '
                 'properties and memory-related words are inspection only. Max '
                 'is disabled. Reimport and resign with Apollo; PS3 encryption '
                 'and PFD authentication are not performed by this adapter.')


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
        raise SaveError('Select the observed Atelier Ayesha decrypted PS3 profile.')
    return FORMAT


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:8] != HEADER:
        raise SaveError('Requires the observed 742,400-byte decrypted Atelier Ayesha PS3 USR-DATA profile.')
    for _, base, count in POOLS:
        if int.from_bytes(raw[base - 4:base], 'big') != count or base + count * RECORD_SIZE > len(raw):
            raise SaveError('Atelier Ayesha inventory capacity/stride profile does not match.')
    if raw[0x392B4:0x392B8] != bytes.fromhex('0004fd98') or raw[0x883C0:0x883C4] != (100).to_bytes(4, 'big'):
        raise SaveError('Atelier Ayesha surrounding inventory serializer markers are unsupported.')


def decode(raw, game_id=GAME_ID, source=Path('ayesha-copy.bin')):
    get_format(game_id)
    qualify(raw)
    return Document(FORMAT, Path(source), raw, raw)


def _copy_path(path):
    path = safe_path(path)
    if path.suffix.lower() != EXTENSION:
        raise SaveError('Use a separate decrypted PS3 .bin copy outside managed save folders.')
    validate_optional_context(path, TITLE_IDS)
    return path


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('A frozen decrypted Atelier Ayesha PS3 snapshot is required.')
    qualify(document.raw)


@lru_cache(maxsize=4)
def _records(payload):
    rows = []
    for group, base, count in POOLS:
        for slot in range(count):
            offset = base + slot * RECORD_SIZE
            identity = int.from_bytes(payload[offset + 2:offset + 4], 'big')
            quantity = int.from_bytes(payload[offset + 30:offset + 32], 'big')
            # Source editor scans the occupied prefix. Never activate dormant
            # records after an empty sentinel, nor manufacture a deleted stack.
            if identity == 0xFFFF or (group == 'Container' and quantity == 0):
                break
            quality = struct.unpack_from('>f', payload, offset + 4)[0]
            appraisal = int.from_bytes(payload[offset + 18:offset + 20], 'big')
            rows.append((group, slot + 1, offset, identity, quantity, quality, appraisal))
    return tuple(rows)


@lru_cache(maxsize=4)
def _fields(payload, experimental=False):
    fields = [Field('cole', 'Cole', GOLD_OFFSET, 4, 999999)]
    for group, slot, offset, identity, quantity, quality, appraisal in _records(payload):
        if ((1 if experimental else 2) <= quantity <= (0xFFFF if experimental else 255) and appraisal == 0 and math.isfinite(quality)
                and 0 <= quality <= 120):
            fields.append(Field(f'{group.lower()}_{slot}_quantity',
                                f'Item ID {identity}: Reduce stack quantity', offset + 30,
                                2, quantity, group + ' stacks', slot, minimum=1))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Atelier Ayesha changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapping:
            raise SaveError('Only Cole and qualified existing stack reductions are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        output[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(output)


def serialize(document, changes):
    result = changed_payload(document, changes)
    qualify(result)
    return document.raw if result == document.payload else result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if key not in mapping:
        raise SaveError('The requested Atelier Ayesha record is inspection only.')
    result = dict(changes)
    if type(value) is int and value == mapping[key].value(document.payload):
        result.pop(key, None)
    else:
        mapping[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    mapping = field_map(document)
    changed_payload(document, changes)
    if any(key not in mapping for key in keys):
        raise SaveError('The requested Atelier Ayesha field is not editable.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    _copy_path(document.source)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    source, destination = _copy_path(document.source), _copy_path(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    with source.open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    result = serialize(document, changes)
    backup(document)
    atomic_new(result, destination)
    return decode(result, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination = _copy_path(destination)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Resources'):
    return f'{group.removesuffix(" stacks")} slot {slot}' if slot else group


def item_records(document):
    validate_document(document)
    rows = []
    mapping = field_map(document)
    for group, slot, offset, identity, quantity, quality, appraisal in _records(document.payload):
        instance = int.from_bytes(document.payload[offset:offset + 2], 'big')
        traits = struct.unpack_from('>5H', document.payload, offset + 8)
        effects = struct.unpack_from('>4H', document.payload, offset + 20)
        key = f'{group.lower()}_{slot}_quantity'
        rows.append((group, slot, identity, instance, quantity, f'{quality:.9g}',
                     ', '.join(str(v) for v in traits if v != 0xFFFF),
                     ', '.join(str(v) for v in effects if v != 0xFFFF),
                     f'0x{appraisal:04X}', 'Reduce only' if key in mapping else 'Inspection only'))
    return tuple(rows)


def memory_records(document):
    validate_document(document)
    return tuple((f'Memory-related word {index + 1}',
                  int.from_bytes(document.payload[offset:offset + 4], 'big'))
                 for index, offset in enumerate((0x9D381, 0x9D385)))


def field_hint(document, key):
    field = field_map(document)[key if isinstance(key, str) else key.id]
    if field.id == 'cole':
        return ('Manual editor range 0–999,999; no natural cap or Max claim. Higher opened '
                'values remain unchanged. After editing, Apollo reimport/resign is required.')
    return ('Reduce this existing stack to 1–its opened quantity. Increasing, deleting '
            'or acquiring items is unavailable. Item identities, float quality, properties '
            'and memory/story records stay unchanged. Max is disabled; Apollo reimport/resign required.')

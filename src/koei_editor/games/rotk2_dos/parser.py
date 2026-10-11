"""Independent raw-save writer for the published 30,752-byte Chinese DOS profile.

Public field facts and complete raw writer: JuQiang/RoTK2Editor_Python.
See docs/ROTK2_DOS_FORMAT.md; no external implementation/catalog/assets reused.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'rotk2_dos'
SIZE = MAX_FILE_SIZE = 30752
INTEGRITY_KIND = 'none'
OFFICER_START, OFFICER_STRIDE, OFFICER_COUNT = 32, 43, 255
PROVINCE_START, PROVINCE_STRIDE, PROVINCE_COUNT = 0x2D8C, 35, 41
POINTER_BIAS = 0x38


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Romance of the Three Kingdoms II (Chinese DOS)'
    note: str = ('Exact 30,752-byte Chinese DOS raw-save layout. Owned-province gold/rice '
                 'deductions; ownership, calendar, officers and unknown data remain intact.')
    size: int = SIZE
    fields: tuple = ()
    sample_verified: bool = False
    game_load_verified: bool = False
    editing_verified: bool = False
    published_format: bool = True


FORMAT = Format()


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    group: str
    slot: int
    size: int
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'
    byteorder: str = 'little'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from 0 to the opened balance ({self.maximum}).')


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
        raise SaveError('Select the Chinese DOS Romance of the Three Kingdoms II profile.')
    return FORMAT


def _u16(raw, offset):
    return int.from_bytes(raw[offset:offset + 2], 'little')


def _pointer(value, start, stride, count):
    if value == 0:
        return None
    offset = value - POINTER_BIAS
    if offset < start or (offset - start) % stride or (offset - start) // stride >= count:
        raise SaveError('ROTK II record pointer is outside its qualified native array.')
    return (offset - start) // stride


@lru_cache(maxsize=4)
def _validate_raw(raw):
    if len(raw) != SIZE or raw[:10] != b'1990.02.19':
        raise SaveError('Not the exact 30,752-byte Chinese DOS ROTK II save revision.')
    # Korean 36-byte officers and scenario assets have different framing.
    if not 1 <= _u16(raw, 12) <= 65535 or raw[14] > 11 or not 1 <= raw[15] <= 16:
        raise SaveError('Invalid ROTK II calendar/ruler header framing.')
    coordinates = set()
    for index in range(PROVINCE_COUNT):
        base = PROVINCE_START + PROVINCE_STRIDE * index
        _pointer(_u16(raw, base), PROVINCE_START, PROVINCE_STRIDE, PROVINCE_COUNT)
        for offset in (2, 4, 6):
            _pointer(_u16(raw, base + offset), OFFICER_START, OFFICER_STRIDE, OFFICER_COUNT)
        owner, invading_owner = raw[base + 16], raw[base + 17]
        if owner not in (*range(16), 255) or invading_owner not in (*range(16), 255):
            raise SaveError('Invalid ROTK II province ownership record.')
        x, y, region = raw[base + 32:base + 35]
        if x > 7 or y > 8 or region > 13 or (x, y) in coordinates:
            raise SaveError('Invalid/duplicate ROTK II province coordinate record.')
        coordinates.add((x, y))
    for start, stride, count in ((PROVINCE_START, PROVINCE_STRIDE, PROVINCE_COUNT),
                                  (OFFICER_START, OFFICER_STRIDE, OFFICER_COUNT)):
        links = [_pointer(_u16(raw, start + index * stride), start, stride, count)
                 for index in range(count)]
        for index in range(count):
            visited = set()
            current = index
            while current is not None:
                if current in visited:
                    raise SaveError('ROTK II record chain contains a cycle.')
                visited.add(current)
                following = links[current]
                if start == PROVINCE_START and following is not None:
                    if raw[start + current * stride + 16] != raw[start + following * stride + 16]:
                        raise SaveError('ROTK II linked provinces have conflicting owners.')
                current = following
    return True


def decode(raw, game_id=GAME_ID, source=Path('copy.sav')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SIZE:
        raise SaveError('ROTK II requires an exact-size native raw save.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('ROTK II opened snapshot was changed outside the staged workflow.')
    _validate_raw(document.raw)


def _copy_path(path):
    resolved = safe_path(path)
    for folder in (resolved.parent, *resolved.parents):
        native_exe = any((folder / name).is_file() for name in ('MAIN.EXE', 'main.exe'))
        native_scenario = any((folder / name).is_file() for name in ('SCENARIO.DAT', 'scenario.dat'))
        if native_exe and native_scenario:
            raise SaveError('Use a separate save copy outside the live DOS game folder.')
    return resolved


def _suffix(path):
    suffix = path.suffix.casefold()
    if suffix not in ('', '.sav', '.dat'):
        raise SaveError('Use a native copied save (.sav, .dat or an extensionless DOS filename).')
    return suffix


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    _suffix(path)
    with path.open('rb') as stream:
        raw = stream.read(SIZE + 1)
    return decode(raw, game_id, path)


@lru_cache(maxsize=4)
def _fields(raw):
    result = {}
    for index in range(PROVINCE_COUNT):
        base = PROVINCE_START + PROVINCE_STRIDE * index
        owner = raw[base + 16]
        if owner == 255:
            continue  # Unclaimed provinces are inspection only; ownership is not created.
        group = f'Province record {index + 1} · owner ID {owner}'
        for key, label, relative, size in (('gold', 'Gold (reduce only)', 8, 2),
                                           ('rice', 'Rice (reduce only)', 10, 4)):
            value = int.from_bytes(raw[base + relative:base + relative + size], 'little')
            field = Field(f'province_{index}_{key}', label, base + relative, value,
                          group, index + 1, size)
            result[field.id] = field
    return MappingProxyType(result)


def field_map(document):
    validate_document(document)
    return _fields(document.payload)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document, changes):
    fields = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('ROTK II edits require a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown ROTK II field or unclaimed province.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown ROTK II field or unclaimed province.')
    field = field_map(document)[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    return result


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    # Published native writer is a complete raw write; no encryption/checksum layer.
    if decode(payload, GAME_ID).payload != payload:
        raise SaveError('ROTK II edited copy failed structural read-back.')
    return payload


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in field_map(document):
            raise SaveError('Unknown ROTK II field.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)  # Published cheat targets are not natural gameplay maxima.


def _validate_source(document):
    source = _copy_path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SIZE + 1)
    except OSError as error:
        raise SaveError('The opened ROTK II copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('The opened ROTK II copy changed on disk; reopen it.')
    return source


def backup(document):
    validate_document(document)
    source = _validate_source(document)
    return snapshot_backup(document.raw, source, GAME_ID,
                           _copy_path(source.parent / 'WarriorsEditorBackups'))


def save_as(document, changes, destination):
    validate_document(document)
    destination = _copy_path(destination)
    _suffix(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    _validate_source(document)
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = _copy_path(backup_path), _copy_path(destination)
    suffix = _suffix(backup_path)
    if _suffix(destination) != suffix:
        raise SaveError('Restore to a new destination with the same filename extension as the backup.')
    return restore_snapshot(backup_path, destination, GAME_ID, suffix, SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def province_records(document):
    validate_document(document)
    result = []
    for index in range(PROVINCE_COUNT):
        base = PROVINCE_START + PROVINCE_STRIDE * index
        result.append((index + 1, document.payload[base + 16], _u16(document.payload, base + 8),
                       int.from_bytes(document.payload[base + 10:base + 14], 'little'),
                       _u16(document.payload, base + 14) * 100,
                       document.payload[base + 32], document.payload[base + 33]))
    return tuple(result)


def record_label(slot, group):
    return group


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown ROTK II field.')
    return ('Reduce the opened province balance only. Max is disabled. Ownership, governor, '
            'officers, population, calendar, troop state and all unknown bytes are preserved.')

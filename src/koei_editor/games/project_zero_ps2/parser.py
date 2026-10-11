"""Independent European Project Zero writer; preserve complete PSU exports.

Field/byte-sum facts: karas84/ProjectZeroSaveEditor and Himuro's native structs.
No external code, game assets or save contents are included. See format notes.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'project_zero_ps2'
EXTENSION = '.psu'
INTEGRITY_KIND = 'checksum'
PRODUCT = 'BESLES-50821zero'
SIZE = 585596
MAX_FILE_SIZE = 8 * 1024 * 1024
CAMERA = 0x42E0
ITEMS = 0x197C
EMPTY = bytes(48) + b'\xff' * (SIZE - 48)


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Project Zero / Fatal Frame (European PS2)'
    size: int = MAX_FILE_SIZE
    fields: tuple = ()
    note: str = ('European SLES-50821 PSU exports. Existing camera points and '
                 'base-upgrade tier reductions; all other records and metadata preserved.')
    sample_verified: bool = True
    published_format: bool = True
    game_load_verified: bool = False


FORMAT = Format()


@dataclass(frozen=True)
class Entry:
    name: str
    offset: int
    size: int
    slot: int = -1
    occupied: bool = False


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    entries: tuple

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str
    slot: int
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from 0 to '
                            f'the opened value ({self.maximum:,}).')


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the original European Project Zero PS2 profile.')
    return FORMAT


def _name(raw, offset):
    stored = raw[offset + 64:offset + 96]
    if b'\0' not in stored:
        raise SaveError('PSU entry name is not terminated.')
    try:
        result = stored.split(b'\0', 1)[0].decode('ascii')
    except UnicodeDecodeError as error:
        raise SaveError('PSU entry name is not supported ASCII.') from error
    if not result or any(c in result for c in '/\\:') or any(ord(c) < 32 for c in result):
        raise SaveError('Invalid PSU entry name.')
    return result


@lru_cache(maxsize=4)
def _entries(raw):
    if not 1536 <= len(raw) <= MAX_FILE_SIZE:
        raise SaveError('Open a bounded complete European PSU save export.')
    mode = int.from_bytes(raw[:2], 'little')
    root = _name(raw, 0)
    if mode & 0x30 != 0x20 or root != PRODUCT + '0':
        raise SaveError('PSU directory must identify European BESLES-50821zero0.')
    count = int.from_bytes(raw[4:8], 'little')
    if not 3 <= count <= min(128, (len(raw) - 512) // 512):
        raise SaveError('Invalid PSU entry count.')
    pos, seen, entries = 512, set(), []
    for index in range(count):
        if pos + 512 > len(raw):
            raise SaveError('Truncated PSU entry.')
        name = _name(raw, pos)
        mode = int.from_bytes(raw[pos:pos + 2], 'little') & 0x30
        size = int.from_bytes(raw[pos + 4:pos + 8], 'little')
        if name in seen or mode not in (0x10, 0x20):
            raise SaveError('Duplicate PSU name or invalid entry mode.')
        seen.add(name)
        pos += 512
        if index < 2:
            if mode != 0x20 or name != ('.', '..')[index]:
                raise SaveError('PSU special directory entries are missing.')
            continue
        if mode != 0x10 or name in ('.', '..'):
            raise SaveError('Nested PSU directories are unsupported.')
        padded = (size + 1023) // 1024 * 1024
        if size > MAX_FILE_SIZE or pos + padded > len(raw):
            raise SaveError('Truncated PSU file or padding.')
        slot, occupied = -1, False
        if name.startswith(PRODUCT):
            if name not in tuple(PRODUCT + str(i) for i in range(3)) or size != SIZE:
                raise SaveError('Unexpected Project Zero slot identity or length.')
            slot = int(name[-1])
            body = raw[pos:pos + size]
            if body != EMPTY:
                if int.from_bytes(body[:4], 'little') != sum(body[16:]):
                    raise SaveError(f'Project Zero slot {slot + 1} checksum failed.')
                if int.from_bytes(body[16:20], 'little') != 1:
                    raise SaveError('Unsupported Project Zero gameplay-header kind.')
                if int.from_bytes(body[20:24], 'little') not in range(6):
                    raise SaveError('Unsupported Project Zero mission-header framing.')
                for relative in (32, 36, 40):
                    if int.from_bytes(body[relative:relative + 4], 'little') > 59:
                        raise SaveError('Invalid Project Zero time-header framing.')
                occupied = True
        entries.append(Entry(name, pos, size, slot, occupied))
        pos += padded
    if pos != len(raw) or not any(e.occupied for e in entries):
        raise SaveError('PSU has trailing bytes or no valid occupied Project Zero slot.')
    return tuple(entries)


def decode(raw, game_id=GAME_ID, source=Path('copy.psu')):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError('Project Zero requires an immutable exported byte snapshot.')
    return Document(FORMAT, Path(source), raw, raw, _entries(raw))


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload or document.entries != _entries(document.raw)):
        raise SaveError('Opened Project Zero snapshot was changed outside staged editing.')


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    _suffix(path)
    with path.open('rb') as stream:
        return decode(stream.read(MAX_FILE_SIZE + 1), game_id, path)


def _suffix(path):
    if path.suffix.casefold() != EXTENSION:
        raise SaveError('Use a separate .psu memory-card export; PSV signing stays external.')


@lru_cache(maxsize=4)
def _fields(raw):
    result = {}
    for entry in _entries(raw):
        if not entry.occupied:
            continue
        for key, label, relative, size in (
                ('points', 'Available camera points (reduce only)', 16, 8),
                ('range', 'Range upgrade tier (reduce only)', 0, 1),
                ('power', 'Maximum charge upgrade tier (reduce only)', 1, 1),
                ('speed', 'Charge speed upgrade tier (reduce only)', 2, 1)):
            offset = entry.offset + CAMERA + relative
            value = int.from_bytes(raw[offset:offset + size], 'little')
            if key != 'points' and not 1 <= value <= 3:
                continue  # Initial or unusual tiers remain read-only, never normalized.
            if key == 'points' and value == 0:
                continue
            field = Field(f'slot_{entry.slot}_{key}', label, offset, size, value,
                          f'Save slot {entry.slot + 1} · Camera', entry.slot + 1)
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
        raise SaveError('Project Zero edits require a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown Project Zero field or unavailable slot.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    for entry in document.entries:
        if entry.occupied and output[entry.offset:entry.offset + SIZE] != document.raw[entry.offset:entry.offset + SIZE]:
            checksum = sum(output[entry.offset + 16:entry.offset + SIZE])
            output[entry.offset:entry.offset + 4] = checksum.to_bytes(4, 'little')
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('Unknown Project Zero field.')
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def serialize(document, changes):
    output = changed_payload(document, changes)
    if output == document.raw:
        return document.raw
    if decode(output).payload != output:
        raise SaveError('Edited Project Zero copy failed read-back.')
    return output


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in field_map(document):
            raise SaveError('Unknown Project Zero field.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def _source(document):
    validate_document(document)
    source = safe_path(document.source)
    _suffix(source)
    try:
        with source.open('rb') as stream:
            current = stream.read(MAX_FILE_SIZE + 1)
    except OSError as error:
        raise SaveError('Opened Project Zero copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('Opened Project Zero copy changed on disk; reopen it.')
    return source


def backup(document):
    source = _source(document)
    return snapshot_backup(document.raw, source, GAME_ID,
                           safe_path(source.parent / 'UniversalEditorBackups'))


def save_as(document, changes, destination):
    _source(document)
    destination = safe_path(destination)
    _suffix(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing copies are preserved.')
    output = serialize(document, changes)
    backup(document)
    _source(document)
    atomic_new(output, destination)
    return decode(output, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = safe_path(backup_path), safe_path(destination)
    _suffix(backup_path)
    _suffix(destination)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, MAX_FILE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def slot_records(document):
    validate_document(document)
    rows = []
    for entry in document.entries:
        if entry.slot < 0:
            continue
        b = document.payload[entry.offset:entry.offset + entry.size]
        if not entry.occupied:
            rows.append((entry.slot + 1, 'Empty', '', '', '', '', ''))
        else:
            rows.append((entry.slot + 1, 'Occupied', int.from_bytes(b[20:24], 'little'),
                         int.from_bytes(b[24:28], 'little'),
                         f'{int.from_bytes(b[28:32], "little")}:{int.from_bytes(b[32:36], "little"):02}:{int.from_bytes(b[36:40], "little"):02}',
                         int.from_bytes(b[0x4C:0x50], 'little'),
                         int.from_bytes(b[CAMERA + 16:CAMERA + 24], 'little')))
    return tuple(rows)


def item_records(document):
    validate_document(document)
    return tuple((entry.slot + 1, index + 1, document.payload[entry.offset + ITEMS + index])
                 for entry in document.entries if entry.occupied for index in range(200))


def camera_records(document):
    validate_document(document)
    labels = ('Range tier', 'Maximum charge tier', 'Charge speed tier',
              'Sub-function 1', 'Sub-function 2', 'Sub-function 3', 'Sub-function 4', 'Sub-function 5',
              'Special-function 1', 'Special-function 2', 'Special-function 3', 'Special-function 4', 'Special-function 5',
              'Equipped sub-function', 'Equipped special-function')
    return tuple((entry.slot + 1, label, document.payload[entry.offset + CAMERA + index])
                 for entry in document.entries if entry.occupied for index, label in enumerate(labels))


def record_label(slot, group):
    return group


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Project Zero field.')
    return ('Reduce an existing camera value only. Max is disabled. Special abilities, equipped '
            'functions, films/items, story, photos and reward records are preserved.')

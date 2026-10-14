"""Original TC DOS native fields, independently implemented from published facts.

Only the acquired 662,640-byte initialized native profile is recognized. The
complete external writer directly replaces records without a checksum layer.
Occupied-player qualification is pending; see docs/ROTK3_DOS_FORMAT.md.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'rotk3_dos'
SIZE = MAX_FILE_SIZE = 662640
INTEGRITY_KIND = 'none'
SIGNATURE = b'1992.01.08'
SLOT_COUNT, INDEX_START, INDEX_STRIDE, SLOT_STRIDE = 10, 10, 14, 0xCE01
CITY_START, CITY_STRIDE, CITY_COUNT = 0x1B8, 74, 45
OFFICER_START, OFFICER_STRIDE, OFFICER_COUNT = 0x544E, 49, 600


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Romance of the Three Kingdoms III (Traditional Chinese DOS)'
    note: str = ('Exact initialized TC native profile; existing occupied-slot cities '
                 'and officer abilities. Names use native glyph IDs; no campaign creation.')
    size: int = SIZE
    fields: tuple = ()
    sample_verified: bool = False
    editing_verified: bool = False
    game_load_verified: bool = False
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

    @property
    def experimental_maximum(self):
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum} to {self.maximum}.')


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
        raise SaveError('Select original Traditional Chinese DOS Romance of the Three Kingdoms III.')
    return FORMAT


def _u16(raw, offset):
    return int.from_bytes(raw[offset:offset + 2], 'little')


def _link(raw, offset):
    value = int.from_bytes(raw[offset:offset + 2], 'little', signed=True)
    if value >= OFFICER_COUNT:
        raise SaveError('ROTK III officer reference exceeds the native array.')
    return value if value >= 0 else None


def _occupied(raw):
    return tuple(index for index in range(SLOT_COUNT)
                 if raw[INDEX_START + INDEX_STRIDE * index + 5] != 0)


@lru_cache(maxsize=4)
def _validate_raw(raw):
    if len(raw) != SIZE or raw[:10] != SIGNATURE:
        raise SaveError('Not the exact 662,640-byte original Traditional Chinese DOS ROTK III profile.')
    for slot in range(SLOT_COUNT):
        directory = INDEX_START + INDEX_STRIDE * slot
        scenario = raw[directory + 5]
        if not scenario:
            # Empty native body allocations contain irrelevant initialization data.
            if (_u16(raw, directory) != 0 or raw[directory + 2] != 0
                    or raw[directory + 4] != 255 or raw[directory + 6] != 255):
                raise SaveError('Unsupported ROTK III empty-slot directory framing.')
            continue
        if (not 1 <= scenario <= 6 or not 1 <= _u16(raw, directory) <= 999
                or not 1 <= raw[directory + 2] <= 12
                or raw[directory + 4] >= CITY_COUNT or raw[directory + 6] not in (0, 1)):
            raise SaveError('Invalid ROTK III occupied-slot calendar/scenario directory.')
        start = slot * SLOT_STRIDE
        names = set()
        for city in range(CITY_COUNT):
            base = start + CITY_START + city * CITY_STRIDE
            for relative in (8, 10, 12, 14):
                _link(raw, base + relative)
            name = raw[base + 65:base + 69]
            if name == b'\0' * 4 or name in names:
                raise SaveError('ROTK III occupied city table has missing or duplicated native names.')
            names.add(name)
        links = {}
        for officer in range(OFFICER_COUNT):
            base = start + OFFICER_START + officer * OFFICER_STRIDE
            if raw[base + 18] > 0 and raw[base + 19] > 0:
                links[officer] = _link(raw, base + 3)
        if not links:
            raise SaveError('ROTK III occupied slot has no existing officer records.')
        for officer in links:
            current, seen = officer, set()
            while current in links:
                if current in seen:
                    raise SaveError('ROTK III officer chain contains a cycle.')
                seen.add(current)
                current = links[current]
    return True


def decode(raw, game_id=GAME_ID, source=Path('copy.sav')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SIZE:
        raise SaveError('ROTK III requires a complete exact-size native TC save copy.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path)
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('ROTK III immutable opened snapshot was changed outside staging.')
    _validate_raw(document.raw)


def _copy_path(path):
    path = safe_path(path)
    for folder in (path.parent, *path.parents):
        if (any((folder / name).is_file() for name in ('MAIN.EXE', 'main.exe'))
                and any((folder / name).is_file() for name in ('KOEI.COM', 'koei.com'))):
            raise SaveError('Open a separate copied save outside the live DOS game folder.')
    return path


def _suffix(path):
    if path.suffix.casefold() != '.sav':
        raise SaveError('Use a copied native SANGOKU3.SAV file with a .sav extension.')


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
    for slot in _occupied(raw):
        start = slot * SLOT_STRIDE
        for officer in range(OFFICER_COUNT):
            base = start + OFFICER_START + officer * OFFICER_STRIDE
            if not (raw[base + 18] > 0 and raw[base + 19] > 0):
                continue
            group = f'Save slot {slot + 1:02d} · Officer record {officer + 1:03d}'
            for relative, key, label in ((16, 'land', 'Land command'), (17, 'water', 'Naval command'),
                                          (18, 'war', 'War'), (19, 'intelligence', 'Intelligence'),
                                          (20, 'politics', 'Politics'), (21, 'charisma', 'Charisma')):
                if raw[base + relative] > 0:
                    field = Field(f's{slot}_o{officer}_{key}', label, base + relative,
                                  100, group, slot + 1, 1, minimum=1)
                    result[field.id] = field
        for city in range(CITY_COUNT):
            base = start + CITY_START + city * CITY_STRIDE
            mayor = _link(raw, base + 8)
            if mayor is None:
                continue
            officer = start + OFFICER_START + mayor * OFFICER_STRIDE
            if not (raw[officer + 18] > 0 and raw[officer + 19] > 0
                    and raw[officer + 26] < 21):
                continue
            group = f'Save slot {slot + 1:02d} · City record {city + 1:02d}'
            for relative, size, key, label in (
                    (26, 2, 'gold', 'Gold (reduce only)'), (28, 4, 'rice', 'Rice (reduce only)'),
                    (46, 2, 'commerce', 'Commerce (reduce only)'),
                    (50, 2, 'crossbows', 'Crossbows (reduce only)'),
                    (52, 2, 'heavy_crossbows', 'Heavy crossbows (reduce only)'),
                    (54, 2, 'horses', 'War horses (reduce only)'),
                    (57, 1, 'warships', 'Warships (reduce only)'),
                    (58, 1, 'heavy_ships', 'Heavy ships (reduce only)'),
                    (59, 1, 'light_ships', 'Light ships (reduce only)')):
                value = int.from_bytes(raw[base + relative:base + relative + size], 'little')
                field = Field(f's{slot}_c{city}_{key}', label, base + relative,
                              value, group, slot + 1, size)
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
        raise SaveError('ROTK III edits require a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown ROTK III field or unsupported/unoccupied record.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown ROTK III field or unsupported/unoccupied record.')
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
    decode(payload)
    return payload


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in field_map(document):
            raise SaveError('Unknown ROTK III field.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def _validate_source(document):
    source = _copy_path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SIZE + 1)
    except OSError as error:
        raise SaveError('The opened ROTK III copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('The opened ROTK III copy changed on disk; reopen it.')
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
    _suffix(backup_path)
    _suffix(destination)
    return restore_snapshot(backup_path, destination, GAME_ID, '.sav', SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def slot_records(document):
    validate_document(document)
    rows = []
    for slot in range(SLOT_COUNT):
        base = INDEX_START + INDEX_STRIDE * slot
        occupied = bool(document.raw[base + 5])
        rows.append((slot + 1, 'Occupied' if occupied else 'Empty',
                     _u16(document.raw, base), document.raw[base + 2],
                     document.raw[base + 5], document.raw[base + 4],
                     document.raw[base + 7:base + 13].hex().upper()))
    return tuple(rows)


def city_records(document):
    validate_document(document)
    rows = []
    for slot in _occupied(document.raw):
        for city in range(CITY_COUNT):
            base = slot * SLOT_STRIDE + CITY_START + city * CITY_STRIDE
            rows.append((slot + 1, city + 1, document.raw[base + 65:base + 69].hex().upper(),
                         _link(document.raw, base + 8), _u16(document.raw, base + 26),
                         int.from_bytes(document.raw[base + 28:base + 32], 'little'),
                         *document.raw[base + 42:base + 46], document.raw[base + 49]))
    return tuple(rows)


def officer_records(document):
    validate_document(document)
    rows = []
    for slot in _occupied(document.raw):
        for officer in range(OFFICER_COUNT):
            base = slot * SLOT_STRIDE + OFFICER_START + officer * OFFICER_STRIDE
            if not (1 <= document.raw[base + 18] <= 127 and 1 <= document.raw[base + 19] <= 127):
                continue
            rows.append((slot + 1, officer + 1, document.raw[base + 42:base + 48].hex().upper(),
                         *document.raw[base + 16:base + 22], _u16(document.raw, base + 5),
                         document.raw[base + 25], document.raw[base + 26],
                         document.raw[base + 31], document.raw[base + 32]))
    return tuple(rows)


def record_label(slot, group):
    return group


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown ROTK III field.')
    return ('Officer abilities accept the published editor range 1–100; city resources '
            'can only be reduced from their opened balance. Max is disabled. '
            'Slot indices, officer/city links, ownership, orders, treasure, dates, '
            'unknown bytes and the complete native tail remain intact.')

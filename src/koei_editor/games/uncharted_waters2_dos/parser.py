"""Original English DOS KOUKAI2.DAT raw writer, independently implemented.

Complete writer and source-correlated mechanics: JohanLi/uncharted-waters-2-research.
See docs/UNCHARTED_WATERS2_DOS_FORMAT.md. No external code/assets/catalog copied.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
import hashlib
import re
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'uncharted_waters2_dos'
HEADER_SIZE, SLOT_SIZE, SLOT_COUNT = 151, 31944, 10
SIZE = MAX_FILE_SIZE = HEADER_SIZE + SLOT_SIZE * SLOT_COUNT
INTEGRITY_KIND = 'none'
SAILOR_START, SAILOR_SIZE, SAILOR_COUNT = 0x612, 42, 120
PORT_START, PORT_SIZE, PORT_COUNT = 0x4f40, 20, 130
ATTRIBUTES = ('Leadership', 'Seamanship', 'Knowledge', 'Intuition', 'Courage',
              'Swordsmanship', 'Charm', 'Luck')
GOLD_MAX = 600_000_000
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Uncharted Waters: New Horizons (English DOS)'
    note: str = ('Existing save-slot gold and protagonist attributes. Story, date, fame, '
                 'rank, equipment, ships, levels and experience remain intact.')
    size: int = SIZE
    fields: tuple = ()
    published_format: bool = True
    sample_verified: bool = False
    editing_verified: bool = False
    game_load_verified: bool = False


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
    maxable: bool = True
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
            raise SaveError(f'{self.label} requires a whole number from 0 to the validated maximum ({self.maximum}).')


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
        raise SaveError('Select the original English DOS Uncharted Waters: New Horizons profile.')
    return FORMAT


def _u16(raw, offset):
    return int.from_bytes(raw[offset:offset + 2], 'little')


def _cstring(raw):
    return raw.split(b'\0', 1)[0].decode('ascii', errors='strict')


def _sailor_name(raw, slot, sailor):
    base = HEADER_SIZE + slot * SLOT_SIZE + SAILOR_START + sailor * SAILOR_SIZE
    try:
        return (_cstring(raw[base:base + 9]) + ' ' + _cstring(raw[base + 9:base + 18])).strip()
    except UnicodeError as error:
        raise SaveError('Not the English DOS sailor-name layout.') from error


def _occupied(raw, slot):
    start = 1 + slot * 15
    return bool(raw[start:start + 12].strip(b'\0'))


@lru_cache(maxsize=4)
def _validate_raw(raw):
    if len(raw) != SIZE:
        raise SaveError('Not the exact 319,591-byte English DOS KOUKAI2.DAT revision.')
    for slot in range(SLOT_COUNT):
        base = HEADER_SIZE + slot * SLOT_SIZE
        # Independent title/locale evidence from original native records. These
        # names are framing anchors, not an imported character/port catalog.
        if _sailor_name(raw, slot, 0) != 'Joao Franco':
            raise SaveError('Unsupported DOS title/locale sailor framing.')
        port = base + PORT_START
        if raw[port + 4:port + 11] != b'Lisbon\0':
            raise SaveError('Unsupported DOS title/locale port framing.')
        for sailor in range(6):
            record = base + SAILOR_START + sailor * SAILOR_SIZE
            if _u16(raw, record + 18) != sailor:
                raise SaveError('Invalid protagonist record identity.')
        if not _occupied(raw, slot):
            continue
        header = 1 + slot * 15
        label = raw[header:header + 12].split(b'\0', 1)[0]
        if not re.fullmatch(rb'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/[ 0-9][0-9]/[0-9]{4}', label):
            raise SaveError('Invalid occupied English DOS slot label.')
        month_text, day_text, year_text = label.decode('ascii').split('/')
        year = int(year_text)
        try:
            if not 1501 <= year <= 1756:
                raise ValueError('Unsupported year')
            date(year, MONTHS.index(month_text) + 1, int(day_text))
        except ValueError as error:
            raise SaveError('Invalid occupied directory calendar date.') from error
        if raw[header + 13] >= 6:
            raise SaveError('Invalid occupied slot protagonist ID.')
        if raw[base + 7] >= 12 or raw[base + 8] >= 31 or raw[base + 9] >= 72:
            raise SaveError('Invalid occupied slot calendar framing.')
        try:
            date(1501 + raw[base + 6], 1 + raw[base + 7], 1 + raw[base + 8])
        except ValueError as error:
            raise SaveError('Invalid occupied slot calendar date.') from error
        if raw[base + 10] >= PORT_COUNT and raw[base + 10] != 255:
            raise SaveError('Invalid occupied slot port identity.')
    return True


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SIZE:
        raise SaveError('Uncharted Waters II requires an exact-size native raw save.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('Uncharted Waters II opened snapshot was changed outside the staged workflow.')
    _validate_raw(document.raw)


def _copy_path(path):
    resolved = safe_path(path)
    for folder in (resolved.parent, *resolved.parents):
        native_exe = any((folder / name).is_file() for name in ('MAIN.EXE', 'main.exe'))
        native_scenario = any((folder / name).is_file() for name in ('MENU.DAT', 'menu.dat'))
        if native_exe and native_scenario:
            raise SaveError('Use a separate save copy outside the live DOS game folder.')
    return resolved


def _suffix(path):
    suffix = path.suffix.casefold()
    if suffix != '.dat':
        raise SaveError('Use a separate .dat save copy.')
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
    for slot in range(SLOT_COUNT):
        if not _occupied(raw, slot):
            continue
        base = HEADER_SIZE + slot * SLOT_SIZE
        sailor = raw[1 + slot * 15 + 13]
        group = f'Save slot {slot + 1} · {_sailor_name(raw, slot, sailor)}'
        field = Field(f'slot_{slot}_gold', 'Carried gold (coins)', base + 0x60a,
                      GOLD_MAX, group, slot + 1, 4)
        result[field.id] = field
        record = base + SAILOR_START + sailor * SAILOR_SIZE
        for index, label in enumerate(ATTRIBUTES):
            field = Field(f'slot_{slot}_attribute_{index}', label, record + 20 + index,
                          100, group, slot + 1, 1)
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
        raise SaveError('Uncharted Waters II edits require a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown Uncharted Waters II field or unoccupied slot.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Uncharted Waters II field or unoccupied slot.')
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
        raise SaveError('Uncharted Waters II edited copy failed structural read-back.')
    return payload


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    fields = field_map(document)
    result = {}
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown Uncharted Waters II field.')
        field = fields[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and current < field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    result = dict(changes)
    fields = [field for field in fields_for(document) if group is None or field.group == group]
    for key, value in limit_values(document, changes, [field.id for field in fields]).items():
        result = stage(document, result, key, value)
    return result


def _validate_source(document):
    source = _copy_path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SIZE + 1)
    except OSError as error:
        raise SaveError('The opened Uncharted Waters II copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('The opened Uncharted Waters II copy changed on disk; reopen it.')
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


def slot_records(document):
    validate_document(document)
    rows = []
    for slot in range(SLOT_COUNT):
        if not _occupied(document.raw, slot):
            rows.append((slot + 1, 'Empty', '', '', '', '', ''))
            continue
        raw = document.payload
        base = HEADER_SIZE + slot * SLOT_SIZE
        sailor = raw[1 + slot * 15 + 13]
        record = base + SAILOR_START + sailor * SAILOR_SIZE
        fame = base + 0x5b6 + sailor * 14
        rows.append((slot + 1, _sailor_name(raw, slot, sailor),
                     _cstring(raw[1 + slot * 15:13 + slot * 15]),
                     int.from_bytes(raw[base + 0x60a:base + 0x60e], 'little'),
                     raw[record + 28], raw[record + 29],
                     f'{_u16(raw, fame)}/{_u16(raw, fame + 2)}/{_u16(raw, fame + 4)}'))
    return tuple(rows)


def sailor_records(document):
    validate_document(document)
    rows = []
    for slot in range(SLOT_COUNT):
        if not _occupied(document.raw, slot):
            continue
        for sailor in range(6):
            base = HEADER_SIZE + slot * SLOT_SIZE + SAILOR_START + sailor * SAILOR_SIZE
            raw = document.payload
            rows.append((slot + 1, sailor, _sailor_name(raw, slot, sailor),
                         *raw[base + 20:base + 28], raw[base + 28], raw[base + 29],
                         _u16(raw, base + 30), _u16(raw, base + 32)))
    return tuple(rows)


def record_label(slot, group):
    return group


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Uncharted Waters II field.')
    return ('Gold uses coins: 10,000 coins equal one gold ingot. Attributes cap at 100. '
            'Max preserves higher existing values. Levels, experience, rewards, ships, '
            'equipment, fame, date, rank and story progress remain intact.')

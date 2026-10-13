"""Surgical original English Macintosh save-data-fork writer.

Factual geometry: danhealy/bandit_kings_modding c0edaed0350e4b62139120bf0bfd0d309af46a05.
No external implementation, name catalogue or game assets are reused.
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

GAME_ID = 'bandit_kings_mac'
SIZE = MAX_FILE_SIZE = 21122
INTEGRITY_KIND = 'none'
HERO_START, HERO_STRIDE, HERO_COUNT = 4, 24, 255
SETUP_START = 0x17EC
PREFECTURE_START, PREFECTURE_STRIDE, PREFECTURE_COUNT = 0x1934, 32, 49
TACTICAL_START, TACTICAL_STRIDE = 0x1F54, 28
NAMES_START, NAMES_STRIDE = 0x24B0, 46


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Bandit Kings of Ancient China (English Macintosh)'
    note: str = ('Exact native SUI0/SUI1 data fork; existing owned-prefecture '
                 'resources and active hero abilities can be reduced. '
                 'Classic Mac file type/creator metadata is external.')
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
    maxable: bool = False
    kind: str = 'int'
    byteorder: str = 'big'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], self.byteorder)

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from {self.minimum} to the opened value ({self.maximum}).')


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
        raise SaveError('Select original English Macintosh Bandit Kings of Ancient China.')
    return FORMAT


def _u16(raw, offset):
    return int.from_bytes(raw[offset:offset + 2], 'big')


def _name(raw, offset, width):
    name = raw[offset:offset + width].split(b'\0', 1)[0]
    if not name or any(value < 32 or value > 126 for value in name):
        raise SaveError('Missing or foreign-locale native Bandit Kings record name.')
    return name.decode('ascii')


@lru_cache(maxsize=4)
def _validate_raw(raw):
    if len(raw) != SIZE or raw[:4] not in (b'SUI0', b'SUI1'):
        raise SaveError('Not an exact 21,122-byte original Macintosh SUI0/SUI1 data fork.')
    if (_name(raw, NAMES_START, 16) != 'Gao Qiu'
            or _name(raw, TACTICAL_START, 10) != 'Lan'):
        raise SaveError('The save does not match the original English Macintosh profile.')
    if not 1100 <= _u16(raw, SETUP_START) <= 65535 or not 1 <= raw[SETUP_START + 2] <= 12:
        raise SaveError('Invalid Bandit Kings native calendar framing.')
    for index in range(HERO_COUNT):
        base = HERO_START + index * HERO_STRIDE
        if raw[base + 23] & 0x80:
            if raw[base + 6] >= PREFECTURE_COUNT:
                raise SaveError('An active Bandit Kings hero references a foreign prefecture.')
            _name(raw, NAMES_START + index * NAMES_STRIDE, 16)
    names = set()
    for index in range(PREFECTURE_COUNT):
        base = PREFECTURE_START + index * PREFECTURE_STRIDE
        name = _name(raw, TACTICAL_START + index * TACTICAL_STRIDE, 10)
        if name in names:
            raise SaveError('Duplicated Bandit Kings prefecture record identity.')
        names.add(name)
        owner = raw[base + 31]
        if owner:
            hero = HERO_START + (owner - 1) * HERO_STRIDE
            if not raw[hero + 23] & 0x80 or raw[hero + 5] != owner - 1 or raw[hero + 6] != index:
                raise SaveError('Bandit Kings ruler/hero/prefecture links disagree.')
    return True


def decode(raw, game_id=GAME_ID, source=Path('copy.cim')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SIZE:
        raise SaveError('Bandit Kings requires a complete exact-size copied data fork.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path)
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('Bandit Kings immutable snapshot was changed outside staging.')
    _validate_raw(document.raw)


def _copy_path(path):
    lexical = Path(path).absolute()
    if any(part.is_symlink() for part in (lexical, *lexical.parents)):
        raise SaveError('Use an ordinary separate Bandit Kings copy, without symbolic-link aliases.')
    if lexical.is_file() and lexical.stat().st_nlink != 1:
        raise SaveError('Use an ordinary separate Bandit Kings copy, without hard-link aliases.')
    resolved = safe_path(path)
    for folder in (resolved.parent, *resolved.parents):
        if any((folder / name).is_file() for name in ('SUIDATA1.CIM', 'SUIDATA2.CIM', 'suidata1.cim', 'suidata2.cim')):
            raise SaveError('Open a separate data-fork copy outside the live classic Macintosh game Data folder.')
    return resolved


def _suffix(path):
    if path.suffix.casefold() != '.cim':
        raise SaveError('Use a .cim copy of the original native Macintosh save data fork.')
    return '.cim'


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
    for index in range(HERO_COUNT):
        base = HERO_START + index * HERO_STRIDE
        if not raw[base + 23] & 0x80:
            continue
        name = _name(raw, NAMES_START + index * NAMES_STRIDE, 16)
        group = f'Hero {index:03d} · {name}'
        for relative, key, label in ((12, 'strength', 'Strength'), (13, 'dexterity', 'Dexterity'), (14, 'wisdom', 'Wisdom')):
            # Reduction scope avoids claiming a cheat target as a natural cap.
            field = Field(f'hero_{index}_{key}', f'{label} (reduce only)', base + relative,
                          raw[base + relative], group, index + 1, 1)
            result[field.id] = field
    for index in range(PREFECTURE_COUNT):
        base = PREFECTURE_START + index * PREFECTURE_STRIDE
        if not raw[base + 31]:
            continue
        name = _name(raw, TACTICAL_START + index * TACTICAL_STRIDE, 10)
        group = f'Prefecture {index + 1:02d} · {name}'
        for relative, key, label in ((12, 'gold', 'Gold'), (14, 'food', 'Food'), (16, 'metal', 'Metal'), (18, 'fur', 'Fur')):
            field = Field(f'prefecture_{index}_{key}', f'{label} (reduce only)', base + relative,
                          _u16(raw, base + relative), group, index + 1, 2)
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
        raise SaveError('Bandit Kings edits require a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown Bandit Kings field or unsupported existing record.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, field.byteorder)
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Bandit Kings field or unsupported existing record.')
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
        raise SaveError('Bandit Kings edited copy failed structural read-back.')
    return payload


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in field_map(document):
            raise SaveError('Unknown Bandit Kings field.')
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
        raise SaveError('The opened Bandit Kings copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('The opened Bandit Kings copy changed on disk; reopen it.')
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
    reopened = read_save(destination, GAME_ID)
    if reopened.raw != raw:
        raise SaveError('The written Bandit Kings copy differs from the validated output.')
    return reopened


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = _copy_path(backup_path), _copy_path(destination)
    suffix = _suffix(backup_path)
    if _suffix(destination) != suffix:
        raise SaveError('Restore to a new destination with the same filename extension as the backup.')
    return restore_snapshot(backup_path, destination, GAME_ID, suffix, SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))




def hero_records(document):
    validate_document(document)
    raw = document.payload
    rows = []
    for index in range(HERO_COUNT):
        base = HERO_START + index * HERO_STRIDE
        if raw[base + 23] & 0x80:
            rows.append((index, _name(raw, NAMES_START + index * NAMES_STRIDE, 16),
                         raw[base + 6] + 1, raw[base + 5], *raw[base + 12:base + 15],
                         raw[base + 7], raw[base + 8], raw[base + 22], raw[base + 23]))
    return tuple(rows)


def prefecture_records(document):
    validate_document(document)
    raw = document.payload
    return tuple((index + 1, _name(raw, TACTICAL_START + index * TACTICAL_STRIDE, 10),
                  raw[PREFECTURE_START + index * PREFECTURE_STRIDE + 31] - 1
                  if raw[PREFECTURE_START + index * PREFECTURE_STRIDE + 31] else 'Unclaimed',
                  *(_u16(raw, PREFECTURE_START + index * PREFECTURE_STRIDE + off) for off in (12, 14, 16, 18)))
                 for index in range(PREFECTURE_COUNT))


def record_label(slot, group):
    return group


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Bandit Kings field.')
    return ('Reduce the opened value only; Max is disabled. Hero ability progress, '
            'body/max-body, loyalty, persona, troop counts, faction membership, '
            'prefecture ownership, dates, names and flags are preserved. '
            'This edits the data fork; classic Macintosh type/creator codes remain external.')

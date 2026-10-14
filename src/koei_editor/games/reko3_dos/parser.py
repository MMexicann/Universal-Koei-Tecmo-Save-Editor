"""Original R3S writer from independently checked native format facts.

The native reference has 384 character records, not the external README's 387.
No source implementation, character catalog or game assets are incorporated.
See docs/REKO3_DOS_FORMAT.md for evidence and the precise supported scope.
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

GAME_ID = 'reko3_dos'
SIZE = MAX_FILE_SIZE = 8789
RECORD_START, RECORD_SIZE, RECORD_COUNT = 0x695, 18, 384
INTEGRITY_KIND = 'none'
# Independently corroborated historical protagonists; not an extracted catalog.
NAMES = {0: 'Liu Bei', 1: 'Guan Yu', 2: 'Zhang Fei'}


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Romance of the Three Kingdoms: Legend of Liu Bei (Chinese DOS)'
    note: str = 'Existing allied troop reductions and within-level EXP; levels, classes, items and story stay intact.'
    size: int = SIZE
    fields: tuple = ()
    published_format: bool = True
    sample_verified: bool = True
    editing_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format()


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    minimum: int
    maximum: int
    group: str
    slot: int
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
        raise SaveError('Select the original Traditional Chinese DOS Legend of Liu Bei profile.')
    return FORMAT


def _chapter(raw):
    name = raw[5:28].split(b'\0', 1)[0]
    try:
        title = name.decode('cp950', errors='strict')
    except UnicodeError as error:
        raise SaveError('Unsupported R3S chapter-name encoding.') from error
    if not title or any(ord(c) < 32 for c in title) or not any('\u4e00' <= c <= '\u9fff' for c in title):
        raise SaveError('Not the qualified Traditional Chinese R3S chapter framing.')
    return title


@lru_cache(maxsize=4)
def _validate_raw(raw):
    if len(raw) != SIZE:
        raise SaveError('Use an original 8,789-byte DOS MSAVE slot, not a console or modified-edition file.')
    _chapter(raw)
    if raw[RECORD_START] != 0x80:
        raise SaveError('Missing original protagonist faction framing.')
    for index in range(RECORD_COUNT):
        base = RECORD_START + index * RECORD_SIZE
        if not 0x80 <= raw[base] <= 0x8e:
            raise SaveError('Unsupported R3S character-array framing.')
    return True


def decode(raw, game_id=GAME_ID, source=Path('copy.r3s')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise SaveError('A native R3S save must contain binary bytes.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or not isinstance(document.source, Path)
            or document.raw != document.payload):
        raise SaveError('The opened Legend of Liu Bei snapshot was changed outside staged editing.')
    _validate_raw(document.raw)


def _copy_path(path):
    path = safe_path(path)
    for folder in (path.parent, *path.parents):
        if any((folder / name).is_file() for name in ('REKO3.EXE', 'reko3.exe')):
            raise SaveError('Open a separate copy outside the live DOS game directory.')
    return path


def _suffix(path):
    if path.suffix.casefold() != '.r3s':
        raise SaveError('Use a separate native .R3S slot copy.')
    return path.suffix.casefold()


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
    for index in range(RECORD_COUNT):
        base = RECORD_START + index * RECORD_SIZE
        # Only occupied, ordinary existing player-army records. Opaque record
        # bytes and unusual classes/levels remain preserved and read only.
        if (raw[base] != 0x80 or raw[base + 4] != 100
                or raw[base + 7] > 18 or not 1 <= raw[base + 8] <= 99):
            continue
        group = NAMES.get(index, f'Allied character #{index}')
        troops = int.from_bytes(raw[base + 5:base + 7], 'little')
        if troops:
            field = Field(f'character_{index}_troops', 'Current troops (reductions)',
                          base + 5, 2, 1, troops, group, index)
            result[field.id] = field
        field = Field(f'character_{index}_exp', 'EXP toward the next level',
                      base + 9, 1, 0, 99, group, index)
        result[field.id] = field
    return MappingProxyType(result)


def field_map(document):
    validate_document(document)
    return _fields(document.raw)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document, changes):
    fields = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('Legend of Liu Bei edits require a field/value mapping.')
    output = bytearray(document.raw)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown or unqualified Legend of Liu Bei field.')
        field = fields[key]
        if type(value) is int and value == field.value(document.raw):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('Unknown or unqualified Legend of Liu Bei field.')
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.raw):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.raw:
        return document.raw
    # The complete published writer writes the native raw file without a
    # cipher/checksum layer. Copy every byte except explicitly staged fields.
    return decode(payload, GAME_ID).raw


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.raw), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    fields = field_map(document)
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('Choose existing allied character fields.')
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
        raise SaveError('The opened R3S copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('The opened R3S copy changed on disk; reopen it.')
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
    return restore_snapshot(backup_path, destination, GAME_ID, '.r3s', SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def character_records(document):
    validate_document(document)
    rows = []
    for index in range(RECORD_COUNT):
        base = RECORD_START + index * RECORD_SIZE
        raw = document.raw
        rows.append((index, NAMES.get(index, f'Character #{index}'),
                     f'0x{raw[base]:02X}', int.from_bytes(raw[base + 5:base + 7], 'little'),
                     raw[base + 7], raw[base + 8], raw[base + 9],
                     ' / '.join('Empty' if v == 255 else f'0x{v:02X}' for v in raw[base + 10:base + 18])))
    return tuple(rows)


def record_label(slot, group):
    return group


def field_hint(document, key):
    if key not in field_map(document):
        raise SaveError('Unknown Legend of Liu Bei field.')
    return ('Troops can be reduced without eliminating the unit. EXP is the existing '
            'within-level byte, 0–99; this does not award levels. Max is unavailable. '
            'Classes, allegiance, level, item ownership and story progress remain intact.')

"""Original NES 17-fief SRAM, independently expressed from complete native writers.

Native source: chrisaacson69/na1-decompiler 52d5532eb0b0ac8312a38088cda4242748924994.
Only original English snapshots retaining the Oda/Tokugawa title anchors qualify.
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

GAME_ID = 'nobunaga_ambition_nes'
SIZE = MAX_FILE_SIZE = 8192
INTEGRITY_KIND = 'checksum'
CHECKSUM_OFFSET = 0x1FEB
SERIALIZED_INTEGRITY_RANGES = ((CHECKSUM_OFFSET, CHECKSUM_OFFSET + 2),)
PROVINCE_START, PROVINCE_STRIDE, PROVINCE_COUNT = 0x1001, 26, 17
OWNER_START, POLICY_START, NAME_START = 0xE15, 0xCF7, 0x17A8


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = "Nobunaga's Ambition (English NES, 17 fiefs)"
    note: str = ('Original 8 KiB native battery SRAM; 17-fief scenario with original '
                 'Oda/Tokugawa name anchors. Existing gold/rice reductions; '
                 'native checksum recomputed only after qualified edits.')
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
    byteorder: str = 'little'

    @property
    def experimental_maximum(self):
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], self.byteorder)

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
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
        raise SaveError("Select original English NES Nobunaga's Ambition, 17-fief scenario.")
    return FORMAT


def _u16(raw, offset):
    return int.from_bytes(raw[offset:offset + 2], 'little')


def checksum(raw):
    # Native syscall copies only the low count byte: 0 means 256.
    # The 0x81EB final count therefore covers exactly [0x1F00, 0x1FEB).
    return (sum(raw[1:0x1000]) + sum(raw[0x1001:CHECKSUM_OFFSET])) & 0xFFFF


def _name(raw, index):
    value = raw[NAME_START + index * 9:NAME_START + (index + 1) * 9].split(b'\0', 1)[0]
    if not value or any(byte < 32 or byte > 126 for byte in value):
        raise SaveError('Missing or incompatible native NES daimyo name.')
    return value.decode('ascii')


@lru_cache(maxsize=4)
def _validate_raw(raw):
    if len(raw) != SIZE or raw[0x1FED:0x1FF2] != b'KOEI\0':
        raise SaveError('Not an original 8 KiB native KOEI NES save bank.')
    if _u16(raw, CHECKSUM_OFFSET) != checksum(raw):
        raise SaveError('Native Nobunaga SRAM checksum mismatch; damaged input is not repaired.')
    if _u16(raw, 0xD9D) != 17:
        raise SaveError('This profile qualifies only the original 17-fief Nobunaga scenario.')
    if (_name(raw, 7) != 'Tokugawa' or _name(raw, 16) != 'Oda'):
        raise SaveError('The native English 17-fief title anchors do not match; successor-name profiles are not qualified.')
    if raw[0xD5F] > 3 or not _u16(raw, 0xD9F):
        raise SaveError('Invalid native Nobunaga year/season framing.')
    for index in range(PROVINCE_COUNT):
        _name(raw, index)
        if raw[POLICY_START + index] == 255:
            continue
        if (raw[POLICY_START + index] > 5
                or raw[OWNER_START + index] not in (*range(PROVINCE_COUNT), 51)):
            raise SaveError('Invalid existing Nobunaga fief policy/daimyo reference.')
    return True


def decode(raw, game_id=GAME_ID, source=Path('copy.sav')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SIZE:
        raise SaveError('Nobunaga requires an exact 8 KiB copied battery save bank.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path)
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('Nobunaga immutable snapshot was changed outside staging.')
    _validate_raw(document.raw)


def _copy_path(path):
    lexical = Path(path).absolute()
    if any(part.is_symlink() for part in (lexical, *lexical.parents)):
        raise SaveError('Use an ordinary separate Nobunaga copy, without symbolic-link aliases.')
    if lexical.is_file() and lexical.stat().st_nlink != 1:
        raise SaveError('Use an ordinary separate Nobunaga copy, without hard-link aliases.')
    path = safe_path(path)
    for folder in (path.parent, *path.parents):
        if any((folder / name).is_file() for name in ("Nobunaga's Ambition (USA).nes", 'nobunaga.nes', 'NOBUNAGA.NES')):
            raise SaveError('Open a separate copied battery save outside the live emulator game folder.')
    return path


def _suffix(path):
    if path.suffix.casefold() != '.sav':
        raise SaveError('Use a .sav copy of the original 8 KiB Nobunaga battery save bank.')
    return '.sav'


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
        if raw[POLICY_START + index] == 255 or raw[OWNER_START + index] == 51:
            continue
        owner = raw[OWNER_START + index]
        group = f'Fief {index + 1:02d} · {_name(raw, owner)}'
        for relative, key, label in ((0, 'gold', 'Gold'), (6, 'rice', 'Rice')):
            offset = PROVINCE_START + index * PROVINCE_STRIDE + relative
            field = Field(f'fief_{index}_{key}', f'{label} (reduce only)', offset,
                          _u16(raw, offset), group, index + 1, 2)
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
        raise SaveError('Nobunaga edits require a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown Nobunaga field or unsupported existing record.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, field.byteorder)
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Nobunaga field or unsupported existing record.')
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
    output = bytearray(payload)
    output[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = checksum(output).to_bytes(2, 'little')
    raw = bytes(output)
    decode(raw, GAME_ID)
    return raw


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in field_map(document):
            raise SaveError('Unknown Nobunaga field.')
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
        raise SaveError('The opened Nobunaga copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('The opened Nobunaga copy changed on disk; reopen it.')
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
        raise SaveError('The written Nobunaga copy differs from the validated output.')
    return reopened


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
    raw = document.payload
    return tuple((index + 1, raw[OWNER_START + index],
                  ('Inactive' if raw[POLICY_START + index] == 255 else 'Native owner 51 (read only)'
                   if raw[OWNER_START + index] == 51 else _name(raw, raw[OWNER_START + index])),
                  _u16(raw, PROVINCE_START + index * PROVINCE_STRIDE),
                  _u16(raw, PROVINCE_START + index * PROVINCE_STRIDE + 6),
                  raw[POLICY_START + index])
                 for index in range(PROVINCE_COUNT))


def record_label(slot, group):
    return group


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Nobunaga field.')
    return ('Reduce only the opened fief balance. Max is disabled. Native debt, '
            'economy high-water history, morale, troops, arms, owner IDs, succession, '
            'policies, tax rates, names and progression remain intact. Only the '
            'two native checksum bytes also change after an edit.')

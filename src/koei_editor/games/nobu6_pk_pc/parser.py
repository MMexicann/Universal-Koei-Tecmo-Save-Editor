"""Source-qualified original Windows PK native raw-save resource editing.

Full external raw writer and packed facts are cited in NOBU6_PK_PC_FORMAT.md.
No external implementation, restricted name catalogue or game asset is reused.
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

GAME_ID = 'nobu6_pk_pc'
SIZE = MAX_FILE_SIZE = 844623
EXTENSION = '.n6p'
MAGIC = b'1995.08.16\0'
INTEGRITY_KIND = 'none'
SLOT_START, SLOT_SIZE, SLOT_COUNT = 0x50F, 105416, 8
GENERAL_START, GENERAL_SIZE, GENERAL_COUNT = 2786, 47, 532
NAME_START, NAME_SIZE = 27790, 18
CASTLE_START, CASTLE_SIZE, CASTLE_COUNT = 37366, 33, 214
DISTRICT_START, DISTRICT_SIZE, DISTRICT_COUNT = 46140, 21, 214
CLAN_START, CLAN_SIZE, CLAN_COUNT = 0xC5CA, 22, 72
TREASURE_START, TREASURE_SIZE, TREASURE_COUNT = 0xD334, 19, 120
RESOURCE_FIELDS = (('gold', 'Gold', 11), ('rice', 'Rice', 13),
                   ('horses', 'Horses', 15), ('firearms', 'Firearms', 17))


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = "Nobunaga's Ambition: Tenshouki with Power-Up Kit (Windows)"
    size: int = SIZE
    fields: tuple = ()
    sample_verified: bool = False
    editing_verified: bool = False
    game_load_verified: bool = False
    published_format: bool = True
    note: str = ('Original Japanese Windows PK eight-slot SAVEDAT.n6p layout. '
                 'Existing military-district Gold, Rice, Horses and Firearms reductions; '
                 'complete public raw writer proof. No genuine occupied player save '
                 'or edited game-load qualification has been performed.')


FORMAT = Format()


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    group: str
    slot: int
    size: int = 2
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + 2], 'little')

    def validate(self, value):
        if type(value) is not int or not 0 <= value <= self.maximum:
            raise SaveError(f'{self.label}: enter a whole number from 0 to the opened stock ({self.maximum}).')


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
        raise SaveError('Select the original Japanese Windows Tenshouki PK profile.')
    return FORMAT


def _u16(raw, offset):
    return int.from_bytes(raw[offset:offset + 2], 'little')


def _slots(raw):
    return tuple(index for index in range(SLOT_COUNT) if _u16(raw, 11 + 2 * index) == 1)


def _districts(raw, slot):
    origin = SLOT_START + slot * SLOT_SIZE
    for index in range(DISTRICT_COUNT):
        base = origin + DISTRICT_START + index * DISTRICT_SIZE
        residence, leader, owner = (_u16(raw, base + relative) for relative in (4, 6, 8))
        if residence == 0xFFFF:
            continue
        if not (1 <= residence <= CASTLE_COUNT and 1 <= leader <= GENERAL_COUNT
                and 1 <= owner <= CLAN_COUNT):
            raise SaveError('Occupied Tenshouki military district has invalid native record references.')
        clan = origin + CLAN_START + (owner - 1) * CLAN_SIZE
        if not 1 <= _u16(raw, clan) <= GENERAL_COUNT:
            raise SaveError('Occupied Tenshouki district refers to an absent or invalid clan.')
        yield index, base, residence, leader, owner


@lru_cache(maxsize=4)
def _validate_raw(raw):
    if len(raw) != SIZE or raw[:len(MAGIC)] != MAGIC:
        raise SaveError('Not the exact original Windows PK 1995.08.16 eight-slot save.')
    for index in range(SLOT_COUNT):
        used = _u16(raw, 11 + 2 * index)
        if used not in (0, 1):
            raise SaveError('Invalid Tenshouki occupied-slot flag.')
        if not used:
            continue
        preview = 0x1F + index * 158
        origin = SLOT_START + index * SLOT_SIZE
        if raw[preview + 2] > 3 or raw[preview + 16] > 5 or raw[preview + 17] > 4:
            raise SaveError('Unsupported Tenshouki scenario/season/difficulty preview.')
        if raw[origin + 2] > 3:
            raise SaveError('Invalid occupied Tenshouki slot season.')
        # Preview year is explicitly independent of the gameplay year in the
        # published format; no identity is inferred from a player's filename.
        tuple(_districts(raw, index))
    return True


def decode(raw, game_id=GAME_ID, source=Path('copy.n6p')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)):
        raise SaveError('Tenshouki requires an exact-size native byte buffer.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source), raw, raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path)
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('The Tenshouki opened snapshot was changed outside staging.')
    _validate_raw(document.raw)


def _path(path):
    lexical = Path(path).absolute()
    if any(part.is_symlink() for part in (lexical, *lexical.parents)):
        raise SaveError('Use an ordinary separate Tenshouki copy, without symbolic-link aliases.')
    if lexical.is_file() and lexical.stat().st_nlink != 1:
        raise SaveError('Use an ordinary separate Tenshouki copy, without hard-link aliases.')
    resolved = safe_path(path)
    for folder in (resolved.parent, *resolved.parents):
        if any((folder / name).is_file() for name in
               ('TEN95PK.EXE', 'ten95pk.exe', 'NOBU6PK.EXE', 'nobu6pk.exe',
                'TENSHOU.EXE', 'tenshou.exe')):
            raise SaveError('Use a separate save copy outside the live Tenshouki game folder.')
    return resolved


def _extension(path):
    if path.suffix.casefold() != EXTENSION:
        raise SaveError('Open a separate original Windows PK .n6p save copy.')


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _path(path)
    _extension(path)
    with path.open('rb') as stream:
        raw = stream.read(SIZE + 1)
    return decode(raw, game_id, path)


def _text(raw):
    value = raw.split(b'\0', 1)[0]
    try:
        text = value.decode('cp932')
    except UnicodeError:
        return f'[native name bytes: {value.hex()}]'
    return text if text and all(c.isprintable() for c in text) else '[unnamed native record]'


def _general_name(raw, origin, index):
    base = origin + NAME_START + index * NAME_SIZE
    return _text(raw[base:base + 7]) + ' ' + _text(raw[base + 7:base + 14])


@lru_cache(maxsize=4)
def _fields(raw):
    result = {}
    for slot in _slots(raw):
        origin = SLOT_START + slot * SLOT_SIZE
        for index, base, residence, leader, owner in _districts(raw, slot):
            castle = origin + CASTLE_START + (residence - 1) * CASTLE_SIZE
            group = f'Slot {slot + 1} · district {index + 1} · {_text(raw[castle + 8:castle + 17])}'
            for key, label, relative in RESOURCE_FIELDS:
                value = _u16(raw, base + relative)
                if value == 0:
                    continue
                field = Field(f'slot_{slot}_district_{index}_{key}', label + ' (reduce only)',
                              base + relative, value, group, slot + 1)
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
        raise SaveError('Tenshouki edits require a field/value mapping.')
    output = bytearray(document.raw)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown field, empty stock or unoccupied military district.')
        field = fields[key]
        field.validate(value)
        output[field.offset:field.offset + 2] = value.to_bytes(2, 'little')
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Tenshouki resource field.')
    field = field_map(document)[key]
    field.validate(value)
    result = dict(changes)
    if value == field.value(document.raw):
        result.pop(key, None)
    else:
        result[key] = value
    return result


def serialize(document, changes):
    output = changed_payload(document, changes)
    if output == document.raw:
        return document.raw
    if decode(output).raw != output:
        raise SaveError('Edited Tenshouki save failed structural read-back.')
    return output


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.raw), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in field_map(document):
            raise SaveError('Unknown Tenshouki resource field.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def _source(document):
    source = _path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SIZE + 1)
    except OSError as error:
        raise SaveError('The opened Tenshouki copy is unavailable; reopen it.') from error
    if current != document.raw:
        raise SaveError('The opened Tenshouki copy changed on disk; reopen it.')
    return source


def backup(document):
    validate_document(document)
    source = _source(document)
    return snapshot_backup(document.raw, source, GAME_ID,
                           _path(source.parent / 'WarriorsEditorBackups'))


def save_as(document, changes, destination):
    validate_document(document)
    destination = _path(destination)
    _extension(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    _source(document)
    output = serialize(document, changes)
    backup(document)
    _source(document)
    atomic_new(output, destination)
    return decode(output, source=destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = _path(backup_path), _path(destination)
    _path(backup_path.with_suffix('.json'))
    _extension(backup_path)
    _extension(destination)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, SIZE,
                            validate_raw=lambda raw: decode(raw))


def inspection_rows(document):
    validate_document(document)
    slots, districts, generals, castles, clans, treasures = [], [], [], [], [], []
    for slot in range(SLOT_COUNT):
        used = slot in _slots(document.raw)
        preview = 0x1F + slot * 158
        slots.append((slot + 1, 'Occupied' if used else 'Unused',
                      _u16(document.raw, preview) + 1454 if used else '',
                      document.raw[preview + 2] if used else '',
                      document.raw[preview + 16] if used else '',
                      document.raw[preview + 17] if used else ''))
        if not used:
            continue
        origin = SLOT_START + slot * SLOT_SIZE
        for index, base, residence, leader, owner in _districts(document.raw, slot):
            districts.append((slot + 1, index + 1, owner, residence,
                              _general_name(document.raw, origin, leader - 1),
                              *(_u16(document.raw, base + rel) for rel in (11, 13, 15, 17))))
        for index in range(GENERAL_COUNT):
            base = origin + GENERAL_START + index * GENERAL_SIZE
            names = origin + NAME_START + index * NAME_SIZE
            generals.append((slot + 1, index + 1, _general_name(document.raw, origin, index),
                             document.raw[names + 16] & 15, _u16(document.raw, base + 21),
                             document.raw[base + 6], document.raw[base + 7], document.raw[base + 8],
                             _u16(document.raw, base + 9), _u16(document.raw, base + 11),
                             _u16(document.raw, base + 13), document.raw[base + 17]))
        for index in range(CASTLE_COUNT):
            base = origin + CASTLE_START + index * CASTLE_SIZE
            castles.append((slot + 1, index + 1, _text(document.raw[base + 8:base + 17]),
                            _u16(document.raw, base + 17), document.raw[base + 19],
                            _u16(document.raw, base + 20), document.raw[base + 22],
                            _u16(document.raw, base + 23), document.raw[base + 25]))
        for index in range(CLAN_COUNT):
            base = origin + CLAN_START + index * CLAN_SIZE
            leader = _u16(document.raw, base)
            if leader == 0xFFFF:
                continue
            clans.append((slot + 1, index + 1, leader,
                          _general_name(document.raw, origin, leader - 1)
                          if 1 <= leader <= GENERAL_COUNT else '[unknown leader reference]',
                          document.raw[base + 9], document.raw[base + 10], document.raw[base + 11]))
        for index in range(TREASURE_COUNT):
            base = origin + TREASURE_START + index * TREASURE_SIZE
            treasures.append((slot + 1, index + 1, _text(document.raw[base:base + 13]),
                              document.raw[base + 13], _u16(document.raw, base + 15),
                              document.raw[base + 17] & 15, document.raw[base + 18]))
    return tuple(tuple(rows) for rows in (slots, districts, generals, castles, clans, treasures))


def record_label(slot, group):
    return group


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unknown Tenshouki resource field.')
    return ('Reduce this existing military district stock only. Automatic Max is disabled. '
            'Ownership, leader, residence, troop allocations, action points and every other slot remain intact.')

"""Qualified native Ultimate PC resources and existing attribute inventory.

Packed offsets and natural bounds are recovered from the Ultimate DLL; unknown
records, lifetime counters, ownership, equipment and progression remain intact.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo4_ultimate import codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'wo4_ultimate'
TITLE = 'Warriors Orochi 4 Ultimate (Windows PC)'
SAVE_SIZE, EXTENSION = codec.FILE_SIZE, '.bin'
INTEGRITY_KIND = 'none'
RESOURCE_MAP = (
    ('gems', 'Spendable Gems', 0x274, 4, 9_999_999),
    ('crystals', 'Spendable Crystals', 0x27C, 2, 999),
    ('growth_points', 'Growth Points', 0x280, 4, 99_999_999),
)
ELEMENT_BASE, ELEMENT_COUNT, ELEMENT_MAXIMUM = 0x28E, 64, 9_999
OFFICER_COUNT, OFFICER_STRIDE = 200, 0x30C
SKILL_POINTS_RELATIVE, PROMOTIONS_RELATIVE, UPGRADE_STONES_RELATIVE = 0x14, 0x10D, 0x10E
WEAPON_BASE, WEAPON_COUNT, WEAPON_STRIDE = 0x26160, 0x1F60, 0x1F


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
    maxable: bool = True
    kind: str = 'int'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'little')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Native Ultimate PC system revision 20200101. Spendable Gems, Crystals, '
                 'Growth Points, progressed officers’ Skill Points and promoted officers’ Upgrade Stones, existing Skill Orbs and attribute quantities. '
                 'Lifetime earnings, officer EXP, allocations, promotions, story, Infinity Mode and equipment '
                 'remain unchanged. The AES fingerprint is not a whole-save checksum; '
                 'edited game-load validation has not been performed by this project.')


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
        raise SaveError('Choose the explicit Warriors Orochi 4 Ultimate Windows PC adapter.')
    return FORMAT


def _path(path):
    original = Path(path).expanduser().absolute()
    path = safe_path(path)
    for candidate in (original, path):
        parts = tuple(part.casefold() for part in candidate.parts)
        if any(parts[index:index + 2] == ('koeitecmo', 'warriors orochi 4')
               for index in range(len(parts) - 1)):
            raise SaveError('Open a separate copy outside the live KoeiTecmo Warriors Orochi 4 folder.')
    if path.suffix.lower() != EXTENSION:
        raise SaveError('Open a separate native SAVEDATAU.BIN copy and save to a new .BIN copy.')
    return path


def decode(raw, game_id=GAME_ID, source=Path('Ultimate-copy.bin')):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError('An immutable complete Ultimate PC save is required.')
    payload = codec.decode(raw)
    return Document(FORMAT, Path(source), raw, payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _path(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            ):
        raise SaveError('A frozen native Ultimate PC snapshot is required.')
    if codec.decode(document.raw) != document.payload:
        raise SaveError('The opened Ultimate snapshot was altered outside staging.')


@lru_cache(maxsize=4)
def _fields(payload):
    fields = [Field(identity, label, offset, size, maximum, 'Resources', 0)
              for identity, label, offset, size, maximum in RESOURCE_MAP]
    # Element ID 0 is not promoted into an editable inventory entry. Unknown,
    # zero/unowned and unusual quantities remain inspectable without writes.
    for identity in range(1, ELEMENT_COUNT):
        offset = ELEMENT_BASE + 2 * identity
        quantity = int.from_bytes(payload[offset:offset + 2], 'little')
        if 1 <= quantity <= ELEMENT_MAXIMUM:
            fields.append(Field(f'element_{identity}', f'Attribute element ID {identity}: Quantity',
                offset, 2, ELEMENT_MAXIMUM, 'Attribute elements', identity, minimum=1))
    for record in range(OFFICER_COUNT):
        base = codec.SYSTEM_PAYLOAD_SIZE + record * OFFICER_STRIDE
        exp = int.from_bytes(payload[base:base + 4], 'little')
        if 0 < exp <= 999_999 and payload[base + PROMOTIONS_RELATIVE] <= 9:
            fields.append(Field(f'officer_{record}_skill_points', 'Unspent Skill Points',
                base + SKILL_POINTS_RELATIVE, 2, 999, 'Officer Skill Points', record + 1))
            if payload[base + PROMOTIONS_RELATIVE] > 0:
                fields.append(Field(f'officer_{record}_upgrade_stones', 'Unspent Upgrade Stones',
                    base + UPGRADE_STONES_RELATIVE, 2, 9_999, 'Officer Upgrade Stones', record + 1))
    orbs = int.from_bytes(payload[0x30E:0x310], 'little')
    if 1 <= orbs <= 999:
        fields.append(Field('skill_orbs', 'Existing Skill Orbs', 0x30E, 2, orbs,
                            'Skill Orbs', 0, maxable=False))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    if type(changes) is not dict:
        raise SaveError('Pending Ultimate PC changes must be a dictionary.')
    mapping = field_map(document)
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only qualified resources and existing ordinary attribute quantities are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        output[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(output)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = codec.encode(document.raw, payload)
    if decode(raw).payload != payload:
        raise SaveError('The edited native Ultimate payload failed exact reconstruction.')
    return raw


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('The requested Ultimate PC record is inspection only.')
    result = dict(changes)
    if type(value) is int and value == mapping[key].value(document.payload):
        result.pop(key, None)
    else:
        mapping[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    keys = tuple(keys)
    mapping = field_map(document)
    changed_payload(document, changes)
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('The requested Ultimate PC record is not editable.')
    result = {}
    for key in keys:
        field = mapping[key]
        if not field.maxable:
            continue
        original = field.value(document.payload)
        current = changes.get(key, original)
        if original > field.maximum:
            result[key] = original
        elif field.minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    result = dict(changes)
    keys = [f.id for f in fields_for(document) if group is None or f.group == group]
    for key, value in limit_values(document, changes, keys).items():
        if value == field_map(document)[key].value(document.payload):
            result.pop(key, None)
        else:
            result[key] = value
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def _validate_source(document):
    validate_document(document)
    source = _path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SAVE_SIZE + 1)
    except OSError as error:
        raise SaveError('The opened Ultimate copy is unavailable. Reopen a separate save copy.') from error
    if current != document.raw:
        raise SaveError('The opened Ultimate copy changed on disk. Reopen it before saving.')
    return source


def backup(document):
    source = _validate_source(document)
    return snapshot_backup(document.raw, source, GAME_ID,
                           source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    source = _validate_source(document)
    destination = _path(destination)
    if source == destination or destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = _path(backup_path), _path(destination)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))



def record_label(slot, group='Resources'):
    if group in ('Officer Skill Points', 'Officer Upgrade Stones'):
        return f'Officer record {slot}'
    return f'Attribute ID {slot}' if group == 'Attribute elements' else 'Shared resources'


def inspection_rows(document):
    validate_document(document)
    rows = [dict(group='Resources', label=label, value=int.from_bytes(document.payload[offset:offset + size], 'little'))
            for _, label, offset, size, _ in RESOURCE_MAP]
    for label, offset, size in [('Lifetime Gems', 0x278, 4), ('Lifetime Crystals', 0x27E, 2)]:
        rows.append(dict(group='History — inspection only', label=label,
                         value=int.from_bytes(document.payload[offset:offset + size], 'little')))
    return tuple(rows)


def element_records(document):
    validate_document(document)
    mapping = field_map(document)
    return tuple((identity, int.from_bytes(document.payload[ELEMENT_BASE + identity * 2:
                ELEMENT_BASE + identity * 2 + 2], 'little'),
                'Editable existing quantity' if f'element_{identity}' in mapping else 'Inspection only')
                for identity in range(ELEMENT_COUNT))


def field_hint(document, key):
    field = field_map(document)[key]
    if field.id == 'skill_orbs':
        return 'Reduce existing Skill Orbs only. Conversion into character Skill Points stays under game control; Max leaves this field intact.'
    return (f'Natural bound: {field.minimum:,}–{field.maximum:,}. '
            'Max preserves higher and unusual existing values. '
            'Available balances, lifetime history, acquisition and story progression are separate.')


def officer_records(document):
    validate_document(document)
    mapping = field_map(document)
    rows = []
    for record in range(OFFICER_COUNT):
        base = codec.SYSTEM_PAYLOAD_SIZE + record * OFFICER_STRIDE
        exp = int.from_bytes(document.payload[base:base + 4], 'little')
        points = int.from_bytes(document.payload[base + SKILL_POINTS_RELATIVE:
                                base + SKILL_POINTS_RELATIVE + 2], 'little')
        promotions = document.payload[base + PROMOTIONS_RELATIVE]
        if exp or points or promotions:
            stones = int.from_bytes(document.payload[base + UPGRADE_STONES_RELATIVE:base + UPGRADE_STONES_RELATIVE + 2], 'little')
            rows.append((record + 1, exp, points, promotions, stones,
                         'Existing pools editable' if f'officer_{record}_skill_points' in mapping else 'Inspection only'))
    return tuple(rows)


def weapon_records(document):
    validate_document(document)
    rows = []
    for record in range(WEAPON_COUNT):
        base = codec.SYSTEM_PAYLOAD_SIZE + WEAPON_BASE + record * WEAPON_STRIDE
        identity = int.from_bytes(document.payload[base:base + 2], 'little')
        if identity == 0xFFFF:
            continue
        elements = ', '.join(f'{document.payload[base + 5 + slot]}:{document.payload[base + 15 + slot]}'
                             for slot in range(10))
        rows.append((record + 1, identity, elements))
    return tuple(rows)

"""Existing custom-horse appearance sliders in native PC SystemSave.dat.

The source's 150-row schema independently matches the genuine native SystemSave
including every fixed ordinal. Occupancy, names, types, models, stats, abilities
and campaign resources remain untouched. See docs/DW8E_CUSTOM_HORSES.md.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8e import dw8e_codec as codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'dw8e'
SAVE_SIZE = codec.SAVE_SIZE
HORSE_BASE, HORSE_STRIDE, HORSE_COUNT = 0x38104, 0x4C, 150
SLIDERS = (('body', 'Body type', 0x10), ('head', 'Head size', 0x11),
           ('neck', 'Neck length', 0x12), ('torso', 'Torso length', 0x13),
           ('legs', 'Leg length', 0x14), ('tail', 'Tail length', 0x15),
           ('muscle', 'Muscle volume', 0x16))
# Body Type has an explicit source-backed 0..4 bound. Other named members admit
# only same-member positions witnessed in existing original ordinary PC horses.
EDITABLE_SLIDERS = SLIDERS
QUALIFIED_MENU_TYPES = frozenset(range(8))
QUALIFIED_MODELS = frozenset(range(0x96, 0x9E))


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int = 1
    maximum: int = 4
    group: str = 'Horse appearance'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'

    @property
    def experimental_maximum(self):
        # Appearance positions are native enum choices.
        return None

    def value(self, payload):
        return payload[self.offset]

    def validate(self, value):
        if type(value) is not int or not 0 <= value <= 4:
            raise SaveError(f'{self.label} requires a slider position from 0 to 4.')

    def encoded(self, value):
        self.validate(value)
        return bytes([value])


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Dynasty Warriors 8 Empires (PC SYSTEM custom horses)', SAVE_SIZE, (),
                'Existing custom-horse appearance sliders in native PC SystemSave.dat. '
                'Campaign resources, horse identity, ownership, type, model, abilities '
                'and progression remain unchanged. Appearance choices are excluded from Max.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    seed: int

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select native PC DW8 Empires SYSTEM custom horses.')
    return FORMAT


@lru_cache(maxsize=4)
def _qualify_horses(payload):
    if any(int.from_bytes(payload[HORSE_BASE + identity * HORSE_STRIDE + 0x44:
                                   HORSE_BASE + identity * HORSE_STRIDE + 0x48], 'little')
           != identity + 30 for identity in range(HORSE_COUNT)):
        raise SaveError('Unsupported DW8 Empires SYSTEM custom-horse identity/layout.')


def decode(raw, game_id=GAME_ID, source=Path('system-copy.dat')):
    get_format(game_id)
    frozen = codec.freeze(raw)
    payload, seed = codec.decode(frozen)
    _qualify_horses(payload)
    return Document(FORMAT, Path(source), frozen, payload, seed)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native PC SystemSave.dat copy.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.seed) is not int):
        raise SaveError('A frozen native PC DW8 Empires SYSTEM snapshot is required.')
    if codec.decode(document.raw) != (document.payload, document.seed):
        raise SaveError('The opened DW8 Empires SYSTEM snapshot was changed externally.')
    _qualify_horses(document.payload)


def _name(payload, start):
    raw = payload[start + 2:start + 15].split(b'\0', 1)[0]
    try:
        decoded = raw.decode('utf-8')
        return ''.join(character if character.isprintable() else f'\\u{ord(character):04X}'
                       for character in decoded) or '(unnamed)'
    except UnicodeDecodeError:
        return repr(raw)[2:-1] or '(unnamed)'


@lru_cache(maxsize=4)
def _mapped_fields(payload):
    fields = []
    for identity in range(HORSE_COUNT):
        start = HORSE_BASE + identity * HORSE_STRIDE
        if payload[start] != 1:
            continue
        name = _name(payload, start)
        for key, label, relative in EDITABLE_SLIDERS:
            if key != 'body' and (payload[start + 15] not in QUALIFIED_MENU_TYPES
                                  or payload[start + 0x1E] not in QUALIFIED_MODELS):
                continue
            if 0 <= payload[start + relative] <= 4:
                fields.append(Field(f'horse_{identity}_{key}', f'{name}: {label}',
                                    start + relative, slot=identity + 1))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _mapped_fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def field_options(document, key):
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('The requested custom-horse slider is not editable.')
    member = key.rsplit('_', 1)[-1]
    positions = range(5) if member == 'body' else sorted({
        field.value(document.payload) for field in fields.values()
        if field.id.rsplit('_', 1)[-1] == member})
    return tuple((position, f'Position {position}') for position in positions)


def changed_payload(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Pending SYSTEM edits must be a field/value mapping.')
    mapping = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only qualified existing custom-horse appearance sliders are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        if value not in dict(field_options(document, key)):
            raise SaveError('Choose a position witnessed for this slider in the opened ordinary PC horses.')
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    raw = codec.encode(payload, document.raw)
    if decode(raw, GAME_ID, document.source).payload != payload:
        raise SaveError('DW8 Empires SYSTEM edited copy verification failed.')
    return raw


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('The requested custom-horse slider is not editable.')
    field = mapping[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
        changed_payload(document, result)
    return result


def limit_values(document, changes, keys):
    mapping = field_map(document)
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in mapping:
            raise SaveError('The requested custom-horse slider is not editable.')
    return {}  # Appearance sliders are choices, never ordered resource upgrades.


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination for the SYSTEM copy.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened SYSTEM copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='Horse appearance'):
    return f'Custom horse slot {slot}' if type(slot) is int and 1 <= slot <= HORSE_COUNT else group


def horses(document):
    validate_document(document)
    rows = []
    for identity in range(HORSE_COUNT):
        start = HORSE_BASE + identity * HORSE_STRIDE
        rows.append({'slot': identity + 1, 'ordinal': identity + 30, 'name': _name(document.payload, start),
                     'occupied': document.payload[start], 'menu_type': document.payload[start + 15],
                     'sliders': tuple(document.payload[start + offset] for _, _, offset in SLIDERS),
                     'model_byte': document.payload[start + 0x1E],
                     'speed': int.from_bytes(document.payload[start + 0x24:start + 0x26], 'little'),
                     'power': int.from_bytes(document.payload[start + 0x2A:start + 0x2C], 'little'),
                     'abilities': tuple(document.payload[start + 0x2E:start + 0x32])})
    return tuple(rows)


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    if key not in field_map(document):
        raise SaveError('The requested custom-horse slider is not editable.')
    return ('Existing custom-horse appearance slider. Body Type has positions 0..4; '
            'other choices are positions witnessed for that same slider in original '
            'ordinary PC horse records. '
            'Max leaves appearance choices unchanged; name, type, model, abilities, '
            'combat stats and ownership are preserved.')


INTEGRITY_KIND = 'checksum'

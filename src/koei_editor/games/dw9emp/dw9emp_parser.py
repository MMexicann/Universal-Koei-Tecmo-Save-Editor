"""Source-backed current native DW9 Empires SYSTEMDATA inventory quantities.

The first serialized component begins immediately after the revision and stores
800 little-endian quantities. Only existing ordinary quantities are writable;
zero, higher and unknown values are retained. Names, acquisition state and other
systems require further qualification and are never manufactured here.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.games.dw9emp import dw9emp_codec as codec


GAME_ID = 'dw9emp'
SAVE_SIZE = codec.SAVE_SIZE
ITEM_BASE, ITEM_COUNT, ITEM_MAXIMUM = 4, 800, 999
CAW_BASE, CAW_STRIDE, CAW_COUNT = codec.CAW_BASE, codec.CAW_STRIDE, codec.CAW_COUNT


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int = 2
    maximum: int = ITEM_MAXIMUM
    group: str = 'Inventory quantities'
    slot: int = 0
    minimum: int = 1
    maxable: bool = False
    kind: str = 'int'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from '
                            f'{self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'little')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = False
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Dynasty Warriors 9 Empires (PC SYSTEMDATA)', SAVE_SIZE,
                (), 'Edit existing ordinary item quantities (1..999); inspect all '
                '800 stored quantities by item ID and 900 custom officer '
                'records read only. Item quantities support individual edits; '
                'bulk Max leaves these unnamed categories unchanged.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    seed: int = 0

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('This adapter handles native PC DW9 Empires SYSTEMDATA only.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('system-copy.bin')):
    layout = get_format(game_id)
    payload = codec.decode(raw)
    return Document(layout, Path(source), payload, payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate native SYSTEMDATA SAVEDATA.BIN copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.seed) is not int or document.seed != 0):
        raise SaveError('A frozen native PC DW9 Empires SYSTEMDATA document is required.')
    if codec.decode(document.raw) != document.payload:
        raise SaveError('The opened DW9 Empires snapshot was changed outside the edit workflow.')


@lru_cache(maxsize=4)
def _mapped_fields(payload):
    return tuple(Field(f'item_{identity}_quantity', f'Item ID {identity}: Quantity',
                       ITEM_BASE + 2 * identity, slot=identity + 1)
                 for identity in range(ITEM_COUNT)
                 if 1 <= int.from_bytes(payload[ITEM_BASE + 2 * identity:
                                               ITEM_BASE + 2 * identity + 2], 'little') <= ITEM_MAXIMUM)


def fields_for(document):
    validate_document(document)
    return _mapped_fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapping:
            raise SaveError('Only existing ordinary DW9 Empires item quantities are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = codec.encode(payload)
    if decode(raw, GAME_ID, document.source).payload != payload:
        raise SaveError('DW9 Empires edited copy verification failed.')
    return raw


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapping = field_map(document)
    if key not in mapping:
        raise SaveError('Only existing ordinary DW9 Empires item quantities are writable.')
    field = mapping[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapping = field_map(document)
    changed_payload(document, changes)
    result = {}
    for key in keys:
        if key not in mapping:
            raise SaveError('The requested DW9 Empires quantity is not editable.')
        field = mapping[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and field.minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changes = normalize_pending_values(document, changes, field_map(document))
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    result = dict(changes)
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


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
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new .bin destination for the SYSTEMDATA copy.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    with safe_path(document.source).open('rb') as stream:
        current = stream.read(SAVE_SIZE + 1)
    if current != document.raw:
        raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='Inventory quantities'):
    if type(slot) is int and 1 <= slot <= ITEM_COUNT:
        return f'Item ID {slot - 1}'
    return group


def items(document):
    validate_document(document)
    return tuple({'id': identity, 'quantity': int.from_bytes(
                      document.payload[ITEM_BASE + 2 * identity:ITEM_BASE + 2 * identity + 2], 'little')}
                 for identity in range(ITEM_COUNT))


def custom_officers(document):
    """Qualified packed records; no inferred ownership, grades or stat edits.

The native saved-to-live rebuild copies these appearance/name values into the
CAW display model. UTF-8 previews are intentionally best effort; unsupported
encoding and control bytes are escaped without altering the source.
    """
    validate_document(document)
    rows = []
    for identity in range(CAW_COUNT):
        start = CAW_BASE + identity * CAW_STRIDE
        raw_name = document.payload[start + 21:start + 46]
        terminated = raw_name.split(b'\0', 1)[0]
        try:
            decoded = terminated.decode('utf-8')
            preview = ''.join(character if character.isprintable()
                              else f'\\u{ord(character):04X}' for character in decoded)
        except UnicodeDecodeError:
            preview = repr(terminated)[2:-1]
        rows.append({'id': identity, 'name_preview': preview or '(empty name)',
                     'name_bytes': raw_name,
                     'flags': tuple(document.payload[start:start + 2]),
                     'stored_values': tuple(int.from_bytes(
                         document.payload[start + 2 + 2 * index:start + 4 + 2 * index], 'little')
                         for index in range(8))})
    return tuple(rows)


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    if key not in field_map(document):
        raise SaveError('The requested DW9 Empires quantity is not editable.')
    return ('Existing item quantity, native cap 999. Zero and unusual higher '
            'quantities remain read only. Item IDs retain their native order; '
            'names, acquisition, equipment and rewards are not inferred.')

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'none'

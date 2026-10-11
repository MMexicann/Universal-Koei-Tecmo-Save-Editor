"""Original WO4 Windows revision20180720 balances and existing elements.

The native DLL's complete serializer has no payload checksum. Its AES
fingerprint detects a wrong key/truncated ending, not general payload damage.
Only proved spendable resources and ordinary existing element quantities change.
"""
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo4 import codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'wo4_pc'
REVISION = 20180720
FILE_SIZE = codec.FILE_SIZE
INTEGRITY_KIND = None
SYSTEM_GLOBAL = 0x1A8
OFFICER_COUNT = 200
OFFICER_STRIDE = 0x30C
WEAPON_START = OFFICER_COUNT * OFFICER_STRIDE
WEAPON_COUNT = 8032
WEAPON_STRIDE = 0x1F
TRAINING_START = WEAPON_START + WEAPON_COUNT * WEAPON_STRIDE
CHALLENGE_START = TRAINING_START + 3 * 0x175
RESERVED_START = CHALLENGE_START + 200 * 0x26


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    minimum: int = 0
    group: str = 'Resources'
    slot: int = 0
    maxable: bool = True
    kind: str = 'int'
    byteorder: str = 'little'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label}: use a whole number from {self.minimum} to {self.maximum}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Warriors Orochi 4 (Windows PC)'
    size: int = FILE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = 'Original PC layout; resources, existing elements and searchable native records.'


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    blocks: tuple

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if type(game_id) is not str or game_id != GAME_ID:
        raise SaveError('Select Warriors Orochi 4 for Windows PC.')
    return FORMAT


@lru_cache(maxsize=2)
def _snapshot(raw):
    try:
        blocks = codec.decode(raw)
    except (ValueError, struct.error) as error:
        raise SaveError(f'WO4 native envelope check failed: {error}.') from error
    payload = b''.join(block.payload for block in blocks)
    if (len(payload) != codec.PAYLOAD_SIZE
            or struct.unpack_from('<I', payload)[0] != REVISION):
        raise SaveError('Unsupported original Windows WO4 revision; Ultimate uses its own profile.')
    # The native header serializes three DWORDs and four uninterpreted bytes.
    # Qualify only the opened/native-initialized (revision, 0, 0) header state
    # and the DLL's one-play-object layout; other header states need separate
    # native qualification. The two words are not inferred gameplay fields.
    if struct.unpack_from('<II', payload, 4) != (0, 0):
        raise SaveError('Unsupported original WO4 header state.')
    if RESERVED_START + 0xF000 != codec.PLAY_PAYLOAD_SIZE:
        raise SaveError('WO4 record geometry does not fit its native gameplay span.')
    return blocks, payload


def decode(raw, game_id=GAME_ID, source=Path('copy.bin')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != FILE_SIZE:
        raise SaveError('Original Windows WO4 saves must contain exactly 927,576 bytes.')
    raw = bytes(raw)
    blocks, payload = _snapshot(raw)
    return Document(FORMAT, Path(source), raw, payload, blocks)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.blocks) is not tuple):
        raise SaveError('WO4 snapshot must be the immutable registered original.')
    if document != decode(document.raw, GAME_ID, document.source):
        raise SaveError('WO4 snapshot changed outside staged edits.')


@lru_cache(maxsize=2)
def _fields(payload):
    fields = {
        'gems': Field('gems', 'Gems', SYSTEM_GLOBAL + 0xCC, 4, 9_999_999),
        'crystals': Field('crystals', 'Crystals', SYSTEM_GLOBAL + 0xD4, 2, 999),
        'growth_points': Field('growth_points', 'Growth points', SYSTEM_GLOBAL + 0xD8, 4, 999_999),
    }
    for element in range(64):
        offset = SYSTEM_GLOBAL + 0xE6 + element * 2
        amount = int.from_bytes(payload[offset:offset + 2], 'little')
        if 1 <= amount <= 999:
            key = f'element_{element:02d}'
            fields[key] = Field(key, f'Element ID {element}: existing quantity', offset, 2, 999,
                                minimum=1, group='Existing weapon elements', slot=element,
                                maxable=False)
    return MappingProxyType(fields)


def field_map(document):
    validate_document(document)
    return _fields(document.payload)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document, changes):
    fields = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('WO4 changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unmapped WO4 field.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(output)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('Unmapped WO4 field.')
    field = fields[key]
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
    blocks = (replace(document.blocks[0], payload=payload[:codec.SYSTEM_PAYLOAD_SIZE]),
              replace(document.blocks[1], payload=payload[codec.SYSTEM_PAYLOAD_SIZE:]))
    raw = codec.encode(blocks)
    reopened = decode(raw, GAME_ID, document.source)
    if reopened.payload != payload or any((a.index, a.file_offset, a.iv_seed, a.padding) !=
            (b.index, b.file_offset, b.iv_seed, b.padding)
            for a, b in zip(document.blocks, reopened.blocks)):
        raise SaveError('WO4 edited copy failed native read-back verification.')
    return raw


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    fields = field_map(document)
    if any(type(key) is not str or key not in fields for key in keys):
        raise SaveError('Unmapped WO4 field.')
    result = {}
    for key in keys:
        field = fields[key]
        if field.maxable:
            opened = field.value(document.payload)
            current = changes.get(key, opened)
            target = max(opened, current, field.maximum)
            if current != target:
                result[key] = target
    return result


def maximums(document, changes, group=None):
    fields = field_map(document)
    result = dict(changes)
    values = limit_values(document, changes, [f.id for f in fields.values()
                                               if group is None or f.group == group])
    for key, value in values.items():
        result = stage(document, result, key, value)
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(f, f.value(document.payload), changes[f.id]) for f in fields_for(document) if f.id in changes]


def _copy_path(path):
    resolved = safe_path(path)
    for text in (str(path), str(resolved)):
        text = text.replace('\\', '/').casefold().rstrip('/')
        if any(part in text + '/' for part in ('/koeitecmo/warriors orochi 4/',
                                                 '/koeitecmo/warriors orochi4/')):
            raise SaveError('Use a separate copy outside live Warriors Orochi 4 save folders.')
    return resolved


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    if path.suffix.casefold() != '.bin':
        raise SaveError('Open a separate original WO4 .bin save copy.')
    with path.open('rb') as stream:
        raw = stream.read(FILE_SIZE + 1)
    return decode(raw, game_id, path)


def _validate_source(document):
    source = _copy_path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(FILE_SIZE + 1)
    except OSError as error:
        raise SaveError('The opened copy is unavailable; reopen before saving.') from error
    if current != document.raw:
        raise SaveError('The opened copy changed on disk; reopen before saving.')
    return source


def backup(document):
    validate_document(document)
    source = _validate_source(document)
    return snapshot_backup(document.raw, source, GAME_ID, _copy_path(source.parent / 'WarriorsEditorBackups'))


def save_as(document, changes, destination):
    validate_document(document)
    destination = _copy_path(destination)
    if destination.suffix.casefold() != '.bin':
        raise SaveError('Choose a new .bin destination.')
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
    return restore_snapshot(_copy_path(backup_path), _copy_path(destination), GAME_ID, '.bin', FILE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group):
    return f'Element ID {slot}' if group == 'Existing weapon elements' else group


def field_hint(document, key):
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('Unmapped WO4 field.')
    if fields[key].group == 'Existing weapon elements':
        return ('Edit an existing ordinary element quantity from 1 to 999. Acquisition/discovery flags, '
                'fusion, equipped attributes and weapon ownership remain intact. Element quantities are excluded from Max.')
    return ('Spendable resources only. Earned histories, purchases, camp prerequisites, officer progression '
            'and story rewards remain intact. Max preserves higher opened balances.')


def inspection_rows(document):
    validate_document(document)
    payload = document.payload
    history = (('Gems earned history', struct.unpack_from('<I', payload, SYSTEM_GLOBAL + 0xD0)[0]),
               ('Crystals earned history', struct.unpack_from('<H', payload, SYSTEM_GLOBAL + 0xD6)[0]))
    elements = tuple((element, struct.unpack_from('<H', payload, SYSTEM_GLOBAL + 0xE6 + 2 * element)[0])
                     for element in range(64))
    play = payload[codec.SYSTEM_PAYLOAD_SIZE:]
    officers = tuple((index, struct.unpack_from('<I', play, index * OFFICER_STRIDE)[0],
                      play[index * OFFICER_STRIDE + 20],
                      struct.unpack_from('<I', play, index * OFFICER_STRIDE + 21)[0],
                      *struct.unpack_from('<HH', play, index * OFFICER_STRIDE + 25))
                     for index in range(OFFICER_COUNT))
    weapons = tuple((index, *struct.unpack_from('<HHB', play, WEAPON_START + index * WEAPON_STRIDE),
                     play[WEAPON_START + index * WEAPON_STRIDE + 5:WEAPON_START + index * WEAPON_STRIDE + 13].hex(),
                     play[WEAPON_START + index * WEAPON_STRIDE + 13:WEAPON_START + index * WEAPON_STRIDE + 21].hex())
                    for index in range(WEAPON_COUNT))
    return history, elements, officers, weapons

"""Source-backed US PS3 DW6 controls, qualified on two native player exports.

Only published combat-stat and existing weapon fields are written. The PFD
authentication layer is external; unknown gameplay bytes remain unchanged.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6.dw6_metadata import WEAPON_NAMES
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.ps3_copy import PS3CopyStorage
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'dw6_ps3'
SAVE_SIZE = 212240
TITLE_DIRECTORY = 'BLUS30110-SAVEDATA'
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xB18, 0xA8, 41
HORSE_BASE, HORSE_STRIDE, HORSE_COUNT = 0x29E0, 0x3C, 8
WEAPON_COUNT, WEAPON_STRIDE = 8, 0x10
HORSE_STATS = (('speed', 'Speed', 16), ('attack', 'Attack', 24),
               ('jump', 'Jump', 28), ('destruction', 'Destruction', 32))
INTEGRITY_KIND = 'external'


def _u32(payload, offset):
    return int.from_bytes(payload[offset:offset + 4], 'big')


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
    maxable: bool = False
    kind: str = 'int'
    encoding: str = 'unsigned big-endian integer'
    experimental: bool = True
    evidence: str = 'Apollo BLUS30110 patch locations and two independently acquired US PS3 exports'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1 if self.experimental else None

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if not within_numeric_limits(value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Dynasty Warriors 6 (original US PS3)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    published_format: bool = True
    game_load_verified: bool = False
    note: str = ('Copied PFD-decrypted BLUS30110 APP.BIN with exact original PARAM.SFO. '
                 'Manual existing horse speed/attack/jump/destruction and weapon stored damage bonus/element. '
                 'Max disabled. Reimport and resign with Apollo. Story, ownership and officer growth are preserved.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    context_digest: str = ''

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select original US PS3 Dynasty Warriors 6; PC, Japanese, Special and Empires formats differ.')
    return FORMAT


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE:
        raise SaveError('Requires a PFD-decrypted original US PS3 DW6 APP.BIN of 212,240 bytes.')
    _qualify(raw)


@lru_cache(maxsize=4)
def _qualify(raw):
    if any(_u32(raw, OFFICER_BASE + index * OFFICER_STRIDE + 136) != index
           for index in range(OFFICER_COUNT)):
        raise SaveError('DW6 PS3 big-endian officer identities do not match the qualified native layout.')


def decode(raw, game_id=GAME_ID, source=Path('APP.BIN')):
    get_format(game_id)
    qualify(raw)
    return Document(FORMAT, Path(source), raw, raw)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            metadata = stream.read(MAX_SFO_SIZE + 1)
    except FileNotFoundError as error:
        raise SaveError('Keep the original BLUS30110-SAVEDATA PARAM.SFO beside the copied APP.BIN.') from error
    if savedata_directory(metadata) != TITLE_DIRECTORY:
        raise SaveError('Requires original US BLUS30110-SAVEDATA metadata. Other DW6 regions are separate.')
    return metadata


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate PFD-decrypted PS3 .bin copy.')
    metadata = context_raw(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), game_id, path)
    if context_raw(path) != metadata:
        raise SaveError('The original PS3 metadata changed during opening.')
    return replace(document, context_digest=hashlib.sha256(metadata).hexdigest())


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or document.payload != document.raw
            or type(document.payload) is not bytes or not isinstance(document.source, Path)
            or type(document.context_digest) is not str):
        raise SaveError('A frozen native DW6 US PS3 snapshot is required.')
    qualify(document.raw)


@lru_cache(maxsize=4)
def _fields(payload):
    fields = []
    for horse in range(HORSE_COUNT):
        base = HORSE_BASE + horse * HORSE_STRIDE
        if (_u32(payload, base + 4) not in (60, 61, 62, 63, 64)
                or _u32(payload, base + 20) == 0
                or any(_u32(payload, base + offset) == 0 for _key, _label, offset in HORSE_STATS)):
            continue
        for key, label, offset in HORSE_STATS:
            fields.append(Field(f'horse_{horse}_{key}', label, base + offset, 4, 500, 'Horses', horse + 1))
    for officer in range(OFFICER_COUNT):
        for weapon in range(WEAPON_COUNT):
            base = OFFICER_BASE + officer * OFFICER_STRIDE + 8 + weapon * WEAPON_STRIDE
            identity, element = _u32(payload, base), _u32(payload, base + 8)
            if not 0 <= identity < len(WEAPON_NAMES) or element not in (0, 1, 2, 3):
                continue
            slot = officer * WEAPON_COUNT + weapon + 1
            fields.append(Field(f'officer_{officer}_weapon_{weapon}_damage_bonus',
                                'Stored damage bonus', base + 4, 4, 100, 'Weapon bonuses', slot))
            fields.append(Field(f'officer_{officer}_weapon_{weapon}_element',
                                'Element', base + 8, 4, 3, 'Weapon elements', slot, experimental=False))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    pending = normalize_pending_values(document, changes, mapping)
    result = bytearray(document.payload)
    for key, value in pending.items():
        field = mapping[key]
        result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'big')
    return bytes(result)


def serialize(document, changes):
    raw = changed_payload(document, changes)
    qualify(raw)
    return raw


def stage(document, changes, key, value):
    mapping = field_map(document)
    pending = normalize_pending_values(document, changes, mapping)
    if type(key) is not str or key not in mapping:
        raise SaveError('Choose a qualified existing DW6 PS3 horse or weapon field.')
    pending[key] = value
    return normalize_pending_values(document, pending, mapping)


def review(document, changes):
    pending = normalize_pending_values(document, changes, field_map(document))
    return [(field, field.value(document.payload), pending[field.id])
            for field in fields_for(document) if field.id in pending]


def limit_values(document, changes, keys):
    mapping = field_map(document)
    normalize_pending_values(document, changes, mapping)
    if isinstance(keys, (str, bytes)):
        raise SaveError('Choose a sequence of qualified field IDs.')
    try:
        keys = tuple(keys)
    except TypeError as error:
        raise SaveError('Choose a sequence of qualified field IDs.') from error
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('Choose qualified existing DW6 PS3 fields.')
    return {}


def maximums(document, changes, group=None):
    return normalize_pending_values(document, changes, field_map(document))


def field_options(document, key):
    if key not in field_map(document):
        raise SaveError('Choose a qualified existing field.')
    if key.endswith('_element'):
        return ((0, 'Fire'), (1, 'Ice'), (2, 'Lightning'), (3, 'No element'))
    return ()


def record_label(slot, group='Horses'):
    if group.startswith('Weapon'):
        return f'Officer {(slot - 1) // WEAPON_COUNT + 1} · Weapon {(slot - 1) % WEAPON_COUNT + 1}'
    return f'Horse {slot}'


def inspection_rows(document):
    validate_document(document)
    return [{'group': 'Officer progression', 'label': f'Officer {index + 1}',
             'value': f'Stored level index: {_u32(document.payload, OFFICER_BASE + index * OFFICER_STRIDE + 148)}; '
                      f'EXP: {_u32(document.payload, OFFICER_BASE + index * OFFICER_STRIDE + 152)}'}
            for index in range(OFFICER_COUNT)]


_storage = PS3CopyStorage(GAME_ID, SAVE_SIZE, validate_document, context_raw, decode, read_save, serialize)
backup, save_as, restore = _storage.backup, _storage.save_as, _storage.restore
prepare_self_test_copy = _storage.prepare_self_test_copy
prepare_copy_context = _storage.prepare_copy_context

"""Qualified original DW7 XL US/European PS3 export snapshots and scalar edits.

The original BLUS30873/BLES01496 native containers corroborate a 470,303-byte
decrypted APP.BIN with big-endian revision 0x11080200. Their encrypted files
include one extra PFD padding byte, which is not part of this plaintext format.
The upstream anonymous 0x6EBBC-byte base-DW7 example does not qualify DW7 XL.
Scalar editing uses individually typed original native getters, preserving all
other bytes. PFD authentication and console signing remain external.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.ps3_copy import PS3CopyStorage
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path


GAME_ID = 'dw7xl_ps3'
SAVE_SIZE = 0x72D1F
REVISION = bytes.fromhex('11080200')
TITLE_IDS = ('BLUS30873', 'BLES01496')
TITLE_DIRECTORIES = frozenset(title + '-SAVEDATA' for title in TITLE_IDS)
INTEGRITY_KIND = 'external'
OFFICER_BASE, OFFICER_COUNT, OFFICER_STRIDE = 0x2039, 65, 128
WEAPON_BASE, WEAPON_COUNT, WEAPON_STRIDE = 0x4E39, 1738, 20
INTERIM_BASE = 0xDD1F


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str = 'Resources'
    slot: int = 0
    minimum: int = 0
    maxable: bool = True
    kind: str = 'int'
    evidence: str = 'Original US/EU XL native PS3 serializers and typed accessors; exact native exports'

    @property
    def encoding(self):
        return ('unsigned big-endian 32-bit word' if self.size == 4
                else 'big-endian 16-bit word; native officer stats are signed shorts')

    @property
    def experimental_maximum(self):
        if self.id.endswith(('_active_weapon', '_seal_meter')):
            return None
        # Native officer getters sign-extend their stored shorts. Gold uses
        # an unsigned word. Keep exact signedness in the optional policy.
        return 32767 if self.size == 2 else 4294967295

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label}: choose a whole number from {self.minimum:,} '
                            f'through {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'big')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Dynasty Warriors 7: Xtreme Legends (original US/European PS3)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    note: str = ('Edit Gold, officer stored stats/skill points and decrease unlearned seal meters; '
                 'switch between already equipped owned weapons. PFD-decrypted APP.BIN with '
                 'its exact original PARAM.SFO is required. Finish suspended battles first. '
                 'External console reimport/resigning and edited game loading remain unverified.')
    sample_verified: bool = True
    published_format: bool = True
    game_load_verified: bool = False


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
    if type(game_id) is not str or game_id != GAME_ID:
        raise SaveError('Choose the original US/European DW7 Xtreme Legends PS3 profile.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('APP.BIN')):
    get_format(game_id)
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != REVISION:
        raise SaveError('Requires the 470,303-byte PFD-decrypted DW7 Xtreme Legends '
                        'PS3 APP.BIN revision 0x11080200. Base DW7 and PC saves differ.')
    return Document(FORMAT, Path(source), raw, raw)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            metadata = stream.read(MAX_SFO_SIZE + 1)
    except FileNotFoundError as error:
        raise SaveError('Keep the original BLUS30873-SAVEDATA or BLES01496-SAVEDATA '
                        'PARAM.SFO beside the copied DW7 XL APP.BIN.') from error
    if savedata_directory(metadata) not in TITLE_DIRECTORIES:
        raise SaveError('Requires original US BLUS30873 or European BLES01496 '
                        'DW7 Xtreme Legends metadata; base DW7 and Empires differ.')
    return metadata


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.casefold() != '.bin':
        raise SaveError('Open a separate PFD-decrypted DW7 XL PS3 .bin copy.')
    metadata = context_raw(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), source=path)
    if context_raw(path) != metadata:
        raise SaveError('Original DW7 XL PS3 metadata changed while opening. Reopen the copied export.')
    return replace(document, context_digest=hashlib.sha256(metadata).hexdigest())


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload or not isinstance(document.source, Path)
            or type(document.context_digest) is not str):
        raise SaveError('A frozen original DW7 Xtreme Legends PS3 snapshot is required.')
    decode(document.raw)


def _read16(payload, offset):
    return int.from_bytes(payload[offset:offset + 2], 'big')


@lru_cache(maxsize=4)
def _mapped_fields(payload):
    # A suspended battle has another live copy of parts of officer/equipment
    # state. Inspect it, but require the game to finish it before scalar edits.
    if payload[INTERIM_BASE] != 0:
        return ()
    result = []
    result.append(Field('gold', 'Gold', 0xC7C, 4, 999999))
    for index in range(OFFICER_COUNT):
        base = OFFICER_BASE + OFFICER_STRIDE * index
        for key, label, relative, maximum, minimum in (
                ('health', 'Stored health', 6, 1000, 0),
                ('attack', 'Stored attack', 8, 1400, 1),
                ('defense', 'Stored defense', 10, 1400, 1),
                ('power', 'Stored power', 12, 100, 0),
                ('speed', 'Stored speed', 14, 100, 0),
                ('skill_points', 'Unspent skill points', 26, 9999, 0)):
            result.append(Field(f'officer_{index}_{key}',
                                f'Officer {index + 1}: {label}',
                                base + relative, 2, maximum, 'Officers', index + 1, minimum))
        result.append(Field(f'officer_{index}_active_weapon',
                            f'Officer {index + 1}: Active equipped weapon (0 = first, 1 = second)',
                            base + 22, 2, 1, 'Equipment', index + 1, maxable=False))
    for index in range(WEAPON_COUNT):
        base = WEAPON_BASE + WEAPON_STRIDE * index
        flags, meter = _read16(payload, base + 4), _read16(payload, base + 6)
        # Native negative meter updates do not award a seal. Learned, unowned
        # and unknown flag combinations cannot enter this writer.
        if flags == 1 and 1 <= meter <= 1000:
            result.append(Field(f'weapon_{index}_seal_meter',
                                f'Weapon record {index + 1}: Seal learning meter (decrease only)',
                                base + 6, 2, meter, 'Seal learning', index + 1, maxable=False))
    return tuple(result)


def fields_for(document):
    validate_document(document)
    return _mapped_fields(document.payload)


@lru_cache(maxsize=4)
def _field_index(payload):
    return MappingProxyType({field.id: field for field in _mapped_fields(payload)})


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def _validate_active_weapon(document, field, value):
    field.validate(value)
    base = OFFICER_BASE + (field.slot - 1) * OFFICER_STRIDE
    reference = _read16(document.payload, base + 18 + value * 2)
    if reference >= WEAPON_COUNT:
        raise SaveError('The selected equipped weapon reference is empty or unsupported.')
    flags = _read16(document.payload, WEAPON_BASE + WEAPON_STRIDE * reference + 4)
    if not flags & 1:
        raise SaveError('The selected equipped weapon is not owned in this save.')


def changed_payload(document, changes):
    mapping = field_map(document)
    changes = normalize_pending_values(document, changes, mapping)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = mapping[key]
        if key.endswith('_active_weapon'):
            _validate_active_weapon(document, field, value)
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    reopened = decode(payload, source=document.source)
    if reopened.payload != payload:
        raise SaveError('The edited DW7 XL PS3 copy failed native read-back.')
    return payload


def stage(document, changes, key, value):
    mapping = field_map(document)
    changes = normalize_pending_values(document, changes, mapping)
    changed_payload(document, changes)
    if type(key) is not str or key not in mapping:
        raise SaveError('This field is not qualified for the opened DW7 XL PS3 copy.')
    result = dict(changes)
    field = mapping[key]
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        if key.endswith('_active_weapon'):
            _validate_active_weapon(document, field, value)
        result[key] = value
    changed_payload(document, result)
    return result


def limit_values(document, changes, keys):
    keys = tuple(keys)
    mapping = field_map(document)
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in mapping:
            raise SaveError('This field is not qualified for the opened DW7 XL PS3 copy.')
    result = {}
    for key in keys:
        field = mapping[key]
        opened = field.value(document.payload)
        current = changes.get(key, opened)
        if (field.maxable and field.minimum <= opened <= field.maximum
                and field.minimum <= current <= field.maximum):
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    mapping = field_map(document)
    changes = normalize_pending_values(document, changes, mapping)
    result = dict(changes)
    keys = tuple(key for key, field in mapping.items() if group is None or field.group == group)
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def review(document, changes):
    mapping = field_map(document)
    changes = normalize_pending_values(document, changes, mapping)
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in mapping.values() if field.id in changes]


def field_options(document, field):
    mapping = field_map(document)
    key = field.id if isinstance(field, Field) else field
    if type(key) is not str or key not in mapping:
        raise SaveError('Choose a qualified DW7 XL PS3 field.')
    if not key.endswith('_active_weapon'):
        return ()
    mapped = mapping[key]
    base = OFFICER_BASE + (mapped.slot - 1) * OFFICER_STRIDE
    options = []
    for value, label in ((0, 'First equipped weapon'), (1, 'Second equipped weapon')):
        try:
            _validate_active_weapon(document, mapped, value)
        except SaveError:
            continue
        reference = _read16(document.payload, base + 18 + value * 2)
        options.append((value, f'{label} · inventory record {reference + 1}'))
    return tuple(options)


def record_label(slot, group='Officers'):
    if group in ('Officers', 'Equipment') and type(slot) is int and 1 <= slot <= OFFICER_COUNT:
        return f'Officer slot {slot}'
    return group if not slot else f'{group} record {slot}'


def field_hint(document, field):
    mapping = field_map(document)
    key = field.id if isinstance(field, Field) else field
    if type(key) is not str or key not in mapping:
        raise SaveError('Choose a qualified DW7 XL PS3 field.')
    if key.endswith('_active_weapon'):
        return ('Choose one of the two already equipped weapon references; the selected '
                'inventory record must be owned. Weapon identity, ownership and seals are preserved.')
    if key.endswith('_seal_meter'):
        return ('Decrease the opened owned, unlearned seal meter. Unknown flag combinations and '
                'learned records are read only; no upward threshold or seal reward is granted.')
    if key == 'gold':
        return ('Spendable Gold, 0 through 999,999, qualified directly by the original PS3 native '
                'setter and validator. Lifetime earnings, story progress and reward flags are preserved.')
    return ('Original PS3 native setter/validator bounds: health 0–1,000; attack/defense 1–1,400; '
            'power/speed 0–100; unspent skill points 0–9,999. Max preserves unusual higher originals. '
            'Officer identities, purchased skill bits, EXP/level, equipment and story remain unchanged.')


def inspection_rows(document):
    validate_document(document)
    rows = []
    if document.payload[INTERIM_BASE] != 0:
        rows.append({'group': 'Status', 'label': 'Suspended battle',
                     'value': 'Finish the suspended battle in-game before editing this copy.'})
    for index in range(OFFICER_COUNT):
        base = OFFICER_BASE + OFFICER_STRIDE * index
        refs = tuple(_read16(document.payload, base + relative) for relative in (18, 20))
        def reference(value):
            return ('Empty' if value == 65535 else f'Weapon record {value + 1}'
                    if value < WEAPON_COUNT else f'Unknown ID {value}')
        rows.append({'group': 'Equipment', 'label': f'Officer slot {index + 1}',
                     'value': f'First: {reference(refs[0])}; second: {reference(refs[1])}; '
                              f'active slot: {_read16(document.payload, base + 22) + 1}; '
                              f'guardian ID: {_read16(document.payload, base + 24)}'})
        rows.append({'group': 'Purchased skills', 'label': f'Officer slot {index + 1}',
                     'value': f'0x{_read16(document.payload, base + 16):04X} (read only)'})
    return tuple(rows)


def weapons(document):
    validate_document(document)
    result = []
    for index in range(WEAPON_COUNT):
        base = WEAPON_BASE + WEAPON_STRIDE * index
        flags = _read16(document.payload, base + 4)
        result.append({'slot': index + 1, 'owned': bool(flags & 1), 'flags': flags,
                       'seal_meter': _read16(document.payload, base + 6)})
    return tuple(result)


_storage = PS3CopyStorage(GAME_ID, SAVE_SIZE, validate_document, context_raw,
                          decode, read_save, serialize)
backup = _storage.backup
save_as = _storage.save_as
restore = _storage.restore
prepare_copy_context = _storage.prepare_copy_context
prepare_self_test_copy = _storage.prepare_self_test_copy

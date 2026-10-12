"""Qualified native Windows DW7 XL Definitive Edition scalar backend.

Offsets are serialized PC payload positions, proven against native serialization
and a freely shared genuine PC save. See DYNASTY_RESEARCH.md for evidence and
coverage. No console conversion, guessed levels or story-unlock writes.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
import koei_editor.games.dw7xl.dw7xl_codec as codec
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.save_safety import safe_path


GAME_ID = 'dw7xl'
SAVE_SIZE = codec.SAVE_SIZE
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0x2039, 0x80, 65
SERIALIZED_OFFICER_COUNT = 92
WEAPON_BASE, WEAPON_STRIDE, WEAPON_COUNT = 0x4E39, 20, 1738


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
    sample_verified: bool = True


_fields = [Field('gold', 'Gold', 0xC7C, 4, 999999)]
for _index in range(OFFICER_COUNT):
    for _key, _label, _relative, _maximum, _minimum in (
            ('health', 'Health', 6, 1000, 0),
            ('attack', 'Attack', 8, 1400, 1),
            ('defense', 'Defense', 10, 1400, 1),
            ('power', 'Power', 12, 100, 0),
            ('speed', 'Speed', 14, 100, 0),
            ('skill_points', 'Skill points', 26, 9999, 0)):
        _fields.append(Field(f'officer_{_index}_{_key}',
                             f'Officer {_index + 1}: {_label}',
                             OFFICER_BASE + OFFICER_STRIDE * _index + _relative,
                             2, _maximum, 'Officers', _index + 1, _minimum))
    _fields.append(Field(f'officer_{_index}_active_weapon',
                         f'Officer {_index + 1}: Active weapon (0 = first, 1 = second)',
                         OFFICER_BASE + OFFICER_STRIDE * _index + 22,
                         2, 1, 'Equipment', _index + 1, maxable=False))

FORMAT = Format(
    GAME_ID, 'Dynasty Warriors 7: Xtreme Legends Definitive Edition (PC)',
    SAVE_SIZE, tuple(_fields),
    'Qualified native PC revision 0x11080200. Gold and 65 playable officer '
    'health, attack, defense, power, speed and skill points. '
    'Switch between already equipped owned weapons; inspect inventory, '
    'purchased skill bits and guardian beast references; reduce existing unlearned seal meters. '
    'Progression, story and rewards are preserved. '
    'Genuine PC file roundtrips verified; edited game loading remains untested.'
)
FIELD_MAP = MappingProxyType({field.id: field for field in FORMAT.fields})


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
        raise SaveError('This adapter handles native PC DW7 XL Definitive Edition only.')
    return FORMAT


@lru_cache(maxsize=4)
def _decode_snapshot(raw):
    # Immutable snapshots may be inspected hundreds of times while rendering
    # the GUI; cache only four complete validated byte snapshots, never paths.
    return codec.decode(raw)


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    layout = get_format(game_id)
    frozen = codec._bytes(raw, 'DW7 XL Definitive Edition PC save', SAVE_SIZE)
    payload, seed = _decode_snapshot(frozen)
    return Document(layout, Path(source), frozen, payload, seed)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native PC .dat save copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError('A frozen native PC DW7 XL document is required.')
    payload, seed = _decode_snapshot(document.raw)
    if payload != document.payload or type(document.seed) is not int or seed != document.seed:
        raise SaveError('The opened DW7 XL snapshot was changed outside the edit workflow.')


def fields_for(document):
    validate_document(document)
    return _mapped_fields(document.payload)


@lru_cache(maxsize=4)
def _mapped_fields(payload):
    fields = list(FORMAT.fields)
    for weapon in range(WEAPON_COUNT):
        offset = WEAPON_BASE + weapon * WEAPON_STRIDE
        flags = int.from_bytes(payload[offset + 4:offset + 6], 'little')
        meter = int.from_bytes(payload[offset + 6:offset + 8], 'little')
        # Native negative learning adjustment changes the meter alone. Keep
        # already learned records and unknown flag bits out of this writer:
        # the system seal acquisition/reward path is a separate transaction.
        if flags == 1 and 1 <= meter <= 1000:
            fields.append(Field(f'weapon_{weapon}_seal_meter',
                                f'Weapon record {weapon + 1}: Seal learning meter (decrease only)',
                                offset + 6, 2, meter, 'Seal learning', weapon + 1,
                                maxable=False))
    return tuple(fields)


@lru_cache(maxsize=4)
def _field_index(payload):
    return MappingProxyType({field.id: field for field in _mapped_fields(payload)})


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def changed_payload(document, changes):
    validate_document(document)
    mapping = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapping:
            raise SaveError('The requested field is not mapped for DW7 XL PC.')
        field = mapping[key]
        # An existing unusual value may be unstaged and preserved unchanged.
        if type(value) is int and value == field.value(document.payload):
            continue
        if key.endswith('_active_weapon'):
            _validate_active_weapon(document, field, value)
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = codec.encode(payload, document.seed)
    if decode(raw, GAME_ID, document.source).payload != payload:
        raise SaveError('DW7 XL PC edited copy verification failed.')
    return raw


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapping = field_map(document)
    changed_payload(document, changes)
    if key not in mapping:
        raise SaveError('The requested field is not mapped for DW7 XL PC.')
    field = mapping[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        if key.endswith('_active_weapon'):
            _validate_active_weapon(document, field, value)
        result[key] = value
    changed_payload(document, result)
    return result


def _validate_active_weapon(document, field, value):
    field.validate(value)
    officer = OFFICER_BASE + (field.slot - 1) * OFFICER_STRIDE
    reference = int.from_bytes(document.payload[officer + 18 + 2 * value:
                                                officer + 20 + 2 * value], 'little')
    if reference >= WEAPON_COUNT:
        raise SaveError('The selected equipped weapon slot is empty or unsupported.')
    flags = int.from_bytes(document.payload[WEAPON_BASE + reference * WEAPON_STRIDE + 4:
                                           WEAPON_BASE + reference * WEAPON_STRIDE + 6], 'little')
    if not flags & 1:
        raise SaveError('The selected equipped weapon is not owned in this save.')


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapping = field_map(document)
    changed_payload(document, changes)
    result = {}
    for key in keys:
        if key not in mapping:
            raise SaveError('The requested field is not mapped for DW7 XL PC.')
        field = mapping[key]
        current = changes.get(key, field.value(document.payload))
        original = field.value(document.payload)
        if (field.maxable and field.minimum <= original <= field.maximum
                and field.minimum <= current <= field.maximum):
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
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination.')
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
    read_save(backup_path, game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='Officers'):
    if group in ('Officers', 'Equipment') and type(slot) is int and 1 <= slot <= OFFICER_COUNT:
        return f'Officer slot {slot}'
    return group if not slot else f'{group} record {slot}'


def inspection_rows(document):
    validate_document(document)
    payload = document.payload
    rows = []
    for index in range(OFFICER_COUNT):
        offset = OFFICER_BASE + OFFICER_STRIDE * index
        read16 = lambda relative: int.from_bytes(payload[offset + relative:offset + relative + 2], 'little')
        refs = [read16(18), read16(20)]
        reference = lambda value: ('Empty' if value == 65535 else f'Weapon record {value + 1}'
                                   if value < WEAPON_COUNT else f'Unknown ID {value}')
        beast = read16(24)
        rows.append({'group': 'Equipment', 'label': f'Officer slot {index + 1}',
                     'value': f'Weapon 1: {reference(refs[0])}; weapon 2: {reference(refs[1])}; '
                              f'active slot: {read16(22) + 1}; guardian: '
                              + ('Red Hare (ID 7)' if beast == 7 else f'ID {beast}')})
        rows.append({'group': 'Purchased skills', 'label': f'Officer slot {index + 1}',
                     'value': f'Purchased skill bits: 0x{read16(16):04X} (read only)'})
    return tuple(rows)


def weapons(document):
    """Native serialized inventory; no inferred weapon names or seal rewards."""
    validate_document(document)
    rows = []
    for index in range(WEAPON_COUNT):
        offset = WEAPON_BASE + index * WEAPON_STRIDE
        flags = int.from_bytes(document.payload[offset + 4:offset + 6], 'little')
        rows.append({'slot': index + 1, 'owned': bool(flags & 1), 'flags': flags,
                     'seal_meter': int.from_bytes(document.payload[offset + 6:offset + 8], 'little')})
    return tuple(rows)


def field_hint(document, field):
    mapping = field_map(document)
    key = field.id if isinstance(field, Field) else field
    if key not in mapping:
        raise SaveError('The requested field is not mapped for DW7 XL PC.')
    if key.endswith('_seal_meter'):
        return ("Decrease an existing owned, unlearned weapon's learning meter, "
                '0 through its opened value. No threshold is crossed upward and no seal '
                'is acquired. Ownership, learned bits and system seal rewards remain '
                'unchanged. Unknown flags and learned records stay read only; excluded from Max.')
    if key == 'gold':
        return 'Gold cap 999,999 is checked by the native PC save reader. Story and rewards stay separate.'
    if key.endswith('_active_weapon'):
        return ('0 selects the first already equipped weapon; 1 selects the second. '
                'The selected reference must point to an owned weapon record. '
                'Max excludes this choice. No weapon is granted and seal progress stays unchanged.')
    if key.endswith('_skill_points'):
        return ('Spendable officer skill points (0..9,999). Purchased skill bits and their '
                'prerequisites are preserved; use the game to purchase skills.')
    return ('Native PC reader bounds: health 0..1,000; attack/defense 1..1,400; '
            'power/speed 0..100. Max preserves higher existing values. '
            'Weapon seals, titles, historical totals and story clears remain unchanged.')


def field_options(document, field):
    """Existing equipped choices, with the same ownership guard as staging."""
    mapping = field_map(document)
    key = field.id if isinstance(field, Field) else field
    if type(key) is not str:
        raise SaveError('Choose a mapped DW7 XL field name.')
    if key not in mapping:
        raise SaveError('The requested field is not mapped for DW7 XL PC.')
    if not key.endswith('_active_weapon'):
        return ()
    mapped = mapping[key]
    start = OFFICER_BASE + (mapped.slot - 1) * OFFICER_STRIDE
    options = []
    for value, name in ((0, 'First equipped weapon'), (1, 'Second equipped weapon')):
        try:
            _validate_active_weapon(document, mapped, value)
        except SaveError:
            continue
        reference = int.from_bytes(document.payload[start + 18 + value * 2:
                                                    start + 20 + value * 2], 'little')
        options.append((value, f'{name} · inventory slot {reference + 1}'))
    return tuple(options)

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'

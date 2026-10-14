"""Observed native DW6 Windows PC save profile, with narrow verified edits.

The public research documents direct save.dat edits and successful game reloads
for playable unlocks and horse combat stats. An independently downloaded native
save corroborates the profile. No upstream parser code is incorporated.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.verified_editor import Field
from koei_editor.games.dw6.dw6_metadata import OFFICER_NAMES, WEAPON_NAMES, ELEMENT_NAMES

GAME_ID = 'dw6'
SAVE_SIZE = 212248
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 2904, 168, 41
HORSE_BASE, HORSE_STRIDE, HORSE_COUNT = 10784, 60, 8
HORSE_STATS = (('speed', 'Speed', 16), ('attack', 'Attack', 24),
               ('jump', 'Jump', 28), ('destruction', 'Destruction', 32))
WEAPON_COUNT, WEAPON_STRIDE, WEAPON_RELATIVE_BASE = 8, 16, 8
WEAPON_ELEMENT_CHOICES = ((0, 'Fire'), (1, 'Ice'), (2, 'Lightning'), (3, 'No element'))


def _u32(payload, offset):
    return struct.unpack_from('<I', payload, offset)[0]


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


_UNLOCK_FIELDS = tuple(
    Field(f'officer_{i}_unlocked', 'Playable (1 unlock)',
          OFFICER_BASE + i * OFFICER_STRIDE + 164, 1, 1,
          'Unlocks', i + 1, maxable=False, experimental=False) for i in range(OFFICER_COUNT))
_HORSE_FIELDS = tuple(
    Field(f'horse_{i}_{key}', label, HORSE_BASE + i * HORSE_STRIDE + relative,
          4, 500, 'Horses', i + 1)
    for i in range(HORSE_COUNT) for key, label, relative in HORSE_STATS)
FORMAT = Format(GAME_ID, 'Dynasty Warriors 6 (PC)', SAVE_SIZE,
                _UNLOCK_FIELDS + _HORSE_FIELDS,
                'Observed 212,248-byte native PC profile with canonical officer identities. '
                'One-way playable unlocks, qualified existing horse combat stats and '
                'individual element choices and manual stored damage bonuses on existing known weapons. '
                'Officer progression, equipment and story remain read only. '
                'Genuine sample parsing is verified; edited game-load validation has not '
                'been performed by this project.')


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
        raise SaveError('Select the Dynasty Warriors 6 Windows PC adapter.')
    return FORMAT


@lru_cache(maxsize=8)
def _validate_raw(raw):
    if len(raw) != SAVE_SIZE:
        raise SaveError('Unsupported DW6 PC file size; the observed native profile is 212,248 bytes.')
    if any(_u32(raw, OFFICER_BASE + i * OFFICER_STRIDE + 136) != i
           for i in range(OFFICER_COUNT)):
        raise SaveError('Unsupported DW6 PC officer identity/layout; console saves and reassigned identities are not supported.')


def decode(raw, game_id=GAME_ID, source=None):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise SaveError('DW6 PC input must be save bytes.')
    byte_count = raw.nbytes if isinstance(raw, memoryview) else len(raw)
    if byte_count != SAVE_SIZE:
        raise SaveError('Unsupported DW6 PC file size; the observed native profile is 212,248 bytes.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source) if source is not None else Path('memory.dat'), raw, raw)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('A preserved native DW6 PC snapshot is required.')
    _validate_raw(document.raw)


def _horse_qualified(payload, index):
    base = HORSE_BASE + index * HORSE_STRIDE
    # These observed ordinary-horse types and nonempty stat records corroborate
    # occupancy. Unknown/empty variants remain read only, never manufactured.
    return (_u32(payload, base + 4) in (60, 61, 64)
            and _u32(payload, base + 20) > 0
            and all(_u32(payload, base + rel) > 0 for _, _, rel in HORSE_STATS))


@lru_cache(maxsize=8)
def _fields(payload):
    elements = []
    for officer in range(OFFICER_COUNT):
        base = OFFICER_BASE + officer * OFFICER_STRIDE + WEAPON_RELATIVE_BASE
        for weapon in range(WEAPON_COUNT):
            offset = base + weapon * WEAPON_STRIDE
            identity, element = _u32(payload, offset), _u32(payload, offset + 8)
            if identity < len(WEAPON_NAMES) and element in (0, 1, 2, 3):
                elements.append(Field(f'officer_{officer}_weapon_{weapon}_damage_bonus',
                                      f'{WEAPON_NAMES[identity]}: Stored damage bonus (manual)',
                                      offset + 4, 4, 0xffffffff, 'Weapon bonuses',
                                      officer * WEAPON_COUNT + weapon + 1, maxable=False))
                elements.append(Field(f'officer_{officer}_weapon_{weapon}_element',
                                      f'{WEAPON_NAMES[identity]}: Element', offset + 8,
                                      4, 3, 'Weapon elements', officer * WEAPON_COUNT + weapon + 1,
                                      maxable=False, experimental=False))
    return tuple(field for field in _UNLOCK_FIELDS
                 if field.value(payload) in (0, 1)) + tuple(
        field for field in _HORSE_FIELDS if _horse_qualified(payload, field.slot - 1)) + tuple(elements)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def _validate_edit(field, value, original):
    if type(value) is not int:
        raise SaveError('A whole-number edit value is required.')
    # Reassigning an unusual opened value must undo an edit without normalizing it.
    if value == original:
        return
    field.validate(value)
    if field.group == 'Unlocks' and value != original and value != 1:
        raise SaveError('Playable unlocks are one-way; relocking officers is unavailable.')


def stage(document, changes, key, value):
    changed_payload(document, changes)
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('The requested record is not qualified for DW6 PC editing.')
    original = field.value(document.payload)
    _validate_edit(field, value, original)
    result = dict(changes)
    if value == original:
        result.pop(key, None)
    else:
        result[key] = value
    return result


def changed_payload(document, changes):
    mapped = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = mapped.get(key)
        if field is None:
            raise SaveError('The requested record is not qualified for DW6 PC editing.')
        _validate_edit(field, value, field.value(document.payload))
        result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    raw = bytes(result)
    _validate_raw(raw)
    return raw


def serialize(document, changes):
    return changed_payload(document, changes)


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapped = field_map(document)
    result = {}
    for key in keys:
        if key not in mapped:
            raise SaveError('The requested record is not qualified for DW6 PC editing.')
        field = mapped[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and type(current) is int and field.minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    result = dict(changes)
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def unlock_values(document):
    return {field.id: 1 for field in fields_for(document)
            if field.group == 'Unlocks' and field.value(document.payload) == 0}


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Unlocks'):
    if group in ('Unlocks', 'Officers') and 1 <= slot <= OFFICER_COUNT:
        return OFFICER_NAMES[slot - 1]
    if group in ('Weapon elements', 'Weapon bonuses') and type(slot) is int and 1 <= slot <= OFFICER_COUNT * WEAPON_COUNT:
        officer, weapon = divmod(slot - 1, WEAPON_COUNT)
        return f'{OFFICER_NAMES[officer]} / weapon {weapon + 1}'
    return f'Horse slot {slot}' if group == 'Horses' else group


def field_options(document, field):
    """Optional choice metadata; the backend validates every value independently."""
    key = field.id if isinstance(field, Field) else field
    if type(key) is not str:
        raise SaveError('Choose a mapped DW6 field name.')
    mapped = field_map(document).get(key)
    if mapped is None:
        raise SaveError('The requested DW6 field is not editable.')
    return WEAPON_ELEMENT_CHOICES if mapped.group == 'Weapon elements' else ()


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    mapped = field_map(document)[key]
    if mapped.group == 'Unlocks':
        return ('Set 1 to unlock this playable officer. Use the separate content-unlock '
                'action for all qualified officers. Story completion, level, EXP, '
                'skill tree and existing weapon inventory are preserved.')
    if mapped.group == 'Weapon elements':
        return ('Existing weapon element: 0 Fire, 1 Ice, 2 Lightning, 3 no element. '
                'This is a choice, so Max leaves it unchanged. Weapon identity, damage '
                'bonus, skill mask, inventory and officer progression are preserved.')
    if mapped.group == 'Weapon bonuses':
        return ('Stored damage bonus over this existing weapon\'s base damage; not total attack. '
                'Manual unsigned 32-bit storage bounds only: the tentative published value 32 '
                'is not a proven natural cap. Max leaves it unchanged. Identity, element, '
                'skills, inventory, level and rewards are preserved.')
    return ('Existing horse combat stat; 500 is the documented effective upper limit. '
            'Max preserves higher existing values. EXP, growth descriptors, model, '
            'element, skill mask and the unqualified adjacent stat are preserved.')


def inspection_rows(document):
    validate_document(document)
    payload = document.payload
    rows = []
    for index, name in enumerate(OFFICER_NAMES):
        base = OFFICER_BASE + index * OFFICER_STRIDE
        rows.append({'group': 'Officers', 'label': name,
                     'value': f'Stored level index {_u32(payload, base + 148)}; '
                              f'EXP {_u32(payload, base + 152):,}; '
                              f'kills {_u32(payload, base + 156):,}; '
                              f'title ID {_u32(payload, base + 144)}; '
                              f'outfit {_u32(payload, base + 140)}; '
                              f'playable value {payload[base + 164]}; '
                              f'skill-tree bytes {payload[base:base + 8].hex(" ")}'})
        for weapon in range(8):
            offset = base + 8 + weapon * 16
            identity, bonus, element, skills = struct.unpack_from('<4I', payload, offset)
            if identity == 174:
                continue
            label = WEAPON_NAMES[identity] if identity < len(WEAPON_NAMES) else f'Unknown weapon ID {identity}'
            element_name = ELEMENT_NAMES[element] if element < len(ELEMENT_NAMES) else f'Unknown {element}'
            rows.append({'group': 'Weapons', 'label': f'{name} / slot {weapon + 1}: {label}',
                         'value': f'ID {identity}; raw damage bonus {bonus}; '
                                  f'element {element_name}; skill mask 0x{skills:08X}'})
    for index in range(HORSE_COUNT):
        base = HORSE_BASE + index * HORSE_STRIDE
        stats = '; '.join(f'{label} {_u32(payload, base + rel)}' for _, label, rel in HORSE_STATS)
        rows.append({'group': 'Horses', 'label': f'Horse slot {index + 1}',
                     'value': f'EXP {_u32(payload, base)}; type {_u32(payload, base + 4)}; '
                              f'element ID {_u32(payload, base + 8)}; '
                              f'skill mask 0x{_u32(payload, base + 12):08X}; {stats}; '
                              f'adjacent value {_u32(payload, base + 20)}; '
                              f'qualified for stats: {_horse_qualified(payload, index)}'})
    return tuple(rows)

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'none'

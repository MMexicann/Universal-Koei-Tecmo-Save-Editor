"""Conservative source-backed decrypted export adapter; no console crypto.

Mappings and exclusions are documented in docs/FIRE_EMBLEM_WARRIORS_FORMAT.md. The native
export remains immutable; serialization only touches staged, qualified scalars.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.save_safety import safe_path
from koei_editor.games.fire_emblem_warriors.catalog import MATERIALS, WEAPONS, SEALS, CHARACTERS

GAME_ID = 'fire_emblem_warriors'
TITLE = 'Fire Emblem Warriors'
SAVE_SIZE = 0x172AC
EXTENSION = ''
BYTEORDER = 'little'
# Published decrypted export readers/writers use no mapped checksum layer.
INTEGRITY_KIND = 'none'
LAYOUT_MARKER = bytes.fromhex('13000000')
GOLD_OFFSET = 0x32C


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

    @property
    def experimental_maximum(self):
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], BYTEORDER)

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = (Field('gold', 'Gold', GOLD_OFFSET, 4, 9_999_999, maxable=False),)
    sample_verified: bool = True
    note: str = ('Nintendo Switch 1.5.0-layout extensionless scenario0/1/2 export. '
                 'Open a separate copy outside console-managed folders; keep system unchanged. '
                 'Save As creates a new export copy with backup.')

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
        raise SaveError(f'Choose the explicit {TITLE} platform adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('scenario0')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SAVE_SIZE:
        raise SaveError(f'{TITLE} requires a complete {SAVE_SIZE:,}-byte decrypted native export.')
    raw = bytes(raw)
    if raw[:4] != LAYOUT_MARKER or int.from_bytes(raw[4:8], 'little') != SAVE_SIZE:
        raise SaveError(f'{TITLE} export does not match the source-reference layout marker.')
    return Document(FORMAT, Path(source), raw, raw)


def _copy_path(path):
    return safe_path(path)


def _extension(path):
    if Path(path).suffix.casefold() != EXTENSION:
        raise SaveError('Use a separate extensionless Switch scenario copy outside console-managed folders.')


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    _extension(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format != FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError(f'Invalid immutable {TITLE} snapshot.')
    original = decode(document.raw, GAME_ID, document.source)
    if original.payload != document.payload:
        raise SaveError('The opened snapshot changed outside the edit workflow.')


def _uint(payload, offset, size):
    return int.from_bytes(payload[offset:offset + size], BYTEORDER)


# Generic E through S weapons have independently described 0–5 star quality.
# Unique/amiibo weapons use badge/scroll/opus power tiers, not qualified stars.
GENERIC_WEAPONS = frozenset((0, 1, 2, 3, 4, 0x72, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x73,
                           0x23, 0x24, 0x25, 0x26, 0x27, 0x74, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x75,
                           0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x76, 0x43, 0x44, 0x45, 0x46, 0x47, 0x77))
# Independently corroborated game mechanic caps, not editor cheat targets.
# Non-sealed attributes, amiibo powers and unique-weapon progression stay opaque.
ORDINARY_SEAL_CAPS = MappingProxyType({23: 2000, 24: 2000, 25: 2000,
    26: 5000, 27: 5000, 28: 5000, 29: 5000, 30: 5000, 31: 5000,
    37: 3000, 38: 2500, 47: 4000, 48: 4000})
WEAPON_OFFSET, WEAPON_STRIDE, WEAPON_COUNT = 0x127AC, 0x20, 600



def _ordinary(name):
    return not any(word in name for word in ('Scroll', 'Opus', 'Essence', 'Master Seal'))


def _inspection(payload):
    rows = [{'group': 'Ordinary materials' if _ordinary(name) else 'Special items (read only)',
             'label': name, 'value': _uint(payload, offset, 2)} for offset, name in MATERIALS]
    for index, name in enumerate(CHARACTERS):
        offset = 0xFF0C + index * 0xD4
        rows.extend(({'group': 'Characters', 'label': name + ': stored EXP (read only)',
                      'value': _uint(payload, offset, 4)},
                     {'group': 'Characters', 'label': name + ': stored level (read only)',
                      'value': payload[offset + 4] + 1}))
    return tuple(rows)


def _weapons(payload):
    rows = []
    for slot in range(WEAPON_COUNT):
        offset = WEAPON_OFFSET + slot * WEAPON_STRIDE
        identity = _uint(payload, offset + 24, 2)
        if identity == 0xFFFF:
            continue
        rows.append({'slot': slot + 1, 'offset': offset, 'identity': identity,
                     'name': WEAPONS.get(identity, f'Unknown weapon ID {identity}'),
                     'stars': payload[offset + 26], 'bonus': payload[offset + 28],
                     'attributes': tuple(payload[offset + 16:offset + 24]),
                     'kos': tuple(_uint(payload, offset + i * 2, 2) for i in range(8))})
    return tuple(rows)


def weapons(document):
    validate_document(document)
    return _weapons(document.payload)


@lru_cache(maxsize=4)
def _field_index(payload):
    fields = list(FORMAT.fields)
    for offset, name in MATERIALS:
        # No independently mapped discovery bitset. Require an existing positive
        # ordinary drop; exhausted and special progression items stay read-only.
        if _ordinary(name) and _uint(payload, offset, 2) > 0:
            fields.append(Field(f'material_{offset}', name, offset, 2, 999,
                                'Ordinary materials', offset, maxable=False))
    for weapon in _weapons(payload):
        if weapon['identity'] not in WEAPONS:
            continue
        slot, offset = weapon['slot'], weapon['offset']
        if weapon['identity'] in GENERIC_WEAPONS:
            fields.append(Field(f'weapon_{slot}_stars', weapon['name'] + f' (slot {slot}): Stars',
                                offset + 26, 1, 5, 'Weapon stars', slot))
        for index, (identity, remaining) in enumerate(zip(weapon['attributes'], weapon['kos'])):
            # True Power/Legendary require unique-weapon badge/scroll/opus flags.
            # Unknown/empty/unused attributes stay opaque. Positive existing
            # counters stay readable after experimental numeric edits.
            if identity in ORDINARY_SEAL_CAPS and remaining > 0:
                fields.append(Field(f'weapon_{slot}_seal_{index + 1}_kos',
                    weapon['name'] + f' (slot {slot}), ' + SEALS[identity] + ': Remaining KOs',
                    offset + index * 2, 2, remaining, 'Ordinary seal KOs',
                    slot * 8 + index, maxable=False))
    return MappingProxyType({field.id: field for field in fields})


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document, changes):
    fields = field_map(document)
    output = bytearray(document.payload)
    for key, value in changes.items():
        if key not in fields:
            raise SaveError('This field or existing record is not qualified for edits.')
        field = fields[key]
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, BYTEORDER)
    return bytes(output)


def serialize(document, changes):
    raw = changed_payload(document, changes)
    if decode(raw, GAME_ID, document.source).payload != raw:
        raise SaveError('Edited export failed read-back verification.')
    return raw


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    fields = field_map(document)
    if key not in fields:
        raise SaveError('This field or existing record is not qualified for edits.')
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    changed_payload(document, changes)
    fields = field_map(document)
    result = {}
    for key in keys:
        if key not in fields:
            raise SaveError('This field is not qualified for edits.')
        field = fields[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and type(current) is int and field.minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changes = normalize_pending_values(document, changes, field_map(document))
    result = dict(changes)
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    source = _copy_path(document.source)
    return snapshot_backup(document.raw, source, GAME_ID, source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    destination = _copy_path(destination)
    _extension(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    validate_document(document)
    with _copy_path(document.source).open('rb') as stream:
        current = stream.read(SAVE_SIZE + 1)
    if current != document.raw:
        raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(_copy_path(backup_path), _copy_path(destination), GAME_ID,
                            EXTENSION, SAVE_SIZE, validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Resources'):
    return f'{group} record {slot}' if slot else group


def field_hint(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('This field is not qualified for edits.')
    if key.endswith('_kos'):
        return ('Remaining KOs for an existing ordinary attribute seal: decrease only; '
                '0 unseals it. True Power/Legendary and all identity/badge flags are preserved. '
                'Excluded from Max. Console game-load validation is unperformed.')
    return ('Qualified existing ordinary resource or weapon stars. Max applies only to generic weapon stars and preserves higher opened values. '
            'Special items, character growth, ownership, forging attributes and story remain preserved. '
            'Nintendo Switch native export; edited console game-load validation is unperformed.')


def inspection_rows(document):
    validate_document(document)
    return _inspection(document.payload)

"""Conservative source-backed decrypted export adapter; no console crypto.

Mappings and exclusions are documented in docs/HYRULE_FORMATS.md. The native
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
from koei_editor.games.age_of_calamity.catalog import MATERIALS, WEAPONS, SEALS

GAME_ID = 'age_of_calamity'
TITLE = 'Hyrule Warriors: Age of Calamity'
SAVE_SIZE = 0x100000
EXTENSION = ''
BYTEORDER = 'little'
# Published decrypted export readers/writers use no mapped checksum layer.
INTEGRITY_KIND = 'none'
LAYOUT_MARKER = bytes.fromhex('89000000')
RUPEES_OFFSET = 0x2C3A4


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
    structural_maximum: int | None = None

    @property
    def experimental_maximum(self):
        if self.group == 'Weapon protection':
            return None
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], BYTEORDER)

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')
        if self.structural_maximum is not None and value > self.structural_maximum:
            raise SaveError('Carried rupees cannot exceed the preserved lifetime earned total.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = (Field('rupees', 'Rupees', RUPEES_OFFSET, 4, 9_999_999),)
    sample_verified: bool = True
    note: str = ('Nintendo Switch svdt, source-mapped 1.3.0 layout marker 89000000. Independently shared native-export roundtrip checked; '
                 'edited console game-load/re-save validation is unperformed. '
                 'Ownership, unknown data and story are preserved.')

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


def decode(raw, game_id=GAME_ID, source=Path('svdt')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SAVE_SIZE:
        raise SaveError(f'{TITLE} requires a complete {SAVE_SIZE:,}-byte decrypted native export.')
    raw = bytes(raw)
    if raw[:4] != LAYOUT_MARKER:
        raise SaveError(f'{TITLE} export does not match the source-reference layout marker.')
    return Document(FORMAT, Path(source), raw, raw)


def _copy_path(path):
    return safe_path(path)


def _extension(path):
    if Path(path).suffix.casefold() != EXTENSION:
        raise SaveError('Use a separate Switch extensionless svdt copy outside console-managed folders.')


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    _extension(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (not isinstance(document, Document) or document.format != FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError(f'Invalid immutable {TITLE} snapshot.')
    original = decode(document.raw, GAME_ID, document.source)
    if original.payload != document.payload:
        raise SaveError('The opened snapshot changed outside the edit workflow.')


def _uint(payload, offset, size):
    return int.from_bytes(payload[offset:offset + size], BYTEORDER)


CHARACTERS = ('Link', 'Zelda', 'King Rhoam', 'Mipha', 'Daruk', 'Revali', 'Urbosa',
              'Impa', 'Sidon', 'Yunobo', 'Teba', 'Riju', 'Hestu', 'Great Fairies',
              'Master Kohga', 'Monk Maz Koshia', 'Terrako', 'Calamity Ganon',
              'Battle-Tested Guardian', 'Purah & Robbie', 'Sooga')
CATEGORY_NAMES = {'fruits': 'Fruit', 'mushrooms': 'Mushrooms', 'vegetables': 'Vegetables / wood',
                  'meat': 'Meat', 'ingredients': 'Ingredients', 'fish': 'Fish',
                  'insects': 'Insects', 'minerals': 'Minerals', 'monster': 'Monster parts',
                  'guardian': 'Ancient / Guardian parts', 'trophies': 'Trophies / reports',
                  'special': 'Special collectibles (read only)'}


def _inspection(payload):
    rows = []
    for i, name in enumerate(CHARACTERS):
        rows.append({'group': 'Characters', 'label': name + ': stored level (read only)',
                     'value': payload[0x2BCAD + i * 30] + 1})
    for identity, category, name, cap in MATERIALS:
        rows.append({'group': CATEGORY_NAMES[category], 'label': name,
                     'value': _uint(payload, 0x2C14E + identity * 2, 2)})
    rows.append({'group': 'Resources', 'label': 'Lifetime rupees earned (read only)',
                 'value': _uint(payload, TOTAL_RUPEES_OFFSET, 4)})
    return tuple(rows)

WEAPON_OFFSET, WEAPON_STRIDE, WEAPONS_PER_CHARACTER = 0x11E6, 0x51, 71
TOTAL_RUPEES_OFFSET = 0x3C2BF
SEAL_OFFSETS = (0x28, 0x29, 0x2A, 0x2B, 0x0C, 0x0D)
SEAL_PARAMETER1 = (0x2C, 0x2E, 0x30, 0x32, 0x0E, 0x10)
SEAL_PARAMETER2 = (0x34, 0x36, 0x38, 0x3A, 0x12, 0x14)


def _weapons(payload):
    result = []
    for owner, character in enumerate(CHARACTERS):
        for index in range(WEAPONS_PER_CHARACTER):
            offset = WEAPON_OFFSET + (owner * WEAPONS_PER_CHARACTER + index) * WEAPON_STRIDE
            identity = _uint(payload, offset, 2)
            if not identity:
                continue
            source_owner, name = WEAPONS.get(identity, (None, f'Unknown weapon ID {identity}'))
            seals = tuple((payload[offset + a], _uint(payload, offset + b, 2),
                           _uint(payload, offset + c, 2))
                          for a, b, c in zip(SEAL_OFFSETS, SEAL_PARAMETER1, SEAL_PARAMETER2))
            result.append({'character': character, 'owner': owner, 'source_owner': source_owner,
                'slot': index + 1, 'offset': offset, 'id': identity, 'name': name,
                'level': payload[offset + 2] + 1, 'exp': _uint(payload, offset + 3, 4),
                'quality': payload[offset + 7], 'bonus_power': _uint(payload, offset + 8, 2),
                'level_power': _uint(payload, offset + 10, 2), 'cap_code': payload[offset + 0x1E],
                'rusty': payload[offset + 0x27], 'protected': payload[offset + 0x4C], 'seals': seals})
    return tuple(result)


def weapons(document):
    validate_document(document)
    return _weapons(document.payload)



@lru_cache(maxsize=4)
def _field_index(payload):
    fields = list(FORMAT.fields)
    for identity, category, name, cap in MATERIALS:
        # Preserve discovery/ownership bytes and unknown discovery states.
        # Korok Seeds/Terrako Components/Ethereal Stones have collection/story
        # prerequisites and remain read-only, even when already discovered.
        if category != 'special' and payload[0x2C2DD + identity] == 1:
            fields.append(Field(f'material_{identity}', name, 0x2C14E + identity * 2,
                                2, cap, CATEGORY_NAMES[category], identity + 1))
    # A second source qualifies an earned-total companion. Preserve its history
    # and prevent new edits from exceeding that existing total.
    fields[0] = Field('rupees', 'Rupees (bounded by preserved lifetime total)',
                      RUPEES_OFFSET, 4, min(9_999_999, _uint(payload, TOTAL_RUPEES_OFFSET, 4)),
                      structural_maximum=_uint(payload, TOTAL_RUPEES_OFFSET, 4))
    for weapon in _weapons(payload):
        if (weapon['source_owner'] == weapon['owner'] and '[Broken]' not in weapon['name']
                and weapon['protected'] in (0, 1) and weapon['rusty'] == 0):
            owner, slot = weapon['owner'], weapon['slot']
            fields.append(Field(f'weapon_{owner}_{slot}_protected',
                weapon['character'] + f": {weapon['name']} (slot {slot}): Protected (0/1)",
                weapon['offset'] + 0x4C, 1, 1, 'Weapon protection',
                owner * WEAPONS_PER_CHARACTER + slot, maxable=False))

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
    if key.endswith('_protected'):
        return ('Existing weapon protection flag: 0 permits use as fusion material, '
                '1 protects the weapon. Does not grant weapon ownership or alter stats/seals. '
                'Excluded from Max; unrecognized/rusty/foreign-owner records are inspection only.')
    if GAME_ID == 'age_of_calamity' and key == 'rupees':
        return ('Current rupees: the edit limit is the lesser of 9,999,999 and the opened '
                'lifetime-earned total. History is read only; higher unusual originals survive Max.')
    if key.endswith('_kos'):
        return ('Remaining KOs for this existing ordinary weapon skill seal. Decrease only; '
                '0 unseals the skill. Legendary/Evil\'s Bane and ownership are preserved. '
                'Excluded from Max; original value unstages the edit.')
    return ('Qualified existing resource or weapon record. Ownership, identities, '
            'story and unknown bytes are preserved. Max keeps higher opened values. '
            'Source-backed export layout; edited game loading is untested.')


def inspection_rows(document):
    validate_document(document)
    return _inspection(document.payload)

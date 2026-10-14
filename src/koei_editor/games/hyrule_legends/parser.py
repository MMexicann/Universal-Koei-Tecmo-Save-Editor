"""Conservative source-backed decrypted export adapter; no console crypto.

Mappings and exclusions are documented in docs/HYRULE_LEGENDS_FORMAT.md. The native
export remains immutable; serialization only touches staged, qualified scalars.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.save_safety import safe_path
from koei_editor.games.hyrule_legends.catalog import MATERIALS, FOOD, CHARACTERS, WEAPONS, SKILLS, MAP_CARDS

GAME_ID = 'hyrule_legends'
TITLE = 'Hyrule Warriors Legends'
SAVE_SIZE = 0x39462
EXTENSION = '.bin'
BYTEORDER = 'little'
LAYOUT_MARKER = bytes.fromhex('00261015')
RUPEES_OFFSET = 0xDE


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
    maxable: bool = False
    kind: str = 'integer'

    @property
    def experimental_maximum(self):
        if self.kind == 'text':
            return None
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        raw = payload[self.offset:self.offset + self.size]
        if self.kind == 'text':
            return raw.decode('ascii').split('\0', 1)[0]
        return int.from_bytes(raw, BYTEORDER)

    def validate(self, value):
        if self.kind == 'text':
            if (type(value) is not str or not 1 <= len(value) <= self.maximum
                    or any(not 32 <= ord(char) <= 126 for char in value)):
                raise SaveError(f'{self.label} requires 1–{self.maximum} printable ASCII characters.')
            return
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = (Field('rupees', 'Rupees', RUPEES_OFFSET, 3, 9_999_999),)
    sample_verified: bool = True
    note: str = ('Nintendo 3DS extracted zmha.bin, source-mapped 1.0.0 profile. '
                 'Open a separate copy; Save As creates a new export with backup. '
                 'Ownership, special weapons and story are preserved.')

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


def decode(raw, game_id=GAME_ID, source=Path('zmha.bin')):
    get_format(game_id)
    if type(raw) not in (bytes, bytearray) or len(raw) != SAVE_SIZE:
        raise SaveError(f'{TITLE} requires a complete {SAVE_SIZE:,}-byte decrypted native export.')
    raw = bytes(raw)
    if raw[:4] != LAYOUT_MARKER:
        raise SaveError(f'{TITLE} export does not match the observed Nintendo 3DS layout marker.')
    if raw[4] != 0 or raw[0xD3] & 0x0F != 0:
        raise SaveError('This adapter requires the source-mapped Legends 1.0.0 layout.')
    if int.from_bytes(raw[12:16], 'little') != SAVE_SIZE:
        raise SaveError('The native stored size does not match this export profile.')
    return Document(FORMAT, Path(source), raw, raw)


def _copy_path(path):
    return safe_path(path)


def _extension(path):
    if Path(path).suffix.casefold() != EXTENSION:
        raise SaveError('Use a separate Nintendo 3DS zmha.bin copy outside console-managed folders.')


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    _extension(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError(f'Invalid immutable {TITLE} snapshot.')
    original = decode(document.raw, GAME_ID, document.source)
    if original.payload != document.payload:
        raise SaveError('The opened snapshot changed outside the edit workflow.')


def _uint(payload, offset, size):
    return int.from_bytes(payload[offset:offset + size], BYTEORDER)


WEAPON_BASE, WEAPON_STRIDE, WEAPON_COUNT = 0x2F372, 0x28, 1030
FAIRY_BASE, FAIRY_STRIDE, FAIRY_COUNT = 0x1AEA, 0x98, 14
FAIRY_NAME_DIFF, FAIRY_NAME_SIZE = 0xA, 8


def _fairy_name(raw):
    try:
        name = raw.decode('ascii').split('\0', 1)[0]
    except UnicodeDecodeError:
        return None
    return name if name and all(32 <= ord(char) <= 126 for char in name) else None



def _weapons(payload):
    rows = []
    for index in range(WEAPON_COUNT):
        offset = WEAPON_BASE + index * WEAPON_STRIDE
        identity = _uint(payload, offset + 0x10, 2)
        if identity == 0xFFFF:
            continue
        rows.append({'slot': index + 1, 'offset': offset, 'id': identity,
                     'name': WEAPONS.get(identity, f'Unknown weapon ID {identity}'),
                     'power': _uint(payload, offset + 0x12, 2),
                     'stars': _uint(payload, offset + 0x14, 2),
                     'state': payload[offset + 0x1E],
                     'skills': tuple((payload[offset + 0x16 + i],
                                      _uint(payload, offset + i * 2, 2))
                                     for i in range(8))})
    return tuple(rows)


def weapons(document):
    validate_document(document)
    return _weapons(document.payload)


def _inspection(payload):
    rows = []
    for relative, name in CHARACTERS:
        offset = 0x2EBF2 + relative
        rows.extend((
            {'group': 'Characters', 'label': name + ': stored level index (read only)',
             'value': payload[offset + 0x1A]},
            {'group': 'Characters', 'label': name + ': EXP (read only)',
             'value': _uint(payload, offset + 0x12, 4)},
            {'group': 'Characters', 'label': name + ': unlock flag (read only)',
             'value': payload[offset + 0x0A]},
        ))
    for offset, name in MATERIALS:
        rows.append({'group': 'Material inventory', 'label': name,
                     'value': _uint(payload, offset, 2)})
    for offset, name in MAP_CARDS:
        rows.append({'group': 'Adventure map cards', 'label': name, 'value': payload[offset]})
    for slot in range(FAIRY_COUNT):
        offset = FAIRY_BASE + slot * FAIRY_STRIDE
        if payload[offset] != 1:
            continue
        raw_name = payload[offset + FAIRY_NAME_DIFF:offset + FAIRY_NAME_DIFF + FAIRY_NAME_SIZE]
        name = _fairy_name(raw_name) or 'Unqualified name bytes: ' + raw_name.hex()
        rows.extend((
            {'group': 'My Fairy', 'label': f'Fairy slot {slot + 1}: Name', 'value': name},
            {'group': 'My Fairy', 'label': f'Fairy slot {slot + 1}: Level (read only)', 'value': payload[offset + 0x1B]},
            {'group': 'My Fairy', 'label': f'Fairy slot {slot + 1}: Trust', 'value': payload[offset + 0x24]},
            {'group': 'My Fairy', 'label': f'Fairy slot {slot + 1}: Refreshes (read only)', 'value': _uint(payload, offset + 0x6C, 2)},
        ))
    for offset, name in FOOD:
        rows.append({'group': 'Fairy food', 'label': name + ' (read only)',
                     'value': payload[offset]})
    return tuple(rows)


@lru_cache(maxsize=4)
def _field_index(payload):
    fields = list(FORMAT.fields)
    for index, (offset, name) in enumerate(MATERIALS):
        # Discovery bits are not independently mapped. Positive known quantities
        # qualify existing ownership, including preserved higher quantities.
        if _uint(payload, offset, 2) > 0:
            fields.append(Field(f'material_{offset:x}', name, offset, 2, 999,
                                'Material inventory', index + 1, minimum=1))
    for index, (offset, name) in enumerate(MAP_CARDS):
        if payload[offset] > 0:
            fields.append(Field(f'map_card_{offset:x}', name, offset, 1, 5,
                                'Adventure map cards', index + 1, minimum=1))
    for slot in range(FAIRY_COUNT):
        offset = FAIRY_BASE + slot * FAIRY_STRIDE
        name_offset = offset + FAIRY_NAME_DIFF
        raw_name = payload[name_offset:name_offset + FAIRY_NAME_SIZE]
        if payload[offset] == 1 and _fairy_name(raw_name) is not None:
            fields.append(Field(f'fairy_{slot + 1}_name', f'Fairy slot {slot + 1}: Name',
                name_offset, FAIRY_NAME_SIZE, FAIRY_NAME_SIZE, 'My Fairy', slot + 1,
                minimum=1, kind='text'))
        # Trust affects existing fairy-skill potency, distinct from personality
        # thresholds, level and refresh rewards. Admit reductions only; no new
        # growth/skill threshold, reward, feeding or refresh action is asserted.
        if (payload[offset] == 1 and 1 <= payload[offset + 0x1B] <= 99
                and payload[offset + 0x24] > 0):
            fields.append(Field(f'fairy_{slot + 1}_trust',
                f'Fairy slot {slot + 1}: Trust (decrease only)', offset + 0x24,
                1, payload[offset + 0x24], 'Fairy trust', slot + 1, minimum=1))
    # Original 3DS getters/setters qualify these exact scalar positions;
    # observed native states match the separately documented normal/Legendary
    # record states. Never change state, identity, base power or references.
    for weapon in _weapons(payload):
        if (weapon['id'] not in WEAPONS or weapon['id'] in (60, 108, 109)
                or weapon['state'] not in (3, 19)):
            continue
        slot, offset = weapon['slot'], weapon['offset']
        fields.append(Field(f'weapon_{slot}_stars', weapon['name'] + f' (slot {slot}): Stars',
            offset + 0x14, 2, 5, 'Weapon stars', slot, maxable=True))
        # Existing positive ordinary seals only; no collection-sensitive seals,
        # new skill IDs, unused/open slots or state changes. The supported limit
        # is the opened countdown; experimental edits retain its native width.
        if weapon['state'] == 3:
            for index, (identity, remaining) in enumerate(weapon['skills']):
                if identity in SKILLS and identity not in (0, 41, 42, 53, 54) and remaining > 0:
                    fields.append(Field(f'weapon_{slot}_skill_{index + 1}_kos',
                        weapon['name'] + f' (slot {slot}), ' + SKILLS[identity] + ': Remaining KOs',
                        offset + index * 2, 2, remaining, 'Ordinary skill seals',
                        slot * 8 + index))
    return MappingProxyType({field.id: field for field in fields})


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document, changes):
    if type(changes) is not dict:
        raise SaveError('Pending changes must be a dictionary.')
    fields = field_map(document)
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('This field or existing record is not qualified for edits.')
        field = fields[key]
        expected_type = str if field.kind == 'text' else int
        if type(value) is expected_type and value == field.value(document.payload):
            continue  # Preserve stale padding and unusual adjacent bytes on unchanged values.
        field.validate(value)
        encoded = (value.encode('ascii').ljust(field.size, b'\0') if field.kind == 'text'
                   else value.to_bytes(field.size, BYTEORDER))
        output[field.offset:field.offset + field.size] = encoded
    return bytes(output)


def serialize(document, changes):
    raw = changed_payload(document, changes)
    if decode(raw, GAME_ID, document.source).payload != raw:
        raise SaveError('Edited export failed read-back verification.')
    return raw


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str:
        raise SaveError('Select a qualified field identifier.')
    fields = field_map(document)
    if key not in fields:
        raise SaveError('This field or existing record is not qualified for edits.')
    result = dict(changes)
    if type(value) in (int, str) and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
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
    changed_payload(document, changes)
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
    if key not in field_map(document):
        raise SaveError('This field or existing record is not qualified for edits.')
    if key.startswith('fairy_') and key.endswith('_name'):
        return ('Rename this owned My Fairy with 1 to 8 printable ASCII characters. '
                'Only its eight-byte name field changes; shorter names are zero padded. '
                'Assigning the opened name restores the original bytes. Ownership, stats, '
                'clothing and trust are preserved; names are excluded from Max.')
    if key.startswith('fairy_') and key.endswith('_trust'):
        return ('Decrease this owned fairy\'s opened Trust only, down to 1. Existing skill potency '
                'can decrease; personality traits, learned skills, level, refresh count and reward flags '
                'remain unchanged. No feeding, ownership, growth reward or natural Max is asserted. '
                'Unusual trust/level/ownership states remain read only.')
    if key.endswith('_kos'):
        return ('Existing ordinary skill seal: decrease remaining KOs only; zero removes its '
                'KO requirement. Identity, state, base power and equipped references are preserved. '
                "Evil's Bane, Legendary, Exorcism and Master Sword are excluded, as is Max.")
    if key.endswith('_stars'):
        return ('Existing recognized normal/Legendary weapon: stars 0–5. Base power is preserved; '
                'displayed star-adjusted attack is derived. Master Sword, reserved IDs and '
                'unknown states are read only. Max preserves unusual higher opened stars.')
    return ('Manual existing resource quantity with published-editor bounds. Natural gameplay '
            'cap and discovery dependencies remain unqualified; excluded from Max. '
            'Ownership, unknown bytes, original higher values and story are preserved.')


def inspection_rows(document):
    validate_document(document)
    return _inspection(document.payload)


# Direct plaintext scalar editing; no native payload checksum was identified.
INTEGRITY_KIND = 'none'

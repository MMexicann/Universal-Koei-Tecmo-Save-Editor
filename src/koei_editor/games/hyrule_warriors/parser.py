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
from koei_editor.shared.save_safety import safe_path
from koei_editor.games.hyrule_warriors.catalog import MATERIALS, WEAPONS, SKILLS

GAME_ID = 'hyrule_warriors'
TITLE = 'Hyrule Warriors'
SAVE_SIZE = 0x300000
EXTENSION = '.bin'
BYTEORDER = 'big'
# Published decrypted export readers/writers use no mapped checksum layer.
INTEGRITY_KIND = 'none'
LAYOUT_MARKER = bytes.fromhex('15010500')
RUPEES_OFFSET = 0x14C


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

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], BYTEORDER)

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = (Field('rupees', 'Rupees', RUPEES_OFFSET, 4, 9_999_999),)
    sample_verified: bool = True
    note: str = ('Wii U APP.BIN, observed source-reference layout marker 15010500. Independently shared native-export roundtrip checked; '
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


def decode(raw, game_id=GAME_ID, source=Path('APP.BIN')):
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
        raise SaveError('Use a separate Wii U APP.BIN copy outside console-managed folders.')


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


CHARACTER_PACKS = (
    (0x8C184, ('Link', 'Zelda', 'Sheik', 'Impa', 'Ganondorf', 'Darunia', 'Ruto',
               'Agitha', 'Midna', 'Fi', 'Ghirahim', 'Zant', None, 'Lana')),
    (0x8CB24, ('Cia', 'Volga', 'Wizzro', 'Twili Midna', 'Young Link', 'Tingle',
               'Ganon', 'Cucco', 'Linkle', 'Skull Kid', 'Toon Link', 'Tetra',
               'King Daphnes', 'Medli', 'Marin', 'Toon Zelda', 'Ravio', 'Yuga')),
)
ADVENTURE_ITEMS = ('Compass', 'Bombs', 'Candle', 'Ladder', 'Power Bracelet',
                   'Water Bombs', 'Digging Mitts', 'Ice Arrows', 'Raft', 'Hookshot',
                   'Recorder', "Goddess's Harp")
MAPS = (
    ('Adventure Map', 0x141E8, tuple(enumerate(ADVENTURE_ITEMS))),
    ('Master Quest Map', 0x19240, tuple(enumerate(ADVENTURE_ITEMS))),
    ('Twilight Map', 0x1BA6C, ((0, 'Compass'), (1, 'Bombs'), (5, 'Water Bombs'),
        (6, 'Digging Mitts'), (12, 'Lantern'), (13, 'Jar'), (14, 'Fishing Rod'),
        (15, 'Clawshot'), (16, 'Spinner'), (17, 'Ooccoo'), (18, 'Tears of Light'),
        (19, 'Tears of Twilight'))),
    ('Termina Map', 0x1E298, ((0, 'Compass'), (1, 'Bombs'), (7, 'Ice Arrows'),
        (20, 'Song of Time'), (21, 'Inverted Song of Time'), (22, 'Deku Stick'),
        (23, 'Deku Mask'), (24, 'Goron Mask'), (25, 'Zora Mask'), (26, 'Mask of Truth'),
        (27, "Majora's Mask"), (28, 'Giant Summon'))),
)
WEAPON_OFFSET, WEAPON_STRIDE, WEAPON_COUNT = 0x8D74C, 0x4C, 1030


def _weapons(payload):
    result = []
    for slot in range(WEAPON_COUNT):
        offset = WEAPON_OFFSET + slot * WEAPON_STRIDE
        state = payload[offset]
        if not state:
            continue
        identity = _uint(payload, offset + 4, 4)
        name = WEAPONS[identity] if identity < len(WEAPONS) else f'Unknown weapon ID {identity}'
        skills = tuple((_uint(payload, offset + 12 + i * 4, 4),
                        _uint(payload, offset + 44 + i * 4, 4)) for i in range(8))
        result.append({'slot': slot + 1, 'offset': offset, 'state': state, 'id': identity,
                       'name': name, 'base_power': _uint(payload, offset + 8, 2),
                       'stars': _uint(payload, offset + 10, 2), 'skills': skills})
    return tuple(result)


def weapons(document):
    validate_document(document)
    return _weapons(document.payload)


def _known_weapon(weapon):
    return (weapon['id'] < len(WEAPONS) and 'unknown' not in weapon['name'].casefold()
            and 'reserved' not in weapon['name'].casefold()
            and not weapon['name'].startswith('Master Sword')
            and weapon['state'] in (2, 3, 18, 19))


def _inspection(payload):
    rows = []
    for base, names in CHARACTER_PACKS:
        for index, name in enumerate(names):
            if name is None:
                continue
            offset = base + index * 0x38
            rows.append({'group': 'Characters', 'label': name + ': stored level (read only)',
                         'value': payload[offset + 7] + 1})
            rows.append({'group': 'Characters', 'label': name + ': EXP (read only)',
                         'value': _uint(payload, offset + 8, 4)})
    for i, name in enumerate(MATERIALS):
        rows.append({'group': 'Material inventory', 'label': name,
                     'value': _uint(payload, 0x13D2C + i * 2, 2)})
    for name, offset, items in MAPS:
        for index, label in items:
            rows.append({'group': name, 'label': label, 'value': payload[offset + index]})
    return tuple(rows)



@lru_cache(maxsize=4)
def _field_index(payload):
    fields = list(FORMAT.fields)
    for i, name in enumerate(MATERIALS):
        offset = 0x13D2C + i * 2
        # The upstream discover-all bitmask does not prove individual discovery
        # bit access. Positive opened quantities qualify existing material IDs.
        if _uint(payload, offset, 2) > 0:
            fields.append(Field(f'material_{i}', name, offset, 2, 999, 'Material inventory', i + 1))
    for map_index, (name, offset, items) in enumerate(MAPS):
        for index, label in items:
            # Do not grant DLC/maps or manufacture cards from an empty record.
            if payload[offset + index] > 0:
                fields.append(Field(f'map_{map_index}_{index}', label, offset + index,
                                    1, 5, name, index + 1))
    for weapon in _weapons(payload):
        if not _known_weapon(weapon):
            continue
        slot, offset = weapon['slot'], weapon['offset']
        fields.append(Field(f'weapon_{slot}_stars', weapon['name'] + ': Stars',
                            offset + 10, 2, 5, 'Weapon stars', slot))
        # Ordinary seals are KO countdowns. Legendary/Evil's Bane require
        # separately unqualified collection conditions and are never written.
        if weapon['state'] in (2, 3):
            for index, (skill, remaining) in enumerate(weapon['skills']):
                if skill in (*range(1, 41), *range(43, 49)) and remaining > 0:
                    fields.append(Field(f'weapon_{slot}_skill_{index}_kos',
                        weapon['name'] + f': {SKILLS[skill]} remaining KOs (slot {index + 1})',
                        offset + 44 + index * 4, 4, remaining, 'Ordinary skill seals', slot,
                        maxable=False))

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

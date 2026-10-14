"""Conservative source-backed decrypted export adapter; no console crypto.

Mappings and exclusions are documented in docs/THREE_HOPES_FORMAT.md. The native
export remains immutable; serialization only touches staged, qualified fields.
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
from koei_editor.games.three_hopes.catalog import CHARACTERS, WEAPONS

GAME_ID = 'three_hopes'
TITLE = 'Fire Emblem Warriors: Three Hopes'
SAVE_SIZE = 0x50015C
EXTENSION = ''
BYTEORDER = 'little'
LAYOUT_MARKER = b'\x01\0\0\0'
GOLD_OFFSET = 0x77F64


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
    mirrors: tuple = ()

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
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Nintendo Switch extracted SlotData export, observed 0x50015C profile. '
                 'Open a separate copy; Save As creates a new export with backup. '
                 'Gold/material decreases and qualified owned-character names preserve progression.')


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


BLOCK_START = 0x15C
BLOCK_SIZES = (0x298, 0x560, 0x6EFC8, 0x85B0, 0x1DB20) + (0xD80,) * 136 + (0x1AF0A4,) * 2
NESTED_HEADER, NESTED_SIZE = 0x6F3BC, 0x560
GAMEPLAY_HEADER, GAMEPLAY_BODY = 0x77ECC, 0x77EDC
CHARACTER_BASE, CHARACTER_COUNT, CHARACTER_STRIDE = 0x959EC, 136, 0xD80
DEPLOY_BASE, RECRUIT_FLAGS = 0x7864C, 0x77FF4
WEAPON_BASE, WEAPON_COUNT, WEAPON_STRIDE = 0x79D98, 1150, 24
# Save-specific FEW2Save.bt at the pinned revision documented in the format notes.
# Each category contains fixed eight-byte records: u16 quantity, six opaque bytes.
# Item name/order and natural quantity limits are not proved by category labels.
MATERIAL_REGIONS = (
    ('stones', 'Stones', 0x831BC, 8),
    ('building', 'Building materials', 0x8366C, 4),
    ('training', 'Training gear', 0x836BC, 3),
    ('manuals', 'Combat manuals', 0x836E4, 3),
    ('smithing', 'Smithing sets', 0x8370C, 3),
    ('furnishings', 'Furnishings', 0x83734, 3),
    ('licenses', 'Licenses', 0x8375C, 3),
    ('insignias', 'Insignias', 0x83784, 3),
    ('storage', 'Storage materials', 0x837AC, 3),
)
MATERIAL_STRIDE = 8


def _uint(payload, offset, size):
    return int.from_bytes(payload[offset:offset + size], BYTEORDER)


def _objects(raw):
    rows = []
    offset = BLOCK_START
    for index, size in enumerate(BLOCK_SIZES):
        if (_uint(raw, offset + 4, 4) != size or _uint(raw, offset + 8, 4) != 1
                or _uint(raw, offset + 12, 4) != 0):
            raise SaveError('Unsupported Three Hopes section size/revision/header profile.')
        body_end = NESTED_HEADER if index == 2 else offset + size
        rows.append((offset, offset + 16, body_end))
        offset += size
    if (_uint(raw, NESTED_HEADER + 4, 4) != NESTED_SIZE
            or _uint(raw, NESTED_HEADER + 8, 4) != 1
            or _uint(raw, NESTED_HEADER + 12, 4) != 0):
        raise SaveError('Unsupported Three Hopes nested section profile.')
    rows.append((NESTED_HEADER, NESTED_HEADER + 16, NESTED_HEADER + NESTED_SIZE))
    for header, begin, end in rows:
        if _uint(raw, header, 4) != sum(raw[begin:end]):
            raise SaveError('Three Hopes native section checksum does not match.')
    return tuple(rows)


def decode(raw, game_id=GAME_ID, source=Path('SlotData0')):
    get_format(game_id)
    if type(raw) not in (bytes, bytearray) or len(raw) != SAVE_SIZE:
        raise SaveError(f'{TITLE} requires a complete {SAVE_SIZE:,}-byte extracted native export.')
    raw = bytes(raw)
    if raw[:4] != LAYOUT_MARKER:
        raise SaveError('Three Hopes export does not match the observed slot-layout marker.')
    _objects(raw)
    return Document(FORMAT, Path(source), raw, raw)


def _copy_path(path):
    return safe_path(path)


def _extension(path):
    if Path(path).suffix:
        raise SaveError('Use a separate extensionless SlotData export outside console-managed folders.')


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


def _ascii_name(raw):
    try:
        text = raw.decode('ascii').split('\0', 1)[0]
    except UnicodeDecodeError:
        return None
    return text if text and all(32 <= ord(char) <= 126 for char in text) else None


def _characters(payload):
    rows = []
    for index in range(CHARACTER_COUNT):
        body = CHARACTER_BASE + index * CHARACTER_STRIDE + 16
        identity = _uint(payload, body + 112, 2)
        rows.append({'slot': index + 1, 'id': identity,
            'name': CHARACTERS.get(identity, f'Unknown character ID {identity}'),
            'hp': _uint(payload, body + 452, 2),
            'level': _uint(payload, body + 470, 2),
            'weapon_slot': _uint(payload, body + 126, 2)})
    return tuple(rows)


def characters(document):
    validate_document(document)
    return _characters(document.payload)


def weapons(document):
    validate_document(document)
    rows = []
    for index in range(WEAPON_COUNT):
        offset = WEAPON_BASE + index * WEAPON_STRIDE
        identity = document.payload[offset + 4]
        if identity == 0xFF:
            continue
        rows.append({'slot': index + 1, 'id': identity,
            'name': WEAPONS.get(identity, f'Unknown weapon ID {identity}'),
            'might_bonus': _uint(document.payload, offset + 6, 2),
            'durability_bonus': _uint(document.payload, offset + 8, 2),
            'skill_ids': (_uint(document.payload, offset + 10, 2), _uint(document.payload, offset + 12, 2)),
            'might_forge': document.payload[offset + 17],
            'durability_forge': document.payload[offset + 19]})
    return tuple(rows)


def _inspection(payload):
    rows = [{'group': 'Resources', 'label': 'Gold', 'value': _uint(payload, GOLD_OFFSET, 4)},
            {'group': 'Resources', 'label': 'Renown (read only)', 'value': _uint(payload, GOLD_OFFSET + 8, 4)}]
    for identity, category, start, count in MATERIAL_REGIONS:
        rows.extend({'group': 'Material stocks',
            'label': f'{category}: native stock {slot + 1}',
            'value': _uint(payload, start + slot * MATERIAL_STRIDE, 2)}
            for slot in range(count))
    for name, header, body in (('Shez', 0x3C, 0x841FC), ('Byleth', 0x64, 0x84224)):
        text = _ascii_name(payload[body:body + 8]) or 'Unqualified name bytes: ' + payload[body:body + 8].hex()
        rows.append({'group': 'Character names', 'label': name + ': stored name', 'value': text})
    return tuple(rows)


@lru_cache(maxsize=4)
def _field_index(payload):
    fields = [Field('gold', 'Gold (decrease only)', GOLD_OFFSET, 4,
                    _uint(payload, GOLD_OFFSET, 4), 'Resources')]
    for identity, category, start, count in MATERIAL_REGIONS:
        for slot in range(count):
            offset = start + slot * MATERIAL_STRIDE
            opened = _uint(payload, offset, 2)
            # The source proves quantities, not discovery flags or natural caps.
            # Require an existing positive stock. Keep the complete native u16
            # range readable after experimental edits; supported edits remain
            # reductions. Pending edits cannot admit another original record.
            if opened > 0:
                fields.append(Field(f'material_{identity}_{slot + 1}',
                    f'{category}: native stock {slot + 1} (decrease only)',
                    offset, 2, opened, 'Material stocks', offset))
    characters = _characters(payload)
    positive = {row['id'] for row in characters if row['hp'] > 0 and row['level'] > 0}
    deployed = {_uint(payload, DEPLOY_BASE + slot * 4, 2) for slot in range(8)}
    byleth_recruits = _uint(payload, RECRUIT_FLAGS, 4) & 3
    eligibility = {'shez': bool(positive & deployed & {110, 111}),
        'byleth': bool((byleth_recruits & 1 and 0 in positive)
                       or (byleth_recruits & 2 and 1 in positive))}
    for identity, label, header, body in (('shez', 'Shez name', 0x3C, 0x841FC),
                                        ('byleth', 'Byleth name', 0x64, 0x84224)):
        original = payload[body:body + 8]
        if (eligibility[identity] and payload[header:header + 8] == original
                and _ascii_name(original) is not None):
            fields.append(Field(identity + '_name', label, body, 8, 8,
                'Character names', minimum=1, kind='text', mirrors=(header,)))
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
        field.validate(value)
        if value == field.value(document.payload):
            continue  # Preserve stale padding and unusual adjacent bytes on unchanged values.
        encoded = (value.encode('ascii').ljust(field.size, b'\0') if field.kind == 'text'
                   else value.to_bytes(field.size, BYTEORDER))
        for offset in (field.offset,) + field.mirrors:
            output[offset:offset + field.size] = encoded
    if output[GAMEPLAY_BODY:GAMEPLAY_HEADER + 0x1DB20] != document.payload[GAMEPLAY_BODY:GAMEPLAY_HEADER + 0x1DB20]:
        checksum = sum(output[GAMEPLAY_BODY:GAMEPLAY_HEADER + 0x1DB20])
        output[GAMEPLAY_HEADER:GAMEPLAY_HEADER + 4] = checksum.to_bytes(4, BYTEORDER)
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
    fields = field_map(document)
    if key not in fields:
        raise SaveError('This original record is not qualified for edits.')
    if fields[key].kind == 'text':
        return ('Existing qualified character: 1–8 printable ASCII characters. Both name mirrors '
                'are updated together; recruitment, gender, equipment and progression are preserved. No Max.')
    if key.startswith('material_'):
        return ('Decrease an existing material stock only. Native category and physical position are known; '
                'individual item names and natural quantity caps remain unqualified. No Max. '
                'Adjacent record bytes, facility upgrades, rewards and discovery state are preserved.')
    return ('Decrease the opened gold balance only. No Max, earning-history, reward or progression changes.')


def inspection_rows(document):
    validate_document(document)
    return _inspection(document.payload)


# Strict observed plaintext sections include 144 native own-body checksums.
INTEGRITY_KIND = 'checksum'

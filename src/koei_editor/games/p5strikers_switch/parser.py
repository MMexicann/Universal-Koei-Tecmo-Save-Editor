"""Qualified English Switch slots and existing ordinary item quantities.

Empty/unknown slots and all acquisition, recipe, growth, Persona and story
records are preserved. Individual manual ranges are editing limits, not
assertions about natural caps; every field is excluded from bulk Max.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType
import unicodedata

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.p5strikers_switch import codec
from koei_editor.games.p5strikers_pc.catalog import ITEM_GROUPS, CHARACTERS
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'p5strikers_switch'
TITLE = 'Persona 5 Strikers (Nintendo Switch, English)'
SAVE_SIZE, EXTENSION = codec.SAVE_SIZE, ''
INTEGRITY_KIND = 'none'
RESOURCE_MAP = (
    ('money', 'Money', 0x8788E, 9_999_999),
    ('persona_points', 'Persona points', 0x87892, 9_999_999),
    ('bond_points', 'Unspent BOND points', 0x876E2, 999),
)


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

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'little')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Native English Switch layout 0x20012000; 6 MiB savedata export. '
                 'Money, persona points, unspent BOND points and existing named '
                 'consumable/cooking, incense, remedy and skill-card stacks; individual edits only. '
                 'Switch save-manager reimport is external. No conversion, ownership, character or story writes.')


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
        raise SaveError('Choose the explicit English Nintendo Switch Persona 5 Strikers adapter.')
    return FORMAT


def _path(path):
    path = safe_path(path)
    if path.suffix:
        raise SaveError('Open a separate extensionless Switch savedata export; save to a new extensionless copy.')
    return path


def decode(raw, game_id=GAME_ID, source=Path('savedata-copy')):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError('An immutable complete Switch save is required.')
    codec.validate_payload(raw)
    return Document(FORMAT, Path(source), raw, raw)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _path(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('A frozen native English Switch Persona 5 Strikers snapshot is required.')
    codec.validate_payload(document.raw)


def _base(slot):
    return codec.HEADER_SIZE + slot * codec.SLOT_SIZE


def _occupied(payload, slot):
    """Conservative native/default distinction; never create a save slot."""
    base = _base(slot)
    if payload[base:base + 2] == b'\xff\xff':
        return False
    for offset in (codec.NAME_RELATIVE, codec.NAME_RELATIVE + codec.NAME_SIZE):
        name = payload[base + offset:base + offset + codec.NAME_SIZE]
        if not name[0] or b'\0' not in name:
            return False
        try:
            text = name.split(b'\0', 1)[0].decode('utf-8')
        except UnicodeDecodeError:
            return False
        if any(unicodedata.category(character) == 'Cc' for character in text):
            return False
    return True


@lru_cache(maxsize=4)
def _fields(payload):
    fields = []
    for slot in range(1, codec.SLOT_COUNT):
        if not _occupied(payload, slot):
            continue
        base = _base(slot)
        for identity, label, relative, maximum in RESOURCE_MAP:
            fields.append(Field(f'slot_{slot}_{identity}', label, base + relative,
                                4, maximum, 'Resources', slot))
        for group, records in ITEM_GROUPS:
            for relative, name in records:
                offset = base + relative
                # Published editor identifies the low quantity byte. The next
                # byte remains opaque and is never clobbered by a wider write.
                if payload[offset + 1] == 0 and 1 <= payload[offset] <= 99:
                    fields.append(Field(f'slot_{slot}_item_{relative:x}', name,
                                        offset, 1, 99, group, slot, minimum=1))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    if type(changes) is not dict:
        raise SaveError('Pending Persona 5 Strikers changes must be a dictionary.')
    mapping = field_map(document)
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only occupied-slot resources and existing ordinary stacks are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        output[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(output)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    codec.validate_payload(payload)
    return payload


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('The requested Persona 5 Strikers record is inspection only.')
    result = dict(changes)
    if type(value) is int and value == mapping[key].value(document.payload):
        result.pop(key, None)
    else:
        mapping[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    mapping = field_map(document)
    changed_payload(document, changes)
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('The requested Persona 5 Strikers record is not editable.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def _validate_source(document):
    validate_document(document)
    source = _path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SAVE_SIZE + 1)
    except OSError as error:
        raise SaveError('The opened Switch copy is unavailable. Reopen a separate save copy.') from error
    if current != document.raw:
        raise SaveError('The opened Switch copy changed on disk. Reopen it before saving.')
    return source


def backup(document):
    source = _validate_source(document)
    return snapshot_backup(document.raw, source, GAME_ID,
                           source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    source = _validate_source(document)
    destination = _path(destination)
    if source == destination or destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Resources'):
    return f'Save slot {slot}'


def slot_records(document):
    validate_document(document)
    return tuple({'slot': slot, 'qualified': _occupied(document.payload, slot),
                  'resources': tuple((label, int.from_bytes(document.payload[
                      _base(slot) + relative:_base(slot) + relative + 4], 'little'))
                      for _, label, relative, _ in RESOURCE_MAP)}
                 for slot in range(1, codec.SLOT_COUNT))


def item_records(document):
    validate_document(document)
    rows = []
    for slot in range(1, codec.SLOT_COUNT):
        if not _occupied(document.payload, slot):
            continue
        for group, records in ITEM_GROUPS:
            for relative, name in records:
                offset = _base(slot) + relative
                quantity, opaque = document.payload[offset:offset + 2]
                if quantity or opaque:
                    rows.append((slot, group, name, quantity, f'0x{opaque:02X}',
                                 'Individual edit' if opaque == 0 and 1 <= quantity <= 99 else 'Inspection only'))
    return tuple(rows)


def progression_records(document):
    """Published character-level bytes and held Persona words; no growth writes."""
    validate_document(document)
    characters, personas = [], []
    for slot in range(1, codec.SLOT_COUNT):
        if not _occupied(document.payload, slot):
            continue
        base = _base(slot)
        for index, name in enumerate(CHARACTERS):
            characters.append((slot, name, document.payload[base + 0x7F846 + 0x80 * index]))
        for index in range(10):
            offset = base + 0x832CA + 2 * index
            identity = int.from_bytes(document.payload[offset:offset + 2], 'little')
            if identity != 0xFFFF:
                personas.append((slot, index + 1, identity))
    return tuple(characters), tuple(personas)


def field_hint(document, key):
    field = field_map(document)[key]
    mechanic = ''
    if field.group == 'Incenses':
        mechanic = 'Changes the existing incense stack only; character/Persona stats change when the game applies the item. '
    elif field.group == 'Skill cards':
        mechanic = 'Changes the existing card stack only; teaching, compatible Personas and learned skill sets remain under game control. '
    return (mechanic + f'Individual edit range {field.minimum:,}–{field.maximum:,}; Max leaves this field unchanged. '
            'This range is a conservative editor limit, not a verified natural cap. '
            'Existing higher/unknown values and acquisition/progression records are preserved.')

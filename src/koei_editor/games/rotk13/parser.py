"""Original Windows XIII revision-14 campaign city quantities.

Native section framing and the city members are qualified independently
against the original PC serializer. Switch/PK offsets are not used here.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.rotk13 import codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'rotk13_pc'
SAVE_SIZE = codec.SAVE_SIZE
CITY_BASE, CITY_COUNT, CITY_STRIDE = 0x3420, 60, 0xF2
DISTRICT_COUNT, EMPTY_DISTRICT = 120, 0xFF
# name, label, serialized member offset, storage width, presentation group.
# Width supplies an encoding bound, never a natural gameplay maximum.
CITY_MEMBERS = (('money', 'Money', 0x36, 4, 'City resources'),
                ('supplies', 'Supplies', 0x3A, 4, 'City resources'),
                ('civilian_population', 'Civilian population', 0x3E, 4, 'City resources'),
                ('military_population', 'Military population', 0x42, 4, 'City resources'),
                ('wounded', 'Wounded troops', 0x46, 4, 'City resources'),
                ('fealty', 'Fealty', 0xAE, 2, 'City development'),
                ('commerce', 'Commerce', 0xB1, 2, 'City development'),
                ('farming', 'Farming', 0xB7, 2, 'City development'),
                ('culture', 'Culture', 0xBD, 2, 'City development'),
                ('spear_proficiency', 'Spear proficiency', 0xC7, 2, 'City training'),
                ('horse_proficiency', 'Horse proficiency', 0xC9, 2, 'City training'),
                ('bow_proficiency', 'Bow proficiency', 0xCB, 2, 'City training'))
# Offsets are relative to the decoded body, after the separately encoded preview.
# Native fixed section framing also distinguishes campaign data from scenario,
# system, registered-officer, Power Up Kit and console files.
SECTION_TAGS = ((0x20, 'Game'), (0xCE0, 'Scenario'), (0xD00, 'Player'),
                (0x3400, 'City'), (0x6CE0, 'Gate'), (0x6E20, 'Town'),
                (0x7C60, 'TownKind'), (0x7C80, 'Force'), (0xC4E0, 'Gundan'),
                (0xDE60, 'Bushou'), (0x19D0E0, 'Item'), (0x19DC00, 'Gunzei'))


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int = 4
    maximum: int = 0xFFFFFFFF
    group: str = 'City resources'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'
    encoding: str = 'unsigned little endian'
    evidence: str = 'Original PC revision 14 City serializer; ROTK13_FORMAT.md'

    @property
    def experimental_maximum(self):
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires an unsigned {self.size * 8}-bit whole number.')

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
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Romance of the Three Kingdoms XIII (original PC)', SAVE_SIZE, (),
                'Revision-14 campaign copies: existing city resources, population, wounded, '
                'development and troop proficiencies. Choose individual amounts; bulk Max is disabled.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    header: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('This adapter handles original Windows XIII revision-14 campaigns only.')
    return FORMAT


@lru_cache(maxsize=4)
def _qualify_body(body):
    for offset, name in SECTION_TAGS:
        tag = name.encode('ascii') + b'\0'
        if body[offset:offset + len(tag)] != tag:
            raise SaveError(f'The native XIII {name} section is missing or belongs to another format.')


def decode(raw, game_id=GAME_ID, source=Path('xiii-copy.s13')):
    layout = get_format(game_id)
    header, body = codec.decode_layers(raw)
    _qualify_body(body)
    return Document(layout, Path(source), raw, body, header)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.s13':
        raise SaveError('Open a separate original PC XIII .s13 campaign copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.header) is not bytes):
        raise SaveError('A frozen original Windows XIII campaign document is required.')
    header, body = codec.decode_layers(document.raw)
    if header != document.header or body != document.payload:
        raise SaveError('The opened XIII snapshot was changed externally.')
    _qualify_body(body)


@lru_cache(maxsize=4)
def _mapped_fields(payload):
    fields = []
    for city in range(CITY_COUNT):
        start = CITY_BASE + city * CITY_STRIDE
        # Unknown references are retained for inspection, without making their
        # records writable. The slot index identifies an existing serialized city.
        if payload[start] != EMPTY_DISTRICT and payload[start] >= DISTRICT_COUNT:
            continue
        for name, label, relative, width, group in CITY_MEMBERS:
            fields.append(Field(f'city_{city}_{name}', f'City {city}: {label}',
                                start + relative, size=width, maximum=(1 << (width * 8)) - 1,
                                group=group, slot=city + 1))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _mapped_fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def _pending_fields(document, changes):
    mapping = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('Pending XIII edits must be a field/value mapping.')
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only qualified existing city quantities are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
    return mapping


def changed_payload(document, changes):
    mapping = _pending_fields(document, changes)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(result)


def serialize(document, changes):
    body = changed_payload(document, changes)
    if body == document.payload:
        return document.raw
    raw = codec.encode_layers(document.header, body)
    if decode(raw, GAME_ID, document.source).payload != body:
        raise SaveError('The edited XIII copy failed verification.')
    return raw


def stage(document, changes, key, value):
    mapping = _pending_fields(document, changes)
    if type(key) is not str or key not in mapping:
        raise SaveError('The requested XIII field is not editable.')
    result = dict(changes)
    if type(value) is int and value == mapping[key].value(document.payload):
        result.pop(key, None)
    else:
        mapping[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    mapping = _pending_fields(document, changes)
    try:
        keys = tuple(keys)
    except TypeError as error:
        raise SaveError('Choose mapped city field IDs for the Max action.') from error
    for key in keys:
        if type(key) is not str or key not in mapping:
            raise SaveError('The requested XIII field is not editable.')
    # Storage width is not a demonstrated natural gameplay maximum.
    return {}


def maximums(document, changes, group=None):
    _pending_fields(document, changes)
    return dict(changes)


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
    if destination.suffix.lower() != '.s13':
        raise SaveError('Choose a new .s13 destination for the XIII campaign copy.')
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
    return restore_snapshot(backup_path, destination, GAME_ID, '.s13', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='City resources'):
    return f'City {slot - 1}' if type(slot) is int and 1 <= slot <= CITY_COUNT else group


def cities(document):
    validate_document(document)
    result = []
    for city in range(CITY_COUNT):
        start = CITY_BASE + city * CITY_STRIDE
        result.append({'id': city, 'district_reference': document.payload[start],
                       **{name: int.from_bytes(document.payload[start + offset:start + offset + width],
                                              'little')
                          for name, _label, offset, width, _group in CITY_MEMBERS}})
    return tuple(result)


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('The requested XIII field is not editable.')
    if key.endswith('_military_population'):
        meaning = 'Stored military population; deployed units, returning troops and wounded are separate.'
    elif key.endswith('_civilian_population'):
        meaning = 'Stored non-military population component; the displayed total can include military population.'
    elif key.endswith('_supplies'):
        meaning = 'Existing city supplies stockpile; seasonal harvest and army provisions are separate.'
    elif key.endswith('_money'):
        meaning = 'Existing city money stockpile; personal money and seasonal revenue are separate.'
    elif key.endswith('_wounded'):
        meaning = 'Stored wounded troops; military population and deployed units are separate.'
    elif key.endswith('_fealty'):
        meaning = 'Stored city fealty; prosperity and force ownership are separate.'
    elif key.endswith('_proficiency'):
        meaning = 'Stored troop proficiency for this city; officer aptitude and deployed units are separate.'
    else:
        meaning = 'Stored current city development; derived development caps are separate.'
    return meaning + ' Enter an amount deliberately; storage bounds are not natural gameplay limits.'


# The applicable native checksum covers the preview only. The original city's
# gameplay body has no checksum; serialize preserves the preview unchanged.
INTEGRITY_KIND = 'checksum'

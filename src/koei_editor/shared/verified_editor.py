"""Copy-only editing for explicitly verified PC save layouts.

Only declared scalar fields can change. Unknown bytes and original cipher seeds
are retained. No sample save or third-party implementation is distributed.
"""
from dataclasses import dataclass
from collections.abc import Mapping
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType
from koei_editor.games.dw3.game_content import DW8_ATTRIBUTE_NAMES, PW3_COSTUME_ASSOCIATIONS
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.koei_codec import byte_cipher, mix_word, word_cipher, word_sum
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.experimental_limits import within_numeric_limits


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
    experimental: bool = True

    @property
    def experimental_maximum(self):
        """Largest representable numeric value; protected choices stay bounded."""
        if not self.experimental:
            return None
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if not within_numeric_limits(value, self.minimum, self.maximum,
                                     storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class CompatibilityField(Field):
    """Published aptitude units: 25/50/75/100 correspond to one/four stars.

    Existing other values remain readable and no-op-safe. Deliberate edits use
    only the four observed native values, rather than arbitrary percentages.
    """

    @property
    def experimental_maximum(self):
        return None

    def validate(self, value):
        super().validate(value)
        if value not in (25, 50, 75, 100):
            raise SaveError(f'{self.label} requires 25, 50, 75 or 100 '
                            '(one, two, three or four stars).')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    magic: tuple
    fields: tuple
    inner_seed: object = None
    note: str = ''


DW8_FIELDS = tuple([
    Field('gold', 'Gold', 0x105, 4, 9_999_999),
    Field('gems', 'Gems', 0x1d43, 2, 9_999),
    Field('facility_materials', 'Facility materials', 0x1f6d1, 2, 9_999),
    Field('weapon_materials', 'Weapon materials', 0x1f6d3, 2, 9_999),
] + [Field(f'officer_{slot}_{name}', label, offset + slot * 0x48, 2, maximum,
           'Officers', slot + 1)
     for slot in range(82)
     for name, label, offset, maximum in (('attack', 'Attack', 0x7fd5, 1500),
                                         ('defense', 'Defense', 0x7fd7, 1500),
                                         ('hp', 'Health', 0x7fd9, 1000))]
    + [CompatibilityField(f'officer_{slot}_compatibility_{index}',
                          f'{label} compatibility (25 units per star)',
                          0x7fdb + slot * 0x48 + index, 1, 100,
                          'Weapon compatibility', slot + 1, 25)
       for slot in range(82)
       for index, label in enumerate(('Dash', 'Dive', 'Shadow Sprint', 'Whirlwind'))])

PW3_FIELDS = tuple([Field(f'character_{slot}_{name}', label, offset + slot * 0x1f0, size, maximum,
           'Characters', slot + 1, minimum)
     for slot in range(47)
     for name, label, offset, size, maximum, minimum in (
         ('hp', 'Health', 0x654, 2, 10000, 0),
         ('attack', 'Attack', 0x656, 2, 1000, 0),
         ('defense', 'Defense', 0x658, 2, 1000, 0),
         ('special', 'Special bars', 0x65a, 1, 4, 1),
         ('skills', 'Skill slots', 0x65c, 1, 6, 1))])

FORMATS = {
    'dw8xl': Format('dw8xl', 'Dynasty Warriors 8: Xtreme Legends Complete Edition',
                    0xb7f49, (bytes.fromhex('f002101309'), bytes.fromhex('f027021909')),
                    DW8_FIELDS, 0x13100200,
                    'Windows PC save.dat. Resources, officer stats, four-star weapon compatibility '
                    'and existing weapon affinities, ranked attributes and attribute replacement. '
                    'Gems use the community-corroborated 9,999 inventory limit. '
                    'Levels, XP and weapon identities remain read only. Qualified original two-weapon '
                    'loadouts may be reordered without acquiring another weapon.'),
    'pw3': Format('pw3', 'One Piece: Pirate Warriors 3', 0x135d04,
                  (b'ONE PIECE: PIRATE WARRIORS 3\x00',), PW3_FIELDS, None,
                  'Windows PC OP3WIN0000.dat. Character stats may reset on level-up. '
                  'Numbered character slots avoid assuming unverified names. '
                  'Currency, levels, experience and the adjacent currency-related counter remain untouched '
                  'pending controlled PC samples. Medals and story progress are also preserved.'),
}

# Published shared layout, corroborated against the converter's native PC sample.
# This is the physical save pool, not a claim about in-game inventory capacity.
DW8_WEAPON_BASE, DW8_WEAPON_STRIDE, DW8_WEAPON_COUNT = 0xe715, 0x18, 1830
# These IDs have ranks 2..10 in populated genuine PC records. Consistently-one
# and unobserved IDs remain untouched; numeric IDs are not assigned guessed names.
DW8_RANKED_ATTRIBUTES = frozenset([0, *range(2, 24), *range(28, 36), 39, 41, 42, 43, 44])
# Shared save-patch fields corroborated by the PC fixture and native PC runtime
# record descriptions. Skill/ally progression is inspected, never rewritten.
DW8_BODYGUARD_BASE, DW8_BODYGUARD_STRIDE, DW8_BODYGUARD_COUNT = 0x9be9, 0xc, 838


def _weapon_record(payload, index):
    offset = DW8_WEAPON_BASE + index * DW8_WEAPON_STRIDE
    state = payload[offset]
    identity = int.from_bytes(payload[offset + 2:offset + 4], 'little')
    if state not in (1, 3) or identity == 0xffff:
        return None
    return {'slot':index + 1, 'state':state, 'id':identity,
            'affinity':payload[offset + 4], 'attack':payload[offset + 5],
            'attributes':tuple(zip(payload[offset + 6:offset + 12], payload[offset + 12:offset + 18]))}


@lru_cache(maxsize=8)
def _field_index(game_id, payload):
    fields = {field.id:field for field in get_format(game_id).fields}
    if game_id == 'dw8xl':
        from koei_editor.games.dw8xl.equipment import fields_for_payload
        from koei_editor.games.dw8xl.attributes import fields_for_payload as attribute_fields
        fields.update((field.id, field) for field in attribute_fields(
            payload, _weapon_record, DW8_WEAPON_COUNT, DW8_WEAPON_BASE,
            DW8_WEAPON_STRIDE, DW8_RANKED_ATTRIBUTES))
        fields.update((field.id, field) for field in fields_for_payload(payload, _weapon_record, DW8_WEAPON_COUNT))
        for index in range(DW8_WEAPON_COUNT):
            record = _weapon_record(payload, index)
            if record is None:
                continue
            if record['affinity'] in (0, 1, 2):
                field = Field(f'weapon_{index}_affinity', 'Affinity ID (0, 1 or 2)',
                              DW8_WEAPON_BASE + index * DW8_WEAPON_STRIDE + 4,
                              1, 2, 'Weapon affinity', index + 1, 0, False, experimental=False)
                fields[field.id] = field
            for attribute, (identity, rank) in enumerate(record['attributes']):
                if identity not in DW8_RANKED_ATTRIBUTES or rank == 0:
                    continue
                field = Field(f'weapon_{index}_attribute_{attribute}_rank',
                              f'Attribute {attribute + 1} rank (opened {DW8_ATTRIBUTE_NAMES.get(identity, "ID " + str(identity))})',
                              DW8_WEAPON_BASE + index * DW8_WEAPON_STRIDE + 12 + attribute,
                              1, 10, 'Weapon attributes', index + 1, 1)
                fields[field.id] = field
    return MappingProxyType(fields)


def fields_for(document):
    """Editable fields for this immutable snapshot, including existing weapons."""
    return tuple(field_map(document).values())


def field_options(document, key):
    from koei_editor.games.dw8xl.equipment import WeaponOrderField
    from koei_editor.games.dw8xl.attributes import AttributeIdentityField
    field = field_map(document).get(key)
    if isinstance(field, AttributeIdentityField):
        return tuple((identity, f'{DW8_ATTRIBUTE_NAMES.get(identity, "Attribute")} (ID {identity})')
                     for identity in field.allowed_ids)
    if isinstance(field, CompatibilityField):
        return tuple((value, f'{value // 25} stars ({value} stored units)')
                     for value in (25, 50, 75, 100))
    if field is not None and field.group == 'Weapon affinity':
        return tuple((value, f'Affinity ID {value}') for value in (0, 1, 2))
    if isinstance(field, WeaponOrderField):
        return tuple((slot, f'Weapon slot {slot:04} (ID {_weapon_record(document.payload, slot - 1)["id"]})')
                     for slot in field.opened_slots)
    return ()


def weapons(document):
    """Read-only populated physical weapon records; stale flag-zero rows are omitted."""
    if document.format.id != 'dw8xl':
        raise SaveError('Weapon inspection is mapped only for this DW8 PC layout.')
    validate_document(document)
    return tuple(record for index in range(DW8_WEAPON_COUNT)
                 if (record := _weapon_record(document.payload, index)) is not None)


def weapon(document, slot):
    if document.format.id != 'dw8xl' or type(slot) is not int or not 1 <= slot <= DW8_WEAPON_COUNT:
        raise SaveError('Choose an existing DW8 PC weapon record.')
    validate_document(document)
    record = _weapon_record(document.payload, slot - 1)
    if record is None:
        raise SaveError('This physical record is not an observed populated weapon.')
    return record


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


def get_format(game_id):
    try:
        return FORMATS[game_id]
    except KeyError as error:
        raise SaveError('No verified editing format is registered for this game.') from error


def decode(raw, game_id, source=Path('copy.dat')):
    layout = get_format(game_id)
    if len(raw) != layout.size:
        raise SaveError(f'{layout.title}: this PC layout requires exactly {layout.size:,} bytes.')
    checksum, seed = struct.unpack_from('<HH', raw)
    encrypted_inner = word_cipher(raw[4:-1] if layout.inner_seed is not None else raw[4:], seed)
    if word_sum(encrypted_inner) != checksum:
        raise SaveError('Save integrity check failed. The selected game or file may be incorrect.')
    payload = encrypted_inner
    if layout.inner_seed is not None:
        payload = byte_cipher(payload, layout.inner_seed)
        if (sum(payload) & 0xff) != (raw[-1] ^ (mix_word(seed) & 0xff)):
            raise SaveError('DW8 Xtreme Legends plaintext checksum failed.')
    if not any(payload.startswith(magic) for magic in layout.magic):
        raise SaveError('Game identity or save revision does not match the selected PC editor.')
    if layout.id == 'pw3' and (payload[0x500:0x508] != bytes.fromhex('0000000002000000') or
                              payload[0x518:0x51c] != bytes.fromhex('d0000000')):
        raise SaveError('Pirate Warriors 3 PC record layout is not a verified revision.')
    return Document(layout, Path(source), bytes(raw), payload, seed)


def read_save(path, game_id):
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate PC .dat save copy.')
    layout = get_format(game_id)
    with path.open('rb') as stream:
        raw = stream.read(layout.size + 1)
    return decode(raw, game_id, path)


def field_map(document):
    validate_document(document)
    return _field_index(document.format.id, document.payload)


def validate_document(document):
    if (not isinstance(document, Document) or not isinstance(document.format, Format) or
            type(document.format.id) is not str or type(document.raw) is not bytes or
            type(document.payload) is not bytes or type(document.seed) is not int):
        raise SaveError('Use an unchanged immutable document from the selected PC editor.')
    layout = get_format(document.format.id)
    if document.format != layout:
        raise SaveError('Unregistered editing layout.')
    _validate_snapshot(layout.id, document.raw, document.payload, document.seed)


@lru_cache(maxsize=8)
def _validate_snapshot(game_id, raw, payload, seed):
    # Native qualification is reusable only for immutable byte snapshots. Bulk
    # staging must not decrypt the complete file again for every field.
    original = decode(raw, game_id)
    if original.payload != payload or original.seed != seed:
        raise SaveError('The opened document was changed outside the edit workflow.')


def observed_beli(document):
    """Read the candidate balance; its coupling to adjacent currency data is unknown."""
    if document.format.id != 'pw3':
        return None
    validate_document(document)
    return int.from_bytes(document.payload[0xc5d4:0xc5d8], 'little')


def observed_health_curve(level_index):
    """PW3 pattern corroborated across two PC samples, not a native clamp."""
    if type(level_index) is not int or not 0 <= level_index <= 99:
        return None
    if level_index <= 49:
        return 2000 + (3000 * level_index // 49)
    return 5000 + 20 * (level_index - 49)


def progression(document, slot):
    """Read-only progression; XP thresholds and recalculation are not write rules."""
    count = 82 if document.format.id == 'dw8xl' else 47 if document.format.id == 'pw3' else 0
    if type(slot) is not int or not 1 <= slot <= count:
        raise SaveError('Choose a mapped officer or character record slot.')
    validate_document(document)
    return _progression(document, slot)


def progressions(document):
    """Inspect all mapped progression records with one snapshot validation."""
    if document.format.id not in ('dw8xl', 'pw3'):
        raise SaveError('Progression inspection is not mapped for this game.')
    validate_document(document)
    return tuple(_progression(document, slot) for slot in range(1, 83 if document.format.id == 'dw8xl' else 48))


def _progression(document, slot):
    if document.format.id == 'dw8xl':
        offset = 0x7fc9 + (slot - 1) * 0x48
        index = document.payload[offset + 0x17]
        return {'level':index + 1, 'level_index':index,
                'experience':int.from_bytes(document.payload[offset + 0x1c:offset + 0x20], 'little'),
                'leadership':int.from_bytes(document.payload[offset + 0x18:offset + 0x1c], 'little') + 1,
                'leadership_experience':int.from_bytes(document.payload[offset + 0x20:offset + 0x24], 'little'),
                'observed_health':None,
                'weapon_slots':tuple(int.from_bytes(document.payload[offset + n:offset + n + 2], 'little') + 1
                                     for n in (0x30, 0x32))}
    offset = 0x650 + (slot - 1) * 0x1f0
    index = document.payload[offset + 0xb]
    return {'level':index + 1, 'level_index':index,
            'experience':int.from_bytes(document.payload[offset:offset + 4], 'little'),
            'observed_health':observed_health_curve(index)}


def costume_associations(document):
    """Read documented PC asset associations; never infer unlock/equipped flags."""
    if document.format.id != 'pw3':
        raise SaveError('Costume associations are mapped only for PW3.')
    validate_document(document)
    return tuple({'slot':character + 1, 'local_slot':local, 'asset_costume_id':identity,
                  'stored_id':document.payload[0x650 + character * 0x1f0 + 0x2f + local]}
                 for character, local, identity in PW3_COSTUME_ASSOCIATIONS)


def compatibilities(document):
    """Stored aptitude units, separate from weapon attributes and officer EXP."""
    if document.format.id != 'dw8xl':
        raise SaveError('Weapon compatibility is mapped only for DW8 PC.')
    validate_document(document)
    return tuple(tuple(document.payload[0x7fdb + slot * 0x48 + index]
                       for index in range(4)) for slot in range(82))


def bodyguards(document):
    """Read existing physical ally progression records without assuming ownership.

    The published shared layout has 838 records. Recruitment, names, battle-skill
    identity and max-level dependencies are not mapped here, so no edits or
    ownership labels are inferred from these values.
    """
    if document.format.id != 'dw8xl':
        raise SaveError('Ally progression inspection is mapped only for DW8 PC.')
    validate_document(document)
    rows = []
    for slot in range(DW8_BODYGUARD_COUNT):
        offset = DW8_BODYGUARD_BASE + slot * DW8_BODYGUARD_STRIDE
        rows.append({'slot':slot + 1, 'skill_level':document.payload[offset] + 1,
                     'support_skill_ids':tuple(document.payload[offset + 1:offset + 3]),
                     'skill_experience':int.from_bytes(document.payload[offset + 4:offset + 6], 'little'),
                     'male_bond':document.payload[offset + 8],
                     'female_bond':document.payload[offset + 9]})
    return tuple(rows)


def _pending_fields(document, changes):
    fields = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('Pending edits must be a mapping of verified fields and values.')
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('A requested field is not verified for this game.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue  # Existing unusual values remain valid unchanged snapshots.
        field.validate(value)
    if document.format.id == 'dw8xl':
        from koei_editor.games.dw8xl.attributes import validate_pending
        validate_pending(document.payload, changes, fields, DW8_WEAPON_BASE, DW8_WEAPON_STRIDE)
    return fields


def changed_payload(document, changes):
    fields = _pending_fields(document, changes)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = fields[key]
        if hasattr(field, 'write'):
            field.write(result, value)
        else:
            result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(result)


def serialize(document, changes):
    validate_document(document)
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    layout = document.format
    inner = byte_cipher(payload, layout.inner_seed) if layout.inner_seed is not None else payload
    raw = struct.pack('<HH', word_sum(inner), document.seed) + word_cipher(inner, document.seed)
    if layout.inner_seed is not None:
        raw += bytes([(sum(payload) & 0xff) ^ (mix_word(document.seed) & 0xff)])
    verified = decode(raw, layout.id, document.source)
    if verified.payload != payload:
        raise SaveError('Edited save verification failed.')
    return raw


def stage(document, changes, key, value):
    fields = _pending_fields(document, changes)
    if type(key) is not str or key not in fields:
        raise SaveError('A requested field is not verified for this game.')
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        result[key] = value
    _pending_fields(document, result)
    return result


def limit_values(document, changes, keys):
    """Published limits never lower higher values already present in a copy."""
    fields = _pending_fields(document, changes)
    result = {}
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('A requested field is not verified for this game.')
        field = fields[key]
        if not field.maxable:
            continue
        current = changes.get(key, field.value(document.payload))
        if isinstance(field, CompatibilityField) and current not in (25, 50, 75, 100):
            # An unusual original aptitude is not permission to normalize it.
            continue
        if type(current) is int and field.minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    fields = _pending_fields(document, changes)
    result = dict(changes)
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    for key, value in limit_values(document, changes, keys).items():
        # The batch and targets are already validated. Preserve stage's unstage
        # behavior without rescanning every pending entry for each Max target.
        if value == fields[key].value(document.payload):
            result.pop(key, None)
        else:
            result[key] = value
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, document.format.id,
                           document.source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination.')
    # Detect edits by another program before preserving the opened snapshot.
    with safe_path(document.source).open('rb') as stream:
        current = stream.read(document.format.size + 1)
    if current != document.raw:
        raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, document.format.id, destination)


def restore(backup_path, destination, game_id):
    layout = get_format(game_id)
    # Qualify the same bounded snapshot that will be written after hash checking.
    return restore_snapshot(backup_path, destination, game_id, '.dat', layout.size,
                            validate_raw=lambda raw: decode(raw, game_id))

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'

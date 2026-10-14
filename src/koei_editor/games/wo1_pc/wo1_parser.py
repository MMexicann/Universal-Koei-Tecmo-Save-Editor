"""Original Windows PC shared Growth Points and existing weapon properties.

Original title-specific disk reader/getter/setter evidence and independent
native saves qualify these offsets; no Z, console or runtime address is used.
"""
from dataclasses import dataclass
from collections.abc import Mapping
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo1_pc import wo1_codec as codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.experimental_limits import within_numeric_limits

GAME_ID = 'wo1'
SAVE_SIZE = codec.SAVE_SIZE
OFFICER_BASE, OFFICER_COUNT, OFFICER_STRIDE = 0xC, 79, 0xC8
WEAPON_BASE, WEAPON_COUNT, WEAPON_STRIDE, EMPTY_WEAPON = 0x14, 8, 0x16, 345
STOCK_EXP_OFFSET, STOCK_EXP_MAXIMUM = 0x40C8, 0xFFFFFFFF
# Limits below are storage/edit domains. Only independently named effect ranks
# have a documented original-game natural maximum and participate in Max.
ATTRIBUTE_NAMES = ('Flame', 'Ice', 'Bolt', 'Flash', 'Slay', None, 'Drain',
                   'Absorb', 'Air', 'Brave', 'Range', 'Multi', 'Agility', 'Might', 'Rage')


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
    display_bias: int = 0

    @property
    def experimental_maximum(self):
        """Largest representable numeric value; protected choices stay bounded."""
        if self.id.endswith(('_equipped_weapon', '_attribute_slots')):
            return None
        return (1 << (8 * self.size)) - 1 + self.display_bias

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little') + self.display_bias

    def validate(self, value):
        if not within_numeric_limits(value, self.minimum, self.maximum,
                                     storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return (value - self.display_bias).to_bytes(self.size, 'little')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Warriors Orochi (original PC)', SAVE_SIZE, (),
                'Manual shared Growth Points, qualified existing weapon properties and existing owned-weapon selection. '
                'Character growth, skills, ownership and story progression remain read only.')


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
        raise SaveError('This adapter handles original Warriors Orochi on Windows PC only.')
    return FORMAT


@lru_cache(maxsize=4)
def _validated_snapshot(raw):
    return codec.decode(raw)


def decode(raw, game_id=GAME_ID, source=Path('wo1-copy.dat')):
    layout = get_format(game_id)
    # Freeze before caching: writable input and forged Document buffers must
    # never share the immutable validated snapshot cache.
    payload = _validated_snapshot(codec._profile(raw))
    return Document(layout, Path(source), payload, payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native original Warriors Orochi PC save.dat copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError('A frozen native original Warriors Orochi PC document is required.')
    if _validated_snapshot(document.raw) != document.payload:
        raise SaveError('The opened original Warriors Orochi PC snapshot was changed externally.')


def _weapon_offset(officer, weapon):
    return OFFICER_BASE + officer * OFFICER_STRIDE + WEAPON_BASE + weapon * WEAPON_STRIDE


def _qualified_weapon(payload, officer, weapon):
    start = _weapon_offset(officer, weapon)
    identity = int.from_bytes(payload[start:start + 2], 'little')
    mask = int.from_bytes(payload[start + 2:start + 4], 'little')
    # The original PC type getter uses descriptor ID // 4 for the owning
    # officer and ID % 4 for weapon tier. Do not reinterpret NPC/foreign IDs.
    return (4 * officer <= identity <= 4 * officer + 3 and not mask & 0x8000
            and mask.bit_count() <= payload[start + 4] <= 8)


def _equipped_options(payload, officer):
    return tuple((weapon + 1, f'Weapon slot {weapon + 1} (ID '
                  f'{int.from_bytes(payload[_weapon_offset(officer, weapon):_weapon_offset(officer, weapon) + 2], "little")})')
                 for weapon in range(WEAPON_COUNT)
                 if _qualified_weapon(payload, officer, weapon))


@lru_cache(maxsize=4)
def _mapped_fields(payload):
    fields = [Field('stock_exp', 'Stock EXP / Growth Points', STOCK_EXP_OFFSET, 4,
                    STOCK_EXP_MAXIMUM, maxable=False)]
    for officer in range(OFFICER_COUNT):
        equipped_offset = OFFICER_BASE + officer * OFFICER_STRIDE + 1
        options = _equipped_options(payload, officer)
        if payload[equipped_offset] + 1 in dict(options) and len(options) > 1:
            fields.append(Field(f'officer_{officer}_equipped_weapon',
                                f'Officer record {officer}: Equipped weapon slot',
                                equipped_offset, 1, 8, 'Equipment', officer + 1,
                                minimum=1, maxable=False, display_bias=1))
        for weapon in range(WEAPON_COUNT):
            start = _weapon_offset(officer, weapon)
            mask = int.from_bytes(payload[start + 2:start + 4], 'little')
            # Preserve structurally unusual weapons; never repair masks or rank bytes.
            if not _qualified_weapon(payload, officer, weapon):
                continue
            prefix = f'officer_{officer}_weapon_{weapon}'
            label = f'Officer record {officer}, weapon {weapon + 1}'
            slot = officer * WEAPON_COUNT + weapon + 1
            fields.extend((Field(prefix + '_attack_bonus', label + ': Attack bonus',
                                 start + 5, 1, 255, 'Weapons', slot, maxable=False),
                           Field(prefix + '_attribute_slots', label + ': Attribute slots',
                                 start + 4, 1, 8, 'Weapons', slot, mask.bit_count(), maxable=False)))
            for attribute, name in enumerate(ATTRIBUTE_NAMES):
                # Native enum 5 is deliberately skipped by the original PC UI.
                # Only independently named effects qualify; no enum is inferred
                # from the manual's different display order.
                if name is not None and mask & (1 << attribute):
                    fields.append(Field(prefix + f'_attribute_{attribute}_level',
                                        label + f': {name} (ID {attribute}) level',
                                        start + 6 + attribute, 1, 10, 'Weapon attributes',
                                        slot, 1, display_bias=1))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _mapped_fields(document.payload)


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


@lru_cache(maxsize=4)
def _field_index(payload):
    return MappingProxyType({field.id: field for field in _mapped_fields(payload)})


def _checked_changes(document, changes):
    mapping = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('Pending changes must be a field-to-value mapping.')
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only mapped resources and existing weapon properties are writable.')
        field = mapping[key]
        if type(value) is not int or value != field.value(document.payload):
            field.validate(value)
            if key.endswith('_equipped_weapon') and value not in dict(
                    _equipped_options(document.payload, field.slot - 1)):
                raise SaveError("Select a qualified existing weapon from this officer's own pool.")
    return mapping


def changed_payload(document, changes):
    mapping = _checked_changes(document, changes)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return codec.encode(result) if changes else document.payload


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    if decode(payload, GAME_ID, document.source).payload != payload:
        raise SaveError('Original Warriors Orochi PC edited copy verification failed.')
    return payload


def stage(document, changes, key, value):
    mapping = _checked_changes(document, changes)
    if type(key) is not str or key not in mapping:
        raise SaveError('The requested original Warriors Orochi PC field is not editable.')
    field = mapping[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
        _checked_changes(document, result)
    return result


def limit_values(document, changes, keys):
    mapping = field_map(document)
    changed_payload(document, changes)
    result = {}
    for key in keys:
        if type(key) is not str or key not in mapping:
            raise SaveError('The requested original Warriors Orochi PC field is not editable.')
        field = mapping[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and field.minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    _checked_changes(document, changes)
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
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination for the original Warriors Orochi PC copy.')
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
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='Resources'):
    if group == 'Equipment' and type(slot) is int and 1 <= slot <= OFFICER_COUNT:
        return f'Officer record {slot - 1}'
    if type(slot) is int and 1 <= slot <= OFFICER_COUNT * WEAPON_COUNT:
        officer, weapon = divmod(slot - 1, WEAPON_COUNT)
        return f'Officer record {officer}: Weapon {weapon + 1}'
    return group


def officers(document):
    validate_document(document)
    rows = []
    for identity in range(OFFICER_COUNT):
        start = OFFICER_BASE + identity * OFFICER_STRIDE
        rows.append({'id': identity, 'stored_level': document.payload[start],
                     'equipped_slot': document.payload[start + 1],
                     'stats': tuple(int.from_bytes(document.payload[start + offset:start + offset + 2],
                                                   'little') for offset in (4, 6, 8, 10, 12)),
                     'proficiency': int.from_bytes(document.payload[start + 14:start + 16], 'little'),
                     'exp': int.from_bytes(document.payload[start + 16:start + 20], 'little')})
    return tuple(rows)


def weapons(document):
    validate_document(document)
    rows = []
    for officer in range(OFFICER_COUNT):
        for weapon in range(WEAPON_COUNT):
            start = _weapon_offset(officer, weapon)
            rows.append({'officer': officer, 'slot': weapon,
                         'id': int.from_bytes(document.payload[start:start + 2], 'little'),
                         'mask': int.from_bytes(document.payload[start + 2:start + 4], 'little'),
                         'capacity': document.payload[start + 4], 'bonus': document.payload[start + 5],
                         'ranks': tuple(document.payload[start + 6:start + 21])})
    return tuple(rows)


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    value = field_map(document).get(key) if type(key) is str else None
    if value is None:
        raise SaveError('The requested original Warriors Orochi PC field is not editable.')
    if key.endswith('_equipped_weapon'):
        return ("Select an existing qualified weapon from this officer's own eight-slot pool. "
                'Slots display 1..8 and store 0..7. Ownership, weapon IDs, effect masks, '
                'growth, collection and rewards are preserved; excluded from Max.')
    if key == 'stock_exp':
        return ('Shared Growth Points used for character growth and weapon fusion. '
                'Individual edits use the u32 storage range; no natural maximum is claimed. '
                'Bulk Max excludes this balance.')
    if key.endswith('_attribute_slots'):
        return f'Existing weapon capacity, {value.minimum}..8; all owned effect identities are preserved.'
    if '_attribute_' in key:
        return 'Already owned effect rank 1..10, encoded as rank minus one. Ownership and other ranks are preserved.'
    return ('Existing attack-bonus byte, separate from descriptor attack and officer growth. '
            'Manual edits use the byte storage range; bulk Max excludes it. Normal fusion '
            'guides describe +20, so larger deliberate values may behave differently in game.')


INTEGRITY_KIND = 'checksum'


def field_options(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('The requested original Warriors Orochi PC field is not editable.')
    return _equipped_options(document.payload, field.slot - 1) if key.endswith('_equipped_weapon') else ()

"""Native Orochi Z existing weapons, base growth stats and bounded EXP.

Offsets come from the native serialized blocks and weapon-fusion mutation path;
no console offsets, new weapon identities or story/reward flags are inferred.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.games.orochiz import orochiz_codec as codec
from koei_editor.games.orochiz.orochiz_limits import (
    BASE_ATTACK_MINIMUMS, BASE_ATTACK_MAXIMUMS, LEVEL_EXP_THRESHOLDS,
    BASE_LIFE_MINIMUMS, BASE_LIFE_MAXIMUMS, BASE_MUSOU_MINIMUMS, BASE_MUSOU_MAXIMUMS,
    BASE_DEFENSE_MINIMUMS, BASE_DEFENSE_MAXIMUMS, BASE_SPEED_MINIMUMS, BASE_SPEED_MAXIMUMS)
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.experimental_limits import within_numeric_limits

GAME_ID = 'orochiz'
SAVE_SIZE = codec.SAVE_SIZE
OFFICER_BASE, OFFICER_COUNT, OFFICER_STRIDE = 0xC, 96, 0xDC
WEAPON_BASE, WEAPON_COUNT, WEAPON_STRIDE, EMPTY_WEAPON = 0x14, 8, 0x18, 414
STOCK_EXP_OFFSET, STOCK_EXP_MAXIMUM = 0x5E30, 99999


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
        if self.id.endswith(('_equipped_weapon', '_attribute_slots', '_exp_within_level')):
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


FORMAT = Format(GAME_ID, 'Warriors Orochi Z (PC)', SAVE_SIZE, (),
                'Stock EXP, qualified officer base Life/Musou/Attack/Defense/Speed and existing weapon attack bonus, attribute capacity and '
                'owned ranked attributes. Switch between qualified existing weapons in an officer\'s own pool. '
                'Adjust EXP inside a progressed officer\'s current level; levels, proficiency, alchemy '
                'abilities, unlocks and story records remain read only.')


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
        raise SaveError('This adapter handles native PC Warriors Orochi Z only.')
    return FORMAT


@lru_cache(maxsize=4)
def _validated_snapshot(raw):
    return codec.decode(raw)


def decode(raw, game_id=GAME_ID, source=Path('orochiz-copy.dat')):
    layout = get_format(game_id)
    # Freeze before caching: writable input and forged Document buffers must
    # never share the immutable validated snapshot cache.
    payload = _validated_snapshot(codec._profile(raw))
    return Document(layout, Path(source), payload, payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native Warriors Orochi Z save.dat copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format != FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError('A frozen native Warriors Orochi Z document is required.')
    if _validated_snapshot(document.raw) != document.payload:
        raise SaveError('The opened Warriors Orochi Z snapshot was changed externally.')


def _weapon_offset(officer, weapon):
    return OFFICER_BASE + officer * OFFICER_STRIDE + WEAPON_BASE + weapon * WEAPON_STRIDE


def _qualified_weapon(payload, officer, weapon):
    start = _weapon_offset(officer, weapon)
    identity = int.from_bytes(payload[start:start + 2], 'little')
    mask = int.from_bytes(payload[start + 2:start + 4], 'little')
    return (0 <= identity < EMPTY_WEAPON and not mask & 0x8000
            and mask.bit_count() <= payload[start + 6] <= 8)


def _equipped_options(payload, officer):
    options = []
    for weapon in range(WEAPON_COUNT):
        if _qualified_weapon(payload, officer, weapon):
            start = _weapon_offset(officer, weapon)
            identity = int.from_bytes(payload[start:start + 2], 'little')
            options.append((weapon + 1, f'Weapon slot {weapon + 1} (ID {identity})'))
    return tuple(options)


@lru_cache(maxsize=4)
def _mapped_fields(payload):
    fields = [Field('stock_exp', 'Stock EXP / Growth Points', STOCK_EXP_OFFSET, 4, STOCK_EXP_MAXIMUM)]
    for officer in range(OFFICER_COUNT):
        fields.append(Field(f'officer_{officer}_base_attack', f'Officer {officer + 1}: Base attack',
                            OFFICER_BASE + officer * OFFICER_STRIDE + 8, 2,
                            BASE_ATTACK_MAXIMUMS[officer], 'Officer attack', officer + 1,
                            BASE_ATTACK_MINIMUMS[officer]))
        start = OFFICER_BASE + officer * OFFICER_STRIDE
        for key, label, relative, minima, maxima in (
                ('life', 'Life', 4, BASE_LIFE_MINIMUMS, BASE_LIFE_MAXIMUMS),
                ('musou', 'Musou', 6, BASE_MUSOU_MINIMUMS, BASE_MUSOU_MAXIMUMS),
                ('defense', 'Defense', 10, BASE_DEFENSE_MINIMUMS, BASE_DEFENSE_MAXIMUMS),
                ('speed', 'Speed', 12, BASE_SPEED_MINIMUMS, BASE_SPEED_MAXIMUMS)):
            current = int.from_bytes(payload[start + relative:start + relative + 2], 'little')
            # The native reset and independent increment paths establish these
            # ID-specific domains. An unusual original is opaque, not repaired
            # into a plausible stat or made eligible by experimental editing.
            if minima[officer] <= current <= maxima[officer]:
                fields.append(Field(f'officer_{officer}_base_{key}',
                                    f'Officer {officer + 1}: Base {label}',
                                    start + relative, 2, maxima[officer],
                                    'Officer base stats', officer + 1, minima[officer]))
        level = payload[start]
        experience = int.from_bytes(payload[start + 16:start + 20], 'little')
        # Only already progressed records with coherent native EXP qualify.
        # Stay strictly below the next threshold: level/stat/reward changes
        # need the native level-up path and its nonserialized random state.
        if (1 <= level < 98 and LEVEL_EXP_THRESHOLDS[level] <= experience
                < LEVEL_EXP_THRESHOLDS[level + 1]):
            fields.append(Field(f'officer_{officer}_exp_within_level',
                                f'Officer {officer + 1} (level {level + 1}): EXP within current level',
                                start + 16, 4, LEVEL_EXP_THRESHOLDS[level + 1] - 1,
                                'Officer growth', officer + 1, LEVEL_EXP_THRESHOLDS[level],
                                maxable=False))
        equipped_offset = OFFICER_BASE + officer * OFFICER_STRIDE + 1
        options = _equipped_options(payload, officer)
        # Do not repair an unknown/empty equipped reference. A choice only selects
        # a qualified record already present in this officer's own eight-slot pool.
        if payload[equipped_offset] + 1 in dict(options) and len(options) > 1:
            fields.append(Field(f'officer_{officer}_equipped_weapon',
                                f'Officer {officer + 1}: Equipped weapon slot',
                                equipped_offset, 1, 8, 'Equipment', officer + 1, 1,
                                maxable=False, display_bias=1))
        for weapon in range(WEAPON_COUNT):
            start = _weapon_offset(officer, weapon)
            mask = int.from_bytes(payload[start + 2:start + 4], 'little')
            # Preserve structurally unusual weapons; never repair masks or rank bytes.
            if not _qualified_weapon(payload, officer, weapon):
                continue
            prefix = f'officer_{officer}_weapon_{weapon}'
            label = f'Officer {officer + 1}, weapon {weapon + 1}'
            slot = officer * WEAPON_COUNT + weapon + 1
            fields.extend((Field(prefix + '_attack_bonus', label + ': Attack bonus',
                                 start + 7, 1, 20, 'Weapons', slot),
                           Field(prefix + '_attribute_slots', label + ': Attribute slots',
                                 start + 6, 1, 8, 'Weapons', slot, mask.bit_count())))
            for attribute in range(15):
                # Native ranked-attribute fusion skips enum 5; its semantics are unqualified.
                if attribute != 5 and mask & (1 << attribute):
                    fields.append(Field(prefix + f'_attribute_{attribute}_level',
                                        label + f': Attribute ID {attribute} level',
                                        start + 8 + attribute, 1, 10, 'Weapon attributes',
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


def field_options(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('The requested Warriors Orochi Z field is not editable.')
    return _equipped_options(document.payload, field.slot - 1) if key.endswith('_equipped_weapon') else ()


def _validate_equipped(document, field, value):
    field.validate(value)
    if value not in dict(_equipped_options(document.payload, field.slot - 1)):
        raise SaveError('Select a qualified existing weapon from this officer\'s own pool.')


def changed_payload(document, changes):
    mapping = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapping:
            raise SaveError('Only mapped resources and existing weapon properties are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        if key.endswith('_equipped_weapon'):
            _validate_equipped(document, field, value)
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return codec.encode(result) if changes else document.payload


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    if decode(payload, GAME_ID, document.source).payload != payload:
        raise SaveError('Warriors Orochi Z edited copy verification failed.')
    return payload


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapping = field_map(document)
    if key not in mapping:
        raise SaveError('The requested Warriors Orochi Z field is not editable.')
    field = mapping[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        if key.endswith('_equipped_weapon'):
            _validate_equipped(document, field, value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapping = field_map(document)
    changed_payload(document, changes)
    result = {}
    for key in keys:
        if key not in mapping:
            raise SaveError('The requested Warriors Orochi Z field is not editable.')
        field = mapping[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and field.minimum <= current <= field.maximum:
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
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination for the Warriors Orochi Z copy.')
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
    if group in ('Officer attack', 'Officer base stats', 'Officer growth', 'Equipment') and type(slot) is int and 1 <= slot <= OFFICER_COUNT:
        return f'Officer {slot}'
    if type(slot) is int and 1 <= slot <= OFFICER_COUNT * WEAPON_COUNT:
        officer, weapon = divmod(slot - 1, WEAPON_COUNT)
        return f'Officer {officer + 1}: Weapon {weapon + 1}'
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
                         'alchemy': int.from_bytes(document.payload[start + 4:start + 6], 'little'),
                         'capacity': document.payload[start + 6], 'bonus': document.payload[start + 7],
                         'ranks': tuple(document.payload[start + 8:start + 23])})
    return tuple(rows)


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    mapping = field_map(document)
    if key not in mapping:
        raise SaveError('The requested Warriors Orochi Z field is not editable.')
    value = mapping[key]
    if key == 'stock_exp':
        return 'Shared stock EXP / Growth Points. Used by leveling and weapon fusion; cap 99,999.'
    if '_base_' in key:
        return (f'Independent saved base growth stat, range {value.minimum}..{value.maximum} '
                'for this officer. The native per-officer growth clamp supplies the bounds. '
                'Weapon, team-skill and battle effects are separate; level, EXP, proficiency, '
                'skills and rewards remain unchanged. This does not run a level-up transaction.')
    if key.endswith('_exp_within_level'):
        return (f'EXP within the opened level, {value.minimum:,}..{value.maximum:,}. '
                'The next level threshold is excluded. Level, growth stats, rewards, '
                'unlock flags and shared Stock EXP remain unchanged. Bulk Max excludes this control.')
    if key.endswith('_equipped_weapon'):
        return ('Select an existing qualified weapon in this officer\'s own pool. '
                'Displayed slots are 1..8; no weapon is created, moved or consumed. '
                'Base attack, weapon contents, collections and progression remain unchanged.')
    if key.endswith('_attribute_slots'):
        return f'Weapon attribute capacity. Retains all owned attributes; range {value.minimum}..8.'
    if '_attribute_' in key and key.endswith('_level'):
        return 'Existing ranked attribute only, level 1..10. Attribute identity and slot masks are preserved.'
    return 'Existing weapon attack bonus, 0..20. Weapon identity, equipment and alchemy abilities are preserved.'


INTEGRITY_KIND = 'checksum'

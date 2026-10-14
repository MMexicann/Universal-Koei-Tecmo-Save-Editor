"""Native Steam WO3 Ultimate Definitive layout, independently mapped.

See OROCHI_RESEARCH.md for executable, public patch and copied-native evidence.
The file is packed little endian plaintext. Serialized vtable fragments are
layout markers, not checksums; preserve their original ASLR-dependent values.
"""
from dataclasses import dataclass
import hashlib
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.games.wo3u import wo3u_equipment as equipment
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.experimental_limits import within_numeric_limits, experimental_enabled

GAME_ID = 'wo3u'
SAVE_SIZE = 0x2119CA
SIGNATURE = bytes.fromhex('f1180314')
OFFICER_BASE, OFFICER_STRIDE = 0xECF2, 0x2B0
OFFICER_COUNT, SERIALIZED_OFFICER_COUNT = 145, 150
WEAPON_BASE, WEAPON_STRIDE, WEAPON_COUNT = 0xC8010, 0x1C, 145 * 16
# Factual IDs from the public element patch; Verity is corroborated by the
# annotated native sample. Unmapped IDs remain read only.
ATTRIBUTE_NAMES = {5: 'Agility', 6: 'Reach', 7: 'Multi', 8: 'Brawn',
                   9: 'Air', 10: 'Frenzy', 11: 'Cavalier', 31: 'Verity'}
# Native factories and the fusion selector distinguish these binary effects
# from ranked effects. Untranslated native identities retain numeric labels.
ATTRIBUTE_COUNT = 58
BINARY_ATTRIBUTE_IDS = frozenset(range(26, 32)) | frozenset(range(46, 58))
RANKED_ATTRIBUTE_IDS = frozenset(range(ATTRIBUTE_COUNT)) - BINARY_ATTRIBUTE_IDS
UPGRADE_STONE_OFFSET, UPGRADE_STONE_MAXIMUM = 52, 891
MATERIAL_SPANS = ((0xE9A8, 16), (0xE9C8, 16), (0xE9E8, 16),
                  (0xEA08, 34), (0xEA3A, 34), (0xEA6C, 34), (0xEAA8, 145))


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
    storage: str = 'unsigned'
    maxable: bool = True
    kind: str = 'int'

    @property
    def experimental_maximum(self):
        """Largest representable numeric value; protected choices stay bounded."""
        if ('_equipped_item_' in self.id
                or self.id.endswith('_slots')
                or (self.id.startswith('weapon_') and '_rank_' in self.id and self.maximum == 1)):
            return None
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if not within_numeric_limits(value, self.minimum, self.maximum,
                                     storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from '
                            f'{self.minimum:,} to {self.maximum:,}.')

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


_static = [Field('growth_points', 'Unallocated growth points', 0x1378, 4, 9999999, maxable=False),
           Field('gems', 'Precious stones (gems)', 0x137C, 4, 999999, maxable=False)]
for index in range(OFFICER_COUNT):
    for key, name, relative, cap in (
            ('health', 'Health', 0, 999), ('musou', 'Musou', 2, 999),
            ('attack', 'Attack', 4, 999), ('defense', 'Defense', 6, 999),
            ('speed', 'Speed', 8, 180)):
        _static.append(Field(f'officer_{index}_{key}',
                             f'Officer {index + 1}: {name}',
                             OFFICER_BASE + index * OFFICER_STRIDE + relative,
                             2, cap, 'Officers', index + 1))
for index in range(58):
    _static.append(Field(f'orb_{index}', f'Weapon attribute orb {index + 1}',
                         0xE944 + index, 1, 99, 'Attribute orbs', maxable=False))
for family, (base, count) in enumerate(MATERIAL_SPANS):
    for index in range(count):
        _static.append(Field(f'material_{family}_{index}',
                             f'Crafting material family {family + 1}, record {index + 1}',
                             base + index, 1, 99, 'Crafting materials', maxable=False))
FORMAT = Format(GAME_ID, 'Warriors Orochi 3 Ultimate Definitive Edition (Steam PC)',
                SAVE_SIZE, tuple(_static),
                'Native copied-file validation; edited game loading remains untested. '
                'Stats, growth points, gems, attribute orbs, crafting materials and '
                'existing weapon slots/ranked attributes, reinforcement reduction, unallocated upgrade stones and owned ordinary-item equipment. Story, unlocks and promotions '
                'remain unchanged. Five internal officer records are read only.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    seed: int = 0

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('This parser handles native Steam WO3 Ultimate Definitive only.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.bin')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SAVE_SIZE:
        raise SaveError(f'WO3 Ultimate Definitive requires exactly {SAVE_SIZE:,} bytes.')
    raw = bytes(raw)
    if raw[:4] != SIGNATURE:
        raise SaveError('WO3 Ultimate Definitive PC title/revision marker failed.')
    _validate_native(raw)
    return Document(FORMAT, Path(source), raw, raw)


@lru_cache(maxsize=8)
def _validate_native(raw):
    officer_marker = raw[OFFICER_BASE - 10:OFFICER_BASE - 6]
    weapon_marker = raw[WEAPON_BASE - 4:WEAPON_BASE]
    # ASLR changes the upper word. The supported build's vtable offsets and
    # difference qualify the packed revision without normalizing those bytes.
    if (officer_marker[:2] != b'\xa8\x6d' or weapon_marker[:2] != b'\x28\x62'
            or officer_marker[2:] != weapon_marker[2:]):
        raise SaveError('Unsupported WO3 Ultimate Definitive serialized record revision.')
    if any(raw[OFFICER_BASE - 10 + index * OFFICER_STRIDE:
               OFFICER_BASE - 6 + index * OFFICER_STRIDE] != officer_marker
           for index in range(SERIALIZED_OFFICER_COUNT)):
        raise SaveError('WO3 Ultimate Definitive officer layout markers are inconsistent.')
    if any(raw[WEAPON_BASE - 4 + index * WEAPON_STRIDE:
               WEAPON_BASE + index * WEAPON_STRIDE] != weapon_marker
           for index in range(WEAPON_COUNT)):
        raise SaveError('WO3 Ultimate Definitive weapon layout markers are inconsistent.')


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate native Steam SAVEDATA.BIN copy.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format != FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.seed) is not int):
        raise SaveError('Foreign WO3 Ultimate Definitive document.')
    original = decode(document.raw, GAME_ID, document.source)
    if original.payload != document.payload or document.seed != 0:
        raise SaveError('The opened WO3 Ultimate Definitive snapshot was modified externally.')


def _fields(payload):
    return _fields_cached(payload, experimental_enabled())


@lru_cache(maxsize=4)
def _fields_cached(payload, _experimental):
    result = list(FORMAT.fields)
    for officer in range(OFFICER_COUNT):
        offset = OFFICER_BASE + officer * OFFICER_STRIDE
        promotions = payload[offset + 62]
        stones = int.from_bytes(payload[offset + UPGRADE_STONE_OFFSET:
                                        offset + UPGRADE_STONE_OFFSET + 2], 'little')
        # Native promotion/allocation UI treats this as a separate spendable
        # balance and clamps it to 891. Do not enable promotion or normalize an
        # unpromoted or unusual record merely to expose this resource.
        if 1 <= promotions <= 9 and within_numeric_limits(stones, 0, UPGRADE_STONE_MAXIMUM, storage_maximum=65535):
            result.append(Field(f'officer_{officer}_upgrade_stones',
                                f'Officer {officer + 1}: Unallocated upgrade stones',
                                offset + UPGRADE_STONE_OFFSET, 2,
                                UPGRADE_STONE_MAXIMUM, 'Upgrade stones', officer + 1,
                                maxable=False))
    for officer in range(OFFICER_COUNT):
        offset = OFFICER_BASE + officer * OFFICER_STRIDE
        for item_slot in range(equipment.qualified_slots(payload, offset)):
            result.append(Field(f'officer_{officer}_equipped_item_{item_slot}',
                                f'Officer {officer + 1}: Equipped item slot {item_slot + 1}',
                                offset + equipment.EQUIPPED_ITEM_OFFSET + item_slot,
                                1, equipment.EMPTY_ITEM, 'Equipment', officer + 1,
                                maxable=False))
    for index in range(WEAPON_COUNT):
        offset = WEAPON_BASE + index * WEAPON_STRIDE
        identity = int.from_bytes(payload[offset:offset + 2], 'little')
        if not 0 <= identity <= 1394:  # Empty/unknown IDs stay untouched.
            continue
        slots = payload[offset + 2]
        if slots > 8:
            continue
        reinforcement = payload[offset + 3]
        # Native total attack adds this separate byte. Decreasing an ordinary
        # existing value cannot exceed a grade-specific reinforcement ceiling.
        if within_numeric_limits(reinforcement, 1, 99, storage_maximum=255):
            result.append(Field(f'weapon_{index}_reinforcement',
                                f'Weapon {index + 1} (ID {identity}): Reinforcement (decrease only)',
                                offset + 3, 1, reinforcement, 'Weapons', index + 1,
                                maxable=False))
        if slots <= 8:
            result.append(Field(f'weapon_{index}_slots',
                                f'Weapon {index + 1} (ID {identity}): Attribute slots',
                                offset + 2, 1, 8, 'Weapons', index + 1,
                                maxable=not any(identity != 255 for identity in
                                                payload[offset + 4 + slots:offset + 12])))
        for attribute_slot in range(8):
            identity = payload[offset + 4 + attribute_slot]
            if (identity not in RANKED_ATTRIBUTE_IDS and identity != 31
                    or attribute_slot >= slots
                    or payload[offset + 12 + attribute_slot] == 0):
                continue
            cap = 1 if identity == 31 else 10
            result.append(Field(f'weapon_{index}_rank_{attribute_slot}',
                                f'Weapon {index + 1}: {ATTRIBUTE_NAMES.get(identity, f"Attribute ID {identity}")} rank',
                                offset + 12 + attribute_slot, 1, cap,
                                'Weapons', index + 1, minimum=1))
    return tuple(result)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def _field_index(payload):
    return _field_index_cached(payload, experimental_enabled())


@lru_cache(maxsize=4)
def _field_index_cached(payload, _experimental):
    return MappingProxyType({field.id: field for field in _fields(payload)})


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def record_label(slot, group='Officers'):
    if group in ('Upgrade stones', 'Equipment') and slot:
        return f'Officer {slot}'
    if group == 'Weapons' and slot:
        return f'Officer {(slot - 1) // 16 + 1}, weapon {(slot - 1) % 16 + 1}'
    return f'Officer {slot}' if group == 'Officers' and slot else group


def changed_payload(document, changes):
    mapped = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapped:
            raise SaveError('The requested WO3 Ultimate Definitive field is not mapped.')
        field = mapped[key]
        # Slots must neither hide existing nor activate dormant attributes,
        # including unknown IDs whose relationship to the count is unproved.
        field.validate(value)
        if key.startswith('weapon_') and key.endswith('_slots'):
            index = field.slot - 1
            base = WEAPON_BASE + index * WEAPON_STRIDE
            original = document.payload[base + 2]
            if value < original and any(identity != 255 for identity in
                                        document.payload[base + 4 + value:base + 12]):
                raise SaveError('Attribute slots cannot hide existing weapon attributes.')
            if value > original and any(identity != 255 for identity in
                                        document.payload[base + 4 + original:base + 4 + value]):
                raise SaveError('Attribute slots cannot activate dormant weapon attributes.')
        result[field.offset:field.offset + field.size] = field.encoded(value)
    for officer in {mapped[key].slot - 1 for key in changes if '_equipped_item_' in key}:
        equipment.validate_selectors(document.payload, result,
                                     OFFICER_BASE + officer * OFFICER_STRIDE)
    return bytes(result)


def field_options(document, key):
    mapped = field_map(document)
    if key not in mapped:
        raise SaveError('The requested WO3 Ultimate Definitive field is not mapped.')
    return equipment.options(document.payload) if '_equipped_item_' in key else ()


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    reopened = decode(payload, GAME_ID, document.source)
    if reopened.payload != payload:
        raise SaveError('WO3 Ultimate Definitive edited-copy validation failed.')
    return payload


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapped = field_map(document)
    changed_payload(document, changes)
    if key not in mapped:
        raise SaveError('The requested WO3 Ultimate Definitive field is not mapped.')
    result = dict(changes)
    if type(value) is int and value == mapped[key].value(document.payload):
        result.pop(key, None)
    else:
        mapped[key].validate(value)
        result[key] = value
    changed_payload(document, result)
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapped = field_map(document)
    changed_payload(document, changes)
    result = {}
    for key in keys:
        if key not in mapped:
            raise SaveError('The requested WO3 Ultimate Definitive field is not mapped.')
        field = mapped[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and type(current) is int and current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapped = field_map(document)
    changed_payload(document, changes)
    result = dict(changes)
    for key, field in mapped.items():
        if group is not None and field.group != group:
            continue
        current = result.get(key, field.value(document.payload))
        if field.maxable and type(current) is int and current <= field.maximum:
            if field.value(document.payload) == field.maximum:
                result.pop(key, None)
            else:
                result[key] = field.maximum
    changed_payload(document, result)
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    destination = safe_path(destination)
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new .bin destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def inspection_rows(document):
    validate_document(document)
    rows = []
    for index in range(SERIALIZED_OFFICER_COUNT):
        offset = OFFICER_BASE + index * OFFICER_STRIDE
        rows.append({'group': 'Progression', 'label': f'Officer {index + 1}' if index <145
                     else f'Internal record {index + 1}',
                     'value': f'Stored level {document.payload[offset + 17] + 1}; '
                              f'EXP {int.from_bytes(document.payload[offset + 26:offset + 30], "little"):,}; '
                              f'promotions {document.payload[offset + 62]}; '
                              f'unallocated upgrade stones {int.from_bytes(document.payload[offset + 52:offset + 54], "little")}; '
                              f'item slots {document.payload[offset + 44]} (read only)'})
    for index in range(WEAPON_COUNT):
        offset = WEAPON_BASE + index * WEAPON_STRIDE
        identity = int.from_bytes(document.payload[offset:offset + 2], 'little')
        if identity == 65535:
            continue
        attrs = ', '.join(f'{ATTRIBUTE_NAMES.get(identity, "Unmapped ID " + str(identity))} '
                          f'[{document.payload[offset + 12 + slot]}]'
                          for slot, identity in enumerate(document.payload[offset + 4:offset + 12])
                          if identity != 255)
        rows.append({'group': 'Weapons', 'label': record_label(index + 1, 'Weapons'),
                     'value': f'Weapon ID {identity}; slots {document.payload[offset + 2]}; '
                              f'reinforcement {document.payload[offset + 3]}; '
                              f'attributes: {attrs or "none"}; compatibility read only'})
    return tuple(rows)


def field_hint(document, field):
    validate_document(document)
    key = field.id if isinstance(field, Field) else field
    mapped = field_map(document)
    if key not in mapped:
        raise SaveError('The requested WO3 Ultimate Definitive field is not mapped.')
    if mapped[key].group == 'Equipment':
        return ('Choose an already owned ordinary item with a positive existing rank, '
                'or Unequipped. Duplicate items on the same officer are rejected. '
                'Item ownership/ranks, locked slots, mounts, promotions and rewards '
                'are preserved. Item IDs retain numeric labels; excluded from Max.')
    if mapped[key].group == 'Upgrade stones':
        return ('Spendable upgrade stones for an already promoted officer, 0..891. '
                'This changes only the unallocated balance. Promotion count, level, EXP, '
                'allocated stones, item slots, stats and rewards are preserved. '
                'Use the game to allocate stones or perform a promotion. Excluded from Max.')
    if mapped[key].group == 'Officers':
        return ('Stored stat only. Level, EXP, promotion, upgrade-stone allocation, unlocks '
                'and story are preserved. Stat growth may later change this value. '
                'Max preserves higher existing values.')
    if mapped[key].group == 'Weapons':
        if key.endswith('_reinforcement'):
            return ('Decrease an existing ordinary reinforcement bonus, 0 through its opened value. '
                    'Weapon grade, compatibility, identity, fusion costs and equipment are preserved. '
                    'This control is excluded from Max; grade-specific increases remain unavailable.')
        return ('Existing records only. Attribute identities, unknown attributes, weapon ID '
                'and equipped references are preserved. Verity is binary (rank 1); '
                'native ranked effects use ranks 1..10; effects without a proved name retain numeric IDs. '
                'Slots cannot hide or activate dormant attributes.')
    return ('This resource uses a published edit limit, not a proven natural cap, and is excluded from bulk Max. Only this balance changes. Names for numbered crafting/orb records '
            'are not yet mapped. Max preserves higher existing values; it grants no '
            'character, story, recipe or collection unlocks.')

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'none'

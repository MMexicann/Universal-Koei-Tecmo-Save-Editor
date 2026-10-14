"""Original Windows PC SW2 disk records, independently implemented.

The 2008 PC disk editor's reader/writer and field accessors establish this
profile; two independently shared complete native saves qualify it. No upstream
code, player data or extracted game catalogs are included. See SW2_PC_FORMAT.md.
"""
from dataclasses import dataclass
from collections.abc import Mapping
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.verified_editor import Field

GAME_ID = 'sw2'
SAVE_SIZE = 0x22EB4
CHECKSUM_OFFSET = 0x22E94
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xC, 0xEC, 26
GUARD_BASE, GUARD_STRIDE, GUARD_COUNT = 0x1804, 0x2C, 54
WEAPON_RELATIVE_BASE, WEAPON_STRIDE, WEAPON_COUNT = 0x28, 19, 8
STAT_NAMES = ('Life', 'Musou', 'Attack', 'Defense', 'Riding', 'Speed', 'Dexterity / Jump', 'Luck')
OFFICER_NAMES = ('Yukimura Sanada', 'Mitsuhide Akechi', 'Nobunaga Oda', 'Keiji Maeda',
                 'Kenshin Uesugi', 'Oichi', 'Okuni', 'Magoichi Saika', 'Shingen Takeda',
                 'Masamune Date', 'Noh', 'Hanzo Hattori', 'Ranmaru Mori', 'Hideyoshi Toyotomi',
                 'Ieyasu Tokugawa', 'Tadakatsu Honda', 'Ina', 'Mitsunari Ishida',
                 'Nagamasa Azai', 'Sakon Shima', 'Yoshihiro Shimazu', 'Ginchiyo Tachibana',
                 'Kanetsugu Naoe', 'Nene', 'Kotaro Fuma', 'Musashi Miyamoto')
ATTRIBUTE_NAMES = STAT_NAMES + ('Musou charge', 'Range')


def _u32(payload, offset):
    return struct.unpack_from('<I', payload, offset)[0]


@dataclass(frozen=True)
class SkillField(Field):
    """Rank is the low seven bits; the separate high bit remains untouched."""
    @property
    def experimental_maximum(self):
        return 0x7F

    def value(self, payload):
        return payload[self.offset] & 0x7F


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Samurai Warriors 2 (original Windows PC)', SAVE_SIZE, (),
                'Native revision-2 original Windows PC save.dat. Money, stored officer '
                'growth stats, acquired ordinary skill ranks, existing weapon bonuses and own-pool weapon selection. '
                'Individual numeric edits use storage bounds; bulk Max is unavailable '
                'where natural limits are unproven. Level/EXP, ownership, other equipped '
                'references, rare skills, mounts, guards, rewards and story are preserved. '
                'Two genuine-file roundtrips qualified; edited game loading is untested.')


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
        raise SaveError('Select original Samurai Warriors 2 for Windows PC.')
    return FORMAT


@lru_cache(maxsize=8)
def _validate_raw(raw):
    if len(raw) != SAVE_SIZE:
        raise SaveError('Original SW2 PC revision 2 requires exactly 143,028 bytes; HD and console saves are unsupported.')
    if struct.unpack_from('<H', raw, 4)[0] != 2:
        raise SaveError('Unsupported original SW2 PC save revision; revision 2 is required.')
    if (sum(raw[:CHECKSUM_OFFSET]) & 0xFFFFFFFF) != _u32(raw, CHECKSUM_OFFSET):
        raise SaveError('SW2 PC native checksum mismatch; damaged input is not repaired.')


def decode(raw, game_id=GAME_ID, source=None):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise SaveError('SW2 PC input must be save bytes.')
    if (raw.nbytes if isinstance(raw, memoryview) else len(raw)) != SAVE_SIZE:
        raise SaveError('Original SW2 PC revision 2 requires exactly 143,028 bytes.')
    raw = bytes(raw)
    _validate_raw(raw)
    return Document(FORMAT, Path(source) if source is not None else Path('copy.dat'), raw, raw)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Choose an original SW2 PC .dat copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('A preserved original SW2 PC snapshot is required.')
    _validate_raw(document.raw)


@lru_cache(maxsize=8)
def _fields(payload):
    fields = [Field('money', 'Money (stored balance)', 0x2150, 4, 0xFFFFFFFF,
                    'Resources', maxable=False)]
    for officer in range(OFFICER_COUNT):
        base = OFFICER_BASE + officer * OFFICER_STRIDE
        # Ownership is a separate bitset. Never expose locked officers' growth.
        if not payload[0x214C + officer // 8] & (1 << (officer % 8)):
            continue
        if _weapon_choices(payload, officer):
            fields.append(Field(f'officer_{officer}_equipped_weapon', 'Equipped existing own-pool weapon',
                                base + 0xC0, 1, WEAPON_COUNT - 1, 'Equipment',
                                officer + 1, maxable=False, experimental=False))
        for stat, label in enumerate(STAT_NAMES):
            fields.append(Field(f'officer_{officer}_stat_{stat}', f'{label} (stored growth)',
                                base + stat * 4, 4, 0xFFFFFFFF, 'Officer growth',
                                officer + 1, maxable=False))
        for skill in range(40):
            offset = base + 0xC1 + skill
            # Rare category-end ranks depend on shop/Survival rewards. Existing
            # ordinary ownership is retained; editing rank never acquires a skill.
            if skill % 10 == 9 or not payload[offset] & 0x7F:
                continue
            fields.append(SkillField(f'officer_{officer}_skill_{skill}',
                                     f'{("Might", "Growth", "Battle", "Special")[skill // 10]} skill {skill % 10 + 1} rank',
                                     offset, 1, 3, 'Acquired skills', officer + 1,
                                     minimum=1, maxable=False))
        for weapon in range(WEAPON_COUNT):
            offset = base + WEAPON_RELATIVE_BASE + weapon * WEAPON_STRIDE
            identity, count = payload[offset], payload[offset + 18]
            if identity >= 104 or identity // 4 != officer or not 1 <= count <= 8:
                continue
            for attribute in range(count):
                kind = payload[offset + 2 + attribute]
                if kind >= len(ATTRIBUTE_NAMES):
                    continue
                fields.append(Field(f'officer_{officer}_weapon_{weapon}_bonus_{attribute}',
                                    f'Weapon {weapon + 1}: {ATTRIBUTE_NAMES[kind]} bonus {attribute + 1}',
                                    offset + 10 + attribute, 1, 255, 'Weapon bonuses',
                                    officer + 1, maxable=False))
    return tuple(fields)


def _weapon_choices(payload, officer):
    base = OFFICER_BASE + officer * OFFICER_STRIDE + WEAPON_RELATIVE_BASE
    return tuple(slot for slot in range(WEAPON_COUNT)
                 if payload[base + slot * WEAPON_STRIDE] < 104
                 and payload[base + slot * WEAPON_STRIDE] // 4 == officer
                 and 1 <= payload[base + slot * WEAPON_STRIDE + 18] <= 8)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def _validate_edit(field, value, original):
    if type(value) is not int:
        raise SaveError('A whole-number edit value is required.')
    if value != original:
        field.validate(value)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str:
        raise SaveError('Choose a mapped SW2 PC field name.')
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('This SW2 PC field/owned record is not qualified for editing.')
    original = field.value(document.payload)
    _validate_edit(field, value, original)
    result = dict(changes)
    if value == original:
        result.pop(key, None)
    else:
        result[key] = value
    changed_payload(document, result)
    return result


def changed_payload(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Staged SW2 PC edits must be a field/value mapping.')
    mapped = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str:
            raise SaveError('Choose a mapped SW2 PC field name.')
        field = mapped.get(key)
        if field is None:
            raise SaveError('This SW2 PC field/owned record is not qualified for editing.')
        _validate_edit(field, value, field.value(document.payload))
        if (field.group == 'Equipment' and value != field.value(document.payload)
                and value not in _weapon_choices(document.payload, field.slot - 1)):
            raise SaveError('Equip an existing known weapon belonging to this owned officer.')
        if isinstance(field, SkillField):
            result[field.offset] = (document.payload[field.offset] & 0x80) | value
        else:
            result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    if result != document.payload:
        struct.pack_into('<I', result, CHECKSUM_OFFSET, sum(result[:CHECKSUM_OFFSET]) & 0xFFFFFFFF)
    raw = bytes(result)
    _validate_raw(raw)
    return raw


def serialize(document, changes):
    raw = changed_payload(document, changes)
    decode(raw)
    return raw


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapped = field_map(document)
    if any(type(key) is not str or key not in mapped for key in keys):
        raise SaveError('An unmapped SW2 PC field cannot be maximized.')
    return {}  # Storage ceilings are not natural gameplay limits.


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


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
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination.')
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
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Officer growth'):
    return OFFICER_NAMES[slot - 1] if 1 <= slot <= OFFICER_COUNT else group


def field_options(document, field):
    key = field.id if isinstance(field, Field) else field
    mapped = field_map(document).get(key)
    if mapped is None:
        raise SaveError('Choose a qualified original SW2 PC field.')
    if mapped.group == 'Equipment':
        return tuple((slot, f'Existing own-pool weapon {slot + 1}')
                     for slot in _weapon_choices(document.payload, mapped.slot - 1))
    return ()


def field_hint(document, field):
    mapped = field_map(document)[field.id if isinstance(field, Field) else field]
    if mapped.group == 'Equipment':
        return ('Choose an existing known weapon in this already owned officer\'s eight-slot pool. '
                'This changes only the equipped reference; no acquisition, identity, element, '
                'bonus or reward is changed. Max leaves choices unchanged.')
    if mapped.group == 'Acquired skills':
        return ('Changes only the rank of an acquired ordinary skill, preserving its high flag bit. '
                'Rare and unacquired skills stay unchanged. Level, EXP and reward prerequisites are separate.')
    if mapped.group == 'Weapon bonuses':
        return ('Changes one existing attribute amount, preserving weapon identity, attribute type, '
                'element, occupied-slot count and equipped reference. 255 is a byte storage bound, '
                'not a natural maximum; bulk Max does not change this field.')
    return ('Individual edit to a stored unsigned 32-bit value; its storage bound is not a natural '
            'gameplay maximum. Bulk Max leaves it unchanged. Ownership, equipment, level/EXP, '
            'story and rewards are preserved; displayed totals may include skill/weapon effects.')


def inspection_rows(document):
    validate_document(document)
    payload, rows = document.payload, []
    for officer, name in enumerate(OFFICER_NAMES):
        base = OFFICER_BASE + officer * OFFICER_STRIDE
        owned = bool(payload[0x214C + officer // 8] & (1 << (officer % 8)))
        rows.append({'group': 'Officers', 'label': name,
                     'value': f'Owned: {owned}; level {payload[base + 0x24] + 1}; EXP {_u32(payload, base + 0x20):,}; '
                              f'equipped weapon index {payload[base + 0xC0]}; unique skill ID {payload[base + 0xE9]}.'})
        for weapon in range(WEAPON_COUNT):
            offset = base + WEAPON_RELATIVE_BASE + weapon * WEAPON_STRIDE
            if payload[offset] == 0x7F:
                continue
            rows.append({'group': 'Weapons', 'label': f'{name} / weapon {weapon + 1}',
                         'value': f'Weapon ID {payload[offset]}; element ID {payload[offset + 1]}; '
                                  f'occupied bonuses {payload[offset + 18]}; '
                                  f'attribute IDs {list(payload[offset + 2:offset + 10])}; '
                                  f'amounts {list(payload[offset + 10:offset + 18])}.'})
    for guard in range(GUARD_COUNT):
        base = GUARD_BASE + guard * GUARD_STRIDE
        rows.append({'group': 'Guards', 'label': f'Guard catalog record {guard + 1}',
                     'value': f'Level {payload[base + 0x24] + 1}; EXP {_u32(payload, base + 0x20):,}; '
                              + '; '.join(f'{label} {_u32(payload, base + i * 4)}' for i, label in enumerate(STAT_NAMES))})
    return tuple(rows)


INTEGRITY_KIND = 'checksum'

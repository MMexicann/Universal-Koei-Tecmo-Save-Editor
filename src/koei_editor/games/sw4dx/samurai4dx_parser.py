"""Qualified native Samurai Warriors 4 DX PC editing, revision 0x39EA.

Mappings follow native code, corroborated with a freely shared native save.
Unknown records, story completion, equipment identities and derived progression
stay unchanged. See SAMURAI_RESEARCH.md for evidence and per-mechanic blockers.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.experimental_limits import within_numeric_limits
import koei_editor.games.sw4dx.samurai4dx_codec as codec

GAME_ID = 'samurai4dx'
SAVE_SIZE = codec.SAVE_SIZE
SERIALIZED_INTEGRITY_RANGES = tuple((offset, offset + 4)
                                    for offset in codec.CHECKSUM_OFFSETS)
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xC7E, 0x44, 55
WEAPON_BASE, WEAPON_STRIDE, WEAPON_OWNERS, WEAPON_SLOTS = 0x3DE6, 0x22, 60, 8
GOLD_OFFSET, GEM_BASE = 0x7DA6, 0x7E20
SKILL_NAMES = (
    'Potency', 'Range', 'Courage', 'Impact', 'Fury', 'Underdog', 'Momentum',
    'Clarity', 'Verity', 'Concentration', 'Fortitude', 'Stability', 'Elasticity',
    'Bravery', 'Determination', 'Resolve', 'Nullification', 'Zeal', 'Conviction',
    'Resurrection', 'Alacrity', 'Blaze', 'Shock', 'Frost', 'Wind', 'Diamond',
    'Reaper', 'Rampage', 'Impulse', 'Awakening', 'Cavalry', 'Equestrian',
    'Connoisseur', 'Collector', 'Hoarder', 'Constitution', 'Expert', 'Endurance',
    'Paladin', 'Stimulus',
)


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
        if self.storage != 'unsigned' or self.id.endswith('_equipped_weapon'):
            return None
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        stored = int.from_bytes(payload[self.offset:self.offset + self.size], 'little')
        if self.storage == 'skill-active':
            return int(not stored & 1)
        return stored & 1 if self.storage == 'officer-unlock' else stored

    def validate(self, value):
        if not within_numeric_limits(value, self.minimum, self.maximum,
                                     storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from '
                            f'{self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value, original):
        self.validate(value)
        if self.storage == 'skill-active':
            value = (original & ~1) | (1 - value)
        elif self.storage == 'officer-unlock':
            # Story reward routine sets playable + new badge, preserving other bits.
            value = original if original & 1 else original | 5
        return value.to_bytes(self.size, 'little')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True


_BASE_FIELDS = (Field('gold', 'Gold', GOLD_OFFSET, 4, 999999),) + tuple(
    Field(f'gem_{i}', f'Gem type {i + 1}', GEM_BASE + i, 1, 99) for i in range(8))
FORMAT = Format(GAME_ID, 'Samurai Warriors 4 DX (PC)', SAVE_SIZE, _BASE_FIELDS,
                'Native PC revision 0x39EA. Gold, eight gem types, standard officer '
                'base stats, playable unlocks, equipped weapon slots and existing weapon skills. Character names and gem '
                'type names are not yet qualified. Level, EXP, proficiency, mounts, '
                'items, custom characters, Chronicle and story remain read only.')


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
        raise SaveError('This parser handles Samurai Warriors 4 DX native PC saves only.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)):
        raise SaveError('Samurai Warriors 4 DX requires native save bytes.')
    raw = bytes(raw)
    payload, seed = codec.decode_envelope(raw)
    return Document(FORMAT, Path(source), raw, payload, seed)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native PC .dat save copy.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.seed) is not int):
        raise SaveError('Unregistered Samurai Warriors 4 DX document.')
    payload, seed = codec.decode_envelope(document.raw)
    if payload != document.payload or seed != document.seed:
        raise SaveError('The opened Samurai Warriors 4 DX snapshot was changed outside editing.')


def record_label(slot, group='Officers'):
    if group in ('Officers', 'Unlocks', 'Equipment') and 1 <= slot <= OFFICER_COUNT:
        return f'Standard officer {slot} (ID {slot - 1})'
    if group == 'Weapons' and slot:
        owner, weapon = divmod(slot - 1, WEAPON_SLOTS)
        return f'Weapon family {owner + 1}, slot {weapon + 1}'
    return group


@lru_cache(maxsize=4)
def _fields(payload):
    result = list(_BASE_FIELDS)
    for index in range(OFFICER_COUNT):
        officer = OFFICER_BASE + index * OFFICER_STRIDE
        equipped = payload[officer + 0x3B]
        weapon = WEAPON_BASE + (index * WEAPON_SLOTS + equipped) * WEAPON_STRIDE
        starter_ready = (equipped < WEAPON_SLOTS
                         and int.from_bytes(payload[weapon:weapon + 2], 'little') < 180)
        if payload[officer + 0x3F] & 1 or starter_ready:
            result.append(Field(f'officer_{index}_unlocked', 'Playable (1 unlock)',
                                officer + 0x3F, 1, 1, 'Unlocks', index + 1,
                                minimum=1, storage='officer-unlock'))
        result.append(Field(f'officer_{index}_equipped_weapon',
                            'Equipped weapon slot (0 first / 7 last)',
                            OFFICER_BASE + index * OFFICER_STRIDE + 0x3B,
                            1, 7, 'Equipment', index + 1, maxable=False))
        for key, label, relative in (('health', 'Base health', 0x20),
                                     ('attack', 'Base attack', 0x22),
                                     ('defense', 'Base defense', 0x24),
                                     ('riding', 'Base riding', 0x26),
                                     ('speed', 'Base speed', 0x28)):
            result.append(Field(f'officer_{index}_{key}', label,
                                OFFICER_BASE + index * OFFICER_STRIDE + relative,
                                2, 65535, 'Officers', index + 1, maxable=False))
    for owner in range(WEAPON_OWNERS):
        for weapon in range(WEAPON_SLOTS):
            record = WEAPON_BASE + (owner * WEAPON_SLOTS + weapon) * WEAPON_STRIDE
            identity = int.from_bytes(payload[record:record + 2], 'little')
            if identity >= 180:  # Empty 180 and foreign/unusual identities remain untouched.
                continue
            for skill in range(8):
                skill_id = payload[record + 0xA + skill]
                ceiling = payload[record + 2 + skill]
                if (skill_id >= len(SKILL_NAMES) or not 1 <= ceiling <= 5
                        or payload[record + 0x12 + skill] == 0):
                    continue
                prefix = f'weapon_{owner}_{weapon}_skill_{skill}'
                name = f'Skill {skill + 1}: {SKILL_NAMES[skill_id]}'
                slot = owner * WEAPON_SLOTS + weapon + 1
                result.append(Field(prefix + '_rank', name + ' level',
                                    record + 0x12 + skill, 1, ceiling,
                                    'Weapons', slot, minimum=1))
                result.append(Field(prefix + '_active', name + ' active (0 locked / 1 active)',
                                    record + 0x1A + skill, 1, 1, 'Weapons', slot,
                                    storage='skill-active', maxable=False))
    return tuple(result)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


def field_map(document):
    return MappingProxyType({f.id: f for f in fields_for(document)})


def changed_payload(document, changes):
    mapped = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapped:
            raise SaveError('The requested field is not mapped for this existing save record.')
        field = mapped[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        if key.endswith('_equipped_weapon'):
            field.validate(value)
            owner = field.slot - 1
            base = WEAPON_BASE + (owner * WEAPON_SLOTS + value) * WEAPON_STRIDE
            if int.from_bytes(document.payload[base:base + 2], 'little') >= 180:
                raise SaveError('Equip a mapped, occupied weapon slot belonging to this officer.')
        result[field.offset:field.offset + field.size] = field.encoded(value, result[field.offset])
        if (field.group == 'Weapons' and key.endswith('_rank') and value == 5
                and value != field.value(document.payload)):
            # Native special-gem upgrade and DLC construction set this bit at level 5.
            # It is a consumed-unlock marker: lower ranks never clear it.
            result[field.offset + 8] |= 2
    return bytes(result)


def serialize(document, changes):
    return codec.encode_envelope(document.raw, changed_payload(document, changes))


def stage(document, changes, key, value):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapped = field_map(document)
    if key not in mapped:
        raise SaveError('The requested field is not mapped for this existing save record.')
    field = mapped[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        if key.endswith('_equipped_weapon'):
            changed_payload(document, {key: value})
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapped = field_map(document)
    changed_payload(document, changes)
    result = {}
    for key in keys:
        if key not in mapped:
            raise SaveError('The requested field is not mapped for this existing save record.')
        field = mapped[key]
        current = changes.get(key, field.value(document.payload))
        minimum = 0 if field.storage == 'officer-unlock' else field.minimum
        if field.maxable and type(current) is int and minimum <= current <= field.maximum:
            result[key] = field.maximum
    return result


def maximums(document, changes, group=None):
    changes = normalize_pending_values(document, changes, field_map(document))
    mapped = field_map(document)
    result = dict(changes)
    keys = [f.id for f in mapped.values() if group is None or f.group == group]
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result


def review(document, changes):
    changed_payload(document, changes)
    return [(f, f.value(document.payload), changes[f.id])
            for f in fields_for(document) if f.id in changes]


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


def field_options(document, field):
    """Native choices from qualified opened records, without creating items."""
    key = field.id if isinstance(field, Field) else field
    mapped = field_map(document).get(key)
    if mapped is None:
        raise SaveError('Choose a mapped Samurai Warriors 4 DX field.')
    if mapped.group == 'Equipment':
        owner = mapped.slot - 1
        choices = []
        for slot in range(WEAPON_SLOTS):
            base = WEAPON_BASE + (owner * WEAPON_SLOTS + slot) * WEAPON_STRIDE
            identity = int.from_bytes(document.payload[base:base + 2], 'little')
            if identity >= 180:
                continue
            skills = [SKILL_NAMES[sid] for sid in document.payload[base + 10:base + 18]
                      if sid < len(SKILL_NAMES)]
            label = f'Weapon {slot + 1} (ID {identity})'
            if skills:
                label += ': ' + ', '.join(skills)
            choices.append((slot, label))
        return tuple(choices)
    if mapped.storage == 'skill-active':
        return ((0, 'Locked'), (1, 'Active'))
    if mapped.storage == 'officer-unlock':
        return ((1, 'Playable (native new-character badge)'),)
    return ()


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    mapped = field_map(document)[key]
    if mapped.group == 'Unlocks':
        return ('Unlock this standard officer and set the native new-character badge. '
                'Other flags, story completion, level and EXP are preserved. '
                'Relocking is unavailable because campaign requirements are not mapped.')
    if mapped.group == 'Equipment':
        return ('Choose an occupied existing weapon slot from this officer\'s own pool. '
                '0 is the first slot, 7 the last. Empty/unknown weapons are rejected. '
                'Weapon identity, skills and inventory records remain unchanged.')
    if mapped.group == 'Weapons':
        if key.endswith('_rank'):
            return (f'Existing skill ceiling: {mapped.maximum}. Max raises the current level '
                    'to this weapon\'s stored ceiling, preserving higher existing levels and '
                    'the skill\'s locked state. Level 5 records the native special-gem marker. '
                    'Skill identity and ceiling are retained.')
        return ('Activate or lock an existing attached skill. Only flag bit 0 changes; '
                'unknown flags, level, skill identity and ceiling are preserved. '
                'Activation is excluded from bulk Max.')
    if mapped.group == 'Officers':
        return ('Stored base stat, before weapon effects. 65,535 is its storage bound, '
                'not a gameplay maximum; excluded from Max. Level, EXP, proficiency '
                'and growth dependencies remain unchanged.')
    return (f'Native gameplay cap {mapped.maximum:,}. Max preserves higher existing values. '
            'Story, spending history and equipped items remain unchanged.')


def inspection_rows(document):
    validate_document(document)
    p = document.payload
    rows = []
    for index in range(OFFICER_COUNT):
        base = OFFICER_BASE + OFFICER_STRIDE * index
        value = lambda rel, size=4: int.from_bytes(p[base + rel:base + rel + size], 'little')
        proficiency = ', '.join(f'{p[base + 0x2A + i]} ({value(0x10 + i * 4):,} EXP)'
                                for i in range(4))
        rows.append({'group': 'Officers', 'label': record_label(index + 1),
                     'value': f'Level {value(0xC)}; EXP {value(8):,}; proficiency levels '
                              f'and EXP: {proficiency}; equipped weapon slot '
                              f'{p[base + 0x3B] + 1}; mount ID {p[base + 0x3D]}; '
                              f'unlock flags 0x{p[base + 0x3F]:02X} (read only)'})
    for owner in range(WEAPON_OWNERS):
        for weapon in range(WEAPON_SLOTS):
            base = WEAPON_BASE + (owner * WEAPON_SLOTS + weapon) * WEAPON_STRIDE
            identity = int.from_bytes(p[base:base + 2], 'little')
            if identity == 180:
                continue
            skills = []
            for i in range(8):
                sid = p[base + 0xA + i]
                if sid == 40:
                    continue
                name = SKILL_NAMES[sid] if sid < len(SKILL_NAMES) else f'Unknown skill ID {sid}'
                skills.append(f'{name} {p[base + 0x12 + i]}/{p[base + 2 + i]} '
                              f'({"locked" if p[base + 0x1A + i] & 1 else "active"}; '
                              f'flags 0x{p[base + 0x1A + i]:02X})')
            rows.append({'group': 'Weapons',
                         'label': record_label(owner * WEAPON_SLOTS + weapon + 1, 'Weapons'),
                         'value': f'Weapon ID {identity}; ' + '; '.join(skills)})
    rows.append({'group': 'History', 'label': 'Gold spent / lifetime kills (read only)',
                 'value': f'{int.from_bytes(p[0x7DAA:0x7DAE], "little"):,} / '
                          f'{int.from_bytes(p[0x7DAE:0x7DB2], "little"):,}'})
    return tuple(rows)

# Integrity validated by this backend, separately from sample qualification.
INTEGRITY_KIND = 'checksum'

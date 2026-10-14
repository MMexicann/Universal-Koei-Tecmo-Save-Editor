"""Qualified existing equipment fields in native Windows DW5 Special saves.

The direct-save guide, independently inspected legacy editor and genuine public
save corroborate this profile. See docs/DW5_SPECIAL.md for scope and blockers.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw5special import dw5special_codec as codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.experimental_limits import within_numeric_limits, experimental_enabled

GAME_ID = 'dw5special'
SAVE_SIZE = codec.SAVE_SIZE
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xEC, 88, 48
WEAPON_RELATIVE, WEAPON_STRIDE, WEAPON_COUNT = 20, 16, 4
ITEM_BASE = 0x1534
OFFICER_NAMES = (
    'Zhao Yun', 'Guan Yu', 'Zhang Fei', 'Xiahou Dun', 'Dian Wei', 'Xu Zhu',
    'Zhou Yu', 'Lu Xun', 'Taishi Ci', 'Diaochan', 'Zhuge Liang', 'Cao Cao',
    'Lu Bu', 'Sun Shangxiang', 'Liu Bei', 'Sun Jian', 'Sun Quan', 'Dong Zhuo',
    'Yuan Shao', 'Ma Chao', 'Huang Zhong', 'Xiahou Yuan', 'Zhang Liao', 'Sima Yi',
    'Lu Meng', 'Gan Ning', 'Jiang Wei', 'Zhang Jiao', 'Xu Huang', 'Zhang He',
    'Zhenji', 'Huang Gai', 'Sun Ce', 'Wei Yan', 'Pang Tong', 'Meng Huo', 'Zhurong',
    'Da Qiao', 'Xiao Qiao', 'Cao Ren', 'Zhou Tai', 'Yueying', 'Cao Pi', 'Pang De',
    'Ling Tong', 'Guan Ping', 'Xingcai', 'Zuo Ci')
ITEM_NAMES = ('Peacock Amulet', 'Dragon Amulet', 'Tiger Amulet', 'Tortoise Amulet',
              'Speed Scroll', "Huang's Bow", 'Horned Helm', 'Seven Star Sash',
              'Ginseng', 'Elixir')
ATTRIBUTE_NAMES = ('Life', 'Musou', 'Attack', 'Defense', 'Speed', 'Bow',
                   'Horse', 'Luck', 'Musou charge', 'Charge attack')
WEIGHT_OPTIONS = ((0, 'Light'), (1, 'Standard'), (2, 'Heavy'))
SPECIAL_ITEM_NAMES = ('Fire Orb', 'Ice Orb', 'Shadow Orb', 'Light Orb',
                      'Red Hare Harness', 'Hex Mark Harness', 'Storm Harness',
                      'Shadow Harness', 'Elephant Harness', 'Art of War',
                      'Survival Guide', 'Bodyguard Manual', 'Demon Band',
                      'Way of Musou', 'Wind Scroll', 'Fire Arrows', 'Arm Guards',
                      'Tiger Collar', 'Reversal Charm', 'Musou Armor',
                      'Herbal Remedy', 'Tiger Stone', 'Tortoise Stone',
                      'Flying Dragon Armor', 'Extreme Musou Scroll',
                      'Ice Arrows', 'Absorb Armor', 'Meat Bun Sack',
                      'Divine Hoof')


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int = 1
    maximum: int = 19
    group: str = 'Items'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'

    @property
    def experimental_maximum(self):
        return None if self.id.endswith('_weight') else 255

    def value(self, payload):
        return payload[self.offset]

    def validate(self, value):
        if not within_numeric_limits(value, self.minimum, self.maximum,
                                     storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a value from {self.minimum} to {self.maximum}.')

    def encoded(self, value):
        self.validate(value)
        return bytes([value])


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Dynasty Warriors 5 Special (native Windows)', SAVE_SIZE, (),
                'Existing ordinary item and weapon attribute ranks, stored attack adjustment, weight choices and stored officer Attack/Defense. '
                'Merit/title growth, ownership, equipment identity and story progression remain unchanged.')


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
        raise SaveError('Select native Windows Dynasty Warriors 5 Special.')
    return FORMAT



def decode(raw, game_id=GAME_ID, source=Path('special-copy.dat')):
    get_format(game_id)
    frozen = codec.freeze(raw)
    payload = codec.decode(frozen)
    return Document(FORMAT, Path(source), frozen, payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native Windows Special save.dat copy.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError('A frozen native Windows DW5 Special snapshot is required.')
    if codec.decode(document.raw) != document.payload:
        raise SaveError('The opened DW5 Special snapshot was changed externally.')


def _mapped_fields(payload):
    return _mapped_fields_cached(payload, experimental_enabled())


@lru_cache(maxsize=4)
def _mapped_fields_cached(payload, _experimental):
    fields = []
    for identity, name in enumerate(ITEM_NAMES):
        if within_numeric_limits(payload[ITEM_BASE + identity], 0, 19, storage_maximum=255):
            fields.append(Field(f'item_{identity}_rank', f'{name}: rank (0 = level 1)',
                                ITEM_BASE + identity, slot=identity + 1))
    for identity, name in enumerate(OFFICER_NAMES):
        officer = OFFICER_BASE + identity * OFFICER_STRIDE
        if payload[officer] != 1:
            continue
        for key, label, relative in (('attack', 'Stored base attack', 6),
                                     ('defense', 'Stored base defense', 7)):
            fields.append(Field(f'officer_{identity}_{key}', f'{name}: {label}',
                                officer + relative, maximum=255, group='Officer base stats',
                                slot=identity + 1))
        for weapon in range(WEAPON_COUNT):
            start = officer + WEAPON_RELATIVE + weapon * WEAPON_STRIDE
            # Restrict identity to this officer's four native weapon IDs. Unknown,
            # empty or cross-family records remain read-only and unchanged.
            if payload[start] // 4 != identity or payload[start + 1] != 0:
                continue
            prefix = f'officer_{identity}_weapon_{weapon}'
            label = f'{name} / weapon {weapon + 1}'
            slot = identity * WEAPON_COUNT + weapon + 1
            if payload[start + 2] <= 2:
                fields.append(Field(prefix + '_weight', label + ': weight', start + 2,
                                    maximum=2, group='Weapon weights', slot=slot))
            if within_numeric_limits(payload[start + 14], 0, 40, storage_maximum=255):
                fields.append(Field(prefix + '_attack', label + ': stored attack adjustment', start + 14,
                                    maximum=40, group='Weapon attack adjustment', slot=slot))
            for attribute in range(5):
                at = start + 4 + attribute * 2
                if payload[at] < len(ATTRIBUTE_NAMES) and within_numeric_limits(payload[at + 1], 0, 19, storage_maximum=255):
                    fields.append(Field(prefix + f'_attribute_{attribute}',
                                        label + ': ' + ATTRIBUTE_NAMES[payload[at]] + ' rank (0 = level 1)',
                                        at + 1, group='Weapon attributes', slot=slot))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _mapped_fields(document.payload)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Pending Special edits must be a field/value mapping.')
    mapping = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only qualified existing Special item and weapon fields are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        result[field.offset:field.offset + field.size] = field.encoded(value)
    result[codec.CHECKSUM_OFFSET:codec.CHECKSUM_OFFSET + 4] = sum(
        result[:codec.CHECKSUM_OFFSET]).to_bytes(4, 'little')
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    raw = codec.encode(payload, document.raw)
    if decode(raw, GAME_ID, document.source).payload != payload:
        raise SaveError('DW5 Special edited copy verification failed.')
    return raw


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('The requested Special field is not editable.')
    field = mapping[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    mapping = field_map(document)
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in mapping:
            raise SaveError('The requested Special field is not editable.')
    return {}  # Manual edits only; natural progression and reward dependencies are not bulk actions.


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
                           document.source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new .dat destination for the Special copy.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened Special copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, GAME_ID))


def record_label(slot, group='Items'):
    if group == 'Officer base stats' and type(slot) is int and 1 <= slot <= OFFICER_COUNT:
        return OFFICER_NAMES[slot - 1]
    if group == 'Items' and type(slot) is int and 1 <= slot <= len(ITEM_NAMES):
        return ITEM_NAMES[slot - 1]
    if type(slot) is int and 1 <= slot <= OFFICER_COUNT * WEAPON_COUNT:
        officer, weapon = divmod(slot - 1, WEAPON_COUNT)
        return f'{OFFICER_NAMES[officer]} / weapon {weapon + 1}'
    return group


def field_options(document, field):
    key = field.id if isinstance(field, Field) else field
    if type(key) is not str:
        raise SaveError('Choose a mapped Windows Special field name.')
    if key not in field_map(document):
        raise SaveError('The requested Special field is not editable.')
    return WEIGHT_OPTIONS if key.endswith('_weight') else ()


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    if key not in field_map(document):
        raise SaveError('The requested Special field is not editable.')
    if field_map(document)[key].group == 'Officer base stats':
        return ('Stored base stat on an already playable officer; displayed battle totals also '
                'include equipment. Manual byte storage bounds only, excluded from Max. '
                'Merit, title, Life/Musou, ownership, weapons and rewards are preserved.')
    return ('Existing equipment only. Weapon attack is the stored adjustment byte; '
            'base/battle total is separate. Stored rank 0 means level 1; rank 19 means level 20. '
            'Weight is a choice. Max leaves these fields unchanged. '
            'Ownership, identity, officer growth and story progression are preserved.')


def inspection_records(document):
    """Named records, retaining raw values rather than inferring rewards/levels."""
    validate_document(document)
    payload = document.payload
    def u16(offset):
        return int.from_bytes(payload[offset:offset + 2], 'little')
    def u32(offset):
        return int.from_bytes(payload[offset:offset + 4], 'little')
    officers, weapons, bodyguards = [], [], []
    for identity, name in enumerate(OFFICER_NAMES):
        start = OFFICER_BASE + identity * OFFICER_STRIDE
        officers.append((identity, name, payload[start], payload[start + 1],
                         u16(start + 2), u16(start + 4), payload[start + 6],
                         payload[start + 7], u16(start + 8), payload[start + 10],
                         payload[start + 18], u32(start + 84)))
        for weapon in range(WEAPON_COUNT):
            at = start + WEAPON_RELATIVE + weapon * WEAPON_STRIDE
            attributes = []
            for slot in range(5):
                effect, rank = payload[at + 4 + slot * 2:at + 6 + slot * 2]
                label = ATTRIBUTE_NAMES[effect] if effect < len(ATTRIBUTE_NAMES) else f'ID {effect}'
                attributes.append(f'{label}: {rank}')
            weapons.append((identity, name, weapon + 1, payload[at], payload[at + 1],
                            dict(WEIGHT_OPTIONS).get(payload[at + 2], f'ID {payload[at + 2]}'),
                            payload[at + 3], payload[at + 14],
                            ' / '.join(attributes), payload[at + 15]))
    items = tuple((identity, name, payload[ITEM_BASE + identity])
                  for identity, name in enumerate(ITEM_NAMES + SPECIAL_ITEM_NAMES))
    for identity in range(8):
        start = 0x1970 + identity * 36
        # Region-specific name encoding is not guessed. Display original bytes.
        name_bytes = payload[start + 1:start + 9].split(b'\0', 1)[0].hex(' ')
        bodyguards.append((identity + 1, payload[start], name_bytes,
                           payload[start + 10], payload[start + 11],
                           payload[start + 18], payload[start + 19],
                           u16(start + 20), u16(start + 22), payload[start + 24],
                           payload[start + 25], payload[start + 26], payload[start + 32]))
    shura = (('Starting bonus iron', u32(0x5128)), ('Gold', u32(0x51B8)),
             ('Iron', u32(0x51BC)))
    return {'officers': tuple(officers), 'weapons': tuple(weapons),
            'items': items, 'bodyguards': tuple(bodyguards), 'shura': shura}


INTEGRITY_KIND = 'checksum'

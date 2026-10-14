"""Narrow source-backed All-Stars PC available-gold editor.

Native serializers establish packed offsets, grant/spend paths distinguish
available gold from lifetime earnings, and a private genuine save corroborates
the current profile. Story, rewards, card records and hero progression are preserved.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.stars import stars_codec as codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.verified_editor import Field

GAME_ID, SAVE_SIZE = 'stars', codec.SAVE_SIZE
GOLD_OFFSET, LIFETIME_GOLD_OFFSET, GOLD_MAXIMUM = 0x2F6A, 0x1CE, 9_999_999
ACTIVE_HERO_OFFSET = 0xA3C
# Native 44A670 array serialization: 100 * 466410, then 2200 * 464810.
HERO_BASE, HERO_COUNT, HERO_STRIDE, EQUIPPED_CARD_OFFSET = 0x3F6E, 100, 0x48D, 0x20E
CARD_BASE, CARD_COUNT, CARD_STRIDE, ORDINARY_POOL_SIZE = 0x20682, 2200, 0x53, 20
MATERIAL_OFFSET, MATERIAL_COUNT, MATERIAL_MAXIMUM = 0x2F10, 45, 9_999
FIELDS = tuple(Field(f'slot_{index}_gold', 'Available gold',
                     codec.SYSTEM_PAYLOAD_SIZE + index * codec.SLOT_PAYLOAD_SIZE + GOLD_OFFSET,
                     4, GOLD_MAXIMUM, 'Campaign gold', index + 1)
               for index in range(codec.SLOT_COUNT))
MATERIAL_FIELDS = tuple(Field(f'slot_{slot}_material_{identity}',
                             f'Material ID {identity}: Quantity',
                             codec.SYSTEM_PAYLOAD_SIZE + slot * codec.SLOT_PAYLOAD_SIZE
                             + MATERIAL_OFFSET + 2 * identity,
                             2, MATERIAL_MAXIMUM, 'Materials', slot + 1,
                             minimum=1, maxable=False)
                        for slot in range(codec.SLOT_COUNT) for identity in range(MATERIAL_COUNT))


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Warriors All-Stars (PC)', SAVE_SIZE, FIELDS + MATERIAL_FIELDS,
                'Current native PC revision: available gold and existing ordinary '
                'material quantities by numeric ID in nine campaign slots; '
                'lifetime earned gold is inspected separately. Switch between existing ordinary '
                "Hero Cards in each hero's own pool. Hero progression, card properties, "
                'material acquisition, regard, requests, routes and reward history remain '
                'read only. Genuine parsing and unchanged reconstruction are verified; '
                'edited game-load validation has not been performed by this project.')


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
        raise SaveError('Select the Warriors All-Stars native Windows PC adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=None):
    get_format(game_id)
    payload, _ = codec.decode(raw)
    return Document(FORMAT, Path(source) if source is not None else Path('all-stars-copy.bin'),
                    bytes(raw), payload)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate SAVEDATA.BIN copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes):
        raise SaveError('An immutable native All-Stars snapshot is required.')
    if codec.decode(document.raw)[0] != document.payload:
        raise SaveError('The opened All-Stars snapshot was changed outside the edit workflow.')


def _slot_base(slot):
    return codec.SYSTEM_PAYLOAD_SIZE + slot * codec.SLOT_PAYLOAD_SIZE


def _card_offset(slot, index):
    return _slot_base(slot) + CARD_BASE + index * CARD_STRIDE


@lru_cache(maxsize=4)
def _card_options(payload, slot, hero):
    # 464220: ordinary inventory is partitioned into twenty physical records
    # per hero. Friendship-gift records 2000..2199 use a separate owner path.
    options = []
    for index in range(hero * ORDINARY_POOL_SIZE, (hero + 1) * ORDINARY_POOL_SIZE):
        identity = struct.unpack_from('<h', payload, _card_offset(slot, index))[0]
        if 0 <= identity < 2000:  # native occupied-card predicate 464310
            options.append((index, f'Card record {index + 1} (card ID {identity})'))
    return tuple(options)


@lru_cache(maxsize=4)
def _fields(payload):
    # Save-preview routine44A2B0 accepts a selected hero in the fixed100-record
    # array. Empty -1 and unknown IDs do not authorize creating a campaign.
    qualified = {field.slot for field in FIELDS
                 if 0 <= struct.unpack_from('<h', payload,
                         codec.SYSTEM_PAYLOAD_SIZE + (field.slot - 1) * codec.SLOT_PAYLOAD_SIZE
                         + ACTIVE_HERO_OFFSET)[0] < 100}
    equipment = []
    for slot in range(codec.SLOT_COUNT):
        if slot + 1 not in qualified:
            continue
        for hero in range(HERO_COUNT):
            offset = _slot_base(slot) + HERO_BASE + hero * HERO_STRIDE + EQUIPPED_CARD_OFFSET
            selected = struct.unpack_from('<i', payload, offset)[0]
            options = _card_options(payload, slot, hero)
            if len(options) > 1 and selected in dict(options):
                equipment.append(Field(f'slot_{slot}_hero_{hero}_equipped_card',
                                       'Equipped ordinary Hero Card', offset, 4,
                                       (hero + 1) * ORDINARY_POOL_SIZE - 1,
                                       'Hero cards', slot * HERO_COUNT + hero + 1,
                                       minimum=hero * ORDINARY_POOL_SIZE, maxable=False, experimental=False))
    return (tuple(field for field in FIELDS if field.slot in qualified)
            + tuple(field for field in MATERIAL_FIELDS if field.slot in qualified
                    and field.minimum <= field.value(payload) <= field.maximum)
            + tuple(equipment))


def fields_for(document):
    validate_document(document)
    return _fields(document.payload)


@lru_cache(maxsize=4)
def _field_index(payload):
    return MappingProxyType({field.id: field for field in _fields(payload)})


def field_map(document):
    validate_document(document)
    return _field_index(document.payload)


def field_options(document, key):
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('This All-Stars field is not editable.')
    if field.group != 'Hero cards':
        return ()
    slot, hero = divmod(field.slot - 1, HERO_COUNT)
    return _card_options(document.payload, slot, hero)


def _validate_selection(document, field, value):
    if value not in dict(field_options(document, field.id)):
        raise SaveError("Select an existing ordinary Hero Card from this hero's own pool.")



def _validate_edit(field, value, original):
    if type(value) is not int:
        raise SaveError('A whole-number resource value is required.')
    if value != original:
        field.validate(value)


def changed_payload(document, changes):
    mapping = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = mapping.get(key)
        if field is None:
            raise SaveError('Only mapped campaign resources and existing own-pool card selections are writable.')
        _validate_edit(field, value, field.value(document.payload))
        if field.group == 'Hero cards':
            _validate_selection(document, field, value)
        result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(result)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('Only mapped campaign resources and existing own-pool card selections are writable.')
    original = field.value(document.payload)
    _validate_edit(field, value, original)
    if field.group == 'Hero cards':
        _validate_selection(document, field, value)
    result = dict(changes)
    if value == original:
        result.pop(key, None)
    else:
        result[key] = value
    return result


def serialize(document, changes):
    return codec.encode(document.raw, changed_payload(document, changes))


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapping = field_map(document)
    result = {}
    for key in keys:
        if key not in mapping:
            raise SaveError('Only mapped campaign resources and existing own-pool card selections are writable.')
        field = mapping[key]
        current = changes.get(key, field.value(document.payload))
        if field.maxable and field.minimum <= current <= field.maximum:
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


def record_label(slot, group='Campaign gold'):
    if group == 'Hero cards':
        campaign, hero = divmod(slot - 1, HERO_COUNT)
        return f'Campaign slot {campaign + 1} / Hero ID {hero}'
    return f'Campaign slot {slot}' if group in ('Campaign gold', 'Materials') else group


def field_hint(document, field):
    key = field.id if isinstance(field, Field) else field
    mapped = field_map(document)[key]
    if mapped.group == 'Hero cards':
        return ("Select another already occupied ordinary card from this hero's twenty-record pool. "
                'Empty, unknown and friendship-gift references remain read only. Card identity, '
                'attack, EXP, traits, acquisition and story bytes are preserved. Bulk Max excludes equipment.')
    if mapped.group == 'Materials':
        return ('Existing material quantity only, 1..9,999. Zero, unknown higher '
                'values and empty campaigns remain read only. Numeric material '
                'IDs are shown because names are not yet mapped. Quantity edits '
                'preserve acquisition, request and reward history. Bulk Max leaves materials unchanged.')
    return ('Available gold balance, 0..9,999,999. Max preserves higher opened '
            'values. Editing the balance does not grant lifetime earnings, '
            'request rewards or achievement progress. Story and equipment stay unchanged.')


def inspection_rows(document):
    validate_document(document)
    revision, selected, secondary = struct.unpack_from('<3I', document.payload)
    rows = [{'group': 'System history', 'label': 'Native profile',
             'value': f'Revision 0x{revision:08X}; current campaign slot {selected + 1}; '
                      f'secondary campaign selection {secondary + 1}'},
            {'group': 'System history', 'label': 'Lifetime earned gold',
             'value': f'{struct.unpack_from("<I", document.payload, LIFETIME_GOLD_OFFSET)[0]:,} '
                      '(read only; distinct from spendable campaign balances)'}]
    qualified = {field.id for field in fields_for(document)}
    for field in FIELDS:
        hero = struct.unpack_from('<h', document.payload, codec.SYSTEM_PAYLOAD_SIZE
                                  + (field.slot - 1) * codec.SLOT_PAYLOAD_SIZE + ACTIVE_HERO_OFFSET)[0]
        rows.append({'group': 'Campaign gold', 'label': record_label(field.slot),
                     'value': f'Available gold {field.value(document.payload):,}; selected hero ID {hero}; '
                              f'qualified campaign: {field.id in qualified}'})
    for field in MATERIAL_FIELDS:
        value = field.value(document.payload)
        if value:
            identity = (field.offset - codec.SYSTEM_PAYLOAD_SIZE
                        - (field.slot - 1) * codec.SLOT_PAYLOAD_SIZE - MATERIAL_OFFSET) // 2
            rows.append({'group': 'Materials', 'label': f'{record_label(field.slot, "Materials")} / Material ID {identity}',
                         'value': f'Quantity {value:,}; editable existing stack: {field.id in qualified}'})
    for slot in range(codec.SLOT_COUNT):
        for index in range(CARD_COUNT):
            offset = _card_offset(slot, index)
            identity = struct.unpack_from('<h', document.payload, offset)[0]
            if not 0 <= identity < 2000:
                continue
            attack = struct.unpack_from('<H', document.payload, offset + 3)[0]
            element = struct.unpack_from('<b', document.payload, offset + 8)[0]
            traits = ', '.join(str(value) for value in document.payload[offset + 10:offset + 14])
            owner = f'Hero ID {index // 20}' if index < 2000 else 'Friendship-gift pool (read only)'
            rows.append({'group': 'Hero cards',
                         'label': f'Campaign slot {slot + 1} / Card record {index + 1}',
                         'value': f'{owner}; card ID {identity}; stored attack {attack}; '
                                  f'element ID {element}; trait IDs {traits}. Card properties read only.'})
    return tuple(rows)


# No checksum covers serialized gameplay bytes. The codec still verifies all
# native encrypted fingerprints; these do not provide payload integrity.
INTEGRITY_KIND = 'none'

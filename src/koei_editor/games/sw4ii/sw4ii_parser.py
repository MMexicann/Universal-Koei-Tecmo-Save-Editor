"""Existing resource and stored base-stat edits for qualified SW4-II PC copies.

Serialized record identities and widths are independently corroborated against
two native saves and published PC memory research. Level/EXP, skill trees,
equipment, growth and reward state remain separate. No player data is packaged.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.verified_editor import Field
from koei_editor.games.sw4ii import sw4ii_codec as codec

GAME_ID = 'sw4ii'
SAVE_SIZE = codec.SAVE_SIZE
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0x1052, 0x8C, 56
GOLD_OFFSET, TOME_BASE = 0xCB82, 0xCC16
WEAPON_BASE, WEAPON_STRIDE, WEAPON_SLOTS = 0x4702, 0x1C, 20
MOUNT_BASE, MOUNT_STRIDE, MOUNT_COUNT = 0xCA42, 0x10, 20
ATTRIBUTE_NAMES = ('Health', 'Attack', 'Defense', 'Speed', 'Riding', 'Musou+',
                   'Spirit+', 'Range', 'Attack speed', 'Indirect', 'Fire',
                   'Lightning', 'Ice', 'Wind', 'Earth', 'Death', 'Luck')
STATS = (('health', 'Stored base health', 0x20), ('attack', 'Stored base attack', 0x22),
         ('defense', 'Stored base defense', 0x24), ('riding', 'Stored base riding', 0x26),
         ('speed', 'Stored base speed', 0x28))
TOME_COLORS = ('Red', 'Green', 'Blue', 'Yellow', 'Purple')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


_BASE_FIELDS = (Field('gold', 'Gold (manual)', GOLD_OFFSET, 4, 0xffffffff,
                      maxable=False),) + tuple(
    Field(f'tome_{i}', f'{color} strategy tomes (manual)', TOME_BASE + i * 2,
          2, 0xffff, maxable=False) for i, color in enumerate(TOME_COLORS))
FORMAT = Format(GAME_ID, 'Samurai Warriors 4-II (Windows PC)', SAVE_SIZE, _BASE_FIELDS,
                'Native PC revision 0x31A4. Manual gold, '
                'five current strategy-tome resources and stored base stats on existing '
                'standard officers, equipped existing own-pool weapons, attached attribute '
                'magnitudes on known existing weapons, existing mount combat stats and qualified existing mount selection. '
                'Numeric limits are storage bounds, not gameplay caps. '
                'EXP, growth, skill trees, new equipment and story/rewards remain read only.')


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


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select Samurai Warriors 4-II Windows PC, separately from SW4 DX.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise SaveError('Samurai Warriors 4-II requires native save bytes.')
    raw = bytes(raw)
    payload, seed = codec.decode_envelope(raw)
    return Document(FORMAT, Path(source), raw, payload, seed)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate native PC .dat gameplay copy.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.seed) is not int):
        raise SaveError('A frozen Samurai Warriors 4-II native snapshot is required.')
    payload, seed = codec.decode_envelope(document.raw)
    if payload != document.payload or seed != document.seed:
        raise SaveError('The opened Samurai Warriors 4-II snapshot was changed outside editing.')


@lru_cache(maxsize=4)
def _fields(payload):
    result = list(_BASE_FIELDS)
    for index in range(OFFICER_COUNT):
        base = OFFICER_BASE + index * OFFICER_STRIDE
        # Unknown/uninitialized progression records do not qualify existing
        # standard officer records. Stats themselves may deliberately be zero.
        level = struct.unpack_from('<I', payload, base + 0xC)[0]
        if not 1 <= level <= 50:
            continue
        for key, label, relative in STATS:
            result.append(Field(f'officer_{index}_{key}', label, base + relative,
                                2, 0xffff, 'Officers', index + 1, maxable=False))
        if _mount_choices(payload):
            result.append(Field(f'officer_{index}_equipped_mount', 'Equipped existing mount slot',
                                base + 0x3D, 1, MOUNT_COUNT - 1, 'Mount equipment',
                                index + 1, maxable=False, experimental=False))
    for owner in range(OFFICER_COUNT):
        allowed = _weapon_choices(payload, owner)
        if _equipment_choices(payload, owner):
            result.append(Field(f'officer_{owner}_equipped_weapon', 'Equipped own-pool weapon slot',
                                OFFICER_BASE + owner * OFFICER_STRIDE + 0x3B, 1, 19,
                                'Equipment', owner + 1, maxable=False, experimental=False))
        for slot in allowed:
            base = WEAPON_BASE + (owner * WEAPON_SLOTS + slot) * WEAPON_STRIDE
            for attribute in range(8):
                identity = payload[base + 0xC + attribute]
                if identity < len(ATTRIBUTE_NAMES):
                    result.append(Field(f'weapon_{owner}_{slot}_attribute_{attribute}',
                                        f'{ATTRIBUTE_NAMES[identity]} magnitude (slot {attribute + 1})',
                                        base + 0x14 + attribute, 1, 0xff, 'Weapons',
                                        owner * WEAPON_SLOTS + slot + 1, maxable=False))
    for index in range(MOUNT_COUNT):
        base = MOUNT_BASE + index * MOUNT_STRIDE
        if not _mount_qualified(payload, index):
            continue
        for key, label, relative in (('power', 'Stored power', 0xA),
                                     ('stamina', 'Stored stamina', 0xB),
                                     ('speed', 'Stored speed', 0xC)):
            result.append(Field(f'mount_{index}_{key}', label, base + relative, 1,
                                0xff, 'Mounts', index + 1, minimum=1, maxable=False))
    return tuple(result)


def _weapon_choices(payload, owner):
    result = []
    for slot in range(WEAPON_SLOTS):
        base = WEAPON_BASE + (owner * WEAPON_SLOTS + slot) * WEAPON_STRIDE
        identity = int.from_bytes(payload[base:base + 2], 'little')
        # Independently observed primary normal/rare IDs on both native saves.
        # Empty 351, DLC and foreign family identities never become writable.
        if identity in (2 + owner * 2, 3 + owner * 2):
            result.append(slot)
    return tuple(result)


def _mount_qualified(payload, index):
    base = MOUNT_BASE + index * MOUNT_STRIDE
    return (payload[base] <= 12 and 1 <= payload[base + 3] <= payload[base + 4] <= 50
            and all(payload[base + relative] for relative in (0xA, 0xB, 0xC)))


def _equipment_choices(payload, owner):
    # Public native-editor gameplay research establishes 15 selectable ordinary
    # positions, not the complete 20-record physical pool. The remaining stored
    # records can be inspected/edited in place but are not selectable targets.
    return tuple(slot for slot in _weapon_choices(payload, owner) if slot < 15)


def _mount_choices(payload):
    return tuple(index for index in range(MOUNT_COUNT) if _mount_qualified(payload, index))


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


def changed_payload(document, changes):
    mapped = field_map(document)
    if not isinstance(changes, dict):
        raise SaveError('Staged Samurai Warriors 4-II edits must be a mapping.')
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = mapped.get(key)
        if field is None:
            raise SaveError('This Samurai Warriors 4-II record is not qualified for editing.')
        _validate_edit(field, value, field.value(document.payload))
        if (field.group == 'Equipment' and value != field.value(document.payload)
                and value not in _equipment_choices(document.payload, field.slot - 1)):
            raise SaveError("Equip an existing known weapon in this standard officer's own pool.")
        if (field.group == 'Mount equipment' and value != field.value(document.payload)
                and value not in _mount_choices(document.payload)):
            raise SaveError('Equip an existing qualified occupied mount; empty and unknown types are unavailable.')
        result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    codec.qualify_payload(result, integrity=False)
    for offset, checksum in zip(codec.CHECKSUM_OFFSETS, codec.checksums(result)):
        struct.pack_into('<I', result, offset, checksum)
    return bytes(result)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('This Samurai Warriors 4-II record is not qualified for editing.')
    original = field.value(document.payload)
    _validate_edit(field, value, original)
    result = dict(changes)
    if value == original:
        result.pop(key, None)
    else:
        result[key] = value
    changed_payload(document, result)
    return result


def serialize(document, changes):
    return codec.encode_envelope(document.raw, changed_payload(document, changes))


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapped = field_map(document)
    if any(key not in mapped for key in keys):
        raise SaveError('This Samurai Warriors 4-II record is not qualified for editing.')
    return {}  # No natural caps are qualified; manual storage limits never drive Max.


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
        raise SaveError('Choose a new .dat gameplay destination.')
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


def record_label(slot, group='Officers'):
    if group in ('Officers', 'Equipment', 'Mount equipment') and slot:
        return f'Standard officer ID {slot - 1}'
    if group == 'Weapons' and slot:
        owner, weapon = divmod(slot - 1, WEAPON_SLOTS)
        return f'Standard officer ID {owner} / weapon slot {weapon}'
    return f'Mount slot {slot - 1}' if group == 'Mounts' and slot else group


def field_options(document, field):
    key = field.id if isinstance(field, Field) else field
    mapped = field_map(document).get(key)
    if mapped is None:
        raise SaveError('Choose a qualified Samurai Warriors 4-II field.')
    if mapped.group == 'Equipment':
        return tuple((slot, f'Existing own-pool slot {slot}')
                     for slot in _equipment_choices(document.payload, mapped.slot - 1))
    if mapped.group == 'Mount equipment':
        return tuple((slot, f'Existing mount slot {slot} (type ID {document.payload[MOUNT_BASE + slot * MOUNT_STRIDE]})')
                     for slot in _mount_choices(document.payload))
    return ()


def field_hint(document, field):
    mapped = field_map(document)[field.id if isinstance(field, Field) else field]
    if mapped.group == 'Mount equipment':
        return ('Select a known occupied mount from the opened inventory. This changes only '
                'the standard officer mount reference. Ownership, type, growth, abilities, '
                'mount stats and rewards are preserved. Max leaves equipment choices unchanged.')
    if mapped.group == 'Equipment':
        return ("Choose an existing known normal/rare weapon in this standard officer's "
                'own pool. This changes equipment only; no acquisition, reward, DLC, '
                'weapon identity or other inventory record changes.')
    if mapped.group == 'Weapons':
        return ('Existing attached attribute magnitude. Identity, slot, weapon rank, '
                'level, EXP, level ceiling and attack remain unchanged. Manual unsigned '
                'byte range only; no natural cap or fusion transaction is simulated.')
    if mapped.group == 'Mounts':
        return ('Stored combat stat on an existing known occupied mount. Type, rank, '
                'level, EXP, growth ceilings, abilities and equipment references stay '
                'unchanged. Manual unsigned byte range; no growth maximum is claimed.')
    if mapped.group == 'Officers':
        return ('Existing stored base stat, not effective battle stat. Level, EXP, skill '
                'modifiers and growth rewards remain unchanged. Manual unsigned 16-bit '
                'storage range; no gameplay growth ceiling or Max is claimed.')
    return ('Current held resource, separate from spending history and skill purchases. '
            'Manual storage range only; no natural gameplay maximum is qualified, '
            'and Max leaves this field unchanged. No purchase/reward transaction is simulated.')


def inspection_rows(document):
    validate_document(document)
    payload = document.payload
    rows = []
    for index in range(OFFICER_COUNT):
        base = OFFICER_BASE + index * OFFICER_STRIDE
        rows.append({'group': 'Progression', 'label': f'Standard officer ID {index}',
                     'value': f'Level {int.from_bytes(payload[base+12:base+16], "little")}; '
                              f'EXP {int.from_bytes(payload[base+8:base+12], "little"):,}; '
                              'growth, personal skills and equipment are preserved'})
        equipped = payload[base + 0x3B]
        choices = _weapon_choices(payload, index)
        rows.append({'group': 'Equipment', 'label': f'Standard officer ID {index}',
                     'value': f'Equipped weapon slot {equipped}; '
                              f'qualified occupied own-pool slots {", ".join(map(str, choices)) or "none"}; '
                              f'opened reference qualified: {equipped in choices}'})
        mount = payload[base + 0x3D]
        rows.append({'group': 'Mount equipment', 'label': f'Standard officer ID {index}',
                     'value': f'Equipped mount slot {mount}; qualified occupied targets '
                              f'{", ".join(map(str, _mount_choices(payload))) or "none"}; '
                              f'opened reference qualified: {mount in _mount_choices(payload)}'})
        for slot in choices:
            weapon = WEAPON_BASE + (index * WEAPON_SLOTS + slot) * WEAPON_STRIDE
            identity = int.from_bytes(payload[weapon:weapon + 2], 'little')
            attributes = []
            for attribute in range(8):
                key = payload[weapon + 0xC + attribute]
                if key == 255:
                    continue
                label = ATTRIBUTE_NAMES[key] if key < len(ATTRIBUTE_NAMES) else f'Unknown attribute ID {key}'
                attributes.append(f'{label} {payload[weapon + 0x14 + attribute]}')
            rows.append({'group': 'Weapons', 'label': f'Standard officer ID {index} / slot {slot}',
                         'value': f'Weapon ID {identity}; stored rank index {payload[weapon+2]}; '
                                  f'level {payload[weapon+4]}/{payload[weapon+5]}; '
                                  f'EXP {int.from_bytes(payload[weapon+6:weapon+8], "little")}; '
                                  f'stored attack {payload[weapon+8]}; ' + '; '.join(attributes)})
    for index in range(MOUNT_COUNT):
        base = MOUNT_BASE + index * MOUNT_STRIDE
        if payload[base] == 26:
            continue
        rows.append({'group': 'Mounts', 'label': f'Mount slot {index}',
                     'value': f'Type ID {payload[base]}; level {payload[base+3]}/{payload[base+4]}; '
                              f'power {payload[base+0xA]}, stamina {payload[base+0xB]}, speed {payload[base+0xC]}; '
                              f'combat stats qualified: {_mount_qualified(payload, index)}'})
    rows.append({'group': 'History', 'label': 'Adjacent gold history (unqualified meaning)',
                 'value': f'{int.from_bytes(payload[GOLD_OFFSET+4:GOLD_OFFSET+8], "little"):,}; '
                          'not a current resource and never written'})
    return tuple(rows)


INTEGRITY_KIND = 'checksum'

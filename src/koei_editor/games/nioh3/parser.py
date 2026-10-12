"""Copy-only balance/common-stack reductions and native equipment inspection.

Only already-positive known ordinary quantities can decrease, or return to their
opened value. Carry-capacity, acquisition, reward and equipped-reference rules
are not inferred from an item ID. Native unknown bytes and unusual values stay
intact; zeroing an owned record and bulk Max are unavailable.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.nioh3 import balances, codec, inventory
from koei_editor.shared.adapter_contract import is_opened_value, normalize_pending_values
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path


GAME_ID = 'nioh3'
SAVE_SIZE = codec.USER_SIZE
INTEGRITY_KIND = 'checksum'


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Nioh 3 (PC)', SAVE_SIZE, (),
                'Native USER revisions 0x01030001 and 0x01040000: reduce existing '
                'positive quantities of eighteen known common items in the item box '
                'and storehouse, or deduct source-mapped Amrita/Gold balances. '
                'Balance edits do not perform a purchase or level-up. Equipment '
                'level, pre-forge level and reinforcement are inspected separately. '
                'Increases, item removal, acquisition, stats, '
                'affixes, skills, rewards and story are not writable. Genuine-file '
                'roundtrips are qualified; actual edited game loading is untested.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    revision: int
    encrypted: bool

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the Nioh 3 native Windows PC USER adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=None):
    get_format(game_id)
    native = codec.decode(raw)
    inventory.fields(native.payload, native.revision)
    balances.fields(native.payload, native.revision)
    return Document(FORMAT, Path(source) if source is not None else Path('nioh3-copy.bin'),
                    native.raw, native.payload, native.revision, native.encrypted)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate Nioh 3 USER .bin copy.')
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    return decode(raw, game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.revision) is not int or type(document.encrypted) is not bool
            or not isinstance(document.source, Path)):
        raise SaveError('An immutable native Nioh 3 USER snapshot is required.')
    native = codec.decode(document.raw)
    if (native.payload != document.payload or native.revision != document.revision
            or native.encrypted != document.encrypted):
        raise SaveError('The opened Nioh 3 snapshot was changed outside the edit workflow.')
    inventory.fields(document.payload, document.revision)
    balances.fields(document.payload, document.revision)


def fields_for(document):
    validate_document(document)
    return (inventory.fields(document.payload, document.revision)
            + balances.fields(document.payload, document.revision))


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def _validated_changes(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Nioh 3 pending edits require an ordinary field/value mapping.')
    if any(type(key) is not str or key not in mapping for key in changes):
        raise SaveError('Only qualified Nioh 3 balances and existing common-stack quantities are writable.')
    normalized = normalize_pending_values(document, changes, mapping)
    return mapping, normalized


def stage(document, changes, key, value):
    mapping, changes = _validated_changes(document, changes)
    if type(key) is not str or key not in mapping:
        raise SaveError('Only qualified Nioh 3 balances and existing common-stack quantities are writable.')
    field = mapping[key]
    result = dict(changes)
    if is_opened_value(document, field, value):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    return result


def changed_payload(document, changes):
    mapping, changes = _validated_changes(document, changes)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = mapping[key]
        opened = field.value(document.payload)
        if type(value) is type(opened) and value == opened:
            continue
        result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    if result != document.payload:
        struct.pack_into('<I', result, codec.CHECKSUM_OFFSET, codec.body_checksum(result))
    return bytes(result)


def serialize(document, changes):
    validate_document(document)
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = codec.encode(document.raw, payload)
    verified = decode(raw, GAME_ID, document.source)
    if verified.payload != payload:
        raise SaveError('Nioh 3 edited USER failed native read-back verification.')
    return raw


def limit_values(document, changes, keys):
    mapping, changes = _validated_changes(document, changes)
    if isinstance(keys, (str, bytes)):
        raise SaveError('Nioh 3 Max keys require an iterable of mapped field IDs.')
    try:
        keys = tuple(keys)
    except TypeError as error:
        raise SaveError('Nioh 3 Max keys require an iterable of mapped field IDs.') from error
    for key in keys:
        if type(key) is not str or key not in mapping:
            raise SaveError('Only qualified Nioh 3 balances and existing common-stack quantities are writable.')
    return {}  # Reductions have no proven natural capacity and never join Max.


def maximums(document, changes, group=None):
    _mapping, normalized = _validated_changes(document, changes)
    return normalized


def review(document, changes):
    _mapping, changes = _validated_changes(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'WarriorsEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new .bin destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed during serialization. Reopen it before saving.')
    backup(document)
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed during backup. Reopen it before saving.')
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def record_label(slot, group='Item box'):
    return f'{group} slot {slot}'


def field_hint(document, field):
    mapped = field_map(document)[field.id if hasattr(field, 'id') else field]
    if mapped.group == 'Balances':
        return ('Balance deduction only: 0 to the opened amount '
                f'({mapped.maximum:,}). This does not perform a purchase or level-up; '
                'grave state, EXP, attributes, rewards and transaction history remain '
                'unchanged. Increases and Max are unavailable; assigning the opened '
                'amount undoes the edit.')
    return ('Existing quantity only: 1 to the opened amount '
            f'({mapped.maximum:,}). Reductions preserve the item record, equipped '
            'references, acquisition and rewards. Increases and zero are blocked '
            'until capacity/removal dependencies qualify. Bulk Max leaves this '
            'field unchanged; assigning its opened amount undoes the edit.')


def inspection_rows(document):
    validate_document(document)
    writable = {field.offset - 4 for field in inventory.fields(document.payload, document.revision)}
    result = [{'group': 'Native profile', 'label': 'USER integrity',
               'value': f'Revision 0x{document.revision:08X}; native body checksum verified; '
                        f'{"encrypted" if document.encrypted else "decoded"} copy'}]
    for field in balances.fields(document.payload, document.revision):
        result.append({'group': 'Balances', 'label': field.label,
                       'value': f'{field.value(document.payload):,}; source-mapped u64; '
                                'deductions only, with native tags and neighbors verified'})
    for pool in inventory.pools_for(document.payload, document.revision):
        result.append({'group': 'Native profile', 'label': pool.title + ' array',
                       'value': f'{pool.count:,} native records; stride 0x{pool.stride:X}; '
                                'tag and both lengths verified'})
        for slot, offset, identity in inventory.records(document.payload, pool):
            appearance, quantity, level, pre_forge, plus = struct.unpack_from('<5H', document.payload, offset + 2)
            name = inventory.COMMON_ITEMS.get(identity, f'Item ID 0x{identity:04X}')
            description = (f'Quantity {quantity:,}; editable reduction: {offset in writable}'
                           if pool.id != 'equipment' else
                           f'Level {level:,}; pre-forge level {pre_forge:,}; +value {plus:,}; '
                           f'appearance ID 0x{appearance:04X} (read only)')
            result.append({'group': pool.title, 'label': f'Slot {slot + 1}: {name}',
                           'value': description})
    return tuple(result)

"""Source-qualified original Xbox SYSTEM.dat order restoration.

Complete published system writer has author Xemu load/save acceptance.
No genuine SYSTEM fixture is claimed; story gameplay writes stay unregistered.
"""
from dataclasses import dataclass, field as hidden
import hashlib
import hmac
import json
from pathlib import Path
import struct
from types import MappingProxyType
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from . import codec, owner

GAME_ID = 'ninja_gaiden_black_xbox'
EXTENSION = '.dat'
INTEGRITY_KIND = 'checksum'
COUNT = 42 + 0x1c6
ORDER = COUNT + 1
MAGIC = 42 + 0x7c

@dataclass(frozen=True)
class Field:
    id: str = 'numeric_slot_order'
    label: str = 'Load-list order'
    offset: int = COUNT
    maximum: int = 1
    minimum: int = 0
    size: int = 1
    group: str = 'Load list'
    slot: int = 0
    kind: str = 'int'
    maxable: bool = False
    def value(self, payload):
        return int(payload[COUNT] == 30 and payload[ORDER:ORDER + 30] == bytes(range(30)))
    def validate(self, value):
        if type(value) is not int or value not in (0, 1):
            raise SaveError('Choose Keep opened order or Sort slots numerically.')

SORT = Field()

@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Ninja Gaiden Black — Original Xbox SYSTEM.dat'
    size: int = codec.SYSTEM_SIZE
    fields: tuple = (SORT,)
    sample_verified: bool = False
    published_format: bool = True
    editing_verified: bool = False
    game_load_verified: bool = False
    note: str = ('Copied original Xbox system.dat with its original console EEPROM beside it. '
                 'Restore numeric slot order and inspect stored times. Story files, '
                 'all time mirrors, settings and unlocks remain unchanged.')

FORMAT = Format()

@dataclass(frozen=True)
class Document:
    format: Format
    source: Path = hidden(repr=False)
    raw: bytes = hidden(repr=False)
    payload: bytes = hidden(repr=False)
    context: owner.Context = hidden(repr=False)
    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the original Xbox Ninja Gaiden Black SYSTEM.dat profile.')
    return FORMAT


def _copy_path(path):
    result = owner.ordinary(path)
    if result.suffix.casefold() != EXTENSION:
        raise SaveError('Choose a separate original Xbox system .dat copy.')
    return result


def _payload(raw, context):
    owner.validate_shape(context)
    if context.metadata != b'' or type(raw) is not bytes or len(raw) != codec.SYSTEM_SIZE:
        raise SaveError('Requires complete original Xbox Ninja Gaiden Black system data.')
    if not hmac.compare_digest(raw[:20], owner.signature(raw, context.key)):
        raise SaveError('The complete native system signature does not match its original console context.')
    _plain, payload, _extent, _counts = codec.decrypt(raw)
    count = payload[COUNT]
    active = payload[ORDER:ORDER + count]
    if (struct.unpack_from('<I', payload, MAGIC)[0] != 0x20030730 or count > 30
            or any(slot >= 30 for slot in active) or len(set(active)) != count):
        raise SaveError('Unsupported original Xbox Ninja Gaiden Black system structure.')
    return payload


def _decode_context(raw, context, source):
    return Document(FORMAT, source, raw, _payload(raw, context), context)


def decode(raw, game_id=GAME_ID, source=Path('system.dat')):
    get_format(game_id)
    source = _copy_path(source)
    context = owner.read_context(source)
    result = _decode_context(raw, context, source)
    owner.validate_context(context)
    return result


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    source = _copy_path(path)
    context = owner.read_context(source)
    try:
        with source.open('rb') as stream:
            raw = stream.read(codec.SYSTEM_SIZE + 1)
    except OSError:
        raise SaveError('The copied original Xbox system save is unavailable.') from None
    result = _decode_context(raw, context, source)
    owner.validate_context(context)
    return result


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path) or not document.source.is_absolute()
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or _payload(document.raw, document.context) != document.payload
            or document.source.parent != document.context.directory):
        raise SaveError('Requires an immutable qualified original Xbox system snapshot.')


def fields_for(document):
    validate_document(document)
    return FORMAT.fields


def field_map(document):
    return MappingProxyType({item.id: item for item in fields_for(document)})


def changed_payload(document, changes):
    validate_document(document)
    if type(changes) is not dict:
        raise SaveError('Original Xbox edits require a field/value mapping.')
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key != SORT.id:
            raise SaveError('Only numeric load-list order restoration is writable.')
        SORT.validate(value)
        if value == 1:
            result[COUNT] = 30
            result[ORDER:ORDER + 30] = bytes(range(30))
        elif value != SORT.value(document.payload):
            raise SaveError('Choose numeric sorting or restore the opened value to undo.')
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    plain, _original, _extent, counts = codec.decrypt(document.raw)
    stream = codec.pack(payload, counts)
    edited_plain = stream + plain[len(stream):]
    encoded = codec.transform(edited_plain, struct.unpack_from('<I', document.raw, 20)[0])
    result = document.raw[:24] + encoded
    result = owner.signature(result, document.context.key) + result[20:]
    if _payload(result, document.context) != payload:
        raise SaveError('Edited original Xbox system failed its complete native reparse.')
    return result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    if type(key) is not str or key != SORT.id:
        raise SaveError('Only numeric load-list order restoration is writable.')
    changed_payload(document, {key: value})
    result = dict(changes)
    if value == SORT.value(document.payload):
        result.pop(key, None)
    else:
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    try:
        keys = tuple(keys)
    except TypeError:
        raise SaveError('Choose verified original Xbox field IDs.') from None
    if any(type(key) is not str or key != SORT.id for key in keys):
        raise SaveError('Unknown original Xbox field ID.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(SORT, SORT.value(document.payload), changes[SORT.id])] if SORT.id in changes else []


def field_options(document, key):
    validate_document(document)
    if key != SORT.id:
        return ()
    opened = SORT.value(document.payload)
    return ((opened, 'Keep opened order'), (1, 'Sort slots numerically')) if opened == 0 else ((1, 'Numeric slot order'),)


def inspection_rows(document):
    validate_document(document)
    payload = document.payload
    count = payload[COUNT]
    active = list(payload[ORDER:ORDER + count])
    return tuple((f'Slot {slot + 1:02d}', struct.unpack_from('<I', payload, 46 + 4 * slot)[0],
                  str(active.index(slot) + 1) if slot in active else 'Not in active list')
                 for slot in range(30))

def _source(document):
    validate_document(document)
    source = _copy_path(document.source)
    owner.validate_context(document.context, source)
    try:
        with source.open('rb') as stream:
            if stream.read(codec.SYSTEM_SIZE + 1) != document.raw:
                raise SaveError('The original Xbox system copy changed; reopen it before saving.')
    except OSError:
        raise SaveError('The original Xbox system copy is unavailable; reopen it before saving.') from None
    return source


def backup(document):
    source = _source(document)
    snapshot = snapshot_backup(document.raw, source, GAME_ID, source.parent / 'UniversalEditorBackups')
    binding = {'game_id': GAME_ID, 'kind': 'original-xbox-context', 'native_sha256': document.sha256,
               'eeprom_sha256': document.context.eeprom_hash, 'metadata_sha256': document.context.metadata_hash,
               'eeprom_basename': document.context.basename}
    context_path = snapshot.with_name(snapshot.name + '.context.json')
    try:
        atomic_new(json.dumps(binding).encode('utf-8'), context_path)
        _source(document)
    except Exception:
        snapshot.unlink(missing_ok=True)
        snapshot.with_suffix('.json').unlink(missing_ok=True)
        context_path.unlink(missing_ok=True)
        raise
    return snapshot


def save_as(document, changes, destination):
    source = _source(document)
    destination = _copy_path(destination)
    owner.validate_context(document.context, destination)
    if destination == source or destination.exists():
        raise FileExistsError('Choose a new original Xbox copy; existing files are never replaced.')
    result = serialize(document, changes)
    backup(document)
    _source(document)
    owner.validate_context(document.context, destination)
    atomic_new(result, destination)
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination, backup_path = _copy_path(destination), _copy_path(backup_path)
    context = owner.read_context(destination)
    try:
        with owner.ordinary(backup_path.with_name(backup_path.name + '.context.json')).open('rb') as stream:
            data = stream.read(2049)
        if len(data) > 2048:
            raise SaveError('Original Xbox backup context is too large.')
        binding = json.loads(data)
    except (OSError, ValueError, UnicodeError):
        raise SaveError('Original Xbox backup context is missing or damaged.') from None
    if (type(binding) is not dict or binding.get('game_id') != GAME_ID
            or binding.get('kind') != 'original-xbox-context'
            or binding.get('eeprom_sha256') != context.eeprom_hash
            or binding.get('metadata_sha256') != context.metadata_hash
            or binding.get('eeprom_basename') != context.basename):
        raise SaveError('Restore requires the exact original Xbox companions bound to this backup.')
    def validate(raw):
        if binding.get('native_sha256') != hashlib.sha256(raw).hexdigest():
            raise SaveError('Original Xbox backup no longer matches its context binding.')
        _payload(raw, context)
        owner.validate_context(context, destination)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, codec.SYSTEM_SIZE, validate_raw=validate)


def prepare_self_test_copy(document, destination):
    _source(document)
    destination = _copy_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    for basename, raw in ((document.context.basename, document.context.eeprom),):
        target = owner.ordinary(destination.parent / basename)
        if target.exists():
            if target.read_bytes() != raw:
                raise SaveError('Private test destination has different original Xbox companions.')
        else:
            _source(document)
            atomic_new(raw, target)
            _source(document)
    owner.validate_context(document.context, destination)

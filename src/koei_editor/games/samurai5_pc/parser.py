"""Copy-only SW5 resource edits in the native current castle checkpoint."""
from dataclasses import dataclass, field as hidden
import hashlib
import json
import os
from pathlib import Path
import struct
from types import MappingProxyType
import uuid
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.samurai5_pc import codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.steam_owner import OwnerContext, read_owner, validate_owner, require_matching_owner

GAME_ID = 'samurai5_pc'
TITLE = 'Samurai Warriors 5 (Windows PC)'
SAVE_SIZE, EXTENSION = codec.SAVE_SIZE, '.bin'
INTEGRITY_KIND = 'none'
RESOURCE_MAP = (
    ('gold', 'Gold', 0xD4, 4, 9_999_999, 'Resources'),
    ('stock_exp', 'Stock EXP', 0xDC, 4, 9_999_999, 'Dojo resources'),
    ('skill_points', 'Shared skill points', 0xE0, 4, 99_999, 'Dojo resources'),
    ('stock_mastery', 'Stock weapon mastery', 0xE4, 4, 9_999_999, 'Dojo resources'),
    ('lumber', 'Lumber', 0x2A48, 2, 9_999, 'Building materials'),
    ('mineral', 'Mineral', 0x2A4A, 2, 9_999, 'Building materials'),
    ('fabric', 'Fabric', 0x2A4C, 2, 9_999, 'Building materials'),
)

@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str
    slot: int = 0
    minimum: int = 0
    maxable: bool = True
    kind: str = 'int'
    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')
    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')
    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'little')

FIELDS = tuple(Field(*row) for row in RESOURCE_MAP)
@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = TITLE
    size: int = SAVE_SIZE
    fields: tuple = FIELDS
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Native PC slot zero, revision 39, saved at My Castle. '
                 'Requires the original steam_autocloud.vdf beside both source and destination copies. '
                 'Current gold, three distinct Dojo resources and building materials; older checkpoints, '
                 'officer skill allocations, facilities, unlocks, story and battle buffers are preserved.')
FORMAT = Format()
@dataclass(frozen=True)
class Document:
    format: Format
    source: Path = hidden(repr=False)
    raw: bytes = hidden(repr=False)
    payload: bytes = hidden(repr=False)
    owner: OwnerContext = hidden(repr=False)
    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Choose the explicit native PC Samurai Warriors 5 adapter.')
    return FORMAT

def _path(path):
    path = safe_path(path)
    if path.suffix.lower() != EXTENSION:
        raise SaveError('Open a separate SAVEDATA00.BIN copy with its original Steam owner sidecar.')
    return path

def decode(raw, game_id=GAME_ID, source=Path('SAVEDATA00.BIN'), *, owner=None):
    get_format(game_id)
    if owner is None:
        owner = read_owner(_path(source))
    if type(owner) is not OwnerContext:
        raise SaveError('The unchanged original Steam owner context is required.')
    payload = codec.decode_file(raw, owner.account_id)
    return Document(FORMAT, Path(source), raw, payload, owner)

def read_save(path, game_id=GAME_ID):
    path = _path(path)
    owner = read_owner(path)
    try:
        with path.open('rb') as stream:
            raw = stream.read(SAVE_SIZE + 1)
    except OSError:
        raise SaveError('The copied SW5 save is unavailable.') from None
    document = decode(raw, game_id, path, owner=owner)
    validate_owner(owner)
    return document

def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.owner) is not OwnerContext or type(document.raw) is not bytes
            or type(document.payload) is not bytes
            or codec.decode_file(document.raw, document.owner.account_id) != document.payload):
        raise SaveError('A frozen qualified native SW5 snapshot is required.')

def fields_for(document):
    validate_document(document)
    return FIELDS

def field_map(document):
    return MappingProxyType({item.id: item for item in fields_for(document)})

def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Pending SW5 changes must be a dictionary.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only the seven mapped current-checkpoint resources are writable.')
        item = mapping[key]
        if type(value) is int and value == item.value(document.payload):
            continue
        output[item.offset:item.offset + item.size] = item.encoded(value)
    return bytes(output)

def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = codec.encode_file(payload, document.owner.account_id, struct.unpack_from('<I', document.raw, SAVE_SIZE - 4)[0])
    if codec.decode_file(raw, document.owner.account_id) != payload:
        raise SaveError('The SW5 edited ciphertext did not reproduce its intended payload.')
    return raw

def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('The requested SW5 record is inspection only.')
    result = dict(changes)
    if type(value) is int and value == mapping[key].value(document.payload):
        result.pop(key, None)
    else:
        mapping[key].validate(value)
        result[key] = value
    return result

def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapping = field_map(document)
    result = {}
    for key in keys:
        if type(key) is not str or key not in mapping:
            raise SaveError('The requested SW5 record is inspection only.')
        item = mapping[key]
        opened = item.value(document.payload)
        current = changes.get(key, opened)
        if opened > item.maximum and current != opened:
            result[key] = opened
        elif opened <= item.maximum and current < item.maximum:
            result[key] = item.maximum
    return result

def maximums(document, changes, group=None):
    changed_payload(document, changes)
    result = dict(changes)
    keys = [item.id for item in FIELDS if group is None or item.group == group]
    for key, value in limit_values(document, changes, keys).items():
        result = stage(document, result, key, value)
    return result

def review(document, changes):
    changed_payload(document, changes)
    return [(item, item.value(document.payload), changes[item.id]) for item in FIELDS if item.id in changes]

def _validate_source(document):
    validate_document(document)
    source = _path(document.source)
    require_matching_owner(document.owner, source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SAVE_SIZE + 1)
    except OSError:
        raise SaveError('Reopen an accessible separate SW5 save copy.') from None
    if current != document.raw:
        raise SaveError('The opened SW5 copy changed on disk. Reopen it before saving.')
    return source

def backup(document):
    source = _validate_source(document)
    snapshot = snapshot_backup(document.raw, source, GAME_ID, source.parent / 'UniversalEditorBackups')
    metadata = {'game_id': GAME_ID, 'kind': 'sw5-original-owner-context',
                'context_sha256': document.owner.sha256, 'owner_basename': document.owner.basename,
                'save_sha256': document.sha256}
    try:
        atomic_new(json.dumps(metadata).encode('utf-8'), snapshot.with_name(snapshot.name + '.context.json'))
        _validate_source(document)
    except Exception:
        snapshot.unlink(missing_ok=True)
        snapshot.with_suffix('.json').unlink(missing_ok=True)
        snapshot.with_name(snapshot.name + '.context.json').unlink(missing_ok=True)
        raise
    return snapshot

def save_as(document, changes, destination):
    source = _validate_source(document)
    destination = _path(destination)
    require_matching_owner(document.owner, destination)
    if source == destination or destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
    require_matching_owner(document.owner, destination)
    atomic_new(raw, destination)
    return read_save(destination)

def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination, backup_path = _path(destination), safe_path(backup_path)
    owner = read_owner(destination)
    try:
        with safe_path(backup_path.with_name(backup_path.name + '.context.json')).open('rb') as stream:
            raw_metadata = stream.read(1025)
        if len(raw_metadata) > 1024:
            raise SaveError('SW5 backup context metadata is oversized.')
        metadata = json.loads(raw_metadata)
    except (OSError, ValueError, UnicodeError):
        raise SaveError('SW5 backup context metadata is missing or damaged.') from None
    if (type(metadata) is not dict or metadata.get('game_id') != GAME_ID
            or metadata.get('kind') != 'sw5-original-owner-context'
            or metadata.get('context_sha256') != owner.sha256
            or metadata.get('owner_basename') != owner.basename):
        raise SaveError('Restore requires the same original Steam owner sidecar as the backup.')
    def validate_restored(raw):
        if hashlib.sha256(raw).hexdigest() != metadata.get('save_sha256'):
            raise SaveError('SW5 backup context does not match the backed-up save.')
        decode(raw, game_id, source=destination, owner=owner)
        require_matching_owner(owner, destination)
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, SAVE_SIZE, validate_raw=validate_restored)

def prepare_copy_context(document, output):
    """Copy only the immutable original companion into a new private copy directory."""
    _validate_source(document)
    destination = _path(Path(output) / 'input-copy.bin')
    destination.parent.mkdir(parents=True, exist_ok=True)
    companion = destination.parent / document.owner.basename
    if companion.exists() or companion.is_symlink():
        require_matching_owner(document.owner, destination)
        return
    if any(entry.name.casefold() == 'steam_autocloud.vdf' for entry in destination.parent.iterdir()):
        raise SaveError('Steam owner metadata is ambiguous beside this copy.')
    temp = destination.parent / ('.sw5-original-context-' + uuid.uuid4().hex + '.tmp')
    try:
        atomic_new(document.owner.raw, temp)
        _validate_source(document)
        if os.name == 'nt':
            os.rename(temp, companion)
        else:
            os.link(temp, companion)
            temp.unlink()
        require_matching_owner(document.owner, destination)
    finally:
        temp.unlink(missing_ok=True)

def prepare_self_test_copy(document, destination):
    require_matching_owner(document.owner, _path(destination))

def record_label(slot, group='Resources'):
    return 'Current castle save'

def field_hint(document, key):
    item = field_map(document)[key]
    note = {
        'gold': 'Changes the current wallet; cumulative spending and rewards remain separate.',
        'stock_exp': 'Stock EXP is a shared Dojo pool. Officer growth and Dojo level limits are applied by the game.',
        'stock_mastery': 'This is the stock weapon mastery pool, separate from weapon ranks and each officer’s mastery.',
        'skill_points': 'Shared spendable skill points; learned skills and per-officer allocated points are preserved.',
    }.get(key, 'Building material quantity; castle rank, building levels and upgrade prerequisites are preserved.')
    return f'{note} Native range 0–{item.maximum:,}. Max preserves existing higher values and older checkpoints.'

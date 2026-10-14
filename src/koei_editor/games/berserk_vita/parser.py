"""Decrypted EU Berserk Vita revision-2 copies; authentication remains external.

The complete published Vita editor writer establishes direct patch-only storage.
Two native EU exports qualify the exact geometry; Windows fields are separate.
Only Gold deductions and existing ordinary materials are writable here.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_enabled, within_numeric_limits
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'berserk_vita'
EXTENSION = '.dat'
SAVE_SIZE = 960512
TITLE_ID = 'PCSB01085'
HEADER = bytes.fromhex('00000000020000007cd401000000000000000000000000007000000000000000')
GOLD_OFFSET = 0x3774
MATERIAL_BASE = 0x3690
MATERIAL_NAMES = ('Red Stone', 'Blue Stone', 'Yellow Stone', 'Brown Stone',
                  'White Stone', 'Black Stone', 'Ruby', 'Aquamarine', 'Topaz',
                  'Amber', 'Quartz', 'Jet', 'Fire Ruby', 'Water Aquamarine',
                  'Wind Topaz', 'Earth Amber', 'Light Crystal', 'Black Crystal')
CHARACTER_BASE, CHARACTER_STRIDE = 0xF0, 384
CHARACTERS = ('Guts', 'Griffith', 'Casca', 'Judeau', 'Character slot 5',
              'Character slot 6', 'Character slot 7', 'Character slot 8')
INTEGRITY_KIND = 'external'
MAX_SFO_SIZE = 4096


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    group: str
    slot: int = 0
    minimum: int = 0
    size: int = 4
    maxable: bool = False
    kind: str = 'int'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Berserk and the Band of the Hawk (PS Vita, EU decrypted PCSB01085)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Decrypted EU Vita revision-2 gameplay copies with original sce_sys/param.sfo. '
                 'Gold reductions and manual existing ordinary material quantities. '
                 'Character growth, status, accessories and progression remain unchanged. '
                 'Vita save-manager reimport is required; this does not decrypt or sign console saves.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    context_sha256: str | None = None

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the EU Vita Berserk profile.')
    return FORMAT


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:32] != HEADER:
        raise SaveError('Requires the qualified decrypted 960,512-byte EU Berserk Vita revision-2 gameplay profile.')
    # Both complete native exports carry these separately serialized roster IDs.
    # Ownership/availability bytes before each ID array remain untouched.
    roster = bytes(range(8))
    if raw[0x44:0x4C] != roster or raw[0x54:0x5C] != roster:
        raise SaveError('Berserk Vita roster/record fingerprint does not match.')


def parent_directory(raw):
    """Parse only the title-bearing PARENT_DIRECTORY from bounded PSF1.1 bytes."""
    if type(raw) is not bytes or not 20 <= len(raw) <= MAX_SFO_SIZE:
        raise SaveError('Vita metadata has an invalid bounded size.')
    magic, version, keys, data, count = struct.unpack_from('<5I', raw)
    if (magic != 0x46535000 or version != 0x101 or count > 128
            or not 20 + count * 16 <= keys <= data <= len(raw)):
        raise SaveError('Vita metadata has an invalid PSF1.1 header.')
    found = None
    for index in range(count):
        key_offset, encoding, length, capacity, relative = struct.unpack_from('<HH3I', raw, 20 + index * 16)
        start = keys + key_offset
        if not keys <= start < data:
            raise SaveError('Vita metadata key lies outside the key table.')
        end = raw.find(b'\0', start, data)
        if end < 0:
            raise SaveError('Vita metadata key is unterminated.')
        if raw[start:end] != b'PARENT_DIRECTORY':
            continue
        position = data + relative
        if (found is not None or encoding != 0x204 or not 1 <= length <= capacity <= 128
                or position < data or position + capacity > len(raw)):
            raise SaveError('Vita title identity entry is malformed or duplicated.')
        value = raw[position:position + length]
        if value[-1:] != b'\0' or b'\0' in value[:-1]:
            raise SaveError('Vita title identity is not a terminated string.')
        try:
            found = value[:-1].decode('ascii')
        except UnicodeDecodeError as error:
            raise SaveError('Vita title identity must be ASCII.') from error
    if found != '/' + TITLE_ID:
        raise SaveError('Vita metadata does not identify the supported EU Berserk title.')
    return found


def context(path):
    companion = safe_path(Path(path).parent / 'sce_sys' / 'param.sfo')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except OSError as error:
        raise SaveError('Keep the original sce_sys/param.sfo beside this decrypted Vita gameplay copy.') from error
    parent_directory(raw)
    return hashlib.sha256(raw).hexdigest()


def _copy_path(path):
    path = safe_path(path)
    if path.suffix.lower() != EXTENSION:
        raise SaveError('Use a separate decrypted gameplay .dat copy; keep its original sce_sys/param.sfo.')
    return path


def decode(raw, game_id=GAME_ID, source=Path('app0000.dat')):
    get_format(game_id)
    qualify(raw)
    return Document(FORMAT, Path(source), raw, raw)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    stamp = context(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    qualify(raw)
    return Document(FORMAT, path, raw, raw, stamp)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload
            or (document.context_sha256 is not None
                and (type(document.context_sha256) is not str
                     or len(document.context_sha256) != 64
                     or any(c not in '0123456789abcdef' for c in document.context_sha256)))):
        raise SaveError('A frozen Berserk Vita gameplay snapshot is required.')
    qualify(document.raw)


@lru_cache(maxsize=4)
def _fields(payload, experimental=False):
    gold = struct.unpack_from('<I', payload, GOLD_OFFSET)[0]
    result = [Field('gold', 'Gold (reduce only)', GOLD_OFFSET, gold, 'Resources')]
    for index, name in enumerate(MATERIAL_NAMES):
        value = payload[MATERIAL_BASE + index]
        # Do not manufacture undiscovered materials or normalize unusual bytes.
        if 1 <= value <= (255 if experimental else 99):
            result.append(Field(f'material_{index}', name, MATERIAL_BASE + index,
                                99, 'Existing materials', index + 1, size=1))
    return tuple(result)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Berserk changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapping:
            raise SaveError('Only qualified Berserk resources and existing materials are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    result = bytes(output)
    qualify(result)
    return result


def serialize(document, changes):
    result = changed_payload(document, changes)
    return document.raw if result == document.payload else result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if key not in mapping:
        raise SaveError('This Berserk field is read only.')
    result = dict(changes)
    if type(value) is int and value == mapping[key].value(document.payload):
        result.pop(key, None)
    else:
        mapping[key].validate(value)
        result[key] = value
    changed_payload(document, result)
    return result


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapping = field_map(document)
    if any(key not in mapping for key in keys):
        raise SaveError('This Berserk field is read only.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def _validate_source(document):
    validate_document(document)
    source = _copy_path(document.source)
    if document.context_sha256 is None or context(source) != document.context_sha256:
        raise SaveError('The original Vita metadata changed or was not qualified. Reopen the copied save.')
    with source.open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The original Vita gameplay copy changed. Reopen it before saving.')
    return source


def backup(document):
    source = _validate_source(document)
    snapshot = snapshot_backup(document.raw, source, GAME_ID, source.parent / 'UniversalEditorBackups')
    metadata = {'game_id': GAME_ID, 'kind': 'vita-export-context',
                'context_sha256': document.context_sha256}
    try:
        atomic_new(json.dumps(metadata).encode('utf-8'),
                   snapshot.with_name(snapshot.name + '.context.json'))
    except Exception:
        snapshot.unlink(missing_ok=True)
        snapshot.with_suffix('.json').unlink(missing_ok=True)
        raise
    return snapshot


def save_as(document, changes, destination):
    source = _validate_source(document)
    destination = _copy_path(destination)
    if context(destination) != document.context_sha256:
        raise SaveError('Keep the same unchanged original Vita metadata with the destination.')
    if source == destination or destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    result = serialize(document, changes)
    backup(document)
    _validate_source(document)
    if context(destination) != document.context_sha256:
        raise SaveError('The destination Vita metadata changed before writing.')
    atomic_new(result, destination)
    return read_save(destination, GAME_ID)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination = _copy_path(destination)
    backup_path = safe_path(backup_path)
    stamp = context(destination)
    try:
        with safe_path(backup_path.with_name(backup_path.name + '.context.json')).open('rb') as stream:
            raw_metadata = stream.read(1025)
        if len(raw_metadata) > 1024:
            raise SaveError('Vita backup context metadata is too large.')
        metadata = json.loads(raw_metadata)
    except (OSError, ValueError, UnicodeError) as error:
        raise SaveError('Vita backup context metadata is missing or damaged.') from error
    if (type(metadata) is not dict or metadata.get('game_id') != GAME_ID
            or metadata.get('kind') != 'vita-export-context'
            or metadata.get('context_sha256') != stamp):
        raise SaveError('Restore requires the same original Vita metadata as the backup.')
    def validate_restored(raw):
        qualify(raw)
        if context(destination) != stamp:
            raise SaveError('The destination Vita metadata changed before restoring.')
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, SAVE_SIZE,
                            validate_raw=validate_restored)


def prepare_self_test_copy(document, destination):
    """Write only minimal title metadata; never export owner or signing fields."""
    validate_document(document)
    companion = safe_path(Path(destination).parent / 'sce_sys' / 'param.sfo')
    if companion.exists():
        context(destination)
        return
    key = b'PARENT_DIRECTORY\0'
    value = ('/' + TITLE_ID).encode('ascii') + b'\0'
    key_start = 36
    data_start = (key_start + len(key) + 3) & ~3
    raw = (struct.pack('<5I', 0x46535000, 0x101, key_start, data_start, 1)
           + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0)
           + key + bytes(data_start - key_start - len(key)) + value)
    parent_directory(raw)
    atomic_new(raw, companion)


def record_label(slot, group='Resources'):
    return MATERIAL_NAMES[slot - 1] if slot else group


def character_records(document):
    validate_document(document)
    return tuple((name, *struct.unpack_from('<I5H', document.payload,
                                           CHARACTER_BASE + slot * CHARACTER_STRIDE))
                 for slot, name in enumerate(CHARACTERS))


def material_records(document):
    validate_document(document)
    return tuple((index + 1, name, document.payload[MATERIAL_BASE + index],
                  'Editable existing material' if 1 <= document.payload[MATERIAL_BASE + index] <= 99
                  else 'Zero or unusual value preserved')
                 for index, name in enumerate(MATERIAL_NAMES))


def field_hint(document, key):
    field = field_map(document)[key if isinstance(key, str) else key.id]
    if field.id == 'gold':
        return ('Reduce this opened spendable Gold balance. Adjacent lifetime/history words, '
                'character growth and unlocks remain unchanged. Max is disabled.')
    return ('Manual quantity 0–99 for this existing ordinary material. This editor range '
            'is not a proved natural gameplay maximum. Zero/unusual opened records are not activated; '
            'accessories, enhancement levels, ownership and rewards remain unchanged. Max is disabled.')

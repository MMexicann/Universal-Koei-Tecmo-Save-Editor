"""Decrypted PCSE00296 Meruru Plus; console authentication remains external.

The complete native layout differs from DX PC. Remumu's published working Vita
writer independently establishes the Cole and character word mappings and its
patch-only integrity model. No calendar, EXP, level, item or story writes occur.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_enabled, within_numeric_limits
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'meruru_plus_vita'
EXTENSION = ''
SAVE_SIZE = 558080
TITLE_ID = 'PCSE00296'
MAGIC = 20100403
CHUNK_SIZES = (46120, 6972, 4, 5628, 179724, 121, 100768, 4, 6968, 1,
               8, 68, 604, 2030, 8, 3584, 95968, 1469, 84, 384, 94260,
               4800, 108, 80)
TRAILER_SIZE = 8091
COLE_OFFSET = 0xCF9C
CHARACTER_BASE, CHARACTER_STRIDE = 0xCFA8, 0x1B0
CHARACTERS = ('Meruru', 'Keina', 'Lias', 'Mimi', 'Gino', 'Sterk', 'Esty',
              'Gio', 'Totori', 'Rorona', 'Rufus', 'Hanna', 'Pamela')
BASE_STATS = (('hp', 'Base HP (increase only)', 24, 1), ('mp', 'Base MP (increase only)', 28, 0),
              ('lp', 'Base LP (increase only)', 32, 0), ('attack', 'Base attack', 36, 0),
              ('defense', 'Base defense', 40, 0), ('speed', 'Base speed', 44, 0))
GAUGES = (('hp', 'Current HP', 12, 1), ('mp', 'Current MP', 16, 0),
          ('lp', 'Current LP', 20, 0))
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

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Atelier Meruru Plus (PS Vita, US decrypted PCSE00296)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Decrypted US Vita gameplay copies with original sce_sys/param.sfo. '
                 'Cole, manual base ATK/DEF/speed, base HP/MP/LP increases and current-gauge reductions. '
                 'Equipment, level/EXP, inventory and story stay unchanged. '
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
        raise SaveError('Select the US Vita Atelier Meruru Plus profile.')
    return FORMAT


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or struct.unpack_from('<I', raw)[0] != MAGIC:
        raise SaveError('Requires the qualified decrypted 558,080-byte Meruru Plus Vita gameplay profile.')
    offset = 32
    for tag, size in enumerate(CHUNK_SIZES, 1):
        if struct.unpack_from('<II', raw, offset) != (tag, size):
            raise SaveError('Meruru Plus Vita chunk/revision fingerprint does not match.')
        offset += size + 8
    if struct.unpack_from('<II', raw, offset) != (1024, TRAILER_SIZE) or offset + TRAILER_SIZE != len(raw):
        raise SaveError('Meruru Plus Vita trailer bounds do not match.')
    for slot in range(len(CHARACTERS)):
        if struct.unpack_from('<I', raw, CHARACTER_BASE + slot * CHARACTER_STRIDE)[0] != slot:
            raise SaveError('Meruru Plus Vita character record identities do not match.')


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
        raise SaveError('Vita metadata does not identify the supported US Meruru Plus title.')
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
        raise SaveError('Use an extensionless decrypted USR-DATA0000 copy; keep its sce_sys/param.sfo.')
    return path


def decode(raw, game_id=GAME_ID, source=Path('USR-DATA0000')):
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
        raise SaveError('A frozen Meruru Plus Vita gameplay snapshot is required.')
    qualify(document.raw)


@lru_cache(maxsize=4)
def _fields(payload, experimental=False):
    result = [Field('cole', 'Cole', COLE_OFFSET, 9999999, 'Resources')]
    for slot, name in enumerate(CHARACTERS):
        base = CHARACTER_BASE + slot * CHARACTER_STRIDE
        for key, label, relative, minimum in BASE_STATS:
            result.append(Field(f'character_{slot}_{key}', label, base + relative,
                                999, 'Base character stats', slot + 1, minimum))
        for key, label, relative, minimum in GAUGES:
            original = struct.unpack_from('<I', payload, base + relative)[0]
            if minimum <= original <= (0xFFFFFFFF if experimental else 0x7FFFFFFF):
                result.append(Field(f'character_{slot}_current_{key}', label, base + relative,
                                    original, 'Current gauges — reduce only', slot + 1, minimum))
    return tuple(result)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Meruru Plus changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if key not in mapping:
            raise SaveError('Only qualified Meruru Plus resources and character fields are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        if (field.group == 'Base character stats'
                and field.id.rsplit('_', 1)[-1] in ('hp', 'mp', 'lp')
                and value < field.value(document.payload)):
            raise SaveError('Base HP/MP/LP can only increase from the opened value; effective equipment maxima are not mapped.')
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
        raise SaveError('This Meruru Plus field is read only.')
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
        raise SaveError('This Meruru Plus field is read only.')
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
    # Preserve completed backup files if companion creation or source
    # revalidation fails; these paths may now contain another app's bytes.
    atomic_new(json.dumps(metadata).encode('utf-8'),
               snapshot.with_name(snapshot.name + '.context.json'))
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
    return CHARACTERS[slot - 1] if slot else group


def character_records(document):
    validate_document(document)
    return tuple((name, *struct.unpack_from('<11I', document.payload,
                                           CHARACTER_BASE + slot * CHARACTER_STRIDE + 4))
                 for slot, name in enumerate(CHARACTERS))


def item_records(document):
    """Read observed numeric records only; the reference editor never saved items."""
    validate_document(document)
    result = []
    base = 0x3A441
    for slot in range(2099):
        values = struct.unpack_from('<12I', document.payload, base + slot * 48)
        serial, identity = values[:2]
        if serial == 0xFFFFFFFF and identity == 0xFFFFFFFF:
            continue
        quality = struct.unpack_from('<f', document.payload, base + slot * 48 + 8)[0]
        text = f'{quality:.9g}' if math.isfinite(quality) else 'Non-finite (preserved)'
        result.append(('Basket' if slot < 100 else 'Container',
                       slot + 1 if slot < 100 else slot - 99, serial, identity, text,
                       ', '.join(str(x) for x in values[3:8]),
                       ', '.join(str(x) for x in values[8:11]), values[11]))
    return tuple(result)


def field_hint(document, key):
    field = field_map(document)[key if isinstance(key, str) else key.id]
    if field.id == 'cole':
        return ('Manual Cole range 0–9,999,999; this is an editor range, not a proved natural cap. '
                'Max is disabled; higher opened values remain unchanged. Reimport the edited decrypted copy on Vita.')
    if '_current_' in field.id:
        return ('Reduce this opened gauge only; equipment changes effective maxima, so stored base stats '
                'are not refill caps. No level, EXP, ownership or equipment reference is changed. Max is disabled.')
    if field.id.rsplit('_', 1)[-1] in ('hp', 'mp', 'lp'):
        return ('Increase this stored base HP/MP/LP only, up to the manual editor limit 999. '
                'Decreases are unavailable because equipment-adjusted maxima are not mapped. '
                'Current gauges remain unchanged. This is not a natural gameplay cap; Max is disabled.')
    return ('Edit the stored base stat within the manual 0–999 range. Equipment and traits '
            'determine effective stats separately. Levels, EXP, skills, party and story stay unchanged; Max is disabled.')

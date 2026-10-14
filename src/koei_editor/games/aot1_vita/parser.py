"""Independent published EU Attack on Titan Vita resource writer.

Complete title-specific RinCheat SE writer facts and two original exports qualify
this conservative scope; internal integrity is not independently established.
See docs/AOT1_VITA_FORMAT.md.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
MAX_SFO_SIZE = 4096
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'aot1_vita'
TITLE_ID = 'PCSB00898'
SAVE_SIZE = 0xBB800
CHECKSUM_OFFSETS = ()
INTEGRITY_KIND = 'external'
HEADER_SEGMENTS = ((0, bytes.fromhex('0000000000000000f0e70500000000000000000000000000c043020000000000')),)


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
    maxable: bool = False
    kind: str = 'int'
    encoding: str = 'unsigned little-endian integer'
    evidence: str = 'Apollo PCSB00898 map; complete fixed-address writer; two original EU Vita exports'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label}: choose a whole number from 0 to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'little')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True
    published_format: bool = True
    game_load_verified: bool = False


FORMAT = Format(GAME_ID, 'Attack on Titan: Wings of Freedom (PS Vita, EU)', SAVE_SIZE, (),
                'Reduce money and positive existing numbered material quantities in copied '
                'decrypted app0000.dat beside its original sce_sys/param.sfo. Item identities, '
                'ownership, equipment, character growth and story remain intact. Vita save-manager '
                'reimport and authentication stay external.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    native_directory: str | None
    context_digest: str = ""

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


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
        raise SaveError('Vita metadata does not identify the supported EU Attack on Titan title.')
    return found



def context_raw(path):
    companion = safe_path(Path(path).parent / 'sce_sys' / 'param.sfo')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except OSError as error:
        raise SaveError('Keep the original sce_sys/param.sfo beside the decrypted Vita copy.') from error
    parent_directory(raw)
    return raw


def context(path):
    return parent_directory(context_raw(path))


def context_digest(path):
    return hashlib.sha256(context_raw(path)).hexdigest()


def qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE
            or any(raw[offset:offset + len(value)] != value
                   for offset, value in HEADER_SEGMENTS)):
        raise SaveError("Requires the qualified 0xBB800-byte decrypted EU Attack on Titan Vita "
                        'app0000.dat layout. Encrypted files, foreign layouts and other revisions are rejected.')
    # Complete title-specific RinCheat SE writer directly changes resource bytes,
    # while Vita save authentication stays external. This is NOT a proof that the
    # native game has no internal integrity. Header matching only gates layout.


def seal(payload):
    return payload


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError("Select this exact Attack on Titan Vita adapter.")
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    qualify(raw)
    directory = context(source) if (Path(source).parent / 'sce_sys' / 'param.sfo').exists() else None
    digest = context_digest(source) if directory else ""
    return Document(FORMAT, Path(source), raw, raw, directory, digest)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate decrypted app0000.dat copy renamed with a .dat extension.')
    directory = context(path)
    digest = context_digest(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    qualify(raw)
    if context(path) != directory or context_digest(path) != digest:
        raise SaveError('The original sce_sys/param.sfo identity changed while opening the copy.')
    return Document(FORMAT, path, raw, raw, directory, digest)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path)
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload
            or type(document.context_digest) is not str
            or (document.native_directory is not None and (len(document.context_digest) != 64
                or any(c not in "0123456789abcdef" for c in document.context_digest)))
            or (document.native_directory is not None and document.native_directory != '/' + TITLE_ID)):
        raise SaveError("A frozen qualified Attack on Titan Vita document is required.")
    qualify(document.raw)


def fields_for(document):
    validate_document(document)
    money = int.from_bytes(document.payload[0x34:0x38], 'little')
    result = [Field('money', 'Money (reduce only)', 0x34, 4, money)]
    for index in range(81):
        offset = 0x35CA0 + index * 0x30
        original = int.from_bytes(document.payload[offset:offset + 2], 'little')
        if original:
            result.append(Field(f'material_{index}_quantity',
                                f'Material record {index + 1}: quantity (reduce only)',
                                offset, 2, original, 'Existing material quantities', index + 1))
    return tuple(result)


def field_map(document):
    return {field.id: field for field in fields_for(document)}


def validated_changes(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Staged resources must be a mapping.')
    fields = field_map(document)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('This resource is not qualified for the opened save.')
        fields[key].validate(value)
    return fields


def changed_payload(document, changes):
    fields = validated_changes(document, changes)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = fields[key]
        result[field.offset:field.offset + field.size] = field.encoded(value)
    payload = bytes(result)
    return seal(payload) if payload != document.payload else payload


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    reopened = decode(payload, source=document.source)
    fields = field_map(document)
    for key, value in changes.items():
        if fields[key].value(reopened.payload) != value:
            raise SaveError('Edited Attack on Titan resource did not read back as requested.')
    return payload


def stage(document, changes, key, value):
    fields = validated_changes(document, changes)
    if type(key) is not str or key not in fields:
        raise SaveError('This resource is not qualified for the opened save.')
    field = fields[key]
    field.validate(value)
    result = dict(changes)
    if value == field.value(document.payload):
        result.pop(key, None)
    else:
        result[key] = value
    return result


def limit_values(document, changes, keys):
    fields = validated_changes(document, changes)
    if any(type(key) is not str or key not in fields for key in keys):
        raise SaveError('Unknown or unqualified resource.')
    return {}  # Published cheat targets do not establish natural gameplay caps.


def maximums(document, changes, group=None):
    validated_changes(document, changes)
    return dict(changes)


def review(document, changes):
    fields = validated_changes(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields.values() if field.id in changes]


def identity_metadata(directory='/' + TITLE_ID):
    key = b'PARENT_DIRECTORY\0'
    value = directory.encode('ascii') + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value)


def validate_source(document):
    validate_document(document)
    if (not document.context_digest or context(document.source) != document.native_directory
            or context_digest(document.source) != document.context_digest):
        raise SaveError('The original sce_sys/param.sfo save identity changed.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen before saving.')


def backup(document):
    validate_source(document)
    result = snapshot_backup(document.raw, document.source, GAME_ID,
                             document.source.parent / 'UniversalEditorBackups')
    metadata = {'game_id': GAME_ID, 'kind': 'aot1-vita-export-context',
                'context_sha256': document.context_digest, 'save_sha256': document.sha256}
    try:
        atomic_new(json.dumps(metadata).encode('utf-8'),
                   result.with_name(result.name + '.context.json'))
    except Exception:
        result.unlink(missing_ok=True)
        result.with_suffix('.json').unlink(missing_ok=True)
        raise
    return result


def save_as(document, changes, destination):
    validate_source(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.dat':
        raise SaveError('Choose a new decrypted .dat destination.')
    if context_digest(destination) != document.context_digest:
        raise SaveError('Destination needs the same unchanged original sce_sys/param.sfo.')
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    raw = serialize(document, changes)
    backup(document)
    validate_source(document)
    if context_digest(destination) != document.context_digest:
        raise SaveError('The destination sce_sys/param.sfo changed before writing.')
    atomic_new(raw, destination)
    reopened = read_save(destination)
    validate_source(document)
    if (reopened.raw != raw
            or reopened.context_digest != document.context_digest
            or reopened.native_directory != document.native_directory
            or context_digest(destination) != document.context_digest):
        raise SaveError('The written copy no longer matches the opened save and original export metadata.')
    return reopened


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path = safe_path(backup_path)
    digest = context_digest(destination)
    try:
        companion = safe_path(backup_path.with_name(backup_path.name + '.context.json'))
        with companion.open('rb') as stream:
            metadata_raw = stream.read(1025)
        if len(metadata_raw) > 1024:
            raise SaveError('Backup context metadata is too large.')
        metadata = json.loads(metadata_raw)
    except (OSError, ValueError, UnicodeError) as error:
        raise SaveError('This backup lacks valid original-context metadata.') from error
    if (type(metadata) is not dict or metadata.get('game_id') != GAME_ID
            or metadata.get('kind') != 'aot1-vita-export-context'
            or metadata.get('context_sha256') != digest
            or type(metadata.get('save_sha256')) is not str
            or len(metadata['save_sha256']) != 64):
        raise SaveError('Restore requires the same unchanged original sce_sys/param.sfo as the backup.')
    def validate_restore(raw):
        qualify(raw)
        if hashlib.sha256(raw).hexdigest() != metadata['save_sha256']:
            raise SaveError('The backup context belongs to another save snapshot.')
        if context_digest(destination) != digest:
            raise SaveError('The restore destination sce_sys/param.sfo changed.')
    result = restore_snapshot(backup_path, destination, GAME_ID, '.dat', SAVE_SIZE,
                              validate_raw=validate_restore)
    reopened = read_save(result)
    if (reopened.sha256 != metadata['save_sha256']
            or reopened.context_digest != digest
            or context_digest(result) != digest):
        raise SaveError('The restored copy no longer matches the backup and original export metadata.')
    return result


def prepare_copy_context(document, output_dir):
    """Privately copy the bounded original opaquely; never synthesize metadata."""
    validate_source(document)
    raw = context_raw(document.source)
    if hashlib.sha256(raw).hexdigest() != document.context_digest:
        raise SaveError('The original sce_sys/param.sfo changed before copying.')
    companion = safe_path(Path(output_dir) / 'sce_sys' / 'param.sfo')
    if companion.exists():
        raise FileExistsError('Choose a new self-test context destination.')
    validate_source(document)
    atomic_new(raw, companion)


def prepare_self_test_copy(document, destination):
    validate_source(document)
    if context_digest(destination) != document.context_digest:
        raise SaveError('Keep the unchanged original sce_sys/param.sfo beside copied output.')


def record_label(slot, group='Resources'):
    return group


def field_hint(document, field_id):
    fields = field_map(document)
    if type(field_id) is not str or field_id not in fields:
        raise SaveError('Unknown or unqualified existing resource.')
    return ('Reduce an existing balance only. Exact typed originals remove staged edits; Max '
            'is disabled. Zero material rows, identities, ownership, equipment and story stay '
            'intact. Native gameplay integrity is not independently established; reimport '
            'and authenticate using the Vita save manager.')


def material_records(document):
    validate_document(document)
    fields = field_map(document)
    return tuple((index + 1, int.from_bytes(document.payload[0x35CA0 + index * 0x30:
                                                           0x35CA2 + index * 0x30], 'little'),
                  'Reduce only' if f'material_{index}_quantity' in fields else 'Read only')
                 for index in range(81))

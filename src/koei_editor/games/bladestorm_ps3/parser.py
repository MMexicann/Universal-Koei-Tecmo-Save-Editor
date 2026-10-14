"""Independent published EU Bladestorm PS3 resource writer.

Complete title-specific Apollo writer facts and two original exports qualify
this conservative scope; internal integrity is not independently established.
See docs/BLADESTORM_PS3_FORMAT.md.
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
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'bladestorm_ps3'
TITLE_IDS = ('BLES00113',)
SAVE_SIZE = 0x793D0
CHECKSUM_OFFSETS = ()
INTEGRITY_KIND = 'external'
HEADER_SEGMENTS = ((2, b'\x01\x01'), (0x2C, bytes.fromhex('bc420000ffffffff')))


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
    encoding: str = 'unsigned big-endian integer'
    evidence: str = 'Apollo BLES00113 resource map; two original decrypted public EU exports'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label}: choose a whole number from 0 to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'big')


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


FORMAT = Format(GAME_ID, "Bladestorm: The Hundred Years' War (PS3, EU)", SAVE_SIZE, (),
                'Reduce published primary money and positive existing book SP pools on a decrypted '
                'PLAYDATA copy beside its original EU PARAM.SFO. Book ownership, learned '
                'skills, secondary money, character stats and story progress stay intact. '
                'Reimport and resign the edited copy with Apollo for console use.')


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


def valid_directory(directory):
    return type(directory) is str and any(
        directory.startswith(title + 'PLAY') and len(directory) == len(title) + 5
        and directory[-1:].isascii() and directory[-1:].isdigit() for title in TITLE_IDS)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
            directory = savedata_directory(raw)
    except FileNotFoundError as error:
        raise SaveError('Keep the original PARAM.SFO beside the decrypted PLAYDATA copy.') from error
    if not valid_directory(directory):
        raise SaveError("PARAM.SFO is not a supported EU Bladestorm save identity.")
    return raw


def context(path):
    return savedata_directory(context_raw(path))


def context_digest(path):
    return hashlib.sha256(context_raw(path)).hexdigest()


def qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE
            or any(raw[offset:offset + len(value)] != value
                   for offset, value in HEADER_SEGMENTS)):
        raise SaveError("Requires the qualified 0x793D0-byte decrypted EU Bladestorm PS3 "
                        'PLAYDATA layout. Encrypted files, foreign layouts and other revisions are rejected.')
    # Complete title-specific Game Genie/Apollo writer directly changes money,
    # then rebuilds external PFD authentication. This is NOT a proof that the
    # native game has no internal integrity. Header matching only gates layout.


def seal(payload):
    return payload


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError("Select this exact Bladestorm PS3 adapter.")
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.bin')):
    get_format(game_id)
    qualify(raw)
    directory = context(source) if (Path(source).parent / 'PARAM.SFO').exists() else None
    digest = context_digest(source) if directory else ""
    return Document(FORMAT, Path(source), raw, raw, directory, digest)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate decrypted PLAYDATA copy renamed with a .bin extension.')
    directory = context(path)
    digest = context_digest(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    qualify(raw)
    if context(path) != directory or context_digest(path) != digest:
        raise SaveError('The original PARAM.SFO identity changed while opening the copy.')
    return Document(FORMAT, path, raw, raw, directory, digest)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path)
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload
            or type(document.context_digest) is not str
            or (document.native_directory is not None and (len(document.context_digest) != 64
                or any(c not in "0123456789abcdef" for c in document.context_digest)))
            or (document.native_directory is not None and not valid_directory(document.native_directory))):
        raise SaveError("A frozen qualified Bladestorm PS3 document is required.")
    qualify(document.raw)


def fields_for(document):
    validate_document(document)
    result = [Field('money', 'Published primary money (reduce only)', 0x84, 4,
                    int.from_bytes(document.payload[0x84:0x88], 'big'))]
    for index in range(16):
        offset = 0x394 + index * 0x54
        value = int.from_bytes(document.payload[offset:offset + 4], 'big')
        if value:
            result.append(Field(f'book_{index}_sp', f'Book record {index + 1}: SP (reduce only)',
                                offset, 4, value, 'Existing book SP pools', index + 1))
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
            raise SaveError('Edited Bladestorm resource did not read back as requested.')
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


def identity_metadata(directory):
    key = b'SAVEDATA_DIRECTORY\0'
    value = directory.encode('ascii') + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value)


def validate_source(document):
    validate_document(document)
    if (not document.context_digest or context(document.source) != document.native_directory
            or context_digest(document.source) != document.context_digest):
        raise SaveError('The original PARAM.SFO save identity changed.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen before saving.')


def backup(document):
    validate_source(document)
    result = snapshot_backup(document.raw, document.source, GAME_ID,
                             document.source.parent / 'UniversalEditorBackups')
    metadata = {'game_id': GAME_ID, 'kind': 'bladestorm-ps3-export-context',
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
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new decrypted .bin destination.')
    if context_digest(destination) != document.context_digest:
        raise SaveError('Destination needs the same unchanged original PARAM.SFO.')
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    raw = serialize(document, changes)
    backup(document)
    validate_source(document)
    if context_digest(destination) != document.context_digest:
        raise SaveError('The destination PARAM.SFO changed before writing.')
    atomic_new(raw, destination)
    reopened = read_save(destination)
    if (reopened.raw != raw or reopened.context_digest != document.context_digest
            or reopened.native_directory != document.native_directory):
        raise SaveError('The written copy no longer matches the opened snapshot and original PARAM.SFO.')
    validate_source(document)
    if context_digest(destination) != document.context_digest:
        raise SaveError('The destination PARAM.SFO changed after writing.')
    return reopened


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path = safe_path(backup_path)
    destination = safe_path(destination)
    directory = context(destination)
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
            or metadata.get('kind') != 'bladestorm-ps3-export-context'
            or metadata.get('context_sha256') != digest
            or type(metadata.get('save_sha256')) is not str
            or len(metadata['save_sha256']) != 64):
        raise SaveError('Restore requires the same unchanged original PARAM.SFO as the backup.')
    def validate_restore(raw):
        qualify(raw)
        if hashlib.sha256(raw).hexdigest() != metadata['save_sha256']:
            raise SaveError('The backup context belongs to another save snapshot.')
        if context_digest(destination) != digest:
            raise SaveError('The restore destination PARAM.SFO changed.')
    result = restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                              validate_raw=validate_restore)
    reopened = read_save(result)
    if (reopened.sha256 != metadata['save_sha256'] or reopened.context_digest != digest
            or reopened.native_directory != directory):
        raise SaveError('The restored copy no longer matches its backup and original PARAM.SFO.')
    if context_digest(result) != digest:
        raise SaveError('The restore destination PARAM.SFO changed after writing.')
    return result


def prepare_copy_context(document, output_dir):
    """Privately copy the bounded original opaquely; never synthesize metadata."""
    validate_source(document)
    raw = context_raw(document.source)
    if hashlib.sha256(raw).hexdigest() != document.context_digest:
        raise SaveError('The original PARAM.SFO changed before copying.')
    companion = safe_path(Path(output_dir) / 'PARAM.SFO')
    if companion.exists():
        raise FileExistsError('Choose a new self-test context destination.')
    validate_source(document)
    atomic_new(raw, companion)


def prepare_self_test_copy(document, destination):
    validate_source(document)
    if context_digest(destination) != document.context_digest:
        raise SaveError('Keep the unchanged original PARAM.SFO beside copied output.')


def record_label(slot, group='Resources'):
    return group


def field_hint(document, field_id):
    fields = field_map(document)
    if type(field_id) is not str or field_id not in fields:
        raise SaveError('Unknown or unqualified resource.')
    return ('Reduce a published resource from zero to its opened value. Assigning the original '
            'typed value removes a staged edit. Max is disabled. Zero SP records, book ownership, '
            'secondary money, learned skills and story progress remain unchanged. Reimport and '
            'resign with Apollo. Native gameplay integrity is not independently established.')


def inspection_rows(document):
    validate_document(document)
    return ({'group': 'Published storage', 'label': 'Secondary money word (read only)',
             'value': str(int.from_bytes(document.payload[0xAB8:0xABC], 'big'))},)

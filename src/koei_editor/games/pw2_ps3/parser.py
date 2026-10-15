"""Published Pirate Warriors 2 PS3 scalar controls.

See docs/PIRATE_WARRIORS_PS3_FORMAT.md for exact source, profiles and limits.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.adapter_contract import normalize_pending_values, is_opened_value
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'pw2_ps3'
TITLE_IDS = ('NPEB01795',)
SAVE_SIZE = 0xbb800
CHECKSUM_OFFSETS = ()
INTEGRITY_KIND = 'external'
HEADER_SEGMENTS = ((0, bytes.fromhex('00000000000000020002ca7800000000')),)


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
    evidence: str = 'Published Apollo NPEB01795 field map; privately qualified original public PS3 export'

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


FORMAT = Format(GAME_ID, 'One Piece: Pirate Warriors 2 (PS3, NPEB01795)', SAVE_SIZE, (),
                'Published primary Berry reductions; secondary Berry word inspected separately. Open a decrypted DATA.BIN copy beside its original PARAM.SFO. '
                'Max is disabled. Reimport and resign with Apollo for console loading; '
                'independent edited game-load validation remains outstanding.')


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
    return type(directory) is str and directory == TITLE_IDS[0] + '-00'

def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
            directory = savedata_directory(raw)
    except FileNotFoundError as error:
        raise SaveError('Keep the original PARAM.SFO beside the decrypted DATA.BIN copy.') from error
    if not valid_directory(directory):
        raise SaveError("PARAM.SFO is not a supported One Piece: Pirate Warriors 2 save identity.")
    return raw


def context(path):
    return savedata_directory(context_raw(path))


def context_digest(path):
    return hashlib.sha256(context_raw(path)).hexdigest()


def qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE
            or any(raw[offset:offset + len(value)] != value
                   for offset, value in HEADER_SEGMENTS)):
        raise SaveError('Requires the qualified NPEB01795 decrypted DATA.BIN profile of 768,000 bytes. '
                        'Other header variants, encrypted data and foreign editions are rejected.')
    # Source recipes directly patch exported values and rebuild external PS3 PFD
    # authentication. The observed zero header word at 0xC is preserved exactly;
    # variants containing another value are not normalized or accepted.


def seal(payload):
    return payload


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError("Select this exact One Piece: Pirate Warriors 2 PS3 adapter.")
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
        raise SaveError('Open a separate decrypted DATA.BIN copy renamed with a .bin extension.')
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
        raise SaveError("A frozen qualified One Piece: Pirate Warriors 2 PS3 document is required.")
    qualify(document.raw)


def fields_for(document):
    validate_document(document)
    return (Field('berry', 'Primary Berry balance (reduce only)', 0xA614, 4,
                  int.from_bytes(document.payload[0xA614:0xA618], 'big')),)


def field_map(document):
    return {field.id: field for field in fields_for(document)}


def validated_changes(document, changes):
    fields = field_map(document)
    normalize_pending_values(document, changes, fields)
    return fields

def changed_payload(document, changes):
    fields = validated_changes(document, changes)
    changes = normalize_pending_values(document, changes, fields)
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
    for key, value in changes.items():
        if field_map(document)[key].value(reopened.payload) != value:
            raise SaveError('Edited One Piece: Pirate Warriors 2 resource did not read back as requested.')
    return payload


def stage(document, changes, key, value):
    fields = validated_changes(document, changes)
    if type(key) is not str or key not in fields:
        raise SaveError('This field is not qualified for the opened save.')
    field = fields[key]
    result = normalize_pending_values(document, changes, fields)
    if is_opened_value(document, field, value):
        result.pop(key, None)
    else:
        field.validate(value)
        result[key] = value
    return result

def limit_values(document, changes, keys):
    fields = validated_changes(document, changes)
    if any(type(key) is not str or key not in fields for key in keys):
        raise SaveError('Unknown or unqualified resource.')
    return {}  # Published cheat targets do not establish natural gameplay caps.


def maximums(document, changes, group=None):
    validated_changes(document, changes)
    return normalize_pending_values(document, changes, field_map(document))


def review(document, changes):
    fields = validated_changes(document, changes)
    changes = normalize_pending_values(document, changes, fields)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields.values() if field.id in changes]


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
    metadata = {'game_id': GAME_ID, 'kind': 'pw2_ps3-export-context',
                'context_sha256': document.context_digest, 'save_sha256': document.sha256}
    # Preserve completed backup files if companion creation or source
    # revalidation fails; these paths may now contain another app's bytes.
    atomic_new(json.dumps(metadata).encode('utf-8'),
               result.with_name(result.name + '.context.json'))
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
            or metadata.get('kind') != 'pw2_ps3-export-context'
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
    if type(field_id) is not str or field_id not in field_map(document):
        raise SaveError('Unknown or unqualified field.')
    return ('Reduce the published stored value from zero to the opened value. '
            'Natural gameplay caps and bulk Max are unqualified. Reimport and resign with Apollo.')


def inspection_rows(document):
    validate_document(document)
    return ({'group': 'Published Berry storage', 'label': 'Secondary Berry word (read only)',
             'value': str(int.from_bytes(document.payload[0xA618:0xA61C], 'big'))},)

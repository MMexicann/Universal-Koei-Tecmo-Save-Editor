"""Independent published EU Pirate Warriors 3 PS3 stat writer.

Complete title-specific Apollo writer facts and one original export qualify
this conservative scope; internal integrity is not independently established.
See docs/PW3_PS3_FORMAT.md.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'pw3_ps3'
TITLE_IDS = ('NPEB02211',)
SAVE_SIZE = 0xEA800
CHECKSUM_OFFSETS = ()
INTEGRITY_KIND = 'external'
HEADER_SEGMENTS = ((0, struct.pack('>2I', 0, 2)), (12, bytes(12)))
RECORD_COUNT = 47
RECORD_STRIDE = 0x1F0


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
    evidence: str = 'Apollo NPEB02211 stat map; original decrypted public EU reference'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
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


FORMAT = Format(GAME_ID, 'One Piece: Pirate Warriors 3 (PS3, EU PSN)', SAVE_SIZE, (),
                'Reduce stored HP, Attack and Defense on existing progressed character records. '
                'Open a copied decrypted DATA.BIN beside its original NPEB02211 PARAM.SFO. '
                'Stats can reset when the character levels up. Currency, levels, XP, medals, '
                'skills and story progress are preserved. Reimport and resign with Apollo.')


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
        directory == title + '-00' for title in TITLE_IDS)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
            directory = savedata_directory(raw)
    except FileNotFoundError as error:
        raise SaveError('Keep the original PARAM.SFO beside the decrypted DATA.BIN copy.') from error
    if not valid_directory(directory):
        raise SaveError("PARAM.SFO is not a supported EU Pirate Warriors 3 save identity.")
    return raw


def context(path):
    return savedata_directory(context_raw(path))


def context_digest(path):
    return hashlib.sha256(context_raw(path)).hexdigest()


def qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE
            or any(raw[offset:offset + len(value)] != value
                   for offset, value in HEADER_SEGMENTS)):
        raise SaveError("Requires the qualified 0xEA800-byte decrypted EU Pirate Warriors 3 PS3 "
                        'DATA.BIN layout. Encrypted files, foreign layouts and other revisions are rejected.')
    # Complete title-specific Game Genie/Apollo writer directly changes stats,
    # then rebuilds external PFD authentication. This is NOT a proof that the
    # native game has no internal integrity. Header matching only gates layout.


def seal(payload):
    return payload


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError("Select this exact Pirate Warriors 3 PS3 adapter.")
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
        raise SaveError("A frozen qualified Pirate Warriors 3 PS3 document is required.")
    qualify(document.raw)


def eligible_records(document):
    validate_document(document)
    return tuple(index for index in range(RECORD_COUNT)
                 if 1 <= document.payload[0xFB + index * RECORD_STRIDE] <= 99
                 and int.from_bytes(document.payload[0xF0 + index * RECORD_STRIDE:
                                                     0xF4 + index * RECORD_STRIDE], 'big') > 0)


def fields_for(document):
    result = []
    for index in eligible_records(document):
        for key, label, relative, minimum in (('hp', 'Stored HP', 0xF4, 1),
                                              ('attack', 'Stored Attack', 0xF6, 0),
                                              ('defense', 'Stored Defense', 0xF8, 0)):
            offset = relative + index * RECORD_STRIDE
            original = int.from_bytes(document.payload[offset:offset + 2], 'big')
            if original >= max(1, minimum):
                result.append(Field(f'character_{index}_{key}',
                                    f'Character record {index + 1}: {label} (reduce only)',
                                    offset, 2, original, 'Existing character stats', index + 1,
                                    minimum=minimum))
    return tuple(result)


def field_map(document):
    return {field.id: field for field in fields_for(document)}


def validated_changes(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Staged stats must be a mapping.')
    fields = field_map(document)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('This character stat is not qualified for the opened save.')
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
            raise SaveError('Edited Pirate Warriors 3 stat did not read back as requested.')
    return payload


def stage(document, changes, key, value):
    fields = validated_changes(document, changes)
    if type(key) is not str or key not in fields:
        raise SaveError('This character stat is not qualified for the opened save.')
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
        raise SaveError('Unknown or unqualified character stat.')
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
    metadata = {'game_id': GAME_ID, 'kind': 'pw3-ps3-export-context',
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
            or metadata.get('kind') != 'pw3-ps3-export-context'
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
        raise SaveError('Unknown or unqualified existing character stat.')
    return ('Reduce an existing stored stat to its opened value or lower. Stats can reset on '
            'level-up. Exact typed original values unstage edits, and Max is disabled. '
            'Levels, XP, currency, medals, skills and story stay intact. Reimport and resign '
            'externally; native gameplay integrity has not been independently established.')


def inspection_rows(document):
    validate_document(document)
    return tuple({'group': 'Currency storage', 'label': label,
                  'value': str(int.from_bytes(document.payload[offset:offset + 4], 'big'))}
                 for label, offset in (('Published primary Beli word (read only)', 0xC074),
                                       ('Adjacent currency word (read only)', 0xC078)))


def character_records(document):
    validate_document(document)
    eligible = set(eligible_records(document))
    return tuple((index + 1, 'Progressed' if index in eligible else 'Read only',
                  document.payload[0xFB + index * RECORD_STRIDE],
                  int.from_bytes(document.payload[0xF0 + index * RECORD_STRIDE:
                                                  0xF4 + index * RECORD_STRIDE], 'big'),
                  *(int.from_bytes(document.payload[offset + index * RECORD_STRIDE:
                                                    offset + 2 + index * RECORD_STRIDE], 'big')
                    for offset in (0xF4, 0xF6, 0xF8))) for index in range(RECORD_COUNT))

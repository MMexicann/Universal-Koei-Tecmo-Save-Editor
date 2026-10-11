"""Source-backed original US/EU PSN DOA5 costume flags with native integrity.

Console PFD extraction/resigning remains external. Source-positive byte offsets
are deliberately separated from broad character/title/story patches and the
unexplained 0x10 costume targets; all unknown bytes and states are preserved.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.doa5_ps3 import codec
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'doa5_ps3'
EXTENSION = '.dat'
INTEGRITY_KIND = 'checksum'
SAVE_SIZE = codec.SAVE_SIZE
DIRECTORIES = ('NPUB30893SYSTEM_SAVE', 'NPEB01129SYSTEM_SAVE')
# Independent factual transcription of only value-1 bytes in the narrowly
# labelled original PS3 costume patch, corroborated on original-title exports.
# The mixed 0x10 target at 0x3E0 and every value-0 write are excluded.
COSTUME_OFFSETS = (0x30F, 0x310, 0x31A, 0x31B, 0x31C, 0x31D, 0x31E,
                   0x325, 0x326, 0x327, 0x33B, 0x33C, 0x346, 0x347,
                   0x348, 0x349, 0x35C, 0x35D, 0x35E, 0x372, 0x373,
                   0x37D, 0x37E, 0x37F, 0x380, 0x381, 0x382, 0x388,
                   0x389, 0x38A, 0x38B, 0x39E, 0x39F, 0x3A0, 0x3A9,
                   0x3AA, 0x3AB, 0x3AC, 0x3B4, 0x3B5, 0x3BF, 0x3C0,
                   0x3C1, 0x3CA, 0x3CB, 0x3CC, 0x3CD, 0x3D5, 0x3D6,
                   0x3D7, 0x3D8, 0x3EB, 0x3EC, 0x3ED, 0x3EE, 0x3EF,
                   0x3F6, 0x438, 0x439, 0x443, 0x444, 0x445, 0x446)


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    group: str = 'Costume unlocks'
    slot: int = 0
    size: int = 1
    minimum: int = 0
    maximum: int = 1
    maxable: bool = False
    kind: str = 'int'

    def value(self, payload):
        return payload[self.offset]

    def validate(self, value):
        if type(value) is not int or value not in (0, 1):
            raise SaveError('Costume flags require 0 (opened locked value) or 1 (unlocked).')


FIELDS = tuple(Field(f'costume_{offset:04x}',
                     f'Unlock costume flag at 0x{offset:04X}', offset, slot=index + 1)
               for index, offset in enumerate(COSTUME_OFFSETS))


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Dead or Alive 5 (original PS3, US/EU PSN export)'
    size: int = SAVE_SIZE
    fields: tuple = FIELDS
    # Genuine exports validate; unlock-transition fixtures are constructed.
    sample_verified: bool = False
    game_load_verified: bool = False
    note: str = ('Open copied PS3-decrypted SAVE_SYS.DAT beside its original PARAM.SFO. '
                 'Unlock source-backed original costumes; preserve other character, title '
                 'and story data. Native block integrity is maintained. Apollo reimport '
                 'and PS3 resigning remain external.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    context_sha256: str | None = None
    native_directory: str | None = None

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the original DOA5 US/EU PSN PS3 profile.')
    return FORMAT


def context(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except OSError as error:
        raise SaveError('Keep the original US/EU DOA5 PSN PARAM.SFO beside this copied native file.') from error
    directory = savedata_directory(raw)
    if directory not in DIRECTORIES:
        raise SaveError('PARAM.SFO does not identify the original supported US/EU PSN DOA5 save.')
    return hashlib.sha256(raw).hexdigest(), directory


def _path(path):
    path = safe_path(path)
    if path.suffix.lower() != EXTENSION:
        raise SaveError('Open a separate PS3-decrypted SAVE_SYS.DAT copy; keep its original PARAM.SFO.')
    return path


def decode(raw, game_id=GAME_ID, source=Path('SAVE_SYS.DAT')):
    get_format(game_id)
    return Document(FORMAT, Path(source), raw, codec.decode(raw))


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _path(path)
    stamp, directory = context(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    payload = codec.decode(raw)
    if context(path) != (stamp, directory):
        raise SaveError('The original PS3 metadata changed while opening the copy.')
    return Document(FORMAT, path, raw, payload, stamp, directory)


@lru_cache(maxsize=4)
def _validated_payload(raw):
    return codec.decode(raw)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or (document.context_sha256 is None) != (document.native_directory is None)
            or (document.native_directory is not None and document.native_directory not in DIRECTORIES)
            or (document.context_sha256 is not None and (
                type(document.context_sha256) is not str or len(document.context_sha256) != 64
                or any(c not in '0123456789abcdef' for c in document.context_sha256)))):
        raise SaveError('A frozen original DOA5 PS3 native snapshot is required.')
    if _validated_payload(document.raw) != document.payload:
        raise SaveError('The immutable DOA5 PS3 decoded snapshot changed.')


def fields_for(document):
    validate_document(document)
    # Higher/nonbinary originals do not authorize an unlock transition.
    return tuple(field for field in FIELDS if field.value(document.payload) in (0, 1))


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('DOA5 costume edits must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('This DOA5 flag is not qualified for editing.')
        field = mapping[key]
        original = field.value(document.payload)
        if type(value) is int and value == original:
            continue
        field.validate(value)
        if original != 0 or value != 1:
            raise SaveError('Only an originally locked costume flag can change from 0 to 1.')
        output[field.offset] = 1
    # Checksums stored in the decoded header describe encrypted block bytes.
    # Return the exact sealed decoded snapshot required by the scalar contract.
    return codec.decode(codec.encode(bytes(output)))


def serialize(document, changes):
    payload = changed_payload(document, changes)
    return document.raw if payload == document.payload else codec.encode(payload)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('This DOA5 costume flag is read only.')
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
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('This DOA5 costume flag is read only.')
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
    source = _path(document.source)
    if document.context_sha256 is None or context(source) != (document.context_sha256, document.native_directory):
        raise SaveError('The original PS3 metadata changed or was not qualified; reopen the copied file.')
    with source.open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The original DOA5 native copy changed; reopen it before saving.')
    return source


def backup(document):
    source = _validate_source(document)
    snapshot = snapshot_backup(document.raw, source, GAME_ID, source.parent / 'UniversalEditorBackups')
    metadata = {'game_id': GAME_ID, 'kind': 'doa5-ps3-export-context',
                'context_sha256': document.context_sha256}
    try:
        atomic_new(json.dumps(metadata).encode('utf-8'), snapshot.with_name(snapshot.name + '.context.json'))
    except Exception:
        snapshot.unlink(missing_ok=True)
        snapshot.with_suffix('.json').unlink(missing_ok=True)
        raise
    return snapshot


def save_as(document, changes, destination):
    source = _validate_source(document)
    destination = _path(destination)
    expected = (document.context_sha256, document.native_directory)
    if context(destination) != expected:
        raise SaveError('Keep the same unchanged original PARAM.SFO beside the destination.')
    if source == destination or destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    result = serialize(document, changes)
    backup(document)
    _validate_source(document)
    if context(destination) != expected:
        raise SaveError('The destination PS3 metadata changed before writing.')
    atomic_new(result, destination)
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination, backup_path = _path(destination), safe_path(backup_path)
    stamp = context(destination)
    try:
        with safe_path(backup_path.with_name(backup_path.name + '.context.json')).open('rb') as stream:
            raw_metadata = stream.read(1025)
        if len(raw_metadata) > 1024:
            raise SaveError('DOA5 backup context metadata is too large.')
        metadata = json.loads(raw_metadata)
    except (OSError, ValueError, UnicodeError) as error:
        raise SaveError('DOA5 backup context metadata is missing or damaged.') from error
    if (type(metadata) is not dict or metadata.get('game_id') != GAME_ID
            or metadata.get('kind') != 'doa5-ps3-export-context'
            or metadata.get('context_sha256') != stamp[0]):
        raise SaveError('Restore requires the same original PARAM.SFO as the backup.')
    def validate_restored(raw):
        codec.decode(raw)
        if context(destination) != stamp:
            raise SaveError('The destination PS3 metadata changed before restoring.')
    return restore_snapshot(backup_path, destination, GAME_ID, EXTENSION, SAVE_SIZE,
                            validate_raw=validate_restored)


def prepare_self_test_copy(document, destination):
    """Generate title identity alone; never copy player/console signing fields."""
    validate_document(document)
    companion = safe_path(Path(destination).parent / 'PARAM.SFO')
    if companion.exists():
        context(destination)
        return
    key = b'SAVEDATA_DIRECTORY\0'
    value = (document.native_directory or DIRECTORIES[0]).encode('ascii') + b'\0'
    data_start = (36 + len(key) + 3) & ~3
    raw = (struct.pack('<5I', 0x46535000, 0x101, 36, data_start, 1)
           + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0)
           + key + bytes(data_start - 36 - len(key)) + value)
    savedata_directory(raw)
    atomic_new(raw, companion)


def record_label(slot, group='Costume unlocks'):
    return f'Costume flag record {slot:02d}' if slot else group


def field_hint(document, key):
    field = field_map(document)[key if isinstance(key, str) else key.id]
    original = field.value(document.payload)
    return (('Set this locked original costume flag to 1.' if original == 0 else 'This costume flag is already unlocked.')
            + ' Character/costume names are not mapped. Native integrity is maintained; '
            'original character ownership, paid DLC, titles and story states are preserved. '
            'Reimport and resign with a PS3 save manager. Max is disabled.')


def costume_rows(document):
    validate_document(document)
    return tuple((record_label(field.slot), field.label, hex(field.offset),
                  'Locked' if field.value(document.payload) == 0 else
                  'Unlocked' if field.value(document.payload) == 1 else 'Unusual — preserved',
                  field.value(document.payload)) for field in FIELDS)

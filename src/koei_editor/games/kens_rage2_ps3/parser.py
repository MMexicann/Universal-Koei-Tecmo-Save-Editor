"""Independent source-backed PS3 adapter. See docs/LICENSED_MUSOU.md.

Published Apollo patch facts are reimplemented; no GPL source or player data is
included. Actual public PS3 exports were decrypted privately for qualification.
"""
from dataclasses import dataclass
from collections.abc import Mapping
import hashlib
from pathlib import Path
import zlib
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str = 'Collections'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'
    experimental_maximum: None = None

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')

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
    sample_verified: bool = False


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    native_directory: str | None = None

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

GAME_ID = 'kens_rage2_ps3'
TITLE_IDS = ('BLES01801',)
SAVE_SIZE = 0xC0000
# Exact native structure observed independently in two public EU gameplay saves.
STRUCTURE = ((0, 0), (4, 2), (8, 0x54C4), (0x10, 0x548C),
             (0x14, 2), (0x18, 0), (0x1C, 0),
             (0x20, 0), (0x24, 2), (0x28, 0x488),
             (0x4B8, 0), (0x4BC, 1), (0x4C0, 0x11D8),
             (0x16A0, 0), (0x16A4, 0), (0x16A8, 0x934),
             (0x16B0, 0x8F4), (0x16B4, 0),
             (0x1FEC, 0), (0x1FF0, 0), (0x1FF4, 0xD0),
             (0x20CC, 0), (0x20D0, 0), (0x20D4, 0x3408))
# Half-open coverage; sub-sections must be sealed before their global parent.
CRC_REGIONS = ((0x2C, 0x30, 0x4B8), (0x4C4, 0x4C8, 0x16A0),
               (0x16AC, 0x16B8, 0x1FEC), (0x1FF8, 0x1FFC, 0x20CC),
               (0x20D8, 0x20DC, 0x54E4), (0xC, 0x20, 0x54E4))
CHECKSUM_OFFSETS = tuple(row[0] for row in CRC_REGIONS)
# Published Apollo gallery ranges, independently qualified against EU samples.
GALLERY_RANGES = (('Music gallery', 0x212, 54), ('Movies', 0x24E, 7),
                  ('Event gallery 1', 0x28B, 62),
                  ('Event gallery 2', 0x2EE, 15),
                  ('Event gallery 3', 0x2FE, 133))
FIELDS = tuple(Field(f'gallery_{offset + index:04x}',
                     'Unlock collection entry', offset + index, 1, 1, group,
                     index + 1, minimum=0)
               for group, offset, count in GALLERY_RANGES for index in range(count))
FORMAT = Format(GAME_ID, "Ken's Rage 2 (PS3, EU decrypted gameplay export)",
                SAVE_SIZE, FIELDS,
                'Open copied decrypted BLES01801 DATA.BIN beside its PARAM.SFO. Set a locked gallery '
                'entry from 0 to 1 to unlock it. Existing nonzero statuses remain '
                'unchanged. Apollo reimport and resign are required for console use.')


def qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE
            or any(int.from_bytes(raw[o:o + 4], 'big') != value
                   for o, value in STRUCTURE)):
        raise SaveError("Requires the qualified EU PS3 Ken's Rage 2 decrypted "
                        'DATA.BIN layout (version 2, 0xC0000 bytes). Encrypted, '
                        'foreign layouts and other revisions are rejected; region requires PARAM.SFO.')
    for offset, start, end in CRC_REGIONS:
        if int.from_bytes(raw[offset:offset + 4], 'big') != zlib.crc32(raw[start:end]):
            raise SaveError("Ken's Rage 2 native section CRC32 failed.")


def seal(payload):
    output = bytearray(payload)
    for offset, start, end in CRC_REGIONS:
        output[offset:offset + 4] = zlib.crc32(output[start:end]).to_bytes(4, 'big')
    return bytes(output)


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select this exact PS3 decrypted-export adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.bin')):
    get_format(game_id)
    qualify(raw)
    directory = validate_context(source) if (Path(source).parent / 'PARAM.SFO').exists() else None
    return Document(FORMAT, Path(source), raw, raw, directory)


def valid_directory(directory):
    return type(directory) is str and any(
        directory.startswith(title + '-') and len(directory) == len(title) + 3
        and directory[-2:].isascii() and directory[-2:].isdigit() for title in TITLE_IDS)


def validate_context(path):
    # Gameplay bytes have layout/version markers, but no title or region string.
    # Require bounded identity-only parsing of the original companion metadata.
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            directory = savedata_directory(stream.read(MAX_SFO_SIZE + 1))
    except FileNotFoundError as error:
        raise SaveError('Keep copied decrypted DATA.BIN and edited copies beside '
                        'the original BLES01801 PARAM.SFO identity companion.') from error
    if not valid_directory(directory):
        raise SaveError('PARAM.SFO is not a qualified EU Ken\'s Rage 2 save.')
    return directory


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate decrypted PS3 .bin export copy.')
    directory = validate_context(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    qualify(raw)
    if validate_context(path) != directory:
        raise SaveError('The PS3 metadata identity changed while opening the copy.')
    return Document(FORMAT, path, raw, raw, directory)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload
            or (document.native_directory is not None and not valid_directory(document.native_directory))):
        raise SaveError('A frozen decrypted PS3 snapshot is required.')
    qualify(document.raw)


def fields_for(document):
    validate_document(document)
    # Unlock controls are selected only from genuinely locked native entries.
    # Nonzero states (including observed 2 and unknown higher states) are immutable.
    return tuple(field for field in FORMAT.fields if field.value(document.payload) == 0)



def field_map(document):
    return {field.id: field for field in fields_for(document)}


def changed_payload(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Pending collection changes must be a field/value mapping.')
    fields = field_map(document)
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('This field is not qualified for the opened PS3 profile.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        if value != 1:
            raise SaveError('Only a locked collection entry can be unlocked (0 to 1).')
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return seal(bytes(result))


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = seal(payload)
    decode(raw, GAME_ID, document.source)
    return raw


def stage(document, changes, key, value):
    changed_payload(document, changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('This field is not qualified for the opened PS3 profile.')
    result = dict(changes)
    if type(value) is int and value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        fields[key].validate(value)
        if value != 1:
            raise SaveError('Only a locked collection entry can be unlocked (0 to 1).')
        result[key] = value
    return result


def limit_values(document, changes, keys):
    fields = field_map(document)
    changed_payload(document, changes)
    for key in keys:
        if type(key) is not str or key not in fields:
            raise SaveError('This field is not qualified for the opened PS3 profile.')
    # Published cheat targets are manual editing bounds, not natural gameplay
    # caps. No automatic Max action is authorized by this source evidence.
    return {}


def maximums(document, changes, group=None):
    limit_values(document, changes, [f.id for f in fields_for(document)
                                   if group is None or f.group == group])
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    if validate_context(document.source) != document.native_directory:
        raise SaveError('The original PS3 metadata identity changed.')
    return snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new decrypted .bin copy destination.')
    if (validate_context(document.source) != document.native_directory
            or validate_context(destination) != document.native_directory):
        raise SaveError('Source and destination need the same original PARAM.SFO save identity.')
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    if (validate_context(document.source) != document.native_directory
            or validate_context(destination) != document.native_directory):
        raise SaveError('Source or destination PARAM.SFO identity changed before writing.')
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination = safe_path(destination)
    directory = validate_context(destination)
    def validate_restore(raw):
        decode(raw, GAME_ID, destination)
        if validate_context(destination) != directory:
            raise SaveError('The restore destination identity changed.')

    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                            validate_raw=validate_restore)


def prepare_self_test_copy(document, destination):
    """Generate only the validated title/slot identity for a new self-test copy.

    Owner fields and other original metadata are never copied to reports/backups.
    This companion identifies the extracted gameplay file; it does not sign it.
    """
    validate_document(document)
    directory = validate_context(document.source)
    if directory != document.native_directory:
        raise SaveError('The original PS3 metadata identity changed.')
    key = b'SAVEDATA_DIRECTORY\0'
    value = directory.encode('ascii') + b'\0'
    identity = (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
                + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0)
                + key + value)
    destination = safe_path(destination)
    atomic_new(identity, destination.parent / 'PARAM.SFO')
    validate_context(destination)


def record_label(slot, group='Collections'):
    return f'{group} entry {slot}' if slot else group


def field_hint(document, field_id):
    validate_document(document)
    if field_id not in field_map(document):
        raise SaveError('This collection entry is already unlocked or unqualified.')
    return ('Set 1 to unlock this existing locked collection entry. Nonzero native '
            'statuses remain unchanged; relocking, story flags and bulk Max are '
            'unavailable. Export decrypted DATA.BIN with Apollo, then reimport '
            'and resign the edited file for the console.')


INTEGRITY_KIND = 'checksum'


def inspection_rows(document):
    validate_document(document)
    return tuple({'group': group, 'label': f'Entry {index + 1}',
                  'value': f'Native collection status {document.payload[offset + index]}'
                           + (' (unlock available)' if document.payload[offset + index] == 0
                              else ' (preserved; read only)')}
                 for group, offset, count in GALLERY_RANGES for index in range(count))

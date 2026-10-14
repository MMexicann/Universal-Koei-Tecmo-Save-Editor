"""Independent source-backed PS3 adapter. See docs/LICENSED_MUSOU.md.

Published Apollo patch facts are reimplemented; no GPL source or player data is
included. Actual public PS3 exports were decrypted privately for qualification.
"""
from dataclasses import dataclass
from collections.abc import Mapping
import hashlib
from pathlib import Path
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
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
    group: str = 'Resources'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
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

GAME_ID = 'kens_rage1_ps3'
TITLE_IDS = ('BLUS30504', 'BLES01062')
SAVE_SIZE = 0xC0000
# Uninterpreted layout identifiers shared by genuine US/EU gameplay files.
# This is a qualified header profile, not a claimed release version/checksum.
HEADER = bytes.fromhex('000000000000000000001b8d000000000000000000000001000000f100000000')
FIGHTERS = ('Kenshiro', 'Toki', 'Raoh', 'Rei', 'Shin', 'Thouzer', 'Jagi', 'Mamiya')
FIELDS = tuple(Field(f'fighter_{i}_skill_points', f'{name}: Skill points',
                     0x12F + i * 0x240, 2, 9999, 'Fighters', i + 1)
               for i, name in enumerate(FIGHTERS))
FORMAT = Format(GAME_ID, "Ken's Rage (PS3, US/EU decrypted gameplay export)",
                SAVE_SIZE, FIELDS,
                'Open copied decrypted DATA.BIN beside its original US/EU PARAM.SFO. '
                'Edit unspent fighter skill points manually, then reimport and '
                'resign with Apollo. Only positive existing balances are writable. '
                'Natural limits and DLC identities are unproved; '
                'automatic Max is unavailable.')


def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:32] != HEADER:
        raise SaveError("Requires the qualified PS3 Ken's Rage US/EU decrypted "
                        'DATA.BIN layout of 0xC0000 bytes. Encrypted, foreign '
                        'layouts and different header profiles are rejected; '
                        'title/region additionally requires PARAM.SFO.')


def seal(payload):
    # Apollo specifies direct writes without a gameplay checksum update.
    # No gameplay integrity algorithm has been independently qualified here.
    # PS3 encryption and PFD authentication remain external responsibilities.
    return payload


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select this exact PS3 decrypted-export adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.bin')):
    get_format(game_id)
    qualify(raw)
    directory = validate_context(source) if (Path(source).parent / 'PARAM.SFO').exists() else None
    return Document(FORMAT, Path(source), raw, raw, directory)


def validate_context(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            directory = savedata_directory(stream.read(MAX_SFO_SIZE + 1))
    except FileNotFoundError as error:
        raise SaveError('Keep decrypted DATA.BIN and edited copies beside the '
                        'original BLUS30504-00 or BLES01062-00 PARAM.SFO companion.') from error
    if directory not in ('BLUS30504-00', 'BLES01062-00'):
        raise SaveError('PARAM.SFO is not a qualified US/EU Ken\'s Rage save.')
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
            or (document.native_directory is not None
                and (type(document.native_directory) is not str
                     or document.native_directory not in ('BLUS30504-00', 'BLES01062-00')))):
        raise SaveError('A frozen decrypted PS3 snapshot is required.')
    qualify(document.raw)


def fields_for(document):
    validate_document(document)
    # The published u16 patch touches only the low half of a candidate word.
    # Anomalous high bytes remain read-only rather than editing a partial value.
    # A positive existing balance qualifies a populated record conservatively.
    # Zero balances stay read-only until a separate ownership map is proved.
    return tuple(field for field in FIELDS
                 if document.payload[field.offset - 2:field.offset] == bytes(2)
                 and field.value(document.payload) > 0)


def field_map(document):
    return {field.id: field for field in fields_for(document)}


def changed_payload(document, changes):
    fields = field_map(document)
    if not isinstance(changes, Mapping):
        raise SaveError('Staged changes must be a field-value mapping.')
    result = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('This field is not qualified for the opened PS3 profile.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        result[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(result)


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


def record_label(slot, group='Fighters'):
    return FIGHTERS[slot - 1] if 1 <= slot <= len(FIGHTERS) else group


def field_hint(document, field):
    validate_document(document)
    return ('Unspent persistent skill points buy upgrades on the Meridian Chart. '
            'This resource edit preserves learned nodes, equipped skills, battle '
            'gauges and story flags. 9999 is a published editing target, not a '
            'proved natural cap; higher originals are preserved and Max is disabled. '
            'Apollo reimport/resign is required. Gameplay integrity and edited '
            'game loading have not been independently proved.')


INTEGRITY_KIND = 'external'


def inspection_rows(document):
    validate_document(document)
    rows = []
    for index, name in enumerate(FIGHTERS):
        offset = 0x12D + index * 0x240
        value = int.from_bytes(document.payload[offset:offset + 4], 'big')
        note = (' (read only: nonzero high bytes)' if value > 0xFFFF
                else ' (read only: no positive existing balance)' if value == 0 else '')
        rows.append({'group': 'Fighter inspection', 'label': name,
                     'value': f'Full skill-point candidate word: {value}{note}'})
    return tuple(rows)


def prepare_self_test_copy(document, destination):
    """Write only title/slot identity; never copy player/account metadata."""
    validate_document(document)
    directory = validate_context(document.source)
    if directory != document.native_directory:
        raise SaveError('The original PS3 metadata identity changed.')
    key = b'SAVEDATA_DIRECTORY' + bytes(1)
    value = directory.encode('ascii') + bytes(1)
    identity = (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
                + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0)
                + key + value)
    destination = safe_path(destination)
    atomic_new(identity, destination.parent / 'PARAM.SFO')
    validate_context(destination)

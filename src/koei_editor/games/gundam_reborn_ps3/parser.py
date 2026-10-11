"""Independent native Reborn PS3 resource writer; console signing is external.

Published individually named patch facts and three original console exports
qualify the exact revision. The overlapping broad pilot/plan/material cheats
are deliberately excluded; see docs/GUNDAM_REBORN_PS3_FORMAT.md.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'gundam_reborn_ps3'
TITLE_IDS = ('NPEB02060', 'NPJB00533')
SAVE_SIZE = 0xFD400
CONTENT_END = 0x5F948
CHECKSUM_OFFSETS = (0xC,)
INTEGRITY_KIND = 'checksum'
PILOTS = (('amuro', 'Amuro Ray', 0x23FBC), ('kamille', 'Kamille Bidan', 0x240DC))


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
    evidence: str = 'Individual published PS3 save maps; three native exports'

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


FORMAT = Format(GAME_ID, 'Dynasty Warriors: Gundam Reborn (PS3, EU/Japan)',
                SAVE_SIZE, (),
                'Edit a decrypted DATA.BIN copy beside its original PARAM.SFO. '
                'Reduce spendable money and existing pilot Team Points; Pilot EXP, '
                'levels, learned skills, plan upgrades, lifetime money and story progress '
                'stay intact. Reimport and resign the edited copy with Apollo for console use.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    native_directory: str | None

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def valid_directory(directory):
    return type(directory) is str and any(
        directory.startswith(title + '-') and len(directory) == len(title) + 3
        and directory[-2:].isascii() and directory[-2:].isdigit() for title in TITLE_IDS)


def context(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            directory = savedata_directory(stream.read(MAX_SFO_SIZE + 1))
    except FileNotFoundError as error:
        raise SaveError('Keep the original PARAM.SFO beside the decrypted DATA.BIN copy.') from error
    if not valid_directory(directory):
        raise SaveError('PARAM.SFO is not a supported EU/Japan Gundam Reborn save identity.')
    return directory


def qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE
            or raw[:12] != bytes.fromhex('00000000000000020005f938')):
        raise SaveError('Requires the 0xFD400-byte decrypted Gundam Reborn PS3 revision-2 '
                        'DATA.BIN layout. Encrypted files, other revisions and other games are rejected.')
    if int.from_bytes(raw[12:16], 'big') != sum(raw[16:CONTENT_END]):
        raise SaveError('Gundam Reborn native ADD integrity failed; damaged input is never repaired.')


def seal(payload):
    result = bytearray(payload)
    result[12:16] = sum(result[16:CONTENT_END]).to_bytes(4, 'big')
    return bytes(result)


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select this exact Gundam Reborn PS3 adapter.')
    return FORMAT


def decode(raw, game_id=GAME_ID, source=Path('copy.bin')):
    get_format(game_id)
    qualify(raw)
    directory = context(source) if (Path(source).parent / 'PARAM.SFO').exists() else None
    return Document(FORMAT, Path(source), raw, raw, directory)


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate decrypted DATA.BIN/.bin copy.')
    directory = context(path)
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    qualify(raw)
    if context(path) != directory:
        raise SaveError('The original PARAM.SFO identity changed while opening the copy.')
    return Document(FORMAT, path, raw, raw, directory)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload
            or (document.native_directory is not None and not valid_directory(document.native_directory))):
        raise SaveError('A frozen qualified Gundam Reborn PS3 document is required.')
    qualify(document.raw)


def fields_for(document):
    validate_document(document)
    money = int.from_bytes(document.payload[0x5AD44:0x5AD48], 'big')
    fields = [Field('money', 'Spendable money (reduce only)', 0x5AD44, 4, money)]
    for slot, (key, name, offset) in enumerate(PILOTS, 1):
        level = document.payload[offset]
        experience = int.from_bytes(document.payload[offset + 2:offset + 6], 'big')
        points = int.from_bytes(document.payload[offset + 26:offset + 30], 'big')
        # Only individually mapped, progressed records with ordinary level byte
        # are eligible. Source's all-pilots stride crosses other structures.
        if level <= 49 and experience > 0 and points > 0:
            fields.append(Field(f'{key}_team_points', f'{name}: Team Points (reduce only)',
                                offset + 26, 4, points, 'Pilot Team Points', slot))
    return tuple(fields)


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
    qualify(payload)
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
    if context(document.source) != document.native_directory:
        raise SaveError('The original PARAM.SFO save identity changed.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen before saving.')


def backup(document):
    validate_source(document)
    result = snapshot_backup(document.raw, document.source, GAME_ID,
                             document.source.parent / 'UniversalEditorBackups')
    try:
        atomic_new(identity_metadata(document.native_directory), result.with_suffix('.sfo'))
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
    if context(destination) != document.native_directory:
        raise SaveError('Destination needs the same original PARAM.SFO save identity.')
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    raw = serialize(document, changes)
    backup(document)
    validate_source(document)
    if context(destination) != document.native_directory:
        raise SaveError('The destination PARAM.SFO identity changed before writing.')
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    companion = safe_path(Path(backup_path).with_suffix('.sfo'))
    try:
        with companion.open('rb') as stream:
            directory = savedata_directory(stream.read(MAX_SFO_SIZE + 1))
    except FileNotFoundError as error:
        raise SaveError('This backup lacks its identity-only companion.') from error
    if not valid_directory(directory) or context(destination) != directory:
        raise SaveError('Restore needs the same original PARAM.SFO save identity as the backup.')
    def validate_restore(raw):
        qualify(raw)
        if context(destination) != directory:
            raise SaveError('The restore destination identity changed.')
    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                            validate_raw=validate_restore)


def prepare_self_test_copy(document, destination):
    validate_source(document)
    companion = safe_path(Path(destination).parent / 'PARAM.SFO')
    if companion.exists():
        if context(destination) != document.native_directory:
            raise SaveError('The destination belongs to another save identity.')
    else:
        atomic_new(identity_metadata(document.native_directory), companion)


def record_label(slot, group='Resources'):
    return PILOTS[slot - 1][1] if slot else group


def field_hint(document, field_id):
    field = field_map(document)[field_id]
    return ('Reduce this existing spendable pool between zero and its opened value. '
            'Assigning its original value removes a staged edit. Learned skills, Pilot EXP, '
            'levels, lifetime earnings and mission rewards remain unchanged. Max is disabled. '
            'Reimport and resign with Apollo after editing.')


def inspection_rows(document):
    validate_document(document)
    result = [{'group': 'Money history', 'label': 'Lifetime earned money',
               'value': str(int.from_bytes(document.payload[0x57F90:0x57F94], 'big'))}]
    for key, name, offset in PILOTS:
        result.append({'group': 'Pilots', 'label': name,
                       'value': f'Level: {document.payload[offset] + 1}; '
                                f'Pilot EXP: {int.from_bytes(document.payload[offset + 2:offset + 6], "big")}; '
                                f'Team Points: {int.from_bytes(document.payload[offset + 26:offset + 30], "big")}; '
                                f'Raw stat words: {[int.from_bytes(document.payload[offset + i:offset + i + 2], "big") for i in (6, 8, 10)]}'})
    for index in range(10):
        offset = 0x5A544 + index * 2
        result.append({'group': 'Material storage', 'label': f'Published material-region word {index + 1}',
                       'value': f'{int.from_bytes(document.payload[offset:offset + 2], "big")} (read only)'})
    return tuple(result)

"""Independent G1 PS3 skill-bit editor; console authentication stays external.

Apollo's US/EU patch facts and four genuine exports qualify this layout. The
published seven-byte all-skills patch is deliberately not reproduced: only the
36 observed learned bits can be added, with all other bits preserved.
"""
from dataclasses import dataclass
import hashlib
import struct
from collections.abc import Mapping
from pathlib import Path

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup, restore_snapshot
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'gundam1_ps3'
TITLE_IDS = ('BLUS30058', 'BLES00147')
SAVE_SIZE = 0x89000
REVISION = bytes.fromhex('00002711')
SKILL_COUNT = 36
CHECKSUM_RANGES = ((0x08, 0x20, 0x2000), (0x0C, 0x1DD1, 0x88DD0),
                   (0x10, 0x20, SAVE_SIZE))
CHECKSUM_OFFSETS = tuple(row[0] for row in CHECKSUM_RANGES)
INTEGRITY_KIND = 'checksum'
# Named pilot records are individually published; no stride is extrapolated.
PILOTS = (('amuro', 'Amuro Ray', 0x188), ('kamille', 'Kamille Bidan', 0x49C),
          ('judau', 'Judau Ashta', 0x93A), ('domon', 'Domon Kasshu', 0xAC4),
          ('heero', 'Heero Yuy', 0xDD8), ('loran', 'Loran Cehack', 0x10EC))


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    bit: int
    slot: int
    skill_id: int
    size: int = 1
    minimum: int = 0
    maximum: int = 1
    group: str = 'Learned skills'
    maxable: bool = False
    kind: str = 'int'

    def value(self, payload):
        return int(bool(payload[self.offset] & (1 << self.bit)))

    def validate(self, value):
        if type(value) is not int or value not in (0, 1):
            raise SaveError('Learned skills use 0 (not learned) or 1 (learned).')


@dataclass(frozen=True)
class EquippedField:
    id: str
    label: str
    offset: int
    slot: int
    size: int = 1
    minimum: int = 0
    maximum: int = SKILL_COUNT - 1
    group: str = 'Equipped skills'
    maxable: bool = False
    kind: str = 'int'
    encoding: str = 'unsigned byte; native learned skill reference'
    evidence: str = 'Four US/EU native copies; CONSOLE_PIRATE_STRATEGY_DEPTH.md'

    def value(self, payload):
        return payload[self.offset]

    def validate(self, value):
        if type(value) is not int or not 0 <= value < SKILL_COUNT:
            raise SaveError('Choose an already learned native skill ID from 0 to 35.')


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    size: int
    fields: tuple
    note: str
    sample_verified: bool = True


FIELDS = tuple(Field(f'{key}_skill_{skill}', f'{name}: native skill ID {skill}',
                     offset + 29 + skill // 8, skill % 8, slot, skill)
               for slot, (key, name, offset) in enumerate(PILOTS, 1)
               for skill in range(SKILL_COUNT))
FORMAT = Format(GAME_ID, 'Dynasty Warriors: Gundam (PS3, US/EU decrypted export)',
                SAVE_SIZE, FIELDS,
                'Learn skills on six qualified existing level-30 pilots. Open a decrypted DATA.BIN '
                'copy with its original PARAM.SFO companion. Output also needs the matching '
                'PARAM.SFO. Reimport and resign with Apollo; this is a decrypted gameplay '
                'writer. Equip already learned skills in four qualified slots; inherent skills, '
                'EXP, levels and mission progress are preserved.')


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
        directory.startswith(title + '-') and len(directory) == len(title) + 3
        and directory[-2:].isascii() and directory[-2:].isdigit() for title in TITLE_IDS)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
            directory = savedata_directory(raw)
    except FileNotFoundError as error:
        raise SaveError('Keep the original PARAM.SFO beside this decrypted DATA.BIN copy '
                        'to qualify its US/EU PS3 title identity.') from error
    if not valid_directory(directory):
        raise SaveError('PARAM.SFO is not a qualified US/EU Dynasty Warriors: Gundam save.')
    return raw


def context(path):
    return savedata_directory(context_raw(path))


def context_digest(path):
    return hashlib.sha256(context_raw(path)).hexdigest()


def qualify(raw):
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != REVISION
            or raw[0x14:0x1C] != bytes.fromhex('0000002000001dd2')):
        raise SaveError('Requires the qualified 0x89000-byte decrypted PS3 Gundam '
                        'DATA.BIN layout 0x00002711. Other games/editions and encrypted files are rejected.')
    for offset, start, end in CHECKSUM_RANGES:
        if int.from_bytes(raw[offset:offset + 4], 'big') != sum(raw[start:end]):
            raise SaveError(f'Gundam gameplay ADD integrity at 0x{offset:02X} failed; '
                            'damaged input is never repaired automatically.')


def seal(payload):
    result = bytearray(payload)
    for offset, start, end in CHECKSUM_RANGES:
        result[offset:offset + 4] = sum(result[start:end]).to_bytes(4, 'big')
    return bytes(result)


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select this exact Gundam PS3 adapter.')
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
        raise SaveError('Open a separate decrypted DATA.BIN/.bin copy.')
    original_context = context_raw(path)
    directory = savedata_directory(original_context)
    digest = hashlib.sha256(original_context).hexdigest()
    with path.open('rb') as stream:
        raw = stream.read(SAVE_SIZE + 1)
    qualify(raw)
    if context_digest(path) != digest:
        raise SaveError('The original PARAM.SFO changed while opening the copy.')
    return Document(FORMAT, path, raw, raw, directory, digest)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path)
            or type(document.context_digest) is not str
            or (document.native_directory is not None and (len(document.context_digest) != 64
                or any(c not in "0123456789abcdef" for c in document.context_digest)))
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload
            or (document.native_directory is not None and not valid_directory(document.native_directory))):
        raise SaveError('A frozen qualified Gundam PS3 document is required.')
    qualify(document.raw)


def qualified_pilots(document):
    validate_document(document)
    result = []
    for slot, (_, _, offset) in enumerate(PILOTS, 1):
        refs = document.payload[offset + 23:offset + 29]
        flags = document.payload[offset + 29:offset + 34]
        # A named record must be at level 30 with learned equipped/inherent skills.
        # Unusual or unowned records remain untouched, without guessing IDs.
        if (document.payload[offset + 16] == 29 and any(flags)
                and all(skill < SKILL_COUNT and flags[skill // 8] & (1 << (skill % 8))
                        for skill in refs)):
            result.append(slot)
    return tuple(result)


def fields_for(document):
    slots = qualified_pilots(document)
    fields = [field for field in FIELDS if field.slot in slots]
    for slot in slots:
        key, name, offset = PILOTS[slot - 1]
        # Six distinct references distinguish four selected slots from the two
        # inherent skills. Ambiguous/duplicate original layouts stay untouched.
        if len(set(document.payload[offset + 23:offset + 29])) != 6:
            continue
        fields.extend(EquippedField(f'{key}_equipped_{index}',
                                    f'{name}: Equipped skill {index + 1}',
                                    offset + 23 + index, slot)
                      for index in range(4))
    return tuple(fields)


def field_map(document):
    return {field.id: field for field in fields_for(document)}


def validated_changes(document, changes):
    if not isinstance(changes, Mapping):
        raise SaveError('Staged skills must be a mapping.')
    fields = field_map(document)
    for key, value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('This skill is not qualified for the opened pilot record.')
        field = fields[key]
        field.validate(value)
        if isinstance(field, EquippedField):
            if value not in dict(field_options(document, key)):
                raise SaveError('Only originally learned, non-inherent skills can be equipped.')
        elif value < field.value(document.payload):
            raise SaveError('Skills can only be learned. Removing learned skills could '
                            'invalidate equipment or other prerequisites.')
    for slot in {field.slot for field in fields.values() if isinstance(field, EquippedField)}:
        selected = [changes.get(field.id, field.value(document.payload))
                    for field in fields.values()
                    if isinstance(field, EquippedField) and field.slot == slot]
        if len(set(selected)) != 4:
            raise SaveError('Each equipped skill must be distinct; use the selector to swap occupied slots.')
    return fields


def changed_payload(document, changes):
    fields = validated_changes(document, changes)
    result = bytearray(document.payload)
    for key, value in changes.items():
        field = fields[key]
        if isinstance(field, EquippedField):
            result[field.offset] = value
        elif value:
            result[field.offset] |= 1 << field.bit
    payload = bytes(result)
    return seal(payload) if payload != document.payload else payload


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = seal(payload)
    qualify(raw)
    # Requalify every existing-record dependency after the surgical bit writes.
    reopened = Document(FORMAT, document.source, raw, raw, document.native_directory, document.context_digest)
    validated_changes(reopened, {})
    return raw


def stage(document, changes, key, value):
    fields = validated_changes(document, changes)
    if type(key) is not str or key not in fields:
        raise SaveError('This skill is not qualified for the opened pilot record.')
    fields[key].validate(value)
    result = dict(changes)
    field = fields[key]
    if isinstance(field, EquippedField):
        # Selecting a skill already in another slot atomically swaps the
        # two slots. Review/Undo sees the complete dependency-safe edit.
        previous = changes.get(key, field.value(document.payload))
        for other in fields.values():
            if (isinstance(other, EquippedField) and other.slot == field.slot
                    and other.id != key
                    and changes.get(other.id, other.value(document.payload)) == value):
                if previous == other.value(document.payload):
                    result.pop(other.id, None)
                else:
                    result[other.id] = previous
    if value == fields[key].value(document.payload):
        result.pop(key, None)
    else:
        result[key] = value
    validated_changes(document, result)
    return result


def _equipped_options(document, field):
    offset = PILOTS[field.slot - 1][2]
    flags = document.payload[offset + 29:offset + 34]
    inherent = document.payload[offset + 27:offset + 29]
    return tuple((skill, f'Learned skill ID {skill}') for skill in range(SKILL_COUNT)
                 if skill not in inherent and flags[skill // 8] & (1 << (skill % 8)))


def limit_values(document, changes, keys):
    fields = validated_changes(document, changes)
    if any(type(key) is not str or key not in fields for key in keys):
        raise SaveError('Unknown or unqualified pilot skill.')
    return {}


def maximums(document, changes, group=None):
    validated_changes(document, changes)
    return dict(changes)


def review(document, changes):
    validated_changes(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def identity_metadata(directory):
    key = b'SAVEDATA_DIRECTORY\0'
    value = directory.encode('ascii') + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value)


def validate_source(document):
    validate_document(document)
    if (not document.context_digest or context(document.source) != document.native_directory
            or context_digest(document.source) != document.context_digest):
        raise SaveError('The original PARAM.SFO changed. Reopen the source copy.')
    with safe_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen before saving.')


def backup(document):
    validate_source(document)
    result = snapshot_backup(document.raw, document.source, GAME_ID,
                             document.source.parent / 'UniversalEditorBackups')
    sidecar_created = False
    try:
        atomic_new(identity_metadata(document.native_directory), result.with_suffix('.sfo'))
        sidecar_created = True
        validate_source(document)
    except Exception:
        result.unlink(missing_ok=True)
        result.with_suffix('.json').unlink(missing_ok=True)
        if sidecar_created:
            result.with_suffix('.sfo').unlink(missing_ok=True)
        raise
    return result


def save_as(document, changes, destination):
    validate_source(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new decrypted .bin copy destination.')
    if context(document.source) != document.native_directory or context(destination) != document.native_directory:
        raise SaveError('Source and destination need the same original PARAM.SFO save identity.')
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    destination_digest = context_digest(destination)
    raw = serialize(document, changes)
    backup(document)
    validate_source(document)
    if context_digest(destination) != destination_digest:
        raise SaveError('The destination PARAM.SFO changed before writing.')
    if context(document.source) != document.native_directory or context(destination) != document.native_directory:
        raise SaveError('Source or destination PARAM.SFO identity changed before writing.')
    atomic_new(raw, destination)
    reopened = read_save(destination)
    validate_source(document)
    if (reopened.raw != raw or reopened.context_digest != destination_digest
            or context_digest(destination) != destination_digest):
        raise SaveError('The written copy or destination PARAM.SFO changed during verification.')
    return reopened


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    identity = safe_path(Path(backup_path).with_suffix('.sfo'))
    try:
        with identity.open('rb') as stream:
            identity_raw = stream.read(MAX_SFO_SIZE + 1)
            directory = savedata_directory(identity_raw)
    except FileNotFoundError as error:
        raise SaveError('This Gundam backup lacks its identity-only companion.') from error
    if context(destination) != directory:
        raise SaveError('Restore needs the same original PARAM.SFO save identity as the backup.')
    destination_digest = context_digest(destination)
    validated_raw = None
    def recheck_context():
        if context_digest(destination) != destination_digest:
            raise SaveError('The restore destination PARAM.SFO changed.')
        with identity.open('rb') as stream:
            if stream.read(MAX_SFO_SIZE + 1) != identity_raw:
                raise SaveError('The backup identity companion changed during restore.')

    def validate_restore(raw):
        nonlocal validated_raw
        qualify(raw)
        recheck_context()
        validated_raw = raw

    result = restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE,
                              validate_raw=validate_restore)
    reopened = read_save(result)
    recheck_context()
    if reopened.raw != validated_raw:
        raise SaveError('The restored destination changed during verification.')
    return result


def record_label(slot, group='Learned skills'):
    return PILOTS[slot - 1][1] if slot else group


def field_options(document, field_id):
    field = field_map(document)[field_id]
    if isinstance(field, EquippedField):
        return _equipped_options(document, field)
    return ((1, 'Learned'),) if field.value(document.payload) else ((0, 'Not learned'), (1, 'Learned'))


def field_hint(document, field_id):
    field = field_map(document)[field_id]
    if isinstance(field, EquippedField):
        return ('Choose an originally learned skill ID. Selecting an already equipped '
                'skill swaps the two slots together. Undo reverses the whole swap; '
                'select both affected slots for Revert Selected. Inherent skills cannot be selected; '
                'duplicate references and unlearned skills are rejected. Learning a skill '
                'requires saving and reopening before it becomes an equipment choice. '
                'Max leaves equipment unchanged. Reimport and resign with Apollo.')
    return (f'Level-30 pilot persistent learned flag for native skill ID {field.skill_id}. Set 1 to learn; '
            '0 can undo a staged learning change when the original was unlearned. '
            'Already learned skills cannot be removed. Skill names/order are not inferred. '
            'Equipped references, EXP, levels and unknown bits remain unchanged. '
            'Reimport and resign this decrypted gameplay copy with Apollo.')


def inspection_rows(document):
    validate_document(document)
    rows = []
    qualified = qualified_pilots(document)
    for slot, (_, name, offset) in enumerate(PILOTS, 1):
        rows.append({'group': 'Pilots', 'label': name,
                     'value': f'Stored level: {document.payload[offset + 16] + 1}; '
                              f'pilot EXP/points: {int.from_bytes(document.payload[offset:offset + 4], "big")}; '
                              f'equipped skill IDs: {list(document.payload[offset + 23:offset + 27])}; '
                              f'skills editable: {slot in qualified}'})
    for name, offset in (('Gundam (Amuro)', 0x20), ('Gundam Mk-II (Kamille)', 0x370)):
        rows.append({'group': 'Mobile suits', 'label': name,
                     'value': f'Stored level: {document.payload[offset + 18] + 1}; '
                              f'mobile suit EXP/points: {int.from_bytes(document.payload[offset:offset + 4], "big")} '
                              '(read only; growth dependencies are not mapped)'})
    return tuple(rows)


def prepare_self_test_copy(document, destination):
    """Emit bounded title/slot identity only; never copy owner/signing metadata."""
    validate_source(document)
    companion = safe_path(Path(destination).parent / 'PARAM.SFO')
    if companion.exists():
        if context(destination) != document.native_directory:
            raise SaveError('The self-test destination belongs to another save identity.')
        return
    atomic_new(identity_metadata(document.native_directory), companion)
    validate_source(document)
    context(destination)

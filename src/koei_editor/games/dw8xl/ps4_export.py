"""DW8 XL PS4 common revision with a strictly zero extension.

No native gameplay checksum is claimed by this reader. Only
the published 0xD0F45-byte common-core profile is accepted; opaque nonzero PS4
extension data is refused instead of discarded.
"""
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl_vita.parser import PAYLOAD_SIZE, SIGNATURE, BASE_FIELDS, common_fields, record_label
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.experimental_limits import experimental_enabled
from koei_editor.shared.copy_storage import snapshot_backup, atomic_new, restore_snapshot
from koei_editor.shared.ps4_export import MAX_SFO_SIZE, title_id
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'dw8xl_ps4'
SAVE_SIZE = 0xD0F45
TITLE_ID = 'CUSA00397'
INTEGRITY_KIND = 'none'


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Dynasty Warriors 8 Xtreme Legends Complete Edition (PS4 CUSA00397)'
    size: int = SAVE_SIZE
    fields: tuple = BASE_FIELDS
    published_format: bool = True
    sample_verified: bool = False
    game_load_verified: bool = False
    note: str = ('Decrypted CUSA00397 APP.BIN, common revision 0x131002F0, zero extension only. '
                 'Resources, 82 officers’ stored stats, four weapon-action aptitudes and '
                 'existing ranked weapon attributes. Individual edits only. '
                 'No native checksum claimed; PS4 authentication/reimport remains external.')


FORMAT = Format()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Choose the exact DW8 XL CUSA00397 PS4 profile.')
    return FORMAT


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    context_digest: str = ''

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def decode(raw, game_id=GAME_ID, source=Path('APP.BIN')):
    get_format(game_id)
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:5] != SIGNATURE:
        raise SaveError('Requires the 855,877-byte decrypted PS4 DW8 XL revision 0x131002F0.')
    if any(raw[PAYLOAD_SIZE:]):
        raise SaveError('Nonzero PS4 extension data cannot be discarded or converted by this profile.')
    return Document(FORMAT, Path(source), raw, raw[:PAYLOAD_SIZE])


def context_raw(path):
    path = safe_path(Path(path).parent / 'sce_sys' / 'param.sfo')
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except OSError as error:
        raise SaveError('Keep original DW8 XL sce_sys/param.sfo beside the copied PS4 APP.BIN.') from error
    title_id(raw, TITLE_ID)
    return raw


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate decrypted PS4 .bin copy.')
    metadata = context_raw(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), game_id, path)
    if context_raw(path) != metadata:
        raise SaveError('PS4 metadata changed during opening.')
    return replace(document, context_digest=hashlib.sha256(metadata).hexdigest())


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or type(document.context_digest) is not str or not isinstance(document.source, Path)
            or (document.context_digest and (len(document.context_digest) != 64
                or any(c not in '0123456789abcdef' for c in document.context_digest)))
            or decode(document.raw).payload != document.payload):
        raise SaveError('A frozen native DW8 XL PS4 snapshot is required.')


def fields_for(document):
    validate_document(document)
    return common_fields(document.payload, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    pending = normalize_pending_values(document, changes, mapping)
    result = bytearray(document.payload)
    for key, value in pending.items():
        field = mapping[key]
        result[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
    return bytes(result)


def serialize(document, changes):
    payload = changed_payload(document, changes)
    if payload == document.payload:
        return document.raw
    raw = payload + document.raw[PAYLOAD_SIZE:]
    if decode(raw).payload != payload:
        raise SaveError('The edited PS4 copy failed common-core readback.')
    return raw


def stage(document, changes, key, value):
    mapping = field_map(document)
    pending = normalize_pending_values(document, changes, mapping)
    if type(key) is not str or key not in mapping:
        raise SaveError('Choose a mapped PS4 field.')
    return normalize_pending_values(document, dict(pending, **{key: value}), mapping)


def limit_values(document, changes, keys):
    mapping = field_map(document)
    normalize_pending_values(document, changes, mapping)
    if isinstance(keys, (str, bytes)):
        raise SaveError('Choose a sequence of mapped field IDs.')
    try:
        keys = tuple(keys)
    except TypeError as error:
        raise SaveError('Choose a sequence of mapped field IDs.') from error
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('Choose only mapped PS4 field IDs.')
    return {}  # Manual bounds do not establish natural gameplay maxima.


def maximums(document, changes, group=None):
    return normalize_pending_values(document, changes, field_map(document))


def review(document, changes):
    pending = normalize_pending_values(document, changes, field_map(document))
    return [(field, field.value(document.payload), pending[field.id])
            for field in fields_for(document) if field.id in pending]


def field_options(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Choose a mapped PS4 field.')
    return tuple((value, f'{value // 25} stars') for value in (25, 50, 75, 100)) if '_compatibility_' in key else ()


def field_hint(document, field):
    validate_document(document)
    return ('Manual common-core field; Max is disabled. Existing record identities, '
            'EXP, story and zero extension stay unchanged. Keep original PS4 metadata; '
            'reimport/resign with your save manager. Edited game loading remains unverified.')


def _check_source(document):
    validate_document(document)
    opened = read_save(document.source)
    if (not document.context_digest or opened.raw != document.raw
            or opened.context_digest != document.context_digest):
        raise SaveError('The PS4 source or original metadata changed. Reopen the copied save.')


def _backup_bytes(path, limit):
    try:
        with safe_path(path).open('rb') as stream:
            raw = stream.read(limit + 1)
    except OSError as error:
        raise SaveError('A required PS4 backup file is missing or unreadable.') from error
    if len(raw) > limit:
        raise SaveError('A PS4 backup file exceeds its bounded size.')
    return raw


def _context_manifest(raw):
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise SaveError('The PS4 backup context manifest is damaged.') from error
    if (type(manifest) is not dict or set(manifest) != {
            'game_id', 'kind', 'context_sha256', 'save_sha256'}
            or manifest.get('game_id') != GAME_ID
            or manifest.get('kind') != 'dw8xl-ps4-export-context'
            or any(type(manifest[key]) is not str or len(manifest[key]) != 64
                   or any(character not in '0123456789abcdef' for character in manifest[key])
                   for key in ('context_sha256', 'save_sha256'))):
        raise SaveError('The PS4 backup context manifest does not match this profile.')
    return manifest


def backup(document):
    _check_source(document)
    metadata = context_raw(document.source)
    path = snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')
    companion = path.with_name(path.name + '.param.sfo')
    context_path = path.with_name(path.name + '.context.json')
    context = {'game_id': GAME_ID, 'kind': 'dw8xl-ps4-export-context',
               'context_sha256': document.context_digest, 'save_sha256': document.sha256}
    context_data = json.dumps(context).encode('utf-8')
    # Keep completed files if any later creation or check fails. Another app
    # may have replaced a path, so failure cleanup must not delete its bytes.
    atomic_new(metadata, companion)
    atomic_new(context_data, context_path)
    _check_source(document)
    if _backup_bytes(path, SAVE_SIZE) != document.raw:
        raise SaveError('The newly created PS4 backup changed during verification.')
    try:
        manifest = json.loads(_backup_bytes(path.with_suffix('.json'), 4096))
    except (ValueError, UnicodeError) as error:
        raise SaveError('The newly created PS4 backup manifest changed.') from error
    if (type(manifest) is not dict or manifest.get('game_id') != GAME_ID
            or manifest.get('kind') != 'opaque-copy'
            or manifest.get('sha256') != document.sha256
            or manifest.get('size_bytes') != SAVE_SIZE):
        raise SaveError('The newly created PS4 backup manifest no longer matches its snapshot.')
    if (_backup_bytes(companion, MAX_SFO_SIZE) != metadata
            or _backup_bytes(context_path, 1024) != context_data):
        raise SaveError('The newly created PS4 backup metadata changed during verification.')
    _check_source(document)
    return path


def save_as(document, changes, destination):
    _check_source(document)
    destination = safe_path(destination)
    if destination.suffix.lower() != '.bin':
        raise SaveError('Choose a new decrypted PS4 .bin copy.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    metadata = context_raw(document.source)
    if context_raw(destination) != metadata:
        raise SaveError('Keep the same original sce_sys/param.sfo beside the destination.')
    raw = serialize(document, changes)
    backup(document)
    _check_source(document)
    if context_raw(destination) != metadata:
        raise SaveError('The destination PS4 metadata changed before writing.')
    atomic_new(raw, destination)
    reopened = read_save(destination)
    _check_source(document)
    if reopened.raw != raw or context_raw(destination) != metadata:
        raise SaveError('The saved PS4 copy or original metadata changed during actual readback.')
    return reopened


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    backup_path, destination = safe_path(backup_path), safe_path(destination)
    metadata = _backup_bytes(backup_path.with_name(backup_path.name + '.param.sfo'), MAX_SFO_SIZE)
    title_id(metadata, TITLE_ID)
    context = _context_manifest(_backup_bytes(
        backup_path.with_name(backup_path.name + '.context.json'), 1024))
    if (hashlib.sha256(metadata).hexdigest() != context['context_sha256']
            or context_raw(destination) != metadata):
        raise SaveError('Restore requires the same original PS4 metadata as the backup.')
    validated = []
    def qualify(raw):
        decode(raw, game_id)
        if hashlib.sha256(raw).hexdigest() != context['save_sha256']:
            raise SaveError('The PS4 backup context belongs to a different gameplay snapshot.')
        if context_raw(destination) != metadata:
            raise SaveError('The destination PS4 metadata changed before restore.')
        validated.append(raw)
    result = restore_snapshot(backup_path, destination, GAME_ID, '.bin', SAVE_SIZE, validate_raw=qualify)
    reopened = read_save(result)
    if (not validated or reopened.raw != validated[-1]
            or reopened.sha256 != context['save_sha256']
            or reopened.context_digest != context['context_sha256']
            or context_raw(result) != metadata):
        raise SaveError('The restored PS4 copy or metadata changed during actual readback.')
    return result


def prepare_self_test_copy(document, destination):
    _check_source(document)
    metadata = context_raw(document.source)
    companion = safe_path(Path(destination).parent / 'sce_sys' / 'param.sfo')
    if companion.exists():
        if context_raw(destination) != metadata:
            raise SaveError('The destination has different original PS4 metadata.')
    else:
        atomic_new(metadata, companion)
    _check_source(document)
    if context_raw(destination) != metadata:
        raise SaveError('The copied original PS4 metadata changed during readback.')

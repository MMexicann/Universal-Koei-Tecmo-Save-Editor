"""Read-only PS4 WO3 Ultimate source for narrowly mapped resource transfer.

The complete public PS4 reference qualifies this exact serialized-marker
profile, while public CUSA00588 facts independently corroborate resource
locations. Its original console metadata was not provided. File reads require
original US CUSA00588 context; no scalar PS4 writer or whole-save compatibility
is implied. See docs/WO3U_PS4_RESOURCE_TRANSFER.md.
"""
from dataclasses import dataclass
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, snapshot_backup
from koei_editor.shared.ps4_export import MAX_SFO_SIZE, title_id
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'wo3u_ps4'
TITLE_ID = 'CUSA00588'
SAVE_SIZE = 0x2119CA
REVISION = bytes.fromhex('f1180314')
INTEGRITY_KIND = 'none'
# Primary officers, stored officer snapshots, root object, existing weapons.
# They are serialized address fragments, not checksums or writable gameplay.
MARKER_TABLES = (
    (0xECE8, 0x2B0, 150, bytes.fromhex('1069f800')),
    (0x3CE94, 0x2B8, 145, bytes.fromhex('1069f800')),
    (0x28008, 4, 1, bytes.fromhex('706af800')),
    (0xC800C, 0x1C, 2320, bytes.fromhex('b06bf800')),
)


@dataclass(frozen=True)
class Resource:
    id: str
    label: str
    offset: int
    size: int = 4

    def validate(self, value):
        # Source-only storage qualification, not a gameplay cap or writable limit.
        if type(value) is not int or not 0 <= value <= (1 << (8 * self.size)) - 1:
            raise SaveError('The opened PS4 resource does not fit its native unsigned word.')

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')


MATERIAL_SPANS = ((0xE9A8, 16), (0xE9C8, 16), (0xE9E8, 16),
                  (0xEA08, 34), (0xEA3A, 34), (0xEA6C, 34), (0xEAA8, 145))
RESOURCES = (Resource('crystals', 'Rare crystals (current balance)', 0xD5DC, 2),) + tuple(
    Resource(f'orb_{index}', f'Weapon attribute orb {index + 1}', 0xE944 + index, 1)
    for index in range(58)) + tuple(
    Resource(f'material_{family}_{index}',
             f'Crafting material family {family + 1}, record {index + 1}', base + index, 1)
    for family, (base, count) in enumerate(MATERIAL_SPANS) for index in range(count))


# PS4 CUSA00588 published facts qualify these exact five u16 base-stat cells
# for 0x91 playable officers, stride0x2B0. The five internal records stay opaque.
STATS = tuple(Resource(f'officer_{index}_{key}', f'Officer {index + 1}: {label}',
                       0xECF2 + index * 0x2B0 + relative, 2)
              for index in range(145)
              for key, label, relative in (('health', 'Health', 0), ('musou', 'Musou', 2),
                                           ('attack', 'Attack', 4), ('defense', 'Defense', 6),
                                           ('speed', 'Speed', 8)))
SOURCE_FIELDS = RESOURCES + STATS



@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Warriors Orochi 3 Ultimate (PS4 CUSA00588 resource-transfer source)'
    size: int = SAVE_SIZE
    fields: tuple = SOURCE_FIELDS


FORMAT = Format()


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


@lru_cache(maxsize=4)
def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != REVISION:
        raise SaveError('Requires a complete decrypted PS4 WO3 Ultimate revision 0x140318F1 APP.BIN.')
    for base, stride, count, marker in MARKER_TABLES:
        if any(raw[base + index * stride:base + index * stride + 4] != marker
               for index in range(count)):
            raise SaveError('The exact PS4 WO3 Ultimate serialized-marker profile failed; '
                            'PC, PS3 and other PS4 profiles cannot be substituted.')


def decode(raw, game_id=GAME_ID, source=Path('APP.BIN')):
    if game_id != GAME_ID:
        raise SaveError('Choose the explicit WO3 Ultimate PS4 resource-transfer source.')
    if type(raw) is not bytes:
        raise SaveError('An immutable complete PS4 source snapshot is required.')
    qualify(raw)
    return Document(FORMAT, Path(source), raw, raw)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'sce_sys' / 'param.sfo')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except OSError as error:
        raise SaveError('Keep original CUSA00588 sce_sys/param.sfo beside the copied PS4 APP.BIN.') from error
    title_id(raw, TITLE_ID)
    return raw


def read_save(path, game_id=GAME_ID):
    path = safe_path(path)
    if path.suffix.lower() != '.bin':
        raise SaveError('Open a separate decrypted PS4 APP.BIN copy.')
    metadata = context_raw(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), game_id, path)
    if context_raw(path) != metadata:
        raise SaveError('The original PS4 metadata changed while opening the source.')
    return Document(FORMAT, path, document.raw, document.payload, hashlib.sha256(metadata).hexdigest())


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or not isinstance(document.source, Path)
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.payload != document.raw or type(document.context_digest) is not str
            or (document.context_digest and (len(document.context_digest) != 64
                or any(c not in '0123456789abcdef' for c in document.context_digest)))):
        raise SaveError('A frozen qualified PS4 WO3 Ultimate source is required.')
    qualify(document.raw)


def field_map(document):
    validate_document(document)
    return MappingProxyType({field.id: field for field in SOURCE_FIELDS})


def serialize(document, changes):
    validate_document(document)
    if type(changes) is not dict or changes:
        raise SaveError('PS4 WO3 Ultimate is a read-only resource-transfer source, not an editing destination.')
    return document.raw


def _check_source(document):
    validate_document(document)
    reopened = read_save(document.source)
    if (not document.context_digest or reopened.raw != document.raw
            or reopened.context_digest != document.context_digest):
        raise SaveError('The PS4 gameplay or original metadata changed. Reopen the copied source.')


def _backup_bytes(path, limit):
    try:
        with safe_path(path).open('rb') as stream:
            raw = stream.read(limit + 1)
    except OSError as error:
        raise SaveError('A required PS4 source backup file is missing or unreadable.') from error
    if len(raw) > limit:
        raise SaveError('A PS4 source backup file exceeds its bounded size.')
    return raw


def backup(document):
    _check_source(document)
    metadata = context_raw(document.source)
    path = snapshot_backup(document.raw, document.source, GAME_ID,
                           document.source.parent / 'UniversalEditorBackups')
    companion = path.with_name(path.name + '.param.sfo')
    receipt = path.with_name(path.name + '.context.json')
    context_data = json.dumps({'game_id': GAME_ID, 'kind': 'wo3u-ps4-source-context',
                               'context_sha256': document.context_digest,
                               'save_sha256': document.sha256}).encode('utf-8')
    # Keep completed files if another app replaces any path during validation.
    atomic_new(metadata, companion)
    atomic_new(context_data, receipt)
    _check_source(document)
    if _backup_bytes(path, SAVE_SIZE) != document.raw:
        raise SaveError('The created PS4 source backup changed during actual readback.')
    try:
        manifest = json.loads(_backup_bytes(path.with_suffix('.json'), 4096))
    except (ValueError, UnicodeError) as error:
        raise SaveError('The created PS4 source backup manifest changed.') from error
    if (type(manifest) is not dict or manifest.get('game_id') != GAME_ID
            or manifest.get('kind') != 'opaque-copy'
            or manifest.get('sha256') != document.sha256
            or manifest.get('size_bytes') != SAVE_SIZE):
        raise SaveError('The created PS4 source backup manifest does not match its snapshot.')
    if (_backup_bytes(companion, MAX_SFO_SIZE) != metadata
            or _backup_bytes(receipt, 1024) != context_data):
        raise SaveError('The created PS4 source backup context changed during actual readback.')
    _check_source(document)
    return path

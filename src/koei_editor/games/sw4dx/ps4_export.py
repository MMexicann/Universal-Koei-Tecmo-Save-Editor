"""Read-only original SW4 PS4 US source for a gold-only PC DX transfer.

A decrypted native US reference and its original CUSA00919 metadata qualify
this exact little-endian revision. Three checksums match the independently
established original SW4 sums; the final sum is at a different PS4 offset.
The large zero region is required unchanged: its checksum coverage cannot be
resolved from the available native reference. The opaque tail is preserved,
not claimed to be checksum protected. No PS4 writer or whole-save transfer is
provided.
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

GAME_ID = 'sw4_ps4'
TITLE_ID = 'CUSA00919'
SAVE_SIZE = 0xBB800
REVISION = bytes.fromhex('18210000')
INTEGRITY_KIND = 'checksum'
CHECKSUM_OFFSETS = (4, 0xA8, 0xC16, 0x80532)
ZERO_REGION = (0x85DE, 0x80532)
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xC1A, 0x44, 55


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


RESOURCES = (Resource('gold', 'Gold', 0x7842),)
SOURCE_FIELDS = RESOURCES



@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Samurai Warriors 4 (PS4 CUSA00919 gold-transfer source)'
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


def checksums(raw):
    """Known original SW4 section sums, valid for the required zero profile.

    The original checksum cells are excluded from the third aggregate. The
    observed PS4 final location is distinct from the original PS3 location.
    No nonzero extension profile is inferred from this zero-region reference.
    """
    data = bytearray(raw)
    for offset in CHECKSUM_OFFSETS:
        data[offset:offset + 4] = b'\0' * 4
    a, b, c, d, e, f = (sum(data[start:end]) for start, end in (
        (8, 0xA8), (0xAC, 0x8EC), (0xC1A, 0x78D6),
        (0x85DE, 0x58532), (0x78D6, 0x85DF), (8, 0x78D6)))
    first = ((c + a) * b + e) & 0x7FFFFFFF
    second = (a * (c + b + d)) & 0x7FFFFFFF
    third = f
    return first, second, third, (first + second + third) & 0x7FFFFFFF


@lru_cache(maxsize=4)
def qualify(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:4] != REVISION:
        raise SaveError('Requires original decrypted US PS4 SW4 app.dat revision '
                        '0x2118 of 0xBB800 bytes; PC, PS3, DX and SW4-II are excluded.')
    start, end = ZERO_REGION
    if any(raw[start:end]):
        raise SaveError('This SW4 PS4 source requires its qualified zero extension '
                        'region; nonzero variants need additional native evidence.')
    for offset, expected in zip(CHECKSUM_OFFSETS, checksums(raw)):
        if int.from_bytes(raw[offset:offset + 4], 'little') != expected:
            raise SaveError('Samurai Warriors 4 PS4 section checksum failed.')
    for index in range(OFFICER_COUNT):
        offset = OFFICER_BASE + index * OFFICER_STRIDE
        if int.from_bytes(raw[offset:offset + 4], 'little') != index:
            raise SaveError('Samurai Warriors 4 PS4 standard officer identities failed.')


def decode(raw, game_id=GAME_ID, source=Path('app.dat')):
    if game_id != GAME_ID:
        raise SaveError('Choose the explicit original SW4 PS4 gold-transfer source.')
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
        raise SaveError('Keep original CUSA00919 sce_sys/param.sfo beside the copied PS4 app.dat.') from error
    title_id(raw, TITLE_ID)
    return raw


def read_save(path, game_id=GAME_ID):
    path = safe_path(path)
    if path.suffix.lower() != '.dat':
        raise SaveError('Open a separate decrypted PS4 app.dat copy.')
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
        raise SaveError('A frozen qualified PS4 SW4 source is required.')
    qualify(document.raw)


def field_map(document):
    validate_document(document)
    return MappingProxyType({field.id: field for field in SOURCE_FIELDS})


def serialize(document, changes):
    validate_document(document)
    if type(changes) is not dict or changes:
        raise SaveError('PS4 SW4 is a read-only gold-transfer source, not an editing destination.')
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
    context_data = json.dumps({'game_id': GAME_ID, 'kind': 'sw4-ps4-source-context',
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

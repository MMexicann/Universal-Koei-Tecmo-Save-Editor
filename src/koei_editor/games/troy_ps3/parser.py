"""EU Troy PROFILE revision 38: guarded Kleos reductions and native inspection.

The independently acquired complete PS3 export and its separately included
RPCS3 plaintext agree byte for byte. The published own-title writer specifies
the Kleos location relative to the music/item lists and a complete trailing
CRC32. Only the acquired populated profile geometry is qualified here.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import struct
import zlib

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import normalize_pending_values
from koei_editor.shared.ps3_copy import PS3CopyStorage
from koei_editor.shared.ps3_export import MAX_SFO_SIZE, savedata_directory
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'troy_ps3'
SAVE_SIZE = 103435
TITLE_DIRECTORY = 'BLES01183-WLOT'
HEADER = bytes.fromhex('0000002600000002')
MUSIC_BASE, MUSIC_COUNT = 0x16E06, 53
KLEOS_OFFSET = 0x17200
MAX_QUALIFIED_KLEOS = 0x7FFFFFFF
ITEM_BASE, ITEM_COUNT = 0x17204, 99
CHECKSUM_OFFSETS = tuple(range(SAVE_SIZE - 4, SAVE_SIZE))
INTEGRITY_KIND = 'checksum'


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    size: int = 4
    minimum: int = 0
    group: str = 'Resources'
    slot: int = 0
    maxable: bool = False
    kind: str = 'int'
    encoding: str = 'nonnegative big-endian 32-bit word; higher-word signedness is unqualified'
    experimental_maximum: None = None
    evidence: str = 'Own-title chaoszage PROFILE writer; original EU PS3/RPCS3 native export'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    def validate(self, value):
        if type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label}: choose a whole number from 0 through '
                            f'the opened balance ({self.maximum:,}).')

    def encoded(self, value):
        self.validate(value)
        return value.to_bytes(self.size, 'big')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Warriors: Legends of Troy (original European PS3)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    note: str = ('Reduce existing Kleos in the qualified populated EU revision-38 PROFILE. '
                 'Keep the complete original PARAM.SFO beside the copy. '
                 'Inventory, collections and story are inspected without writes. '
                 'PFD reimport/signing remains external; in-game loading is untested.')
    sample_verified: bool = True
    published_format: bool = True
    game_load_verified: bool = False


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


def get_format(game_id=GAME_ID):
    if type(game_id) is not str or game_id != GAME_ID:
        raise SaveError('Choose the original European Warriors: Legends of Troy PS3 profile.')
    return FORMAT


def _word(raw, position):
    if not 0 <= position <= len(raw) - 4:
        raise SaveError('The native Troy profile table is truncated.')
    return struct.unpack_from('>I', raw, position)[0]


def _strings(raw, position, count, pattern):
    values = []
    for _ in range(count):
        length = _word(raw, position)
        position += 4
        # This profile stores a bounded count of UTF-16 code units including
        # the terminal NUL. Native data strings are inspected, never renamed.
        if not 2 <= length <= 128 or position + length * 2 > len(raw) - 4:
            raise SaveError('A Troy profile string has an invalid bounded length.')
        encoded = raw[position:position + length * 2]
        position += length * 2
        try:
            text = encoded.decode('utf-16-be')
        except UnicodeDecodeError as error:
            raise SaveError('A Troy profile string is not valid UTF-16.') from error
        if text[-1:] != '\0' or re.fullmatch(pattern, text[:-1]) is None:
            raise SaveError('A Troy profile table has an unqualified native identity.')
        values.append(text[:-1])
    if len(set(values)) != len(values):
        raise SaveError('The qualified Troy table must not contain duplicate identities.')
    return tuple(values), position


@lru_cache(maxsize=4)
def _layout(raw):
    if len(raw) != SAVE_SIZE or raw[:len(HEADER)] != HEADER:
        raise SaveError('Requires the qualified 103,435-byte EU revision-38 plaintext PROFILE. '
                        'Encrypted files, SCENARIO, SETTINGS and other layouts are different.')
    if zlib.crc32(raw[:-4]) != _word(raw, len(raw) - 4):
        raise SaveError('Warriors: Legends of Troy native PROFILE CRC32 does not match.')
    if _word(raw, MUSIC_BASE) != MUSIC_COUNT:
        raise SaveError('This Troy music-table geometry has not been qualified.')
    music, end = _strings(raw, MUSIC_BASE + 4, MUSIC_COUNT, r'Bgm[0-9]{3}')
    if _word(raw, end) != 42 or end + 4 + 42 + 18 != ITEM_BASE:
        raise SaveError('The Troy profile music/flag/resource boundary is not qualified.')
    if _word(raw, ITEM_BASE) != ITEM_COUNT:
        raise SaveError('This Troy named-item table has not been qualified.')
    items, end = _strings(raw, ITEM_BASE + 4, ITEM_COUNT, r'Items\.SkillItem\.[A-Za-z0-9_]+')
    if _word(raw, end) != ITEM_COUNT or end + 4 + ITEM_COUNT * 6 + 9 != len(raw):
        raise SaveError('The Troy item names and six-byte status table do not agree.')
    # Independently corroborate the author's relative write recipe. Its
    # parenthesized (-11) is decimal, not hexadecimal. Do not find an arbitrary
    # occurrence elsewhere or substitute another game's resource map.
    first = raw.find(bytes.fromhex('420067006d'))
    second = raw.find(bytes.fromhex('290049007400'), first)
    if first != MUSIC_BASE + 9 or second - 11 != KLEOS_OFFSET:
        raise SaveError('The published Troy Kleos anchor is ambiguous or unsupported.')
    return music, items, end + 4


def decode(raw, game_id=GAME_ID, source=Path('PROFILE')):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError('A complete frozen European Troy PROFILE copy is required.')
    _layout(raw)
    return Document(FORMAT, Path(source), raw, raw)


def context_raw(path):
    companion = safe_path(Path(path).parent / 'PARAM.SFO')
    try:
        with companion.open('rb') as stream:
            raw = stream.read(MAX_SFO_SIZE + 1)
    except FileNotFoundError as error:
        raise SaveError('Keep the original BLES01183-WLOT PARAM.SFO beside PROFILE.') from error
    if savedata_directory(raw) != TITLE_DIRECTORY:
        raise SaveError('Requires original European BLES01183-WLOT metadata.')
    return raw


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = safe_path(path)
    if path.suffix:
        raise SaveError('Open a separate decrypted extensionless PROFILE copy.')
    metadata = context_raw(path)
    with path.open('rb') as stream:
        document = decode(stream.read(SAVE_SIZE + 1), source=path)
    if context_raw(path) != metadata:
        raise SaveError('Original Troy metadata changed while opening the copied profile.')
    return replace(document, context_digest=hashlib.sha256(metadata).hexdigest())


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload or not isinstance(document.source, Path)
            or type(document.context_digest) is not str):
        raise SaveError('A frozen qualified European Troy PROFILE snapshot is required.')
    _layout(document.raw)


def fields_for(document):
    validate_document(document)
    balance = _word(document.raw, KLEOS_OFFSET)
    # The title patch establishes a positive wallet word, not the native
    # getter's signedness or sentinel behavior. Higher opaque words must not
    # become editable balances merely because they fit an unsigned integer.
    if balance > MAX_QUALIFIED_KLEOS:
        return ()
    return (Field('kleos', 'Kleos (reduce only)', KLEOS_OFFSET,
                  balance),)


def field_map(document):
    return {field.id: field for field in fields_for(document)}


def _changes(document, changes):
    mapping = field_map(document)
    return mapping, normalize_pending_values(document, changes, mapping)


def changed_payload(document, changes):
    mapping, pending = _changes(document, changes)
    if not pending:
        return document.raw
    output = bytearray(document.raw)
    for key, value in pending.items():
        field = mapping[key]
        output[field.offset:field.offset + field.size] = field.encoded(value)
    struct.pack_into('>I', output, len(output) - 4, zlib.crc32(output[:-4]))
    result = bytes(output)
    _layout(result)
    return result


def serialize(document, changes):
    return changed_payload(document, changes)


def stage(document, changes, key, value):
    mapping, pending = _changes(document, changes)
    if type(key) is not str or key not in mapping:
        raise SaveError('Choose a qualified Troy resource.')
    pending[key] = value
    return normalize_pending_values(document, pending, mapping)


def limit_values(document, changes, keys):
    mapping, _ = _changes(document, changes)
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('Choose qualified Troy resources.')
    return {}


def maximums(document, changes, group=None):
    return _changes(document, changes)[1]


def review(document, changes):
    mapping, pending = _changes(document, changes)
    return [(field, field.value(document.payload), pending[field.id])
            for field in mapping.values() if field.id in pending]


def record_label(slot, group='Resources'):
    return group


def field_hint(document, field):
    if (field.id if isinstance(field, Field) else field) not in field_map(document):
        raise SaveError('Choose a qualified Troy resource.')
    return ('Reduce the existing saved Kleos wallet. Purchased items, equipped items, '
            'stage scores, story completion and unlocks remain unchanged. '
            'The published cheat target is not treated as a natural maximum.')


def inspection_rows(document):
    validate_document(document)
    music, items, status = _layout(document.raw)
    balance = _word(document.raw, KLEOS_OFFSET)
    rows = [{'group': 'Resources', 'label': 'Stored Kleos word',
             'value': f'{balance:,}' + (' (read only; higher-word signedness/sentinels unqualified)'
                                      if balance > MAX_QUALIFIED_KLEOS else ' (opened wallet)')}]
    rows += [{'group': 'Music collection', 'label': identity,
             'value': 'Serialized music entry (read only)'} for identity in music]
    for index, identity in enumerate(items):
        position = status + index * 6
        rows.append({'group': 'Item records', 'label': identity.removeprefix('Items.SkillItem.'),
                     'value': f'Stored word: {_word(document.raw, position):,}; '
                              f'status bytes: {document.raw[position + 4:position + 6].hex().upper()} '
                              '(read only)'})
    return tuple(rows)


_storage = PS3CopyStorage(GAME_ID, SAVE_SIZE, validate_document, context_raw,
                          decode, read_save, serialize, extension='')
backup = _storage.backup
save_as = _storage.save_as
restore = _storage.restore
prepare_copy_context = _storage.prepare_copy_context
prepare_self_test_copy = _storage.prepare_self_test_copy

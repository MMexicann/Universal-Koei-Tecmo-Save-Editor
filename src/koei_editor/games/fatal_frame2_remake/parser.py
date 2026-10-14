"""Photo Point reductions with native checksums and byte-preserved JSON/photos.

Photo Points belong to SystemPlayerRecordData.shop_point_, shared between slots;
KT official manual 5200 and support article 56588368652953 explain the distinction
from gameplay items. Catalog/controlled-action evidence for item eligibility and
natural currency caps is unavailable, so those records remain inspection only.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.games.fatal_frame2_remake import codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'fatal_frame2_remake'
MAX_FILE_SIZE = codec.MAX_FILE_SIZE
INTEGRITY_KIND = 'checksum'
_TOKEN = re.compile(rb'"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null|[{}\[\]:,]')


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str = 'Shared Photo Points'
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'

    def value(self, payload):
        return int(payload[self.offset:self.offset + self.size])

    @property
    def experimental_maximum(self):
        # Keep the native signed balance inside the original JSON token span.
        return min(0x7FFFFFFF, 10 ** self.size - 1)

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError('Photo Points may only be reduced from 0 to the opened balance; Max is disabled.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Fatal Frame II: Crimson Butterfly REMAKE (Steam PC)'
    size: int = MAX_FILE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Observed Steam revision 0x24121300. System Photo Point reductions; '
                 'gameplay inventory and Camera Obscura records are inspection only. '
                 'Native header/body checksums and all photo bytes are preserved. '
                 'Actual edited game loading remains untested.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    header: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select Fatal Frame II: Crimson Butterfly REMAKE Steam PC.')
    return FORMAT


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON member.')
        result[key] = value
    return result


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('Nonfinite JSON.')
    return value


@lru_cache(maxsize=2)
def _json(body):
    # Native gameplay carries binary photo data after the terminator. Do not
    # interpret it as JSON padding or clear/rebuild it as upstream import does.
    end = body.find(b'\0', 16)
    if not 16 < end <= 2 * 1024 * 1024:
        raise SaveError('FF2 remake JSON terminator is missing or outside the reviewed processing bound.')
    encoded = body[16:end]
    try:
        value = json.loads(encoded.decode('utf-8'), object_pairs_hook=_pairs, parse_float=_finite_float,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON.')))
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise SaveError('FF2 remake JSON is malformed or ambiguous.') from error
    if type(value) is not dict:
        raise SaveError('FF2 remake JSON root must be an object.')
    return value, encoded


def _require(value, key, kind, length=None):
    item = value.get(key) if type(value) is dict else None
    if type(item) is not kind or (length is not None and len(item) != length):
        raise SaveError(f'FF2 remake title-specific schema is missing or malformed: {key}.')
    return item


def _qualify(header, body):
    root, _ = _json(body)
    if header[:8] == b'WLNSYS\0\0':
        system = _require(root, 'SystemData', dict)
        _require(system, 'is_ce_demo_', bool)
        if system['is_ce_demo_']:
            raise SaveError('FF2 remake demo system data is not qualified.')
        records = _require(root, 'SystemPlayerRecordData', dict)
        _require(records, 'shop_point_', int)
        for key, size in (('futago_doll_unlock_data_', 100), ('omamori_unlock_data_', 210),
                          ('reiseki_unlock_data_', 100), ('ghost_list_unlock_data_', 379)):
            _require(records, key, list, size)
        _require(_require(root, 'PHOTO_SYSTEM', dict), 'photo_info_array_', list, 144)
        _require(_require(root, 'PHOTO_GHOST_LIST', dict), 'photo_info_array_', list, 384)
        _require(_require(root, 'SystemUiData', dict), 'ghost_photo_array_', list, 379)
        return 'system'
    player = _require(root, 'PlayerData', dict)
    for key in ('costume_mio', 'costume_mayu', 'current_film_slot', 'unlock_amulet_slot_num'):
        _require(player, key, int)
    _require(player, 'amulet_slot', list, 4)
    _require(player, 'equipment_mayu', list, 26)
    camera = _require(player, 'camera_enhance_data', dict)
    for key in ('flag_L_', 'flag_R_', 'flag_release_L_', 'flag_release_R_'):
        _require(camera, key, int)
    items = _require(root, 'PossessionItemData', dict)
    for key, length in (('possession_items', 650), ('storage_items', 550)):
        for item in _require(items, key, list, length):
            record = _require(item, 'ItemObjectData', dict)
            for name in ('key', 'key_num', 'num', 'flag', 'entry_number', 'equipment_slot', 'amulet_level'):
                _require(record, name, int)
    _require(_require(root, 'PHOTO_SLOT', dict), 'photo_info_array_', list)
    for key in ('MissionData', 'WorldData', 'PlayRecordData', 'TempRecordData', 'UIData'):
        _require(root, key, dict)
    return 'gameplay'


def decode(raw, game_id=GAME_ID, source=Path('ff2-copy.bin')):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError('An immutable native FF2 remake byte snapshot is required.')
    try:
        header, body = codec.decode(raw)
    except (ValueError, OverflowError) as error:
        raise SaveError(str(error)) from error
    _qualify(header, body)
    return Document(FORMAT, Path(source), raw, body, header)


def _copy_path(path):
    path = safe_path(path)
    if path.suffix.casefold() != '.bin':
        raise SaveError('Use a separate native Steam SAVEDATA.BIN copy.')
    return path


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    with path.open('rb') as stream:
        return decode(stream.read(MAX_FILE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or any(type(getattr(document, name)) is not bytes for name in ('raw', 'payload', 'header'))):
        raise SaveError('A frozen native FF2 remake snapshot is required.')
    original = decode(document.raw, GAME_ID, document.source)
    if original.payload != document.payload or original.header != document.header:
        raise SaveError('The FF2 remake snapshot changed outside the staged edit workflow.')


def _point_span(encoded):
    """Locate one qualified integer by parsed object path, never global regex."""
    tokens = list(_TOKEN.finditer(encoded))
    if len(tokens) > 500000:
        raise SaveError('FF2 remake JSON exceeds the token processing bound.')
    cursor = 0
    found = []

    def parse(path=(), depth=0):
        nonlocal cursor
        if depth > 64 or cursor >= len(tokens):
            raise SaveError('FF2 remake JSON nesting exceeds the processing bound.')
        token = tokens[cursor]; cursor += 1
        text = token.group()
        if text == b'{':
            if tokens[cursor].group() == b'}':
                cursor += 1; return
            while True:
                key = json.loads(tokens[cursor].group().decode('utf-8')); cursor += 2
                parse(path + (key,), depth + 1)
                delimiter = tokens[cursor].group(); cursor += 1
                if delimiter == b'}': break
        elif text == b'[':
            if tokens[cursor].group() == b']':
                cursor += 1; return
            index = 0
            while True:
                parse(path + (index,), depth + 1); index += 1
                delimiter = tokens[cursor].group(); cursor += 1
                if delimiter == b']': break
        elif path == ('SystemPlayerRecordData', 'shop_point_'):
            if re.fullmatch(rb'(?:0|[1-9][0-9]*)', text) is None:
                raise SaveError('FF2 remake Photo Point balance is not a nonnegative decimal integer token.')
            found.append((token.start() + 16, len(text)))

    try:
        parse()
    except (IndexError, RecursionError, ValueError) as error:
        raise SaveError('Unable to resolve the unambiguous Photo Point token.') from error
    if len(found) != 1 or cursor != len(tokens):
        raise SaveError('FF2 remake Photo Point token is missing or ambiguous.')
    return found[0]


@lru_cache(maxsize=2)
def _fields(body, system):
    if not system:
        return ()
    root, encoded = _json(body)
    points = root['SystemPlayerRecordData']['shop_point_']
    if points < 0 or points > 0x7fffffff:
        return ()  # Preserve unusual originals without normalization or writes.
    offset, width = _point_span(encoded)
    return (Field('photo_points', 'Photo Points: Reduce shared balance', offset, width, points),)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload, document.header[:8] == b'WLNSYS\0\0')


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('FF2 remake changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only a qualified system Photo Point reduction is writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        # Space is valid JSON whitespace. Reserve the original exact token width
        # so no unknown token, byte offset, terminator or photograph ever moves.
        output[field.offset:field.offset + field.size] = str(value).encode('ascii').rjust(field.size, b' ')
    result = bytes(output)
    _qualify(document.header, result)
    return result


def serialize(document, changes):
    body = changed_payload(document, changes)
    if body == document.payload:
        return document.raw
    raw = codec.encode(document.header, body)
    reopened = decode(raw, GAME_ID, document.source)
    mutable = set(range(codec.DATA_CHECKSUM, codec.DATA_CHECKSUM + 32)) | set(range(codec.HEADER_CHECKSUM, codec.HEADER_CHECKSUM + 32))
    if (reopened.payload != body or any(a != b for i, (a, b) in enumerate(zip(document.header, reopened.header)) if i not in mutable)):
        raise SaveError('FF2 remake edited output failed native read-back preservation.')
    return raw


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('FF2 remake gameplay and unlock records are inspection only.')
    result = dict(changes)
    if type(value) is int and value == mapping[key].value(document.payload):
        result.pop(key, None)
    else:
        mapping[key].validate(value); result[key] = value
    return result


def limit_values(document, changes, keys):
    mapping = field_map(document)
    changed_payload(document, changes)
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('FF2 remake requested field is not writable.')
    return {}


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id]) for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    source = _copy_path(document.source)
    return snapshot_backup(document.raw, source, GAME_ID, source.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    validate_document(document)
    source, destination = _copy_path(document.source), _copy_path(destination)
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    with source.open('rb') as stream:
        if stream.read(MAX_FILE_SIZE + 1) != document.raw:
            raise SaveError('The opened FF2 remake copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    destination = _copy_path(destination)
    return restore_snapshot(backup_path, destination, GAME_ID, '.bin', MAX_FILE_SIZE,
                            validate_raw=lambda raw: decode(raw, game_id))


def field_hint(document, key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('FF2 remake requested field is not writable.')
    return ('Reduce the opened shared Photo Point balance. This system resource applies to all '
            'gameplay slots; per-slot exchanged items are separate. Natural cap and increases '
            'are unqualified. Max is disabled. Save after purchases in the game.')


def item_records(document):
    validate_document(document)
    root, _ = _json(document.payload)
    if document.header[:8] != b'WLNUSR\0\0':
        return ()
    rows = []
    for name, label in (('possession_items', 'Possession'), ('storage_items', 'Storage')):
        for index, wrapper in enumerate(root['PossessionItemData'][name]):
            item = wrapper['ItemObjectData']
            if item['key'] == 0 and item['num'] == 0:
                continue
            rows.append((label, index + 1, item['key'], item['key_num'], item['num'],
                         item['flag'], item['entry_number'], item['equipment_slot'], item['amulet_level']))
    return tuple(rows)


def inspection_rows(document):
    validate_document(document)
    root, _ = _json(document.payload)
    rows = [{'group': 'Native save', 'label': 'Save kind', 'value': 'Shared system' if document.header[:8] == b'WLNSYS\0\0' else 'Gameplay slot'},
            {'group': 'Native save', 'label': 'Header and body checksums', 'value': 'Both validated'},
            {'group': 'Native save', 'label': 'Edited game loading', 'value': 'Not tested'}]
    if document.header[:8] == b'WLNSYS\0\0':
        records = root['SystemPlayerRecordData']
        rows.append({'group': 'Shared Photo Points', 'label': 'Opened shared Photo Point balance', 'value': records['shop_point_']})
        for key in ('futago_doll_unlock_data_', 'omamori_unlock_data_', 'reiseki_unlock_data_', 'ghost_list_unlock_data_'):
            rows.append({'group': 'Collections', 'label': key + ' (read only)', 'value': f'{len(records[key])} serialized records'})
    else:
        for key, value in root['PlayerData']['camera_enhance_data'].items():
            rows.append({'group': 'Camera Obscura', 'label': key + ' (raw flags; read only)', 'value': value})
        for key in ('current_film_slot', 'unlock_amulet_slot_num'):
            rows.append({'group': 'Equipment', 'label': key + ' (read only)', 'value': root['PlayerData'][key]})
    return tuple(rows)

"""Original Atelier Sophie Steam tagged gameplay profile, independently mapped.

Thirty-one native slots from one freely shared player archive establish the mixed-endian framing and
occupied records. Public original-PC editing reports describe unencrypted saves
without a checksum; native loader and edited in-game qualification remain pending.
DX/encrypted/console/system formats are rejected, never repaired or transplanted.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import math
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_enabled, within_numeric_limits
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'atelier_sophie'
EXTENSION = ''
SAVE_SIZE = 768000
MAX_FILE_SIZE = SAVE_SIZE
INTEGRITY_KIND = 'none'
HEADER = bytes.fromhex('013379c9') + bytes(28)
RECORD_SIZE = 56
# All root spans agree across the 31 original-PC snapshots in the shared archive.
ROOTS = (
    ('PlayGo', 0xC), ('dlc', 0x20), ('event', 0x5A08), ('knowledge', 0x46F2),
    ('money', 0x1C), ('party', 0x22F7), ('fieldmap', 0x2D54B), ('friend', 0xA18),
    ('library', 0x469), ('item', 0x4CE33), ('time', 0x11), ('fieldmap_effect', 0xCA),
    ('event_check', 0x15), ('date', 0x1D), ('global', 0x63), ('mix_lv', 0x26),
    ('explore_equip', 0x14C), ('worldmap', 0x16A1), ('bonus', 0x282), ('system', 0x85),
    ('dlcbgm', 0x1F61), ('shop', 0xB166), ('quest', 0x2BA7), ('mix_recipe', 0x288B),
    ('achievement', 0x506E), ('grow', 0x459), ('RecipeIdea', 0x8B0), ('rumor', 0xC21),
    ('dollmake', 0xB6), ('event_management', 0x17A), ('Info', 0xC19),
)
POOLS = (
    ('basket', 'Basket', 'm_unitKago', 120, True),
    ('container', 'Container', 'm_unitContainer', 5000, True),
    ('basket_important', 'Important basket', 'm_unitKagoImportant', 100, False),
    ('important', 'Important container', 'm_unitContainerImportant', 100, False),
    ('material', 'Synthesis work buffer', 'm_unitMaterial', 200, False),
    ('temporary', 'Temporary container', 'm_unitTempContainer', 100, False),
)


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
    encoding: str = 'uint_be'

    def value(self, payload):
        if self.encoding == 'float32_be':
            return int(struct.unpack_from('>f', payload, self.offset)[0])
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'big')

    @property
    def experimental_maximum(self):
        return (1 << 24) if self.encoding == 'float32_be' else (1 << (8 * self.size)) - 1

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from {self.minimum:,} to {self.maximum:,}.')

    def encoded(self, value):
        self.validate(value)
        return struct.pack('>f', value) if self.encoding == 'float32_be' else value.to_bytes(self.size, 'big')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Atelier Sophie: The Alchemist of the Mysterious Book (original Steam PC)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Original Steam PC observed 768,000-byte tagged profile. Individual Cole, '
                 'Tess exchange tickets and existing basket/container whole-number quality edits. '
                 'Max disabled; item identities, properties, equipment, recipes and story preserved. '
                 'Public no-checksum format evidence; edited in-game validation pending. '
                 'Sophie DX, Sophie 2 and console exports are different formats.')


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def get_format(game_id=GAME_ID):
    if game_id != GAME_ID:
        raise SaveError('Select the original Atelier Sophie Steam PC profile.')
    return FORMAT


def _node(raw, name, start, end, expected_size=None):
    marker = name.encode('ascii') + b'\0'
    pos = raw.find(marker, start + 4, end)
    if pos < 4 or raw.find(marker, pos + len(marker), end) >= 0:
        raise SaveError(f'Missing or ambiguous original Sophie node: {name}.')
    span = int.from_bytes(raw[pos - 4:pos], 'little')
    if (span < len(marker) + 4 or pos - 4 < start or pos - 4 + span > end
            or expected_size is not None and span != expected_size):
        raise SaveError(f'Unsupported original Sophie framing for {name}.')
    return pos + len(marker), pos - 4 + span


@lru_cache(maxsize=4)
def _structure(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:32] != HEADER:
        raise SaveError('Requires the observed original Steam Sophie 768,000-byte GAMEDATA profile.')
    roots = {}
    cursor = 32
    for name, size in ROOTS:
        marker = name.encode('ascii') + b'\0'
        if (int.from_bytes(raw[cursor:cursor + 4], 'little') != size
                or raw[cursor + 4:cursor + 4 + len(marker)] != marker):
            raise SaveError(f'Original Sophie root layout mismatch at {name}; DX and foreign saves are excluded.')
        roots[name] = (cursor, cursor + size)
        cursor += size
    item_start, item_end = roots['item']
    item_version, _ = _node(raw, 'version', item_start, item_start + 32, 14)
    if raw[item_version:item_version + 2] != b'\0\2':
        raise SaveError('Original Sophie requires item revision 2.')
    pools = []
    for key, label, name, count, editable in POOLS:
        start, end = _node(raw, name, *roots['item'], 4 + len(name) + 1 + 4 + count * RECORD_SIZE)
        if int.from_bytes(raw[start:start + 4], 'big') != count * RECORD_SIZE:
            raise SaveError(f'Original Sophie {label} record extent is invalid.')
        pools.append((key, label, start + 4, count, editable))
    pstart, pend = roots['party']
    version, _ = _node(raw, 'version', pstart, pstart + 32, 14)
    if raw[version:version + 2] != b'\0\2' or int.from_bytes(raw[version + 2:version + 6], 'big') != 9:
        raise SaveError('Original Sophie requires party revision 2 with nine character records.')
    party = version + 6
    for identity in range(9):
        if (int.from_bytes(raw[party:party + 4], 'little') != 0x3D4 or raw[party + 4:party + 10] != b'Party\0'
                or int.from_bytes(raw[party + 10:party + 14], 'big') != identity):
            raise SaveError('Original Sophie party record identity/stride is invalid.')
        party += 0x3D4
    if raw[party + 4:party + 12] != b'm_squad\0' or party + 0x67 != pend:
        raise SaveError('Original Sophie party references are misplaced.')
    money_root, money_end = roots['money']
    money, _ = _node(raw, 'money', money_root + 10, money_end, 18)
    tickets, tend = _node(raw, 'numOfTickets', *roots['quest'], 25)
    if int.from_bytes(raw[tickets:tickets + 4], 'big') != 4 or tickets + 8 != tend:
        raise SaveError('Original Sophie ticket scalar length is invalid.')
    alchemy_level, lend = _node(raw, 'm_lv', *roots['mix_lv'], 13)
    if alchemy_level + 4 != lend:
        raise SaveError('Original Sophie alchemy level node is malformed.')
    alchemy, aend = _node(raw, 'm_exp', *roots['mix_lv'], 14)
    if alchemy + 4 != aend:
        raise SaveError('Original Sophie alchemy node is malformed.')
    return tuple(pools), money, tickets + 4, alchemy


def decode(raw, game_id=GAME_ID, source=Path('sophie-copy')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)):
        raise SaveError('A bounded original Sophie byte snapshot is required.')
    raw = bytes(raw)
    _structure(raw)
    return Document(FORMAT, Path(source), raw, raw)


def _copy_path(path):
    original = str(path).replace('\\', '/').casefold()
    resolved = safe_path(path)
    for value in (original, str(resolved).replace('\\', '/').casefold()):
        if '/koeitecmo/a17/' in value or value.endswith('/koeitecmo/a17'):
            raise SaveError('Use a separate copy outside the live original Sophie A17 save folder.')
    return resolved


def read_save(path, game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    if path.suffix != EXTENSION:
        raise SaveError('Open an extensionless original PC GAMEDATA copy, not SYSTEM.DAT or a DX .pcsave.')
    with path.open('rb') as stream:
        return decode(stream.read(SAVE_SIZE + 1), game_id, path)


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or document.raw != document.payload):
        raise SaveError('A frozen original Sophie Steam PC snapshot is required.')
    _structure(document.raw)


@lru_cache(maxsize=4)
def _records(payload):
    pools, _, _, _ = _structure(payload)
    rows = []
    for key, label, base, count, editable in pools:
        for slot in range(count):
            offset = base + slot * RECORD_SIZE
            instance, identity = struct.unpack_from('>HH', payload, offset)
            if identity == 0xFFFF or instance == 0xFFFF:
                continue
            quality = struct.unpack_from('>f', payload, offset + 4)[0]
            rows.append((key, label, slot + 1, offset, instance, identity, quality, editable))
    return tuple(rows)


@lru_cache(maxsize=4)
def _fields(payload, experimental=False):
    _, cole, tickets, _ = _structure(payload)
    # Deliberate edit limits, not verified natural game caps. Bulk Max is disabled.
    fields = [Field('cole', 'Cole', cole, 4, 999999),
              Field('tickets', 'Tess exchange tickets', tickets, 4, 9999)]
    for key, label, slot, offset, instance, identity, quality, editable in _records(payload):
        if editable and math.isfinite(quality) and quality.is_integer() and 0 <= quality <= (1 << 24 if experimental else 0xFFFFFF):
            fields.append(Field(f'{key}_{slot}_quality', f'Quality (item ID {identity}, instance {instance})',
                                offset + 4, 4, 999, label, slot, minimum=1, encoding='float32_be'))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Original Sophie changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only Cole, tickets and qualified occupied item quality are writable.')
        field = mapping[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        output[field.offset:field.offset + field.size] = field.encoded(value)
    return bytes(output)


def serialize(document, changes):
    result = changed_payload(document, changes)
    decode(result, GAME_ID, document.source)
    return result


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('The original Sophie field is unmapped or the item is not eligible.')
    result = dict(changes)
    if type(value) is int and value == mapping[key].value(document.payload):
        result.pop(key, None)
    else:
        mapping[key].validate(value)
        result[key] = value
    return result


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapping = field_map(document)
    if any(type(key) is not str or key not in mapping for key in keys):
        raise SaveError('An original Sophie Max selection contains an unmapped field.')
    return {}  # No natural currency or per-item synthesis cap has been qualified.


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def backup(document):
    validate_document(document)
    source = _copy_path(document.source)
    folder = _copy_path(source.parent / 'WarriorsEditorBackups')
    return snapshot_backup(document.raw, source, GAME_ID, folder)


def save_as(document, changes, destination):
    destination = _copy_path(destination)
    if destination.suffix != EXTENSION:
        raise SaveError('Choose a new extensionless GAMEDATA copy destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    with _copy_path(document.source).open('rb') as stream:
        if stream.read(SAVE_SIZE + 1) != document.raw:
            raise SaveError('The opened copy changed on disk. Reopen it before saving.')
    raw = serialize(document, changes)
    backup(document)
    atomic_new(raw, destination)
    return decode(raw, GAME_ID, destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(_copy_path(backup_path), _copy_path(destination), GAME_ID, EXTENSION,
                            SAVE_SIZE, validate_raw=lambda raw: decode(raw, game_id))


def item_records(document):
    validate_document(document)
    return _records(document.payload)


def field_hint(document, key):
    if type(key) is not str:
        raise SaveError('The original Sophie field is unmapped.')
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('The original Sophie field is unmapped.')
    if field.encoding == 'float32_be':
        return ('Existing item quality: whole-number edits 1–999. Effects, traits, identities and '
                'all other item bytes stay unchanged. Fractional/nonfinite qualities are inspection only. '
                'Max is disabled because attainable quality and equipment effects depend on each item.')
    return ('Individual resource edit. The shown maximum is an editor limit, not a verified natural cap. '
            'Max is disabled; ticket carry-over, quest rewards, friendship and progression stay unchanged.')


def progression_rows(document):
    validate_document(document)
    cursor = 32
    for name, size in ROOTS:
        if name == 'mix_lv':
            level, _ = _node(document.payload, 'm_lv', cursor, cursor + size, 13)
            _, _, _, alchemy = _structure(document.payload)
            return (('Alchemy level (read only)', int.from_bytes(document.payload[level:level + 4], 'big')),
                    ('Alchemy EXP (read only)', int.from_bytes(document.payload[alchemy:alchemy + 4], 'big')))
        cursor += size
    raise SaveError('Original Sophie alchemy progression layout is missing.')

"""Original Atelier Firis Steam tagged gameplay profile, independently mapped.

A public native clear-data slot establishes this complete mixed-endian profile.
A title-specific report describes successful direct container transplantation
with a hex editor. Independent edited game loading remains untested.
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

GAME_ID = 'atelier_firis_pc'
EXTENSION = ''
SAVE_SIZE = 1228800
MAX_FILE_SIZE = SAVE_SIZE
INTEGRITY_KIND = 'none'
HEADER = bytes.fromhex('0133a13d') + bytes(28)
RECORD_SIZE = 52
# Complete root spans in the independently shared original-PC native profile.
ROOTS = (
    ('PlayGo',12), ('dlc',58), ('event',26563), ('knowledge',18221), ('money',28),
    ('party',10236), ('fieldmap',124322), ('friend',207), ('library',12),
    ('item',223760), ('time',17), ('fieldmap_effect',186), ('event_check',21),
    ('date',25), ('global',95), ('mix_lv',38), ('explore_equip',1636), ('bonus',111),
    ('system',149), ('dlcbgm',8033), ('shop',129785), ('quest',206705),
    ('mix_recipe',4109), ('achievement',16), ('grow',9), ('RecipeIdea',2046),
    ('atelier_making',1335), ('change_env_gimmick',164), ('event_management',21),
    ('collectData',6960), ('payInfo',5392), ('costume',276), ('Info',3105),
)
POOLS = (
    ('basket','Basket','m_unitKago',100,True),
    ('container','Container','m_unitContainer',4000,True),
    ('basket_important','Important basket','m_unitKagoImportant',100,False),
    ('important','Important container','m_unitContainerImportant',100,False),
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
        return (1 << 24) if self.encoding == 'float32_be' else 0x7FFFFFFF

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
    title: str = 'Atelier Firis: The Alchemist and the Mysterious Journey (original Steam PC)'
    size: int = SAVE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Original Steam PC observed 1,228,800-byte tagged profile. Cole and existing '
                 'whole-number basket/container quality reductions only; Max disabled. '
                 'Public direct hex-edit/load testimony; independent edited game loading untested. '
                 'DX, console and different native revisions are excluded.')



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
        raise SaveError('Select the original Atelier Firis Steam PC profile.')
    return FORMAT


def _node(raw, name, start, end, expected_size=None):
    marker = name.encode('ascii') + b'\0'
    pos = raw.find(marker, start + 4, end)
    if pos < 4 or raw.find(marker, pos + len(marker), end) >= 0:
        raise SaveError(f'Missing or ambiguous original Firis node: {name}.')
    span = int.from_bytes(raw[pos - 4:pos], 'little')
    if (span < len(marker) + 4 or pos - 4 < start or pos - 4 + span > end
            or expected_size is not None and span != expected_size):
        raise SaveError(f'Unsupported original Firis framing for {name}.')
    return pos + len(marker), pos - 4 + span


@lru_cache(maxsize=4)
def _structure(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE or raw[:32] != HEADER:
        raise SaveError('Requires the observed original Steam Firis 1,228,800-byte GAMEDATA profile.')
    roots = {}
    cursor = 32
    for name, size in ROOTS:
        marker = name.encode('ascii') + b'\0'
        if (int.from_bytes(raw[cursor:cursor + 4], 'little') != size
                or raw[cursor + 4:cursor + 4 + len(marker)] != marker):
            raise SaveError(f'Original Firis root layout mismatch at {name}; DX and foreign saves are excluded.')
        roots[name] = (cursor, cursor + size)
        cursor += size
    item_start, item_end = roots['item']
    item_version, _ = _node(raw, 'version', item_start, item_start + 32, 14)
    if raw[item_version:item_version + 2] != b'\0\3':
        raise SaveError('Original Firis requires item revision 3.')
    pools = []
    for key, label, name, count, editable in POOLS:
        start, end = _node(raw, name, *roots['item'], 4 + len(name) + 1 + 4 + count * RECORD_SIZE)
        if int.from_bytes(raw[start:start + 4], 'big') != count * RECORD_SIZE:
            raise SaveError(f'Original Firis {label} record extent is invalid.')
        pools.append((key, label, start + 4, count, editable))
    pstart, pend = roots['party']
    version, _ = _node(raw, 'version', pstart, pstart + 32, 14)
    if raw[version:version + 2] != b'\0\3' or int.from_bytes(raw[version + 2:version + 6], 'big') != 12:
        raise SaveError('Original Firis requires Party revision 3 with twelve records.')
    party = version + 6
    identities = []
    for index in range(12):
        if int.from_bytes(raw[party:party + 4], 'little') != 840 or raw[party + 4:party + 10] != b'Party\0':
            raise SaveError('Original Firis Party stride/framing is invalid.')
        identities.append(int.from_bytes(raw[party + 10:party + 14], 'big'))
        party += 840
    if len(set(identities)) != 12 or 0xffffffff in identities:
        raise SaveError('Original Firis Party identities are missing or ambiguous.')
    if raw[party + 4:party + 12] != b'm_squad\0' or party + 128 != pend:
        raise SaveError('Original Firis party references are misplaced.')
    money_root, money_end = roots['money']
    money, _ = _node(raw, 'money', money_root + 10, money_end, 18)
    alchemy_level, lend = _node(raw, 'm_lv', *roots['mix_lv'], 13)
    if alchemy_level + 4 != lend:
        raise SaveError('Original Firis alchemy level node is malformed.')
    alchemy, aend = _node(raw, 'm_exp', *roots['mix_lv'], 14)
    if alchemy + 4 != aend:
        raise SaveError('Original Firis alchemy node is malformed.')
    return tuple(pools), money, alchemy


def decode(raw, game_id=GAME_ID, source=Path('firis-copy')):
    get_format(game_id)
    if not isinstance(raw, (bytes, bytearray)):
        raise SaveError('A bounded original Firis byte snapshot is required.')
    raw = bytes(raw)
    _structure(raw)
    return Document(FORMAT, Path(source), raw, raw)


def _copy_path(path):
    original = str(path).replace('\\', '/').casefold()
    resolved = safe_path(path)
    for value in (original, str(resolved).replace('\\', '/').casefold()):
        if any('/koeitecmo/' + name + '/' in value.rstrip('/') + '/'
               for name in ('a18','atelier firis','atelier firis dx')):
            raise SaveError('Use a separate copy outside the live original Firis A18 save folder.')
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
        raise SaveError('A frozen original Firis Steam PC snapshot is required.')
    _structure(document.raw)


@lru_cache(maxsize=4)
def _records(payload):
    pools, _, _ = _structure(payload)
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
    _, cole, _ = _structure(payload)
    balance = int.from_bytes(payload[cole:cole + 4], 'big', signed=True)
    fields = [Field('cole','Cole (reduce only)',cole,4,balance)] if balance >= 0 else []
    records = _records(payload)
    instances = {}
    for _key,_label,_slot,_offset,instance,_identity,_quality,_editable in records:
        instances[instance] = instances.get(instance,0) + 1
    for key,label,slot,offset,instance,identity,quality,editable in records:
        if (editable and instances[instance] == 1 and math.isfinite(quality)
                and quality.is_integer() and 1 <= quality <= (1 << 24 if experimental else 0xFFFFFF)):
            fields.append(Field(f'{key}_{slot}_quality',
                                f'Quality (item ID {identity}, instance {instance}; reduce only)',
                                offset + 4,4,int(quality),label,slot,minimum=1,encoding='float32_be'))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.payload, experimental_enabled())


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Original Firis changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only Cole and qualified existing quality reductions are writable.')
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
        raise SaveError('The original Firis field is unmapped or the item is not eligible.')
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
        raise SaveError('An original Firis Max selection contains an unmapped field.')
    return {}  # No natural currency or per-item synthesis cap has been qualified.


def maximums(document, changes, group=None):
    changed_payload(document, changes)
    return dict(changes)


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.payload), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def _validate_source(document):
    source = _copy_path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(SAVE_SIZE + 1)
    except OSError as error:
        raise SaveError('The opened copy is unavailable; reopen before saving or backing up.') from error
    if current != document.raw:
        raise SaveError('The opened copy changed on disk; reopen before saving or backing up.')
    return source


def backup(document):
    validate_document(document)
    source = _validate_source(document)
    folder = _copy_path(source.parent / 'WarriorsEditorBackups')
    return snapshot_backup(document.raw, source, GAME_ID, folder)


def save_as(document, changes, destination):
    destination = _copy_path(destination)
    if destination.suffix != EXTENSION:
        raise SaveError('Choose a new extensionless GAMEDATA copy destination.')
    if destination.exists():
        raise FileExistsError('Choose a new file; existing files are never replaced.')
    validate_document(document)
    _validate_source(document)
    raw = serialize(document, changes)
    backup(document)
    _validate_source(document)
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
        raise SaveError('The original Firis field is unmapped.')
    field = field_map(document).get(key)
    if field is None:
        raise SaveError('The original Firis field is unmapped.')
    if field.encoding == 'float32_be':
        return ('Reduce existing whole-number item quality, down to 1. The opened quality is the '
                'maximum. Fractional/nonfinite/duplicate-instance records are inspection only. '
                'Traits, effects, quantity, equipment references and item identity stay intact. Max is disabled.')
    return ('Reduce only the opened Cole balance. No currency cap or increase is inferred. '
            'Quest rewards, character growth, recipes, calendar and story stay intact. Max is disabled.')


def progression_rows(document):
    validate_document(document)
    cursor = 32
    for name, size in ROOTS:
        if name == 'mix_lv':
            level, _ = _node(document.payload, 'm_lv', cursor, cursor + size, 13)
            _, _, alchemy = _structure(document.payload)
            return (('Alchemy level (read only)', int.from_bytes(document.payload[level:level + 4], 'big')),
                    ('Alchemy EXP (read only)', int.from_bytes(document.payload[alchemy:alchemy + 4], 'big')))
        cursor += size
    raise SaveError('Original Firis alchemy progression layout is missing.')

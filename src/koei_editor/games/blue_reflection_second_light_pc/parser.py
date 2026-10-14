"""Second Light original Steam PC existing inventory quantity deductions.

Known native terminal Guide bytes remain opaque and byte-exact. Native XOR and
additive envelope checksums are mandatory. See BRSL_PC_FORMAT.md.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import experimental_enabled, within_numeric_limits
from koei_editor.games.sophie2 import atelier_sophie2_codec as codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'blue_reflection_second_light_pc'
MAX_FILE_SIZE = codec.MAX_FILE_SIZE
INTEGRITY_KIND = 'checksum'
# Exact complete-root geometries from the two independently shared PC slots.
ROOT_PROFILE = (
    ('info',29), ('PlayGo',12), ('dlc',158), ('event',68632), ('knowledge',11258),
    ('money',32), ('party',80799), ('fieldmap',44786), ('friend',295), ('library',20031),
    ('item',470961), ('time',17), ('fieldmap_effect',2178), ('event_check',21),
    ('date',29), ('global',91), ('mix_lv',38), ('explore_equip',3605), ('bonus',577),
    ('system',4443), ('dlcbgm',8033), ('shop',1272), ('mix_recipe',501),
    ('achievement',14578), ('quest',5689), ('collectData',10901), ('costume',2223),
    ('FieldMix',128), ('battlescore',362), ('lambRoast',988), ('Feeding',955),
    ('weaponskin',79), ('SchoolComm',165), ('SchoolDev',11252), ('charaCondition',240),
    ('LinkSketch',2852), ('mix_party',85), ('free_space',22609),
)
NG_PLUS_SIZES = {'knowledge':11534,'fieldmap':48936,'library':20663,'achievement':14594,
                 'collectData':11039,'free_space':22642}
ROOT_PROFILES = (ROOT_PROFILE,tuple((name,NG_PLUS_SIZES.get(name,size)) for name,size in ROOT_PROFILE))
PAYLOAD_SIZES = (790986,796231)
TAIL = bytes.fromhex('360000004775696465000e00000076657273696f6e0000001e000000697347756964696e675363656e6172696f0000000004')
POOLS = (('Container','m_unitContainer',5000),
         ('Important container','m_unitContainerImportant',300),
         ('Consumable container','m_unitContainerExpendable',50))
RECORD_SIZE = 88



@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    group: str = 'Container quantity'
    slot: int = 0
    size: int = 1
    minimum: int = 1
    maxable: bool = False
    kind: str = 'int'
    byteorder: str = 'little'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    @property
    def experimental_maximum(self):
        return (1 << (8 * self.size)) - 1

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label}: use a whole number from 1 to the opened count ({self.maximum}).')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'BLUE REFLECTION: Second Light (original Steam PC)'
    size: int = MAX_FILE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = 'Original Steam native checksum-protected profile; existing identified container count reductions only. Max disabled; edited game loading untested.'


FORMAT = Format()


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes
    header: bytes
    seed: int
    footer: bytes
    trailer: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


@dataclass(frozen=True)
class Node:
    name: bytes
    start: int
    body: int
    end: int


def get_format(game_id=GAME_ID):
    if type(game_id) is not str or game_id != GAME_ID:
        raise SaveError('Select the qualified Second Light original Steam PC profile.')
    return FORMAT


def _nodes(payload, start, end):
    result = []
    while start < end:
        if start + 5 > end:
            raise SaveError('Truncated Second Light tagged node.')
        size = struct.unpack_from('<I', payload, start)[0]
        stop = start + size
        zero = payload.find(b'\0', start + 4, min(stop, start + 85, end))
        if not start + 5 <= stop <= end or zero < 0:
            raise SaveError('Invalid Second Light tagged framing.')
        name = payload[start + 4:zero]
        if not name or any(value < 32 or value > 126 for value in name):
            raise SaveError('Invalid Second Light node name.')
        result.append(Node(name, start, zero + 1, stop))
        start = stop
    if len({n.name for n in result}) != len(result):
        raise SaveError('Duplicate Second Light tagged node.')
    return tuple(result)


def _unique(nodes, name):
    matches = [n for n in nodes if n.name == name.encode()]
    if len(matches) != 1:
        raise SaveError(f'Missing or ambiguous Second Light node: {name}.')
    return matches[0]


def _children(payload, node):
    return _nodes(payload, node.body, node.end)


def _body(payload, node):
    return payload[node.body:node.end]


@lru_cache(maxsize=2)
def _structure(payload):
    if len(payload) not in PAYLOAD_SIZES or payload[:32] != bytes.fromhex('013379c9') + bytes(28):
        raise SaveError('Unqualified Second Light native preamble/size.')
    if payload[-len(TAIL):] != TAIL:
        raise SaveError('Unqualified Second Light opaque terminal Guide profile.')
    roots = _nodes(payload,32,len(payload) - len(TAIL))
    profile = tuple((n.name.decode(),n.end - n.start) for n in roots)
    profile_index = PAYLOAD_SIZES.index(len(payload))
    if profile != ROOT_PROFILES[profile_index]:
        raise SaveError('Unqualified Second Light complete-root geometry.')
    app = _unique(_children(payload,_unique(roots,'info')),'app_ver')
    if _body(payload,app) != struct.pack('>II',1,profile_index):
        raise SaveError('Unqualified Second Light app/item revision combination.')
    item = _children(payload,_unique(roots,'item'))
    if tuple(n.name for n in item) != (b'version',b'm_unitContainer',b'm_unitContainerImportant',
                                     b'm_unitContainerExpendable',b'limitSize',b'ID',b'Jewel'):
        raise SaveError('Unqualified Second Light complete inventory framing.')
    if _body(payload,_unique(item,'version')) != struct.pack('>H',profile_index + 1):
        raise SaveError('Unqualified Second Light item revision.')
    if _body(payload,_unique(item,'limitSize')) != struct.pack('>I',5000):
        raise SaveError('Unqualified Second Light container limit.')
    regions = []
    for label,name,count in POOLS:
        node = _unique(item,name)
        if (node.end - node.body != 4 + count * RECORD_SIZE
                or struct.unpack_from('>I',payload,node.body)[0] != count * RECORD_SIZE):
            raise SaveError('Unqualified Second Light inventory extent.')
        regions.append((label,node.body + 4,count))
    party = _unique(roots,'party')
    version_end = party.body + 14
    version = _nodes(payload,party.body,version_end)
    if (len(version) != 1 or version[0].name != b'version'
            or _body(payload,version[0]) != struct.pack('>H',profile_index + 5)):
        raise SaveError('Unqualified Second Light Party revision.')
    if struct.unpack_from('>I',payload,version_end)[0] != 15:
        raise SaveError('Unqualified Second Light Party array count.')
    array_start = version_end + 4
    members = []
    for index in range(15):
        record = _nodes(payload,array_start + index * 5374,array_start + (index + 1) * 5374)
        if len(record) != 1 or record[0].name != b'Party':
            raise SaveError('Unqualified Second Light Party framing.')
        identity = struct.unpack_from('>I',payload,record[0].body)[0]
        if identity != (index if index < 12 else 0xffffffff):
            raise SaveError('Unqualified Second Light existing Party identity.')
        members.append(record[0])
    _nodes(payload,array_start + 15 * 5374,party.end)
    return roots,tuple(regions),tuple(members)


@lru_cache(maxsize=2)
def _snapshot(raw):
    try:
        header,payload,details = codec.decode_file(raw)
    except (codec.SaveFormatError,struct.error,IndexError) as error:
        raise SaveError(f'Second Light native integrity/codec check failed: {error}.') from error
    _structure(payload)
    if header[:40] != struct.pack('<I',1) + bytes(36) or header[40:48] != struct.pack('<II',1,PAYLOAD_SIZES.index(len(payload))):
        raise SaveError('Unqualified Second Light original Steam PC header.')
    _structure(payload)
    trailer = raw[codec.HEADER_SIZE + details.padded_size:]
    return header,payload,details,trailer


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    if not isinstance(raw,(bytes,bytearray)) or not codec.HEADER_SIZE < len(raw) <= MAX_FILE_SIZE:
        raise SaveError('Second Light save exceeds processing bounds.')
    raw = bytes(raw)
    header,payload,details,trailer = _snapshot(raw)
    return Document(FORMAT,Path(source),raw,payload,header,details.seed,details.footer,trailer)


def validate_document(document):
    if type(document) is not Document or document.format is not FORMAT or type(document.seed) is not int:
        raise SaveError('Unregistered Second Light snapshot.')
    if any(type(getattr(document,key)) is not bytes for key in ('raw','payload','header','footer','trailer')):
        raise SaveError('Second Light snapshot is not immutable.')
    if document != decode(document.raw,GAME_ID,document.source):
        raise SaveError('Second Light snapshot changed outside staged edits.')


@lru_cache(maxsize=2)
def _fields(payload, experimental=False):
    _roots,regions,_members = _structure(payload)
    instances = {}
    for _label,start,count in regions:
        for slot in range(count):
            offset = start + slot * RECORD_SIZE
            instance,identity = struct.unpack_from('<HH',payload,offset)
            if instance != 0xffff and identity != 0xffff:
                instances[instance] = instances.get(instance,0) + 1
    fields = {}
    _label,start,count = regions[0]
    for slot in range(count):
        offset = start + slot * RECORD_SIZE
        instance,identity = struct.unpack_from('<HH',payload,offset)
        quantity = payload[offset + 6]
        # Never set zero/remove ownership or raise counts. +7 is opaque, so only
        # source-backed one-byte counts with zero high byte qualify.
        if (instance != 0xffff and identity != 0xffff and instances.get(instance) == 1
                and quantity >= (1 if experimental else 2) and payload[offset + 7] == 0):
            key = f'container_{slot + 1}_quantity'
            fields[key] = Field(key,f'Quantity (item ID {identity}, instance {instance}; reduce only)',
                                offset + 6,quantity,slot=slot + 1)
    return MappingProxyType(fields)


def field_map(document):
    validate_document(document)
    return _fields(document.payload, experimental_enabled())


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document,changes):
    fields = field_map(document)
    if not isinstance(changes,Mapping):
        raise SaveError('Second Light changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key,value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unmapped Second Light field.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + field.size] = value.to_bytes(field.size,'little')
    return bytes(output)


def stage(document,changes,key,value):
    changed_payload(document,changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('Unmapped Second Light field.')
    field = fields[key]
    result = dict(changes)
    if type(value) is int and value == field.value(document.payload):
        result.pop(key,None)
    else:
        field.validate(value)
        result[key] = value
    return result


def serialize(document,changes):
    payload = changed_payload(document,changes)
    if payload == document.payload:
        return document.raw
    raw = codec.encode_file(document.header,payload,document.seed,document.footer) + document.trailer
    reopened = decode(raw,GAME_ID,document.source)
    if (reopened.payload,reopened.header,reopened.seed,reopened.footer,reopened.trailer) != (
            payload,document.header,document.seed,document.footer,document.trailer):
        raise SaveError('Second Light edited copy failed read-back verification.')
    return raw


def limit_values(document,changes,keys):
    changed_payload(document,changes)
    fields = field_map(document)
    if any(type(key) is not str or key not in fields for key in keys):
        raise SaveError('Unmapped Second Light field.')
    return {}  # Reductions have no meaningful Max action.


def maximums(document,changes,group=None):
    changed_payload(document,changes)
    return dict(changes)


def review(document,changes):
    changed_payload(document,changes)
    return [(f,f.value(document.payload),changes[f.id]) for f in fields_for(document) if f.id in changes]


def _copy_path(path):
    resolved = safe_path(path)
    for text in (str(path),str(resolved)):
        text = text.replace('\\','/').casefold().rstrip('/')
        if any('/koeitecmo/' + name + '/' in text + '/'
               for name in ('blue reflection second light','blue reflection secondlight',
                            'blue reflection: second light','blue reflection 2')):
            raise SaveError('Use a separate copy outside live Second Light save folders.')
    return resolved


def read_save(path,game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    if path.suffix.casefold() != '.dat':
        raise SaveError('Open a separate Second Light .dat gameplay copy.')
    with path.open('rb') as stream:
        raw = stream.read(MAX_FILE_SIZE + 1)
    return decode(raw,game_id,path)


def _validate_source(document):
    source = _copy_path(document.source)
    try:
        with source.open('rb') as stream:
            current = stream.read(MAX_FILE_SIZE + 1)
    except OSError as error:
        raise SaveError('The opened copy is unavailable; reopen before saving.') from error
    if current != document.raw:
        raise SaveError('The opened copy changed on disk; reopen before saving.')
    return source


def backup(document):
    validate_document(document)
    source = _validate_source(document)
    return snapshot_backup(document.raw,source,GAME_ID,_copy_path(source.parent / 'WarriorsEditorBackups'))


def save_as(document,changes,destination):
    validate_document(document)
    destination = _copy_path(destination)
    if destination.suffix.casefold() != '.dat':
        raise SaveError('Choose a new .dat destination.')
    if destination.exists():
        raise FileExistsError('Choose a new destination; existing files are never replaced.')
    _validate_source(document)
    raw = serialize(document,changes)
    backup(document)
    _validate_source(document)
    atomic_new(raw,destination)
    return decode(raw,GAME_ID,destination)


def restore(backup_path,destination,game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(_copy_path(backup_path),_copy_path(destination),GAME_ID,'.dat',MAX_FILE_SIZE,
                            validate_raw=lambda raw: decode(raw,GAME_ID))


def record_label(slot,group):
    return group


def field_hint(document,key):
    if type(key) is not str or key not in field_map(document):
        raise SaveError('Unmapped Second Light field.')
    return ('Reduce an existing positive container count down to 1. The opened count is the maximum; '
            'Max is disabled. Zero, creation, item IDs, quality, traits/effects, equipment, '
            'Coins, TP, relationships and quests have no writable mapping.')


def inspection_rows(document):
    """Exact layout observations, with unknown record words labelled as raw."""
    validate_document(document)
    roots,regions,members = _structure(document.payload)
    inventory = []
    for label,start,count in regions:
        for slot in range(count):
            offset = start + slot * RECORD_SIZE
            instance,identity = struct.unpack_from('<HH',document.payload,offset)
            if instance == 0xffff or identity == 0xffff:
                continue
            inventory.append((label,slot + 1,instance,identity,document.payload[offset + 6]))
    party = tuple((index + 1,struct.unpack_from('>I',document.payload,node.body)[0],
                   node.end - node.start) for index,node in enumerate(members))
    sections = tuple((node.name.decode(),node.end - node.start) for node in roots)
    return tuple(inventory),party,sections

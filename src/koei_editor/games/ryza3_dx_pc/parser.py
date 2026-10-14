"""Ryza 3 DX PC revision-4 resources with exact opaque native tail retention.

Only explicit tagged SP/gem balances are writable, as deductions. This is not
an original Ryza 3, console or earlier Ryza schema. See RYZA3_DX_PC_FORMAT.md.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.games.sophie2 import atelier_sophie2_codec as codec
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'atelier_ryza3_dx_pc'
MAX_FILE_SIZE = codec.MAX_FILE_SIZE
INTEGRITY_KIND = 'checksum'
# Complete roots before the independently game-loaded eight-byte native elision.
ROOT_PROFILE = (
    ('info',29), ('PlayGo',12), ('dlc',149), ('event',51870), ('knowledge',25304),
    ('money',32), ('party',23448), ('fieldmap',34124), ('friend',51), ('library',1828),
    ('item',2084726), ('time',17), ('event_check',21), ('date',29), ('global',91),
    ('mix_lv',73), ('explore_equip',5208), ('bonus',577), ('system',3841),
    ('dlcbgm',8033), ('shop',8289), ('mix_recipe',2023), ('achievement',23919),
    ('collectData',10785), ('costume',897), ('secret_base',136717), ('SecretKey',2710),
    ('battlescore',1565), ('lambRoast',361), ('weaponskin',87), ('record',6125),
    ('AlchemyTree',881), ('worldmap',168), ('party_quest',3057), ('tutorial',184),
    ('quest',32708), ('Feeding',9383), ('FreeBattle',188), ('AtelierMaking',150),
    ('itemquiz',50), ('ObjControl',90),
)
TAIL_START = 2479832
PAYLOAD_SIZE = 2480654
POOLS = (
    ('Basket', 'item_basket_units', 700),
    ('Important basket', 'item_basket_impt_units', 250),
    ('Container', 'item_container_units', 15000),
    ('Important container', 'item_container_impt_units', 250),
    ('Consumable container', 'item_container_expen_units', 50),
)


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    group: str = 'Alchemy resources'
    slot: int = 0
    size: int = 4
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'
    byteorder: str = 'little'

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    @property
    def experimental_maximum(self):
        return 0x7FFFFFFF

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label}: use a whole number from 0 to the opened balance ({self.maximum}).')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Atelier Ryza 3 DX: Alchemist of the End & the Secret Key (Steam PC)'
    size: int = MAX_FILE_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = 'Native revision-4 DX layout; SP and gem deductions with searchable native records.'


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
        raise SaveError('Select the qualified Ryza 3 DX Steam PC profile.')
    return FORMAT


def _nodes(payload, start, end):
    result = []
    while start < end:
        if start + 5 > end:
            raise SaveError('Truncated Ryza 3 DX tagged node.')
        size = struct.unpack_from('<I', payload, start)[0]
        stop = start + size
        zero = payload.find(b'\0', start + 4, min(stop, start + 85, end))
        if not start + 5 <= stop <= end or zero < 0:
            raise SaveError('Invalid Ryza 3 DX tagged framing.')
        name = payload[start + 4:zero]
        if not name or any(value < 32 or value > 126 for value in name):
            raise SaveError('Invalid Ryza 3 DX node name.')
        result.append(Node(name, start, zero + 1, stop))
        start = stop
    if len({n.name for n in result}) != len(result):
        raise SaveError('Duplicate Ryza 3 DX tagged node.')
    return tuple(result)


def _unique(nodes, name):
    matches = [n for n in nodes if n.name == name.encode()]
    if len(matches) != 1:
        raise SaveError(f'Missing or ambiguous Ryza 3 DX node: {name}.')
    return matches[0]


def _children(payload, node):
    return _nodes(payload, node.body, node.end)


def _body(payload, node):
    return payload[node.body:node.end]


@lru_cache(maxsize=2)
def _structure(payload):
    if len(payload) != PAYLOAD_SIZE or payload[:32] != struct.pack('<I', 20150730) + bytes(28):
        raise SaveError('Unqualified Ryza 3 DX native preamble/size.')
    roots = _nodes(payload, 32, TAIL_START)
    if tuple((n.name.decode(), n.end - n.start) for n in roots) != ROOT_PROFILE:
        raise SaveError('Unqualified Ryza 3 DX complete-root profile.')
    # Exact final order_switch/version/order_data framing only. Native loader
    # evidence qualifies its eight missing terminal bytes, never arbitrary
    # truncation. The available 822 bytes stay opaque and unchanged.
    tail = payload[TAIL_START:]
    prefix = (struct.pack('<I',830) + b'order_switch\0'
              + struct.pack('<I',14) + b'version\0\1\0'
              + struct.pack('<I',799) + b'order_data\0' + struct.pack('<I',780))
    if len(tail) != 822 or not tail.startswith(prefix):
        raise SaveError('Unqualified Ryza 3 DX terminal order-switch profile.')
    app = _unique(_children(payload, _unique(roots,'info')), 'app_ver')
    if _body(payload,app) != struct.pack('<II',1,1):
        raise SaveError('Unqualified Ryza 3 DX app revision.')
    fmap = _unique(roots,'fieldmap')
    if any(payload.find(marker, fmap.body, fmap.end) < 0
           for marker in (b'_I_SECRETBASE_01\0',b'_T_SECRETBASE_02\0',b'_T_RASEN\0')):
        raise SaveError('Ryza 3 DX title-specific map schema is absent.')
    item = _children(payload,_unique(roots,'item'))
    if _body(payload,_unique(item,'version')) != b'\2\0':
        raise SaveError('Unqualified Ryza 3 DX item revision.')
    if _body(payload,_unique(item,'limitSize')) != struct.pack('<II',700,15000):
        raise SaveError('Unqualified Ryza 3 DX inventory limits.')
    regions = []
    for label,name,count in POOLS:
        node = _unique(item,name)
        if (node.end - node.body != 4 + count * 128
                or struct.unpack_from('<I',payload,node.body)[0] != count * 128):
            raise SaveError('Unqualified Ryza 3 DX inventory array framing.')
        regions.append((label,node.body + 4,count))
    party = _unique(roots,'party')
    version_end = party.body + 14
    version = _nodes(payload,party.body,version_end)
    if len(version) != 1 or version[0].name != b'version' or _body(payload,version[0]) != b'\1\0':
        raise SaveError('Unqualified Ryza 3 DX Party revision.')
    if struct.unpack_from('<I',payload,version_end)[0] != 14:
        raise SaveError('Unqualified Ryza 3 DX Party array count.')
    array_start = version_end + 4
    # Repeated Party names are native array records, not tagged-map keys.
    members = []
    for index in range(14):
        record = _nodes(payload,array_start + index * 1600,array_start + (index + 1) * 1600)
        if len(record) != 1 or record[0].name != b'Party':
            raise SaveError('Unqualified Ryza 3 DX Party record framing.')
        members.append(record[0])
    _nodes(payload,array_start + 14 * 1600,party.end)
    tree = _children(payload,_unique(roots,'AlchemyTree'))
    if _body(payload,_unique(tree,'version')) != struct.pack('<IH',2,0):
        raise SaveError('Unqualified Ryza 3 DX skill-tree revision.')
    state = _unique(tree,'skill_state')
    if state.end - state.body != 762 or struct.unpack_from('<I',payload,state.body)[0] != 758:
        raise SaveError('Unqualified Ryza 3 DX learned-skill framing.')
    keys = _children(payload,_unique(roots,'SecretKey'))
    if _body(payload,_unique(keys,'version')) != b'\1\0':
        raise SaveError('Unqualified Ryza 3 DX key-pool revision.')
    key_regions = []
    for name in ('secretkey_general','secretkey_innocent'):
        node = _unique(keys,name)
        if node.end - node.body != 1284 or struct.unpack_from('<I',payload,node.body)[0] != 1280:
            raise SaveError('Unqualified Ryza 3 DX key-pool framing.')
        key_regions.append((name,node.body + 4,10))
    return roots, tuple(regions), tuple(members), tuple(key_regions), item, tree


@lru_cache(maxsize=2)
def _snapshot(raw):
    try:
        header,payload,details = codec.decode_file(raw)
    except (codec.SaveFormatError,struct.error,IndexError) as error:
        raise SaveError(f'Ryza 3 DX native integrity/codec check failed: {error}.') from error
    if header[:48] != struct.pack('<I',4) + bytes(36) + struct.pack('<II',1,1):
        raise SaveError('Unqualified Ryza 3 DX Steam PC header.')
    _structure(payload)
    trailer = raw[codec.HEADER_SIZE + details.padded_size:]
    return header,payload,details,trailer


def decode(raw, game_id=GAME_ID, source=Path('copy.dat')):
    get_format(game_id)
    if not isinstance(raw,(bytes,bytearray)) or not codec.HEADER_SIZE < len(raw) <= MAX_FILE_SIZE:
        raise SaveError('Ryza 3 DX save exceeds processing bounds.')
    raw = bytes(raw)
    header,payload,details,trailer = _snapshot(raw)
    return Document(FORMAT,Path(source),raw,payload,header,details.seed,details.footer,trailer)


def validate_document(document):
    if type(document) is not Document or document.format is not FORMAT or type(document.seed) is not int:
        raise SaveError('Unregistered Ryza 3 DX snapshot.')
    if any(type(getattr(document,key)) is not bytes for key in ('raw','payload','header','footer','trailer')):
        raise SaveError('Ryza 3 DX snapshot is not immutable.')
    if document != decode(document.raw,GAME_ID,document.source):
        raise SaveError('Ryza 3 DX snapshot changed outside staged edits.')


@lru_cache(maxsize=2)
def _fields(payload):
    _roots,_regions,_members,_keys,item,tree = _structure(payload)
    fields = {}
    for key,label,nodes,name in (
            ('skill_points','Unspent skill-tree SP (reduce only)',tree,'skill_point'),
            ('synthesis_gems','Gems (reduce only)',item,'mix_gem')):
        node = _unique(nodes,name)
        if node.end - node.body != 8 or struct.unpack_from('<I',payload,node.body)[0] != 4:
            continue  # Unknown scalar width is preserved without a control.
        value = struct.unpack_from('<i',payload,node.body + 4)[0]
        if value >= 0:
            fields[key] = Field(key,label,node.body + 4,value)
    return MappingProxyType(fields)


def field_map(document):
    validate_document(document)
    return _fields(document.payload)


def fields_for(document):
    return tuple(field_map(document).values())


def changed_payload(document,changes):
    fields = field_map(document)
    if not isinstance(changes,Mapping):
        raise SaveError('Ryza 3 DX changes must be a field/value mapping.')
    output = bytearray(document.payload)
    for key,value in changes.items():
        if type(key) is not str or key not in fields:
            raise SaveError('Unmapped Ryza 3 DX field.')
        field = fields[key]
        if type(value) is int and value == field.value(document.payload):
            continue
        field.validate(value)
        output[field.offset:field.offset + 4] = value.to_bytes(4,'little')
    return bytes(output)


def stage(document,changes,key,value):
    changed_payload(document,changes)
    fields = field_map(document)
    if type(key) is not str or key not in fields:
        raise SaveError('Unmapped Ryza 3 DX field.')
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
        raise SaveError('Ryza 3 DX edited copy failed read-back verification.')
    return raw


def limit_values(document,changes,keys):
    changed_payload(document,changes)
    fields = field_map(document)
    if any(type(key) is not str or key not in fields for key in keys):
        raise SaveError('Unmapped Ryza 3 DX field.')
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
        if '/koeitecmo/atelier ryza 3 dx/' in text + '/':
            raise SaveError('Use a separate copy outside live Ryza 3 DX save folders.')
    return resolved


def read_save(path,game_id=GAME_ID):
    get_format(game_id)
    path = _copy_path(path)
    if path.suffix.casefold() != '.dat':
        raise SaveError('Open a separate Ryza 3 DX .dat gameplay copy.')
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
        raise SaveError('Unmapped Ryza 3 DX field.')
    return ('Reduce only the opened balance. Max is disabled. Learned skills, recipes, quality caps, '
            'duplication/rebuilding unlocks, items, quests and rewards stay intact. Gems fund unlocked duplication and rebuilding.')


def inspection_rows(document):
    """Exact layout observations, with unknown record words labelled as raw."""
    validate_document(document)
    roots,regions,members,key_regions,_item,_tree = _structure(document.payload)
    inventory = []
    for label,start,count in regions + key_regions:
        for slot in range(count):
            offset = start + slot * 128
            words = struct.unpack_from('<6H',document.payload,offset)
            if words[0] == 0xffff and words[2] == 0xffff:
                continue
            inventory.append((label,slot + 1,*words))
    party = tuple((index + 1,struct.unpack_from('<i',document.payload,node.body)[0],
                   node.end - node.start) for index,node in enumerate(members))
    sections = tuple((node.name.decode(),node.end - node.start) for node in roots)
    return tuple(inventory),party,sections

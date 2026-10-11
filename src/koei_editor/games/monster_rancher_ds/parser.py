"""Independently implemented MRDS native replica/CRC writer.

Only matched existing records in both qualified replicas are editable. Unknown
bytes and the physical backup-memory tail remain opaque; no latest-slot guess.
See docs/MONSTER_RANCHER_DS_FORMAT.md for pinned source and mechanics evidence.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType
import zlib

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.save_safety import safe_path

GAME_ID = 'monster_rancher_ds'
EXTENSION = '.sav'
MAX_SIZE = 65536
INTEGRITY_KIND = 'checksum'
SIGNATURE = b'MonsterRancherDS\0MonsterRancherDS\0'
ENTRY_SIZE = 15584
ENTRY_BASES = (34, 34 + ENTRY_SIZE)
HEADER_CRC = 56
BODY_CRC = 15580
MONSTER_BASE = 456
MONSTER_SIZE = 420
STATS = ('Power', 'Intelligence', 'Skill', 'Speed', 'Defense', 'Life')
STAT_BUDGET = 5994
# Occupied identities independently present in genuine native fixtures. A full
# species-ID domain/catalog is not yet established; other IDs remain opaque.
QUALIFIED_SPECIES_IDS = frozenset((3, 56, 156))
# Individually cross-checked factual ordinary IDs, not an upstream catalog.
ITEM_NAMES = MappingProxyType({0: 'Banana Ring', 1: 'Medicinal Herb', 2: 'Honey Shroom',
    3: 'Monster Candy', 4: 'Elixir', 5: 'Sea Angel', 6: 'Soda Lozenge', 7: 'Worm Fungus',
    8: 'Roll Cake', 9: 'Shock Rock', 10: 'Fatty Meat', 11: 'Blade Weed',
    13: 'Silver Peach', 14: 'Gold Peach'})


def _name(raw):
    """Only existing canonical printable ASCII fields may be renamed."""
    head, separator, tail = raw.partition(b'\0')
    if (not head or not head.strip() or any(not 32 <= value <= 126 for value in head)
            or separator and any(tail)):
        return None
    return head.decode('ascii')


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    size: int
    maximum: int
    group: str
    slot: int = 0
    minimum: int = 0
    maxable: bool = False
    kind: str = 'int'
    record: str = ''

    def value(self, payload):
        raw = payload[self.offset:self.offset + self.size]
        return _name(raw) if self.kind == 'text' else int.from_bytes(raw, 'little')

    def validate(self, value):
        if self.kind == 'text':
            if (type(value) is not str or not 1 <= len(value) <= self.maximum
                    or not value.strip() or any(not 32 <= ord(c) <= 126 for c in value)):
                raise SaveError(f'{self.label}: use 1–{self.maximum} printable ASCII characters.')
        elif type(value) is not int or not self.minimum <= value <= self.maximum:
            raise SaveError(f'{self.label}: use a whole number from {self.minimum} to {self.maximum}.')


@dataclass(frozen=True)
class Format:
    id: str = GAME_ID
    title: str = 'Monster Rancher DS — US Nintendo DS'
    size: int = MAX_SIZE
    fields: tuple = ()
    sample_verified: bool = True
    game_load_verified: bool = False
    note: str = ('Raw 32/64 KiB US .sav exports. Edit matching existing monster stats and '
                 'positive lifespan, ASCII names and gold reductions. Ordinary stats cap '
                 'at 999; existing Overdrive values stay intact. Inventory and progression '
                 'are searchable. Reimport the raw edited copy through your save manager.')


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
        raise SaveError('Select the US Nintendo DS Monster Rancher DS profile.')
    return FORMAT


@lru_cache(maxsize=8)
def _checked(raw):
    if (type(raw) is not bytes or len(raw) not in (32768, 65536)
            or raw[:34] != SIGNATURE):
        raise SaveError('Requires a complete raw 32/64 KiB US Monster Rancher DS .sav export.')
    for base in ENTRY_BASES:
        header = struct.unpack_from('<I', raw, base + HEADER_CRC)[0]
        body = struct.unpack_from('<I', raw, base + BODY_CRC)[0]
        if (zlib.crc32(raw[base:base + HEADER_CRC]) != header
                or zlib.crc32(raw[base:base + BODY_CRC]) != body):
            raise SaveError('Monster Rancher DS replica/header CRC is damaged; input is never repaired.')
    return raw


def decode(raw, game_id=GAME_ID, source=Path('copy.sav')):
    get_format(game_id)
    if type(raw) is not bytes:
        raise SaveError('A frozen native save snapshot is required.')
    return Document(FORMAT, Path(source), raw, _checked(raw))


def validate_document(document):
    if (type(document) is not Document or document.format is not FORMAT
            or type(document.raw) is not bytes or type(document.payload) is not bytes
            or _checked(document.raw) != document.payload):
        raise SaveError('A frozen qualified Monster Rancher DS snapshot is required.')


def _copy_path(path):
    path = safe_path(path)
    if path.suffix.lower() != EXTENSION:
        raise SaveError('Choose a separate raw .sav copy; export .dsv containers first.')
    if any(part.casefold() in ('battery', 'battery saves') for part in path.parts):
        raise SaveError('Copy the save outside the emulator battery-save folder first.')
    return path


def read_save(path, game_id=GAME_ID):
    path = _copy_path(path)
    with path.open('rb') as stream:
        raw = stream.read(MAX_SIZE + 1)
    return decode(raw, game_id, path)


def _matched(raw, offset, size):
    a, b = ENTRY_BASES
    return raw[a + offset:a + offset + size] == raw[b + offset:b + offset + size]


def _context(raw):
    return all(_matched(raw, offset, 13) and _name(raw[34 + offset:34 + offset + 13])
               for offset in (10, 27))


def _monster(raw, replica, slot):
    offset = ENTRY_BASES[replica] + MONSTER_BASE + slot * MONSTER_SIZE
    species = struct.unpack_from('<H', raw, offset + 18)[0]
    name = _name(raw[offset:offset + 12])
    age, lifespan = struct.unpack_from('<HH', raw, offset + 30)
    stats = struct.unpack_from('<6H', raw, offset + 40)
    return offset, species, name, age, lifespan, stats


@lru_cache(maxsize=8)
def _fields(raw):
    fields = []
    if not _context(raw):
        return ()
    for key, label, offset in (('ranch_name', 'Ranch name', 10), ('player_name', 'Breeder name', 27)):
        fields.append(Field(key, label, 34 + offset, 13, 12, 'Names', minimum=1,
                            kind='text', record='Ranch / breeder'))
    gold = struct.unpack_from('<I', raw, 34 + 352)[0]
    if gold and _matched(raw, 352, 4):
        fields.append(Field('gold', 'Gold (reductions only)', 34 + 352, 4, gold,
                            'Resources', record='Ranch funds'))
    for slot in range(31):
        offset, species, name, _age, lifespan, stats = _monster(raw, 0, slot)
        if (species not in QUALIFIED_SPECIES_IDS or name is None or not _matched(raw, MONSTER_BASE + slot * MONSTER_SIZE, MONSTER_SIZE)
                or any(value > 1500 for value in stats)):
            continue
        record = f'{"Current" if slot == 0 else "Frozen " + str(slot)} · {name}'
        group = 'Current monster' if slot == 0 else 'Frozen monsters'
        fields.append(Field(f'monster_{slot}_name', 'Monster name', offset, 12, 12,
                            group, slot + 1, minimum=1, kind='text', record=record))
        if lifespan == 0:
            continue  # No dead/expired monster stat edits or implicit revival.
        for index, label in enumerate(STATS):
            fields.append(Field(f'monster_{slot}_stat_{index}', label, offset + 40 + index * 2,
                                2, 999, group, slot + 1,
                                maxable=all(value <= 999 for value in stats), record=record))
        if 1 <= lifespan <= 9999:
            fields.append(Field(f'monster_{slot}_lifespan', 'Remaining lifespan (10 units / week)',
                                offset + 32, 2, 9999, group, slot + 1, minimum=lifespan,
                                maxable=True, record=record))
    return tuple(fields)


def fields_for(document):
    validate_document(document)
    return _fields(document.raw)


def field_map(document):
    return MappingProxyType({field.id: field for field in fields_for(document)})


def changed_payload(document, changes):
    mapping = field_map(document)
    if type(changes) is not dict:
        raise SaveError('Monster Rancher DS edits must be a field/value mapping.')
    output = bytearray(document.raw)
    touched = False
    for key, value in changes.items():
        if type(key) is not str or key not in mapping:
            raise SaveError('Only qualified paired existing fields are editable.')
        field = mapping[key]
        if type(value) is type(field.value(document.raw)) and value == field.value(document.raw):
            continue  # Preserve opened unusual values and exact name padding.
        field.validate(value)
        encoded = ((value.encode('ascii') + bytes(field.size - len(value)))
                   if field.kind == 'text' else value.to_bytes(field.size, 'little'))
        for delta in (0, ENTRY_SIZE):
            output[field.offset + delta:field.offset + delta + field.size] = encoded
        touched = True
    for slot in range(31):
        old = _monster(document.raw, 0, slot)[-1]
        new = _monster(output, 0, slot)[-1]
        if sum(new) > max(STAT_BUDGET, sum(old)):
            raise SaveError('A monster’s six stats cannot exceed 5994 total; lower other stats first. '
                            'Existing unusual totals may be preserved or reduced.')
    if touched:
        for base in ENTRY_BASES:
            struct.pack_into('<I', output, base + HEADER_CRC, zlib.crc32(output[base:base + HEADER_CRC]))
            struct.pack_into('<I', output, base + BODY_CRC, zlib.crc32(output[base:base + BODY_CRC]))
    return _checked(bytes(output))


def serialize(document, changes):
    return changed_payload(document, changes)


def stage(document, changes, key, value):
    changed_payload(document, changes)
    mapping = field_map(document)
    if type(key) is not str or key not in mapping:
        raise SaveError('This Monster Rancher DS record is inspection only.')
    pending = dict(changes)
    field = mapping[key]
    if type(value) is type(field.value(document.raw)) and value == field.value(document.raw):
        pending.pop(key, None)
    else:
        pending[key] = value
    changed_payload(document, pending)
    return pending


def limit_values(document, changes, keys):
    changed_payload(document, changes)
    mapping = field_map(document)
    if (type(keys) not in (list, tuple, set, frozenset)
            or any(type(key) is not str or key not in mapping for key in keys)):
        raise SaveError('Select qualified Monster Rancher DS fields.')
    result = {key: max(mapping[key].value(document.raw), changes.get(key, mapping[key].value(document.raw)),
                       mapping[key].maximum) for key in keys if mapping[key].maxable}
    changed_payload(document, {**changes, **result})
    return result


def maximums(document, changes, group=None):
    keys = [field.id for field in fields_for(document) if group is None or field.group == group]
    return {**changes, **limit_values(document, changes, keys)}


def review(document, changes):
    changed_payload(document, changes)
    return [(field, field.value(document.raw), changes[field.id])
            for field in fields_for(document) if field.id in changes]


def _source(document):
    validate_document(document)
    path = _copy_path(document.source)
    with path.open('rb') as stream:
        if stream.read(MAX_SIZE + 1) != document.raw:
            raise SaveError('The original Monster Rancher DS copy changed; reopen it before saving.')
    return path


def backup(document):
    path = _source(document)
    return snapshot_backup(document.raw, path, GAME_ID, path.parent / 'UniversalEditorBackups')


def save_as(document, changes, destination):
    source = _source(document)
    destination = _copy_path(destination)
    if destination == source or destination.exists():
        raise FileExistsError('Choose a new file; original and existing saves are never replaced.')
    raw = serialize(document, changes)
    backup(document)
    _source(document)
    atomic_new(raw, destination)
    return read_save(destination)


def restore(backup_path, destination, game_id=GAME_ID):
    get_format(game_id)
    return restore_snapshot(_copy_path(backup_path), _copy_path(destination), GAME_ID, EXTENSION,
                            MAX_SIZE, validate_raw=lambda raw: decode(raw))


def inspection_tables_data(document):
    validate_document(document)
    raw = document.raw
    monsters, items, status = [], [], []
    editable = field_map(document)
    for replica, base in enumerate(ENTRY_BASES):
        label = f'Replica {replica + 1}'
        status.extend((label, name, value) for name, value in (
            ('Save counter (active ordering not inferred)', raw[base]),
            ('Breeder grade', raw[base + 70]),
            ('Lifetime money won (not spendable gold)', struct.unpack_from('<I', raw, base + 140)[0]),
            ('Spendable gold', struct.unpack_from('<I', raw, base + 352)[0]),
            ('Year', struct.unpack_from('<H', raw, base + 48)[0]),
            ('Month', raw[base + 50]), ('Week', raw[base + 51]), ('Day', raw[base + 52])))
        for slot in range(31):
            offset, species, name, age, lifespan, stats = _monster(raw, replica, slot)
            monsters.append((label, 'Current' if slot == 0 else f'Frozen {slot}',
                             name or ('Empty' if species == 0xFFFF else 'Non-ASCII / unmapped name'),
                             species, age, lifespan, *stats,
                             'Paired existing record' if f'monster_{slot}_stat_0' in editable else 'Inspection only'))
        for slot in range(50):
            item_id = struct.unpack_from('<H', raw, base + 356 + slot * 2)[0]
            items.append((label, slot + 1, item_id,
                          ITEM_NAMES.get(item_id, 'Empty' if item_id == 0xFFFF else 'Unmapped / special item')))
    return tuple(monsters), tuple(items), tuple(status)


def field_hint(document, key):
    field = field_map(document)[key]
    if field.kind == 'text':
        return f'Existing name: 1–{field.maximum} printable ASCII characters; both matching replicas update together.'
    if key == 'gold':
        return 'Reduce existing spendable gold. Lifetime winnings, breeder rank and tournament progression stay intact.'
    if key.endswith('_lifespan'):
        return ('Extend positive remaining lifespan to 9999 units; normal time costs 10 units per week. '
                'Calendar age, growth stage, stress and fatigue stay intact. No revival of expired monsters.')
    return ('Ordinary stat range 0–999; six-stat budget 5994. Existing Overdrive values above 999 '
            'are preserved by Max. No breed, grade, technique or tournament unlocks are changed.')

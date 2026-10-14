"""Independent Gemfire battery-record writer from published native routines.

NES and SNES use the same relative record layout with different RAM pointers.
Existing complete state blocks are located by their native KOEI footer and
qualified structurally; no undocumented fixed slot-address table is invented.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.copy_storage import atomic_new, restore_snapshot, snapshot_backup
from koei_editor.shared.experimental_limits import within_numeric_limits
from koei_editor.shared.save_safety import safe_path

SIZE = MAX_FILE_SIZE = 8192
BLOCK_SIZE = 0x769
MARKER = 0x765
ARMY_START, ARMY_STRIDE, ARMY_COUNT = 0x35, 4, 30
LEADER_START, LEADER_STRIDE, LEADER_COUNT = 0xAD, 10, 64
PROVINCE_START, PROVINCE_STRIDE, PROVINCE_COUNT = 0x32D, 36, 30
INTEGRITY_KIND = 'none'


@dataclass(frozen=True)
class Format:
    id: str
    title: str
    note: str
    size: int = SIZE
    fields: tuple = ()
    sample_verified: bool = False
    game_load_verified: bool = False
    editing_verified: bool = False
    published_format: bool = True


@dataclass(frozen=True)
class Field:
    id: str
    label: str
    offset: int
    maximum: int
    group: str
    slot: int
    size: int
    minimum: int = 0
    maxable: bool = True
    kind: str = 'int'
    byteorder: str = 'little'

    @property
    def experimental_maximum(self):
        return (1 << (self.size * 8)) - 1

    def value(self, payload):
        return int.from_bytes(payload[self.offset:self.offset + self.size], 'little')

    def validate(self, value):
        if type(value) is not int or not within_numeric_limits(
                value, self.minimum, self.maximum, storage_maximum=self.experimental_maximum):
            raise SaveError(f'{self.label} requires a whole number from 0 to {self.maximum}.')


@dataclass(frozen=True)
class Document:
    format: Format
    source: Path
    raw: bytes
    payload: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


def _word(raw, offset):
    return int.from_bytes(raw[offset:offset + 2], 'little')


def _id(value, count):
    return value == 255 or value < count


def _leader_pointer(value, ram_base):
    if value == 0:
        return None
    offset = value - ram_base - LEADER_START
    if offset < 0 or offset % LEADER_STRIDE or offset // LEADER_STRIDE >= LEADER_COUNT:
        raise SaveError('Gemfire leader pointer is outside the selected platform record table.')
    return offset // LEADER_STRIDE


def _qualify_block(raw, base, ram_base, month_offset, player_offset):
    block = raw[base:base + BLOCK_SIZE]
    if len(block) != BLOCK_SIZE or block[MARKER:] != b'KOEI':
        raise SaveError('Incomplete Gemfire native state block.')
    if not 1 <= block[month_offset] <= 12:
        raise SaveError('Gemfire native saved month is invalid.')
    players = tuple(value for value in block[player_offset:player_offset + 2] if value != 255)
    if not players or any(not _id(value, ARMY_COUNT) for value in players):
        raise SaveError('Gemfire saved player faction records are invalid.')
    for index in range(ARMY_COUNT):
        army = ARMY_START + index * ARMY_STRIDE
        if not _id(block[army + 1], LEADER_COUNT) or not _id(block[army + 2], ARMY_COUNT):
            raise SaveError('Gemfire army leader/partner records are invalid.')
        if index in players and block[army + 1] == 255:
            raise SaveError('Gemfire player faction has no existing army leader.')
    links = []
    for index in range(LEADER_COUNT):
        leader = LEADER_START + index * LEADER_STRIDE
        links.append(_leader_pointer(_word(block, leader), ram_base))
        if not _id(block[leader + 5], PROVINCE_COUNT) or not _id(block[leader + 6], ARMY_COUNT):
            raise SaveError('Gemfire leader province/faction records are invalid.')
    # Native reconstruction checks each assigned leader's faction against its
    # province owner; preserve empty/unassigned leaders and opaque stat bytes.
    for index in range(LEADER_COUNT):
        leader = LEADER_START + index * LEADER_STRIDE
        province, owner = block[leader + 5:leader + 7]
        if province != 255 and owner != 255:
            if block[PROVINCE_START + province * PROVINCE_STRIDE + 14] != owner:
                raise SaveError('Gemfire leader and province ownership disagree.')
    visited = set()
    live = 0
    for index in range(PROVINCE_COUNT):
        province = PROVINCE_START + index * PROVINCE_STRIDE
        owner = block[province + 14]
        if not _id(owner, ARMY_COUNT):
            raise SaveError('Gemfire province owner is outside the existing faction table.')
        current = _leader_pointer(_word(block, province), ram_base)
        if owner != 255 and block[ARMY_START + owner * ARMY_STRIDE + 1] == 255:
            raise SaveError('Gemfire owned province references an empty faction.')
        if owner in players:
            live += 1
        local = set()
        while current is not None:
            if current in local or current in visited:
                raise SaveError('Gemfire province leader chains contain a cycle or shared record.')
            local.add(current)
            visited.add(current)
            leader = LEADER_START + current * LEADER_STRIDE
            if block[leader + 5] != index or block[leader + 6] != owner:
                raise SaveError('Gemfire linked leader has conflicting province/faction ownership.')
            current = links[current]
    if not visited or not live:
        raise SaveError('Gemfire requires existing linked leaders and a player-owned province.')
    return players


@lru_cache(maxsize=8)
def qualified_blocks(raw, ram_base, month_offset, player_offset):
    if len(raw) != SIZE:
        raise SaveError('Gemfire requires a raw 8 KiB battery image, without emulator/container headers.')
    blocks, invalid = [], []
    position = raw.find(b'KOEI')
    while position >= 0:
        base = position - MARKER
        try:
            if base < 0 or base + BLOCK_SIZE > SIZE:
                raise SaveError('Gemfire native KOEI footer has no complete state block.')
            players = _qualify_block(raw, base, ram_base, month_offset, player_offset)
        except SaveError as error:
            invalid.append((position, error))
        else:
            blocks.append((base, players))
        position = raw.find(b'KOEI', position + 4)
    for (base, _players), (following, _next_players) in zip(blocks, blocks[1:]):
        if following < base + BLOCK_SIZE:
            raise SaveError('Gemfire state blocks overlap.')
    for position, error in invalid:
        # A resource/stat edit or opaque in-record bytes can spell KOEI before
        # the real footer. Qualify all candidates first, then discard interior
        # occurrences; scanning order must not invent a second state block.
        if not any(base <= position and position + 4 <= base + BLOCK_SIZE
                   for base, _players in blocks):
            raise error
    if not blocks:
        raise SaveError('No qualified Gemfire native KOEI state block exists in this battery image.')
    return tuple(blocks)


class Backend:
    def __init__(self, game_id, platform, ram_base, extension, month_offset, player_offset):
        self.game_id, self.ram_base, self.extension = game_id, ram_base, extension
        self.month_offset, self.player_offset = month_offset, player_offset
        self.format = Format(game_id, f'Gemfire (USA {platform}, qualified battery records)',
                             'Raw 8 KiB battery image with existing qualified native state blocks. '
                             'Player-owned province gold, food, loyalty, farming and protection; '
                             'factions, leaders, armies, soldiers, calendar and unknown bytes preserved. '
                             'Public native routines establish the format; copied native gameplay '
                             'and game-load/re-save validation remain unverified.')

    def get_format(self, game_id=None):
        if game_id is not None and game_id != self.game_id:
            raise SaveError('Select the explicit Gemfire game/platform battery profile.')
        return self.format

    def qualified_blocks(self, raw):
        return qualified_blocks(raw, self.ram_base, self.month_offset, self.player_offset)

    def decode(self, raw, game_id=None, source=None):
        self.get_format(game_id)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) != SIZE:
            raise SaveError('Open a raw 8 KiB Gemfire battery image, not a ROM or emulator state.')
        raw = bytes(raw)
        self.qualified_blocks(raw)
        source = Path('copy' + self.extension) if source is None else Path(source)
        return Document(self.format, source, raw, raw)

    def validate_document(self, document):
        if (type(document) is not Document or document.format is not self.format
                or type(document.raw) is not bytes or type(document.payload) is not bytes
                or document.raw != document.payload):
            raise SaveError('The Gemfire opened snapshot was changed outside staging.')
        self.qualified_blocks(document.raw)

    def _suffix(self, path):
        if path.suffix.lower() != self.extension:
            raise SaveError(f'Use a separate raw Gemfire battery image with the {self.extension} extension.')
        return path.suffix.lower()

    def read_save(self, path, game_id=None):
        self.get_format(game_id)
        path = safe_path(path)
        self._suffix(path)
        with path.open('rb') as stream:
            raw = stream.read(SIZE + 1)
        return self.decode(raw, game_id, path)

    @lru_cache(maxsize=8)
    def _fields(self, raw):
        result = {}
        for base, players in self.qualified_blocks(raw):
            for province in range(PROVINCE_COUNT):
                record = base + PROVINCE_START + province * PROVINCE_STRIDE
                owner = raw[record + 14]
                # Foreign factions and empty provinces never become writable.
                if owner not in players:
                    continue
                group = f'State 0x{base:04X} · Province {province + 1:02} · faction {owner}'
                for key, label, relative, width, cap in (
                        ('gold', 'Gold', 2, 2, 999), ('food', 'Food', 4, 2, 999),
                        ('loyalty', 'Loyalty', 8, 1, 100), ('farming', 'Farming', 9, 1, 100),
                        ('protection', 'Protection', 10, 1, 100)):
                    field = Field(f'state_{base:04x}_province_{province}_{key}', label,
                                  record + relative, cap, group, province + 1, width)
                    result[field.id] = field
        return MappingProxyType(result)

    def field_map(self, document):
        self.validate_document(document)
        return self._fields(document.payload)

    def fields_for(self, document):
        return tuple(self.field_map(document).values())

    def changed_payload(self, document, changes):
        fields = self.field_map(document)
        if not isinstance(changes, Mapping):
            raise SaveError('Gemfire changes require a field/value mapping.')
        output = bytearray(document.payload)
        for key, value in changes.items():
            if type(key) is not str or key not in fields:
                raise SaveError('Unknown Gemfire field or province outside the saved player factions.')
            field = fields[key]
            if type(value) is int and value == field.value(document.payload):
                continue  # Exact typed unusual opened values remain no-ops.
            field.validate(value)
            output[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
        return bytes(output)

    def stage(self, document, changes, key, value):
        self.changed_payload(document, changes)
        fields = self.field_map(document)
        if type(key) is not str or key not in fields:
            raise SaveError('Unknown Gemfire field or province outside the saved player factions.')
        field, result = fields[key], dict(changes)
        if type(value) is int and value == field.value(document.payload):
            result.pop(key, None)
        else:
            field.validate(value)
            result[key] = value
        return result

    def serialize(self, document, changes):
        output = self.changed_payload(document, changes)
        if output == document.raw:
            return document.raw
        # Native writer is a complete block copy; there is no additional native
        # sum/signature layer. Requalify every block and all untouched bytes.
        return self.decode(output).raw

    def review(self, document, changes):
        self.changed_payload(document, changes)
        return [(field, field.value(document.payload), changes[field.id])
                for field in self.fields_for(document) if field.id in changes]

    def limit_values(self, document, changes, keys):
        self.changed_payload(document, changes)
        fields, result = self.field_map(document), {}
        for key in keys:
            if type(key) is not str or key not in fields:
                raise SaveError('Unknown Gemfire province field.')
            field = fields[key]
            if field.maxable:
                result[key] = max(field.value(document.payload), changes.get(key, 0), field.maximum)
        return result

    def maximums(self, document, changes, group=None):
        self.changed_payload(document, changes)
        fields = [field for field in self.fields_for(document)
                  if field.maxable and (group is None or field.group == group)]
        result = dict(changes)
        for key, value in self.limit_values(document, changes, [field.id for field in fields]).items():
            result = self.stage(document, result, key, value)
        return result

    def _source(self, document):
        path = safe_path(document.source)
        try:
            with path.open('rb') as stream:
                raw = stream.read(SIZE + 1)
        except OSError as error:
            raise SaveError('The opened Gemfire battery copy is unavailable; reopen it.') from error
        if raw != document.raw:
            raise SaveError('The opened Gemfire battery copy changed on disk; reopen it.')
        return path

    def backup(self, document):
        self.validate_document(document)
        path = self._source(document)
        return snapshot_backup(document.raw, path, self.game_id,
                               safe_path(path.parent / 'WarriorsEditorBackups'))

    def save_as(self, document, changes, destination):
        self.validate_document(document)
        destination = safe_path(destination)
        self._suffix(destination)
        if destination.exists():
            raise FileExistsError('Choose a new destination; existing files are never replaced.')
        self._source(document)
        raw = self.serialize(document, changes)
        self.backup(document)
        self._source(document)
        atomic_new(raw, destination)
        with destination.open('rb') as stream:
            written = stream.read(SIZE + 1)
        if written != raw:
            raise SaveError('Gemfire saved bytes failed on-disk verification.')
        return self.decode(written, source=destination)

    def restore(self, backup_path, destination, game_id=None):
        self.get_format(game_id)
        backup_path, destination = safe_path(backup_path), safe_path(destination)
        suffix = self._suffix(backup_path)
        self._suffix(destination)
        return restore_snapshot(backup_path, destination, self.game_id, suffix, SIZE,
                                validate_raw=self.decode)

    def province_records(self, document):
        self.validate_document(document)
        result = []
        for base, players in self.qualified_blocks(document.raw):
            for province in range(PROVINCE_COUNT):
                record = base + PROVINCE_START + province * PROVINCE_STRIDE
                owner = document.raw[record + 14]
                result.append((f'0x{base:04X}', province + 1, owner,
                               _word(document.raw, record + 2), _word(document.raw, record + 4),
                               _word(document.raw, record + 6), *document.raw[record + 8:record + 11],
                               'Player province' if owner in players else 'Read only'))
        return tuple(result)

    @staticmethod
    def record_label(slot, group):
        return group

    def field_hint(self, document, key):
        if type(key) is not str or key not in self.field_map(document):
            raise SaveError('Unknown Gemfire province field.')
        return ('Existing province in a saved player faction. Gold/food cap at 999; loyalty, '
                'farming and protection at 100. Max preserves higher opened values. '
                'Soldiers, army deployment, leader stats, factions, gems and calendar are preserved.')

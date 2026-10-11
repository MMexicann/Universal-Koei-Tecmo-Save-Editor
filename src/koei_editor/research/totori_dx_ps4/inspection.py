"""Bounded Totori DX PS4 research inspection; deliberately provides no writer.

Native public CUSA14014/GAMEDATA00 exports corroborate the exact framing and
read-only Cole/character/item leads. Game-internal integrity remains unresolved.
PS4 PFS removal and signing remain external. No PC or PS3 support is implied.
"""
from dataclasses import dataclass
import math
import struct

from koei_editor.games.dw3.models import SaveError

SAVE_SIZE = 380928
MAGIC = 20100403
HEADER_SIZE = 32
MAX_SFO_SIZE = 4096
TITLE_ID = 'CUSA14014'
SAVE_DIRECTORY = 'GAMEDATA00'
CHUNK_SIZES = (
    40848, 5172, 4, 3972, 152520, 51, 57164, 4, 5632, 1, 24,
    68, 940, 1616, 8, 4536, 400, 1836, 15013, 168, 112, 64,
)
TRAILER_TAG = 1024
TRAILER_SIZE = 90567  # Includes its eight-byte header.
ITEM_SIZE = 52
BASKET_COUNT = 100
CONTAINER_COUNT = 999
CHARACTER_COUNT = 10
CHARACTER_SIZE = 396


@dataclass(frozen=True)
class Chunk:
    tag: int
    header_offset: int
    payload_offset: int
    size: int


@dataclass(frozen=True)
class ItemLead:
    """Observed record geometry, not editable ownership/applicability proof."""
    collection: str
    index: int
    offset: int
    instance_id: int
    item_id: int
    quality_bits: int
    traits: tuple[int, ...]
    effects: tuple[int, ...]
    tail: int

    @property
    def quality(self):
        return struct.unpack('<f', struct.pack('<I', self.quality_bits))[0]

    @property
    def canonical_empty(self):
        return (self.instance_id == self.item_id == -1 and self.quality == 50.0
                and self.traits == (-1,) * 5 and self.effects == (-1,) * 4
                and self.tail == -1)

    @property
    def ordinary_shape(self):
        return (self.instance_id >= 0 and self.item_id >= 0
                and math.isfinite(self.quality) and 1 <= self.quality <= 120
                and all(-1 <= value < 204 for value in self.traits)
                and all(-1 <= value < 223 for value in self.effects)
                and -1 <= self.tail <= 0xFFFF)


@dataclass(frozen=True)
class CharacterLead:
    """Native correlations; EXP dependencies and skill updates are unqualified."""
    index: int
    offset: int
    stored_id: int
    stored_level: int
    stored_exp: int
    stored_stat_bonuses: tuple[int, ...]


@dataclass(frozen=True)
class Inspection:
    raw: bytes
    title_id: str
    save_directory: str
    chunks: tuple[Chunk, ...]
    trailer_offset: int
    trailer_size: int
    cole: int
    characters: tuple[CharacterLead, ...]
    items: tuple[ItemLead, ...]
    basket_limit: int
    container_limit: int
    alchemy_exp_lead: int
    adventurer_points_lead: int
    zero_based_calendar_lead: tuple[int, int, int]
    editable: bool = False
    qualified_game_profile: bool = False
    integrity_qualified: bool = False


def identity(sfo: bytes) -> tuple[str, str]:
    """Select title/directory only; never retain account, signing or preview data."""
    if type(sfo) is not bytes or not 20 <= len(sfo) <= MAX_SFO_SIZE:
        raise SaveError('Totori PS4 metadata requires immutable, bounded SFO bytes.')
    magic, version, keys, data, count = struct.unpack_from('<5I', sfo)
    if (magic != 0x46535000 or version != 0x101 or count > 128
            or not 20 + count * 16 <= keys <= data <= len(sfo)):
        raise SaveError('Totori PS4 metadata header is malformed.')
    selected = {}
    for index in range(count):
        key_relative, encoding, length, capacity, relative = struct.unpack_from(
            '<HHIII', sfo, 20 + 16 * index)
        start = keys + key_relative
        if not keys <= start < data:
            raise SaveError('Totori PS4 metadata key is outside the key table.')
        end = sfo.find(b'\0', start, data)
        if end < 0:
            raise SaveError('Totori PS4 metadata key is unterminated.')
        key = sfo[start:end]
        if key not in (b'TITLE_ID', b'SAVEDATA_DIRECTORY'):
            continue
        position = data + relative
        if (key in selected or encoding != 0x204
                or not 1 <= length <= capacity <= 128
                or position + capacity > len(sfo)):
            raise SaveError('Totori PS4 title/directory identity is malformed.')
        value = sfo[position:position + length]
        if value[-1:] != b'\0' or b'\0' in value[:-1]:
            raise SaveError('Totori PS4 title/directory identity is unterminated.')
        try:
            selected[key] = value[:-1].decode('ascii')
        except UnicodeDecodeError as error:
            raise SaveError('Totori PS4 title/directory identity must be ASCII.') from error
    result = (selected.get(b'TITLE_ID'), selected.get(b'SAVEDATA_DIRECTORY'))
    if result != (TITLE_ID, SAVE_DIRECTORY):
        raise SaveError('Only CUSA14014 GAMEDATA00 Totori DX gameplay is qualified for inspection.')
    return result


def _inspect(raw: bytes, context: tuple[str, str]) -> Inspection:
    if (type(raw) is not bytes or len(raw) != SAVE_SIZE
            or context != (TITLE_ID, SAVE_DIRECTORY)):
        raise SaveError('Totori PS4 inspection requires exact-size immutable gameplay bytes and title context.')
    if struct.unpack_from('<I', raw)[0] != MAGIC:
        raise SaveError('Unrecognized Totori PS4 candidate header.')
    offset = HEADER_SIZE
    chunks = []
    for expected_tag, expected_size in enumerate(CHUNK_SIZES, 1):
        if offset > len(raw) - 8:
            raise SaveError('Truncated Totori PS4 candidate chunk header.')
        tag, size = struct.unpack_from('<II', raw, offset)
        if (tag != expected_tag or size != expected_size
                or size > len(raw) - offset - 8):
            raise SaveError('Unrecognized Totori PS4 candidate chunk layout.')
        chunks.append(Chunk(tag, offset, offset + 8, size))
        offset += 8 + size
    tag, size = struct.unpack_from('<II', raw, offset)
    if (tag != TRAILER_TAG or size != TRAILER_SIZE
            or size != len(raw) - offset):
        raise SaveError('Unrecognized Totori PS4 candidate trailer bounds.')
    characters = tuple(CharacterLead(index, chunks[3].payload_offset + index * CHARACTER_SIZE,
                       *struct.unpack_from('<3i', raw, chunks[3].payload_offset + index * CHARACTER_SIZE),
                       struct.unpack_from('<6i', raw, chunks[3].payload_offset + index * CHARACTER_SIZE + 0x34))
                       for index in range(CHARACTER_COUNT))
    items = []
    for index in range(BASKET_COUNT + CONTAINER_COUNT):
        position = chunks[6].payload_offset + index * ITEM_SIZE
        instance, item, quality_bits, *rest = struct.unpack_from('<iiI10i', raw, position)
        collection = 'Basket' if index < BASKET_COUNT else 'Container'
        local_index = index if index < BASKET_COUNT else index - BASKET_COUNT
        items.append(ItemLead(collection, local_index, position, instance, item,
                              quality_bits, tuple(rest[:5]), tuple(rest[5:9]), rest[9]))
    limits_position = chunks[6].payload_offset + (BASKET_COUNT + CONTAINER_COUNT) * ITEM_SIZE
    basket, container = struct.unpack_from('<2i', raw, limits_position)
    return Inspection(raw, *context, tuple(chunks), offset, size,
                      struct.unpack_from('<I', raw, chunks[2].payload_offset)[0],
                      characters, tuple(items), basket, container,
                      struct.unpack_from('<I', raw, chunks[14].payload_offset + 4)[0],
                      struct.unpack_from('<I', raw, chunks[17].payload_offset)[0],
                      struct.unpack_from('<3I', raw, chunks[10].payload_offset + 8))


def inspect(raw: bytes, sfo: bytes) -> Inspection:
    """Read exact framing with required PS4 title context; no integrity claim."""
    return _inspect(raw, identity(sfo))


def unchanged(document: Inspection) -> bytes:
    """A byte-exact no-edit research roundtrip, never an edited save writer."""
    if (type(document) is not Inspection or _inspect(document.raw,
            (document.title_id, document.save_directory)) != document):
        raise SaveError('Totori PS4 candidate inspection was changed or forged.')
    return document.raw

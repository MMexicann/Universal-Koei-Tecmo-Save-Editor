"""Native tagged pools qualified independently in two public USER revisions.

The published inventory bases are deliberately not used. Each qualified profile
requires the actual native tag, both lengths and its adjacent pool boundary.
Item names/IDs below are factual corroborations, not an imported catalog.
"""
from dataclasses import dataclass
from functools import lru_cache
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.nioh3 import codec
from koei_editor.shared.verified_editor import Field


COMMON_ITEMS = {
    0x05E7: 'Elixir',
    0x382A: 'Sacred Water',
    0xF3EE: 'Arrow',
    0xA70B: 'Incendiary Arrow',
    0xF8DD: 'Ochoko Cup',
    0x8A41: 'Salt',
    0x79CF: 'Rifle Ammunition',
    0x6514: 'Antidote',
    0xFA6E: 'Antiparalytic Needle',
    0x96A7: 'Arrowproof Amulet',
    0x4E22: "Daion-Jin's Sake",
    0xE7D3: 'Dung Ball',
    0x4D66: 'Fireproof Amulet',
    0xFC7A: 'Sacred Ash',
    0x5A51: 'Smoke Ball',
    0x4C5F: 'Throwing Stone',
    0x5943: 'Travel Amulet',
    0x304E: 'Water Amulet',
    0x2296: 'Yokai Water Pot',
    0x683B: 'Scampuss Furball',
    0x3F5A: "Summoner's Candle",
    0x140F: 'Righteous Jasper',
    0xCC42: 'Power Pill',
    0x059A: 'Lantern Plant Fruit',
    0x3299: 'Steel Pill',
    0xE4AA: 'Luckbringer Amulet',
    0x3A1B: 'Uchiko Powder',
    0x9509: 'Fragrant Wood',
    0x65B4: 'Healing Pill',
    0x5EDB: 'Tiger-Running Amulet',
    0x7EA2: 'Sacred Brush',
    0xF681: 'Herbal Remedy',
}


@dataclass(frozen=True)
class Pool:
    id: str
    title: str
    tag_offset: int
    tag: int
    count: int
    stride: int

    @property
    def start(self):
        return self.tag_offset + 12

    @property
    def end(self):
        return self.start + self.count * self.stride


POOLS = (
    Pool('equipment', 'Equipment', 0x240349, 0x938A61DD, 2500, 0xF0),
    Pool('inventory', 'Item box', 0x2D2B15, 0xE255E585, 1500, 0xE8),
    Pool('storehouse', 'Storehouse', 0x327A81, 0x7E3D5D38, 400, 0xE8),
)
# Explicit native revision profiles, even though these acquired revisions share
# the same pool layout. This is not a promise about another game build/revision.
REVISION_POOLS = {revision: POOLS for revision in codec.SUPPORTED_REVISIONS}
FOLLOWING_TAG = (0x33E50D, 0xAD8691AB, 4)


@lru_cache(maxsize=2)
def pools_for(payload, revision):
    if revision not in REVISION_POOLS:
        raise SaveError('Nioh 3 inventory revision has no qualified native pool map.')
    pools = REVISION_POOLS[revision]
    for index, pool in enumerate(pools):
        expected_size = pool.count * pool.stride
        if struct.unpack_from('<III', payload, pool.tag_offset) != (
                pool.tag, expected_size + 4, expected_size):
            raise SaveError('Nioh 3 native inventory tag or array lengths do not match the revision.')
        # A matching byte sequence elsewhere does not relocate or qualify a pool.
        expected_next = pools[index + 1].tag_offset if index + 1 < len(pools) else FOLLOWING_TAG[0]
        if pool.end != expected_next:
            raise SaveError('Nioh 3 native inventory array boundaries are inconsistent.')
    if struct.unpack_from('<II', payload, FOLLOWING_TAG[0]) != FOLLOWING_TAG[1:]:
        raise SaveError('Nioh 3 native storehouse boundary marker is invalid.')
    return pools


def records(payload, pool):
    for slot in range(pool.count):
        offset = pool.start + slot * pool.stride
        identity = struct.unpack_from('<H', payload, offset)[0]
        if identity:
            yield slot, offset, identity


@lru_cache(maxsize=2)
def fields(payload, revision):
    result = []
    for pool in pools_for(payload, revision):
        if pool.id == 'equipment':
            continue
        identities = set()
        for slot, offset, identity in records(payload, pool):
            if identity not in COMMON_ITEMS:
                continue
            if identity in identities:
                raise SaveError('Nioh 3 has ambiguous duplicate common-item records in one pool.')
            identities.add(identity)
            appearance, quantity, level, pre_forge, plus = struct.unpack_from('<5H', payload, offset + 2)
            instance = struct.unpack_from('<H', payload, offset + 0x1C)[0]
            # Existing positive ordinary stacks only. Refashioned/nonordinary
            # shapes and zero/empty rows cannot authorize ownership creation.
            if (appearance != identity or not quantity or not instance
                    or level or pre_forge or plus):
                continue
            result.append(Field(f'{pool.id}_{slot}_quantity', COMMON_ITEMS[identity] + ' quantity',
                                offset + 4, 2, quantity, pool.title, slot + 1,
                                minimum=1, maxable=False))
    return tuple(result)

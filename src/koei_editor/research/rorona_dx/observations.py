"""Read-only gameplay leads for the observed Rorona DX PC layout.

These observations deliberately provide no ScalarField, staging or writer API.
They help qualify existing records against an independently captured native
loader or controlled action pair. Native integrity is still unproved.
"""
from dataclasses import dataclass
import struct

from .inspection import Inspection, unchanged


CHARACTER_COUNT = 12
CHARACTER_STRIDE = 0x1F4
ITEM_COUNT = 2100
ITEM_STRIDE = 0x30


@dataclass(frozen=True)
class CharacterLead:
    slot: int
    offset: int
    native_id: int
    second_word: int
    experience: int


@dataclass(frozen=True)
class ItemLead:
    slot: int
    offset: int
    record_word: int
    item_word: int
    quality_bits: int
    quality: float
    following_words: tuple[int, ...]

    @property
    def empty_marker(self) -> bool:
        """Observed two-word empty marker; this is not an ownership proof."""
        return self.record_word == -1 and self.item_word == -1


@dataclass(frozen=True)
class GameplayLeads:
    cole: int
    characters: tuple[CharacterLead, ...]
    items: tuple[ItemLead, ...]


def observe(document: Inspection) -> GameplayLeads:
    """Read early corroborated leads, preserving all unusual raw values.

    PS3 Plus facts corroborate Cole, EXP and the float quality position only.
    The two record words and remaining following words are explicitly unnamed:
    they must not become PC item creation, ownership or trait dropdowns.
    """
    raw = unchanged(document)
    character_base = document.chunks[3].payload_offset
    item_base = document.chunks[6].payload_offset
    characters = tuple(
        CharacterLead(slot, character_base + slot * CHARACTER_STRIDE,
                      *struct.unpack_from('<iii', raw,
                                          character_base + slot * CHARACTER_STRIDE))
        for slot in range(CHARACTER_COUNT)
    )
    items = []
    for slot in range(ITEM_COUNT):
        offset = item_base + slot * ITEM_STRIDE
        record_word, item_word, quality_bits = struct.unpack_from('<iiI', raw, offset)
        quality = struct.unpack_from('<f', raw, offset + 8)[0]
        following = struct.unpack_from('<9i', raw, offset + 12)
        items.append(ItemLead(slot, offset, record_word, item_word,
                              quality_bits, quality, following))
    return GameplayLeads(struct.unpack_from('<I', raw,
                                            document.chunks[2].payload_offset)[0],
                         characters, tuple(items))

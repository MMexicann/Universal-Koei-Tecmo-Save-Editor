"""Inspect the bounded PC layout observed in two independent public save sources.

Native integrity and gameplay field dependencies remain unqualified. This module
cannot edit, reseal or write a save. See docs/ARLAND_DX_RESEARCH.md.
"""
from dataclasses import dataclass
import struct

from koei_editor.games.dw3.models import SaveError


SAVE_SIZE = 558080
MAGIC = 20100403
HEADER_SIZE = 32
CHUNK_SIZES = (
    46120, 6972, 4, 5628, 179724, 121, 100768, 4, 6968, 1, 8,
    68, 604, 2220, 8, 3584, 95968, 1469, 84, 384, 94260, 4800,
    128, 80,
)
TRAILER_TAG = 1024
TRAILER_SIZE = 7881  # Includes the trailer's eight-byte header.


@dataclass(frozen=True)
class Chunk:
    tag: int
    header_offset: int
    payload_offset: int
    size: int


@dataclass(frozen=True)
class Inspection:
    raw: bytes
    chunks: tuple[Chunk, ...]
    trailer_offset: int
    trailer_size: int
    editable: bool = False
    qualified_game_profile: bool = False
    integrity_qualified: bool = False


@dataclass(frozen=True)
class ColeLead:
    """Observed currency candidate; this is not an editable scalar field.

    The two independently authored clear copies correlate this standalone
    tag-three word with their resource descriptions. Native loader integrity
    and a controlled purchase/sale pair are still missing.
    """
    offset: int
    value: int
    byteorder: str = 'little'
    width: int = 4
    editable: bool = False
    maxable: bool = False


def inspect(raw: bytes) -> Inspection:
    """Require the complete observed tag/length fingerprint; preserve all payloads."""
    if type(raw) is not bytes or len(raw) != SAVE_SIZE:
        raise SaveError('Meruru DX layout inspection requires immutable, exact-size candidate bytes.')
    if struct.unpack_from('<I', raw)[0] != MAGIC:
        raise SaveError('Unrecognized Meruru DX candidate header.')
    offset = HEADER_SIZE
    chunks = []
    for expected_tag, expected_size in enumerate(CHUNK_SIZES, 1):
        if offset > len(raw) - 8:
            raise SaveError('Truncated Meruru DX candidate chunk header.')
        tag, size = struct.unpack_from('<II', raw, offset)
        if tag != expected_tag or size != expected_size or size > len(raw) - offset - 8:
            raise SaveError('Unrecognized Meruru DX candidate chunk layout.')
        chunks.append(Chunk(tag, offset, offset + 8, size))
        offset += 8 + size
    if offset > len(raw) - 8:
        raise SaveError('Missing Meruru DX candidate trailer.')
    tag, size = struct.unpack_from('<II', raw, offset)
    if tag != TRAILER_TAG or size != TRAILER_SIZE or size != len(raw) - offset:
        raise SaveError('Unrecognized Meruru DX candidate trailer bounds.')
    return Inspection(raw, tuple(chunks), offset, size)


def unchanged(inspection: Inspection) -> bytes:
    """Return the exact original after rechecking a read-only research snapshot."""
    if type(inspection) is not Inspection or inspect(inspection.raw) != inspection:
        raise SaveError('Meruru DX candidate inspection was changed or forged.')
    return inspection.raw


def cole_lead(inspection: Inspection) -> ColeLead:
    """Read tag three only after validating the complete immutable snapshot.

    In particular, this does not accept a lone magic/offset, assume that the
    zero trailer proves absent checksums, clamp large balances, or provide a
    writer. Returning an observation does not qualify a game-library card.
    """
    raw = unchanged(inspection)
    chunk = inspection.chunks[2]
    return ColeLead(chunk.payload_offset, struct.unpack_from('<I', raw, chunk.payload_offset)[0])

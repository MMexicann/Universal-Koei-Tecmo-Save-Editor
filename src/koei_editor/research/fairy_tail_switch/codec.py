"""Independently recovered native FAIRY TAIL Switch block integrity.

Only framing and checksums are qualified. These primitives deliberately contain
no gameplay field offsets or GUI adapter: a validated envelope alone does not
authorize edits to inventory identities, quantities, rewards or character data.
"""

from dataclasses import dataclass
import struct

from koei_editor.games.dw3.models import SaveError


MAX_SIZE = 2 * 1024 * 1024
HEADER_SIZE = 20
OUTER_SIGNATURE = b'#USR'
OUTER_REVISION = 0x10001
# Exact independently observed leaf revisions and fixed extents. Variable
# inventory/quest/retry extents remain strictly bounded by their native frames.
BLOCK_LAYOUT = (
    (b'#NFD', 0x40001, 5280),
    (b'#PRD', 0xA0001, 2609),
    (b'#QUD', 0x50001, None),
    (b'#PTD', 0xD0001, 7784),
    (b'#IND', 0x10001, None),
    (b'#PLD', 0x90001, 631),
    (b'#GLD', 0x20001, 3492),
    (b'#STD', 0x30001, 10470),
    (b'#CTD', 1, 4),
    (b'#RTD', 0x10001, None),
)


@dataclass(frozen=True)
class Block:
    signature: bytes
    start: int
    body_start: int
    end: int
    revision: int
    checksum: int
    body: bytes


@dataclass(frozen=True)
class Envelope:
    raw: bytes
    outer: Block
    blocks: tuple[Block, ...]


def signed_fnv1a(data):
    """32-bit FNV-1a with native signed-char extension before XOR."""
    if type(data) is not bytes:
        raise SaveError('Native checksum input must be immutable bytes.')
    value = 0x811C9DC5
    for byte in data:
        signed = byte if byte < 128 else byte - 256
        value = ((value ^ signed) * 0x1000193) & 0xFFFFFFFF
    return value


def _block(raw, start, boundary):
    if start < 0 or start + HEADER_SIZE > boundary:
        raise SaveError('Truncated FAIRY TAIL native block header.')
    signature, header_size, size, revision, checksum = struct.unpack_from(
        '<4sIIII', raw, start)
    if header_size != HEADER_SIZE or size > MAX_SIZE:
        raise SaveError('Unsupported FAIRY TAIL native block framing.')
    body_start = start + HEADER_SIZE
    end = body_start + size
    if end > boundary:
        raise SaveError('FAIRY TAIL block extends beyond its parent.')
    body = raw[body_start:end]
    if signed_fnv1a(body) != checksum:
        raise SaveError('FAIRY TAIL native block checksum failed.')
    return Block(signature, start, body_start, end, revision, checksum, body)


def decode(raw):
    if type(raw) is not bytes or not HEADER_SIZE <= len(raw) <= MAX_SIZE:
        raise SaveError('Requires bounded immutable native FAIRY TAIL slot bytes.')
    outer = _block(raw, 0, len(raw))
    if (outer.signature != OUTER_SIGNATURE or outer.revision != OUTER_REVISION
            or outer.end != len(raw)):
        raise SaveError('Not the supported original FAIRY TAIL Switch slot framing.')
    blocks = []
    position = outer.body_start
    for signature, revision, fixed_size in BLOCK_LAYOUT:
        block = _block(raw, position, outer.end)
        if block.signature != signature or block.revision != revision:
            raise SaveError('Unsupported FAIRY TAIL native leaf order or revision.')
        if fixed_size is not None and len(block.body) != fixed_size:
            raise SaveError('Unsupported FAIRY TAIL native leaf extent.')
        blocks.append(block)
        position = block.end
    if position != outer.end:
        raise SaveError('Unexpected extra FAIRY TAIL native slot blocks.')
    return Envelope(raw, outer, tuple(blocks))


def encode(envelope):
    """Unchanged roundtrip only, until gameplay mappings are qualified."""
    if type(envelope) is not Envelope or decode(envelope.raw) != envelope:
        raise SaveError('Requires an unchanged validated native slot envelope.')
    return envelope.raw


def checksum_patch(raw, block_signature, body):
    """Research-only same-extent leaf replacement with required native hashes.

    This is intentionally not a registered editor backend. A future parser must
    authorize individual gameplay fields before calling this low-level codec.
    All unrelated headers, payloads and their hashes remain byte-identical.
    """
    envelope = decode(raw)
    if type(block_signature) is not bytes or type(body) is not bytes:
        raise SaveError('A native leaf signature and immutable replacement are required.')
    selected = next((block for block in envelope.blocks
                     if block.signature == block_signature), None)
    if selected is None or len(body) != len(selected.body):
        raise SaveError('Only an existing same-extent native leaf can be replaced.')
    if body == selected.body:
        return raw
    output = bytearray(raw)
    output[selected.body_start:selected.end] = body
    struct.pack_into('<I', output, selected.start + 16, signed_fnv1a(body))
    struct.pack_into('<I', output, 16, signed_fnv1a(bytes(output[HEADER_SIZE:])))
    result = bytes(output)
    decode(result)
    return result

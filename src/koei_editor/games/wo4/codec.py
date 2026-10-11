"""Native WO4/WO4 Ultimate PC two-block AES envelope.

Independently recovered from static DLL instructions. The encrypted fingerprint
is only a final-block marker, not a checksum of the gameplay bytes. Callers must
separately qualify the exact edition/revision and serializer before editing.
"""
from dataclasses import dataclass
import struct

from koei_editor.games.dw3.save_codec import CNG_AES

SYSTEM_PAYLOAD_SIZE = 0x6E714
PLAY_PAYLOAD_SIZE = 0x7400F
SYSTEM_BLOCK_SIZE = 0x6E734
PLAY_BLOCK_SIZE = 0x74024
FILE_SIZE = SYSTEM_BLOCK_SIZE + PLAY_BLOCK_SIZE
PAYLOAD_SIZE = SYSTEM_PAYLOAD_SIZE + PLAY_PAYLOAD_SIZE
FINGERPRINT = b'FingerPrint01234'
# Low DWORD after ten ordered x=(3.66*x)*(1-x) operations, beginning
# at (block_index+1)*0.5*0.5. System index1, gameplay index0.
KEY_SEEDS = (0x77318BB8, 0x3A211944)
SPECS = ((1, 0, SYSTEM_BLOCK_SIZE, SYSTEM_PAYLOAD_SIZE),
         (0, SYSTEM_BLOCK_SIZE, PLAY_BLOCK_SIZE, PLAY_PAYLOAD_SIZE))


def _bytes(seed, multiplier, increment, shift):
    output = bytearray()
    for _ in range(16):
        seed = (seed * multiplier + increment) & 0xFFFFFFFF
        output.append((seed >> shift) & 255)
    return bytes(output)


def key_for_block(index):
    if type(index) is not int or index not in (0, 1):
        raise ValueError('Native WO4 key index must be 0 or 1.')
    return _bytes(KEY_SEEDS[index], 0x343FD, 0x269EC3, 24)


def iv_from_seed(seed):
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError('Native WO4 IV seed must be an unsigned DWORD.')
    return _bytes(seed, 0x15A4E35, 1, 16)


@dataclass(frozen=True)
class Block:
    index: int
    file_offset: int
    iv_seed: int
    payload: bytes
    padding: bytes


def decode(raw):
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != FILE_SIZE:
        raise ValueError('Native WO4 PC container must contain exactly 927,576 bytes.')
    raw = bytes(raw)
    blocks = []
    with CNG_AES('CBC') as aes:
        for index, offset, size, payload_size in SPECS:
            seed = struct.unpack_from('<I', raw, offset + size - 4)[0]
            plain = aes.transform(raw[offset:offset + size - 4], key_for_block(index),
                                  direction='decrypt', iv=iv_from_seed(seed))
            if plain[-16:] != FINGERPRINT:
                raise ValueError('Native WO4 encrypted fingerprint failed.')
            blocks.append(Block(index, offset, seed, plain[:payload_size], plain[payload_size:-16]))
    return tuple(blocks)


def encode(blocks):
    if type(blocks) is not tuple or len(blocks) != 2:
        raise ValueError('Native WO4 encoding requires two immutable blocks.')
    for block, (index, offset, size, payload_size) in zip(blocks, SPECS):
        if (type(block) is not Block or type(block.index) is not int
                or type(block.file_offset) is not int or block.index != index
                or block.file_offset != offset or type(block.payload) is not bytes
                or len(block.payload) != payload_size or type(block.padding) is not bytes
                or len(block.padding) != size - 4 - 16 - payload_size):
            raise ValueError('Native WO4 block geometry changed.')
        iv_from_seed(block.iv_seed)
    output = bytearray()
    with CNG_AES('CBC') as aes:
        for block in blocks:
            plain = block.payload + block.padding + FINGERPRINT
            output.extend(aes.transform(plain, key_for_block(block.index),
                                        direction='encrypt', iv=iv_from_seed(block.iv_seed)))
            output.extend(struct.pack('<I', block.iv_seed))
    return bytes(output)

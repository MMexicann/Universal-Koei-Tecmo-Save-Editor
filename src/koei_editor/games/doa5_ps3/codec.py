"""Independently implemented native DOA5 PS3 word cipher and block sums.

Format facts are corroborated with public original-title console exports and
Bucanero/alfizari's documented DOA5 codec. No third-party source is included.
The PS3 PFD encryption/signature layer remains external to this native file.
"""
import struct

from koei_editor.games.dw3.models import SaveError

SAVE_SIZE = 43068
BLOCKS = ((0, 0x1548), (0x1548, 0x92F4))
REVISION_PREFIX = bytes.fromhex('00060100000100000008646464000000')


def _shape(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE:
        raise SaveError('Requires the original DOA5 PS3 43,068-byte native SAVE_SYS.DAT layout.')
    for offset, size in BLOCKS:
        magic, stored_size = struct.unpack_from('>II', raw, offset)
        if magic != 0 or stored_size != size:
            raise SaveError('DOA5 PS3 block identity or revision does not match.')


def _transform(raw):
    """XOR each big-endian word with its block's evolving original seed."""
    output = bytearray(raw)
    for offset, size in BLOCKS:
        state = struct.unpack_from('>I', raw, offset + 12)[0]
        for position in range(offset + 16, offset + size, 4):
            word = struct.unpack_from('>I', raw, position)[0]
            struct.pack_into('>I', output, position, word ^ state)
            state = ((state << 4) + (state >> 4)) & 0xFFFFFFFF
    return bytes(output)


def decode(raw):
    _shape(raw)
    for offset, size in BLOCKS:
        stored = struct.unpack_from('>I', raw, offset + 8)[0]
        if stored != (sum(raw[offset + 16:offset + size]) & 0xFFFFFFFF):
            raise SaveError('DOA5 native encrypted-block checksum failed.')
    payload = _transform(raw)
    if payload[16:32] != REVISION_PREFIX:
        raise SaveError('DOA5 original PS3 native revision fingerprint does not match.')
    return payload


def encode(payload):
    _shape(payload)
    if payload[16:32] != REVISION_PREFIX:
        raise SaveError('DOA5 original PS3 native revision fingerprint does not match.')
    output = bytearray(_transform(payload))
    for offset, size in BLOCKS:
        struct.pack_into('>I', output, offset + 8,
                         sum(output[offset + 16:offset + size]) & 0xFFFFFFFF)
    encoded = bytes(output)
    decoded = decode(encoded)
    # Native stored checksums describe encrypted block bytes. Their header
    # words are the only differences permitted when plaintext edits are sealed.
    expected = bytearray(payload)
    for offset, _ in BLOCKS:
        expected[offset + 8:offset + 12] = decoded[offset + 8:offset + 12]
    if decoded != bytes(expected):
        raise SaveError('DOA5 native codec revalidation failed.')
    return encoded

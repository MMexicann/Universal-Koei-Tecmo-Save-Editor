"""Ultimate revision gate around independently recovered native PC framing."""
from dataclasses import replace
from functools import lru_cache
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo4 import codec as envelope

FILE_SIZE = envelope.FILE_SIZE
SYSTEM_PAYLOAD_SIZE = envelope.SYSTEM_PAYLOAD_SIZE
PLAY_PAYLOAD_SIZE = envelope.PLAY_PAYLOAD_SIZE
PAYLOAD_SIZE = envelope.PAYLOAD_SIZE
REVISION = 20200101
SYSTEM_RESERVED_SIZE, PLAY_RESERVED_SIZE = 0x6051E, 0xF000


def validate_payload(payload):
    if type(payload) is not bytes or len(payload) != PAYLOAD_SIZE:
        raise SaveError('The complete native Ultimate system and gameplay payloads are required.')
    if struct.unpack_from('<I', payload)[0] != REVISION:
        raise SaveError('This is not the supported Ultimate PC system revision 20200101.')
    if struct.unpack_from('<II', payload, 4) != (0, 0):
        raise SaveError('The supported Ultimate PC profile requires the qualified native 0/0 header layout.')
    system = payload[:SYSTEM_PAYLOAD_SIZE]
    gameplay = payload[SYSTEM_PAYLOAD_SIZE:]
    # Native serializers23CE24/23CAC5 explicitly emit these reserved regions as
    # zeros. Reject corruption here without rewriting or normalizing input.
    if any(system[-SYSTEM_RESERVED_SIZE:]) or any(gameplay[-PLAY_RESERVED_SIZE:]):
        raise SaveError('Native Ultimate reserved serializer regions are invalid.')


def decode(raw):
    if type(raw) is not bytes:
        raise SaveError('An immutable complete native Ultimate PC file is required.')
    return _decode(raw)


@lru_cache(maxsize=4)
def _decode(raw):
    try:
        blocks = envelope.decode(raw)
    except ValueError as error:
        raise SaveError(str(error)) from error
    payload = b''.join(block.payload for block in blocks)
    validate_payload(payload)
    return payload


def encode(original, payload):
    opened = decode(original)
    validate_payload(payload)
    if payload == opened:
        return original
    blocks = envelope.decode(original)
    blocks = (replace(blocks[0], payload=payload[:SYSTEM_PAYLOAD_SIZE]),
              replace(blocks[1], payload=payload[SYSTEM_PAYLOAD_SIZE:]))
    try:
        return envelope.encode(blocks)
    except ValueError as error:
        raise SaveError(str(error)) from error

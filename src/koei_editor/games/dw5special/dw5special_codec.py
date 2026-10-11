"""Qualified native Windows Special headers, plaintext with a byte-sum trailer.

Format facts independently corroborated by a contemporary native-save guide,
static inspection of its separate editor's I/O, and a genuine shared PC save.
No game or third-party editor is executed. No third-party code is included.
"""
from functools import lru_cache

from koei_editor.games.dw3.models import SaveError

SAVE_SIZE = 0xB3B0
CHECKSUM_OFFSET = 0xB390
REVISION = b'\x03\0\0\0'
# Both exact markers have independently checksum-valid native copies with the
# same officer, item and weapon layout. The upper word's meaning is unproved;
# preserve it, rather than interpreting it as a region or normalizing it.
SUPPORTED_REVISION_MARKERS = (REVISION, b'\x03\0\x01\0')


def freeze(raw):
    if type(raw) not in (bytes, bytearray, memoryview):
        raise SaveError('A native Windows DW5 Special save is required.')
    if (raw.nbytes if isinstance(raw, memoryview) else len(raw)) != SAVE_SIZE:
        raise SaveError('Unsupported DW5 Special size; expected 46,000 bytes.')
    try:
        return bytes(raw)
    except (TypeError, ValueError) as error:
        raise SaveError('A contiguous native DW5 Special snapshot is required.') from error


@lru_cache(maxsize=4)
def _decode(raw):
    if raw[4:8] not in SUPPORTED_REVISION_MARKERS:
        raise SaveError('Unsupported Windows DW5 Special revision.')
    if sum(raw[:CHECKSUM_OFFSET]) != int.from_bytes(raw[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4], 'little'):
        raise SaveError('DW5 Special byte checksum does not match.')
    return raw


def decode(raw):
    return _decode(freeze(raw))


def encode(payload, original_raw):
    original = decode(original_raw)
    if (type(payload) is not bytes or len(payload) != SAVE_SIZE
            or payload[4:8] != original[4:8]):
        raise SaveError('A frozen native DW5 Special payload is required.')
    if payload == original:
        return original
    result = bytearray(payload)
    result[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4] = sum(result[:CHECKSUM_OFFSET]).to_bytes(4, 'little')
    return decode(result)

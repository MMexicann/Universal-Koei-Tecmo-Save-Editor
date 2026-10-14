"""Bounded PS4 title-only qualification, with opaque metadata preservation."""
import struct
from koei_editor.games.dw3.models import SaveError

MAX_SFO_SIZE = 4096


def title_id(raw, expected):
    if type(raw) is not bytes or not 20 <= len(raw) <= MAX_SFO_SIZE:
        raise SaveError('PS4 metadata has an invalid bounded size.')
    magic, version, keys, data, count = struct.unpack_from('<5I', raw)
    if (magic != 0x46535000 or version != 0x101 or count > 128
            or not 20 + count * 16 <= keys <= data <= len(raw)):
        raise SaveError('PS4 metadata header is malformed.')
    found = None
    for index in range(count):
        key_offset, encoding, length, capacity, relative = struct.unpack_from('<HH3I', raw, 20 + index * 16)
        start = keys + key_offset
        if not keys <= start < data:
            raise SaveError('PS4 metadata key exceeds its bounded table.')
        end = raw.find(b'\0', start, data)
        if end < 0:
            raise SaveError('PS4 metadata key is unterminated.')
        if raw[start:end] != b'TITLE_ID':
            continue
        position = data + relative
        if (found is not None or encoding != 0x204 or not 1 <= length <= capacity <= 32
                or position < data or position + capacity > len(raw)):
            raise SaveError('PS4 title identity is malformed.')
        value = raw[position:position + length]
        if value[-1:] != b'\0' or b'\0' in value[:-1]:
            raise SaveError('PS4 title identity must be terminated.')
        try:
            found = value[:-1].decode('ascii')
        except UnicodeDecodeError as error:
            raise SaveError('PS4 title identity must be ASCII.') from error
    if found != expected:
        raise SaveError('Requires original PS4 ' + expected + ' metadata.')
    return found

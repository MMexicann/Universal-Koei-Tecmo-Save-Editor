"""Existing protagonist-name framing, independently implemented from native facts.

The public v13/v23 layouts and v23 SetName writer establish a forty-byte UTF-8
name buffer. Native references use two different closing controls; retain the
opened control rather than adopting an external writer's normalization.
"""
from dataclasses import dataclass

from koei_editor.games.dw3.models import SaveError

SIZE = 40
PREFIX = b'\x1bN0'
CLOSERS = (b'\x1bN0', b'\x1bN1')
OFFSETS = {13: 0x8984, 23: 0x9014}  # Native payload coordinates.


def framed_name(raw):
    """Return decoded text and exact closing marker only for known framing."""
    if len(raw) != SIZE or not raw.startswith(PREFIX):
        return None
    end = raw.find(b'\x1b', len(PREFIX))
    if end < 4 or raw[end:end + 3] not in CLOSERS or any(raw[end + 3:]):
        return None
    try:
        text = raw[3:end].decode('utf-8')
    except UnicodeError:
        return None
    if not text or not text.isprintable() or '\x00' in text:
        return None
    return text, raw[end:end + 3]


@dataclass(frozen=True)
class NameField:
    offset: int
    id: str = 'protagonist_name'
    label: str = 'Protagonist name'
    size: int = SIZE
    group: str = 'Customization'
    slot: int = 0
    minimum: int = 1
    maximum: int = 8
    maxable: bool = False
    kind: str = 'text'
    forbidden: tuple = ()
    encoding: str = '40-byte framed UTF-8 buffer; original name controls preserved'
    experimental_maximum: None = None

    def value(self, payload):
        result = framed_name(payload[self.offset:self.offset + SIZE])
        if result is None:
            raise SaveError('This existing protagonist name has unqualified framing.')
        return result[0]

    def validate(self, value):
        if (type(value) is not str or not 1 <= len(value) <= 8
                or any(ord(char) < 32 or ord(char) > 126 for char in value)):
            raise SaveError('Use 1–8 printable ASCII characters for the protagonist name.')

    def write(self, payload, value, original):
        self.validate(value)
        opened = framed_name(original[self.offset:self.offset + SIZE])
        if opened is None:
            raise SaveError('This existing protagonist name has unqualified framing.')
        encoded = PREFIX + value.encode('ascii') + opened[1]
        payload[self.offset:self.offset + SIZE] = encoded.ljust(SIZE, b'\0')

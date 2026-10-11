"""Qualified plaintext English PS4 framing; console integrity is external.

The complete platform converter emits the PS4 header and ten unchanged field
blocks directly, without a native checksum/cipher. See P5STRIKERS_PS4_FORMAT.md.
No PC
stream transform, Japanese conversion or corruption repair is performed here.
"""
from functools import lru_cache

from koei_editor.games.dw3.models import SaveError

SAVE_SIZE = 0x55DCBC
HEADER_SIZE = 0x1C
SLOT_COUNT = 10
NAME_SIZE = 33
NAME_RELATIVE = 0x87842
SLOT_SIZE = 0x88DF4 + 2 * NAME_SIZE
SLOTS_END = HEADER_SIZE + SLOT_COUNT * SLOT_SIZE
MARKER_RELATIVE = 0x938
LAYOUT_MARKER = 0x0036EE7F
VERSION_BYTES = bytes.fromhex('00200120')
INTEGRITY_KIND = 'none'


def validate_payload(payload):
    if type(payload) is not bytes or len(payload) != SAVE_SIZE:
        raise SaveError('Open a complete 5,627,068-byte English decrypted PS4 APP.BIN export.')
    _validate(payload)


@lru_cache(maxsize=4)
def _validate(payload):
    if payload[:4] != VERSION_BYTES:
        raise SaveError('Unsupported Persona 5 Strikers PS4 revision.')
    selected = int.from_bytes(payload[4:8], 'little', signed=True)
    if not -1 <= selected < SLOT_COUNT:
        raise SaveError('Persona 5 Strikers selected save slot is malformed.')
    for slot in range(SLOT_COUNT):
        base = HEADER_SIZE + slot * SLOT_SIZE
        marker = int.from_bytes(payload[base + MARKER_RELATIVE:base + MARKER_RELATIVE + 4], 'little')
        if marker != LAYOUT_MARKER:
            raise SaveError('Requires the English PlayStation 4 slot/name layout; other platforms and Japanese exports are separate.')
    if payload[SLOTS_END:] != bytes(SAVE_SIZE - SLOTS_END):
        raise SaveError('Unsupported nonzero PS4 reserved tail; no data is trimmed or repaired.')

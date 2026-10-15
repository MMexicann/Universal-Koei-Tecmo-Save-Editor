"""Bounded native DW6 CON context and its level-zero SHA-1 block chain.

This reads the original package for title/framing provenance. It does not write
STFS, verify its RSA certificate, replace gameplay, or sign a console package.
Only the independently observed single-file, level-zero CON profile is accepted.
"""
from functools import lru_cache
import hashlib
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError

MAX_CONTEXT_SIZE = 1024 * 1024
SAVE_SIZE = 212496
OFFICER_BASE, OFFICER_STRIDE, OFFICER_COUNT = 0xB18, 168, 41
HORSE_BASE, HORSE_STRIDE, HORSE_COUNT = 0x29E0, 60, 8
MARKER_OFFSET, MARKER = 0x33E04, bytes.fromhex('07090400')
PROFILES = MappingProxyType({'dw6_xbox360_na': (0x4B4F07E0, 'DW6_NA.dat'),
                            'dw6_xbox360_eu': (0x4B4F07E1, 'DW6_EU.dat')})


def qualify_payload(raw):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE:
        raise SaveError('Requires the original 212,496-byte extracted DW6 Xbox 360 gameplay file.')
    _qualify_payload(raw)


@lru_cache(maxsize=4)
def _qualify_payload(raw):
    if raw[MARKER_OFFSET:MARKER_OFFSET + 4] != MARKER:
        raise SaveError('The DW6 Xbox 360 native footer does not match this qualified profile.')
    if any(int.from_bytes(raw[OFFICER_BASE + i * OFFICER_STRIDE + 136:
                              OFFICER_BASE + i * OFFICER_STRIDE + 140], 'big') != i
           for i in range(OFFICER_COUNT)):
        raise SaveError('The original DW6 Xbox 360 big-endian officer identities do not match.')


def extract_payload(raw, game_id):
    """Validate an original CON context and return its unchanged native entry.

The preserved context contains its old gameplay. A later converted raw export
must be inserted externally before rehashing/resigning that destination copy.
"""
    if type(game_id) is not str or game_id not in PROFILES:
        raise SaveError('Choose the exact North American or European DW6 Xbox 360 endpoint.')
    if type(raw) is not bytes or not 0x41000 <= len(raw) <= MAX_CONTEXT_SIZE:
        raise SaveError('ORIGINAL.CON exceeds the qualified bounded Xbox 360 package profile.')
    return _extract_payload(raw, game_id)


@lru_cache(maxsize=4)
def _extract_payload(raw, game_id):
    title_id, filename = PROFILES[game_id]
    if (len(raw) % 4096 or raw[:4] != b'CON '
            or int.from_bytes(raw[0x340:0x344], 'big') != 0x971A
            or raw[0x344:0x34C] != bytes.fromhex('0000000100000002')
            or int.from_bytes(raw[0x360:0x364], 'big') != title_id
            or raw[0x379:0x37B] != b'\x24\x00'
            or raw[0x37B] not in (0, 2)
            or int.from_bytes(raw[0x37C:0x37E], 'little') != 1):
        raise SaveError('ORIGINAL.CON does not match this exact native DW6 Xbox 360 regional package profile.')
    if hashlib.sha1(raw[0x344:0xA000]).digest() != raw[0x32C:0x340]:
        raise SaveError('The original DW6 CON header SHA-1 is damaged; reopen an unchanged export.')
    table_start = int.from_bytes(raw[0x37E:0x381], 'little')
    allocated = int.from_bytes(raw[0x395:0x399], 'big')
    unallocated = int.from_bytes(raw[0x399:0x39D], 'big')
    if (not 0 <= table_start < allocated <= 170 or not 0 <= unallocated <= allocated
            or 0xC000 + allocated * 4096 > len(raw)):
        raise SaveError('The original DW6 CON allocation range is outside the qualified level-zero profile.')
    roots = [offset for offset in (0xA000, 0xB000)
             if hashlib.sha1(raw[offset:offset + 4096]).digest() == raw[0x381:0x395]]
    if not roots:
        raise SaveError('The original DW6 CON root SHA-1 does not match its hash table.')
    root = roots[0]

    def block(index):
        if not 0 <= index < allocated:
            raise SaveError('The original DW6 CON chain leaves its qualified allocation range.')
        offset, entry = 0xC000 + index * 4096, root + index * 24
        data = raw[offset:offset + 4096]
        if (len(data) != 4096 or not raw[entry + 20] & 0x80
                or hashlib.sha1(data).digest() != raw[entry:entry + 20]):
            raise SaveError('An original DW6 CON file-table or gameplay block failed its SHA-1.')
        return data, int.from_bytes(raw[entry + 21:entry + 24], 'big')

    entries, following_table = block(table_start)
    name_length, flags = entries[40] & 63, entries[40]
    count = int.from_bytes(entries[41:44], 'little')
    count_copy = int.from_bytes(entries[44:47], 'little')
    first = int.from_bytes(entries[47:50], 'little')
    size = int.from_bytes(entries[52:56], 'big')
    if (following_table != 0xFFFFFF or flags not in (10, 74)
            or entries[:name_length] != filename.encode('ascii')
            or entries[name_length:40] != bytes(40 - name_length)
            or entries[50:52] != b'\xFF\xFF'
            or count != (SAVE_SIZE + 4095) // 4096 or count_copy != count
            or size != SAVE_SIZE or entries[64:] != bytes(4096 - 64)):
        raise SaveError('ORIGINAL.CON must contain exactly the qualified native DW6 regional gameplay entry.')
    chunks, seen, index = [], {table_start}, first
    for number in range(count):
        if index in seen:
            raise SaveError('The original DW6 CON gameplay chain loops or overlaps its file table.')
        seen.add(index)
        data, following = block(index)
        chunks.append(data)
        if flags & 64 and number + 1 < count and following != index + 1:
            raise SaveError('The original DW6 CON contiguous chain does not match its file flags.')
        index = following
    if index != 0xFFFFFF:
        raise SaveError('The original DW6 CON gameplay chain does not end at its native length.')
    payload = b''.join(chunks)[:size]
    qualify_payload(payload)
    return payload

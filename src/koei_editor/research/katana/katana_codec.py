"""Explicit PC Katana envelopes, without account reassignment or checksum bypass.

The algorithms are adapted from Michał Gębicki's MIT-licensed
KatanaSaveDataResigner, commit 4c90a2b388438cb27a9752e6eab7333257de215f.
See licenses/katana-save-data-resigner-MIT.txt. No external program is executed.

Nioh 1/2/3 and Stranger of Paradise are inspection-only: the upstream cipher
does not validate or rebuild their gameplay integrity. Only an unchanged
snapshot can be encoded for those profiles. Wo Long's PC envelope has implemented
header/data checksums, but its upstream fixture is a dummy, not in-game evidence.
No profile is automatically selected by guessing another game's cipher.
"""
from dataclasses import dataclass
from functools import lru_cache
import hmac
import json
import struct

from koei_editor.games.dw3.save_codec import CNG_AES


MAX_SIZE = 16 * 1024 * 1024
_SBOX = bytes.fromhex(
    '1c2f0353a30149daa6cde08a19a704d4061ada4908e2f6b29ee12249ce7b7e5ea0092a63af49ce707b3c2380fa1747f2'
    '62626c5910cc299cb54658c74413e738d5af2783d4d5a09ee3763b8504d9d6986066d47853eaca0e8d565344e2efbd'
    'a99b100aa11393f0430b7c398a47dfd3c50e3431a6ae5ab8e7e63143c0aa0fe082124cd1df8ba5ac70c53d1b8e93174d'
    '794ece63c4330e1457f0d8195b9b6171f22b337efd2c0bb62320b9d491199404a430138af1d005ec5eac4ad4d6a5177ff9e5f'
    '60029d7932d5e2cf181a3b7633957c233872da83f02cc08677460d8f0da6740648755bb7ff210c90314b58066cb91f61f795'
    '888bc95c2065fe90932ed9b85')
_HEADER_KEYS = (bytes.fromhex('35311fcdf8524ea279cc51924b5848fe'),
                bytes.fromhex('0e8c95cd6329f6c253ecfa34d5b47f5e'))
_HEADER_STATES = (bytes.fromhex('1bdfdd5727cbce873aeac29ee05b2925'),
                  bytes.fromhex('fd4c40a28ece198b7701bc0c14b757bd'))
_DATA_KEY = bytes.fromhex('545b5ebdfd7843557c7d7c7274c74491')
_DATA_STATE = bytes.fromhex('57077871dfece8e48762c77e69f9045d')
_SOP_KEY = bytes.fromhex('0a906d27695506b58c1a229dc471f454')
_SOP_IV = bytes.fromhex('a81bd2510442afa24f5b37150c3bcf8a')
# The upstream Wo Long lookup tables implement ordinary AES-128-CBC. The
# first 16 bytes of its expanded encryption key are the standard AES key.
_WOLONG_KEY = bytes.fromhex('50c4e33ae6fe4d8add3fe69b728866c7')
_WOLONG_IV = bytes.fromhex('bb40840a5f9c7d40c18e9028fbee518f')
_CHECKSUM_TABLE = bytes.fromhex(
    'f35d0c65dbe740a29913ab09037f475f8284cae96150f4c6c36db1b95354acc4'
    'ffab77ac47be919f95f6f859654ea55a4f22cbf4094a0a99ece31dfee76716b2'
    '247004e051821b5d85e29657ce86d59493bf3ac0b1b5a4c844bcccd76b7e2e88'
    '7d2b031749e96900b45c19ea20f2caee979c6c3234a88f9d7106e83b0c7cbdb072'
    'f38b62257b1cbad126f7057f3f92808e5f504cc658e1b6a175dec7f181cd23dbdc'
    '27dd556adafc42a6a7a301b3d0ed76fa4bb70db874e66ea08d3873d32f3078872d'
    '526f39843d4054210b153356e441c1f0c246fbcfefd9c47ab9d6601166368a1abb9'
    'a2afd37c5149835a2108c6dc302c9f98343adaeaf070e290f9053d89b133ed44d6'
    '35beb1ef51f9ee545311264682ca93c08df79d228895eaa614818')


@dataclass(frozen=True)
class Profile:
    header_size: int
    magic: tuple[bytes, bytes]
    revision: int
    length_offset: int = 0x14
    key_offset: int = 0x40
    cipher: str = 'custom_ctr'
    integrity_verified: bool = False


# Conservative reviewed PC revisions; matching magic alone cannot distinguish
# Nioh from Nioh 2, or Stranger of Paradise from Nioh 3.
PROFILES = {
    'nioh': Profile(0x148, (b'NIOHUSR\0', b'NIOHSYS\0'), 0x17091200),
    'nioh2': Profile(0x148, (b'NIOHUSR\0', b'NIOHSYS\0'), 0x21030200),
    'nioh3': Profile(0x158, (b'RNNUSR\0\0', b'RNNSYS\0\0'), 0x01000001,
                     length_offset=0x18, key_offset=0x49),
    'sopffo': Profile(0x100, (b'RNNUSR\0\0', b'RNNSYS\0\0'), 0x23013100,
                      cipher='sop_cbc'),
    'wolong': Profile(0x100, (b'WLNUSR\0\0', b'WLNSYS\0\0'), 0x23121200,
                      cipher='wolong_cbc', integrity_verified=True),
}


@dataclass(frozen=True)
class Document:
    """Immutable full decoded snapshot; payload offsets include the header."""
    raw: bytes
    payload: bytes
    game_id: str
    header_size: int
    encrypted: bool
    integrity_verified: bool

    @property
    def writable(self) -> bool:
        return self.integrity_verified


def _profile(game_id: str) -> Profile:
    try:
        return PROFILES[game_id]
    except (KeyError, TypeError) as error:
        raise ValueError('Select an explicitly supported PC Katana profile.') from error


@lru_cache(maxsize=2)
def _tables(sbox: bytes) -> tuple[tuple[int, ...], ...]:
    if len(sbox) != 256:
        raise ValueError('A substitution box must contain 256 entries.')
    first = []
    for value in sbox:
        twice = ((value << 1) ^ (0x1b if value & 0x80 else 0)) & 255
        first.append((twice << 24) | (value << 16) | (value << 8) | (twice ^ value))
    return tuple(tuple(((word >> shift) | (word << (32 - shift))) & 0xffffffff
                       if shift else word for word in first)
                 for shift in (0, 8, 16, 24))


def _expand_key(key: bytes, sbox: bytes = _SBOX) -> tuple[int, ...]:
    if len(key) != 16 or len(sbox) != 256:
        raise ValueError('Custom AES requires a 16-byte key and 256-byte S-box.')
    words = list(struct.unpack('>4I', key))
    rcon = 1
    for index in range(4, 44):
        temp = words[-1]
        if index % 4 == 0:
            temp = ((sbox[(temp >> 16) & 255] ^ rcon) << 24 |
                    sbox[(temp >> 8) & 255] << 16 | sbox[temp & 255] << 8 |
                    sbox[temp >> 24])
            rcon = ((rcon << 1) ^ (0x1b if rcon & 0x80 else 0)) & 255
        words.append(words[index - 4] ^ temp)
    return tuple(words)


def _encrypt_block(block: bytes, keys: tuple[int, ...],
                   sbox: bytes = _SBOX) -> bytes:
    """AES round structure with the game's nonstandard, noninvertible S-box."""
    if len(block) != 16 or len(keys) != 44:
        raise ValueError('Custom AES requires one block and 44 round words.')
    a, b, c, d = (word ^ keys[index]
                  for index, word in enumerate(struct.unpack('>4I', block)))
    t0, t1, t2, t3 = _tables(sbox)
    for offset in range(4, 40, 4):
        a, b, c, d = (
            t0[a >> 24] ^ t1[(b >> 16) & 255] ^ t2[(c >> 8) & 255] ^ t3[d & 255] ^ keys[offset],
            t0[b >> 24] ^ t1[(c >> 16) & 255] ^ t2[(d >> 8) & 255] ^ t3[a & 255] ^ keys[offset + 1],
            t0[c >> 24] ^ t1[(d >> 16) & 255] ^ t2[(a >> 8) & 255] ^ t3[b & 255] ^ keys[offset + 2],
            t0[d >> 24] ^ t1[(a >> 16) & 255] ^ t2[(b >> 8) & 255] ^ t3[c & 255] ^ keys[offset + 3])
    words = (a, b, c, d)
    final = []
    for index in range(4):
        final.append((sbox[words[index] >> 24] << 24 |
                      sbox[(words[(index + 1) % 4] >> 16) & 255] << 16 |
                      sbox[(words[(index + 2) % 4] >> 8) & 255] << 8 |
                      sbox[words[(index + 3) % 4] & 255]) ^ keys[40 + index])
    return struct.pack('>4I', *final)


def _ctr(data: bytes, key: bytes, state: bytes) -> bytes:
    if len(state) != 16:
        raise ValueError('Custom CTR requires a 16-byte counter state.')
    keys = _expand_key(key)
    result = bytearray(len(data))
    counter = int.from_bytes(state[12:], 'big')
    for offset in range(0, len(data), 16):
        stream = _encrypt_block(state[:12] + struct.pack('>I', counter), keys)
        block = data[offset:offset + 16]
        result[offset:offset + len(block)] = bytes(a ^ b for a, b in zip(block, stream))
        counter = (counter + 1) & 0xffffffff
    return bytes(result)


def _header_crypt(header: bytes) -> bytes:
    for key, state in zip(_HEADER_KEYS, _HEADER_STATES):
        header = _ctr(header, key, state)
    return header


def _nioh_decrypt(raw: bytes, profile: Profile) -> bytes:
    header = bytearray(_header_crypt(raw[:profile.header_size]))
    offset = profile.key_offset
    key1 = _ctr(header[offset:offset + 16], _DATA_KEY, _DATA_STATE)
    state1 = _ctr(header[offset + 16:offset + 32], _DATA_KEY, _DATA_STATE)
    key2 = _ctr(header[offset + 32:offset + 48], key1, state1)
    state2 = _ctr(header[offset + 48:offset + 64], key1, state1)
    header[offset:offset + 64] = key1 + state1 + key2 + state2
    body = _ctr(_ctr(raw[profile.header_size:], key2, state2), key1, state1)
    return bytes(header) + body


def _nioh_encrypt(payload: bytes, profile: Profile) -> bytes:
    """Internal cipher only. This does not rebuild gameplay integrity."""
    header = bytearray(payload[:profile.header_size])
    offset = profile.key_offset
    key1, state1, key2, state2 = (payload[start:start + 16]
                                  for start in range(offset, offset + 64, 16))
    body = _ctr(_ctr(payload[profile.header_size:], key2, state2), key1, state1)
    header[offset + 32:offset + 64] = _ctr(key2, key1, state1) + _ctr(state2, key1, state1)
    header[offset:offset + 32] = _ctr(key1, _DATA_KEY, _DATA_STATE) + _ctr(state1, _DATA_KEY, _DATA_STATE)
    return _header_crypt(bytes(header)) + body


def _cbc(data: bytes, key: bytes, iv: bytes, direction: str) -> bytes:
    with CNG_AES('CBC') as provider:
        return provider.transform(data, key, direction=direction, iv=iv)


def _checksum(data: bytes) -> bytes:
    # Each input byte contributes to the total, its alternating four-byte
    # block lane and its position modulo four. Strided sums perform the same
    # accumulation in C instead of updating three Python integers per byte.
    # Subtracting the first alternating lane gives the second even for a
    # partial final block; defer ushort wrap until all seven sums are complete.
    quarters = [sum(data[offset::4]) for offset in range(4)]
    total = sum(quarters)
    first_blocks = sum(sum(data[offset::8]) for offset in range(4))
    lanes = [total, first_blocks, total - first_blocks, *quarters]
    result = bytearray(32)
    struct.pack_into('<7H', result, 0, *(value & 0xffff for value in lanes))
    for index in range(31):
        result[index + 1] = (result[index + 1] + 2 * index + result[index]) & 255
    return bytes((_CHECKSUM_TABLE[32 + value] + _CHECKSUM_TABLE[index]) & 255
                 for index, value in enumerate(result))


def _wolong_checksums(payload: bytes) -> None:
    if not hmac.compare_digest(payload[0x3c:0x5c], _checksum(payload[0x100:])):
        raise ValueError('Wo Long PC data checksum is invalid.')
    header = bytearray(payload[:0x100])
    expected = bytes(header[0x5c:0x7c])
    header[0x5c:0x7c] = bytes(32)
    if not hmac.compare_digest(expected, _checksum(header)):
        raise ValueError('Wo Long PC header checksum is invalid.')


def _validate(payload: bytes, profile: Profile, *, integrity: bool = True) -> None:
    if not profile.header_size + 16 <= len(payload) <= MAX_SIZE:
        raise ValueError('Empty, truncated or oversized Katana PC save.')
    if payload[:8] not in profile.magic or struct.unpack_from('<I', payload, 8)[0] != profile.revision:
        raise ValueError('Wrong title/platform or unreviewed Katana PC revision.')
    header_length, body_length = struct.unpack_from('<II', payload, profile.length_offset)
    if header_length != profile.header_size or body_length != len(payload) - header_length:
        raise ValueError('Katana PC header/data lengths do not match the file.')
    if profile.cipher.endswith('cbc') and len(payload) % 16:
        raise ValueError('Katana PC CBC save is not block aligned.')
    if profile.cipher != 'custom_ctr' or profile.header_size == 0x148:
        if payload[profile.header_size + 8:profile.header_size + 12] != payload[8:12] and profile.cipher == 'custom_ctr':
            raise ValueError('Nioh PC inner revision does not match its header.')
        pattern_offset = profile.header_size + (8 if profile.cipher == 'sop_cbc' else 0)
        if profile.cipher.endswith('cbc') and payload[pattern_offset:pattern_offset + 8] != payload[8:16]:
            raise ValueError('Katana PC inner revision does not match its header.')
    if profile.cipher == 'wolong_cbc':
        json_data = payload[0x108:]
        zero = json_data.find(b'\0')
        encoded = json_data if zero < 0 else json_data[:zero]
        if zero >= 0 and any(json_data[zero:]):
            raise ValueError('Wo Long PC JSON padding is invalid.')
        try:
            value = json.loads(encoded.decode('utf-8'))
        except (ValueError, UnicodeDecodeError, RecursionError) as error:
            raise ValueError('Wo Long PC JSON payload is invalid.') from error
        if not isinstance(value, dict):
            raise ValueError('Wo Long PC JSON must contain an object.')
        if integrity:
            _wolong_checksums(payload)


def decode(raw: bytes, game_id: str) -> Document:
    """Decode one explicit reviewed PC profile, preserving all original bytes.

    Check Document.integrity_verified before considering gameplay writes.
    For inspection-only profiles structure is checked, but an arbitrary body
    corruption cannot be reliably detected without their unreversed integrity.
    """
    profile = _profile(game_id)
    raw = bytes(raw)
    if not profile.header_size + 16 <= len(raw) <= MAX_SIZE:
        raise ValueError('Empty, truncated or oversized Katana PC save.')
    if profile.cipher.endswith('cbc') and len(raw) % 16:
        raise ValueError('Katana PC CBC save is not block aligned.')
    if profile.cipher == 'wolong_cbc':
        encrypted = raw[8:16] != raw[0x100:0x108]
        payload = raw[:0x100] + _cbc(raw[0x100:], _WOLONG_KEY, _WOLONG_IV, 'decrypt') if encrypted else raw
    else:
        encrypted = raw[:8] not in profile.magic
        if not encrypted:
            payload = raw
        elif profile.cipher == 'sop_cbc':
            payload = _cbc(raw, _SOP_KEY, _SOP_IV, 'decrypt')
        else:
            # Reject foreign headers before processing a potentially large body.
            header = _header_crypt(raw[:profile.header_size])
            if header[:8] not in profile.magic or struct.unpack_from('<I', header, 8)[0] != profile.revision:
                raise ValueError('Wrong title/platform or unreviewed Katana PC revision.')
            header_length, body_length = struct.unpack_from('<II', header, profile.length_offset)
            if header_length != profile.header_size or body_length != len(raw) - header_length:
                raise ValueError('Katana PC header/data lengths do not match the file.')
            payload = _nioh_decrypt(raw, profile)
    _validate(payload, profile)
    return Document(raw, payload, game_id, profile.header_size, encrypted,
                    profile.integrity_verified)


def encode(payload: bytes, original_raw: bytes, game_id: str) -> bytes:
    """Preserve the input representation, account, header and unknown bytes.

    Native Wo Long edits update only its two checksum ranges. Other profiles
    reject every change until their gameplay integrity is independently mapped.
    """
    original = decode(original_raw, game_id)
    payload = bytes(payload)
    if payload == original.payload:
        return original.raw
    if not original.writable:
        raise ValueError('This Katana PC profile is inspection-only: gameplay integrity is not verified.')
    if len(payload) != len(original.payload):
        raise ValueError('Katana PC edits must preserve the original file size.')
    if payload[:original.header_size] != original.payload[:original.header_size]:
        raise ValueError('Katana PC edits must preserve the original header and account binding.')
    profile = _profile(game_id)
    _validate(payload, profile, integrity=False)
    result = bytearray(payload)
    result[0x3c:0x5c] = _checksum(result[0x100:])
    result[0x5c:0x7c] = bytes(32)
    result[0x5c:0x7c] = _checksum(result[:0x100])
    result = bytes(result)
    encoded = (result[:0x100] + _cbc(result[0x100:], _WOLONG_KEY, _WOLONG_IV, 'encrypt')
               if original.encrypted else result)
    reopened = decode(encoded, game_id)
    if reopened.payload != result:
        raise ValueError('Katana PC re-encoding failed validation.')
    return encoded

"""Owner-dependent slot-zero SW5 revision-39 native CBC envelope.

Native framing has a fingerprint, not a payload checksum. No owner fallback,
file repair, cross-slot conversion or ciphertext-to-plaintext bypass is used.
"""
import struct
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw3.save_codec import CNG_AES

SAVE_SIZE = 4_493_236
FINGERPRINT = b'01Finger2Print34'
MANAGER_END = 0x18CF9B
RESUME_SIZE = 0x15E000
SECOND_RESUME = 0x2EAF9B
PAD_START = 4_493_211
COUNTS = (1, 1, 2, 1, 300, 256, 1680, 1000, 1, 2, 100, 64, 1, 32, 64, 256, 70)
STRIDES = (42, 14, 70, 0x3B3E, 135, 11, 27, 1, 27, 74, 0xB2C, 32, 200, 14, 3, 46, 10)

def sections():
    offset, rows = 4, []
    for state in (4, 1, 2, 3):
        for kind, (count, stride) in enumerate(zip(COUNTS, STRIDES), 1):
            if (state == 4 and kind in (9, 10)) or (state != 4 and kind == 1):
                continue
            rows.append((state, kind, offset, count, stride))
            offset += count * stride
    if offset != MANAGER_END:
        raise SaveError('The supported SW5 stream schema is inconsistent.')
    return tuple(rows)

SECTIONS = sections()

def _key(account):
    if type(account) is not int or not 1 <= account <= 0xFFFFFFFF:
        raise SaveError('The original Steam owner context is required.')
    value = 0.5 / 6.0
    value = (1.0 - value) * (value * 3.66)
    for _ in range(9):
        value = (value * 3.66) * (1.0 - value)
    state = struct.unpack('<I', struct.pack('<d', value)[:4])[0] ^ account
    result = bytearray()
    for _ in range(16):
        state = (state * 0x343FD + 0x269EC3) & 0xFFFFFFFF
        result.append(state >> 24)
    return bytes(result)

def _iv(seed):
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise SaveError('SW5 native IV framing is invalid.')
    result = bytearray()
    for _ in range(16):
        seed = (seed * 0x15A4E35 + 1) & 0xFFFFFFFF
        result.append((seed >> 16) & 255)
    return bytes(result)

def validate_payload(payload):
    if type(payload) is not bytes or len(payload) != SAVE_SIZE - 4:
        raise SaveError('Requires a complete native SW5 slot-zero save.')
    if payload[-16:] != FINGERPRINT:
        raise SaveError('The copied save and original Steam owner context do not match.')
    if payload[:8] != struct.pack('<II', 39, 39):
        raise SaveError('Only SW5 native stream revision 39 is supported.')
    if payload[PAD_START:-16] != bytes(5):
        raise SaveError('SW5 native alignment is unsupported or damaged.')
    if payload[MANAGER_END] not in (0, 1) or payload[SECOND_RESUME] != 0:
        raise SaveError('Return to My Castle and make a fresh save copy; battle/resume saves are inspection-blocked.')

def decode_file(raw, account):
    if type(raw) is not bytes or len(raw) != SAVE_SIZE:
        raise SaveError('Requires a complete native SW5 slot-zero save.')
    seed = struct.unpack_from('<I', raw, len(raw) - 4)[0]
    with CNG_AES('CBC') as provider:
        payload = provider.transform(raw[:-4], _key(account), direction='decrypt', iv=_iv(seed))
    validate_payload(payload)
    return payload

def encode_file(payload, account, seed):
    validate_payload(payload)
    with CNG_AES('CBC') as provider:
        return provider.transform(payload, _key(account), direction='encrypt', iv=_iv(seed)) + struct.pack('<I', seed)

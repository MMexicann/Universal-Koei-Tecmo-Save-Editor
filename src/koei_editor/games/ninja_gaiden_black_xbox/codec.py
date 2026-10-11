"""Independent bounded native MT/Blowfish and carryless range codec.

The MT tempering masks are applied before shifts. Blowfish serializes its
two input/output words little endian. Unknown trailing buffer bytes remain
opaque. This module contains no copied editor implementation or assets.
"""
from bisect import bisect_right
from functools import lru_cache
import struct

from koei_editor.games.dw3.models import SaveError
from ._pi import PI_HEX

MASK = 0xffffffff
SIZE = 0x174a8
PLAIN_SIZE = SIZE - 24
DECODED_SIZE = 0x1748a
SYSTEM_SIZE = 0x550
SYSTEM_PLAIN_SIZE = SYSTEM_SIZE - 24
SYSTEM_DECODED_SIZE = 42 + 0x508
CAPACITIES = {PLAIN_SIZE: DECODED_SIZE, SYSTEM_PLAIN_SIZE: SYSTEM_DECODED_SIZE}
MARKER = bytes.fromhex('94458ed28a4f')


class _Random:
    def __init__(self, seed):
        self.words = [seed]
        for index in range(1, 624):
            previous = self.words[-1]
            self.words.append((1812433253 * (previous ^ (previous >> 30)) + index) & MASK)
        self.position = 624

    def next(self):
        if self.position == 624:
            for index in range(624):
                combined = ((self.words[index] & 0x80000000)
                            | (self.words[(index + 1) % 624] & 0x7fffffff))
                self.words[index] = (self.words[(index + 397) % 624] ^ (combined >> 1)
                                     ^ (0x9908b0df if combined & 1 else 0))
            self.position = 0
        value = self.words[self.position]
        self.position += 1
        value ^= value >> 11
        value ^= ((value & 0xff3a58ad) << 7) & MASK
        value ^= ((value & 0xffffdf8c) << 15) & MASK
        return (value ^ (value >> 18)) & MASK


class _Blowfish:
    def __init__(self, key):
        constants = [int(PI_HEX[i:i + 8], 16) for i in range(0, len(PI_HEX), 8)]
        self.p = constants[:18]
        self.s = [constants[18 + 256 * index:18 + 256 * (index + 1)] for index in range(4)]
        for index in range(18):
            word = bytes(key[(index * 4 + n) % len(key)] for n in range(4))
            self.p[index] ^= int.from_bytes(word, 'big')
        pair = (0, 0)
        for array in (self.p, *self.s):
            for index in range(0, len(array), 2):
                pair = self.block(*pair)
                array[index:index + 2] = pair

    def _f(self, value):
        first = (self.s[0][value >> 24] + self.s[1][(value >> 16) & 255]) & MASK
        return ((first ^ self.s[2][(value >> 8) & 255]) + self.s[3][value & 255]) & MASK

    def block(self, left, right, decrypt=False):
        indexes = range(17, 1, -1) if decrypt else range(16)
        for index in indexes:
            left ^= self.p[index]
            right ^= self._f(left)
            left, right = right, left
        left, right = right, left
        return (left ^ self.p[0 if decrypt else 17],
                right ^ self.p[1 if decrypt else 16])


def transform(data, seed, decrypt=False):
    if type(data) is not bytes or len(data) not in CAPACITIES or type(seed) is not int or not 0 <= seed <= MASK:
        raise SaveError('Invalid original Xbox Ninja Gaiden Black cipher framing.')
    generator = _Random(seed)
    key = struct.pack('<14I', *(generator.next() for _ in range(14)))
    cipher = _Blowfish(key)
    words = list(struct.unpack(f'<{len(data) // 4}I', data))
    if decrypt:
        words = [word ^ generator.next() for word in words]
    for index in range(0, len(words), 2):
        words[index:index + 2] = cipher.block(*words[index:index + 2], decrypt)
    if not decrypt:
        words = [word ^ generator.next() for word in words]
    return struct.pack(f'<{len(words)}I', *words)


def frequencies(plain):
    if type(plain) is not bytes or len(plain) not in CAPACITIES:
        raise SaveError('Invalid original Xbox native compression capacity.')
    kind = plain[0]
    if kind == 0:
        return None, 1
    if kind == 255:
        counts, start = list(plain[1:257]), 257
    elif 1 <= kind <= 127:
        counts, start = [0] * 256, 1 + 2 * kind
        seen = set()
        for position in range(1, start, 2):
            symbol, count = plain[position:position + 2]
            if not count or symbol in seen:
                raise SaveError('Invalid original Xbox compression frequencies.')
            seen.add(symbol)
            counts[symbol] = count
    else:
        raise SaveError('Unsupported original Xbox compression framing.')
    if not any(counts):
        raise SaveError('Empty original Xbox compression frequencies.')
    return tuple(counts), start


def unpack(plain):
    counts, position = frequencies(plain)
    decoded_size = CAPACITIES[len(plain)]
    if counts is None:
        return plain[1:1 + decoded_size], 1 + decoded_size, counts
    cumulative = [0]
    for count in (*counts, 1):
        cumulative.append(cumulative[-1] + count)
    code = int.from_bytes(plain[position:position + 4], 'big')
    position += 4
    low, interval, output = 0, MASK, bytearray()
    while True:
        unit = interval // cumulative[-1]
        if not unit:
            raise SaveError('Invalid original Xbox compression interval.')
        scaled = ((code - low) & MASK) // unit
        symbol = bisect_right(cumulative, scaled) - 1
        if not 0 <= symbol <= 256:
            raise SaveError('Invalid original Xbox compressed symbol.')
        if symbol == 256:
            break
        if len(output) >= decoded_size:
            raise SaveError('Original Xbox decoded save exceeds its qualified capacity.')
        output.append(symbol)
        low = (low + unit * cumulative[symbol]) & MASK
        interval = unit * counts[symbol]
        while (low ^ ((low + interval) & MASK)) < 1 << 24 or interval < 1 << 16:
            if (low ^ ((low + interval) & MASK)) >= 1 << 24:
                interval = (-low) & 65535
            if position >= len(plain) - len(MARKER):
                raise SaveError('Original Xbox compressed stream has no bounded terminator.')
            code = ((code << 8) | plain[position]) & MASK
            position += 1
            low = (low << 8) & MASK
            interval = (interval << 8) & MASK
    if len(output) != decoded_size:
        raise SaveError('Unsupported original Xbox decoded gameplay length.')
    return bytes(output), position, counts


def pack(payload, counts):
    if type(payload) is not bytes or len(payload) not in CAPACITIES.values():
        raise SaveError('Invalid original Xbox decoded save capacity.')
    plain_size = next(size for size, decoded in CAPACITIES.items() if decoded == len(payload))
    if counts is not None and (type(counts) is not tuple or len(counts) != 256
                               or any(type(n) is not int or not 0 <= n <= 255 for n in counts)
                               or not any(counts)):
        raise SaveError('Invalid original Xbox compression table.')
    # Keep the original table if every edited symbol remains representable.
    if counts is None or any(counts[byte] == 0 for byte in set(payload)):
        totals = [payload.count(bytes((value,))) for value in range(256)]
        highest = max(totals)
        counts = tuple(max(1, count * 255 // highest) if count else 0 for count in totals)
    cumulative = [0]
    for count in (*counts, 1):
        cumulative.append(cumulative[-1] + count)
    output = bytearray(b'\xff' + bytes(counts))
    low, interval = 0, MASK
    for symbol in (*payload, 256):
        unit = interval // cumulative[-1]
        low = (low + unit * cumulative[symbol]) & MASK
        interval = unit * (counts[symbol] if symbol < 256 else 1)
        while (low ^ ((low + interval) & MASK)) < 1 << 24 or interval < 1 << 16:
            if (low ^ ((low + interval) & MASK)) >= 1 << 24:
                interval = (-low) & 65535
            output.append(low >> 24)
            low = (low << 8) & MASK
            interval = (interval << 8) & MASK
            if len(output) > plain_size - len(MARKER) - 4:
                raise SaveError('Edited original Xbox stream exceeds its fixed capacity.')
    for _ in range(4):
        output.append(low >> 24)
        low = (low << 8) & MASK
    return bytes(output)


@lru_cache(maxsize=8)
def _decrypt_cached(raw):
    if type(raw) is not bytes or len(raw) not in (SIZE, SYSTEM_SIZE):
        raise SaveError('Requires a complete original Xbox Ninja Gaiden Black native file.')
    plain = transform(raw[24:], struct.unpack_from('<I', raw, 20)[0], True)
    if plain[-6:] != MARKER:
        raise SaveError('Unsupported original Xbox Ninja Gaiden Black cipher profile.')
    payload, extent, counts = unpack(plain)
    if payload[:6] != MARKER or b'TeamNINJA 2003' not in payload[:42]:
        raise SaveError('Original Xbox Ninja Gaiden Black native identity does not match.')
    return plain, payload, extent, counts


def decrypt(raw):
    if type(raw) is not bytes or len(raw) not in (SIZE, SYSTEM_SIZE):
        raise SaveError('Requires a complete original Xbox Ninja Gaiden Black native file.')
    return _decrypt_cached(raw)

"""Private original Xbox context, never exposed in reviews or manifests.

EEPROM protected-section SHA1 states and layout are published Xbox format
facts. SHA1 compression and RC4 are independently implemented here. The
remaining EEPROM bytes are opaque and bound by their complete original hash.
"""
from dataclasses import dataclass, field
import hashlib
import hmac
from pathlib import Path
import struct

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path

MASK = 0xffffffff
# Published SHA1 intermediate states after each hardware-revision HMAC pad.
STATES = (
    ((0x85f9e51a, 0xe04613d2, 0x6d86a50c, 0x77c32e3c, 0x4bd717a4),
     (0x5d7a9c6b, 0xe1922beb, 0xb82ccdbc, 0x3137ab34, 0x486b52b3)),
    ((0x72127625, 0x336472b9, 0xbe609bea, 0xf55e226b, 0x99958dac),
     (0x76441d41, 0x4de82659, 0x2e8ef85e, 0xb256faca, 0xc4fe2de8)),
    ((0x39b06e79, 0xc9bd25e8, 0xdbc6b498, 0x40b4389d, 0x86bbd7ed),
     (0x9b49bed3, 0x84b430fc, 0x6b8749cd, 0xebfe5fe5, 0xd96e7393)),
    ((0x8058763a, 0xf97d4e0e, 0x865a9762, 0x8a3d920d, 0x08995b2c),
     (0x01075307, 0xa2f1e037, 0x1186eeea, 0x88da9992, 0x168a5609)),
)
SIGNING_KEY = hmac.digest(bytes.fromhex('5c0733ae0401f7e8ba7993fdcd2f1fe0'),
                         bytes.fromhex('fc3376488b3e5f00f65a6bda9209cfe8'), 'sha1')[:16]


def _rotate(value, count):
    return ((value << count) | (value >> (32 - count))) & MASK


def _sha1(data, state):
    bit_length = (64 + len(data)) * 8
    padded = data + b'\x80' + bytes((55 - len(data)) % 64) + struct.pack('>Q', bit_length)
    state = list(state)
    for start in range(0, len(padded), 64):
        words = list(struct.unpack('>16I', padded[start:start + 64]))
        for index in range(16, 80):
            words.append(_rotate(words[index - 3] ^ words[index - 8]
                                 ^ words[index - 14] ^ words[index - 16], 1))
        a, b, c, d, e = state
        for index, word in enumerate(words):
            if index < 20:
                function, constant = (b & c) | (~b & d), 0x5a827999
            elif index < 40:
                function, constant = b ^ c ^ d, 0x6ed9eba1
            elif index < 60:
                function, constant = (b & c) | (b & d) | (c & d), 0x8f1bbcdc
            else:
                function, constant = b ^ c ^ d, 0xca62c1d6
            a, b, c, d, e = ((_rotate(a, 5) + function + e + constant + word) & MASK,
                              a, _rotate(b, 30), c, d)
        state = [(left + right) & MASK for left, right in zip(state, (a, b, c, d, e))]
    return struct.pack('>5I', *state)


def _xhash(data, states):
    return _sha1(_sha1(data, states[0]), states[1])


def _rc4(data, key):
    permutation, second = list(range(256)), 0
    for first in range(256):
        second = (second + permutation[first] + key[first % len(key)]) % 256
        permutation[first], permutation[second] = permutation[second], permutation[first]
    first = second = 0
    result = bytearray()
    for value in data:
        first = (first + 1) % 256
        second = (second + permutation[first]) % 256
        permutation[first], permutation[second] = permutation[second], permutation[first]
        result.append(value ^ permutation[(permutation[first] + permutation[second]) % 256])
    return bytes(result)


def extract_key(eeprom):
    if type(eeprom) is not bytes or len(eeprom) != 256:
        raise SaveError('Requires an original 256-byte console EEPROM copy.')
    matches = []
    for states in STATES:
        protected = _rc4(eeprom[20:48], _xhash(eeprom[:20], states))
        if hmac.compare_digest(_xhash(protected, states), eeprom[:20]):
            matches.append(protected[8:24])
    if len(matches) != 1:
        raise SaveError('The copied console EEPROM protected section is invalid.')
    return matches[0]


def signature(raw, key):
    if type(raw) is not bytes or len(raw) < 24 or type(key) is not bytes or len(key) != 16:
        raise SaveError('Invalid original Xbox native signing context.')
    return hmac.digest(key, hmac.digest(SIGNING_KEY, raw[20:], 'sha1'), 'sha1')


@dataclass(frozen=True)
class Context:
    directory: Path = field(repr=False)
    basename: str
    eeprom: bytes = field(repr=False)
    metadata: bytes = field(repr=False)
    key: bytes = field(repr=False)

    @property
    def eeprom_hash(self):
        return hashlib.sha256(self.eeprom).hexdigest()

    @property
    def metadata_hash(self):
        return hashlib.sha256(self.metadata).hexdigest()


def ordinary(path):
    try:
        path = Path(path).absolute()
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise SaveError('Use ordinary separate Xbox copies without path aliases.')
        result = safe_path(path)
        for candidate in (path, result):
            parts = str(candidate).replace('\\', '/').casefold().split('/')
            if any(parts[i:i + 2] in (['udata', '5443000d'], ['tdata', '5443000d'])
                   for i in range(len(parts) - 1)):
                raise SaveError('Use separate copies outside live original Xbox save folders.')
        if result.exists() and (not result.is_file() or result.stat().st_nlink != 1):
            raise SaveError('Use ordinary separate Xbox files without linked aliases.')
        return result
    except (OSError, TypeError, ValueError):
        raise SaveError('The copied original Xbox file is unavailable.') from None


def _read(path, maximum):
    path = ordinary(path)
    try:
        with path.open('rb') as stream:
            value = stream.read(maximum + 1)
    except OSError:
        raise SaveError('An original Xbox save companion is unavailable.') from None
    if len(value) > maximum:
        raise SaveError('An original Xbox save companion exceeds its bounded size.')
    return value


def read_story_context(source):
    directory = ordinary(source).parent
    try:
        entries = tuple(directory.iterdir())
    except OSError:
        raise SaveError('The copied Xbox context directory is unavailable.') from None
    candidates = [item for item in entries if item.name.casefold() in ('eeprom.bin', 'factory_eeprom.bin')]
    metas = [item for item in entries if item.name.casefold() == 'savemeta.xbx']
    if len(candidates) != 1 or len(metas) != 1 or metas[0].name != 'SaveMeta.xbx':
        raise SaveError('Keep one original eeprom.bin or factory_eeprom.bin and SaveMeta.xbx beside the copy.')
    eeprom = _read(candidates[0], 256)
    metadata = _read(metas[0], 1024)
    try:
        text = metadata.decode('utf-16') if metadata.startswith(b'\xff\xfe') else metadata.decode('utf-16-le')
    except UnicodeError:
        raise SaveError('The original Xbox slot metadata is invalid.') from None
    import re
    if not re.fullmatch(r'Name=(?:[1-9]|[12][0-9]|30)\. CHAPTER (?:[1-9]|1[0-6]) [0-9]{3}:[0-5][0-9]\r?\nNoCopy=1\r?\n?', text):
        raise SaveError('Requires original Xbox Ninja Gaiden Black chapter-slot metadata.')
    return Context(directory, candidates[0].name, eeprom, metadata, extract_key(eeprom))


def validate_shape(context):
    if (type(context) is not Context or not isinstance(context.directory, Path)
            or not context.directory.is_absolute() or type(context.basename) is not str
            or context.basename.casefold() not in ('eeprom.bin', 'factory_eeprom.bin')
            or type(context.metadata) is not bytes or len(context.metadata) > 1024
            or type(context.key) is not bytes or len(context.key) != 16
            or extract_key(context.eeprom) != context.key):
        raise SaveError('Invalid immutable original Xbox owner context.')


def validate_story_context(context, destination=None):
    validate_shape(context)
    current = read_story_context(context.directory / 'save000.dat')
    if current != context:
        raise SaveError('Original Xbox companions changed; reopen the copied save.')
    if destination is not None:
        target = read_story_context(destination)
        if (target.basename != context.basename or target.eeprom != context.eeprom
                or target.metadata != context.metadata):
            raise SaveError('The edited destination requires the unchanged original Xbox companions.')


def read_context(source):
    """SYSTEM.dat has no story SaveMeta requirement; bind one original EEPROM."""
    directory = ordinary(source).parent
    try:
        candidates = [item for item in directory.iterdir()
                      if item.name.casefold() in ('eeprom.bin', 'factory_eeprom.bin')]
    except OSError:
        raise SaveError('The copied Xbox context directory is unavailable.') from None
    if len(candidates) != 1:
        raise SaveError('Keep one original eeprom.bin or factory_eeprom.bin beside the system copy.')
    eeprom = _read(candidates[0], 256)
    return Context(directory, candidates[0].name, eeprom, b'', extract_key(eeprom))


def validate_context(context, destination=None):
    validate_shape(context)
    if context.metadata != b'' or read_context(context.directory / 'system.dat') != context:
        raise SaveError('Original Xbox companions changed; reopen the copied system save.')
    if destination is not None and read_context(destination).eeprom != context.eeprom:
        raise SaveError('The edited destination requires the unchanged original console EEPROM.')
    if destination is not None and read_context(destination).basename != context.basename:
        raise SaveError('The edited destination requires the same original EEPROM basename.')

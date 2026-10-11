"""Read-only Warriors: Abyss encrypted PC envelope candidate.

Statically recovered AES-256-CBC and owner-key derivation are documented in
PIRATE_ABYSS_RESEARCH.md. Both envelope capacities now have native no-edit
roundtrips; gameplay integrity and dependencies still need qualification.
No mutable encoding, file-writing operations,
account reassignment, GUI registration or gameplay fields are provided.
Owner context is supplied explicitly and is neither stored nor returned.
"""
from dataclasses import dataclass, field
import hmac
import struct

from koei_editor.games.dw3.save_codec import CNG_AES
from koei_editor.shared.steam_owner import read_owner, validate_owner
from types import MappingProxyType
from pathlib import Path


OUTER_MAGIC = b'470558d4d8015d9f'
INNER_MAGIC = b'a1423bc7d48e148b'
IV = bytes.fromhex('e1c1c49f9a3019341ea820f99fd09a83')
OWNER_MASK = 0xFABE9C015F6E379A
OBSERVED_SIZES = (0x2800, 0x30000)
OBSERVED_REVISION = 0xA4
REVISIONS_BY_SIZE = MappingProxyType({0x2800: (0x77, 0xA4), 0x30000: (0xA4,)})
PC_SAMPLE_VERIFIED = True
GAMEPLAY_INTEGRITY_VERIFIED = False


def _owner_key(owner_context):
    if type(owner_context) is not int or not 0 <= owner_context <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError('Explicit unsigned 64-bit save-owner context required.')
    return str(owner_context ^ OWNER_MASK).encode('ascii').ljust(32, b'\0')


def _bytes(value):
    if type(value) not in (bytes, bytearray, memoryview):
        raise ValueError('The candidate envelope requires byte data.')
    size = value.nbytes if type(value) is memoryview else len(value)
    if size not in OBSERVED_SIZES:
        raise ValueError('Only executable-observed aligned system/game buffers are investigated.')
    return value.tobytes() if type(value) is memoryview else bytes(value)


def _decode(raw, owner_context):
    key = _owner_key(owner_context)
    if not raw.startswith(OUTER_MAGIC):
        raise ValueError('Missing encrypted Abyss candidate marker.')
    with CNG_AES('CBC') as provider:
        plaintext = provider.transform(raw[16:], key, direction='decrypt', iv=IV)
    if not hmac.compare_digest(plaintext[:16], INNER_MAGIC):
        raise ValueError('Candidate encrypted marker mismatch; owner context or input is invalid.')
    payload = plaintext[16:]
    if struct.unpack_from('<I', payload)[0] not in REVISIONS_BY_SIZE[len(raw)]:
        raise ValueError('Unsupported Abyss candidate capacity/revision pair.')
    return payload


@dataclass(frozen=True)
class CandidateDocument:
    """Read-only decrypted snapshot; inner gameplay integrity remains unknown."""
    raw: bytes = field(repr=False)
    payload: bytes = field(repr=False)

    @property
    def writable(self):
        return False

    @property
    def integrity_verified(self):
        return False

    def unchanged_roundtrip(self, *, owner_context):
        """Require original owner context and unchanged bytes before re-encryption."""
        if type(self.raw) is not bytes or type(self.payload) is not bytes:
            raise ValueError('Candidate snapshots must contain immutable bytes.')
        raw = _bytes(self.raw)
        if _decode(raw, owner_context) != self.payload:
            raise ValueError('The candidate snapshot was modified.')
        with CNG_AES('CBC') as provider:
            encoded = OUTER_MAGIC + provider.transform(
                INNER_MAGIC + self.payload, _owner_key(owner_context),
                direction='encrypt', iv=IV)
        if encoded != raw:
            raise ValueError('Candidate unchanged roundtrip mismatch.')
        return encoded


def decode_candidate(raw, *, owner_context):
    """Inspect a copied candidate without retaining owner/account information."""
    _owner_key(owner_context)
    frozen = _bytes(raw)
    return CandidateDocument(frozen, _decode(frozen, owner_context))


def read_candidate_copy(path):
    """Read an ordinary copied envelope and its original standard-named VDF.

    Account values remain private inside the bounded owner helper. This still
    provides inspection and unchanged roundtrips only, never a body writer.
    """
    from koei_editor.shared.save_safety import safe_path
    import re
    for candidate in (Path(path).absolute(), safe_path(path)):
        normalized = str(candidate).replace('\\', '/').casefold()
        if re.search(r'/koeitecmo/warriorsabyss(?:/|$)', normalized):
            raise ValueError('Use a separate copy outside the live Warriors: Abyss save folder.')
    owner = read_owner(path)
    with Path(path).open('rb') as stream:
        raw = stream.read(max(OBSERVED_SIZES) + 1)
    result = decode_candidate(raw, owner_context=owner.steam_id64)
    validate_owner(owner)
    if result.unchanged_roundtrip(owner_context=owner.steam_id64) != raw:
        raise ValueError('Copied Abyss envelope changed during inspection.')
    validate_owner(owner)
    return result

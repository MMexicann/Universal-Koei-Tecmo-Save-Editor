"""Exact native TLV framing observations; no checksum or wallet writer claimed."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.save_safety import safe_path


@dataclass(frozen=True)
class Profile:
    id: str
    title: str
    title_id: str
    size: int
    magic: int
    chunk_sizes: tuple[int, ...]
    trailer_size: int


PROFILES = MappingProxyType(
    {
        profile.id: profile
        for profile in (
            Profile(
                "totori_plus_vita",
                "Atelier Totori Plus",
                "PCSE00231",
                282624,
                20100403,
                (
                    33264,
                    5172,
                    4,
                    3972,
                    152520,
                    51,
                    57164,
                    4,
                    5632,
                    1,
                    20,
                    68,
                    940,
                    1452,
                    8,
                    4536,
                    400,
                    1836,
                    14325,
                    168,
                    96,
                    64,
                ),
                719,
            ),
            Profile(
                "rorona_plus_vita",
                "Atelier Rorona Plus",
                "PCSE00466",
                380928,
                20100403,
                (
                    39392,
                    8416,
                    4,
                    6112,
                    138252,
                    128,
                    100816,
                    4,
                    5248,
                    1,
                    8,
                    68,
                    132,
                    3328,
                    8,
                    9376,
                    47984,
                    4137,
                    128,
                    768,
                    384,
                    112,
                    256,
                    234,
                    4,
                    4,
                    64,
                    7048,
                    32,
                    188,
                    832,
                    488,
                ),
                6684,
            ),
            Profile(
                "ayesha_plus_vita",
                "Atelier Ayesha Plus",
                "PCSE00584",
                813056,
                0x0132DC57,
                (
                    47104,
                    7488,
                    4,
                    10512,
                    331788,
                    128,
                    327064,
                    4,
                    3584,
                    1,
                    8,
                    68,
                    1580,
                    1536,
                    8,
                    15632,
                    10004,
                    256,
                    512,
                    108,
                    8000,
                    1024,
                    16800,
                    640,
                    1280,
                    25116,
                    1036,
                    680,
                    400,
                ),
                427,
            ),
        )
    }
)


@dataclass(frozen=True)
class Document:
    profile: Profile
    source: Path
    raw: bytes
    chunks: tuple[tuple[int, int, int], ...]
    context_digest: str = ""


def get_profile(profile_id):
    try:
        return PROFILES[profile_id]
    except (KeyError, TypeError) as error:
        raise SaveError(
            "Select an explicit unregistered Vita Plus research profile."
        ) from error


def decode(raw, profile_id, source=Path("USR-DATA0000")):
    profile = get_profile(profile_id)
    if (
        type(raw) is not bytes
        or len(raw) != profile.size
        or raw[:32] != struct.pack("<I", profile.magic) + bytes(28)
    ):
        raise SaveError(
            "Input does not match the selected original US Vita Plus framing profile."
        )
    offset = 32
    chunks = []
    for tag, size in enumerate(profile.chunk_sizes, 1):
        if struct.unpack_from("<II", raw, offset) != (tag, size):
            raise SaveError("Vita Plus native chunk fingerprint differs.")
        chunks.append((tag, offset + 8, size))
        offset += 8 + size
    if struct.unpack_from("<II", raw, offset) != (
        1024,
        profile.trailer_size,
    ) or offset + profile.trailer_size != len(raw):
        raise SaveError("Vita Plus native trailer bounds differ.")
    chunks.append((1024, offset + 8, profile.trailer_size - 8))
    return Document(profile, Path(source), raw, tuple(chunks))


def title_context(raw, title_id):
    if type(raw) is not bytes or not 20 <= len(raw) <= 4096:
        raise SaveError("Requires bounded original Vita PSF metadata.")
    magic, version, keys, data, count = struct.unpack_from("<5I", raw)
    if (
        magic != 0x46535000
        or version != 0x101
        or not 1 <= count <= 64
        or not 20 + 16 * count <= keys < data <= len(raw)
    ):
        raise SaveError("Original Vita PSF tables are malformed.")
    found = None
    for index in range(count):
        key, encoding, length, capacity, relative = struct.unpack_from(
            "<HH3I", raw, 20 + 16 * index
        )
        start = keys + key
        end = raw.find(b"\0", start, data)
        if not keys <= start < data or end < 0:
            raise SaveError("Original Vita PSF key bounds are malformed.")
        if raw[start:end] != b"PARENT_DIRECTORY":
            continue
        position = data + relative
        if (
            found is not None
            or encoding != 0x204
            or not 1 <= length <= capacity <= 128
            or position < data
            or position + capacity > len(raw)
        ):
            raise SaveError("Original Vita title identity is malformed or duplicated.")
        value = raw[position : position + length]
        if value[-1:] != b"\0" or b"\0" in value[:-1]:
            raise SaveError("Original Vita title identity is unterminated.")
        try:
            found = value[:-1].decode("ascii")
        except UnicodeError as error:
            raise SaveError("Original Vita title identity must be ASCII.") from error
    if found != "/" + title_id:
        raise SaveError("Original Vita metadata belongs to a different title/profile.")
    return hashlib.sha256(raw).hexdigest()


def read_save(path, profile_id):
    profile = get_profile(profile_id)
    path = safe_path(path)
    if path.suffix:
        raise SaveError("Open an extensionless copied USR-DATA gameplay export.")
    metadata = safe_path(path.parent / "sce_sys/param.sfo")
    with metadata.open("rb") as stream:
        context = stream.read(4097)
    digest = title_context(context, profile.title_id)
    with path.open("rb") as stream:
        document = decode(stream.read(profile.size + 1), profile.id, path)
    with metadata.open("rb") as stream:
        if stream.read(4097) != context:
            raise SaveError("Original Vita metadata changed during inspection.")
    return Document(profile, path, document.raw, document.chunks, digest)


def inspect(document):
    if (
        type(document) is not Document
        or not isinstance(document.profile, Profile)
        or document.profile is not get_profile(document.profile.id)
        or not isinstance(document.source, Path)
        or type(document.context_digest) is not str
    ):
        raise SaveError("Inspect a frozen own-profile native snapshot.")
    expected = decode(document.raw, document.profile.id, document.source)
    if (
        type(document.chunks) is not tuple
        or any(
            type(chunk) is not tuple
            or len(chunk) != 3
            or any(type(value) is not int for value in chunk)
            for chunk in document.chunks
        )
        or document.chunks != expected.chunks
    ):
        raise SaveError("Native research chunk snapshot was altered.")
    if (
        document.context_digest
        and read_save(document.source, document.profile.id) != document
    ):
        raise SaveError(
            "The copied gameplay or original Vita metadata changed during inspection."
        )
    tag3 = next(chunk for chunk in document.chunks if chunk[0] == 3)
    return {
        "profile": document.profile.id,
        "title": document.profile.title,
        "platform": "PlayStation Vita",
        "registered_editor": False,
        "read_only": True,
        "source_sha256": hashlib.sha256(document.raw).hexdigest(),
        "original_context_bound": bool(document.context_digest),
        "native_checksum_established": False,
        "game_load_verified": False,
        "uninterpreted_tag_3_u32": struct.unpack_from("<I", document.raw, tag3[1])[0],
        "chunks": [
            {"tag": tag, "offset": offset, "size": size}
            for tag, offset, size in document.chunks
        ],
        "needed": "Own-title complete disk writer/integrity proof and controlled resource/record action pairs before editing. Tag 3 is not promoted to a wallet mapping.",
    }

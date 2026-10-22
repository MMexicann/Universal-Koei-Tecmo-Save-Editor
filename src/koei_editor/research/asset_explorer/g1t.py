"""Bounded, read-only inspection of a small documented G1T subset.

The header and texture-entry layout follows the independently reviewed
``Formats/KTGL/G1T.cs`` in G1Tool at commit
``68c5a42b170d49ea03e3d0b138e7fa8c4a5bdb91``.  This module does not import
G1Tool or its rendering/editor dependencies.  It accepts only the 0600, 0601,
and 0602 header versions and raw BGRA8/RGBA8, DXT1, and DXT5 texture formats.
Other G1T variants are deliberately rejected.

All offsets and mip chains are validated before records are returned. Texture
bytes are copied only by :meth:`TextureRecord.read_mip`, on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct


G1T_MAGIC = b"GT1G"
SUPPORTED_VERSIONS = frozenset((b"0600", b"0601", b"0602"))

# These limits keep malformed input from driving unbounded allocations or
# arithmetic while allowing large, ordinary texture bundles. Parsing itself
# retains only metadata and memory offsets; read_mip() copies one level.
MAX_FILE_SIZE = 512 * 1024 * 1024
MAX_TEXTURE_COUNT = 16_384
MAX_MIP_BYTES = 512 * 1024 * 1024

_HEADER_SIZE = 0x1C
_FORMAT_NAMES = {
    0x01: "BGRA8",
    0x02: "RGBA8",
    0x06: "DXT1",
    0x59: "DXT1",
    0x08: "DXT5",
    0x5B: "DXT5",
}


class G1TFormatError(ValueError):
    """The input is outside the validated G1T subset."""


@dataclass(frozen=True, slots=True)
class TextureRecord:
    """Immutable metadata and a bounded view of one G1T texture.

    ``payload_offset`` and ``payload_size`` identify mip level zero. The
    ``mip_payload_sizes`` tuple gives the complete validated chain. Higher
    levels begin immediately after the preceding level.
    """

    index: int
    width: int
    height: int
    version: str
    format_code: int
    format_name: str
    mip_count: int
    payload_offset: int
    payload_size: int
    mip_payload_sizes: tuple[int, ...]
    entry_end: int
    archive_size: int
    normal_map_flags: int
    flags: int

    def read_mip(self, data: bytes | bytearray | memoryview, level: int = 0) -> bytes:
        """Return one already-validated mip as bytes, copying only on demand."""
        if isinstance(level, bool) or not isinstance(level, int):
            raise TypeError("mip level must be an integer")
        if not 0 <= level < self.mip_count:
            raise IndexError("mip level is outside this texture")

        try:
            view = memoryview(data).cast("B")
        except (BufferError, TypeError, ValueError) as exc:
            raise TypeError("texture source must be a contiguous bytes-like value") from exc
        if len(view) != self.archive_size:
            raise G1TFormatError("texture source size does not match the parsed archive")

        offset = self.payload_offset + sum(self.mip_payload_sizes[:level])
        size = self.mip_payload_sizes[level]
        end = offset + size
        if (offset < self.payload_offset or end < offset
                or end > self.entry_end or end > len(view)):
            raise G1TFormatError("texture mip payload is outside its validated entry")
        return bytes(view[offset:end])


def parse_g1t(data: bytes | bytearray | memoryview) -> tuple[TextureRecord, ...]:
    """Parse the bounded G1Tool-documented subset of a G1T archive.

    Accepted version markers are the ASCII bytes ``0600``, ``0601`` and
    ``0602``. Texture entries support raw BGRA8/RGBA8 and DXT1/DXT5 codes
    documented by G1Tool. Unknown headers, formats, table layouts, and
    truncated/oversized spans raise :class:`G1TFormatError`.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("G1T input must be bytes, bytearray, or memoryview")
    try:
        view = memoryview(data).cast("B")
    except (BufferError, TypeError, ValueError) as exc:
        raise TypeError("G1T input must be a contiguous bytes-like value") from exc

    size = len(view)
    if size > MAX_FILE_SIZE:
        raise G1TFormatError("G1T archive exceeds the configured size limit")
    if size < _HEADER_SIZE:
        raise G1TFormatError("G1T header is truncated")
    if bytes(view[:4]) != G1T_MAGIC:
        raise G1TFormatError("G1T magic is invalid")

    version_bytes = bytes(view[4:8])
    if version_bytes not in SUPPORTED_VERSIONS:
        raise G1TFormatError("G1T version is not in the supported subset")
    version = version_bytes.decode("ascii")

    declared_size, table_offset, texture_count, _unknown_a, _unknown_b = struct.unpack_from(
        "<IIIII", view, 8
    )
    if declared_size > MAX_FILE_SIZE:
        raise G1TFormatError("declared G1T size exceeds the configured size limit")
    if declared_size != size:
        raise G1TFormatError("declared G1T size does not match the input length")
    if texture_count > MAX_TEXTURE_COUNT:
        raise G1TFormatError("G1T texture count exceeds the configured limit")

    # The normal-map flags immediately follow the fixed header. G1Tool writes
    # the offset table after that array; permit intervening padding bytes but
    # require both tables to fit entirely within the declared file.
    normal_flags_offset = _HEADER_SIZE
    normal_flags_end = normal_flags_offset + texture_count * 4
    if normal_flags_end < normal_flags_offset or normal_flags_end > size:
        raise G1TFormatError("G1T normal-map table is truncated")
    if table_offset < normal_flags_end:
        raise G1TFormatError("G1T offset table address is invalid")
    offset_table_end = table_offset + texture_count * 4
    if offset_table_end < table_offset or offset_table_end > size:
        raise G1TFormatError("G1T offset table is truncated")

    normal_flags = tuple(
        struct.unpack_from("<I", view, normal_flags_offset + index * 4)[0]
        for index in range(texture_count)
    )
    relative_offsets = tuple(
        struct.unpack_from("<I", view, table_offset + index * 4)[0]
        for index in range(texture_count)
    )

    entry_starts: list[int] = []
    for relative in relative_offsets:
        absolute = table_offset + relative
        if absolute < offset_table_end or absolute >= size:
            raise G1TFormatError("G1T texture entry offset is outside the data area")
        entry_starts.append(absolute)

    # A table may reference entries in any order. Each payload is bounded by
    # the next distinct entry start, or by the declared archive end.
    ordered_starts = sorted(set(entry_starts))
    next_start = dict(zip(ordered_starts, ordered_starts[1:]))

    records: list[TextureRecord] = []
    for index, start in enumerate(entry_starts):
        entry_end = next_start.get(start, size)
        if entry_end - start < 8:
            raise G1TFormatError("G1T texture header is truncated")

        mip_header, format_code, dimensions = struct.unpack_from("<BBH", view, start)
        mip_count = mip_header >> 4
        if mip_header & 0x0F:
            raise G1TFormatError("G1T texture uses unsupported mip-header flags")
        if mip_count == 0:
            raise G1TFormatError("G1T texture mip count must be nonzero")
        format_name = _FORMAT_NAMES.get(format_code)
        if format_name is None:
            raise G1TFormatError(f"G1T texture format 0x{format_code:02X} is unsupported")
        if dimensions & 0xFF00:
            raise G1TFormatError("G1T texture dimensions use unsupported high bits")

        width = 1 << (dimensions & 0x0F)
        height = 1 << ((dimensions >> 4) & 0x0F)
        max_chain = max(width, height).bit_length()
        if mip_count > max_chain:
            raise G1TFormatError("G1T texture mip count exceeds its dimensions")

        flags = struct.unpack_from("<I", view, start + 4)[0]
        payload_offset = start + 8 + (12 if (flags >> 24) == 0x10 else 0)
        if payload_offset > entry_end:
            raise G1TFormatError("G1T texture extended header is truncated")

        mip_sizes = tuple(
            _mip_size(format_name, max(1, width >> level), max(1, height >> level))
            for level in range(mip_count)
        )
        total_payload_size = sum(mip_sizes)
        if total_payload_size > MAX_MIP_BYTES:
            raise G1TFormatError("G1T texture mip chain exceeds the configured size limit")
        payload_end = payload_offset + total_payload_size
        if payload_end < payload_offset or payload_end > entry_end or payload_end > size:
            raise G1TFormatError("G1T texture mip chain exceeds its bounded entry")

        records.append(TextureRecord(
            index=index,
            width=width,
            height=height,
            version=version,
            format_code=format_code,
            format_name=format_name,
            mip_count=mip_count,
            payload_offset=payload_offset,
            payload_size=mip_sizes[0],
            mip_payload_sizes=mip_sizes,
            entry_end=entry_end,
            archive_size=size,
            normal_map_flags=normal_flags[index],
            flags=flags,
        ))

    return tuple(records)


def _mip_size(format_name: str, width: int, height: int) -> int:
    """Return the byte size for one raw or block-compressed mip level."""
    if format_name in ("BGRA8", "RGBA8"):
        size = width * height * 4
    else:
        block_bytes = 8 if format_name == "DXT1" else 16
        size = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block_bytes
    if size <= 0 or size > MAX_MIP_BYTES:
        raise G1TFormatError("G1T texture mip exceeds the configured size limit")
    return size

"""Bounded, read-only inspection of standard ZIP containers.

This module identifies ZIP structure only. It does not identify a game, unpack
members to disk, or infer that a ZIP belongs to a Koei Tecmo title.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
import stat
import struct
import unicodedata
import zipfile
import zlib
from typing import Any, Iterator


MAX_MEMBERS = 100_000
MAX_CENTRAL_DIRECTORY_BYTES = 64 * 1024 * 1024
MAX_MEMBER_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
DEFAULT_MAX_READ_BYTES = 64 * 1024 * 1024

_EOCD = struct.Struct("<4s4H2LH")
_ZIP64_LOCATOR = struct.Struct("<4sLQL")
_ZIP64_EOCD = struct.Struct("<4sQ2H2L4Q")
_CENTRAL_HEADER = struct.Struct("<4s6H3I5H2I")
_EOCD_SIGNATURE = b"PK\x05\x06"
_ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
_ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
_CENTRAL_SIGNATURE = b"PK\x01\x02"
_DIGITAL_SIGNATURE = b"PK\x05\x05"
_SUPPORTED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_EOCD_SEARCH_BYTES = 22 + 0xFFFF


class ZipArchiveError(ValueError):
    """Raised for unsupported or unsafe ZIP structure or member data."""


@dataclass(frozen=True, slots=True)
class ZipMember:
    """Immutable central-directory metadata for one member."""

    id: str
    index: int
    name: str
    offset: int
    size: int
    compressed_size: int
    crc32: int
    compression: int
    flag_bits: int
    is_directory: bool


@dataclass(frozen=True, slots=True)
class ZipArchive:
    """ZIP member listing; the source remains owned by the caller."""

    entries: tuple[ZipMember, ...]


@dataclass(frozen=True, slots=True)
class _DirectoryInfo:
    count: int


class _MemoryReader:
    """Seekable file-like view over a bytes-like object without whole-copying."""

    def __init__(self, buffer: Any) -> None:
        try:
            view = memoryview(buffer)
        except TypeError as exc:
            raise ZipArchiveError("ZIP buffer must support the buffer protocol") from exc
        if not view.c_contiguous:
            view.release()
            raise ZipArchiveError("ZIP buffer must be contiguous")
        try:
            self._view = view.cast("B")
        except (TypeError, ValueError) as exc:
            view.release()
            raise ZipArchiveError("ZIP buffer must be byte-addressable") from exc
        if self._view is not view:
            view.release()
        self._position = 0

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_SET:
            position = offset
        elif whence == os.SEEK_CUR:
            position = self._position + offset
        elif whence == os.SEEK_END:
            position = len(self._view) + offset
        else:
            raise ValueError("invalid seek origin")
        if position < 0:
            raise ValueError("negative seek position")
        self._position = position
        return position

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            end = len(self._view)
        else:
            end = min(len(self._view), self._position + size)
        start = min(self._position, len(self._view))
        self._position = end
        return bytes(self._view[start:end])

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def close(self) -> None:
        # ZipFile does not own a file-like object passed to its constructor.
        # Release the buffer view in the surrounding source context instead.
        pass

    def release(self) -> None:
        self._view.release()


class _SeekableProxy:
    """Supply the file methods ZipFile needs for mmap and custom streams."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream

    def tell(self) -> int:
        return self._stream.tell()

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        return self._stream.seek(offset, whence)

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def close(self) -> None:
        pass


@contextmanager
def _open_source(source: Any) -> Iterator[Any]:
    """Open a path, preserve a caller stream's position, or view bytes in place."""

    if isinstance(source, (str, os.PathLike)):
        try:
            stream = open(source, "rb")
        except OSError as exc:
            raise ZipArchiveError(f"could not read ZIP source: {exc}") from exc
        with stream:
            yield stream
        return

    if isinstance(source, (bytes, bytearray, memoryview)):
        reader = _MemoryReader(source)
        try:
            yield reader
        finally:
            reader.release()
        return

    if not all(hasattr(source, attr) for attr in ("read", "seek", "tell")):
        raise ZipArchiveError("source must be a path, bytes-like object, or seekable binary stream")
    seekable = getattr(source, "seekable", None)
    if callable(seekable) and not seekable():
        raise ZipArchiveError("file-like ZIP sources must be seekable")
    try:
        original_position = source.tell()
        source.seek(0)
    except (OSError, ValueError, TypeError) as exc:
        raise ZipArchiveError("file-like ZIP sources must seek to byte zero") from exc
    try:
        yield _SeekableProxy(source)
    finally:
        try:
            source.seek(original_position)
        except (OSError, ValueError, TypeError):
            pass


def _read_at(stream: Any, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0:
        raise ZipArchiveError("ZIP directory has a negative offset or size")
    try:
        stream.seek(offset)
        data = stream.read(size)
    except (OSError, ValueError, TypeError) as exc:
        raise ZipArchiveError("could not seek within ZIP source") from exc
    if not isinstance(data, bytes) or len(data) != size:
        raise ZipArchiveError("ZIP source ended unexpectedly")
    return data


def _find_eocd(stream: Any, source_size: int) -> tuple[int, tuple[Any, ...]]:
    tail_size = min(source_size, _EOCD_SEARCH_BYTES)
    tail_start = source_size - tail_size
    tail = _read_at(stream, tail_start, tail_size)
    position = tail.rfind(_EOCD_SIGNATURE)
    while position >= 0:
        if position + _EOCD.size <= len(tail):
            fields = _EOCD.unpack_from(tail, position)
            comment_size = fields[-1]
            if position + _EOCD.size + comment_size == len(tail):
                return tail_start + position, fields
        position = tail.rfind(_EOCD_SIGNATURE, 0, position)
    raise ZipArchiveError("ZIP end-of-central-directory record is missing or malformed")


def _preflight_directory(stream: Any) -> _DirectoryInfo:
    """Bound directory size/count before zipfile allocates ZipInfo records."""

    try:
        stream.seek(0, os.SEEK_END)
        source_size = stream.tell()
    except (OSError, ValueError, TypeError) as exc:
        raise ZipArchiveError("ZIP source must be seekable") from exc
    eocd_offset, end = _find_eocd(stream, source_size)
    disk_number, directory_disk, disk_count, total_count = end[1:5]
    central_size, central_offset = end[5:7]
    central_end = eocd_offset

    locator_offset = eocd_offset - _ZIP64_LOCATOR.size
    has_zip64_locator = False
    if locator_offset >= 0:
        locator = _read_at(stream, locator_offset, _ZIP64_LOCATOR.size)
        has_zip64_locator = locator[:4] == _ZIP64_LOCATOR_SIGNATURE

    zip64_required = (
        total_count == 0xFFFF
        or disk_count == 0xFFFF
        or central_size == 0xFFFFFFFF
        or central_offset == 0xFFFFFFFF
    )
    if has_zip64_locator or zip64_required:
        if not has_zip64_locator:
            raise ZipArchiveError("ZIP64 end record is missing")
        _, locator_disk, zip64_offset, disk_total = _ZIP64_LOCATOR.unpack(
            _read_at(stream, locator_offset, _ZIP64_LOCATOR.size)
        )
        if locator_disk != 0 or disk_total != 1:
            raise ZipArchiveError("multi-disk ZIP64 archives are unsupported")
        zip64_values = _ZIP64_EOCD.unpack(
            _read_at(stream, zip64_offset, _ZIP64_EOCD.size)
        )
        if zip64_values[0] != _ZIP64_EOCD_SIGNATURE:
            raise ZipArchiveError("ZIP64 end record has an invalid signature")
        record_size = zip64_values[1]
        if record_size < _ZIP64_EOCD.size - 12:
            raise ZipArchiveError("ZIP64 end record is truncated")
        if zip64_offset + 12 + record_size > locator_offset:
            raise ZipArchiveError("ZIP64 end record extends beyond its locator")
        disk_number, directory_disk = zip64_values[4:6]
        disk_count, total_count = zip64_values[6:8]
        central_size, central_offset = zip64_values[8:10]
        central_end = zip64_offset

    if disk_number != 0 or directory_disk != 0 or disk_count != total_count:
        raise ZipArchiveError("multi-disk ZIP archives are unsupported")
    if total_count > MAX_MEMBERS:
        raise ZipArchiveError(f"ZIP member count exceeds {MAX_MEMBERS}")
    if central_size > MAX_CENTRAL_DIRECTORY_BYTES:
        raise ZipArchiveError(
            f"ZIP central directory exceeds {MAX_CENTRAL_DIRECTORY_BYTES} bytes"
        )
    if central_size > central_end:
        raise ZipArchiveError("ZIP central directory lies outside the source")

    central_start = central_end - central_size
    # Self-extracting ZIPs may have a prefix. The recorded offset is relative
    # to the ZIP portion, while central_start is the absolute source position.
    if central_offset > central_start:
        raise ZipArchiveError("ZIP central directory offset is outside the source")
    if central_start + central_size > source_size:
        raise ZipArchiveError("ZIP central directory extends beyond the source")

    _scan_directory_records(stream, central_start, central_size, total_count)
    return _DirectoryInfo(total_count)


def _scan_directory_records(stream: Any, start: int, size: int, count: int) -> None:
    """Check every central record boundary without allocating member objects."""

    end = start + size
    cursor = start
    for _ in range(count):
        if cursor + _CENTRAL_HEADER.size > end:
            raise ZipArchiveError("ZIP central directory is truncated")
        header = _read_at(stream, cursor, _CENTRAL_HEADER.size)
        fields = _CENTRAL_HEADER.unpack(header)
        if fields[0] != _CENTRAL_SIGNATURE:
            raise ZipArchiveError("ZIP central directory contains an invalid record")
        name_size, extra_size, comment_size = fields[10:13]
        record_size = _CENTRAL_HEADER.size + name_size + extra_size + comment_size
        if record_size > end - cursor:
            raise ZipArchiveError("ZIP central directory record exceeds its declared bounds")
        cursor += record_size

    remaining = end - cursor
    if remaining:
        # ZIP permits an optional central-directory digital-signature record.
        if remaining < 6:
            raise ZipArchiveError("ZIP central directory has trailing malformed bytes")
        trailer = _read_at(stream, cursor, remaining)
        if trailer[:4] != _DIGITAL_SIGNATURE:
            raise ZipArchiveError("ZIP central directory has unexpected trailing bytes")
        signature_size = struct.unpack_from("<H", trailer, 4)[0]
        if signature_size != remaining - 6:
            raise ZipArchiveError("ZIP central-directory signature has invalid bounds")


def _member_path(info: zipfile.ZipInfo) -> tuple[str, bool]:
    original = getattr(info, "orig_filename", info.filename)
    if not original or "\x00" in original:
        raise ZipArchiveError("ZIP member has an empty or NUL-containing name")
    if any(ord(char) < 32 or ord(char) == 127 for char in original):
        raise ZipArchiveError("ZIP member name contains a control character")
    if "\\" in original:
        raise ZipArchiveError("ZIP member name contains a backslash separator")
    if original.startswith("/") or original.startswith("\\"):
        raise ZipArchiveError("ZIP member name is absolute")

    is_directory = info.is_dir()
    name_without_slash = original[:-1] if original.endswith("/") else original
    components = name_without_slash.split("/")
    if any(component in ("", ".", "..") for component in components):
        raise ZipArchiveError("ZIP member name contains an unsafe path component")
    if any(":" in component for component in components):
        raise ZipArchiveError("ZIP member name contains a drive or stream separator")

    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    if file_type == stat.S_IFLNK:
        raise ZipArchiveError("ZIP symbolic links are unsupported")
    if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise ZipArchiveError("ZIP special files are unsupported")
    if file_type == stat.S_IFDIR:
        if not original.endswith("/"):
            raise ZipArchiveError("ZIP directory entry is missing its trailing slash")
        is_directory = True
    elif is_directory and file_type == stat.S_IFREG:
        raise ZipArchiveError("ZIP member has conflicting file and directory metadata")

    normalized = "/".join(unicodedata.normalize("NFC", part).casefold() for part in components)
    return normalized, is_directory


def _validate_infos(infos: list[zipfile.ZipInfo], expected_count: int) -> ZipArchive:
    if len(infos) != expected_count:
        raise ZipArchiveError("ZIP central-directory member count does not match its end record")
    if len(infos) > MAX_MEMBERS:
        raise ZipArchiveError(f"ZIP member count exceeds {MAX_MEMBERS}")

    members: list[ZipMember] = []
    normalized_paths: dict[str, bool] = {}
    total_size = 0
    for index, info in enumerate(infos):
        if info.flag_bits & (0x0001 | 0x0040):
            raise ZipArchiveError(f"ZIP member {index} is encrypted")
        if info.compress_type not in _SUPPORTED_COMPRESSION:
            raise ZipArchiveError(f"ZIP member {index} uses unsupported compression")
        normalized, is_directory = _member_path(info)
        if normalized in normalized_paths:
            raise ZipArchiveError("ZIP contains duplicate or conflicting member names")
        normalized_paths[normalized] = is_directory

        if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
            raise ZipArchiveError(f"ZIP member {index} exceeds the uncompressed-size limit")
        total_size += info.file_size
        if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ZipArchiveError("ZIP total uncompressed size exceeds the archive limit")
        if info.file_size and info.compress_size == 0:
            raise ZipArchiveError(f"ZIP member {index} has an invalid zero compressed size")
        if info.file_size > info.compress_size * MAX_COMPRESSION_RATIO:
            raise ZipArchiveError(f"ZIP member {index} exceeds the compression-ratio limit")
        if is_directory and info.file_size:
            raise ZipArchiveError(f"ZIP directory member {index} contains payload bytes")

        member_id = f"zip:{index:06d}:{info.header_offset:016x}:{info.CRC:08x}"
        members.append(
            ZipMember(
                id=member_id,
                index=index,
                name=info.filename,
                offset=info.header_offset,
                size=info.file_size,
                compressed_size=info.compress_size,
                crc32=info.CRC,
                compression=info.compress_type,
                flag_bits=info.flag_bits,
                is_directory=is_directory,
            )
        )

    # All names have already been indexed, so checking each entry's ancestors
    # catches a file/child collision in either central-directory order. Do not
    # scan every other entry for descendants: flat archives may contain up to
    # MAX_MEMBERS names and that redundant scan makes indexing quadratic.
    for normalized in normalized_paths:
        components = normalized.split("/")
        for length in range(1, len(components)):
            parent = "/".join(components[:length])
            if normalized_paths.get(parent) is False:
                raise ZipArchiveError("ZIP contains a file/directory path conflict")

    return ZipArchive(tuple(members))


def _inspect_stream(stream: Any) -> tuple[ZipArchive, list[zipfile.ZipInfo]]:
    directory = _preflight_directory(stream)
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream, mode="r", allowZip64=True) as zipped:
            infos = zipped.infolist()
            archive = _validate_infos(infos, directory.count)
            return archive, infos
    except ZipArchiveError:
        raise
    except (zipfile.BadZipFile, OSError, EOFError, ValueError, struct.error) as exc:
        raise ZipArchiveError(f"invalid ZIP archive: {exc}") from exc


def parse_zip_archive(source: Any) -> ZipArchive:
    """List a standard ZIP's safe member metadata without extracting files.

    Paths, bytes-like values, and seekable binary streams are supported. Only
    stored and deflate members are listed. Names are not treated as game IDs.
    """

    with _open_source(source) as stream:
        archive, _ = _inspect_stream(stream)
        return archive


def read_member(
    source: Any,
    member: ZipMember,
    *,
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> bytes:
    """Read one member into memory, bounded by `max_bytes`, and verify its CRC."""

    if not isinstance(member, ZipMember):
        raise ZipArchiveError("member must come from a parsed ZIP archive")
    if type(max_bytes) is not int or max_bytes < 0:
        raise ZipArchiveError("max_bytes must be a non-negative integer")
    if member.index < 0:
        raise ZipArchiveError("member index is invalid")
    if member.is_directory:
        raise ZipArchiveError("directory members have no readable payload")
    if member.size > max_bytes:
        raise ZipArchiveError(f"ZIP member exceeds the {max_bytes}-byte read limit")

    with _open_source(source) as stream:
        archive, infos = _inspect_stream(stream)
        if member.index >= len(archive.entries) or archive.entries[member.index] != member:
            raise ZipArchiveError("member does not match the current ZIP source")
        try:
            with zipfile.ZipFile(stream, mode="r", allowZip64=True) as zipped:
                chunks: list[bytes] = []
                total = 0
                with zipped.open(infos[member.index], mode="r") as payload:
                    while True:
                        chunk = payload.read(min(64 * 1024, max_bytes - total + 1))
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes or total > member.size:
                            raise ZipArchiveError("ZIP member expanded beyond its validated size")
                        chunks.append(chunk)
                if total != member.size:
                    raise ZipArchiveError("ZIP member size does not match its central directory")
                result = b"".join(chunks)
                if zlib.crc32(result) & 0xFFFFFFFF != member.crc32:
                    raise ZipArchiveError("ZIP member failed CRC validation")
                return result
        except ZipArchiveError:
            raise
        except zipfile.BadZipFile as exc:
            raise ZipArchiveError("ZIP member failed CRC or structure validation") from exc
        except (OSError, EOFError, RuntimeError, NotImplementedError, struct.error, zlib.error) as exc:
            raise ZipArchiveError(f"could not read ZIP member: {exc}") from exc


__all__ = [
    "DEFAULT_MAX_READ_BYTES",
    "MAX_CENTRAL_DIRECTORY_BYTES",
    "MAX_COMPRESSION_RATIO",
    "MAX_MEMBERS",
    "MAX_MEMBER_UNCOMPRESSED_BYTES",
    "MAX_TOTAL_UNCOMPRESSED_BYTES",
    "ZipArchive",
    "ZipArchiveError",
    "ZipMember",
    "parse_zip_archive",
    "read_member",
]

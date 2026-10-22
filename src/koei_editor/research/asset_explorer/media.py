"""Bounded, read-only previews for common local game-asset media.

All public functions accept bytes-like input only.  They never open a path,
follow a URI, invoke another process, write a file, or play audio.  Optional
decoders are imported only by the function that needs them.
"""

from __future__ import annotations

import array
import importlib
import io
import json
import math
import struct
import zlib
from dataclasses import dataclass


MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_IMAGE_PIXELS = 4_194_304
MAX_AUDIO_PREVIEW_SECONDS = 5
MAX_AUDIO_PREVIEW_RATE = 22_050
MAX_AUDIO_PREVIEW_FRAMES = MAX_AUDIO_PREVIEW_SECONDS * MAX_AUDIO_PREVIEW_RATE
MAX_WAVEFORM_POINTS = 1_024
MAX_MESH_VERTICES = 50_000
MAX_MESH_FACES = 100_000
MAX_GLTF_JSON_BYTES = 2 * 1024 * 1024
MAX_GLTF_NODES = 10_000
MAX_GLTF_MATERIALIZED_BYTES = 128 * 1024 * 1024
MAX_PLY_HEADER_BYTES = 64 * 1024
MAX_PNG_CHUNKS = 4_096
MAX_TEXT_LINE_CHARS = 256 * 1024
MAX_TEXT_LINES = 1_000_000
_UNSUPPORTED_GLTF_EXTENSIONS = frozenset({"KHR_draco_mesh_compression", "EXT_meshopt_compression"})


class AssetInspectionError(ValueError):
    """The supplied bytes are malformed, unsupported, or exceed a safe cap."""


class AssetDependencyError(RuntimeError):
    """An optional, permissively licensed media decoder is not installed."""


@dataclass(frozen=True, slots=True)
class ImagePreview:
    format: str
    width: int
    height: int
    mode: str
    rgba_bytes: bytes


@dataclass(frozen=True, slots=True)
class AudioPreview:
    format: str
    channels: int
    sample_rate: int
    duration_seconds: float | None
    waveform: tuple[float, ...]
    preview_sample_rate: int
    preview_frames: int
    preview_duration_seconds: float
    truncated: bool


@dataclass(frozen=True, slots=True)
class MeshPreview:
    format: str
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]
    vertex_count: int
    face_count: int
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True, slots=True)
class _AudioSourceInfo:
    channels: int
    sample_rate: int
    frames: int | None

    @property
    def duration(self) -> float | None:
        if self.frames is None:
            return None
        return self.frames / self.sample_rate


def _bytes(data: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("asset data must be bytes-like; file paths are not accepted")
    if len(data) > MAX_INPUT_BYTES:
        raise AssetInspectionError(f"asset exceeds the {MAX_INPUT_BYTES}-byte input cap")
    return bytes(data)


def _extension(extension: str, allowed: set[str]) -> str:
    if not isinstance(extension, str):
        raise TypeError("extension must be a string")
    normalized = extension.strip().lower().lstrip(".")
    if normalized not in allowed:
        raise AssetInspectionError(f"unsupported asset extension: {extension!r}")
    return normalized


def _optional_import(module: str, label: str):
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise AssetDependencyError(
            f"{label} preview needs the optional {module} package"
        ) from exc


def _iter_text_lines(text: str):
    """Yield universal-newline text with bounded line size and record count."""

    stream = io.StringIO(text, newline=None)
    for _ in range(MAX_TEXT_LINES):
        line = stream.readline(MAX_TEXT_LINE_CHARS + 2)
        if not line:
            return
        line = line.removesuffix("\n")
        if len(line) > MAX_TEXT_LINE_CHARS:
            raise AssetInspectionError("text model line exceeds the inspection cap")
        yield line
    if stream.read(1):
        raise AssetInspectionError("text model line count exceeds the inspection cap")


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    corner_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= corner_distance:
        return left
    if above_distance <= corner_distance:
        return above
    return upper_left


def _png_decode(raw: bytes) -> ImagePreview:
    signature = b"\x89PNG\r\n\x1a\n"
    if not raw.startswith(signature):
        raise AssetInspectionError("PNG signature is missing")
    offset = len(signature)
    width = height = color_type = 0
    palette: bytes | None = None
    transparency = b""
    idat = bytearray()
    saw_ihdr = saw_idat = saw_iend = idat_closed = False
    chunk_count = 0
    while offset < len(raw):
        chunk_count += 1
        if chunk_count > MAX_PNG_CHUNKS:
            raise AssetInspectionError("PNG chunk count exceeds the inspection cap")
        if offset + 12 > len(raw):
            raise AssetInspectionError("PNG chunk header is truncated")
        length = struct.unpack_from(">I", raw, offset)[0]
        kind = raw[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(raw):
            raise AssetInspectionError("PNG chunk extends past the input")
        body = memoryview(raw)[offset + 8 : offset + 8 + length]
        checksum = struct.unpack_from(">I", raw, offset + 8 + length)[0]
        if zlib.crc32(body, zlib.crc32(kind)) & 0xFFFFFFFF != checksum:
            raise AssetInspectionError("PNG chunk checksum is invalid")
        if any(not (65 <= char <= 90 or 97 <= char <= 122) for char in kind):
            raise AssetInspectionError("PNG chunk type is malformed")
        if not saw_ihdr and kind != b"IHDR":
            raise AssetInspectionError("PNG IHDR must be the first chunk")
        if kind == b"IHDR":
            if saw_ihdr or length != 13:
                raise AssetInspectionError("PNG IHDR is duplicated or malformed")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", body
            )
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                raise AssetInspectionError("image dimensions exceed the preview cap")
            if bit_depth != 8 or color_type not in {2, 3, 6}:
                raise AssetInspectionError("PNG must use 8-bit RGB, RGBA or indexed color")
            if compression != 0 or filtering != 0 or interlace != 0:
                raise AssetInspectionError("unsupported PNG compression, filter or interlace mode")
            saw_ihdr = True
        elif kind == b"PLTE":
            if saw_idat or palette is not None or color_type not in {2, 3, 6}:
                raise AssetInspectionError("PNG palette is misplaced or unsupported")
            if not body or len(body) > 768 or len(body) % 3:
                raise AssetInspectionError("PNG palette length is invalid")
            palette = bytes(body)
        elif kind == b"tRNS":
            if saw_idat or color_type != 3 or transparency:
                raise AssetInspectionError("PNG transparency table is misplaced or unsupported")
            if not body:
                raise AssetInspectionError("PNG transparency table is empty")
            transparency = bytes(body)
        elif kind == b"IDAT":
            if idat_closed:
                raise AssetInspectionError("PNG IDAT chunks are not consecutive")
            if color_type == 3 and palette is None:
                raise AssetInspectionError("indexed PNG is missing its palette")
            saw_idat = True
            idat.extend(body)
        elif kind == b"IEND":
            if length != 0 or not saw_idat or end != len(raw):
                raise AssetInspectionError("PNG IEND is malformed or not the final chunk")
            saw_iend = True
            offset = end
            break
        else:
            if saw_idat:
                idat_closed = True
            # Unknown critical chunks affect image decoding; ancillary metadata
            # is safely ignored because it does not change the decoded pixels.
            if 65 <= kind[0] <= 90:
                raise AssetInspectionError("PNG contains an unsupported critical chunk")
        if saw_idat and kind != b"IDAT":
            idat_closed = True
        offset = end
    if not saw_iend or offset != len(raw):
        raise AssetInspectionError("PNG is missing its final IEND chunk")
    if palette is not None and len(transparency) > len(palette) // 3:
        raise AssetInspectionError("PNG transparency table exceeds its palette")

    channels = {2: 3, 3: 1, 6: 4}[color_type]
    row_bytes = width * channels
    expected = height * (row_bytes + 1)
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(idat, expected + 1)
    except zlib.error as exc:
        raise AssetInspectionError("PNG image data is malformed") from exc
    if (
        len(decoded) != expected
        or not inflater.eof
        or inflater.unused_data
        or inflater.unconsumed_tail
    ):
        raise AssetInspectionError("PNG image data does not match its dimensions")

    rgba = bytearray(width * height * 4)
    previous = bytearray(row_bytes)
    source_offset = 0
    palette_count = len(palette) // 3 if palette else 0
    for y in range(height):
        filter_type = decoded[source_offset]
        source_offset += 1
        scanline = bytearray(decoded[source_offset : source_offset + row_bytes])
        source_offset += row_bytes
        if filter_type > 4:
            raise AssetInspectionError("PNG scanline uses an unsupported filter")
        for i in range(row_bytes):
            left = scanline[i - channels] if i >= channels else 0
            above = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                predictor = _paeth(left, above, upper_left)
            else:
                predictor = 0
            scanline[i] = (scanline[i] + predictor) & 0xFF
        target = y * width * 4
        if color_type == 2:
            for x in range(width):
                source = x * 3
                dest = target + x * 4
                rgba[dest : dest + 4] = bytes((*scanline[source : source + 3], 255))
        elif color_type == 6:
            rgba[target : target + width * 4] = scanline
        else:
            assert palette is not None
            for x, palette_index in enumerate(scanline):
                if palette_index >= palette_count:
                    raise AssetInspectionError("PNG pixel references a missing palette entry")
                source = palette_index * 3
                dest = target + x * 4
                alpha = transparency[palette_index] if palette_index < len(transparency) else 255
                rgba[dest : dest + 4] = palette[source : source + 3] + bytes((alpha,))
        previous = scanline
    return ImagePreview("PNG", width, height, "RGBA", bytes(rgba))


def _rgb565(value: int) -> tuple[int, int, int]:
    red = (value >> 11) & 0x1F
    green = (value >> 5) & 0x3F
    blue = value & 0x1F
    return (red << 3) | (red >> 2), (green << 2) | (green >> 4), (blue << 3) | (blue >> 2)


def _dxt_decode(data: bytes, width: int, height: int, pixel_format: str) -> bytes:
    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
        raise AssetInspectionError("texture dimensions exceed the preview cap")
    if pixel_format not in {"DXT1", "DXT5"}:
        raise AssetInspectionError("only DXT1 and DXT5 payloads are supported")
    block_size = 8 if pixel_format == "DXT1" else 16
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    expected = blocks_x * blocks_y * block_size
    if len(data) != expected:
        raise AssetInspectionError("compressed texture length does not match its dimensions")
    rgba = bytearray(width * height * 4)
    offset = 0
    for block_y in range(blocks_y):
        for block_x in range(blocks_x):
            alpha_values: list[int] | None = None
            alpha_selectors = 0
            if pixel_format == "DXT5":
                alpha0, alpha1 = data[offset], data[offset + 1]
                alpha_selectors = int.from_bytes(data[offset + 2 : offset + 8], "little")
                if alpha0 > alpha1:
                    alpha_values = [alpha0, alpha1] + [
                        ((8 - index) * alpha0 + (index - 1) * alpha1) // 7
                        for index in range(2, 8)
                    ]
                else:
                    alpha_values = [alpha0, alpha1] + [
                        ((6 - index) * alpha0 + (index - 1) * alpha1) // 5
                        for index in range(2, 6)
                    ] + [0, 255]
                offset += 8
            color0, color1, selectors = struct.unpack_from("<HHI", data, offset)
            offset += 8
            first = _rgb565(color0)
            second = _rgb565(color1)
            if pixel_format == "DXT1" and color0 <= color1:
                colors = [
                    (*first, 255),
                    (*second, 255),
                    (tuple((first[c] + second[c]) // 2 for c in range(3)) + (255,)),
                    (0, 0, 0, 0),
                ]
            else:
                colors = [
                    (*first, 255),
                    (*second, 255),
                    (tuple((2 * first[c] + second[c]) // 3 for c in range(3)) + (255,)),
                    (tuple((first[c] + 2 * second[c]) // 3 for c in range(3)) + (255,)),
                ]
            for local_y in range(4):
                y = block_y * 4 + local_y
                if y >= height:
                    continue
                for local_x in range(4):
                    x = block_x * 4 + local_x
                    if x >= width:
                        continue
                    pixel = local_y * 4 + local_x
                    color = colors[(selectors >> (pixel * 2)) & 3]
                    if alpha_values is not None:
                        color = color[:3] + (alpha_values[(alpha_selectors >> (pixel * 3)) & 7],)
                    dest = (y * width + x) * 4
                    rgba[dest : dest + 4] = bytes(color)
    return bytes(rgba)


def _dds_decode(raw: bytes) -> ImagePreview:
    if len(raw) < 128 or raw[:4] != b"DDS ":
        raise AssetInspectionError("DDS header is missing or truncated")
    header_size, flags, height, width = struct.unpack_from("<4I", raw, 4)
    pixel_format_size, pixel_flags = struct.unpack_from("<2I", raw, 76)
    fourcc = raw[84:88]
    mip_count = struct.unpack_from("<I", raw, 28)[0]
    caps = struct.unpack_from("<I", raw, 108)[0]
    if header_size != 124 or pixel_format_size != 32 or not (pixel_flags & 0x4):
        raise AssetInspectionError("DDS header structure is unsupported")
    if not (flags & 0x1 and flags & 0x2 and flags & 0x4 and flags & 0x1000):
        raise AssetInspectionError("DDS header is missing required flags")
    if not caps & 0x1000 or mip_count > 1:
        raise AssetInspectionError("DDS must contain a single texture level")
    try:
        pixel_format = fourcc.decode("ascii")
    except UnicodeDecodeError as exc:
        raise AssetInspectionError("DDS FourCC is invalid") from exc
    width, height = int(width), int(height)
    rgba = _dxt_decode(raw[128:], width, height, pixel_format)
    return ImagePreview("DDS", width, height, "RGBA", rgba)


def inspect_image(data: bytes | bytearray | memoryview, extension: str) -> ImagePreview:
    """Decode a bounded PNG or DXT1/DXT5 DDS image from memory into RGBA."""

    raw = _bytes(data)
    ext = _extension(extension, {"png", "dds"})
    if not raw:
        raise AssetInspectionError("image is empty")
    return _png_decode(raw) if ext == "png" else _dds_decode(raw)


def decode_g1t_texture(
    data: bytes | bytearray | memoryview,
    width: int,
    height: int,
    pixel_format: str,
) -> ImagePreview:
    """Convert bounded G1T RGBA/BGRA or DXT1/DXT5 pixel bytes to RGBA."""

    raw = _bytes(data)
    fmt = pixel_format.strip().upper() if isinstance(pixel_format, str) else ""
    if fmt not in {"RGBA8", "BGRA8", "DXT1", "DXT5"}:
        raise AssetInspectionError(f"unsupported G1T texture pixel format: {pixel_format!r}")
    if not isinstance(width, int) or not isinstance(height, int):
        raise TypeError("texture dimensions must be integers")
    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
        raise AssetInspectionError("texture dimensions exceed the preview cap")
    if fmt in {"RGBA8", "BGRA8"}:
        expected = width * height * 4
        if len(raw) != expected:
            raise AssetInspectionError("raw texture length does not match its dimensions")
        if fmt == "RGBA8":
            rgba = raw
        else:
            converted = bytearray(expected)
            converted[0::4] = raw[2::4]
            converted[1::4] = raw[1::4]
            converted[2::4] = raw[0::4]
            converted[3::4] = raw[3::4]
            rgba = bytes(converted)
        return ImagePreview(f"G1T-{fmt}", width, height, "RGBA", rgba)
    rgba = _dxt_decode(raw, width, height, fmt)
    return ImagePreview(f"G1T-{fmt}", width, height, "RGBA", rgba)


def _valid_source_info(channels: int, sample_rate: int, frames: int | None) -> _AudioSourceInfo:
    if not (1 <= channels <= 8):
        raise AssetInspectionError("audio channel count is outside the supported range")
    if not (8_000 <= sample_rate <= 384_000):
        raise AssetInspectionError("audio sample rate is outside the supported range")
    if frames == 0:
        frames = None
    if frames is not None and (frames < 0 or frames > sample_rate * 24 * 60 * 60):
        raise AssetInspectionError("audio duration is outside the 24-hour inspection cap")
    return _AudioSourceInfo(channels, sample_rate, frames)


def _audio_signature_matches(data: bytes, extension: str) -> bool:
    if extension == "wav":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if extension == "flac":
        return data.startswith(b"fLaC")
    if extension in {"ogg", "vorbis"}:
        return data.startswith(b"OggS")
    cursor = 0
    if data.startswith(b"ID3"):
        if len(data) < 10 or any(value & 0x80 for value in data[6:10]):
            return False
        tag_size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        cursor = 10 + tag_size + (10 if data[5] & 0x10 else 0)
    if cursor + 4 > len(data):
        return False
    header = int.from_bytes(data[cursor : cursor + 4], "big")
    version = (header >> 19) & 0x3
    layer = (header >> 17) & 0x3
    bitrate = (header >> 12) & 0xF
    sample_rate = (header >> 10) & 0x3
    return (header >> 21) == 0x7FF and version != 1 and layer == 1 and bitrate not in {0, 15} and sample_rate != 3


def _audio_info(miniaudio, data: bytes, extension: str) -> tuple[str, _AudioSourceInfo]:
    if extension == "wav":
        label, getter = "WAV", miniaudio.wav_get_info
    elif extension == "flac":
        label, getter = "FLAC", miniaudio.flac_get_info
    elif extension in {"ogg", "vorbis"}:
        label, getter = "Vorbis", miniaudio.vorbis_get_info
    else:
        label, getter = "MP3", miniaudio.mp3_get_info
    try:
        info = getter(data)
    except Exception as exc:
        raise AssetInspectionError(f"malformed or unsupported {label} audio stream") from exc
    return label, _valid_source_info(info.nchannels, info.sample_rate, info.num_frames)


def _waveform(samples: array.array, points: int = MAX_WAVEFORM_POINTS) -> tuple[float, ...]:
    count = len(samples)
    if not count:
        return ()
    width = max(1, math.ceil(count / points))
    result: list[float] = []
    for start in range(0, count, width):
        values = samples[start : start + width]
        peak = max(abs(value) for value in values)
        result.append(min(1.0, peak / 32768.0))
    return tuple(result)


def _audio_chunk(stream, frames: int) -> array.array:
    """Read a miniaudio generator chunk, treating normal EOF as an empty chunk."""

    try:
        return stream.send(frames)
    except StopIteration:
        return array.array("h")


def inspect_audio(
    data: bytes | bytearray | memoryview,
    extension: str,
) -> AudioPreview:
    """Inspect WAV/FLAC/Vorbis/MP3 bytes and decode at most five seconds to a waveform."""

    raw = _bytes(data)
    ext = _extension(extension, {"wav", "flac", "ogg", "vorbis", "mp3"})
    if not raw:
        raise AssetInspectionError("audio is empty")
    if not _audio_signature_matches(raw, ext):
        raise AssetInspectionError(f"{ext.upper()} extension does not match its stream signature")
    miniaudio = _optional_import("miniaudio", "Audio")
    try:
        label, source = _audio_info(miniaudio, raw, ext)
    except AssetInspectionError:
        raise
    except Exception as exc:
        raise AssetInspectionError(f"malformed {ext.upper()} audio metadata") from exc
    samples = array.array("h")
    truncated = False
    try:
        stream = miniaudio.stream_memory(
            raw,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=MAX_AUDIO_PREVIEW_RATE,
            frames_to_read=4_096,
        )
        try:
            # The first `send` requests a small chunk; one extra frame determines
            # truncation without decoding an unbounded stream.
            while len(samples) <= MAX_AUDIO_PREVIEW_FRAMES:
                remaining = MAX_AUDIO_PREVIEW_FRAMES + 1 - len(samples)
                chunk = _audio_chunk(stream, min(4_096, remaining))
                if not chunk:
                    break
                if not isinstance(chunk, array.array):
                    raise AssetInspectionError("audio decoder returned an unexpected sample buffer")
                if chunk.typecode != "h":
                    raise AssetInspectionError("audio decoder returned an unexpected sample format")
                available = MAX_AUDIO_PREVIEW_FRAMES - len(samples)
                if len(chunk) > available:
                    if available > 0:
                        samples.extend(chunk[:available])
                    truncated = True
                    break
                samples.extend(chunk)
                if len(samples) == MAX_AUDIO_PREVIEW_FRAMES:
                    # Ask for one additional frame, then discard it if present.
                    extra = _audio_chunk(stream, 1)
                    truncated = bool(extra)
                    break
        finally:
            stream.close()
    except AssetInspectionError:
        raise
    except Exception as exc:
        raise AssetInspectionError(f"malformed or unsupported {label} audio stream") from exc
    decoded_frames = len(samples)
    if decoded_frames == 0:
        raise AssetInspectionError("audio stream contains no decodable sample frames")
    return AudioPreview(
        format=label,
        channels=source.channels,
        sample_rate=source.sample_rate,
        duration_seconds=source.duration,
        waveform=_waveform(samples),
        preview_sample_rate=MAX_AUDIO_PREVIEW_RATE,
        preview_frames=decoded_frames,
        preview_duration_seconds=decoded_frames / MAX_AUDIO_PREVIEW_RATE,
        truncated=truncated,
    )


def _obj_preflight(data: bytes) -> None:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AssetInspectionError("OBJ must be UTF-8 text") from exc
    if "\x00" in text:
        raise AssetInspectionError("OBJ contains a NUL byte")
    vertices = 0
    triangles = 0
    for line in _iter_text_lines(text):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if fields[0] == "v":
            if len(fields) < 4:
                raise AssetInspectionError("OBJ vertex is missing coordinates")
            try:
                coords = tuple(float(value) for value in fields[1:4])
            except ValueError as exc:
                raise AssetInspectionError("OBJ vertex coordinate is malformed") from exc
            if not all(math.isfinite(value) for value in coords):
                raise AssetInspectionError("OBJ vertex coordinate is not finite")
            vertices += 1
            if vertices > MAX_MESH_VERTICES:
                raise AssetInspectionError("OBJ vertex count exceeds the preview cap")
        elif fields[0] == "f":
            if len(fields) < 4:
                raise AssetInspectionError("OBJ face needs at least three vertices")
            face_size = len(fields) - 1
            triangles += face_size - 2
            if triangles > MAX_MESH_FACES:
                raise AssetInspectionError("OBJ face count exceeds the preview cap")
            for token in fields[1:]:
                head = token.split("/", 1)[0]
                try:
                    index = int(head)
                except ValueError as exc:
                    raise AssetInspectionError("OBJ face index is malformed") from exc
                if index == 0 or (index > 0 and index > MAX_MESH_VERTICES) or index < -vertices:
                    raise AssetInspectionError("OBJ face index is outside the supported range")


def _stl_preflight(data: bytes) -> None:
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        expected = 84 + count * 50
        if expected == len(data):
            if count > MAX_MESH_FACES or count * 3 > MAX_MESH_VERTICES:
                raise AssetInspectionError("STL geometry exceeds the preview cap")
            for offset in range(84, len(data), 50):
                values = struct.unpack_from("<12f", data, offset)
                if not all(math.isfinite(value) for value in values):
                    raise AssetInspectionError("STL contains non-finite coordinates")
            return
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise AssetInspectionError("STL is neither a valid binary nor ASCII model") from exc
    triangles = 0
    vertices = 0
    first_token = None
    saw_endsolid = False
    for line in _iter_text_lines(text):
        words = line.split()
        if not words:
            continue
        token = words[0].lower()
        if first_token is None:
            first_token = token
        if token == "endsolid":
            saw_endsolid = True
        if token == "facet":
            triangles += 1
        elif token == "vertex":
            if len(words) != 4:
                raise AssetInspectionError("ASCII STL vertex is malformed")
            try:
                coordinates = tuple(float(value) for value in words[1:])
            except ValueError as exc:
                raise AssetInspectionError("ASCII STL coordinate is malformed") from exc
            if not all(math.isfinite(value) for value in coordinates):
                raise AssetInspectionError("ASCII STL coordinate is not finite")
            vertices += 1
    if first_token != "solid" or not saw_endsolid:
        raise AssetInspectionError("STL text framing is malformed")
    if triangles > MAX_MESH_FACES or vertices > MAX_MESH_VERTICES:
        raise AssetInspectionError("STL geometry exceeds the preview cap")
    if triangles == 0 or vertices != triangles * 3:
        raise AssetInspectionError("ASCII STL has an invalid triangle/vertex count")


def _stl_geometry_only(data: bytes) -> bytes:
    """Pass binary STL through; normalize ASCII STL to bounded vertex records."""

    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        if 84 + count * 50 == len(data):
            return data
    text = data.decode("ascii")
    filtered = io.BytesIO()
    filtered.write(b"solid\n")
    for line in _iter_text_lines(text):
        words = line.split()
        if words and words[0].lower() == "vertex":
            filtered.write(("vertex " + " ".join(words[1:]) + "\n").encode("ascii"))
    filtered.write(b"endsolid\n")
    return filtered.getvalue()


_PLY_SCALAR_SIZES = {
    "char": 1, "int8": 1, "uchar": 1, "uint8": 1,
    "short": 2, "int16": 2, "ushort": 2, "uint16": 2,
    "int": 4, "int32": 4, "uint": 4, "uint32": 4,
    "float": 4, "float32": 4, "double": 8, "float64": 8,
}
_PLY_INT_TYPES = {
    "char": "b", "int8": "b", "uchar": "B", "uint8": "B",
    "short": "h", "int16": "h", "ushort": "H", "uint16": "H",
    "int": "i", "int32": "i", "uint": "I", "uint32": "I",
}


def _ply_header(data: bytes) -> tuple[str, list[tuple[str, int, list[tuple[str, ...]]]], int]:
    marker = data.find(b"end_header")
    if marker < 0 or marker > MAX_PLY_HEADER_BYTES:
        raise AssetInspectionError("PLY header is missing or exceeds the header cap")
    line_end = data.find(b"\n", marker)
    if line_end < 0:
        raise AssetInspectionError("PLY end_header line is truncated")
    header_bytes = data[: line_end + 1]
    try:
        lines = header_bytes.decode("ascii").replace("\r", "").splitlines()
    except UnicodeDecodeError as exc:
        raise AssetInspectionError("PLY header must be ASCII") from exc
    if not lines or lines[0] != "ply":
        raise AssetInspectionError("PLY signature is missing")
    ply_format: str | None = None
    elements: list[tuple[str, int, list[tuple[str, ...]]]] = []
    current_name: str | None = None
    current_count = 0
    current_properties: list[tuple[str, ...]] = []
    for line in lines[1:]:
        fields = line.strip().split()
        if not fields or fields[0] in {"comment", "obj_info"}:
            continue
        if fields[0] == "format":
            if len(fields) != 3 or fields[2] != "1.0":
                raise AssetInspectionError("unsupported PLY format declaration")
            ply_format = fields[1]
        elif fields[0] == "element":
            if current_name is not None:
                elements.append((current_name, current_count, current_properties))
            if len(fields) != 3:
                raise AssetInspectionError("PLY element declaration is malformed")
            current_name = fields[1]
            try:
                current_count = int(fields[2])
            except ValueError as exc:
                raise AssetInspectionError("PLY element count is malformed") from exc
            if current_count < 0:
                raise AssetInspectionError("PLY element count is negative")
            current_properties = []
        elif fields[0] == "property":
            if current_name is None:
                raise AssetInspectionError("PLY property appears before an element")
            if len(fields) == 3 and fields[1] in _PLY_SCALAR_SIZES:
                current_properties.append(("scalar", fields[1], fields[2]))
            elif len(fields) == 5 and fields[1] == "list":
                if fields[2] not in _PLY_SCALAR_SIZES or fields[3] not in _PLY_SCALAR_SIZES:
                    raise AssetInspectionError("PLY list uses an unsupported scalar type")
                current_properties.append(("list", fields[2], fields[3], fields[4]))
            else:
                raise AssetInspectionError("PLY property declaration is malformed")
        elif fields[0] not in {"end_header"}:
            raise AssetInspectionError(f"unsupported PLY header directive: {fields[0]}")
    if current_name is not None:
        elements.append((current_name, current_count, current_properties))
    if ply_format not in {"ascii", "binary_little_endian", "binary_big_endian"}:
        raise AssetInspectionError("unsupported PLY encoding")
    if [item[0] for item in elements] != ["vertex", "face"]:
        raise AssetInspectionError("only mesh-only PLY files with vertex and face elements are supported")
    vertices, faces = elements
    if not (1 <= vertices[1] <= MAX_MESH_VERTICES and 1 <= faces[1] <= MAX_MESH_FACES):
        raise AssetInspectionError("PLY vertex or face count exceeds the preview cap")
    vertex_props = vertices[2]
    if any(prop[0] != "scalar" for prop in vertex_props):
        raise AssetInspectionError("PLY vertex lists are not supported")
    if not {prop[2] for prop in vertex_props} >= {"x", "y", "z"}:
        raise AssetInspectionError("PLY vertices need x, y and z properties")
    face_lists = [prop for prop in faces[2] if prop[0] == "list"]
    if len(face_lists) != 1 or face_lists[0][3] not in {"vertex_indices", "vertex_index"}:
        raise AssetInspectionError("PLY faces need one vertex_indices list")
    if any(prop[0] != "list" for prop in faces[2] if prop != face_lists[0]):
        raise AssetInspectionError("PLY face scalar properties are not supported")
    return ply_format, elements, line_end + 1


def _ply_preflight(data: bytes) -> None:
    ply_format, elements, offset = _ply_header(data)
    vertex_element, face_element = elements
    vertex_count, face_count = vertex_element[1], face_element[1]
    vertex_props, face_props = vertex_element[2], face_element[2]
    list_prop = next(prop for prop in face_props if prop[0] == "list")
    count_type, item_type = list_prop[1], list_prop[2]
    triangles = 0
    if ply_format == "ascii":
        try:
            text = data[offset:].decode("ascii")
        except UnicodeDecodeError as exc:
            raise AssetInspectionError("ASCII PLY body contains non-ASCII data") from exc
        rows = iter(_iter_text_lines(text))
        for _ in range(vertex_count):
            row = next(rows, None)
            if row is None or not row.split():
                raise AssetInspectionError("PLY vertex table is truncated")
            values = row.split()
            if len(values) != len(vertex_props):
                raise AssetInspectionError("PLY vertex row has the wrong property count")
            for value, prop in zip(values, vertex_props):
                try:
                    number = float(value)
                except ValueError as exc:
                    raise AssetInspectionError("PLY vertex value is malformed") from exc
                if prop[2] in {"x", "y", "z"} and not math.isfinite(number):
                    raise AssetInspectionError("PLY coordinates must be finite")
        for _ in range(face_count):
            row = next(rows, None)
            if row is None:
                raise AssetInspectionError("PLY face table is truncated")
            values = row.split()
            if not values:
                raise AssetInspectionError("PLY face row is empty")
            try:
                n = int(values[0])
                indices = [int(value) for value in values[1:]]
            except ValueError as exc:
                raise AssetInspectionError("PLY face index is malformed") from exc
            if n < 3 or n != len(indices) or n > vertex_count:
                raise AssetInspectionError("PLY face list length is invalid")
            if any(index < 0 or index >= vertex_count for index in indices):
                raise AssetInspectionError("PLY face index is outside the vertex table")
            triangles += n - 2
            if triangles > MAX_MESH_FACES:
                raise AssetInspectionError("PLY triangulated face count exceeds the preview cap")
        return
    endian = "<" if ply_format == "binary_little_endian" else ">"
    vertex_stride = sum(_PLY_SCALAR_SIZES[prop[1]] for prop in vertex_props)
    vertex_end = offset + vertex_count * vertex_stride
    if vertex_end > len(data):
        raise AssetInspectionError("binary PLY vertex table is truncated")
    offset = vertex_end
    count_code = _PLY_INT_TYPES.get(count_type)
    item_code = _PLY_INT_TYPES.get(item_type)
    if count_code is None or item_code is None:
        raise AssetInspectionError("PLY face list indices must use integer types")
    count_size = struct.calcsize(count_code)
    item_size = struct.calcsize(item_code)
    for _ in range(face_count):
        if offset + count_size > len(data):
            raise AssetInspectionError("binary PLY face table is truncated")
        n = struct.unpack_from(endian + count_code, data, offset)[0]
        offset += count_size
        if n < 3 or n > vertex_count or offset + n * item_size > len(data):
            raise AssetInspectionError("binary PLY face list length is invalid")
        indices = struct.unpack_from(endian + str(n) + item_code, data, offset)
        if any(index < 0 or index >= vertex_count for index in indices):
            raise AssetInspectionError("binary PLY face index is outside the vertex table")
        offset += n * item_size
        triangles += n - 2
        if triangles > MAX_MESH_FACES:
            raise AssetInspectionError("PLY triangulated face count exceeds the preview cap")
    if offset > len(data):
        raise AssetInspectionError("binary PLY body is truncated")


def _ply_ascii_geometry_only(data: bytes) -> bytes:
    """Trim ASCII PLY to its declared, preflighted vertex and face rows."""

    ply_format, elements, offset = _ply_header(data)
    if ply_format != "ascii":
        return data
    try:
        text = data[offset:].decode("ascii")
    except UnicodeDecodeError as exc:
        raise AssetInspectionError("ASCII PLY body contains non-ASCII data") from exc
    rows = iter(_iter_text_lines(text))
    row_count = sum(element[1] for element in elements)
    filtered = io.BytesIO()
    filtered.write(data[:offset])
    for _ in range(row_count):
        row = next(rows, None)
        if row is None:
            raise AssetInspectionError("ASCII PLY row table is truncated")
        filtered.write(row.encode("ascii"))
        filtered.write(b"\n")
    return filtered.getvalue()


def _glb_json(data: bytes) -> tuple[dict, bytes]:
    if len(data) < 20 or data[:4] != b"glTF":
        raise AssetInspectionError("GLB extension does not match glTF binary data")
    version, total = struct.unpack_from("<II", data, 4)
    if version != 2 or total != len(data):
        raise AssetInspectionError("unsupported or malformed GLB header")
    cursor = 12
    json_data: bytes | None = None
    binary_data = b""
    chunks = 0
    while cursor < len(data):
        if cursor + 8 > len(data):
            raise AssetInspectionError("GLB chunk header is truncated")
        length, kind = struct.unpack_from("<II", data, cursor)
        cursor += 8
        end = cursor + length
        if length % 4 or end > len(data):
            raise AssetInspectionError("GLB chunk length is invalid")
        chunk = data[cursor:end]
        if chunks == 0 and kind != 0x4E4F534A:
            raise AssetInspectionError("GLB JSON chunk must be first")
        if kind == 0x4E4F534A:
            if json_data is not None or length > MAX_GLTF_JSON_BYTES:
                raise AssetInspectionError("GLB JSON chunk is duplicated or too large")
            json_data = chunk.rstrip(b" \t\r\n\x00")
        elif kind == 0x004E4942:
            if binary_data:
                raise AssetInspectionError("GLB has more than one binary chunk")
            binary_data = chunk
        cursor = end
        chunks += 1
    if json_data is None:
        raise AssetInspectionError("GLB is missing its JSON chunk")
    try:
        document = json.loads(json_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssetInspectionError("GLB JSON is malformed") from exc
    asset = document.get("asset") if isinstance(document, dict) else None
    if not isinstance(asset, dict) or asset.get("version") != "2.0":
        raise AssetInspectionError("GLB is not a glTF 2.0 document")
    if not isinstance(document.get("nodes", []), list) or len(document.get("nodes", [])) > MAX_GLTF_NODES:
        raise AssetInspectionError("GLB node count exceeds the preview cap")
    for section in ("buffers", "images"):
        entries = document.get(section, [])
        if not isinstance(entries, list):
            raise AssetInspectionError(f"GLB {section} table is malformed")
        for entry in entries:
            if not isinstance(entry, dict):
                raise AssetInspectionError(f"GLB {section} entry is malformed")
            uri = entry.get("uri")
            if uri is not None and (not isinstance(uri, str) or not uri.startswith("data:")):
                raise AssetInspectionError("GLB external URIs are not followed")
    for field in ("extensionsUsed", "extensionsRequired"):
        extensions = document.get(field, [])
        if not isinstance(extensions, list) or any(not isinstance(ext, str) for ext in extensions):
            raise AssetInspectionError(f"GLB {field} list is malformed")
        if _UNSUPPORTED_GLTF_EXTENSIONS.intersection(extensions):
            raise AssetInspectionError("compressed glTF geometry extensions are not supported")
    _glb_geometry_preflight(document, binary_data)
    return document, binary_data


def _glb_geometry_preflight(document: dict, binary_data: bytes) -> None:
    buffers = document.get("buffers", [])
    if not isinstance(buffers, list) or len(buffers) > 1:
        raise AssetInspectionError("GLB must use at most one embedded buffer")
    if buffers:
        buffer = buffers[0]
        if not isinstance(buffer, dict) or buffer.get("uri") is not None:
            raise AssetInspectionError("GLB buffer must be embedded in the binary chunk")
        byte_length = buffer.get("byteLength")
        if not isinstance(byte_length, int) or byte_length < 0 or byte_length > len(binary_data):
            raise AssetInspectionError("GLB buffer length is outside the binary chunk")
    views = document.get("bufferViews", [])
    accessors = document.get("accessors", [])
    meshes = document.get("meshes", [])
    nodes = document.get("nodes", [])
    if not all(isinstance(value, list) for value in (views, accessors, meshes, nodes)):
        raise AssetInspectionError("GLB geometry tables are malformed")
    if len(views) > MAX_GLTF_NODES * 8 or len(accessors) > MAX_GLTF_NODES * 8 or len(meshes) > MAX_GLTF_NODES:
        raise AssetInspectionError("GLB geometry table exceeds the preview cap")
    component_sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    type_sizes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
    materialized_bytes = 0
    for view in views:
        if not isinstance(view, dict) or view.get("buffer", 0) != 0:
            raise AssetInspectionError("GLB buffer view references a missing buffer")
        view_extensions = view.get("extensions", {})
        if not isinstance(view_extensions, dict):
            raise AssetInspectionError("GLB buffer-view extensions are malformed")
        if _UNSUPPORTED_GLTF_EXTENSIONS.intersection(view_extensions):
            raise AssetInspectionError("compressed glTF geometry extensions are not supported")
        offset = view.get("byteOffset", 0)
        length = view.get("byteLength")
        if not isinstance(offset, int) or not isinstance(length, int) or offset < 0 or length < 0:
            raise AssetInspectionError("GLB buffer view range is malformed")
        if offset + length > len(binary_data):
            raise AssetInspectionError("GLB buffer view extends past the binary chunk")
        materialized_bytes += length
        if materialized_bytes > MAX_GLTF_MATERIALIZED_BYTES:
            raise AssetInspectionError("GLB buffer views exceed the decoded-memory cap")
    for accessor in accessors:
        if not isinstance(accessor, dict) or "sparse" in accessor:
            raise AssetInspectionError("sparse or malformed GLB accessors are not supported")
        view_index = accessor.get("bufferView")
        count = accessor.get("count")
        component_type = accessor.get("componentType")
        kind = accessor.get("type")
        if not isinstance(view_index, int) or view_index < 0 or view_index >= len(views):
            raise AssetInspectionError("GLB accessor has no valid buffer view")
        if not isinstance(count, int) or count < 1 or count > max(MAX_MESH_VERTICES, MAX_MESH_FACES * 3):
            raise AssetInspectionError("GLB accessor count exceeds the preview cap")
        if component_type not in component_sizes or kind not in type_sizes:
            raise AssetInspectionError("GLB accessor element type is unsupported")
        accessor_offset = accessor.get("byteOffset", 0)
        if not isinstance(accessor_offset, int) or accessor_offset < 0:
            raise AssetInspectionError("GLB accessor offset is malformed")
        element_size = component_sizes[component_type] * type_sizes[kind]
        materialized_bytes += count * element_size
        if materialized_bytes > MAX_GLTF_MATERIALIZED_BYTES:
            raise AssetInspectionError("GLB accessors exceed the decoded-memory cap")
        stride = views[view_index].get("byteStride", element_size)
        view_length = views[view_index]["byteLength"]
        if not isinstance(stride, int) or stride < element_size:
            raise AssetInspectionError("GLB accessor stride is invalid")
        if "byteStride" in views[view_index] and (stride < 4 or stride > 252 or stride % 4):
            raise AssetInspectionError("GLB byteStride is outside the glTF range")
        needed = accessor_offset + (count - 1) * stride + element_size
        if needed > view_length:
            raise AssetInspectionError("GLB accessor extends past its buffer view")
    per_mesh: list[tuple[int, int]] = []
    all_mesh_vertices = 0
    all_mesh_faces = 0
    for mesh in meshes:
        if not isinstance(mesh, dict) or not isinstance(mesh.get("primitives", []), list):
            raise AssetInspectionError("GLB mesh entry is malformed")
        vertex_total = 0
        face_total = 0
        for primitive in mesh.get("primitives", []):
            if not isinstance(primitive, dict) or primitive.get("mode", 4) != 4:
                raise AssetInspectionError("only triangle GLB primitives are supported")
            primitive_extensions = primitive.get("extensions", {})
            if not isinstance(primitive_extensions, dict):
                raise AssetInspectionError("GLB primitive extensions are malformed")
            if _UNSUPPORTED_GLTF_EXTENSIONS.intersection(primitive_extensions):
                raise AssetInspectionError("compressed glTF geometry extensions are not supported")
            attributes = primitive.get("attributes")
            if not isinstance(attributes, dict) or not isinstance(attributes.get("POSITION"), int):
                raise AssetInspectionError("GLB triangle primitive is missing POSITION")
            position_index = attributes["POSITION"]
            if position_index < 0 or position_index >= len(accessors):
                raise AssetInspectionError("GLB POSITION accessor index is invalid")
            position = accessors[position_index]
            if position.get("type") != "VEC3" or position.get("componentType") != 5126:
                raise AssetInspectionError("GLB POSITION accessor must contain float VEC3 values")
            primitive_vertices = position["count"]
            indices_index = primitive.get("indices")
            if indices_index is None:
                index_count = primitive_vertices
            elif isinstance(indices_index, int) and 0 <= indices_index < len(accessors):
                indices_accessor = accessors[indices_index]
                if indices_accessor.get("type") != "SCALAR" or indices_accessor.get("componentType") not in {5121, 5123, 5125}:
                    raise AssetInspectionError("GLB triangle indices must use unsigned scalar values")
                index_count = indices_accessor["count"]
            else:
                raise AssetInspectionError("GLB indices accessor index is invalid")
            if index_count % 3:
                raise AssetInspectionError("GLB triangle index count is not divisible by three")
            vertex_total += primitive_vertices
            face_total += index_count // 3
            if vertex_total > MAX_MESH_VERTICES or face_total > MAX_MESH_FACES:
                raise AssetInspectionError("GLB mesh geometry exceeds the preview cap")
        all_mesh_vertices += vertex_total
        all_mesh_faces += face_total
        if all_mesh_vertices > MAX_MESH_VERTICES or all_mesh_faces > MAX_MESH_FACES:
            raise AssetInspectionError("GLB total mesh geometry exceeds the preview cap")
        per_mesh.append((vertex_total, face_total))
    vertices = 0
    faces = 0
    for node in nodes:
        if not isinstance(node, dict):
            raise AssetInspectionError("GLB node entry is malformed")
        mesh_index = node.get("mesh")
        if mesh_index is None:
            continue
        if not isinstance(mesh_index, int) or mesh_index < 0 or mesh_index >= len(per_mesh):
            raise AssetInspectionError("GLB node references a missing mesh")
        vertices += per_mesh[mesh_index][0]
        faces += per_mesh[mesh_index][1]
    if vertices > MAX_MESH_VERTICES or faces > MAX_MESH_FACES:
        raise AssetInspectionError("GLB instantiated geometry exceeds the preview cap")


def _mesh_preflight(data: bytes, extension: str) -> None:
    if extension == "obj":
        _obj_preflight(data)
    elif extension == "stl":
        _stl_preflight(data)
    elif extension == "ply":
        _ply_preflight(data)
    else:
        _glb_json(data)


def inspect_model(
    data: bytes | bytearray | memoryview,
    extension: str,
) -> MeshPreview:
    """Load a bounded OBJ/STL/PLY/GLB mesh from memory for a wireframe preview."""

    raw = _bytes(data)
    ext = _extension(extension, {"obj", "stl", "ply", "glb"})
    if not raw:
        raise AssetInspectionError("model is empty")
    try:
        _mesh_preflight(raw, ext)
    except AssetInspectionError:
        raise
    except Exception as exc:
        raise AssetInspectionError(f"malformed {ext.upper()} model structure") from exc
    trimesh = _optional_import("trimesh", "3D model")
    # OBJ materials and vertex attributes are outside this geometry preview.
    # Rebuild only position and face records, so sidecars and unused attributes
    # never reach the external parser.
    file_bytes = raw
    if ext == "obj":
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AssetInspectionError("OBJ must be UTF-8 text") from exc
        filtered = io.BytesIO()
        for line in _iter_text_lines(text):
            fields = line.strip().split()
            if fields and fields[0] == "v":
                filtered.write(("v " + " ".join(fields[1:4]) + "\n").encode("utf-8"))
            elif fields and fields[0] == "f":
                indices = (token.split("/", 1)[0] for token in fields[1:])
                filtered.write(("f " + " ".join(indices) + "\n").encode("utf-8"))
        file_bytes = filtered.getvalue()
    elif ext == "stl":
        file_bytes = _stl_geometry_only(raw)
    elif ext == "ply":
        file_bytes = _ply_ascii_geometry_only(raw)
    try:
        options = {"resolver": {}, "allow_remote": False, "process": False}
        if ext == "glb":
            options["skip_materials"] = True
        scene = trimesh.load_scene(
            io.BytesIO(file_bytes),
            file_type=ext,
            **options,
        )
        geometries = tuple(scene.geometry.values())
        if not geometries or any(not isinstance(geometry, trimesh.Trimesh) for geometry in geometries):
            raise AssetInspectionError("model does not contain triangle mesh geometry")
        mesh = scene.to_geometry()
        vertices_array = mesh.vertices
        faces_array = mesh.faces
        if vertices_array.ndim != 2 or vertices_array.shape[1] != 3:
            raise AssetInspectionError("model vertex array has an unsupported shape")
        if faces_array.ndim != 2 or faces_array.shape[1] != 3:
            raise AssetInspectionError("model contains non-triangle faces")
        vertex_count, face_count = len(vertices_array), len(faces_array)
        if not (1 <= vertex_count <= MAX_MESH_VERTICES):
            raise AssetInspectionError("model vertex count exceeds the preview cap")
        if not (1 <= face_count <= MAX_MESH_FACES):
            raise AssetInspectionError("model face count exceeds the preview cap")
        if not all(math.isfinite(float(value)) for vertex in vertices_array for value in vertex):
            raise AssetInspectionError("model contains non-finite vertices")
        if faces_array.size and (int(faces_array.min()) < 0 or int(faces_array.max()) >= vertex_count):
            raise AssetInspectionError("model face index is outside the vertex array")
        bounds_array = mesh.bounds
        if bounds_array.shape != (2, 3) or not all(
            math.isfinite(float(value)) for row in bounds_array for value in row
        ):
            raise AssetInspectionError("model bounds are malformed")
        vertices = tuple(tuple(float(value) for value in vertex) for vertex in vertices_array)
        faces = tuple(tuple(int(value) for value in face) for face in faces_array)
        bounds = (
            tuple(float(value) for value in bounds_array[0]),
            tuple(float(value) for value in bounds_array[1]),
        )
        return MeshPreview(ext.upper(), vertices, faces, vertex_count, face_count, bounds)
    except AssetInspectionError:
        raise
    except Exception as exc:
        raise AssetInspectionError(f"malformed or unsupported {ext.upper()} model") from exc


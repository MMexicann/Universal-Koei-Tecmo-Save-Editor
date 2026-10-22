from __future__ import annotations

import array
import importlib
import importlib.util
import io
import json
import struct
import unittest
import wave
import zlib
from types import SimpleNamespace
from unittest import mock

from koei_editor.research.asset_explorer import media


def _png_chunk(kind: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    )


def png_bytes(
    width: int,
    height: int,
    color_type: int,
    scanlines: bytes,
    palette: bytes | None = None,
    transparency: bytes | None = None,
) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    result = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header)
    if palette is not None:
        result += _png_chunk(b"PLTE", palette)
    if transparency is not None:
        result += _png_chunk(b"tRNS", transparency)
    result += _png_chunk(b"IDAT", zlib.compress(scanlines))
    return result + _png_chunk(b"IEND", b"")


def png_fixture(width: int = 2, height: int = 1) -> bytes:
    # Construct a tiny true-color PNG without an image decoder dependency.
    pixels = bytes((255, 0, 0, 255, 0, 255, 0, 128))
    scanlines = b"\x00" + pixels[: width * 4]
    return png_bytes(width, height, 6, scanlines * height)


def filtered_png_fixture() -> tuple[bytes, bytes]:
    rows = (
        bytes((10, 20, 30, 40, 50, 60)),
        bytes((11, 21, 31, 41, 51, 61)),
        bytes((12, 22, 32, 42, 52, 62)),
        bytes((13, 23, 33, 43, 53, 63)),
        bytes((14, 24, 34, 44, 54, 64)),
    )
    encoded = bytearray()
    previous = bytes(len(rows[0]))
    for filter_type, row in enumerate(rows):
        bpp = 3
        filtered = bytearray()
        for index, value in enumerate(row):
            left = row[index - bpp] if index >= bpp else 0
            above = previous[index]
            upper_left = previous[index - bpp] if index >= bpp else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            else:
                estimate = left + above - upper_left
                distances = (
                    (abs(estimate - left), left),
                    (abs(estimate - above), above),
                    (abs(estimate - upper_left), upper_left),
                )
                predictor = min(distances, key=lambda item: item[0])[1]
            filtered.append((value - predictor) & 0xFF)
        encoded.append(filter_type)
        encoded.extend(filtered)
        previous = row
    expected = b"".join(
        bytes((row[0], row[1], row[2], 255, row[3], row[4], row[5], 255))
        for row in rows
    )
    return png_bytes(2, len(rows), 2, bytes(encoded)), expected


def palette_png_fixture() -> bytes:
    return png_bytes(
        3,
        1,
        3,
        b"\x00\x00\x01\x02",
        palette=bytes((255, 0, 0, 0, 255, 0, 0, 0, 255)),
        transparency=bytes((255, 128)),
    )


def dds_dxt_fixture(fourcc: bytes = b"DXT1", width: int = 4, height: int = 4) -> bytes:
    block_size = 8 if fourcc == b"DXT1" else 16
    blocks = ((width + 3) // 4) * ((height + 3) // 4)
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    header = bytearray(b"DDS ")
    header += struct.pack("<7I", 124, flags, height, width, blocks * block_size, 0, 0)
    header += bytes(44)
    header += struct.pack("<II4s5I", 32, 0x4, fourcc, 0, 0, 0, 0, 0)
    header += struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    if fourcc == b"DXT1":
        # Solid red RGB565 with all sixteen selectors set to color zero.
        body = struct.pack("<HHI", 0xF800, 0x07E0, 0)
    else:
        # Opaque alpha and solid red RGB565.
        body = bytes((255, 0)) + bytes(6) + struct.pack("<HHI", 0xF800, 0x07E0, 0)
    return bytes(header) + body * blocks


def wav_fixture(frames: int = 8, rate: int = 22_050, channels: int = 1) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        values = array.array("h", [1_000, -1_000] * ((frames * channels + 1) // 2))
        writer.writeframes(values[: frames * channels].tobytes())
    return output.getvalue()


def flac_fixture(rate: int = 44_100, channels: int = 2, frames: int = 44_100) -> bytes:
    packed = (rate << 44) | ((channels - 1) << 41) | (15 << 36) | frames
    streaminfo = bytearray(34)
    streaminfo[10:18] = packed.to_bytes(8, "big")
    return b"fLaC" + b"\x80\x00\x00\x22" + bytes(streaminfo) + b"synthetic"


def vorbis_fixture(rate: int = 48_000, channels: int = 2, frames: int = 48_000) -> bytes:
    packet = bytearray(30)
    packet[:7] = b"\x01vorbis"
    struct.pack_into("<I", packet, 7, 0)
    packet[11] = channels
    struct.pack_into("<I", packet, 12, rate)
    packet[29] = 1
    # One final Ogg page, with the identification packet and no CRC dependency.
    header = bytearray(b"OggS")
    header += bytes((0, 0x06))
    header += struct.pack("<QIII", frames, 0x12345678, 0, 0)
    header += bytes((1,))
    return bytes(header) + bytes((len(packet),)) + packet


def mp3_fixture(rate_code: int = 0, bitrate_index: int = 9, frames: int = 3) -> bytes:
    header = (
        (0x7FF << 21)
        | (0b11 << 19)  # MPEG-1
        | (0b01 << 17)  # Layer III
        | (1 << 16)     # no CRC
        | (bitrate_index << 12)
        | (rate_code << 10)
    )
    header_bytes = header.to_bytes(4, "big")
    frame_size = (144 * 128_000 // 44_100)
    return (header_bytes + bytes(frame_size - 4)) * frames


def obj_fixture() -> bytes:
    return b"""mtllib /path/that/must/not/be/read.mtl
v 0 0 0
v 1 0 0
v 0 1 0
f 1 2 3
"""


def stl_binary_fixture() -> bytes:
    header = b"synthetic triangle".ljust(80, b"\0") + struct.pack("<I", 1)
    triangle = struct.pack(
        "<12fH",
        0.0, 0.0, 1.0,
        0.0, 0.0, 0.0,
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0,
    )
    return header + triangle


def stl_ascii_fixture() -> bytes:
    return b"""solid synthetic
facet normal 0 0 1
outer loop
vertex 0 0 0
vertex 1 0 0
vertex 0 1 0
endloop
endfacet
endsolid synthetic
"""


def ply_ascii_fixture() -> bytes:
    return b"""ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
element face 1
property list uchar int vertex_indices
end_header
0 0 0
1 0 0
0 1 0
3 0 1 2
"""


def ply_binary_fixture() -> bytes:
    header = b"""ply
format binary_little_endian 1.0
element vertex 3
property float x
property float y
property float z
element face 1
property list uchar uint vertex_indices
end_header
"""
    vertices = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    face = b"\x03" + struct.pack("<3I", 0, 1, 2)
    return header + vertices + face


def glb_fixture(
    external_image: bool = False,
    repeated_accessors: int = 0,
    repeated_meshes: int = 0,
    compression_extension: str | None = None,
    declare_extension: bool = True,
) -> bytes:
    binary = struct.pack("<9f3H", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 2)
    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36},
            {"buffer": 0, "byteOffset": 36, "byteLength": 6},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    for _ in range(repeated_accessors):
        gltf["accessors"].append(
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}
        )
    gltf["meshes"].extend(
        {"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}
        for _ in range(repeated_meshes)
    )
    if external_image:
        gltf["images"] = [{"uri": "../must-not-be-read.png"}]
    if compression_extension is not None:
        if declare_extension:
            gltf["extensionsUsed"] = [compression_extension]
        if compression_extension == "KHR_draco_mesh_compression":
            gltf["meshes"][0]["primitives"][0]["extensions"] = {compression_extension: {}}
        else:
            gltf["bufferViews"][0]["extensions"] = {compression_extension: {}}
    json_data = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_data += b" " * ((-len(json_data)) % 4)
    binary += b"\0" * ((-len(binary)) % 4)
    json_chunk = struct.pack("<II", len(json_data), 0x4E4F534A) + json_data
    bin_chunk = struct.pack("<II", len(binary), 0x004E4942) + binary
    total = 12 + len(json_chunk) + len(bin_chunk)
    return b"glTF" + struct.pack("<II", 2, total) + json_chunk + bin_chunk


class _FakeStream:
    def __init__(self, frames: int):
        self.remaining = frames
        self.closed = False

    def send(self, requested: int) -> array.array:
        count = min(requested, self.remaining)
        self.remaining -= count
        return array.array("h", [2_000] * count)

    def close(self) -> None:
        self.closed = True


class _FakeMiniaudio:
    class SampleFormat:
        SIGNED16 = "s16"

    def __init__(
        self,
        frames: int,
        source_channels: int = 1,
        source_rate: int = 22_050,
        source_frames: int | None = None,
    ):
        self.frames = frames
        self.stream = _FakeStream(frames)
        self.info = SimpleNamespace(
            nchannels=source_channels,
            sample_rate=source_rate,
            num_frames=source_frames if source_frames is not None else frames,
        )

    def stream_memory(self, *_args, **_kwargs):
        return self.stream

    def wav_get_info(self, _data):
        return self.info

    def flac_get_info(self, _data):
        return self.info

    def vorbis_get_info(self, _data):
        return self.info

    def mp3_get_info(self, _data):
        return self.info


class ImageInspectionTests(unittest.TestCase):
    def test_png_rgba_preview_is_bounded_and_pathless(self):
        preview = media.inspect_image(png_fixture(), ".PNG")
        self.assertEqual((preview.format, preview.width, preview.height, preview.mode), ("PNG", 2, 1, "RGBA"))
        self.assertEqual(preview.rgba_bytes, bytes((255, 0, 0, 255, 0, 255, 0, 128)))
        with self.assertRaises(TypeError):
            media.inspect_image("/tmp/image.png", "png")

    def test_png_filters_and_palette_alpha(self):
        filtered, expected = filtered_png_fixture()
        preview = media.inspect_image(filtered, "png")
        self.assertEqual(preview.rgba_bytes, expected)
        palette = media.inspect_image(palette_png_fixture(), "png")
        self.assertEqual(
            palette.rgba_bytes,
            bytes((255, 0, 0, 255, 0, 255, 0, 128, 0, 0, 255, 255)),
        )

    def test_png_rejects_bad_crc_and_interlace(self):
        raw = bytearray(png_fixture())
        raw[28] = 1  # IHDR interlace method.
        struct.pack_into(">I", raw, 29, zlib.crc32(raw[12:29]) & 0xFFFFFFFF)
        with self.assertRaises(media.AssetInspectionError):
            media.inspect_image(bytes(raw), "png")
        bad_crc = bytearray(png_fixture())
        bad_crc[29] ^= 0x01
        with self.assertRaises(media.AssetInspectionError):
            media.inspect_image(bytes(bad_crc), "png")

    def test_dds_and_g1t_dxt1_preview(self):
        dds = media.inspect_image(dds_dxt_fixture(), "dds")
        self.assertEqual((dds.format, dds.width, dds.height), ("DDS", 4, 4))
        texture = media.decode_g1t_texture(dds_dxt_fixture()[128:], 4, 4, "DXT1")
        self.assertEqual(texture.format, "G1T-DXT1")
        self.assertEqual(len(texture.rgba_bytes), 4 * 4 * 4)
        self.assertEqual(texture.rgba_bytes[:4], bytes((255, 0, 0, 255)))
        dxt5 = media.decode_g1t_texture(dds_dxt_fixture(b"DXT5")[128:], 4, 4, "DXT5")
        self.assertEqual(dxt5.format, "G1T-DXT5")
        self.assertEqual(dxt5.rgba_bytes[:4], bytes((255, 0, 0, 255)))

    def test_g1t_rgba_and_bgra_conversions(self):
        rgba = bytes((1, 2, 3, 4))
        self.assertEqual(media.decode_g1t_texture(rgba, 1, 1, "RGBA8").rgba_bytes, rgba)
        self.assertEqual(media.decode_g1t_texture(bytes((3, 2, 1, 4)), 1, 1, "BGRA8").rgba_bytes, rgba)
        transparent_dxt1 = media.decode_g1t_texture(
            struct.pack("<HHI", 0, 0, 0xFFFFFFFF), 1, 1, "DXT1"
        )
        self.assertEqual(transparent_dxt1.rgba_bytes, bytes((0, 0, 0, 0)))
        dxt5 = bytes((200, 0)) + (2).to_bytes(6, "little") + struct.pack(
            "<HHI", 0xF800, 0x07E0, 0
        )
        self.assertEqual(
            media.decode_g1t_texture(dxt5, 1, 1, "DXT5").rgba_bytes,
            bytes((255, 0, 0, 171)),
        )
        with self.assertRaises(media.AssetInspectionError):
            media.decode_g1t_texture(b"short", 1, 1, "RGBA8")

    def test_image_allowlist_rejects_mismatch_and_pixel_overflow(self):
        with self.assertRaises(media.AssetInspectionError):
            media.inspect_image(png_fixture(), "jpg")
        with self.assertRaises(media.AssetInspectionError):
            media.inspect_image(b"not png", "png")
        with mock.patch.object(media, "MAX_IMAGE_PIXELS", 1):
            with self.assertRaises(media.AssetInspectionError):
                media.inspect_image(png_fixture(), "png")


class AudioInspectionTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("miniaudio") is not None, "pyminiaudio is optional")
    def test_wav_decodes_only_bounded_waveform(self):
        short = media.inspect_audio(wav_fixture(frames=8), "wav")
        self.assertEqual(short.preview_frames, 8)
        self.assertFalse(short.truncated)

        raw = wav_fixture(frames=media.MAX_AUDIO_PREVIEW_FRAMES + 10)
        preview = media.inspect_audio(raw, ".wav")
        self.assertEqual(preview.format, "WAV")
        self.assertEqual((preview.channels, preview.sample_rate), (1, 22_050))
        self.assertEqual(preview.duration_seconds, (media.MAX_AUDIO_PREVIEW_FRAMES + 10) / 22_050)
        self.assertEqual(preview.preview_frames, media.MAX_AUDIO_PREVIEW_FRAMES)
        self.assertEqual(preview.preview_duration_seconds, 5.0)
        self.assertTrue(preview.truncated)
        self.assertLessEqual(len(preview.waveform), media.MAX_WAVEFORM_POINTS)
        self.assertTrue(all(0.0 <= point <= 1.0 for point in preview.waveform))

    def test_compressed_metadata_and_decoding_cap_use_bytes_only(self):
        fixtures = (
            ("flac", flac_fixture(rate=44_100, channels=2, frames=88_200), "FLAC", 2, 44_100, 88_200, 2.0),
            ("ogg", vorbis_fixture(rate=48_000, channels=2, frames=96_000), "Vorbis", 2, 48_000, 96_000, 2.0),
            ("mp3", mp3_fixture(frames=3), "MP3", 2, 44_100, 3 * 1_152, 3 * 1_152 / 44_100),
        )
        for extension, data, label, channels, rate, source_frames, duration in fixtures:
            with self.subTest(extension=extension):
                fake = _FakeMiniaudio(
                    media.MAX_AUDIO_PREVIEW_FRAMES + 5,
                    source_channels=channels,
                    source_rate=rate,
                    source_frames=source_frames,
                )
                with mock.patch.object(media, "_optional_import", return_value=fake):
                    preview = media.inspect_audio(data, extension)
                self.assertEqual((preview.format, preview.channels, preview.sample_rate), (label, channels, rate))
                self.assertAlmostEqual(preview.duration_seconds, duration)
                self.assertEqual(preview.preview_frames, media.MAX_AUDIO_PREVIEW_FRAMES)
                self.assertTrue(preview.truncated)
                self.assertTrue(fake.stream.closed)

    @unittest.skipUnless(importlib.util.find_spec("miniaudio") is not None, "pyminiaudio is optional")
    def test_exact_audio_cap_is_not_marked_truncated(self):
        preview = media.inspect_audio(
            wav_fixture(frames=media.MAX_AUDIO_PREVIEW_FRAMES), "wav"
        )
        self.assertEqual(preview.preview_frames, media.MAX_AUDIO_PREVIEW_FRAMES)
        self.assertFalse(preview.truncated)

    def test_audio_extension_mismatch_and_bad_header_reject_before_decoder(self):
        with mock.patch.object(media, "_optional_import", side_effect=AssertionError("decoder should not load")):
            with self.assertRaises(media.AssetInspectionError):
                media.inspect_audio(wav_fixture(), "mp3")
            with self.assertRaises(media.AssetInspectionError):
                media.inspect_audio(b"not audio", "flac")


class ModelInspectionTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("trimesh") is not None, "trimesh is optional")
    def test_obj_preview_strips_external_material_reference(self):
        preview = media.inspect_model(obj_fixture(), ".OBJ")
        self.assertEqual((preview.format, preview.vertex_count, preview.face_count), ("OBJ", 3, 1))
        self.assertEqual(preview.vertices[1], (1.0, 0.0, 0.0))
        self.assertEqual(preview.faces, ((0, 1, 2),))
        self.assertEqual(preview.bounds, ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0)))

    @unittest.skipUnless(importlib.util.find_spec("trimesh") is not None, "trimesh is optional")
    def test_stl_ply_and_glb_procedural_geometry(self):
        for extension, data in (
            ("stl", stl_binary_fixture()),
            ("stl", stl_ascii_fixture() + b"\n" * 1_000),
            ("ply", ply_ascii_fixture()),
            ("ply", ply_ascii_fixture() + b"\n" * 1_000),
            ("ply", ply_binary_fixture()),
            ("glb", glb_fixture()),
        ):
            with self.subTest(extension=extension, size=len(data)):
                preview = media.inspect_model(data, extension)
                self.assertEqual(preview.vertex_count, 3)
                self.assertEqual(preview.face_count, 1)
                self.assertEqual(preview.faces[0], (0, 1, 2))

    def test_model_external_references_and_bounds_reject(self):
        with self.assertRaises(media.AssetInspectionError):
            media.inspect_model(glb_fixture(external_image=True), "glb")
        with self.assertRaises(TypeError):
            media.inspect_model("model.obj", "obj")
        with mock.patch.object(media, "MAX_MESH_VERTICES", 2):
            with self.assertRaises(media.AssetInspectionError):
                media.inspect_model(obj_fixture(), "obj")

    def test_glb_repeated_accessors_and_text_model_lines_are_bounded(self):
        with mock.patch.object(media, "MAX_GLTF_MATERIALIZED_BYTES", 100):
            with self.assertRaisesRegex(media.AssetInspectionError, "decoded-memory cap"):
                media._glb_json(glb_fixture(repeated_accessors=4))
        with mock.patch.object(media, "MAX_MESH_VERTICES", 4):
            with self.assertRaisesRegex(media.AssetInspectionError, "total mesh geometry"):
                media._glb_json(glb_fixture(repeated_meshes=1))
        with mock.patch.object(media, "MAX_TEXT_LINE_CHARS", 8):
            with self.assertRaisesRegex(media.AssetInspectionError, "line exceeds"):
                media._obj_preflight(b"#" + b"x" * 9)
        with mock.patch.object(media, "MAX_TEXT_LINES", 2):
            with self.assertRaisesRegex(media.AssetInspectionError, "line count exceeds"):
                list(media._iter_text_lines("\n\n\n"))

    def test_glb_rejects_optional_compression_extensions_before_loader(self):
        for extension in ("KHR_draco_mesh_compression", "EXT_meshopt_compression"):
            for declared in (True, False):
                with self.subTest(extension=extension, declared=declared):
                    with self.assertRaisesRegex(media.AssetInspectionError, "compressed glTF"):
                        media._glb_json(glb_fixture(
                            compression_extension=extension,
                            declare_extension=declared,
                        ))


class OptionalDependencyTests(unittest.TestCase):
    def test_missing_optional_dependency_has_clear_error(self):
        with mock.patch.object(media.importlib, "import_module", side_effect=ImportError("missing")):
            with self.assertRaises(media.AssetDependencyError) as caught:
                media.inspect_audio(wav_fixture(), "wav")
        self.assertIn("miniaudio", str(caught.exception))


if __name__ == "__main__":
    unittest.main()


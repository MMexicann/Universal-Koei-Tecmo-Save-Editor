"""Read-only workspace dispatch checks using synthetic media bytes only."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
import zipfile
import zlib

from koei_editor.research.asset_explorer import gui


def _png_chunk(kind: bytes, body: bytes) -> bytes:
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def _one_pixel_png() -> bytes:
    return (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + _png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
            + _png_chunk(b"IEND", b""))


class AssetExplorerDispatchTests(unittest.TestCase):
    def test_direct_and_zip_member_images_reach_the_in_memory_preview(self):
        image = _one_pixel_png()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            direct_path = directory / "direct.png"
            direct_path.write_bytes(image)
            direct = gui._load_local(str(direct_path))
            self.assertEqual(direct[0], "image")
            self.assertEqual(direct[2].rgba_bytes, bytes((255, 0, 0, 255)))

            archive_path = directory / "synthetic.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive_file:
                archive_file.writestr("textures/portrait.png", image)
            archive_result = gui._load_local(str(archive_path))
            self.assertEqual(archive_result[0], "archive")
            archive = archive_result[2]
            self.assertEqual(len(archive.entries), 1)

            preview_result = gui._load_zip_member(str(archive_path), archive.entries[0])
            self.assertEqual(preview_result[0], "image")
            self.assertEqual(preview_result[1], "textures/portrait.png")
            self.assertEqual(preview_result[2].rgba_bytes, bytes((255, 0, 0, 255)))
            self.assertEqual(preview_result[3], archive.entries[0])
            self.assertEqual(sorted(path.name for path in directory.iterdir()),
                             ["direct.png", "synthetic.zip"])


if __name__ == "__main__":
    unittest.main()

"""Verified archive creation and rejection checks for the mod workshop."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from koei_editor.shared.mod_workshop.asset_explorer import register_replacement
from koei_editor.shared.mod_workshop.models import ModManifest
from koei_editor.shared.mod_workshop.packaging import (
    PackageError,
    build_package,
    verify_package,
)
from koei_editor.shared.mod_workshop.project_manager import initialize_project, save_manifest
from koei_editor.shared.mod_workshop.validation import CompatibilityContext
from unittest.mock import patch


def _manifest(**changes):
    values = {
        "mod_id": "demo.texture",
        "name": "Demo Texture",
        "version": "1.0.0",
        "author": "Creator",
        "description": "A user authored replacement.",
        "game_id": "demo-game",
        "game_version": "1.0.0",
        "platform": "Windows PC",
        "license": "MIT",
    }
    values.update(changes)
    return ModManifest(**values)


class VerifiedPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = initialize_project(self.root / "project", _manifest(), "texture-replacement")
        self.source = self.project / "assets" / "textures" / "replacement.bin"
        self.source.write_bytes(b"creator-authored replacement bytes")
        record = register_replacement(
            self.project,
            self.source,
            "data/textures/custom.bin",
            license="MIT",
            rights_status="creator-owned",
        )
        self.manifest = _manifest(replacements=(record,))
        save_manifest(self.project, self.manifest)
        self.context = CompatibilityContext("demo-game", "1.0.0", "Windows PC")

    def test_build_and_verify_package_contains_only_selected_replacements(self):
        unrelated = self.project / "notes.txt"
        unrelated.write_text("must stay out of the package", encoding="utf-8")
        output = self.root / "demo.zip"

        report = build_package(self.project, output, self.context)
        verification = verify_package(output)

        self.assertTrue(report["valid"])
        self.assertTrue(verification["valid"])
        self.assertEqual(verification["summary"]["replacement_files"], 1)
        self.assertEqual(verification["mod_id"], self.manifest.mod_id)
        self.assertEqual(verification["compatibility"]["context"]["game_id"], "demo-game")
        self.assertEqual(verification["assets"][0]["sha256"], self.manifest.replacements[0].sha256)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"mod.json", "verification.json", "replacements/data/textures/custom.bin"},
            )
            packaged_manifest = json.loads(archive.read("mod.json"))
            replacement = packaged_manifest["replacements"][0]
            self.assertEqual(replacement["source_path"], "replacements/data/textures/custom.bin")
            self.assertNotIn(str(self.project), archive.read("mod.json").decode("utf-8"))
            self.assertEqual(
                archive.read("replacements/data/textures/custom.bin"),
                b"creator-authored replacement bytes",
            )

    def test_archive_is_reproducible_and_existing_output_is_not_overwritten(self):
        first = self.root / "first.zip"
        second = self.root / "second.zip"
        build_package(self.project, first, self.context)
        build_package(self.project, second, self.context)
        self.assertEqual(first.read_bytes(), second.read_bytes())

        existing = self.root / "existing.zip"
        existing.write_bytes(b"keep existing file")
        with self.assertRaises(FileExistsError):
            build_package(self.project, existing, self.context)
        self.assertEqual(existing.read_bytes(), b"keep existing file")

    def test_invalid_context_does_not_create_output(self):
        output = self.root / "incompatible.zip"
        bad_context = CompatibilityContext("other-game", "1.0.0", "Windows PC")
        with self.assertRaises(PackageError):
            build_package(self.project, output, bad_context)
        self.assertFalse(output.exists())

    def test_replacement_change_after_registration_blocks_packaging(self):
        self.source.write_bytes(b"different bytes")
        output = self.root / "changed.zip"
        with self.assertRaises(PackageError):
            build_package(self.project, output, self.context)
        self.assertFalse(output.exists())

    def test_oversized_replacement_is_stopped_while_streaming(self):
        output = self.root / "oversized.zip"
        with patch("koei_editor.shared.mod_workshop.packaging.MAX_ASSET_BYTES", 8):
            with self.assertRaisesRegex(PackageError, "safety limit"):
                build_package(self.project, output, self.context)
        self.assertFalse(output.exists())

    def test_highly_compressible_replacements_still_build_and_verify(self):
        self.source.write_bytes(b"\x00" * 100_000)
        record = register_replacement(
            self.project,
            self.source,
            "data/textures/mostly-empty.bin",
            license="MIT",
            rights_status="creator-owned",
        )
        save_manifest(self.project, _manifest(replacements=(record,)))
        output = self.root / "compressible.zip"

        build_package(self.project, output, self.context)

        self.assertTrue(verify_package(output)["valid"])

    def test_multiple_replacements_verify_in_canonical_path_order(self):
        second_source = self.project / "assets" / "textures" / "second.bin"
        second_source.write_bytes(b"second creator-authored file")
        second_record = register_replacement(
            self.project,
            second_source,
            "data/textures/a.bin",
            license="MIT",
            rights_status="creator-owned",
        )
        later_record = register_replacement(
            self.project,
            self.source,
            "data/textures/z.bin",
            license="MIT",
            rights_status="creator-owned",
        )
        # Deliberately declare the targets in the opposite order from package order.
        save_manifest(self.project, _manifest(replacements=(later_record, second_record)))
        output = self.root / "multiple.zip"

        build_package(self.project, output, self.context)

        self.assertTrue(verify_package(output)["valid"])
        with zipfile.ZipFile(output) as archive:
            report = json.loads(archive.read("verification.json"))
        self.assertEqual(
            [item["path"] for item in report["assets"]],
            ["replacements/data/textures/a.bin", "replacements/data/textures/z.bin"],
        )

    def test_verifier_rejects_tampered_replacement_bytes(self):
        output = self.root / "good.zip"
        tampered = self.root / "tampered.zip"
        build_package(self.project, output, self.context)
        with zipfile.ZipFile(output) as original, zipfile.ZipFile(tampered, "w") as altered:
            for name in original.namelist():
                payload = original.read(name)
                if name.startswith("replacements/"):
                    payload = b"tampered"
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o100644) << 16
                altered.writestr(info, payload)
        with self.assertRaisesRegex(PackageError, "digest"):
            verify_package(tampered)

    def test_verifier_rejects_unsafe_archive_paths_and_unexpected_files(self):
        unsafe = self.root / "unsafe.zip"
        with zipfile.ZipFile(unsafe, "w") as archive:
            info = zipfile.ZipInfo("../escape.bin")
            info.create_system = 3
            info.external_attr = (0o100644) << 16
            archive.writestr(info, b"escape")
        with self.assertRaisesRegex(PackageError, "Unsafe package path"):
            verify_package(unsafe)

        output = self.root / "good.zip"
        extra = self.root / "extra.zip"
        build_package(self.project, output, self.context)
        with zipfile.ZipFile(output) as original, zipfile.ZipFile(extra, "w") as altered:
            for name in original.namelist():
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o100644) << 16
                altered.writestr(info, original.read(name))
            info = zipfile.ZipInfo("README.txt")
            info.create_system = 3
            info.external_attr = (0o100644) << 16
            altered.writestr(info, b"undeclared")
        with self.assertRaisesRegex(PackageError, "undeclared"):
            verify_package(extra)

    def test_packaging_rejects_a_symlinked_project_root(self):
        link = self.root / "project-link"
        try:
            link.symlink_to(self.project, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlinks are unavailable on this platform.")
        with self.assertRaises(ValueError):
            build_package(link, self.root / "linked.zip", self.context)

    def test_verification_report_binds_the_asset_sha256(self):
        output = self.root / "report.zip"
        build_package(self.project, output, self.context)
        with zipfile.ZipFile(output) as archive:
            report = json.loads(archive.read("verification.json"))
        self.assertEqual(
            report["assets"][0]["sha256"],
            hashlib.sha256(b"creator-authored replacement bytes").hexdigest(),
        )
        self.assertEqual(report["checks"][2]["status"], "self-declared")


if __name__ == "__main__":
    unittest.main()

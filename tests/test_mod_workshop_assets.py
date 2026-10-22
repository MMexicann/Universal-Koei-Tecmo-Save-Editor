import hashlib
import tempfile
import unittest
from pathlib import Path

from koei_editor.shared.mod_workshop.asset_explorer import (
    AssetSafetyError,
    hash_project_file,
    normalize_target_path,
    read_verified_replacement,
    register_replacement,
    verify_replacement,
)


class AssetExplorerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "project"
        (self.root / "assets").mkdir(parents=True)
        self.source = self.root / "assets" / "new-texture.bin"
        self.source.write_bytes(b"user replacement bytes")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def register(self, **overrides):
        options = {
            "project_root": self.root,
            "source_file": self.source,
            "target_path": "data/textures/new-texture.bin",
            "license": "CC-BY-4.0",
            "rights_status": "permissive-license",
            "attribution": "Example Artist",
        }
        options.update(overrides)
        return register_replacement(**options)

    def test_registration_records_project_relative_path_and_sha256(self):
        record = self.register()
        self.assertEqual(record.source_path, "assets/new-texture.bin")
        self.assertEqual(record.target_path, "data/textures/new-texture.bin")
        self.assertEqual(record.sha256, hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(record.license, "CC-BY-4.0")
        self.assertEqual(record.rights_status, "permissive-license")
        self.assertEqual(verify_replacement(self.root, record), record.sha256)

    def test_hash_project_file_accepts_absolute_picker_path_and_returns_relative_record(self):
        relative, digest = hash_project_file(self.root, self.source)
        self.assertEqual(relative, "assets/new-texture.bin")
        self.assertEqual(digest, hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_changed_source_is_detected(self):
        record = self.register()
        self.source.write_bytes(b"changed after registration")
        with self.assertRaisesRegex(AssetSafetyError, "changed after registration"):
            verify_replacement(self.root, record)

    def test_read_verified_replacement_returns_exact_registered_bytes(self):
        record = self.register()
        self.assertEqual(read_verified_replacement(self.root, record), b"user replacement bytes")

    def test_read_verified_replacement_rejects_changed_file(self):
        record = self.register()
        self.source.write_bytes(b"changed before package read")
        with self.assertRaisesRegex(AssetSafetyError, "changed after registration"):
            read_verified_replacement(self.root, record)

    def test_target_paths_are_normalized_and_reject_unsafe_forms(self):
        self.assertEqual(normalize_target_path(r"data\textures\custom.dds"), "data/textures/custom.dds")
        unsafe_paths = (
            "",
            "/absolute/file.bin",
            r"C:\\Windows\\file.bin",
            r"\\\\server\\share\\file.bin",
            "../outside.bin",
            "data/../outside.bin",
            r"data\..\outside.bin",
            "data//empty-segment.bin",
            "data/./current.bin",
            "data\n/linebreak.bin",
            "data/bad?.bin",
        )
        for target in unsafe_paths:
            with self.subTest(target=target), self.assertRaises(AssetSafetyError):
                normalize_target_path(target)

    def test_source_outside_project_is_rejected(self):
        outside = self.root.parent / "outside.bin"
        outside.write_bytes(b"not part of the project")
        with self.assertRaisesRegex(AssetSafetyError, "inside the selected project"):
            self.register(source_file=outside)

    def test_parent_traversal_in_source_path_is_rejected(self):
        with self.assertRaisesRegex(AssetSafetyError, "parent traversal"):
            self.register(source_file="assets/../assets/new-texture.bin")

    def test_symlink_sources_and_symlink_directories_are_rejected(self):
        outside = self.root.parent / "linked.bin"
        outside.write_bytes(b"outside")
        link = self.root / "assets" / "linked.bin"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable on this platform.")
        with self.assertRaises(AssetSafetyError):
            self.register(source_file=link)

        link.unlink()
        external_directory = self.root.parent / "external"
        external_directory.mkdir()
        (external_directory / "escape.bin").write_bytes(b"outside")
        linked_directory = self.root / "linked-assets"
        linked_directory.symlink_to(external_directory, target_is_directory=True)
        with self.assertRaises(AssetSafetyError):
            self.register(source_file="linked-assets/escape.bin")

    def test_symlinked_selected_project_root_is_rejected(self):
        selected_root = self.root.parent / "selected-project-link"
        try:
            selected_root.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable on this platform.")
        with self.assertRaisesRegex(AssetSafetyError, "project root cannot be a symbolic link"):
            self.register(project_root=selected_root)

    def test_rights_status_must_be_explicit_and_allowed(self):
        for status in (None, "", "game-original", "game-extracted", "unknown"):
            with self.subTest(status=status), self.assertRaises(AssetSafetyError):
                self.register(rights_status=status)

    def test_permissive_license_requires_attribution(self):
        with self.assertRaisesRegex(AssetSafetyError, "require attribution"):
            self.register(attribution=" ")

    def test_creator_owned_and_public_domain_declarations_are_allowed(self):
        creator = self.register(rights_status="creator-owned", license="MIT", attribution="")
        public_domain = self.register(rights_status="public-domain", license="CC0-1.0", attribution="")
        self.assertEqual(creator.rights_status, "creator-owned")
        self.assertEqual(public_domain.rights_status, "public-domain")

    def test_license_label_is_required(self):
        with self.assertRaisesRegex(AssetSafetyError, "license or rights label"):
            self.register(license=" ")


if __name__ == "__main__":
    unittest.main()

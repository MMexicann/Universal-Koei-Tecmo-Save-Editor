"""Project initialization, templates and dependency declarations."""

import json
import tempfile
import unittest
from pathlib import Path

from koei_editor.shared.mod_workshop.models import Dependency, ManifestError, ModManifest
from koei_editor.shared.mod_workshop.project_manager import (
    MANIFEST_FILENAME,
    add_dependency,
    initialize_project,
    load_project,
    remove_dependency,
    save_manifest,
    validate_dependency,
)
from koei_editor.shared.mod_workshop.templates import PROJECT_TEMPLATES, get_template, list_templates


def _manifest(**changes):
    values = {
        "mod_id": "demo.texture",
        "name": "Demo Texture",
        "version": "1.0.0",
        "author": "Creator",
        "description": "A user-authored replacement.",
        "game_id": "demo-game",
        "game_version": "1.0.0",
        "platform": "Windows PC",
        "license": "MIT",
    }
    values.update(changes)
    return ModManifest(**values)


class ProjectTemplateTests(unittest.TestCase):
    def test_generic_templates_have_no_game_asset_payloads(self):
        templates = list_templates()
        self.assertEqual(templates, PROJECT_TEMPLATES)
        self.assertEqual(
            {template.template_id for template in templates},
            {"blank", "texture-replacement", "audio-replacement"},
        )
        for template in templates:
            self.assertTrue(template.description)
            self.assertTrue(template.asset_guidance)
            self.assertEqual(template.asset_subfolders, {
                "blank": (),
                "texture-replacement": ("textures",),
                "audio-replacement": ("audio",),
            }[template.template_id])
        self.assertEqual(get_template("blank").name, "Blank replacement mod")
        with self.assertRaises(ValueError):
            get_template("unknown")

    def test_initialize_and_load_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "new-project"
            manifest = _manifest()
            result = initialize_project(project, manifest, "texture-replacement")

            self.assertEqual(result, project)
            self.assertEqual(load_project(project), manifest)
            self.assertEqual(json.loads((project / MANIFEST_FILENAME).read_text()), manifest.to_dict())
            self.assertTrue((project / "assets").is_dir())
            self.assertEqual(list((project / "assets" / "textures").iterdir()), [])
            self.assertEqual([path.name for path in (project / "assets").iterdir()], ["textures"])
            readme = (project / "README.md").read_text(encoding="utf-8")
            self.assertIn("do not add original game files", readme.lower())
            self.assertIn("public modding documentation", readme)

    def test_blank_and_audio_templates_create_empty_asset_layouts(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            blank = initialize_project(base / "blank", _manifest(), "blank")
            audio = initialize_project(base / "audio", _manifest(), "audio-replacement")

            self.assertEqual(list((blank / "assets").iterdir()), [])
            self.assertEqual([path.name for path in (audio / "assets").iterdir()], ["audio"])
            self.assertEqual(list((audio / "assets" / "audio").iterdir()), [])

    def test_initialize_rejects_existing_empty_or_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            empty = Path(temp) / "empty"
            empty.mkdir()
            with self.assertRaises(FileExistsError):
                initialize_project(empty, _manifest())
            self.assertEqual(list(empty.iterdir()), [])

            occupied = Path(temp) / "occupied"
            occupied.mkdir()
            original = occupied / "keep.txt"
            original.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                initialize_project(occupied, _manifest())
            self.assertEqual(original.read_text(encoding="utf-8"), "keep")

    def test_project_paths_and_manifest_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / "target"
            target.mkdir()
            link = base / "project-link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError):
                self.skipTest("Directory symlinks are unavailable on this platform.")
            with self.assertRaises(ValueError):
                initialize_project(link, _manifest())

            project = base / "safe-project"
            initialize_project(project, _manifest())
            outside = base / "outside.json"
            outside.write_text(json.dumps(_manifest().to_dict()), encoding="utf-8")
            (project / MANIFEST_FILENAME).unlink()
            (project / MANIFEST_FILENAME).symlink_to(outside)
            with self.assertRaises(ManifestError):
                load_project(project)

    def test_save_manifest_preserves_project_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            initialize_project(project, _manifest())
            user_asset = project / "assets" / "my-art.bin"
            user_asset.write_bytes(b"user-created")
            changed = _manifest(description="Updated metadata")
            save_manifest(project, changed)
            self.assertEqual(load_project(project), changed)
            self.assertEqual(user_asset.read_bytes(), b"user-created")


class DependencyDeclarationTests(unittest.TestCase):
    def test_add_and_remove_dependency_are_immutable(self):
        original = _manifest()
        dependency = Dependency("shared.palette", ">=1.2.0,<2.0.0", optional=True)
        updated = add_dependency(original, dependency)
        self.assertEqual(original.dependencies, ())
        self.assertEqual(updated.dependencies, (dependency,))
        self.assertEqual(remove_dependency(updated, "SHARED.PALETTE").dependencies, ())

    def test_duplicate_self_invalid_identifier_and_invalid_version_are_rejected(self):
        manifest = _manifest()
        with self.assertRaisesRegex(ValueError, "already declared"):
            add_dependency(add_dependency(manifest, Dependency("shared.palette")), Dependency("shared.palette"))
        with self.assertRaisesRegex(ValueError, "cannot depend on itself"):
            add_dependency(manifest, Dependency("demo.texture"))
        with self.assertRaises(ValueError):
            validate_dependency(Dependency("Not-A-Mod", "*"), manifest)
        with self.assertRaises(ValueError):
            validate_dependency(Dependency("shared.palette", "latest"), manifest)
        with self.assertRaises(ValueError):
            validate_dependency(Dependency("shared.palette", ">=1.2"), manifest)

    def test_supported_dependency_constraint_forms(self):
        manifest = _manifest()
        for constraint in ("*", "1.2.3", "=1.2.3", ">=1.2.0", ">=1.2.0,<2.0.0"):
            with self.subTest(constraint=constraint):
                validate_dependency(Dependency("shared.palette", constraint), manifest)


if __name__ == "__main__":
    unittest.main()

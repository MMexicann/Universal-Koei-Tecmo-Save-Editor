"""Metadata and compatibility checks for the mod creation workshop."""

import tempfile
import unittest
from pathlib import Path

from koei_editor.shared.mod_workshop.asset_explorer import register_replacement
from koei_editor.shared.mod_workshop.models import AssetReplacement, Dependency, ModManifest
from koei_editor.shared.mod_workshop.project_manager import initialize_project, save_manifest
from koei_editor.shared.mod_workshop.validation import (
    CompatibilityContext,
    InstalledMod,
    validate_manifest,
    validate_project,
    version_satisfies,
)


def _manifest(**changes):
    values = {
        "mod_id": "demo.texture",
        "name": "Demo Texture",
        "version": "1.0.0",
        "author": "Creator",
        "description": "A user-created replacement.",
        "game_id": "demo-game",
        "game_version": ">=1.0.0,<2.0.0",
        "platform": "Windows PC",
        "license": "MIT",
    }
    values.update(changes)
    return ModManifest(**values)


class VersionRangeTests(unittest.TestCase):
    def test_semver_comparators_and_intersections(self):
        self.assertTrue(version_satisfies("1.5.0", ">=1.2.0,<2.0.0"))
        self.assertTrue(version_satisfies("1.2.0", "=1.2.0"))
        self.assertTrue(version_satisfies("4.0.0", "*"))
        self.assertFalse(version_satisfies("2.0.0", ">=1.2.0,<2.0.0"))
        self.assertFalse(version_satisfies("1.2.0", "latest"))
        self.assertFalse(version_satisfies("01.2.0", "*"))


class CompatibilityValidationTests(unittest.TestCase):
    def test_valid_manifest_matches_selected_game_and_dependencies(self):
        manifest = _manifest(dependencies=(Dependency("shared.palette", ">=1.2.0,<2.0.0"),))
        context = CompatibilityContext(
            game_id="demo-game",
            game_version="1.5.0",
            platform="windows pc",
            installed_mods=(InstalledMod("shared.palette", "1.4.0"),),
        )
        report = validate_manifest(manifest, context)
        self.assertTrue(report.valid)
        self.assertEqual(report.to_dict()["summary"], {"errors": 0, "warnings": 0})

    def test_game_build_platform_and_required_dependency_mismatches_fail(self):
        manifest = _manifest(dependencies=(Dependency("shared.palette", ">=1.2.0,<2.0.0"),))
        context = CompatibilityContext("other-game", "2.0.0", "Linux", ())
        report = validate_manifest(manifest, context)
        self.assertFalse(report.valid)
        codes = {item.code for item in report.findings}
        self.assertTrue({
            "compatibility.game.mismatch",
            "compatibility.platform.mismatch",
            "compatibility.game_version.mismatch",
            "compatibility.dependency_missing",
        }.issubset(codes))

    def test_optional_missing_dependency_is_a_warning(self):
        manifest = _manifest(dependencies=(Dependency("optional.palette", "*", optional=True),))
        context = CompatibilityContext("demo-game", "1.5.0", "Windows PC", ())
        report = validate_manifest(manifest, context)
        self.assertTrue(report.valid)
        self.assertEqual([item.severity for item in report.findings], ["warning"])

    def test_installed_dependency_version_mismatch_fails(self):
        manifest = _manifest(dependencies=(Dependency("shared.palette", ">=1.2.0,<2.0.0"),))
        context = CompatibilityContext(
            "demo-game", "1.5.0", "Windows PC", (InstalledMod("shared.palette", "2.1.0"),)
        )
        report = validate_manifest(manifest, context)
        self.assertFalse(report.valid)
        self.assertIn("compatibility.dependency_version", {item.code for item in report.findings})

    def test_invalid_unrelated_installed_mod_entries_fail_context_validation(self):
        report = validate_manifest(
            _manifest(),
            CompatibilityContext("demo-game", "1.5.0", "Windows PC", (InstalledMod("bad id", "latest"),)),
        )
        self.assertFalse(report.valid)
        codes = {item.code for item in report.findings}
        self.assertIn("compatibility.installed_id.invalid", codes)
        self.assertIn("compatibility.installed_version.invalid", codes)

    def test_manifest_metadata_and_asset_declarations_are_checked(self):
        invalid_asset = AssetReplacement("assets/texture.bin", "../escape.bin", "bad", "", "", "game-original")
        manifest = _manifest(mod_id="Upper ID", version="1.2", replacements=(invalid_asset,))
        report = validate_manifest(manifest)
        self.assertFalse(report.valid)
        codes = {item.code for item in report.findings}
        self.assertTrue({
            "manifest.id.invalid",
            "manifest.version.invalid",
            "asset.target.unsafe",
            "asset.hash.invalid",
            "asset.rights.unverified",
            "asset.license.required",
        }.issubset(codes))

    def test_permissive_asset_declaration_requires_attribution(self):
        replacement = AssetReplacement(
            "assets/texture.bin", "textures/demo.bin", "a" * 64,
            "CC-BY-4.0", "", "permissive-license",
        )
        report = validate_manifest(_manifest(replacements=(replacement,)))
        self.assertFalse(report.valid)
        self.assertIn("asset.attribution.required", {item.code for item in report.findings})

    def test_project_validation_checks_source_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "demo"
            initialize_project(project, _manifest())
            source = project / "assets" / "texture.bin"
            source.write_bytes(b"first bytes")
            replacement = register_replacement(
                project, source, "textures/demo.bin", license="MIT", rights_status="creator-owned"
            )
            save_manifest(project, _manifest(replacements=(replacement,)))
            report = validate_project(str(project), CompatibilityContext("demo-game", "1.5.0", "Windows PC"))
            self.assertTrue(report.valid)
            source.write_bytes(b"changed bytes")
            report = validate_project(str(project), CompatibilityContext("demo-game", "1.5.0", "Windows PC"))
            self.assertFalse(report.valid)
            self.assertIn("asset.source.invalid", {item.code for item in report.findings})


if __name__ == "__main__":
    unittest.main()

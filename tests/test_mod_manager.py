"""Safety and profile tests for the verified Nioh 2 PC mod folder adapter."""

import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from koei_editor.shared.mod_manager import (
    DISABLED_SUFFIX,
    GAME_EXE,
    LOADER_FILE,
    MODS_DIR,
    InstallationError,
    ModManager,
    PackageError,
    ProfileError,
    SafetyError,
)


def make_archive(path, *, mod_id=None, dependencies=(), conflicts=(), files=None,
                 extra_entries=()):
    """Write a small, generated package matching Nioh 2's documented layout."""
    entries = {
        "NiohMod/mod.ini": b"[Mod]\nName=Test\n",
        "NiohMod/assets/model.fmt": b"synthetic fmt payload",
    }
    if files:
        entries = dict(files)
    if mod_id is not None:
        metadata = {
            "schema_version": 1,
            "game_id": "nioh2_pc",
            "id": mod_id,
            "name": mod_id.replace("-", " ").title(),
            "version": "1.0",
            "dependencies": list(dependencies),
            "conflicts": list(conflicts),
        }
        entries["koei-mod.json"] = json.dumps(metadata).encode("utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in entries.items():
            archive.writestr(name, contents)
        for item in extra_entries:
            if len(item) == 2:
                name, contents = item
                archive.writestr(name, contents)
            else:
                name, contents, mode = item
                info = zipfile.ZipInfo(name)
                info.external_attr = (mode & 0xFFFF) << 16
                archive.writestr(info, contents)
    return path


def install_root(path):
    path.mkdir()
    (path / GAME_EXE).write_bytes(b"original Nioh 2 executable fixture")
    (path / LOADER_FILE).write_bytes(b"user-installed loader fixture")
    return path


class ModManagerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.state_dir = self.folder / "manager-state"
        self.game = install_root(self.folder / "game")
        self.manager = ModManager(self.state_dir, self.game)

    def package(self, filename, **kwargs):
        return make_archive(self.folder / filename, **kwargs)

    def import_mod(self, filename="test-mod.zip", **kwargs):
        return self.manager.import_archive(self.package(filename, **kwargs))

    def test_import_and_apply_profile_preserve_original_game_files(self):
        original = {name: (self.game / name).read_bytes() for name in (GAME_EXE, LOADER_FILE)}
        mod = self.import_mod(mod_id="test-mod")
        self.manager.set_profile_mod_enabled("default", mod.id, True)

        statuses = self.manager.apply_profile("default", loader_confirmed=True)

        self.assertTrue(any("Installed and enabled" in status for status in statuses))
        self.assertEqual((self.game / GAME_EXE).read_bytes(), original[GAME_EXE])
        self.assertEqual((self.game / LOADER_FILE).read_bytes(), original[LOADER_FILE])
        installed = self.game / MODS_DIR / mod.id
        self.assertEqual((installed / "mod.ini").read_bytes(), b"[Mod]\nName=Test\n")
        self.assertEqual((installed / "assets/model.fmt").read_bytes(), b"synthetic fmt payload")
        record = next(item for item in self.manager.mods() if item.id == mod.id)
        self.assertTrue(record.installed)
        self.assertTrue(record.enabled)

    def test_profile_switch_uses_loader_disabled_suffix_and_uninstall_removes_only_managed_files(self):
        original = {name: (self.game / name).read_bytes() for name in (GAME_EXE, LOADER_FILE)}
        mod = self.import_mod(mod_id="switchable")
        self.manager.set_profile_mod_enabled("default", mod.id, True)
        self.manager.apply_profile("default", loader_confirmed=True)
        alternate = self.manager.create_profile("Alternate")

        self.manager.apply_profile(alternate.id, loader_confirmed=True)

        disabled = self.game / MODS_DIR / (mod.id + DISABLED_SUFFIX)
        self.assertTrue(disabled.is_dir())
        self.assertFalse((self.game / MODS_DIR / mod.id).exists())
        self.assertFalse(next(item for item in self.manager.mods() if item.id == mod.id).enabled)

        self.manager.apply_profile("default", loader_confirmed=True)
        self.assertTrue((self.game / MODS_DIR / mod.id).is_dir())
        self.assertFalse(disabled.exists())
        self.manager.set_profile_mod_enabled("default", mod.id, False)
        self.manager.apply_profile("default", loader_confirmed=True)
        self.assertTrue(disabled.is_dir())
        self.manager.uninstall_mod(mod.id, loader_confirmed=True)

        self.assertFalse((self.game / MODS_DIR).exists())
        self.assertEqual((self.game / GAME_EXE).read_bytes(), original[GAME_EXE])
        self.assertEqual((self.game / LOADER_FILE).read_bytes(), original[LOADER_FILE])
        self.manager.remove_mod(mod.id)
        self.assertEqual(self.manager.mods(), ())

    def test_loader_and_game_folder_must_be_explicitly_qualified(self):
        mod = self.import_mod(mod_id="guarded")
        self.manager.set_profile_mod_enabled("default", mod.id, True)
        with self.assertRaises(InstallationError):
            self.manager.apply_profile("default")

        missing_loader_root = install_root(self.folder / "without-loader")
        (missing_loader_root / LOADER_FILE).unlink()
        manager = ModManager(self.state_dir, missing_loader_root)
        with self.assertRaises(InstallationError):
            manager.install_mod(mod.id, loader_confirmed=True)

        wrong_root = self.folder / "wrong-game"
        wrong_root.mkdir()
        with self.assertRaises(InstallationError):
            self.manager.set_game_root(wrong_root)

    def test_import_rejects_unsafe_paths_unknown_payload_and_fomod(self):
        invalid = (
            ("traversal", {"NiohMod/mod.ini": b"x", "../escape.fmt": b"x"}, ()),
            ("absolute", {"NiohMod/mod.ini": b"x", "/escape.fmt": b"x"}, ()),
            ("unknown-extension", {"NiohMod/mod.ini": b"x", "NiohMod/loader.dll": b"x"}, ()),
            ("loader-package", {"NiohMod/mod.ini": b"x", "NiohMod/d3d11.dll": b"x"}, ()),
            ("fomod", {"NiohMod/mod.ini": b"x", "NiohMod/module.fmt": b"x"},
             (("NiohMod/FOMOD/ModuleConfig.xml", b"<config />"),)),
            ("missing-marker", {"NiohMod/readme.txt": b"docs", "NiohMod/model.fmt": b"x"}, ()),
        )
        for label, files, extra in invalid:
            with self.subTest(label=label):
                archive = self.package(f"{label}.zip", files=files, extra_entries=extra)
                with self.assertRaises(PackageError):
                    self.manager.import_archive(archive)
        self.assertEqual(self.manager.mods(), ())

    def test_import_rejects_case_collisions_and_symlink_entries(self):
        collision = self.package("case-collision.zip", files={
            "NiohMod/mod.ini": b"x",
            "NiohMod/a.fmt": b"first",
            "NiohMod/A.fmt": b"second",
        })
        with self.assertRaises(PackageError):
            self.manager.import_archive(collision)

        symlink = self.package("symlink.zip", files={
            "NiohMod/mod.ini": b"x",
            "NiohMod/a.fmt": b"payload",
        }, extra_entries=(("NiohMod/link.fmt", b"target", stat.S_IFLNK | 0o777),))
        with self.assertRaises(PackageError):
            self.manager.import_archive(symlink)
        self.assertEqual(self.manager.mods(), ())

    def test_dependencies_conflicts_and_asset_collisions_block_profile_changes(self):
        core = self.import_mod("core.zip", mod_id="core-mod")
        child = self.import_mod("child.zip", mod_id="dependent-mod", dependencies=(core.id,))
        self.manager.set_profile_mod_enabled("default", child.id, False)
        with self.assertRaises(ProfileError):
            self.manager.set_profile_mod_enabled("default", child.id, True)
        self.manager.set_profile_mod_enabled("default", core.id, True)
        self.manager.set_profile_mod_enabled("default", child.id, True)
        self.assertEqual(self.manager.profile_issues("default"), ())

        conflicting = self.import_mod("conflict.zip", mod_id="conflicting-mod", conflicts=(core.id,))
        with self.assertRaises(ProfileError):
            self.manager.set_profile_mod_enabled("default", conflicting.id, True)

        shared = {"NiohMod/mod.ini": b"x", "NiohMod/assets/shared.fmt": b"same path one"}
        other = {"NiohMod/mod.ini": b"x", "NiohMod/assets/shared.fmt": b"same path two"}
        first = self.import_mod("first-asset.zip", mod_id="asset-mod-one", files=shared)
        second = self.import_mod("second-asset.zip", mod_id="asset-mod-two", files=other)
        self.manager.set_profile_mod_enabled("default", first.id, True)
        with self.assertRaisesRegex(ProfileError, "asset path conflict"):
            self.manager.set_profile_mod_enabled("default", second.id, True)
        self.assertNotIn(second.id, self.manager._profile("default")["enabled_mods"])

    def test_changed_managed_files_are_preserved_and_not_uninstalled(self):
        mod = self.import_mod(mod_id="drifted")
        self.manager.install_mod(mod.id, loader_confirmed=True)
        changed = self.game / MODS_DIR / (mod.id + DISABLED_SUFFIX) / "assets" / "model.fmt"
        changed.write_bytes(b"user changed this managed file")

        with self.assertRaises(SafetyError):
            self.manager.uninstall_mod(mod.id, loader_confirmed=True)

        self.assertEqual(changed.read_bytes(), b"user changed this managed file")
        self.assertTrue((self.game / MODS_DIR / (mod.id + DISABLED_SUFFIX)).is_dir())
        self.assertTrue(next(item for item in self.manager.mods() if item.id == mod.id).installed)

    def test_failed_install_rolls_back_files_and_profile_state(self):
        mod = self.import_mod(mod_id="transactional")
        self.manager.set_profile_mod_enabled("default", mod.id, True)
        original_save = self.manager._save_installation
        calls = 0

        def fail_first_state_write():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("simulated state write failure")
            return original_save()

        with patch.object(self.manager, "_save_installation", side_effect=fail_first_state_write):
            with self.assertRaisesRegex(OSError, "simulated state write failure"):
                self.manager.apply_profile("default", loader_confirmed=True)

        self.assertFalse((self.game / MODS_DIR).exists())
        self.assertEqual(self.manager.installation["installed"], {})
        self.assertFalse(self.manager.journal_path.exists())
        self.assertFalse(any(path.name.startswith(".ktmm-transaction-")
                             for path in self.game.iterdir()))
        self.assertEqual((self.game / GAME_EXE).read_bytes(), b"original Nioh 2 executable fixture")

    def test_short_archive_name_uses_restartable_safe_fallback_id(self):
        mod = self.import_mod("A.zip")
        self.assertEqual(mod.id, "a-mod")
        reloaded = ModManager(self.state_dir, self.game)
        self.assertEqual(tuple(item.id for item in reloaded.mods()), ("a-mod",))

    def test_library_removal_checks_profiles_for_every_registered_install(self):
        mod = self.import_mod(mod_id="profile-reference")
        other_game = install_root(self.folder / "other-game")
        other = ModManager(self.state_dir, other_game)
        profile = other.create_profile("Keeps this mod")
        other.set_profile_mod_enabled(profile.id, mod.id, True)

        with self.assertRaisesRegex(ProfileError, "every registered profile"):
            self.manager.remove_mod(mod.id)

        self.assertEqual(tuple(item.id for item in self.manager.mods()), (mod.id,))

    def test_failed_committed_cleanup_keeps_journal_until_recovery(self):
        mod = self.import_mod(mod_id="cleanup-recovery")
        self.manager.install_mod(mod.id, loader_confirmed=True)

        with patch("koei_editor.shared.mod_manager.shutil.rmtree",
                   side_effect=OSError("simulated cleanup failure")):
            with self.assertRaisesRegex(OSError, "simulated cleanup failure"):
                self.manager.uninstall_mod(mod.id, loader_confirmed=True)

            saved_installation = self.manager.install_state_dir / "state.json"
            saved_library = self.manager.index_path
            before_blocked_mutations = (saved_installation.read_bytes(), saved_library.read_bytes())

            pending_mutations = (
                lambda: self.manager.import_archive(self.package("blocked-import.zip", mod_id="blocked-import")),
                lambda: self.manager.create_profile("Blocked"),
                lambda: self.manager.rename_profile("default", "Blocked"),
                lambda: self.manager.delete_profile("default"),
                lambda: self.manager.set_profile_mod_enabled("default", mod.id, True),
                lambda: self.manager.install_mod(mod.id, loader_confirmed=True),
                lambda: self.manager.uninstall_mod(mod.id, loader_confirmed=True),
                lambda: self.manager.remove_mod(mod.id),
                lambda: self.manager.apply_profile("default", loader_confirmed=True),
            )
            for mutation in pending_mutations:
                with self.subTest(mutation=mutation):
                    with self.assertRaisesRegex(OSError, "simulated cleanup failure"):
                        mutation()

            self.assertIn(mod.id, self.manager.index["mods"])
            self.assertTrue((self.manager.packages_dir / mod.id).is_dir())
            self.assertTrue(self.manager.journal_path.exists())
            self.assertEqual((saved_installation.read_bytes(), saved_library.read_bytes()),
                             before_blocked_mutations)

        self.assertTrue(self.manager.journal_path.exists())
        self.assertNotIn(mod.id, self.manager.installation["installed"])
        reloaded = ModManager(self.state_dir, self.game)
        self.assertFalse(reloaded.journal_path.exists())
        self.assertFalse((self.game / MODS_DIR / (mod.id + DISABLED_SUFFIX)).exists())
        self.assertFalse(any(self.game.glob(f".ktmm-remove-*-{mod.id}")))

    def test_unsafe_transaction_journal_does_not_touch_external_paths(self):
        outside = self.folder / "outside"
        outside.mkdir()
        sentinel = outside / "keep.txt"
        sentinel.write_text("preserve", encoding="utf-8")
        self.manager.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.manager.journal_path.write_text(json.dumps({
            "schema_version": 1,
            "committed": True,
            "stage": "../../outside",
        }), encoding="utf-8")

        with self.assertRaises(SafetyError):
            self.manager.recover_pending_transaction()

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
        self.assertTrue(self.manager.journal_path.exists())


if __name__ == "__main__":
    unittest.main()

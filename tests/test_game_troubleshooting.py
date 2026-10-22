"""Deterministic, read-only tests for the Game Troubleshooting Center."""
import json
import os
from contextlib import contextmanager
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import game_troubleshooting as troubleshooting


SECRET = "PRIVATE_CONFIG_VALUE_7c4c1d"
_DEFAULT = object()


def finding(report, identifier):
    matches = [item for item in report.findings if item.id == identifier]
    if len(matches) != 1:
        raise AssertionError(f"Expected one finding {identifier!r}; got {len(matches)}")
    return matches[0]


def snapshot_tree(root):
    """Capture local tree contents and stable metadata, without following links."""
    root = Path(root)
    if not root.exists() and not root.is_symlink():
        return ("missing",)
    paths = [root, *root.rglob("*")]
    snapshot = []
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()
                       if item != root else ""):
        info = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            value = ("symlink", os.readlink(path))
        elif stat.S_ISDIR(info.st_mode):
            value = ("directory",)
        elif stat.S_ISREG(info.st_mode):
            value = ("file", path.read_bytes())
        else:
            value = ("other",)
        snapshot.append((relative, value, mode, info.st_size, info.st_mtime_ns))
    return tuple(snapshot)


@unittest.skipUnless(troubleshooting._DIRECTORY_FDS, "Anchored folder access unavailable")
class GameTroubleshootingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.install = self.base / "installed game"
        self.config = self.base / "configuration"
        self.mods = self.base / "mods"
        self.install.mkdir()
        self.config.mkdir()
        self.mods.mkdir()

    def diagnose(self, *, game_id="origins", install=_DEFAULT, config=_DEFAULT, mods=_DEFAULT):
        return troubleshooting.diagnose_game(
            game_id,
            self.install if install is _DEFAULT else install,
            self.config if config is _DEFAULT else config,
            self.mods if mods is _DEFAULT else mods,
        )

    def test_ordinary_temp_tree_is_scanned_read_only_and_report_is_reproducible(self):
        (self.install / "game.exe").write_bytes(b"synthetic executable marker")
        (self.mods / "plugin.asi").write_text("loader bytes are not inspected", encoding="utf-8")
        (self.config / "settings.json").write_text(
            json.dumps({"privateSetting": SECRET}), encoding="utf-8")
        before = {root: snapshot_tree(root) for root in (self.install, self.config, self.mods)}

        with patch.object(subprocess, "run", side_effect=AssertionError("must not run subprocess")), \
                patch.object(subprocess, "Popen", side_effect=AssertionError("must not run subprocess")), \
                patch.object(os, "system", side_effect=AssertionError("must not run a command")):
            first = self.diagnose()
            second = self.diagnose()

        self.assertEqual(first.to_json(), second.to_json())
        self.assertTrue(first.to_dict()["read_only"])
        self.assertEqual(finding(first, "installation.selected_root").status, "passed")
        self.assertEqual(finding(first, "configuration.syntax").status, "passed")
        self.assertEqual(finding(first, "mods.scan").status, "passed")
        self.assertEqual(finding(first, "mods.conflicts").status, "not_checked")
        self.assertNotIn("mods.candidate_markers", {item.id for item in first.findings})
        self.assertEqual(
            {item.category for item in first.findings},
            set(troubleshooting.CATEGORY_ORDER),
        )
        rank = {category: index for index, category in enumerate(troubleshooting.CATEGORY_ORDER)}
        expected_order = sorted(first.findings, key=lambda item: (rank[item.category], item.id))
        self.assertEqual(list(first.findings), expected_order)

        serialized = first.to_json()
        text = first.to_text()
        for private in (str(self.install), str(self.config), str(self.mods), SECRET,
                       "synthetic executable marker", "loader bytes are not inspected"):
            self.assertNotIn(private, serialized)
            self.assertNotIn(private, text)
        payload = json.loads(serialized)
        self.assertEqual(payload["schema"], troubleshooting.SCHEMA)
        self.assertNotIn("timestamp", payload)
        self.assertNotIn("absolute_path", serialized)
        self.assertNotIn("sha256", serialized)
        self.assertEqual(before, {root: snapshot_tree(root) for root in before})

    def test_valid_and_invalid_config_syntax_produces_only_safe_summary(self):
        (self.config / "valid.json").write_text(
            json.dumps({"account": SECRET}), encoding="utf-8")
        (self.config / "invalid.ini").write_text(
            "[broken\npassword=" + SECRET, encoding="utf-8")
        before = snapshot_tree(self.config)

        report = self.diagnose()

        syntax = finding(report, "configuration.syntax")
        self.assertEqual(syntax.status, "warning")
        self.assertIn("syntax parsing failed", syntax.summary)
        self.assertTrue(any("JSON" in item for item in syntax.evidence))
        self.assertTrue(any("INI" in item for item in syntax.evidence))
        self.assertNotIn(SECRET, report.to_json())
        self.assertEqual(before, snapshot_tree(self.config))

    def test_unsupported_config_encoding_is_unverified_not_a_syntax_warning(self):
        (self.config / "legacy.json").write_bytes(b"\xff\xfe\x00\x00")
        before = snapshot_tree(self.config)

        report = self.diagnose()

        self.assertNotIn("configuration.syntax", {item.id for item in report.findings})
        unverified = finding(report, "configuration.scan_limits")
        self.assertEqual(unverified.status, "unknown")
        self.assertIn("unreadable", unverified.summary)
        self.assertEqual(before, snapshot_tree(self.config))

    def test_json_nan_and_infinity_constants_are_rejected_as_syntax_warnings(self):
        invalid_values = {
            "nan.json": b'{"value": NaN}',
            "infinity.json": b'{"value": Infinity}',
            "negative-infinity.json": b'{"value": -Infinity}',
        }
        for name, content in invalid_values.items():
            (self.config / name).write_bytes(content)
        before = snapshot_tree(self.config)

        report = self.diagnose()

        syntax = finding(report, "configuration.syntax")
        self.assertEqual(syntax.status, "warning")
        self.assertIn("3 selected configuration file(s)", syntax.summary)
        self.assertNotIn("NaN", report.to_json())
        self.assertNotIn("Infinity", report.to_json())
        self.assertEqual(before, snapshot_tree(self.config))

    def test_oversized_config_is_not_parsed_or_exposed(self):
        content = json.dumps({"secret": SECRET}).encode("utf-8")
        config_file = self.config / "oversized.json"
        config_file.write_bytes(content)
        before = snapshot_tree(self.config)

        with patch.object(troubleshooting, "MAX_CONFIG_BYTES", len(content) - 1):
            report = self.diagnose()

        limit = finding(report, "configuration.scan_limits")
        self.assertEqual(limit.status, "unknown")
        self.assertIn("too large", limit.summary)
        self.assertNotIn("configuration.syntax", {item.id for item in report.findings})
        self.assertNotIn(SECRET, report.to_json())
        self.assertEqual(before, snapshot_tree(self.config))

    def test_config_file_count_limit_reports_partial_coverage(self):
        for name in ("a.json", "b.ini"):
            (self.config / name).write_text("{}" if name.endswith("json") else "[x]\ny=1",
                                            encoding="utf-8")
        with patch.object(troubleshooting, "MAX_CONFIG_FILES", 1):
            report = self.diagnose()
        limit = finding(report, "configuration.scan_limits")
        self.assertEqual(limit.status, "unknown")
        self.assertIn("only the first 1", limit.summary)

    def test_common_loader_names_do_not_create_candidate_or_conflict_warnings(self):
        marker_names = ("plugin.asi", "dinput8.dll", "version.dll", "winmm.dll")
        for name in marker_names:
            (self.mods / name).write_bytes(b"not opened")
        before = snapshot_tree(self.mods)

        report = self.diagnose()

        scanned = finding(report, "mods.scan")
        conflicts = finding(report, "mods.conflicts")
        self.assertEqual(scanned.status, "passed")
        self.assertEqual(conflicts.status, "not_checked")
        self.assertNotIn("mods.candidate_markers", {item.id for item in report.findings})
        self.assertFalse(any(item.status == "warning" for item in report.findings
                             if item.category == "mods"))
        self.assertNotIn("conflict detected", report.to_text().casefold())
        self.assertEqual(before, snapshot_tree(self.mods))

    def test_reviewed_mod_pattern_match_is_only_a_version_scoped_warning(self):
        first = "plugins/sample/loader-a.dll"
        second = "plugins/sample/loader-b.dll"
        (self.mods / first).parent.mkdir(parents=True)
        (self.mods / first).write_bytes(b"private file content A")
        (self.mods / second).write_bytes(b"private file content B")
        rule = {
            "id": "test.sample-loader-pair",
            "title": "Reviewed sample loader filename pair",
            "summary": "A reviewed filename pattern can be associated with an issue.",
            "evidence": "The test catalog records this exact pair.",
            "match_files": [first, second],
            "affected_versions": "game 1.0 through 1.2; loader 2.x",
            "recommendation": "Review the publisher's compatibility notes before making any manual change.",
            "source": "https://example.org/mod-compatibility",
        }
        profile = {"prerequisites": [], "mod_conflicts": [rule], "compatibility": []}
        before = snapshot_tree(self.mods)

        with patch.dict(troubleshooting._PROFILES, {"origins": profile}):
            report = self.diagnose()

        matched = finding(report, rule["id"])
        self.assertEqual(matched.category, "mods")
        self.assertEqual(matched.status, "warning")
        self.assertEqual(matched.severity, "warning")
        self.assertEqual(matched.source, rule["source"])
        self.assertIn("Affected version scope: " + rule["affected_versions"], matched.evidence)
        self.assertIn("file contents and installed versions were not checked", matched.summary)
        self.assertNotIn("mods.conflicts", {item.id for item in report.findings})
        self.assertNotIn("failed", {item.status for item in report.findings if item.category == "mods"})
        for private in (str(self.mods), first, second, "private file content A", "private file content B"):
            self.assertNotIn(private, report.to_json())
            self.assertNotIn(private, report.to_text())
        self.assertEqual(before, snapshot_tree(self.mods))

    def test_incomplete_reviewed_mod_pattern_remains_not_checked(self):
        first = "plugins/sample/loader-a.dll"
        second = "plugins/sample/loader-b.dll"
        (self.mods / first).parent.mkdir(parents=True)
        (self.mods / first).write_bytes(b"first member only")
        rule = {
            "id": "test.sample-loader-pair",
            "title": "Reviewed sample loader filename pair",
            "summary": "A reviewed filename pattern can be associated with an issue.",
            "evidence": "The test catalog records this exact pair.",
            "match_files": [first, second],
            "affected_versions": "game 1.0 through 1.2; loader 2.x",
            "recommendation": "Review the publisher's compatibility notes before making any manual change.",
            "source": "https://example.org/mod-compatibility",
        }
        profile = {"prerequisites": [], "mod_conflicts": [rule], "compatibility": []}
        before = snapshot_tree(self.mods)

        with patch.dict(troubleshooting._PROFILES, {"origins": profile}):
            report = self.diagnose()

        conflicts = finding(report, "mods.conflicts")
        self.assertEqual(conflicts.status, "not_checked")
        self.assertIn("no exact reviewed filename pattern matched", conflicts.summary)
        self.assertNotIn(rule["id"], {item.id for item in report.findings})
        self.assertEqual(before, snapshot_tree(self.mods))

    def test_catalog_rejects_builtin_finding_id_collisions_and_traversal_paths(self):
        base_rule = {
            "id": "test.sample-loader-pair",
            "title": "Reviewed sample loader filename pair",
            "summary": "A reviewed filename pattern can be associated with an issue.",
            "evidence": "The catalog records this exact pair.",
            "match_files": ["plugins/loader-a.dll", "plugins/loader-b.dll"],
            "affected_versions": "game 1.0 through 1.2; loader 2.x",
            "recommendation": "Review the publisher's compatibility notes before any manual change.",
            "source": "https://example.org/mod-compatibility",
        }
        invalid_rules = (
            {**base_rule, "id": "mods.conflicts"},
            {**base_rule, "id": "test.traversal",
             "match_files": ["plugins/loader-a.dll", "../outside/loader-b.dll"]},
        )
        for index, rule in enumerate(invalid_rules):
            with self.subTest(rule_id=rule["id"]):
                catalog_path = self.base / f"catalog-{index}.json"
                catalog_path.write_text(json.dumps({
                    "schema_version": 1,
                    "ruleset_version": "2026.10.22",
                    "profiles": [{
                        "game_id": "origins",
                        "prerequisites": [{
                            "id": "test.directx-requirement",
                            "title": "DirectX system requirement",
                            "summary": "The publisher lists a DirectX requirement.",
                            "evidence": "Official specification: DirectX 12 or over.",
                            "recommendation": "Check the full system requirements with the publisher.",
                            "source": "https://example.org/system-requirements",
                        }],
                        "mod_conflicts": [rule],
                        "compatibility": [],
                    }],
                }), encoding="utf-8")
                with patch.object(troubleshooting, "data_file", return_value=catalog_path):
                    with self.assertRaises(troubleshooting.TroubleshootingError):
                        troubleshooting._load_catalog()

    def test_missing_and_unavailable_inputs_remain_unknown_or_not_checked(self):
        missing = self.base / "does not exist"
        report = self.diagnose(install=missing, config=missing, mods=missing)
        self.assertEqual(finding(report, "installation.selected_root").status, "unknown")
        self.assertEqual(finding(report, "configuration.selected_root").status, "unknown")
        self.assertEqual(finding(report, "mods.scan").status, "unknown")
        self.assertEqual(finding(report, "mods.conflicts").status, "not_checked")

        inaccessible = self.base / "inaccessible"
        inaccessible.mkdir()
        real_scandir = os.scandir

        def deny_selected(path):
            if ((isinstance(path, int) and os.fstat(path).st_ino == inaccessible.stat().st_ino)
                    or (not isinstance(path, int) and Path(path) == inaccessible)):
                raise PermissionError("synthetic denied root")
            return real_scandir(path)

        with patch.object(troubleshooting.os, "scandir", side_effect=deny_selected):
            denied = self.diagnose(install=inaccessible, config=inaccessible, mods=inaccessible)
        self.assertEqual(finding(denied, "installation.selected_root").status, "unknown")
        self.assertEqual(finding(denied, "configuration.selected_root").status, "unknown")
        self.assertEqual(finding(denied, "mods.scan").status, "unknown")
        self.assertNotIn("synthetic denied root", denied.to_json())

    def test_queued_directory_replacement_cannot_enumerate_outside_files(self):
        for anchored in (True,):
            with self.subTest(directory_descriptors=anchored):
                queued = self.config / "queued"
                queued.mkdir()
                held = self.base / "held queued"
                outside = self.base / "outside queued"
                outside.mkdir()
                (outside / "private.json").write_text(json.dumps({"secret": SECRET}))
                original = troubleshooting._directory
                replaced = False

                @contextmanager
                def replace_before_open(bindings):
                    nonlocal replaced
                    if bindings[-1][0] == queued and not replaced:
                        queued.rename(held)
                        try:
                            queued.symlink_to(outside, target_is_directory=True)
                        except OSError:
                            held.rename(queued)
                            self.skipTest("Directory symlinks unavailable")
                        replaced = True
                    with original(bindings) as descriptor:
                        yield descriptor

                try:
                    with patch.object(troubleshooting, "_DIRECTORY_FDS", anchored), \
                            patch.object(troubleshooting, "_directory", replace_before_open), \
                            patch.object(troubleshooting, "_decode_config",
                                         side_effect=AssertionError("Outside candidates must not be read")):
                        report = self.diagnose(install=None, mods=None)
                    self.assertTrue(replaced)
                    self.assertEqual(finding(report, "configuration.scan_limits").status, "unknown")
                    self.assertNotIn(SECRET, report.to_json())
                finally:
                    if queued.is_symlink():
                        queued.unlink()
                    if held.exists():
                        held.rename(queued)
                    queued.rmdir()
                    (outside / "private.json").unlink()
                    outside.rmdir()

    def test_configuration_parent_replacement_is_rejected_before_content_read(self):
        queued = self.config / "queued"
        queued.mkdir()
        (queued / "settings.json").write_text('{"selected": true}')
        held = self.base / "held config"
        outside = self.base / "outside config"
        outside.mkdir()
        (outside / "settings.json").write_text(json.dumps({"secret": SECRET}))
        selected, state = troubleshooting._ordinary_root(self.config)
        self.assertEqual(state, "ready")
        files, _, _, truncated = troubleshooting._walk(selected)
        self.assertFalse(truncated)
        self.assertEqual(len(files), 1)
        queued.rename(held)
        try:
            queued.symlink_to(outside, target_is_directory=True)
        except OSError:
            held.rename(queued)
            self.skipTest("Directory symlinks unavailable")
        for anchored in (True,):
            with self.subTest(directory_descriptors=anchored):
                with patch.object(troubleshooting, "_DIRECTORY_FDS", anchored), \
                        patch.object(troubleshooting.os, "fdopen",
                                     side_effect=AssertionError("No configuration content may be read")):
                    self.assertEqual(troubleshooting._decode_config(files[0][0]), "unavailable")

    def test_configuration_read_keeps_walk_identity_after_parent_aba_swap(self):
        # Hold a qualified directory iterator while its pathname temporarily
        # points outside. Its entries must keep the held directory's identity.
        if not troubleshooting._DIRECTORY_FDS:
            self.skipTest("Directory descriptors unavailable")
        queued = self.config / "queued"
        queued.mkdir()
        (queued / "settings.json").write_text('{"selected": true}')
        held = self.base / "held aba"
        outside = self.base / "outside aba"
        outside.mkdir()
        (outside / "settings.json").write_text(json.dumps({"secret": SECRET}))
        selected, _ = troubleshooting._ordinary_root(self.config)
        original_scandir = os.scandir
        queued_identity = queued.stat().st_ino
        replaced = False

        @contextmanager
        def swap_during_enumeration(path):
            nonlocal replaced
            matches = isinstance(path, int) and os.fstat(path).st_ino == queued_identity
            if matches:
                queued.rename(held)
                try:
                    queued.symlink_to(outside, target_is_directory=True)
                except OSError:
                    held.rename(queued)
                    self.skipTest("Directory symlinks unavailable")
                replaced = True
            try:
                with original_scandir(path) as iterator:
                    yield iterator
            finally:
                if matches:
                    queued.unlink()
                    held.rename(queued)

        with patch.object(troubleshooting.os, "scandir", swap_during_enumeration):
            files, _, _, truncated = troubleshooting._walk(selected)
        self.assertTrue(replaced)
        self.assertFalse(truncated)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][0].info.st_ino, (queued / "settings.json").stat().st_ino)
        self.assertNotEqual(files[0][0].info.st_ino, (outside / "settings.json").stat().st_ino)
        self.assertEqual(troubleshooting._decode_config(files[0][0]), "valid")

    def test_replaced_config_cannot_become_a_fresh_read_baseline(self):
        path = self.config / "settings.json"
        path.write_text('{"selected": true}')
        selected, _ = troubleshooting._ordinary_root(self.config)
        files, _, _, _ = troubleshooting._walk(selected)
        path.rename(self.base / "original config")
        path.write_text(json.dumps({"secret": SECRET}))
        for anchored in (True,):
            with self.subTest(directory_descriptors=anchored):
                with patch.object(troubleshooting, "_DIRECTORY_FDS", anchored), \
                        patch.object(troubleshooting.os, "fdopen",
                                     side_effect=AssertionError("Replacement must be rejected before reading")):
                    self.assertEqual(troubleshooting._decode_config(files[0][0]), "changed")

    def test_replacement_between_stat_and_open_is_rejected_before_read(self):
        path = self.config / "settings.json"
        path.write_text('{"selected": true}')
        selected, _ = troubleshooting._ordinary_root(self.config)
        files, _, _, _ = troubleshooting._walk(selected)
        held = self.base / "held original"
        replacement = self.base / "outside replacement"
        replacement.write_text(json.dumps({"secret": SECRET}))
        original_open, original_fdopen = os.open, os.fdopen
        for anchored in (True,):
            with self.subTest(directory_descriptors=anchored):
                replaced = False

                def swap_on_open(target, flags, **kwargs):
                    nonlocal replaced
                    if Path(target).name != path.name:
                        return original_open(target, flags, **kwargs)
                    self.assertTrue(flags & getattr(os, "O_NONBLOCK", 0)
                                    or not hasattr(os, "O_NONBLOCK"))
                    path.rename(held)
                    replacement.rename(path)
                    try:
                        descriptor = original_open(target, flags, **kwargs)
                    finally:
                        path.rename(replacement)
                        held.rename(path)
                    replaced = True
                    return descriptor

                @contextmanager
                def forbid_content_read(descriptor, mode):
                    with original_fdopen(descriptor, mode) as stream:
                        class Guard:
                            def fileno(self):
                                return stream.fileno()

                            def read(self, *_args):
                                raise AssertionError("Replacement bytes were read")
                        yield Guard()

                with patch.object(troubleshooting, "_DIRECTORY_FDS", anchored), \
                        patch.object(troubleshooting.os, "open", swap_on_open), \
                        patch.object(troubleshooting.os, "fdopen", forbid_content_read):
                    self.assertEqual(troubleshooting._decode_config(files[0][0]), "changed")
                self.assertTrue(replaced)

    def test_missing_config_selection_is_not_treated_as_an_error(self):
        report = self.diagnose(config=None)
        selected = finding(report, "configuration.selected_root")
        self.assertEqual(selected.status, "not_checked")
        self.assertIn("not searched automatically", selected.summary)

    def test_symlink_roots_are_rejected_and_symlink_items_are_skipped(self):
        linked_target = self.base / "linked target"
        linked_target.mkdir()
        (linked_target / "plugin.asi").write_text("outside", encoding="utf-8")
        root_link = self.base / "installation link"
        item_link = self.install / "linked-plugin.asi"
        try:
            root_link.symlink_to(linked_target, target_is_directory=True)
            item_link.symlink_to(linked_target / "plugin.asi")
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symlinks are unavailable: {error}")

        before = {root: snapshot_tree(root) for root in (self.install, linked_target)}
        linked_report = self.diagnose(install=root_link, config=self.config, mods=root_link)
        self.assertEqual(finding(linked_report, "installation.selected_root").status, "unknown")
        self.assertEqual(finding(linked_report, "mods.scan").status, "unknown")
        self.assertNotIn("plugin.asi", finding(linked_report, "mods.scan").summary)

        item_report = self.diagnose(install=self.install, config=self.config, mods=self.install)
        self.assertEqual(finding(item_report, "installation.links_skipped").status, "not_checked")
        self.assertEqual(finding(item_report, "mods.scan").status, "passed")
        self.assertEqual(finding(item_report, "mods.scan_limits").status, "unknown")
        self.assertEqual(before, {root: snapshot_tree(root) for root in before})

    def test_parent_traversal_in_selected_root_is_rejected(self):
        selected = self.base / "unused" / ".." / "installed game"
        before = snapshot_tree(self.install)
        report = self.diagnose(install=str(selected), config=self.config, mods=self.mods)
        installation = finding(report, "installation.selected_root")
        self.assertEqual(installation.status, "unknown")
        self.assertNotIn(str(selected), report.to_json())
        self.assertEqual(before, snapshot_tree(self.install))

    def test_entry_limit_is_bounded_and_reported(self):
        for index in range(8):
            (self.install / f"file-{index}.dat").write_bytes(b"x")
        before = snapshot_tree(self.install)
        with patch.object(troubleshooting, "MAX_ENTRIES", 3):
            report = self.diagnose()
            repeated = self.diagnose()
        limited = finding(report, "installation.scan_limit")
        self.assertEqual(limited.status, "unknown")
        self.assertEqual(limited.evidence, ())
        self.assertEqual(report.to_json(), repeated.to_json())
        self.assertNotIn("installation.selected_root", {item.id for item in report.findings})
        self.assertEqual(before, snapshot_tree(self.install))

    def test_origins_directx_requirement_is_cited_but_not_probed(self):
        before = {root: snapshot_tree(root) for root in (self.install, self.config, self.mods)}

        report = self.diagnose()

        prerequisite = finding(report, "origins.directx12.system-requirement")
        self.assertEqual(prerequisite.category, "prerequisites")
        self.assertEqual(prerequisite.status, "not_checked")
        self.assertIn("DirectX 12 or over", prerequisite.summary)
        self.assertIn("graphics feature support", prerequisite.summary)
        self.assertTrue(any("DirectX 12 or over" in item for item in prerequisite.evidence))
        self.assertEqual(
            prerequisite.source,
            "https://www.koeitecmoamerica.com/dw_origins/us/products/steam_spec.html",
        )
        self.assertNotIn("D3D12.dll", prerequisite.summary + " ".join(prerequisite.evidence))
        self.assertEqual(before, {root: snapshot_tree(root) for root in before})

    def test_unreviewed_profiles_leave_prerequisites_and_compatibility_unchecked(self):
        report = self.diagnose(game_id="pw4")
        self.assertEqual(finding(report, "prerequisites.reviewed_rules").status, "not_checked")
        compatibility = finding(report, "compatibility.reviewed_notes")
        self.assertEqual(compatibility.status, "not_checked")
        self.assertIn("No title-specific", compatibility.summary)

    def test_compatibility_note_is_cited_and_never_claims_current_impact(self):
        report = self.diagnose()
        compatibility = finding(report, "origins.steam.dlc-companion-frame-rate")
        self.assertEqual(compatibility.category, "compatibility")
        self.assertEqual(compatibility.status, "not_checked")
        self.assertTrue(compatibility.source.startswith("https://www.koeitecmoamerica.com/"))
        self.assertIn("does not establish", compatibility.summary)

    def test_unregistered_and_non_windows_profiles_are_rejected_without_echoing_input(self):
        for game_id in ("not-a-game", "dw7xl_ps3"):
            with self.subTest(game_id=game_id):
                with self.assertRaises(troubleshooting.TroubleshootingError):
                    troubleshooting.diagnose_game(game_id, self.install)

    def test_non_pathlike_inputs_are_not_coerced(self):
        for value in (True, 3, object()):
            with self.subTest(value=type(value).__name__):
                report = troubleshooting.diagnose_game("origins", value)
                self.assertEqual(finding(report, "installation.selected_root").status,
                                 "unknown")


class UnsupportedFolderRuntimeTests(unittest.TestCase):
    def test_unsupported_runtime_reads_no_selected_metadata_or_content(self):
        selected = Path("synthetic-selected-folder")
        with patch.object(troubleshooting, "_DIRECTORY_FDS", False), \
                patch.object(Path, "lstat", side_effect=AssertionError("No selected metadata read")), \
                patch.object(troubleshooting.os, "scandir", side_effect=AssertionError("No directory enumeration")), \
                patch.object(troubleshooting.os, "open", side_effect=AssertionError("No selected file open")):
            report = troubleshooting.diagnose_game("origins", selected, selected, selected)
            with self.assertRaises(OSError):
                with troubleshooting._directory(()):
                    self.fail("Unsupported directory access was allowed")
        for identifier in ("installation.selected_root", "configuration.selected_root", "mods.scan"):
            result = finding(report, identifier)
            self.assertEqual(result.status, "unknown")
            self.assertIn("unavailable on this runtime", result.summary)
        self.assertEqual(finding(report, "origins.directx12.system-requirement").status, "not_checked")
        self.assertEqual(finding(report, "origins.steam.dlc-companion-frame-rate").status, "not_checked")


if __name__ == "__main__":
    unittest.main()

"""Read-only patch compatibility comparison for tracker snapshots."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from koei_editor.shared import game_compatibility as compatibility


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_record(path: str, content: bytes | None, size: int | None = None) -> dict:
    return {
        "relative_path": path,
        "size_bytes": len(content) if size is None and content is not None else (size or 0),
        "sha256": digest(content) if content is not None else None,
    }


def snapshot(version_label: str = "1.0", **changes) -> dict:
    result = {
        "schema_id": compatibility.SNAPSHOT_SCHEMA_ID,
        "schema_version": compatibility.SCHEMA_VERSION,
        "game_id": "dw8xl-pc",
        "platform_id": "windows",
        "version": {"value": version_label, "source": "manual", "build_id": "build-a"},
        "files": [],
        "archives": [],
        "formats": [],
    }
    result.update(changes)
    return result


def requirements(rows: list[dict]) -> dict:
    return {
        "schema_id": compatibility.REQUIREMENTS_SCHEMA_ID,
        "schema_version": compatibility.SCHEMA_VERSION,
        "requirements": rows,
    }


def consumer(
    kind: str,
    *,
    files: list[dict] | None = None,
    formats: list[dict] | None = None,
    archive_entries: list[dict] | None = None,
) -> dict:
    return {
        "id": f"{kind}.fixture",
        "name": f"Fixture {kind}",
        "kind": kind,
        "game_id": "dw8xl-pc",
        "platform_id": "windows",
        "required_files": files or [],
        "required_formats": formats or [],
        "required_archive_entries": archive_entries or [],
    }


class GameCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def test_file_version_archive_and_format_changes_are_reported_deterministically(self):
        baseline = snapshot(
            "1.0",
            files=[
                file_record("bin/stable.dll", b"stable"),
                file_record("bin/changed.dll", b"before"),
                file_record("bin/removed.dll", b"removed"),
                file_record("bin/unknown.dat", None, size=11),
            ],
            archives=[{
                "relative_path": "data/game.pack",
                "format_id": "koei.pack.v1",
                "status": "parsed",
                "entries": [
                    {"path": "scripts/main.bin", "size_bytes": 6, "crc32": "aabbccdd", "sha256": digest(b"before")},
                    {"path": "scripts/removed.bin", "size_bytes": 7, "crc32": 1, "sha256": digest(b"removed")},
                ],
            }],
            formats=[{
                "id": "save.dw8xl-pc",
                "revision": "1",
                "evidence_paths": ["bin/save.dll"],
                "confidence": 0.8,
            }],
        )
        candidate = snapshot(
            "1.1",
            files=[
                file_record("bin/stable.dll", b"stable"),
                file_record("bin/changed.dll", b"after!"),
                file_record("bin/added.dll", b"added"),
                file_record("bin/unknown.dat", None, size=11),
            ],
            archives=[{
                "relative_path": "data/game.pack",
                "format_id": "koei.pack.v1",
                "status": "parsed",
                "entries": [
                    {"path": "scripts/main.bin", "size_bytes": 6, "crc32": "11223344", "sha256": digest(b"after!")},
                    {"path": "scripts/added.bin", "size_bytes": 5, "crc32": None, "sha256": digest(b"added")},
                ],
            }],
            formats=[{
                "id": "save.dw8xl-pc",
                "revision": "2",
                "evidence_paths": ["bin/save.dll", "bin/changed.dll"],
                "confidence": 0.9,
            }],
        )
        baseline_before = deepcopy(baseline)
        candidate_before = deepcopy(candidate)

        report = compatibility.analyze_snapshots(baseline, candidate)
        self.assertEqual(report["version_change"]["before"]["value"], "1.0")
        self.assertTrue(report["version_change"]["changed"])
        self.assertEqual([item["relative_path"] for item in report["file_changes"]["added"]], ["bin/added.dll"])
        self.assertEqual([item["relative_path"] for item in report["file_changes"]["removed"]], ["bin/removed.dll"])
        modified = {item["relative_path"]: item for item in report["file_changes"]["modified"]}
        self.assertIn("bin/changed.dll", modified)
        self.assertIn("sha256", modified["bin/changed.dll"]["changed_fields"])
        self.assertEqual(report["file_changes"]["unchanged_count"], 1)
        self.assertEqual(report["file_changes"]["unverified"], [{
            "relative_path": "bin/unknown.dat",
            "reason": "sha256_missing_on_both_sides",
        }])

        archive = report["archive_changes"]["changed"][0]
        self.assertEqual(archive["relative_path"], "data/game.pack")
        self.assertEqual([item["path"] for item in archive["entries"]["added"]], ["scripts/added.bin"])
        self.assertEqual([item["path"] for item in archive["entries"]["removed"]], ["scripts/removed.bin"])
        self.assertEqual([item["path"] for item in archive["entries"]["modified"]], ["scripts/main.bin"])
        self.assertEqual(report["format_changes"]["changed"][0]["id"], "save.dw8xl-pc")
        self.assertIn("revision", report["format_changes"]["changed"][0]["changed_fields"])
        self.assertEqual(report, compatibility.analyze_snapshots(baseline, candidate))
        self.assertEqual(baseline, baseline_before)
        self.assertEqual(candidate, candidate_before)

    def test_size_delta_is_reported_even_when_hash_is_missing(self):
        before = snapshot(files=[file_record("data/unknown.bin", None, size=3)])
        after = snapshot(files=[file_record("data/unknown.bin", None, size=4)])
        report = compatibility.analyze_snapshots(before, after)
        row = report["file_changes"]["modified"][0]
        self.assertEqual(row["changed_fields"], ["size_bytes"])
        self.assertEqual(row["verification"], "size_or_partial_hash")
        self.assertEqual(report["file_changes"]["unverified"][0]["relative_path"], "data/unknown.bin")

    def test_archive_unknown_states_remain_unknown_and_are_not_treated_as_parsed(self):
        before = snapshot(archives=[
            {"relative_path": "data/unsupported.bin", "format_id": None, "status": "unsupported", "entries": []},
            {"relative_path": "data/malformed.bin", "format_id": "koei.unknown", "status": "malformed", "entries": []},
        ])
        after = snapshot(archives=[
            {"relative_path": "data/unsupported.bin", "format_id": None, "status": "unsupported", "entries": []},
            {"relative_path": "data/malformed.bin", "format_id": "koei.unknown", "status": "malformed", "entries": []},
        ])
        report = compatibility.analyze_snapshots(before, after)
        unknown = {item["relative_path"]: item["reason"] for item in report["archive_changes"]["unknown"]}
        self.assertEqual(unknown["data/unsupported.bin"], "archive_format_unsupported")
        self.assertEqual(unknown["data/malformed.bin"], "archive_structure_unavailable")
        self.assertEqual(report["archive_changes"]["changed"], [])

    def test_archive_state_change_preserves_known_side_inventory(self):
        before = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [{"path": "scripts/main.bin", "size_bytes": 12, "sha256": digest(b"member")}],
        }])
        after = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "unsupported",
            "entries": [],
        }])

        report = compatibility.analyze_snapshots(before, after)
        archive = report["archive_changes"]["changed"][0]
        self.assertEqual(archive["analysis_status"], "unknown")
        self.assertEqual(archive["entries"]["added"], [])
        self.assertEqual(archive["entries"]["removed"], [])
        self.assertEqual(
            [entry["path"] for entry in archive["entries"]["observed_before"]],
            ["scripts/main.bin"],
        )
        self.assertEqual(archive["entries"]["observed_after"], [])

    def test_declared_requirements_show_possible_impact_without_hash_only_claims(self):
        old_file, new_file = digest(b"old executable"), digest(b"new executable")
        old_entry, new_entry = digest(b"old archive member"), digest(b"new archive member")
        before = snapshot(
            "1.0",
            files=[file_record("bin/game.exe", b"old executable")],
            archives=[{
                "relative_path": "data/game.pack",
                "format_id": "koei.pack.v1",
                "status": "parsed",
                "entries": [{"path": "scripts/main.bin", "size_bytes": 18, "sha256": old_entry}],
            }],
            formats=[{"id": "save.dw8xl-pc", "revision": "1", "evidence_paths": ["bin/game.exe"]}],
        )
        after = snapshot(
            "1.1",
            files=[file_record("bin/game.exe", b"new executable")],
            archives=[{
                "relative_path": "data/game.pack",
                "format_id": "koei.pack.v1",
                "status": "parsed",
                "entries": [{"path": "scripts/main.bin", "size_bytes": 18, "sha256": new_entry}],
            }],
            formats=[{"id": "save.dw8xl-pc", "revision": "2", "evidence_paths": ["bin/game.exe"]}],
        )
        hash_only = compatibility.analyze_snapshots(before, after)
        self.assertEqual(hash_only["impacts"]["status"], "unknown")
        self.assertNotIn("incompatible", str(hash_only).lower())

        declared = requirements([
            consumer("mods", files=[{"relative_path": "bin/game.exe", "sha256": old_file}]),
            consumer("tools", formats=[{"id": "save.dw8xl-pc", "revision": "1"}]),
            consumer("saves", archive_entries=[{
                "relative_path": "data/game.pack",
                "format_id": "koei.pack.v1",
                "path": "scripts/main.bin",
                "sha256": old_entry,
            }]),
        ])
        report = compatibility.analyze_snapshots(before, after, declared)
        self.assertEqual(report["impacts"]["status"], "may_affect")
        by_kind = report["impacts"]["by_kind"]
        self.assertEqual({kind for kind, row in by_kind.items() if row["status"] == "may_affect"}, {"mods", "tools", "saves"})
        self.assertTrue(all(row["status"] == "may_affect" for row in report["impacts"]["consumers"]))
        self.assertIn("do not prove", report["impacts"]["interpretation"])

    def test_missing_or_unknown_requirement_evidence_is_not_called_compatible(self):
        before = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [{"path": "scripts/main.bin", "size_bytes": 1, "sha256": None}],
        }])
        after = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "unsupported",
            "entries": [],
        }])
        declared = requirements([consumer("mods", archive_entries=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "path": "scripts/main.bin",
            "sha256": digest(b"expected"),
        }])])
        report = compatibility.analyze_snapshots(before, after, declared)
        row = report["impacts"]["consumers"][0]
        self.assertEqual(row["status"], "unknown")
        self.assertEqual(row["candidate"]["status"], "unknown")
        self.assertEqual(row["candidate"]["reasons"][0]["type"], "required_archive_structure_unknown")

    def test_schema_identity_path_hash_and_duplicate_validation(self):
        valid = snapshot(files=[file_record("bin/game.exe", b"game")])
        mutations = []
        bad_schema = deepcopy(valid)
        bad_schema["schema_id"] = "other"
        mutations.append(bad_schema)
        bad_hash = deepcopy(valid)
        bad_hash["files"][0]["sha256"] = "abc"
        mutations.append(bad_hash)
        for bad_path in ("../escape.bin", "/root/game.exe", "C:/game.exe", "bin\\game.exe", "bin//game.exe"):
            bad = deepcopy(valid)
            bad["files"][0]["relative_path"] = bad_path
            mutations.append(bad)
        duplicate = deepcopy(valid)
        duplicate["files"].append(deepcopy(duplicate["files"][0]))
        mutations.append(duplicate)
        for invalid in mutations:
            with self.subTest(invalid=invalid):
                with self.assertRaises(compatibility.CompatibilityInputError):
                    compatibility.analyze_snapshots(invalid, valid)

        wrong_game = snapshot("1.0", game_id="another-game")
        wrong_platform = snapshot("1.0", platform_id="steam-deck")
        with self.assertRaisesRegex(ValueError, "same game_id"):
            compatibility.analyze_snapshots(valid, wrong_game)
        with self.assertRaisesRegex(ValueError, "same platform_id"):
            compatibility.analyze_snapshots(valid, wrong_platform)

    def test_requirements_schema_duplicate_ids_and_invalid_kinds_are_rejected(self):
        before = snapshot()
        after = snapshot("1.1")
        for rows in (
            [consumer("mods"), consumer("mods")],
            [{**consumer("tools"), "kind": "installer"}],
            [{**consumer("saves"), "required_files": [{"relative_path": "save.bin", "sha256": None}]}],
        ):
            with self.subTest(rows=rows), self.assertRaises(compatibility.CompatibilityInputError):
                compatibility.analyze_snapshots(before, after, requirements(rows))

    def test_json_loader_rejects_duplicate_keys_and_reports_are_path_free_and_stable(self):
        input_path = self.folder / "baseline.json"
        input_path.write_text('{"schema_id":"first","schema_id":"second"}', encoding="utf-8")
        with self.assertRaises(compatibility.CompatibilityInputError):
            compatibility.load_json(input_path)

        before = snapshot("1.0", files=[file_record("bin/game.exe", b"before")])
        after = snapshot("1.1", files=[file_record("bin/game.exe", b"after!")])
        report = compatibility.analyze_snapshots(before, after)
        rendered = compatibility.render_markdown(report)
        self.assertEqual(rendered, compatibility.render_markdown(report))
        self.assertIn("changed file hash", rendered.lower())
        self.assertNotIn(str(self.folder), rendered)
        self.assertNotIn("before!", rendered)
        self.assertEqual(json.dumps(report, sort_keys=True), json.dumps(compatibility.analyze_snapshots(before, after), sort_keys=True))

    def test_cli_emits_repeatable_reports_without_modifying_inputs_or_overwriting_sources(self):
        before = snapshot("1.0", files=[file_record("bin/game.exe", b"before")])
        after = snapshot("1.1", files=[file_record("bin/game.exe", b"after!")])
        before_path = self.folder / "before.json"
        after_path = self.folder / "after.json"
        before_bytes = json.dumps(before, sort_keys=True).encode("utf-8")
        after_bytes = json.dumps(after, sort_keys=True).encode("utf-8")
        before_path.write_bytes(before_bytes)
        after_path.write_bytes(after_bytes)
        json_out = self.folder / "report.json"
        markdown_out = self.folder / "report.md"
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(root / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

        command = [
            sys.executable, "-m", "koei_editor.shared.game_compatibility",
            str(before_path), str(after_path), "--json-out", str(json_out), "--markdown-out", str(markdown_out),
        ]
        first = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(first.returncode, 0, first.stderr)
        second_json = self.folder / "report-again.json"
        second_markdown = self.folder / "report-again.md"
        second_command = [
            sys.executable, "-m", "koei_editor.shared.game_compatibility",
            str(before_path), str(after_path), "--json-out", str(second_json), "--markdown-out", str(second_markdown),
        ]
        second = subprocess.run(second_command, cwd=root, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json_out.read_bytes(), second_json.read_bytes())
        self.assertEqual(markdown_out.read_bytes(), second_markdown.read_bytes())
        self.assertEqual(json.loads(json_out.read_text(encoding="utf-8")), compatibility.analyze_snapshots(before, after))
        self.assertEqual(before_path.read_bytes(), before_bytes)
        self.assertEqual(after_path.read_bytes(), after_bytes)

        bad_output = subprocess.run(
            [sys.executable, "-m", "koei_editor.shared.game_compatibility", str(before_path), str(after_path), "--json-out", str(before_path)],
            cwd=root, env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(bad_output.returncode, 2)
        self.assertEqual(before_path.read_bytes(), before_bytes)

    def test_parsed_archive_members_without_checksums_are_unverified_not_unchanged(self):
        archive = {
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [{
                "path": "scripts/main.bin",
                "size_bytes": 100,
                "crc32": None,
                "sha256": None,
            }],
        }
        before = snapshot(archives=[deepcopy(archive)])
        after = snapshot(archives=[deepcopy(archive)])

        report = compatibility.analyze_snapshots(before, after)
        self.assertEqual(report["archive_changes"]["changed"], [])
        self.assertEqual(report["archive_changes"]["unchanged_count"], 0)
        changed_archive = report["archive_changes"]["unknown"]
        self.assertIn(
            {"relative_path": "data/game.pack", "reason": "member_checksum_missing"},
            changed_archive,
        )
        self.assertEqual(report["evidence_status"], "unknown")
        self.assertEqual(report["overall_status"], "unknown")

    def test_unknown_archive_format_requirement_is_unknown_not_a_mismatch(self):
        before = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [{
                "path": "scripts/main.bin",
                "size_bytes": 8,
                "sha256": digest(b"member"),
            }],
        }])
        after = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": None,
            "status": "parsed",
            "entries": [{
                "path": "scripts/main.bin",
                "size_bytes": 8,
                "sha256": digest(b"member"),
            }],
        }])
        declared = requirements([consumer("mods", archive_entries=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "path": "scripts/main.bin",
            "sha256": digest(b"member"),
        }])])

        report = compatibility.analyze_snapshots(before, after, declared)
        row = report["impacts"]["consumers"][0]
        self.assertEqual(row["baseline"]["status"], "satisfied")
        self.assertEqual(row["candidate"]["status"], "unknown")
        self.assertEqual(row["status"], "unknown")
        self.assertIn(
            "required_archive_format_unknown",
            {reason["type"] for reason in row["candidate"]["reasons"]},
        )
        self.assertEqual(report["overall_status"], "unknown")

    def test_archive_compressed_size_delta_is_reported(self):
        entry = {
            "path": "scripts/main.bin",
            "size_bytes": 20,
            "compressed_size_bytes": 10,
            "crc32": "abcd1234",
            "sha256": digest(b"same member"),
        }
        before = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [entry],
        }])
        after_entry = {**entry, "compressed_size_bytes": 11}
        after = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [after_entry],
        }])

        report = compatibility.analyze_snapshots(before, after)
        changed = report["archive_changes"]["changed"][0]
        member = changed["entries"]["modified"][0]
        self.assertEqual(member["path"], "scripts/main.bin")
        self.assertEqual(member["changed_fields"], ["compressed_size_bytes"])
        self.assertEqual(member["before"]["compressed_size_bytes"], 10)
        self.assertEqual(member["after"]["compressed_size_bytes"], 11)

    def test_added_and_removed_archive_reports_include_member_inventories(self):
        before = snapshot(archives=[{
            "relative_path": "data/removed.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [{"path": "old/member.bin", "size_bytes": 3, "sha256": digest(b"old")}],
        }])
        after = snapshot(archives=[{
            "relative_path": "data/added.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [{"path": "new/member.bin", "size_bytes": 3, "sha256": digest(b"new")}],
        }])

        report = compatibility.analyze_snapshots(before, after)
        added = report["archive_changes"]["added"][0]
        removed = report["archive_changes"]["removed"][0]
        self.assertEqual(added["relative_path"], "data/added.pack")
        self.assertEqual([entry["path"] for entry in added["entries"]["added"]], ["new/member.bin"])
        self.assertEqual(removed["relative_path"], "data/removed.pack")
        self.assertEqual([entry["path"] for entry in removed["entries"]["removed"]], ["old/member.bin"])
        markdown = compatibility.render_markdown(report)
        self.assertIn("new/member.bin", markdown)
        self.assertIn("old/member.bin", markdown)

    def test_timezone_aware_capture_times_are_normalized_into_repeatable_provenance(self):
        before = snapshot("1.0", captured_at="2026-10-20T12:00:00+02:00")
        after = snapshot("1.0", captured_at="2026-10-21T09:30:00Z")

        report = compatibility.analyze_snapshots(before, after)
        self.assertEqual(report["provenance"], {
            "baseline_captured_at": "2026-10-20T10:00:00Z",
            "candidate_captured_at": "2026-10-21T09:30:00Z",
        })
        self.assertEqual(report, compatibility.analyze_snapshots(before, after))
        markdown = compatibility.render_markdown(report)
        self.assertIn("2026-10-20T10:00:00Z", markdown)
        self.assertIn("2026-10-21T09:30:00Z", markdown)
        invalid = snapshot(captured_at="2026-10-20T12:00:00")
        with self.assertRaises(compatibility.CompatibilityInputError):
            compatibility.analyze_snapshots(invalid, after)

    def test_version_and_build_allowlists_can_report_version_only_impact(self):
        before = snapshot("1.0")
        after = snapshot("1.1", version={"value": "1.1", "source": "manifest", "build_id": "build-b"})
        declared = requirements([{
            **consumer("tools"),
            "supported_versions": ["1.0"],
            "supported_build_ids": ["build-a"],
        }])

        report = compatibility.analyze_snapshots(before, after, declared)
        self.assertTrue(report["version_change"]["changed"])
        self.assertTrue(report["has_changes"])
        row = report["impacts"]["consumers"][0]
        self.assertEqual(row["baseline"]["status"], "satisfied")
        self.assertEqual(row["candidate"]["status"], "not_satisfied")
        self.assertEqual(row["status"], "may_affect")
        self.assertEqual(
            {reason["type"] for reason in row["candidate"]["reasons"]},
            {"supported_version_not_listed", "supported_build_id_not_listed"},
        )
        self.assertEqual(report["overall_status"], "may_affect")

    def test_control_characters_are_rejected_but_slash_names_render_escaped(self):
        bad_version = snapshot("1.0\n## injected")
        with self.assertRaises(compatibility.CompatibilityInputError):
            compatibility.analyze_snapshots(bad_version, snapshot())

        bad_name = requirements([{
            **consumer("mods"),
            "name": "weapon fix\n## injected heading",
        }])
        with self.assertRaises(compatibility.CompatibilityInputError):
            compatibility.analyze_snapshots(snapshot(), snapshot(), bad_name)

        safe_name = "mods/weapon-fix | <trusted>"
        safe_requirements = requirements([{
            **consumer("mods"),
            "name": safe_name,
        }])
        report = compatibility.analyze_snapshots(snapshot(), snapshot(), safe_requirements)
        self.assertEqual(report["impacts"]["consumers"][0]["name"], safe_name)
        markdown = compatibility.render_markdown(report)
        self.assertIn("mods/weapon-fix", markdown)
        self.assertIn("&lt;trusted&gt;", markdown)
        self.assertNotIn("\n## injected heading", markdown)

    def test_added_and_removed_files_without_hashes_are_unverified(self):
        before = snapshot(files=[file_record("bin/removed.bin", None, size=5)])
        after = snapshot(files=[file_record("bin/added.bin", None, size=7)])

        report = compatibility.analyze_snapshots(before, after)
        unverified = {item["relative_path"] for item in report["file_changes"]["unverified"]}
        self.assertEqual(unverified, {"bin/added.bin", "bin/removed.bin"})
        self.assertEqual(report["evidence_status"], "unknown")

    def test_matching_file_sha_with_different_sizes_is_flagged_as_inconsistent(self):
        before = snapshot(files=[file_record("bin/game.exe", b"same bytes", size=10)])
        after = snapshot(files=[file_record("bin/game.exe", b"same bytes", size=11)])

        report = compatibility.analyze_snapshots(before, after)
        row = report["file_changes"]["modified"][0]
        self.assertEqual(row["changed_fields"], ["size_bytes"])
        self.assertEqual(row["verification"], "inconsistent_metadata")
        self.assertIn(
            {"relative_path": "bin/game.exe", "reason": "sha256_size_conflict"},
            report["file_changes"]["unverified"],
        )
        self.assertEqual(report["file_changes"]["unchanged_count"], 0)
        self.assertEqual(report["evidence_status"], "unknown")
        self.assertEqual(report["overall_status"], "unknown")

    def test_matching_archive_member_sha_with_different_sizes_lowers_evidence_status(self):
        member = {
            "path": "scripts/main.bin",
            "size_bytes": 10,
            "sha256": digest(b"same member bytes"),
        }
        before = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [member],
        }])
        after = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [{**member, "size_bytes": 11}],
        }])

        report = compatibility.analyze_snapshots(before, after)
        archive = report["archive_changes"]["changed"][0]
        row = archive["entries"]["modified"][0]
        self.assertEqual(row["changed_fields"], ["size_bytes"])
        self.assertIn(
            {"path": "scripts/main.bin", "reason": "sha256_size_conflict"},
            archive["entries"]["unverified"],
        )
        self.assertEqual(archive["analysis_status"], "unknown")
        self.assertIn(
            {"relative_path": "data/game.pack", "reason": "member_size_hash_conflict"},
            report["archive_changes"]["unknown"],
        )
        self.assertEqual(report["evidence_status"], "unknown")
        self.assertEqual(report["overall_status"], "unknown")

    def test_kind_summary_remains_unsatisfied_when_requirements_are_mixed(self):
        baseline = snapshot(files=[file_record("bin/known.dll", b"known")])
        candidate_snapshot = deepcopy(baseline)
        known = {
            **consumer("mods", files=[{"relative_path": "bin/known.dll", "sha256": digest(b"known")}]),
            "id": "mods.known",
        }
        persistently_missing = {
            **consumer("mods", files=[{"relative_path": "bin/missing.dll", "sha256": digest(b"missing")}]),
            "id": "mods.missing",
        }

        report = compatibility.analyze_snapshots(
            baseline,
            candidate_snapshot,
            requirements([known, persistently_missing]),
        )
        mod_summary = report["impacts"]["by_kind"]["mods"]
        self.assertEqual(mod_summary["counts"]["requirements_satisfied"], 1)
        self.assertEqual(mod_summary["counts"]["already_not_satisfied"], 1)
        self.assertEqual(mod_summary["status"], "already_not_satisfied")
        self.assertEqual(report["overall_status"], "requirements_not_satisfied_before_and_after")

    def test_oversized_integer_and_deep_json_are_wrapped_for_loader_and_cli(self):
        baseline = snapshot("1.0")
        candidate_snapshot = snapshot("1.1")
        before_path = self.folder / "before.json"
        after_path = self.folder / "after.json"
        before_path.write_text(json.dumps(baseline), encoding="utf-8")
        after_path.write_text(json.dumps(candidate_snapshot), encoding="utf-8")
        invalid_inputs = {
            "oversized-integer.json": "9" * 5000,
            "deep.json": "[" * 10000 + "0" + "]" * 10000,
        }
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        previous_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(root / "src") + (os.pathsep + previous_pythonpath if previous_pythonpath else "")

        for name, text in invalid_inputs.items():
            with self.subTest(name=name):
                invalid_path = self.folder / name
                invalid_path.write_text(text, encoding="utf-8")
                with self.assertRaises(compatibility.CompatibilityInputError):
                    compatibility.load_json(invalid_path)
                output_path = self.folder / f"{name}.report.json"
                process = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "koei_editor.shared.game_compatibility",
                        str(before_path),
                        str(after_path),
                        "--requirements",
                        str(invalid_path),
                        "--json-out",
                        str(output_path),
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assertFalse(output_path.exists())

    def test_json_nesting_scanner_ignores_brackets_inside_strings(self):
        value = "[" * (compatibility._MAX_JSON_NESTING + 1) + "]" * (compatibility._MAX_JSON_NESTING + 1)
        input_path = self.folder / "brackets-in-string.json"
        input_path.write_text(json.dumps({"value": value}), encoding="utf-8")

        self.assertEqual(compatibility.load_json(input_path), {"value": value})

    def test_invalid_utf8_json_is_wrapped_for_loader_and_cli(self):
        baseline = snapshot("1.0")
        candidate_snapshot = snapshot("1.1")
        before_path = self.folder / "before-utf8.json"
        after_path = self.folder / "after-utf8.json"
        requirements_path = self.folder / "invalid-utf8.json"
        before_path.write_text(json.dumps(baseline), encoding="utf-8")
        after_path.write_text(json.dumps(candidate_snapshot), encoding="utf-8")
        requirements_path.write_bytes(b'{"requirements": [\xff]}')

        with self.assertRaises(compatibility.CompatibilityInputError):
            compatibility.load_json(requirements_path)

        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        previous_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(root / "src") + (os.pathsep + previous_pythonpath if previous_pythonpath else "")
        output_path = self.folder / "invalid-utf8.report.json"
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "koei_editor.shared.game_compatibility",
                str(before_path),
                str(after_path),
                "--requirements",
                str(requirements_path),
                "--json-out",
                str(output_path),
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertFalse(output_path.exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Named pipes are unavailable on this platform")
    def test_non_regular_json_input_is_rejected_without_blocking(self):
        fifo_path = self.folder / "snapshot.fifo"
        after_path = self.folder / "after-fifo.json"
        after_path.write_text(json.dumps(snapshot("1.1")), encoding="utf-8")
        os.mkfifo(fifo_path)

        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        previous_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(root / "src") + (os.pathsep + previous_pythonpath if previous_pythonpath else "")
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "koei_editor.shared.game_compatibility",
                str(fifo_path),
                str(after_path),
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertIn("regular file", process.stderr)

    def test_directory_is_rejected_as_non_regular_json_input(self):
        with self.assertRaisesRegex(compatibility.CompatibilityInputError, "regular file"):
            compatibility.load_json(self.folder)

    def test_unpaired_surrogate_is_rejected_before_cli_output_is_written(self):
        bad_snapshot = snapshot(version_label="1.0\ud800")
        with self.assertRaises(compatibility.CompatibilityInputError):
            compatibility.analyze_snapshots(bad_snapshot, snapshot())

        before_path = self.folder / "before-surrogate.json"
        after_path = self.folder / "after-surrogate.json"
        before_path.write_text(json.dumps(bad_snapshot, ensure_ascii=True), encoding="utf-8")
        after_path.write_text(json.dumps(snapshot(), ensure_ascii=True), encoding="utf-8")
        before_bytes = before_path.read_bytes()
        output_path = self.folder / "surrogate-report.json"
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        previous_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(root / "src") + (os.pathsep + previous_pythonpath if previous_pythonpath else "")

        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "koei_editor.shared.game_compatibility",
                str(before_path),
                str(after_path),
                "--json-out",
                str(output_path),
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertFalse(output_path.exists())
        self.assertEqual(before_path.read_bytes(), before_bytes)

    def test_unknown_version_and_asymmetric_build_are_uncertain_not_confirmed_changes(self):
        baseline = snapshot("1.0")
        unknown_version = snapshot(
            "unknown",
            version={"value": "unknown", "source": "unavailable", "build_id": "build-a"},
        )
        unknown_report = compatibility.analyze_snapshots(baseline, unknown_version)
        self.assertIsNone(unknown_report["version_change"]["changed"])
        self.assertEqual(unknown_report["version_change"]["status"], "unknown")
        self.assertIn(
            "version_value_unknown",
            {reason["type"] for reason in unknown_report["version_change"]["evidence_reasons"]},
        )
        self.assertEqual(unknown_report["evidence_status"], "unknown")

        asymmetric_build = snapshot(
            "1.0",
            version={"value": "1.0", "source": "manual"},
        )
        asymmetric_report = compatibility.analyze_snapshots(baseline, asymmetric_build)
        self.assertIsNone(asymmetric_report["version_change"]["changed"])
        self.assertEqual(asymmetric_report["version_change"]["status"], "unknown")
        self.assertIn(
            "build_id_asymmetric",
            {reason["type"] for reason in asymmetric_report["version_change"]["evidence_reasons"]},
        )
        self.assertEqual(asymmetric_report["evidence_status"], "unknown")

        unknown_build = snapshot(
            "1.0",
            version={"value": "1.0", "source": "manual", "build_id": "unavailable"},
        )
        build_report = compatibility.analyze_snapshots(unknown_build, snapshot("1.0"))
        self.assertIsNone(build_report["version_change"]["changed"])
        self.assertEqual(build_report["version_change"]["status"], "unknown")
        self.assertIn(
            "build_id_unknown",
            {reason["type"] for reason in build_report["version_change"]["evidence_reasons"]},
        )

    def test_hard_link_output_alias_is_rejected_without_mutating_input(self):
        before = snapshot("1.0", files=[file_record("bin/game.exe", b"before")])
        after = snapshot("1.1", files=[file_record("bin/game.exe", b"after!")])
        before_path = self.folder / "before-hardlink.json"
        after_path = self.folder / "after-hardlink.json"
        before_path.write_text(json.dumps(before, sort_keys=True), encoding="utf-8")
        after_path.write_text(json.dumps(after, sort_keys=True), encoding="utf-8")
        original = before_path.read_bytes()
        hard_link = self.folder / "before-hardlink-alias.json"
        try:
            os.link(before_path, hard_link)
        except OSError as error:
            self.skipTest(f"The test filesystem does not support hard links: {error}")
        self.assertTrue(before_path.samefile(hard_link))

        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        previous_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(root / "src") + (os.pathsep + previous_pythonpath if previous_pythonpath else "")
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "koei_editor.shared.game_compatibility",
                str(before_path),
                str(after_path),
                "--json-out",
                str(hard_link),
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertEqual(before_path.read_bytes(), original)
        self.assertEqual(hard_link.read_bytes(), original)

    def test_matching_archive_member_sha_with_different_crc_lowers_evidence(self):
        member = {
            "path": "scripts/main.bin",
            "size_bytes": 12,
            "crc32": "11111111",
            "sha256": digest(b"same archive member"),
        }
        before = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [member],
        }])
        after = snapshot(archives=[{
            "relative_path": "data/game.pack",
            "format_id": "koei.pack.v1",
            "status": "parsed",
            "entries": [{**member, "crc32": "22222222"}],
        }])

        report = compatibility.analyze_snapshots(before, after)
        archive = report["archive_changes"]["changed"][0]
        self.assertIn(
            {"path": "scripts/main.bin", "reason": "sha256_crc_conflict"},
            archive["entries"]["unverified"],
        )
        self.assertEqual(archive["analysis_status"], "unknown")
        self.assertIn(
            {"relative_path": "data/game.pack", "reason": "member_checksum_conflict"},
            report["archive_changes"]["unknown"],
        )
        self.assertEqual(report["evidence_status"], "unknown")
        self.assertEqual(report["overall_status"], "unknown")


if __name__ == "__main__":
    unittest.main()

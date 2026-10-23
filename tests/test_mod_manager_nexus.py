"""Mocked integration checks for the in-memory Nexus-to-manager handoff."""

from dataclasses import dataclass, replace
import ctypes
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import zipfile
from unittest.mock import patch

from koei_editor.shared.mod_manager import ModManager, _NexusDownloadJob


@dataclass(frozen=True)
class Request:
    provider: str = "nexus"
    game_id: str = "nioh2_pc"
    game_domain: str = "nioh2"
    game_scoped_mod_id: str = "1234"
    mod_id: str = "1234"
    file_id: str = "98765"
    file_name: str = "sample-mod.zip"
    file_version_id: str = "34567"
    game_scoped_file_version_id: str = "45678"
    mod_page_url: str = "https://www.nexusmods.com/nioh2/mods/1234"


def write_valid_zip(path, *, mod_id="downloaded-mod"):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("NiohMod/mod.ini", "[Mod]\nName=Downloaded\n")
        archive.writestr("NiohMod/assets/model.fmt", b"synthetic asset")
        archive.writestr(
            "koei-mod.json",
            '{"schema_version":1,"game_id":"nioh2_pc","id":"'
            + mod_id
            + '","name":"Downloaded Mod","version":"1.0",'
            '"dependencies":[],"conflicts":[]}',
        )


class FakeDownloader:
    def __init__(self, writer=None, error=None):
        self.writer = writer or write_valid_zip
        self.error = error
        self.destination = None
        self.called = threading.Event()
        self.release = None

    def download_archive(self, request, destination):
        self.called.set()
        self.destination = Path(destination)
        if self.release is not None:
            self.release.wait(3)
        if self.error is not None:
            raise self.error
        self.writer(self.destination)


class RateLimitError(RuntimeError):
    status = 429

    def __init__(self, message, retry_after):
        super().__init__(message)
        self.retry_after = retry_after


class NexusManagerHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state_dir = Path(self.temporary.name) / "manager-state"
        self.manager = ModManager(self.state_dir)

    def wait_for_result(self, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            results = self.manager.poll_nexus_download_results()
            if results:
                return results[0]
            time.sleep(0.01)
        self.fail("Nexus manager job did not report a result in time")

    def test_nexus_zip_download_is_queued_imported_and_never_installed(self):
        downloader = FakeDownloader()
        started = time.monotonic()

        self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
        self.assertLess(time.monotonic() - started, 1.25)
        self.assertTrue(self.manager.nexus_downloads_pending)
        self.assertTrue(downloader.called.wait(2))

        result = self.wait_for_result()

        self.assertEqual(result.status, "imported")
        self.assertEqual(result.mod_id, "downloaded-mod")
        self.assertIn("Review it before enabling or installing", result.message)
        self.assertEqual(downloader.destination.parent.parent, self.manager.state_dir)
        self.assertTrue(downloader.destination.name.startswith("sample-mod-"))
        self.assertEqual(downloader.destination.suffix, ".zip")
        self.assertTrue(downloader.destination.exists(), "untrusted staging bytes must be retained")
        record = next(item for item in self.manager.mods() if item.id == "downloaded-mod")
        self.assertFalse(record.installed)
        self.assertFalse(record.enabled)

    @unittest.skipUnless(os.name == "nt", "Windows 8.3 aliases require a native Windows filesystem.")
    def test_windows_short_state_alias_stages_under_canonical_manager_root(self):
        state = Path(self.temporary.name) / "manager state with long folder name"
        state.mkdir()
        get_short_path = ctypes.windll.kernel32.GetShortPathNameW
        get_short_path.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
        get_short_path.restype = ctypes.c_uint
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_short_path(str(state.resolve(strict=True)), buffer, len(buffer))
        if not length or length >= len(buffer):
            self.skipTest("The native temporary filesystem has no available 8.3 alias.")
        alias = Path(buffer.value)
        if os.path.normcase(os.path.abspath(alias)) == os.path.normcase(str(state.resolve(strict=True))):
            self.skipTest("The native temporary filesystem has no distinct 8.3 alias.")
        self.assertTrue(alias.samefile(state))
        self.manager = ModManager(alias)
        downloader = FakeDownloader()
        self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
        result = self.wait_for_result()
        self.assertEqual(result.status, "imported")
        self.assertEqual(self.manager.state_dir, state.resolve(strict=True))
        self.assertEqual(downloader.destination.parent.parent, self.manager.state_dir)
        self.assertTrue(downloader.destination.is_relative_to(self.manager.state_dir))
        self.assertTrue(downloader.destination.exists(), "untrusted staging bytes must be retained")
        record = next(item for item in self.manager.mods() if item.id == "downloaded-mod")
        self.assertFalse(record.installed)
        self.assertFalse(record.enabled)

    def test_request_provider_game_domain_and_unsafe_names_are_gated_before_queueing(self):
        downloader = FakeDownloader()
        unsupported = (
            replace(Request(), provider="other"),
            replace(Request(), game_id="dw8xl"),
            replace(Request(), game_domain="wolongfallendynasty"),
            replace(Request(), file_name="folder/sample-mod.zip"),
            replace(Request(), mod_page_url="https://www.nexusmods.com/nioh2/mods/1234?key=secret"),
            replace(Request(), game_scoped_mod_id="../1234",
                    mod_page_url="https://www.nexusmods.com/nioh2/mods/../1234"),
            replace(Request(), mod_id="1234/../evil"),
            replace(Request(), file_id="../98765"),
            replace(Request(), file_version_id="version\\with-separator"),
            replace(Request(), game_scoped_file_version_id="../45678"),
        )
        for request in unsupported:
            with self.subTest(request=request):
                self.assertFalse(self.manager.enqueue_nexus_download(request, downloader))
        self.assertFalse(downloader.called.is_set())
        self.assertEqual(self.manager.mods(), ())

    def test_logical_filename_does_not_control_archive_format(self):
        request = replace(Request(), file_name="Nioh 2 appearance mod")
        downloader = FakeDownloader()

        self.assertTrue(self.manager.enqueue_nexus_download(request, downloader))
        result = self.wait_for_result()

        self.assertEqual(result.status, "imported")

    def test_downloader_error_is_sanitized_and_not_saved_to_manager_state(self):
        secret = "https://cdn.example.invalid/archive.zip?token=private-key"
        downloader = FakeDownloader(error=RuntimeError(secret))

        self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
        result = self.wait_for_result()

        self.assertEqual(result.status, "download_failed")
        self.assertNotIn(secret, repr(result))
        self.assertFalse(list(self.manager.state_dir.glob(".nexus-*")))
        for path in self.manager.state_dir.glob("**/*"):
            if path.is_file():
                self.assertNotIn(secret.encode(), path.read_bytes())

    def test_failed_download_retains_partial_output_without_importing(self):
        class PartialDownloader:
            def download_archive(inner, request, destination):
                inner.destination = Path(destination)
                inner.destination.write_bytes(b"incomplete download")
                raise RuntimeError("private signed URL")

        downloader = PartialDownloader()
        self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
        result = self.wait_for_result()
        self.assertEqual(result.status, "download_failed")
        self.assertEqual(downloader.destination.read_bytes(), b"incomplete download")
        self.assertEqual(self.manager.mods(), ())
        self.assertNotIn("private signed URL", repr(result))

    def test_failed_download_retains_foreign_replacement_and_extra_files(self):
        class ReplacedDownloader:
            def download_archive(inner, request, destination):
                inner.destination = Path(destination)
                inner.destination.write_bytes(b"partial")
                inner.destination.unlink()
                inner.destination.write_bytes(b"foreign replacement")
                inner.extra = inner.destination.parent / "foreign-notes.txt"
                inner.extra.write_bytes(b"foreign notes")
                raise RuntimeError("failed")

        downloader = ReplacedDownloader()
        self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
        self.assertEqual(self.wait_for_result().status, "download_failed")
        self.assertEqual(downloader.destination.read_bytes(), b"foreign replacement")
        self.assertEqual(downloader.extra.read_bytes(), b"foreign notes")
        self.assertEqual(self.manager.mods(), ())

    def test_successful_import_retains_replacement_created_during_import(self):
        downloader = FakeDownloader()
        real_import = self.manager.import_archive

        def import_then_replace(destination):
            record = real_import(destination)
            Path(destination).unlink()
            Path(destination).write_bytes(b"foreign replacement after import")
            return record

        with patch.object(self.manager, "import_archive", side_effect=import_then_replace):
            self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
            result = self.wait_for_result()
        self.assertEqual(result.status, "imported")
        self.assertEqual(downloader.destination.read_bytes(), b"foreign replacement after import")
        self.assertEqual(len(self.manager.mods()), 1)

    def test_rate_limit_result_preserves_safe_retry_after_without_retrying(self):
        secret = "https://cdn.example.invalid/archive.zip?token=private-key"
        downloader = FakeDownloader(error=RateLimitError(secret, "23"))

        self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
        result = self.wait_for_result()

        self.assertEqual(result.status, "rate_limited")
        self.assertEqual(result.retry_after_seconds, 23)
        self.assertIn("Wait at least 23 seconds", result.message)
        self.assertNotIn(secret, repr(result))

    def test_invalid_downloaded_zip_is_rejected_by_existing_import_validator(self):
        def invalid_zip(destination):
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("readme.txt", "not a Nioh 2 mod")

        downloader = FakeDownloader(writer=invalid_zip)
        self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))

        result = self.wait_for_result()

        self.assertEqual(result.status, "package_rejected")
        self.assertEqual(self.manager.mods(), ())
        self.assertFalse(self.manager.packages_dir.joinpath("downloaded-mod").exists())

    def test_nexus_filename_gives_metadata_free_archive_a_stable_distinct_fallback_id(self):
        def metadata_free_zip(destination):
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("NiohMod/mod.ini", "[Mod]\n")
                archive.writestr("NiohMod/assets/model.fmt", b"asset")

        request = replace(
            Request(),
            game_scoped_mod_id="5678",
            mod_id="5678",
            file_id="98766",
            file_name="Ninja Weapon Textures.zip",
            file_version_id="34568",
            game_scoped_file_version_id="45679",
            mod_page_url="https://www.nexusmods.com/nioh2/mods/5678",
        )
        downloader = FakeDownloader(writer=metadata_free_zip)
        self.assertTrue(self.manager.enqueue_nexus_download(request, downloader))

        result = self.wait_for_result()

        self.assertEqual(result.status, "imported")
        self.assertIn("ninja-weapon-textures-", result.mod_id)
        self.assertEqual(len(self.manager.mods()), 1)

    def test_missing_downloader_capability_is_rejected(self):
        self.assertFalse(self.manager.enqueue_nexus_download(Request(), object()))
        self.assertEqual(self.manager.poll_nexus_download_results(), ())

    def test_waiting_queue_is_bounded_and_never_blocks_the_caller(self):
        downloader = FakeDownloader()
        downloader.release = threading.Event()
        self.addCleanup(downloader.release.set)

        started = time.monotonic()
        self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
        self.assertLess(time.monotonic() - started, 1.25)
        self.assertTrue(downloader.called.wait(2))

        for _ in range(3):
            self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
        self.assertFalse(self.manager.enqueue_nexus_download(Request(), downloader))

        downloader.release.set()
        deadline = time.monotonic() + 5
        results = []
        while time.monotonic() < deadline and len(results) < 4:
            results.extend(self.manager.poll_nexus_download_results(limit=10))
            if len(results) < 4:
                time.sleep(0.01)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(result.status == "imported" for result in results))
        deadline = time.monotonic() + 2
        while self.manager.nexus_downloads_pending and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self.manager.nexus_downloads_pending)

    def test_repeated_enqueue_near_worker_shutdown_does_not_lose_accepted_jobs(self):
        downloader = FakeDownloader()
        for _ in range(30):
            self.assertTrue(self.manager.enqueue_nexus_download(Request(), downloader))
            self.assertEqual(self.wait_for_result().status, "imported")
        deadline = time.monotonic() + 2
        while self.manager.nexus_downloads_pending and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self.manager.nexus_downloads_pending)

    def test_thread_start_failure_preserves_older_queued_request(self):
        older = _NexusDownloadJob(Request(file_id="older"), FakeDownloader())
        self.manager._nexus_jobs.put_nowait(older)
        with patch("koei_editor.shared.mod_manager.threading.Thread.start",
                   side_effect=RuntimeError("thread start failed")):
            self.assertFalse(self.manager.enqueue_nexus_download(Request(), FakeDownloader()))

        self.assertEqual(self.manager._nexus_jobs.qsize(), 1)
        self.assertIs(self.manager._nexus_jobs.get_nowait(), older)
        self.manager._nexus_jobs.task_done()


if __name__ == "__main__":
    unittest.main()

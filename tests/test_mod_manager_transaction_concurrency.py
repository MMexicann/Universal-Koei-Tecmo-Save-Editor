"""Regression coverage for live journal/recovery concurrency."""

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import zipfile
from unittest.mock import patch

import koei_editor.shared.mod_manager as mod_manager_module
from koei_editor.shared.mod_manager import GAME_EXE, LOADER_FILE, MODS_DIR, ModManager


@dataclass(frozen=True)
class NexusRequest:
    provider: str = "nexus"
    game_id: str = "nioh2_pc"
    game_domain: str = "nioh2"
    game_scoped_mod_id: str = "1234"
    mod_id: str = "1234"
    file_id: str = "98765"
    file_name: str = "queued-mod.zip"
    file_version_id: str = "34567"
    game_scoped_file_version_id: str = "45678"
    mod_page_url: str = "https://www.nexusmods.com/nioh2/mods/1234"


def write_package(path: Path, mod_id: str, name: str) -> None:
    metadata = {
        "schema_version": 1,
        "game_id": "nioh2_pc",
        "id": mod_id,
        "name": name,
        "version": "1.0",
        "dependencies": [],
        "conflicts": [],
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("NiohMod/mod.ini", "[Mod]\n")
        archive.writestr("NiohMod/assets/model.fmt", b"synthetic fixture")
        archive.writestr("koei-mod.json", json.dumps(metadata))


class _Downloader:
    def __init__(self):
        self.started = threading.Event()

    def download_archive(self, _request, destination):
        self.started.set()
        write_package(Path(destination), "queued-mod", "Queued Mod")
        return Path(destination).stat().st_size


class _ObservedMutationLock:
    """Expose that the Nexus worker found a live mutation lock held."""

    def __init__(self):
        self._lock = threading.RLock()
        self.nexus_worker_blocked = threading.Event()
        self.nexus_worker_entered_without_block = threading.Event()

    def __enter__(self):
        if (threading.current_thread().name == "koei-nexus-import"
                and not (self.nexus_worker_blocked.is_set()
                         or self.nexus_worker_entered_without_block.is_set())):
            if self._lock.acquire(blocking=False):
                self._lock.release()
                self.nexus_worker_entered_without_block.set()
            else:
                self.nexus_worker_blocked.set()
        self._lock.acquire()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self._lock.release()


class ModManagerTransactionConcurrencyTests(unittest.TestCase):
    def test_nexus_import_waits_for_live_install_transaction_instead_of_recovering_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            game = base / "game"
            game.mkdir()
            original_files = {
                GAME_EXE: b"original executable fixture",
                LOADER_FILE: b"user-installed loader fixture",
            }
            for name, contents in original_files.items():
                (game / name).write_bytes(contents)

            manager = ModManager(base / "state", game)
            mutation_lock = _ObservedMutationLock()
            manager._library_lock = mutation_lock
            source_package = base / "selected-mod.zip"
            write_package(source_package, "selected-mod", "Selected Mod")
            selected = manager.import_archive(source_package)
            manager.set_profile_mod_enabled("default", selected.id, True)

            journal_written = threading.Event()
            release_transaction = threading.Event()
            transaction_errors = []
            transaction_statuses = []
            original_atomic_json = mod_manager_module._atomic_json

            def pause_after_uncommitted_journal(path, value):
                revision = original_atomic_json(path, value)
                if (Path(path) == manager.journal_path
                        and value.get("committed") is False
                        and not journal_written.is_set()):
                    journal_written.set()
                    if not release_transaction.wait(5):
                        raise TimeoutError("test did not release the live transaction")
                return revision

            downloader = _Downloader()

            def apply_selected_profile():
                try:
                    transaction_statuses.extend(
                        manager.apply_profile("default", loader_confirmed=True))
                except Exception as error:  # surfaced in the main test thread below
                    transaction_errors.append(error)

            transaction_thread = threading.Thread(target=apply_selected_profile)
            with patch.object(mod_manager_module, "_atomic_json", side_effect=pause_after_uncommitted_journal):
                try:
                    transaction_thread.start()
                    self.assertTrue(journal_written.wait(5), "transaction did not write its journal")
                    self.assertTrue(manager.has_pending_transaction)
                    journal = json.loads(manager.journal_path.read_text(encoding="utf-8"))
                    self.assertFalse(journal["committed"])
                    stage_path = game / journal["stage"]
                    self.assertTrue(stage_path.is_dir())

                    self.assertTrue(manager.enqueue_nexus_download(NexusRequest(), downloader))
                    self.assertTrue(downloader.started.wait(5), "Nexus downloader did not start")
                    self.assertTrue(
                        mutation_lock.nexus_worker_blocked.wait(5),
                        "Nexus import did not wait for the live mutation lock",
                    )
                    self.assertTrue(manager.has_pending_transaction)
                    self.assertFalse(json.loads(manager.journal_path.read_text(encoding="utf-8"))["committed"])
                    self.assertTrue(stage_path.is_dir())
                    self.assertEqual(manager.poll_nexus_download_results(), ())
                finally:
                    release_transaction.set()
                    transaction_thread.join(5)
                    worker = manager._nexus_worker
                    if worker is not None:
                        worker.join(5)

            self.assertFalse(transaction_thread.is_alive(), "transaction thread did not finish")
            self.assertEqual(transaction_errors, [])
            self.assertTrue(any("Installed and enabled" in item for item in transaction_statuses))
            self.assertFalse(manager.has_pending_transaction)
            self.assertTrue((game / MODS_DIR / selected.id).is_dir())
            self.assertTrue(manager.installation["installed"][selected.id])
            self.assertTrue(manager.installation["profiles"][0]["enabled_mods"] == [selected.id])
            for name, contents in original_files.items():
                self.assertEqual((game / name).read_bytes(), contents)

            deadline = time.monotonic() + 5
            results = ()
            while time.monotonic() < deadline and not results:
                results = manager.poll_nexus_download_results()
                if not results:
                    time.sleep(0.01)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "imported")
            self.assertEqual(results[0].mod_id, "queued-mod")
            imported = {item.id: item for item in manager.mods()}["queued-mod"]
            self.assertFalse(imported.installed)
            self.assertFalse(imported.enabled)
            self.assertFalse(manager.has_pending_transaction)
            self.assertFalse(stage_path.exists())
            self.assertFalse(list(game.glob(".ktmm-transaction-*")))


if __name__ == "__main__":
    unittest.main()

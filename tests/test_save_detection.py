"""Procedural Steam metadata and live-read/import safety; no game execution."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import stat
import struct
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_detection as detection
from koei_editor.shared.save_detection_catalog import PROFILES
from koei_editor.shared.save_safety import safe_path
from koei_editor.shared.steam_owner import read_owner
from tests.test_origins_parser import fixture as origins_fixture
from koei_editor.games.origins import origins_codec
from tests.test_samurai5_pc import procedural as samurai5_fixture, sidecar
from tests.test_verified_editors import synthetic_raw


def installation(root, app_id, component='Installed Game'):
    steamapps = Path(root) / 'steamapps'
    folder = steamapps / 'common' / component
    folder.mkdir(parents=True, exist_ok=True)
    (steamapps / f'appmanifest_{app_id}.acf').write_text(
        f'"AppState" {{ "appid" "{app_id}" "installdir" "{component}" "StateFlags" "4" }}', encoding='utf-8')
    return folder


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        self.steam, self.documents, self.output = (self.folder / name for name in ('Steam', 'Documents', 'Imports'))
        self.steam.mkdir(); self.documents.mkdir(); self.output.mkdir()

    def scan(self):
        return detection.discover((self.steam,), (self.documents,))

    def native_dw8(self):
        profile = next(p for p in PROFILES if p.game_id == 'dw8xl')
        installation(self.steam, profile.app_id)
        source = self.documents.joinpath(*profile.documents_folder) / 'save.dat'
        source.parent.mkdir(parents=True)
        source.write_bytes(synthetic_raw('dw8xl'))
        return source

    def test_strict_vdf_nested_escaped_windows_paths_and_legacy_folders(self):
        parsed = detection.parse_vdf(b'"libraryfolders" { "0" { "path" "C:\\\\Program Files\\\\Steam" } "1" "D:\\\\Games" } // hi\n')
        self.assertEqual(parsed['libraryfolders']['0']['path'], 'C:\\Program Files\\Steam')
        self.assertEqual(parsed['libraryfolders']['1'], 'D:\\Games')
        for raw in (b'"a" "1" "A" "2"', b'"a" {', b'a "b"', b'"a" "unterminated',
                    b'"a" }', b'"a" "\0"', b'"a" {' * 10 + b'}' * 10):
            with self.subTest(raw=raw[:20]), self.assertRaises(SaveError):
                detection.parse_vdf(raw)

    def test_catalog_profiles_are_unique_registered_pc_and_location_parts_are_literal(self):
        self.assertEqual(len({p.app_id for p in PROFILES}), len(PROFILES))
        for profile in PROFILES:
            game = detection.get_game(profile.game_id)
            self.assertIsNotNone(game.scalar_backend)
            self.assertTrue(game.platform.startswith('Windows'))
            self.assertTrue(profile.evidence.startswith('https://'))
            self.assertFalse(any(part in ('.', '..') or '/' in part or '\\' in part for part in profile.documents_folder))

    def test_extra_library_app_manifest_and_no_save_status(self):
        library = self.folder / 'Library'; library.mkdir()
        installation(library, 968790)
        (self.steam / 'steamapps').mkdir()
        quoted = str(library).replace('\\', '\\\\')
        (self.steam / 'steamapps/libraryfolders.vdf').write_text(
            f'"libraryfolders" {{ "0" {{ "path" "{quoted}" }} }}', encoding='utf-8')
        result = self.scan()
        self.assertEqual(result.stop_reason, 'complete')
        self.assertEqual([(e.game_id, e.status) for e in result.entries], [('dw7xl', 'no_saves')])

    def test_native_qualification_occurs_only_on_copies_then_explicit_import(self):
        source = self.native_dw8(); original = source.read_bytes()
        with self.assertRaises(SaveError):
            safe_path(source)
        adapter = detection.library.adapter_for('dw8xl')
        calls = []
        original_read = type(adapter).read_save
        def checked_read(selected_adapter, path):
            calls.append(Path(path))
            self.assertNotEqual(Path(path), source)
            self.assertFalse(Path(path).is_relative_to(self.documents))
            return original_read(selected_adapter, path)
        with patch.object(type(adapter), 'read_save', checked_read):
            result = self.scan()
            entry, = result.entries
            self.assertEqual(entry.status, 'qualified')
            self.assertGreater(entry.mapped_fields, 0)
            copied = detection.import_copy(entry, self.output)
        self.assertTrue(calls)
        self.assertEqual(copied.read_bytes(), original)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(list(source.parent.iterdir()), [source])
        self.assertTrue(copied.parent.is_relative_to(self.output))
        self.assertEqual(detection.get_game('dw8xl').read_save(copied).raw, original)

    def test_foreign_data_does_not_trigger_any_other_parser_fallback(self):
        source = self.native_dw8()
        source.write_bytes(origins_fixture())
        original_adapter_for = detection.library.adapter_for
        selected = []
        def only(game_id):
            selected.append(game_id)
            return original_adapter_for(game_id)
        with patch.object(detection.library, 'adapter_for', side_effect=only):
            result = self.scan()
        self.assertEqual(selected, ['dw8xl'])
        self.assertEqual(result.entries[0].status, 'rejected')

    def test_native_noop_serializer_failure_refuses_qualification(self):
        self.native_dw8()
        adapter = detection.library.adapter_for('dw8xl')
        with patch.object(adapter.backend, 'serialize', return_value=b'not the opened native bytes') as native:
            result = self.scan()
        native.assert_called()
        self.assertEqual(result.entries[0].status, 'rejected')

    def test_changed_actual_import_is_retained_and_never_returned_as_qualified(self):
        source = self.native_dw8(); original = source.read_bytes()
        entry, = self.scan().entries
        publish = detection._publish_bundle
        def changed_output(profile, bundle, folder, budget):
            publish(profile, bundle, folder, budget)
            if folder.is_relative_to(self.output):
                copied = folder / source.name
                copied.write_bytes(b'foreign replacement')
        with patch.object(detection, '_publish_bundle', side_effect=changed_output), self.assertRaises(SaveError):
            detection.import_copy(entry, self.output)
        folders = list(self.output.iterdir())
        self.assertEqual(len(folders), 1)
        self.assertEqual((folders[0] / source.name).read_bytes(), b'foreign replacement')
        self.assertEqual(source.read_bytes(), original)

    def test_origin_cloud_capture_rejects_unsupported_native_revision(self):
        installation(self.steam, 2384580)
        source = self.steam / 'userdata/123/2384580/remote/SLOT0000.dat'
        source.parent.mkdir(parents=True)
        source.write_bytes(origins_fixture())
        result = self.scan()
        self.assertEqual(result.entries[0].status, 'qualified')
        self.assertEqual(result.entries[0].revision, '29')
        envelope = origins_codec.decode(source.read_bytes(), 'slot')
        body = bytearray(envelope.payload)
        struct.pack_into('<I', body, 0x664, 0xffffffff)
        source.write_bytes(origins_codec.encode(bytes(body), envelope.seed, 'slot'))
        self.assertEqual(self.scan().entries[0].status, 'rejected')

    def test_source_changed_after_scan_and_live_destination_refused(self):
        source = self.native_dw8()
        entry, = self.scan().entries
        with self.assertRaises(SaveError):
            detection.import_copy(entry, source.parent)
        original = source.read_bytes(); source.write_bytes(original[:-1] + bytes((original[-1] ^ 1,)))
        with self.assertRaises(SaveError):
            detection.import_copy(entry, self.output)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_ambiguous_duplicate_installs_and_malicious_install_component(self):
        installation(self.steam, 278080)
        other = self.folder / 'Other'; other.mkdir(); installation(other, 278080)
        result = detection.discover((self.steam, other), (self.documents,))
        self.assertEqual(result.entries[0].status, 'ambiguous')
        manifest = self.steam / 'steamapps/appmanifest_278080.acf'
        manifest.write_text('"AppState" { "appid" "278080" "installdir" "../Outside" }', encoding='utf-8')
        self.assertFalse(self.scan().entries)
        self.assertTrue(self.scan().warnings)

    def test_symlinks_hardlinks_fifo_and_linked_ancestors_are_refused_before_open(self):
        ordinary = self.folder / 'ordinary'; ordinary.write_bytes(b'test')
        try:
            linked = self.folder / 'linked'; linked.symlink_to(ordinary)
            linked_dir = self.folder / 'linked-dir'; linked_dir.symlink_to(self.folder, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Link creation unavailable.')
        for path in (linked, linked_dir / 'ordinary'):
            with self.assertRaises(SaveError), patch.object(detection.os, 'open') as opened:
                detection.capture_ordinary(path, 20)
            opened.assert_not_called()
        hard = self.folder / 'hard'; os.link(ordinary, hard)
        with self.assertRaises(SaveError):
            detection.capture_ordinary(ordinary, 20)
        if hasattr(os, 'mkfifo'):
            fifo = self.folder / 'pipe'; os.mkfifo(fifo)
            with self.assertRaises(SaveError):
                detection.capture_ordinary(fifo, 20)

    def test_capture_detects_mid_read_changes_and_windows_ctime_api_difference(self):
        source = self.folder / 'source'; source.write_bytes(b'a' * 100)
        original_read = detection.os.read
        changed = False
        def race(descriptor, size):
            nonlocal changed
            block = original_read(descriptor, size)
            if not changed:
                changed = True
                source.write_bytes(b'b' * 100)
            return block
        with patch.object(detection.os, 'read', side_effect=race), self.assertRaises(SaveError):
            detection.capture_ordinary(source, 200)
        original_fstat = detection.os.fstat
        def modern_windows(descriptor):
            info = original_fstat(descriptor)
            values = {name: getattr(info, name) for name in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_mode', 'st_nlink')}
            return SimpleNamespace(**values, st_ctime_ns=info.st_ctime_ns + 10000)
        with patch.object(detection.os, 'fstat', side_effect=modern_windows):
            raw, _ = detection.capture_ordinary(source, 200)
        self.assertEqual(raw, b'b' * 100)

    def test_sw5_opaque_companion_is_captured_and_imported_byte_exactly(self):
        profile = next(p for p in PROFILES if p.game_id == 'samurai5_pc')
        installation(self.steam, profile.app_id)
        source = self.documents.joinpath(*profile.documents_folder) / 'SAVEDATA.BIN'
        source.parent.mkdir(parents=True)
        fixture_folder = self.folder / 'ProceduralFixture'; fixture_folder.mkdir()
        fixture_path = fixture_folder / 'copy.bin'
        fixture_context = sidecar(fixture_folder)
        original_context = fixture_context.read_bytes()
        context = source.parent / fixture_context.name
        context.write_bytes(original_context)
        source.write_bytes(samurai5_fixture(read_owner(fixture_path)))
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        entry, = self.scan().entries
        self.assertEqual(entry.status, 'qualified')
        copied = detection.import_copy(entry, self.output)
        self.assertEqual((copied.parent / context.name).read_bytes(), original_context)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        self.assertEqual(context.read_bytes(), original_context)
        with self.assertRaises(SaveError):
            safe_path(copied.parent / context.name)
        context.write_bytes(original_context + b'\n')
        with self.assertRaises(SaveError):
            detection.import_copy(entry, self.output)
        if os.name != 'nt':
            context.write_bytes(original_context)
            (context.parent / 'STEAM_AUTOCLOUD.VDF').write_bytes(original_context)
            self.assertEqual(self.scan().entries[0].status, 'rejected')

    def test_cancellation_and_hard_budget_stop_without_writing_source(self):
        source = self.native_dw8(); before = source.read_bytes()
        cancel = threading.Event(); cancel.set()
        self.assertEqual(detection.discover((self.steam,), (self.documents,), cancel).stop_reason, 'cancelled')
        entry, = self.scan().entries
        with self.assertRaises(detection.DetectionCancelled):
            detection.import_copy(entry, self.output, cancel)
        with patch.object(detection, 'MAX_BYTES', 1):
            self.assertEqual(self.scan().stop_reason, 'limit')
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main()

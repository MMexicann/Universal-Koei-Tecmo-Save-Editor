"""Independent cross-component regressions using generated PS3 test bytes.

These tests establish copied-file safety and API integration, never native
player-file qualification or actual game loading.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.game_registry import GAMES, Game
from koei_editor.games.deception4_ps3 import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_discovery, save_doctor, save_library
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.save_vault import SaveVault
from tests import test_ps3_expansion as ps3_helpers
from tests.test_ps3_new_families import fixture
from tests.owned_directory_contract import install_owned_directory_contract


class SaveManagementRegressions(unittest.TestCase):
    def setUp(self):
        install_owned_directory_contract(self)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def copied_export(self, directory, slot='10'):
        directory.mkdir(parents=True)
        path = directory / 'DATA.BIN'
        path.write_bytes(fixture(parser))
        (directory / 'PARAM.SFO').write_bytes(
            ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-' + slot))
        return path

    def test_library_doctor_vault_roundtrip_preserves_distinct_original_context(self):
        copies = self.root / 'copies'
        first = self.copied_export(copies / 'first')
        second = self.copied_export(copies / 'second', slot='11')
        original = {str(path.relative_to(copies)): path.read_bytes()
                    for path in copies.rglob('*') if path.is_file()}
        inventory = save_library.scan(parser.GAME_ID, copies, recursive=True)
        self.assertEqual(inventory.qualified_count, 2)
        self.assertEqual(len({entry.duplicate_group for entry in inventory.entries}), 1)
        self.assertNotEqual(inventory.entries[0].duplicate_group, 0)
        for entry in inventory.entries:
            report = save_doctor.inspect_save(parser.GAME_ID, copies / entry.relative_path,
                                             expected_sha256=entry.sha256)
            self.assertTrue(report.success)
        vault = SaveVault.create(self.root / 'vault')
        a = vault.snapshot(parser.GAME_ID, first)
        b = vault.snapshot(parser.GAME_ID, second)
        comparison = vault.compare(a.id, b.id)
        self.assertTrue(comparison.identical_gameplay_bytes)
        self.assertFalse(comparison.identical_context_bytes)
        self.assertEqual(comparison.changed_field_ids, ())
        restored = vault.restore(a.id, self.root / 'restored')
        self.assertEqual(restored.read_bytes(), first.read_bytes())
        self.assertEqual((restored.parent / 'PARAM.SFO').read_bytes(),
                         (first.parent / 'PARAM.SFO').read_bytes())
        restored_scan = save_library.scan(parser.GAME_ID, restored.parent)
        self.assertEqual(restored_scan.qualified_count, 1)
        self.assertTrue(save_doctor.inspect_save(parser.GAME_ID, restored).success)
        self.assertTrue(all(item.valid for item in vault.verify()))
        self.assertEqual(original, {str(path.relative_to(copies)): path.read_bytes()
                                    for path in copies.rglob('*') if path.is_file()})

    def test_discovery_does_not_authorize_live_locations_for_other_save_tools(self):
        steam = self.root / 'Steam'
        remote = steam / 'userdata/123456/527270/remote'
        self.copied_export(remote)
        before = {item: item.read_bytes() for item in remote.iterdir() if item.is_file()}
        home = self.root / 'home'
        home.mkdir()
        result = save_discovery.discover_saves(steam_roots=(steam,), home=home)
        self.assertTrue(any(item.path == remote for item in result.locations))
        vault = SaveVault.create(self.root / 'vault')
        # Every profile must reject live paths before native reads, even if a
        # discovery result points there and the candidate filename is absent.
        with patch.object(Game, 'read_save', side_effect=AssertionError('Live file reached native reader')), \
                patch.object(BoundScalarAdapter, 'read_save', side_effect=AssertionError('Live file reached scalar reader')):
            for game in GAMES:
                with self.subTest(game=game.id):
                    protected = remote / ('candidate-' + game.id + game.extension)
                    self.assertEqual(save_doctor.inspect_save(game.id, protected).status, 'unsafe')
                    with self.assertRaises(SaveError):
                        save_library.scan(game.id, remote)
                    with self.assertRaises(SaveError):
                        vault.snapshot(game.id, protected)
        self.assertEqual(vault.list_snapshots(), ())
        self.assertEqual(tuple(vault.objects.iterdir()), ())
        self.assertEqual(before, {item: item.read_bytes() for item in remote.iterdir() if item.is_file()})

    def test_every_registered_profile_rejects_empty_inputs_without_creating_history(self):
        vault = SaveVault.create(self.root / 'vault')
        for game in GAMES:
            with self.subTest(game=game.id):
                source = self.root / ('empty-' + game.id + game.extension)
                source.write_bytes(b'')
                report = save_doctor.inspect_save(game.id, source)
                self.assertFalse(report.success)
                self.assertFalse(any(check.code == 'unchanged_roundtrip' and check.status == 'passed'
                                     for check in report.checks))
                with self.assertRaises((SaveError, OSError)):
                    vault.snapshot(game.id, source)
                self.assertEqual(source.read_bytes(), b'')
        self.assertEqual(vault.list_snapshots(), ())
        self.assertEqual(tuple(vault.objects.iterdir()), ())

    def test_corrupt_vault_context_blocks_restore_before_destination_creation(self):
        source = self.copied_export(self.root / 'copy')
        vault = SaveVault.create(self.root / 'vault')
        item = vault.snapshot(parser.GAME_ID, source)
        context = vault.objects / item.id / 'PARAM.SFO'
        context.write_bytes(ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
        verification, = vault.verify(item.id)
        self.assertFalse(verification.valid)
        destination = self.root / 'restored'
        with self.assertRaises(SaveError):
            vault.restore(item.id, destination)
        self.assertFalse(destination.exists())
        self.assertTrue(save_doctor.inspect_save(parser.GAME_ID, source).success)


if __name__ == '__main__':
    unittest.main()

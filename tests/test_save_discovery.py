"""Procedural metadata fixtures; no game files, personal paths or account data."""
import json
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest import mock

from koei_editor.game_registry import GAMES
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_discovery as discovery
from koei_editor.shared.save_safety import safe_path


class VdfTests(unittest.TestCase):
    def test_old_new_comments_escaping_and_case(self):
        parsed = discovery.parse_vdf('// comment\n"LibraryFolders" { "0" "C:\\\\Steam" "1" { "path" "/games/with \\"quotes\\"" "apps" { "527270" "10" } } }')
        self.assertEqual(parsed['libraryfolders']['0'], 'C:\\Steam')
        self.assertEqual(parsed['libraryfolders']['1']['path'], '/games/with "quotes"')

    def test_ambiguous_malformed_and_excessive_inputs_rejected(self):
        malformed = ('"x" {', '}', '"x"', '"x" }', '"x" "a" "X" "b"',
                     '"x" "unterminated', '#include "other.vdf"', '"x" "a\0b"',
                     '"x" { "A" "a" "a" "b" }', '"x" {' * 14 + '}' * 14,
                     'x' * (256 * 1024 + 1))
        for text in malformed:
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                discovery.parse_vdf(text)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.home = self.folder / 'home'
        self.home.mkdir()
        self.steam = self.folder / 'Steam'
        self.steam.mkdir()

    def scan(self, **kwargs):
        kwargs.setdefault('home', self.home)
        kwargs.setdefault('local_app_data', self.home / 'AppData/Local')
        kwargs.setdefault('roaming_app_data', self.home / 'AppData/Roaming')
        kwargs.setdefault('steam_roots', (self.steam,))
        return discovery.discover_saves(**kwargs)

    def write(self, relative, text, *, root=None):
        path = (root or self.steam) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def installation(self, app='527270', *, root=None, name='Game'):
        root = root or self.steam
        self.write(f'steamapps/appmanifest_{app}.acf',
                   f'"AppState" {{ "appid" "{app}" "installdir" "{name}" }}', root=root)
        install = root / 'steamapps/common' / name
        install.mkdir(parents=True, exist_ok=True)
        return install

    def remote(self, app='527270', *, root=None, account='123456'):
        path = (root or self.steam) / 'userdata' / account / app / 'remote'
        path.mkdir(parents=True)
        return path

    def link(self, link, target):
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except OSError:
            self.skipTest('Creating symlinks requires platform privileges.')

    def test_missing_roots_and_unmapped_profiles_remain_compatible(self):
        result = self.scan(steam_roots=(self.folder / 'missing',))
        self.assertEqual(result.stop_reason, 'complete')
        self.assertEqual(result.installed_games, ())
        self.assertEqual(result.locations, ())
        self.assertFalse(result.issues)
        registered = {game.id for game in GAMES}
        self.assertTrue(set(result.mapped_game_ids) < registered)
        self.assertTrue(all(item.game_id in registered for item in discovery.STEAM_MAPPINGS))
        self.assertTrue(all(item.game_id in registered for item in discovery.NATIVE_MAPPINGS))

    def test_installed_games_require_matching_manifest_and_ordinary_installation(self):
        install = self.installation()
        result = self.scan()
        self.assertEqual(len(result.installed_games), 1)
        item = result.installed_games[0]
        self.assertEqual((item.game_id, item.app_id, item.install_path),
                         ('atelier_sophie', '527270', install))
        self.assertEqual(item.confidence, 'installation_metadata')
        install.rmdir()
        self.assertFalse(self.scan().installed_games)
        install.mkdir()
        self.write('steamapps/appmanifest_527270.acf',
                   '"AppState" { "appid" "999999" "installdir" "Game" }')
        self.assertFalse(self.scan().installed_games)
        self.assertIn('manifest_identity_mismatch_skipped', self.scan().issues)

    def test_unrelated_apps_and_other_editions_never_matched_by_names(self):
        self.installation('999999', name='Atelier Sophie')
        self.installation('1502970', name='Atelier Sophie DX')
        self.remote('999999')
        result = self.scan()
        self.assertFalse(result.installed_games)
        self.assertFalse(result.locations)
        self.assertEqual(result.metadata_bytes, 0)

    def test_all_reviewed_steam_mappings_detect_exact_registered_pc_profiles(self):
        registered = {game.id: game for game in GAMES}
        for mapping in discovery.STEAM_MAPPINGS:
            self.installation(mapping.app_id, name='Game-' + mapping.app_id)
            self.remote(mapping.app_id)
            self.assertEqual(registered[mapping.game_id].platform, 'Windows PC')
            self.assertTrue(Path(mapping.evidence).is_file())
        result = self.scan()
        expected = {(item.game_id, item.app_id) for item in discovery.STEAM_MAPPINGS}
        self.assertGreaterEqual(len(expected), 19)
        self.assertEqual({(item.game_id, item.app_id) for item in result.installed_games}, expected)
        self.assertEqual({item.game_id for item in result.locations}, {item[0] for item in expected})
        self.assertEqual(result.stop_reason, 'complete')

    def test_research_only_and_console_pc_store_ids_are_excluded(self):
        # Existing console support and PC research documents do not qualify a
        # corresponding installed Windows profile or justify parser fallback.
        excluded = ('936160', '936190', '936180', '502280', '449800', '601050',
                    '730310', '595740', '410850', '574050', '1902690', '1716120')
        for app_id in excluded:
            self.installation(app_id, name='Unregistered-' + app_id)
            self.remote(app_id)
        result = self.scan()
        self.assertFalse(result.installed_games)
        self.assertFalse(result.locations)
        self.assertEqual(result.metadata_bytes, 0)

    def test_malformed_vdf_does_not_hide_other_valid_metadata(self):
        self.write('steamapps/libraryfolders.vdf', '"libraryfolders" {')
        self.installation()
        result = self.scan()
        self.assertEqual(len(result.installed_games), 1)
        self.assertIn('malformed_metadata_skipped', result.issues)

    def test_old_and_new_libraryfolders_and_cycles(self):
        library = self.folder / 'other-library'
        library.mkdir()
        self.installation('527290', root=library)
        for value in (f'"{library.as_posix()}"', f'{{ "path" "{library.as_posix()}" "apps" {{ "527290" "1" }} }}'):
            with self.subTest(value=value):
                self.write('steamapps/libraryfolders.vdf', f'"libraryfolders" {{ "0" {value} }}')
                self.write('steamapps/libraryfolders.vdf',
                           f'"libraryfolders" {{ "0" "{self.steam.as_posix()}" }}', root=library)
                result = self.scan()
                self.assertEqual([item.game_id for item in result.installed_games], ['atelier_firis_pc'])
                self.assertEqual(result.stop_reason, 'complete')

    def test_relative_library_paths_and_directory_traversal_rejected(self):
        self.write('steamapps/libraryfolders.vdf', '"libraryfolders" { "0" { "path" "../elsewhere" } }')
        self.write('steamapps/appmanifest_527270.acf',
                   '"AppState" { "appid" "527270" "installdir" "../escape" }')
        result = self.scan()
        self.assertFalse(result.installed_games)
        self.assertIn('invalid_library_path_skipped', result.issues)
        self.assertIn('invalid_install_directory_skipped', result.issues)

    def test_legacy_config_libraryfolders_location(self):
        library = self.folder / 'legacy-library'
        library.mkdir()
        self.installation(root=library)
        self.write('config/libraryfolders.vdf', f'"LibraryFolders" {{ "1" "{library.as_posix()}" }}')
        result = self.scan()
        self.assertEqual([item.game_id for item in result.installed_games], ['atelier_sophie'])

    def test_userdata_candidates_do_not_require_current_installation(self):
        remote = self.remote()
        (self.steam / 'userdata/not-an-account/527270/remote').mkdir(parents=True)
        result = self.scan()
        self.assertEqual(len(result.locations), 1)
        self.assertEqual(result.locations[0].path, remote)
        self.assertEqual(result.locations[0].source, 'steam_userdata')
        self.assertEqual(result.locations[0].confidence, 'location_candidate')
        self.assertTrue(result.locations[0].live)
        self.assertFalse(result.installed_games)

    def test_native_documents_and_local_data_locations(self):
        expected = []
        bases = dict(documents=self.home / 'Documents', local_app_data=self.home / 'AppData/Local',
                     roaming_app_data=self.home / 'AppData/Roaming')
        for item in discovery.NATIVE_MAPPINGS:
            base = bases[item.base]
            path = base / item.relative
            path.mkdir(parents=True, exist_ok=True)
            expected.append((item.game_id, path))
        result = self.scan(steam_roots=())
        self.assertEqual([(item.game_id, item.path) for item in result.locations], expected)
        self.assertTrue(all(item.source == 'reviewed_native_location' for item in result.locations))

    def test_roaming_account_scoped_parent_is_reported_without_listing_or_reading_accounts(self):
        roaming = self.folder / 'redirected-roaming'
        account = roaming / 'SEGA/Steam/P5S/private-account'
        account.mkdir(parents=True)
        (account / 'SAVEDATA.BIN').write_bytes(b'private gameplay bytes')
        with mock.patch.object(discovery.os, 'scandir', side_effect=AssertionError('No account traversal')), \
                mock.patch.object(discovery.os, 'open', side_effect=AssertionError('No gameplay reads')):
            result = self.scan(steam_roots=(), roaming_app_data=roaming)
        self.assertEqual([(item.game_id, item.path) for item in result.locations],
                         [('p5strikers_pc', roaming / 'SEGA/Steam/P5S')])
        self.assertNotIn('private-account', json.dumps(discovery.report(result)))

    def test_windows_installation_defaults_use_only_readonly_registry_keys_and_environment(self):
        registry = types.SimpleNamespace(HKEY_CURRENT_USER=1, HKEY_LOCAL_MACHINE=2,
                                         KEY_READ=0x20019, REG_SZ=1)
        handle = mock.MagicMock()
        handle.__enter__.return_value = handle
        registry.OpenKey = mock.Mock(return_value=handle)
        registry.QueryValueEx = mock.Mock(side_effect=[(str(self.steam), 1),
                                                       (str(self.folder / 'machine-steam'), 1)])
        environment = {'PROGRAMFILES(X86)': str(self.folder / 'program-files-x86'),
                       'PROGRAMFILES': str(self.folder / 'program-files'),
                       'LOCALAPPDATA': str(self.folder / 'local-data')}
        with mock.patch.dict('sys.modules', {'winreg': registry}), \
                mock.patch.dict(os.environ, environment, clear=True):
            roots = discovery._windows_roots()
        self.assertEqual(roots, [Path(environment[name]) / 'Steam' for name in environment]
                         + [self.steam, self.folder / 'machine-steam'])
        self.assertEqual(registry.OpenKey.call_args_list,
                         [mock.call(1, r'Software\Valve\Steam', 0, registry.KEY_READ),
                          mock.call(2, r'SOFTWARE\WOW6432Node\Valve\Steam', 0, registry.KEY_READ)])
        self.assertEqual(registry.QueryValueEx.call_args_list,
                         [mock.call(handle, 'SteamPath'), mock.call(handle, 'InstallPath')])

    def test_windows_missing_registry_and_wrong_value_types_are_safe(self):
        registry = types.SimpleNamespace(HKEY_CURRENT_USER=1, HKEY_LOCAL_MACHINE=2,
                                         KEY_READ=1, REG_SZ=1)
        handle = mock.MagicMock()
        registry.OpenKey = mock.Mock(side_effect=[handle, OSError('Missing machine installation')])
        registry.QueryValueEx = mock.Mock(return_value=(str(self.steam), 7))
        with mock.patch.dict('sys.modules', {'winreg': registry}), \
                mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(discovery._windows_roots(), [])

    def test_explicit_redirected_documents_and_local_data(self):
        docs = self.folder / 'redirected-documents'
        local = self.folder / 'redirected-local'
        (docs / 'KOEI/WARRIORS OROCHI/Savedata').mkdir(parents=True)
        (local / 'KoeiTecmo/Dynasty Warriors Origins/Savedata').mkdir(parents=True)
        result = self.scan(documents=docs, local_app_data=local)
        self.assertEqual({item.game_id for item in result.locations}, {'wo1', 'origins'})

    def test_proton_location_is_scoped_to_manifest_app(self):
        self.installation('363150')
        expected = self.steam / 'steamapps/compatdata/363150/pfx/drive_c' / 'users' / 'steamuser' / 'Documents/KoeiTecmo/SAN13'
        expected.mkdir(parents=True)
        unrelated = self.steam / 'steamapps/compatdata/999999/pfx/drive_c' / 'users' / 'steamuser' / 'Documents/KoeiTecmo/SAN13'
        unrelated.mkdir(parents=True)
        result = self.scan()
        self.assertEqual(len(result.locations), 1)
        self.assertEqual(result.locations[0].path, expected)
        self.assertEqual(result.locations[0].source, 'proton_reviewed_location')

    def test_all_reviewed_proton_documents_local_and_roaming_mappings(self):
        expected = set()
        for steam in discovery.STEAM_MAPPINGS:
            self.installation(steam.app_id, name='Proton-' + steam.app_id)
            user = self.steam / f'steamapps/compatdata/{steam.app_id}/pfx/drive_c' / 'users' / 'steamuser'
            bases = dict(documents=user / 'Documents', local_app_data=user / 'AppData/Local',
                         roaming_app_data=user / 'AppData/Roaming')
            for mapping in discovery.NATIVE_MAPPINGS:
                if mapping.game_id == steam.game_id:
                    path = bases[mapping.base] / mapping.relative
                    path.mkdir(parents=True)
                    expected.add((mapping.game_id, path))
        result = self.scan()
        self.assertGreaterEqual(len(expected), 10)
        self.assertEqual({(item.game_id, item.path) for item in result.locations}, expected)
        self.assertTrue(all(item.source == 'proton_reviewed_location' for item in result.locations))

    def test_discovery_never_opens_gameplay_or_cloud_account_files(self):
        self.installation()
        remote = self.remote()
        (remote / 'GAMEDATA').write_bytes(b'not a save')
        (remote.parent / 'remotecache.vdf').write_text('private account metadata')
        (remote / 'steam_autocloud.vdf').write_text('private account metadata')
        opened = []
        original_open = os.open

        def record(path, flags, *args, **kwargs):
            opened.append(Path(path))
            self.assertEqual(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC), 0)
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(discovery.os, 'open', side_effect=record), \
                mock.patch.object(discovery, 'parse_vdf', wraps=discovery.parse_vdf) as parser:
            result = self.scan()
        self.assertEqual(len(result.locations), 1)
        self.assertEqual([item.name for item in opened], ['appmanifest_527270.acf'])
        self.assertEqual(parser.call_count, 1)
        # Discovery has not relaxed the shared live-save protections.
        with self.assertRaises(SaveError):
            safe_path(remote / 'GAMEDATA')

    def test_portable_report_and_repr_hide_local_paths_accounts_and_names(self):
        self.installation(name='Private installation name')
        self.remote(account='998877665544332211')
        result = self.scan()
        text = json.dumps(discovery.report(result))
        for private in (str(self.folder), '998877665544332211', 'Private installation name', 'remote'):
            self.assertNotIn(private, text)
            self.assertNotIn(private, repr(result))
        self.assertIn('not native-save qualification', text)

    def test_duplicate_roots_and_native_locations_are_deduplicated(self):
        self.installation()
        self.remote()
        result = self.scan(steam_roots=(self.steam, self.steam))
        self.assertEqual(len(result.installed_games), 1)
        self.assertEqual(len(result.locations), 1)

    def test_linked_root_ancestor_installation_and_userdata_rejected(self):
        self.installation()
        self.remote()
        alias = self.folder / 'alias'
        self.link(alias, self.steam)
        result = self.scan(steam_roots=(alias,))
        self.assertFalse(result.installed_games)
        self.assertFalse(result.locations)
        self.assertIn('linked_or_nonordinary_path_skipped', result.issues)
        result = self.scan(steam_roots=(alias / 'steamapps',))
        self.assertFalse(result.installed_games)
        self.assertIn('linked_or_nonordinary_path_skipped', result.issues)

    def test_linked_metadata_and_hardlinked_metadata_rejected_without_read(self):
        external = self.write('external.acf', '"AppState" { "appid" "527270" "installdir" "Game" }')
        metadata = self.steam / 'steamapps/appmanifest_527270.acf'
        self.link(metadata, external)
        with mock.patch.object(discovery.os, 'open', side_effect=AssertionError('Must not open linked metadata')):
            result = self.scan()
        self.assertFalse(result.installed_games)
        self.assertIn('linked_or_changed_metadata_skipped', result.issues)
        metadata.unlink()
        os.link(external, metadata)
        with mock.patch.object(discovery.os, 'open', side_effect=AssertionError('Must not open aliased metadata')):
            result = self.scan()
        self.assertIn('linked_or_changed_metadata_skipped', result.issues)

    def test_linked_account_remote_and_native_ancestors_rejected(self):
        target = self.folder / 'external'
        (target / '527270/remote').mkdir(parents=True)
        self.link(self.steam / 'userdata/123456', target)
        self.link(self.home / 'Documents', target)
        (target / 'KOEI/WARRIORS OROCHI/Savedata').mkdir(parents=True)
        result = self.scan()
        self.assertFalse(result.locations)
        self.assertIn('linked_or_nonordinary_path_skipped', result.issues)

    def test_reparse_attribute_is_rejected_on_every_platform(self):
        info = mock.Mock(st_mode=0o040755, st_file_attributes=0x400)
        self.assertTrue(discovery._linked(info))

    def test_precancelled_does_not_read_anything(self):
        self.installation()
        cancel = threading.Event()
        cancel.set()
        with mock.patch.object(discovery.os, 'open', side_effect=AssertionError('Cancelled')):
            result = self.scan(cancel=cancel)
        self.assertEqual(result.stop_reason, 'cancelled')
        self.assertEqual(result.metadata_bytes, 0)
        self.assertFalse(result.installed_games)

    def test_cancellation_during_read_closes_descriptor(self):
        self.installation()
        cancel = threading.Event()
        original_read = os.read
        original_close = os.close
        closed = []

        def read(descriptor, count):
            cancel.set()
            return original_read(descriptor, count)

        def close(descriptor):
            closed.append(descriptor)
            return original_close(descriptor)

        with mock.patch.object(discovery.os, 'read', side_effect=read), \
                mock.patch.object(discovery.os, 'close', side_effect=close):
            result = self.scan(cancel=cancel)
        self.assertEqual(result.stop_reason, 'cancelled')
        self.assertEqual(len(closed), 1)

    def test_fixed_limits_and_all_stop_reasons(self):
        self.installation()
        self.remote()
        self.remote(account='654321')
        result = self.scan(limits=discovery.DiscoveryLimits(max_entries=1))
        self.assertEqual((result.stop_reason, result.visited_entries), ('entry_limit', 1))
        result = self.scan(limits=discovery.DiscoveryLimits(max_metadata_bytes=1))
        self.assertEqual((result.stop_reason, result.metadata_bytes), ('byte_limit', 0))
        result = self.scan(limits=discovery.DiscoveryLimits(max_results=1))
        self.assertEqual(result.stop_reason, 'result_limit')
        self.assertEqual(len(result.installed_games) + len(result.locations), 1)
        result = self.scan(steam_roots=(self.folder / 'missing', self.steam),
                           limits=discovery.DiscoveryLimits(max_roots=1))
        self.assertEqual(result.stop_reason, 'root_limit')
        for limits in (None, {}, discovery.DiscoveryLimits(max_entries=True),
                       discovery.DiscoveryLimits(max_roots=17), discovery.DiscoveryLimits(max_results=0)):
            with self.subTest(limits=limits), self.assertRaises(SaveError):
                self.scan(limits=limits)

    def test_oversized_metadata_is_never_opened(self):
        self.write('steamapps/libraryfolders.vdf', 'x' * 50)
        with mock.patch.object(discovery.os, 'open', side_effect=AssertionError('Oversized')):
            result = self.scan(limits=discovery.DiscoveryLimits(max_file_bytes=49))
        self.assertIn('oversized_metadata_skipped', result.issues)
        self.assertEqual(result.metadata_bytes, 0)

    def test_same_size_metadata_rewrite_with_restored_mtime_is_rejected(self):
        self.installation()
        path = self.steam / 'steamapps/appmanifest_527270.acf'
        original_read = os.read
        before = path.stat()

        def read(descriptor, count):
            block = original_read(descriptor, count)
            original = path.read_bytes()
            path.write_bytes(original.replace(b'Game', b'Else'))
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            return block

        with mock.patch.object(discovery.os, 'read', side_effect=read):
            result = self.scan()
        self.assertFalse(result.installed_games)
        self.assertIn('linked_or_changed_metadata_skipped', result.issues)

    def test_metadata_replaced_after_open_is_rejected(self):
        self.installation()
        path = self.steam / 'steamapps/appmanifest_527270.acf'
        replacement = self.write('different-file.acf', path.read_text())
        original_checked = discovery._ordinary
        checks = 0

        def replace(path_arg, *, directory):
            nonlocal checks
            if path_arg == path:
                checks += 1
                if checks >= 2:
                    return path, replacement.stat()
            return original_checked(path_arg, directory=directory)

        # Model a different path inode after opening without requiring Windows
        # to permit deleting an in-use file handle.
        with mock.patch.object(discovery, '_ordinary', side_effect=replace):
            result = self.scan()
        self.assertFalse(result.installed_games)
        self.assertIn('linked_or_changed_metadata_skipped', result.issues)


if __name__ == '__main__':
    unittest.main()

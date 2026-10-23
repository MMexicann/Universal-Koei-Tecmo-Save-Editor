"""Native Linux Steam roots and metadata-only Hub/Tracker behavior."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import game_hub, save_discovery, version_tracker


@unittest.skipUnless(sys.platform.startswith('linux'), 'Native Linux filesystem discovery')
class LinuxSteamDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.home = self.folder / 'home'
        self.home.mkdir()
        environment = patch.dict(os.environ, {'XDG_DATA_HOME': ''})
        environment.start()
        self.addCleanup(environment.stop)

    def install(self, root, *, name='Atelier Sophie'):
        apps = root / 'steamapps'
        apps.mkdir(parents=True, exist_ok=True)
        installation = apps / 'common' / name
        installation.mkdir(parents=True)
        (apps / 'appmanifest_527270.acf').write_text(
            '"AppState" { "appid" "527270" "installdir" "' + name +
            '" "buildid" "12345678" "LastUpdated" "1743511000" }', encoding='utf-8')
        return installation

    def scan(self, **kwargs):
        return save_discovery.discover_installed_builds(home=self.home, **kwargs)

    def test_native_flatpak_and_xdg_roots_detect_installs_without_save_scans(self):
        roots = (self.home / '.local/share/Steam',
                 self.home / '.var/app/com.valvesoftware.Steam/.local/share/Steam',
                 self.folder / 'custom-data/Steam')
        for index, root in enumerate(roots):
            self.install(root, name='Sophie ' + str(index))
        with patch.dict(os.environ, {'XDG_DATA_HOME': str(self.folder / 'custom-data')}), \
                patch.object(save_discovery._Scanner, 'native', side_effect=AssertionError('save scan')), \
                patch.object(save_discovery._Scanner, 'children', side_effect=AssertionError('userdata scan')):
            result = self.scan()
        self.assertEqual({game.library_path for game in result.installed_games}, set(roots))
        self.assertEqual(result.locations, ())
        self.assertEqual(result.stop_reason, 'complete')
        portable = json.dumps(save_discovery.report(result))
        self.assertNotIn(str(self.folder), portable)
        self.assertTrue(all(game.game_id == 'atelier_sophie' for game in result.installed_games))

    def test_flatpak_xdg_data_layout_is_also_detected(self):
        root = self.home / '.var/app/com.valvesoftware.Steam/data/Steam'
        installation = self.install(root)
        self.assertEqual(self.scan().installed_games[0].install_path, installation)

    def test_steam_symbolic_default_aliases_are_resolved_and_deduplicated(self):
        canonical = self.home / '.local/share/Steam'
        self.install(canonical)
        aliases = self.home / '.steam'
        aliases.mkdir()
        (aliases / 'steam').symlink_to(canonical, target_is_directory=True)
        (aliases / 'root').symlink_to(aliases / 'steam', target_is_directory=True)
        roots = save_discovery._default_roots(self.home)
        self.assertEqual(roots.count(canonical), 1)
        result = self.scan()
        self.assertEqual(len(result.installed_games), 1)
        self.assertEqual(result.installed_games[0].library_path, canonical)

    def test_steam_alias_can_identify_external_install_but_explicit_links_stay_rejected(self):
        canonical = self.folder / 'external-steam'
        self.install(canonical)
        alias = self.home / '.steam/steam'
        alias.parent.mkdir()
        alias.symlink_to(canonical, target_is_directory=True)
        self.assertEqual(self.scan().installed_games[0].library_path, canonical)
        result = self.scan(steam_roots=(alias,))
        self.assertEqual(result.installed_games, ())
        self.assertIn('linked_or_nonordinary_path_skipped', result.issues)

    def test_relative_xdg_home_is_ignored(self):
        with patch.dict(os.environ, {'XDG_DATA_HOME': 'relative-data'}):
            roots = save_discovery._default_roots(self.home)
        self.assertNotIn(Path('relative-data/Steam'), roots)
        self.assertTrue(all(root.is_absolute() for root in roots))

    def test_linked_library_and_metadata_are_still_rejected(self):
        root = self.home / '.local/share/Steam'
        self.install(root)
        outside = self.folder / 'outside'
        outside.mkdir()
        self.install(outside)
        linked_library = self.folder / 'linked-library'
        linked_library.symlink_to(outside, target_is_directory=True)
        (root / 'steamapps/libraryfolders.vdf').write_text(
            '"libraryfolders" { "0" { "path" "' + str(linked_library) + '" } }', encoding='utf-8')
        manifest = root / 'steamapps/appmanifest_527270.acf'
        manifest.unlink()
        manifest.symlink_to(outside / 'steamapps/appmanifest_527270.acf')
        result = self.scan()
        self.assertEqual(result.installed_games, ())
        self.assertIn('linked_or_nonordinary_path_skipped', result.issues)
        self.assertIn('linked_or_changed_metadata_skipped', result.issues)

    def test_alias_loops_do_not_abort_other_default_roots(self):
        root = self.home / '.local/share/Steam'
        self.install(root)
        alias = self.home / '.steam/steam'
        alias.parent.mkdir()
        alias.symlink_to(alias)
        result = self.scan()
        self.assertEqual(len(result.installed_games), 1)
        self.assertEqual(result.stop_reason, 'complete')

    def test_tracker_observes_same_linux_install_without_claiming_linux_game_profile(self):
        self.install(self.home / '.var/app/com.valvesoftware.Steam/data/Steam')
        with patch.object(game_hub.webbrowser, 'open') as opener:
            result = version_tracker.scan_installed_builds(home=self.home)
        self.assertEqual(len(result.observations), 1)
        observation, = result.observations
        self.assertEqual(observation.platform, 'Windows PC')
        self.assertEqual(observation.game_id, 'atelier_sophie')
        self.assertEqual(observation.build_id, '12345678')
        self.assertEqual(observation.confidence, 'installation_metadata')
        opener.assert_not_called()


class SteamRuntimeNoticeTests(unittest.TestCase):
    def test_linux_notice_distinguishes_save_profile_from_game_runtime(self):
        with patch.object(game_hub.sys, 'platform', 'linux'):
            notice = game_hub.installation_runtime_notice()
            self.assertIn('Proton', notice)
            self.assertIn('registered save profile', notice)
            self.assertIn('not been verified', notice)
            self.assertIn('nicht verifiziert', game_hub.installation_runtime_notice('de'))
        with patch.object(game_hub.sys, 'platform', 'win32'):
            self.assertEqual(game_hub.installation_runtime_notice(), '')


if __name__ == '__main__':
    unittest.main()

"""Steam install metadata used by Game Hub; fixtures contain no user files."""
import json
from pathlib import Path
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_discovery


class GameHubDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.steam = self.root / 'Steam'
        self.steam.mkdir()

    def write(self, root, relative, text):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def install(self, root, *, app_id='527270', name='Atelier Sophie', metadata=''):
        manifest = (f'"AppState" {{ "appid" "{app_id}" "installdir" "{name}" '
                    f'{metadata} }}')
        self.write(root, f'steamapps/appmanifest_{app_id}.acf', manifest)
        install_path = root / 'steamapps/common' / name
        install_path.mkdir(parents=True, exist_ok=True)
        return install_path

    def scan(self):
        return save_discovery.discover_saves(
            home=self.home,
            local_app_data=self.home / 'AppData/Local',
            roaming_app_data=self.home / 'AppData/Roaming',
            steam_roots=(self.steam,),
        )

    def test_additional_library_exposes_build_metadata_and_redacts_local_paths(self):
        library = self.root / 'Games Library'
        library.mkdir()
        install_path = self.install(
            library,
            metadata='"buildid" "83921005" "LastUpdated" "1743511000" '
                     '"SizeOnDisk" "2430432"',
        )
        self.write(
            self.steam,
            'steamapps/libraryfolders.vdf',
            f'"libraryfolders" {{ "0" {{ "path" "{self.steam.as_posix()}" }} '
            f'"1" {{ "path" "{library.as_posix()}" "apps" {{ "527270" "1" }} }} }}',
        )

        result = self.scan()

        self.assertEqual(len(result.installed_games), 1)
        game, = result.installed_games
        self.assertEqual(game.game_id, 'atelier_sophie')
        self.assertEqual(game.app_id, '527270')
        self.assertEqual(game.library_path, library)
        self.assertEqual(game.install_path, install_path)
        self.assertEqual(game.build_id, '83921005')
        self.assertEqual(game.last_updated, 1743511000)
        self.assertEqual(game.size_on_disk, 2430432)

        portable = json.dumps(save_discovery.report(result), sort_keys=True)
        safe_game, = save_discovery.report(result)['installed_games']
        self.assertEqual(safe_game['build_id'], '83921005')
        self.assertEqual(safe_game['last_updated'], 1743511000)
        self.assertEqual(safe_game['size_on_disk'], 2430432)
        for local_path in (str(self.root), str(self.steam), str(library), str(install_path)):
            self.assertNotIn(local_path, portable)

    def test_missing_and_malformed_optional_metadata_keeps_valid_install_visible(self):
        install_path = self.install(
            self.steam,
            metadata='"LastUpdated" "not-a-timestamp" "SizeOnDisk" '
                     '"999999999999999999999999999999"',
        )

        result = self.scan()

        self.assertEqual(len(result.installed_games), 1)
        game, = result.installed_games
        self.assertEqual(game.install_path, install_path)
        self.assertEqual(game.library_path, self.steam)
        self.assertIsNone(game.build_id)
        self.assertIsNone(game.last_updated)
        self.assertIsNone(game.size_on_disk)
        self.assertIn('invalid_install_metadata_skipped', result.issues)

    def test_install_scan_can_skip_save_locations_and_rejects_non_boolean_flag(self):
        self.install(self.steam, metadata='"buildid" "83921005"')

        result = save_discovery.discover_saves(
            home=self.home,
            local_app_data=self.home / 'AppData/Local',
            roaming_app_data=self.home / 'AppData/Roaming',
            steam_roots=(self.steam,),
            include_locations=False,
        )

        self.assertEqual(len(result.installed_games), 1)
        self.assertEqual(result.installed_games[0].build_id, '83921005')
        self.assertEqual(result.locations, ())
        for invalid in (0, 1, None, 'false'):
            with self.subTest(value=invalid), self.assertRaises(SaveError):
                save_discovery.discover_saves(
                    home=self.home,
                    local_app_data=self.home / 'AppData/Local',
                    roaming_app_data=self.home / 'AppData/Roaming',
                    steam_roots=(self.steam,),
                    include_locations=invalid,
                )


if __name__ == '__main__':
    unittest.main()

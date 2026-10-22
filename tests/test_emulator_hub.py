"""Mocked integration checks for emulator discovery, launch, and save handoff."""
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from koei_editor.games.deception4_ps3 import parser as deception4
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import emulator_hub, emulator_hub_preferences
from koei_editor.shared.emulator_hub_gui import EmulatorHubWorkspace
from koei_editor.shared.emulator_provider_contract import EmulatorProvider
from tests import test_ps3_expansion as ps3_helpers
from tests.test_ps3_new_families import fixture as ps3_fixture


class EmulatorHubTests(unittest.TestCase):
    def test_provider_catalog_associates_only_exact_existing_platforms(self):
        catalog = emulator_hub.providers()
        self.assertGreaterEqual(len(catalog), 11)
        self.assertEqual(len({item.id for item in catalog}), len(catalog))
        for provider in catalog:
            self.assertIs(type(provider), EmulatorProvider)
            self.assertIs(provider.validate(), provider)
            self.assertTrue(provider.documentation)
            self.assertTrue(all(url.startswith('https://') for url in provider.documentation))
            for game in emulator_hub.games_for_provider(provider.id):
                self.assertIn(game.platform, provider.platforms)

        # PSP is discoverable/launchable, but the editor has no registered PSP
        # save profile and must not invent one for save qualification.
        self.assertEqual(emulator_hub.games_for_provider('ppsspp'), ())
        self.assertEqual(emulator_hub.games_for_provider('ppsspp', editors_only=True), ())
        self.assertEqual(emulator_hub.games_for_provider('dolphin'), ())

    def test_discovery_finds_mock_installation_from_path_without_executing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'rpcs3.exe'
            executable.write_bytes(b'mocked executable')

            def which(name, *, path=None):
                return str(executable) if name.casefold() == 'rpcs3.exe' else None

            with patch.object(emulator_hub, 'providers', return_value=(
                    next(item for item in emulator_hub.providers() if item.id == 'rpcs3'),)):
                found = emulator_hub.discover_installations(
                    environment={'PATH': directory}, which=which)

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].provider_id, 'rpcs3')
        self.assertEqual(found[0].discovered_by, 'PATH')
        self.assertEqual(found[0].executable, str(executable))

    def test_discovery_collects_every_existing_standard_data_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'mock.exe'
            first = root / 'first'
            second = root / 'second'
            executable.write_bytes(b'mocked executable')
            first.mkdir()
            second.mkdir()
            provider = EmulatorProvider(
                id='mock_console', name='Mock console', platforms=('PlayStation 3',),
                executable_names=('mock.exe',), install_candidates=(), config_candidates=(),
                data_candidates=('{ROOT_A}', '{ROOT_B}'), launch_style='gui',
                documentation=('https://example.invalid/docs',)).validate()
            with patch.object(emulator_hub, 'providers', return_value=(provider,)):
                found = emulator_hub.discover_installations(
                    environment={'PATH': directory, 'ROOT_A': str(first), 'ROOT_B': str(second)},
                    which=lambda name, *, path=None: str(executable) if name == 'mock.exe' else None)
        self.assertEqual(found[0].protected_data_paths, (str(first), str(second)))

    def test_manual_installation_requires_exact_provider_executable_family(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'Cemu.exe'
            data = Path(directory) / 'cemu-managed'
            executable.write_bytes(b'mocked executable')
            data.mkdir()
            self.assertEqual(emulator_hub.manual_installation('cemu', str(executable)).provider_id, 'cemu')
            manual = emulator_hub.manual_installation('cemu', str(executable), data_path=str(data))
            self.assertEqual(manual.protected_data_paths, (str(data),))
            with self.assertRaises(SaveError):
                emulator_hub.manual_installation('dolphin', str(executable))

    def test_cemu_documented_mlc_path_is_read_as_an_additional_protected_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            managed = root / 'custom-mlc'
            managed.mkdir()
            config = root / 'settings.xml'
            config.write_text(f'<content><mlc_path>{managed}</mlc_path></content>', encoding='utf-8')
            cemu = emulator_hub.provider_for('cemu')
            self.assertEqual(emulator_hub._cemu_config_data_paths(cemu, str(config)), (str(managed),))
            config.write_text('<!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>', encoding='utf-8')
            self.assertEqual(emulator_hub._cemu_config_data_paths(cemu, str(config)), ())
            config.write_bytes('<!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'.encode('utf-16'))
            self.assertEqual(emulator_hub._cemu_config_data_paths(cemu, str(config)), ())

    def test_discovery_adds_configured_cemu_mlc_to_all_protected_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'Cemu.exe'
            executable.write_bytes(b'mocked executable')
            managed = root / 'external-mlc'
            managed.mkdir()
            config = root / 'settings.xml'
            config.write_text(f'<content><mlc_path>{managed}</mlc_path></content>', encoding='utf-8')
            provider = replace(emulator_hub.provider_for('cemu'), install_candidates=(),
                               config_candidates=('{INSTALL_DIR}/settings.xml',), data_candidates=())
            with patch.object(emulator_hub, 'providers', return_value=(provider,)):
                found = emulator_hub.discover_installations(
                    environment={'PATH': directory},
                    which=lambda name, *, path=None: str(executable) if name.casefold() == 'cemu.exe' else None)

        self.assertEqual(found[0].configuration_paths, (str(config),))
        self.assertEqual(found[0].protected_data_paths, (str(managed),))

    def test_ppsspp_bounded_installed_txt_adds_custom_memstick_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'PPSSPPWindows64.exe'
            executable.write_bytes(b'mocked executable')
            memstick = root / 'custom-memstick'
            memstick.mkdir()
            (root / 'installed.txt').write_bytes(b'\xef\xbb\xbf' + str(memstick).encode('utf-8') + b'\n')
            ppsspp = emulator_hub.provider_for('ppsspp')
            self.assertEqual(emulator_hub._ppsspp_installed_data_paths(ppsspp, str(executable)),
                             (str(memstick),))
            (root / 'installed.txt').write_text('custom-memstick\n', encoding='utf-8')
            self.assertEqual(emulator_hub._ppsspp_installed_data_paths(ppsspp, str(executable)),
                             (str(memstick),))
            (root / 'installed.txt').write_bytes(b'x' * 2049)
            self.assertEqual(emulator_hub._ppsspp_installed_data_paths(ppsspp, str(executable)), ())

    def test_ppsspp_custom_memstick_precedes_default_hints_and_adds_its_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'PPSSPPWindows64.exe'
            executable.write_bytes(b'mocked executable')
            override = root / 'elsewhere' / 'memstick'
            override_config = override / 'PSP' / 'SYSTEM' / 'ppsspp.ini'
            override_config.parent.mkdir(parents=True)
            override_config.write_text('[General]\n', encoding='utf-8')
            (root / 'installed.txt').write_text('elsewhere/memstick\n', encoding='utf-8')

            config_paths, data_paths = emulator_hub._installation_hints(
                emulator_hub.provider_for('ppsspp'), str(executable), {})

        self.assertEqual(config_paths[0], str(override_config))
        self.assertEqual(data_paths[0], str(override))

    def test_launch_uses_documented_argv_without_shell_interpretation(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'Cemu.exe'
            content = Path(directory) / 'game ; & launch.iso'
            executable.write_bytes(b'mocked executable')
            content.write_bytes(b'mocked content')
            profile = emulator_hub.create_launch_profile(
                'cemu', str(executable), 'hyrule_warriors', str(content))
            popen = Mock(return_value=object())
            plan, process = emulator_hub.launch(profile, popen=popen)

        self.assertEqual(plan.argv, (str(executable), '-g', str(content.resolve())))
        self.assertTrue(plan.content_passed)
        popen.assert_called_once_with(list(plan.argv), cwd=str(executable.parent), shell=False)
        self.assertIsNotNone(process)

    def test_gui_only_profile_opens_emulator_without_game_path(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'Ryujinx.exe'
            content = Path(directory) / 'game.nsp'
            executable.write_bytes(b'mocked executable')
            content.write_bytes(b'mocked content')
            profile = emulator_hub.create_launch_profile(
                'ryujinx_compatible', str(executable), 'p5strikers_switch', str(content))
            popen = Mock(return_value=object())
            plan, _process = emulator_hub.launch(profile, popen=popen)

        self.assertEqual(plan.argv, (str(executable),))
        self.assertFalse(plan.content_passed)
        self.assertIn('GUI-only', plan.note)
        popen.assert_called_once_with([str(executable)], cwd=str(executable.parent), shell=False)

    def test_provider_specific_target_shapes_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vita_exe = root / 'Vita3K.exe'
            vita_exe.write_bytes(b'mocked executable')
            arbitrary = root / 'not-installed'
            arbitrary.mkdir()
            with self.assertRaisesRegex(SaveError, 'ux0/app'):
                emulator_hub.create_launch_profile('vita3k', str(vita_exe), 'dw8xl_vita', str(arbitrary))
            installed = root / 'ux0' / 'app' / 'PCSG00360'
            installed.mkdir(parents=True)
            self.assertEqual(emulator_hub.create_launch_profile(
                'vita3k', str(vita_exe), 'dw8xl_vita', str(installed)).content_path, str(installed))

            xenia_exe = root / 'xenia.exe'
            xenia_exe.write_bytes(b'mocked executable')
            invalid = root / 'game.bin'
            invalid.write_bytes(b'mocked content')
            with self.assertRaisesRegex(SaveError, r'\.xex or \.iso'):
                emulator_hub.create_launch_profile('xenia', str(xenia_exe),
                                                   'ninjagaiden2_x360', str(invalid))
            valid = root / 'game.XEX'
            valid.write_bytes(b'mocked content')
            self.assertEqual(emulator_hub.create_launch_profile(
                'xenia', str(xenia_exe), 'ninjagaiden2_x360', str(valid)).content_path, str(valid))

    def test_wrong_platform_missing_content_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'rpcs3.exe'
            content = Path(directory) / 'save.iso'
            executable.write_bytes(b'mocked executable')
            content.write_bytes(b'mocked content')
            with self.assertRaises(SaveError):
                emulator_hub.create_launch_profile('rpcs3', str(executable), 'project_zero_ps2', str(content))
            profile = emulator_hub.create_launch_profile('rpcs3', str(executable),
                                                         deception4.GAME_ID, str(content))
            content.unlink()
            with self.assertRaises(SaveError):
                emulator_hub.build_launch_plan(profile)

            content.write_bytes(b'mocked content')
            link = Path(directory) / 'game-link.iso'
            try:
                link.symlink_to(content)
            except (OSError, NotImplementedError):
                self.skipTest('Host cannot create symlinks')
            with self.assertRaises(SaveError):
                emulator_hub.create_launch_profile('rpcs3', str(executable), deception4.GAME_ID, str(link))

    def test_local_profiles_roundtrip_and_invalid_data_falls_back_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'pcsx2-qt.exe'
            content = Path(directory) / 'game.iso'
            executable.write_bytes(b'mocked executable')
            content.write_bytes(b'mocked content')
            profile = emulator_hub.create_launch_profile(
                'pcsx2', str(executable), 'project_zero_ps2', str(content))
            path = Path(directory) / 'prefs.json'
            settings = emulator_hub_preferences.add_profile(
                emulator_hub_preferences.HubPreferences(), profile)
            self.assertTrue(emulator_hub_preferences.save(settings, path))
            self.assertEqual(emulator_hub_preferences.load(path), settings)
            path.write_text('{"schema":1,"profiles":[],"profiles":[]}', encoding='utf-8')
            self.assertEqual(emulator_hub_preferences.load(path), emulator_hub_preferences.HubPreferences())

    def test_export_scan_qualifies_exact_profile_and_blocks_known_live_data_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exported = root / 'exported'
            exported.mkdir()
            managed_a = root / 'managed-a'
            managed_b = root / 'managed-b'
            managed_a.mkdir()
            managed_b.mkdir()
            source = exported / 'DATA.BIN'
            source.write_bytes(ps3_fixture(deception4))
            (exported / 'PARAM.SFO').write_bytes(
                ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))

            installation = emulator_hub.EmulatorInstallation(
                'rpcs3:mock', 'rpcs3', str(root / 'rpcs3.exe'), '', str(managed_a), 'PATH',
                (str(managed_a), str(managed_b)))
            with patch.object(emulator_hub, 'discover_installations', return_value=(installation,)):
                with self.assertRaisesRegex(SaveError, 'Select the active emulator-managed'):
                    emulator_hub.scan_export_folder(deception4.GAME_ID, exported, provider_id='rpcs3')
                result = emulator_hub.scan_export_folder(
                    deception4.GAME_ID, exported, provider_id='rpcs3',
                    active_data_root=str(managed_a))
                self.assertEqual(result.qualified_count, 1)
                self.assertEqual(result.entries[0].relative_path, 'DATA.BIN')

                with self.assertRaisesRegex(SaveError, 'outside emulator-managed'):
                    emulator_hub.scan_export_folder(
                        deception4.GAME_ID, exported, provider_id='rpcs3',
                        active_data_root=str(managed_a), protected_roots=(str(root),))
                for protected in (managed_a, managed_b):
                    with self.subTest(protected=protected), self.assertRaisesRegex(
                            SaveError, 'outside emulator-managed'):
                        emulator_hub.scan_export_folder(
                            deception4.GAME_ID, protected, provider_id='rpcs3',
                            active_data_root=str(managed_a),
                            protected_roots=(str(managed_a), str(managed_b)))
                with self.assertRaisesRegex(SaveError, 'outside emulator-managed'):
                    emulator_hub.scan_export_folder(
                        deception4.GAME_ID, root, provider_id='rpcs3',
                        active_data_root=str(managed_a),
                        protected_roots=(str(managed_a), str(managed_b)))
            with patch.object(emulator_hub, 'discover_installations', return_value=()):
                result = emulator_hub.scan_export_folder(
                    deception4.GAME_ID, exported, provider_id='rpcs3',
                    active_data_root=str(managed_a))
                self.assertEqual(result.qualified_count, 1)

            with self.assertRaisesRegex(SaveError, 'does not match this emulator'):
                emulator_hub.scan_export_folder('project_zero_ps2', exported, provider_id='rpcs3')
            with self.assertRaises(SaveError):
                emulator_hub.scan_export_folder(deception4.GAME_ID, exported, provider_id='dolphin')

    def test_qualified_export_handoff_rechecks_then_calls_normal_editor_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            managed = folder / 'managed'
            managed.mkdir()
            export_folder = folder / 'exports'
            export_folder.mkdir()
            save = export_folder / 'DATA.BIN'
            save.write_bytes(ps3_fixture(deception4))
            (export_folder / 'PARAM.SFO').write_bytes(
                ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))
            installation = emulator_hub.EmulatorInstallation(
                'rpcs3:mock', 'rpcs3', str(folder / 'rpcs3.exe'), '', str(managed), 'PATH', (str(managed),))
            with patch.object(emulator_hub, 'discover_installations', return_value=(installation,)):
                result = emulator_hub.scan_export_folder(deception4.GAME_ID, export_folder,
                                                         provider_id='rpcs3',
                                                         active_data_root=str(managed))
            entry = result.entries[0]
            selection = Mock(return_value=('0',))
            status = Mock()
            callback = Mock(return_value=True)
            workspace = object.__new__(EmulatorHubWorkspace)
            workspace.export_result = result
            workspace.export_game_id = deception4.GAME_ID
            workspace.export_tree = Mock(selection=selection)
            workspace.export_status = status
            workspace.open_saved_copy = callback
            workspace._export_busy = False

            def run_export(kind, operation):
                self.assertEqual(kind, 'open')
                path = operation(threading.Event())
                callback(deception4.GAME_ID, path)
                status.set('Opened through the selected game profile’s normal editor path.')

            workspace._start_export_operation = run_export
            with patch.object(emulator_hub, 'qualify_export', wraps=emulator_hub.qualify_export) as qualify:
                workspace.open_export_selected()

        self.assertEqual(qualify.call_count, 1)
        self.assertEqual(qualify.call_args.args, (result, entry))
        self.assertIsInstance(qualify.call_args.kwargs.get('cancel'), threading.Event)
        callback.assert_called_once_with(deception4.GAME_ID, save)
        status.set.assert_called_once()

    def test_scan_worker_result_clears_active_root_confirmation(self):
        workspace = object.__new__(EmulatorHubWorkspace)
        workspace._closed = False
        workspace._export_poll_id = 'scheduled'
        workspace._export_busy = True
        workspace._export_cancel = threading.Event()
        workspace._export_queue = queue.SimpleQueue()
        result = Mock(entries=(), qualified_count=0, stop_reason='complete')
        workspace._export_queue.put(('scan', result, None, False))
        workspace._active_export_provider_id = 'rpcs3'
        workspace._protected_root_by_provider = {'rpcs3': '/active-root'}
        workspace.protected_root_var = Mock()
        for name in ('export_provider_combo', 'export_game_combo', 'export_folder_entry',
                     'protected_root_entry', 'scan_export_button', 'open_export_button',
                     'export_tree', 'cancel_export_button', 'export_status'):
            setattr(workspace, name, Mock())
        workspace.export_tree.get_children.return_value = ()
        workspace._export_selected = Mock()

        workspace._poll_export_operation()

        self.assertEqual(workspace._protected_root_by_provider['rpcs3'], '')
        workspace.protected_root_var.set.assert_called_once_with('')
        workspace.export_status.set.assert_called_with('No compatible copied saves were found.')

    def test_destroy_cancels_pending_export_worker(self):
        workspace = object.__new__(EmulatorHubWorkspace)
        workspace._closed = False
        workspace._export_cancel = threading.Event()
        workspace._export_poll_id = 'scheduled'
        workspace.parent = Mock()

        workspace._on_destroy()

        self.assertTrue(workspace._closed)
        self.assertTrue(workspace._export_cancel.is_set())
        workspace.parent.after_cancel.assert_called_once_with('scheduled')


if __name__ == '__main__':
    unittest.main()

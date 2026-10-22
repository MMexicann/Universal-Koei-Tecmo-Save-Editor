"""Other emulator providers use only documented argv and mocked installs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from koei_editor.shared.emulator_provider_contract import EmulatorProvider
from koei_editor.shared.emulator_providers.other import PROVIDERS
from koei_editor.shared import emulator_hub


_BY_ID = {provider.id: provider for provider in PROVIDERS}


class OtherProviderCatalogTests(unittest.TestCase):
    def test_catalog_is_valid_and_maps_only_registered_platform_names(self):
        self.assertEqual(
            {provider.id for provider in PROVIDERS},
            {"azahar_3ds", "vita3k", "melonds", "xenia", "xemu"},
        )
        expected = {
            "azahar_3ds": ("Nintendo 3DS",),
            "vita3k": ("PlayStation Vita",),
            "melonds": ("Nintendo DS",),
            "xenia": ("Xbox 360 / Xenia",),
            "xemu": ("Original Xbox",),
        }
        for provider in PROVIDERS:
            with self.subTest(provider=provider.id):
                self.assertIs(type(provider), EmulatorProvider)
                self.assertIs(provider.validate(), provider)
                self.assertEqual(provider.platforms, expected[provider.id])
                self.assertTrue(provider.documentation)
                self.assertTrue(all(url.startswith("https://") for url in provider.documentation))

    def test_only_verified_title_launch_arguments_are_configured(self):
        self.assertEqual(_BY_ID["azahar_3ds"].launch_style, "gui")
        self.assertEqual(_BY_ID["vita3k"].launch_flag, ("--installed-path",))
        self.assertEqual(_BY_ID["melonds"].launch_style, "positional")
        self.assertEqual(_BY_ID["xenia"].launch_flag, ("--target",))
        self.assertEqual(_BY_ID["xemu"].launch_style, "gui")

    def test_discovery_finds_mocked_melonds_executable_without_running_it(self):
        with tempfile.TemporaryDirectory() as area:
            executable = Path(area) / "melonDS.exe"
            executable.write_bytes(b"mock executable")

            def which(name, *, path=None):
                return str(executable) if name == "melonDS.exe" else None

            with patch.object(emulator_hub, "providers", return_value=(_BY_ID["melonds"],)):
                found = emulator_hub.discover_installations(
                    environment={"PATH": area}, which=which)

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].provider_id, "melonds")
        self.assertEqual(found[0].executable, str(executable))
        self.assertEqual(found[0].discovered_by, "PATH")

    def test_launch_uses_documented_ds_rom_positional_argument(self):
        with tempfile.TemporaryDirectory() as area:
            executable = Path(area) / "melonDS.exe"
            content = Path(area) / "monster-rancher.nds"
            executable.write_bytes(b"mock executable")
            content.write_bytes(b"mock content")
            with patch.object(emulator_hub, "providers", return_value=(_BY_ID["melonds"],)):
                profile = emulator_hub.create_launch_profile(
                    "melonds", str(executable), "monster_rancher_ds", str(content))
                popen = Mock(return_value=object())
                plan, process = emulator_hub.launch(profile, popen=popen)

        self.assertEqual(plan.argv, (str(executable), str(content.resolve())))
        self.assertTrue(plan.content_passed)
        popen.assert_called_once_with(
            [str(executable), str(content.resolve())], cwd=str(executable.parent), shell=False)
        self.assertIsNotNone(process)

    def test_vita3k_installed_path_is_passed_as_separate_arguments(self):
        with tempfile.TemporaryDirectory() as area:
            executable = Path(area) / "Vita3K.exe"
            app = Path(area) / "ux0" / "app" / "PCSG00360"
            executable.write_bytes(b"mock executable")
            app.mkdir(parents=True)
            with patch.object(emulator_hub, "providers", return_value=(_BY_ID["vita3k"],)):
                profile = emulator_hub.create_launch_profile(
                    "vita3k", str(executable), "meruru_plus_vita", str(app))
                popen = Mock(return_value=object())
                plan, _ = emulator_hub.launch(profile, popen=popen)

        self.assertEqual(plan.argv, (str(executable), "--installed-path", str(app.resolve())))
        popen.assert_called_once_with(
            [str(executable), "--installed-path", str(app.resolve())],
            cwd=str(executable.parent), shell=False)

    def test_xenia_target_and_gui_only_providers_never_use_shell(self):
        with tempfile.TemporaryDirectory() as area:
            executable = Path(area) / "xenia.exe"
            iso = Path(area) / "ninja-gaiden-2.iso"
            executable.write_bytes(b"mock executable")
            iso.write_bytes(b"mock content")
            with patch.object(emulator_hub, "providers", return_value=(_BY_ID["xenia"],)):
                profile = emulator_hub.create_launch_profile(
                    "xenia", str(executable), "ninjagaiden2_x360", str(iso))
                popen = Mock(return_value=object())
                plan, _ = emulator_hub.launch(profile, popen=popen)

        self.assertEqual(plan.argv, (str(executable), "--target", str(iso.resolve())))
        popen.assert_called_once_with(
            [str(executable), "--target", str(iso.resolve())],
            cwd=str(executable.parent), shell=False)

        for provider_id, game_id in (("azahar_3ds", "hyrule_legends"),
                                     ("xemu", "ninja_gaiden_black_xbox")):
            with self.subTest(provider=provider_id), tempfile.TemporaryDirectory() as area:
                executable = Path(area) / _BY_ID[provider_id].executable_names[0]
                content = Path(area) / "selected-game.bin"
                executable.write_bytes(b"mock executable")
                content.write_bytes(b"mock content")
                with patch.object(emulator_hub, "providers", return_value=(_BY_ID[provider_id],)):
                    profile = emulator_hub.create_launch_profile(
                        provider_id, str(executable), game_id, str(content))
                    popen = Mock(return_value=object())
                    plan, _ = emulator_hub.launch(profile, popen=popen)
                self.assertEqual(plan.argv, (str(executable),))
                self.assertFalse(plan.content_passed)
                popen.assert_called_once_with([str(executable)], cwd=str(executable.parent), shell=False)


if __name__ == "__main__":
    unittest.main()

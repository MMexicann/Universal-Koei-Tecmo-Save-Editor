"""Metadata and mocked path checks for Nintendo emulator providers.

No emulator executable or player save is needed for these provider tests.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import PureWindowsPath
from unittest.mock import patch

from koei_editor.shared.emulator_provider_contract import EmulatorProvider
from koei_editor.shared.emulator_providers.nintendo import PROVIDERS


_ENV_TEMPLATE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


def _expand_template(template: str, environment: dict[str, str]) -> str:
    """Expand only known uppercase environment placeholders for test fixtures."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in environment:
            raise KeyError(name)
        return environment[name]

    return _ENV_TEMPLATE.sub(replace, template)


class NintendoProviderCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.providers = {provider.id: provider for provider in PROVIDERS}

    def test_records_validate_and_platforms_are_exact(self) -> None:
        self.assertEqual(set(self.providers), {"dolphin", "cemu", "ryujinx_compatible"})
        for provider in PROVIDERS:
            self.assertIs(type(provider), EmulatorProvider)
            self.assertIs(provider.validate(), provider)
            self.assertTrue(provider.documentation)
            self.assertTrue(all(url.startswith("https://") for url in provider.documentation))

        self.assertEqual(self.providers["dolphin"].platforms, ("GameCube", "Wii"))
        self.assertEqual(self.providers["cemu"].platforms, ("Wii U",))
        self.assertEqual(self.providers["ryujinx_compatible"].platforms, ("Nintendo Switch",))

    def test_launch_modes_use_only_documented_capabilities(self) -> None:
        dolphin = self.providers["dolphin"]
        self.assertEqual((dolphin.launch_style, dolphin.launch_flag), ("flag", ("-e",)))
        self.assertIn("-u option", dolphin.launch_note)

        cemu = self.providers["cemu"]
        self.assertEqual((cemu.launch_style, cemu.launch_flag), ("flag", ("-g",)))
        self.assertIn("--title-id/-t", cemu.launch_note)
        self.assertIn("--mlc/-m", cemu.launch_note)
        self.assertIn(r"{INSTALL_DIR}\portable\settings.xml", cemu.config_candidates)
        self.assertEqual(cemu.config_candidates[0], r"{INSTALL_DIR}\portable\settings.xml")
        self.assertEqual(cemu.data_candidates[0], r"{INSTALL_DIR}\portable\mlc01")

        ryujinx = self.providers["ryujinx_compatible"]
        self.assertEqual(ryujinx.executable_names, ("Ryujinx.exe",))
        self.assertIn(r"{INSTALL_DIR}\portable\Config.json", ryujinx.config_candidates)
        self.assertEqual(len(ryujinx.data_candidates), len(set(ryujinx.data_candidates)))
        self.assertEqual((ryujinx.launch_style, ryujinx.launch_flag), ("gui", ()))
        self.assertIn("Per-title launch is GUI-only", ryujinx.launch_note)
        self.assertIn("no stable", ryujinx.launch_note)
        self.assertIn("does not replay custom shortcut arguments", ryujinx.launch_note)

        self.assertIn(r"{INSTALL_DIR}\User\Config\Dolphin.ini", dolphin.config_candidates)

    def test_windows_path_templates_are_bounded_and_environment_only(self) -> None:
        environment = {
            "APPDATA": r"C:\Fixture\AppData\Roaming",
            "LOCALAPPDATA": r"C:\Fixture\AppData\Local",
            "PROGRAMFILES": r"C:\Program Files",
            "USERPROFILE": r"C:\Fixture",
            "INSTALL_DIR": r"C:\Program Files\Emulator",
        }
        with patch.dict(os.environ, environment, clear=False):
            for provider in PROVIDERS:
                candidates = (
                    provider.install_candidates
                    + provider.config_candidates
                    + provider.data_candidates
                )
                self.assertLessEqual(len(candidates), 16)
                for template in candidates:
                    self.assertLessEqual(len(template), 512)
                    self.assertNotIn("*", template)
                    self.assertNotIn("?", template)
                    self.assertNotIn("..", template)
                    expanded = _expand_template(template, environment)
                    self.assertTrue(PureWindowsPath(expanded).is_absolute(), expanded)

    def test_mocked_install_candidates_resolve_without_starting_binaries(self) -> None:
        """A small fake environment verifies deterministic discovery hints only."""
        environment = {
            "APPDATA": r"C:\Fixture\AppData\Roaming",
            "LOCALAPPDATA": r"C:\Fixture\AppData\Local",
            "PROGRAMFILES": r"C:\Program Files",
            "USERPROFILE": r"C:\Fixture",
        }
        mocked_files = {
            r"C:\Program Files\Dolphin-x64\Dolphin.exe",
            r"C:\Fixture\AppData\Local\Programs\Cemu\Cemu.exe",
            r"C:\Program Files\Ryujinx\Ryujinx.exe",
        }

        resolved = {
            provider.id: tuple(
                _expand_template(candidate, environment)
                for candidate in provider.install_candidates
                if _expand_template(candidate, environment) in mocked_files
            )
            for provider in PROVIDERS
        }
        self.assertEqual(
            resolved,
            {
                "dolphin": (r"C:\Program Files\Dolphin-x64\Dolphin.exe",),
                "cemu": (r"C:\Fixture\AppData\Local\Programs\Cemu\Cemu.exe",),
                "ryujinx_compatible": (r"C:\Program Files\Ryujinx\Ryujinx.exe",),
            },
        )


if __name__ == "__main__":
    unittest.main()

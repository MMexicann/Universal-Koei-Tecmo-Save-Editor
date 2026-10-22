"""Static, mocked-path checks for the documented Sony emulator providers."""

import unittest

from koei_editor.shared.emulator_providers.sony import PROVIDERS


class SonyEmulatorProviderTests(unittest.TestCase):
    def test_provider_ids_and_platforms_are_stable(self):
        self.assertEqual(
            tuple(provider.id for provider in PROVIDERS),
            ("rpcs3", "pcsx2", "ppsspp"),
        )
        self.assertEqual(
            {provider.id: provider.platforms for provider in PROVIDERS},
            {
                "rpcs3": ("PlayStation 3",),
                "pcsx2": ("PlayStation 2",),
                "ppsspp": ("PlayStation Portable",),
            },
        )

    def test_every_spec_validates_and_uses_a_positional_boot_target(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider.id):
                self.assertIs(provider.validate(), provider)
                self.assertEqual(provider.launch_style, "positional")
                self.assertEqual(provider.launch_flag, ())
                self.assertIn("positional", provider.launch_note.lower())

    def test_windows_candidates_are_bounded_named_templates(self):
        roots = ("{PROGRAMFILES}", "{APPDATA}", "{USERPROFILE}",
                 "{RPCS3_CONFIG_DIR}", "{INSTALL_DIR}")
        for provider in PROVIDERS:
            with self.subTest(provider=provider.id):
                self.assertTrue(provider.executable_names)
                self.assertTrue(provider.install_candidates)
                self.assertTrue(provider.config_candidates)
                self.assertTrue(provider.data_candidates)
                for collection in (
                    provider.install_candidates,
                    provider.config_candidates,
                    provider.data_candidates,
                ):
                    for candidate in collection:
                        self.assertLessEqual(len(candidate), 512)
                        self.assertTrue(candidate.startswith(roots), candidate)

    def test_documentation_links_are_authoritative_upstream_sources(self):
        expected_docs = {
            "rpcs3": {
                "https://github.com/RPCS3/rpcs3/blob/master/rpcs3/rpcs3.cpp",
                "https://github.com/RPCS3/rpcs3/blob/master/Utilities/File.cpp",
                "https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/vfs_config.h",
                "https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/vfs_config.cpp",
            },
            "pcsx2": {
                "https://github.com/PCSX2/pcsx2/blob/master/pcsx2-qt/QtHost.cpp",
                "https://github.com/PCSX2/pcsx2/blob/master/pcsx2/Pcsx2Config.cpp",
            },
            "ppsspp": {
                "https://github.com/hrydgard/ppsspp/blob/master/docs/command-line.md",
                "https://github.com/hrydgard/ppsspp/blob/master/Core/CmdLine.cpp",
                "https://github.com/hrydgard/ppsspp/blob/master/Windows/main.cpp",
                "https://github.com/hrydgard/ppsspp/blob/master/Core/Util/PathUtil.cpp",
            },
        }
        for provider in PROVIDERS:
            with self.subTest(provider=provider.id):
                self.assertEqual(set(provider.documentation), expected_docs[provider.id])

    def test_launch_notes_keep_emulator_state_files_out_of_save_handoff(self):
        notes = {provider.id: provider.launch_note.lower() for provider in PROVIDERS}
        self.assertIn("savestate", notes["rpcs3"])
        self.assertIn("-state and -statefile", notes["pcsx2"])
        self.assertIn("state files", notes["ppsspp"])
        self.assertIn("--decrypt", notes["rpcs3"])
        self.assertTrue(all("savedata" not in " ".join(p.data_candidates).lower()
                            for p in PROVIDERS if p.id != "ppsspp"))

    def test_rpcs3_paths_follow_portable_config_precedence_without_broad_appdata_roots(self):
        rpcs3 = next(provider for provider in PROVIDERS if provider.id == "rpcs3")
        self.assertEqual(rpcs3.config_candidates[0], r"{INSTALL_DIR}\portable\config\config.yml")
        self.assertIn(r"{INSTALL_DIR}\portable\config\vfs.yml", rpcs3.config_candidates)
        self.assertIn(r"{RPCS3_CONFIG_DIR}\config\vfs.yml", rpcs3.config_candidates)
        self.assertEqual(rpcs3.data_candidates[:2],
                         (r"{INSTALL_DIR}\portable\dev_hdd0", r"{RPCS3_CONFIG_DIR}\dev_hdd0"))
        self.assertNotIn(r"{APPDATA}\RPCS3", rpcs3.data_candidates)

    def test_ppsspp_includes_bounded_install_relative_roots(self):
        ppsspp = next(provider for provider in PROVIDERS if provider.id == "ppsspp")
        self.assertIn(r"{INSTALL_DIR}\memstick\PSP\SAVEDATA", ppsspp.data_candidates)
        self.assertFalse(any("installed.txt" in path for path in ppsspp.config_candidates))


if __name__ == "__main__":
    unittest.main()

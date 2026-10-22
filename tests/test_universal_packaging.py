"""Nested package build configuration and bundle privacy contracts."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tests import test_package_release as fixture
from tools import package_release as release

PROJECT = Path(__file__).resolve().parents[1]
BASE = 'src/koei_editor/'


class UniversalPackagingTests(fixture.PackagingTests):
    def setUp(self):
        super().setUp()
        self.add_sources({
            BASE + 'application.py': b"VERSION = '1.0'\nfrom .shared import adapter_contract, scalar_presentation, musou_presentations, preferences\n",
            BASE + 'shared/__init__.py': b'# Shared package\n',
            BASE + 'shared/adapter_contract.py': b'# Adapter contract\n',
            BASE + 'shared/scalar_presentation.py': b'# Scalar presentation\n',
            BASE + 'shared/musou_presentations.py': b'# Musou presentation\n',
            BASE + 'shared/preferences.py': b'# Preferences\n',
            BASE + 'games/__init__.py': b'# Game packages\n',
            BASE + 'games/origins/__init__.py': b'# Origins package\n',
            BASE + 'game_registry.py': b"Game(id='origins', editor_module='koei_editor.games.origins.origins_game_editor', parser_module='koei_editor.games.origins.origins_parser')\n",
            BASE + 'games/origins/origins_game_editor.py': b'from . import origins_parser\n',
            BASE + 'games/origins/origins_parser.py': b'from .origins_codec import decode\n',
            BASE + 'games/origins/origins_codec.py': b'# Codec\n',
            'docs/ORIGINS_FORMAT.md': b'# Proven native layout\n',
        })
        self.write_manifest()

    def test_universal_sources_cannot_omit_game_module_from_manifest(self):
        del self.sources[BASE + 'games/origins/origins_game_editor.py']
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Required public sources.*origins_game_editor.py'):
            release.verified_sources(self.root)

    def test_sources_require_runtime_contract_modules(self):
        for leaf in ('adapter_contract.py', 'scalar_presentation.py', 'musou_presentations.py', 'preferences.py'):
            name = BASE + 'shared/' + leaf
            original = self.sources.pop(name)
            self.write_manifest()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Required public sources.*' + leaf):
                release.verified_sources(self.root)
            self.sources[name] = original

    def test_registered_native_origins_requires_parser_and_codec_sources(self):
        for leaf in ('origins_parser.py', 'origins_codec.py'):
            name = BASE + 'games/origins/' + leaf
            original = self.sources.pop(name)
            self.write_manifest()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Required public sources.*' + leaf):
                release.verified_sources(self.root)
            self.sources[name] = original

    def test_reviewed_scaffold_sources_are_packaged_and_cannot_be_omitted(self):
        names = release.ADAPTER_TEMPLATE_FILES | release.PUBLIC_TEST_HELPERS
        self.add_sources({name: b'# Contributor scaffold\n' for name in names})
        self.write_manifest()
        with patch.object(release, 'verify_executable', return_value=1), \
                patch.object(release, 'verify_standalone', return_value=1):
            assets = release.package(self.root)
        with zipfile.ZipFile(assets[1]) as archive:
            for name in names:
                self.assertEqual(archive.read('UniversalKoeiTecmoSaveEditor-v1.0-Source/' + name), self.sources[name])
        for name in release.ADAPTER_TEMPLATE_FILES | {'tests/scalar_contract.py'}:
            original = self.sources.pop(name)
            self.write_manifest()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Required public sources'):
                release.verified_sources(self.root)
            self.sources[name] = original

    def test_standalone_adapted_codec_cannot_omit_or_change_its_license(self):
        codec = BASE + 'games/sophie2/atelier_sophie2_codec.py'
        notice = 'licenses/atelier-sophie2-save-editor-MIT.txt'
        self.add_sources({codec: b'# Existing MIT adaptation\n', notice: b'MIT adapted-code notice\n'})
        self.write_manifest()
        archive, blobs, module = self.archive_fixture()
        release.verify_executable(self.root, lambda _: archive)
        del archive.toc[notice]
        (self.runtime / '_internal' / notice).unlink()
        with self.assertRaisesRegex(ValueError, 'missing from executable'):
            release.verify_executable(self.root, lambda _: archive)
        self.write_runtime_resources()
        archive.toc[notice] = (0, 0, 0, 0, 'x')
        blobs[notice] = b'Incorrect notice'
        with self.assertRaisesRegex(ValueError, 'differs from manifest'):
            release.verify_executable(self.root, lambda _: archive)
        self.sources.pop(notice)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Required public sources.*atelier-sophie2-save-editor-MIT'):
            release.verified_sources(self.root)

    def test_native_team_ninja_cipher_requires_its_embedded_mit_notice(self):
        codec = BASE + 'research/katana/katana_codec.py'
        notice = 'licenses/katana-save-data-resigner-MIT.txt'
        self.add_sources({codec: b'# MIT-attributed native cipher\n',
                          notice: b'MIT cipher notice\n'})
        self.write_manifest()
        archive, blobs, _module = self.archive_fixture()
        release.verify_executable(self.root, lambda _: archive)
        del archive.toc[notice]
        (self.runtime / '_internal' / notice).unlink()
        with self.assertRaisesRegex(ValueError, 'missing from executable'):
            release.verify_executable(self.root, lambda _: archive)
        self.write_runtime_resources()
        archive.toc[notice] = (0, 0, 0, 0, 'x')
        blobs[notice] = b'Changed notice'
        with self.assertRaisesRegex(ValueError, 'differs from manifest'):
            release.verify_executable(self.root, lambda _: archive)
        self.sources.pop(notice)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Required public sources.*katana-save-data-resigner-MIT'):
            release.verified_sources(self.root)

    def test_failed_bundle_validation_prevents_creating_any_downloads(self):
        with patch.object(release, 'verify_executable', side_effect=ValueError('Private artifact')):
            with self.assertRaisesRegex(ValueError, 'Private artifact'):
                release.package(self.root)
        self.assertFalse((self.root / 'release').exists())

    def test_packaging_verifies_bundle_once_before_creating_downloads(self):
        def inspect(root):
            self.assertEqual(root, self.root.resolve())
            self.assertFalse((root / 'release').exists())
            return 1
        with patch.object(release, 'verify_executable', side_effect=inspect) as verifier, \
                patch.object(release, 'verify_standalone', side_effect=inspect) as standalone_verifier:
            assets = release.package(self.root)
        verifier.assert_called_once_with(self.root.resolve())
        standalone_verifier.assert_called_once_with(self.root.resolve())
        self.assertTrue(all(asset.exists() for asset in assets))

    def test_katana_dependency_requires_its_exact_embedded_license(self):
        codec = BASE + 'research/katana/katana_codec.py'
        notice = 'licenses/katana-save-data-resigner-MIT.txt'
        self.add_sources({codec: b'# Attributed native cipher primitive\n', notice: b'MIT Katana notice\n'})
        self.write_manifest()
        archive, blobs, _module = self.archive_fixture()
        release.verify_executable(self.root, lambda _: archive)
        blobs[notice] = b'Incorrect notice'
        with self.assertRaisesRegex(ValueError, 'differs from manifest'):
            release.verify_executable(self.root, lambda _: archive)
        del archive.toc[notice]
        (self.runtime / '_internal' / notice).unlink()
        with self.assertRaisesRegex(ValueError, 'missing from executable'):
            release.verify_executable(self.root, lambda _: archive)
        self.sources.pop(notice)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Required public sources.*katana-save-data-resigner-MIT'):
            release.verified_sources(self.root)

    def test_reviewed_research_documents_ship_only_in_source_download(self):
        names = {'docs/GAME_MECHANICS.md', 'docs/KOEI_FORMATS.md', 'docs/PC_EDITOR_ATTEMPTS.md', 'docs/PC_RESEARCH_RETRY.md'}
        self.add_sources({name: b'# Evidence\n' for name in names})
        self.write_manifest()
        with patch.object(release, 'verify_executable', return_value=1), \
                patch.object(release, 'verify_standalone', return_value=1):
            assets = release.package(self.root)
        with zipfile.ZipFile(assets[0]) as archive:
            prefix = 'UniversalKoeiTecmoSaveEditor-v1.0/'
            self.assertTrue(all(name.startswith(prefix) for name in archive.namelist()))
            self.assertFalse(any('/docs/' in name for name in archive.namelist()))
        with zipfile.ZipFile(assets[1]) as archive:
            for name in names:
                self.assertEqual(archive.read('UniversalKoeiTecmoSaveEditor-v1.0-Source/' + name), self.sources[name])


class WindowsBuildConfigurationTests(unittest.TestCase):
    def test_build_uses_one_package_launcher_and_explicit_game_modules(self):
        from tools import build_windows as build
        args = build.build_args()
        self.assertIn('--onedir', args)
        self.assertIn('--noupx', args)
        self.assertNotIn('--onefile', args)
        self.assertEqual(args[args.index('--contents-directory') + 1], '_internal')
        self.assertIn('--windowed', args)
        self.assertEqual(args[args.index('--name') + 1], 'UniversalKoeiTecmoSaveEditor-v' + build.VERSION)
        self.assertEqual(Path(args[-1]), PROJECT / 'launch.pyw')
        self.assertEqual(Path(args[args.index('--paths') + 1]), PROJECT / 'src')
        for game in build.ALL_ADAPTERS:
            for module in (game.editor_module, game.parser_module, game.scalar_backend):
                if module is not None:
                    self.assertTrue(module.startswith('koei_editor.'))
                    self.assertIn(module, args)
        self.assertEqual({source for source, target in build.DATA if target == 'koei_editor/data'},
                         {BASE + 'data/' + name for name in release.RUNTIME_DATA})

    def test_dual_formats_keep_the_same_modules_metadata_and_complete_licenses(self):
        from tools import build_windows as build
        portable = build.build_args()
        standalone = build.build_args(standalone=True)
        self.assertIn('--onefile', standalone)
        self.assertNotIn('--onedir', standalone)
        self.assertNotIn('--contents-directory', standalone)
        self.assertIn('--noupx', standalone)
        for option in ('--distpath', '--workpath', '--specpath'):
            self.assertNotEqual(portable[portable.index(option) + 1], standalone[standalone.index(option) + 1])
        self.assertEqual(Path(standalone[standalone.index('--distpath') + 1]), PROJECT / 'dist-standalone')
        for option in ('--add-data', '--hidden-import'):
            def values(args):
                return [args[index + 1] for index, value in enumerate(args) if value == option]
            self.assertEqual(values(portable), values(standalone))
        expected = {'LICENSE', 'docs/THIRD_PARTY_NOTICES.md', *release.RUNTIME_LICENSES,
                    'licenses/atelier-sophie2-save-editor-MIT.txt', 'licenses/katana-save-data-resigner-MIT.txt'}
        self.assertEqual({source for source, destination in build.DATA if destination == 'licenses'}, expected)
        self.assertEqual(standalone[-1], portable[-1])

    def test_application_build_and_project_have_matching_versions(self):
        from koei_editor import application
        self.assertEqual(release.version(PROJECT), application.VERSION)
        self.assertEqual(release.artifact_name(PROJECT), 'UniversalKoeiTecmoSaveEditor-v' + application.VERSION)

    def test_distinct_registered_scalar_backend_is_collected(self):
        from tools import build_windows as build
        game = SimpleNamespace(editor_module='koei_editor.games.new.gui', parser_module='koei_editor.games.new.reader',
                               scalar_backend='koei_editor.games.new.native',
                               workshop_module='koei_editor.games.new.workshop')
        with patch.object(build, 'ALL_ADAPTERS', (game,)), patch.object(build, 'ENDPOINTS', {}), \
                patch.object(build, 'RESEARCH_PROFILES', {}):
            args = build.build_args()
        modules = [args[index + 1] for index, value in enumerate(args) if value == '--hidden-import']
        self.assertEqual(set(modules), {game.editor_module, game.parser_module,
                                        game.scalar_backend, game.workshop_module})
        legacy_game = SimpleNamespace(editor_module='koei_editor.games.legacy.gui',
                                      parser_module='koei_editor.games.legacy.reader',
                                      scalar_backend=None)
        with patch.object(build, 'ALL_ADAPTERS', (legacy_game,)), patch.object(build, 'ENDPOINTS', {}), \
                patch.object(build, 'RESEARCH_PROFILES', {}):
            legacy_args = build.build_args()
        legacy_modules = [legacy_args[index + 1] for index, value in enumerate(legacy_args)
                          if value == '--hidden-import']
        self.assertEqual(set(legacy_modules), {legacy_game.editor_module, legacy_game.parser_module})

    def test_conversion_only_native_backends_are_collected_without_scalar_registration(self):
        from tools import build_windows as build
        for standalone in (False, True):
            args = build.build_args(standalone=standalone)
            modules = {args[i + 1] for i, value in enumerate(args) if value == '--hidden-import'}
            for endpoint in build.ENDPOINTS.values():
                if endpoint.conversion_only:
                    self.assertIn(endpoint.backend.__name__, modules)
                    self.assertNotIn(endpoint.id, {game.id for game in build.ALL_ADAPTERS})
            for profile in build.RESEARCH_PROFILES.values():
                self.assertIn(profile.backend.__name__, modules)
                self.assertNotIn(profile.id, {game.id for game in build.ALL_ADAPTERS})

    def test_publication_requires_a_tag_or_explicit_release_commit_and_native_build(self):
        workflow = (PROJECT / '.github/workflows/windows-release.yml').read_text()
        for required in ("github.ref_type == 'tag'", "github.ref_name == 'main' && contains(github.event.head_commit.message, '[release]')",
                         '"ref=refs/tags/$release_tag" -f "sha=$GITHUB_SHA"', 'needs: build',
                         'Release tag must match the application version.', 'python -m tools.package_release\n',
                         'sha256sum --check SHA256SUMS.txt', 'gh release create', '--verify-tag',
                         'python -m pip install -e .', 'python -m tools.build_windows', 'python -m koei_editor --smoke-test',
                         'tools/requirements/build.txt', '--notes-file docs/RELEASE_NOTES.md', "github.event_name == 'pull_request'"):
            self.assertIn(required, workflow)
        for forbidden in ('gh release edit', 'gh release upload', 'git push'):
            self.assertNotIn(forbidden, workflow)
        self.assertEqual(workflow.count('python -m tools.package_release\n'), 1)
        self.assertIn('python -m tools.package_release --verify-executable', workflow)
        self.assertIn('python -m tools.package_release --verify-standalone', workflow)
        self.assertIn("throw 'Bundle validation or local packaging failed.'", workflow)


if __name__ == '__main__':
    unittest.main()

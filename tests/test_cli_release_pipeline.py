"""Console packaging and real PowerShell smoke guards; never execute fixture EXEs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch
import zipfile

from tests import test_package_release as fixture
from tools import build_windows as build
from tools import package_release as release

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/smoke_cli_windows.ps1'
PWSH = shutil.which('pwsh')


class CliPackagingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.PackagingTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root

    def test_console_mode_is_separate_and_preserves_complete_gui_dependencies_and_notices(self):
        cli = build.build_args(ROOT, cli=True)
        self.assertIn('--onefile', cli)
        self.assertIn('--console', cli)
        self.assertNotIn('--windowed', cli)
        self.assertEqual(cli[cli.index('--name') + 1], release.artifact_name(ROOT) + '-CLI')
        self.assertEqual(Path(cli[-1]), ROOT / 'src/koei_editor/cli.py')
        self.assertEqual(Path(cli[cli.index('--distpath') + 1]), ROOT / 'dist-cli')
        for gui in (build.build_args(ROOT), build.build_args(ROOT, standalone=True)):
            self.assertIn('--windowed', gui)
            self.assertNotIn('--console', gui)
            for flag in ('--hidden-import', '--add-data', '--exclude-module', '--copy-metadata'):
                expected = {gui[i + 1] for i, value in enumerate(gui) if value == flag}
                actual = {cli[i + 1] for i, value in enumerate(cli) if value == flag}
                self.assertLessEqual(expected, actual)
        with self.assertRaises(ValueError):
            build.build_args(ROOT, standalone=True, cli=True)

    def test_console_payload_verification_requires_same_complete_embedded_runtime(self):
        archive, blobs, _ = self.fixture.standalone_archive_fixture()
        shutil.rmtree(self.fixture.runtime)
        release.standalone_executable_path(self.root).unlink()
        self.assertEqual(release.verify_cli(self.root, lambda _: archive), len(blobs))
        for name in ('python314.dll', 'licenses/LICENSE', 'licenses/THIRD_PARTY_NOTICES.md',
                     'koei_editor/data/game_metadata.json', *release.RUNTIME_LICENSES,
                     *release.TRIMESH_RESOURCES, *release.RUNTIME_DEPENDENCY_METADATA):
            entry = archive.toc.pop(name)
            with self.subTest(missing=name), self.assertRaises(ValueError):
                release.verify_cli(self.root, lambda _: archive)
            archive.toc[name] = entry

    def test_gui_subsystem_wrong_machine_and_truncated_pe_cannot_be_console_download(self):
        path = release.cli_executable_path(self.root)
        original = path.read_bytes()
        machine = bytearray(original)
        machine[0x84:0x86] = (0x14c).to_bytes(2, 'little')
        for data in (self.fixture.console_pe(2), bytes(machine), b'MZ incomplete', original[:180]):
            with self.subTest(size=len(data)):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    release._cli_snapshot(self.root)

    def test_console_archive_privacy_and_source_change_checks_are_not_bypassed(self):
        archive, _, module = self.fixture.standalone_archive_fixture()
        module[0] = b'/' + b'home' + b'/fictional-owner/private'
        with self.assertRaisesRegex(ValueError, 'Personal home path'):
            release.verify_cli(self.root, lambda _: archive)
        module[0] = b'public module'
        path = release.cli_executable_path(self.root)
        def changed(_):
            path.write_bytes(path.read_bytes() + b'changed during inspection')
            return archive
        with self.assertRaisesRegex(ValueError, 'CLI executable changed'):
            release.verify_cli(self.root, changed)

    def test_invalid_or_changing_console_prevents_any_release_output(self):
        for verifier in (ValueError('CLI runtime incomplete'),
                         lambda _: release.cli_executable_path(self.root).write_bytes(self.fixture.console_pe() + b'changed')):
            with patch.object(release, 'verify_executable', return_value=1), \
                    patch.object(release, 'verify_standalone', return_value=1), \
                    patch.object(release, 'verify_cli', side_effect=verifier):
                with self.assertRaises(ValueError):
                    release.package(self.root)
            self.assertFalse((self.root / 'release').exists())

    def test_console_is_exact_separate_download_and_is_not_nested_in_portable_zip(self):
        with patch.object(release, 'verify_executable', return_value=1), \
                patch.object(release, 'verify_standalone', return_value=1), \
                patch.object(release, 'verify_cli', return_value=1):
            assets = release.package(self.root)
        self.assertEqual(len(assets), 5)
        self.assertEqual(assets[3].name, release.artifact_name(self.root) + '-CLI.exe')
        self.assertEqual(assets[3].read_bytes(), release.cli_executable_path(self.root).read_bytes())
        with zipfile.ZipFile(assets[0]) as archive:
            self.assertFalse(any(name.endswith('-CLI.exe') for name in archive.namelist()))
        checksums = assets[4].read_text().splitlines()
        self.assertEqual(checksums, [hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name for p in assets[:4]])

    def test_official_cli_execution_follows_payload_and_defender_checks(self):
        workflow = (ROOT / '.github/workflows/windows-release.yml').read_text()
        build_job = workflow.split('\n  build:\n', 1)[1].split('\n  prepare_release:\n', 1)[0]
        build_step = build_job.index('python -m tools.build_windows --cli')
        verify = build_job.index('python -m tools.package_release --verify-cli')
        scan = build_job.index('-Path $cli -ReportPath defender-reports/cli-runtime.json')
        execute = build_job.index('./tools/smoke_cli_windows.ps1 -Path $cli')
        package = build_job.index('python -m tools.package_release\n')
        self.assertLess(build_step, verify)
        self.assertLess(verify, scan)
        self.assertLess(scan, execute)
        self.assertLess(execute, package)
        cli_step = build_job.split('- name: Verify bounded headless console CLI startup and JSON inventories', 1)[1].split('- name: Package verified', 1)[0]
        self.assertIn('timeout-minutes: 6', cli_step)
        # Five60-second commands plus10-second process cleanup fit the outer budget.
        self.assertGreater(6 * 60, 5 * 60 + 10)
        self.assertIn('cli_runtime=$cliRuntime; cli=$cliFinal', build_job)
        self.assertIn('$cliRuntime.inputs[0].sha256 -ne $cliFinal.inputs[0].sha256', build_job)


@unittest.skipUnless(PWSH, 'Actual PowerShell runtime unavailable.')
class CliSmokePowerShellTests(unittest.TestCase):
    """Run the actual helper with a retained-process double, not a fixture binary."""

    def run_helper(self, scenario='valid'):
        with tempfile.TemporaryDirectory() as directory:
            area = Path(directory)
            executable = area / 'procedural.exe'
            executable.write_bytes(b'procedural fixture, never executed')
            fixture_directory = area / 'procedural copy folder'
            fixture_directory.mkdir()
            fixture_path = fixture_directory / 'COPY.dat'
            fixture_bytes = b'procedural copied save bytes, never executed'
            fixture_path.write_bytes(fixture_bytes)
            expected = dict(version='1.0', game_ids=['one', 'two'], platform_count=2, route_ids=['one-to-two'])
            (area / 'expected.json').write_text(json.dumps(expected))
            games = dict(schema='koei-toolkit-games', schema_version=1, read_only=True,
                         in_game_verified=False, profile_count=2, platform_count=2,
                         games=[dict(id='one'), dict(id='two')])
            routes = dict(schema='koei-toolkit-routes', schema_version=1, read_only=True,
                          in_game_verified=False, route_count=1, routes=[dict(id='one-to-two')])
            if scenario == 'duplicate_games':
                games['games'][1]['id'] = 'one'
            if scenario == 'case_only_id':
                games['games'][0]['id'] = 'ONE'
            if scenario == 'string_claim':
                games['read_only'] = 'true'
            if scenario == 'wrong_route':
                routes['routes'][0]['id'] = 'foreign-route'
            inspected_hash = hashlib.sha256(fixture_bytes).hexdigest()
            if scenario == 'fields_wrong_hash':
                inspected_hash = '0' * 64
            data = dict(help='games routes help', version='Universal Koei Tecmo Game Toolkit ' + ('9.9' if scenario == 'wrong_version' else '1.0'),
                        games=json.dumps(games), routes=json.dumps(routes),
                        fields=json.dumps(dict(success=True, status='inspected', game_id='dw8xl',
                                               source_sha256=inspected_hash,
                                               fields=[dict(field='gold', kind='integer', value=50)])))
            (area / 'outputs.json').write_text(json.dumps(data))
            harness = area / 'harness.ps1'
            harness.write_text(textwrap.dedent('''
                $ErrorActionPreference = 'Stop'
                Add-Type @'
                using System;
                using System.IO;
                using System.Threading;
                public sealed class CliSmokeProcess : IDisposable {
                    public bool HasExited {get; private set;}
                    public int ExitCode {get {return Environment.GetEnvironmentVariable("SCENARIO") == "exit_error" ? 2 : 0;}}
                    public bool WaitForExit(int milliseconds) {
                        string scenario = Environment.GetEnvironmentVariable("SCENARIO");
                        if ((scenario == "timeout" || scenario == "overflow") && !HasExited) {
                            Thread.Sleep(Math.Min(milliseconds, 20)); return false;
                        }
                        HasExited = true; return true;
                    }
                    public void Kill(bool tree) {HasExited = true; File.AppendAllText(Environment.GetEnvironmentVariable("CLEANUP"), "kill:" + tree + "\\n");}
                    public void Dispose() {File.AppendAllText(Environment.GetEnvironmentVariable("CLEANUP"), "dispose\\n");}
                }
                '@
                function Start-Process {
                    param($FilePath, [string[]]$ArgumentList, $WindowStyle, $RedirectStandardOutput,
                          $RedirectStandardError, [switch]$PassThru)
                    $name = switch ($ArgumentList[0]) {'--help' {'help'} '--version' {'version'} default {$ArgumentList[0]}}
                    $outputs = Get-Content -LiteralPath $env:OUTPUTS -Raw | ConvertFrom-Json
                    $value = $outputs.$name
                    if ($env:SCENARIO -eq 'overflow') { $value = 'x' * 524289 }
                    [IO.File]::WriteAllText($RedirectStandardOutput, $value)
                    [IO.File]::WriteAllText($RedirectStandardError, $(if ($env:SCENARIO -eq 'stderr') {'unexpected error'} else {''}))
                    if ($env:SCENARIO -eq 'changed' -and $name -eq 'routes') {
                        [IO.File]::AppendAllText($FilePath, 'changed during execution')
                    }
                    if ($name -eq 'fields') {
                        if ($ArgumentList[-1] -notmatch '^".*procedural copy folder.*"$') { throw 'Fixture argument was not quoted for Windows.' }
                        if ($env:SCENARIO -eq 'fixture_changed') { [IO.File]::AppendAllText($env:FIXTURE, 'unexpected edit') }
                        if ($env:SCENARIO -eq 'fixture_output') { [IO.File]::WriteAllText((Join-Path ([IO.Path]::GetDirectoryName($env:FIXTURE)) 'unexpected.dat'), 'unexpected output') }
                    }
                    return [CliSmokeProcess]::new()
                }
                & $env:SMOKE_HELPER -Path $env:FAKE_EXE -ExpectedInventoryPath $env:EXPECTED -FixturePath $env:FIXTURE -ReportPath $env:REPORT -TimeoutSeconds 10
                exit $LASTEXITCODE
            '''))
            environment = dict(os.environ, SCENARIO=scenario, CLEANUP=str(area / 'cleanup.log'),
                               OUTPUTS=str(area / 'outputs.json'), SMOKE_HELPER=str(HELPER),
                               FAKE_EXE=str(executable), FIXTURE=str(fixture_path), EXPECTED=str(area / 'expected.json'), REPORT=str(area / 'report.json'))
            result = subprocess.run([PWSH, '-NoProfile', '-File', str(harness)], env=environment,
                                    capture_output=True, text=True, timeout=30)
            report = json.loads((area / 'report.json').read_text(encoding='utf-8-sig'))
            cleanup = (area / 'cleanup.log').read_text() if (area / 'cleanup.log').exists() else ''
            return result, report, cleanup

    def test_complete_read_only_inventory_and_version_smoke_passes(self):
        result, report, cleanup = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr + str(report))
        self.assertTrue(report['clean'])
        self.assertEqual([row['name'] for row in report['commands']], ['help', 'version', 'games', 'routes', 'fields'])
        self.assertEqual(report['sha256_before'], report['sha256_after'])
        self.assertEqual(cleanup.count('dispose'), 5)
        self.assertEqual(report['fixture_sha256_before'], report['fixture_sha256_after'])
        self.assertNotIn('kill', cleanup)

    def test_wrong_version_duplicate_ids_false_types_and_foreign_routes_fail(self):
        for scenario in ('wrong_version', 'duplicate_games', 'case_only_id', 'string_claim', 'wrong_route'):
            with self.subTest(scenario=scenario):
                result, report, _ = self.run_helper(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(report['clean'])
                self.assertTrue(report['errors'])

    def test_nonzero_error_output_and_binary_mutation_fail(self):
        for scenario in ('exit_error', 'stderr', 'changed'):
            with self.subTest(scenario=scenario):
                result, report, cleanup = self.run_helper(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(report['clean'])
                self.assertIn('dispose', cleanup)

    def test_fields_source_hash_mutation_and_output_files_are_rejected(self):
        for scenario in ('fields_wrong_hash', 'fixture_changed', 'fixture_output'):
            with self.subTest(scenario=scenario):
                result, report, _ = self.run_helper(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(report['clean'])
                self.assertTrue(report['errors'])

    def test_output_overflow_kills_only_the_retained_process_tree(self):
        result, report, cleanup = self.run_helper('overflow')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(report['commands'][0]['output_limit'])
        self.assertIn('kill:True', cleanup)
        self.assertIn('dispose', cleanup)

    def test_timeout_kills_retained_process_tree_and_reports_failure(self):
        result, report, cleanup = self.run_helper('timeout')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(report['commands'][0]['timed_out'])
        self.assertIn('kill:True', cleanup)
        self.assertIn('dispose', cleanup)


if __name__ == '__main__':
    unittest.main()

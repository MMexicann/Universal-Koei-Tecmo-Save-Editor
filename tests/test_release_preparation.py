"""Release workflow gates and mocked protected PR preparation; no network writes."""
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile

from tools.package_release import version

PROJECT = Path(__file__).resolve().parents[1]
WORKFLOW = PROJECT / '.github/workflows/windows-release.yml'


def job_block(name):
    text = WORKFLOW.read_text()
    match = re.search(r'^  ' + name + r':\n(.*?)(?=^  [a-z_]+:\n|\Z)', text, re.M | re.S)
    if match is None:
        raise AssertionError('Missing workflow job: ' + name)
    return match.group(1)


def preparation_script():
    block = job_block('prepare_release')
    return textwrap.dedent(block.split('        run: |\n', 1)[1])


class ReleasePreparationContracts(unittest.TestCase):
    def test_only_explicit_matching_preparation_branch_gets_write_permissions(self):
        workflow = WORKFLOW.read_text()
        self.assertIn('permissions:\n  contents: read\n', workflow)
        prepare = job_block('prepare_release')
        self.assertIn("github.event_name == 'push' && startsWith(github.ref_name, 'codex/release-v')", prepare)
        self.assertIn("contains(github.event.head_commit.message, '[release]')", prepare)
        self.assertIn('needs: build', prepare)
        self.assertIn('pull-requests: write', prepare)
        self.assertIn('actions: write', prepare)
        self.assertIn('test "$GITHUB_REF_NAME" = "codex/release-v$version"', prepare)
        for forbidden in ('--admin', 'gh pr review', 'gh api --method PATCH', 'git push', '--force'):
            self.assertNotIn(forbidden, preparation_script())
        self.assertNotIn('pull-requests: write', job_block('build'))

    def test_publish_dispatch_is_opt_in_main_only_and_pinned_to_tested_commit(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("default: false\n        type: boolean", workflow)
        build = job_block('build')
        self.assertIn("$env:RELEASE_REF_NAME -ne 'main'", build)
        self.assertIn('$env:RELEASE_EXPECTED_SHA -ne $env:RELEASE_COMMIT_SHA', build)
        self.assertIn('needs: tests', build)
        self.assertIn('python -m tools.run_tests --verify-reports test-results', build)
        self.assertIn('python -m tools.package_release\n', build)
        self.assertIn("throw 'Bundle validation or local packaging failed.'", build)
        release = job_block('release')
        self.assertIn("github.event_name == 'workflow_dispatch'", release)
        self.assertIn("github.ref_name == 'main' && inputs.publish", release)
        self.assertIn('needs: build', release)
        self.assertIn('sha256sum --check SHA256SUMS.txt', release)
        self.assertIn('-f "sha=$GITHUB_SHA"', release)
        self.assertIn('--verify-tag', release)
        self.assertNotIn('gh release edit', release)

    def test_full_suite_is_partitioned_and_failure_cannot_be_hidden_by_a_matrix(self):
        tests = job_block('tests')
        self.assertIn('fail-fast: false', tests)
        self.assertIn('shard: [0, 1, 2, 3]', tests)
        self.assertIn('--workers 2 --shards 4 --shard-index ${{ matrix.shard }}', tests)
        self.assertIn('--timings tools/test_timings.json', tests)
        self.assertIn('if: always()', tests)
        self.assertIn('if-no-files-found: error', tests)
        self.assertNotIn('continue-on-error', tests)
        build = job_block('build')
        self.assertIn('pattern: test-results-*', build)
        self.assertIn('merge-multiple: true', build)
        self.assertIn('Full test coverage or shard integrity validation failed.', build)
        self.assertNotIn('python -m unittest discover -s tests -v', build)

    def test_defender_scans_precede_execution_and_bind_publication_to_exact_assets(self):
        build = job_block('build')
        scan = build.index('-Path $bundle -ReportPath defender-reports/runtime.json')
        standalone_scan = build.index('-Path $standalone -ReportPath defender-reports/standalone-runtime.json')
        execute = build.index('./tools/smoke_windows.ps1 -Path $launcher -Format portable')
        package = build.index('python -m tools.package_release\n')
        archives = build.index('-Path $windowsZip -ReportPath defender-reports/windows-archive.json')
        self.assertLess(scan, execute)
        self.assertLess(standalone_scan, execute)
        self.assertLess(standalone_scan, build.index('./tools/smoke_windows.ps1 -Path $standalone -Format standalone'))
        for preflight in ('--verify-executable', '--verify-standalone'):
            self.assertLess(build.index(preflight), scan)
        self.assertLess(execute, package)
        self.assertLess(package, archives)
        self.assertNotIn('continue-on-error', build)
        self.assertIn('if ($LASTEXITCODE -ne 0)', build[scan:execute])
        self.assertIn('$pair.scan.inputs[0].sha256 -ne $hash', build)
        self.assertIn('$runtime.clean -ne $true', build)
        release = job_block('release')
        self.assertIn("report['commit'] == os.environ['GITHUB_SHA']", release)
        self.assertIn("python -I - <<'PY'", release)
        self.assertIn('def require(condition, message):', release)
        self.assertIn("scan['engine_ready'] is True", release)
        self.assertIn("scan['scan_exit_code'] == 0", release)
        self.assertIn("scan['inputs'] == scan['inputs_after']", release)
        self.assertIn("'sha256': digest", release)
        self.assertIn('DefenderScan-v$version.json', release)
        self.assertNotIn('release/*.exe', release)
        self.assertNotIn('release/*.zip', release)
        self.assertIn('release/UniversalKoeiTecmoSaveEditor-v$version.exe', release)


class DefenderArtifactEvidenceTests(unittest.TestCase):
    """Exercise the actual publication gate with fabricated scan evidence only."""

    def run_gate(self, scenario='valid'):
        release_version = version(PROJECT)
        prefix = f'UniversalKoeiTecmoSaveEditor-v{release_version}'
        block = job_block('release')
        script = textwrap.dedent(block.split("python -I - <<'PY'\n", 1)[1].split('\n          PY', 1)[0])
        with tempfile.TemporaryDirectory() as folder:
            area = Path(folder)
            root = area / 'release'
            root.mkdir()
            (area / 'pyproject.toml').write_text('[project]\nversion="' + release_version + '"\n')
            payload = b'procedural portable launcher bytes'
            standalone_bytes = b'procedural complete standalone bytes, distinct from portable launcher'
            sha = lambda data: hashlib.sha256(data).hexdigest()
            def clean_scan(name, data):
                inputs = [{'path': name, 'size': len(data), 'sha256': sha(data)}]
                return dict(baseline=False, clean=True, engine_ready=True, scan_exit_code=0,
                            maps_exit_code=0, inputs=inputs, inputs_after=inputs)
            report = dict(version=release_version, commit='a' * 40, assets={},
                          runtime=clean_scan(prefix + '.exe', payload),
                          standalone_runtime=clean_scan(prefix + '.exe', standalone_bytes),
                          standalone=clean_scan(prefix + '.exe', standalone_bytes))
            executable = prefix + '.exe'
            final_bytes = b'changed after startup qualification' if scenario == 'standalone_after_startup' else standalone_bytes
            (root / executable).write_bytes(final_bytes)
            report['standalone'] = clean_scan(executable, final_bytes)
            report['assets'][executable] = sha(final_bytes)
            if scenario == 'standalone_wrong_hash':
                changed = b'changed after final executable scan'
                (root / executable).write_bytes(changed)
                report['assets'][executable] = sha(changed)
            if scenario == 'standalone_unscanned':
                report['standalone']['scan_exit_code'] = None
            for suffix, key in (('Windows', 'windows_archive'), ('Source', 'source_archive')):
                name = f'{prefix}-{suffix}.zip'
                with zipfile.ZipFile(root / name, 'w') as archive:
                    if suffix == 'Windows':
                        data = b'changed after individual scan' if scenario == 'runtime_changed' else payload
                        archive.writestr(prefix + '/' + prefix + '.exe', data)
                        if scenario == 'root_clutter':
                            archive.writestr('README.txt', b'unscanned download clutter')
                    else:
                        archive.writestr('README.md', b'procedural reviewed source')
                data = (root / name).read_bytes()
                report[key] = clean_scan(name, data)
                report['assets'][name] = sha(data)
            if scenario == 'engine_unavailable':
                report['windows_archive']['engine_ready'] = False
            if scenario == 'baseline_mode':
                report['standalone']['baseline'] = True
            if scenario == 'extra_exe':
                (root / 'unscanned.exe').write_bytes(payload)
            report_file = root / f'DefenderScan-v{release_version}.json'
            report_file.write_text(json.dumps(report), encoding='utf-8')
            hashes = {**report['assets'], report_file.name: sha(report_file.read_bytes())}
            (root / 'SHA256SUMS.txt').write_text(''.join(digest + '  ' + name + '\n' for name, digest in hashes.items()), encoding='ascii')
            return subprocess.run([sys.executable, '-I', '-O', '-c', script], cwd=area,
                                  env=dict(os.environ, GITHUB_SHA='a' * 40, PYTHONOPTIMIZE='2'),
                                  capture_output=True, text=True, timeout=20)

    def test_complete_matching_dual_format_evidence_is_accepted_under_optimization(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rescanned_zip_cannot_replace_individually_scanned_runtime_bytes(self):
        result = self.run_gate('runtime_changed')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Published runtime differs', result.stderr)

    def test_unavailable_engine_baseline_mode_and_extra_executable_are_rejected(self):
        for scenario in ('engine_unavailable', 'baseline_mode', 'extra_exe'):
            with self.subTest(scenario=scenario):
                self.assertNotEqual(self.run_gate(scenario).returncode, 0)

    def test_wrong_unscanned_or_changed_standalone_executable_is_rejected(self):
        for scenario in ('standalone_wrong_hash', 'standalone_unscanned', 'standalone_after_startup'):
            with self.subTest(scenario=scenario):
                self.assertNotEqual(self.run_gate(scenario).returncode, 0)

    def test_portable_zip_rejects_unscanned_root_clutter_even_with_clean_zip_evidence(self):
        result = self.run_gate('root_clutter')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unexpected portable archive member', result.stderr)


@unittest.skipIf(os.name == 'nt' or not shutil.which('bash'), 'Mocked Ubuntu preparation job requires POSIX bash.')
class ReleasePreparationScriptTests(unittest.TestCase):
    def run_preparation(self, scenario='success', branch=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            mock = root / 'mock_gh.py'
            log = root / 'calls.jsonl'
            mock.write_text(textwrap.dedent('''
                import json, os, sys
                args = sys.argv[1:]
                with open(os.environ['MOCK_LOG'], 'a') as stream:
                    stream.write(json.dumps(args) + '\\n')
                scenario = os.environ['MOCK_SCENARIO']
                if args[:2] == ['pr', 'list']:
                    print('23' if os.environ.get('MOCK_CREATED') or scenario == 'existing' else '')
                elif args[:2] == ['pr', 'create']:
                    if scenario == 'creation_disabled':
                        sys.exit('Actions cannot create pull requests under repository settings.')
                    open(os.environ['MOCK_STATE'], 'w').write('created')
                    print('https://example.invalid/pull/23')
                elif args[:2] == ['pr', 'merge']:
                    if scenario in ('protection_blocked', 'head_changed'):
                        sys.exit('Repository rules or head commit prevent this merge.')
                elif args[:2] == ['pr', 'view']:
                    print('' if scenario == 'queued' else os.environ['MOCK_MERGED_SHA'])
                elif args[:1] == ['api']:
                    print('0' * 40 if scenario == 'main_moved' else os.environ['MOCK_MERGED_SHA'])
                elif args[:2] != ['workflow', 'run']:
                    sys.exit('Unexpected mock command')
            ''').replace("os.environ.get('MOCK_CREATED')", "os.path.exists(os.environ['MOCK_STATE'])"))
            wrapper = 'gh() { "$MOCK_PYTHON" "$MOCK_SCRIPT" "$@"; }\n'
            env = dict(os.environ, GITHUB_REF_TYPE='branch', GITHUB_REF_NAME=branch or 'codex/release-v' + version(PROJECT),
                       GITHUB_SHA='a' * 40, GITHUB_REPOSITORY='example/editor', GH_TOKEN='synthetic-only',
                       MOCK_PYTHON=sys.executable, MOCK_SCRIPT=str(mock), MOCK_LOG=str(log),
                       MOCK_STATE=str(root / 'created'), MOCK_SCENARIO=scenario, MOCK_MERGED_SHA='b' * 40)
            result = subprocess.run(['bash', '-c', wrapper + preparation_script()], cwd=PROJECT,
                                    env=env, capture_output=True, text=True, timeout=30)
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, calls

    def test_success_uses_reviewable_pr_normal_merge_and_explicit_main_dispatch(self):
        result, calls = self.run_preparation()
        self.assertEqual(result.returncode, 0, result.stderr)
        create = next(args for args in calls if args[:2] == ['pr', 'create'])
        self.assertEqual(create[create.index('--body-file') + 1], 'docs/RELEASE_NOTES.md')
        merge = next(args for args in calls if args[:2] == ['pr', 'merge'])
        self.assertIn('--squash', merge)
        self.assertEqual(merge[merge.index('--match-head-commit') + 1], 'a' * 40)
        dispatch = next(args for args in calls if args[:2] == ['workflow', 'run'])
        self.assertEqual(dispatch[dispatch.index('--ref') + 1], 'main')
        self.assertIn('publish=true', dispatch)
        self.assertIn('expected_sha=' + 'b' * 40, dispatch)
        self.assertNotIn('--admin', merge)

    def test_existing_review_is_reused_without_creating_another_pr(self):
        result, calls = self.run_preparation('existing')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(args[:2] == ['pr', 'create'] for args in calls))

    def test_near_matching_feature_branch_is_rejected_before_github_actions(self):
        result, calls = self.run_preparation(branch='codex/release-v' + version(PROJECT) + '-feature')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_disabled_pr_creation_or_protected_merge_never_dispatches_release(self):
        for scenario in ('creation_disabled', 'protection_blocked', 'head_changed', 'queued', 'main_moved'):
            result, calls = self.run_preparation(scenario)
            with self.subTest(scenario=scenario):
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(args[:2] == ['workflow', 'run'] for args in calls))
                self.assertFalse(any('--admin' in args for args in calls))


if __name__ == '__main__':
    unittest.main()

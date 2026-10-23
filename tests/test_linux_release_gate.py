"""Publication must wait for the exact trusted native Linux main build."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == 'nt' or not shutil.which('bash') or not shutil.which('jq'),
                 'The release job runs native POSIX bash and jq.')
class LinuxPublicationGateTests(unittest.TestCase):
    def run_gate(self, runs):
        workflow = (ROOT / '.github/workflows/windows-release.yml').read_text(encoding='utf-8')
        section = workflow.split('- name: Require native Linux qualification for the same main commit\n', 1)[1]
        script = textwrap.dedent(section.split('run: |\n', 1)[1].split('\n      -', 1)[0])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            environment = dict(os.environ, GITHUB_REPOSITORY='example/toolkit', GITHUB_SHA='a' * 40,
                               GITHUB_OUTPUT=str(output), MOCK_RUNS=json.dumps({'workflow_runs': runs}))
            result = subprocess.run(['bash', '-c',
                'gh() { printf "%s" "$MOCK_RUNS"; }\nsleep() { :; }\n' + script],
                env=environment, capture_output=True, text=True, timeout=30)
            return result, output.read_text() if output.exists() else ''

    @staticmethod
    def candidate(**changes):
        return dict(id=7, head_sha='a' * 40, head_branch='main', event='push',
                    status='completed', conclusion='success') | changes

    def test_exact_main_success_exports_only_qualified_run_id(self):
        result, output = self.run_gate([self.candidate()])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, 'run_id=7\n')

    def test_other_source_pull_request_and_other_branch_cannot_satisfy_gate(self):
        for candidate in (self.candidate(head_sha='b' * 40), self.candidate(event='pull_request'),
                          self.candidate(head_branch='contributor-branch')):
            with self.subTest(candidate=candidate):
                result, output = self.run_gate([candidate])
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output)

    def test_newest_failed_attempt_cannot_fall_back_to_earlier_success(self):
        result, output = self.run_gate([self.candidate(), self.candidate(id=8, conclusion='failure')])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output)

    def test_missing_and_unfinished_evidence_fail_closed(self):
        for runs in ([], [self.candidate(status='in_progress', conclusion=None)]):
            with self.subTest(runs=runs):
                result, output = self.run_gate(runs)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output)


if __name__ == '__main__':
    unittest.main()

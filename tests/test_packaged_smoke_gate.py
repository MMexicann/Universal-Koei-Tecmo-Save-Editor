"""Bounded packaged-startup contracts; procedural processes are not EXE proof."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/smoke_windows.ps1'
PWSH = shutil.which('pwsh')


class PackagedSmokeContracts(unittest.TestCase):
    def test_both_smokes_follow_unchanged_defender_gates_and_precede_packaging(self):
        source = (ROOT / '.github/workflows/windows-release.yml').read_text()
        step = source.split('- name: Build both Windows formats', 1)[1].split('- name: Scan every', 1)[0]
        gate = step.index("throw 'Defender rejected the standalone executable")
        portable = step.index('./tools/smoke_windows.ps1 -Path $launcher -Format portable')
        standalone = step.index('./tools/smoke_windows.ps1 -Path $standalone -Format standalone')
        packaging = step.index('python -m tools.package_release\n')
        self.assertLess(gate, portable)
        self.assertLess(portable, standalone)
        self.assertLess(standalone, packaging)
        self.assertNotIn('Start-Process', step)
        self.assertIn("if ($LASTEXITCODE -ne 0) { throw 'Packaged GUI startup failed", step)
        self.assertIn("if ($LASTEXITCODE -ne 0) { throw 'Standalone packaged GUI startup failed", step)
        self.assertIn('if: always()\n        with:\n          name: packaged-startup-diagnostics', source)

    def test_timeout_is_bounded_and_cleanup_uses_retained_process_tree(self):
        source = HELPER.read_text()
        self.assertIn('[ValidateRange(30, 300)][int]$TimeoutSeconds = 180', source)
        self.assertIn('$process.WaitForExit($TimeoutSeconds * 1000)', source)
        self.assertIn('$process.Kill($true)', source)
        self.assertNotIn('Stop-Process', source)
        self.assertNotIn('taskkill', source)
        self.assertNotIn('CommandLine', source)
        self.assertIn('-RedirectStandardOutput $stdout -RedirectStandardError $stderr', source)
        self.assertIn('Get-OwnedProcessIds $process.Id', source)
        self.assertIn('ids.Contains((int)pid)', source)
        self.assertIn('$report.clean = $false', source)

    @unittest.skipUnless(PWSH, 'Actual PowerShell parser unavailable.')
    def test_actual_powershell_parser_accepts_helper(self):
        command = ('$tokens=$null;$errors=$null;'
                   '[void][System.Management.Automation.Language.Parser]::ParseFile('
                   '$env:SMOKE_HELPER,[ref]$tokens,[ref]$errors);'
                   'if($errors.Count){$errors | ForEach-Object {Write-Error $_};exit 1}')
        result = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-Command', command],
                                env=dict(os.environ, SMOKE_HELPER=str(HELPER)),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def procedural_process(self, mode):
        # No executable is launched: the actual script runs with a process
        # double. Timeout records only the double's descendant and invokes its
        # retained Kill(true) method, preserving unrelated process IDs.
        command = r'''
function Start-Process {
    param($FilePath,$ArgumentList,$WindowStyle,$RedirectStandardOutput,$RedirectStandardError,[switch]$PassThru)
    'procedural stdout' | Set-Content $RedirectStandardOutput
    'procedural stderr' | Set-Content $RedirectStandardError
    $p=[pscustomobject]@{Id=900001;Handle=1;HasExited=($env:SMOKE_MODE -ne 'timeout');ExitCode=0}
    if($env:SMOKE_MODE -eq 'failure'){$p.ExitCode=7}
    $p | Add-Member ScriptMethod WaitForExit {param($milliseconds) return $this.HasExited}
    $p | Add-Member ScriptMethod Kill {param($tree)
        if($tree -ne $true){throw 'Whole owned tree required'}
        $this.HasExited=$true; 'owned' | Set-Content $env:SMOKE_KILL_MARKER
    }
    $p | Add-Member ScriptMethod Dispose {}
    return $p
}
function Get-CimInstance {
    [pscustomobject]@{ProcessId=900002;ParentProcessId=900001;Name='owned-child.exe'}
    [pscustomobject]@{ProcessId=900003;ParentProcessId=42;Name='unrelated.exe'}
}
& $env:SMOKE_HELPER -Path $env:SMOKE_EXE -Format portable -ReportPath $env:SMOKE_REPORT -TimeoutSeconds 30
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            executable = path / 'procedural.exe'
            executable.write_bytes(b'not executable; procedural process double only')
            report_path, kill = path / 'report.json', path / 'kill-marker'
            result = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-Command', command],
                                    env=dict(os.environ, SMOKE_HELPER=str(HELPER), SMOKE_MODE=mode,
                                             SMOKE_EXE=str(executable), SMOKE_REPORT=str(report_path),
                                             SMOKE_KILL_MARKER=str(kill)),
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0 if mode == 'success' else 1, result.stdout + result.stderr)
            report = json.loads(report_path.read_text(encoding='utf-8-sig'))
            self.assertEqual(report['clean'], mode == 'success')
            self.assertEqual(report['timed_out'], mode == 'timeout')
            self.assertEqual(kill.exists(), mode == 'timeout')
            self.assertEqual(report['phase'], 'completed')
            self.assertTrue((path / 'portable-smoke.stdout.log').is_file())
            self.assertTrue((path / 'portable-smoke.stderr.log').is_file())
            if mode == 'timeout':
                self.assertEqual([p['pid'] for p in report['owned_processes']], [900002])
            else:
                self.assertEqual(report['exit_code'], 7 if mode == 'failure' else 0)

    @unittest.skipUnless(PWSH and os.name == 'nt', 'Windows procedural PowerShell check unavailable.')
    def test_success_and_nonzero_exit_and_timeout_are_fail_closed(self):
        for mode in ('success', 'failure', 'timeout'):
            with self.subTest(mode=mode):
                self.procedural_process(mode)


if __name__ == '__main__':
    unittest.main()

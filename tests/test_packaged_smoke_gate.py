"""Bounded packaged-startup contracts; procedural processes are not EXE proof."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/smoke_windows.ps1'
PWSH = shutil.which('pwsh')


class PackagedSmokeContracts(unittest.TestCase):
    def test_individual_phases_are_named_bounded_and_success_gated(self):
        source = (ROOT / '.github/workflows/windows-release.yml').read_text()
        expected = (
            ('Build both Windows formats and verify frozen payloads', 10),
            ('Scan portable runtime with active Defender', 10),
            ('Scan standalone runtime with active Defender', 10),
            ('Verify bounded portable packaged startup', 4),
            ('Verify bounded standalone packaged startup', 4),
            ('Package verified Windows and source downloads', 5),
        )
        blocks = {}
        positions = []
        for name, minutes in expected:
            match = re.search(r'^      - name: ' + re.escape(name)
                              + r'\n(.*?)(?=^      - |\Z)', source, re.M | re.S)
            self.assertIsNotNone(match, name)
            block = blocks[name] = match.group(1)
            positions.append(match.start())
            self.assertIn(f'        timeout-minutes: {minutes}\n', block)
            self.assertIn('        run: |\n', block)
            self.assertNotIn('        if:', block)
            self.assertNotIn('continue-on-error', block)
        self.assertEqual(positions, sorted(positions))
        build = blocks[expected[0][0]]
        for command in ('python -m tools.build_windows\n', 'python -m tools.build_windows --standalone\n',
                        'python -m tools.package_release --verify-executable\n',
                        'python -m tools.package_release --verify-standalone\n'):
            self.assertEqual(build.count(command), 1)
        self.assertIn('$bundle = python -m tools.package_release --bundle-path', blocks[expected[1][0]])
        for index in (2, 4):
            self.assertIn('$standalone = python -m tools.package_release --standalone-path', blocks[expected[index][0]])
            self.assertIn("throw 'Standalone executable path validation failed.'", blocks[expected[index][0]])
        self.assertIn('$launcher = python -m tools.package_release --executable-path', blocks[expected[3][0]])
        build_job = source.split('\n  build:\n', 1)[1].split('\n  prepare_release:\n', 1)[0]
        self.assertIn('    timeout-minutes: 30\n', build_job)

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
        waits = re.findall(r'\$process\.WaitForExit\(([^)]*)\)', source)
        self.assertEqual(waits, ['$TimeoutSeconds * 1000', '10000'])
        self.assertIn('$process.Kill($true)', source)
        self.assertNotIn('Stop-Process', source)
        self.assertNotIn('taskkill', source)
        self.assertNotIn('CommandLine', source)
        self.assertIn('-RedirectStandardOutput $stdout -RedirectStandardError $stderr', source)
        self.assertIn('Get-OwnedProcessIds $process.Id', source)
        self.assertIn('Get-RootWindows $process.Id', source)
        self.assertIn('[PackagedSmokeWindows]::Read([int[]]@($RootPid))', source)
        self.assertNotIn('Get-OwnedWindows', source)
        self.assertIn('$rootCreationTime = $process.StartTime', source)
        self.assertIn('Name,CreationDate -OperationTimeoutSec 5', source)
        self.assertIn('$child.CreationDate -isnot [DateTime]', source)
        self.assertIn('$childCreated -lt $createdAt[$parentId]', source)
        self.assertIn('if ($ids.Count -ge 64) { break }', source)
        self.assertIn('ids.Contains((int)pid)', source)
        self.assertIn('SendMessageTimeout(hwnd, 0x000D', source)
        self.assertIn('text, 3, 250, out result)', source)
        self.assertIn('return visited < 64;', source)
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
    $p=[pscustomobject]@{Id=900001;Handle=1;HasExited=($env:SMOKE_MODE -ne 'timeout');ExitCode=0;StartTime=[DateTime]::UtcNow.AddMinutes(-1)}
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
    [pscustomobject]@{ProcessId=900002;ParentProcessId=900001;Name='owned-child.exe';CreationDate=[DateTime]::UtcNow.AddSeconds(-30)}
    [pscustomobject]@{ProcessId=900003;ParentProcessId=42;Name='unrelated.exe';CreationDate=[DateTime]::UtcNow.AddSeconds(-30)}
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
            self.assertEqual(report['window_text_scope'], 'retained_root_only')
            self.assertTrue((path / 'portable-smoke.stdout.log').is_file())
            self.assertTrue((path / 'portable-smoke.stderr.log').is_file())
            if mode == 'timeout':
                self.assertEqual([p['pid'] for p in report['owned_processes']], [900002])
                self.assertFalse(any(error.startswith('Owned-window diagnostics:') for error in report['errors']),
                                 report['errors'])
            else:
                self.assertEqual(report['exit_code'], 7 if mode == 'failure' else 0)

    @unittest.skipUnless(PWSH and os.name == 'nt', 'Windows procedural PowerShell check unavailable.')
    def test_success_and_nonzero_exit_and_timeout_are_fail_closed(self):
        for mode in ('success', 'failure', 'timeout'):
            with self.subTest(mode=mode):
                self.procedural_process(mode)

    @unittest.skipUnless(PWSH, 'Procedural PowerShell ancestry check unavailable.')
    def test_process_ancestry_rejects_reused_pids_unknown_dates_and_excess_children(self):
        command = r'''
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($env:SMOKE_HELPER,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Helper parse failed'}
$definition=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-OwnedProcessIds'},$true)
. ([ScriptBlock]::Create($definition.Extent.Text))
function Get-CimInstance { return $script:rows }
$rootTime=[DateTime]::SpecifyKind([DateTime]::new(2020,1,1),[DateTimeKind]::Utc)
function Row($id,$parent,$date) { [pscustomobject]@{ProcessId=$id;ParentProcessId=$parent;CreationDate=$date;Name='procedural.exe'} }
$script:rows=@(
    (Row 1000 1 $rootTime.AddSeconds(10)),
    (Row 2001 1000 $rootTime.AddSeconds(1)),
    (Row 2002 1000 $rootTime.AddSeconds(-10)),
    (Row 2003 2002 $rootTime.AddSeconds(5)),
    (Row 2004 2001 $rootTime.AddMilliseconds(500)),
    (Row 2005 2004 $rootTime.AddSeconds(3)),
    (Row 2006 1000 '2020-01-01T00:00:01Z'),
    (Row 2007 1000 $null),
    (Row 2008 1000 ([DateTime]::UtcNow.AddDays(1))),
    (Row 2009 1000 $rootTime.AddSeconds(2)),
    (Row 2009 1000 $rootTime.AddSeconds(2)),
    (Row 2010 2001 $rootTime.AddSeconds(2))
)
$report=@{owned_processes=@()}
$ids=Get-OwnedProcessIds 1000 $rootTime
if((@($ids | Sort-Object) -join ',') -ne '1000,2001,2010'){throw 'Timestamp ancestry admitted a stale or unknown owner'}
if(($report.owned_processes.pid -join ',') -ne '2001,2010'){throw 'Excluded process metadata leaked'}
$script:rows=@(1..80 | ForEach-Object { Row (4000+$_) 1000 $rootTime.AddSeconds($_) })
$report=@{owned_processes=@()}
$ids=Get-OwnedProcessIds 1000 $rootTime
if($ids.Count -ne 64 -or $report.owned_processes.Count -ne 63){throw 'Direct-child collection exceeded its strict bound'}
'''
        result = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-Command', command],
                                env=dict(os.environ, SMOKE_HELPER=str(HELPER)),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

"""Release scanner policy contracts; these are not real antivirus scan evidence.

Windows CI parses the PowerShell with its actual parser. The build job runs the
real engine on the complete runtime and the exact archives before publication.
"""
import os
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / 'tools' / 'scan_release.ps1'
POWERSHELL = shutil.which('pwsh') or os.environ.get('DEFENDER_PWSH_TEST_BINARY')


def executable_source():
    # Ignore commentary when enforcing the release tool's security policy.
    return '\n'.join(line for line in SCANNER.read_text().splitlines()
                     if not line.lstrip().startswith('#'))


class DefenderReleaseGateContracts(unittest.TestCase):
    def test_input_is_only_scanned_never_executed_and_scanner_is_authenticated(self):
        source = executable_source()
        invoked_variables = set(re.findall(r'&\s+\$(\w+)', source))
        self.assertEqual(invoked_variables, {'Command'})
        self.assertNotRegex(source, r'(?i)Start-Process|Invoke-Expression|\.\s+\$Path')
        self.assertIn('Get-AuthenticodeSignature -LiteralPath $candidate', source)
        self.assertIn("$signature.Status -ne 'Valid'", source)
        self.assertIn('Microsoft Corporation|Microsoft Windows', source)
        command = re.search(r'\$report.scan_arguments\s*=\s*@\(([^\n]+)\)', source).group(1)
        self.assertIn("'-Scan', '-ScanType', '3', '-File', $resolved", command)
        self.assertIn("'-DisableRemediation'", command)
        self.assertNotIn('-ReturnHR', command)

    def test_runner_settings_can_only_strengthen_protection_and_remove_exclusions(self):
        source = executable_source()
        self.assertNotRegex(source, r'(?i)Add-MpPreference|Set-MpPreference[^\n]*-Exclusion')
        preference = re.search(r'Set-MpPreference.*?(?=\n\s*Update-MpSignature)', source, re.S).group()
        for switch, value in re.findall(r'-(Disable\w+)\s+(\$\w+)', preference):
            with self.subTest(switch=switch):
                self.assertEqual(value.lower(), '$false')
        self.assertIn('-MAPSReporting Advanced', preference)
        self.assertIn('-SubmitSamplesConsent SendSafeSamples', preference)
        self.assertIn('Remove-MpPreference -ExclusionPath', source)
        self.assertNotRegex(source, r'(?i)Set-ItemProperty[^\n]*(?:TamperProtection|DisableAntiSpyware)')
        # Writing preferences is insufficient: the live state must reject
        # stopped/passive services and disabled real-time or cloud protection.
        self.assertIn("$State.service_status -ne 'Running'", source)
        self.assertIn("$status.AMRunningMode -ne 'Normal'", source)
        self.assertIn('-not $status.RealTimeProtectionEnabled', source)
        self.assertIn('$preferences.MAPSReporting -ne 2', source)
        self.assertIn('$State.exclusion_count -ne 0', source)

    def test_cloud_errors_and_native_scan_errors_cannot_be_reported_clean(self):
        source = executable_source()
        self.assertRegex(source, r'\$exitCode\s*=\s*1')
        self.assertRegex(source, r'clean\s*=\s*\$false')
        self.assertIn('@(\'-ValidateMapsConnection\')', source)
        self.assertRegex(source, r'if \(\$report.maps_exit_code -ne 0\)\s*\{\s*throw')
        self.assertIn('$nativeExitCode = $LASTEXITCODE', source)
        self.assertIn('$report.scan_exit_code -ne 0', source)
        # An old-baseline diagnostic may complete on detection, but candidate
        # detections must throw; native code 2 also includes scanner errors.
        error_branch = source.split("$report.verdict = 'detected_or_scan_error'", 1)[1].split("$report.verdict = 'clean'", 1)[0]
        self.assertRegex(error_branch, re.compile(r'if \(\$Baseline\).*?else \{ throw', re.S))
        success = source.index("$report.verdict = 'clean'")
        self.assertGreater(success, source.index('$report.scan_exit_code -ne 0'))
        self.assertGreater(success, source.index('Assert-DefenderReady $report.defender_after'))

    def test_entire_input_inventory_and_bytes_are_verified_after_scan(self):
        source = executable_source()
        self.assertIn('Get-ChildItem -LiteralPath $item.FullName -Recurse -Force', source)
        self.assertIn('Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256', source)
        self.assertIn('[IO.Path]::GetRelativePath', source)
        for key in ('path = $relative', 'size = $entry.Length', 'sha256 ='):
            self.assertIn(key, source)
        self.assertIn('$report.inputs = @(Get-InputSnapshot $Path)', source)
        self.assertIn('$report.inputs_after = @(Get-InputSnapshot $Path)', source)
        self.assertIn('$before -ne $after', source)
        self.assertIn("$report.verdict = 'input_changed_or_quarantined'", source)
        self.assertIn('$report.inputs.Count -eq 0', source)
        # Logging into the bundle or silent reparse-point traversal would make
        # its hash chain invalid; reparse-point inputs must be rejected.
        self.assertIn('[IO.FileAttributes]::ReparsePoint', source)
        self.assertNotIn('Copy-Item', source)
        self.assertNotIn('-Restore', source)

    def test_reports_survive_failures_and_never_dump_account_status(self):
        source = executable_source()
        self.assertIn('} finally {', source)
        finalizer = source.split('} finally {', 1)[1]
        self.assertIn('Write-ScanReport', finalizer)
        self.assertIn('$exitCode = 1', finalizer)
        self.assertIn('Tee-Object -FilePath $logFile -Append', source)
        self.assertIn('AntivirusSignatureVersion', source)
        self.assertIn('AntivirusSignatureLastUpdated', source)
        self.assertIn('AMEngineVersion', source)
        self.assertNotIn('ComputerID', source)
        self.assertNotIn('Get-MpPreference | ConvertTo-Json', source)

    @unittest.skipUnless(POWERSHELL, 'PowerShell parser is available in Windows CI.')
    def test_actual_powershell_parser_accepts_release_scanner(self):
        command = (
            '$tokens=$null; $errors=$null; '
            '[System.Management.Automation.Language.Parser]::ParseFile('
            '$env:DEFENDER_SCRIPT_TEST_PATH,[ref]$tokens,[ref]$errors) | Out-Null; '
            'if($errors.Count -ne 0){$errors | Out-String | Write-Host; exit 1}; exit 0'
        )
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                                env=dict(os.environ, DEFENDER_SCRIPT_TEST_PATH=str(SCANNER)),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(POWERSHELL, 'PowerShell is available in Windows CI.')
    def test_native_error_code_and_stdout_stderr_are_preserved(self):
        # Exercise only the native-command boundary with a harmless child
        # process. Its failure is a procedural vector, not a Defender verdict.
        command = (
            '$tokens=$null; $errors=$null; '
            '$ast=[System.Management.Automation.Language.Parser]::ParseFile('
            '$env:DEFENDER_SCRIPT_TEST_PATH,[ref]$tokens,[ref]$errors); '
            '$function=$ast.Find({param($node) '
            '$node -is [System.Management.Automation.Language.FunctionDefinitionAst] '
            '-and $node.Name -eq "Invoke-DefenderCommand"},$true); '
            '. ([ScriptBlock]::Create($function.Extent.Text)); '
            '$logFile=$env:DEFENDER_TEST_LOG; $ErrorActionPreference="Stop"; '
            '$PSNativeCommandUseErrorActionPreference=$false; '
            '$LASTEXITCODE=129; '
            '$actual=Invoke-DefenderCommand $env:DEFENDER_TEST_CHILD @('
            '"-NoProfile","-NonInteractive","-File",$env:DEFENDER_TEST_CHILD_SCRIPT); '
            'if($actual -ne 2){throw "Native failure was lost: $actual"}; '
            'exit 0'
        )
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder).resolve() / 'native.log'
            child = log.with_name('harmless-child.ps1')
            child.write_text("[Console]::Out.WriteLine('procedural-stdout')\n"
                             "[Console]::Error.WriteLine('procedural-stderr')\nexit 2\n", encoding='utf-8')
            result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                                    env=dict(os.environ, DEFENDER_SCRIPT_TEST_PATH=str(SCANNER),
                                             DEFENDER_TEST_CHILD=str(POWERSHELL), DEFENDER_TEST_LOG=str(log),
                                             DEFENDER_TEST_CHILD_SCRIPT=str(child)),
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = log.read_text(encoding='utf-8-sig')
            self.assertIn('procedural-stdout', output)
            self.assertIn('procedural-stderr', output)

    @unittest.skipUnless(POWERSHELL, 'PowerShell is available in Windows CI.')
    def test_stopped_passive_stale_and_disabled_cloud_states_are_rejected(self):
        # Synthetic policy inputs exercise the real predicate; accepting the
        # good vector does not imply an installed/scanning antivirus engine.
        now = datetime.now(timezone.utc)
        ready = {'service_status': 'Running', 'exclusion_count': 0,
                 'status': {'AMRunningMode': 'Normal', 'AMServiceEnabled': True,
                            'AntivirusEnabled': True, 'RealTimeProtectionEnabled': True,
                            'BehaviorMonitorEnabled': True, 'IoavProtectionEnabled': True,
                            'AMEngineVersion': 'procedural-engine', 'AMProductVersion': 'procedural-platform',
                            'AntivirusSignatureVersion': 'procedural-signature',
                            'AntivirusSignatureLastUpdated': now.isoformat()},
                 'preferences': {'MAPSReporting': 2, 'SubmitSamplesConsent': 1,
                                 'DisableBlockAtFirstSeen': False, 'DisableRealtimeMonitoring': False,
                                 'DisableBehaviorMonitoring': False, 'DisableIOAVProtection': False,
                                 'DisableScriptScanning': False, 'DisableArchiveScanning': False,
                                 'PUAProtection': 1}}
        vectors = [{'name': 'procedural-ready', 'state': ready, 'reject': False}]
        mutations = [('', 'service_status', 'Stopped'), ('', 'exclusion_count', 2),
                     ('status', 'AMRunningMode', 'Passive'), ('status', 'AMServiceEnabled', False),
                     ('status', 'AntivirusEnabled', False), ('status', 'RealTimeProtectionEnabled', False),
                     ('status', 'AntivirusSignatureVersion', ''),
                     ('status', 'AntivirusSignatureLastUpdated', (now - timedelta(days=3)).isoformat()),
                     ('status', 'AntivirusSignatureLastUpdated', (now + timedelta(days=1)).isoformat()),
                     ('preferences', 'MAPSReporting', 0), ('preferences', 'SubmitSamplesConsent', 2),
                     ('preferences', 'DisableArchiveScanning', True)]
        for index, (section, key, value) in enumerate(mutations):
            state = deepcopy(ready)
            (state[section] if section else state)[key] = value
            vectors.append({'name': f'rejected-{index}-{key}', 'state': state, 'reject': True})
        command = (
            '$tokens=$null; $errors=$null; '
            '$ast=[System.Management.Automation.Language.Parser]::ParseFile('
            '$env:DEFENDER_SCRIPT_TEST_PATH,[ref]$tokens,[ref]$errors); '
            '$function=$ast.Find({param($node) '
            '$node -is [System.Management.Automation.Language.FunctionDefinitionAst] '
            '-and $node.Name -eq "Assert-DefenderReady"},$true); '
            '. ([ScriptBlock]::Create($function.Extent.Text)); '
            '$vectors=Get-Content -LiteralPath $env:DEFENDER_TEST_VECTORS -Raw | ConvertFrom-Json; '
            'foreach($vector in $vectors){$rejected=$false; '
            'try{Assert-DefenderReady $vector.state}catch{$rejected=$true}; '
            'if($rejected -ne $vector.reject){throw "Incorrect readiness policy: $($vector.name)"}}; exit 0'
        )
        with tempfile.TemporaryDirectory() as folder:
            inputs = Path(folder).resolve() / 'readiness.json'
            inputs.write_text(json.dumps(vectors), encoding='utf-8')
            result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                                    env=dict(os.environ, DEFENDER_SCRIPT_TEST_PATH=str(SCANNER),
                                             DEFENDER_TEST_VECTORS=str(inputs)),
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(POWERSHELL and os.name != 'nt', 'Missing Windows Defender is tested on portable PowerShell.')
    def test_unavailable_engine_fails_with_hash_report_even_for_baseline(self):
        # On Linux the real Defender commands are absent. Running the helper
        # must fail before configuration; it must not manufacture a clean scan.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'input.txt'
            source.write_bytes(b'Harmless procedural input for missing-engine handling.')
            for baseline in (False, True):
                with self.subTest(baseline=baseline):
                    report = root / ('baseline.json' if baseline else 'candidate.json')
                    args = [POWERSHELL, '-NoProfile', '-NonInteractive', '-File', str(SCANNER),
                            '-Path', str(source), '-ReportPath', str(report)]
                    if baseline:
                        args.append('-Baseline')
                    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    state = json.loads(report.read_text(encoding='utf-8-sig'))
                    self.assertFalse(state['clean'])
                    self.assertFalse(state['engine_ready'])
                    self.assertEqual(state['verdict'], 'scanner_unavailable_or_failed')
                    self.assertEqual(state['inputs'], [{'path': source.name, 'size': source.stat().st_size,
                                                       'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}])


if __name__ == '__main__':
    unittest.main()

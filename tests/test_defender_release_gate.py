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


def procedural_ready_state():
    now = datetime.now(timezone.utc)
    return {'service_status': 'Running', 'exclusion_count': 0,
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


class DefenderReleaseGateContracts(unittest.TestCase):
    def run_preparation_procedure(self, procedure):
        command = r'''
            $ErrorActionPreference='Stop'
            $tokens=$null; $errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile(
                $env:DEFENDER_SCRIPT_TEST_PATH,[ref]$tokens,[ref]$errors)
            if($errors.Count -ne 0){throw 'Scanner parse failed.'}
            foreach($name in @('Get-PreparationFailure','Wait-DefenderPreparationService',
                              'Enable-DefenderProtection','Invoke-DefenderPreparation',
                              'Get-DefenderState','Assert-DefenderReady')) {
                $definition=$ast.Find({param($node)
                    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
                    $node.Name -eq $name},$true)
                . ([ScriptBlock]::Create($definition.Extent.Text))
            }
        ''' + procedure
        with tempfile.TemporaryDirectory() as folder:
            ready = Path(folder).resolve() / 'ready-state.json'
            ready.write_text(json.dumps(procedural_ready_state()), encoding='utf-8')
            result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                                    env=dict(os.environ, DEFENDER_SCRIPT_TEST_PATH=str(SCANNER),
                                             DEFENDER_TEST_READY_STATE=str(ready)),
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

    def test_preparation_retry_cannot_change_inputs_or_qualification(self):
        source = executable_source()
        preparation = source.split('function Get-PreparationFailure', 1)[1].split('function Get-DefenderCommand', 1)[0]
        self.assertIn('$attempt -le 2', preparation)
        self.assertIn('[ValidateRange(1, 120)][int]$TimeoutSeconds = 120', preparation)
        self.assertIn("$service.Status -eq 'Stopped'", preparation)
        self.assertNotIn("$service.Status -ne 'Running'", preparation)
        self.assertIn('-RequireQueries', preparation)
        self.assertIn('Get-DefenderState', preparation)
        self.assertNotRegex(preparation, r'\$report\.(?:inputs(?:_after)?|engine_ready|clean|verdict)\s*=')
        self.assertNotRegex(preparation, r'(?i)Stop-Service|Restart-Service|Restart-Computer')
        self.assertIn('if (-not $failure.transient_rpc -or $attempt -eq 2) { throw }', preparation)
        self.assertLess(source.index('    Invoke-DefenderPreparation\n'),
                        source.index('    $report.defender_after = Wait-DefenderReady\n'))

    @unittest.skipUnless(POWERSHELL, 'PowerShell is available in Windows CI.')
    def test_preparation_retry_recognizes_only_documented_rpc_codes(self):
        self.run_preparation_procedure(r'''
            $script:preparationCommand='Update-MpSignature MMPC'
            $vectors=@(
                @{exception=[Runtime.InteropServices.COMException]::new('RPC',-2147023170);
                  id='COM'; retry=$true},
                @{exception=[Exception]::new('Outer',
                    [Runtime.InteropServices.COMException]::new('RPC',-2147023174));
                  id='Nested'; retry=$true},
                @{exception=[ComponentModel.Win32Exception]::new(1727,'RPC');
                  id='Native'; retry=$true},
                @{exception=[Exception]::new('Generic provider exception');
                  id='HRESULT0x800706be,Update-MpSignature'; retry=$true},
                @{exception=[Exception]::new('Generic provider exception');
                  id='HRESULT 0x800706BA,Get-MpPreference'; retry=$true},
                @{exception=[Exception]::new('Generic provider exception');
                  id='0x800706bf'; retry=$true},
                @{exception=[Runtime.InteropServices.COMException]::new('Denied',-2147024891);
                  id='AccessDenied'; retry=$false},
                @{exception=[ComponentModel.Win32Exception]::new(5,'Denied');
                  id='AccessDenied'; retry=$false},
                @{exception=[Exception]::new('The remote procedure call failed.');
                  id='Generic'; retry=$false},
                @{exception=[Exception]::new('Signature download failed');
                  id='HRESULT0x80072ee2,Update-MpSignature'; retry=$false},
                @{exception=[Exception]::new('RPC-looking ID');
                  id='HRESULT0x800706bee,Update-MpSignature'; retry=$false},
                @{exception=[Exception]::new('Defender initialization');
                  id='HRESULT 0x800106ba,Get-MpPreference'; retry=$false; initializing=$true},
                @{exception=[Runtime.InteropServices.COMException]::new('Defender initialization',-2147416390);
                  id='COM'; retry=$false; initializing=$true},
                @{exception=[ComponentModel.Win32Exception]::new(-2147416390,'Defender initialization');
                  id='Native'; retry=$false; initializing=$true},
                @{exception=[Exception]::new('Operation failed: 0x800106ba');
                  id='Generic'; retry=$false},
                @{exception=[Exception]::new('Provider error');
                  id='HRESULT0x800106baa,Get-MpPreference'; retry=$false}
            )
            foreach($vector in $vectors) {
                $failure=[Management.Automation.ErrorRecord]::new($vector.exception,$vector.id,
                    [Management.Automation.ErrorCategory]::NotSpecified,$null)
                $details=Get-PreparationFailure $failure
                if($details.transient_rpc -ne $vector.retry -or
                   $details.defender_initializing -ne [bool]$vector.initializing -or
                   $details.command -ne $script:preparationCommand -or
                   $details.fully_qualified_error_id -ne $vector.id -or
                   $details.hresults.Count -lt 1) {
                    throw ('Incorrect RPC classification/diagnostics: '+$vector.id)
                }
            }
        ''')

    @unittest.skipUnless(POWERSHELL, 'PowerShell is available in Windows CI.')
    def test_provider_load_failure_only_waits_for_queries_after_confirmed_rpc_restart(self):
        self.run_preparation_procedure(r'''
            function Write-ScanReport {
                if($report.engine_ready -or $report.clean -or
                   (ConvertTo-Json -InputObject $report.inputs -Compress) -ne $script:originalInputs) {
                    throw 'Provider polling changed inputs or claimed qualification.'
                }
            }
            function Throw-ProviderFailure {
                param($Command,$Code='0x80041013')
                throw [Management.Automation.ErrorRecord]::new([Exception]::new('Procedural provider load failure'),
                    ('HRESULT '+$Code+','+$Command),[Management.Automation.ErrorCategory]::NotSpecified,$null)
            }
            function Get-Service {
                param($Name)
                if($script:mode -eq 'service-provider') {Throw-ProviderFailure 'Get-Service'}
                return [pscustomobject]@{Status='Running'}
            }
            function Start-Service {throw 'Provider polling restarted the service.'}
            function Get-DefenderState {
                $script:queries+=1
                if($script:mode -eq 'wrong-code') {Throw-ProviderFailure 'Get-MpComputerStatus' '0x800410131'}
                if($script:mode -eq 'message-only') {throw 'Provider load failure 0x80041013'}
                if($script:mode -ne 'recover' -or $script:queries -le 2) {
                    Throw-ProviderFailure 'Get-MpComputerStatus'
                }
                return Get-Content -LiteralPath $env:DEFENDER_TEST_READY_STATE -Raw | ConvertFrom-Json
            }
            function Enable-DefenderProtection {
                param($Timer,$TimeoutSeconds,$PollSeconds)
                $script:enableCalls+=1
                $script:preparationCommand='Update-MpSignature MMPC'
                if($script:mode -in @('enable-provider','signature-provider')) {
                    if($script:mode -eq 'enable-provider') {$script:preparationCommand='Get-MpPreference'}
                    Throw-ProviderFailure $script:preparationCommand
                }
                if($script:enableCalls -eq 1) {
                    throw [ComponentModel.Win32Exception]::new(1726,'Procedural RPC restart')
                }
            }
            foreach($mode in @('recover','expiry','enable-provider','signature-provider','service-provider',
                               'query-without-rpc','wrong-code','message-only')) {
                $script:mode=$mode; $script:queries=0; $script:enableCalls=0
                $report=[ordered]@{clean=$false;engine_ready=$false;preparation_attempts=0;
                    preparation_wait_seconds=0;preparation_observations=@();
                    inputs=@(@{path='original';size=7;sha256='original-hash'})}
                $script:originalInputs=ConvertTo-Json -InputObject $report.inputs -Compress
                $timeout=if($mode -eq 'expiry'){1}else{5}
                $failed=$false
                try {
                    if($mode -eq 'query-without-rpc') {
                        Wait-DefenderPreparationService -Timer ([Diagnostics.Stopwatch]::StartNew()) `
                            -TimeoutSeconds $timeout -PollSeconds 1 -RequireQueries
                    } else {Invoke-DefenderPreparation -TimeoutSeconds $timeout -PollSeconds 1}
                } catch {$failed=$true}
                $expectedCalls=if($mode -eq 'recover'){2}elseif($mode -eq 'query-without-rpc'){0}else{1}
                if($failed -ne ($mode -ne 'recover') -or $script:enableCalls -ne $expectedCalls -or
                   $report.preparation_attempts -ne $expectedCalls) {
                    throw ('Provider load error widened complete retry scope: '+$mode)
                }
                $waits=@($report.preparation_observations | Where-Object provider_query_wait)
                if($mode -in @('recover','expiry')) {
                    if($waits.Count -lt 1 -or @($waits | Where-Object transient_rpc).Count -ne 0 -or
                       @($waits | Where-Object { -not $_.provider_load_failure }).Count -ne 0) {
                        throw 'Provider settling lost its exact classification or diagnostics.'
                    }
                    if($mode -eq 'expiry' -and
                       ($report.preparation_wait_seconds -lt 1 -or
                        $report.preparation_observations[-1].outcome -ne 'settling_expired')) {
                        throw 'Provider polling bypassed the original settling budget.'
                    }
                } elseif($waits.Count -ne 0) {throw ('Provider polling escaped post-RPC query scope: '+$mode)}
                Write-ScanReport
            }
        ''')

    @unittest.skipUnless(POWERSHELL, 'PowerShell is available in Windows CI.')
    def test_preparation_settling_rechecks_service_after_queries_and_enforces_deadline(self):
        self.run_preparation_procedure(r'''
            function Write-ScanReport {}
            function Get-Service {param($Name) return [pscustomobject]@{Status='Running'}}
            function Start-Service {throw 'Running/pending service was started again.'}
            function Get-DefenderState {
                $script:queries+=1
                if($script:mode -eq 'late') {Start-Sleep -Milliseconds 1100}
                $status=if($script:mode -eq 'race' -and $script:queries -eq 1){'StartPending'}else{'Running'}
                return [pscustomobject]@{service_status=$status;status=@{};preferences=@{}}
            }
            foreach($mode in @('race','late')) {
                $script:mode=$mode; $script:queries=0
                $report=[ordered]@{preparation_wait_seconds=0;preparation_observations=@()}
                $timer=[Diagnostics.Stopwatch]::StartNew()
                $timeout=if($mode -eq 'race'){5}else{1}
                $failed=$false
                try {Wait-DefenderPreparationService -Timer $timer -TimeoutSeconds $timeout -PollSeconds 1 -RequireQueries}
                catch {$failed=$true}
                if($mode -eq 'race') {
                    if($failed -or $script:queries -ne 2 -or
                       $report.preparation_observations[0].outcome -ne 'settling' -or
                       $report.preparation_observations[0].state.service_status -ne 'StartPending' -or
                       $report.preparation_observations[-1].state.service_status -ne 'Running') {
                        throw 'Replay accepted a service restart during its status/preference queries.'
                    }
                } elseif(-not $failed -or $report.preparation_wait_seconds -lt 1 -or
                         $report.preparation_observations[-1].outcome -ne 'settling_expired') {
                    throw 'A successful query after the settling deadline was accepted.'
                }
            }
        ''')

    @unittest.skipUnless(POWERSHELL, 'PowerShell is available in Windows CI.')
    def test_defender_initialization_wait_is_only_for_post_rpc_settling_queries(self):
        self.run_preparation_procedure(r'''
            function Write-ScanReport {
                if($report.engine_ready -or $report.clean -or
                   (ConvertTo-Json -InputObject $report.inputs -Compress) -ne $script:originalInputs) {
                    throw 'Initialization polling changed inputs or claimed qualification.'
                }
            }
            function Throw-InitializationFailure {
                param($Command)
                throw [Management.Automation.ErrorRecord]::new([Exception]::new('Procedural provider not initialized'),
                    ('HRESULT 0x800106ba,'+$Command),[Management.Automation.ErrorCategory]::NotSpecified,$null)
            }
            function Get-Service {
                param($Name)
                if($script:mode -in @('service-init','outside-require-queries')) {
                    Throw-InitializationFailure 'Get-Service'
                }
                return [pscustomobject]@{Status='Running'}
            }
            function Start-Service {throw 'Initialization polling restarted the service.'}
            function Get-DefenderState {
                $script:queries+=1
                if($script:mode -eq 'expiry' -or
                   ($script:mode -eq 'recover' -and $script:queries -le 2)) {
                    Throw-InitializationFailure 'Get-MpPreference'
                }
                return Get-Content -LiteralPath $env:DEFENDER_TEST_READY_STATE -Raw | ConvertFrom-Json
            }
            function Enable-DefenderProtection {
                param($Timer,$TimeoutSeconds,$PollSeconds)
                $script:enableCalls+=1
                $script:preparationCommand='Update-MpSignature MMPC'
                if($script:mode -eq 'enable-init') {
                    $script:preparationCommand='Get-MpPreference'
                    Throw-InitializationFailure 'Get-MpPreference'
                }
                if($script:mode -eq 'signature-init') {
                    Throw-InitializationFailure 'Update-MpSignature'
                }
                if($script:enableCalls -eq 1) {
                    throw [ComponentModel.Win32Exception]::new(1726,'Procedural RPC restart')
                }
            }
            foreach($mode in @('recover','expiry','enable-init','signature-init','service-init','outside-require-queries')) {
                $script:mode=$mode; $script:queries=0; $script:enableCalls=0
                $report=[ordered]@{clean=$false;engine_ready=$false;preparation_attempts=0;
                    preparation_wait_seconds=0;preparation_observations=@();
                    inputs=@(@{path='original';size=7;sha256='original-hash'})}
                $script:originalInputs=ConvertTo-Json -InputObject $report.inputs -Compress
                $timeout=if($mode -eq 'expiry'){1}else{5}
                $failed=$false
                try {
                    if($mode -eq 'outside-require-queries') {
                        Wait-DefenderPreparationService -Timer ([Diagnostics.Stopwatch]::StartNew()) `
                            -TimeoutSeconds $timeout -PollSeconds 1
                    } else {Invoke-DefenderPreparation -TimeoutSeconds $timeout -PollSeconds 1}
                } catch {$failed=$true}
                $expectedCalls=if($mode -eq 'recover'){2}elseif($mode -eq 'outside-require-queries'){0}else{1}
                if($failed -ne ($mode -ne 'recover') -or $script:enableCalls -ne $expectedCalls -or
                   $report.preparation_attempts -ne $expectedCalls) {
                    throw ('Invalid initialization retry scope: '+$mode)
                }
                $initializationWaits=@($report.preparation_observations | Where-Object initialization_query_wait)
                if($mode -in @('recover','expiry')) {
                    if($initializationWaits.Count -lt 1 -or
                       @($initializationWaits | Where-Object transient_rpc).Count -ne 0 -or
                       @($initializationWaits | Where-Object { -not $_.defender_initializing }).Count -ne 0) {
                        throw 'Initialization wait was incorrectly treated as RPC or lost its diagnostics.'
                    }
                    if($mode -eq 'expiry' -and
                       ($report.preparation_wait_seconds -lt 1 -or
                        $report.preparation_observations[-1].outcome -ne 'settling_expired')) {
                        throw 'Initialization query expiry bypassed the original settling budget.'
                    }
                } elseif($initializationWaits.Count -ne 0) {
                    throw ('Initialization errors outside settling queries were retried: '+$mode)
                }
                Write-ScanReport
            }
        ''')

    @unittest.skipUnless(POWERSHELL, 'PowerShell is available in Windows CI.')
    def test_preparation_replays_strong_settings_and_limits_complete_attempts(self):
        self.run_preparation_procedure(r'''
            function Write-ScanReport {
                if($report.clean -or $report.engine_ready -or
                   (ConvertTo-Json -InputObject $report.inputs -Compress) -ne $script:originalInputs) {
                    throw 'Preparation changed inventory or claimed qualification.'
                }
            }
            function Test-Path {param($LiteralPath) return $false}
            function Get-Service {
                param($Name)
                if($script:mode -eq 'recover-start-pending' -and $script:updateCalls -eq 1 -and
                   $script:serviceReads -lt 3) {
                    $script:serviceReads+=1
                    return [pscustomobject]@{Status='StartPending'}
                }
                if($script:mode -eq 'start-pending' -and $script:serviceReads -eq 0) {
                    $script:serviceReads+=1
                    return [pscustomobject]@{Status='StartPending'}
                }
                if($script:mode -eq 'stopped' -and $script:startCalls -eq 0) {
                    return [pscustomobject]@{Status='Stopped'}
                }
                return [pscustomobject]@{Status='Running'}
            }
            function Start-Service {param($Name) $script:startCalls+=1}
            function Get-MpComputerStatus {
                if($script:updateCalls -eq 1 -and $script:mode -eq 'query-rpc-expiry') {
                    throw [ComponentModel.Win32Exception]::new(1726,'Procedural query RPC failure')
                }
                if($script:updateCalls -eq 1 -and $script:mode -eq 'query-denied') {
                    throw [ComponentModel.Win32Exception]::new(5,'Procedural query denied')
                }
                return $script:state.status
            }
            function Get-MpPreference {return $script:state.preferences}
            function Remove-MpPreference {
                param($ExclusionPath,$ExclusionExtension,$ExclusionProcess)
                foreach($name in @('ExclusionPath','ExclusionExtension','ExclusionProcess')) {
                    if($PSBoundParameters.ContainsKey($name)) {
                        $script:state.preferences.$name=@()
                        $script:removed+=$name
                    }
                }
            }
            function Set-MpPreference {
                param($DisableRealtimeMonitoring,$DisableBehaviorMonitoring,$DisableIOAVProtection,
                      $DisableScriptScanning,$DisableArchiveScanning,$MAPSReporting,
                      $SubmitSamplesConsent,$DisableBlockAtFirstSeen,$PUAProtection)
                foreach($name in @('DisableRealtimeMonitoring','DisableBehaviorMonitoring',
                                  'DisableIOAVProtection','DisableScriptScanning',
                                  'DisableArchiveScanning','DisableBlockAtFirstSeen')) {
                    if(-not $PSBoundParameters.ContainsKey($name) -or $PSBoundParameters[$name] -ne $false) {
                        throw ('Preparation disabled or omitted protection: '+$name)
                    }
                    $script:state.preferences.$name=$false
                }
                if($MAPSReporting -ne 'Advanced' -or $SubmitSamplesConsent -ne 'SendSafeSamples' -or
                   $PUAProtection -ne 'Enabled') {throw 'Cloud/PUA setting weakened.'}
                $script:state.preferences.MAPSReporting=2
                $script:state.preferences.SubmitSamplesConsent=1
                $script:state.preferences.PUAProtection=1
                $script:state.status.RealTimeProtectionEnabled=($script:mode -ne 'protection-blocked')
                $script:state.status.BehaviorMonitorEnabled=$true
                $script:state.status.IoavProtectionEnabled=$true
                $script:setCalls+=1
            }
            function Update-MpSignature {
                param($UpdateSource)
                if($UpdateSource -ne 'MMPC') {throw 'Signature source changed.'}
                $script:updateCalls+=1
                if($script:mode -eq 'generic') {throw 'Procedural signature download failed'}
                if($script:mode -eq 'rpc-message-only') {throw 'The remote procedure call failed.'}
                if($script:mode -eq 'persistent-rpc' -or
                   ($script:updateCalls -eq 1 -and $script:mode -in
                       @('recover','recover-start-pending','query-rpc-expiry','query-denied','protection-blocked'))) {
                    $failure=[Management.Automation.ErrorRecord]::new(
                        [Exception]::new('Procedural provider failure'),
                        'HRESULT0x800706be,Update-MpSignature',
                        [Management.Automation.ErrorCategory]::NotSpecified,$null)
                    throw $failure
                }
            }
            foreach($mode in @('first-success','recover','recover-start-pending','persistent-rpc','generic','rpc-message-only',
                               'query-rpc-expiry','query-denied','start-pending','stopped','protection-blocked')) {
                $script:mode=$mode; $script:updateCalls=0; $script:setCalls=0
                $script:startCalls=0; $script:serviceReads=0; $script:removed=@()
                $script:state=Get-Content -LiteralPath $env:DEFENDER_TEST_READY_STATE -Raw | ConvertFrom-Json
                foreach($name in @('ExclusionPath','ExclusionExtension','ExclusionProcess')) {
                    $script:state.preferences | Add-Member -NotePropertyName $name -NotePropertyValue @('procedural')
                }
                $report=[ordered]@{clean=$false; engine_ready=$false; preparation_attempts=0;
                    preparation_wait_seconds=0; preparation_observations=@();
                    inputs=@(@{path='original';size=7;sha256='original-hash'})}
                $script:originalInputs=ConvertTo-Json -InputObject $report.inputs -Compress
                $failed=$false
                $timeout=if($mode -eq 'query-rpc-expiry'){1}else{5}
                try {Invoke-DefenderPreparation -TimeoutSeconds $timeout -PollSeconds 1}
                catch {$failed=$true}
                $expectedFailure=$mode -in @('persistent-rpc','generic','rpc-message-only','query-rpc-expiry','query-denied')
                $expectedAttempts=if($mode -in @('recover','recover-start-pending','persistent-rpc','protection-blocked')){2}else{1}
                if($failed -ne $expectedFailure -or $report.preparation_attempts -ne $expectedAttempts -or
                   $script:updateCalls -ne $expectedAttempts -or $script:setCalls -ne $expectedAttempts) {
                    throw ('Incorrect preparation retry: '+$mode+'; '+($report | ConvertTo-Json -Depth 8))
                }
                if($script:startCalls -ne [int]($mode -eq 'stopped') -or
                   $script:removed.Count -ne 3) {throw ('Invalid service/exclusion handling: '+$mode)}
                if($mode -eq 'query-rpc-expiry' -and
                   ($report.preparation_wait_seconds -lt 1 -or
                    @($report.preparation_observations | Where-Object outcome -eq 'settling_expired').Count -ne 1)) {
                    throw 'Service/query expiry lost its bounded wait evidence.'
                }
                if($expectedAttempts -eq 2) {
                    $available=@($report.preparation_observations | Where-Object {
                        $_.outcome -eq 'service_available' -and $null -ne $_.state
                    })
                    $failures=@($report.preparation_observations | Where-Object outcome -eq 'preparation_failure')
                    if($available.Count -lt 1 -or $failures.Count -lt 1 -or
                       $failures[0].command -ne 'Update-MpSignature MMPC' -or
                       -not $failures[0].transient_rpc -or $null -eq $failures[0].state) {
                        throw ('Recovery lacked command/state diagnostics or successful replay queries: '+$mode)
                    }
                }
                if($mode -eq 'protection-blocked') {
                    $rejected=$false
                    try {Assert-DefenderReady (Get-DefenderState)} catch {$rejected=$true}
                    if(-not $rejected) {throw 'Preparation recovery bypassed actual readiness.'}
                }
                Write-ScanReport
            }
        ''')

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
        ready = procedural_ready_state()
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

    @unittest.skipUnless(POWERSHELL, 'PowerShell is available in Windows CI.')
    def test_readiness_wait_accepts_observed_activation_and_rejects_expiry(self):
        # The real waiting function and predicate consume procedural live
        # observations. Configuration being enabled is deliberately insufficient.
        command = r'''
            $ErrorActionPreference='Stop'
            $tokens=$null; $errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile(
                $env:DEFENDER_SCRIPT_TEST_PATH,[ref]$tokens,[ref]$errors)
            foreach($name in @('Assert-DefenderReady','Wait-DefenderReady')) {
                $definition=$ast.Find({param($node)
                    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
                    $node.Name -eq $name},$true)
                . ([ScriptBlock]::Create($definition.Extent.Text))
            }
            function Write-ScanReport {}
            function Get-DefenderState {
                $script:attempt += 1
                if($script:mode -eq 'query-error' -and $script:attempt -eq 1) {
                    throw 'Procedural CIM state temporarily unavailable'
                }
                $state=Get-Content -LiteralPath $env:DEFENDER_TEST_READY_STATE -Raw | ConvertFrom-Json
                if($script:mode -eq 'persistent' -or
                    ($script:mode -eq 'delayed' -and $script:attempt -eq 1)) {
                    $state.status.RealTimeProtectionEnabled=$false
                    $state.status.BehaviorMonitorEnabled=$false
                    $state.status.IoavProtectionEnabled=$false
                }
                return $state
            }
            foreach($mode in @('delayed','query-error','persistent')) {
                $script:mode=$mode; $script:attempt=0
                $report=[ordered]@{defender_after=$null; readiness_attempts=0;
                    readiness_wait_seconds=0; readiness_observations=@(); engine_ready=$false}
                $expired=$false
                try {$result=Wait-DefenderReady -TimeoutSeconds 1 -PollSeconds 1}
                catch {$expired=$true}
                if($mode -eq 'persistent') {
                    if(-not $expired -or $report.engine_ready -or
                        @($report.readiness_observations | Where-Object ready).Count -ne 0) {
                        throw 'Expired, disabled protection was accepted.'
                    }
                } else {
                    if($expired -or $report.readiness_attempts -ne 2 -or
                        $report.readiness_observations[0].ready -or
                        -not $report.readiness_observations[1].ready -or
                        -not $result.status.RealTimeProtectionEnabled) {
                        throw ('Activation did not require actual live readiness: ' + $mode)
                    }
                }
                if($report.readiness_attempts -ne $report.readiness_observations.Count) {
                    throw 'Readiness observations were lost.'
                }
            }
            exit 0
        '''
        with tempfile.TemporaryDirectory() as folder:
            ready = Path(folder).resolve() / 'ready-state.json'
            ready.write_text(json.dumps(procedural_ready_state()), encoding='utf-8')
            result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                                    env=dict(os.environ, DEFENDER_SCRIPT_TEST_PATH=str(SCANNER),
                                             DEFENDER_TEST_READY_STATE=str(ready)),
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

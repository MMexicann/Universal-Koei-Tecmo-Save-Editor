# Static Microsoft Defender release qualification. Run only on an isolated,
# elevated Windows build runner; this enables protection and removes exclusions.
# https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus
# https://learn.microsoft.com/en-us/defender-endpoint/configure-block-at-first-sight-microsoft-defender-antivirus
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [switch]$Baseline
)

$ErrorActionPreference = 'Stop'
# Capture native failures ourselves, including their output, before failing.
$PSNativeCommandUseErrorActionPreference = $false
$started = [DateTime]::UtcNow
$reportFile = [IO.Path]::GetFullPath($ReportPath)
$logFile = [IO.Path]::ChangeExtension($reportFile, '.log')
$report = [ordered]@{
    schema_version = 1
    baseline = [bool]$Baseline
    clean = $false
    verdict = 'in_progress'
    phase = 'initialization'
    failure_phase = $null
    started_utc = $started.ToString('o')
    completed_utc = $null
    input_name = [IO.Path]::GetFileName($Path.TrimEnd([char[]]@('\', '/')))
    inputs = @()
    inputs_after = @()
    defender_before = $null
    defender_after = $null
    engine_ready = $false
    preparation_attempts = 0
    preparation_wait_seconds = 0
    preparation_observations = @()
    readiness_attempts = 0
    readiness_wait_seconds = 0
    readiness_observations = @()
    protection_diagnostics = $null
    maps_exit_code = $null
    scan_exit_code = $null
    scan_arguments = @()
    errors = @()
    diagnostics_errors = @()
}
$exitCode = 1

function Write-ScanReport {
    $folder = [IO.Path]::GetDirectoryName($reportFile)
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportFile -Encoding utf8
}

function Get-InputSnapshot([string]$InputPath) {
    $item = Get-Item -LiteralPath $InputPath -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'A release input cannot be a reparse point.'
    }
    $entries = if ($item.PSIsContainer) {
        $children = @(Get-ChildItem -LiteralPath $item.FullName -Recurse -Force)
        if (@($children | Where-Object {
            ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        }).Count -ne 0) { throw 'The release bundle contains a reparse point.' }
        @($children | Where-Object { -not $_.PSIsContainer } | Sort-Object FullName)
    } else { @($item) }
    if ($entries.Count -eq 0) { throw 'A release input must contain at least one file.' }
    foreach ($entry in $entries) {
        $relative = if ($item.PSIsContainer) {
            [IO.Path]::GetRelativePath($item.FullName, $entry.FullName).Replace('\', '/')
        } else { $entry.Name }
        [ordered]@{
            path = $relative
            size = $entry.Length
            sha256 = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
}

function Get-DefenderState {
    $status = Get-MpComputerStatus
    $preferences = Get-MpPreference
    [ordered]@{
        service_status = (Get-Service -Name WinDefend).Status.ToString()
        status = $status | Select-Object AMEngineVersion, AMProductVersion, AMServiceVersion,
            AMRunningMode, AMServiceEnabled, AntivirusEnabled, AntivirusSignatureVersion,
            AntivirusSignatureLastUpdated, AntivirusSignatureAge, RealTimeProtectionEnabled,
            BehaviorMonitorEnabled, IoavProtectionEnabled, IsTamperProtected
        preferences = $preferences | Select-Object MAPSReporting, SubmitSamplesConsent,
            DisableBlockAtFirstSeen, DisableRealtimeMonitoring, DisableBehaviorMonitoring,
            DisableIOAVProtection, DisableScriptScanning, DisableArchiveScanning, PUAProtection
        exclusion_count = @($preferences.ExclusionPath | Where-Object { $_ }).Count +
            @($preferences.ExclusionExtension | Where-Object { $_ }).Count +
            @($preferences.ExclusionProcess | Where-Object { $_ }).Count
    }
}

function Get-ProtectionDiagnostics {
    # Selected local Defender service/driver and policy fields only. Do not
    # export the registry, process environment or machine/account identifiers.
    $details = [ordered]@{ services = @(); drivers = @(); policies = @(); errors = @() }
    foreach ($name in @('WinDefend', 'WdFilter', 'WdNisDrv', 'WdNisSvc')) {
        try {
            $service = Get-Service -Name $name -ErrorAction Stop
            $details.services += [ordered]@{
                name = $service.Name
                status = $service.Status.ToString()
                start_type = $service.StartType.ToString()
            }
        } catch { $details.errors += ($name + ': ' + $_.Exception.Message) }
    }
    try {
        # Some platforms expose kernel drivers through CIM, not Get-Service.
        $details.drivers = @(Get-CimInstance -ClassName Win32_SystemDriver `
            -Filter "Name='WdFilter' OR Name='WdNisDrv'" -ErrorAction Stop |
            Select-Object Name, State, Started, StartMode)
    } catch { $details.errors += ('Defender drivers: ' + $_.Exception.Message) }
    $queries = @(
        @{path='HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender'; names=@('DisableAntiSpyware','DisableAntiVirus')},
        @{path='HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection'; names=@('DisableRealtimeMonitoring','DisableBehaviorMonitoring','DisableIOAVProtection')},
        @{path='HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet'; names=@('SpynetReporting','SubmitSamplesConsent','DisableBlockAtFirstSeen')},
        @{path='HKLM:\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection'; names=@('ForceDefenderPassiveMode')},
        @{path='HKLM:\SYSTEM\CurrentControlSet\Services\WdFilter'; names=@('Start')},
        @{path='HKLM:\SYSTEM\CurrentControlSet\Services\WdNisDrv'; names=@('Start')},
        @{path='HKLM:\SYSTEM\CurrentControlSet\Services\WdNisSvc'; names=@('Start')}
    )
    foreach ($query in $queries) {
        try {
            if (Test-Path -LiteralPath $query.path) {
                $values = Get-ItemProperty -LiteralPath $query.path -Name $query.names -ErrorAction SilentlyContinue
                $selected = [ordered]@{}
                foreach ($name in $query.names) {
                    if ($null -ne $values -and $null -ne $values.PSObject.Properties[$name]) {
                        $selected[$name] = $values.PSObject.Properties[$name].Value
                    }
                }
                $details.policies += [ordered]@{ path=$query.path; values=$selected }
            }
        } catch { $details.errors += ('Defender policy: ' + $_.Exception.Message) }
    }
    return $details
}

function Assert-DefenderReady($State) {
    $status = $State.status
    $preferences = $State.preferences
    if ($State.service_status -ne 'Running' -or $status.AMRunningMode -ne 'Normal' -or
        -not $status.AMServiceEnabled -or -not $status.AntivirusEnabled -or
        -not $status.RealTimeProtectionEnabled -or -not $status.BehaviorMonitorEnabled -or
        -not $status.IoavProtectionEnabled -or -not $status.AMEngineVersion -or
        -not $status.AMProductVersion -or -not $status.AntivirusSignatureVersion) {
        throw 'Microsoft Defender must have an active service, engine and real-time protection.'
    }
    if ($preferences.MAPSReporting -ne 2 -or $preferences.SubmitSamplesConsent -ne 1 -or
        $preferences.DisableBlockAtFirstSeen -ne $false -or
        $preferences.DisableRealtimeMonitoring -ne $false -or
        $preferences.DisableBehaviorMonitoring -ne $false -or
        $preferences.DisableIOAVProtection -ne $false -or
        $preferences.DisableScriptScanning -ne $false -or
        $preferences.DisableArchiveScanning -ne $false -or
        $preferences.PUAProtection -ne 1 -or $State.exclusion_count -ne 0) {
        throw 'Defender cloud/protection settings or inherited exclusions prevent qualification.'
    }
    $updated = ([DateTime]$status.AntivirusSignatureLastUpdated).ToUniversalTime()
    if ($updated -gt [DateTime]::UtcNow.AddMinutes(5) -or
        $updated -lt [DateTime]::UtcNow.AddDays(-2)) {
        throw 'Defender security intelligence is missing, future-dated or stale.'
    }
}

function Wait-DefenderReady(
    [ValidateRange(1, 300)][int]$TimeoutSeconds = 120,
    [ValidateRange(1, 10)][int]$PollSeconds = 2
) {
    # Preference writes can finish before the actual protection state changes.
    # Poll the same strict predicate; expiry is an error, never qualification.
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        $observation = [ordered]@{
            observed_utc = [DateTime]::UtcNow.ToString('o')
            state = $null
            ready = $false
            error = $null
        }
        try {
            $state = Get-DefenderState
            $report.defender_after = $state
            $observation.state = $state
            Assert-DefenderReady $state
            $observation.ready = $true
        } catch { $observation.error = $_.Exception.Message }
        $report.readiness_attempts += 1
        $report.readiness_wait_seconds = [Math]::Round($timer.Elapsed.TotalSeconds, 3)
        $report.readiness_observations += $observation
        Write-ScanReport
        if ($observation.ready) { return $state }
        if ($timer.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
            throw ('Defender readiness did not become active within ' + $TimeoutSeconds +
                   ' seconds: ' + $observation.error)
        }
        $remaining = $TimeoutSeconds - $timer.Elapsed.TotalSeconds
        Start-Sleep -Milliseconds ([int]([Math]::Min($PollSeconds, $remaining) * 1000))
    }
}

function Get-PreparationFailure($Failure) {
    $codes = @()
    $nativeCodes = @()
    $exception = $Failure.Exception
    for ($depth = 0; $null -ne $exception -and $depth -lt 8; $depth++) {
        $codes += ('0x{0:X8}' -f ([long]$exception.HResult -band 0xffffffffL))
        if ($null -ne $exception.PSObject.Properties['NativeErrorCode']) {
            $nativeCodes += [long]$exception.NativeErrorCode
        }
        $exception = $exception.InnerException
    }
    # Only the documented RPC unavailable/call failed/call failed without
    # execution codes qualify. A message alone or generic CIM error does not.
    $rpc = @($codes | Where-Object { $_ -in @('0x800706BA', '0x800706BE', '0x800706BF') }).Count -gt 0 -or
        @($nativeCodes | Where-Object { $_ -in @(1722, 1726, 1727, 2147944122, 2147944126, 2147944127,
                                                       -2147023174, -2147023170, -2147023169) }).Count -gt 0 -or
        $Failure.FullyQualifiedErrorId -match '(?i)(?:^|\bHRESULT\s*|[^a-z0-9])0x800706(?:ba|be|bf)(?![a-z0-9])'
    $initializing = $codes -contains '0x800106BA' -or
        @($nativeCodes | Where-Object { $_ -in @(2147550906, -2147416390) }).Count -gt 0 -or
        $Failure.FullyQualifiedErrorId -match '(?i)(?:^|\bHRESULT\s*|[^a-z0-9])0x800106ba(?![a-z0-9])'
    $providerLoad = $codes -contains '0x80041013' -or
        @($nativeCodes | Where-Object { $_ -in @(2147749907, -2147217389) }).Count -gt 0 -or
        $Failure.FullyQualifiedErrorId -match '(?i)^(?:HRESULT\s*)?0x80041013(?:,|$)'
    [ordered]@{
        observed_utc = [DateTime]::UtcNow.ToString('o')
        command = $script:preparationCommand
        error = $Failure.Exception.Message
        fully_qualified_error_id = $Failure.FullyQualifiedErrorId
        hresults = $codes
        native_error_codes = $nativeCodes
        transient_rpc = [bool]$rpc
        defender_initializing = [bool]$initializing
        provider_load_failure = [bool]$providerLoad
        service_status = $null
        state = $null
        state_error = $null
    }
}

function Wait-DefenderPreparationService(
    [Diagnostics.Stopwatch]$Timer,
    [ValidateRange(1, 120)][int]$TimeoutSeconds = 120,
    [ValidateRange(1, 10)][int]$PollSeconds = 2,
    [switch]$RequireQueries,
    [switch]$AfterRpcRestart
) {
    while ($true) {
        if ($Timer.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
            $report.preparation_wait_seconds = [Math]::Round($Timer.Elapsed.TotalSeconds, 3)
            $report.preparation_observations += [ordered]@{
                observed_utc = [DateTime]::UtcNow.ToString('o')
                outcome = 'settling_expired'
                command = $script:preparationCommand
            }
            Write-ScanReport
            throw 'Defender preparation service/query settling budget expired.'
        }
        $observation = [ordered]@{
            observed_utc = [DateTime]::UtcNow.ToString('o')
            outcome = 'settling'
            service_status = $null
            state = $null
        }
        try {
            $script:preparationCommand = 'Get-Service WinDefend'
            $service = Get-Service -Name WinDefend
            $observation.service_status = $service.Status.ToString()
            if ($service.Status -eq 'Stopped') {
                $script:preparationCommand = 'Start-Service WinDefend'
                Start-Service -Name WinDefend
            } elseif ($service.Status -eq 'Running') {
                if ($RequireQueries) {
                    $script:preparationCommand = 'Get-MpComputerStatus/Get-MpPreference'
                    # Successful queries only establish that replay is possible.
                    # The unchanged strict readiness predicate runs afterward.
                    $observation.state = Get-DefenderState
                    if ($observation.state.service_status -eq 'Running') {
                        $observation.outcome = 'service_available'
                    }
                } else {
                    $observation.outcome = 'service_available'
                }
            }
        } catch {
            $failure = Get-PreparationFailure $_
            $failure.outcome = 'settling_failure'
            $failure.service_status = $observation.service_status
            # Defender can expose its service before its status/preferences
            # provider initializes after an RPC restart. This exact code permits
            # only preliminary query polling, never another full enable attempt.
            $initializationQuery = $RequireQueries -and $failure.defender_initializing -and
                $script:preparationCommand -eq 'Get-MpComputerStatus/Get-MpPreference'
            # A confirmed RPC restart can briefly leave the WMI provider unloaded.
            # Poll only this exact query failure within the original budget; never
            # classify it as permission for another complete preparation attempt.
            $providerQuery = $RequireQueries -and $AfterRpcRestart -and $failure.provider_load_failure -and
                $script:preparationCommand -eq 'Get-MpComputerStatus/Get-MpPreference'
            $failure.initialization_query_wait = [bool]$initializationQuery
            $failure.provider_query_wait = [bool]$providerQuery
            $report.preparation_observations += $failure
            Write-ScanReport
            if (-not $failure.transient_rpc -and -not $initializationQuery -and -not $providerQuery) { throw }
        }
        $report.preparation_observations += $observation
        $report.preparation_wait_seconds = [Math]::Round($Timer.Elapsed.TotalSeconds, 3)
        Write-ScanReport
        if ($observation.outcome -eq 'service_available' -and $Timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) { return }
        $remaining = $TimeoutSeconds - $Timer.Elapsed.TotalSeconds
        if ($remaining -gt 0) {
            Start-Sleep -Milliseconds ([int]([Math]::Min($PollSeconds, $remaining) * 1000))
        }
    }
}

function Enable-DefenderProtection(
    [Diagnostics.Stopwatch]$Timer,
    [ValidateRange(1, 120)][int]$TimeoutSeconds = 120,
    [ValidateRange(1, 10)][int]$PollSeconds = 2
) {
    # Hosted runner images can install Defender but disable its protections.
    # Never treat installation, a stopped service or a policy write as readiness.
    $policy = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection'
    $script:preparationCommand = 'Read ForceDefenderPassiveMode policy'
    if (Test-Path -LiteralPath $policy) {
        $current = Get-ItemProperty -LiteralPath $policy -Name ForceDefenderPassiveMode -ErrorAction SilentlyContinue
        if ($null -ne $current -and $current.ForceDefenderPassiveMode -ne 0) {
            $script:preparationCommand = 'Set-ItemProperty ForceDefenderPassiveMode 0'
            Set-ItemProperty -LiteralPath $policy -Name ForceDefenderPassiveMode -Value 0 -Type DWord
        }
    }
    Wait-DefenderPreparationService -Timer $Timer -TimeoutSeconds $TimeoutSeconds -PollSeconds $PollSeconds
    $script:preparationCommand = 'Get-MpPreference'
    $preferences = Get-MpPreference
    foreach ($entry in @($preferences.ExclusionPath)) {
        if ($entry) {
            $script:preparationCommand = 'Remove-MpPreference ExclusionPath'
            Remove-MpPreference -ExclusionPath $entry
        }
    }
    foreach ($entry in @($preferences.ExclusionExtension)) {
        if ($entry) {
            $script:preparationCommand = 'Remove-MpPreference ExclusionExtension'
            Remove-MpPreference -ExclusionExtension $entry
        }
    }
    foreach ($entry in @($preferences.ExclusionProcess)) {
        if ($entry) {
            $script:preparationCommand = 'Remove-MpPreference ExclusionProcess'
            Remove-MpPreference -ExclusionProcess $entry
        }
    }
    $script:preparationCommand = 'Set-MpPreference protection/cloud settings'
    Set-MpPreference -DisableRealtimeMonitoring $false -DisableBehaviorMonitoring $false `
        -DisableIOAVProtection $false -DisableScriptScanning $false -DisableArchiveScanning $false `
        -MAPSReporting Advanced -SubmitSamplesConsent SendSafeSamples -DisableBlockAtFirstSeen $false `
        -PUAProtection Enabled
    $script:preparationCommand = 'Update-MpSignature MMPC'
    Update-MpSignature -UpdateSource MMPC
}

function Invoke-DefenderPreparation(
    [ValidateRange(1, 120)][int]$TimeoutSeconds = 120,
    [ValidateRange(1, 10)][int]$PollSeconds = 2
) {
    # At most two complete attempts share one bounded service/query settling
    # budget. Input inventory, scanner readiness and scan verdicts are untouched.
    $timer = [Diagnostics.Stopwatch]::StartNew()
    for ($attempt = 1; $attempt -le 2; $attempt++) {
        $report.preparation_attempts = $attempt
        try {
            Enable-DefenderProtection -Timer $timer -TimeoutSeconds $TimeoutSeconds -PollSeconds $PollSeconds
            $report.preparation_observations += [ordered]@{
                observed_utc = [DateTime]::UtcNow.ToString('o')
                attempt = $attempt
                outcome = 'prepared'
            }
            Write-ScanReport
            return
        } catch {
            $failure = Get-PreparationFailure $_
            $failure.attempt = $attempt
            $failure.outcome = 'preparation_failure'
            try { $failure.service_status = (Get-Service -Name WinDefend).Status.ToString() }
            catch { $failure.state_error = $_.Exception.Message }
            try { $failure.state = Get-DefenderState }
            catch { $failure.state_error = $_.Exception.Message }
            $report.preparation_observations += $failure
            Write-ScanReport
            if (-not $failure.transient_rpc -or $attempt -eq 2) { throw }
        }
        Wait-DefenderPreparationService -Timer $timer -TimeoutSeconds $TimeoutSeconds `
            -PollSeconds $PollSeconds -RequireQueries -AfterRpcRestart
    }
}

function Get-DefenderCommand {
    $platformRoot = Join-Path $env:ProgramData 'Microsoft\Windows Defender\Platform'
    $platforms = if (Test-Path -LiteralPath $platformRoot) {
        @(Get-ChildItem -LiteralPath $platformRoot -Directory | Where-Object {
            $_.Name -match '^\d+\.\d+\.\d+\.\d+(?:-\d+)?$'
        } | Sort-Object { [Version]($_.Name -replace '-\d+$', '') } -Descending)
    } else { @() }
    $candidates = @($platforms | ForEach-Object { Join-Path $_.FullName 'MpCmdRun.exe' })
    $candidates += Join-Path $env:ProgramFiles 'Windows Defender\MpCmdRun.exe'
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $signature = Get-AuthenticodeSignature -LiteralPath $candidate
            if ($signature.Status -ne 'Valid' -or
                $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation|Microsoft Windows') {
                throw 'The installed Defender command has no valid Microsoft signature.'
            }
            return $candidate
        }
    }
    throw 'No installed Microsoft Defender command-line scanner was found.'
}

function Invoke-DefenderCommand([string]$Command, [string[]]$Arguments) {
    ('MpCmdRun ' + ($Arguments -join ' ')) | Add-Content -LiteralPath $logFile -Encoding utf8
    & $Command @Arguments 2>&1 | ForEach-Object {
        $_.ToString() | Tee-Object -FilePath $logFile -Append | Write-Host
    }
    $nativeExitCode = $LASTEXITCODE
    return $nativeExitCode
}

try {
    Write-ScanReport
    # Preserve a complete file inventory before enabling protection, which can
    # itself quarantine a flagged old baseline. Failure is recorded, not clean.
    try { $report.inputs = @(Get-InputSnapshot $Path) }
    catch { $report.errors += ('Initial input snapshot: ' + $_.Exception.Message) }
    $report.phase = 'defender_preparation'
    # A stopped service can make the initial CIM status query fail. Preserve
    # that observation, then attempt normal service startup before qualification.
    try { $report.defender_before = Get-DefenderState }
    catch { $report.diagnostics_errors += ('Initial Defender state: ' + $_.Exception.Message) }
    Write-ScanReport
    Invoke-DefenderPreparation
    $report.defender_after = Wait-DefenderReady
    $report.defender_scan_start = $report.defender_after
    $command = Get-DefenderCommand
    $report.scanner_version = (Get-Item -LiteralPath $command).VersionInfo.FileVersion
    $report.phase = 'cloud_connectivity'
    Write-ScanReport
    $report.maps_exit_code = Invoke-DefenderCommand $command @('-ValidateMapsConnection')
    if ($report.maps_exit_code -ne 0) { throw 'Defender cloud connectivity validation failed.' }
    $report.engine_ready = $true
    $report.phase = 'input_validation'
    if (-not (Test-Path -LiteralPath $Path)) {
        $report.verdict = 'input_unavailable'
        if ($Baseline) { $exitCode = 0 } else { throw 'The release scan input is missing or quarantined.' }
    } elseif ($report.inputs.Count -eq 0) {
        $report.verdict = 'input_unavailable'
        if ($Baseline) { $exitCode = 0 } else { throw 'The release input could not be hashed before qualification.' }
    } else {
        $resolved = (Get-Item -LiteralPath $Path -Force).FullName
        $report.phase = 'scanning'
        # Microsoft documents that this CUSTOM-SCAN flag ignores exclusions,
        # scans archives and reports detections in stdout without remediation.
        # It does not disable antivirus. Real-time protection remains active.
        $report.scan_arguments = @('-Scan', '-ScanType', '3', '-File', $resolved, '-DisableRemediation')
        Write-ScanReport
        $report.scan_exit_code = Invoke-DefenderCommand $command $report.scan_arguments
        try { $report.inputs_after = @(Get-InputSnapshot $Path) }
        catch { $report.errors += ('Final input snapshot: ' + $_.Exception.Message) }
        $report.defender_after = Get-DefenderState
        Assert-DefenderReady $report.defender_after
        $before = ConvertTo-Json -InputObject @($report.inputs) -Depth 4 -Compress
        $after = ConvertTo-Json -InputObject @($report.inputs_after) -Depth 4 -Compress
        if ($before -ne $after) {
            $report.verdict = 'input_changed_or_quarantined'
            if ($Baseline) { $exitCode = 0 } else { throw 'Release files changed or disappeared during the scan.' }
        } elseif ($report.scan_exit_code -ne 0) {
            # Native code 2 means detection OR scanning error, not always malware.
            $report.verdict = 'detected_or_scan_error'
            if ($Baseline) { $exitCode = 0 } else { throw 'Defender reported a detection or scanning error.' }
        } else {
            $report.verdict = 'clean'
            $report.clean = $true
            $exitCode = 0
        }
    }
} catch {
    $report.failure_phase = $report.phase
    $report.errors += $_.Exception.Message
    if ($report.verdict -eq 'in_progress') { $report.verdict = 'scanner_unavailable_or_failed' }
    $report.clean = $false
    $exitCode = 1
} finally {
    $report.phase = 'completed'
    $report.completed_utc = [DateTime]::UtcNow.ToString('o')
    try { $report.protection_diagnostics = Get-ProtectionDiagnostics }
    catch { $report.diagnostics_errors += ('Protection diagnostics: ' + $_.Exception.Message) }
    # DisableRemediation does not write detection events; the native stdout log
    # is the primary evidence. These supplement real-time/quarantine diagnostics.
    try {
        Get-MpThreatDetection | Select-Object ThreatID, InitialDetectionTime,
            LastThreatStatusChangeTime, ActionSuccess, Resources |
            ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($reportFile, '.threats.json')) -Encoding utf8
        Get-MpThreat | Select-Object ThreatID, ThreatName, IsActive, DidThreatExecute |
            ConvertTo-Json -Depth 4 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($reportFile, '.threat-names.json')) -Encoding utf8
    } catch { $report.diagnostics_errors += ('Threat history: ' + $_.Exception.Message) }
    try {
        Get-WinEvent -FilterHashtable @{
            LogName = 'Microsoft-Windows-Windows Defender/Operational'
            StartTime = $started.ToLocalTime()
        } -ErrorAction Stop | Select-Object TimeCreated, Id, LevelDisplayName, Message |
            ConvertTo-Json -Depth 4 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($reportFile, '.events.json')) -Encoding utf8
    } catch { $report.diagnostics_errors += ('Defender event log: ' + $_.Exception.Message) }
    try { Write-ScanReport }
    catch { Write-Host ('Unable to preserve the Defender report: ' + $_.Exception.Message); $exitCode = 1 }
}
exit $exitCode

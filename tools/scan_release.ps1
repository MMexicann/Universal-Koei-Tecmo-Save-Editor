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

function Enable-DefenderProtection {
    # Hosted runner images can install Defender but disable its protections.
    # Never treat installation, a stopped service or a policy write as readiness.
    $policy = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows Advanced Threat Protection'
    if (Test-Path -LiteralPath $policy) {
        $current = Get-ItemProperty -LiteralPath $policy -Name ForceDefenderPassiveMode -ErrorAction SilentlyContinue
        if ($null -ne $current -and $current.ForceDefenderPassiveMode -ne 0) {
            Set-ItemProperty -LiteralPath $policy -Name ForceDefenderPassiveMode -Value 0 -Type DWord
        }
    }
    $service = Get-Service -Name WinDefend
    if ($service.Status -ne 'Running') {
        Start-Service -Name WinDefend
        $service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    }
    $preferences = Get-MpPreference
    foreach ($entry in @($preferences.ExclusionPath)) {
        if ($entry) { Remove-MpPreference -ExclusionPath $entry }
    }
    foreach ($entry in @($preferences.ExclusionExtension)) {
        if ($entry) { Remove-MpPreference -ExclusionExtension $entry }
    }
    foreach ($entry in @($preferences.ExclusionProcess)) {
        if ($entry) { Remove-MpPreference -ExclusionProcess $entry }
    }
    Set-MpPreference -DisableRealtimeMonitoring $false -DisableBehaviorMonitoring $false `
        -DisableIOAVProtection $false -DisableScriptScanning $false -DisableArchiveScanning $false `
        -MAPSReporting Advanced -SubmitSamplesConsent SendSafeSamples -DisableBlockAtFirstSeen $false `
        -PUAProtection Enabled
    Update-MpSignature -UpdateSource MMPC
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
    Enable-DefenderProtection
    $report.defender_after = Get-DefenderState
    Assert-DefenderReady $report.defender_after
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

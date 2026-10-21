# Bounded startup qualification of the exact already-scanned packaged executable.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [Parameter(Mandatory = $true)][ValidateSet('portable', 'standalone')][string]$Format,
    [ValidateRange(30, 300)][int]$TimeoutSeconds = 180
)
$ErrorActionPreference = 'Stop'
$reportFile = [IO.Path]::GetFullPath($ReportPath)
$folder = [IO.Path]::GetDirectoryName($reportFile)
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$stdout = Join-Path $folder "$Format-smoke.stdout.log"
$stderr = Join-Path $folder "$Format-smoke.stderr.log"
$report = [ordered]@{
    schema_version = 1; format = $Format; clean = $false; phase = 'initialization'
    timeout_seconds = $TimeoutSeconds; timed_out = $false; exit_code = $null
    pid = $null; owned_processes = @(); windows = @(); errors = @()
    executable_name = $null; sha256_before = $null; sha256_after = $null
    stdout = [IO.Path]::GetFileName($stdout); stderr = [IO.Path]::GetFileName($stderr)
    started_utc = [DateTime]::UtcNow.ToString('o'); completed_utc = $null
}
$process = $null
$exitCode = 1
function Write-SmokeReport {
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportFile -Encoding utf8
}
function Get-OwnedProcessIds([int]$RootPid) {
    # Only descendants of the launched process enter the report. Never collect
    # environment, command lines, full image paths or unrelated window text.
    $ids = [Collections.Generic.HashSet[int]]::new()
    [void]$ids.Add($RootPid)
    $pending = [Collections.Generic.Queue[int]]::new()
    $pending.Enqueue($RootPid)
    $snapshot = @(Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId,Name -OperationTimeoutSec 5)
    while ($pending.Count -gt 0 -and $ids.Count -lt 64) {
        $parentId = $pending.Dequeue()
        foreach ($child in @($snapshot | Where-Object { $_.ParentProcessId -eq $parentId })) {
            if ($ids.Add([int]$child.ProcessId)) {
                $report.owned_processes += [ordered]@{
                    pid = [int]$child.ProcessId; parent_pid = $parentId; name = $child.Name
                }
                $pending.Enqueue([int]$child.ProcessId)
            }
        }
    }
    return ,$ids
}
function Get-OwnedWindows($Ids) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class PackagedSmokeWindows {
    public delegate bool EnumProc(IntPtr hwnd, IntPtr arg);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc callback, IntPtr arg);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr arg);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int maximum);
    public static string[] Read(int[] owned) {
        var ids = new HashSet<int>(owned);
        var texts = new List<string>();
        EnumProc read = (hwnd, arg) => {
            uint pid; GetWindowThreadProcessId(hwnd, out pid);
            if (ids.Contains((int)pid) && texts.Count < 64) {
                var text = new StringBuilder(4096);
                GetWindowText(hwnd, text, text.Capacity);
                if (text.Length > 0) texts.Add(pid.ToString() + ": " + text.ToString());
            }
            return true;
        };
        EnumWindows((hwnd, arg) => {
            uint pid; GetWindowThreadProcessId(hwnd, out pid);
            if (ids.Contains((int)pid)) {
                read(hwnd, arg); EnumChildWindows(hwnd, read, IntPtr.Zero);
            }
            return true;
        }, IntPtr.Zero);
        return texts.ToArray();
    }
}
'@
    return [PackagedSmokeWindows]::Read([int[]]@($Ids))
}
try {
    Write-SmokeReport
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -or $item.Extension -ne '.exe' -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Packaged smoke requires an ordinary already-scanned Windows executable.'
    }
    $report.executable_name = $item.Name
    $report.sha256_before = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.phase = 'starting'
    Write-SmokeReport
    Write-Host "Starting bounded $Format packaged smoke ($TimeoutSeconds seconds)."
    $process = Start-Process -FilePath $item.FullName -ArgumentList '--smoke-test' -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    # Retain the exact launched process handle, not a later PID/name lookup.
    $null = $process.Handle
    $report.pid = $process.Id
    $report.phase = 'waiting'
    Write-SmokeReport
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $report.timed_out = $true
        $report.phase = 'timeout_diagnostics'
        Write-SmokeReport
        try { $ids = Get-OwnedProcessIds $process.Id; $report.windows = @(Get-OwnedWindows $ids) }
        catch { $report.errors += ('Owned-window diagnostics: ' + $_.Exception.Message) }
        throw 'The packaged smoke exceeded its deadline; startup is not qualified.'
    }
    $process.WaitForExit()
    $report.exit_code = $process.ExitCode
    if ($process.ExitCode -ne 0) { throw 'The packaged smoke exited unsuccessfully.' }
    $report.sha256_after = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($report.sha256_after -ne $report.sha256_before) { throw 'The packaged executable changed during startup qualification.' }
    $report.clean = $true
    $exitCode = 0
} catch {
    $report.errors += $_.Exception.Message
    $report.clean = $false
} finally {
    if ($null -ne $process) {
        try {
            if (-not $process.HasExited) {
                # Kill only the retained launched process and its descendants.
                $process.Kill($true)
                if (-not $process.WaitForExit(10000)) { throw 'Owned process tree did not terminate.' }
            }
        } catch { $report.errors += ('Owned-process cleanup: ' + $_.Exception.Message); $exitCode = 1; $report.clean = $false }
        $process.Dispose()
    }
    $report.phase = 'completed'
    $report.completed_utc = [DateTime]::UtcNow.ToString('o')
    try { Write-SmokeReport }
    catch { Write-Host ('Cannot preserve smoke evidence: ' + $_.Exception.Message); $exitCode = 1 }
}
exit $exitCode

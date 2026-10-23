# Bounded, read-only headless qualification of the already-scanned console EXE.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$ExpectedInventoryPath,
    [Parameter(Mandatory = $true)][string]$FixturePath,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [ValidateRange(10, 120)][int]$TimeoutSeconds = 60
)
$ErrorActionPreference = 'Stop'
$reportFile = [IO.Path]::GetFullPath($ReportPath)
$folder = [IO.Path]::GetDirectoryName($reportFile)
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$report = [ordered]@{
    schema_version = 1; format = 'cli'; clean = $false; errors = @(); commands = @()
    executable_name = $null; sha256_before = $null; sha256_after = $null
    timeout_seconds_per_command = $TimeoutSeconds; output_limit_bytes_per_stream = 524288
    fixture_scope = 'procedural_only'; fixture_sha256_before = $null; fixture_sha256_after = $null
}
$item = $null
$fixture = $null
$fixtureEntries = @()
$exitCode = 1
function Write-CliSmokeReport {
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportFile -Encoding utf8
}
function Invoke-BoundedCli([string]$Name, [string[]]$Arguments) {
    $stdout = Join-Path $folder "cli-$Name.stdout.log"
    $stderr = Join-Path $folder "cli-$Name.stderr.log"
    $process = $null
    $row = [ordered]@{ name = $Name; exit_code = $null; timed_out = $false; output_limit = $false }
    try {
        # Start-Process joins its array without escaping; quote each argument
        # that needs Windows command-line escaping, including paths with spaces.
        $escapedArguments = @($Arguments | ForEach-Object {
            if ($_ -ne '' -and $_ -notmatch '[\s"]') { $_ }
            else {
                $escaped = [regex]::Replace($_, '(\\*)"', '$1$1\"')
                $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
                '"' + $escaped + '"'
            }
        })
        $process = Start-Process -FilePath $item.FullName -ArgumentList $escapedArguments -WindowStyle Hidden `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
        $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
        while (-not $process.WaitForExit(100)) {
            foreach ($outputFile in @($stdout, $stderr)) {
                if ((Test-Path -LiteralPath $outputFile) -and
                    (Get-Item -LiteralPath $outputFile).Length -gt 524288) {
                    $row.output_limit = $true
                    throw 'CLI output exceeds the qualification bound.'
                }
            }
            if ([DateTime]::UtcNow -gt $deadline) {
                $row.timed_out = $true
                throw 'CLI command exceeded its qualification timeout.'
            }
        }
        $row.exit_code = $process.ExitCode
        foreach ($outputFile in @($stdout, $stderr)) {
            if ((Get-Item -LiteralPath $outputFile).Length -gt 524288) {
                $row.output_limit = $true
                throw 'CLI output exceeds the qualification bound.'
            }
        }
        if ($row.exit_code -ne 0) { throw 'CLI command returned a failure exit code.' }
        if ((Get-Item -LiteralPath $stderr).Length -ne 0) { throw 'CLI command produced unexpected error output.' }
        return [IO.File]::ReadAllText($stdout)
    }
    finally {
        if ($null -ne $process) {
            if (-not $process.HasExited) {
                # The retained launch handle identifies only this process tree.
                $process.Kill($true)
                if (-not $process.WaitForExit(10000)) { throw 'CLI process tree did not stop after cleanup.' }
            }
            $process.Dispose()
        }
        $report.commands += $row
    }
}
function Assert-ExactIds($Rows, $Expected, [string]$Kind) {
    $ids = @($Rows | ForEach-Object { $_.id })
    $wanted = @($Expected)
    if ($ids.Count -ne $wanted.Count -or @($ids | Sort-Object -CaseSensitive -Unique).Count -ne $ids.Count -or
        @(Compare-Object ($ids | Sort-Object -CaseSensitive) ($wanted | Sort-Object -CaseSensitive) -CaseSensitive).Count -ne 0) {
        throw "CLI $Kind inventory differs from the tested source."
    }
}
try {
    Write-CliSmokeReport
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -or $item.Extension -ne '.exe' -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'CLI smoke requires an ordinary already-scanned Windows executable.'
    }
    $expectedFile = Get-Item -LiteralPath $ExpectedInventoryPath
    if ($expectedFile.Length -gt 524288) { throw 'Expected CLI inventory exceeds its bound.' }
    $expected = Get-Content -LiteralPath $expectedFile.FullName -Raw | ConvertFrom-Json
    $fixture = Get-Item -LiteralPath $FixturePath -Force
    if ($fixture.PSIsContainer -or $fixture.Length -gt 16777216 -or
        ($fixture.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'CLI fields smoke requires the bounded ordinary procedural fixture.'
    }
    $fixtureEntries = @(Get-ChildItem -LiteralPath $fixture.DirectoryName -Force | ForEach-Object { $_.Name } | Sort-Object)
    $report.fixture_sha256_before = (Get-FileHash -LiteralPath $fixture.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.executable_name = $item.Name
    $report.sha256_before = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $help = Invoke-BoundedCli 'help' @('--help')
    if ($help -notmatch 'games' -or $help -notmatch 'routes') { throw 'CLI help is missing its public command groups.' }
    $version = Invoke-BoundedCli 'version' @('--version')
    if ($version.Trim() -cne ('Universal Koei Tecmo Game Toolkit ' + $expected.version)) {
        throw 'Packaged CLI reports another product or version.'
    }
    $games = (Invoke-BoundedCli 'games' @('games', '--json')) | ConvertFrom-Json
    if ($games.schema -cne 'koei-toolkit-games' -or $games.schema_version -ne 1 -or
        $games.read_only -isnot [bool] -or $games.in_game_verified -isnot [bool] -or
        $games.read_only -ne $true -or $games.in_game_verified -ne $false -or
        $games.profile_count -ne @($expected.game_ids).Count -or
        $games.platform_count -ne $expected.platform_count) {
        throw 'CLI games JSON has an incorrect schema, count or compatibility claim.'
    }
    Assert-ExactIds $games.games $expected.game_ids 'game'
    $routes = (Invoke-BoundedCli 'routes' @('routes', '--json')) | ConvertFrom-Json
    if ($routes.schema -cne 'koei-toolkit-routes' -or $routes.schema_version -ne 1 -or
        $routes.read_only -isnot [bool] -or $routes.in_game_verified -isnot [bool] -or
        $routes.read_only -ne $true -or $routes.in_game_verified -ne $false -or
        $routes.route_count -ne @($expected.route_ids).Count) {
        throw 'CLI routes JSON has an incorrect schema, count or compatibility claim.'
    }
    Assert-ExactIds $routes.routes $expected.route_ids 'route'
    $fields = (Invoke-BoundedCli 'fields' @('fields', '--game', 'dw8xl', $fixture.FullName)) | ConvertFrom-Json
    $gold = @($fields.fields | Where-Object { $_.field -ceq 'gold' })
    $fieldIds = @($fields.fields | ForEach-Object { $_.field })
    if ($fields.success -isnot [bool] -or $fields.success -ne $true -or
        $fields.status -cne 'inspected' -or $fields.game_id -cne 'dw8xl' -or
        $fields.source_sha256 -cne $report.fixture_sha256_before -or
        $fieldIds.Count -eq 0 -or @($fieldIds | Sort-Object -CaseSensitive -Unique).Count -ne $fieldIds.Count -or
        $gold.Count -ne 1 -or $gold[0].kind -cne 'integer' -or
        ($gold[0].value -isnot [int] -and $gold[0].value -isnot [long]) -or $gold[0].value -ne 50) {
        throw 'CLI procedural fields inspection did not match the validated DW8 XL fixture.'
    }
    $report.clean = $true
    $exitCode = 0
}
catch { $report.errors += $_.Exception.Message }
finally {
    if ($null -ne $fixture) {
        try {
            $report.fixture_sha256_after = (Get-FileHash -LiteralPath $fixture.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            $afterEntries = @(Get-ChildItem -LiteralPath $fixture.DirectoryName -Force | ForEach-Object { $_.Name } | Sort-Object)
            if ($report.fixture_sha256_before -ne $report.fixture_sha256_after -or
                @(Compare-Object $fixtureEntries $afterEntries -CaseSensitive).Count -ne 0) {
                $report.clean = $false; $exitCode = 1
                $report.errors += 'The read-only CLI inspection changed its procedural fixture or created output files.'
            }
        }
        catch { $report.clean = $false; $exitCode = 1; $report.errors += 'CLI procedural fixture preservation failed.' }
    }
    if ($null -ne $item) {
        try {
            $report.sha256_after = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($report.sha256_before -ne $report.sha256_after) {
                $report.clean = $false; $exitCode = 1
                $report.errors += 'The CLI executable changed during qualification.'
            }
        }
        catch { $report.clean = $false; $exitCode = 1; $report.errors += 'CLI final hash verification failed.' }
    }
    Write-CliSmokeReport
}
exit $exitCode

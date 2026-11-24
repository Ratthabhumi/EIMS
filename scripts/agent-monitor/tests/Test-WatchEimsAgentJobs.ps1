<#
.SYNOPSIS
    Self-contained tests for Watch-EimsAgentJobs.ps1 (Windows PowerShell 5.1).

.DESCRIPTION
    No Pester, modules, network, database, or repository artifacts are used.
    Every test creates disposable synthetic artifact directories under %TEMP%,
    exercises the monitor's pure scan/tail functions, and removes only its own
    temporary directory afterwards.

    Run from anywhere:
      powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<repo>\scripts\agent-monitor\tests\Test-WatchEimsAgentJobs.ps1"

    Exit code 0 = all assertions passed; 1 = one or more assertions failed;
    2 = the monitor script could not be loaded.
#>
[CmdletBinding()]
param()

$savedErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Stop'

$script:Pass = 0
$script:Fail = 0
$script:TestRoot = Join-Path $env:TEMP ('eims-agent-monitor-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $script:TestRoot -Force | Out-Null

function Assert-Equal {
    param([object]$Expected, [object]$Actual, [string]$Message)
    if ($Actual -ne $Expected) {
        $script:Fail++
        Write-Host ('FAIL: {0} (expected [{1}], got [{2}])' -f $Message, $Expected, $Actual) -ForegroundColor Red
    }
    else { $script:Pass++ }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        $script:Fail++
        Write-Host ('FAIL: {0}' -f $Message) -ForegroundColor Red
    }
    else { $script:Pass++ }
}

function Invoke-Test {
    param([string]$Name, [scriptblock]$Body)
    try { & $Body }
    catch {
        $script:Fail++
        Write-Host ('FAIL: {0} - unexpected exception: {1}' -f $Name, $_.Exception.Message) -ForegroundColor Red
    }
}

function New-SyntheticJob {
    param([string]$Root, [string]$Id)
    $directory = Join-Path $Root $Id
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    return $directory
}

function Set-SyntheticFile {
    param([string]$Path, [AllowEmptyString()][string]$Content)
    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8 -NoNewline -ErrorAction Stop
}

function Add-SyntheticFile {
    param([string]$Path, [AllowEmptyString()][string]$Content)
    Add-Content -LiteralPath $Path -Value $Content -Encoding UTF8 -NoNewline -ErrorAction Stop
}

# Dot-source with -NoRun so the functions are available without starting a loop.
try {
    $monitorPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'Watch-EimsAgentJobs.ps1'
    . $monitorPath -NoRun
}
catch {
    Write-Host ('FATAL: could not load {0}: {1}' -f $monitorPath, $_.Exception.Message) -ForegroundColor Red
    if (Test-Path -LiteralPath $script:TestRoot) {
        Remove-Item -LiteralPath $script:TestRoot -Recurse -Force
    }
    exit 2
}

try {
    # -----------------------------------------------------------------------
    Invoke-Test -Name 'running -> completed, exactly one terminal alert' -Body {
        $root = Join-Path $script:TestRoot 'case-running-completed'
        $job = New-SyntheticJob -Root $root -Id 'job-running-1'
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'stderr.log') -Content ''

        $state = @{}
        $scan0 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($scan0.Statuses).Count 'one status for an in-flight job folder'
        Assert-Equal 'RUNNING' $scan0.Statuses[0].Lifecycle 'folder alone is RUNNING, not COMPLETED'
        Assert-Equal $false $scan0.Statuses[0].IsTerminal 'folder alone is not terminal'
        Assert-Equal 0 @($scan0.Terminals).Count 'no terminal alert for in-flight job'
        Assert-Equal 0 @($scan0.TailLines).Count 'no historical tail replay on first sight'

        Add-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content "line one`nline two`n"
        $scan1 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($scan1.TailLines).Count 'one tail event for appended stdout'
        Assert-True ($scan1.TailLines[0] -match 'line two') 'appended stdout text is tailed'
        Assert-Equal 'RUNNING' $scan1.Statuses[0].Lifecycle 'log growth alone is not completion'

        Set-SyntheticFile -Path (Join-Path $job 'exit.json') -Content '{"exitCode": 0, "status": "completed"}'
        $scan2 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 'COMPLETED' $scan2.Statuses[0].Lifecycle 'exit.json produces COMPLETED'
        Assert-Equal $true $scan2.Statuses[0].IsTerminal 'exit.json produces terminal'
        Assert-Equal '0' $scan2.Statuses[0].ExitCode 'exit code is displayed'
        Assert-Equal 1 @($scan2.Terminals).Count 'one terminal alert on transition'

        $scan3 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 0 @($scan3.Terminals).Count 'terminal alert is not repeated across polls'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'failed transitions across common field names' -Body {
        $root = Join-Path $script:TestRoot 'case-failed'
        $jobA = New-SyntheticJob -Root $root -Id 'job-fail-exit-code'
        Set-SyntheticFile -Path (Join-Path $jobA 'exit.json') -Content '{"exit_code": 2, "status": "failed"}'
        $jobB = New-SyntheticJob -Root $root -Id 'job-fail-code'
        Set-SyntheticFile -Path (Join-Path $jobB 'exit.json') -Content '{"code": 9}'
        $jobC = New-SyntheticJob -Root $root -Id 'job-fail-status'
        Set-SyntheticFile -Path (Join-Path $jobC 'exit.json') -Content '{"status": "error"}'

        $state = @{}
        $scan = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        $byId = @{}
        foreach ($s in $scan.Statuses) { $byId[$s.JobId] = $s }

        Assert-Equal 'FAILED' $byId['job-fail-exit-code'].Lifecycle 'exit_code + status failed => FAILED'
        Assert-Equal '2' $byId['job-fail-exit-code'].ExitCode 'exit_code is parsed'
        Assert-Equal 'FAILED' $byId['job-fail-code'].Lifecycle 'code field => FAILED'
        Assert-Equal '9' $byId['job-fail-code'].ExitCode 'code field is parsed'
        Assert-Equal 'FAILED' $byId['job-fail-status'].Lifecycle 'status error => FAILED'
        Assert-Equal '-' $byId['job-fail-status'].ExitCode 'missing exit code shown as dash'
        Assert-Equal 3 @($scan.Terminals).Count 'three failed jobs each alert once'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'incremental tail, truncation, replacement, partial line' -Body {
        $root = Join-Path $script:TestRoot 'case-tail'
        $job = New-SyntheticJob -Root $root -Id 'job-tail-1'
        $stdout = Join-Path $job 'stdout.log'
        Set-SyntheticFile -Path $stdout -Content ''

        $state = @{}
        $null = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)

        Add-SyntheticFile -Path $stdout -Content "alpha`n"
        $s1 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($s1.TailLines).Count 'alpha append produces one tail event'
        Assert-True ($s1.TailLines[0] -match 'alpha') 'alpha text captured'

        Add-SyntheticFile -Path $stdout -Content "beta`n"
        $s2 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($s2.TailLines).Count 'beta append produces one tail event'
        Assert-True ($s2.TailLines[0] -match 'beta') 'beta text captured'
        Assert-True ($s2.TailLines[0] -notmatch 'alpha') 'alpha is not repeated'

        Set-SyntheticFile -Path $stdout -Content "gamma`n"
        $s3 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($s3.TailLines).Count 'truncation produces one tail event'
        Assert-True ($s3.TailLines[0] -match 'gamma') 'truncated content is tailed from start'
        Assert-True ($s3.TailLines[0] -notmatch 'beta') 'pre-truncation content is not repeated'

        Remove-Item -LiteralPath $stdout -Force
        Set-SyntheticFile -Path $stdout -Content "delta one`ndelta two`n"
        $s4 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-True ($s4.TailLines[0] -match 'delta two') 'replaced file is tailed from start'
        Assert-True ($s4.TailLines[0] -notmatch 'gamma') 'pre-replacement content is not repeated'

        Add-SyntheticFile -Path $stdout -Content 'partial'
        $s5 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 0 @($s5.TailLines).Count 'incomplete line is held, not emitted'

        Add-SyntheticFile -Path $stdout -Content "`nfinished`n"
        $s6 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($s6.TailLines).Count 'completed line emitted as one tail event'
        Assert-True ($s6.TailLines[0] -match 'partial') 'held prefix included'
        Assert-True ($s6.TailLines[0] -match 'finished') 'held suffix included'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'malformed / absent exit.json never fabricates completion' -Body {
        $root = Join-Path $script:TestRoot 'case-malformed'
        $jobMalformed = New-SyntheticJob -Root $root -Id 'job-malformed'
        Set-SyntheticFile -Path (Join-Path $jobMalformed 'exit.json') -Content '{"exitCode":'
        $jobEmpty = New-SyntheticJob -Root $root -Id 'job-empty-exit'
        Set-SyntheticFile -Path (Join-Path $jobEmpty 'exit.json') -Content ''
        $jobNoFields = New-SyntheticJob -Root $root -Id 'job-no-fields'
        Set-SyntheticFile -Path (Join-Path $jobNoFields 'exit.json') -Content '{}'

        $state = @{}
        $scan = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 0 @($scan.Terminals).Count 'malformed exit.json produces no terminal alert'
        Assert-Equal 3 @($scan.Statuses).Count 'all three jobs still reported'

        $byId = @{}
        foreach ($s in $scan.Statuses) { $byId[$s.JobId] = $s }
        Assert-Equal 'UNKNOWN' $byId['job-malformed'].Lifecycle 'truncated JSON => UNKNOWN'
        Assert-Equal 'UNKNOWN' $byId['job-empty-exit'].Lifecycle 'empty exit.json => UNKNOWN'
        Assert-Equal 'UNKNOWN' $byId['job-no-fields'].Lifecycle 'empty object => UNKNOWN'
        Assert-True (@($scan.Warnings | Where-Object { $_ -match 'malformed JSON' }).Count -ge 1) 'malformed JSON warning surfaced'

        Set-SyntheticFile -Path (Join-Path $jobMalformed 'exit.json') -Content '{"exitCode": 0}'
        $scan2 = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($scan2.Terminals).Count 'job completes after valid exit.json appears'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'oversized JSON is bounded without parsing' -Body {
        $root = Join-Path $script:TestRoot 'case-oversized'
        $job = New-SyntheticJob -Root $root -Id 'job-oversized'
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        $big = '{"version":1,"files":{"probe":"' + ('b' * 600000) + '"}}'
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content $big

        $scan = Invoke-EimsAgentJobScan -ArtifactRoot $root -State @{} -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($scan.Statuses).Count 'oversized runner does not break the scan'
        Assert-True (@($scan.Warnings | Where-Object { $_ -match 'exceeds 512 KiB' }).Count -ge 1) `
            'oversized JSON is reported as a bounded warning'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'runner schema: runnerPid/agentPid means Running' -Body {
        $root = Join-Path $script:TestRoot 'case-real-runner'
        $job = New-SyntheticJob -Root $root -Id 'job-real-runner'
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'stderr.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content `
            '{"runnerPid":74260,"agentPid":73212,"startedAt":"2026-11-17T16:22:23.823Z","jobId":"job-real-runner","projectId":"eims","command":"opencode.exe","argCount":8,"node":"v24.14.1"}'

        $scan = Invoke-EimsAgentJobScan -ArtifactRoot $root -State @{} -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($scan.Statuses).Count 'one status for the real runner schema'
        Assert-Equal 'Running' $scan.Statuses[0].State 'runnerPid/agentPid maps to Running'
        Assert-Equal '73212' $scan.Statuses[0].Pid 'agentPid is displayed'
        Assert-Equal $false $scan.Statuses[0].IsTerminal 'live runner is not terminal'
    }

    Invoke-Test -Name 'runner schema: runnerPid alone means Running' -Body {
        $root = Join-Path $script:TestRoot 'case-runner-pid-only'
        $job = New-SyntheticJob -Root $root -Id 'job-runner-pid-only'
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content `
            '{"runnerPid":74261,"startedAt":"2026-11-17T16:22:23.823Z","command":"claude.exe"}'

        $scan = Invoke-EimsAgentJobScan -ArtifactRoot $root -State @{} -Now ([datetime]::UtcNow)
        Assert-Equal 'Running' $scan.Statuses[0].State 'runnerPid maps to Running'
        Assert-Equal '74261' $scan.Statuses[0].Pid 'runnerPid is displayed'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'runner/manifest secrets are never surfaced' -Body {
        $root = Join-Path $script:TestRoot 'case-safe-metadata'
        $job = New-SyntheticJob -Root $root -Id 'job-safe-1'
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content `
            '{"pid": 7331, "startedAt": "2026-11-17T01:02:03Z", "commandLine": "SUPER_SECRET_CMD", "env": {"TOKEN": "SUPER_SECRET_TOKEN"}, "prompt": "SUPER_SECRET_PROMPT"}'
        Set-SyntheticFile -Path (Join-Path $job 'manifest.json') -Content `
            '{"jobId": "job-safe-1", "apiKey": "SUPER_SECRET_KEY"}'

        $state = @{}
        $scan = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -Now ([datetime]::UtcNow)
        Assert-Equal '7331' $scan.Statuses[0].Pid 'only allowlisted PID metadata is displayed'
        $serialized = $scan | ConvertTo-Json -Depth 8
        Assert-True ($serialized -notmatch 'SUPER_SECRET') 'no secret-bearing field leaked into scan result'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'missing root and JobId filter' -Body {
        $missing = Join-Path $script:TestRoot 'does-not-exist'
        $state = @{}
        $scanMissing = Invoke-EimsAgentJobScan -ArtifactRoot $missing -State $state -Now ([datetime]::UtcNow)
        Assert-Equal $false $scanMissing.RootExists 'missing root reported'
        Assert-Equal 0 @($scanMissing.Statuses).Count 'missing root has no statuses'
        Assert-True (@($scanMissing.Warnings).Count -ge 1) 'missing root emits a warning, not a crash'

        $root = Join-Path $script:TestRoot 'case-filter'
        $null = New-SyntheticJob -Root $root -Id 'job-filter-1'
        $null = New-SyntheticJob -Root $root -Id 'job-filter-2'
        $filtered = Invoke-EimsAgentJobScan -ArtifactRoot $root -State @{} -JobId 'job-filter-2' -Now ([datetime]::UtcNow)
        Assert-Equal 1 @($filtered.Statuses).Count 'JobId filter selects one job'
        Assert-Equal 'job-filter-2' $filtered.Statuses[0].JobId 'JobId filter selects the requested job'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'synthetic fixture detected as completed' -Body {
        $fixtureSource = Join-Path $PSScriptRoot 'fixtures'
        if (Test-Path -LiteralPath $fixtureSource -PathType Container) {
            $target = Join-Path $script:TestRoot 'case-fixture'
            Copy-Item -LiteralPath $fixtureSource -Destination $target -Recurse -Force
            $scan = Invoke-EimsAgentJobScan -ArtifactRoot $target -State @{} -Now ([datetime]::UtcNow)
            Assert-Equal 1 @($scan.Statuses).Count 'fixture job discovered'
            Assert-Equal 'COMPLETED' $scan.Statuses[0].Lifecycle 'fixture exit.json yields COMPLETED'
            Assert-Equal '0' $scan.Statuses[0].ExitCode 'fixture exit code is 0'
        }
        else {
            Assert-True $false 'fixtures directory is present'
        }
    }
}
finally {
    if (Test-Path -LiteralPath $script:TestRoot) {
        Remove-Item -LiteralPath $script:TestRoot -Recurse -Force
    }
    $ErrorActionPreference = $savedErrorActionPreference
}

# ---------------------------------------------------------------------------
# Dashboard / TUI regression tests. These run after the artifact-fixture tests
# and manage their own disposable root (the shared one was removed above).
# ---------------------------------------------------------------------------
$dashRoot = Join-Path $env:TEMP ('eims-agent-monitor-dashboard-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $dashRoot -Force | Out-Null

function New-DashJob {
    param([string]$Id, [AllowNull()][string]$ExitJson)
    $dir = Join-Path $dashRoot $Id
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Set-SyntheticFile -Path (Join-Path $dir 'stdout.log') -Content "out`r`n"
    Set-SyntheticFile -Path (Join-Path $dir 'stderr.log') -Content ''
    if ($null -ne $ExitJson -and $ExitJson -ne '__none__') {
        Set-SyntheticFile -Path (Join-Path $dir 'exit.json') -Content $ExitJson
    }
    return $dir
}

function Get-DashStatus {
    param([string]$Id)
    return Get-EimsJobStatus -JobFolder (Get-Item -LiteralPath (Join-Path $dashRoot $Id)) -Now ([datetime]::UtcNow)
}

try {
    New-DashJob -Id 'job-completed' -ExitJson '{"exitCode":0,"status":"completed"}' | Out-Null
    New-DashJob -Id 'job-failed'    -ExitJson '{"exitCode":1,"status":"failed"}' | Out-Null
    New-DashJob -Id 'job-cancelled' -ExitJson '{"status":"cancelled"}' | Out-Null
    New-DashJob -Id 'job-pending'   -ExitJson '{"status":"queued"}' | Out-Null
    New-DashJob -Id 'job-unknown'   -ExitJson '{not json' | Out-Null
    New-DashJob -Id 'job-running'   -ExitJson '__none__' | Out-Null
    Set-SyntheticFile -Path (Join-Path $dashRoot 'job-running\runner.json') -Content '{"pid":1234}'
    New-DashJob -Id 'job-bare'      -ExitJson '__none__' | Out-Null
    New-DashJob -Id 'job-bigex'     -ExitJson '{"exitCode":4294967295}' | Out-Null
    New-DashJob -Id 'job-timedout'  -ExitJson '{"status":"timed_out","timedOut":true}' | Out-Null
    New-DashJob -Id 'job-timedout-flag' -ExitJson '{"timedOut":true}' | Out-Null
    New-DashJob -Id 'job-hugeexit' -ExitJson '{"exitCode":9223372036854775808}' | Out-Null

    Assert-Equal 'Completed' (Get-DashStatus 'job-completed').State 'state mapping: exit 0 is Completed'
    Assert-Equal 'Failed'    (Get-DashStatus 'job-failed').State    'state mapping: exit 1 is Failed'
    Assert-Equal 'Cancelled' (Get-DashStatus 'job-cancelled').State 'state mapping: cancelled is Cancelled'
    Assert-Equal 'Pending'   (Get-DashStatus 'job-pending').State   'state mapping: queued is Pending'
    Assert-Equal 'Unknown'   (Get-DashStatus 'job-unknown').State   'state mapping: malformed exit.json is Unknown'
    Assert-Equal 'Running'   (Get-DashStatus 'job-running').State   'state mapping: a live runner pid is Running'
    Assert-Equal 'Unknown'   (Get-DashStatus 'job-bare').State      'state mapping: a bare folder is never Running'
    Assert-Equal '4294967295' (Get-DashStatus 'job-bigex').ExitCode 'large Int64 exit code preserved'
    Assert-Equal 'TimedOut' (Get-DashStatus 'job-timedout').State 'timed_out status maps to TimedOut'
    Assert-Equal 'TimedOut' (Get-DashStatus 'job-timedout-flag').State 'timedOut flag maps to TimedOut'
    $huge = Get-DashStatus 'job-hugeexit'
    Assert-Equal 'Unknown' $huge.State 'out-of-range exit code becomes Unknown instead of disappearing'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$huge.UnknownReason)) 'out-of-range exit code has a reason'

    # Job display metadata (Chat_HAND job.json contract).
    Set-SyntheticFile -Path (Join-Path $dashRoot 'job-completed\job.json') -Content '{"taskTitle":"Monitor UX","taskId":"task-1","agentId":"opencode","agentDisplayName":"OpenCode","role":"read_only","cwd":"scripts/agent-monitor"}'
    $metaStatus = Get-DashStatus 'job-completed'
    Assert-Equal 'Monitor UX' $metaStatus.TaskTitle 'job.json taskTitle is displayed'
    Assert-Equal 'Monitor UX' $metaStatus.TaskLabel 'taskTitle is the row label'
    Assert-Equal 'OpenCode' $metaStatus.Agent 'agent display name is displayed'
    Assert-Equal 'read_only' $metaStatus.Role 'role is displayed'
    Assert-Equal 'task-1' $metaStatus.TaskId 'task id is displayed'
    $unknownStatus = Get-DashStatus 'job-unknown'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$unknownStatus.UnknownReason)) 'Unknown explains why instead of only ?'
    Assert-True ($unknownStatus.UnknownReason -notmatch '^\?$') 'Unknown reason is actionable text'
    Assert-Equal 'job-completed' (Resolve-EimsDashboardSelection -Statuses @($metaStatus) -View 'Overview' -SelectedJobId '') 'single-row dashboard auto-selects the only job'
    Assert-Equal 'job-completed' (Resolve-EimsDashboardSelection -Statuses @($metaStatus) -View 'Result' -SelectedJobId 'job-completed') 'single-row explicit selection is preserved'
    Assert-Equal $null (Resolve-EimsDashboardSelection -Statuses @() -View 'Overview' -SelectedJobId '') 'empty dashboard has no selection'

    $dashStatuses = @($metaStatus, $unknownStatus, (Get-DashStatus 'job-running'), (Get-DashStatus 'job-failed'))
    $resultFrame = @(Render-EimsDashboard -Statuses $dashStatuses -View 'Result' -SelectedJobId 'job-completed' `
        -Unicode $false -Root $dashRoot -IntervalSeconds 2 -Now ([datetime]::UtcNow) -LastScan ([datetime]::UtcNow))
    $resultText = ($resultFrame -join "`n")
    Assert-True ($resultText -match 'final result') 'Final Result view is available'
    Assert-True ($resultText -match 'Monitor UX') 'task title appears in the dashboard'
    Assert-True ($resultText -match 'OpenCode') 'agent name appears in the dashboard'
    Assert-True ($resultText -match 'last refresh=') 'header shows last refresh'

    $errorsFrame = @(Render-EimsDashboard -Statuses $dashStatuses -View 'Errors' -SelectedJobId 'job-failed' `
        -Unicode $false -Root $dashRoot -IntervalSeconds 2 -Now ([datetime]::UtcNow) -LastScan ([datetime]::UtcNow))
    Assert-True ((($errorsFrame -join "`n")) -match 'errors: stderr') 'Errors section is available'

    $artifactsFrame = @(Render-EimsDashboard -Statuses $dashStatuses -View 'Artifacts' -SelectedJobId 'job-completed' `
        -Unicode $false -Root $dashRoot -IntervalSeconds 2 -Now ([datetime]::UtcNow) -LastScan ([datetime]::UtcNow))
    Assert-True ((($artifactsFrame -join "`n")) -match 'stdout\.log') 'Artifacts section lists files'

    $infoFrame = @(Render-EimsDashboard -Statuses $dashStatuses -View 'Info' -SelectedJobId 'job-completed' `
        -Unicode $false -Root $dashRoot -IntervalSeconds 2 -Now ([datetime]::UtcNow) -LastScan ([datetime]::UtcNow))
    Assert-True ((($infoFrame -join "`n")) -match 'taskId=task-1') 'Info section shows lifecycle metadata'

    $monitorSource = Get-Content -LiteralPath $monitorPath -Raw
    Assert-True ($monitorSource -notmatch 'Stop-Process|taskkill|agent\.cancel') 'monitor has no job-control path; Q only closes the view'

    $frozenA = Get-EimsJobStatus -JobFolder (Get-Item -LiteralPath (Join-Path $dashRoot 'job-completed')) -Now ([datetime]::UtcNow)
    $frozenB = Get-EimsJobStatus -JobFolder (Get-Item -LiteralPath (Join-Path $dashRoot 'job-completed')) -Now ([datetime]::UtcNow.AddHours(2))
    Assert-Equal $frozenA.Elapsed $frozenB.Elapsed 'terminal elapsed time is frozen'
    Assert-True ($null -ne $frozenA.EndUtc) 'terminal job records an end timestamp'
    Assert-True ($null -eq (Get-DashStatus 'job-running').EndUtc) 'running job has no end timestamp'

    $state = @{}
    $scanOld = Invoke-EimsAgentJobScan -ArtifactRoot $dashRoot -State $state -SinceUtc ([datetime]::UtcNow.AddHours(1))
    Assert-Equal 0 $scanOld.Terminals.Count 'historical terminal jobs do not alert on first sight'
    $state2 = @{}
    $scanNew = Invoke-EimsAgentJobScan -ArtifactRoot $dashRoot -State $state2 -SinceUtc ([datetime]::UtcNow.AddDays(-1))
    Assert-True ($scanNew.Terminals.Count -ge 3) 'terminal jobs completed inside the window do alert'

    $missing = Invoke-EimsAgentJobScan -ArtifactRoot (Join-Path $dashRoot 'does-not-exist') -State @{}
    Assert-Equal $false $missing.RootExists 'missing artifact root is reported, not thrown'
    Assert-True ($missing.Warnings.Count -ge 1) 'missing artifact root produces a warning'

    $statuses = @(
        [pscustomobject]@{ JobId='a'; State='Running'; ExitCode='-'; Elapsed='00:01:00'; LastActivity='2026-11-17 10:00:00'; StdoutBytes=1; StderrBytes=0; Pid=1; Note=''; StdoutPath=''; StderrPath=''; EndUtc=$null },
        [pscustomobject]@{ JobId='b'; State='Completed'; ExitCode='0'; Elapsed='00:02:00'; LastActivity='2026-11-17 11:00:00'; StdoutBytes=2; StderrBytes=0; Pid=2; Note=''; StdoutPath=''; StderrPath=''; EndUtc=$null },
        [pscustomobject]@{ JobId='c'; State='Failed'; ExitCode='1'; Elapsed='00:03:00'; LastActivity='2026-11-17 12:00:00'; StdoutBytes=3; StderrBytes=0; Pid=3; Note=''; StdoutPath=''; StderrPath=''; EndUtc=$null }
    )
    $overview = (Render-EimsDashboard -Statuses $statuses -View 'Overview' -SelectedJobId 'b' -Unicode:$false) -join "`n"
    Assert-True ($overview -match 'Total 3') 'overview shows the total'
    Assert-True ($overview -match 'Running 1') 'overview counts running'
    Assert-True ($overview -match 'Completed 1') 'overview counts completed'
    Assert-True ($overview -match 'Failed 1') 'overview counts failed'
    Assert-True ($overview -match '> b') 'selected job is marked in the table'

    $active = (Render-EimsDashboard -Statuses $statuses -View 'Active' -SelectedJobId 'a' -Unicode:$false) -join "`n"
    Assert-True ($active -match '> a ') 'active view lists the running job'
    $activeUnknown = (Render-EimsDashboard -Statuses @([pscustomobject]@{ JobId='z'; State='Unknown'; ExitCode='-'; Elapsed='00:00:01'; LastActivity='2026-11-17 09:00:00'; StdoutBytes=0; StderrBytes=0; Pid='-'; Note=''; StdoutPath=''; StderrPath=''; EndUtc=$null }) -View 'Active' -SelectedJobId 'z' -Unicode:$false) -join [Environment]::NewLine
    Assert-True ($activeUnknown -match '> z ') 'active view includes Unknown jobs'
    Assert-True ($active -notmatch ' b ') 'active view excludes completed jobs'

    $history = (Render-EimsDashboard -Statuses $statuses -View 'History' -SelectedJobId 'b' -Unicode:$false) -join "`n"
    $posC = $history.IndexOf(' c ')
    $posB = $history.IndexOf(' b ')
    Assert-True ($posC -ge 0 -and $posB -ge 0 -and $posC -lt $posB) 'history is newest first'

    $bigLog = Join-Path $dashRoot 'job-completed\stdout.log'
    $chunk = ('x' * 900) + "`r`n"
    for ($i = 0; $i -lt 30; $i++) { Add-SyntheticFile -Path $bigLog -Content $chunk }
    $logsStatus = @([pscustomobject]@{ JobId='job-completed'; State='Completed'; ExitCode='0'; Elapsed='00:01:00'; LastActivity='2026-11-17 10:00:00'; StdoutBytes=27000; StderrBytes=0; Pid=1; Note=''; StdoutPath=$bigLog; StderrPath=''; EndUtc=$null })
    $logsView = (Render-EimsDashboard -Statuses $logsStatus -View 'Logs' -SelectedJobId 'job-completed' -Unicode:$false) -join "`n"
    Assert-True ($logsView -match 'log truncated') 'log view states truncation explicitly'
    Assert-True ($logsView -match '\| ') 'log lines are prefixed'

    $dirty = "plain " + [char]27 + "[31mred" + [char]27 + "[0m" + " " + [char]7 + [char]0 + " tail"
    $safe = ConvertTo-EimsSafeText -Text $dirty
    Assert-True ($safe -notmatch ([string][char]27)) 'ANSI escapes are stripped'
    Assert-True ($safe -notmatch ([string][char]7)) 'control characters are stripped'
    $secret = ConvertTo-EimsSafeText -Text ('token sk-' + ('A' * 24))
    Assert-True ($secret -match '\[REDACTED\]') 'secret-shaped tokens are masked'
    Assert-True ($secret -notmatch 'sk-AAAA') 'raw secret is not shown'

$emptyFrame = @(Render-EimsDashboard -Statuses @() -View 'Overview' -SelectedJobId $null -Unicode:$false)
    Assert-True ($emptyFrame.Count -gt 0) 'dashboard renders with no jobs'

    $anchorTime = [datetime]::UtcNow
    $elapsed = Format-EimsElapsed -Now $anchorTime.AddMinutes(100) -StartUtc $anchorTime
    Assert-Equal '01:40:00' $elapsed 'elapsed hours are floored, not rounded'

    foreach ($pattern in @(
            @{ Text = ('token ghp_' + ('B' * 20)); Name = 'GitHub token' },
            @{ Text = ('AKIA' + ('C' * 16)); Name = 'AWS key id' },
            @{ Text = ('password=' + 'hunter2'); Name = 'password= value' },
            @{ Text = ('eyJ' + ('d' * 12) + '.' + ('e' * 12) + '.' + ('f' * 12)); Name = 'JWT' })) {
        $masked = ConvertTo-EimsSafeText -Text $pattern.Text
        Assert-True ($masked -match '\[REDACTED\]') ('secret masked: ' + $pattern.Name)
        Assert-True ($masked -notmatch [regex]::Escape($pattern.Text)) ('raw secret absent: ' + $pattern.Name)
    }
    $word = ConvertTo-EimsSafeText -Text 'risk-assessment'
    Assert-Equal 'risk-assessment' $word 'ordinary kebab-case words are not mangled'

    $crOnly = ConvertTo-EimsSafeText -Text ('a' + [char]13 + 'b' + [char]0x9B + 'c')
    Assert-True ($crOnly -notmatch ([string][char]13)) 'lone CR is stripped'
    Assert-True ($crOnly -notmatch ([string][char]0x9B)) 'C1 control is stripped'

    $noTailState = @{}
    $noTailScan = Invoke-EimsAgentJobScan -ArtifactRoot $dashRoot -State $noTailState -NoTail
    Assert-Equal 0 $noTailScan.TailLines.Count 'dashboard scan can skip log tailing'

    $wide = ConvertTo-EimsSafeText -Text ('y' * 300) -MaxChars 50
    Assert-True ($wide.Length -le 53) 'long log lines are bounded'

    # -----------------------------------------------------------------------
    # Persistent dashboard lifecycle (idle is a display state, never an exit)
    # -----------------------------------------------------------------------
    $modeDefault = Resolve-EimsDashboardRuntimeMode -InputRedirected $false
    Assert-Equal 'persistent' $modeDefault.Mode 'interactive dashboard defaults to persistent'
    Assert-Equal $true $modeDefault.Persistent 'interactive dashboard is persistent'
    $modeExplicit = Resolve-EimsDashboardRuntimeMode -Persistent -InputRedirected $false
    Assert-Equal 'persistent' $modeExplicit.Mode 'explicit -Persistent stays persistent'
    $modeSnap = Resolve-EimsDashboardRuntimeMode -Snapshot -InputRedirected $false
    Assert-Equal 'snapshot' $modeSnap.Mode 'explicit -Snapshot is one frame'
    $modeRedirected = Resolve-EimsDashboardRuntimeMode -InputRedirected $true
    Assert-Equal 'snapshot' $modeRedirected.Mode 'redirected stdin never blocks on a key prompt'
    Assert-True ($modeRedirected.Reason -match 'redirected') 'redirected stdin explains the snapshot'
    $modeRedirectedExplicit = Resolve-EimsDashboardRuntimeMode -Persistent -InputRedirected $true
    Assert-Equal 'snapshot' $modeRedirectedExplicit.Mode 'persistent + redirected stdin degrades to snapshot'
    Assert-True ($modeRedirectedExplicit.Reason -match 'persistent requested') 'degradation is explicit, not silent'

    $idleInfo = Get-EimsDashboardIdleState -Statuses @()
    Assert-Equal $true $idleInfo.IsIdle 'zero jobs is idle'
    $doneStatus = Get-DashStatus 'job-completed'
    Assert-Equal $true (Get-EimsDashboardIdleState -Statuses @($doneStatus)).IsIdle 'all-terminal jobs are idle'
    Assert-Equal $false (Get-EimsDashboardIdleState -Statuses @($doneStatus, (Get-DashStatus 'job-running'))).IsIdle 'a running job is not idle'
    Assert-Equal $false (Get-EimsDashboardIdleState -Statuses @((Get-DashStatus 'job-bare'))).IsIdle 'an unknown/bare job is not idle'

    # Zero-job persistent session: it must keep rendering frames and must NOT
    # exit on idleness. MaxFrames is the only bound.
    $emptyRoot = Join-Path $dashRoot 'empty-root'
    New-Item -ItemType Directory -Path $emptyRoot -Force | Out-Null
    $script:IdleFrames = New-Object System.Collections.ArrayList
    $idleSession = Invoke-EimsDashboardSession -Root $emptyRoot -IntervalSeconds 1 -Mode 'persistent' `
        -MaxFrames 5 -KeyProvider { param($wait) '' } `
        -FrameWriter { param($frameLines, $useAnsi) [void]$script:IdleFrames.Add(($frameLines -join "`n")) }
    Assert-Equal 5 $idleSession.Frames 'idle persistent session keeps rendering frames'
    Assert-Equal 'max-frames' $idleSession.ExitReason 'idle alone never ends a persistent session'
    Assert-Equal $true $idleSession.Idle 'session reports idle'
    Assert-True ($script:IdleFrames[0] -match 'IDLE') 'zero-job frame states IDLE explicitly'
    Assert-True ($script:IdleFrames[0] -match 'mode=persistent') 'zero-job frame states persistent mode'
    Assert-True ($script:IdleFrames[0] -match 'Total 0') 'zero-job frame shows zero counts'
    Assert-True ($script:IdleFrames[0] -match 'Agent jobs keep running') 'frame states that jobs are unaffected'

    # Explicit Quit is the only interactive exit; it happens on the key frame.
    $script:QuitKeys = @('', '', 'Q')
    $script:QuitIndex = 0
    $quitSession = Invoke-EimsDashboardSession -Root $emptyRoot -IntervalSeconds 1 -Mode 'persistent' `
        -KeyProvider {
            param($wait)
            if ($script:QuitIndex -ge $script:QuitKeys.Count) { return '' }
            $key = $script:QuitKeys[$script:QuitIndex]
            $script:QuitIndex++
            return $key
        } -FrameWriter { param($frameLines, $useAnsi) }
    Assert-Equal 3 $quitSession.Frames 'frames render until the explicit quit key'
    Assert-Equal 'quit' $quitSession.ExitReason 'Q is reported as the exit reason'

    $script:EscKeys = @('H', 'Escape', 'Escape')
    $script:EscIndex = 0
    $escSession = Invoke-EimsDashboardSession -Root $dashRoot -IntervalSeconds 1 -Mode 'persistent' `
        -KeyProvider {
            param($wait)
            if ($script:EscIndex -ge $script:EscKeys.Count) { return '' }
            $key = $script:EscKeys[$script:EscIndex]
            $script:EscIndex++
            return $key
        } -FrameWriter { param($frameLines, $useAnsi) }
    Assert-Equal 'quit' $escSession.ExitReason 'Esc quits only from the Overview'
    Assert-Equal 'Overview' $escSession.View 'Esc first returns to Overview'
    Assert-Equal 3 $escSession.Frames 'view change and quit take one frame each'

    # Snapshot mode is deterministic: exactly one frame, no key wait.
    $snapSession = Invoke-EimsDashboardSession -Root $emptyRoot -Mode 'snapshot' `
        -FrameWriter { param($frameLines, $useAnsi) }
    Assert-Equal 1 $snapSession.Frames 'snapshot renders exactly one frame'
    Assert-Equal 'snapshot' $snapSession.ExitReason 'snapshot exit reason is explicit'

    # One-row dashboard: the single job is rendered, selected, and counted.
    $oneRoot = Join-Path $dashRoot 'one-row-root'
    $oneJob = Join-Path $oneRoot 'job-only'
    New-Item -ItemType Directory -Path $oneJob -Force | Out-Null
    Set-SyntheticFile -Path (Join-Path $oneJob 'stdout.log') -Content "hello`n"
    Set-SyntheticFile -Path (Join-Path $oneJob 'job.json') -Content '{"taskTitle":"One Row","agentDisplayName":"OpenCode"}'
    Set-SyntheticFile -Path (Join-Path $oneJob 'exit.json') -Content '{"exitCode":0}'
    $script:OneFrames = New-Object System.Collections.ArrayList
    $oneSession = Invoke-EimsDashboardSession -Root $oneRoot -Mode 'snapshot' `
        -FrameWriter { param($frameLines, $useAnsi) [void]$script:OneFrames.Add(($frameLines -join "`n")) }
    Assert-Equal 1 $oneSession.Frames 'one-row dashboard renders one frame'
    Assert-Equal 'job-only' $oneSession.SelectedJobId 'one-row dashboard selects its only job'
    Assert-True ($script:OneFrames[0] -match '> job-only') 'one-row dashboard marks the selected job'
    Assert-True ($script:OneFrames[0] -match 'One Row') 'one-row dashboard shows the task title'
    Assert-True ($script:OneFrames[0] -match 'OpenCode') 'one-row dashboard shows the agent'
    Assert-True ($script:OneFrames[0] -match 'Total 1') 'one-row dashboard count is correct'
    Assert-True ($script:OneFrames[0] -match 'IDLE') 'terminal-only dashboard is shown as idle'

    # No-job dashboard: a missing root is called out, not silently blank.
    $missingRoot = Join-Path $dashRoot 'missing-root-does-not-exist'
    $missingFrame = (Render-EimsDashboard -Statuses @() -View 'Overview' -SelectedJobId $null `
        -Unicode:$false -Root $missingRoot -Mode 'persistent' -RefreshInSeconds 3) -join "`n"
    Assert-True ($missingFrame -match 'root MISSING') 'missing root is explicit in the dashboard'
    Assert-True ($missingFrame -match 'mode=persistent') 'missing root still reports persistent mode'
    Assert-True ($missingFrame -match 'next refresh=3s') 'dashboard shows the next refresh'

    # Agent survival: a live "agent" (dummy process) recorded in runner.json is
    # still alive after a dashboard session is quit. The monitor must never
    # signal it.
    $script:SurvivalDummy = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 45') `
        -PassThru -WindowStyle Hidden
    try {
        $survRoot = Join-Path $dashRoot 'survival-root'
        $survJob = Join-Path $survRoot 'job-survive'
        New-Item -ItemType Directory -Path $survJob -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $survJob 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $survJob 'runner.json') -Content `
            ('{{"runnerPid":{0},"startedAt":"2026-11-18T01:00:00.000Z","command":"opencode.exe"}}' -f $script:SurvivalDummy.Id)
        $script:SurvKeys = @('Q')
        $script:SurvIndex = 0
        $survSession = Invoke-EimsDashboardSession -Root $survRoot -Mode 'persistent' `
            -KeyProvider {
                param($wait)
                if ($script:SurvIndex -ge $script:SurvKeys.Count) { return 'Q' }
                $key = $script:SurvKeys[$script:SurvIndex]
                $script:SurvIndex++
                return $key
            } -FrameWriter { param($frameLines, $useAnsi) }
        Assert-Equal 'Running' $survSession.Statuses[0].State 'surviving dummy is observed as Running'
        Assert-Equal 'quit' $survSession.ExitReason 'dashboard quit is explicit'
        $alive = $false
        try { $null = Get-Process -Id $script:SurvivalDummy.Id -ErrorAction Stop; $alive = $true } catch { }
        Assert-True $alive 'agent process survives dashboard shutdown'
        Assert-True (-not $script:SurvivalDummy.HasExited) 'agent process has not exited'
    }
    finally {
        if ($null -ne $script:SurvivalDummy) {
            try { if (-not $script:SurvivalDummy.HasExited) { Stop-Process -Id $script:SurvivalDummy.Id -Force } } catch { }
        }
    }

    # Static guard: the monitor has no job-control or process-kill path at all.
    Assert-True ($monitorSource -notmatch 'Stop-Process|taskkill|/T\b') 'monitor cannot signal or tree-kill a process'

    # Entry-point mode guards (subprocess, so the throw is real and bounded).
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $conflictOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $monitorPath `
            -Dashboard -Persistent -Snapshot -NoColor 2>&1 | Out-String
        Assert-True ($conflictOutput -match 'either -Persistent or -Snapshot') `
            'persistent and snapshot are mutually exclusive'

        $needsDashboard = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $monitorPath `
            -Snapshot -NoColor 2>&1 | Out-String
        Assert-True ($needsDashboard -match 'require -Dashboard') `
            'snapshot requires -Dashboard'
    }
    finally { $ErrorActionPreference = $saved }
}
catch {
    # A thrown exception must count as a failure; the results line must never
    # say "0 failed" because a test body aborted early.
    $script:Fail++
    Write-Host ('FAIL: dashboard lifecycle tests - unexpected exception: {0}' -f $_.Exception.Message) -ForegroundColor Red
}
finally {
    if (Test-Path -LiteralPath $dashRoot) { Remove-Item -LiteralPath $dashRoot -Recurse -Force }
}

Write-Host ('Results: {0} passed, {1} failed' -f $script:Pass, $script:Fail)
if ($script:Fail -gt 0) { exit 1 }
exit 0

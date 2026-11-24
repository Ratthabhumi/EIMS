<#
.SYNOPSIS
    Windows Trigger C integration: host the persistent EIMS Agent Monitor
    dashboard in a visible console when an eligible job starts or on -Open.

.DESCRIPTION
    This is the EIMS-side auto-launch counterpart of the Chat_HAND Trigger C
    lifecycle. It never runs, cancels, or approves an agent job. It observes the
    same local artifact directory as Watch-EimsAgentJobs.ps1 and hosts the
    existing Dashboard TUI, which is PERSISTENT:

        powershell.exe -WindowStyle Normal  ->  EimsMonitorHost.ps1
                                              ->  Watch-EimsAgentJobs.ps1 -Dashboard -Persistent

    Persistent lifecycle contract:
      - The dashboard stays open when there are zero jobs. There is no idle timer
        and no auto-close in this scope; it exits only on explicit user Q, Esc
        from the Overview, Ctrl+C, or closing the console window.
      - Closing the dashboard never stops, cancels, or signals an agent job. The
        monitor is a read-only observer and has no job-control code path. Cleanup
        only ever stops a host whose lease is held and whose PID, process start
        time, nonce, AND CIM command line all match the state record, never a
        process tree, so an OpenCode/Claude runner tree cannot be reached. Missing
        or incomplete evidence fails closed: the PID is left alone.
      - Single instance is preserved: the exclusive lease, the atomic state claim,
        and the process marker suppress a second window. A record left behind by a
        hard window close (dead PID, or a pid=0 claim older than the grace period)
        is reclaimed only after its nonce is re-validated and its PID is proven
        not live, so it cannot block every future launch.

    Design properties:
      - Idempotent / single instance: an exclusive lease plus an atomic state-file
        claim suppress duplicate windows (including a second launcher instance).
      - No focus stealing: Start-Process -WindowStyle Normal; no SetForegroundWindow,
        AppActivate, or forced foreground calls.
      - Windows PowerShell 5.1, no modules, no external dependencies.
      - Headless safe: non-interactive sessions are detected before any process is
        spawned; no window, no keyboard wait, and no unbounded loop.
      - State records are nonce-bound and process-identity checked. The host
        releases its lease and restores the terminal on every managed exit path
        (Q, Esc, Ctrl+C, exception).

    All decision logic is in pure/injectable functions so it can be tested without
    opening a window. -NoRun defines functions only; -DryRun evaluates and reports
    a launch decision without spawning anything.

.PARAMETER Open
    Open the persistent dashboard now, even with zero jobs (and even when the
    artifact root does not exist yet), then exit. This is the explicit
    user-facing "start the dashboard" mode. It still honours headless fallback,
    single-instance suppression, and -DryRun.

.PARAMETER ArtifactRoot
    Artifact root passed to the TUI. Defaults to the same root as the watcher.

.PARAMETER MonitorScript
    Path to Watch-EimsAgentJobs.ps1. Defaults to the sibling script.

.PARAMETER HostScript
    Path to EimsMonitorHost.ps1. Defaults to the sibling script.

.PARAMETER StateDirectory
    Directory holding monitor.lease and monitor.json. Defaults to
    %LOCALAPPDATA%\EimsAgentMonitor.

.PARAMETER AllowedAgents
    Optional agent allowlist. When supplied, a running job triggers a window only
    if its manifest/runner agent token is in this list. Explicit agent keys are
    preferred; the runner `command` basename is used as a fallback
    (claude.exe -> claude_code, opencode.exe -> opencode).

.PARAMETER PollSeconds
    Poll interval for -Watch (1..3600). Default 2.

.PARAMETER Watch
    Continuously evaluate launches; an existing owned window suppresses further
    launches until it closes.

.PARAMETER Once
    Evaluate job eligibility exactly once and exit. Default when neither -Watch,
    -Open, -Cleanup, nor -Diagnose is set.

.PARAMETER DryRun
    Evaluate and report the decision; never spawn a process or create a claim.

.PARAMETER Diagnose
    Print artifact root, scan counts, eligible job ids, session/duplicate state,
    persistent mode, and the resulting decision, then exit without spawning or
    claiming.

.PARAMETER Cleanup
    Stop the owned monitor host (PID, start time, nonce and CIM command line must
    all match; exact PID only, never a tree) and remove its state. Incomplete or
    mismatched evidence is not-owned, so no signal is sent.

.PARAMETER NoProcessScan
    Internal test hook: treat the live-process duplicate scan as empty. Never use
    this to claim a real window is closed; ownership is still lease/state checked.

.PARAMETER NoRun
    Internal test hook: define functions but do not run the entry point.
#>
[CmdletBinding()]
param(
    [string]$ArtifactRoot,
    [string]$MonitorScript,
    [string]$HostScript,
    [string]$StateDirectory,
    [string[]]$AllowedAgents = @(),
    [ValidateRange(1, 3600)]
    [int]$PollSeconds = 2,
    [switch]$Watch,
    [switch]$Once,
    [switch]$Open,
    [switch]$DryRun,
    [switch]$Diagnose,
    [switch]$Cleanup,
    [switch]$NoProcessScan,
    [switch]$NoRun
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Paths and state
# ---------------------------------------------------------------------------
function Resolve-EimsAutoLaunchPath {
    param([string]$Path, [Parameter(Mandatory = $true)][string]$FileName)
    if (-not [string]::IsNullOrWhiteSpace($Path)) {
        return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    }
    return (Join-Path $PSScriptRoot $FileName)
}

function Resolve-EimsAutoLaunchStateDirectory {
    param([string]$Directory)
    if ([string]::IsNullOrWhiteSpace($Directory)) {
        $local = $env:LOCALAPPDATA
        if ([string]::IsNullOrWhiteSpace($local)) {
            $local = Join-Path $env:USERPROFILE 'AppData\Local'
        }
        $Directory = Join-Path $local 'EimsAgentMonitor'
    }
    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Directory)
}

function Resolve-EimsAutoLaunchArtifactRoot {
    param([string]$Root)
    if (-not [string]::IsNullOrWhiteSpace($Root)) {
        return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Root)
    }
    $local = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($local)) {
        $local = Join-Path $env:USERPROFILE 'AppData\Local'
    }
    return (Join-Path $local 'ChatHandControlPlane\artifacts\eims')
}

function Get-EimsAutoLaunchStateFilePath {
    param([Parameter(Mandatory = $true)][string]$Directory)
    return (Join-Path $Directory 'monitor.json')
}

function Get-EimsAutoLaunchLeaseFilePath {
    param([Parameter(Mandatory = $true)][string]$Directory)
    return (Join-Path $Directory 'monitor.lease')
}

function ConvertTo-EimsAutoLaunchUtc {
    param([AllowEmptyString()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    $offsetValue = [datetimeoffset]::MinValue
    $styles = [System.Globalization.DateTimeStyles]::AssumeUniversal -bor
              [System.Globalization.DateTimeStyles]::AdjustToUniversal
    if ([datetimeoffset]::TryParse(
            $Value,
            [System.Globalization.CultureInfo]::InvariantCulture,
            $styles,
            [ref]$offsetValue)) {
        return $offsetValue.UtcDateTime
    }
    return $null
}

function Read-EimsAutoLaunchState {
    param([Parameter(Mandatory = $true)][string]$StateFile)
    if (-not (Test-Path -LiteralPath $StateFile -PathType Leaf)) { return $null }
    try {
        $info = Get-Item -LiteralPath $StateFile -ErrorAction Stop
        if ($info.Length -gt 65536L) { return $null }
        $text = [System.IO.File]::ReadAllText($StateFile)
        if ([string]::IsNullOrWhiteSpace($text)) { return $null }
        return ($text | ConvertFrom-Json -ErrorAction Stop)
    }
    catch { return $null }
}

function Write-EimsAutoLaunchState {
    param(
        [Parameter(Mandatory = $true)][string]$StateFile,
        [Parameter(Mandatory = $true)][object]$Record
    )
    $parent = Split-Path -Parent $StateFile
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $json = $Record | ConvertTo-Json -Depth 6 -Compress
    [System.IO.File]::WriteAllText(
        $StateFile, $json, (New-Object System.Text.UTF8Encoding($false)))
}

function New-EimsAutoLaunchClaim {
    param(
        [Parameter(Mandatory = $true)][string]$StateFile,
        [Parameter(Mandatory = $true)][object]$Record
    )
    $parent = Split-Path -Parent $StateFile
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $json = $Record | ConvertTo-Json -Depth 6 -Compress
    try {
        # CreateNew is the atomic single-winner claim: two launchers racing on the
        # same state directory cannot both open the file.
        $stream = [System.IO.File]::Open(
            $StateFile, [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try {
            $bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes($json)
            $stream.Write($bytes, 0, $bytes.Length)
        }
        finally { $stream.Dispose() }
        return $true
    }
    catch { return $false }
}

function Clear-EimsAutoLaunchState {
    param(
        [Parameter(Mandatory = $true)][string]$StateFile,
        [AllowEmptyString()][string]$Nonce = '',
        [AllowNull()][object]$LeaseStream
    )
    if ($null -ne $LeaseStream) { try { $LeaseStream.Dispose() } catch { } }
    if (-not (Test-Path -LiteralPath $StateFile -PathType Leaf)) { return $true }
    $record = Read-EimsAutoLaunchState -StateFile $StateFile
    $recordedNonce = if ($null -ne $record) { [string]$record.nonce } else { '' }
    if ([string]::IsNullOrEmpty($Nonce) -or
        [string]::Equals($recordedNonce, $Nonce, [StringComparison]::Ordinal)) {
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
        return -not (Test-Path -LiteralPath $StateFile -PathType Leaf)
    }
    return $false
}

# ---------------------------------------------------------------------------
# Eligibility (pure / injectable)
# ---------------------------------------------------------------------------
function ConvertTo-EimsAutoLaunchAgentToken {
    param([AllowNull()][object]$Value)
    if ($null -eq $Value -or $Value -is [bool]) { return '' }
    $candidate = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($candidate)) { return '' }
    # `command` may be a path or include arguments; use the executable basename.
    $first = ($candidate -split '\s+')[0]
    try { $base = [System.IO.Path]::GetFileNameWithoutExtension($first) }
    catch { $base = $first }
    if ([string]::IsNullOrWhiteSpace($base)) { return '' }
    $normalized = $base.Trim().ToLowerInvariant()
    switch ($normalized) {
        'claude'      { return 'claude_code' }
        'claude-code' { return 'claude_code' }
        'claude_code' { return 'claude_code' }
        'opencode'    { return 'opencode' }
        default {
            if ($normalized.Length -le 64 -and $normalized -match '^[a-z0-9._-]+$') { return $normalized }
        }
    }
    return ''
}

function Get-EimsAutoLaunchAgentToken {
    param([Parameter(Mandatory = $true)][string]$JobFolder)
    # runner.json is small and is the authoritative live metadata. manifest.json
    # in this deployment can be a multi-megabyte file manifest, so read it only
    # as a fallback and only when it is small enough to be identity metadata.
    foreach ($name in @('runner.json', 'manifest.json')) {
        $path = Join-Path $JobFolder $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        try {
            $file = [System.IO.FileInfo]::new($path)
            if ($file.Length -gt 262144) { continue }
            $text = [System.IO.File]::ReadAllText($path)
            if ([string]::IsNullOrWhiteSpace($text)) { continue }
            $data = $text | ConvertFrom-Json -ErrorAction Stop
            $value = Get-EimsPropertyValue -Object $data -Names @(
                'agent', 'agentId', 'agent_id', 'agentName', 'provider')
            $token = ConvertTo-EimsAutoLaunchAgentToken -Value $value
            if (-not [string]::IsNullOrEmpty($token)) { return $token }
            # The real Chat_HAND runner.json identifies the executable in
            # `command` (for example opencode.exe or claude.exe), not an agent id.
            $command = Get-EimsPropertyValue -Object $data -Names @(
                'command', 'executable', 'exe', 'commandName')
            $token = ConvertTo-EimsAutoLaunchAgentToken -Value $command
            if (-not [string]::IsNullOrEmpty($token)) { return $token }
        }
        catch { continue }
    }
    return ''
}

function Test-EimsAutoLaunchSafeJobId {
    param([AllowEmptyString()][string]$JobId)
    if ([string]::IsNullOrWhiteSpace($JobId)) { return $false }
    if ($JobId -notmatch '^[A-Za-z0-9._-]+$') { return $false }
    # Dots are allowed in real job ids, but a relative traversal name must never
    # be used to build a folder path for agent-token lookup.
    if ($JobId -eq '.' -or $JobId -eq '..' -or $JobId -like '*..*') { return $false }
    return $true
}

function Test-EimsAutoLaunchEligibility {
    param(
        [AllowNull()][object]$Status,
        [AllowEmptyString()][string]$AgentToken = '',
        [string[]]$AllowedAgents = @()
    )
    if ($null -eq $Status) { return $false }
    if ($true -eq $Status.IsTerminal) { return $false }

    $jobId = [string]$Status.JobId
    if (-not (Test-EimsAutoLaunchSafeJobId -JobId $jobId)) { return $false }

    $state = [string]$Status.State
    if ($state -notin @('Running', 'Pending')) { return $false }

    if ($null -ne $AllowedAgents -and $AllowedAgents.Count -gt 0) {
        $token = ([string]$AgentToken).Trim().ToLowerInvariant()
        if ([string]::IsNullOrEmpty($token)) { return $false }
        $match = @($AllowedAgents | Where-Object {
            ([string]$_).Trim().ToLowerInvariant() -eq $token
        })
        if ($match.Count -eq 0) { return $false }
    }
    return $true
}

function Get-EimsAutoLaunchEligibleFromScan {
    param(
        [Parameter(Mandatory = $true)][object]$Scan,
        [Parameter(Mandatory = $true)][string]$ArtifactRoot,
        [string[]]$AllowedAgents = @()
    )
    $eligible = @()
    foreach ($status in @($Scan.Statuses)) {
        if ($null -eq $status) { continue }
        if ($true -eq $status.IsTerminal) { continue }
        if ([string]$status.State -notin @('Running', 'Pending')) { continue }
        $jobId = [string]$status.JobId
        if (-not (Test-EimsAutoLaunchSafeJobId -JobId $jobId)) { continue }

        # No allowlist means the agent token is irrelevant; do not read job
        # metadata (which may include a large file manifest) at all.
        if ($null -eq $AllowedAgents -or $AllowedAgents.Count -eq 0) {
            if (Test-EimsAutoLaunchEligibility -Status $status -AgentToken '' -AllowedAgents @()) {
                $eligible += $status
            }
            continue
        }

        $agent = Get-EimsAutoLaunchAgentToken -JobFolder (Join-Path $ArtifactRoot $jobId)
        if (Test-EimsAutoLaunchEligibility -Status $status -AgentToken $agent `
                                             -AllowedAgents $AllowedAgents) {
            $eligible += $status
        }
    }
    return @($eligible)
}

function Get-EimsAutoLaunchEligibleJobs {
    param(
        [Parameter(Mandatory = $true)][string]$ArtifactRoot,
        [string[]]$AllowedAgents = @(),
        [datetime]$Now = ([datetime]::UtcNow)
    )
    $scanState = @{}
    $scan = Invoke-EimsAgentJobScan -ArtifactRoot $ArtifactRoot -State $scanState `
                                    -Now $Now -NoTail
    return @(Get-EimsAutoLaunchEligibleFromScan -Scan $scan -ArtifactRoot $ArtifactRoot `
                                                -AllowedAgents $AllowedAgents)
}

function Get-EimsAutoLaunchScanCounts {
    param([Parameter(Mandatory = $true)][object]$Scan)
    $counts = [ordered]@{
        Scanned = 0; Pending = 0; Running = 0; Completed = 0
        Failed = 0; Cancelled = 0; TimedOut = 0; Unknown = 0; Terminal = 0
    }
    foreach ($status in @($Scan.Statuses)) {
        $counts.Scanned++
        $state = [string]$status.State
        if ($counts.Contains($state)) { $counts[$state]++ } else { $counts.Unknown++ }
        if ($true -eq $status.IsTerminal) { $counts.Terminal++ }
    }
    return [pscustomobject]$counts
}

function Get-EimsAutoLaunchDiagnosis {
    param(
        [Parameter(Mandatory = $true)][string]$ArtifactRoot,
        [string]$StateDirectory = '',
        [string[]]$AllowedAgents = @(),
        [AllowNull()][object]$Session = $null,
        [AllowNull()][object[]]$Processes = $null,
        [datetime]$Now = ([datetime]::UtcNow)
    )
    $scan = Invoke-EimsAgentJobScan -ArtifactRoot $ArtifactRoot -State @{} -Now $Now -NoTail
    $counts = Get-EimsAutoLaunchScanCounts -Scan $scan
    $eligible = @(Get-EimsAutoLaunchEligibleFromScan -Scan $scan -ArtifactRoot $ArtifactRoot `
                                                      -AllowedAgents $AllowedAgents)
    $sessionCheck = Test-EimsAutoLaunchInteractiveSession -Session $Session
    $duplicate = $false
    if ($sessionCheck.Interactive -and -not [string]::IsNullOrWhiteSpace($StateDirectory)) {
        $duplicate = Test-EimsAutoLaunchDuplicateWindow -StateDirectory $StateDirectory `
                                                        -Processes $Processes -Now $Now
    }

    $decision = ''
    if (-not $scan.RootExists) {
        $decision = 'artifact root unavailable: ' + $ArtifactRoot
    }
    elseif (-not $sessionCheck.Interactive) {
        $decision = 'headless fallback: ' + $sessionCheck.Reason
    }
    elseif ($eligible.Count -eq 0) {
        $decision = ('no eligible running job (scanned={0}, pending={1}, running={2}, terminal={3}, timedout={4}, unknown={5})' -f `
            $counts.Scanned, $counts.Pending, $counts.Running, $counts.Terminal, $counts.TimedOut, $counts.Unknown)
    }
    elseif ($duplicate) {
        $decision = 'duplicate window suppressed'
    }
    else {
        $decision = 'eligible job found; would launch'
    }

    return [pscustomobject]@{
        ArtifactRoot  = $ArtifactRoot
        RootExists    = [bool]$scan.RootExists
        Scanned       = $counts.Scanned
        Pending       = $counts.Pending
        Running       = $counts.Running
        Completed     = $counts.Completed
        Failed        = $counts.Failed
        Cancelled     = $counts.Cancelled
        TimedOut      = $counts.TimedOut
        Unknown       = $counts.Unknown
        Terminal      = $counts.Terminal
        EligibleJobs  = $eligible.Count
        EligibleJobIds = @($eligible | ForEach-Object { [string]$_.JobId })
        AllowedAgents = @($AllowedAgents)
        Interactive   = [bool]$sessionCheck.Interactive
        SessionReason = $sessionCheck.Reason
        Duplicate     = [bool]$duplicate
        Decision      = $decision
        Warnings      = @($scan.Warnings)
    }
}

# ---------------------------------------------------------------------------
# Interactive / headless detection (pure / injectable)
# ---------------------------------------------------------------------------
function Get-EimsAutoLaunchSessionInfo {
    $inputRedirected = $true
    $outputRedirected = $true
    $userInteractive = $false
    try { $inputRedirected = [Console]::IsInputRedirected } catch { }
    try { $outputRedirected = [Console]::IsOutputRedirected } catch { }
    try { $userInteractive = [Environment]::UserInteractive } catch { }
    return [pscustomobject]@{
        UserInteractive  = [bool]$userInteractive
        InputRedirected  = [bool]$inputRedirected
        OutputRedirected = [bool]$outputRedirected
        HostName         = [string]$Host.Name
        SessionName      = [string]$env:SESSIONNAME
    }
}

function Test-EimsAutoLaunchInteractiveSession {
    param([AllowNull()][object]$Session)
    if ($null -eq $Session) { $Session = Get-EimsAutoLaunchSessionInfo }

    if (-not $Session.UserInteractive) {
        return [pscustomobject]@{ Interactive = $false; Reason = 'non-interactive session' }
    }
    $sessionName = ([string]$Session.SessionName).Trim().ToLowerInvariant()
    if ($sessionName -in @('service', 'noninteractive')) {
        return [pscustomobject]@{ Interactive = $false; Reason = 'service session has no desktop' }
    }
    $hostName = ([string]$Session.HostName).Trim()
    $knownConsoleHosts = @('ConsoleHost', 'PowerShell ISE Host')
    if ($Session.InputRedirected -and $Session.OutputRedirected -and
        $hostName -notin $knownConsoleHosts) {
        return [pscustomobject]@{ Interactive = $false; Reason = 'redirected I/O in non-console host' }
    }
    return [pscustomobject]@{ Interactive = $true; Reason = '' }
}

# ---------------------------------------------------------------------------
# Lease and duplicate-window suppression
# ---------------------------------------------------------------------------
function New-EimsAutoLaunchLease {
    param([Parameter(Mandatory = $true)][string]$LeasePath)
    $parent = Split-Path -Parent $LeasePath
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    try {
        return [System.IO.File]::Open(
            $LeasePath, [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    }
    catch { return $null }
}

function Test-EimsAutoLaunchLeaseHeld {
    param([Parameter(Mandatory = $true)][string]$LeasePath)
    if (-not (Test-Path -LiteralPath $LeasePath -PathType Leaf)) { return $false }
    try {
        # FileShare.None succeeds only when nobody else holds the lease.
        $probe = [System.IO.File]::Open(
            $LeasePath, [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $probe.Dispose()
        return $false
    }
    catch {
        # A sharing violation (or any inability to take the lease) is treated as
        # "held" so a duplicate window is never opened.
        return $true
    }
}

function Get-EimsAutoLaunchMonitorProcessIds {
    param([AllowNull()][object[]]$Processes)
    $ids = @()
    $selfPid = $PID
    foreach ($process in @($Processes)) {
        if ($null -eq $process) { continue }
        $commandLine = [string]$process.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) { continue }
        $processId = 0
        if (-not [int]::TryParse([string]$process.ProcessId, [ref]$processId) -or $processId -le 0) { continue }
        if ($processId -eq $selfPid) { continue }
        # Match the actual -File invocation, not a shell -Command that merely
        # mentions the script names. This prevents test harnesses, editors, or
        # diagnostic shells from suppressing a real launch.
        if ($commandLine -match '(?i)-Command\b') { continue }
        $isHost = $commandLine -match '(?i)-File\s+.*EimsMonitorHost\.ps1'
        if ($isHost) { $ids += $processId; continue }
        $isTui = $commandLine -match '(?i)-File\s+.*Watch-EimsAgentJobs\.ps1'
        if ($isTui -and $commandLine -match '(?i)-Dashboard') { $ids += $processId }
    }
    return @($ids | Select-Object -Unique)
}

function Get-EimsAutoLaunchRunningMonitorProcesses {
    try {
        $all = @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop |
                 Select-Object -Property ProcessId, CommandLine)
        return @(Get-EimsAutoLaunchMonitorProcessIds -Processes $all)
    }
    catch { return @() }
}

function Test-EimsAutoLaunchDuplicateWindow {
    param(
        [Parameter(Mandatory = $true)][string]$StateDirectory,
        [AllowNull()][object[]]$Processes,
        [datetime]$Now = ([datetime]::UtcNow)
    )
    $leasePath = Get-EimsAutoLaunchLeaseFilePath -Directory $StateDirectory
    if (Test-EimsAutoLaunchLeaseHeld -LeasePath $leasePath) { return $true }

    $stateFile = Get-EimsAutoLaunchStateFilePath -Directory $StateDirectory
    $record = Read-EimsAutoLaunchState -StateFile $stateFile
    if ($null -ne $record) {
        $trackedPid = 0
        [void][int]::TryParse([string]$record.pid, [ref]$trackedPid)
        if ($trackedPid -gt 0) {
            try {
                $process = Get-Process -Id $trackedPid -ErrorAction Stop
                # Suppression only. This is a weak liveness identity check; it is
                # never used to authorize a signal (see the ownership section).
                if (Test-EimsAutoLaunchLiveIdentity -Record $record -Process $process) {
                    return $true
                }
            }
            catch {
                # Stale identity record (dead/recycled process); not a live duplicate.
            }
        }
        else {
            $claimedAt = ConvertTo-EimsAutoLaunchUtc -Value ([string]$record.claimedAt)
            if ($null -ne $claimedAt -and ($Now - $claimedAt).TotalSeconds -lt 30) {
                return $true
            }
        }
    }

    $processIds = if ($null -eq $Processes) {
        @(Get-EimsAutoLaunchRunningMonitorProcesses)
    }
    else {
        @(Get-EimsAutoLaunchMonitorProcessIds -Processes $Processes)
    }
    return ($processIds.Count -gt 0)
}

# ---------------------------------------------------------------------------
# Ownership / cleanup (identity-checked, fail closed)
# ---------------------------------------------------------------------------
function Get-EimsAutoLaunchProcessStartText {
    param([AllowNull()][object]$Process)
    if ($null -eq $Process) { return '' }
    # Injectable test doubles may supply the exact recorded text directly.
    if ($null -ne $Process.PSObject.Properties['StartTimeText']) {
        return [string]$Process.StartTimeText
    }
    $value = $null
    try { $value = $Process.StartTime } catch { return '' }
    if ($null -eq $value) { return '' }
    try { return ([datetime]$value).ToUniversalTime().ToString('o') } catch { return '' }
}

function Test-EimsAutoLaunchLiveIdentity {
    param(
        [AllowNull()][object]$Record,
        [AllowNull()][object]$Process
    )
    # Liveness identity only: PID plus the exact process start time. An
    # incomplete record or unreadable start time is never "live", so a stale or
    # tampered record cannot suppress launches or authorize work.
    if ($null -eq $Record -or $null -eq $Process) { return $false }

    $recordPid = 0L
    if (-not [long]::TryParse([string]$Record.pid, [ref]$recordPid) -or $recordPid -le 0) {
        return $false
    }
    $processId = 0L
    if (-not [long]::TryParse([string]$Process.Id, [ref]$processId) -or $processId -le 0) {
        return $false
    }
    if ($recordPid -ne $processId) { return $false }

    $recordedStart = [string]$Record.startedAt
    if ([string]::IsNullOrWhiteSpace($recordedStart)) { return $false }
    $processStart = Get-EimsAutoLaunchProcessStartText -Process $Process
    if ([string]::IsNullOrWhiteSpace($processStart)) { return $false }
    return [string]::Equals($recordedStart, $processStart, [StringComparison]::Ordinal)
}

function Test-EimsAutoLaunchMonitorCommandLine {
    param([AllowEmptyString()][string]$CommandLine)
    # FAIL CLOSED. A signal requires positive proof that this process is our
    # monitor host. An unavailable/empty command line, a blank line, or a shell
    # -Command that merely mentions the script names is NOT proof, so it is
    # treated as not-owned and the PID is left untouched.
    if ([string]::IsNullOrWhiteSpace($CommandLine)) { return $false }
    if ($CommandLine -match '(?i)-Command\b') { return $false }
    return [bool]($CommandLine -match '(?i)-File\s+.*(EimsMonitorHost|Watch-EimsAgentJobs)\.ps1')
}

function Test-EimsAutoLaunchOwnedProcess {
    param(
        [AllowNull()][object]$Record,
        [AllowNull()][object]$Process,
        [AllowEmptyString()][string]$CommandLine = ''
    )
    if ($null -eq $Record -or $null -eq $Process) { return $false }

    # Claim evidence: only a record written through a launcher claim is
    # removable. A record with no nonce cannot prove provenance, so it is not
    # owned and must never be signalled.
    if ([string]::IsNullOrWhiteSpace([string]$Record.nonce)) { return $false }

    # Process identity evidence: exact PID and exact start time. A blank
    # startedAt cannot distinguish the owned host from a recycled PID, and a
    # recycled PID must never be signalled on behalf of a dead host.
    if (-not (Test-EimsAutoLaunchLiveIdentity -Record $Record -Process $Process)) {
        return $false
    }

    # Defense in depth: even if the identity record were corrupted to point at an
    # agent/runner process, a known non-monitor (or missing) command line is
    # refused.
    return (Test-EimsAutoLaunchMonitorCommandLine -CommandLine $CommandLine)
}

function Get-EimsAutoLaunchStopArguments {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [switch]$Force
    )
    # NEVER /T: only the exact owned host PID is signalled. A runner tree is
    # never enumerated or killed, even if it were somehow a descendant.
    if ($Force) { return @('/PID', [string]$ProcessId, '/F') }
    return @('/PID', [string]$ProcessId)
}

function Stop-EimsAutoLaunchOwnedProcess {
    param(
        [AllowNull()][object]$Record,
        [AllowNull()][object]$Process,
        [AllowNull()][scriptblock]$StopAction,
        [AllowEmptyString()][string]$CommandLine = '',
        [switch]$Force
    )
    if (-not (Test-EimsAutoLaunchOwnedProcess -Record $Record -Process $Process -CommandLine $CommandLine)) {
        return $false
    }
    $targetPid = [int]$Process.Id
    if ($null -ne $StopAction) {
        & $StopAction -ProcessId $targetPid -Force:$Force
        return $true
    }

    $taskkill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
    if (-not (Test-Path -LiteralPath $taskkill -PathType Leaf)) { $taskkill = 'taskkill.exe' }
    try {
        # Graceful first: taskkill without /F lets the host release its lease and
        # lets the TUI restore the terminal. No /T is ever used.
        $graceful = Get-EimsAutoLaunchStopArguments -ProcessId $targetPid
        & $taskkill @graceful 2>$null | Out-Null
        if (-not $Force) { Start-Sleep -Milliseconds 400 }
        $survivor = $null
        try { $survivor = Get-Process -Id $targetPid -ErrorAction Stop }
        catch { return $true }
        # Re-prove ownership on the surviving process before the forced kill: the
        # original PID may have exited and been recycled during the graceful wait,
        # and a recycled PID must never be signalled.
        if (-not (Test-EimsAutoLaunchOwnedProcess -Record $Record -Process $survivor `
                                                  -CommandLine $CommandLine)) {
            return $false
        }
        # Only a re-verified owned process is force-killed, still by exact PID and
        # never as a tree.
        $forced = Get-EimsAutoLaunchStopArguments -ProcessId $targetPid -Force
        & $taskkill @forced 2>$null | Out-Null
        return $true
    }
    catch { return $false }
}

# ---------------------------------------------------------------------------
# Stale claim reclamation (nonce-validated)
# ---------------------------------------------------------------------------
function Get-EimsAutoLaunchLiveProcessIdentity {
    param([Parameter(Mandatory = $true)][long]$ProcessId)
    if ($ProcessId -le 0) { return $null }
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        return [pscustomobject]@{
            Id            = [long]$process.Id
            StartTimeText = (Get-EimsAutoLaunchProcessStartText -Process $process)
        }
    }
    catch { return $null }
}

function Remove-EimsAutoLaunchStaleState {
    param(
        [Parameter(Mandatory = $true)][string]$StateFile,
        [datetime]$Now = ([datetime]::UtcNow),
        # Test seam: receives the recorded PID and returns $null (not live) or an
        # object with Id/StartTimeText. Production uses Get-Process.
        [AllowNull()][scriptblock]$ProcessIdentity = $null,
        [ValidateRange(0, 86400)][int]$ProvisionalGraceSeconds = 30
    )
    # Returns: missing | leased | provisional | live | changed | reclaimed | failed
    if (-not (Test-Path -LiteralPath $StateFile -PathType Leaf)) { return 'missing' }

    # A held lease is positive proof that an owned host is alive: the host takes
    # the lease before it publishes its identity record. Never reclaim under it.
    $directory = Split-Path -Parent $StateFile
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        $leasePath = Get-EimsAutoLaunchLeaseFilePath -Directory $directory
        if (Test-EimsAutoLaunchLeaseHeld -LeasePath $leasePath) { return 'leased' }
    }

    $record = Read-EimsAutoLaunchState -StateFile $StateFile
    if ($null -eq $record) {
        # Unreadable/truncated record: no nonce exists to validate, so require a
        # stable, aged file, an identical second read, and a free lease before it
        # is removed. A launcher always writes complete JSON in one write.
        try { $info = Get-Item -LiteralPath $StateFile -ErrorAction Stop }
        catch { return 'failed' }
        if (($Now.ToUniversalTime() - $info.LastWriteTimeUtc).TotalSeconds -lt
            $ProvisionalGraceSeconds) {
            return 'provisional'
        }
        $stamp = $info.LastWriteTimeUtc.Ticks
        $again = $null
        try { $again = Get-Item -LiteralPath $StateFile -ErrorAction Stop }
        catch { return 'changed' }
        if ($again.LastWriteTimeUtc.Ticks -ne $stamp) { return 'changed' }
        if ($null -ne (Read-EimsAutoLaunchState -StateFile $StateFile)) { return 'changed' }
        try { Remove-Item -LiteralPath $StateFile -Force -ErrorAction Stop }
        catch { return 'failed' }
        if (Test-Path -LiteralPath $StateFile -PathType Leaf) { return 'failed' }
        return 'reclaimed'
    }

    $recordPid = 0L
    [void][long]::TryParse([string]$record.pid, [ref]$recordPid)
    if ($recordPid -gt 0) {
        # Prove the recorded PID is not live. A live PID whose start time differs
        # is a recycled PID, so the record is stale.
        $identity = if ($null -ne $ProcessIdentity) { & $ProcessIdentity $recordPid }
                    else { Get-EimsAutoLaunchLiveProcessIdentity -ProcessId $recordPid }
        if ($null -ne $identity -and
            (Test-EimsAutoLaunchLiveIdentity -Record $record -Process $identity)) {
            return 'live'
        }
    }
    else {
        # pid=0 is the launcher's provisional claim, valid only for the grace
        # window between the atomic claim and the host publishing its identity.
        $claimedAt = ConvertTo-EimsAutoLaunchUtc -Value ([string]$record.claimedAt)
        if ($null -ne $claimedAt -and
            ($Now.ToUniversalTime() - $claimedAt).TotalSeconds -lt $ProvisionalGraceSeconds) {
            return 'provisional'
        }
    }

    # Compare-and-delete on the validated record. If a faster launcher replaced
    # the record while we were proving it stale, the nonce (or any other field)
    # differs and the new record wins. This is the nonce validation that makes
    # reclamation safe.
    $fingerprint = ('{0}|{1}|{2}' -f [string]$record.pid, [string]$record.nonce,
                    [string]$record.startedAt)
    $confirmed = Read-EimsAutoLaunchState -StateFile $StateFile
    if ($null -eq $confirmed) { return 'changed' }
    $confirmedFingerprint = ('{0}|{1}|{2}' -f [string]$confirmed.pid,
                             [string]$confirmed.nonce, [string]$confirmed.startedAt)
    if (-not [string]::Equals($fingerprint, $confirmedFingerprint,
                              [StringComparison]::Ordinal)) {
        return 'changed'
    }

    try { Remove-Item -LiteralPath $StateFile -Force -ErrorAction Stop }
    catch { return 'failed' }
    if (Test-Path -LiteralPath $StateFile -PathType Leaf) { return 'failed' }
    return 'reclaimed'
}

function Get-EimsAutoLaunchPowerShellExe {
    $full = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (Test-Path -LiteralPath $full -PathType Leaf) { return $full }
    return 'powershell.exe'
}

function Format-EimsAutoLaunchArgument {
    param([AllowEmptyString()][string]$Value)
    # Start-Process 5.1 joins -ArgumentList with spaces. Single quotes wrapping an
    # embedded double-quoted value keep paths with spaces intact.
    $inner = ([string]$Value).Replace("'", "''").Replace('"', '""')
    return ("'" + '"' + $inner + '"' + "'")
}

# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
function New-EimsAutoLaunchHostArgumentList {
    param(
        [Parameter(Mandatory = $true)][string]$MonitorScript,
        [Parameter(Mandatory = $true)][string]$HostScript,
        [Parameter(Mandatory = $true)][string]$ArtifactRoot,
        [Parameter(Mandatory = $true)][string]$StateFile,
        [Parameter(Mandatory = $true)][string]$LeasePath,
        [Parameter(Mandatory = $true)][string]$Nonce,
        [int]$PollSeconds = 2,
        [ValidateSet('Persistent', 'Snapshot')]
        [string]$Mode = 'Persistent'
    )
    return @(
        (Format-EimsAutoLaunchArgument '-NoProfile'),
        (Format-EimsAutoLaunchArgument '-ExecutionPolicy'),
        (Format-EimsAutoLaunchArgument 'Bypass'),
        (Format-EimsAutoLaunchArgument '-File'),
        (Format-EimsAutoLaunchArgument $HostScript),
        (Format-EimsAutoLaunchArgument '-MonitorScript'),
        (Format-EimsAutoLaunchArgument $MonitorScript),
        (Format-EimsAutoLaunchArgument '-ArtifactRoot'),
        (Format-EimsAutoLaunchArgument $ArtifactRoot),
        (Format-EimsAutoLaunchArgument '-StateFile'),
        (Format-EimsAutoLaunchArgument $StateFile),
        (Format-EimsAutoLaunchArgument '-LeasePath'),
        (Format-EimsAutoLaunchArgument $LeasePath),
        (Format-EimsAutoLaunchArgument '-Nonce'),
        (Format-EimsAutoLaunchArgument $Nonce),
        (Format-EimsAutoLaunchArgument '-Mode'),
        (Format-EimsAutoLaunchArgument $Mode),
        (Format-EimsAutoLaunchArgument '-PollSeconds'),
        (Format-EimsAutoLaunchArgument ([string]$PollSeconds))
    )
}

function Start-EimsAutoLaunchHost {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [AllowNull()][scriptblock]$StartAction = $null
    )
    if ($null -ne $StartAction) {
        # Injectable for tests: receives the argument list, returns a
        # process-like object with an Id, and never spawns a console.
        return (& $StartAction $Arguments)
    }
    return (Start-Process -FilePath (Get-EimsAutoLaunchPowerShellExe) `
                          -ArgumentList $Arguments `
                          -PassThru -WindowStyle Normal)
}

function Invoke-EimsAutoLaunch {
    param(
        [Parameter(Mandatory = $true)][string]$ArtifactRoot,
        [Parameter(Mandatory = $true)][string]$MonitorScript,
        [Parameter(Mandatory = $true)][string]$HostScript,
        [Parameter(Mandatory = $true)][string]$StateDirectory,
        [int]$PollSeconds = 2,
        [string[]]$AllowedAgents = @(),
        [AllowNull()][object]$Session = $null,
        [AllowNull()][object[]]$Processes = $null,
        [datetime]$Now = ([datetime]::UtcNow),
        [switch]$DryRun,
        # -Open is the explicit persistent-dashboard mode: open now, even with
        # zero jobs and even when the artifact root does not exist yet.
        [switch]$Open,
        [AllowNull()][scriptblock]$StartAction = $null,
        # Test seam for stale-record reclamation (see
        # Remove-EimsAutoLaunchStaleState). Production uses Get-Process.
        [AllowNull()][scriptblock]$ProcessIdentity = $null
    )

    $result = [pscustomobject]@{
        Launched     = $false
        Reason       = ''
        Pid          = [long]0
        EligibleJobs = 0
        RootExists   = $false
        Scanned      = 0
        Pending      = 0
        Running      = 0
        Terminal     = 0
        Unknown      = 0
        Mode         = 'persistent'
        Open         = [bool]$Open
    }

    $sessionCheck = Test-EimsAutoLaunchInteractiveSession -Session $Session
    if (-not $sessionCheck.Interactive) {
        # Headless fallback: report a plain decision, spawn nothing, wait nowhere.
        $result.Reason = 'headless fallback: ' + $sessionCheck.Reason
        return $result
    }

    $scan = Invoke-EimsAgentJobScan -ArtifactRoot $ArtifactRoot -State @{} -Now $Now -NoTail
    $counts = Get-EimsAutoLaunchScanCounts -Scan $scan
    $result.RootExists = [bool]$scan.RootExists
    $result.Scanned = $counts.Scanned
    $result.Pending = $counts.Pending
    $result.Running = $counts.Running
    $result.Terminal = $counts.Terminal
    $result.Unknown = $counts.Unknown
    if (-not $scan.RootExists -and -not $Open) {
        $result.Reason = 'artifact root unavailable: ' + $ArtifactRoot
        return $result
    }

    if (-not $Open) {
        $eligible = @(Get-EimsAutoLaunchEligibleFromScan -Scan $scan -ArtifactRoot $ArtifactRoot `
                                                          -AllowedAgents $AllowedAgents)
        $result.EligibleJobs = $eligible.Count
        if ($eligible.Count -eq 0) {
            $result.Reason = ('no eligible running job (scanned={0}, pending={1}, running={2}, terminal={3}, unknown={4})' -f `
                $counts.Scanned, $counts.Pending, $counts.Running, $counts.Terminal, $counts.Unknown)
            return $result
        }
    }

    if (Test-EimsAutoLaunchDuplicateWindow -StateDirectory $StateDirectory `
                                            -Processes $Processes -Now $Now) {
        $result.Reason = 'duplicate window suppressed'
        return $result
    }

    if ($DryRun) {
        $result.Launched = $true
        $result.Reason = if ($Open) { 'dry-run: would open persistent dashboard' } else { 'dry-run: would launch visible TUI' }
        return $result
    }

    $nonce = [guid]::NewGuid().ToString('N')
    $stateFile = Get-EimsAutoLaunchStateFilePath -Directory $StateDirectory
    $leasePath = Get-EimsAutoLaunchLeaseFilePath -Directory $StateDirectory
    $claim = [ordered]@{
        pid           = 0
        startedAt     = ''
        nonce         = $nonce
        claimedAt     = $Now.ToUniversalTime().ToString('o')
        artifactRoot  = $ArtifactRoot
        monitorScript = $MonitorScript
        mode          = 'persistent'
        idleClose     = $false
        open          = [bool]$Open
    }
    $claimed = New-EimsAutoLaunchClaim -StateFile $stateFile -Record $claim
    if (-not $claimed) {
        # A record left by a hard window close (dead PID) or a crashed launcher
        # (pid=0 claim past the grace window) must not block every future launch.
        # Reclaim it only when the record is proven stale: the lease is free, the
        # recorded PID is not live, and the nonce is unchanged between validation
        # and deletion. Anything else is a live owner and stays untouched.
        $reclaim = Remove-EimsAutoLaunchStaleState -StateFile $stateFile -Now $Now `
                                                  -ProcessIdentity $ProcessIdentity
        if ([string]::Equals($reclaim, 'reclaimed', [StringComparison]::Ordinal)) {
            $claimed = New-EimsAutoLaunchClaim -StateFile $stateFile -Record $claim
        }
    }
    if (-not $claimed) {
        $result.Reason = 'duplicate window suppressed (state claim)'
        return $result
    }

    try {
        $arguments = New-EimsAutoLaunchHostArgumentList -MonitorScript $MonitorScript `
                                                       -HostScript $HostScript `
                                                       -ArtifactRoot $ArtifactRoot `
                                                       -StateFile $stateFile `
                                                       -LeasePath $leasePath `
                                                       -Nonce $nonce `
                                                       -PollSeconds $PollSeconds `
                                                       -Mode 'Persistent'
        $process = Start-EimsAutoLaunchHost -Arguments $arguments -StartAction $StartAction
        $result.Launched = $true
        $result.Pid = [long]$process.Id
        $result.Reason = if ($Open) { 'opened persistent dashboard' } else { 'launched persistent dashboard' }
    }
    catch {
        # A failed launch must never leave a claim that blocks the next attempt.
        Clear-EimsAutoLaunchState -StateFile $stateFile -Nonce $nonce | Out-Null
        $result.Reason = 'launch failed: ' + $_.Exception.GetType().Name
    }
    return $result
}

function Invoke-EimsAutoLaunchCleanup {
    param(
        [Parameter(Mandatory = $true)][string]$StateDirectory,
        [AllowNull()][object]$Process = $null,
        [AllowNull()][scriptblock]$StopAction = $null,
        # $null means "read the command line from CIM"; '' means the caller knows
        # it is unavailable. Both a failed CIM lookup and an explicitly empty
        # command line are missing ownership evidence, never permission.
        [AllowNull()][object]$CommandLine = $null
    )
    $stateFile = Get-EimsAutoLaunchStateFilePath -Directory $StateDirectory
    $record = Read-EimsAutoLaunchState -StateFile $stateFile
    if ($null -eq $record) {
        Clear-EimsAutoLaunchState -StateFile $stateFile | Out-Null
        return [pscustomobject]@{ Stopped = $false; Reason = 'no owned monitor'; Cleared = $false }
    }
    $trackedPid = 0L
    [void][long]::TryParse([string]$record.pid, [ref]$trackedPid)
    if ($null -eq $Process -and $trackedPid -gt 0) {
        try { $Process = Get-Process -Id $trackedPid -ErrorAction Stop } catch { }
    }

    $commandLine = if ($null -ne $CommandLine) { [string]$CommandLine } else { '' }
    if ($null -eq $CommandLine -and $trackedPid -gt 0) {
        try {
            $cim = Get-CimInstance -ClassName Win32_Process -Filter ('ProcessId={0}' -f $trackedPid) -ErrorAction Stop
            if ($null -ne $cim) { $commandLine = [string]$cim.CommandLine }
        }
        catch { $commandLine = '' }
    }

    # Ownership requires a held lease (a live owned host always holds it),
    # PID + exact start time, a non-empty claim nonce, and the CIM command line.
    # Any missing piece is not-owned, so no signal is sent to a possibly
    # unrelated (agent/runner) PID; only the stale state record is cleared.
    $leaseHeld = Test-EimsAutoLaunchLeaseHeld `
        -LeasePath (Get-EimsAutoLaunchLeaseFilePath -Directory $StateDirectory)
    $stopped = $false
    if ($leaseHeld) {
        $stopped = Stop-EimsAutoLaunchOwnedProcess -Record $record -Process $Process `
                                                   -StopAction $StopAction -CommandLine $commandLine
    }
    $cleared = Clear-EimsAutoLaunchState -StateFile $stateFile -Nonce ([string]$record.nonce)
    $reason = if ($stopped) { 'owned monitor stopped' }
              elseif (-not $leaseHeld) { 'no live owned monitor (lease not held); no signal sent' }
              elseif ($null -ne $Process) { 'no verified owned monitor (incomplete or mismatched evidence); no signal sent' }
              else { 'no live owned monitor' }
    return [pscustomobject]@{
        Stopped = $stopped
        Reason  = $reason
        Cleared = $cleared
    }
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if (-not $NoRun) {
    # Dot-sourcing the watcher shares this scope and its param() block rebinds
    # names such as ArtifactRoot, PollSeconds and Watch. Snapshot our parameters
    # into distinct names before loading it.
    $launchArtifactRoot = $ArtifactRoot
    $launchMonitorScript = $MonitorScript
    $launchHostScript = $HostScript
    $launchStateDirectory = $StateDirectory
    $launchAllowedAgents = $AllowedAgents
    $launchPollSeconds = $PollSeconds
    $launchWatch = [bool]$Watch
    $launchOnce = [bool]$Once
    $launchOpen = [bool]$Open
    $launchDryRun = [bool]$DryRun
    $launchDiagnose = [bool]$Diagnose
    $launchCleanup = [bool]$Cleanup
    $launchNoProcessScan = [bool]$NoProcessScan
    $launchProcesses = $null
    if ($launchNoProcessScan) { $launchProcesses = [object[]]@() }

    if ($launchWatch -and $launchOnce) {
        throw 'Specify either -Watch or -Once, not both.'
    }
    if ($launchOpen -and ($launchWatch -or $launchOnce)) {
        throw 'Specify either -Open or -Watch/-Once, not both.'
    }
    if ($launchOpen -and ($launchDiagnose -or $launchCleanup)) {
        throw '-Open cannot be combined with -Diagnose or -Cleanup.'
    }
    if (-not $launchWatch -and -not $launchOnce -and -not $launchCleanup -and -not $launchOpen) {
        $launchOnce = $true
    }

    # The scan/eligibility helpers come from the watcher; load its functions only.
    $monitorPath = Resolve-EimsAutoLaunchPath -Path $launchMonitorScript `
                                              -FileName 'Watch-EimsAgentJobs.ps1'
    . $monitorPath -NoRun

    $resolvedStateDir = Resolve-EimsAutoLaunchStateDirectory -Directory $launchStateDirectory
    if (-not (Test-Path -LiteralPath $resolvedStateDir -PathType Container)) {
        New-Item -ItemType Directory -Path $resolvedStateDir -Force | Out-Null
    }
    $resolvedRoot = Resolve-EimsAutoLaunchArtifactRoot -Root $launchArtifactRoot
    $hostPath = Resolve-EimsAutoLaunchPath -Path $launchHostScript `
                                           -FileName 'EimsMonitorHost.ps1'

    if ($launchDiagnose) {
        $diag = Get-EimsAutoLaunchDiagnosis -ArtifactRoot $resolvedRoot `
                                           -StateDirectory $resolvedStateDir `
                                           -AllowedAgents $launchAllowedAgents `
                                           -Processes $launchProcesses `
                                           -Now ([datetime]::UtcNow)
        Write-Output 'EIMS monitor auto-launch diagnosis:'
        Write-Output ('  artifactRoot : {0}' -f $diag.ArtifactRoot)
        Write-Output ('  rootExists   : {0}' -f $diag.RootExists)
        Write-Output ('  scanned      : {0}' -f $diag.Scanned)
        Write-Output ('  pending      : {0}' -f $diag.Pending)
        Write-Output ('  running      : {0}' -f $diag.Running)
        Write-Output ('  completed    : {0}' -f $diag.Completed)
        Write-Output ('  failed       : {0}' -f $diag.Failed)
        Write-Output ('  cancelled    : {0}' -f $diag.Cancelled)
        Write-Output ('  unknown      : {0}' -f $diag.Unknown)
        Write-Output ('  terminal     : {0}' -f $diag.Terminal)
        Write-Output ('  eligible     : {0}' -f $diag.EligibleJobs)
        Write-Output ('  eligibleIds  : {0}' -f $(if ($diag.EligibleJobIds.Count -gt 0) { $diag.EligibleJobIds -join ', ' } else { '(none)' }))
        Write-Output ('  allowedAgents: {0}' -f $(if ($diag.AllowedAgents.Count -gt 0) { $diag.AllowedAgents -join ', ' } else { '(all)' }))
        Write-Output ('  interactive  : {0}' -f $diag.Interactive)
        Write-Output ('  sessionReason: {0}' -f $diag.SessionReason)
        Write-Output ('  duplicate    : {0}' -f $diag.Duplicate)
        Write-Output ('  mode         : persistent (no idle auto-close)')
        Write-Output ('  decision     : {0}' -f $diag.Decision)
        foreach ($warning in @($diag.Warnings)) {
            Write-Output ('  warning      : {0}' -f $warning)
        }
        return
    }

    if ($launchCleanup) {
        $cleanup = Invoke-EimsAutoLaunchCleanup -StateDirectory $resolvedStateDir
        Write-Output ('EIMS monitor cleanup: {0}' -f $cleanup.Reason)
        return
    }

    if ($launchOpen) {
        # Explicit persistent dashboard open: zero jobs is a valid state.
        $opened = Invoke-EimsAutoLaunch -ArtifactRoot $resolvedRoot `
                                        -MonitorScript $monitorPath `
                                        -HostScript $hostPath `
                                        -StateDirectory $resolvedStateDir `
                                        -PollSeconds $launchPollSeconds `
                                        -AllowedAgents $launchAllowedAgents `
                                        -Processes $launchProcesses `
                                        -Open `
                                        -DryRun:$launchDryRun
        Write-Output ('EIMS monitor open: {0}' -f $opened.Reason)
        return
    }

    do {
        $decision = Invoke-EimsAutoLaunch -ArtifactRoot $resolvedRoot `
                                          -MonitorScript $monitorPath `
                                          -HostScript $hostPath `
                                          -StateDirectory $resolvedStateDir `
                                          -PollSeconds $launchPollSeconds `
                                          -AllowedAgents $launchAllowedAgents `
                                          -Processes $launchProcesses `
                                          -DryRun:$launchDryRun
        Write-Output ('EIMS monitor auto-launch: {0}' -f $decision.Reason)
        if (-not $launchWatch) { break }
        if ($decision.Reason -like 'headless fallback:*') { break }
        Start-Sleep -Seconds $launchPollSeconds
    } while ($true)
}

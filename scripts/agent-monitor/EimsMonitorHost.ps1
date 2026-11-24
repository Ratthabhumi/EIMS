<#
.SYNOPSIS
    Visible-console host for the EIMS Agent Monitor TUI (Trigger C).

.DESCRIPTION
    Started by Launch-EimsAgentMonitor.ps1 with Start-Process -WindowStyle Normal.
    The host:
      1. takes an exclusive monitor.lease (FileShare.None) so only one owned
         window exists for the state directory;
      2. writes a nonce-bound identity record (pid + start time + mode) so the
         launcher can prove ownership before it ever stops this process;
      3. runs the existing Watch-EimsAgentJobs.ps1 -Dashboard TUI in PERSISTENT
         mode: the window stays open with zero jobs and exits only on Q, Esc from
         the Overview, Ctrl+C, or closing the console window;
      4. on every managed exit path (Q, Esc, Ctrl+C, exception) removes only its
         own state record and releases the lease. A hard window close cannot run
         a finally block; the OS still releases the lease, and the launcher then
         reclaims the remaining record as stale only after proving its PID is not
         live and re-validating its nonce (see Launch-EimsAgentMonitor.ps1).

    The host never launches, signals, cancels, or stops an agent job. It has no
    job-control code path at all, so closing this window cannot affect a runner.

    No focus stealing: the window is simply created with WindowStyle Normal; this
    script never activates or foregrounds a window. No modules are required and
    Windows PowerShell 5.1 syntax is used throughout.

.PARAMETER MonitorScript
    Path to Watch-EimsAgentJobs.ps1.

.PARAMETER StateFile
    Nonce-bound identity record written for the owning launcher.

.PARAMETER LeasePath
    Exclusive lease file proving a live owner.

.PARAMETER PollSeconds
    Dashboard refresh interval, passed to the TUI (1..3600).

.PARAMETER ArtifactRoot
    Artifact root passed to the TUI. Empty means use the TUI default.

.PARAMETER Nonce
    Claim nonce issued by the launcher. Used to prove this host owns the state
    record before removing it.

.PARAMETER Mode
    Persistent (default) or Snapshot. Persistent is the user-facing dashboard
    lifecycle; Snapshot renders one frame and exits (used only by tests/tools).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$MonitorScript,
    [Parameter(Mandatory = $true)][string]$StateFile,
    [Parameter(Mandatory = $true)][string]$LeasePath,
    [ValidateRange(1, 3600)]
    [int]$PollSeconds = 2,
    [string]$ArtifactRoot = '',
    [string]$Nonce = '',
    [ValidateSet('Persistent', 'Snapshot')]
    [string]$Mode = 'Persistent'
)

$ErrorActionPreference = 'Stop'

$lease = $null
try {
    $parent = Split-Path -Parent $StateFile
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $leaseParent = Split-Path -Parent $LeasePath
    if ($leaseParent -and -not (Test-Path -LiteralPath $leaseParent -PathType Container)) {
        New-Item -ItemType Directory -Path $leaseParent -Force | Out-Null
    }

    $acquired = $false
    for ($i = 0; $i -lt 10 -and -not $acquired; $i++) {
        try {
            $lease = [System.IO.File]::Open(
                $LeasePath, [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            $acquired = $true
        }
        catch { Start-Sleep -Milliseconds 100 }
    }
    if (-not $acquired) {
        # Another owned window is already open. Do not touch its state or lease.
        Write-Host 'EIMS Agent Monitor: another owned monitor window is already open (lease held).' -ForegroundColor Yellow
        return
    }

    $self = Get-Process -Id $PID
    $record = [ordered]@{
        pid           = $PID
        startedAt     = $self.StartTime.ToUniversalTime().ToString('o')
        nonce         = $Nonce
        claimedAt     = (Get-Date).ToUniversalTime().ToString('o')
        leaseFile     = $LeasePath
        monitorScript = $MonitorScript
        artifactRoot  = $ArtifactRoot
        mode          = $Mode.ToLowerInvariant()
        idleClose     = $false
        owner         = 'EimsMonitorHost'
    }
    [System.IO.File]::WriteAllText(
        $StateFile, ($record | ConvertTo-Json -Depth 6 -Compress),
        (New-Object System.Text.UTF8Encoding($false)))

    # -Dashboard is the existing TUI. Persistent mode is explicit here: the TUI
    # stays open with zero jobs and is closed only by the user.
    $invoke = @{ PollSeconds = $PollSeconds }
    if (-not [string]::IsNullOrWhiteSpace($ArtifactRoot)) {
        $invoke.ArtifactRoot = $ArtifactRoot
    }
    if ($Mode -eq 'Snapshot') { $invoke.Snapshot = $true }
    else { $invoke.Persistent = $true }
    & $MonitorScript @invoke -Dashboard
}
finally {
    # Terminal restoration is owned by the TUI's own finally block. This host
    # only cleans its own resources, and never hides an exception from the TUI.
    try {
        if (Test-Path -LiteralPath $StateFile -PathType Leaf) {
            $text = [System.IO.File]::ReadAllText($StateFile)
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                $existing = $text | ConvertFrom-Json -ErrorAction SilentlyContinue
                if ($null -ne $existing) {
                    $recordedNonce = [string]$existing.nonce
                    $recordedPid = 0
                    [void][int]::TryParse([string]$existing.pid, [ref]$recordedPid)
                    # Ownership proof: same pid, and the same nonce when this host
                    # was given one. A manual host start (empty nonce) can never
                    # delete another owner's record.
                    $ownsRecord = ($recordedPid -eq $PID) -and
                                  ([string]::IsNullOrEmpty($Nonce) -or
                                   [string]::Equals($recordedNonce, $Nonce, [StringComparison]::Ordinal))
                    if ($ownsRecord) {
                        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
                    }
                }
            }
        }
    }
    catch { }
    if ($null -ne $lease) {
        try { $lease.Dispose() } catch { }
    }
}

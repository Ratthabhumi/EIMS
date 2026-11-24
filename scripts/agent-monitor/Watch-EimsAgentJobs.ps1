<#
.SYNOPSIS
    Local, read-only observer for Chat_HAND Control Plane EIMS agent job artifacts.

.DESCRIPTION
    Polls the per-job artifact directory written by the Chat_HAND gateway and
    displays lifecycle, exit code, elapsed time, last activity, stdout/stderr
    byte counts, and incrementally tailed log output.

    This is a LOCAL OBSERVER ONLY. It:
      - does not launch, stop, cancel, or otherwise control agent processes;
      - does not modify, delete, or acknowledge any job artifact;
      - does not access the EIMS operational database, Redis, MinIO, credentials,
        secrets, or network listeners;
      - cannot inject a message into a ChatGPT conversation.

    Windows PowerShell 5.1 compatible. No modules or external dependencies.

.PARAMETER ArtifactRoot
    Override the artifact root. Default:
    %LOCALAPPDATA%\ChatHandControlPlane\artifacts\eims

.PARAMETER JobId
    Restrict the scan to one job folder name. Only job-id-safe characters are
    accepted ([A-Za-z0-9._-]) to prevent path traversal.

.PARAMETER PollSeconds
    Polling interval, 1..3600 seconds. Default 5.

.PARAMETER Watch
    Continuous monitoring loop; auto-discovers new job folders.

.PARAMETER Once
    Perform exactly one scan and exit. This is the default when neither
    -Watch nor -Once is supplied.

.PARAMETER NoBell
    Suppress the console bell on terminal job transitions.

.PARAMETER NoColor
    Plain output (no ANSI/console color).

.PARAMETER Toast
    Opt-in best-effort Windows toast on terminal transitions. Unsupported or
    misconfigured toast runtimes are silently ignored; the console bell and
    terminal banner are the guaranteed fallback. No module is installed.

.PARAMETER Dashboard
    Interactive dashboard TUI. This is the user-facing persistent mode: the
    window stays open when there are zero jobs and exits only on explicit Q,
    Esc from the Overview, Ctrl+C, or closing the console window. Closing the
    dashboard never stops, cancels, or signals an agent job process.

.PARAMETER Persistent
    Explicit persistent dashboard mode (the default for an interactive
    -Dashboard). There is no idle auto-close and no "exit when no jobs" timer:
    zero jobs is a rendered state, not an exit condition.

.PARAMETER Snapshot
    Render exactly one dashboard frame and exit 0. This is the deterministic,
    non-blocking mode for automation. It is also selected automatically when
    stdin is redirected so a headless/CI caller can never hang on a key prompt.

.PARAMETER MaxFrames
    Test/automation hook: render at most N frames and return. 0 (default) means
    unlimited frames for a persistent session.

.PARAMETER NoRun
    Internal test hook. When present, the script only defines its functions
    and does not start the monitor. Used by the self-contained test script.
#>
[CmdletBinding()]
param(
    [string]$ArtifactRoot,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$JobId,

    [ValidateRange(1, 3600)]
    [int]$PollSeconds = 5,

    [switch]$Watch,
    [switch]$Once,
    [switch]$Dashboard,
    [switch]$NoBell,
    [switch]$NoColor,
    [switch]$Toast,
    [switch]$Ascii,
    [switch]$Plain,
    [switch]$Persistent,
    [switch]$Snapshot,
    [ValidateRange(0, 1000000)]
    [int]$MaxFrames = 0,
    [switch]$NoRun
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Safe JSON reading (locked / partial / malformed files never throw outward).
# ---------------------------------------------------------------------------
function Read-EimsJsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject]@{ Exists = $false; Data = $null; Note = '' }
    }

    # Check the size before opening. A real manifest can be a multi-megabyte file
    # inventory; opening it only to reject it is slow and unnecessary.
    try {
        $fileInfo = [System.IO.FileInfo]::new($Path)
        if ($fileInfo.Length -gt 524288L) {
            return [pscustomobject]@{ Exists = $true; Data = $null; Note = 'file exceeds 512 KiB safety bound' }
        }
    }
    catch { /* fall through to the normal open/read error path */ }

    $note = ''
    $text = $null
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
        try {
            $length = [long]$stream.Length
            if ($length -le 0) {
                return [pscustomobject]@{ Exists = $true; Data = $null; Note = 'empty file' }
            }
            if ($length -gt 524288L) {
                return [pscustomobject]@{ Exists = $true; Data = $null; Note = 'file exceeds 512 KiB safety bound' }
            }
            $buffer = New-Object byte[] ([int]$length)
            $total = 0
            while ($total -lt [int]$length) {
                $read = $stream.Read($buffer, $total, ([int]$length - $total))
                if ($read -le 0) { break }
                $total += $read
            }
            if ($total -le 0) {
                return [pscustomobject]@{ Exists = $true; Data = $null; Note = 'no bytes readable' }
            }
            $text = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $total)
        }
        finally {
            $stream.Dispose()
        }
    }
    catch {
        return [pscustomobject]@{ Exists = $true; Data = $null; Note = 'unreadable (locked or permission denied)' }
    }

    if ($null -ne $text -and $text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
        $text = $text.Substring(1)
    }
    if ([string]::IsNullOrWhiteSpace($text)) {
        return [pscustomobject]@{ Exists = $true; Data = $null; Note = 'blank file' }
    }

    try {
        $parsed = $text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        # A partially written or malformed JSON file is NOT a completion signal.
        return [pscustomobject]@{ Exists = $true; Data = $null; Note = 'malformed JSON (ignored for completion)' }
    }
    return [pscustomobject]@{ Exists = $true; Data = $parsed; Note = $note }
}

# ---------------------------------------------------------------------------
# Defensive property lookup. Only allowlisted keys are ever read by callers;
# raw JSON (which may contain prompts, command lines, env, or tokens) is never
# printed or returned in a status object.
# ---------------------------------------------------------------------------
function Get-EimsPropertyValue {
    param(
        [object]$Object,
        [Parameter(Mandatory = $true)][string[]]$Names,
        [int]$Depth = 0
    )

    if ($null -eq $Object -or $Depth -gt 2) { return $null }
    if ($Object -is [System.Array]) {
        if ($Object.Count -eq 0) { return $null }
        $Object = $Object[0]
    }
    $properties = $Object.PSObject.Properties
    if ($null -eq $properties) { return $null }

    foreach ($name in $Names) {
        foreach ($property in $properties) {
            if ([string]::Equals($property.Name, $name, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $property.Value
            }
        }
    }
    if ($Depth -lt 2) {
        foreach ($wrapper in @('result', 'exit', 'metadata', 'data')) {
            foreach ($property in $properties) {
                if ([string]::Equals($property.Name, $wrapper, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $value = Get-EimsPropertyValue -Object $property.Value -Names $Names -Depth ($Depth + 1)
                    if ($null -ne $value) { return $value }
                }
            }
        }
    }
    return $null
}

function ConvertTo-EimsExitCode {
    param([object]$Value)
    if ($null -eq $Value -or $Value -is [bool]) { return $null }
    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrEmpty($text)) { return $null }

    $number = [long]0
    if ([long]::TryParse($text, [ref]$number)) { return $number }

    $decimal = 0.0
    if ([double]::TryParse(
            $text,
            [System.Globalization.NumberStyles]::Float,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [ref]$decimal)) {
        if ($decimal -eq [math]::Floor($decimal) -and
            $decimal -ge [double][long]::MinValue -and
            $decimal -le [double][long]::MaxValue) {
            return [long]$decimal
        }
    }
    return $null
}

function ConvertTo-EimsStatusToken {
    param([object]$Value)
    if ($null -eq $Value) { return '' }
    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) { return '' }
    return (($text.Trim() -replace '[\s_\-]+', '').ToLowerInvariant())
}

function ConvertTo-EimsUtcDateTime {
    param([object]$Value)
    if ($null -eq $Value) { return $null }
    if ($Value -is [datetime]) { return $Value.ToUniversalTime() }

    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrEmpty($text)) { return $null }
    $styles = [System.Globalization.DateTimeStyles]::AssumeUniversal -bor
              [System.Globalization.DateTimeStyles]::AdjustToUniversal
    $offsetValue = [datetimeoffset]::MinValue
    if ([datetimeoffset]::TryParse(
            $text,
            [System.Globalization.CultureInfo]::InvariantCulture,
            $styles,
            [ref]$offsetValue)) {
        return $offsetValue.UtcDateTime
    }
    $dateValue = [datetime]::MinValue
    if ([datetime]::TryParse(
            $text,
            [System.Globalization.CultureInfo]::InvariantCulture,
            $styles,
            [ref]$dateValue)) {
        return $dateValue
    }
    return $null
}

function Get-EimsExitDecision {
    param(
        [object]$ExitData,
        [bool]$ExitFileExists,
        [string]$ReadNote = ''
    )

    $decision = [pscustomobject]@{
        Lifecycle   = 'UNKNOWN'
        IsTerminal  = $false
        ExitCode    = $null
        Note        = ''
        StatusToken = ''
    }

    # A folder alone, or a log that stopped growing, is NEVER a completion.
    if (-not $ExitFileExists) {
        $decision.Lifecycle = 'RUNNING'
        return $decision
    }
    if ($null -eq $ExitData) {
        $decision.Note = if ([string]::IsNullOrEmpty($ReadNote)) {
            'exit.json present but empty, unreadable, or malformed'
        }
        else {
            ('exit.json: {0}' -f $ReadNote)
        }
        return $decision
    }

    $code = ConvertTo-EimsExitCode -Value (Get-EimsPropertyValue -Object $ExitData -Names @(
        'exitCode', 'exit_code', 'exit-code', 'code', 'returnCode', 'return_code'))
    $statusToken = ConvertTo-EimsStatusToken -Value (Get-EimsPropertyValue -Object $ExitData -Names @(
        'status', 'state', 'result_status', 'outcome'))
    $decision.StatusToken = $statusToken
    $timedOutFlag = Get-EimsPropertyValue -Object $ExitData -Names @('timedOut', 'timed_out', 'timeout')

    $successTokens = @('completed', 'complete', 'success', 'succeeded', 'ok', 'passed',
                       'pass', 'done', 'finished', 'exit', 'terminatednormally')
    $timeoutTokens = @('timedout', 'timeout')
    $failureTokens = @('failed', 'fail', 'failure', 'error', 'errored', 'cancelled',
                       'canceled', 'aborted', 'terminated',
                       'killed', 'crashed')
    $runningTokens = @('running', 'inprogress', 'pending', 'started', 'active', 'queued', 'waiting')

    # A timeout is terminal but is not a generic failure: the process may have
    # produced useful partial output and the monitor reports it separately.
    if ($timedOutFlag -eq $true -or ([string]$timedOutFlag).Trim().ToLowerInvariant() -eq 'true' -or $statusToken -in $timeoutTokens) {
        $decision.Lifecycle = 'TIMED_OUT'
        $decision.IsTerminal = $true
        if ($null -ne $code) { $decision.ExitCode = $code }
        return $decision
    }

    if ($null -ne $code) {
        if ($code -ne 0 -or $statusToken -in $failureTokens) {
            $decision.Lifecycle = 'FAILED'
            $decision.IsTerminal = $true
            $decision.ExitCode = $code
        }
        else {
            $decision.Lifecycle = 'COMPLETED'
            $decision.IsTerminal = $true
            $decision.ExitCode = $code
        }
        return $decision
    }
    if ($statusToken -in $failureTokens) {
        $decision.Lifecycle = 'FAILED'
        $decision.IsTerminal = $true
        return $decision
    }
    if ($statusToken -in $successTokens) {
        $decision.Lifecycle = 'COMPLETED'
        $decision.IsTerminal = $true
        return $decision
    }
    if ($statusToken -in $runningTokens) {
        $decision.Lifecycle = 'RUNNING'
        return $decision
    }

    $decision.Note = 'exit.json has no recognized exit code or status'
    return $decision
}

function Get-EimsSupplementaryMetadata {
    param($RunnerData, $ManifestData)

    $pidValue = Get-EimsPropertyValue -Object $RunnerData -Names @(
        'agentPid', 'agent_pid', 'runnerPid', 'runner_pid', 'pid', 'processId', 'process_id')
    if ($null -eq $pidValue) {
        $pidValue = Get-EimsPropertyValue -Object $ManifestData -Names @(
            'agentPid', 'agent_pid', 'runnerPid', 'runner_pid', 'pid', 'processId', 'process_id')
    }
    $startValue = Get-EimsPropertyValue -Object $RunnerData -Names @(
        'startedAt', 'startTime', 'started_at', 'start_time', 'createdAt', 'created_at')
    if ($null -eq $startValue) {
        $startValue = Get-EimsPropertyValue -Object $ManifestData -Names @(
            'startedAt', 'startTime', 'started_at', 'start_time', 'createdAt', 'created_at')
    }

    $pidText = '-'
    if ($null -ne $pidValue -and $pidValue -isnot [bool]) {
        $candidate = ([string]$pidValue).Trim()
        if ($candidate -match '^\d{1,10}$') { $pidText = $candidate }
    }
    return [pscustomobject]@{
        Pid         = $pidText
        StartTimeUtc = ConvertTo-EimsUtcDateTime -Value $startValue
    }
}

# ---------------------------------------------------------------------------
# Incremental tail. State is per process run. On first sight a stream is
# anchored at its current length so historical logs are not replayed; only
# subsequently appended bytes are emitted. Truncation or file replacement
# resets the offset. A trailing partial line is held until it is completed
# (or until the job becomes terminal).
# ---------------------------------------------------------------------------
function Get-EimsFileIdentity {
    param([System.IO.FileInfo]$File)
    if ($null -eq $File) { return 'MISSING' }
    try { return ('{0}:{1}' -f $File.CreationTimeUtc.Ticks, $File.Name) }
    catch { return ('UNKNOWN:' + $File.Name) }
}

function Get-EimsFileInfoSafe {
    param([string]$Path)
    try {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            # FileInfo carries Length/LastWriteTimeUtc/CreationTimeUtc/FullName
            # without the PowerShell provider overhead of Get-Item.
            return [System.IO.FileInfo]::new($Path)
        }
    }
    catch { }
    return $null
}

function Read-EimsJobTail {
    param(
        [string]$Path,
        [Parameter(Mandatory = $true)][hashtable]$StreamState,
        [bool]$Terminal = $false
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $file = Get-EimsFileInfoSafe -Path $Path
    $identity = Get-EimsFileIdentity -File $file
    $length = if ($null -ne $file) { [long]$file.Length } else { [long]0 }

    if ($StreamState.Identity -ne $identity) {
        $StreamState.Identity = $identity
        $StreamState.Offset = [long]0
    }
    elseif ($length -lt [long]$StreamState.Offset) {
        # Truncated in place.
        $StreamState.Offset = [long]0
    }

    $offset = [long]$StreamState.Offset
    if ($length -le $offset) { return '' }

    $bytes = $null
    $total = 0
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
        try {
            [void]$stream.Seek($offset, [System.IO.SeekOrigin]::Begin)
            # Bounded per-poll read: a log that grew by hundreds of MB between
            # polls must never allocate the whole delta.
            $toRead = [int][Math]::Min([long]65536, ($length - $offset))
            $bytes = New-Object byte[] $toRead
            while ($total -lt $toRead) {
                $read = $stream.Read($bytes, $total, ($toRead - $total))
                if ($read -le 0) { break }
                $total += $read
            }
        }
        finally {
            $stream.Dispose()
        }
    }
    catch {
        # Locked or replaced mid-read: try again on the next poll.
        return ''
    }
    if ($total -le 0) { return '' }

    $lastNewline = -1
    for ($i = $total - 1; $i -ge 0; $i--) {
        if ($bytes[$i] -eq [byte]10) { $lastNewline = $i; break }
    }
    if ($lastNewline -ge 0) {
        $count = $lastNewline + 1
    }
    elseif ($Terminal) {
        $count = $total
    }
    elseif ($toRead -ge 65536) {
        # A line longer than the read window must not stall the tail forever:
        # flush what was read and advance past it.
        $count = $total
    }
    else {
        # Withhold an incomplete short line; do not advance the offset.
        return ''
    }

    $text = ''
    try { $text = [System.Text.Encoding]::UTF8.GetString($bytes, 0, $count) }
    catch { $text = '' }
    $StreamState.Offset = $offset + [long]$count
    return $text
}

function Format-EimsElapsed {
    param([datetime]$Now, [datetime]$StartUtc)
    $span = $Now - $StartUtc
    if ($span.TotalSeconds -lt 0) { $span = [timespan]::Zero }
    return ('{0:00}:{1:00}:{2:00}' -f [int][math]::Floor($span.TotalHours), $span.Minutes, $span.Seconds)
}

function Get-EimsJobStatus {
    param(
        [Parameter(Mandatory = $true)][System.IO.DirectoryInfo]$JobFolder,
        [Parameter(Mandatory = $true)][datetime]$Now
    )

    $root = $JobFolder.FullName
    $fileNameMap = @{
        Stdout   = 'stdout.log'
        Stderr   = 'stderr.log'
        Exit     = 'exit.json'
        Runner   = 'runner.json'
        Manifest = 'manifest.json'
        RunnerLog = 'runner.log'
        Job      = 'job.json'
    }
    $files = @{}
    foreach ($key in $fileNameMap.Keys) {
        $files[$key] = Get-EimsFileInfoSafe -Path (Join-Path $root $fileNameMap[$key])
    }

    $exitWrap = Read-EimsJsonFile -Path (Join-Path $root 'exit.json')
    $runnerWrap = Read-EimsJsonFile -Path (Join-Path $root 'runner.json')
    $jobWrap = Read-EimsJsonFile -Path (Join-Path $root 'job.json')
    $runnerHasPid = $null -ne (Get-EimsPropertyValue -Object $runnerWrap.Data -Names @(
        'agentPid', 'agent_pid', 'runnerPid', 'runner_pid', 'pid', 'processId', 'process_id'))
    $runnerHasStart = $null -ne (Get-EimsPropertyValue -Object $runnerWrap.Data -Names @(
        'startedAt', 'startTime', 'started_at', 'start_time', 'createdAt', 'created_at'))
    # runner.json is authoritative and small. Read the manifest only when the
    # runner metadata is incomplete; a real manifest can be a multi-megabyte
    # file inventory and is not needed for status in the normal case.
    $manifestWrap = if ($null -ne $runnerWrap.Data -and $runnerHasPid -and $runnerHasStart) {
        [pscustomobject]@{ Exists = $false; Data = $null; Note = '' }
    }
    else {
        Read-EimsJsonFile -Path (Join-Path $root 'manifest.json')
    }
    try {
        $decision = Get-EimsExitDecision -ExitData $exitWrap.Data -ExitFileExists $exitWrap.Exists -ReadNote $exitWrap.Note
    }
    catch {
        # A hand-edited artifact with an out-of-range numeric value must become
        # Unknown with a reason, not disappear from the monitor.
        $decision = [pscustomobject]@{
            Lifecycle = 'UNKNOWN'; IsTerminal = $false; ExitCode = $null
            Note = 'exit.json contains an out-of-range or invalid value'; StatusToken = ''
        }
    }
    $metadata = Get-EimsSupplementaryMetadata -RunnerData $runnerWrap.Data -ManifestData $manifestWrap.Data

    $taskTitle = [string](Get-EimsPropertyValue -Object $jobWrap.Data -Names @('taskTitle', 'task_title', 'title'))
    $taskId = [string](Get-EimsPropertyValue -Object $jobWrap.Data -Names @('taskId', 'task_id'))
    $agentId = [string](Get-EimsPropertyValue -Object $jobWrap.Data -Names @('agentId', 'agent_id', 'agent'))
    $agentDisplay = [string](Get-EimsPropertyValue -Object $jobWrap.Data -Names @('agentDisplayName', 'agent_display_name', 'agentName'))
    $role = [string](Get-EimsPropertyValue -Object $jobWrap.Data -Names @('role'))
    $cwdLabel = [string](Get-EimsPropertyValue -Object $jobWrap.Data -Names @('cwd'))
    if ([string]::IsNullOrWhiteSpace($agentDisplay)) { $agentDisplay = $agentId }
    if ([string]::IsNullOrWhiteSpace($agentDisplay)) {
        $runnerCommand = [string](Get-EimsPropertyValue -Object $runnerWrap.Data -Names @('command', 'executable'))
        if (-not [string]::IsNullOrWhiteSpace($runnerCommand)) {
            try { $agentDisplay = [System.IO.Path]::GetFileNameWithoutExtension($runnerCommand) } catch { $agentDisplay = $runnerCommand }
        }
    }
    if ([string]::IsNullOrWhiteSpace($agentDisplay)) { $agentDisplay = '-' }
    $taskLabel = if (-not [string]::IsNullOrWhiteSpace($taskTitle)) { $taskTitle }
                 elseif (-not [string]::IsNullOrWhiteSpace($taskId)) { $taskId }
                 else { $JobFolder.Name.Substring(0, [Math]::Min(8, $JobFolder.Name.Length)) }

    $startUtc = $metadata.StartTimeUtc
    if ($null -eq $startUtc) { $startUtc = $JobFolder.CreationTimeUtc }

    $latest = $JobFolder.LastWriteTimeUtc
    foreach ($key in $files.Keys) {
        $file = $files[$key]
        if ($null -ne $file -and $file.LastWriteTimeUtc -gt $latest) {
            $latest = $file.LastWriteTimeUtc
        }
    }

    $stdoutBytes = if ($null -ne $files.Stdout) { [long]$files.Stdout.Length } else { [long]0 }
    $stderrBytes = if ($null -ne $files.Stderr) { [long]$files.Stderr.Length } else { [long]0 }

    # Elapsed freezes at the last observed activity once the job is terminal; a
    # stopped process must never keep counting time.
    $endUtc = if ($decision.IsTerminal) { $latest } else { $null }
    $elapsedAnchor = if ($null -ne $endUtc) { $endUtc } else { $Now }

    $state = switch ($decision.Lifecycle) {
        'COMPLETED' { 'Completed' }
        'TIMED_OUT' { 'TimedOut' }
        'FAILED' {
            if ($decision.StatusToken -in @('cancelled', 'canceled', 'aborted', 'killed')) { 'Cancelled' } else { 'Failed' }
        }
        'RUNNING' {
            if ($decision.StatusToken -in @('queued', 'pending', 'waiting', 'started')) { 'Pending' }
            elseif (-not [string]::IsNullOrEmpty([string]$metadata.Pid) -and [string]$metadata.Pid -ne '-') { 'Running' }
            else { 'Unknown' }                                # a bare folder is never "Running"
        }
        default { 'Unknown' }
    }

    $unknownReason = ''
    if ($state -eq 'Unknown') {
        if (-not $exitWrap.Exists) {
            $unknownReason = if ($null -eq $runnerWrap.Data) {
                'no exit.json and no runner.json; a bare artifact folder is never completion'
            } else {
                'no exit.json and no runner pid; a stalled log is never completion'
            }
        }
        elseif (-not [string]::IsNullOrWhiteSpace([string]$decision.Note)) {
            $unknownReason = [string]$decision.Note
        }
        else {
            $unknownReason = 'exit.json is present but has no recognized exit code or status'
        }
    }

    $notes = @($decision.Note, $runnerWrap.Note, $(if ($manifestWrap.Note -eq 'file exceeds 512 KiB safety bound') { '' } else { $manifestWrap.Note })) |
        Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
        Select-Object -Unique

    return [pscustomobject]@{
        JobId        = $JobFolder.Name
        TaskTitle    = if (-not [string]::IsNullOrWhiteSpace($taskTitle)) { $taskTitle } else { $null }
        TaskLabel    = $taskLabel
        TaskId       = if (-not [string]::IsNullOrWhiteSpace($taskId)) { $taskId } else { $null }
        Agent        = $agentDisplay
        AgentId      = if (-not [string]::IsNullOrWhiteSpace($agentId)) { $agentId } else { $null }
        Role         = if (-not [string]::IsNullOrWhiteSpace($role)) { $role } else { $null }
        Cwd          = if (-not [string]::IsNullOrWhiteSpace($cwdLabel)) { $cwdLabel } else { $null }
        UnknownReason = $unknownReason
        ArtifactDir  = $root
        Lifecycle    = $decision.Lifecycle
        State        = $state
        IsTerminal   = $decision.IsTerminal
        ExitCode     = if ($null -ne $decision.ExitCode) { [string]$decision.ExitCode } else { '-' }
        Elapsed      = Format-EimsElapsed -Now $elapsedAnchor -StartUtc $startUtc
        EndUtc       = $endUtc
        LastActivity = $latest.ToLocalTime().ToString('yyyy-MM-dd HH:mm:ss')
        StdoutBytes  = $stdoutBytes
        StderrBytes  = $stderrBytes
        Pid          = $metadata.Pid
        Note         = ($notes -join '; ')
        StdoutPath   = if ($null -ne $files.Stdout) { $files.Stdout.FullName } else { '' }
        StderrPath   = if ($null -ne $files.Stderr) { $files.Stderr.FullName } else { '' }
    }
}

function New-EimsJobState {
    return @{
        TerminalReported = $false
        Streams = @{
            stdout = @{ Initialized = $false; Identity = $null; Offset = [long]0 }
            stderr = @{ Initialized = $false; Identity = $null; Offset = [long]0 }
        }
    }
}

function Invoke-EimsAgentJobScan {
    param(
        [Parameter(Mandatory = $true)][string]$ArtifactRoot,
        [Parameter(Mandatory = $true)][hashtable]$State,
        [string]$JobId,
        [datetime]$Now = (Get-Date).ToUniversalTime(),
        [datetime]$SinceUtc = [datetime]::MinValue,
        [switch]$NoTail
    )

    $result = [pscustomobject]@{
        ScannedAt  = $Now
        RootExists = $false
        Statuses   = @()
        TailLines  = @()
        Terminals  = @()
        Warnings   = @()
    }

    if (-not (Test-Path -LiteralPath $ArtifactRoot -PathType Container)) {
        $result.Warnings += ('Artifact root not present: {0}' -f $ArtifactRoot)
        return $result
    }
    $result.RootExists = $true

    try {
        $directories = @(Get-ChildItem -LiteralPath $ArtifactRoot -Directory -ErrorAction Stop)
    }
    catch {
        $result.Warnings += ('Cannot enumerate artifact root: {0}' -f $_.Exception.GetType().Name)
        return $result
    }
    if (-not [string]::IsNullOrWhiteSpace($JobId)) {
        $directories = @($directories | Where-Object { $_.Name -eq $JobId })
    }
    $directories = @($directories | Sort-Object Name)

    foreach ($directory in $directories) {
        try {
            $status = Get-EimsJobStatus -JobFolder $directory -Now $Now
            $firstSeen = -not $State.ContainsKey($status.JobId)
            if ($firstSeen) {
                $State[$status.JobId] = New-EimsJobState
            }
            $jobState = $State[$status.JobId]

            foreach ($streamName in @('stdout', 'stderr')) {
                $streamState = $jobState.Streams[$streamName]
                if (-not $streamState.Initialized) {
                    $path = if ($streamName -eq 'stdout') { $status.StdoutPath } else { $status.StderrPath }
                    $file = if ([string]::IsNullOrEmpty($path)) { $null } else { Get-EimsFileInfoSafe -Path $path }
                    $streamState.Identity = Get-EimsFileIdentity -File $file
                    $streamState.Offset = if ($null -ne $file) { [long]$file.Length } else { [long]0 }
                    $streamState.Initialized = $true
                }
            }

            $stdoutText = if ($NoTail) { '' } else { Read-EimsJobTail -Path $status.StdoutPath -StreamState $jobState.Streams.stdout -Terminal $status.IsTerminal }
            if (-not [string]::IsNullOrEmpty($stdoutText)) {
                $result.TailLines += ('[{0}][stdout] {1}' -f $status.JobId, $stdoutText)
            }
            $stderrText = if ($NoTail) { '' } else { Read-EimsJobTail -Path $status.StderrPath -StreamState $jobState.Streams.stderr -Terminal $status.IsTerminal }
            if (-not [string]::IsNullOrEmpty($stderrText)) {
                $result.TailLines += ('[{0}][stderr] {1}' -f $status.JobId, $stderrText)
            }

            $result.Statuses += $status
            if (-not [string]::IsNullOrEmpty($status.Note)) {
                $result.Warnings += ('[{0}] {1}' -f $status.JobId, $status.Note)
            }
            if ($status.IsTerminal -and -not $jobState.TerminalReported) {
                $jobState.TerminalReported = $true
                # A completion that predates this observer is history, not a new
                # transition. When no watermark is supplied (one-shot CLI use),
                # keep the original behaviour.
                $isNewTransition = $true
                if ($null -ne $SinceUtc -and $null -ne $status.EndUtc) {
                    $isNewTransition = ($status.EndUtc -ge $SinceUtc)
                }
                if ($isNewTransition) { $result.Terminals += $status }
            }
        }
        catch {
            $result.Warnings += ('[{0}] scan skipped: {1}' -f $directory.Name, $_.Exception.GetType().Name)
        }
    }
    return $result
}

function Format-EimsStatusTable {
    param([object[]]$Statuses)
    if ($null -eq $Statuses -or $Statuses.Count -eq 0) { return '' }
    $rows = @($Statuses | Sort-Object JobId | Select-Object -Property @(
        @{ Name = 'JobId';        Expression = { $_.JobId } },
        @{ Name = 'Lifecycle';    Expression = { $_.Lifecycle } },
        @{ Name = 'ExitCode';     Expression = { $_.ExitCode } },
        @{ Name = 'Elapsed';      Expression = { $_.Elapsed } },
        @{ Name = 'LastActivity'; Expression = { $_.LastActivity } },
        @{ Name = 'StdoutBytes';  Expression = { $_.StdoutBytes } },
        @{ Name = 'StderrBytes';  Expression = { $_.StderrBytes } },
        @{ Name = 'Pid';          Expression = { $_.Pid } }
    ))
    $text = ($rows | Format-Table -AutoSize | Out-String -Width 220).TrimEnd()
    return $text
}

function Write-EimsLine {
    param(
        [AllowEmptyString()][string]$Text,
        [string]$Color,
        [switch]$NoColor
    )
    if ($NoColor) { Write-Output $Text }
    elseif ($Color) { Write-Host $Text -ForegroundColor $Color }
    else { Write-Host $Text }
}

function Invoke-EimsToastBestEffort {
    param([string]$Title, [string]$Message)
    try {
        $null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
        $null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime]
        $template = [Windows.UI.Notifications.ToastTemplateManager]::GetTemplateContent(
            [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName('text')
        $textNodes.Item(0).InnerText = $Title
        $textNodes.Item(1).InnerText = $Message
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier(
            'Microsoft.Windows.PowerShell.Shell32').Show($toast)
    }
    catch {
        # Toast is strictly best-effort. No module is installed and no error is raised.
    }
}

function Write-EimsTerminalNotice {
    param(
        [Parameter(Mandatory = $true)][object]$Status,
        [switch]$NoBell,
        [switch]$NoColor,
        [switch]$Toast
    )

    $color = switch ($Status.Lifecycle) {
        'FAILED'    { 'Red' }
        'TIMED_OUT' { 'Magenta' }
        'CANCELLED' { 'DarkYellow' }
        'COMPLETED' { 'Green' }
        default     { 'Yellow' }
    }
    Write-EimsLine -Text ('=== JOB {0} {1} (exit {2}) ===' -f $Status.JobId, $Status.Lifecycle, $Status.ExitCode) -Color $color -NoColor:$NoColor
    Write-EimsLine -Text ('Final stdout: {0}' -f $(if ($Status.StdoutPath) { $Status.StdoutPath } else { '(none)' })) -Color $color -NoColor:$NoColor
    Write-EimsLine -Text ('Final stderr: {0}' -f $(if ($Status.StderrPath) { $Status.StderrPath } else { '(none)' })) -Color $color -NoColor:$NoColor

    if (-not $NoBell) {
        try { [console]::Beep() }
        catch { Write-EimsLine -Text ([string][char]7) -NoColor:$NoColor }
    }
    if ($Toast) {
        Invoke-EimsToastBestEffort -Title ('EIMS job {0} {1}' -f $Status.JobId, $Status.Lifecycle) `
                                   -Message ('exit {0}' -f $Status.ExitCode)
    }
}

function Resolve-EimsArtifactRoot {
    param([string]$Root)
    if ([string]::IsNullOrWhiteSpace($Root)) {
        $local = $env:LOCALAPPDATA
        if ([string]::IsNullOrWhiteSpace($local)) {
            $local = Join-Path $env:USERPROFILE 'AppData\Local'
        }
        $Root = Join-Path $local 'ChatHandControlPlane\artifacts\eims'
    }
    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Root)
}

function Start-EimsAgentJobMonitor {
    param(
        [string]$ArtifactRootOverride,
        [string]$JobIdFilter,
        [int]$IntervalSeconds,
        [switch]$Continuous,
        [switch]$NoBell,
        [switch]$NoColor,
        [switch]$Toast
    )

    $root = Resolve-EimsArtifactRoot -Root $ArtifactRootOverride
    $state = @{}

    Write-EimsLine -Text ('EIMS Agent Job Monitor | root={0} | mode={1} | poll={2}s' -f `
        $root, $(if ($Continuous) { 'WATCH' } else { 'ONCE' }), $IntervalSeconds) -Color 'Cyan' -NoColor:$NoColor
    Write-EimsLine -Text 'Local read-only observer. Cannot send messages into ChatGPT.' -Color 'DarkGray' -NoColor:$NoColor

    try {
        do {
            $now = [datetime]::UtcNow
            $scan = Invoke-EimsAgentJobScan -ArtifactRoot $root -State $state -JobId $JobIdFilter -Now $now

            foreach ($line in $scan.TailLines) {
                Write-EimsLine -Text (ConvertTo-EimsSafeText -Text $line -MaxChars 400) -Color 'Cyan' -NoColor:$NoColor
            }
            foreach ($warning in $scan.Warnings) {
                Write-EimsLine -Text ('WARN: {0}' -f $warning) -Color 'Yellow' -NoColor:$NoColor
            }
            $table = Format-EimsStatusTable -Statuses $scan.Statuses
            if ($table) { Write-EimsLine -Text $table -NoColor:$NoColor }
            else { Write-EimsLine -Text 'No job folders found (waiting).' -Color 'DarkGray' -NoColor:$NoColor }

            foreach ($terminal in $scan.Terminals) {
                Write-EimsTerminalNotice -Status $terminal -NoBell:$NoBell -NoColor:$NoColor -Toast:$Toast
            }

            if (-not $Continuous) { break }
            Start-Sleep -Seconds $IntervalSeconds
        } while ($true)
    }
    finally {
        Write-EimsLine -Text 'Monitor stopped.' -Color 'DarkGray' -NoColor:$NoColor
    }
}

# ---------------------------------------------------------------------------
# Entry point. -NoRun is used by the self-contained test script to load the
# functions without starting the loop.
# ---------------------------------------------------------------------------
# Interactive dashboard (-Dashboard). Windows PowerShell 5.1, no dependencies.
#
# Rendering is a pure function (Render-EimsDashboard) so it can be tested without
# a terminal. The loop only reads keys and writes frames.
# ---------------------------------------------------------------------------

$script:EimsEsc = [char]27
$script:EimsSymbolUnicode = @{
    Completed = [string][char]0x25CF; Failed = [string][char]0x25CF
    Running   = [string][char]0x25D0; Pending = [string][char]0x25CB
    Cancelled = [string][char]0x00D7; TimedOut = 'T'; Unknown = '?'
}
$script:EimsSymbolAscii = @{
    Completed = '+'; Failed = 'x'; Running = '~'; Pending = '.'; Cancelled = '!'; TimedOut = 'T'; Unknown = '?'
}

function ConvertTo-EimsSafeText {
    param([string]$Text, [int]$MaxChars = 400)
    if ([string]::IsNullOrEmpty($Text)) { return '' }
    $clean = $Text -replace ($script:EimsEsc + '\[[0-9;?]*[A-Za-z]'), ''
    # CR/LF/tab and every other C0/C1 control become spaces: a lone CR would
    # otherwise return the cursor to column 0 and overwrite the frame.
    $clean = $clean -replace '[\x00-\x1F\x7F-\x9F]', ' '
    $clean = $clean -replace '\s{2,}', ' '
    # Best-effort secret masking before anything reaches the screen.
    $clean = $clean -replace '\bsk-[A-Za-z0-9_\-]{8,}', '[REDACTED]'
    $clean = $clean -replace '\bgh[pousr]_[A-Za-z0-9]{8,}', '[REDACTED]'
    $clean = $clean -replace '\bgithub_pat_[A-Za-z0-9_]{8,}', '[REDACTED]'
    $clean = $clean -replace '\bAKIA[0-9A-Z]{12,}', '[REDACTED]'
    $clean = $clean -replace '\bxox[abprs]-[A-Za-z0-9-]{8,}', '[REDACTED]'
    $clean = $clean -replace '\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}', '[REDACTED]'
    $clean = $clean -replace '(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}', 'Bearer [REDACTED]'
    $clean = $clean -replace '(?i)\b(api[_\-]?key|token|secret|password|passwd)\s*[=:]\s*\S+', '$1=[REDACTED]'
    $clean = $clean -replace '-----BEGIN [A-Z ]*PRIVATE KEY-----', '-----BEGIN PRIVATE KEY [REDACTED]-----'
    $clean = $clean.TrimEnd()
    if ($clean.Length -gt $MaxChars) { return $clean.Substring(0, $MaxChars) + '...' }
    return $clean
}

function Get-EimsTerminalCaps {
    param([switch]$Ascii, [switch]$Plain)
    $ansi = $false
    $raw = $false
    if (-not $Plain) {
        try { $ansi = -not [Console]::IsOutputRedirected } catch { $ansi = $false }
        if ($ansi) {
            try {
                $prop = $Host.UI.PSObject.Properties['SupportsVirtualTerminal']
                if ($null -ne $prop) { $ansi = [bool]$prop.Value }
            } catch { }
        }
        try { $raw = -not [Console]::IsInputRedirected } catch { $raw = $false }
    }
    $unicode = $false
    if (-not $Ascii) {
        try { $unicode = ([Console]::OutputEncoding.CodePage -eq 65001) } catch { $unicode = $false }
    }
    return [pscustomobject]@{ Ansi = $ansi; RawKey = $raw; Unicode = $unicode }
}

function Get-EimsStatusSymbol {
    param([string]$State, [bool]$Unicode)
    $map = if ($Unicode) { $script:EimsSymbolUnicode } else { $script:EimsSymbolAscii }
    if ($null -ne $map[$State]) { return $map[$State] }
    return $map.Unknown
}

function Get-EimsStatusColor {
    param([string]$State)
    switch ($State) {
        'Completed' { return 'Green' }
        'Failed'    { return 'Red' }
        'Cancelled' { return 'DarkYellow' }
        'TimedOut'  { return 'Magenta' }
        'Running'   { return 'Yellow' }
        'Pending'   { return 'DarkGray' }
        default     { return 'DarkGray' }
    }
}

function Get-EimsDashboardRows {
    param([object[]]$Statuses, [string]$View)
    $list = @($Statuses)
    switch ($View) {
        'Active'  { return @($list | Where-Object { $_.State -in @('Running', 'Pending', 'Unknown') }) }
        'History' { return @($list | Where-Object { $_.State -in @('Completed', 'Failed', 'Cancelled', 'TimedOut') } |
                              Sort-Object -Property LastActivity -Descending) }
        default   { return @($list | Sort-Object -Property JobId) }
    }
}

function Resolve-EimsDashboardSelection {
    param([object[]]$Statuses, [string]$View, [string]$SelectedJobId)
    $list = @($Statuses)
    if (-not [string]::IsNullOrEmpty($SelectedJobId)) {
        if (@($list | Where-Object { $_.JobId -eq $SelectedJobId }).Count -gt 0) { return $SelectedJobId }
    }
    $rows = @(Get-EimsDashboardRows -Statuses $list -View $View)
    if ($rows.Count -gt 0) { return $rows[0].JobId }
    return $null
}

function Get-EimsStateCounts {
    param([object[]]$Statuses)
    $counts = [ordered]@{ Total = 0; Running = 0; Pending = 0; Completed = 0; Failed = 0; Cancelled = 0; TimedOut = 0; Unknown = 0 }
    foreach ($status in @($Statuses)) {
        $counts.Total++
        if ($null -ne $counts[$status.State]) { $counts[$status.State]++ } else { $counts.Unknown++ }
    }
    return $counts
}

# Idle is a DISPLAY state, never an exit condition. A job is "active" while it
# has not reported a terminal signal; a bare/unknown folder therefore keeps the
# dashboard non-idle, exactly as it keeps the dashboard's rows visible.
function Get-EimsDashboardIdleState {
    param([object[]]$Statuses)
    $list = @($Statuses)
    $active = @($list | Where-Object { $null -ne $_ -and -not $_.IsTerminal })
    return [pscustomobject]@{
        IsIdle        = ($active.Count -eq 0)
        ActiveCount   = $active.Count
        TotalCount    = $list.Count
        TerminalCount = ($list.Count - $active.Count)
    }
}

function Move-EimsDashboardSelection {
    param(
        [object[]]$Statuses,
        [string]$View,
        [string]$SelectedJobId,
        [int]$Delta
    )
    $rows = @(Get-EimsDashboardRows -Statuses $Statuses -View $View)
    if ($rows.Count -eq 0) { return $SelectedJobId }
    $ids = @($rows | ForEach-Object { $_.JobId })
    $index = [array]::IndexOf($ids, $SelectedJobId)
    if ($index -lt 0) { $index = 0 }
    else { $index = [Math]::Max(0, [Math]::Min($rows.Count - 1, $index + $Delta)) }
    return $rows[$index].JobId
}

function Read-EimsLogPreview {
    param(
        [string]$Path,
        [int]$MaxLines = 16,
        [int]$MaxBytes = 16384
    )
    if ([string]::IsNullOrEmpty($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @('[no log file]')
    }
    $info = Get-EimsFileInfoSafe -Path $Path
    if ($null -eq $info) { return @('[log unreadable]') }
    $truncated = $info.Length -gt $MaxBytes
    try {
        $share = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $share)
        try {
            $start = [Math]::Max(0, $info.Length - $MaxBytes)
            [void]$fs.Seek($start, [System.IO.SeekOrigin]::Begin)
            $buffer = New-Object byte[] ([int]($info.Length - $start))
            $read = $fs.Read($buffer, 0, $buffer.Length)
            $text = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
        }
        finally { $fs.Dispose() }
    }
    catch {
        return @('[log locked or unreadable: ' + $_.Exception.GetType().Name + ']')
    }
    $lines = @($text -split "`r?`n")
    $maxBody = if ($truncated) { [Math]::Max(1, $MaxLines - 1) } else { $MaxLines }
    if ($lines.Count -gt $maxBody) { $lines = $lines[($lines.Count - $maxBody)..($lines.Count - 1)] }
    if ($truncated) { $lines = @('... [log truncated: showing last ' + $MaxBytes + ' bytes]') + $lines }
    return @($lines | ForEach-Object { ConvertTo-EimsSafeText -Text $_ -MaxChars 160 })
}

function Get-EimsArtifactList {
    param(
        [string]$Path,
        [int]$MaxEntries = 20
    )
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Container)) {
        return @('[artifact directory unavailable]')
    }
    try {
        # Enumerate lazily and stop after one extra entry so a directory with
        # thousands of files cannot stall the frame render.
        $dirInfo = [System.IO.DirectoryInfo]::new($Path)
        $sample = @($dirInfo.EnumerateFiles() | Select-Object -First ($MaxEntries + 1))
    }
    catch {
        return @('[artifact directory unreadable: ' + $_.Exception.GetType().Name + ']')
    }
    if ($sample.Count -eq 0) { return @('[no artifact files]') }
    $more = $sample.Count -gt $MaxEntries
    $files = @($sample | Select-Object -First $MaxEntries | Sort-Object -Property Name)
    $lines = @($files | ForEach-Object {
        ConvertTo-EimsSafeText -Text ('{0}  {1,10} bytes  {2}' -f $_.Name, $_.Length, $_.LastWriteTime.ToString('HH:mm:ss')) -MaxChars 120
    })
    if ($more) { $lines += ('... more file(s) not listed (showing {0})' -f $MaxEntries) }
    return @($lines)
}

function Render-EimsDashboard {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Statuses,
        [Parameter(Mandatory = $true)][string]$View,
        [string]$SelectedJobId,
        [object[]]$Warnings = @(),
        [bool]$Unicode = $false,
        [string]$Root = '',
        [int]$IntervalSeconds = 5,
        [datetime]$Now = ([datetime]::UtcNow),
        [datetime]$LastScan = ([datetime]::UtcNow),
        [ValidateSet('persistent', 'snapshot')]
        [string]$Mode = 'persistent',
        [int]$RefreshInSeconds = -1
    )

    $lines = New-Object System.Collections.ArrayList
    $symbols = if ($Unicode) { $script:EimsSymbolUnicode } else { $script:EimsSymbolAscii }
    $viewName = switch ($View) {
        'Active' { 'Active' } 'History' { 'History' } 'Logs' { 'Logs' }
        'Result' { 'Result' } 'Errors' { 'Errors' } 'Artifacts' { 'Artifacts' } 'Info' { 'Info' }
        default { 'Overview' }
    }

    [void]$lines.Add('EIMS Agent Monitor   [O]verview [A]ctive [H]istory [L]ogs [F]inal [E]rrors [T]artifacts [I]nfo [R]efresh [Q]uit')
    $rootState = if ([string]::IsNullOrWhiteSpace($Root)) { 'default' } elseif (Test-Path -LiteralPath $Root -PathType Container) { 'OK' } else { 'MISSING' }
    $refreshText = if ($RefreshInSeconds -ge 0) { ('{0}s' -f $RefreshInSeconds) } else { '-' }
    [void]$lines.Add(('mode={0}  view={1}  root={2} ({3})' -f
        $Mode, $viewName, (ConvertTo-EimsSafeText -Text $Root -MaxChars 56), $rootState))
    [void]$lines.Add(('poll={0}s  next refresh={1}  last refresh={2}Z  selected={3}' -f
        $IntervalSeconds, $refreshText, $LastScan.ToString('HH:mm:ss'),
        (ConvertTo-EimsSafeText -Text $SelectedJobId -MaxChars 38)))
    [void]$lines.Add('')

    $counts = Get-EimsStateCounts -Statuses $Statuses
    [void]$lines.Add(('Total {0}  {1} Running {2}  {3} Pending {4}  {5} Completed {6}  {7} Failed {8}  {9} Cancelled {10}  {11} TimedOut {12}  {13} Unknown {14}' -f
        $counts.Total, (Get-EimsStatusSymbol -State 'Running' -Unicode $Unicode), $counts.Running,
        (Get-EimsStatusSymbol -State 'Pending' -Unicode $Unicode), $counts.Pending,
        (Get-EimsStatusSymbol -State 'Completed' -Unicode $Unicode), $counts.Completed,
        (Get-EimsStatusSymbol -State 'Failed' -Unicode $Unicode), $counts.Failed,
        (Get-EimsStatusSymbol -State 'Cancelled' -Unicode $Unicode), $counts.Cancelled,
        (Get-EimsStatusSymbol -State 'TimedOut' -Unicode $Unicode), $counts.TimedOut,
        (Get-EimsStatusSymbol -State 'Unknown' -Unicode $Unicode), $counts.Unknown))

    # Zero-job / idle state is explicit and actionable: it says what the
    # dashboard is waiting for and that the window is persistent.
    $idleInfo = Get-EimsDashboardIdleState -Statuses $Statuses
    $persistenceHint = if ($Mode -eq 'persistent') {
        ' -- persistent: this dashboard does not auto-close, Q / window close to exit'
    }
    else { ' -- snapshot frame' }
    if ($idleInfo.TotalCount -eq 0) {
        if ($rootState -eq 'MISSING') {
            [void]$lines.Add('IDLE   no job artifacts yet (root MISSING) -- waiting for the gateway to write them' + $persistenceHint)
        }
        else {
            [void]$lines.Add('IDLE   no job folders found -- waiting for the first job' + $persistenceHint)
        }
    }
    elseif ($idleInfo.IsIdle) {
        [void]$lines.Add(('IDLE   {0} job(s), all terminal -- nothing running' -f $idleInfo.TotalCount) + $persistenceHint)
    }
    else {
        [void]$lines.Add(('ACTIVE {0} active / {1} total job(s)' -f $idleInfo.ActiveCount, $idleInfo.TotalCount) + $persistenceHint)
    }
    [void]$lines.Add('')

    $rows = @(Get-EimsDashboardRows -Statuses $Statuses -View $viewName)
    if ($rows.Count -eq 0) {
        [void]$lines.Add('  (no jobs in this view)')
    }
    else {
        [void]$lines.Add('  Job          Task                        Agent        State    Exit   Elapsed    Last activity       Out     Err')
        foreach ($job in ($rows | Select-Object -First 12)) {
            $marker = if ($job.JobId -eq $SelectedJobId) { '>' } else { ' ' }
            # MaxChars is the pre-ellipsis budget, so width-3 keeps every column
            # aligned even when a value is truncated (the full job id is shown on
            # the selected line and in the Info view).
            $jobLabel = ConvertTo-EimsSafeText -Text ([string]$job.JobId) -MaxChars 9
            $task = ConvertTo-EimsSafeText -Text $(if ([string]::IsNullOrWhiteSpace([string]$job.TaskLabel)) { [string]$job.JobId } else { [string]$job.TaskLabel }) -MaxChars 24
            $agent = ConvertTo-EimsSafeText -Text $(if ([string]::IsNullOrWhiteSpace([string]$job.Agent)) { '-' } else { [string]$job.Agent }) -MaxChars 9
            [void]$lines.Add(('{0} {1,-12} {2,-27} {3,-12} {4,-8} {5,-6} {6,-10} {7,-19} {8,7} {9,7}' -f
                $marker, $jobLabel, $task, $agent, $job.State, $job.ExitCode, $job.Elapsed,
                $job.LastActivity, $job.StdoutBytes, $job.StderrBytes))
        }
        if ($rows.Count -gt 12) { [void]$lines.Add(('  ... {0} more (narrow the window or pick a view)' -f ($rows.Count - 12))) }
    }

    [void]$lines.Add('')
    $selected = if ([string]::IsNullOrEmpty($SelectedJobId)) { $null } else { @($Statuses | Where-Object { $_.JobId -eq $SelectedJobId }) | Select-Object -First 1 }
    if ($null -eq $selected) {
        [void]$lines.Add('Selected: (none)   -- select with J/K, then L=logs F=result E=errors T=artifacts I=info')
    }
    else {
        [void]$lines.Add(('Selected {0}   agent={1}   role={2}   state={3}   exit={4}' -f
            (ConvertTo-EimsSafeText -Text ([string]$selected.TaskLabel) -MaxChars 34),
            (ConvertTo-EimsSafeText -Text ([string]$selected.Agent) -MaxChars 16),
            (ConvertTo-EimsSafeText -Text ([string]$selected.Role) -MaxChars 10),
            $selected.State, $selected.ExitCode))
        [void]$lines.Add(('  job={0}   elapsed={1}   last={2}   pid={3}' -f
            $selected.JobId, $selected.Elapsed, $selected.LastActivity, $selected.Pid))
        if (-not [string]::IsNullOrEmpty($selected.UnknownReason)) {
            [void]$lines.Add('  why unknown: ' + (ConvertTo-EimsSafeText -Text $selected.UnknownReason -MaxChars 140))
        }
        if (-not [string]::IsNullOrEmpty($selected.Note)) {
            [void]$lines.Add('  note: ' + (ConvertTo-EimsSafeText -Text $selected.Note -MaxChars 120))
        }

        if ($viewName -eq 'Logs') {
            [void]$lines.Add('  --- log tail (sanitized, bounded) ---')
            $logPath = if ($selected.StderrBytes -gt 0 -and $selected.StdoutBytes -eq 0) { $selected.StderrPath } else { $selected.StdoutPath }
            foreach ($line in (Read-EimsLogPreview -Path $logPath)) {
                [void]$lines.Add('  | ' + $line)
            }
        }
        elseif ($viewName -eq 'Result') {
            [void]$lines.Add('  --- final result: stdout tail (sanitized, bounded) ---')
            foreach ($line in (Read-EimsLogPreview -Path $selected.StdoutPath -MaxLines 18)) {
                [void]$lines.Add('  | ' + $line)
            }
            [void]$lines.Add(('  stdout={0} bytes  stderr={1} bytes  [L] full log  [E] errors  [T] artifacts' -f
                $selected.StdoutBytes, $selected.StderrBytes))
        }
        elseif ($viewName -eq 'Errors') {
            [void]$lines.Add('  --- errors: stderr tail (sanitized, bounded) ---')
            if ($selected.StderrBytes -le 0) {
                [void]$lines.Add('  | [no stderr output recorded]')
            }
            else {
                foreach ($line in (Read-EimsLogPreview -Path $selected.StderrPath -MaxLines 18)) {
                    [void]$lines.Add('  | ' + $line)
                }
            }
        }
        elseif ($viewName -eq 'Artifacts') {
            [void]$lines.Add('  --- artifacts (bounded listing; read-only) ---')
            foreach ($line in (Get-EimsArtifactList -Path $selected.ArtifactDir)) {
                [void]$lines.Add('  | ' + $line)
            }
        }
        elseif ($viewName -eq 'Info') {
            [void]$lines.Add('  --- lifecycle / metadata ---')
            [void]$lines.Add(('  cwd: {0}' -f (ConvertTo-EimsSafeText -Text ([string]$selected.Cwd) -MaxChars 100)))
            [void]$lines.Add(('  stdout: {0}' -f (ConvertTo-EimsSafeText -Text $selected.StdoutPath -MaxChars 100)))
            [void]$lines.Add(('  stderr: {0}' -f (ConvertTo-EimsSafeText -Text $selected.StderrPath -MaxChars 100)))
            [void]$lines.Add(('  artifacts: {0}' -f (ConvertTo-EimsSafeText -Text ([string]$selected.ArtifactDir) -MaxChars 100)))
            [void]$lines.Add(('  state={0} lifecycle={1} terminal={2} taskId={3}' -f
                $selected.State, $selected.Lifecycle, $selected.IsTerminal, (ConvertTo-EimsSafeText -Text ([string]$selected.TaskId) -MaxChars 40)))
        }
    }

    if ($null -ne $Warnings -and $Warnings.Count -gt 0) {
        [void]$lines.Add('')
        foreach ($warning in ($Warnings | Select-Object -First 3)) {
            [void]$lines.Add('WARN: ' + (ConvertTo-EimsSafeText -Text $warning -MaxChars 120))
        }
    }

    # Lifecycle contract, visible in the UI: quitting the dashboard never stops
    # an agent job, and idle is never an automatic close.
    [void]$lines.Add('')
    if ($Mode -eq 'persistent') {
        [void]$lines.Add('Exit: Q (or Esc from Overview, Ctrl+C, closing this window). Idle never auto-closes. Agent jobs keep running.')
    }
    else {
        [void]$lines.Add('Snapshot: one frame rendered, then exit. Interactive mode never auto-closes. Agent jobs keep running.')
    }
    return @($lines)
}

function Write-EimsScreen {
    param([string[]]$Lines, [bool]$Ansi)
    $width = 120
    $height = 40
    try {
        if (-not [Console]::IsOutputRedirected) {
            $width = [Console]::WindowWidth
            $height = [Console]::WindowHeight
        }
    }
    catch { }
    if ($width -lt 40) { $width = 40 }
    if ($height -lt 10) { $height = 10 }

    $visible = $Lines
    $hidden = 0
    if ($visible.Count -gt ($height - 1)) {
        $hidden = $visible.Count - ($height - 2)
        $visible = @($visible[0..($height - 3)]) + @(('... {0} more line(s) hidden (resize or switch view)' -f $hidden))
    }

    $builder = New-Object System.Text.StringBuilder
    if ($Ansi) { [void]$builder.Append($script:EimsEsc + '[H') }
    for ($i = 0; $i -lt $visible.Count; $i++) {
        $line = [string]$visible[$i]
        if ($line.Length -gt ($width - 1)) { $line = $line.Substring(0, $width - 2) }
        [void]$builder.Append($line.PadRight($width - 1))
        if ($i -lt $visible.Count - 1) { [void]$builder.Append([Environment]::NewLine) }
    }
    if ($Ansi) { [void]$builder.Append($script:EimsEsc + '[J') }
    [Console]::Write($builder.ToString())
}

# ---------------------------------------------------------------------------
# Dashboard lifecycle
#
# Contract: the interactive dashboard is PERSISTENT. Zero jobs is a rendered
# state, not an exit condition; there is no idle timer and no auto-close. The
# only dashboard exits are explicit Q, Esc from the Overview, Ctrl+C, and
# closing the console window. None of those paths can reach an agent process:
# this script has no job-control code at all (see the source guard in the tests).
#
# A non-interactive caller (stdin redirected) gets a single deterministic frame
# so automation and CI can never block on a key prompt.
# ---------------------------------------------------------------------------
function Resolve-EimsDashboardRuntimeMode {
    param(
        [switch]$Persistent,
        [switch]$Snapshot,
        [AllowNull()][object]$InputRedirected = $null
    )

    $redirected = $null
    if ($null -ne $InputRedirected) { $redirected = [bool]$InputRedirected }
    else { try { $redirected = [Console]::IsInputRedirected } catch { $redirected = $true } }

    if ($Snapshot) {
        return [pscustomobject]@{
            Mode            = 'snapshot'
            Persistent      = $false
            Requested       = 'snapshot'
            InputRedirected = [bool]$redirected
            Reason          = 'explicit snapshot: one frame, then exit'
        }
    }

    if (-not $redirected) {
        return [pscustomobject]@{
            Mode            = 'persistent'
            Persistent      = $true
            Requested       = 'persistent'
            InputRedirected = $false
            Reason          = ''
        }
    }

    return [pscustomobject]@{
        Mode            = 'snapshot'
        Persistent      = $false
        Requested       = 'persistent'
        InputRedirected = $true
        Reason          = if ($Persistent) {
            'persistent requested but stdin is redirected; rendering one frame instead of blocking'
        }
        else {
            'stdin is redirected; rendering one frame instead of blocking'
        }
    }
}

function Read-EimsDashboardKey {
    param(
        [int]$WaitMilliseconds = 250,
        [bool]$RawKey = $true
    )

    if (-not $RawKey) {
        # Write-EimsScreen leaves the cursor at the end of the last frame line;
        # start the prompt on a fresh line (as the previous line-prompt mode did).
        try { [Console]::Write([Environment]::NewLine) } catch { }
        $answer = ''
        try {
            $answer = Read-Host 'O=overview A=active H=history L=logs F=final E=errors T=artifacts I=info R=refresh Q=quit'
        }
        catch { return 'Q' }
        # A closed/redirected stdin must never produce an endless "refresh" spin.
        if ($null -eq $answer) { return 'Q' }
        $text = ([string]$answer).Trim()
        if ($text.Length -eq 0) { return 'R' }
        return $text.Substring(0, 1).ToUpperInvariant()
    }

    $deadline = [datetime]::UtcNow.AddMilliseconds([Math]::Max(50, $WaitMilliseconds))
    while ([datetime]::UtcNow -lt $deadline) {
        try {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
                return [string]$key.Key
            }
        }
        catch {
            # No readable console: exit instead of hot-looping. Mode resolution
            # already routes redirected stdin to snapshot mode.
            return 'Q'
        }
        Start-Sleep -Milliseconds 50
    }
    return ''
}

function Invoke-EimsDashboardSession {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [string]$JobIdFilter,
        [int]$IntervalSeconds = 5,
        [ValidateSet('persistent', 'snapshot')]
        [string]$Mode = 'persistent',
        [AllowNull()][scriptblock]$KeyProvider = $null,
        [AllowNull()][scriptblock]$FrameWriter = $null,
        [AllowNull()][scriptblock]$Clock = $null,
        [int]$MaxFrames = 0,
        [switch]$RawKey,
        [switch]$NoBell,
        [switch]$Toast,
        [switch]$Unicode,
        [switch]$Ansi
    )

    $getNow = if ($null -ne $Clock) { $Clock } else { { [datetime]::UtcNow } }
    $writeFrame = if ($null -ne $FrameWriter) {
        $FrameWriter
    }
    else {
        { param($lines, $useAnsi) Write-EimsScreen -Lines $lines -Ansi $useAnsi }
    }

    $state = @{}
    $view = 'Overview'
    $selected = $null
    $lastScan = $null
    $lastScanAt = $null
    $nextScan = & $getNow
    $warnings = @()
    $statuses = @()
    $monitorStarted = & $getNow
    $frames = 0
    $idle = $true
    $exitReason = 'max-frames'
    $forceRefresh = $true

    try {
        if ($Ansi -and $Mode -eq 'persistent') {
            [Console]::Write($script:EimsEsc + '[?1049h' + $script:EimsEsc + '[?25l')
        }

        while ($true) {
            $now = & $getNow
            if ($forceRefresh -or $null -eq $lastScan -or $now -ge $nextScan) {
                try {
                    $scan = Invoke-EimsAgentJobScan -ArtifactRoot $Root -State $state `
                                                     -JobId $JobIdFilter -Now $now -SinceUtc $monitorStarted -NoTail
                    $lastScan = $now
                    $lastScanAt = $now
                    $nextScan = $now.AddSeconds($IntervalSeconds)
                    $warnings = @($scan.Warnings)
                    $statuses = @($scan.Statuses)
                    foreach ($terminal in $scan.Terminals) {
                        if (-not $NoBell) { try { [console]::Beep() } catch { } }
                        if ($Toast) {
                            Invoke-EimsToastBestEffort -Title ('EIMS job {0} {1}' -f $terminal.JobId, $terminal.State) `
                                                       -Message ('exit {0}' -f $terminal.ExitCode)
                        }
                    }
                }
                catch {
                    # A failed scan is a warning frame, never a dashboard exit.
                    $warnings = @('scan failed: ' + $_.Exception.GetType().Name)
                    $lastScan = $now
                    $lastScanAt = $now
                    $nextScan = $now.AddSeconds($IntervalSeconds)
                }
                $forceRefresh = $false
            }

            $idleInfo = Get-EimsDashboardIdleState -Statuses $statuses
            $idle = $idleInfo.IsIdle
            $selected = Resolve-EimsDashboardSelection -Statuses $statuses -View $view -SelectedJobId $selected

            $remaining = ($nextScan - (& $getNow)).TotalSeconds
            $refreshIn = if ($remaining -gt 0) { [int][Math]::Ceiling($remaining) } else { 0 }

            $frame = Render-EimsDashboard -Statuses $statuses -View $view -SelectedJobId $selected `
                -Warnings $warnings -Unicode:$Unicode -Root $Root -IntervalSeconds $IntervalSeconds `
                -Now $now -LastScan $(if ($null -eq $lastScanAt) { $now } else { $lastScanAt }) `
                -Mode $Mode -RefreshInSeconds $refreshIn
            & $writeFrame $frame $Ansi.IsPresent
            $frames++

            if ($Mode -eq 'snapshot') { $exitReason = 'snapshot'; break }
            if ($MaxFrames -gt 0 -and $frames -ge $MaxFrames) { $exitReason = 'max-frames'; break }

            $waitMs = [int][Math]::Max(50, [Math]::Min(500, $remaining * 1000))
            $keyChar = if ($null -ne $KeyProvider) {
                [string](& $KeyProvider $waitMs)
            }
            else {
                Read-EimsDashboardKey -WaitMilliseconds $waitMs -RawKey:$RawKey
            }

            $quit = $false
            switch ($keyChar) {
                'O' { $view = 'Overview' }
                'A' { $view = 'Active' }
                'H' { $view = 'History' }
                'L' { if ($null -ne $selected) { $view = 'Logs' } }
                'F' { if ($null -ne $selected) { $view = 'Result' } }
                'E' { if ($null -ne $selected) { $view = 'Errors' } }
                'T' { if ($null -ne $selected) { $view = 'Artifacts' } }
                'I' { if ($null -ne $selected) { $view = 'Info' } }
                'R' { $forceRefresh = $true }
                'Q' { $quit = $true }
                'Escape' { if ($view -ne 'Overview') { $view = 'Overview' } else { $quit = $true } }
                'UpArrow' { $selected = Move-EimsDashboardSelection -Statuses $statuses -View $view -SelectedJobId $selected -Delta -1 }
                'DownArrow' { $selected = Move-EimsDashboardSelection -Statuses $statuses -View $view -SelectedJobId $selected -Delta 1 }
                'J' { $selected = Move-EimsDashboardSelection -Statuses $statuses -View $view -SelectedJobId $selected -Delta 1 }
                'K' { $selected = Move-EimsDashboardSelection -Statuses $statuses -View $view -SelectedJobId $selected -Delta -1 }
            }
            if ($quit) { $exitReason = 'quit'; break }
        }
    }
    finally {
        # Terminal restoration must never hide the original failure, and it must
        # never touch anything outside this console.
        try {
            if ($Ansi -and $Mode -eq 'persistent') {
                [Console]::Write($script:EimsEsc + '[?25h' + $script:EimsEsc + '[0m' + $script:EimsEsc + '[?1049l')
            }
        }
        catch { }
    }

    return [pscustomobject]@{
        Mode           = $Mode
        Frames         = $frames
        ExitReason     = $exitReason
        Idle           = $idle
        View           = $view
        SelectedJobId  = $selected
        Statuses       = @($statuses)
        LastScan       = $lastScanAt
        MonitorStarted = $monitorStarted
    }
}

function Start-EimsDashboard {
    param(
        [string]$ArtifactRootOverride,
        [string]$JobIdFilter,
        [int]$IntervalSeconds = 5,
        [switch]$NoBell,
        [switch]$NoColor,
        [switch]$Toast,
        [switch]$Ascii,
        [switch]$Plain,
        [switch]$Persistent,
        [switch]$Snapshot,
        [int]$MaxFrames = 0
    )

    $root = Resolve-EimsArtifactRoot -Root $ArtifactRootOverride
    $caps = Get-EimsTerminalCaps -Ascii:$Ascii -Plain:$Plain
    # Without VT there is no in-place redraw; the line-prompt fallback is used
    # instead of appending a new frame every poll.
    if (-not $caps.Ansi) { $caps = [pscustomobject]@{ Ansi = $false; RawKey = $false; Unicode = $caps.Unicode } }

    $runtime = Resolve-EimsDashboardRuntimeMode -Persistent:$Persistent -Snapshot:$Snapshot
    if ($runtime.Mode -eq 'snapshot' -and -not $Snapshot) {
        # Host-stream notice only; never pollute the pipeline with text.
        try { Write-Host ('mode=snapshot ({0})' -f $runtime.Reason) -ForegroundColor DarkGray } catch { }
    }

    return (Invoke-EimsDashboardSession -Root $root -JobIdFilter $JobIdFilter `
                -IntervalSeconds $IntervalSeconds -Mode $runtime.Mode `
                -MaxFrames $MaxFrames -RawKey:$caps.RawKey -NoBell:$NoBell -Toast:$Toast `
                -Unicode:$caps.Unicode -Ansi:$caps.Ansi)
}

# ---------------------------------------------------------------------------
if (-not $NoRun) {
    if ($Watch -and $Once) {
        throw 'Specify either -Watch or -Once, not both.'
    }
    if ($Persistent -and $Snapshot) {
        throw 'Specify either -Persistent or -Snapshot, not both.'
    }
    if (($Persistent -or $Snapshot) -and -not $Dashboard) {
        throw '-Persistent and -Snapshot require -Dashboard.'
    }
    if ($Dashboard) {
        $null = Start-EimsDashboard -ArtifactRootOverride $ArtifactRoot `
                                    -JobIdFilter $JobId `
                                    -IntervalSeconds $PollSeconds `
                                    -NoBell:$NoBell `
                                    -NoColor:$NoColor `
                                    -Toast:$Toast `
                                    -Ascii:$Ascii `
                                    -Plain:$Plain `
                                    -Persistent:$Persistent `
                                    -Snapshot:$Snapshot `
                                    -MaxFrames $MaxFrames
        return
    }
    if (-not $Watch -and -not $Once) {
        $Once = $true
    }
    Start-EimsAgentJobMonitor -ArtifactRootOverride $ArtifactRoot `
                              -JobIdFilter $JobId `
                              -IntervalSeconds $PollSeconds `
                              -Continuous:$Watch `
                              -NoBell:$NoBell `
                              -NoColor:$NoColor `
                              -Toast:$Toast
}

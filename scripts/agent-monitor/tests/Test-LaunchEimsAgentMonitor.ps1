<#
.SYNOPSIS
    Focused tests for the Windows Trigger C auto-launch integration
    (Launch-EimsAgentMonitor.ps1 + EimsMonitorHost.ps1).

.DESCRIPTION
    No Pester, modules, network, database, or visible console is used. Every test
    uses injectable decisions or disposable synthetic directories under %TEMP%,
    and removes only its own directory afterwards. No agent process is started
    or stopped.

    Run from anywhere:
      powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<repo>\scripts\agent-monitor\tests\Test-LaunchEimsAgentMonitor.ps1"

    Exit code 0 = all assertions passed; 1 = one or more failed;
    2 = a monitor script could not be loaded or parsed.
#>
[CmdletBinding()]
param()

$savedErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Stop'

$script:Pass = 0
$script:Fail = 0
$script:TestRoot = Join-Path $env:TEMP ('eims-agent-launch-tests-' + [guid]::NewGuid().ToString('N'))
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

function Set-SyntheticFile {
    param([string]$Path, [AllowEmptyString()][string]$Content)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8 -NoNewline -ErrorAction Stop
}

$script:MonitorDir = Split-Path -Parent $PSScriptRoot
$script:MonitorPath = Join-Path $script:MonitorDir 'Watch-EimsAgentJobs.ps1'
$script:LaunchPath = Join-Path $script:MonitorDir 'Launch-EimsAgentMonitor.ps1'
$script:HostPath = Join-Path $script:MonitorDir 'EimsMonitorHost.ps1'

# Parse all three scripts before loading them; a syntax regression is a hard stop.
foreach ($path in @($script:MonitorPath, $script:LaunchPath, $script:HostPath)) {
    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $path, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count -gt 0) {
        Write-Host ('FATAL: parse error in {0}: {1}' -f $path, $parseErrors[0].Message) -ForegroundColor Red
        if (Test-Path -LiteralPath $script:TestRoot) { Remove-Item -LiteralPath $script:TestRoot -Recurse -Force }
        exit 2
    }
}

try {
    # The launcher reuses the watcher's scan/JSON helpers. Load both without
    # starting any loop and without spawning a visible console.
    . $script:MonitorPath -NoRun
    . $script:LaunchPath -NoRun
}
catch {
    Write-Host ('FATAL: could not load monitor scripts: {0}' -f $_.Exception.Message) -ForegroundColor Red
    if (Test-Path -LiteralPath $script:TestRoot) { Remove-Item -LiteralPath $script:TestRoot -Recurse -Force }
    exit 2
}

$script:InteractiveSession = [pscustomobject]@{
    UserInteractive  = $true
    InputRedirected  = $false
    OutputRedirected = $false
    HostName         = 'ConsoleHost'
    SessionName      = 'Console'
}
$script:HeadlessSession = [pscustomobject]@{
    UserInteractive  = $false
    InputRedirected  = $true
    OutputRedirected = $true
    HostName         = 'DefaultHost'
    SessionName      = 'Service'
}

try {
    # -----------------------------------------------------------------------
    Invoke-Test -Name 'eligibility: only running/pending jobs with safe job ids' -Body {
        $running = [pscustomobject]@{ JobId = 'job-1'; State = 'Running'; IsTerminal = $false }
        $pending = [pscustomobject]@{ JobId = 'job-2'; State = 'Pending'; IsTerminal = $false }
        Assert-True (Test-EimsAutoLaunchEligibility -Status $running) 'running job is eligible'
        Assert-True (Test-EimsAutoLaunchEligibility -Status $pending) 'pending job is eligible'

        foreach ($state in @('Completed', 'Failed', 'Cancelled', 'Unknown', '')) {
            $status = [pscustomobject]@{ JobId = 'job-3'; State = $state; IsTerminal = $false }
            Assert-Equal $false (Test-EimsAutoLaunchEligibility -Status $status) `
                ('state {0} is not eligible' -f $(if ($state) { $state } else { '<empty>' }))
        }
        $terminal = [pscustomobject]@{ JobId = 'job-4'; State = 'Running'; IsTerminal = $true }
        Assert-Equal $false (Test-EimsAutoLaunchEligibility -Status $terminal) 'terminal job is not eligible'

        foreach ($badId in @('', '..', 'a/b', 'bad path', '..\escape')) {
            $status = [pscustomobject]@{ JobId = $badId; State = 'Running'; IsTerminal = $false }
            Assert-Equal $false (Test-EimsAutoLaunchEligibility -Status $status) `
                ('unsafe job id is rejected: {0}' -f $badId)
        }
        Assert-Equal $false (Test-EimsAutoLaunchEligibility -Status $null) 'null status is not eligible'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'eligibility: agent allowlist is enforced when configured' -Body {
        $status = [pscustomobject]@{ JobId = 'job-5'; State = 'Running'; IsTerminal = $false }
        Assert-True (Test-EimsAutoLaunchEligibility -Status $status -AgentToken 'claude_code' `
            -AllowedAgents @('claude_code', 'opencode')) 'listed agent is eligible'
        Assert-Equal $false (Test-EimsAutoLaunchEligibility -Status $status -AgentToken 'grok' `
            -AllowedAgents @('claude_code', 'opencode')) 'unlisted agent is not eligible'
        Assert-Equal $false (Test-EimsAutoLaunchEligibility -Status $status -AgentToken '' `
            -AllowedAgents @('claude_code')) 'unknown agent is not eligible when filtered'
        Assert-True (Test-EimsAutoLaunchEligibility -Status $status -AgentToken '' `
            -AllowedAgents @()) 'no allowlist permits any eligible job'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'real runner schema: command derives the agent token' -Body {
        $root = Join-Path $script:TestRoot 'case-agent-command'
        $job = Join-Path $root 'job-open'
        New-Item -ItemType Directory -Path $job -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content `
            '{"runnerPid":74260,"agentPid":73212,"startedAt":"2026-11-17T16:22:23.823Z","command":"opencode.exe"}'

        $open = @(Get-EimsAutoLaunchEligibleJobs -ArtifactRoot $root -AllowedAgents @('opencode'))
        Assert-Equal 1 $open.Count 'opencode.exe maps to the opencode token'
        $claude = @(Get-EimsAutoLaunchEligibleJobs -ArtifactRoot $root -AllowedAgents @('claude_code'))
        Assert-Equal 0 $claude.Count 'opencode.exe does not match claude_code'

        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content `
            '{"runnerPid":74261,"agentPid":73213,"startedAt":"2026-11-17T16:22:23.823Z","command":"claude.exe"}'
        $claude2 = @(Get-EimsAutoLaunchEligibleJobs -ArtifactRoot $root -AllowedAgents @('claude_code'))
        Assert-Equal 1 $claude2.Count 'claude.exe maps to the claude_code token'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'large manifest does not block runner eligibility' -Body {
        $root = Join-Path $script:TestRoot 'case-large-manifest'
        $job = Join-Path $root 'job-large'
        New-Item -ItemType Directory -Path $job -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content `
            '{"runnerPid":74270,"agentPid":73220,"startedAt":"2026-11-17T16:22:23.823Z","command":"opencode.exe"}'
        # A real Chat_HAND manifest can be a multi-megabyte file inventory. It
        # must not be parsed just to find an agent token.
        $large = '{"version":1,"files":{"probe":"' + ('a' * 300000) + '"}}'
        Set-SyntheticFile -Path (Join-Path $job 'manifest.json') -Content $large

        $eligible = @(Get-EimsAutoLaunchEligibleJobs -ArtifactRoot $root -AllowedAgents @('opencode'))
        Assert-Equal 1 $eligible.Count 'runner token is used without reading the large manifest'
        $unfiltered = @(Get-EimsAutoLaunchEligibleJobs -ArtifactRoot $root)
        Assert-Equal 1 $unfiltered.Count 'no allowlist does not require reading job metadata'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'diagnosis distinguishes live, terminal, missing and headless' -Body {
        $liveRoot = Join-Path $script:TestRoot 'diag-live'
        $liveJob = Join-Path $liveRoot 'job-live'
        New-Item -ItemType Directory -Path $liveJob -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $liveJob 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $liveJob 'runner.json') -Content `
            '{"runnerPid":74260,"agentPid":73212,"startedAt":"2026-11-17T16:22:23.823Z","command":"opencode.exe"}'
        $diagLive = Get-EimsAutoLaunchDiagnosis -ArtifactRoot $liveRoot `
            -StateDirectory (Join-Path $script:TestRoot 'diag-state') `
            -AllowedAgents @() -Session $script:InteractiveSession -Processes @()
        Assert-Equal 1 $diagLive.EligibleJobs 'live real-schema job is eligible'
        Assert-Equal 1 $diagLive.Running 'diagnosis reports one Running job'
        Assert-True ($diagLive.Decision -like 'eligible job found*') 'live decision is explicit'

        $terminalRoot = Join-Path $script:TestRoot 'diag-terminal'
        $terminalJob = Join-Path $terminalRoot 'job-done'
        New-Item -ItemType Directory -Path $terminalJob -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $terminalJob 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $terminalJob 'exit.json') -Content '{"exitCode":0}'
        $diagDone = Get-EimsAutoLaunchDiagnosis -ArtifactRoot $terminalRoot `
            -StateDirectory (Join-Path $script:TestRoot 'diag-state') `
            -AllowedAgents @() -Session $script:InteractiveSession -Processes @()
        Assert-Equal 0 $diagDone.EligibleJobs 'terminal job is not eligible'
        Assert-Equal 1 $diagDone.Completed 'diagnosis reports one Completed job'
        Assert-True ($diagDone.Decision -like 'no eligible running job*') 'terminal decision includes counts'

        $missing = Join-Path $script:TestRoot 'diag-missing-does-not-exist'
        $diagMissing = Get-EimsAutoLaunchDiagnosis -ArtifactRoot $missing `
            -StateDirectory (Join-Path $script:TestRoot 'diag-state') `
            -AllowedAgents @() -Session $script:InteractiveSession -Processes @()
        Assert-Equal $false $diagMissing.RootExists 'missing root is reported'
        Assert-True ($diagMissing.Decision -like 'artifact root unavailable*') 'missing root decision is explicit'

        $diagHeadless = Get-EimsAutoLaunchDiagnosis -ArtifactRoot $liveRoot `
            -StateDirectory (Join-Path $script:TestRoot 'diag-state') `
            -AllowedAgents @() -Session $script:HeadlessSession -Processes @()
        Assert-True ($diagHeadless.Decision -like 'headless fallback:*') 'headless decision is explicit'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'headless detection never opens a window' -Body {
        Assert-True (Test-EimsAutoLaunchInteractiveSession -Session $script:InteractiveSession).Interactive `
            'interactive desktop is accepted'
        Assert-Equal $false (Test-EimsAutoLaunchInteractiveSession -Session $script:HeadlessSession).Interactive `
            'service session is headless'

        $redirected = [pscustomobject]@{
            UserInteractive = $true; InputRedirected = $true; OutputRedirected = $true
            HostName = 'SomeEmbeddedHost'; SessionName = 'Console'
        }
        Assert-Equal $false (Test-EimsAutoLaunchInteractiveSession -Session $redirected).Interactive `
            'redirected I/O in a non-console host is headless'

        $ideTerminal = [pscustomobject]@{
            UserInteractive = $true; InputRedirected = $true; OutputRedirected = $true
            HostName = 'ConsoleHost'; SessionName = 'Console'
        }
        Assert-True (Test-EimsAutoLaunchInteractiveSession -Session $ideTerminal).Interactive `
            'a console host can still open a window even when its own IO is redirected'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'dry-run decision: eligible job launches, headless falls back' -Body {
        $root = Join-Path $script:TestRoot 'decision-root'
        $job = Join-Path $root 'job-live'
        New-Item -ItemType Directory -Path $job -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content '{"pid":4242}'
        $stateDir = Join-Path $script:TestRoot 'decision-state'
        New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

        $launched = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:InteractiveSession -Processes @() -DryRun
        Assert-True $launched.Launched 'dry-run reports a launch for a live job'
        Assert-Equal 1 $launched.EligibleJobs 'one eligible job discovered'

        $headless = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:HeadlessSession -Processes @() -DryRun
        Assert-Equal $false $headless.Launched 'headless dry-run does not launch'
        Assert-True ($headless.Reason -like 'headless fallback:*') 'headless fallback reason is explicit'

        $noJobs = Invoke-EimsAutoLaunch -ArtifactRoot (Join-Path $script:TestRoot 'empty-root') `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:InteractiveSession -Processes @() -DryRun
        Assert-Equal $false $noJobs.Launched 'no eligible job means no launch'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'eligibility: manifest agent token gates a real scan' -Body {
        $root = Join-Path $script:TestRoot 'agent-root'
        $job = Join-Path $root 'agent-job'
        New-Item -ItemType Directory -Path $job -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content '{"pid":77}'
        Set-SyntheticFile -Path (Join-Path $job 'manifest.json') -Content '{"agent":"claude_code"}'
        $stateDir = Join-Path $script:TestRoot 'agent-state'
        New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

        $allowed = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -AllowedAgents @('claude_code') `
            -Session $script:InteractiveSession -Processes @() -DryRun
        Assert-True $allowed.Launched 'allowlisted agent triggers launch'

        $blocked = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -AllowedAgents @('opencode') `
            -Session $script:InteractiveSession -Processes @() -DryRun
        Assert-Equal $false $blocked.Launched 'non-allowlisted agent does not trigger launch'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'entry point: -ArtifactRoot survives watcher function load' -Body {
        # Regression: dot-sourcing the watcher shares scope; its param() block
        # used to overwrite the launcher's own $ArtifactRoot/$PollSeconds.
        $root = Join-Path $script:TestRoot 'entry-root'
        $job = Join-Path $root 'job-entry'
        New-Item -ItemType Directory -Path $job -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content '{"pid":5555}'
        $stateDir = Join-Path $script:TestRoot 'entry-state'
        if (Test-Path -LiteralPath $stateDir) { Remove-Item -LiteralPath $stateDir -Recurse -Force }
        $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script:LaunchPath `
            -Once -DryRun -NoProcessScan -ArtifactRoot $root -StateDirectory $stateDir 2>&1 | Out-String
        if ($output -notmatch 'would launch visible TUI') {
            Write-Host ('ENTRY OUTPUT: ' + $output)
        }
        Assert-True ($output -match 'would launch visible TUI') `
            'entry point honours the supplied artifact root and reports a launch'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'duplicate suppression: exclusive lease and process marker' -Body {
        $dir = Join-Path $script:TestRoot 'dup-state'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $leasePath = Join-Path $dir 'monitor.lease'

        $first = New-EimsAutoLaunchLease -LeasePath $leasePath
        Assert-True ($null -ne $first) 'first lease acquisition succeeds'
        Assert-True (Test-EimsAutoLaunchLeaseHeld -LeasePath $leasePath) 'held lease is detected'
        $second = New-EimsAutoLaunchLease -LeasePath $leasePath
        Assert-True ($null -eq $second) 'second lease acquisition is refused'
        Assert-True (Test-EimsAutoLaunchDuplicateWindow -StateDirectory $dir -Processes @()) `
            'held lease suppresses a duplicate window'
        $first.Dispose()
        Assert-Equal $false (Test-EimsAutoLaunchLeaseHeld -LeasePath $leasePath) 'released lease is free'
        Assert-Equal $false (Test-EimsAutoLaunchDuplicateWindow -StateDirectory $dir -Processes @()) `
            'no duplicate once lease is released'

        $fake = @(
            [pscustomobject]@{ ProcessId = 4242; CommandLine = 'powershell.exe -File C:\x\Watch-EimsAgentJobs.ps1 -Dashboard' },
            [pscustomobject]@{ ProcessId = 99; CommandLine = 'C:\Windows\System32\notepad.exe' }
        )
        $ids = @(Get-EimsAutoLaunchMonitorProcessIds -Processes $fake)
        Assert-Equal 1 $ids.Count 'only the TUI process matches the command-line marker'
        Assert-Equal 4242 $ids[0] 'matched process id is the TUI process'
        Assert-True (Test-EimsAutoLaunchDuplicateWindow -StateDirectory $dir -Processes $fake) `
            'an existing TUI process suppresses a duplicate window'

        $hostFake = @(
            [pscustomobject]@{ ProcessId = 4343; CommandLine = 'powershell.exe -File C:\x\EimsMonitorHost.ps1 -MonitorScript C:\x\Watch-EimsAgentJobs.ps1' }
        )
        $hostIds = @(Get-EimsAutoLaunchMonitorProcessIds -Processes $hostFake)
        Assert-Equal 1 $hostIds.Count 'a real host -File invocation matches'
        Assert-Equal 4343 $hostIds[0] 'matched process id is the host process'

        $selfMatch = @(
            [pscustomobject]@{ ProcessId = 4444; CommandLine = 'powershell.exe -NoProfile -Command "Get-Content Watch-EimsAgentJobs.ps1; Launch-EimsAgentMonitor.ps1"' },
            [pscustomobject]@{ ProcessId = 4545; CommandLine = 'powershell.exe -File C:\x\Launch-EimsAgentMonitor.ps1 -Once' }
        )
        Assert-Equal 0 @(Get-EimsAutoLaunchMonitorProcessIds -Processes $selfMatch).Count `
            'a shell -Command or a launcher process is not a TUI'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'duplicate suppression: atomic claim, stale records, dry-run' -Body {
        $dir = Join-Path $script:TestRoot 'claim-state'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $stateFile = Join-Path $dir 'monitor.json'
        $claim = [ordered]@{ pid = 0; nonce = 'claim-1'; claimedAt = ([datetime]::UtcNow).ToString('o') }
        Assert-True (New-EimsAutoLaunchClaim -StateFile $stateFile -Record $claim) `
            'first atomic claim wins'
        Assert-Equal $false (New-EimsAutoLaunchClaim -StateFile $stateFile -Record $claim) `
            'second atomic claim loses'
        Assert-True (Test-EimsAutoLaunchDuplicateWindow -StateDirectory $dir -Processes @()) `
            'fresh provisional claim suppresses a duplicate'

        Remove-Item -LiteralPath $stateFile -Force
        $stale = [ordered]@{ pid = 0; nonce = 'old'; claimedAt = ([datetime]::UtcNow.AddMinutes(-5)).ToString('o') }
        Assert-True (New-EimsAutoLaunchClaim -StateFile $stateFile -Record $stale) 'stale claim can be written'
        Assert-Equal $false (Test-EimsAutoLaunchDuplicateWindow -StateDirectory $dir -Processes @()) `
            'stale provisional claim is not a live duplicate'

        # A dead recorded pid must not throw or block recovery.
        Write-EimsAutoLaunchState -StateFile $stateFile `
            -Record ([ordered]@{ pid = 2147483647; nonce = 'dead'; startedAt = '2026-11-17T01:02:03.0000000Z' })
        Assert-Equal $false (Test-EimsAutoLaunchDuplicateWindow -StateDirectory $dir -Processes @()) `
            'dead recorded pid is not a live duplicate'

        # A held lease must suppress the full decision pipeline as well.
        $root = Join-Path $script:TestRoot 'claim-root'
        $job = Join-Path $root 'job-live'
        New-Item -ItemType Directory -Path $job -Force | Out-Null
        Set-SyntheticFile -Path (Join-Path $job 'stdout.log') -Content ''
        Set-SyntheticFile -Path (Join-Path $job 'runner.json') -Content '{"pid":77}'
        $lease = New-EimsAutoLaunchLease -LeasePath (Join-Path $dir 'monitor.lease')
        $decision = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $dir -Session $script:InteractiveSession -Processes @() -DryRun
        Assert-Equal $false $decision.Launched 'held lease prevents a dry-run launch decision'
        Assert-True ($decision.Reason -match 'duplicate') 'duplicate reason is explicit'
        $lease.Dispose()
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'stale claim: reclaimed only when the PID is dead and the nonce validates' -Body {
        $dir = Join-Path $script:TestRoot 'reclaim-state'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $stateFile = Join-Path $dir 'monitor.json'
        $now = [datetime]::UtcNow
        $deadLookup = { param([long]$ProcessId) $null }

        Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
            pid = 2147483647; startedAt = '2026-11-17T01:02:03.0000000Z'
            nonce = 'dead-1'; claimedAt = $now.AddMinutes(-5).ToString('o') })
        Assert-Equal 'reclaimed' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
            -Now $now -ProcessIdentity $deadLookup) 'a dead recorded pid is reclaimed'
        Assert-Equal $false (Test-Path -LiteralPath $stateFile) 'the dead record is gone'

        Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
            pid = 0; nonce = 'fresh'; claimedAt = $now.ToString('o') })
        Assert-Equal 'provisional' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
            -Now $now -ProcessIdentity $deadLookup) 'a fresh provisional claim is not reclaimed'
        Assert-True (Test-Path -LiteralPath $stateFile) 'the fresh claim is preserved'

        Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
            pid = 0; nonce = 'old'; claimedAt = $now.AddMinutes(-5).ToString('o') })
        Assert-Equal 'reclaimed' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
            -Now $now -ProcessIdentity $deadLookup) 'a stale pid=0 claim is reclaimed'

        # A truncated/tampered record has no nonce to validate; it is removed only
        # after an aged, stable second read with a free lease.
        Set-SyntheticFile -Path $stateFile -Content '{"pid":'
        Assert-Equal 'provisional' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
            -Now $now -ProcessIdentity $deadLookup) 'a just-written truncated record is left alone'
        Assert-Equal 'reclaimed' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
            -Now $now.AddMinutes(1) -ProcessIdentity $deadLookup -ProvisionalGraceSeconds 0) `
            'a stable truncated record is reclaimed'
        Assert-Equal $false (Test-Path -LiteralPath $stateFile) 'the truncated record is gone'

        $started = [datetime]::Parse('2026-11-17T01:02:03Z').ToUniversalTime()
        $startedText = $started.ToString('o')
        Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
            pid = 4321; startedAt = $startedText; nonce = 'live-1'
            claimedAt = $now.AddMinutes(-5).ToString('o') })
        $liveLookup = {
            param([long]$ProcessId)
            return [pscustomobject]@{ Id = $ProcessId; StartTimeText = $startedText }
        }
        Assert-Equal 'live' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
            -Now $now -ProcessIdentity $liveLookup) 'a live recorded pid is never reclaimed'
        Assert-True (Test-Path -LiteralPath $stateFile) 'the live record is preserved'

        $reusedText = $started.AddSeconds(9).ToString('o')
        $reusedLookup = {
            param([long]$ProcessId)
            return [pscustomobject]@{ Id = $ProcessId; StartTimeText = $reusedText }
        }
        Assert-Equal 'reclaimed' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
            -Now $now -ProcessIdentity $reusedLookup) 'a recycled pid (different start time) is reclaimed'

        # A held lease is positive proof of a live owner, even for an otherwise
        # stale-looking record.
        Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
            pid = 0; nonce = 'leased'; claimedAt = $now.AddMinutes(-5).ToString('o') })
        $heldLease = New-EimsAutoLaunchLease -LeasePath (Join-Path $dir 'monitor.lease')
        try {
            Assert-Equal 'leased' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
                -Now $now -ProcessIdentity $deadLookup) 'a held lease blocks reclamation'
        }
        finally {
            if ($null -ne $heldLease) { $heldLease.Dispose() }
        }
        Assert-True (Test-Path -LiteralPath $stateFile) 'the leased record is preserved'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'stale claim: a concurrently replaced record is never removed' -Body {
        $dir = Join-Path $script:TestRoot 'reclaim-race'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $stateFile = Join-Path $dir 'monitor.json'
        $now = [datetime]::UtcNow
        Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
            pid = 2147483647; startedAt = '2026-11-17T01:02:03.0000000Z'
            nonce = 'stale-race'; claimedAt = $now.AddMinutes(-5).ToString('o') })

        # While the stale record is being validated, a faster launcher wins the
        # claim. The nonce no longer matches, so reclamation must abort.
        $racingLookup = {
            param([long]$ProcessId)
            Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
                pid = 0; nonce = 'winner'; claimedAt = $now.ToString('o') })
            return $null
        }

        Assert-Equal 'changed' (Remove-EimsAutoLaunchStaleState -StateFile $stateFile `
            -Now $now -ProcessIdentity $racingLookup) 'a replaced record aborts reclamation'
        $record = Read-EimsAutoLaunchState -StateFile $stateFile
        Assert-Equal 'winner' $record.nonce 'the newer claim is preserved'
        Assert-Equal $false (New-EimsAutoLaunchClaim -StateFile $stateFile `
            -Record ([ordered]@{ pid = 0; nonce = 'loser' })) 'the older launcher cannot overwrite the winner'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'stale claim: a dead record no longer blocks the persistent dashboard' -Body {
        $root = Join-Path $script:TestRoot 'reclaim-open-root'
        New-Item -ItemType Directory -Path $root -Force | Out-Null
        $dir = Join-Path $script:TestRoot 'reclaim-open-state'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $stateFile = Join-Path $dir 'monitor.json'
        Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
            pid = 2147483647; startedAt = '2026-11-17T01:02:03.0000000Z'
            nonce = 'dead-pipeline'; claimedAt = ([datetime]::UtcNow.AddMinutes(-5)).ToString('o') })

        $spawn = {
            param($arguments)
            return [pscustomobject]@{ Id = 5511 }
        }
        $deadLookup = { param([long]$ProcessId) $null }

        $opened = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $dir -Session $script:InteractiveSession -Processes @() `
            -Open -StartAction $spawn -ProcessIdentity $deadLookup
        Assert-True $opened.Launched 'a dead stale claim is reclaimed instead of blocking forever'
        Assert-Equal 5511 $opened.Pid 'the dashboard is spawned after reclamation'
        $record = Read-EimsAutoLaunchState -StateFile $stateFile
        Assert-True ($null -ne $record) 'a new claim record exists'
        Assert-True ($record.nonce -ne 'dead-pipeline') 'the claim is rewritten with a new nonce'
        Assert-Equal 0 $record.pid 'the new claim stays pid 0 until the host writes its identity'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'cleanup: nonce-bound state removal and lease release' -Body {
        $dir = Join-Path $script:TestRoot 'cleanup-state'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $stateFile = Join-Path $dir 'monitor.json'
        Write-EimsAutoLaunchState -StateFile $stateFile `
            -Record ([ordered]@{ pid = 1234; nonce = 'abc'; startedAt = '2026-11-17T01:02:03.0000000Z' })
        Assert-Equal $false (Clear-EimsAutoLaunchState -StateFile $stateFile -Nonce 'other') `
            'state with a different nonce is not removed'
        Assert-True (Test-Path -LiteralPath $stateFile) 'foreign state file is preserved'
        Assert-Equal $true (Clear-EimsAutoLaunchState -StateFile $stateFile -Nonce 'abc') `
            'matching nonce removes owned state'
        Assert-Equal $false (Test-Path -LiteralPath $stateFile) 'owned state file is gone'

        $leasePath = Join-Path $dir 'monitor.lease'
        $lease = New-EimsAutoLaunchLease -LeasePath $leasePath
        Assert-True (Test-EimsAutoLaunchLeaseHeld -LeasePath $leasePath) 'lease held before cleanup'
        Assert-Equal $true (Clear-EimsAutoLaunchState -StateFile (Join-Path $dir 'none.json') `
            -Nonce 'abc' -LeaseStream $lease) 'cleanup reports success with no state file'
        Assert-Equal $false (Test-EimsAutoLaunchLeaseHeld -LeasePath $leasePath) 'cleanup releases the lease'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'cleanup: only the identity-verified owned process is stopped' -Body {
        $started = [datetime]::Parse('2026-11-17T01:02:03Z').ToUniversalTime()
        $record = [pscustomobject]@{ pid = 1234; startedAt = $started.ToString('o'); nonce = 'nonce-1234' }
        $owned = [pscustomobject]@{ Id = 1234; StartTime = $started }
        $otherPid = [pscustomobject]@{ Id = 9999; StartTime = $started }
        $otherStart = [pscustomobject]@{ Id = 1234; StartTime = $started.AddSeconds(1) }
        $monitorCommand = 'powershell.exe -NoProfile -File "C:\x\EimsMonitorHost.ps1" -MonitorScript "C:\x\Watch-EimsAgentJobs.ps1"'

        Assert-True (Test-EimsAutoLaunchOwnedProcess -Record $record -Process $owned `
            -CommandLine $monitorCommand) 'matching pid, start time, nonce and command line are owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $record -Process $otherPid `
            -CommandLine $monitorCommand) 'different pid is not owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $record -Process $otherStart `
            -CommandLine $monitorCommand) 'different start time (recycled pid) is not owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $record -Process $null `
            -CommandLine $monitorCommand) 'missing process is not owned'

        $calls = New-Object System.Collections.ArrayList
        $stopper = {
            param([int]$ProcessId, [switch]$Force)
            [void]$calls.Add(('{0}:{1}' -f $ProcessId, $Force))
        }
        Assert-Equal $true (Stop-EimsAutoLaunchOwnedProcess -Record $record -Process $owned `
            -CommandLine $monitorCommand -StopAction $stopper) 'owned process is stopped'
        Assert-Equal 1 $calls.Count 'one stop call for the owned process'
        Assert-Equal '1234:False' $calls[0] 'graceful stop is attempted first'
        Assert-Equal $false (Stop-EimsAutoLaunchOwnedProcess -Record $record -Process $otherPid `
            -CommandLine $monitorCommand -StopAction $stopper) 'foreign process is not stopped'
        Assert-Equal 1 $calls.Count 'no extra stop call for a foreign process'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'persistent open: zero jobs, missing root, headless' -Body {
        $emptyRoot = Join-Path $script:TestRoot 'open-empty'
        New-Item -ItemType Directory -Path $emptyRoot -Force | Out-Null
        $stateDir = Join-Path $script:TestRoot 'open-empty-state'
        New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

        $idle = Invoke-EimsAutoLaunch -ArtifactRoot $emptyRoot `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:InteractiveSession `
            -Processes @() -DryRun -Open
        Assert-True $idle.Launched 'zero jobs still opens the persistent dashboard'
        Assert-Equal 0 $idle.EligibleJobs 'zero-job open requires no eligible job'
        Assert-Equal 'dry-run: would open persistent dashboard' $idle.Reason 'zero-job open reason is explicit'

        $missingRoot = Join-Path $script:TestRoot 'open-missing-root'
        $missing = Invoke-EimsAutoLaunch -ArtifactRoot $missingRoot `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:InteractiveSession `
            -Processes @() -DryRun -Open
        Assert-True $missing.Launched 'missing root still opens (dashboard shows MISSING)'
        Assert-Equal $false $missing.RootExists 'missing root is reported honestly'

        $headless = Invoke-EimsAutoLaunch -ArtifactRoot $emptyRoot `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:HeadlessSession `
            -Processes @() -DryRun -Open
        Assert-Equal $false $headless.Launched 'headless open spawns nothing'
        Assert-True ($headless.Reason -like 'headless fallback:*') 'headless open reason is explicit'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'persistent open: spawn arguments, mode record, single instance' -Body {
        $root = Join-Path $script:TestRoot 'open-real'
        New-Item -ItemType Directory -Path $root -Force | Out-Null
        $stateDir = Join-Path $script:TestRoot 'open-real-state'
        New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
        $script:SpawnedArguments = $null
        $spawn = {
            param($arguments)
            $script:SpawnedArguments = @($arguments)
            return [pscustomobject]@{ Id = 4321 }
        }

        $opened = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:InteractiveSession `
            -Processes @() -Open -StartAction $spawn
        Assert-True $opened.Launched 'injected spawn reports an open'
        Assert-Equal 4321 $opened.Pid 'spawned host pid is reported'
        Assert-Equal 'opened persistent dashboard' $opened.Reason 'open reason is explicit'

        $joined = @($script:SpawnedArguments) -join ' '
        Assert-True ($joined -match 'EimsMonitorHost\.ps1') 'host script is invoked with -File'
        Assert-True ($joined -match 'Watch-EimsAgentJobs\.ps1') 'monitor script is passed to the host'
        Assert-True ($joined -match '"?-Mode"?') 'host mode is passed explicitly'
        Assert-True ($joined -match 'Persistent') 'host mode is Persistent'

        $record = Read-EimsAutoLaunchState -StateFile (Join-Path $stateDir 'monitor.json')
        Assert-True ($null -ne $record) 'claim record exists after spawn'
        Assert-Equal 'persistent' $record.mode 'claim records persistent mode'
        Assert-Equal $false $record.idleClose 'claim records no idle close'
        Assert-Equal 0 $record.pid 'claim pid stays 0 until the host writes its identity'

        $second = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:InteractiveSession `
            -Processes @() -Open -StartAction { param($a) throw 'must not spawn a second window' }
        Assert-Equal $false $second.Launched 'a second open is suppressed'
        Assert-True ($second.Reason -match 'duplicate') 'duplicate open reason is explicit'

        $lease = New-EimsAutoLaunchLease -LeasePath (Join-Path $stateDir 'monitor.lease')
        Remove-Item -LiteralPath (Join-Path $stateDir 'monitor.json') -Force
        $held = Invoke-EimsAutoLaunch -ArtifactRoot $root `
            -MonitorScript $script:MonitorPath -HostScript $script:HostPath `
            -StateDirectory $stateDir -Session $script:InteractiveSession `
            -Processes @() -Open -DryRun
        Assert-Equal $false $held.Launched 'a held lease suppresses open'
        $lease.Dispose()
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'shutdown: exact-PID stop arguments, never a tree kill' -Body {
        $graceful = @(Get-EimsAutoLaunchStopArguments -ProcessId 4242)
        Assert-Equal 2 $graceful.Count 'graceful stop is /PID <pid> only'
        Assert-Equal '/PID' $graceful[0] 'graceful stop uses /PID'
        Assert-Equal '4242' $graceful[1] 'graceful stop targets the owned pid'
        Assert-Equal $false ($graceful -contains '/F') 'graceful stop is not forced'
        Assert-Equal $false ($graceful -contains '/T') 'graceful stop never kills a tree'

        $forced = @(Get-EimsAutoLaunchStopArguments -ProcessId 4242 -Force)
        Assert-Equal 3 $forced.Count 'forced stop is /PID <pid> /F'
        Assert-Equal '/F' $forced[2] 'forced stop is explicit'
        Assert-Equal $false ($forced -contains '/T') 'forced stop never kills a tree'

        $launcherSource = Get-Content -LiteralPath $script:LaunchPath -Raw
        Assert-True ($launcherSource -notmatch '/T\s+/F') 'launcher has no tree-kill invocation'
        Assert-True ($launcherSource -notmatch '/IM\b') 'launcher never kills by image name'
        Assert-True ($launcherSource -notmatch 'Stop-Process') 'launcher has no PowerShell-level process termination'
        Assert-True ($launcherSource -match 'Test-EimsAutoLaunchMonitorCommandLine') 'cleanup verifies the command line'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'shutdown: ownership refuses a non-monitor (agent) process' -Body {
        $started = [datetime]::Parse('2026-11-17T01:02:03Z').ToUniversalTime()
        $record = [pscustomobject]@{ pid = 1234; startedAt = $started.ToString('o'); nonce = 'nonce-1234' }
        $process = [pscustomobject]@{ Id = 1234; StartTime = $started }
        $monitorCommand = 'powershell.exe -NoProfile -File "C:\x\EimsMonitorHost.ps1" -MonitorScript "C:\x\Watch-EimsAgentJobs.ps1"'
        $agentCommand = '"C:\x\opencode.exe" run --model foo'

        Assert-True (Test-EimsAutoLaunchOwnedProcess -Record $record -Process $process -CommandLine $monitorCommand) `
            'monitor host command line is owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $record -Process $process -CommandLine $agentCommand) `
            'an agent runner command line is never owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $record -Process $process -CommandLine '') `
            'an unavailable command line is not ownership (fail closed)'

        $calls = New-Object System.Collections.ArrayList
        $stopper = {
            param([int]$ProcessId, [switch]$Force)
            [void]$calls.Add(('{0}:{1}' -f $ProcessId, $Force))
        }
        Assert-Equal $false (Stop-EimsAutoLaunchOwnedProcess -Record $record -Process $process `
            -CommandLine $agentCommand -StopAction $stopper) 'an agent process is never stopped'
        Assert-Equal 0 $calls.Count 'no stop call for an agent process'
        Assert-Equal $true (Stop-EimsAutoLaunchOwnedProcess -Record $record -Process $process `
            -CommandLine $monitorCommand -StopAction $stopper) 'the owned monitor host is stopped'
        Assert-Equal 1 $calls.Count 'one stop call for the owned host'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'ownership: blank start time, missing nonce and missing CIM line are not owned' -Body {
        $started = [datetime]::Parse('2026-11-17T01:02:03Z').ToUniversalTime()
        $process = [pscustomobject]@{ Id = 1234; StartTime = $started }
        $monitorCommand = 'powershell.exe -NoProfile -File "C:\x\EimsMonitorHost.ps1" -MonitorScript "C:\x\Watch-EimsAgentJobs.ps1"'
        $agentCommand = '"C:\x\opencode.exe" run --model foo'
        $complete = [pscustomobject]@{ pid = 1234; startedAt = $started.ToString('o'); nonce = 'n1' }
        $noStart = [pscustomobject]@{ pid = 1234; startedAt = ''; nonce = 'n1' }
        $noNonce = [pscustomobject]@{ pid = 1234; startedAt = $started.ToString('o'); nonce = '' }
        $unreadableStart = [pscustomobject]@{ Id = 1234 }

        Assert-True (Test-EimsAutoLaunchOwnedProcess -Record $complete -Process $process `
            -CommandLine $monitorCommand) 'complete evidence is owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $complete -Process $process `
            -CommandLine '') 'empty command line is not owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $complete -Process $process `
            -CommandLine '   ') 'blank command line is not owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $noStart -Process $process `
            -CommandLine $monitorCommand) 'blank startedAt is not owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $noNonce -Process $process `
            -CommandLine $monitorCommand) 'missing nonce is not owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $complete -Process $unreadableStart `
            -CommandLine $monitorCommand) 'unreadable process start time is not owned'
        Assert-Equal $false (Test-EimsAutoLaunchOwnedProcess -Record $complete -Process $process `
            -CommandLine $agentCommand) 'a record pointing at an agent process is not owned'

        $calls = New-Object System.Collections.ArrayList
        $stopper = {
            param([int]$ProcessId, [switch]$Force)
            [void]$calls.Add($ProcessId)
        }
        $ambiguous = @(
            @{ Record = $complete; Process = $process; CommandLine = '' },
            @{ Record = $complete; Process = $process; CommandLine = '   ' },
            @{ Record = $noStart; Process = $process; CommandLine = $monitorCommand },
            @{ Record = $noNonce; Process = $process; CommandLine = $monitorCommand },
            @{ Record = $complete; Process = $unreadableStart; CommandLine = $monitorCommand },
            @{ Record = $complete; Process = $process; CommandLine = $agentCommand }
        )
        foreach ($case in $ambiguous) {
            Assert-Equal $false (Stop-EimsAutoLaunchOwnedProcess -Record $case.Record `
                -Process $case.Process -CommandLine $case.CommandLine -StopAction $stopper) `
                'ambiguous evidence is never signalled'
        }
        Assert-Equal 0 $calls.Count 'no signal is sent for any ambiguous case'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'cleanup pipeline: incomplete evidence clears state but signals nothing' -Body {
        $started = [datetime]::Parse('2026-11-17T01:02:03Z').ToUniversalTime()
        $dir = Join-Path $script:TestRoot 'cleanup-evidence'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $stateFile = Join-Path $dir 'monitor.json'
        $process = [pscustomobject]@{ Id = 2468; StartTime = $started }
        $monitorCommand = 'powershell.exe -NoProfile -File "C:\x\EimsMonitorHost.ps1"'
        $calls = New-Object System.Collections.ArrayList
        $stopper = {
            param([int]$ProcessId, [switch]$Force)
            [void]$calls.Add($ProcessId)
        }
        $write = {
            Write-EimsAutoLaunchState -StateFile $stateFile -Record ([ordered]@{
                pid = 2468; startedAt = $started.ToString('o'); nonce = 'cleanup-1' })
        }

        & $write
        # A live owned host always holds monitor.lease, so refusal below is caused
        # by the evidence, not by a missing lease.
        $lease = New-EimsAutoLaunchLease -LeasePath (Join-Path $dir 'monitor.lease')
        try {
            $empty = Invoke-EimsAutoLaunchCleanup -StateDirectory $dir -Process $process `
                -CommandLine '' -StopAction $stopper
            Assert-Equal $false $empty.Stopped 'an empty CIM command line is not ownership'
            Assert-Equal 0 $calls.Count 'no signal is sent when the command line is missing'
            Assert-True ($empty.Reason -match 'no signal sent') 'the refusal is reported explicitly'

            & $write
            $matched = Invoke-EimsAutoLaunchCleanup -StateDirectory $dir -Process $process `
                -CommandLine $monitorCommand -StopAction $stopper
            Assert-Equal $true $matched.Stopped 'complete evidence stops the owned host'
            Assert-Equal 1 $calls.Count 'exactly one signal is sent'
            Assert-Equal $false (Test-Path -LiteralPath $stateFile) 'the owned state record is cleared'
        }
        finally {
            if ($null -ne $lease) { $lease.Dispose() }
        }

        # A free lease means no live owned host exists, so a surviving record is
        # cleared without ever signalling its PID.
        & $write
        $unleased = Invoke-EimsAutoLaunchCleanup -StateDirectory $dir -Process $process `
            -CommandLine $monitorCommand -StopAction $stopper
        Assert-Equal $false $unleased.Stopped 'a free lease means no live owned host to stop'
        Assert-Equal 1 $calls.Count 'no signal is sent without a held lease'
        Assert-True ($unleased.Reason -match 'lease not held') 'the lease refusal is reported explicitly'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'host script has no job-control path and publishes mode' -Body {
        $hostSource = Get-Content -LiteralPath $script:HostPath -Raw
        Assert-True ($hostSource -notmatch 'Stop-Process|taskkill') 'host cannot signal or kill any process'
        Assert-True ($hostSource -match 'idleClose') 'host publishes idleClose in its identity record'
        Assert-True ($hostSource -match 'Persistent') 'host runs the TUI in persistent mode'
        Assert-True ($hostSource -match 'ownsRecord') 'host only removes its own state record'
    }

    # -----------------------------------------------------------------------
    Invoke-Test -Name 'entry point: -Open and -Snapshot/-Open mode separation' -Body {
        $root = Join-Path $script:TestRoot 'entry-open-root'
        New-Item -ItemType Directory -Path $root -Force | Out-Null
        $stateDir = Join-Path $script:TestRoot 'entry-open-state'
        if (Test-Path -LiteralPath $stateDir) { Remove-Item -LiteralPath $stateDir -Recurse -Force }
        # A thrown mode conflict writes to stderr; merging it must not become a
        # terminating NativeCommandError inside this test.
        $saved = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $openOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script:LaunchPath `
                -Open -DryRun -NoProcessScan -ArtifactRoot $root -StateDirectory $stateDir 2>&1 | Out-String
            Assert-True ($openOutput -match 'would open persistent dashboard') `
                'entry point -Open reports a zero-job open'

            $conflict = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script:LaunchPath `
                -Open -Once -DryRun -NoProcessScan -ArtifactRoot $root -StateDirectory $stateDir 2>&1 | Out-String
            Assert-True ($conflict -match '-Open') 'entry point rejects -Open with -Once'
            Assert-True ($conflict -match 'not both') 'mode conflict message is explicit'
        }
        finally { $ErrorActionPreference = $saved }
    }
}
finally {
    if (Test-Path -LiteralPath $script:TestRoot) {
        Remove-Item -LiteralPath $script:TestRoot -Recurse -Force
    }
    $ErrorActionPreference = $savedErrorActionPreference
}

Write-Host ('Results: {0} passed, {1} failed' -f $script:Pass, $script:Fail)
if ($script:Fail -gt 0) { exit 1 }
exit 0

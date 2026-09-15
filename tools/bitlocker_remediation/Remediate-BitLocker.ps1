<#
.SYNOPSIS
    BitLocker remediation assistant for EIMS endpoints.

.DESCRIPTION
    Read-only BitLocker state assessment plus a strictly-scoped, explicitly
    authorized remediation action (resume protection ONLY).

    SAFETY CONTRACT
    ------------------------------------------------------------------------
    * PLAN-ONLY DEFAULT: without -Apply this script only reports a plan and
      makes NO change to the machine.
    * Applying a change requires ALL of:
        (1) the -Apply switch,
        (2) an Administrator shell,
        (3) an exact typed confirmation "REMEDIATE <MountPoint>".
    * The ONLY mutation ever performed is Resume-BitLocker for a volume that is
      encrypted but currently suspended (CASE 2). No other change is possible.
    * This tool NEVER enables BitLocker, NEVER creates recovery
      passwords/protectors, NEVER decrypts, and NEVER reboots the machine
      (no Restart-Computer / shutdown / wmic).
    * The BitLocker Recovery Password is NEVER read, printed, written, or
      exported. Key protectors are filtered by KeyProtectorType and COUNTED -
      secret material is never accessed.

    PLAN MATRIX
    ------------------------------------------------------------------------
      CASE  STATE                                         PLAN (DECISION)
      1     Protected + FullyEncrypted + 100% + recovery
            protector present                              -> NO ACTION REQUIRED
      2     FullyEncrypted but ProtectionStatus = Off
            (suspended) with a recovery protector          -> RESUME PROTECTION (Apply)
      3     Encryption/Decryption in progress or volume
            not yet FullyEncrypted                         -> IN PROGRESS (no action)
      4     Encrypted/Protected but recovery protector
            count == 0                                     -> BLOCKED (RECOVERY / ESCROW
                                                              REQUIRED) - no automated fix
      5     FullyDecrypted / Protection Off                -> ACTION REQUIRED (approved
                                                              encryption policy needed)
      6     Unknown / query failure                        -> FAIL SAFE (no automated action)

.PARAMETER MountPoint
    Drive letter to evaluate. Defaults to 'C:'.

.PARAMETER Apply
    When set, executes the plan IF permitted (CASE 2 only). Default is
    PLAN-ONLY.

.EXAMPLE
    .\Remediate-BitLocker.ps1
    Plan-only assessment of C:.

.EXAMPLE
    .\Remediate-BitLocker.ps1 -Apply
    Requires Administrator + exact typed confirmation; resumes protection if
    the volume is encrypted and suspended.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$MountPoint = 'C:',

    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$AuditLogPath = Join-Path $PSScriptRoot 'remediation-audit.log'

function Write-AuditLine {
    param([string]$Line)
    try {
        Add-Content -LiteralPath $AuditLogPath -Value $Line -Encoding UTF8
    } catch {
        Write-Warning "Could not write audit log: $_"
    }
}

function Test-IsAdministrator {
    $principal = New-Object Security.Principal.WindowsPrincipal(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-BitLockerSafeState {
    <#
    Collects ONLY non-secret BitLocker properties. Recovery Password material
    is never accessed.
    #>
    $empty = @{
        Available              = $false
        VolumeStatus           = 'Unavailable'
        ProtectionStatus       = 'Unavailable'
        EncryptionPercentage   = $null
        EncryptionMethod       = $null
        RecoveryProtectorCount = 0
    }

    try {
        $vol = Get-BitLockerVolume -MountPoint $MountPoint -ErrorAction Stop
    } catch {
        return $empty
    }

    if ($null -eq $vol) {
        return $empty
    }

    $rp = @()
    try {
        $rp = @($vol.KeyProtector | Where-Object { $_.KeyProtectorType -eq 'RecoveryPassword' })
    } catch {}

    return @{
        Available              = $true
        VolumeStatus           = [string]$vol.VolumeStatus
        ProtectionStatus       = [string]$vol.ProtectionStatus
        EncryptionPercentage   = $vol.EncryptionPercentage
        EncryptionMethod       = if ($null -ne $vol.EncryptionMethod) { [string]$vol.EncryptionMethod } else { $null }
        RecoveryProtectorCount = $rp.Count
    }
}

function Get-PlanDecision {
    param($State)

    if (-not $State.Available) {
        return @{
            Case      = 6
            Code      = 'UNKNOWN'
            Allowed   = $false
            Summary   = 'FAIL SAFE - BitLocker volume unavailable, no automated action.'
            Detail    = 'Get-BitLockerVolume returned no result for this mount point.'
        }
    }

    $vs = $State.VolumeStatus
    $ps = $State.ProtectionStatus
    $rp = $State.RecoveryProtectorCount

    if ($vs -in @('EncryptionInProgress', 'EncryptionPaused', 'DecryptionInProgress', 'DecryptionPaused')) {
        return @{
            Case      = 3
            Code      = 'IN_PROGRESS'
            Allowed   = $false
            Summary   = "IN PROGRESS - BitLocker operation in progress ($vs), no action."
            Detail    = 'Wait for the operation to finish before re-assessing.'
        }
    }

    if ($ps -eq 'On' -and $vs -eq 'FullyEncrypted') {
        if ($rp -gt 0) {
            return @{
                Case      = 1
                Code      = 'COMPLIANT'
                Allowed   = $false
                Summary   = 'NO ACTION REQUIRED - BitLocker is fully protected.'
                Detail    = 'Encrypted, protection on, and a recovery protector is present.'
            }
        }
        return @{
            Case      = 4
            Code      = 'BLOCKED'
            Allowed   = $false
            Summary   = 'BLOCKED - RECOVERY PROTECTOR / ESCROW REQUIRED.'
            Detail    = 'Volume is encrypted and protected but has NO recovery protector. This tool never creates recovery passwords; arrange a protector per your approved escrow policy, then re-run.'
        }
    }

    if ($ps -eq 'Off' -and $vs -eq 'FullyEncrypted') {
        if ($rp -gt 0) {
            return @{
                Case      = 2
                Code      = 'RESUME_PROTECTION'
                Allowed   = $true
                Summary   = 'RESUME PROTECTION - BitLocker is encrypted but protection is suspended.'
                Detail    = 'Resume is the ONLY permitted mutation for this state.'
            }
        }
        return @{
            Case      = 4
            Code      = 'BLOCKED'
            Allowed   = $false
            Summary   = 'BLOCKED - RECOVERY PROTECTOR / ESCROW REQUIRED.'
            Detail    = 'Volume is encrypted (protection suspended) but has NO recovery protector. Arrange a protector per your approved escrow policy before resuming.'
        }
    }

    if ($ps -eq 'On') {
        return @{
            Case      = 3
            Code      = 'IN_PROGRESS'
            Allowed   = $false
            Summary   = 'IN PROGRESS - volume not yet reported FullyEncrypted.'
            Detail    = "Current state: $vs / $ps (encrypted $($State.EncryptionPercentage)%)."
        }
    }

    if ($ps -eq 'Off' -and $vs -eq 'FullyDecrypted') {
        return @{
            Case      = 5
            Code      = 'ACTION_REQUIRED'
            Allowed   = $false
            Summary   = 'ACTION REQUIRED - ENCRYPTION ENABLEMENT NEEDS APPROVED POLICY.'
            Detail    = 'Volume is fully unencrypted. This tool never enables BitLocker; follow your approved endpoint-encryption policy.'
        }
    }

    return @{
        Case      = 6
        Code      = 'UNKNOWN'
        Allowed   = $false
        Summary   = 'FAIL SAFE - unknown state, no automated action.'
        Detail    = "State: $vs / $ps. Re-run as Administrator if necessary."
    }
}

# ── Main ─────────────────────────────────────────────────────────────────────
$state = Get-BitLockerSafeState

Write-Host ''
Write-Host '======================================================'
Write-Host ' EIMS BitLocker Remediation Assistant (PLAN-ONLY)'
Write-Host '======================================================'
Write-Host (" Host         : {0}" -f $env:COMPUTERNAME)
Write-Host (" MountPoint   : {0}" -f $MountPoint)
Write-Host (" Admin shell  : {0}" -f (Test-IsAdministrator))
Write-Host '------------------------------------------------------'
Write-Host (" Volume Status       : {0}" -f $state.VolumeStatus)
Write-Host (" Protection Status   : {0}" -f $state.ProtectionStatus)
if ($null -ne $state.EncryptionPercentage) {
    Write-Host (" Encryption %        : {0}" -f $state.EncryptionPercentage)
}
if ($null -ne $state.EncryptionMethod) {
    Write-Host (" Encryption Method   : {0}" -f $state.EncryptionMethod)
}
Write-Host (" Recovery Protectors : {0} (count only - NEVER the key)" -f $state.RecoveryProtectorCount)
Write-Host '------------------------------------------------------'

$plan = Get-PlanDecision -State $state

Write-Host (" Assessment  : CASE {0} [{1}]" -f $plan.Case, $plan.Code)
Write-Host (" Plan        : {0}" -f $plan.Summary)
Write-Host (" Detail      : {0}" -f $plan.Detail)
Write-Host ''

$before = "{0}|{1}" -f $state.VolumeStatus, $state.ProtectionStatus

# ── Apply path (triple-gated) ────────────────────────────────────────────────
if ($Apply) {
    if (-not $plan.Allowed) {
        Write-Host "[SAFE] No permitted mutation for CASE $($plan.Case). Nothing to apply."
        if ($plan.Code -eq 'BLOCKED') {
            Write-Host '  -> Arrange provision of a recovery protector via approved escrow, then re-run.'
        } elseif ($plan.Code -eq 'ACTION_REQUIRED') {
            Write-Host '  -> Obtain approved encryption-enablement policy sign-off before enabling BitLocker manually.'
        }
        $line = '{0}|{1}|{2}|{3}|{4}|{5}|NO_APPLY|no action permitted' -f `
            (Get-Date).ToString('s'), $env:COMPUTERNAME, $MountPoint, $before, $plan.Code, $plan.Case
        Write-AuditLine $line
        exit 0
    }

    if (-not (Test-IsAdministrator)) {
        Write-Host '[ERROR] -Apply requires an Administrator shell.'
        Write-Host '  Run from an elevated prompt (or "Run as administrator").'
        $line = '{0}|{1}|{2}|{3}|{4}|{5}|REJECTED|not administrator' -f `
            (Get-Date).ToString('s'), $env:COMPUTERNAME, $MountPoint, $before, $plan.Code, $plan.Case
        Write-AuditLine $line
        exit 3
    }

    $expected = "REMEDIATE {0}" -f $MountPoint
    Write-Host '[CONFIRM] An authorized operator must type the exact phrase below.'
    Write-Host ("          Type: {0}" -f $expected)
    $typed = Read-Host '  > '

    if ($typed.Trim() -ne $expected) {
        Write-Host '[ABORT] Confirmation did not match. No change was made.'
        $line = '{0}|{1}|{2}|{3}|{4}|{5}|ABORTED|confirmation mismatch' -f `
            (Get-Date).ToString('s'), $env:COMPUTERNAME, $MountPoint, $before, $plan.Code, $plan.Case
        Write-AuditLine $line
        exit 4
    }

    Write-Host "[APPLY] Resuming BitLocker protection on $MountPoint ..."
    try {
        Resume-BitLocker -MountPoint $MountPoint -ErrorAction Stop | Out-Null
    } catch {
        Write-Host "[ERROR] Resume-BitLocker failed: $_"
        $line = '{0}|{1}|{2}|{3}|{4}|{5}|FAILED|{6}' -f `
            (Get-Date).ToString('s'), $env:COMPUTERNAME, $MountPoint, $before, $plan.Code, $plan.Case, $_
        Write-AuditLine $line
        exit 5
    }

    Start-Sleep -Seconds 5
    $after = Get-BitLockerSafeState
    $afterSummary = "{0}/{1}" -f $after.ProtectionStatus, $after.VolumeStatus
    Write-Host "[OK] Post-action state: $afterSummary"
    Write-Host '[NOTE] If protection was suspended because of a pending reboot,'
    Write-Host '       resume takes effect after Windows restarts.'
    Write-Host '       This tool NEVER restarts the machine automatically.'
    $line = '{0}|{1}|{2}|{3}|{4}|{5}|APPLIED|{6}|reboot_required=manual' -f `
        (Get-Date).ToString('s'), $env:COMPUTERNAME, $MountPoint, $before, $plan.Code, $plan.Case, $afterSummary
    Write-AuditLine $line
    exit 0
}

# ── Plan-only path ───────────────────────────────────────────────────────────
Write-Host '[PLAN-ONLY] No change was made. Re-run with -Apply to execute the plan'
Write-Host '            (requires Administrator + exact typed confirmation).'
$line = '{0}|{1}|{2}|{3}|{4}|{5}|PLAN_ONLY|no change made' -f `
    (Get-Date).ToString('s'), $env:COMPUTERNAME, $MountPoint, $before, $plan.Code, $plan.Case
Write-AuditLine $line
exit 0
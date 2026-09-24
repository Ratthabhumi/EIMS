#requires -Version 5.1
<#
Build-EIMS-USB.ps1

Package the portable EIMS USB Auditor and deploy it to a removable drive
selected explicitly by the operator.

SAFETY GUARANTEES:
  - NEVER auto-selects a drive
  - NEVER formats or repartitions a drive
  - NEVER deletes the drive root
  - Only ever replaces:

      <drive>:\EIMS_USB_Auditor\

Steps:
  1. Stage and verify the portable package
  2. List removable drives
  3. Require explicit operator selection
  4. Validate free space and writability
  5. Confirm before replacing an existing package
  6. Copy package to USB
  7. Verify the on-drive copy using manifest hashes
#>

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

$ToolsDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = Split-Path -Parent $ToolsDir
$VenvPython = Join-Path $RepoRoot 'venv\Scripts\python.exe'
$BuilderPy  = Join-Path $ToolsDir 'build_usb_package.py'

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Host '[FAIL] Repo virtualenv not found:' -ForegroundColor Red
    Write-Host "       $VenvPython" -ForegroundColor Red
    exit 2
}

if (-not (Test-Path -LiteralPath $BuilderPy -PathType Leaf)) {
    Write-Host '[FAIL] USB package builder not found:' -ForegroundColor Red
    Write-Host "       $BuilderPy" -ForegroundColor Red
    exit 2
}

# ---------------------------------------------------------------------------
# 1) Stage the package
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host '  EIMS Portable USB Auditor Builder' -ForegroundColor Cyan
Write-Host '==============================================' -ForegroundColor Cyan
Write-Host '[..] Building staged package...'

& $VenvPython $BuilderPy --build

if ($LASTEXITCODE -ne 0) {
    Write-Host '[FAIL] Package build failed.' -ForegroundColor Red
    exit 2
}

$StagePackage = Join-Path $RepoRoot 'dist\usb-auditor\EIMS_USB_Auditor'

if (-not (Test-Path -LiteralPath $StagePackage -PathType Container)) {
    Write-Host '[FAIL] Staged package was not created:' -ForegroundColor Red
    Write-Host "       $StagePackage" -ForegroundColor Red
    exit 2
}

Write-Host '[OK] Staged package built.' -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2) Removable drive discovery and explicit selection
# ---------------------------------------------------------------------------

try {
    $Drives = @(
        Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 2' |
        Where-Object {
            $_.DeviceID -and
            $_.Size -gt 0
        } |
        Sort-Object DeviceID
    )
}
catch {
    Write-Host '[FAIL] Unable to enumerate removable drives.' -ForegroundColor Red
    Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
    exit 2
}

if ($Drives.Count -eq 0) {
    Write-Host ''
    Write-Host '[FAIL] No removable drive found.' -ForegroundColor Red
    Write-Host '       Insert a USB drive and run the builder again.' -ForegroundColor Yellow
    exit 2
}

Write-Host ''
Write-Host 'Removable drives found:' -ForegroundColor Cyan

for ($i = 0; $i -lt $Drives.Count; $i++) {
    $d = $Drives[$i]

    $sizeGB = 0
    if ($null -ne $d.Size) {
        $sizeGB = $d.Size / 1GB
    }

    $label = ''
    if ($d.VolumeName) {
        $label = "  [$($d.VolumeName)]"
    }

    Write-Host (
        "  [{0}] {1}  {2:N1} GB{3}" -f
        $i,
        $d.DeviceID,
        $sizeGB,
        $label
    )
}

Write-Host ''

$choice = Read-Host 'Select drive index'

if ($choice -notmatch '^\d+$') {
    Write-Host '[FAIL] Invalid drive selection.' -ForegroundColor Red
    exit 2
}

$choiceIndex = [int]$choice

if ($choiceIndex -lt 0 -or $choiceIndex -ge $Drives.Count) {
    Write-Host '[FAIL] Invalid drive selection.' -ForegroundColor Red
    exit 2
}

$Drive = $Drives[$choiceIndex]

if (-not $Drive.DeviceID) {
    Write-Host '[FAIL] Selected drive has no valid device ID.' -ForegroundColor Red
    exit 2
}

$DriveLetter = $Drive.DeviceID.TrimEnd(':')

# Extra safety: refuse the Windows system drive.
$SystemDriveLetter = $env:SystemDrive.TrimEnd(':')

if ($DriveLetter -ieq $SystemDriveLetter) {
    Write-Host "[FAIL] Refusing to use system drive $($DriveLetter):" -ForegroundColor Red
    exit 2
}

$DriveRoot = "$($DriveLetter):\"
$Target    = Join-Path $DriveRoot 'EIMS_USB_Auditor'

Write-Host ''
Write-Host "Selected removable drive : $($DriveLetter):" -ForegroundColor Cyan
Write-Host "Target package directory : $Target" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 3) Free-space check
# ---------------------------------------------------------------------------

try {
    $SizeBytes = (
        Get-ChildItem -LiteralPath $StagePackage -Recurse -File |
        Measure-Object -Property Length -Sum
    ).Sum

    if ($null -eq $SizeBytes) {
        $SizeBytes = 0
    }

    $SizeMB = [math]::Ceiling($SizeBytes / 1MB)

    $DriveInfo = Get-PSDrive -Name $DriveLetter -ErrorAction Stop
    $FreeBytes = $DriveInfo.Free

    $NeedBytes = $SizeBytes + 100MB
}
catch {
    Write-Host '[FAIL] Unable to calculate package/drive capacity.' -ForegroundColor Red
    Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
    exit 2
}

if ($FreeBytes -lt $NeedBytes) {
    $FreeMB = [math]::Ceiling($FreeBytes / 1MB)

    Write-Host (
        "[FAIL] Not enough free space on $($DriveLetter): " +
        "need ~$SizeMB MB (+100 MB reserve), have $FreeMB MB."
    ) -ForegroundColor Red

    exit 2
}

Write-Host (
    "[OK] Free space check passed on $($DriveLetter): " +
    "package ~$SizeMB MB."
) -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4) Writability probe
# ---------------------------------------------------------------------------

$Probe = Join-Path `
    $DriveRoot `
    ('.eims_probe_' + [guid]::NewGuid().ToString('N') + '.tmp')

try {
    [System.IO.File]::WriteAllText($Probe, 'EIMS USB writability probe')

    if (-not (Test-Path -LiteralPath $Probe -PathType Leaf)) {
        throw 'Probe file could not be verified after creation.'
    }

    Remove-Item -LiteralPath $Probe -Force -ErrorAction Stop

    Write-Host "[OK] Drive $($DriveLetter): is writable." -ForegroundColor Green
}
catch {
    # Best-effort cleanup if creation succeeded but another operation failed.
    if (Test-Path -LiteralPath $Probe) {
        Remove-Item -LiteralPath $Probe -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[FAIL] Drive $($DriveLetter): is not writable." -ForegroundColor Red
    Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
    exit 2
}

# ---------------------------------------------------------------------------
# 5) Confirm replacement of ONLY EIMS_USB_Auditor
# ---------------------------------------------------------------------------

if (Test-Path -LiteralPath $Target) {
    try {
        $ExistingFiles = @(
            Get-ChildItem `
                -LiteralPath $Target `
                -Recurse `
                -File `
                -ErrorAction SilentlyContinue
        )
    }
    catch {
        $ExistingFiles = @()
    }

    Write-Host ''
    Write-Host 'Existing EIMS USB Auditor package detected.' -ForegroundColor Yellow
    Write-Host "  Target : $Target" -ForegroundColor Yellow
    Write-Host "  Files  : $($ExistingFiles.Count)" -ForegroundColor Yellow
    Write-Host ''
    Write-Host (
        "ONLY $Target will be replaced."
    ) -ForegroundColor Yellow
    Write-Host (
        "Nothing else on $($DriveLetter): will be touched."
    ) -ForegroundColor Yellow
    Write-Host ''

    $reply = Read-Host 'Confirm replacement (type YES)'

    if ($reply -cne 'YES') {
        Write-Host ''
        Write-Host '[STOP] Replacement cancelled.' -ForegroundColor Yellow
        Write-Host '       No existing package was removed.' -ForegroundColor Yellow
        exit 1
    }

    # Defense-in-depth: ensure target still resolves under selected drive root.
    $ExpectedTarget = Join-Path $DriveRoot 'EIMS_USB_Auditor'

    if ($Target -ne $ExpectedTarget) {
        Write-Host '[FAIL] Internal target safety check failed.' -ForegroundColor Red
        Write-Host '       Refusing to remove anything.' -ForegroundColor Red
        exit 2
    }

    Write-Host '[..] Removing existing EIMS_USB_Auditor package only...'

    try {
        Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction Stop
    }
    catch {
        Write-Host '[FAIL] Could not remove the existing package.' -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
        exit 2
    }
}

# ---------------------------------------------------------------------------
# 6) Copy package
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host "[..] Copying package (~$SizeMB MB) to:" -ForegroundColor Cyan
Write-Host "     $Target" -ForegroundColor Cyan

try {
    Copy-Item `
        -LiteralPath $StagePackage `
        -Destination $Target `
        -Recurse `
        -Force `
        -ErrorAction Stop
}
catch {
    Write-Host '[FAIL] Failed to copy package to the removable drive.' -ForegroundColor Red
    Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
    exit 2
}

if (-not (Test-Path -LiteralPath $Target -PathType Container)) {
    Write-Host '[FAIL] Target package directory is missing after copy.' -ForegroundColor Red
    exit 2
}

# ---------------------------------------------------------------------------
# 7) Verify on-drive copy against MANIFEST
# ---------------------------------------------------------------------------

Write-Host '[..] Verifying the on-drive copy (manifest hashes)...'

& $VenvPython $BuilderPy --check $Target

if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[FAIL] On-drive verification failed.' -ForegroundColor Red
    Write-Host '       The copied package is NOT trustworthy.' -ForegroundColor Red
    Write-Host '       Do not use it for evidence collection.' -ForegroundColor Red
    exit 2
}

# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host '==============================================' -ForegroundColor Green
Write-Host "PACKAGE VERIFIED on $Target" -ForegroundColor Green
Write-Host '==============================================' -ForegroundColor Green
Write-Host ''
Write-Host 'Next on the target Windows machine:' -ForegroundColor Cyan
Write-Host '  1. Open EIMS_USB_Auditor on the USB drive.'
Write-Host '  2. Right-click Run-EIMS-Audit.bat.'
Write-Host '  3. Choose "Run as administrator".'
Write-Host '  4. Evidence will be written back to reports\ and logs\.'
Write-Host ''

exit 0
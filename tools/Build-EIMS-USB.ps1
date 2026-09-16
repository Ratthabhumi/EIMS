#requires -Version 5.1
<#
Build-EIMS-USB.ps1 - Package the portable USB Auditor and deploy it to a
removable drive selected by the operator. The script NEVER auto-selects a
drive, NEVER formats, and only ever replaces the single directory:

    <drive>:\EIMS_USB_Auditor\

Steps:
  1. Stage the package (tools/build_usb_package.py --build)
  2. List removable drives and require an explicit letter choice
  3. Validate free space and writability
  4. Confirm before replacing an existing <drive>:\EIMS_USB_Auditor
  5. Copy the staged package and verify the on-drive copy (manifest hashes)
#>
$ErrorActionPreference = 'Stop'

$ToolsDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = Split-Path -Parent $ToolsDir
$VenvPython = Join-Path $RepoRoot 'venv\Scripts\python.exe'
$BuilderPy  = Join-Path $ToolsDir 'build_usb_package.py'

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host '[FAIL] Repo virtualenv not found (venv\Scripts\python.exe).' -ForegroundColor Red
    exit 2
}

# ---- 1) Stage the package ---------------------------------------------------
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

# ---- 2) Removable drive selection (never automatic) --------------------------
$Drives = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 2' | Sort-Object DeviceID)
if ($Drives.Count -eq 0) {
    Write-Host '[FAIL] No removable drive found. Insert a USB drive and re-run.' -ForegroundColor Red
    exit 2
}

Write-Host ''
Write-Host 'Removable drives found:' -ForegroundColor Cyan
for ($i = 0; $i -lt $Drives.Count; $i++) {
    $d = $Drives[$i]
    $gb = '{0:N1}' -f ($d.Size / 1GB)
    Write-Host ("  [{0}] {1}  ({2} GB)" -f $i, $d.DeviceID, $gb)
}
Write-Host ''
$choice = Read-Host 'Select drive index'
if ($choice -notmatch '^\d+$' -or [int]$choice -lt 0 -or [int]$choice -ge $Drives.Count) {
    Write-Host '[FAIL] Invalid drive selection.' -ForegroundColor Red
    exit 2
}
$Drive = $Drives[[int]$choice]
$DriveLetter = $Drive.DeviceID.TrimEnd(':')
$Target = "$($DriveLetter):\EIMS_USB_Auditor"

# ---- 3) Free space + writability checks --------------------------------------
$SizeBytes = (Get-ChildItem -LiteralPath $StagePackage -Recurse -File | Measure-Object -Property Length -Sum).Sum
$SizeMB = [math]::Ceiling($SizeBytes / 1MB)
$FreeBytes = (Get-PSDrive -Name $DriveLetter).Free
$NeedBytes = $SizeBytes + 100MB
if ($FreeBytes -lt $NeedBytes) {
    $freeMB = [math]::Ceiling($FreeBytes / 1MB)
    Write-Host "[FAIL] Not enough free space on $DriveLetter: need ~$SizeMB MB (+100 MB), have ${freeMB} MB." -ForegroundColor Red
    exit 2
}

$Probe = Join-Path "$($DriveLetter):\" ('.eims_probe_' + [guid]::NewGuid().ToString('N') + '.tmp')
try {
    [System.IO.File]::WriteAllText($Probe, 'probe')
    Remove-Item -LiteralPath $Probe -Force -ErrorAction SilentlyContinue
} catch {
    Write-Host "[FAIL] Drive $DriveLetter is not writable." -ForegroundColor Red
    exit 2
}

# ---- 4) Confirm before replacing an existing package -------------------------
if (Test-Path -LiteralPath $Target) {
    $existing = @(Get-ChildItem -LiteralPath $Target -Recurse -File -ErrorAction SilentlyContinue)
    Write-Host ''
    Write-Host "An existing EIMS_USB_Auditor package is present: $Target" -ForegroundColor Yellow
    Write-Host ("It contains {0} file(s) and WILL BE replaced. Nothing else on {1}:\ is touched." -f $existing.Count, $DriveLetter) -ForegroundColor Yellow
    $reply = Read-Host 'Confirm replacement (type YES)'
    if ($reply -ne 'YES') {
        Write-Host '[STOP] Replacement cancelled. No changes were made.' -ForegroundColor Yellow
        exit 1
    }
    Remove-Item -LiteralPath $Target -Recurse -Force
}

# ---- 5) Copy + verify on the drive -------------------------------------------
Write-Host "[..] Copying package (~${SizeMB} MB) to $Target ..."
Copy-Item -LiteralPath $StagePackage -Destination $Target -Recurse -Force

Write-Host '[..] Verifying the on-drive copy (manifest hashes)...'
& $VenvPython $BuilderPy --check $Target
if ($LASTEXITCODE -ne 0) {
    Write-Host '[FAIL] On-drive verification failed. The drive copy is NOT trustworthy.' -ForegroundColor Red
    exit 2
}

Write-Host ''
Write-Host "PACKAGE VERIFIED on $Target" -ForegroundColor Green
Write-Host '  Use it: open the drive, run Run-EIMS-Audit.bat as Administrator on the target.'
Write-Host '==============================================' -ForegroundColor Cyan
exit 0
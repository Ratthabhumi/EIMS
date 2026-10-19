#requires -Version 5.1
param([switch]$DryRun,[string]$TestDestination)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Integrity.ps1')
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$payload=Join-Path $repo 'Final_CO-OP/Payload'
try {
    $manifest=Test-Package $payload
    $ledger=Get-Content -LiteralPath (Join-Path $payload 'Tools/source-ledger.json') -Raw | ConvertFrom-Json
    $head=& git -C $repo rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $head -ne $ledger.revision) { throw 'Source revision changed. Rebuild handover.' }
    $paths=(& git -C $repo ls-files) -join "`n"
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$pathsHash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($paths)))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
    if($pathsHash -ne $ledger.trackedPathsHash){throw 'Tracked source file inventory changed. Rebuild handover.'}
    foreach ($entry in $ledger.files) {
        $file=Join-Path $repo $entry.path
        if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-FileHash -LiteralPath $file).Hash.ToLowerInvariant() -ne $entry.sha256) { throw "Source changed since build: $($entry.path). Rebuild handover." }
    }
    if ($DryRun) {
        Write-Host "LOCAL PACKAGE VERIFIED: $(@($manifest.files).Count) manifest files. USB permission is NOT implied."
        if ($TestDestination) {
            $target=[IO.Path]::GetFullPath($TestDestination)
            $allowed=[IO.Path]::GetFullPath((Join-Path $repo 'Final_CO-OP/verification')).TrimEnd('\')+'\'
            if (-not $target.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)) { throw 'Dry-run copy must stay inside Final_CO-OP/verification. Never use it for USB transfer.' }
            [void](Copy-VerifiedPackage $payload $target)
            Write-Host 'LOCAL COPY VERIFIED. This is not an actual USB transfer.'
        }
        exit 0
    }
    Test-ReleasePermission $payload (Join-Path $repo 'Final_CO-OP/Release_Authorization')
    $authority=Read-Host 'Type INTERNAL to confirm you are authorized to copy this package to the KANEMATSU ELECTRONICS (THAILAND) engineering team for internal use'
    if($authority -cne 'INTERNAL'){Write-Host 'Cancelled; nothing copied.';exit 0}
    $candidates=@(Get-Volume | Where-Object {
        if (-not $_.DriveLetter) { return $false }
        $part=Get-Partition -DriveLetter $_.DriveLetter -ErrorAction SilentlyContinue
        $disk=$part | Get-Disk -ErrorAction SilentlyContinue
        $_.DriveType -eq 'Removable' -or $disk.BusType -eq 'USB'
    })
    if (-not $candidates.Count) { throw 'No USB volume detected. Insert USB and retry.' }
    for($i=0;$i -lt $candidates.Count;$i++) {
        $vol=$candidates[$i]
        Write-Host ('[{0}] {1}:  {2}  {3}  capacity {4:N1} GiB  free {5:N1} GiB' -f $i,$vol.DriveLetter,$vol.FileSystemLabel,$vol.DriveType,($vol.Size/1GB),($vol.SizeRemaining/1GB))
    }
    $answer=Read-Host 'Select drive index, or Q to cancel'
    if ($answer -eq 'Q') { Write-Host 'Cancelled; nothing copied.'; exit 0 }
    if ($answer -notmatch '^\d+$' -or [long]$answer -ge $candidates.Count) { throw 'Invalid drive selection.' }
    $vol=$candidates[[int]$answer]; $driveRoot="$($vol.DriveLetter):\"
    Assert-UsbDestination $driveRoot $repo $env:SystemDrive
    Assert-CopySpace ([long](($manifest.files | Measure-Object size -Sum).Sum)+1MB) $vol.SizeRemaining $vol.FileSystem ([long](($manifest.files | Measure-Object size -Maximum).Maximum))
    $dest=Join-Path $driveRoot 'Final_EIMS_Project'
    if (Test-Path -LiteralPath $dest) { throw "$dest already exists. Review it manually; nothing will be overwritten." }
    $confirm=Read-Host "Type COPY $($vol.DriveLetter): to confirm volume '$($vol.FileSystemLabel)' -> $dest"
    if ($confirm -cne "COPY $($vol.DriveLetter):") { Write-Host 'Cancelled; nothing copied.'; exit 0 }
    [void](Copy-VerifiedPackage $payload $dest)
    $report=Join-Path $repo ('Final_CO-OP/verification/usb-copy-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.json')
    @{status='VERIFIED';manifest=(Get-FileHash (Join-Path $dest 'MANIFEST.txt')).Hash;time=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $report
    Write-Host 'FLASH DRIVE COPY COMPLETE - VERIFIED'
    exit 0
} catch { Write-Host ('[STOP] '+$_.Exception.Message) -ForegroundColor Red; exit 2 }

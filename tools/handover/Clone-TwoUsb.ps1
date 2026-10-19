#requires -Version 5.1
param([Parameter(Mandatory=$true)][ValidateSet('USB_AUDITOR','EIMS_HANDOVER')][string]$Kind,[switch]$DryRun)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Integrity.ps1')
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
try {
    $area=Join-Path $repo 'Final_CO-OP/Two_USB'
    $receiptPath=Join-Path $area 'release-review.json'
    if($Kind -eq 'USB_AUDITOR' -and (Test-Path -LiteralPath (Join-Path $area 'USB_AUDITOR-review.json'))){
        $receiptPath=Join-Path $area 'USB_AUDITOR-review.json'
    }
    $receipt=Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    $review=@($receipt.packages | Where-Object {$_.kind -eq $Kind})
    if($review.Count -ne 1 -or $review[0].security -ne 'PASS'){throw 'Package review missing or blocked.'}
    $review=$review[0]
    $payload=Join-Path $repo $review.source
    if((Get-Content -LiteralPath (Join-Path $payload 'PACKAGE_TYPE') -Raw).Trim() -cne $Kind){throw 'Wrong package type.'}
    $manifestHash=(Get-FileHash -LiteralPath (Join-Path $payload 'MANIFEST.txt')).Hash.ToLowerInvariant()
    if($manifestHash -ne $review.manifestSha256){throw 'Package changed after review.'}
    foreach($entry in $receipt.sourceFiles){
        $path=Join-Path $repo $entry.path
        if(-not(Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $entry.sha256){throw ('Source changed; rebuild before copying: '+$entry.path)}
    }
    if($Kind -eq 'USB_AUDITOR'){
        & (Join-Path $repo 'venv/Scripts/python.exe') (Join-Path $repo 'tools/build_usb_package.py') --check $payload
        if($LASTEXITCODE -ne 0){throw 'Auditor integrity failed.'}
        $folder='EIMS_USB_Auditor'
    }else{
        [void](Test-Package $payload)
        Test-ReleasePermission $payload (Join-Path $repo 'Final_CO-OP/Release_Authorization')
        $folder='Final_EIMS_Project'
    }
    if($DryRun){Write-Host ('VERIFIED '+$Kind+'; no USB written.');exit 0}
    $candidates=@(Get-Volume | Where-Object {
        $_.DriveLetter -and ($_.DriveType -eq 'Removable' -or (Get-Partition -DriveLetter $_.DriveLetter -ErrorAction SilentlyContinue | Get-Disk -ErrorAction SilentlyContinue).BusType -eq 'USB')
    })
    for($i=0;$i -lt $candidates.Count;$i++){
        $v=$candidates[$i];Write-Host ("[$i] $($v.DriveLetter): '$($v.FileSystemLabel)' $($v.FileSystem) free $([math]::Round($v.SizeRemaining/1GB,1)) GiB")
    }
    $choice=Read-Host 'Select drive index'
    if($choice -notmatch '^\d+$' -or [long]$choice -ge $candidates.Count){throw 'Invalid selection; nothing copied.'}
    $v=$candidates[[int]$choice];$drive="$($v.DriveLetter):\"
    Assert-UsbDestination $drive $repo $env:SystemDrive
    $other=if($Kind -eq 'USB_AUDITOR'){'Final_EIMS_Project'}else{'EIMS_USB_Auditor'}
    if(Test-Path -LiteralPath (Join-Path $drive $other)){throw 'The other package is already on this USB. Select a separate USB.'}
    $dest=Join-Path $drive $folder
    if(Test-Path -LiteralPath $dest){throw 'Destination exists. Preserve/review it first; no overwrite permitted.'}
    $files=@(Get-PackageFiles $payload)
    Assert-CopySpace ([long](($files | Measure-Object Length -Sum).Sum)) $v.SizeRemaining $v.FileSystem ([long](($files | Measure-Object Length -Maximum).Maximum))
    $confirm=Read-Host "Type COPY $Kind $($v.DriveLetter): to confirm '$($v.FileSystemLabel)' -> $dest for authorized internal use"
    if($confirm -cne "COPY $Kind $($v.DriveLetter):"){Write-Host 'Cancelled.';exit 0}
    $now=Get-Volume -DriveLetter $v.DriveLetter
    if($now.UniqueId -ne $v.UniqueId -or $now.Size -ne $v.Size){throw 'USB identity changed; select again.'}
    if($Kind -eq 'EIMS_HANDOVER'){
        [void](Copy-VerifiedPackage $payload $dest)
    }else{
        New-Item -ItemType Directory -Path $dest -ErrorAction Stop | Out-Null
        & robocopy.exe $payload $dest /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
        if($LASTEXITCODE -ge 8){throw 'Copy failed; preserve the incomplete folder for inspection.'}
        $copied=@(Get-PackageFiles $dest)
        if($copied.Count -ne $files.Count){throw 'Copied file inventory differs.'}
        foreach($f in $files){
            $rel=$f.FullName.Substring($payload.Length+1)
            if((Get-FileHash -LiteralPath $f.FullName).Hash -ne (Get-FileHash -LiteralPath (Join-Path $dest $rel)).Hash){throw 'Copied file hash differs.'}
        }
    }
    @{kind=$Kind;destination=$dest;manifestSha256=$manifestHash;status='VERIFIED';utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $area ($Kind+'-copy.json'))
    Write-Host ('COPY VERIFIED: '+$dest)
    exit 0
}catch{Write-Host ('STOP: '+$_.Exception.Message);exit 2}

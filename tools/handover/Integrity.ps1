#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# A PS7 caller may pass a PSModulePath which omits Windows PowerShell modules.
# Load the built-in module by its own runtime path; do not alter policy.
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Archive') -ErrorAction Stop

function Get-PackageFiles([string]$Root) {
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
    if ((Get-Item -LiteralPath $base).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Package root cannot be a link.' }
    $all = @(Get-ChildItem -LiteralPath $base -Recurse -Force)
    if (@($all | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'Package links/reparse points are forbidden.' }
    @($all | Where-Object { -not $_.PSIsContainer })
}

function Test-Package([string]$Root) {
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
    $manifest = Get-Content -LiteralPath (Join-Path $base 'MANIFEST.txt') -Raw | ConvertFrom-Json
    if ($manifest.format -ne 'eims-handover-v1' -or @($manifest.files).Count -lt 10) { throw 'Invalid or incomplete package manifest.' }
    $seen = @{}
    foreach ($entry in $manifest.files) {
        $rel = [string]$entry.path
        if ($rel -match '(^[/\\]|:|(^|[/\\])\.\.([/\\]|$))' -or $seen.ContainsKey($rel)) { throw 'Unsafe or duplicate manifest path.' }
        $path = [IO.Path]::GetFullPath((Join-Path $base $rel))
        if (-not $path.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Manifest path escapes package.' }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing package file: $rel" }
        if ((Get-Item -LiteralPath $path).Length -ne $entry.size) { throw "Package size mismatch: $rel" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw "Package hash mismatch: $rel" }
        $seen[$rel] = $entry
    }
    $actual = @(Get-PackageFiles $base)
    if ($actual.Count -ne $seen.Count + 2) { throw 'Unexpected or missing package files.' }
    foreach ($file in $actual) {
        $rel = $file.FullName.Substring($base.Length + 1).Replace('\','/')
        if ($rel -notin @('MANIFEST.txt','SHA256SUMS.txt') -and -not $seen.ContainsKey($rel)) { throw "Unexpected package file: $rel" }
    }
    $sums = @(Get-Content -LiteralPath (Join-Path $base 'SHA256SUMS.txt'))
    if ($sums.Count -ne $seen.Count + 1) { throw 'Checksum index count mismatch.' }
    $sumSeen = @{}
    foreach ($line in $sums) {
        if ($line -notmatch '^([a-f0-9]{64})  (.+)$') { throw 'Invalid checksum index.' }
        $hash = $Matches[1]; $rel = $Matches[2]
        if ($sumSeen.ContainsKey($rel)) { throw 'Duplicate checksum entry.' }
        $sumSeen[$rel] = $true
        if ($rel -eq 'MANIFEST.txt') { $expected=(Get-FileHash -LiteralPath (Join-Path $base $rel) -Algorithm SHA256).Hash.ToLowerInvariant() }
        elseif ($seen.ContainsKey($rel)) { $expected=$seen[$rel].sha256 }
        else { throw 'Unknown checksum path.' }
        if ($hash -ne $expected) { throw 'Checksum index mismatch.' }
    }
    $required=@('SETUP.bat','Start.bat','Stop.bat','START_HERE.txt','EIMS_Handover_Guide.pdf','VERSION.txt','OWNER_HANDOVER_AUTHORIZATION.txt','Tools/release-gate.json','Tools/source-ledger.json')
    if($manifest.PSObject.Properties['mode'] -and $manifest.mode -eq 'LOCAL_DEMO_AND_FULL'){
        $required=@('Start_EIMS.bat','START_HERE.txt','EIMS_Handover_Guide.pdf','OWNER_HANDOVER_AUTHORIZATION.txt','Tools/release-gate.json','Tools/source-ledger.json','Demo_Runtime/Python/python.exe','Demo_Runtime/server.py','Demo_Runtime/supervisor.py','Demo_Runtime/index.html','Full_EIMS/SETUP.bat','Full_EIMS/Start.bat','Full_EIMS/Stop.bat','Full_EIMS/MANIFEST.txt')
    }
    foreach ($required in $required) {
        if (-not $seen.ContainsKey($required)) { throw "Required file absent: $required" }
    }
    return $manifest
}

function Test-ReleasePermission([string]$Payload, [string]$EvidenceRoot) {
    $gate = Get-Content -LiteralPath (Join-Path $Payload 'Tools/release-gate.json') -Raw | ConvertFrom-Json
    if ($gate.status -ne 'OWNER_AUTHORIZED_INTERNAL' -or $gate.securityReview -ne 'PASS') { throw 'Internal copy blocked: owner authorization or independent payload security review is incomplete.' }
    $owner=Join-Path $Payload 'OWNER_HANDOVER_AUTHORIZATION.txt'
    if ((Get-FileHash -LiteralPath $owner).Hash.ToLowerInvariant() -ne $gate.ownerAuthorizationSha256) { throw 'Owner authorization changed since review.' }
    $receipt=Get-Content -LiteralPath (Join-Path $Payload 'Tools/security-review.json') -Raw | ConvertFrom-Json
    if($receipt.status -ne 'PASS' -or -not $receipt.reviewedAt -or -not $receipt.reviewedBy){throw 'Independent security review missing.'}
    $manifest=Test-Package $Payload
    $reviewed=@{}
    foreach($entry in $receipt.files){
        if($reviewed.ContainsKey($entry.path)){throw 'Duplicate reviewed path.'}
        $reviewed[$entry.path]=$entry.sha256
    }
    foreach($entry in $manifest.files){
        if($entry.path -in @('Tools/security-review.json','Tools/release-gate.json')){continue}
        if(-not $reviewed.ContainsKey($entry.path) -or $reviewed[$entry.path] -ne $entry.sha256){throw 'Payload changed since independent security review; rescan required.'}
        $reviewed.Remove($entry.path)
    }
    if($reviewed.Count){throw 'Reviewed inventory differs from current payload.'}
    # Owner statement is recorded, not independently proven ownership/signature.
    # This permits internal source transfer, never production certification.
}

function Assert-CopySpace([long]$Bytes,[long]$Available,[string]$FileSystem,[long]$Largest) {
    if ($Available -lt ($Bytes + [Math]::Max(64MB,[long]($Bytes*0.1)))) { throw 'Insufficient free space including safety margin.' }
    if ($FileSystem -eq 'FAT32' -and $Largest -gt 4294967295) { throw 'A package file exceeds the FAT32 size limit.' }
}

function Assert-UsbDestination([string]$DriveRoot,[string]$RepoRoot,[string]$SystemRoot) {
    if ($DriveRoot -notmatch '^[A-Za-z]:\\$') { throw 'Select a drive-letter root, not a directory or network path.' }
    if ($DriveRoot.Substring(0,2) -eq $SystemRoot.TrimEnd('\') -or $DriveRoot.Substring(0,2) -eq $RepoRoot.Substring(0,2)) { throw 'Windows/source drive is forbidden.' }
}

function Copy-VerifiedPackage([string]$Source,[string]$Destination) {
    [void](Test-Package $Source)
    $target=[IO.Path]::GetFullPath($Destination).TrimEnd('\','/')
    $sourceFull=[IO.Path]::GetFullPath($Source).TrimEnd('\','/')
    if ($target -eq $sourceFull -or $target.StartsWith($sourceFull+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Destination is inside source.' }
    if (Test-Path -LiteralPath $target) { throw 'Destination exists. No overwrite, merge or rename is performed.' }
    $parent=Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'Destination parent does not exist.' }
    if ((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Destination parent cannot be a link.' }
    & robocopy.exe $sourceFull $target /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XJ /NFL /NDL /NJH /NJS /NP | Out-Null
    $copyCode=$LASTEXITCODE
    if ($copyCode -ge 8) { throw "Copy failed (robocopy $copyCode). Partial copy preserved." }
    $destManifest=Test-Package $target
    if ((Get-FileHash -LiteralPath (Join-Path $target 'MANIFEST.txt')).Hash -ne (Get-FileHash -LiteralPath (Join-Path $sourceFull 'MANIFEST.txt')).Hash) { throw 'Source/destination manifest mismatch.' }
    return $destManifest
}

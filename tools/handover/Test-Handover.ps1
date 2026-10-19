#requires -Version 5.1
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Integrity.ps1')
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$payload=Join-Path $repo 'Final_CO-OP/Payload'
$area=Join-Path $repo ('Final_CO-OP/verification/run-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $area | Out-Null
$script:checks=@()
function Check([string]$Name,[scriptblock]$Test) {
    & $Test
    $script:checks+=@{test=$Name;status='PASS'}
    Write-Host ('PASS '+$Name)
}
function Reject([scriptblock]$Test) {
    $failed=$false
    try{& $Test | Out-Null}catch{$failed=$true}
    if(-not $failed){throw 'Expected rejection did not occur.'}
}
foreach($file in Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1') {
    Check ('syntax-'+$file.Name) {
        $tokens=$null;$parseErrors=$null
        [void][Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$parseErrors)
        if($parseErrors.Count){throw ($parseErrors | Out-String)}
    }
}
Check 'payload-integrity' { [void](Test-Package $payload) }
Check 'owner-authorized-independent-review-accepted' { Test-ReleasePermission $payload '' }
Check 'missing-owner-review-blocks' { Reject {Test-ReleasePermission $area ''} }
Check 'system-drive-rejected' { Reject {Assert-UsbDestination 'C:\' 'D:\EIMS' 'C:'} }
Check 'source-drive-rejected' { Reject {Assert-UsbDestination 'D:\' 'D:\EIMS' 'C:'} }
Check 'network-destination-rejected' { Reject {Assert-UsbDestination '\\server\share' 'D:\EIMS' 'C:'} }
Check 'directory-not-volume-rejected' { Reject {Assert-UsbDestination 'E:\other' 'D:\EIMS' 'C:'} }
Check 'independent-usb-root-accepted' { Assert-UsbDestination 'E:\' 'D:\EIMS' 'C:' }
Check 'insufficient-space-rejected' { Reject {Assert-CopySpace 100MB 100MB NTFS 10MB} }
Check 'fat32-oversize-rejected' { Reject {Assert-CopySpace 8GB 20GB FAT32 5GB} }
Check 'adequate-space-accepted' { Assert-CopySpace 1MB 1GB NTFS 1MB }
$copy=Join-Path $area 'arbitrary path with spaces/Final_EIMS_Project'
New-Item -ItemType Directory -Path (Split-Path -Parent $copy) | Out-Null
Check 'copy-with-spaces-and-sha256' { [void](Copy-VerifiedPackage $payload $copy) }
Check 'missing-security-pass-blocks' {
    $gatePath=Join-Path $copy 'Tools/release-gate.json'
    $original=[IO.File]::ReadAllBytes($gatePath)
    try {
        $gate=Get-Content $gatePath -Raw | ConvertFrom-Json
        $gate.securityReview='PENDING'
        $gate | ConvertTo-Json | Set-Content $gatePath
        Reject {Test-ReleasePermission $copy ''}
    } finally {[IO.File]::WriteAllBytes($gatePath,$original)}
}
Check 'existing-destination-never-overwritten' { Reject {[void](Copy-VerifiedPackage $payload $copy)} }
Check 'copy-inside-source-rejected' { Reject {[void](Copy-VerifiedPackage $payload (Join-Path $payload 'nested-copy'))} }
Check 'corrupt-file-detected' {
    Add-Content -LiteralPath (Join-Path $copy 'START_HERE.txt') -Value 'synthetic corruption for verification'
    Reject {[void](Test-Package $copy)}
}
$copy2=Join-Path $area 'unexpected-file-copy'
Check 'unexpected-file-detected' {
    [void](Copy-VerifiedPackage $payload $copy2)
    Set-Content -LiteralPath (Join-Path $copy2 'unexpected-critical.txt') -Value 'synthetic extra file'
    Reject {[void](Test-Package $copy2)}
}
Check 'runtime-credential-generator-and-acl' {
    $tokens=$null;$parseErrors=$null
    $tree=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'Runtime.ps1'),[ref]$tokens,[ref]$parseErrors)
    foreach($name in @('New-Secret','Protect-PrivateDirectory')) {
        $function=$tree.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
        Invoke-Expression $function.Extent.Text
    }
    $first=New-Secret;$second=New-Secret
    if($first -eq $second -or $first -notmatch '^[a-f0-9]{64}$'){throw 'Credential generator failed.'}
    $privacy=Join-Path $area 'private-acl-test';New-Item -ItemType Directory -Path $privacy | Out-Null
    Protect-PrivateDirectory $privacy
    Protect-PrivateDirectory $privacy # Resume verifies the existing ACL without resetting it.
    if(-not (Get-Acl -LiteralPath $privacy).AreAccessRulesProtected){throw 'Private ACL is not protected.'}
}
$checks | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $area 'results.json')
Write-Host "$($checks.Count) handover checks passed. Actual USB and clean Windows are NOT RUN."
exit 0

#Requires -RunAsAdministrator
param([Parameter(Mandatory=$true)][string]$BackupRoot)
$ErrorActionPreference='Stop'
$targets=@('D:\EIMS_Evidence','D:\EIMS_USB_Auditor\Evidence')
$volume=Get-Volume -DriveLetter D
if ($volume.FileSystem -ne 'NTFS' -or $volume.FileSystemLabel -ne '128 GB') {throw 'Unexpected USB; nothing changed'}
if (-not [IO.Path]::IsPathRooted($BackupRoot) -or [IO.Path]::GetPathRoot($BackupRoot) -in @('D:\','E:\')) {throw 'Backup must be an absolute local path outside USB drives'}
if (Test-Path -LiteralPath $BackupRoot) {throw 'Backup directory already exists; preserve it'}
New-Item -ItemType Directory -Path $BackupRoot | Out-Null
$records=[Collections.Generic.List[object]]::new()
function Repair-Item([string]$Path,[string]$Root,[string]$Backup) {
    $full=[IO.Path]::GetFullPath($Path)
    if ($full -ne $Root -and -not $full.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase)) {throw 'Path escaped Evidence'}
    $item=Get-Item -LiteralPath $full -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {throw 'Link/reparse point rejected'}
    $old='UNREADABLE BEFORE REPAIR'
    try {$old=(Get-Acl -LiteralPath $full).Sddl} catch {}
    $kind=if($item.PSIsContainer){[Security.AccessControl.DirectorySecurity]}else{[Security.AccessControl.FileSecurity]}
    $acl=New-Object $kind.FullName
    $flags=if($item.PSIsContainer){'OICI'}else{''}
    $acl.SetSecurityDescriptorSddlForm("D:P(A;$flags;FA;;;SY)(A;$flags;FA;;;BA)(A;$flags;0x1301bf;;;AU)",[Security.AccessControl.AccessControlSections]::Access)
    try {Set-Acl -LiteralPath $full -AclObject $acl} catch {
        # Ownership is required only for this inaccessible Evidence item.
        & takeown.exe /F $full /A | Out-Null
        if($LASTEXITCODE -ne 0){throw 'Cannot take ownership of the requested Evidence item'}
        Set-Acl -LiteralPath $full -AclObject $acl
    }
    $relative=$full.Substring($Root.Length).TrimStart('\')
    $destination=if($relative){Join-Path $Backup $relative}else{$Backup}
    if($item.PSIsContainer){
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
        $records.Add([pscustomobject]@{Path=$full;OriginalSddl=$old;Type='Directory'})
        foreach($child in Get-ChildItem -LiteralPath $full -Force){Repair-Item $child.FullName $Root $Backup}
    }else{
        $before=(Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash
        Copy-Item -LiteralPath $full -Destination $destination
        if((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $before -or (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash -ne $before){throw 'Evidence hash changed'}
        $records.Add([pscustomobject]@{Path=$full;OriginalSddl=$old;Type='File';Sha256=$before})
    }
}
try {
    foreach($target in $targets){
        if(Test-Path -LiteralPath $target){Repair-Item $target $target (Join-Path $BackupRoot ([IO.Path]::GetFileName($target)))}
    }
    $records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $BackupRoot 'private-recovery-manifest.json') -Encoding utf8
    @{status='PASS';files=@($records | Where-Object Type -eq 'File').Count} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $BackupRoot 'result.json')
} catch {
    @{status='FAILED';message=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $BackupRoot 'result.json')
    throw
}

#requires -Version 5.1
param([Parameter(Mandatory=$true)][string]$PackageRoot,[switch]$Export,[switch]$Elevated,
      [Parameter(ValueFromRemainingArguments=$true)][string[]]$AuditorArgs)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security') -ErrorAction Stop
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility') -ErrorAction Stop
try {
    $PackageRoot=[IO.Path]::GetFullPath($PackageRoot)
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $admin=(New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if(-not $admin){
        if($Elevated){throw 'Elevation did not grant Administrator privileges. Scanner was not started.'}
        $literalPath="'"+$PSCommandPath.Replace("'","''")+"'"
        $literalRoot="'"+$PackageRoot.Replace("'","''")+"'"
        $command='& '+$literalPath+' -PackageRoot '+$literalRoot+' -Elevated -Export'
        if($AuditorArgs){$command+=' -AuditorArgs @('+ (($AuditorArgs | ForEach-Object {"'"+$_.Replace("'","''")+"'"}) -join ',')+')'}
        $command+='; exit $LASTEXITCODE'
        $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
        try{
            $child=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -Verb RunAs -ArgumentList @('-NoProfile','-EncodedCommand',$encoded) -Wait -PassThru
            Write-Host ('Administrator audit exit code: '+$child.ExitCode)
            exit $child.ExitCode
        }catch{Write-Host 'UAC was denied or blocked. No full audit was performed.';exit 2}
    }
    Write-Host 'Read-only: hardware, device/user identifiers, network, security, services, registry and System/Application events.'
    Write-Host 'Authorized targets only. No upload, firewall changes or recovery-key collection.'
    Write-Host '[OK] Administrator privileges'
    $root=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) ('EIMS-Auditor-Private\'+[guid]::NewGuid().ToString('N'))
    [void][IO.Directory]::CreateDirectory($root)
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true,$false)
    foreach($identity in @($sid,(New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
        $rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $root -AclObject $acl
    $env:EIMS_REPORTS_DIR=Join-Path $root 'reports'
    $env:EIMS_LOGS_DIR=Join-Path $root 'logs'
    $env:EIMS_AUTO_SYNC='false'
    Write-Host '[OK] Offline mode enabled'
    Write-Host ('[OK] Output directory: '+$root)
    Write-Host 'Output belongs to the elevated account, which may differ from the signed-in operator.'
    $arguments=@('-B',(Join-Path $PackageRoot 'main.py'),'--authorized','--export')+$AuditorArgs
    & (Join-Path $PackageRoot 'runtime\python\python.exe') @arguments
    $result=$LASTEXITCODE
    switch($result) {
        0 {Write-Host 'Report saved. Compliance checks passed.'}
        1 {Write-Host 'Report saved. Compliance findings require review.'}
        3 {Write-Host 'PARTIAL report saved. Some evidence/checks unavailable; review the report.'}
        default {Write-Host 'FAILED: review private logs; do not assume a complete report.'}
    }
    Write-Host ('Private evidence: '+$root)
    if($Elevated -and [Environment]::UserInteractive -and -not [Console]::IsInputRedirected){
        Write-Host 'Result window closes in 15 seconds. The private evidence remains saved.'
        Start-Sleep -Seconds 15
    }
    exit $result
} catch { Write-Host ('Audit could not start safely: '+$_.Exception.Message); exit 2 }

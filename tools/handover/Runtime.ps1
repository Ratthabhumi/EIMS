#requires -Version 5.1
param([ValidateSet('Setup','Start','Stop','Preflight','BackupStatus')][string]$Action='Preflight',[switch]$NoBrowser)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Integrity.ps1')
. (Join-Path $PSScriptRoot 'Prerequisites.ps1')


function Get-AppPython {
    if($script:PreparedRoot){return (Join-Path $script:PreparedRoot 'Python/python.exe')}
    return (Join-Path $install 'venv/Scripts/python.exe')
}

function Write-Status([string]$Status,[string]$Detail) {
    @{status=$Status;detail=$Detail;time=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $install 'setup-status.json')
}
function New-Secret {
    $bytes=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try {$rng.GetBytes($bytes)} finally {$rng.Dispose()}
    return ([BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()
}
function Protect-PrivateDirectory([string]$Path) {
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $existing=Get-Acl -LiteralPath $Path
    $allowedSids=@($sid.Value,'S-1-5-18')
    $rules=@($existing.Access)
    $valid=@($rules | Where-Object {
        $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -in $allowedSids -and
        $_.AccessControlType -eq 'Allow' -and -not $_.IsInherited -and
        ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl
    })
    if($existing.AreAccessRulesProtected -and $existing.GetOwner([Security.Principal.SecurityIdentifier]).Value -eq $sid.Value -and $rules.Count -eq 2 -and $valid.Count -eq 2 -and @($valid.IdentityReference | ForEach-Object {$_.Translate([Security.Principal.SecurityIdentifier]).Value} | Select-Object -Unique).Count -eq 2){return}
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($sid); $acl.SetAccessRuleProtection($true,$false)
    foreach($account in @($sid, (New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
        $rule=New-Object Security.AccessControl.FileSystemAccessRule($account,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
function Invoke-Checked([string]$Exe,[string[]]$Arguments,[string]$Label) {
    $log=Join-Path $private ($Label+'.log')
    Write-Host "Running $Label. A moving indicator and elapsed time will appear below."
    Write-Host "Private detailed log: $log" -ForegroundColor DarkGray
    if($Exe -like '*npm.cmd') {
        # Invoke Node directly: avoid .cmd quoting/working-directory ambiguity.
        $Arguments=@((Join-Path (Split-Path $Exe) 'node_modules/npm/bin/npm-cli.js'))+$Arguments
        $Exe=(Get-Command node.exe).Source
    }
    $runnerPython=Get-AppPython
    if(-not (Test-Path $runnerPython)) {
        $detected=Get-Variable HandoverPython -Scope Script -ErrorAction SilentlyContinue
        if(-not $detected -or -not $detected.Value){throw 'Setup Python is unavailable; preserve data and repair the pinned runtime.'}
        $runnerPython=$detected.Value
    }
    & $runnerPython (Join-Path $payload 'Tools/command_runner.py') 900 $log $Exe @Arguments
    if($LASTEXITCODE -ne 0){throw "$Label failed. Review the private local log; do not post it publicly."}
}
function Invoke-Compose([string[]]$Arguments,[string]$Label) {
    Invoke-Checked 'docker.exe' (@('compose','--project-name',$state.project,'--env-file',(Join-Path $private '.env'),'-f',(Join-Path $release 'Tools/compose.yaml'))+$Arguments) $Label
}
function Import-BundledImages {
    $imageList=Join-Path $payload 'Tools/container-images.json'
    if(-not (Test-Path $imageList)){return}
    $verifier=Join-Path $payload 'Tools/container_images.py'
    & (Get-AppPython) $verifier $payload
    $imageResult=$LASTEXITCODE
    if($imageResult -notin @(0,2)){throw 'Bundled image archive/catalog validation failed. No images were loaded.'}
    if($imageResult -eq 2){
        Invoke-Checked 'docker.exe' @('load','--input',(Join-Path $payload 'Tools/Container_Images.tar')) 'load-bundled-images'
        & (Get-AppPython) $verifier $payload
        if($LASTEXITCODE -ne 0){throw 'Bundled container image identity mismatch. See per-tag expected/actual digests above; no infrastructure was started.'}
    }
    Write-Host 'Container images: READY - pinned bundled images; no registry download required.'
}

function Import-PrivateEnvironment {
    foreach($line in Get-Content -LiteralPath (Join-Path $private '.env')) {
        if($line -match '^([A-Z0-9_]+)=(.*)$'){[Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process')}
    }
}
function Test-HostRequirements([switch]$OfferInstall) {
    if([Environment]::OSVersion.Platform -ne 'Win32NT' -or -not [Environment]::Is64BitOperatingSystem){throw 'Windows x64 is required.'}
    $os=Get-CimInstance Win32_OperatingSystem
    if([int]$os.BuildNumber -lt 22631){throw 'Supported target: Windows 11 x64 build 22631 or newer; confirm current Docker/IT support.'}
    if($env:PROCESSOR_ARCHITECTURE -ne 'AMD64'){throw 'Only Windows x64 is tested as a target. ARM64 is not supported by this package.'}
    $missing=@()
    $script:HandoverPython=$null
    # Do not call the Python install-manager launcher: it may offer/download
    # runtimes. Discover existing executables without starting an installer.
    if($script:PreparedRoot){$script:HandoverPython=Join-Path $payload 'Tools/BootstrapPython/python.exe'}
    if(-not $script:HandoverPython){
        foreach($candidate in @((Join-Path $env:LOCALAPPDATA 'Python/pythoncore-3.14-64/python.exe'),(Join-Path $env:LOCALAPPDATA 'Programs/Python/Python314/python.exe'))){
            if(Test-Path -LiteralPath $candidate){$script:HandoverPython=$candidate;break}
        }
    }
    if(-not $script:HandoverPython){
        $candidate=Get-Command python.exe -ErrorAction SilentlyContinue
        if($candidate -and $candidate.Source -notlike '*WindowsApps*'){$script:HandoverPython=$candidate.Source}
    }
    $node=Get-Command node.exe -ErrorAction SilentlyContinue
    if($script:PreparedRoot){$node=[pscustomobject]@{Source=(Join-Path $script:PreparedRoot 'Node/node.exe')}}
    if(-not $script:HandoverPython -or -not $node){throw 'Legacy runtime dependencies are absent. Use the prepared USB package with bundled Python/Node; no online installation was started.'}
    $pythonResult=& $script:HandoverPython -c 'import platform; print(platform.python_version())'
    if($LASTEXITCODE -ne 0 -or -not $pythonResult){throw 'The detected Python executable could not run. Ask IT to repair/select Python 3.14.6.'}
    $pythonVersion=$pythonResult.Trim()
    if($LASTEXITCODE -ne 0 -or $pythonVersion -ne '3.14.6'){throw 'This build pins Python 3.14.6. Ask IT to install/select that version; no arbitrary latest upgrade.'}
    if((-not $script:PreparedRoot) -and (& $node.Source --version).Trim() -ne 'v24.18.0'){throw 'This build pins Node.js 24.18.0. Ask IT to select that version.'}
    Ensure-EimsDocker -Payload $payload -PackageId $version.id -AllowInstall:$OfferInstall -AllowStart:($Action -ne 'Preflight')

}
function Test-OwnerProcess($record) {
    if($record.PSObject.Properties['host'] -and $record.host -ne [Environment]::MachineName){return $false}
    $p=Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)" -ErrorAction SilentlyContinue
    if(-not $p){return $false}
    if($p.CreationDate.ToUniversalTime().Ticks -ne ([DateTimeOffset]$record.created).UtcTicks -or $p.CommandLine -notlike ('*'+$install+'*')){return $false} # Stale record: never control that process; Start still checks occupied ports.
    return $true
}
function Save-ProcessRecord([string]$Name,$Process) {
    $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
    @{host=[Environment]::MachineName;pid=$Process.Id;created=$proc.CreationDate.ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $private ($Name+'.process.json'))
}
function Quote-Arg([string]$Value){return '"'+$Value.Replace('"','\"')+'"'}
function Test-PortFree([int]$Port) {
    $listener=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,$Port)
    try{$listener.Start()}catch{throw "Port $Port is occupied. No process will be killed. Stop the conflicting application or use a separately reviewed configuration."}finally{$listener.Stop()}
}
function Stop-Instance {
    $backendRecord=Join-Path $private 'backend.process.json'
    if(Test-Path -LiteralPath $backendRecord){
        $record=Get-Content $backendRecord -Raw | ConvertFrom-Json
        if(Test-OwnerProcess $record){
            Set-Content -LiteralPath (Join-Path $private 'backend.stop') -Value 'stop'
            for($i=0;$i -lt 20;$i++){if(-not (Get-Process -Id $record.pid -ErrorAction SilentlyContinue)){break};Start-Sleep -Milliseconds 500}
            if(Get-Process -Id $record.pid -ErrorAction SilentlyContinue){throw 'Backend has not drained yet. Retry Stop; no forced database shutdown was performed.'}
        }
    }
    $frontendRecord=Join-Path $private 'frontend.process.json'
    if(Test-Path -LiteralPath $frontendRecord){
        $record=Get-Content $frontendRecord -Raw | ConvertFrom-Json
        if(Test-OwnerProcess $record){Stop-Process -Id $record.pid -ErrorAction Stop}
    }
    if($portable){Stop-UsbBackup}
    Invoke-Compose @('stop','--timeout','20') 'stop-infrastructure'
    Write-Host 'STOPPED - this installation only. History, volumes and private configuration preserved.'
}
function Start-UsbBackup {
    $recordPath=Join-Path $private 'usb-backup.process.json'
    if(Test-Path $recordPath){
        $record=Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        if(Test-OwnerProcess $record){return}
    }
    $stop=Join-Path $private 'usb-backup.stop'
    if(Test-Path $stop){[IO.File]::Delete($stop)}
    $process=Start-Process -FilePath (Get-AppPython) -ArgumentList ((Quote-Arg (Join-Path $release 'Tools/usb_backup.py'))+' watch '+(Quote-Arg $install)+' '+(Quote-Arg $payload)) -WorkingDirectory $install -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $private 'usb-backup.stdout.log') -RedirectStandardError (Join-Path $private 'usb-backup.stderr.log')
    Save-ProcessRecord 'usb-backup' $process
    Write-Host 'USB auto-save runs now and every 2 minutes. Use USB_Backup_Status.bat to check the last completed recovery point.'
}
function Stop-UsbBackup {
    Set-Content -LiteralPath (Join-Path $private 'usb-backup.stop') -Value 'stop'
    $recordPath=Join-Path $private 'usb-backup.process.json'
    if(Test-Path $recordPath){
        $record=Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        for($i=0;$i -lt 120;$i++){
            if(-not (Test-OwnerProcess $record)){break}
            Start-Sleep -Milliseconds 500
        }
        if(Test-OwnerProcess $record){throw 'USB backup is still finishing. Local data is safe; wait and run Stop again.'}
    }
    try {Invoke-Checked (Get-AppPython) @((Join-Path $release 'Tools/usb_backup.py'),'checkpoint',$install,$payload) 'final-usb-checkpoint'}
    catch {Write-Host 'USB was not saved. Local data is preserved; reconnect the original USB before moving to another PC.' -ForegroundColor Yellow}
}

function Start-Instance {
    Test-HostRequirements
    Import-PrivateEnvironment
    $python=Get-AppPython
    if(-not (Test-Path -LiteralPath $python) -or (-not $script:PreparedRoot -and -not (Test-Path -LiteralPath (Join-Path $app 'clients/dashboard/.next/BUILD_ID')))){throw 'Setup/build is incomplete. Run SETUP.bat.'}
    foreach($name in @('backend','frontend')) {
        $recordFile=Join-Path $private ($name+'.process.json')
        if(Test-Path $recordFile){
            $record=Get-Content $recordFile -Raw | ConvertFrom-Json
            if(Test-OwnerProcess $record){$running[$name]=$true}
        }
    }
    if(-not $running.ContainsKey('backend')){Test-PortFree 18101}
    if(-not $running.ContainsKey('frontend')){Test-PortFree 13101}
    Invoke-Compose @('up','-d','--wait','--wait-timeout','120') 'start-infrastructure'
    if(-not $state.migrated){throw 'Database migration has not completed. Run SETUP.bat.'}
    if($version.PSObject.Properties['localPasswordless'] -and $version.localPasswordless){
        Protect-PrivateDirectory $private
        @{sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;logon=(Get-Process -Id $PID).SessionId} | ConvertTo-Json | Set-Content (Join-Path $private 'local-session-enabled.json') -Encoding UTF8
    }
    if(-not $running.ContainsKey('backend')){
        $stopMarker=Join-Path $private 'backend.stop'
        if(Test-Path $stopMarker){[IO.File]::Delete($stopMarker)}
        $process=Start-Process -FilePath $python -ArgumentList ((Quote-Arg (Join-Path $release 'Tools/run_backend.py'))+' '+(Quote-Arg $app)+' '+(Quote-Arg $private)) -WorkingDirectory $app -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $private 'backend.stdout.log') -RedirectStandardError (Join-Path $private 'backend.stderr.log')
        Save-ProcessRecord 'backend' $process
    }
    for($i=0;$i -lt 40;$i++){
        try{$health=Invoke-RestMethod 'http://127.0.0.1:18101/api/v1/health' -TimeoutSec 2;if($health.status -eq 'HEALTHY'){break}}catch{}
        if($i -eq 39){throw 'Required backend health failed. Review private logs. Optional Vector RAG is not a health requirement.'};Start-Sleep -Milliseconds 500
    }
    if(-not $running.ContainsKey('frontend')){
        $next=Join-Path $app 'clients/dashboard/node_modules/next/dist/bin/next'
        $nodeExe=$null
        if(-not $script:PreparedRoot){$nodeExe=(Get-Command node.exe).Source}
        $frontendArguments=(Quote-Arg $next)+' start -H 127.0.0.1 -p 13101'
        $frontendDirectory=Join-Path $app 'clients/dashboard'
        if($script:PreparedRoot){
            $nodeExe=Join-Path $script:PreparedRoot 'Node/node.exe'
            $frontendDirectory=Join-Path $script:PreparedRoot 'Frontend'
            $frontendArguments=Quote-Arg (Join-Path $frontendDirectory 'server.js')
            $env:PORT='13101';$env:HOSTNAME='127.0.0.1';$env:NEXT_TELEMETRY_DISABLED='1'
        }
        $process=Start-Process -FilePath $nodeExe -ArgumentList $frontendArguments -WorkingDirectory $frontendDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $private 'frontend.stdout.log') -RedirectStandardError (Join-Path $private 'frontend.stderr.log')
        Save-ProcessRecord 'frontend' $process
    }
    for($i=0;$i -lt 40;$i++){
        try{$response=Invoke-WebRequest 'http://127.0.0.1:13101/analyzer' -UseBasicParsing -TimeoutSec 2;if($response.StatusCode -eq 200){break}}catch{}
        if($i -eq 39){throw 'Frontend not ready. Review private frontend log.'};Start-Sleep -Milliseconds 500
    }
    Invoke-Checked $python @((Join-Path $release 'Tools/smoke.py'),$release) 'synthetic-smoke'
    if($version.PSObject.Properties['demoOnly'] -and $version.demoOnly){
        Invoke-Checked $python @((Join-Path $release 'Tools/seed_demo.py'),$release,$private) 'synthetic-demo-inventory'
    }
    if($portable){Start-UsbBackup}
    Write-Status 'READY' 'Secure Analyzer login, real synthetic bundle, evidence line and saved History passed; optional Vector RAG is not installed.'
    Write-Host 'EIMS services: READY'
    Write-Host 'Dashboard: READY - http://127.0.0.1:13101/analyzer'
    Write-Host 'READY - core EIMS on http://127.0.0.1:13101/analyzer. Vector RAG models and external AI are not installed/configured.'
    if(-not $NoBrowser){
        if($version.PSObject.Properties['localPasswordless'] -and $version.localPasswordless){
            & $python (Join-Path $release 'Tools/handover_session.py') launch $app $private
            if($LASTEXITCODE -ne 0){throw 'Browser session could not open. Use Start.bat from the authorized Windows session.'}
        }else{Start-Process 'http://127.0.0.1:13101/analyzer'}
    }
}

$payload=Split-Path -Parent $PSScriptRoot
$private=$null; $install=$null; $script:PreparedRoot=$null; $portable=$false
try {
    [void](Test-Package $payload)
    $version=Get-Content -LiteralPath (Join-Path $payload 'Tools/package.json') -Raw | ConvertFrom-Json
    if($version.id -notmatch '^eims-[a-f0-9]{16}$'){throw 'Invalid package identity.'}
    $portable=$version.PSObject.Properties['storageMode'] -and $version.storageMode -eq 'USB_CHECKPOINT'
    $install=Join-Path $env:LOCALAPPDATA ('EIMS-Coop/'+$version.id)
    if($portable -and $Action -ne 'Preflight'){
        $cache=Join-Path $env:LOCALAPPDATA ('EIMS-Coop/'+$version.id+'-portable')
        $bootstrap=Join-Path $payload 'Tools/BootstrapPython/python.exe'
        $install=& $bootstrap (Join-Path $payload 'Tools/usb_backup.py') select $payload $cache
        if($LASTEXITCODE -ne 0 -or -not $install){throw 'USB recovery selection failed; existing local data preserved.'}
        $install=$install.Trim()
        Write-Host 'Live data stays in the local working cache. Recovery checkpoints are saved to USB automatically.'
    }
    $private=Join-Path $install 'Private';$app=Join-Path $install 'App'
    $release=Join-Path $install ('Release-'+(Get-FileHash -LiteralPath (Join-Path $payload 'MANIFEST.txt')).Hash.Substring(0,16).ToLowerInvariant())
    if(Test-Path (Join-Path $payload 'Tools/Prepared_Runtime.zip')){
        $script:PreparedRoot=Join-Path $install ('Runtime-'+(Get-FileHash -LiteralPath (Join-Path $payload 'Tools/Prepared_Runtime.zip')).Hash.Substring(0,16).ToLowerInvariant())
    }
    $running=@{}
    if($Action -ne 'Setup'){$release=$payload}
    if($Action -eq 'Preflight'){Test-HostRequirements;Write-Host 'HOST PREFLIGHT PASS. No install, credentials, database or service changes performed.';exit 0}
    if($Action -eq 'Setup'){
        Test-HostRequirements -OfferInstall
        $drive=Get-PSDrive -Name ([IO.Path]::GetPathRoot($install).Substring(0,1))
        if($drive.Free -lt 8GB){throw 'At least 8 GiB free local disk is required for the working cache; models are excluded.'}
        Write-Host 'SETUP launched by the operator: checking pinned dependencies and isolated EIMS. Required installer/license/IT approvals still apply.'
        if((Test-Path $install) -and -not (Test-Path (Join-Path $install 'installation.json'))){throw 'Unidentified existing installation/data. Nothing will be overwritten.'}
        if(-not (Test-Path $install)){New-Item -ItemType Directory -Path $install | Out-Null;@{id=$version.id;project=('eims-coop-'+[guid]::NewGuid().ToString('N').Substring(0,12));migrated=$false} | ConvertTo-Json | Set-Content (Join-Path $install 'installation.json')}
        if(-not (Test-Path $private)){New-Item -ItemType Directory -Path $private | Out-Null}
        Protect-PrivateDirectory $private
        if($portable){
            & $script:HandoverPython (Join-Path $payload 'Tools/usb_backup.py') stage-restore $payload $private
            if($LASTEXITCODE -ne 0){throw 'USB recovery staging failed; no live database was replaced.'}
        }
        $state=Get-Content (Join-Path $install 'installation.json') -Raw | ConvertFrom-Json
        if($state.id -ne $version.id){throw 'Existing installation identity mismatch.'}
        if(-not (Test-Path $release)){[void](Copy-VerifiedPackage $payload $release)}else{[void](Test-Package $release)}
        $envPath=Join-Path $private '.env'
        if(-not (Test-Path $envPath)){
            if(Test-Path (Join-Path $private 'Data')){throw 'Existing initialized data without credentials. Do not regenerate or reset accounts.'}
            $values=@{EIMS_DB_PASSWORD=(New-Secret);EIMS_JWT_SECRET_KEY=(New-Secret);EIMS_ADMIN_TOKEN=(New-Secret);EIMS_ADMIN_PASSWORD=(New-Secret);EIMS_MINIO_ACCESS_KEY=('eims'+(New-Secret).Substring(0,20));EIMS_MINIO_SECRET_KEY=(New-Secret);EIMS_ENVIRONMENT='production';EIMS_AUTH_MODE='secure';EIMS_DB_HOST='127.0.0.1';EIMS_DB_PORT='18543';EIMS_DB_USER='eims_user';EIMS_DB_NAME='eims_handover';EIMS_REDIS_HOST='127.0.0.1';EIMS_REDIS_PORT='16379';EIMS_MINIO_ENDPOINT='127.0.0.1:19000';EIMS_CORS_ORIGINS='["http://127.0.0.1:13101"]';EIMS_LOG_LEVEL='INFO';HF_HUB_OFFLINE='1';TRANSFORMERS_OFFLINE='1';HTTP_PROXY='http://127.0.0.1:9';HTTPS_PROXY='http://127.0.0.1:9';NO_PROXY='127.0.0.1,localhost';NEXT_PUBLIC_EIMS_API_URL='http://127.0.0.1:18101';EIMS_DATA_ROOT=((Join-Path $private 'Data').Replace('\','/'))}
            $values.GetEnumerator() | Sort-Object Key | ForEach-Object {$_.Key+'='+$_.Value} | Set-Content -LiteralPath $envPath -Encoding ASCII
            @('EIMS local administrator','Username: admin','Password: '+$values.EIMS_ADMIN_PASSWORD,'Private local account only. Never send this file with the USB.') | Set-Content -LiteralPath (Join-Path $private 'LOCAL_ADMIN.txt')
            New-Item -ItemType Directory -Path (Join-Path $private 'Data') | Out-Null
        }
        if(-not (Test-Path (Join-Path $private 'Data'))){New-Item -ItemType Directory -Path (Join-Path $private 'Data') | Out-Null}
        # Codex may run inside an MSIX container. Docker runs outside that
        # container, so its bind mount must use the actual filesystem path.
        $physicalData=& $script:HandoverPython -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' (Join-Path $private 'Data')
        if($LASTEXITCODE -ne 0 -or -not $physicalData){throw 'Cannot resolve isolated Docker data path.'}
        $configuredData=@(Get-Content $envPath | Where-Object {$_ -like 'EIMS_DATA_ROOT=*'})
        $physicalLine='EIMS_DATA_ROOT='+$physicalData.Trim().Replace('\','/')
        if($configuredData.Count -ne 1){throw 'Ambiguous data configuration; preserve data and ask the owner.'}
        if($configuredData[0] -ne $physicalLine){
            if($state.migrated){throw 'Initialized Docker data path differs. No path or credentials were overwritten.'}
            (Get-Content $envPath) | ForEach-Object {if($_ -like 'EIMS_DATA_ROOT=*'){$physicalLine}else{$_}} | Set-Content $envPath -Encoding ASCII
        }
        # Dependency installation/build must retain the operator's network/IT
        # proxy. The private offline proxy is for application execution only.
        $env:NEXT_PUBLIC_EIMS_API_URL='http://127.0.0.1:18101'
        if(-not (Test-Path $app)){
            Expand-Archive -LiteralPath (Join-Path $release 'Source_Code/EIMS_Source.zip') -DestinationPath $app
        }
        if($script:PreparedRoot){
            if(-not (Test-Path $script:PreparedRoot)){
                Write-Host 'Preparing bundled runtime from USB - no pip, npm install or frontend build.'
                & $script:HandoverPython (Join-Path $payload 'Tools/prepared_runtime.py') install (Join-Path $payload 'Tools/Prepared_Runtime.zip') $script:PreparedRoot
                if($LASTEXITCODE -ne 0){throw 'Prepared runtime verification failed; partial files preserved.'}
            } else {
                & $script:HandoverPython (Join-Path $payload 'Tools/prepared_runtime.py') verify $script:PreparedRoot
                if($LASTEXITCODE -ne 0){throw 'Prepared runtime changed; no overwrite performed.'}
            }
            $python=Get-AppPython
            Write-Host 'Bundled runtime: VERIFIED'
        } else {
        $python=Get-AppPython
        if(-not (Test-Path $python)){Invoke-Checked $script:HandoverPython @('-m','venv',(Join-Path $install 'venv')) 'create-venv'}
        Invoke-Checked $python @('-m','pip','install','--timeout','30','--retries','1','--requirement',(Join-Path $release 'Tools/requirements-handover.txt')) 'install-python'
        Push-Location (Join-Path $app 'clients/dashboard')
        try{
            $lockHash=(Get-FileHash -LiteralPath 'package-lock.json').Hash
            $stampPath=Join-Path $private 'frontend-install.json'
            $stamp=$null
            if(Test-Path $stampPath){$stamp=Get-Content $stampPath -Raw | ConvertFrom-Json}
            if($stamp -and $stamp.lockHash -eq $lockHash -and (Test-Path 'node_modules/.package-lock.json')){
                Invoke-Checked (Get-Command npm.cmd).Source @('ls','--depth=0') 'npm-resume-check'
                Write-Host 'Reusing the successful locked frontend installation; no npm ci retry.'
            } else {
                Invoke-Checked (Get-Command npm.cmd).Source @('ci','--no-audit','--no-fund','--fetch-timeout=30000','--fetch-retries=0') 'npm-ci'
                @{lockHash=$lockHash;installedAt=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content $stampPath
            }
            Invoke-Checked (Get-Command node.exe).Source @('node_modules/typescript/bin/tsc','--noEmit') 'typescript'
            Invoke-Checked (Get-Command npm.cmd).Source @('run','build') 'frontend-build'
        }finally{Pop-Location}
        }
        Import-PrivateEnvironment
        $ownedCore=@(& docker.exe ps -q --filter ('label=com.docker.compose.project='+$state.project))
        if($LASTEXITCODE -ne 0){throw 'Cannot verify Docker project ownership for setup resume.'}
        foreach($port in @(18543,16379,19000,19001)){
            # First initialization must not attach to any unrelated listener.
            # Resume may already own these ports. Compose still rejects any
            # unrelated conflicting bind; it never attaches to that listener.
            if(-not $state.migrated -and -not $ownedCore.Count){Test-PortFree $port}
        }
        Import-BundledImages
        Invoke-Compose @('up','-d','--wait','--wait-timeout','120') 'setup-infrastructure'
        if($portable -and -not $state.migrated -and (Test-Path (Join-Path $private 'restore-pending.json'))){
            Invoke-Checked $python @((Join-Path $payload 'Tools/usb_backup.py'),'restore',$install,$payload) 'restore-usb-checkpoint'
            $state.migrated=$true;$state | ConvertTo-Json | Set-Content (Join-Path $install 'installation.json')
        }
        if(-not $state.migrated){
            Push-Location $app
            try{Invoke-Checked $python @('-m','alembic','upgrade','head') 'initial-migration'}finally{Pop-Location}
            $state.migrated=$true;$state | ConvertTo-Json | Set-Content (Join-Path $install 'installation.json')
        }
        Start-Instance
        Write-Host 'EIMS SETUP COMPLETE - installation and startup checks passed.' -ForegroundColor Green
        exit 0
    }
    if(-not (Test-Path (Join-Path $install 'installation.json'))){if($Action -eq 'Stop'){Write-Host 'Already stopped; installation absent.';exit 0};throw 'Run SETUP.bat first.'}
    $state=Get-Content (Join-Path $install 'installation.json') -Raw | ConvertFrom-Json
    if($state.id -ne $version.id){throw 'Installation identity mismatch.'}
    if(-not (Test-Path (Join-Path $private '.env'))){throw 'Private configuration is missing. Preserve existing data and ask the owner; do not regenerate accounts.'}
    if($Action -eq 'BackupStatus'){
        $statusFile=Join-Path $private 'usb-backup-status.json'
        if(Test-Path $statusFile){Get-Content -LiteralPath $statusFile}else{Write-Host 'No completed USB backup status yet. Local data remains on this PC.'}
        exit 0
    }
    if($portable -and $Action -eq 'Start' -and -not (Test-Path (Join-Path $install 'installation.json'))){throw 'Run SETUP.bat once on this PC to prepare the USB checkpoint.'}
    if($Action -eq 'Stop'){Stop-Instance}else{Start-Instance}
    exit 0
}catch{
    if($install -and (Test-Path -LiteralPath $install)){Write-Status 'NOT_READY' 'Setup/start requires attention; read the private local logs and handover guide.'}
    Write-Host ('[NOT READY] '+$_.Exception.Message) -ForegroundColor Red
    exit 2
}

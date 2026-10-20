#requires -Version 5.1
# Definitions only. Installing/enabling components is allowed only by SETUP.
function Invoke-EimsProbe([string]$Exe,[string[]]$Arguments,[int]$Seconds=8) {
    $info=New-Object Diagnostics.ProcessStartInfo
    $info.FileName=$Exe
    $info.Arguments=($Arguments | ForEach-Object {if($_ -match '[\s"]'){'"'+$_.Replace('"','\"')+'"'}else{$_}}) -join ' '
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true
    $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    $p=New-Object Diagnostics.Process;$p.StartInfo=$info
    try {
        [void]$p.Start()
        $out=$p.StandardOutput.ReadToEndAsync();$err=$p.StandardError.ReadToEndAsync()
        if(-not $p.WaitForExit($Seconds*1000)){$p.Kill();return @{code=124;output='';error='Probe timeout'}}
        return @{code=$p.ExitCode;output=$out.Result.Replace([string][char]0,'');error=$err.Result.Replace([string][char]0,'')}
    } finally {$p.Dispose()}
}
function Get-EimsPrerequisiteState {
    $os=Get-CimInstance Win32_OperatingSystem
    $cs=Get-CimInstance Win32_ComputerSystem
    $cpus=@(Get-CimInstance Win32_Processor)
    $feature=Get-CimInstance Win32_OptionalFeature -Filter "Name='VirtualMachinePlatform'" -ErrorAction SilentlyContinue
    $cli=$null;$desktop=$null
    foreach($root in @((Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop'),(Join-Path $env:ProgramFiles 'Docker/Docker'))){
        if(Test-Path (Join-Path $root 'Docker Desktop.exe')){$desktop=Join-Path $root 'Docker Desktop.exe';$cli=Join-Path $root 'resources/bin/docker.exe';break}
    }
    if(-not $cli -or -not (Test-Path $cli)){$cmd=Get-Command docker.exe -ErrorAction SilentlyContinue;if($cmd){$cli=$cmd.Source}else{$cli=$null}}
    $wsl=$null;$wslReady=$false
    $wslExe=Join-Path $env:SystemRoot 'System32/wsl.exe'
    if(Test-Path $wslExe){
        $version=Invoke-EimsProbe $wslExe @('--version')
        if($version.code -eq 0 -and $version.output -match '(?m)^\D*?(\d+\.\d+\.\d+(?:\.\d+)?)'){$wsl=$Matches[1];$wslReady=[version]$wsl -ge [version]'2.1.5'}
    }
    $engine='stopped';$compose=$false;$local=$false
    if($cli){
        $probe=Invoke-EimsProbe $cli @('info','--format','{{.OSType}}')
        if($probe.code -eq 0){$engine=$probe.output.Trim()}
        $c=Invoke-EimsProbe $cli @('compose','version','--short')
        $compose=$c.code -eq 0 -and $c.output.Trim() -match '^v?[2-9]\.'
        $endpoint=if($env:DOCKER_HOST){$env:DOCKER_HOST}else{
            $context=Invoke-EimsProbe $cli @('context','inspect','--format','{{.Endpoints.docker.Host}}')
            if($context.code -eq 0){$context.output.Trim()}else{''}
        }
        $local=$endpoint -like 'npipe://*'
    }
    $drive=Get-PSDrive -Name ([IO.Path]::GetPathRoot($env:LOCALAPPDATA).Substring(0,1))
    return @{windows=([int]$os.BuildNumber -ge 22631 -and [int]$os.ProductType -eq 1 -and $env:PROCESSOR_ARCHITECTURE -eq 'AMD64');
        ram=([long]$cs.TotalPhysicalMemory -ge 8GB);disk=([long]$drive.Free -ge 8GB);
        virtualization=([bool]$cs.HypervisorPresent -or @($cpus | Where-Object {$_.VirtualizationFirmwareEnabled -and $_.SecondLevelAddressTranslationExtensions}).Count -gt 0);
        hypervisor=[bool]$cs.HypervisorPresent;vmp=($feature -and [int]$feature.InstallState -eq 1);wsl=$wslReady;wslVersion=$wsl;
        cli=$cli;desktop=$desktop;engine=$engine;compose=$compose;local=$local;
        boot=([DateTimeOffset]$os.LastBootUpTime).UtcTicks.ToString()}
}
function Write-EimsPrerequisiteCheckpoint([string]$Directory,[string]$Status,[string]$Boot) {
    if(-not (Test-Path $Directory)){New-Item -ItemType Directory -Path $Directory -Force | Out-Null}
    Protect-PrivateDirectory $Directory
    $target=Join-Path $Directory 'prerequisite-status.json'
    @{status=$Status;boot=$Boot;updatedUtc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath ($target+'.tmp') -Encoding UTF8
    Move-Item -LiteralPath ($target+'.tmp') -Destination $target -Force
}
function Assert-EimsInstaller([string]$Payload,[string]$Kind) {
    $index=Get-Content -LiteralPath (Join-Path $Payload 'Installers/installers.json') -Raw | ConvertFrom-Json
    $record=$index.$Kind
    $path=[IO.Path]::GetFullPath((Join-Path $Payload $record.path))
    $boundary=[IO.Path]::GetFullPath((Join-Path $Payload 'Installers'))+[IO.Path]::DirectorySeparatorChar
    if(-not $path.StartsWith($boundary,[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $path -PathType Leaf)){throw "Missing approved offline $Kind installer; no online fallback or installation."}
    if((Get-Item -LiteralPath $path).Length -ne $record.size -or (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $record.sha256){throw "Corrupted $Kind installer; no installation."}
    $signature=Get-AuthenticodeSignature -LiteralPath $path
    if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch $record.publisherPattern){throw "Untrusted $Kind publisher/signature; ask IT to validate the vendor package. No installation."}
    return $path
}
function Invoke-EimsPrerequisiteInstaller([string]$Kind,[string]$Path) {
    Write-Host "${Kind}: INSTALLING - follow the official installer. IT authorization, license acceptance and Windows UAC remain required."
    if($Kind -eq 'Docker'){
        $p=Start-Process -FilePath $Path -ArgumentList 'install','--user','--backend=wsl-2' -WindowStyle Normal -PassThru
    } elseif($Kind -eq 'WSL') {
        $p=Start-Process -FilePath (Join-Path $env:SystemRoot 'System32/msiexec.exe') -ArgumentList ('/i "'+$Path+'" /norestart') -Verb RunAs -WindowStyle Normal -PassThru
    } else {
        Write-Host 'Windows will enable VirtualMachinePlatform. Approve UAC only if authorized by IT. No forced restart.'
        $p=Start-Process -FilePath (Join-Path $env:SystemRoot 'System32/dism.exe') -ArgumentList '/online','/enable-feature','/featurename:VirtualMachinePlatform','/all','/norestart','/LimitAccess' -Verb RunAs -WindowStyle Hidden -PassThru
    }
    $timer=[Diagnostics.Stopwatch]::StartNew()
    while(-not $p.WaitForExit(2000)){
        Write-Host ("{0}: INSTALLING | elapsed {1:mm\:ss}" -f $Kind,$timer.Elapsed)
        # Never kill a system installer mid-operation.
        if($timer.Elapsed.TotalMinutes -gt 30){throw 'Installer still running. Finish/cancel its own wizard, then rerun SETUP. No process was killed.'}
    }
    return $p.ExitCode
}
function Start-EimsDockerDesktop([string]$Path) {
    $signature=Get-AuthenticodeSignature -LiteralPath $Path
    if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(?:CN|O)=Docker Inc\b'){throw 'Docker Desktop publisher verification failed; ask IT.'}
    Write-Host 'Docker: STARTING - complete any genuine Docker license/sign-in dialog.'
    Start-Process -FilePath $Path -WindowStyle Normal | Out-Null
}
function Wait-EimsDocker([int]$TimeoutSeconds=180) {
    $timer=[Diagnostics.Stopwatch]::StartNew()
    do {
        $state=Get-EimsPrerequisiteState
        if($state.engine -eq 'linux' -and $state.compose -and $state.local){return $state}
        if($state.engine -eq 'windows'){throw 'Docker is using Windows containers. Select Linux containers in Docker Desktop, then rerun SETUP; no engine/context was changed.'}
        Write-Host ("Docker: STARTING | elapsed {0:mm\:ss}" -f $timer.Elapsed)
        if($timer.Elapsed.TotalSeconds -ge $TimeoutSeconds){throw 'Docker readiness timed out. Check its license/UAC/WSL/IT message, then rerun SETUP.'}
        Start-Sleep -Seconds 2
    } while($true)
}
function Ensure-EimsDocker([string]$Payload,[string]$PackageId,[switch]$AllowInstall,[switch]$AllowStart) {
    $state=Get-EimsPrerequisiteState
    if(-not $state.windows -or -not $state.ram -or -not $state.disk){throw 'Windows requirements: BLOCKED. Need supported Windows 11 x64 (22631+), 8 GiB RAM and 8 GiB free working space. Windows Server/ARM64 are not supported.'}
    Write-Host 'Windows requirements: PASS'
    if($state.engine -eq 'linux' -and $state.compose -and $state.local){
        Write-Host ('WSL2: '+$(if($state.wsl){'READY'}else{'NOT REQUIRED - reusing existing working Linux backend'}))
        Write-Host 'Docker: READY - existing local engine and Compose reused; no upgrade or reinstall.'
        $env:PATH=(Split-Path $state.cli)+[IO.Path]::PathSeparator+$env:PATH
        return
    }
    if($state.cli -and -not $state.local){throw 'Docker context/DOCKER_HOST is not a verified local Windows named pipe. Select an approved local Desktop context yourself; no remote project was touched.'}
    if($state.engine -eq 'windows'){throw 'Docker uses Windows containers. Select Linux containers manually; no settings were changed.'}
    if(-not $AllowStart){throw 'Docker: NOT READY. Run SETUP or start the approved Docker Desktop; read-only preflight made no changes.'}
    if(-not $state.virtualization){throw 'Windows requirements: BLOCKED - enable hardware virtualization/SLAT in BIOS/UEFI or ask IT about nested virtualization. No Windows feature was changed.'}
    $checkpoint=Join-Path $env:LOCALAPPDATA ('EIMS-Coop/Prerequisites/'+$PackageId)
    $status=Join-Path $checkpoint 'prerequisite-status.json'
    if(Test-Path $status){
        $previous=Get-Content -LiteralPath $status -Raw | ConvertFrom-Json
        if($previous.status -eq 'REBOOT_REQUIRED' -and $previous.boot -eq $state.boot){throw 'WSL2: REBOOT REQUIRED. Restart Windows when approved, then double-click SETUP again. No automatic reboot.'}
    }
    if(-not $state.vmp -or -not $state.wsl){
        if(-not $AllowInstall){throw 'WSL2: NOT READY. Run SETUP to prepare the approved offline prerequisites.'}
        # Validate the offline WSL payload before requesting Windows changes.
        $wslPath=Assert-EimsInstaller $Payload 'WSL'
        if(-not $state.vmp){
            try {$code=Invoke-EimsPrerequisiteInstaller 'VirtualMachinePlatform' ''}catch{Write-EimsPrerequisiteCheckpoint $checkpoint 'CANCELLED_OR_FAILED' $state.boot;throw}
            if($code -notin @(0,3010)){Write-EimsPrerequisiteCheckpoint $checkpoint 'CANCELLED_OR_FAILED' $state.boot;throw 'WSL2 feature activation failed/cancelled. No restart was requested.'}
            $updated=Get-EimsPrerequisiteState
            if($code -eq 3010 -or -not $updated.hypervisor -or -not $updated.vmp){
                Write-EimsPrerequisiteCheckpoint $checkpoint 'REBOOT_REQUIRED' $state.boot
                throw 'WSL2: REBOOT REQUIRED. Restart when approved, then rerun SETUP.'
            }
        }
        if(-not $state.wsl){
            try {$code=Invoke-EimsPrerequisiteInstaller 'WSL' $wslPath}catch{Write-EimsPrerequisiteCheckpoint $checkpoint 'CANCELLED_OR_FAILED' $state.boot;throw}
            if($code -in @(3010,1641)){Write-EimsPrerequisiteCheckpoint $checkpoint 'REBOOT_REQUIRED' $state.boot;throw 'WSL2: REBOOT REQUIRED. Rerun SETUP after an approved restart.'}
            if($code -ne 0){Write-EimsPrerequisiteCheckpoint $checkpoint 'CANCELLED_OR_FAILED' $state.boot;throw 'WSL installer failed/cancelled. Existing data was not changed.'}
        }
        $state=Get-EimsPrerequisiteState
        if(-not $state.wsl -or -not $state.vmp){throw 'WSL2: BLOCKED. Complete Windows component servicing/restart with IT, then rerun SETUP.'}
    }
    Write-Host 'WSL2: READY'
    if(-not $state.desktop){
        if(-not $AllowInstall){throw 'Docker Desktop is absent. Run SETUP to launch the approved offline installer.'}
        $installer=Assert-EimsInstaller $Payload 'Docker'
        try {$code=Invoke-EimsPrerequisiteInstaller 'Docker' $installer}catch{Write-EimsPrerequisiteCheckpoint $checkpoint 'CANCELLED_OR_FAILED' $state.boot;throw}
        if($code -in @(3010,1641)){Write-EimsPrerequisiteCheckpoint $checkpoint 'REBOOT_REQUIRED' $state.boot;throw 'Docker: REBOOT REQUIRED. Rerun SETUP after an approved restart.'}
        if($code -ne 0){Write-EimsPrerequisiteCheckpoint $checkpoint 'CANCELLED_OR_FAILED' $state.boot;throw 'Docker installer failed/cancelled. No EIMS installation or database reset occurred.'}
        $state=Get-EimsPrerequisiteState
        if(-not $state.desktop){throw 'Installer finished but Docker Desktop was not found. Complete its wizard/IT requirements, then rerun SETUP.'}
    }
    Start-EimsDockerDesktop $state.desktop
    $state=Wait-EimsDocker
    if($AllowInstall){Write-EimsPrerequisiteCheckpoint $checkpoint 'READY' $state.boot}
    $env:PATH=(Split-Path $state.cli)+[IO.Path]::PathSeparator+$env:PATH
    Write-Host 'Docker: READY'
}

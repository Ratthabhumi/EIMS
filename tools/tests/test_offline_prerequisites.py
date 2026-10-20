"""Mock installer/OS transitions; never install/reboot or stop a real engine."""
from pathlib import Path
import shutil
import subprocess

import pytest


MODULE = Path(__file__).parents[1] / 'handover/Prerequisites.ps1'


def run(script, shell='powershell.exe'):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip('Shell unavailable')
    module = str(MODULE.resolve()).replace("'", "''")
    result = subprocess.run([executable, '-NoProfile', '-Command',
        "$ErrorActionPreference='Stop';"
        "Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility');"
        "Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security');. '" + module + "';" + script],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout


@pytest.mark.parametrize('case', ['ready', 'stopped', 'missing', 'wsl_missing', 'vmp_reboot',
    'same_boot', 'after_reboot', 'cancel', 'uac_cancel', 'corrupt', 'bios', 'remote', 'windows'])
def test_setup_state_transitions_without_host_changes(case):
    script = r'''
$case='CASE'
$script:events=New-Object 'System.Collections.Generic.List[string]'
$script:base=@{windows=$true;ram=$true;disk=$true;virtualization=$true;hypervisor=$true;vmp=$true;wsl=$true;cli='C:\Synthetic\Docker\docker.exe';desktop='C:\Synthetic\Docker\Docker Desktop.exe';engine='linux';compose=$true;local=$true;boot='boot1'}
$script:current=$script:base.Clone()
switch($case){
 'stopped' {$script:current.engine='stopped'}
 'missing' {$script:current.engine='stopped';$script:current.cli=$null;$script:current.desktop=$null}
 'wsl_missing' {$script:current.engine='stopped';$script:current.wsl=$false;$script:current.desktop=$null;$script:current.cli=$null}
 'vmp_reboot' {$script:current.engine='stopped';$script:current.vmp=$false;$script:current.wsl=$false}
 'same_boot' {$script:current.engine='stopped'}
 'after_reboot' {$script:current.engine='stopped';$script:current.boot='boot2'}
 'cancel' {$script:current.engine='stopped';$script:current.desktop=$null}
 'uac_cancel' {$script:current.engine='stopped';$script:current.wsl=$false}
 'corrupt' {$script:current.engine='stopped';$script:current.desktop=$null}
 'bios' {$script:current.engine='stopped';$script:current.virtualization=$false}
 'remote' {$script:current.local=$false}
 'windows' {$script:current.engine='windows'}
}
function Get-EimsPrerequisiteState {return $script:current.Clone()}
function Assert-EimsInstaller($Payload,$Kind){if($case -eq 'corrupt'){throw 'Corrupt installer'};return 'C:\Synthetic\installer'}
function Invoke-EimsPrerequisiteInstaller($Kind,$Path){
 $script:events.Add('install-'+$Kind)
 if($case -eq 'cancel'){return 1602}
 if($case -eq 'uac_cancel'){throw 'UAC cancellation'}
 if($case -eq 'vmp_reboot'){return 3010}
 if($Kind -eq 'WSL'){$script:current.wsl=$true}
 if($Kind -eq 'Docker'){$script:current.desktop='C:\Synthetic\Docker Desktop.exe';$script:current.cli='C:\Synthetic\Docker\docker.exe'}
 return 0
}
function Start-EimsDockerDesktop($Path){$script:events.Add('start')}
function Wait-EimsDocker {$script:events.Add('wait');return $script:base.Clone()}
function Write-EimsPrerequisiteCheckpoint($Directory,$Status,$Boot){$script:events.Add('checkpoint-'+$Status)}
function Test-Path($Path){return $case -in @('same_boot','after_reboot')}
function Get-Content {return '{"status":"REBOOT_REQUIRED","boot":"boot1"}'}
$failed=$false
try{Ensure-EimsDocker 'C:\Synthetic\Payload' 'eims-0000000000000000' -AllowInstall -AllowStart}catch{$failed=$true}
$expected=$case -in @('vmp_reboot','same_boot','cancel','uac_cancel','corrupt','bios','remote','windows')
if($failed -ne $expected){throw 'Unexpected transition result'}
if($case -eq 'ready' -and $script:events.Count -ne 0){throw 'Working Docker changed'}
if($case -in @('same_boot','corrupt','bios','remote','windows') -and $script:events.Count -ne 0){throw 'Blocked host changed'}
if($case -eq 'stopped' -and ($script:events -contains 'install-Docker')){throw 'Existing installation replaced'}
if($case -eq 'missing' -and -not ($script:events -contains 'install-Docker')){throw 'Offline installer not selected'}
if($case -eq 'wsl_missing' -and -not ($script:events -contains 'install-WSL')){throw 'WSL skipped'}
if($case -eq 'after_reboot' -and ($script:events -contains 'install-Docker')){throw 'Completed installer repeated'}
if($case -eq 'vmp_reboot' -and -not ($script:events -contains 'checkpoint-REBOOT_REQUIRED')){throw 'Resume checkpoint missing'}
if($case -in @('cancel','uac_cancel') -and -not ($script:events -contains 'checkpoint-CANCELLED_OR_FAILED')){throw 'Cancellation not recorded'}
Write-Output 'PASS'
'''.replace('CASE', case)
    assert 'PASS' in run(script)


def test_engine_wait_is_bounded():
    assert 'PASS' in run(r'''
function Get-EimsPrerequisiteState {return @{engine='stopped';compose=$true;local=$true}}
$failed=$false;try{Wait-EimsDocker -TimeoutSeconds 0}catch{$failed=$true}
if(-not $failed){throw 'Unbounded wait'};Write-Output 'PASS'
''')


def test_native_probe_keeps_flags_and_quotes_command_text():
    assert 'ARG_OK' in run(r'''
$probe=Invoke-EimsProbe (Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe') @('-NoProfile','-Command',"Write-Output 'ARG_OK'")
if($probe.code -ne 0 -or $probe.output.Trim() -ne 'ARG_OK'){throw 'Native argument forwarding failed'}
Write-Output 'ARG_OK'
''')


def test_docker_install_flags_preserve_vendor_acceptance():
    assert 'PASS' in run(r'''
function Start-Process {
 param($FilePath,$ArgumentList,$WindowStyle,[switch]$PassThru)
 if($ArgumentList -contains '--accept-license' -or $ArgumentList -contains '--quiet'){throw 'Terms bypass'}
 if(-not ($ArgumentList -contains '--user') -or -not ($ArgumentList -contains '--backend=wsl-2')){throw 'Wrong mode'}
 $p=[pscustomobject]@{ExitCode=0};$p|Add-Member ScriptMethod WaitForExit {param($ms) return $true};return $p
}
if((Invoke-EimsPrerequisiteInstaller 'Docker' 'C:\Synthetic\installer.exe') -ne 0){throw 'Installer failure'}
Write-Output 'PASS'
''')


@pytest.mark.parametrize('kind', ['missing', 'corrupt', 'unsigned'])
def test_offline_payload_rejected_before_execution(tmp_path, kind):
    import hashlib
    import json
    folder = tmp_path / 'Installers/Docker'
    folder.mkdir(parents=True)
    binary = folder / 'installer.exe'
    binary.write_bytes(b'synthetic')
    record = {'Docker': {'path': 'Installers/Docker/installer.exe', 'size': 9,
        'sha256': hashlib.sha256(b'synthetic').hexdigest(), 'publisherPattern': 'Docker Inc'}}
    (tmp_path / 'Installers/installers.json').write_text(json.dumps(record))
    if kind == 'missing':
        binary.unlink()
    elif kind == 'corrupt':
        binary.write_bytes(b'corrupt')
    path = str(tmp_path).replace("'", "''")
    message = {'missing':'Missing approved', 'corrupt':'Corrupted', 'unsigned':'Untrusted'}[kind]
    assert 'PASS' in run("function Get-AuthenticodeSignature {return @{Status='NotSigned'}};"
        "$failure='';try{Assert-EimsInstaller '" + path + "' 'Docker'}catch{$failure=$_.Exception.Message};"
        "if($failure -notlike '" + message + "*'){throw ('Wrong rejection: '+$failure)};Write-Output 'PASS'")

"""Exercise the actual PS function without starting/stopping a real process."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('shell', ['powershell.exe', 'pwsh.exe'])
def test_identity_compares_instants_and_rejects_reused_pid(shell):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip('Shell not installed')
    source = Path(__file__).parents[1] / 'handover/Runtime.ps1'
    script = r'''
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($args[0],[ref]$tokens,[ref]$errors)
if($errors){throw 'Parse failed'}
$fn=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-OwnerProcess'},$true)
. ([scriptblock]::Create($fn.Extent.Text))
$install='C:\Synthetic\EIMS'
function Get-CimInstance {return [pscustomobject]@{CreationDate=[datetime]'2026-10-20T00:00:00.1234560Z';CommandLine='C:\Synthetic\EIMS\server'}}
$record='{"pid":123,"created":"2026-10-20T00:00:00.123456Z"}' | ConvertFrom-Json
if(-not (Test-OwnerProcess $record)){throw 'Matching instant rejected'}
$record.created='2026-10-20T00:00:01.123456Z'
if(Test-OwnerProcess $record){throw 'Reused PID accepted'}
$record.created='2026-10-20T00:00:00.123456Z'
function Get-CimInstance {return [pscustomobject]@{CreationDate=[datetime]'2026-10-20T00:00:00.1234560Z';CommandLine='C:\Unrelated\server'}}
if(Test-OwnerProcess $record){throw 'Unrelated command accepted'}
Write-Output 'Identity comparison PASS'
'''
    # -Command does not bind trailing argv consistently across the two shells.
    quoted = str(source.resolve()).replace("'", "''")
    script = script.replace('$args[0]', "'" + quoted + "'")
    result = subprocess.run([executable, '-NoProfile', '-Command', script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'Identity comparison PASS' in result.stdout

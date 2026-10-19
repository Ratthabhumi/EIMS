import subprocess
import sys
from pathlib import Path

RUNNER=Path(__file__).resolve().parents[1]/'handover/command_runner.py'


def test_setup_prints_live_running_and_done_without_disclosing_child_output(tmp_path):
    log=tmp_path/'npm-ci.log'
    command=[sys.executable,str(RUNNER),'10',str(log),sys.executable,'-c',
             "import time;print('SYNTHETIC_PRIVATE_VALUE',flush=True);time.sleep(2.3)"]
    with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as proc:
        first=proc.stdout.readline()
        assert 'RUNNING' in first and proc.poll() is None
        out,err=proc.communicate(timeout=15)
    assert proc.returncode==0 and 'DONE npm-ci' in out
    assert 'SYNTHETIC_PRIVATE_VALUE' not in first+out+err
    assert 'SYNTHETIC_PRIVATE_VALUE' in log.read_text()


def test_failed_step_never_displays_done(tmp_path):
    result=subprocess.run([sys.executable,str(RUNNER),'10',str(tmp_path/'install-python.log'),
                           sys.executable,'-c','raise SystemExit(7)'],capture_output=True,text=True,timeout=15)
    assert result.returncode==7 and 'FAILED install-python' in result.stdout
    assert 'DONE' not in result.stdout


def test_timeout_keeps_private_log_and_stops_only_its_own_child(tmp_path):
    result=subprocess.run([sys.executable,str(RUNNER),'1',str(tmp_path/'bounded.log'),
                           sys.executable,'-c','import time;time.sleep(30)'],capture_output=True,text=True,timeout=15)
    assert result.returncode==124 and 'FAILED bounded' in result.stdout
    assert 'SETUP COMMAND TIMEOUT' in (tmp_path/'bounded.log').read_text()

"""Bound only the child command launched by this setup; retain private logs."""
import subprocess
import sys

seconds = int(sys.argv[1])
with open(sys.argv[2], 'wb') as log:
    child = subprocess.Popen(sys.argv[3:], stdout=log, stderr=subprocess.STDOUT)
    try:
        result = child.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        # The handle is still alive: PID cannot have been recycled. Kill only
        # this setup-owned command tree, never other Node/Python processes.
        if child.poll() is None:
            subprocess.run(['taskkill.exe', '/PID', str(child.pid), '/T', '/F'],
                           stdout=log, stderr=subprocess.STDOUT, timeout=30)
        log.write(b'\nSETUP COMMAND TIMEOUT: review this private log before retrying.\n')
        result = 124
sys.exit(result)

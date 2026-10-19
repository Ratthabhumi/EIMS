"""Bound only the child command launched by this setup; retain private logs."""
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def run(seconds, log_path, command):
    label = re.sub(r'[^a-zA-Z0-9_-]', '_', Path(log_path).stem)
    started = time.monotonic()
    interactive = bool(getattr(sys.stdout, 'isatty', lambda:False)())
    tick = 0
    with open(log_path, 'wb') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        while True:
            elapsed = time.monotonic() - started
            if child.poll() is not None:
                result = child.returncode
                break
            if elapsed >= seconds:
                # The exact child handle is alive: never kill unrelated processes.
                if child.poll() is None:
                    subprocess.run(['taskkill.exe','/PID',str(child.pid),'/T','/F'],
                                   stdout=log,stderr=subprocess.STDOUT,timeout=30)
                log.write(b'\nSETUP COMMAND TIMEOUT: review this private log before retrying.\n')
                result = 124
                break
            position = tick % 13
            animation = '[' + ' ' * position + '====' + ' ' * (12-position) + ']'
            minutes,secs = divmod(int(elapsed),60)
            size = os.fstat(log.fileno()).st_size // 1024
            print(('\r' if interactive else '')+f'{animation} {label} | elapsed {minutes:02}:{secs:02} | private log {size} KiB | RUNNING',
                  end='' if interactive else '\n',flush=True)
            tick += 1
            try:
                result = child.wait(timeout=min(2.0,max(.01,seconds-elapsed)))
                break
            except subprocess.TimeoutExpired:
                continue
    elapsed = time.monotonic()-started
    print(('\r' if interactive else '')+f'{"DONE" if result==0 else "FAILED"} {label} | elapsed {elapsed:.1f}s | exit {result}'+' '*25,flush=True)
    return result


if __name__ == '__main__':
    sys.exit(run(int(sys.argv[1]),sys.argv[2],sys.argv[3:]))

"""Owned local server with a graceful stop marker; no operational .env reuse."""
import os
import json
import re
from pathlib import Path
import sys
import threading
import time
sys.dont_write_bytecode = True  # The reviewed Tools directory must remain immutable.

# Validate the supplied installation boundary before resolving MSIX paths.
# Windows may redirect App but leave the ACL-protected Private directory on
# the host. Their resolved parents can legitimately differ in that case.
logical_app = Path(os.path.abspath(sys.argv[1]))
logical_private = Path(os.path.abspath(sys.argv[2]))
if logical_app.parent != logical_private.parent or logical_app.name != 'App' or logical_private.name != 'Private':
    raise SystemExit('Invalid isolated installation identity')
identity = json.loads((logical_app.parent / 'installation.json').read_text(encoding='utf-8-sig'))
if not re.fullmatch(r'eims-[a-f0-9]{16}', identity.get('id', '')) or not re.fullmatch(r'eims-coop-[a-f0-9]{12}', identity.get('project', '')):
    raise SystemExit('Invalid isolated installation record')
app = logical_app.resolve()
private = logical_private.resolve()
if not (private / '.env').is_file() or not (app / 'backend/main.py').is_file():
    raise SystemExit('Incomplete isolated installation')
os.chdir(app)
sys.path.insert(0, str(app))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import uvicorn

from backend.main import app as application
if (private / 'local-session-enabled.json').is_file():
    from handover_session import attach
    attach(application, app, private)
server = uvicorn.Server(uvicorn.Config(application, host='127.0.0.1', port=18101, log_level='warning'))

def watch_stop():
    while not server.should_exit:
        if (private / 'backend.stop').is_file():
            server.should_exit = True
            return
        time.sleep(0.25)

threading.Thread(target=watch_stop, daemon=True).start()
server.run()

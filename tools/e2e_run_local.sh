#!/usr/bin/env bash
# Rebuild the DISPOSABLE e2e database, start the backend on it, run the end-to-end driver, then (optionally) hard-restart
# the backend and run the recovery phase. Never touches port 5432 / the operational database.
#   tools/e2e_run_local.sh [--restart]
set -u
cd "$(dirname "$0")/.."
CONTAINER="${E2E_PG_CONTAINER:-eims-knowledge-b-pg-20261119}"
export EIMS_DB_HOST=127.0.0.1 EIMS_DB_PORT=56470 EIMS_DB_USER=eims_incident_test EIMS_DB_PASSWORD=eims_synthetic_only
export EIMS_DB_NAME=eims_e2e_test EIMS_DEMO_SOFT_DEPS=1
E2E_PORT="${E2E_PORT:-8032}"   # never 8000/8021: another backend may own them
LOG="${TEMP:-/tmp}/e2e_backend.log"

stop_backend() {
  PID=$(powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort $E2E_PORT -State Listen -ErrorAction SilentlyContinue).OwningProcess" | tr -d '\r')
  if [ -n "$PID" ]; then
    powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId=$PID').CommandLine" | grep -q "uvicorn backend.main:app" \
      && powershell -NoProfile -Command "Stop-Process -Id $PID -Force"
    sleep 2
  fi
}
start_backend() {
  (nohup ./venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port $E2E_PORT > "$LOG" 2>&1 &)
  for _ in $(seq 1 40); do curl -s -m 3 -o /dev/null http://127.0.0.1:$E2E_PORT/api/v1/health && return 0; sleep 2; done
  echo "backend did not start"; return 1
}

stop_backend
docker exec "$CONTAINER" psql -U eims_test -d eims_integration_test \
  -c "DROP DATABASE IF EXISTS eims_e2e_test WITH (FORCE)" -c "CREATE DATABASE eims_e2e_test OWNER eims_incident_test" >/dev/null
for ext in vector pg_trgm; do docker exec "$CONTAINER" psql -U eims_test -d eims_e2e_test -c "CREATE EXTENSION IF NOT EXISTS $ext" >/dev/null; done
./venv/Scripts/python.exe -m alembic upgrade head 2>&1 | tail -1
rm -f docs/acceptance/evidence/e2e_*
start_backend || exit 1
PYTHONPATH=. PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/e2e_incident_intelligence.py --base http://127.0.0.1:$E2E_PORT --phase main || echo "main phase had failures"
if [ "${1:-}" = "--restart" ]; then
  echo "---- hard restart of the backend process ----"
  stop_backend
  start_backend || exit 1
  PYTHONPATH=. PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/e2e_incident_intelligence.py --base http://127.0.0.1:$E2E_PORT --phase after-restart || echo "recovery phase had failures"
fi

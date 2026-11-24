#!/usr/bin/env bash
# Isolated, reproducible CURRENT backend for browser acceptance (Cursor). Never touches the operational database
# (port 5432) or any process on 8000/8021. Safe to re-run: it only stops a uvicorn it started itself on ISO_PORT.
#
#   tools/run_isolated_backend.sh start    # rebuild disposable DB from empty via the REAL Alembic chain, start backend
#   tools/run_isolated_backend.sh status   # prove WHICH backend answers on ISO_PORT (identity + migration head)
#   tools/run_isolated_backend.sh stop
#
# Frontend: EIMS_BACKEND_URL=http://127.0.0.1:8031 (and NEXT_PUBLIC_EIMS_API_URL for the same value).
set -u
cd "$(dirname "$0")/.."
CONTAINER="${E2E_PG_CONTAINER:-eims-knowledge-b-pg-20261119}"   # disposable PostgreSQL container, host port 56470
ISO_PORT="${ISO_PORT:-8031}"
ISO_DB="${ISO_DB:-eims_cursor_accept}"
export EIMS_DB_HOST=127.0.0.1 EIMS_DB_PORT=56470 EIMS_DB_USER=eims_incident_test EIMS_DB_PASSWORD=eims_synthetic_only
export EIMS_DB_NAME="$ISO_DB" EIMS_DEMO_SOFT_DEPS=1
case "$ISO_DB" in eims_*_accept|eims_*_acceptance) ;; *) echo "refusing: ISO_DB must match eims_*_accept (got $ISO_DB)"; exit 2;; esac
LOG="${TEMP:-/tmp}/isolated_backend_${ISO_PORT}.log"
PIDFILE="${TEMP:-/tmp}/isolated_backend_${ISO_PORT}.pid"

stop_backend() {
  if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId=$PID').CommandLine" | grep -q "backend.main:app --host 127.0.0.1 --port $ISO_PORT" \
      && powershell -NoProfile -Command "Stop-Process -Id $PID -Force"
    rm -f "$PIDFILE"; sleep 2
  fi
}

case "${1:-status}" in
  stop) stop_backend; echo "stopped (only a process this script started)";;
  start)
    stop_backend
    docker exec "$CONTAINER" psql -U eims_test -d eims_integration_test \
      -c "DROP DATABASE IF EXISTS $ISO_DB WITH (FORCE)" -c "CREATE DATABASE $ISO_DB OWNER eims_incident_test" >/dev/null || exit 1
    for ext in vector pg_trgm; do docker exec "$CONTAINER" psql -U eims_test -d "$ISO_DB" -c "CREATE EXTENSION IF NOT EXISTS $ext" >/dev/null; done
    ./venv/Scripts/python.exe -m alembic upgrade head 2>&1 | tail -1
    (nohup ./venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port "$ISO_PORT" > "$LOG" 2>&1 & echo $! > "$PIDFILE")
    for _ in $(seq 1 40); do curl -s -m 3 -o /dev/null "http://127.0.0.1:$ISO_PORT/api/v1/health" && break; sleep 2; done
    PYTHONPATH=. ./venv/Scripts/python.exe tools/verify_backend_identity.py --port "$ISO_PORT";;
  status) PYTHONPATH=. ./venv/Scripts/python.exe tools/verify_backend_identity.py --port "$ISO_PORT";;
  *) echo "usage: $0 start|status|stop"; exit 2;;
esac

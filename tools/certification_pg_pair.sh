#!/usr/bin/env bash
# Provision / tear down a DISPOSABLE PostgreSQL 16 primary + streaming standby for certification class-D evidence.
# Usage: tools/certification_pg_pair.sh up|down      (password is read from / written to $CERT_PG_PWFILE)
# Containers, volume and network are created by this script only and carry the label eims.purpose=synthetic-cert-test.
# Never point certification tooling at any other database. Ports are bound to 127.0.0.1 only.
set -euo pipefail
IMAGE="${CERT_PG_IMAGE:-pgvector/pgvector:pg16}"
PWFILE="${CERT_PG_PWFILE:?set CERT_PG_PWFILE to a scratch file path for the generated password}"
NET=eims-cert-net; PRI=eims-cert-pg-primary; STB=eims-cert-pg-standby; VOL=eims-cert-standby-data
q() { docker exec -e PGPASSWORD="$PW" "$PRI" psql -U postgres -d eims_cert_state -Atc "$1"; }

down() {
  docker rm -f "$STB" "$PRI" >/dev/null 2>&1 || true
  docker volume rm "$VOL" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}

up() {
  down
  [ -s "$PWFILE" ] || python -c "import secrets;print(secrets.token_hex(16))" > "$PWFILE"
  PW=$(cat "$PWFILE")
  docker network create "$NET" >/dev/null
  # max_slot_wal_keep_size is deliberately NOT passed with -c: a command-line value would override ALTER SYSTEM.
  docker run -d --name "$PRI" --network "$NET" --label eims.purpose=synthetic-cert-test -e POSTGRES_PASSWORD="$PW" -e POSTGRES_DB=eims_cert_state \
    -p 127.0.0.1:56480:5432 "$IMAGE" -c cluster_name=eims-cert-disposable -c wal_level=replica -c max_wal_senders=5 -c max_replication_slots=8 \
    -c max_wal_size=32MB -c min_wal_size=32MB -c wal_keep_size=0 -c hot_standby=on -c listen_addresses='*' >/dev/null
  for _ in $(seq 1 40); do docker exec "$PRI" pg_isready -U postgres -q && break; sleep 1; done
  docker exec "$PRI" bash -c 'echo "host replication all all scram-sha-256" >> $PGDATA/pg_hba.conf'
  q "alter system set max_slot_wal_keep_size = '64MB'" >/dev/null
  q "select pg_reload_conf()" >/dev/null
  q "select pg_create_physical_replication_slot('cert_standby_slot', true)" >/dev/null
  docker volume create "$VOL" >/dev/null
  docker run --rm --network "$NET" -e PGPASSWORD="$PW" -v "$VOL":/var/lib/postgresql/data "$IMAGE" bash -c \
    "chown postgres:postgres /var/lib/postgresql/data && chmod 700 /var/lib/postgresql/data && gosu postgres pg_basebackup -h $PRI -U postgres -D /var/lib/postgresql/data -R -X stream -S cert_standby_slot" >/dev/null
  docker run -d --name "$STB" --network "$NET" --label eims.purpose=synthetic-cert-test -e POSTGRES_PASSWORD="$PW" -v "$VOL":/var/lib/postgresql/data \
    -p 127.0.0.1:56481:5432 "$IMAGE" -c cluster_name=eims-cert-disposable-standby -c hot_standby=on >/dev/null
  for _ in $(seq 1 60); do docker exec "$STB" pg_isready -U postgres -q && break; sleep 1; done
  q "select 'server_version=' || current_setting('server_version') || ' max_slot_wal_keep_size=' || current_setting('max_slot_wal_keep_size')"
  q "select 'standby streaming: ' || count(*) from pg_stat_replication where state='streaming'"
}

case "${1:-}" in up) up ;; down) down ;; *) echo "usage: $0 up|down" >&2; exit 2 ;; esac

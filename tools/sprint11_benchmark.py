"""
EIMS Sprint 11 Benchmark — p50/p95/p99 latency evidence for Search, Timeline, and Audit endpoints.

SAFETY REQUIREMENT
==================
This benchmark requires a DEDICATED benchmark database.
It MUST NOT be run against the normal EIMS application database (eims_registry).

The benchmark performs TRUNCATE operations on core application tables.
Running it against eims_registry will DESTROY application data.

This is a confirmed engineering incident: the original script was run
against eims_registry on 2026-09-10, permanently destroying the application
dataset in infrastructure_assets, audit_logs, telemetry_metrics, and
windows_event_logs tables.

SAFE USAGE
==========
1. Create a separate benchmark database, e.g.:
       createdb -U eims_user eims_benchmark
2. Run migrations against it:
       DATABASE_URL=postgresql+asyncpg://eims_user:...@localhost/eims_benchmark alembic upgrade head
3. Run with the benchmark DB URL:
       EIMS_BENCHMARK_DATABASE_URL=postgresql+asyncpg://eims_user:...@localhost/eims_benchmark python tools/sprint11_benchmark.py

The script will REFUSE to run if:
- EIMS_BENCHMARK_DATABASE_URL is not set
- The target database name ends with 'registry' (production DB guard)
- EIMS_ALLOW_BENCHMARK_ON_REGISTRY is not explicitly set to 'yes-i-know-what-i-am-doing'

Usage:
    # Set benchmark DB URL (separate from production)
    set EIMS_BENCHMARK_DATABASE_URL=postgresql+asyncpg://eims_user:eims_pass@localhost:5432/eims_benchmark
    set PYTHONPATH=.
    python tools/sprint11_benchmark.py
"""
import asyncio
import json
import os
import statistics
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.domain.asset_registry.models import InfrastructureAsset, AuditLog
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog

ITERATIONS = 30
WARMUP = 3
ASSET_COUNT = 10_000
AUDIT_COUNT = 50_000
METRIC_COUNT = 20_000
WINLOG_COUNT = 20_000

# ============================================================
# SAFETY GUARD — must be checked before any DB operation
# ============================================================

_SAFE_DB_NAME_SUFFIXES_BLOCKLIST = ["registry"]
_OVERRIDE_ENV_VAR = "EIMS_ALLOW_BENCHMARK_ON_REGISTRY"
_BENCHMARK_DB_ENV_VAR = "EIMS_BENCHMARK_DATABASE_URL"


def _assert_benchmark_safety(db_url: str) -> None:
    """
    Refuses to run the benchmark against a database that appears to be the
    production/application database.

    Raises RuntimeError if the target is unsafe.
    """
    # Require explicit benchmark DB URL
    if not db_url:
        raise RuntimeError(
            "\n"
            "╔══════════════════════════════════════════════════════════════════╗\n"
            "║  BENCHMARK SAFETY GUARD — EXECUTION REFUSED                     ║\n"
            "╠══════════════════════════════════════════════════════════════════╣\n"
            "║  EIMS_BENCHMARK_DATABASE_URL is not set.                        ║\n"
            "║                                                                  ║\n"
            "║  This benchmark performs TRUNCATE on core application tables.   ║\n"
            "║  It MUST target a dedicated benchmark database, not eims_registry.║\n"
            "║                                                                  ║\n"
            "║  Set EIMS_BENCHMARK_DATABASE_URL to a dedicated benchmark DB:   ║\n"
            "║    postgresql+asyncpg://user:pass@host/eims_benchmark            ║\n"
            "╚══════════════════════════════════════════════════════════════════╝\n"
        )

    # Extract DB name from URL
    db_name = db_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0].lower()

    # Block known production DB name patterns unless override is set
    override = os.environ.get(_OVERRIDE_ENV_VAR, "").strip()
    for blocked_suffix in _SAFE_DB_NAME_SUFFIXES_BLOCKLIST:
        if db_name.endswith(blocked_suffix):
            if override != "yes-i-know-what-i-am-doing":
                raise RuntimeError(
                    f"\n"
                    f"╔══════════════════════════════════════════════════════════════════╗\n"
                    f"║  BENCHMARK SAFETY GUARD — EXECUTION REFUSED                     ║\n"
                    f"╠══════════════════════════════════════════════════════════════════╣\n"
                    f"║  Target database '{db_name}' looks like a production database.  ║\n"
                    f"║  Databases ending with 'registry' are blocked by default.       ║\n"
                    f"║                                                                  ║\n"
                    f"║  This benchmark TRUNCATES: infrastructure_assets, audit_logs,   ║\n"
                    f"║  telemetry_metrics, windows_event_logs.                         ║\n"
                    f"║                                                                  ║\n"
                    f"║  Data loss incident: 2026-09-10 — original data permanently     ║\n"
                    f"║  destroyed when run against eims_registry without this guard.   ║\n"
                    f"║                                                                  ║\n"
                    f"║  To proceed anyway (NOT RECOMMENDED):                           ║\n"
                    f"║    set {_OVERRIDE_ENV_VAR}=yes-i-know-what-i-am-doing          ║\n"
                    f"╚══════════════════════════════════════════════════════════════════╝\n"
                )
            else:
                print(
                    f"[BENCHMARK WARN] Override accepted — targeting '{db_name}' despite safety guard.\n"
                    f"                 This WILL destroy data in the target database."
                )


def _pct(values, pct):
    k = (len(values) - 1) * pct / 100
    f = int(k)
    c = min(f + 1, len(values) - 1)
    d = k - f
    return values[f] + d * (values[c] - values[f])


async def seed(session):
    """Seeds synthetic rows via bulk inserts for maximum throughput."""
    asset_ids = [uuid.uuid4() for _ in range(ASSET_COUNT)]
    now = datetime.now(UTC)

    # Bulk insert assets
    asset_rows = []
    for i, aid in enumerate(asset_ids):
        ts = now - timedelta(days=i % 90)
        asset_rows.append({
            "asset_id": aid,
            "hostname": f"PROD-NODE-{i}",
            "canonical_ip": f"10.{(i // 256) % 256}.{i % 256}.{(i * 7) % 255}",
            "cryptographic_fingerprint": f"fp-{aid.hex[:55]}".ljust(64, "0"),
            "lifecycle_state": "Discovered",
            "current_compliance_score": 0,
            "created_at": ts,
            "updated_at": ts,
        })
    await session.execute(insert(InfrastructureAsset), asset_rows)
    await session.flush()

    # Bulk insert audit logs
    audit_rows = []
    for i in range(AUDIT_COUNT):
        ts = now - timedelta(days=i % 90, hours=i % 24)
        audit_rows.append({
            "log_id": uuid.uuid4(),
            "asset_id": asset_ids[i % ASSET_COUNT],
            "actor_id": None,
            "action_verb": "TRANSITION_STATE",
            "immutable_payload": {"i": i},
            "performed_at": ts,
        })
    for chunk in _chunks(audit_rows, 5000):
        await session.execute(insert(AuditLog), chunk)
    await session.flush()

    # Bulk insert telemetry metrics
    metric_rows = []
    for i in range(METRIC_COUNT):
        ts = now - timedelta(days=i % 30, hours=i % 24)
        metric_rows.append({
            "metric_id": uuid.uuid4(),
            "asset_id": asset_ids[i % ASSET_COUNT],
            "event_time": ts,
            "cpu_utilization": float(i % 100),
            "diagnostic_payload": {"i": i},
        })
    for chunk in _chunks(metric_rows, 5000):
        await session.execute(insert(TelemetryMetric), chunk)
    await session.flush()

    # Bulk insert winlog events
    severities = ["Information", "Warning", "Critical"]
    winlog_rows = []
    for i in range(WINLOG_COUNT):
        ts = now - timedelta(days=i % 30, hours=i % 24)
        winlog_rows.append({
            "log_id": uuid.uuid4(),
            "asset_id": asset_ids[i % ASSET_COUNT],
            "occurrence_time": ts,
            "event_id": 4600 + (i % 100),
            "severity_level": severities[i % 3],
            "evtx_metadata": {"i": i},
        })
    for chunk in _chunks(winlog_rows, 5000):
        await session.execute(insert(WindowsEventLog), chunk)
    await session.flush()

    return asset_ids


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


async def measure(client, asset_ids):
    """Runs benchmark iterations and returns timing results."""
    target_asset = str(asset_ids[0])

    endpoints = [
        ("search?q=node", "Global Search (trigram)"),
        ("search?q=TRANSITION_STATE&type=audit", "Search Audit-only"),
        ("timeline", "Timeline (UNION ALL, no filter)"),
        ("timeline?severity=Critical", "Timeline Critical only"),
        ("timeline?type=audit", "Timeline Audit-only"),
        (f"telemetry/metrics?asset_id={target_asset}", "Telemetry Metrics"),
        (f"telemetry/winlogs?asset_id={target_asset}", "Telemetry Winlogs"),
    ]

    results = {}
    for path, label in endpoints:
        times = []
        for _ in range(WARMUP):
            client.get(f"/api/v1/{path}")
        for _ in range(ITERATIONS):
            start = time.perf_counter_ns()
            resp = client.get(f"/api/v1/{path}")
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            assert resp.status_code == 200, f"{label} failed ({resp.status_code}): {resp.text[:200]}"
            times.append(elapsed_ms)
        times_sorted = sorted(times)
        results[label] = {
            "p50_ms": round(_pct(times_sorted, 50), 2),
            "p95_ms": round(_pct(times_sorted, 95), 2),
            "p99_ms": round(_pct(times_sorted, 99), 2),
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
            "mean_ms": round(statistics.mean(times), 2),
        }
    return results


async def main():
    # ── SAFETY GATE ─────────────────────────────────────────────────────────
    benchmark_db_url = os.environ.get(_BENCHMARK_DB_ENV_VAR, "").strip()
    _assert_benchmark_safety(benchmark_db_url)

    print(f"[BENCHMARK] Target database: {benchmark_db_url.rsplit('/', 1)[-1].split('?')[0]}")
    print(f"[BENCHMARK] SAFETY GUARD PASSED — proceeding with benchmark.")

    # ── Create isolated engine for benchmark DB ──────────────────────────────
    engine = create_async_engine(benchmark_db_url, echo=False)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        print(f"Seeding {ASSET_COUNT:,} assets, {AUDIT_COUNT:,} audit, {METRIC_COUNT:,} metrics, {WINLOG_COUNT:,} winlogs...")
        t0 = time.perf_counter()
        async with sm() as session:
            async with session.begin():
                # TRUNCATE is safe here because we are operating on the DEDICATED
                # benchmark database, not the application database.
                # This was verified by _assert_benchmark_safety() above.
                await session.execute(text(
                    "TRUNCATE infrastructure_assets, audit_logs, telemetry_metrics, "
                    "windows_event_logs RESTART IDENTITY CASCADE"
                ))
                asset_ids = await seed(session)
        seed_time = time.perf_counter() - t0
        print(f"Seed complete in {seed_time:.1f}s")

        print(f"Running {ITERATIONS} iterations per endpoint ({WARMUP} warmup)...")
        t0 = time.perf_counter()
        results = await measure(client, asset_ids)
        bench_time = time.perf_counter() - t0
        print(f"Benchmark complete in {bench_time:.1f}s")

    # Write report
    os.makedirs("docs", exist_ok=True)
    report_path = "docs/BENCHMARK_RESULTS.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# EIMS Benchmark Results (Sprint 11)\n\n")
        f.write(f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}  \n")
        f.write(f"**Iterations:** {ITERATIONS} per endpoint (+{WARMUP} warmup)  \n")
        f.write(f"**Seed:** {ASSET_COUNT:,} assets / {AUDIT_COUNT:,} audit_logs / {METRIC_COUNT:,} telemetry_metrics / {WINLOG_COUNT:,} winlogs  \n")
        f.write(f"**Seed time:** {seed_time:.1f}s / **Bench time:** {bench_time:.1f}s  \n\n")
        f.write("## Results\n\n")
        f.write("| Endpoint | p50 (ms) | p95 (ms) | p99 (ms) | min (ms) | max (ms) | mean (ms) |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|\n")
        for label, m in results.items():
            f.write(f"| {label} | {m['p50_ms']} | {m['p95_ms']} | {m['p99_ms']} | {m['min_ms']} | {m['max_ms']} | {m['mean_ms']} |\n")
        f.write("\n## Methodology\n\n")
        f.write("- All queries run via FastAPI TestClient (full request lifecycle including Pydantic validation).\n")
        f.write("- Data seeded within a single DB transaction against a DEDICATED benchmark database.\n")
        f.write("- 3 warmup iterations discarded before measurement.\n")
        f.write("- p50/p95/p99 calculated via linear interpolation.\n")
        f.write("- PostgreSQL connection pool at default warm state.\n")
        f.write(f"- Target database: `{benchmark_db_url.rsplit('/', 1)[-1].split('?')[0]}`\n")

    with open(report_path, "r", encoding="utf-8") as f:
        print(f.read())

    await engine.dispose()
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())

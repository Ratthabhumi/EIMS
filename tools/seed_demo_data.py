"""
EIMS Phase 12.1 — Demo Data Seeder (Idempotent, Non-Destructive)

Populates the dev database with a small, deterministic, coherent demo dataset
for the graduation/showcase. Safe to run multiple times.

IMPORTANT:
- Does NOT delete or truncate any existing data (including benchmark rows)
- Uses deterministic UUIDs and hostnames as idempotency keys
- Skips assets/records that already exist
- Demo records are identified by the 'fp-demo-' fingerprint prefix (assets)
  and 'demo_seeder' payload key (audit/telemetry/winlog)
- analysis_history is NOT seeded here (8 real records already survive from
  before the benchmark incident)

Demo Story:
    AI-WORKER-001 (AI inference/training node at KEL)
       ↓
    Telemetry: CPU/memory anomaly (elevated utilization)
       ↓
    Windows Event: Auth failure + service crash
       ↓
    Audit: SECURITY_ALERT_RAISED → ANALYSIS_COMPLETED
       ↓
    AI Analysis: brute force + resource exhaustion findings (existing records)
       ↓
    Timeline: unified view of the incident
       ↓
    Search: 'AI-WORKER', 'KEL', 'GPU', 'brute force', 'SECURITY', 'AUTH_FAILURE'

Data Classification:
    infrastructure_assets  → RECONSTRUCTED DEMO DATA (new rows added)
    audit_logs             → RECONSTRUCTED DEMO DATA (new rows added alongside benchmark)
    telemetry_metrics      → RECONSTRUCTED DEMO DATA (new rows added alongside benchmark)
    windows_event_logs     → RECONSTRUCTED DEMO DATA (new rows added alongside benchmark)
    analysis_history       → REAL SURVIVING DATA (8 rows, not touched here)

Usage:
    set PYTHONPATH=.
    python tools/seed_demo_data.py
"""
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from backend.infrastructure.database import database_engine

os.environ.setdefault("EIMS_ENVIRONMENT", "development")

# ── Deterministic demo asset definitions ────────────────────────────────────
# UUIDs are deterministic (name-based UUID5) so re-runs are idempotent.
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID namespace for DNS

def _demo_uuid(name: str) -> str:
    """Returns a deterministic UUID5 for a given demo entity name."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"eims.demo.{name}"))


DEMO_ASSETS = [
    {
        "name": "AI-WORKER-001",
        "hostname": "AI-WORKER-001",
        "canonical_ip": "10.10.1.50",
        "lifecycle_state": "Active",
        "compliance_score": 72,
        "description": "Primary AI inference and training node — KEL GPU cluster",
    },
    {
        "name": "KEL-PROD-WEB-01",
        "hostname": "KEL-PROD-WEB-01",
        "canonical_ip": "10.10.1.10",
        "lifecycle_state": "Active",
        "compliance_score": 85,
        "description": "Production web server — KEL external-facing portal",
    },
    {
        "name": "KEL-PROD-DB-01",
        "hostname": "KEL-PROD-DB-01",
        "canonical_ip": "10.10.1.20",
        "lifecycle_state": "Active",
        "compliance_score": 91,
        "description": "Production PostgreSQL primary database server",
    },
    {
        "name": "SECURITY-SIEM-01",
        "hostname": "SECURITY-SIEM-01",
        "canonical_ip": "10.10.2.5",
        "lifecycle_state": "Active",
        "compliance_score": 78,
        "description": "Security Information and Event Management server",
    },
    {
        "name": "KEL-OFFICE-PC-001",
        "hostname": "KEL-OFFICE-PC-001",
        "canonical_ip": "10.10.5.101",
        "lifecycle_state": "Active",
        "compliance_score": 65,
        "description": "Office workstation — administration use",
    },
]

# ── Demo incident timeline (T=0 is base_time, offsets in minutes) ────────────
# Story: AI-WORKER-001 CPU anomaly → auth failure → alert → analysis → resolved

def _build_demo_events(asset_map: dict, base_time: datetime) -> dict:
    """Builds all demo events referenced to a coherent base_time."""

    ai_worker_id = asset_map["AI-WORKER-001"]
    web_id = asset_map["KEL-PROD-WEB-01"]
    siem_id = asset_map["SECURITY-SIEM-01"]
    office_id = asset_map["KEL-OFFICE-PC-001"]

    audit_events = [
        # T-120: AI worker first noticed high CPU
        {
            "asset_id": ai_worker_id,
            "action_verb": "TELEMETRY_INGESTED",
            "offset_min": -120,
            "payload": {"source": "demo_seeder", "detail": "GPU utilization spike detected on AI-WORKER-001", "cpu_pct": 98.2},
        },
        # T-90: Security alert raised
        {
            "asset_id": ai_worker_id,
            "action_verb": "SECURITY_ALERT_RAISED",
            "offset_min": -90,
            "payload": {"source": "demo_seeder", "detail": "AUTH_FAILURE threshold exceeded — 47 failed attempts in 60s", "severity": "HIGH"},
        },
        # T-75: SIEM picks up audit log clear
        {
            "asset_id": siem_id,
            "action_verb": "SECURITY_ALERT_RAISED",
            "offset_min": -75,
            "payload": {"source": "demo_seeder", "detail": "Audit log cleared on SECURITY-SIEM-01 — possible tampering", "severity": "CRITICAL"},
        },
        # T-60: Analysis triggered
        {
            "asset_id": ai_worker_id,
            "action_verb": "AI_DIAGNOSIS_RAN",
            "offset_min": -60,
            "payload": {"source": "demo_seeder", "detail": "AI analysis triggered for brute force pattern on AI-WORKER-001"},
        },
        # T-45: Web server login failure
        {
            "asset_id": web_id,
            "action_verb": "USER_LOGIN_FAILED",
            "offset_min": -45,
            "payload": {"source": "demo_seeder", "detail": "AUTH_FAILURE on KEL-PROD-WEB-01 — 23 attempts from 185.220.101.5", "ip": "185.220.101.5"},
        },
        # T-30: Analysis completed
        {
            "asset_id": ai_worker_id,
            "action_verb": "ANALYSIS_COMPLETED",
            "offset_min": -30,
            "payload": {"source": "demo_seeder", "detail": "AI analysis completed — brute force confirmed, GPU thermal anomaly separate incident"},
        },
        # T-15: Compliance score updated
        {
            "asset_id": ai_worker_id,
            "action_verb": "COMPLIANCE_SCORE_UPDATED",
            "offset_min": -15,
            "payload": {"source": "demo_seeder", "detail": "Compliance score recalculated after incident — score: 72"},
        },
        # T-0: New user enrolled (office)
        {
            "asset_id": office_id,
            "action_verb": "ASSET_ENROLLED",
            "offset_min": 0,
            "payload": {"source": "demo_seeder", "detail": "New employee onboarding — KEL-OFFICE-PC-001 enrolled in EIMS"},
        },
    ]

    telemetry_events = [
        # AI worker GPU spike sequence
        {"asset_id": ai_worker_id, "offset_min": -130, "cpu": 45.2, "payload": {"source": "demo_seeder", "ram_percent": 62.1, "gpu_temp_c": 72, "gpu_util_pct": 45}},
        {"asset_id": ai_worker_id, "offset_min": -125, "cpu": 78.5, "payload": {"source": "demo_seeder", "ram_percent": 78.3, "gpu_temp_c": 85, "gpu_util_pct": 78}},
        {"asset_id": ai_worker_id, "offset_min": -120, "cpu": 98.2, "payload": {"source": "demo_seeder", "ram_percent": 94.1, "gpu_temp_c": 97, "gpu_util_pct": 99, "alert": "GPU_THERMAL_CRITICAL"}},
        {"asset_id": ai_worker_id, "offset_min": -115, "cpu": 97.1, "payload": {"source": "demo_seeder", "ram_percent": 93.5, "gpu_temp_c": 95, "gpu_util_pct": 97}},
        {"asset_id": ai_worker_id, "offset_min": -60,  "cpu": 72.0, "payload": {"source": "demo_seeder", "ram_percent": 71.0, "gpu_temp_c": 81, "gpu_util_pct": 72, "note": "throttled"}},
        # Web server baseline
        {"asset_id": web_id, "offset_min": -100, "cpu": 22.0, "payload": {"source": "demo_seeder", "ram_percent": 55.0, "connections": 247}},
        {"asset_id": web_id, "offset_min": -50,  "cpu": 31.5, "payload": {"source": "demo_seeder", "ram_percent": 57.2, "connections": 312, "note": "auth_flood_detected"}},
        # DB server
        {"asset_id": asset_map["KEL-PROD-DB-01"], "offset_min": -90, "cpu": 18.5, "payload": {"source": "demo_seeder", "ram_percent": 44.0, "active_connections": 28}},
    ]

    winlog_events = [
        # AI-WORKER auth failures
        {"asset_id": ai_worker_id, "offset_min": -95, "event_id": 4625, "severity": "Warning",
         "payload": {"source": "demo_seeder", "channel": "Security", "message": "AUTH_FAILURE — account: svc_ai_runner, ip: 185.220.101.5", "logon_type": 3}},
        {"asset_id": ai_worker_id, "offset_min": -92, "event_id": 4625, "severity": "Warning",
         "payload": {"source": "demo_seeder", "channel": "Security", "message": "AUTH_FAILURE — account: administrator, ip: 185.220.101.5", "attempts": 15}},
        {"asset_id": ai_worker_id, "offset_min": -88, "event_id": 4625, "severity": "Critical",
         "payload": {"source": "demo_seeder", "channel": "Security", "message": "AUTH_FAILURE — brute force lockout triggered, 47 attempts", "locked": True}},
        # GPU service crash
        {"asset_id": ai_worker_id, "offset_min": -119, "event_id": 7034, "severity": "Critical",
         "payload": {"source": "demo_seeder", "channel": "System", "message": "CUDA GPU Service terminated unexpectedly — thermal shutdown", "service": "NVIDIACudaDriver"}},
        # SIEM audit cleared
        {"asset_id": siem_id, "offset_min": -76, "event_id": 1102, "severity": "Critical",
         "payload": {"source": "demo_seeder", "channel": "Security", "message": "Audit log was cleared by: SECURITY-SIEM-01\\Administrator", "cleared_by": "Administrator"}},
        # Web server successful login after lockout resolved
        {"asset_id": web_id, "offset_min": -40, "event_id": 4624, "severity": "Information",
         "payload": {"source": "demo_seeder", "channel": "Security", "message": "Successful logon — admin console re-authenticated after investigation", "logon_type": 2}},
        # Office PC new account
        {"asset_id": office_id, "offset_min": -5, "event_id": 4720, "severity": "Information",
         "payload": {"source": "demo_seeder", "channel": "Security", "message": "New user account created — onboarding: KEL-OFFICE-PC-001\\newuser2847"}},
    ]

    return {
        "audit": audit_events,
        "telemetry": telemetry_events,
        "winlog": winlog_events,
    }


# ── Seeder functions ─────────────────────────────────────────────────────────

async def _seed_assets(session) -> dict[str, str]:
    """
    Inserts demo assets using deterministic fingerprints.
    ON CONFLICT on cryptographic_fingerprint (UNIQUE) makes this idempotent.
    Returns hostname→asset_id map.
    """
    now = datetime.now(UTC)
    asset_map = {}

    for asset_def in DEMO_ASSETS:
        asset_id = _demo_uuid(f"asset.{asset_def['name']}")
        fingerprint = f"fp-demo-{asset_def['name'].lower().replace('-', '')}".ljust(64, "0")[:64]
        ts = now - timedelta(days=14)

        result = await session.execute(
            text("""
                INSERT INTO infrastructure_assets
                    (asset_id, hostname, canonical_ip, cryptographic_fingerprint,
                     lifecycle_state, current_compliance_score, created_at, updated_at)
                VALUES (:aid, :hn, :ip, :fp, :ls, :cs, :ca, :ua)
                ON CONFLICT (cryptographic_fingerprint) DO UPDATE
                    SET updated_at = EXCLUDED.updated_at
                RETURNING asset_id
            """),
            {
                "aid": asset_id,
                "hn": asset_def["hostname"],
                "ip": asset_def["canonical_ip"],
                "fp": fingerprint,
                "ls": asset_def["lifecycle_state"],
                "cs": asset_def["compliance_score"],
                "ca": ts,
                "ua": ts,
            }
        )
        returned_id = str(result.scalar())
        asset_map[asset_def["hostname"]] = returned_id

    return asset_map


async def _seed_audit_events(session, events: list, base_time: datetime):
    """Inserts demo audit events (always inserts — IDs are random UUIDs)."""
    for ev in events:
        ts = base_time + timedelta(minutes=ev["offset_min"])
        await session.execute(
            text("""
                INSERT INTO audit_logs (log_id, asset_id, action_verb, performed_at, immutable_payload)
                VALUES (:lid, :aid, :av, :pa, :ip)
            """),
            {
                "lid": str(uuid.uuid4()),
                "aid": ev["asset_id"],
                "av": ev["action_verb"],
                "pa": ts,
                "ip": json.dumps(ev["payload"]),
            }
        )


async def _seed_telemetry_events(session, events: list, base_time: datetime):
    """Inserts demo telemetry metrics."""
    for ev in events:
        ts = base_time + timedelta(minutes=ev["offset_min"])
        await session.execute(
            text("""
                INSERT INTO telemetry_metrics (metric_id, asset_id, event_time, cpu_utilization, diagnostic_payload)
                VALUES (:mid, :aid, :et, :cpu, :dp)
            """),
            {
                "mid": str(uuid.uuid4()),
                "aid": ev["asset_id"],
                "et": ts,
                "cpu": ev["cpu"],
                "dp": json.dumps(ev["payload"]),
            }
        )


async def _seed_winlog_events(session, events: list, base_time: datetime):
    """Inserts demo Windows event log records."""
    for ev in events:
        ts = base_time + timedelta(minutes=ev["offset_min"])
        await session.execute(
            text("""
                INSERT INTO windows_event_logs (log_id, asset_id, occurrence_time, event_id, severity_level, evtx_metadata)
                VALUES (:lid, :aid, :ot, :eid, :sv, :em)
            """),
            {
                "lid": str(uuid.uuid4()),
                "aid": ev["asset_id"],
                "ot": ts,
                "eid": ev["event_id"],
                "sv": ev["severity"],
                "em": json.dumps(ev["payload"]),
            }
        )


async def _demo_already_seeded(session) -> bool:
    """Returns True if demo audit events already exist (checks for demo_seeder payload marker)."""
    r = await session.execute(
        text("SELECT COUNT(*) FROM audit_logs WHERE immutable_payload->>'source' = 'demo_seeder'")
    )
    return r.scalar() > 0


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    await database_engine.initialize()
    sm = database_engine.get_session_maker()

    # Use a fixed base_time so re-runs produce the same timestamps
    # Base = Sept 9 2026 18:00 UTC (day before the benchmark incident)
    base_time = datetime(2026, 9, 9, 18, 0, 0, tzinfo=UTC)

    async with sm() as session:
        async with session.begin():
            print("=== EIMS Demo Data Seeder (Phase 12.1) ===\n")

            # ── Assets ───────────────────────────────────────────────────────
            print("Seeding demo assets (deterministic, idempotent)...")
            asset_map = await _seed_assets(session)
            print(f"  Assets ready: {list(asset_map.keys())}\n")

            # ── Check if demo events already exist ────────────────────────
            already_seeded = await _demo_already_seeded(session)
            if already_seeded:
                print("Demo audit/telemetry/winlog events already present (demo_seeder marker found).")
                print("Skipping event seeding to preserve idempotency.\n")
            else:
                events = _build_demo_events(asset_map, base_time)

                print(f"Seeding {len(events['audit'])} demo audit events...")
                await _seed_audit_events(session, events["audit"], base_time)
                print(f"  Done.\n")

                print(f"Seeding {len(events['telemetry'])} demo telemetry events...")
                await _seed_telemetry_events(session, events["telemetry"], base_time)
                print(f"  Done.\n")

                print(f"Seeding {len(events['winlog'])} demo Windows event logs...")
                await _seed_winlog_events(session, events["winlog"], base_time)
                print(f"  Done.\n")

            # ── Summary ───────────────────────────────────────────────────
            r = await session.execute(text("SELECT COUNT(*) FROM infrastructure_assets WHERE cryptographic_fingerprint LIKE 'fp-demo-%'"))
            demo_assets = r.scalar()

            r = await session.execute(text("SELECT COUNT(*) FROM audit_logs WHERE immutable_payload->>'source' = 'demo_seeder'"))
            demo_audit = r.scalar()

            r = await session.execute(text("SELECT COUNT(*) FROM telemetry_metrics WHERE diagnostic_payload->>'source' = 'demo_seeder'"))
            demo_telemetry = r.scalar()

            r = await session.execute(text("SELECT COUNT(*) FROM windows_event_logs WHERE evtx_metadata->>'source' = 'demo_seeder'"))
            demo_winlog = r.scalar()

            r = await session.execute(text("SELECT COUNT(*) FROM analysis_history"))
            total_analysis = r.scalar()

            print("=== Demo Dataset Summary ===")
            print(f"  Demo assets (fp-demo- fingerprint):  {demo_assets}")
            print(f"  Demo audit logs (demo_seeder):       {demo_audit}")
            print(f"  Demo telemetry (demo_seeder):        {demo_telemetry}")
            print(f"  Demo winlogs (demo_seeder):          {demo_winlog}")
            print(f"  Analysis history (REAL surviving):   {total_analysis}")
            print()
            print("Searchable demo terms: AI-WORKER, KEL, GPU, SECURITY, ANALYSIS_COMPLETED,")
            print("                       AUTH_FAILURE, brute force, SIEM, PROD-WEB, TRAINING")

    await database_engine.close()
    print("\nDemo data seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())

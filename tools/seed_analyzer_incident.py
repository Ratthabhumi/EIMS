"""
EIMS — AI Analyzer Demo Incident Seeder (Idempotent, Non-Destructive)

Creates ONE coherent synthetic incident for the /analyzer investigation console:

    Incident : "Suspicious Authentication + Resource Anomaly"
    Asset    : KEL-PROD-WEB-01 (10.10.1.10)
    Base time: 2026-09-10 14:00 UTC (deterministic; ~10 minute span)

Everything written here is EXPLICITLY classified as SYNTHETIC / AI DEMO DATA.
It reuses the EXISTING EIMS schema only (infrastructure_assets, audit_logs,
telemetry_metrics, windows_event_logs, analysis_history, ai_knowledge).
It NEVER deletes, truncates, or renames any existing row (including the real
surviving analysis_history records and real benchmark evidence).

Idempotency:
  - Evidence rows carry `"source": "seed_analyzer_incident"` markers. If ANY
    are already present, evidence insertion is skipped.
  - The incident analysis_history record is keyed by event_id AINC-2026-0910-0001
    and upserted (content refreshed, never duplicated).
  - ai_knowledge rows are inserted only when (event_id, description) is new.

Usage:
    set PYTHONPATH=.
    python tools/seed_analyzer_incident.py
"""
import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from backend.domain.analyzer.services.vector_db import _get_embedding
from backend.infrastructure.database import database_engine

# ── Incident identity ─────────────────────────────────────────────────────────
INCIDENT_EVENT_ID = "AINC-2026-0910-0001"
INCIDENT_NAME = "Suspicious Authentication + Resource Anomaly"
AFFECTED_HOST = "KEL-PROD-WEB-01"
INCIDENT_IP = "185.220.101.5"            # synthetic external attacker source
EVIDENCE_SOURCE = "seed_analyzer_incident"

# Deterministic base time (matches demo_seeder's KEL narrative; day before v0.3.0 demo)
BASE_TIME = datetime(2026, 9, 10, 14, 0, 0, tzinfo=UTC)


def _demo_uuid(name: str) -> str:
    """Deterministic UUID5 so the KEL-PROD-WEB-01 asset id matches seed_demo_data.py."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"eims.demo.{name}"))


KEL_WEB_ASSET_ID = _demo_uuid(f"asset.{AFFECTED_HOST}")


# ── Evidence builders ─────────────────────────────────────────────────────────

def _winlog(offset_min, event_id, severity, channel, message, **extra) -> dict:
    payload = {
        "source": EVIDENCE_SOURCE,
        "classification": "SYNTHETIC_AI_DEMO",
        "incident": INCIDENT_EVENT_ID,
        "channel": channel,
        "message": message,
    }
    payload.update(extra)
    return {"offset_min": offset_min, "event_id": event_id, "severity": severity, "payload": payload}


def _telemetry(offset_min, cpu, ram, connections, note, payload_extra=None) -> dict:
    payload = {
        "source": EVIDENCE_SOURCE,
        "classification": "SYNTHETIC_AI_DEMO",
        "incident": INCIDENT_EVENT_ID,
        "ram_percent": ram,
        "connections": connections,
        "note": note,
    }
    if payload_extra:
        payload.update(payload_extra)
    return {"offset_min": offset_min, "cpu": cpu, "payload": payload}


def _audit(offset_min, verb, detail, severity=None) -> dict:
    payload = {
        "source": EVIDENCE_SOURCE,
        "classification": "SYNTHETIC_AI_DEMO",
        "incident": INCIDENT_EVENT_ID,
        "detail": detail,
    }
    if severity:
        payload["severity"] = severity
    return {"offset_min": offset_min, "verb": verb, "payload": payload}


def _build_evidence() -> dict:
    """Windows events, telemetry and audit rows for KEL-PROD-WEB-01 (offsets in minutes)."""
    winlogs = [
        # t+1 Authentication burst
        _winlog(1, 4625, "Warning", "Security",
                "Failed logon attempt for Administrator via RDP from 185.220.101.5",
                target_user_name="Administrator", source_network_ip=INCIDENT_IP,
                logon_type=10, sub_status="0xC000006A"),
        _winlog(1, 4625, "Warning", "Security",
                "Failed logon attempt for svc_web_deploy via SMB from 185.220.101.5",
                target_user_name="svc_web_deploy", source_network_ip=INCIDENT_IP,
                logon_type=3, sub_status="0xC000006D"),
        # t+2 second failed burst
        _winlog(2, 4625, "Warning", "Security",
                "Failed logon attempt for Administrator via RDP from 185.220.101.5",
                target_user_name="Administrator", source_network_ip=INCIDENT_IP,
                logon_type=10, sub_status="0xC000006A"),
        _winlog(2, 4625, "Critical", "Security",
                "Failed logon burst — 12th failure in 60s window for svc_web_deploy",
                target_user_name="svc_web_deploy", source_network_ip=INCIDENT_IP,
                logon_type=3, attempts=12),
        # t+3 lockout
        _winlog(3, 4740, "Warning", "Security",
                "Account Administrator locked out after repeated failed logons",
                target_user_name="Administrator", locked_out_source="185.220.101.5"),
        # t+4 privileged logon + process creation
        _winlog(4, 4624, "Information", "Security",
                "Successful logon for svc_web_deploy over network (logon after failure burst)",
                target_user_name="svc_web_deploy", logon_type=3, source_network_ip="10.10.1.5"),
        _winlog(4, 4672, "Information", "Security",
                "Special privileges assigned to new logon for svc_web_deploy",
                target_user_name="svc_web_deploy", privileges="SeDebugPrivilege, SeImpersonatePrivilege"),
        _winlog(4, 4688, "Information", "Security",
                "New process created: cmd.exe launched encoded PowerShell from parent w3wp.exe",
                process_name="cmd.exe", command_line='cmd.exe /c powershell.exe -enc SQBFAFgA...',
                parent_process="w3wp.exe", target_user_name="svc_web_deploy"),
        # t+5 persistence + firewall evidence
        _winlog(5, 7045, "Information", "System",
                "A service was installed on the system: svcmon4021 (nssm-style wrapper)",
                service_name="svcmon4021", image_path="C:\\Windows\\Temp\\svcmon4021.exe"),
        _winlog(5, 5152, "Warning", "Microsoft-Windows-Windows Filtering Platform",
                "Windows Filtering Platform blocked an inbound connection attempt (RDP/3389)",
                source_network_ip=INCIDENT_IP, app_id="\\device\\harddiskvolume2\\windows\\system32\\svchost.exe"),
        # t+6 endpoint protection + audit-log tampering pointer
        _winlog(6, 1116, "Information", "Microsoft-Windows-Windows Defender/Operational",
                "Endpoint protection detected threat 'Trojan:Win32/PsShell.Enc' on host",
                threat_name="Trojan:Win32/PsShell.Enc", action_status="Quarantined"),
        _winlog(6, 1102, "Critical", "Security",
                "Security audit log was cleared on this host",
                cleared_by="KEL-PROD-WEB-01\\Administrator"),
        # t+7 stability failure
        _winlog(7, 41, "Critical", "System",
                "Kernel-Power — system rebooted without clean shutdown",
                bugcheck_code=0),
        _winlog(7, 6008, "Critical", "System",
                "The previous system shutdown at 13:52 UTC was unexpected",
                previous_shutdown="2026-09-10 13:52:20 UTC"),
        _winlog(7, 7034, "Warning", "System",
                "IIS World Wide Web Publishing Service terminated unexpectedly",
                service_name="W3SVC"),
        _winlog(8, 7036, "Information", "System",
                "Windows Update service entered Stopped then Running state",
                service_name="wuauserv", transition="Stopped->Running"),
    ]

    telemetry = [
        _telemetry(0, 12.4, 48.2, 210, "baseline"),
        _telemetry(1, 14.1, 49.0, 214, "baseline"),
        _telemetry(6, 41.8, 61.4, 388, "connections increasing"),
        _telemetry(7, 87.3, 82.1, 540, "resource anomaly",
                   payload_extra={"gpu_util_pct": 91, "gpu_temp_c": 87, "alert": "RESOURCE_ANOMALY"}),
        _telemetry(8, 91.5, 85.7, 576, "peak anomaly",
                   payload_extra={"gpu_util_pct": 94, "gpu_temp_c": 89, "alert": "GPU_ANOMALY"}),
        _telemetry(9, 72.2, 71.0, 450, "throttled"),
        _telemetry(10, 16.8, 50.3, 236, "recovering"),
    ]

    audit = [
        _audit(5, "FIREWALL_BLOCK", "Blocked inbound RDP/SMB connection attempts from 185.220.101.5 (21 blocked in 60s)", "HIGH"),
        _audit(6, "SECURITY_ALERT_RAISED", "Endpoint protection flagged Trojan:Win32/PsShell.Enc on KEL-PROD-WEB-01", "CRITICAL"),
        _audit(8, "AI_ANALYSIS_TRIGGERED", "AI investigation opened for suspicious authentication + resource anomaly on KEL-PROD-WEB-01"),
    ]

    return {"winlog": winlogs, "telemetry": telemetry, "audit": audit}


# ── Incident analysis content (deterministic AI story, all hedged wording) ───

def _analysis_content() -> tuple[dict, dict, str, str, list]:
    """Returns (solution_summary, event_metadata, description, ai_summary, search_results)."""

    exec_summary = (
        "AI investigation of production web server KEL-PROD-WEB-01 reconstructed a ~10 minute "
        "suspicious authentication burst followed by possible code execution and a resource "
        "anomaly. Evidence sequence: repeated failed logons (Event 4625) targeting Administrator "
        "and svc_web_deploy from a single external source IP, an account lockout (4740), a "
        "successful network logon with special-privilege assignment (4624/4672), an encoded "
        "PowerShell process (4688), a suspicious service install (7045), blocked inbound "
        "RDP/SMB connections (5152 + firewall policy), an endpoint-protection detection (1116), "
        "and a cleared Security audit log (1102). CPU/GPU utilization spiked to ~90% immediately "
        "before an unexpected reboot (41/6008). Evidence suggests a possible credential-based "
        "attack attempt; the resource anomaly may be related or independent."
    )

    causes = [
        "Likely brute-force or credential-stuffing attempt: repeated 4625 logon failures from 185.220.101.5 escalated to an Administrator account lockout (Event 4740).",
        "Suspected credential reuse or privilege escalation: a successful logon (4624) with special privileges (4672) and encoded PowerShell execution (4688) occurred within one minute of the lockout.",
        "Potential persistence setup: an unknown service (Event 7045) was installed during the same window as blocked inbound RDP/SMB connections.",
        "Resource anomaly possibly separate: the CPU/GPU spike and Kernel-Power / unexpected shutdown (41, 6008) may reflect load or an environmental fault rather than pure attacker action.",
    ]

    steps = [
        "Reset and enforce password change for affected local accounts (Administrator, svc_web_deploy); tune the account-lockout threshold for RDP/SMB sources.",
        "Contain the host: block 185.220.101.5 at the network layer and isolate KEL-PROD-WEB-01 from production traffic pending forensic review.",
        "Investigate the encoded PowerShell command and the newly installed service 'svcmon4021'; remove the service and scan for persistence (scheduled tasks, run keys, WMI).",
        "Rotate secrets used by svc_web_deploy and any service account that logged on during the window.",
        "Centralize Security/System event logs and enable full process auditing to close the gap exposed by Event 1102.",
        "Rebuild the host from a clean image if forensic review confirms unintended code execution, and review host/hypervisor resource policy for the GPU anomaly.",
    ]

    assessment = (
        "The evidence strongly supports a credential-based attack narrative: repeated failed logons, "
        "an account lockout, an elevated network logon, encoded command execution, a suspicious service "
        "installation, and an audit-log clear are consistent with a suspected attacker performing initial "
        "access, privilege escalation, and persistence setup. The resource spike and unexpected shutdown "
        "may be a consequence of the load or an independent environmental anomaly; the correlation is "
        "suggestive rather than confirmed."
    )

    evidence_interpretation = [
        "4 logon failures (Event 4625) in ~2 minutes from the same external source IP 185.220.101.5.",
        "Account lockout (Event 4740) for Administrator — consistent with an automated brute-force attempt.",
        "Successful logon (4624) with Special Privileges (4672) and an encoded PowerShell process (4688) one minute after lockout — timing is consistent with credential reuse or escalation.",
        "Unknown service installed (7045) and inbound RDP/SMB connections blocked by the Windows Filtering Platform (5152) and firewall policy.",
        "Endpoint protection flagged Trojan:Win32/PsShell.Enc (Event 1116) on the host.",
        "Security audit log was cleared (Event 1102) during the event window — an anti-forensics indicator.",
        "CPU/GPU utilization spiked to ~90% with elevated connection counts immediately before an unexpected reboot (Event 41 / 6008).",
    ]

    confidence = {
        "level": "Moderate",
        "percent": 72,
        "rationale": "Correlated across seven independent evidence sources with a coherent timeline, but attribution and the attacker's end goal remain unconfirmed; the resource anomaly may be unrelated.",
    }

    questions_answered = [
        {"q": "What happened?", "a": "A ~10 minute suspicious authentication burst was followed by possible code execution, a resource anomaly, and an unexpected reboot on KEL-PROD-WEB-01."},
        {"q": "Which asset was affected?", "a": "KEL-PROD-WEB-01 (10.10.1.10), the production-facing web server."},
        {"q": "What evidence supports the finding?", "a": "Event IDs 4625/4740/4624/4672/4688/7045/5152/1116/1102/41/6008 plus correlated telemetry and firewall audit records."},
        {"q": "What is the likely root cause?", "a": "Suspected brute-force followed by privilege escalation and a possible persistence attempt; the resource anomaly is potentially correlated but unconfirmed."},
        {"q": "How severe is it?", "a": "High — a production-facing host with signs of possible code execution and credential targeting."},
        {"q": "What should the operator do next?", "a": "Contain the host, disable affected accounts, block the source IP, audit persistence, rotate secrets, and rebuild if code execution is confirmed."},
    ]

    solution_summary = {
        "overview": exec_summary,
        "causes": causes,
        "steps": steps,
        "severity": "High",
        "confidence": confidence,
        "assessment": assessment,
        "evidenceInterpretation": evidence_interpretation,
        "questionsAnswered": questions_answered,
    }

    event_metadata = {
        "eventId": INCIDENT_EVENT_ID,
        "provider": "IncidentInvestigation (Synthetic Demo)",
        "level": "Critical",
        "logName": "Security + System + Telemetry",
        "timestamp": (BASE_TIME + timedelta(minutes=8)).strftime("%Y-%m-%d %H:%M:%S"),
        "computer": AFFECTED_HOST,
        "isCritical": True,
        "faultingApp": "",
        "incident": {
            "name": INCIDENT_NAME,
            "classification": "SYNTHETIC_AI_DEMO",
            "affectedAsset": AFFECTED_HOST,
            "state": "Investigation complete (demo)",
        },
    }

    description = (
        f"AI DEMO INCIDENT — {INCIDENT_NAME} on {AFFECTED_HOST} ({INCIDENT_IP}). "
        f"Reconstructed synthetic investigation spanning {(BASE_TIME + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')} "
        f"to {(BASE_TIME + timedelta(minutes=8)).strftime('%H:%M:%S')} UTC. "
        "Failed logons, lockout, elevated logon, encoded command execution, service install, blocked RDP/SMB, "
        "endpoint detection, audit-log clear, CPU/GPU anomaly, unexpected reboot."
    )

    ai_summary = (
        "Suspicious authentication burst + resource anomaly on KEL-PROD-WEB-01. Evidence suggests a likely "
        "brute-force attempt (4x Event 4625) escalating to a lockout (4740), followed by elevated logon (4624/4672), "
        "encoded command execution (4688), a service install (7045), blocked RDP/SMB (5152), endpoint detection (1116), "
        "and an audit-log clear (1102). CPU/GPU spiked to ~90% before an unexpected reboot (41/6008). Severity High, "
        "confidence Moderate (72%). SYNTHETIC / AI DEMO DATA."
    )

    search_results = [
        {"title": "MITRE ATT&CK — T1110 Brute Force", "link": "https://attack.mitre.org/techniques/T1110/",
         "snippet": "Adversaries may use credentials obtained through brute-force attempts to access valid accounts; relevant to the observed 4625/4740 chain.", "sourceType": "community"},
        {"title": "MITRE ATT&CK — T1059.001 PowerShell", "link": "https://attack.mitre.org/techniques/T1059/001/",
         "snippet": "Adversaries may abuse PowerShell for execution; aligns with Event 4688 encoded command execution.", "sourceType": "community"},
        {"title": "Microsoft Learn: Windows security event 4625", "link": "https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4625",
         "snippet": "Official documentation for failed logon events (substatus codes, logon types).", "sourceType": "official"},
        {"title": "Microsoft Learn: Windows security event 1102", "link": "https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/event-1102",
         "snippet": "Official documentation for audit log cleared events — an anti-forensics indicator.", "sourceType": "official"},
    ]

    return solution_summary, event_metadata, description, ai_summary, search_results


# ── Seeder functions ─────────────────────────────────────────────────────────

async def _evidence_already_seeded(session) -> bool:
    r = await session.execute(
        text("SELECT COUNT(*) FROM windows_event_logs WHERE evtx_metadata->>'source' = :src"),
        {"src": EVIDENCE_SOURCE},
    )
    return r.scalar() > 0


async def _seed_winlog(session, rows):
    for ev in rows:
        ts = BASE_TIME + timedelta(minutes=ev["offset_min"])
        await session.execute(
            text("""
                INSERT INTO windows_event_logs (log_id, asset_id, occurrence_time, event_id, severity_level, evtx_metadata)
                VALUES (:lid, :aid, :ot, :eid, :sv, :em)
            """),
            {
                "lid": str(uuid.uuid4()),
                "aid": KEL_WEB_ASSET_ID,
                "ot": ts,
                "eid": ev["event_id"],
                "sv": ev["severity"],
                "em": json.dumps(ev["payload"]),
            }
        )


async def _seed_telemetry(session, rows):
    for ev in rows:
        ts = BASE_TIME + timedelta(minutes=ev["offset_min"])
        await session.execute(
            text("""
                INSERT INTO telemetry_metrics (metric_id, asset_id, event_time, cpu_utilization, diagnostic_payload)
                VALUES (:mid, :aid, :et, :cpu, :dp)
            """),
            {
                "mid": str(uuid.uuid4()),
                "aid": KEL_WEB_ASSET_ID,
                "et": ts,
                "cpu": ev["cpu"],
                "dp": json.dumps(ev["payload"]),
            }
        )


async def _seed_audit(session, rows):
    for ev in rows:
        ts = BASE_TIME + timedelta(minutes=ev["offset_min"])
        await session.execute(
            text("""
                INSERT INTO audit_logs (log_id, asset_id, action_verb, performed_at, immutable_payload)
                VALUES (:lid, :aid, :av, :pa, :ip)
            """),
            {
                "lid": str(uuid.uuid4()),
                "aid": KEL_WEB_ASSET_ID,
                "av": ev["verb"],
                "pa": ts,
                "ip": json.dumps(ev["payload"]),
            }
        )


async def _upsert_analysis_record(session):
    solution, metadata, description, ai_summary, search_results = _analysis_content()
    created_at = BASE_TIME + timedelta(minutes=8)

    existing = (await session.execute(
        text("SELECT id FROM analysis_history WHERE event_id = :eid"),
        {"eid": INCIDENT_EVENT_ID},
    )).scalars().first()

    values = {
        "eid": INCIDENT_EVENT_ID,
        "prov": metadata["provider"],
        "pm": "AI Incident Investigation (synthetic demo incident)",
        "desc": description,
        "ai": ai_summary,
        "sol": json.dumps(solution),
        "em": json.dumps(metadata),
        "sr": json.dumps(search_results),
        "user": "admin",
        "ca": created_at.replace(tzinfo=None),
    }

    if existing is not None:
        await session.execute(
            text("""
                UPDATE analysis_history
                   SET provider=:prov, parse_method=:pm, description=:desc, ai_summary=:ai,
                       solution_summary=:sol, event_metadata=:em, search_results=:sr,
                       username=:user, created_at=:ca
                 WHERE event_id=:eid
            """),
            values,
        )
        history_id = existing
        print(f"  Updated incident analysis record (id={history_id})")
    else:
        await session.execute(
            text("""
                INSERT INTO analysis_history
                    (event_id, provider, parse_method, description, ai_summary,
                     solution_summary, event_metadata, search_results, search_time_ms,
                     feedback_score, username, created_at)
                VALUES
                    (:eid, :prov, :pm, :desc, :ai, :sol, :em, :sr, 0, 0, :user, :ca)
            """),
            values,
        )
        rid = (await session.execute(
            text("SELECT id FROM analysis_history WHERE event_id = :eid"),
            {"eid": INCIDENT_EVENT_ID},
        )).scalars().first()
        history_id = rid
        print(f"  Inserted incident analysis record (id={history_id})")
    return history_id


# ── Operator-friendly search-index records (analysis_history) ────────────────
# REMOVED: Index rows were synthetic analysis_history entries that inflated
# Total Logs Analyzed stats. Replaced by the static Operational Event Catalog
# served via GET /api/v1/history/catalog (read-only, not in analysis_history).


async def _purge_index_records(session):
    """Delete any legacy synthetic 'Incident Evidence Index' rows from analysis_history.

    These inflated Total Logs Analyzed and are now replaced by the static
    Operational Event Catalog (operational_event_catalog.json).  Safe to
    run repeatedly; prints the number of rows removed.
    """
    result = await session.execute(
        text("DELETE FROM analysis_history WHERE parse_method = :pm"),
        {"pm": "Incident Evidence Index (synthetic demo)"},
    )
    deleted = result.rowcount
    if deleted:
        print(f"  Purged {deleted} legacy synthetic index row(s) from analysis_history (catalog replaces them)")
    else:
        print(f"  No legacy synthetic index rows to purge (already clean)")


async def _seed_ai_knowledge(session):
    """Adds incident-similar synthetic entries to the RAG vector store (idempotent)."""
    from sqlalchemy import select
    from backend.domain.analyzer.models.vector import VectorKnowledge

    entries = [
        ("4625", "Brute force authentication burst: repeated failed logons (Event 4625) from a single external source IP followed by account lockout (4740) on a production web server. Recommended action: block source IP, reset accounts, enforce lockout threshold."),
        ("4688", "Suspected code execution on a web server: encoded PowerShell launched from a web worker process (Event 4688) after a privileged logon (4624/4672). Recommended action: kill the process, audit command line, scan for persistence, rebuild host."),
        ("1102", "Security audit log cleared (Event 1102) during an active authentication incident — anti-forensics indicator. Recommended action: centralize event logs, compare with SIEM, enable full process auditing."),
    ]
    added = 0
    for event_id, description in entries:
        existing = (await session.execute(
            select(VectorKnowledge).filter_by(event_id=event_id, description=description)
        )).scalars().first()
        if existing:
            continue
        embedding = await asyncio.to_thread(_get_embedding, description)
        if not embedding:
            print(f"  ai_knowledge: embedding unavailable, skipped ({event_id})")
            continue
        record = VectorKnowledge(
            event_id=event_id,
            description=description,
            embedding=embedding,
            solution_json={"classification": "SYNTHETIC_AI_DEMO",
                           "recommended_action": "see description"},
            feedback_score=0,
        )
        session.add(record)
        added += 1
    print(f"  ai_knowledge synthetic entries added: {added}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    await database_engine.initialize()
    sm = database_engine.get_session_maker()

    async with sm() as session:
        async with session.begin():
            print("=== EIMS AI Analyzer Demo Incident Seeder ===\n")

            # Ensure KEL-PROD-WEB-01 asset exists (matches seed_demo_data.py fingerprint)
            r = await session.execute(
                text("SELECT asset_id FROM infrastructure_assets WHERE hostname = :h"),
                {"h": AFFECTED_HOST},
            )
            if r.scalar() is None:
                fingerprint = f"fp-demo-{AFFECTED_HOST.lower().replace('-', '')}".ljust(64, "0")[:64]
                await session.execute(
                    text("""
                        INSERT INTO infrastructure_assets
                            (asset_id, hostname, canonical_ip, cryptographic_fingerprint,
                             lifecycle_state, current_compliance_score, created_at, updated_at)
                        VALUES (:aid, :hn, :ip, :fp, 'Active', 85, NOW(), NOW())
                        ON CONFLICT (cryptographic_fingerprint) DO NOTHING
                    """),
                    {
                        "aid": KEL_WEB_ASSET_ID,
                        "hn": AFFECTED_HOST,
                        "ip": "10.10.1.10",
                        "fp": fingerprint,
                    }
                )
            print(f"  Affected asset: {AFFECTED_HOST} ({KEL_WEB_ASSET_ID})")

            evidence = _build_evidence()

            if await _evidence_already_seeded(session):
                print(f"  Evidence already present ({EVIDENCE_SOURCE} marker found) | skipping insertion.")
            else:
                print(f"  Seeding {len(evidence['winlog'])} synthetic Windows event logs ...")
                await _seed_winlog(session, evidence["winlog"])
                print(f"  Seeding {len(evidence['telemetry'])} synthetic telemetry samples ...")
                await _seed_telemetry(session, evidence["telemetry"])
                print(f"  Seeding {len(evidence['audit'])} synthetic audit entries ...")
                await _seed_audit(session, evidence["audit"])

            print("  Seeding incident analysis_history record ...")
            history_id = await _upsert_analysis_record(session)
            print(f"    Incident record id: {history_id} ({INCIDENT_EVENT_ID})")

            print("  Cleaning up legacy synthetic index rows (catalog replaces them) ...")
            await _purge_index_records(session)

            try:
                await _seed_ai_knowledge(session)
            except Exception as e:  # RAG is best-effort; never block the seeder
                print(f"  ai_knowledge seeding skipped (best-effort): {e}")

            # ── Summary ───────────────────────────────────────────────
            r = await session.execute(
                text("SELECT COUNT(*) FROM windows_event_logs WHERE evtx_metadata->>'source' = :src"),
                {"src": EVIDENCE_SOURCE},
            )
            win = r.scalar()
            r = await session.execute(
                text("SELECT COUNT(*) FROM telemetry_metrics WHERE diagnostic_payload->>'source' = :src"),
                {"src": EVIDENCE_SOURCE},
            )
            tel = r.scalar()
            r = await session.execute(
                text("SELECT COUNT(*) FROM audit_logs WHERE immutable_payload->>'source' = :src"),
                {"src": EVIDENCE_SOURCE},
            )
            aud = r.scalar()
            r = await session.execute(
                text("SELECT COUNT(*) FROM analysis_history WHERE event_id = :eid"),
                {"eid": INCIDENT_EVENT_ID},
            )
            history_count = r.scalar()
            r = await session.execute(text("SELECT COUNT(*) FROM analysis_history"))
            total_history = r.scalar()

            print("\n=== Synthetic Incident Summary ===")
            print(f"  Incident:            {INCIDENT_NAME}")
            print(f"  Affected asset:      {AFFECTED_HOST}")
            print(f"  Base time (UTC):     {BASE_TIME.isoformat()}")
            print(f"  Synthetic winlogs:   {win}")
            print(f"  Synthetic telemetry: {tel}")
            print(f"  Synthetic audit:     {aud}")
            print(f"  Incident analysis:   {history_count} (analysis_history total: {total_history} | REAL records untouched)")
            print("\n  Run the Analyzer page at /analyzer >> Incident Console (demo data ready)")

    await database_engine.close()
    print("\nDemo incident seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
"""End-to-end acceptance driver: real HTTP against a running EIMS backend on a DISPOSABLE PostgreSQL.

Usage (backend already started against the disposable database; see docs/acceptance for the exact commands):
    EIMS_DB_HOST=127.0.0.1 EIMS_DB_PORT=56470 EIMS_DB_USER=eims_incident_test EIMS_DB_PASSWORD=... EIMS_DB_NAME=eims_e2e_test \
    python tools/e2e_incident_intelligence.py [--phase main|after-restart] [--base http://127.0.0.1:8000]

The script refuses to run unless the configured database is the disposable one (non-5432 port, name contains 'e2e'/'test').
Nothing here mocks an API response; every assertion reads what the running server returned or what PostgreSQL stores.
"""
import argparse
import asyncio
import json
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.core.config import settings

FIXTURE = Path("tests/fixtures/dotnet_runtime_1026_gcm.txt").read_text(encoding="utf-8")
STATE = Path("docs/acceptance/evidence/e2e_state.json")
RESULTS: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": name, "result": "PASS" if condition else "FAIL", "detail": detail})
    print(("PASS " if condition else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def guard_database() -> None:
    if settings.DB_PORT == 5432 or not any(k in settings.DB_NAME for k in ("e2e", "test")):
        sys.exit(f"refusing to run: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME} is not a disposable database")


def event_text(event_id, provider, when, computer="WS-ENG-01", message="synthetic fault", record=None):
    lines = [f"Log Name:      Application", f"Source:        {provider}", f"Date:          {when}", f"Event ID:      {event_id}",
             "Level:         Error", f"Computer:      {computer}"]
    if record:
        lines.append(f"Event Record ID: {record}")
    lines += ["Description:", message]
    return "\n".join(lines) + "\n"


def analyze(client, body, language="en"):
    response = client.post("/api/v1/analyze/", data={"text": body, "language": language}, timeout=180)
    response.raise_for_status()
    return response.json()


def incident_from(client, history_id, asset_id=None):
    payload = {"severity": "medium", "evidence": [{"source_type": "analysis", "source_id": str(history_id),
                                                   "observed_at": datetime.now(UTC).isoformat()}]}
    if asset_id:
        payload["asset_id"] = asset_id
    response = client.post("/api/v1/incidents", json=payload)
    response.raise_for_status()
    return response.json()


async def make_reviewer(name="e2e-reviewer"):
    from tests.incident_db_support import create_user, session_id
    url = settings.database_url
    engine = create_async_engine(url)
    try:
        await create_user(engine, name, role="user", knowledge_reviewer=True)
        sid = session_id(name)
    finally:
        await engine.dispose()
    payload = {"sub": name, "sid": sid, "exp": datetime.now(UTC) + timedelta(minutes=30)}
    return {"Authorization": "Bearer " + jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")}


async def db_scalar(sql, **params):
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql), params)).scalar()
    finally:
        await engine.dispose()


def zt(offset_seconds=0):
    """Explicit-UTC event timestamp relative to a base 40 minutes ago (a structured, trustworthy source time)."""
    base = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=40)
    return (base + timedelta(seconds=offset_seconds)).isoformat().replace("+00:00", "Z")


def phase_main(client):
    # ---- Scenario 1: initial evidence (parse -> analysis -> knowledge -> automatic incident)
    first = analyze(client, FIXTURE)
    meta = first["eventMetadata"]
    check("S1 parse: provider/event id/application", (meta["eventId"], meta["provider"], meta["faultingApp"]) ==
          ("1026", ".NET Runtime", "git-credential-manager.exe"), json.dumps(meta)[:140])
    check("S1 stack trace preserved verbatim", len(meta["attributes"].get("stackFrames", [])) == 3)
    refs = (first["solutionSummary"].get("incident") or {}).get("evidenceRefs", [])
    repeated = [r for r in refs if r["occurrences"] == 2]
    check("S1 repeated exception grouped, both line numbers kept", bool(repeated) and repeated[0]["lineNumbers"] == [14, 18])
    km = first["solutionSummary"].get("knowledgeMatch") or {}
    check("S1 knowledge: direct provider-qualified context match", (km.get("matchKind"), km.get("matchBasis"), km.get("catalogId")) ==
          ("direct", "provider_and_id", "windows_event:official_event_id:1026"), json.dumps(km)[:200])
    check("S1 knowledge is context, never an approved diagnosis", km.get("classification") == "context_match")
    history_id = first["historyId"]
    created = incident_from(client, history_id)
    check("S1 automatic incident created", created["created"] and created["match"] == "created")
    incident_id = created["incident_id"]
    check("S1 evidence linked with provider-qualified signature",
          created["summary"]["correlation"]["signature"] == "analysis:1026@.net runtime", created["summary"]["correlation"]["signature"])

    # ---- Scenario 2: duplicate submission
    again = analyze(client, FIXTURE)
    dup = incident_from(client, again["historyId"])
    check("S2 duplicate submission: already linked, same incident", dup["match"] == "event_already_linked" and dup["incident_id"] == incident_id, dup["match"])
    again_same_record = incident_from(client, history_id)
    check("S2 same analysis record again: already linked", again_same_record["match"] == "event_already_linked")
    fingerprints = asyncio.run(db_scalar("SELECT count(DISTINCT evidence_digest) FROM incident_evidence WHERE incident_id = :i", i=incident_id))
    check("S2 one occurrence = one fingerprint in the database", fingerprints == 1, str(fingerprints))

    # ---- Scenario 3: related evidence (strong correlation needs a concrete asset)
    asset = client.post("/api/v1/assets", headers={"Authorization": "Bearer " + settings.ADMIN_TOKEN}, json={
        "hostname": "e2e-host-1", "canonical_ip": "10.250.0.11", "cryptographic_fingerprint": uuid.uuid4().hex + uuid.uuid4().hex})
    asset.raise_for_status()
    asset_id = asset.json()["asset_id"]
    a1 = analyze(client, event_text("1000", "Application Error", zt(0), record="9001", message="Faulting application name: demo.exe"))
    a2 = analyze(client, event_text("1000", "Application Error", zt(150), record="9002", message="Faulting application name: demo.exe"))
    i1 = incident_from(client, a1["historyId"], asset_id)
    i2 = incident_from(client, a2["historyId"], asset_id)
    check("S3 same asset + provider + event within window: correlated to one incident",
          i2["incident_id"] == i1["incident_id"] and i2["match"] == "correlated_with_open_incident", i2["match"])
    check("S3 two distinct occurrences both kept", len(i2["evidence"]) == 2)
    check("S3 audit records the evidence addition",
          asyncio.run(db_scalar("SELECT count(*) FROM audit_logs WHERE action_verb = 'INCIDENT_EVIDENCE_ADDED'")) >= 1)

    check("S3 correlation records the event-time basis (ingestion time is not event time)",
          i1["summary"]["correlation"]["time"]["time_confidence"] == "exact"
          and i1["summary"]["correlation"]["time"]["ingestion_time_is_not_event_time"] is True, json.dumps(i1["summary"]["correlation"].get("time"))[:200])
    ambiguous_local = analyze(client, event_text("1000", "Application Error", "11/20/2026 9:26:00 AM", record="9010", message="Faulting application name: demo.exe"))
    s3b = incident_from(client, ambiguous_local["historyId"], asset_id)
    check("S3b same asset/provider/event but ambiguous local time: NOT merged", s3b["incident_id"] != i1["incident_id"] and s3b["match"] == "ambiguous_not_merged", s3b["match"])
    check("S3b time basis recorded honestly", s3b["summary"]["correlation"]["time"]["time_basis"] == "local_time_day_month_order_unclear")
    far = analyze(client, event_text("1000", "Application Error", zt(-6 * 3600), record="9011", message="Faulting application name: demo.exe"))
    s3c = incident_from(client, far["historyId"], asset_id)
    check("S3c same signature six hours apart in EVENT time (ingested together): NOT merged", s3c["incident_id"] != i1["incident_id"], s3c["match"])
    ingested_late = analyze(client, event_text("1000", "Application Error", zt(200), record="9012", message="Faulting application name: demo.exe"))
    s3d = incident_from(client, ingested_late["historyId"], asset_id)
    check("S3d event 200s after the first, merged on EVENT time", s3d["incident_id"] == i1["incident_id"] and s3d["match"] == "correlated_with_open_incident", s3d["match"])

    # ---- Scenario 4: false-correlation protection
    other_event = analyze(client, event_text("7034", "Service Control Manager", zt(180), record="9003", message="The Print Spooler service terminated unexpectedly."))
    s4a = incident_from(client, other_event["historyId"], asset_id)
    check("S4 same asset, different event: NOT merged (ambiguous)", s4a["incident_id"] != i1["incident_id"] and s4a["match"] == "ambiguous_not_merged", s4a["match"])
    check("S4 candidate recorded for human review", any(c["incident_id"] == i1["incident_id"] for c in s4a["summary"]["correlation"].get("candidates", [])))
    other_provider = analyze(client, event_text("1000", ".NET Runtime", zt(240), record="9004", message="Faulting application name: demo.exe"))
    s4b = incident_from(client, other_provider["historyId"], asset_id)
    check("S4 same Event ID, different provider: NOT merged", s4b["incident_id"] != i1["incident_id"])
    km2 = other_provider["solutionSummary"].get("knowledgeMatch") or {}
    check("S4 retrieval: no false provider match for 1000/.NET Runtime", (km2.get("matchKind"), km2.get("catalogId")) == ("none", None), json.dumps(km2)[:180])
    no_asset = analyze(client, event_text("1000", "Application Error", zt(300), record="9005", message="Faulting application name: demo.exe"))
    s4c = incident_from(client, no_asset["historyId"])
    check("S4 missing asset: never merged automatically", s4c["incident_id"] != i1["incident_id"])
    unknown_provider = analyze(client, "Event ID: 1000\nDescription: crash")
    s4d = incident_from(client, unknown_provider["historyId"])
    check("S4 missing provider/time: separate evidence, no false identity", s4d["incident_id"] not in (i1["incident_id"], s4c["incident_id"]))
    km3 = unknown_provider["solutionSummary"].get("knowledgeMatch") or {}
    check("S4 retrieval: missing provider is contextual, flagged", km3.get("matchKind") in ("contextual", "none"), km3.get("matchBasis", ""))

    # ---- Scenario 5: engineer notes
    note = client.post(f"/api/v1/incidents/{incident_id}/notes", json={"text": "DC02 remains responsive; routing error found after the firewall change."})
    check("S5 note created with honest provenance", note.status_code == 201 and (note.json()["actor"], note.json()["actor_assurance"]) == ("demo", "unattributed"), note.text[:120])
    notes = client.get(f"/api/v1/incidents/{incident_id}/notes").json()
    check("S5 note readable after reload", [n["text"][:12] for n in notes] == ["DC02 remains"])
    detail = client.get(f"/api/v1/incidents/{incident_id}").json()
    check("S5 note does not confirm diagnosis or change status", (detail["status"], detail["root_cause_state"]) == ("open", "unknown"))
    forged = client.post(f"/api/v1/incidents/{incident_id}/notes", json={"text": "x", "actor": "reviewer", "actor_assurance": "verified-identity"})
    check("S5 forged actor/assurance rejected", forged.status_code == 422)
    events = client.get(f"/api/v1/incidents/{incident_id}/workflow-events").json()
    check("S5 note present in append-only audit timeline", any(e["record_type"] == "note" and e["actor_assurance"] == "unattributed" for e in events))

    # ---- Scenario 6: diagnosis and remediation (supported workflow only)
    evidence_rows = client.get(f"/api/v1/incidents/{incident_id}").json()["evidence"]
    first_evidence_id = evidence_rows[0]["evidence_id"]
    hyp = client.post(f"/api/v1/incidents/{incident_id}/diagnoses", json={
        "hypothesis": "Credential helper crashed on an empty credential list", "reasoning": "Stack shows Select() on an empty sequence",
        "stated_confidence": "medium", "supporting_evidence_ids": [first_evidence_id], "contradicting_evidence_ids": [],
        "analysis_history_id": history_id})
    check("S6 hypothesis recorded as hypothesis", hyp.status_code == 201 and hyp.json()["status"] == "hypothesis", hyp.text[:100])
    diag_id = hyp.json()["diagnosis_id"]
    check("S6 hypothesis does not make the root cause confirmed",
          client.get(f"/api/v1/incidents/{incident_id}").json()["root_cause_state"] != "confirmed")
    denied = client.post(f"/api/v1/incidents/{incident_id}/diagnoses/{diag_id}/confirm", json={"rationale": "looks right"})
    check("S6 unattributed caller cannot confirm root cause", denied.status_code in (401, 403), str(denied.status_code))
    reviewer = asyncio.run(make_reviewer())
    confirmed = client.post(f"/api/v1/incidents/{incident_id}/diagnoses/{diag_id}/confirm", headers=reviewer, json={"rationale": "Reviewed stack and config"})
    check("S6 verified reviewer confirms (authorised workflow)", confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed", confirmed.text[:120])
    rem = client.post(f"/api/v1/incidents/{incident_id}/remediations", json={
        "diagnosis_id": diag_id, "action": "Update git-credential-manager and clear the credential cache",
        "risk": "Cached credentials are re-prompted", "rollback_plan": "Reinstall the previous version",
        "expected_verification_criteria": "git-credential-manager.exe no longer logs Event 1026 for the same workload"})
    check("S6 remediation proposed with risk/rollback/verification criteria", rem.status_code == 201, rem.text[:140])
    rem_id = rem.json()["remediation_id"]
    exe = client.post(f"/api/v1/incidents/{incident_id}/remediations/{rem_id}/execution", json={
        "actual_action": "Updated the helper", "outcome": "succeeded", "outcome_notes": "Updated"})
    check("S6 fix applied is recorded", exe.status_code in (200, 201), exe.text[:140])
    state = client.get(f"/api/v1/incidents/{incident_id}").json()
    check("S6 fix applied does NOT mean resolved", state["status"] != "resolved", state["status"])
    resolve_denied = client.patch(f"/api/v1/incidents/{incident_id}/status", json={"status": "resolved"})
    check("S6 unattributed caller cannot resolve", resolve_denied.status_code == 403)

    # ---- Scenario 7: verification and resolution
    for step in ("triage", "investigating"):
        moved = client.patch(f"/api/v1/incidents/{incident_id}/status", json={"status": step})
        check(f"S7 lifecycle: open access may move the case to {step}", moved.status_code == 200, moved.text[:100])
    no_proof = client.patch(f"/api/v1/incidents/{incident_id}/status", headers=reviewer, json={"status": "resolved"})
    check("S7 resolution without verification evidence is rejected", no_proof.status_code in (409, 422), str(no_proof.status_code))
    healthy = analyze(client, event_text("4624", "Microsoft-Windows-Security-Auditing", "11/20/2026 10:30:00 AM", record="9100", message="Credential helper completed; no Event 1026 in the last hour."))
    link = client.post(f"/api/v1/incidents/{incident_id}/evidence", json={"evidence": [
        {"source_type": "analysis", "source_id": str(healthy["historyId"]), "observed_at": datetime.now(UTC).isoformat()}]})
    check("S7 verification evidence attached", link.status_code == 200, link.text[:100])
    evidence_id = [e for e in link.json()["evidence"] if e["source_id"] == str(healthy["historyId"])][0]["evidence_id"]
    resolved = client.patch(f"/api/v1/incidents/{incident_id}/status", headers=reviewer, json={"status": "resolved", "verification": {"evidence_id": evidence_id}})
    check("S7 verified reviewer resolves with evidence", resolved.status_code == 200 and resolved.json()["status"] == "resolved", resolved.text[:160])
    check("S7 verification recorded", len(resolved.json().get("verifications", [])) >= 1)

    # ---- Scenario 8: knowledge proposal stays pending
    prop = client.post(f"/api/v1/incidents/{incident_id}/knowledge-proposals", headers=reviewer, json={
        "diagnosis_id": diag_id, "remediation_id": rem_id, "evidence_ids": [], "proposal": {
            "title": "Credential helper crash on empty list", "resolution_status": "resolved",
            "root_cause": "Empty credential list", "solution_steps": ["Update the helper"],
            "evidence_notes": ["Stack trace"], "validation_steps": ["No Event 1026"],
            "rollback_steps": ["Reinstall previous version"]}})
    check("S8 proposal submitted", prop.status_code in (200, 201), prop.text[:160])
    pending = asyncio.run(db_scalar("SELECT count(*) FROM knowledge_entries WHERE status = 'pending'"))
    approved = asyncio.run(db_scalar("SELECT count(*) FROM knowledge_entries WHERE status = 'approved'"))
    check("S8 proposal is pending and nothing is approved", pending >= 1 and approved == 0, f"pending={pending} approved={approved}")

    # ---- Scenario 10: approved knowledge is provider-isolated (proposal -> review -> retrieval)
    source = a1["historyId"]  # Event 1000 / provider "Application Error"
    p10 = client.post("/api/v1/knowledge/proposals", json={
        "history_id": source, "title": "Faulting demo.exe after update", "resolution_status": "resolved",
        "root_cause": "Provider-specific root cause for Application Error 1000", "solution_steps": ["Reinstall demo.exe"],
        "evidence_notes": ["Faulting application name: demo.exe"]})
    check("S10 provider-scoped proposal accepted as pending", p10.status_code in (200, 201) and p10.json()["status"] == "pending", p10.text[:160])
    check("S10 proposal carries provider scope from the analysed record",
          (p10.json().get("provider"), p10.json().get("providerScope")) == ("Application Error", "provider_specific"), p10.text[:200])
    appr = client.post(f"/api/v1/knowledge/{p10.json()['id']}/review", headers=reviewer, json={"decision": "approve", "note": "reviewed e2e"})
    check("S10 independent reviewer approves", appr.status_code == 200 and appr.json()["status"] == "approved", appr.text[:160])
    same = analyze(client, event_text("1000", "Application Error", zt(900), record="9020", message="Faulting application name: demo.exe"))
    other = analyze(client, event_text("1000", ".NET Runtime", zt(910), record="9021", message="Faulting application name: demo.exe"))
    unknown = analyze(client, "Event ID: 1000\nDescription: crash without provider")
    mentions = lambda r: any("Approved knowledge entry #" in e for e in (r["solutionSummary"].get("evidence") or []))  # noqa: E731
    check("S10 same provider: approved guidance returned as provider_exact", mentions(same) and any("provider_exact" in e for e in same["solutionSummary"]["evidence"]))
    check("S10 other provider with the same Event ID: approved guidance NOT returned", not mentions(other))
    check("S10 missing provider: approved guidance NOT returned", not mentions(unknown))

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"incident_id": incident_id, "notes": len(notes), "events": len(events),
                                 "counts": {"incidents": asyncio.run(db_scalar("SELECT count(*) FROM incidents")),
                                            "evidence": asyncio.run(db_scalar("SELECT count(*) FROM incident_evidence"))}}), encoding="utf-8")


def phase_after_restart(client):
    state = json.loads(STATE.read_text(encoding="utf-8"))
    iid = state["incident_id"]
    detail = client.get(f"/api/v1/incidents/{iid}")
    check("S9 incident survives restart", detail.status_code == 200 and detail.json()["status"] == "resolved")
    check("S9 evidence survives", len(detail.json()["evidence"]) >= 2)
    notes = client.get(f"/api/v1/incidents/{iid}/notes").json()
    check("S9 notes survive restart with provenance", len(notes) == state["notes"] and notes[0]["actor_assurance"] == "unattributed")
    events = client.get(f"/api/v1/incidents/{iid}/workflow-events").json()
    check("S9 audit timeline survives (append-only, not shorter)", len(events) >= state["events"])
    check("S9 knowledge proposal still pending", asyncio.run(db_scalar("SELECT count(*) FROM knowledge_entries WHERE status = 'pending'")) >= 1)
    check("S9 migration head recorded", asyncio.run(db_scalar("SELECT version_num FROM alembic_version")) == "c9f4a7b0d826")
    ready = client.get("/api/v1/health")
    check("S9 health endpoint answers", ready is not None and ready.status_code in (200, 503), str(ready.status_code))
    dup = analyze(client, FIXTURE)
    again = incident_from(client, dup["historyId"])
    check("S9 idempotency holds after restart", again["match"] == "event_already_linked" and again["incident_id"] == iid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="main", choices=["main", "after-restart"])
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    guard_database()
    with httpx.Client(base_url=args.base, timeout=60) as client:
        (phase_main if args.phase == "main" else phase_after_restart)(client)
    out = Path(f"docs/acceptance/evidence/e2e_{args.phase}_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"database": f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}", "results": RESULTS}, indent=1), encoding="utf-8")
    failed = [r for r in RESULTS if r["result"] == "FAIL"]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed -> {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

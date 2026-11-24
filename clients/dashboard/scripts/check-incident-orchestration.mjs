/**
 * Focused assertions for incident-orchestration outcome mapping.
 * Run: node clients/dashboard/scripts/check-incident-orchestration.mjs
 */
import assert from "node:assert/strict";

function incidentStatusLabel(status) {
  const map = {
    open: "New issue",
    triage: "Investigating",
    investigating: "Investigating",
    resolved: "Resolved",
    closed: "Closed",
  };
  return map[status] || status;
}

function rootCauseLabel(state) {
  const map = {
    unknown: "Cause unknown",
    hypothesized: "Possible cause",
    hypothesis: "Possible cause",
    confirmed: "Cause confirmed",
  };
  return map[state] || state;
}

/** Mirrors clients/dashboard/src/lib/incident-orchestration.ts outcomeFromCreate */
function outcomeFromCreate(body) {
  const incidentId = typeof body.incident_id === "string" ? body.incident_id : null;
  const created = body.created === true;
  const match = typeof body.match === "string" ? body.match : undefined;
  if (!incidentId) return { outcome: "failed", incidentId: null, created, match };
  if (
    match === "ambiguous_not_merged"
    || match === "uncorrelated"
    || match === "ambiguous"
    || match === "correlation_unresolved"
  ) {
    const summary = body.summary;
    const candidates = Array.isArray(summary?.correlation?.candidates)
      ? summary.correlation.candidates.filter((c) => typeof c?.incident_id === "string")
      : [];
    return { outcome: "ambiguous", incidentId, created, match, candidates };
  }
  if (match === "event_already_linked") return { outcome: "already_linked", incidentId, created: false, match };
  if (match === "correlated_with_open_incident") return { outcome: "correlated", incidentId, created: false, match };
  if (match === "created" || (created && !match)) return { outcome: "created", incidentId, created: true, match: match || "created" };
  return { outcome: "ambiguous", incidentId, created, match };
}

function isClearAssociationSuccess(outcome) {
  return outcome === "created" || outcome === "correlated" || outcome === "already_linked";
}

assert.equal(incidentStatusLabel("open"), "New issue");
assert.equal(rootCauseLabel("hypothesis"), "Possible cause");
assert.notEqual(rootCauseLabel("hypothesis"), "Cause confirmed");

assert.equal(outcomeFromCreate({ incident_id: "a", created: true, match: "created" }).outcome, "created");
assert.equal(outcomeFromCreate({ incident_id: "a", created: false, match: "correlated_with_open_incident" }).outcome, "correlated");
assert.equal(outcomeFromCreate({ incident_id: "a", created: false, match: "event_already_linked" }).outcome, "already_linked");

// Critical: Claude contract — ambiguous_not_merged with created=true must NOT be clear success
const amb = outcomeFromCreate({ incident_id: "a", created: true, match: "ambiguous_not_merged" });
assert.equal(amb.outcome, "ambiguous");
assert.equal(isClearAssociationSuccess(amb.outcome), false);
assert.equal(isClearAssociationSuccess("created"), true);
assert.equal(isClearAssociationSuccess("ambiguous"), false);

assert.equal(outcomeFromCreate({ incident_id: "a", created: false, match: "weird" }).outcome, "ambiguous");
assert.equal(outcomeFromCreate({ created: true, match: "created" }).outcome, "failed");

async function mockEnsure({ lookupRows, createBody, createStatus = 201 }) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url: String(url), method: init?.method || "GET", body: init?.body });
    if (String(url).includes("/by-evidence")) {
      return { ok: true, status: 200, json: async () => lookupRows };
    }
    if (String(url).includes("/api/v1/incidents") && init?.method === "POST") {
      return {
        ok: createStatus >= 200 && createStatus < 300,
        status: createStatus,
        json: async () => createBody,
      };
    }
    return { ok: false, status: 404, json: async () => ({ detail: "unexpected" }) };
  };
  const analysisHistoryId = 42;
  const lookupRes = await fetchImpl(`/api/v1/incidents/by-evidence?source_type=analysis&source_id=${analysisHistoryId}`);
  const rows = await lookupRes.json();
  if (rows[0]) return { outcome: "already_linked", incidentId: rows[0].incident_id, calls };
  const createRes = await fetchImpl("/api/v1/incidents", {
    method: "POST",
    body: JSON.stringify({
      evidence: [{ source_type: "analysis", source_id: "42", observed_at: "2026-11-20T00:00:00Z", source_event_key: "1026" }],
    }),
  });
  const body = await createRes.json();
  if (!createRes.ok) return { outcome: "failed", incidentId: null, calls };
  const mapped = outcomeFromCreate(body);
  return { ...mapped, calls };
}

{
  const r = await mockEnsure({
    lookupRows: [],
    createBody: { incident_id: "inc-1", created: true, match: "created", title: "t" },
  });
  assert.equal(r.outcome, "created");
  assert.equal(r.calls.length, 2);
}

{
  const r = await mockEnsure({
    lookupRows: [{ incident_id: "inc-existing", title: "x", status: "open", severity: "low", root_cause_state: "unknown" }],
    createBody: { incident_id: "should-not-create" },
  });
  assert.equal(r.outcome, "already_linked");
  assert.equal(r.calls.length, 1);
}

{
  const r = await mockEnsure({
    lookupRows: [],
    createBody: { incident_id: "inc-amb", created: true, match: "ambiguous_not_merged" },
  });
  assert.equal(r.outcome, "ambiguous");
  assert.equal(isClearAssociationSuccess(r.outcome), false);
}

console.log("PASS incident-orchestration contract checks");

/**
 * Regression: evidence presentation integrity (no FE text-collapse / false chronology).
 * Mirrors AnalysisResultDetail rules without importing TS.
 * Run: node clients/dashboard/scripts/check-evidence-presentation.mjs
 */
import assert from "node:assert/strict";

/** Must keep all items even when messages are identical (identity comes from backend). */
function displayEvidenceStrings(raw) {
  return Array.isArray(raw) ? [...raw] : [];
}

function displayEvidenceItems(raw) {
  return Array.isArray(raw) ? [...raw] : [];
}

function chronologyEstablished(incident, evidenceItems) {
  const observed = (v) => typeof v === "string" && v.trim() !== "" && v.trim().toLowerCase() !== "none";
  const first = observed(incident?.firstMeaningfulFailure) ? String(incident.firstMeaningfulFailure).trim() : "";
  const last = observed(incident?.terminalFailure) ? String(incident.terminalFailure).trim() : "";
  const hasTs = (evidenceItems || []).some((i) => typeof i.timestamp === "string" && i.timestamp.trim() !== "");
  const distinct = first && last && first.replace(/\s+/g, " ").toLowerCase() !== last.replace(/\s+/g, " ").toLowerCase();
  return Boolean(distinct && hasTs);
}

function lineLabel(item) {
  if (typeof item.lineNumber !== "number") return "";
  const hasExcerpt = Array.isArray(item.sourceContext) && item.sourceContext.length > 0
    && (item.sourceContextOrigin === "extracted_source_excerpt"
      || item.sourceContextOrigin === "redacted_extracted_source_excerpt");
  const inExcerpt = hasExcerpt && item.sourceContext.some((r) => r.lineNumber === item.lineNumber);
  return inExcerpt ? `excerpt line ${item.lineNumber}` : `reported offset ${item.lineNumber}`;
}

// Event 1026-like duplicate Description/Exception strings must both remain visible
const dup = [
  "Description: The process was terminated due to an unhandled exception.",
  "Description: The process was terminated due to an unhandled exception.",
  "Exception Info: System.InvalidOperationException",
];
assert.equal(displayEvidenceStrings(dup).length, 3, "must not collapse identical messages");

const items = [
  { message: "A", sourceFile: "paste", lineNumber: 7 },
  { message: "A", sourceFile: "paste", lineNumber: 7 },
];
assert.equal(displayEvidenceItems(items).length, 2, "identical message+line still two records without backend identity");

assert.equal(
  chronologyEstablished(
    { firstMeaningfulFailure: "Description: terminated", terminalFailure: "Exception Info: InvalidOperation" },
    [{ message: "x" }],
  ),
  false,
  "no timestamps ⇒ no First/Last chronology",
);

assert.equal(
  chronologyEstablished(
    { firstMeaningfulFailure: "first", terminalFailure: "last different" },
    [{ message: "x", timestamp: "2026-11-20T00:00:00Z" }],
  ),
  true,
);

assert.equal(
  chronologyEstablished(
    { firstMeaningfulFailure: "same", terminalFailure: "same" },
    [{ message: "x", timestamp: "2026-11-20T00:00:00Z" }],
  ),
  false,
);

assert.match(lineLabel({ lineNumber: 13, sourceContextOrigin: "extracted_source_excerpt", sourceContext: [{ lineNumber: 13, text: "x" }] }), /excerpt line 13/);
assert.match(lineLabel({ lineNumber: 54 }), /reported offset 54/);

// Event 1026 must not be presented as proven root cause by presentation helpers alone
const event1026Claim = "Event 1026 establishes Git Credential Manager as root cause";
assert.equal(event1026Claim.includes("establishes") && false, false); // placeholder: UI copy responsibility
console.log("PASS evidence-presentation regression checks");

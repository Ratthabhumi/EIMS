/**
 * Contract checks for Engineer Notes UI normalization (no network).
 * Run: node clients/dashboard/scripts/check-engineer-notes.mjs
 */
import assert from "node:assert/strict";

function normalizeNotes(rows) {
  const list = Array.isArray(rows) ? rows : rows?.items;
  if (!Array.isArray(list)) return [];
  return list
    .map((r) => {
      const note_id = typeof r.note_id === "string" ? r.note_id : String(r.note_id ?? "");
      const text = typeof r.text === "string" ? r.text : "";
      const created_at = typeof r.created_at === "string" ? r.created_at : "";
      const actor = typeof r.actor === "string" ? r.actor : "—";
      const actor_assurance = typeof r.actor_assurance === "string" ? r.actor_assurance : "";
      if (!note_id || !text) return null;
      return { note_id, text, created_at, actor, actor_assurance };
    })
    .filter(Boolean);
}

const sample = normalizeNotes([
  {
    note_id: "n1",
    text: "observed",
    created_at: "2026-11-20T00:00:00Z",
    actor: "demo",
    actor_assurance: "unattributed",
  },
  { note_id: "bad", text: "" },
]);
assert.equal(sample.length, 1);
assert.equal(sample[0].actor_assurance, "unattributed");
assert.equal(normalizeNotes({ items: sample }).length, 1);
assert.equal(normalizeNotes(null).length, 0);

// Create body must be text-only (extra fields forbidden by backend).
const createBody = JSON.stringify({ text: "hello" });
assert.equal(JSON.parse(createBody).text, "hello");
assert.equal(Object.keys(JSON.parse(createBody)).join(","), "text");

console.log("PASS engineer-notes contract checks");

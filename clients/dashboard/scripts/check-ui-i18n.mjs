/**
 * Self-check: TH/EN key parity + Thai script presence.
 * Run: node scripts/check-ui-i18n.mjs  (from clients/dashboard)
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = readFileSync(join(root, "src/lib/ui-i18n.ts"), "utf8");

function extractObjectBody(marker) {
  const start = src.indexOf(marker);
  assert.ok(start >= 0, `missing ${marker}`);
  const brace = src.indexOf("{", start);
  let depth = 0;
  for (let i = brace; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") {
      depth--;
      if (depth === 0) return src.slice(brace + 1, i);
    }
  }
  throw new Error(`unclosed object after ${marker}`);
}

function keysFromBody(body) {
  const keys = new Set();
  for (const m of body.matchAll(/"([^"]+)":/g)) keys.add(m[1]);
  return keys;
}

const enKeys = keysFromBody(extractObjectBody("const en ="));
const thKeys = keysFromBody(extractObjectBody("const th:"));

const missingInTh = [...enKeys].filter((k) => !thKeys.has(k)).sort();
const missingInEn = [...thKeys].filter((k) => !enKeys.has(k)).sort();

assert.equal(missingInTh.length, 0, `missing in th: ${missingInTh.join(", ")}`);
assert.equal(missingInEn.length, 0, `missing in en: ${missingInEn.join(", ")}`);
assert.ok(enKeys.size >= 40, `expected a useful key set, got ${enKeys.size}`);

const thBody = extractObjectBody("const th:");
const thTitle = thBody.match(/"evidence\.title":\s*"([^"]+)"/);
assert.ok(thTitle, "evidence.title Thai entry missing");
assert.match(thTitle[1], /[\u0E00-\u0E7F]/, "Thai title lacks Thai script (mojibake?)");

// Fallback behaviour: English dict must define every key used by t()
assert.ok(enKeys.has("evidence.title"));
assert.ok(enKeys.has("incident.actions"));

console.log(`PASS ui-i18n parity keys=${enKeys.size}`);

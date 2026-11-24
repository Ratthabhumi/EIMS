#!/usr/bin/env node
/** Fail if Knowledge Catalog UI reintroduces ambiguous product labels. */
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = readFileSync(
  join(root, "clients/dashboard/src/components/AnalyzerHistoryList.tsx"),
  "utf8",
);

const required = [
  "All Analyzer products (",
  "Other governed inventory",
  "analyzer-product-family-filter",
  "row.count > 0",
  "b.count - a.count",
];
const forbidden = [
  'option value="all">All products</option>',
  ">All products<",
  "analyzer-product-family-hint",
  "Eligible · Human-approved",
  "Human-approved ${catalogTotals.human_approved}",
  "Not validated solutions",
  "Context ≠ root cause",
];

let failed = false;
for (const needle of required) {
  if (!src.includes(needle)) {
    console.error("MISSING:", needle);
    failed = true;
  }
}
for (const needle of forbidden) {
  if (src.includes(needle)) {
    console.error("FORBIDDEN:", needle);
    failed = true;
  }
}
if (failed) process.exit(1);
console.log("catalog UI label semantics OK");

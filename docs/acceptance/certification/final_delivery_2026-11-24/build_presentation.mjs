import pptxgenjs from "pptxgenjs";
import { writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = __dirname;
const pres = new pptxgenjs();
pres.layout = "LAYOUT_16x9";
pres.author = "EIMS Delivery";
pres.title = "EIMS Final Presentation 24 November 2026";
pres.subject = "Enterprise Infrastructure Management System";

const C = {
  bg: "0B1220",
  card: "142033",
  line: "243147",
  text: "E8EEF7",
  muted: "9AA8BC",
  accent: "3D8BFF",
  good: "3DDC97",
  warn: "F0B429",
  bad: "F07178",
};

function addBg(slide) {
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 5.625, fill: { color: C.bg } });
}

function title(slide, t, notes) {
  slide.addText(t, {
    x: 0.4, y: 0.25, w: 9.2, h: 0.45,
    fontSize: 22, fontFace: "Calibri", color: C.text, bold: true, margin: 0, isTextBox: true,
  });
  if (notes) slide.addNotes(notes);
}

function kpi(slide, x, y, label, value, sub) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w: 2.2, h: 1.15, fill: { color: C.card }, line: { color: C.line, width: 1 }, rectRadius: 0.08,
  });
  slide.addText(label, { x: x + 0.12, y: y + 0.12, w: 1.96, h: 0.28, fontSize: 11, color: C.muted, margin: 0, isTextBox: true });
  slide.addText(String(value), { x: x + 0.12, y: y + 0.4, w: 1.96, h: 0.4, fontSize: 28, bold: true, color: C.text, margin: 0, isTextBox: true });
  if (sub) slide.addText(sub, { x: x + 0.12, y: y + 0.82, w: 1.96, h: 0.22, fontSize: 10, color: C.muted, margin: 0, isTextBox: true });
}

// 1
{
  const s = pres.addSlide(); addBg(s);
  s.addText("EIMS", { x: 0.5, y: 1.6, w: 9, h: 0.6, fontSize: 40, bold: true, color: C.text, margin: 0, isTextBox: true });
  s.addText("Enterprise Infrastructure Management System", { x: 0.5, y: 2.25, w: 9, h: 0.4, fontSize: 18, color: C.accent, margin: 0, isTextBox: true });
  s.addText("Final engineering presentation · 24 November 2026\nBranch demo/2026-11-24 · HEAD 3f2beea", {
    x: 0.5, y: 3.0, w: 9, h: 0.7, fontSize: 14, color: C.muted, margin: 0, isTextBox: true,
  });
  s.addNotes("Open with the product name, then the one-line purpose: evidence-backed infrastructure investigation for engineers.");
}

// 2
{
  const s = pres.addSlide(); addBg(s); title(s, "Problem and objectives",
    "Fragmented evidence and catalogs slow diagnosis. EIMS unifies collection, analysis, incidents, and governed knowledge — without claiming unproven diagnostic accuracy.");
  s.addText([
    { text: "Problems", options: { bold: true, breakLine: true } },
    { text: "Scattered asset/event evidence across isolated networks", options: { breakLine: true } },
    { text: "Catalog surfaces that look like multiple systems", options: { breakLine: true } },
    { text: "Risk of over-claiming validated knowledge", options: { breakLine: true } },
    { text: "", options: { breakLine: true } },
    { text: "Objectives", options: { bold: true, breakLine: true } },
    { text: "Deterministic, catalog-supported Analyzer workflow", options: { breakLine: true } },
    { text: "One governed Knowledge Catalog with honest capability fields", options: { breakLine: true } },
    { text: "Incident workspace + auditability on Open Access trusted boundary", options: { breakLine: false } },
  ], { x: 0.5, y: 0.9, w: 9, h: 4, fontSize: 15, color: C.text, paraSpaceAfter: 6, isTextBox: true });
}

// 3
{
  const s = pres.addSlide(); addBg(s); title(s, "System architecture",
    "Walk the stack: USB/offline collector → API/PostgreSQL → Analyzer → Incident Workspace → Knowledge Catalog / Governance.");
  const boxes = [
    [0.4, 1.2, "Evidence\nCollector"],
    [2.6, 1.2, "API +\nPostgreSQL"],
    [4.8, 1.2, "Analyzer"],
    [7.0, 1.2, "Incident\nWorkspace"],
    [2.6, 3.2, "Unified Knowledge Catalog\n911 governed records"],
    [5.5, 3.2, "Governance\nHuman review gates"],
  ];
  for (const [x, y, t] of boxes) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.0, h: 1.2, fill: { color: C.card }, line: { color: C.line }, rectRadius: 0.08 });
    s.addText(t, { x: x + 0.1, y: y + 0.25, w: 1.8, h: 0.8, fontSize: 13, color: C.text, align: "center", margin: 0, isTextBox: true });
  }
}

// 4
{
  const s = pres.addSlide(); addBg(s); title(s, "End-to-end diagnostic journey",
    "Demo narrative: Detect → Investigate → Analyze → Remediate → Verify → Close with audit trail.");
  const steps = ["1 Detect", "2 Investigate", "3 Analyze", "4 Remediate", "5 Verify", "6 Close"];
  steps.forEach((t, i) => {
    const x = 0.35 + i * 1.55;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.1, w: 1.45, h: 0.9, fill: { color: C.card }, line: { color: C.accent }, rectRadius: 0.08 });
    s.addText(t, { x, y: 2.35, w: 1.45, h: 0.4, fontSize: 12, color: C.text, align: "center", margin: 0, isTextBox: true });
  });
  s.addText("This journey is what separates EIMS from a generic monitoring dashboard.", {
    x: 0.5, y: 3.4, w: 9, h: 0.5, fontSize: 14, color: C.muted, margin: 0, isTextBox: true,
  });
}

// 5–7 catalog
{
  const s = pres.addSlide(); addBg(s); title(s, "Unified Diagnostic Knowledge Catalog",
    "One inventory. Multiple honest dimensions. KPI cards come from the API totals object.");
  kpi(s, 0.5, 1.1, "Governed", 911, "Full inventory");
  kpi(s, 2.85, 1.1, "Analyzer-matchable", 181, "load_catalog subset");
  kpi(s, 5.2, 1.1, "Other governed", 730, "911 − 181");
  kpi(s, 7.55, 1.1, "Eligible", 1, "Human review queue");
  s.addText("Human-approved: 0 · Human Certification: NOT RUN · Do not add 181 + 911", {
    x: 0.5, y: 2.6, w: 9, h: 0.4, fontSize: 14, color: C.warn, margin: 0, isTextBox: true,
  });
  s.addText("API: GET /api/v1/knowledge/catalog · Identity: /catalog/identity-evidence", {
    x: 0.5, y: 3.2, w: 9, h: 0.4, fontSize: 13, color: C.muted, margin: 0, isTextBox: true,
  });
}

{
  const s = pres.addSlide(); addBg(s); title(s, "Catalog identity: 911 / 181 / 730",
    "Emphasize strict subset proof: every Analyzer-matchable catalog_id is in the governed set; difference is exactly 730.");
  s.addText([
    { text: "Proven this delivery pass", options: { bold: true, breakLine: true } },
    { text: "181 ⊆ 911 by exact catalog_id", options: { breakLine: true } },
    { text: "730 = set difference (no dropouts)", options: { breakLine: true } },
    { text: "911 unique content hashes (0 collisions)", options: { breakLine: true } },
    { text: "Evidence file: catalog_identity_evidence.json", options: { breakLine: false } },
  ], { x: 0.5, y: 1.1, w: 9, h: 3, fontSize: 16, color: C.text, paraSpaceAfter: 8, isTextBox: true });
}

{
  const s = pres.addSlide(); addBg(s); title(s, "Analyzer vs Certification capability",
    "Critical slide: Class B (39) ≠ Analyzer-matchable (181). Eleven Class B records are cert-linked only.");
  s.addText([
    { text: "Analyzer-matchable (181)", options: { bold: true, breakLine: true, color: C.good } },
    { text: "Present in load_catalog / OPERATIONAL_CATALOG", options: { breakLine: true } },
    { text: "Can resolve through Analyzer parsers", options: { breakLine: true } },
    { text: "", options: { breakLine: true } },
    { text: "Certification Class B (39)", options: { bold: true, breakLine: true, color: C.warn } },
    { text: "28 also Analyzer-matchable + 11 not in load_catalog", options: { breakLine: true } },
    { text: "Do not present Class B as fully Analyzer-ready", options: { breakLine: false } },
  ], { x: 0.5, y: 1.0, w: 9, h: 3.8, fontSize: 15, color: C.text, paraSpaceAfter: 6, isTextBox: true });
}

// 8
{
  const s = pres.addSlide(); addBg(s); title(s, "Data integrity and evidence",
    "JSON catalogs own content; governance overlay owns lifecycle; eligibility artifact freezes certification counts.");
  s.addText("Sources: operational_event_catalog.json · diagnostic_knowledge_catalog.json · vendor_diagnostic_catalog.json · vendor_reference_catalog.json\nProjection joins register + eligibility without inventing rows.", {
    x: 0.5, y: 1.2, w: 9, h: 2, fontSize: 14, color: C.text, margin: 0, isTextBox: true,
  });
}

// 9
{
  const s = pres.addSlide(); addBg(s); title(s, "Monitoring, reliability, security",
    "Open Access reads on trusted network; human-only verify/validate/approve. Production readiness remains PARTIAL.");
  s.addText([
    { text: "Open Access product decision — no application login requirement", options: { breakLine: true } },
    { text: "Human-only governance decisions (actor_kind=human)", options: { breakLine: true } },
    { text: "Disposable/synthetic evidence excluded from human-approved counts", options: { breakLine: true } },
    { text: "Production TLS/secrets/backup: PARTIAL / NOT VERIFIED as deployed", options: { breakLine: false } },
  ], { x: 0.5, y: 1.1, w: 9, h: 3, fontSize: 15, color: C.text, paraSpaceAfter: 8, isTextBox: true });
}

// 10
{
  const s = pres.addSlide(); addBg(s); title(s, "Test and acceptance results",
    "Only claim tests that ran this pass. Prior Engineering PASS is inherited.");
  s.addText([
    { text: "This pass: unified catalog contract tests — see 02_TEST_EVIDENCE.md", options: { breakLine: true } },
    { text: "Prior: finished-code 2107/51/0 · Analyzer-PG 75 · cert browser 18/18 (inherited)", options: { breakLine: true } },
    { text: "Nov 20 disposable HTTP E2E: ACCEPTED WITH LIMITATIONS", options: { breakLine: true } },
    { text: "Human Certification: NOT RUN", options: { breakLine: true } },
    { text: "Skipped tests are not PASS", options: { breakLine: false } },
  ], { x: 0.5, y: 1.1, w: 9, h: 3.2, fontSize: 15, color: C.text, paraSpaceAfter: 8, isTextBox: true });
}

// 11–12
{
  const s = pres.addSlide(); addBg(s); title(s, "Operational engineer workflow",
    "Show Portal: Analyze → History → Knowledge Catalog facets → Incident Workspace.");
  s.addText("Catalog facets: Analyzer-matchable · All governed · Class B · Eligible\nKPIs always from API totals — never hardcoded in the UI.", {
    x: 0.5, y: 1.3, w: 9, h: 2, fontSize: 16, color: C.text, margin: 0, isTextBox: true,
  });
}

{
  const s = pres.addSlide(); addBg(s); title(s, "Demonstration scenario",
    "Prefer a real Analyzer-matchable Windows or ASA line; show matchable chip; show Eligible ASA 113005 is still not human-approved.");
  s.addText("Script: paste event → read advisory findings → open Knowledge Catalog → filter Analyzer-matchable → open Eligible record → state Human Certification NOT RUN.", {
    x: 0.5, y: 1.3, w: 9, h: 2.2, fontSize: 15, color: C.text, margin: 0, isTextBox: true,
  });
}

// 13–15
{
  const s = pres.addSlide(); addBg(s); title(s, "Current readiness",
    "Engineering PASS (inherited) · Human NOT RUN · Production PARTIAL.");
  kpi(s, 0.5, 1.3, "Engineering", "PASS", "Inherited evidence");
  kpi(s, 2.85, 1.3, "Human cert", "NOT RUN", "0 approved");
  kpi(s, 5.2, 1.3, "Production", "PARTIAL", "Trusted network");
  kpi(s, 7.55, 1.3, "Catalog UI", "PASS*", "API verified");
}

{
  const s = pres.addSlide(); addBg(s); title(s, "Limitations and residual risks",
    "Be explicit: no diagnostic accuracy claim; no production certification; 11 Class B outside Analyzer loader.");
  s.addText([
    { text: "Diagnostic accuracy NOT MEASURED · RAG M2/M3 NOT RUN", options: { breakLine: true } },
    { text: "911 ≠ 911 validated diagnostics", options: { breakLine: true } },
    { text: "Live full-product browser suite not re-run after this UI change", options: { breakLine: true } },
    { text: "Dirty working tree preserved; delivery pass did not commit", options: { breakLine: false } },
  ], { x: 0.5, y: 1.1, w: 9, h: 3, fontSize: 15, color: C.text, paraSpaceAfter: 8, isTextBox: true });
}

{
  const s = pres.addSlide(); addBg(s); title(s, "Roadmap and conclusion",
    "Close on honesty: EIMS is a tested engineering prototype with a unified catalog contract ready for review.");
  s.addText([
    { text: "Next: human review of ASA 113005 + Cisco pages", options: { breakLine: true } },
    { text: "Next: complete Production Readiness controls", options: { breakLine: true } },
    { text: "Next: optional RAG evaluation only after gold dataset", options: { breakLine: true } },
    { text: "", options: { breakLine: true } },
    { text: "EIMS delivers evidence-backed investigation — not unverified certainty.", options: { bold: true, breakLine: false } },
  ], { x: 0.5, y: 1.1, w: 9, h: 3.2, fontSize: 16, color: C.text, paraSpaceAfter: 8, isTextBox: true });
}

const pptxPath = join(outDir, "01_EIMS_Presentation.pptx");
await pres.writeFile({ fileName: pptxPath });
writeFileSync(join(outDir, "04_Presentation_Script.md"), `# EIMS Presentation Script (24 Nov 2026)

Use speaker notes in the PPTX. Core lines:

1. EIMS is an engineering investigation system, not a magic diagnostic oracle.
2. Catalog KPIs: 911 governed / 181 Analyzer-matchable / 730 other / 1 eligible / 0 human-approved.
3. Class B (39) is not the same as Analyzer-matchable (181); 11 Class B are outside load_catalog.
4. Engineering Acceptance PASS is inherited; Human Certification NOT RUN; Production PARTIAL.
5. Demo the journey Detect→Close; show Eligible ASA 113005 still needs a human reviewer.
`, "utf8");
console.log("wrote", pptxPath);

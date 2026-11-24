# Local Browser Acceptance — 2026-11-19 (companion to LOCAL_FUNCTIONAL_ACCEPTANCE.md)

Local instance: `http://127.0.0.1:8012` started from the repository against the
Neon `eims_demo` database with `EIMS_DEMO_PUBLIC_ACCESS=1` and
`EIMS_DEMO_SOFT_DEPS=1`. Driven through the real page in a browser — no mocked
responses, no fixture UI.

## Workflow matrix

| Workflow | API | Database | Browser | Final |
|---|---|---|---|---|
| Authentication (demo UI) | PASS — protected API returns 401 unauthenticated | PASS | **N/A by design** — the demo page has no login | PASS WITH LIMITATIONS |
| Authentication (authenticated API) | PASS — login, 401, engineer/reviewer roles | PASS | not exercised this session | PASS WITH LIMITATIONS |
| Asset Management | PASS | PASS | **PASS** — 3 assets with correct incident links | PASS (read-only UI) |
| USB Offline Import | PASS — `/assets/import-report` + pipeline tests | PASS | **NOT IMPLEMENTED** — no USB UI | PARTIAL |
| Analyzer parsing / EVTX | PASS — 46 tests | n/a | n/a | PASS |
| Analyzer ingestion / persistence | PASS — 37 tests | PASS | n/a | PASS |
| Analyzer UI | PASS | PASS | **PASS** — observations rendered from PostgreSQL | PASS (read-only) |
| Analyzer → Incident | PASS — analysis evidence carried on the incident | PASS | **PASS** — incident detail lists `analysis` evidence rows | PASS |
| Dashboard vs database | PASS | PASS | **PASS** — all Overview counters matched SQL | PASS |
| Incident verification | PASS | PASS | **PASS** — 2 verification rows, cycles 0 and 1 | PASS WITH LIMITATIONS |

## Dashboard cross-check (browser vs SQL)

| Metric | Browser | SQL |
|---|---|---|
| assets | 3 | 3 |
| observations | 3 | 3 |
| open / investigating / resolved | 1 / 1 / 1 | 1 / 1 / 1 |
| evidence | 7 | 7 |
| verifications | 3 | 3 |
| audit rows | 16 | 16 |

## Browser evidence for the incident path

Opening `Disk latency spike on DEMO-DB-01` rendered all nine sections from
persisted data: header (status `investigating`, cycle 2, asset DEMO-DB-01,
confidence strong, root cause unknown), what happened, why, impact, what to
inspect, recommended remediation, risks, evidence (4 rows including two
`analysis` sources), and verification history (cycle 0 and cycle 1, verifier
`demo.reviewer`). No login form and no password field exist on the page.

## Defect found and fixed in this session

**D6 — stale guidance text.** The stored guidance for the database incident said
"remediation cycle 1" while the incident had advanced to cycle 2, which would
mislead the instructor.

- Root cause: static guidance text written when the cycle was 1.
- Fix: guidance is now cycle-agnostic ("the cycle that was open at the time",
  "earlier cycles"), applied to the demo database.
- Regression evidence: the rendered detail page above no longer contradicts the
  incident's actual cycle.

## Verdict

**LOCAL DEMO ACCEPTED WITH LIMITATIONS.**

- Must fix before 24 November: none in the demonstrated paths.
- Acceptable presentation limitations: no login (deliberate), read-only demo (no
  interactive resolve), USB is offline report import only, analysis is
  deterministic (not an LLM), dashboard limited to the demo tabs.
- Future production work: independent verifier service, tamper-evident journal,
  USB hardware agent, full dashboard, pooler acceptance.

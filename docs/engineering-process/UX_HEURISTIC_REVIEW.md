# Source-based UX heuristic review

This is a code/heuristic inspection, not a human usability study. Integrated dashboard components are the core; standalone client is preserved as legacy/needs review. Browser checks, if available, are recorded in the engineering test report.

| Area | Source observation | Action / status | Need |
|---|---|---|---|
| Input modes / analyze action | Analyzer page offers text, file and bundle paths | Retain modes; inspect labels and file selection during T1/T2 | FR-01 |
| File feedback / error state | Client and server can disagree on accepted type; malformed single-file errors | Tighten server rules with actionable 4xx; keep clear allowed types | NFR-E01/S01 |
| Source / catalog navigation | History and catalog already have separate tabs and source filtering | Preserve improvements from supervision branch | FR-02/06 |
| Evidence versus explanation | Generic possible causes can appear beside original evidence | Explicit possible-cause disclaimer and evidence-grounded gates | FR-03/05 |
| Confidence | Bare confidence label; route can supply medium without evidence match | Clarify diagnostic match versus cross-file association; remove fallback | FR-05 |
| Missing metadata / counts | UI and PDF filled absent channel/computer/severity with plausible defaults and displayed a hardcoded one-event count | Show Not supplied; remove unmeasured count; browser negative assertions | FR-03/05 |
| Original source | Existing evidence items show filename and line | Preserve; test T3 discoverability and keyboard traversal | FR-04 |
| History/search | Existing history IDs, sort/search and saved details | Regression checks; T4 measures retrieval with real user | FR-06 |
| Export | Existing JSON/Markdown download callbacks | Do not claim privacy-safe export automatically; review identifiers | NFR-S01 |
| Responsive/accessibility | Existing responsive classes and form labels | Automated viewport/keyboard checks where supported; full audit not claimed | NFR-A01 |

User needs link through REQUIREMENTS_TRACEABILITY_MATRIX.md. Cosmetic changes unrelated to investigation are out of scope. No new user success/time results are inferred from code inspection.

## Upload-control combining: assessed, DEFERRED (15 Oct 2026)

Proposal (usability hypothesis, not a requirement): merge one-file and
multi-file upload into a single control. Assessment against the prompt criteria:
- Fewer decisions: marginal — three labeled modes (text/file/bundle) already
  map 1:1 to distinct API contracts (`POST /api/v1/analyze/` single vs
  `/bundle` multi-file with `BundleResponse`); merging hides that distinction.
- Bundle behavior: at risk — correlation/association semantics differ from
  single analysis; auto-detection heuristics add failure modes.
- Accessibility: no evidence of current harm; redesign without user data
  risks confusing existing flows before T1–T4.
- API/tests: merging breaks existing contracts and regression coverage
  (bundle tests, upload-security tests) for no measured gain.
Decision: DEFER until engineer testing produces observations. Revisit only
with participant evidence per the academic cycle
(Observation → Issue → Change → Regression test → Re-evaluation).

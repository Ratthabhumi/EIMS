# Annotation semantics v2 and full-investigation execution

v1 manifests, their heldout lock, M0/M1 meanings, and historical output folders
are preserved. `gold/manifest.v2.dev-draft.json` is a **parallel DEV-only
proposal**, bound to the exact v1 manifest bytes and each original case digest.
It has 12 DRAFT cases and no human reviewer receipts. It does not migrate the
five heldout cases, regenerate their lock or transfer review authority.

| v2 field | Meaning | Deliberately distinct from |
|---|---|---|
| event_identity | Source-provided event/log/message ID, when present | Internal vendor diagnostic signature, failure or RCA |
| failure_present | Operational failure in supplied evidence; null if unresolved | Merely having a known ID or warning |
| failure_type | Reviewed diagnostic category, or unknown/unclassified | Event ID or physical cause |
| first_observed_failure | First supported failure reference | First metadata/header or warning |
| last_observed_failure | Last supported technical failure | Explicit final job/session status |
| explicit_terminal_outcome | Literal completed job/task-session status with evidence | CTK code, time proximity, last line or inferred completion |
| root_cause_status | UNKNOWN / HYPOTHESIZED / PROVEN under explicit evidence | Possible-cause lists or confidence score |
| evidence_references | Exact references with EVENT_IDENTITY, SEVERITY, FAILURE_DESCRIPTION, TECHNICAL_FAILURE, EXPLICIT_OUTCOME, ROOT_CAUSE or INFORMATIONAL role | Coordinate validity implying semantic support |
| uncertainty_reason | What prevents stronger interpretation | A manufactured neutral/positive result |

The prediction role adapter reuses existing canonical `_is_noise`,
`_signal_strength` and `order_records`; rank >=2 exposes failure candidates
separately from legacy first/terminal signals that can include warnings.
Explicit status parsing is a declared annotation-role projection, not a change
to the production detector. All raw/native outputs stay visible. In particular,
the typed root-cause projection remains UNKNOWN because production output does
not certify proven causes. That invariant is **not evidence of good narrative
abstention**; RCA abstention quality remains NOT_MEASURED without human review.

## Commands

```powershell
python tools/eval_analyzer.py --mode rule_only --split dev --include-draft --annotations-v2 evaluation/analyzer/gold/manifest.v2.dev-draft.json --output evaluation/analyzer/results/new-v2-m0
python tools/eval_analyzer.py --mode rule_kb --split dev --include-draft --annotations-v2 evaluation/analyzer/gold/manifest.v2.dev-draft.json --output evaluation/analyzer/results/new-v2-m1
python tools/eval_analyzer.py --mode full_investigation --split dev --include-draft --annotations-v2 evaluation/analyzer/gold/manifest.v2.dev-draft.json --output evaluation/analyzer/results/new-full
python tools/demo_analyzer_investigation.py --output evaluation/analyzer/results/new-demo
```

Omit `--include-draft` to select actual reviewed v2 annotations. With none,
results remain INSUFFICIENT_DATA; no cases become REVIEWED automatically.
Legacy-v1 and v2 reviewed cohorts are reported separately. V2 review does not
certify legacy v1 truth. Any future v1 content change invalidates the explicit
v2 source binding and requires a documented version migration, not a silent
update of heldout locks. The existing review tool supports `--annotations-v2`
only for an actual human assertion; the agent does not execute confirmation.

## Exact full path and isolation

`full_investigation` is a new mode, not a redefinition of M0/M1. It executes
the existing `submit_analysis` or `submit_bundle` function, `build_summary`,
incident/evidence attachment and `get_all_history` reconstruction. External
search is replaced by the existing per-file/operation-local official reference
function. RAG and vector export are explicitly disabled; Gemini is forbidden;
only English synthesis is supported to avoid network translation. Supported
inputs are UTF-8 plaintext .txt/.log. No live HTTP, real auth, operational
PostgreSQL/History, model or vector index is exercised.

A new memory sink receives synthetic ORM objects. Its JSON snapshot is reloaded
into a separate memory sink, and reconstructed summary/metadata must exactly
match the native response. This tests serialization/reconstruction parity,
**not PostgreSQL persistence**. Separate in-process FastAPI transport tests
compare metadata/summary/references/formatted output with native route results;
test-only dependencies do not change installed authentication or settings.

Windows asyncio initializes a local wakeup socketpair before the outbound
network guard is installed; all Analyzer imports/business logic run with
external connections/DNS blocked. This OS IPC is not provider access. The full
adapter supplies a pristine curated cache per case to prevent contamination of
the experiment. A separately reproduced production shared-object defect is
handled on a separate correctness branch, not hidden by this isolation.

Trace records identify actual native route, local KB retrieval, native synthesis,
deterministic-vendor/curated-event/fallback branches, disabled RAG/export calls,
and isolated History reconstruction. M2/M3 remain NOT_RUN. Package availability
does not prove model execution; no AI performance benefit is asserted.

Full-harness timing includes stage comparison, pristine cache copy, native
orchestration, summary and memory serialization/reload. It excludes actual HTTP,
auth and PostgreSQL latency. Warm imports are excluded by per-case warmups;
recorded raw samples must not be advertised as installed end-to-end latency.

## Claim grounding and source inspection

Full outputs include stable claim IDs, text, role/category, exact candidate
references, NOT_REVIEWED support judgments and null reviewer/rationale. Possible
causes are exposed as hypotheses rather than proven facts. A directly observed
record means the literal log text was present, not that it proves a cause.
`claim_grounding_queue.json` binds every claim to the exact prediction hash.
`grounding.v2.schema.json` and the validator reject stale/unknown claims, invalid
source spans and unsupported human-review assertions. Human SUPPORTED,
UNSUPPORTED and UNCERTAIN judgments are counted separately; without them,
semantic support and unsupported-claim rate remain null/NOT_MEASURED.

The standalone `inspector.html` opens with no internet, escapes source text,
uses a restrictive CSP and shows at most five neighboring lines on either side.
It highlights exact spans and distinguishes hypotheses from observed text.
Missing/ambiguous/compacted-away source is shown as unavailable, never invented.
Its synthetic History snapshot is explicitly isolated. This artifact does not
claim an installed-dashboard source-drilldown or USB release implementation.

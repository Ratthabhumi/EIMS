# PR #2 engineering review — 2026-10-25

Inspected remote PR head `1c6d3e1e65b6d64adabc3601bfc96b350406f30f`,
base `bf634d9ddf86f44220ef961cf4be32988cfc5ee5`, 57 changed files. PR was
OPEN / MERGEABLE / CLEAN. CI run `40125771506` passed analyzer-hermetic and
dashboard-typecheck-build. Local existing+evaluation tests: 160 passed,
one Windows symlink skip; this is engineering evidence, not Gold accuracy.

## Findings and recommendation

| Check | Evidence | Verdict / limitation |
|---|---|---|
| Production Analyzer unchanged | Diff against original main under backend/domain/analyzer and existing regression file is empty | PASS for the inspected infrastructure head |
| Publication safety | Corpus is synthetic; committed fixtures and generated configs contain no observed injected credentials/private source paths/customer payloads | PASS in inspected scope; not a universal secret-detection guarantee |
| Output isolation | allowlisted checkout results/test-results roots, existing output rejection, no automatic cleanup | PASS; no adversarial filesystem TOCTOU proof |
| Offline execution | existing pure stage calls; socket connect/DNS/sendto guards; operational-import guard tests | PASS for supported paths, not an OS sandbox |
| Repeatability | 12/12 cross-process prediction hashes; exact source/scorer/manifest hashes | PASS for measured synthetic dev stages |
| Heldout protection | DRAFT heldout refused, input/annotation lock and split/group/duplicate checks | PASS mechanically; semantic independence still requires review |
| Review state | AI proposals stay DRAFT; receipts bind labels; stale receipts rejected | PASS for change detection; reviewer alias is a human assertion, not authentication |
| Regression preservation | 129 original tests retained and passing | PASS |

**Recommendation: engineering-ready to merge the inspected evaluation
infrastructure; scientific readiness remains INCOMPLETE.** Zero reviewed cases
is not itself an engineering merge blocker. No main merge was performed: the
current request authorizes implementation, commits, pushes and PR preparation,
but does not explicitly authorize merging main. Production behavior fixes must
remain separately reviewable. New follow-up commits require matching fresh CI.

## Follow-up scope

The follow-up adds parallel DEV-only annotation semantics v2 and an offline
full-investigation adapter. It continues using the existing runner/scorer and
actual production route/synthesis/History reconstruction functions. Real storage,
search and model dependencies are replaced by declared isolated dependencies.
No production auth settings or database session are used. A FastAPI transport
parity test creates a separate in-process test app; dependency overrides never
apply to the installed production application.

Human review is an unresolved scientific dependency, not a reason to fabricate
receipts or halt independent engineering. The owner explicitly confirmed that
the 12 DEV proposals have not been reviewed; all remain DRAFT. See the
[consolidated Thai review packet](ANALYZER_DEV_ADJUDICATION_20261025.md).

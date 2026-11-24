# EIMS Final Readiness Snapshot — 2026-11-15

## Executive status

The engineering core has reached a green synthetic acceptance baseline. The project is **not yet ready to be declared complete as a comprehensive engineer-facing knowledge system**: independent ground-truth review, initial approved knowledge coverage, and final security/operations sign-off remain explicit gates.

## Verified technical acceptance

- Secure Browser Acceptance final10: **PASS, 33/33 browser checks**; Playwright **2/2**; zero correlated HTTP 502/503 responses.
- Browser authentication used a real login and session cookie, not an injected bearer token. The expiry check expired the PostgreSQL session row while the JWT itself remained unexpired; JWT-expiry behavior is therefore **not claimed as covered by this browser test**.
- Full repository pytest collection: **748 tests, 0 failures**. Six opt-in infrastructure tests were skipped in that run because their dedicated service settings are intentionally required.
- Those six tests were then run separately against the dedicated disposable PostgreSQL, Redis, and MinIO containers: **6/6 PASS**, including EVTX upload/parse/replay, Redis/MinIO restart recovery, telemetry commit/ACK replay, lease refresh, and concurrent outbox dispatch.
- Combined distinct test coverage: **748/748 tests passed**, with no known failing test.
- Analyzer/PostgreSQL integration: **67/67 PASS** against a clean isolated database.
- Health-probe regressions: **46/46 PASS**.
- Focused Analyzer investigation/auth/catalog suite: **186/186 PASS**.
- Diagnostic catalog suite after the Event 1129 correction: **48/48 PASS**.
- Targeted Ruff import/unused-import checks, Python compilation, JSON validation, and `git diff --check`: PASS. Git reports only line-ending conversion warnings.

## Knowledge coverage and integrity

The current static reference catalogue contains **163 entries**:

- 141 Windows Event definitions.
- 22 vendor/syslog definitions: Veeam VBR 4, VMware 2, Fortinet 5, Cisco ASA 6, Palo Alto 4, Linux syslog 1.
- Vendor-entry verification states: 16 official-documentation verified, 4 code-supported with contextual reference, 2 code-supported.

The dynamic Knowledge Lifecycle has browser-verified proposal, independent admin approval, exact source-family/diagnostic-identity retrieval, provenance/hash retention, owner-history isolation, cross-user access to approved knowledge, and reuse in a subsequent incident analysis. Raw source logs are not copied into shared knowledge.

A reference catalogue is not the same as a populated, independently approved incident knowledge base. No customer incident data was imported or fabricated during this work. Synthetic acceptance records remain test evidence only.

A specific overclaim was corrected: Windows Event 1129 no longer states that DNS is the confirmed root cause. DNS/DC discovery, routing, VPN, firewall, and network readiness are hypotheses until corroborating evidence distinguishes them.

## Remaining release gates

1. **Independent ground-truth review.** The current gold manifest contains 17 cases: 12 development and 5 held-out. All 17 remain DRAFT. Domain reviewers must independently review the expected diagnosis, evidence attribution, confidence, and resolution claims. Do not unlock or score the held-out set as authoritative before that review.
2. **Initial approved knowledge coverage.** Build a prioritized starter set of recurring incidents from official vendor documentation and real, authorized incident records. Each entry must preserve exact diagnostic identity, applicability/version scope, evidence, resolution outcome, prevention, references, and independent reviewer approval. Do not auto-promote Analyzer suggestions.
3. **JWT expiry/security boundary.** Add an explicit browser/API test for JWT expiration separately from database-session expiry, plus refresh/revocation behavior where supported. The current final10 browser test proves server-side session expiry only.
4. **Production operations sign-off.** Witness backup/restore and rollback on a production-like disposable environment; verify TLS/secrets, retention, monitoring, and recovery ownership before a production rollout.

## Repository preservation

- Branch: `integration/eims-consolidated`
- HEAD: `85493b2 fix(analyzer): preserve Thai catalog text encoding`
- Existing modifications and untracked files are intentionally preserved. No reset, clean, stash, commit, push, or destructive cleanup was performed.
- This snapshot supplements, and does not replace, `EIMS_ACCEPTANCE_LEDGER.md` and `EIMS_OPERATIONAL_HANDOFF.md`.

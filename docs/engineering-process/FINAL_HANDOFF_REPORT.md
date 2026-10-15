# Final engineering handoff — 15 October 2026

## A. Git state and delivery

- Starting checkout: handoff/eims-supervision-2026-10-08 at 8c26f035244aeff9eefb87c3ed16b1aaa8e307f8.
- Isolated development branch: work/eims-engineering-process-2026-10; original checkout and its local files are retained.
- Code snapshot recorded when generating this report: `3e10118405829cd5d81ebdfbc98ac705ae574ef6`. Documentation is committed afterward; the exact final HEAD is reported in the final chat/private delivery state rather than embedding this file's own future commit hash.
- Remote comparison at audit: main bf634d9, supervision 8c26f03, supervision ahead by 2 commits. New work descends from supervision; main, release tag and Git history were not rewritten or merged.
- **Push: BLOCKED / not performed.** The task explicitly requires withholding remote publication for unresolved credential exposure. Preserved development configuration reached local PostgreSQL, and owner confirmation/rotation of published credentials is absent. Preparing environment-based files does not revoke old credentials. No real credential rotation or service restart was authorized/performed.
- Source/docs are committed with explicit paths. Original local tracked demo deletions, local media, standalone client files, reports and generated material are not bulk-added. Full current status and commit hashes are in the final response/private delivery state.

## B. Local preservation and cleanup

506 tracked paths, 177 untracked paths and 184,107 ignored paths inventoried at start. A private path-level CSV and backup outside Git preserve 772 valuable local-only files (~506 MB), plus deleted baseline demo bytes, the original binary diff and a verified complete Git bundle of main/supervision/release refs. No cleanup deletion, archive move, forced checkout, reset or volume deletion was performed.

Safe to track: reviewed source, synthetic tests, environment templates and sanitized engineering docs. Keep private: real credentials, raw logs, database backups, unredacted media, identifiable research/consent and personal academic material. Needs review: legacy standalone client, local-only client helpers, older slides/demo packs and historical field claims. Proposed deletion: none. See LOCAL_REPOSITORY_AUDIT.md and SAFE_CLEANUP_PLAN.md.

## C. Scope and engineering evidence

Core: **EIMS Log Investigation & Evidence Review** for infrastructure engineers. Provisional problem: scattered logs and unsupported explanations make it hard to establish observed facts, inspect original evidence and retrieve investigations. This derives from student-reported workplace observations, not formal interviews. FR-01 through FR-06 and NFRs link needs, UX decisions, components, acceptance criteria and measured tests. Seven editable Mermaid diagrams cover context, use cases, provisional journey, activity, components, sequence and the actual JSON-based History model. USB collection/import stays separate; no fictitious evidence table/FK was introduced.

## D. Research adoption

Implemented and synthetically verified: bounded source handling, static catalog, provenance and regression automation. Implemented but incompletely validated: live persistence/integration, diagnostic quality outside bounded cases, supporting USB import and deployment security. Prepared/documented: focused requirements, context hypotheses, heuristic UX review, decisions and task evaluation. Not implemented: evidence-sufficient file-copy/exfiltration diagnosis, calibrated causal probabilities and completed human study. See RESEARCH_ADOPTION_MATRIX.md; focused research questions are in RESEARCH_HANDOFF_FOR_CHATGPT.md for the student's ChatGPT Research follow-up. Only a short primary-source check was performed; no standards certification or invented research was added.

## E. Changes and validation

- Deterministic Windows Group Policy 1129 and Kernel-Power 41 gates avoid unsupported causes and disclose missing evidence before optional AI/RAG synthesis.
- Non-vendor incident unknowns no longer inherit CTK/VMDK/file-corruption speculation. Unknown-source input does not invite external vendor synthesis.
- Unsupported automatic medium confidence is removed; UI distinguishes possible explanations, diagnostic confidence and cross-file association. Legacy stored values remain readable.
- Missing severity/channel/computer metadata displays Not supplied in the result and PDF export; a hardcoded one-event display was removed. Browser negative assertions cover missing metadata rather than inventing values.
- Upload validation covers names/alternate streams/control characters, supported extensions, UTF-8/binary content, EVTX signature, PNG/JPEG dimensions and explicit 4xx errors; original basename/line evidence is preserved.
- PDF export escapes untrusted nested strings; original evidence is unchanged. Secret-bearing provider exception/bootstrap logging is removed in the integrated backend.
- Compose credentials move to required private environment inputs; no live passwords, data or service configuration were changed by deployment commands.
- Auth tests are now isolated after the legacy safety incident. Final combined isolated Python run: 213 tests, 0 failures, 0 errors. TypeScript and export helper pass. Production build: PASS (final metadata revision; webpack and TypeScript; 12 routes); catalog UI: PASS (Edge; intercepted synthetic API; successful retry); investigation UI: PASS (Edge; intercepted synthetic API; keyboard bundle selection and missing-metadata assertions; successful retry). These are local automated checks, not human usability or CI.

## F. Remaining work and risks

1. Credential exposure and deployment privacy remain owner-controlled blockers. Existing MinIO public bucket policy and preserved historical defaults/standalone client need review; history was not rewritten.
2. The unsafe legacy auth run created three synthetic service-session rows. Exact IDs/timestamps are private; no automatic deletion occurred. Startup/worker side effects beyond those confirmed rows cannot be ruled out without a pre-run snapshot. See TEST_SAFETY_INCIDENT.md.
3. Confirm needs with the engineer; arrange 2–5 eligible participants for T1–T4. Metrics/consent/results templates are blank. No fake results, quotes or participants exist.
4. Validate supported real-world formats/encodings with permitted sanitized examples, then controlled live API/DB integration and physical USB collection/import separately. No production accuracy or exfiltration claim is justified.
5. Chapter 1–5, PRD/master/SAD, README and Roadmap receive dated links/addenda, preserving historical claims and original scope. Finish the final report/presentation only after approved real evaluation and current verification evidence.

## G. Exact next three owner actions

1. Review the private security/incident report; confirm which published credentials were used and arrange authorized rotation/deployment. Review the three exact synthetic session rows before deciding on any selective cleanup. Do not reset the database.
2. Send RESEARCH_HANDOFF_FOR_CHATGPT.md to ChatGPT Research and discuss the provisional Windows/Veeam/firewall needs with the workplace engineer. Return confirmed priorities and permitted example formats, not confidential logs.
3. Arrange 2–5 participants using evaluation/USER_TESTING_SCRIPT.md. After security publication clearance, publish only the reviewed development branch and use actual anonymized task results to prioritize the next change; do not merge main automatically.

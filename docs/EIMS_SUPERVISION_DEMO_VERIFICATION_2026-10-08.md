# EIMS demo verification — 8 October 2026

## Repository and scope at the live rehearsal

- Branch: `main`.
- HEAD: `bf634d9ddf86f44220ef961cf4be32988cfc5ee5` (matches the expected baseline).
- Staged files: none at the initial check.
- The Analyzer History UI fix already existed in this working tree from the preceding task. No supplied patch needed applying, and no existing code was overwritten.
- This continuation creates only this verification note and `docs/EIMS_SUPERVISION_DEMO_RUNBOOK_EN_2026-10-09.md`. It makes no additional application-code changes.
- Existing tracked changes remain: `clients/dashboard/src/components/AnalyzerHistoryList.tsx` (+88/-133) and `backend/api/routers/analyzer/history.py` (+59/-3). The backend change predates both the current continuation and the UI task; it was preserved.
- Existing untracked items were preserved: `EIMS_SUPERVISION_ENGLISH_COLORED_2026-10-09/`, `EIMS_supervision_synthetic_demo_files_2026-10-09/`, `clients/log_analyzer/frontend/src/lib/`, and the four previously present supervision PDF/PPTX/script/audit files under `docs/`.
- No commit, staging, push, reset, tag modification, migration execution, seed, deletion, database export, or modification of the prohibited document/folder was performed.

## Technical checks

| Check | Result | Evidence / limitation |
|---|---|---|
| `npx tsc --noEmit` in `clients/dashboard` | PASS | Exit code 0. |
| `npm run build` in `clients/dashboard` | PASS | Exit code 0; compiled successfully and generated all 12 pages. Run outside the sandbox because the preceding task established a Windows path-access restriction. |
| `git diff --check` | PASS | Exit code 0. Git emitted an LF-to-CRLF working-copy warning, not a whitespace error. |
| `venv\Scripts\python.exe -m pytest tests/test_analyzer_reliability.py -q` | PASS | 129 test cases completed, exit code 0. Three dependency deprecation warnings: Starlette/httpx, AnyIO BlockingPortal, and pythonjsonlogger. No packages were installed. These regression tests use synthetic fixtures and fake network/database sessions. |

The initial sandboxed Python attempt emitted a runtime-location access warning and stalled after partial progress. It was interrupted (exit code 1) after the independent run outside the sandbox completed successfully. Only the latter run is reported as PASS.

## History UI checks

| Requirement | Result | Observation |
|---|---|---|
| Analysis History is the default tab | PASS | Selected on the first live page load. |
| Newest first | PASS | The new synthetic bundle result was first after analysis. Source sorts by `created_at` descending with numeric ID descending as tie-breaker; the preceding component check also verified numeric ties. |
| Oldest first | PASS | Changing the control put the older User Account Created record first; returning to Newest restored the newest bundle first. |
| Active-tab search | PASS | History and Catalog searches operated within their respective tabs. Searching the synthetic bundle diagnostic ID in Catalog produced no history rows. Existing token-based search is broad: a query can return partial-token matches. |
| Repeated Event IDs are retained | PASS | Searching `8198` showed six history rows. Both synthetic bundle analyses remained visible. |
| Catalog is reference information | PASS | “Static event definitions · Not analyzed logs” was visible. |
| All 141 definitions available | PASS | With Catalog search cleared, the tab panel contained 141 definition headings. |
| Old synthetic incident is unpinned and labeled | PASS | It appeared after newer records on initial load, at its 10 September date, with Synthetic Demo text. |
| Bundle metadata survives History reopening | PASS | The newly created record preserved both filenames/hashes, correlation none/reason, timeline, reference 424591, and `02_Task_long.log:1001`. |
| Existing deletion path | NOT RUN | Source retains the confirmation, DELETE API call, toast, and local removal logic. No deletion was executed because records must be preserved. |
| Refresh after analysis | PASS | The new analysis appeared in History and the runtime count updated from 26 to 27. |

## Live workflow results

| Step | Result | Observed evidence / reason |
|---|---|---|
| 1. Start Docker Desktop | NOT RUN | Docker was already running. Availability verified: server version 29.6.2; core service health and backend health were operational. |
| 2. Start EIMS with `start_eims.bat` | NOT RUN | Backend and dashboard were already running. Script inspected; did not spawn duplicate servers or rerun its migrations. Cold start remains unverified. |
| 3. Check backend health | PASS | `http://localhost:8000/api/v1/health` returned HEALTHY, with PostgreSQL/PgBouncer, Redis, and MinIO tiers UP. |
| 4. Open Analyzer | PASS | Live page loaded at `http://localhost:3001/analyzer`. Status settled to All Systems Operational. Initial in-app navigation timed out; selecting its existing tab and navigating succeeded. |
| 5. Select Evidence Bundle | PASS | Bundle picker displayed. |
| 6. Select English | PASS | English selected; result and follow-up controls rendered in English. |
| 7. Upload the two synthetic files | PASS | Both approved filenames were selected; Analyze Log became enabled. |
| 8. Click Analyze Log | PASS | Request completed and Diagnostic Report opened. |
| 9. Inspect result | PASS | Diagnostic `VEEAM-REPLICA-SNAPSHOT-CHAIN`; snapshot cleanup/revert assessment displayed. |
| 10. Inspect failure evidence | PASS | RevertSnapshot / InvalidSnapshotFormat and A required file was not found displayed. Missing filename remained unknown. |
| 11. Verify original-line provenance | PASS | `02_Task_long.log:1001` with `02.10.2026 00:11:06.410` displayed. |
| 12. Check applicable references | PASS | Broadcom Support KB 424591 displayed, with an applicability caution. Its external article was not opened or independently verified during the rehearsal. |
| 13. Ask follow-up | PASS | Asked “What evidence should we check next before attempting any recovery?” Response returned the summary and collection steps in Local Offline DB mode. No cloud-model success is claimed. |
| 14. Close and reopen from History | PASS | Newly created record reopened with the same bundle evidence and metadata. |

Only one new runtime analysis was submitted, using the approved synthetic files. It added one record (26 → 27); existing records were not deleted or edited. Metrics continued to reflect runtime history, and Catalog definitions were not added to the runtime count.

## Remaining limitations and presentation risks

- Cold startup through `start_eims.bat` was not tested; it includes database migrations. Rehearse a normal cold start ahead of the visit only if needed and appropriate for the local database.
- A backup video was not recorded by the agent. The runbook includes manual recording and playback verification instructions. Do this before the visit.
- Follow-up was verified with Local Offline DB behavior, not cloud-model generation.
- Correlation remained none. The UI also lists both files under “Correlated”; explain the explicit confidence/reason and avoid claiming a shared incident or causality.
- Existing search intentionally matches partial tokens. Filter History with the full synthetic diagnostic ID and visually confirm the rows before sharing the screen.
- Unfiltered History contains unrelated records. No company history was exported into these preparation artifacts. Do not include those rows in a recording.
- Vendor-reference availability and AI latency can differ on another installation. Saved synthetic History or a reviewed recording is the fallback.
- At the time of the rehearsal, code was uncommitted. Transfer requires the separately authorized handoff branch or a validated code-only patch; normal `git pull` on main does not select the handoff branch.

Use the runbook’s supervision-day checklist. No additional feature work is required for the verified running demo.

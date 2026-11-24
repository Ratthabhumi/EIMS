# V12 Report and Monitor Evidence Provenance

Generated: 2026-11-18 (Asia/Bangkok)

## V12 Final Engineering Report

| Field | Value |
|---|---|
| Source repository | Chat_HAND |
| Source path | `docs/V12_FINAL_ENGINEERING_REPORT.md` |
| Source SHA256 | `5AFB495E2EEEA4432F2C0161D936B7767CBF9998D06C42208AEA59B4F370E2FF` |
| Source revision | `v2/verified-fallback` / `c293b8aa…` (working tree) |
| Destination | `EIMS/docs/V12_FINAL_ENGINEERING_REPORT.md` |
| Destination SHA256 | `5AFB495E2EEEA4432F2C0161D936B7767CBF9998D06C42208AEA59B4F370E2FF` |
| Copy method | non-destructive byte-identical copy; original preserved |
| Authority | **HISTORICAL / NOT CURRENT ACCEPTANCE** |

The report is the canonical product narrative, but its content was assembled
before the current EIMS HEAD and before the final recovery. It must not be cited
as proof that the current revision passes any gate. Revalidate with evidence
bound to the tested revision before formal closure.

## EIMS Monitor acceptance evidence

| Field | Value |
|---|---|
| Source repository | Chat_HAND |
| Source path | `evidence/monitor-persistent-acceptance.json` |
| Source SHA256 | `F59DCC751502D8A36DC2EB7A2E1AB1E0309774EB19EE10AB9672198174203F63` |
| Destination | `EIMS/evidence/monitor-persistent-acceptance.json` |
| Destination SHA256 | `F59DCC751502D8A36DC2EB7A2E1AB1E0309774EB19EE10AB9672198174203F63` |
| Observed test result | watcher 169/169, launcher 171/171 (separate suites) |
| Source-byte binding | Current `scripts/agent-monitor` hashes match the disposable-copy snapshot for Watch/Launch/Host/README/tests (verified 2026-11-18; full hashes in `evidence/provenance-manifest.json`) |
| Authority | **CURRENT SOURCE BYTES VERIFIED for the monitor implementation; GUI/raw-key and long-running survival remain BLOCKED** |

Evidence manifest: `EIMS/evidence/provenance-manifest.json`.

## Boundary statement

- Chat_HAND Trust Grant code, tests and evidence remain in Chat_HAND; they are
  internal authorization infrastructure and are not EIMS product evidence.
- EIMS Persistent Monitor source remains in EIMS under
  `scripts/agent-monitor/`; it is untracked and needs a separate Git provenance
  decision.
- No file was deleted, renamed or committed by this provenance operation.

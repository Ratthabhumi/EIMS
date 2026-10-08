EIMS LIVE-DEMO FILES — SYNTHETIC ONLY (NOT COMPANY LOGS)
Date: 2026-10-09 | EIMS baseline: bf634d9

Two generated evidence files reproduce the conditions used in the repository
test_bundle_http_original_line_provenance_and_history regression. These
files are 100% fictional and contain no original company/customer logs.

DEMO:
1. Start EIMS normally. Open http://localhost:3001/analyzer
2. Select Evidence Bundle, choose English (EN).
3. Add 01_report.txt and 02_Task_long.log together, then Analyze Log.
4. Inspect Oct 1 report outcome vs Oct 2 snapshot revert diagnostic.
5. Inspect source evidence at 02_Task_long.log line 1001, if displayed.
6. Look for Broadcom KB 424591 if the reference source is available.
7. Ask Follow-up: What evidence should we check next?
8. Close result and open the new record from History.

IMPORTANT:
- The logs are synthetic; describe this explicitly to the advisor.
- A relevant KB link is not proof of root cause.
- The files do not contain shared job IDs: correlation may be NONE.
- A regression test running with stubbed network and DB is not a guarantee
  that a local installation is working. Rehearse all clicks and screen-record
  the successful live session before the academic visit.
- Keep the video, PDF/slides, files and summary offline on your laptop.

DEMO FILES:
01_report.txt: trailing Oct 1 failure timestamp.
02_Task_long.log: 1001-line synthetic task log, Oct 2 error on line 1001.

NEVER modify production snapshots or execute recovery/remediation as part of this demo.

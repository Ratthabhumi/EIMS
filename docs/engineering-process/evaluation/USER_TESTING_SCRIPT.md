# Task-based usability testing script — prepared, NOT RUN

Student arranges 2–5 eligible participants, preferably infrastructure engineers. Obtain permission before the session. Use only a permitted test environment, synthetic inputs and anonymized IDs. Neither participation nor consent is presumed. No invitations were sent by the agent.

Setup: first have the engineer review [provisional requirements](REQUIREMENT_CONFIRMATION_SHEET.md). Use the [isolated evaluation environment](../ISOLATED_HISTORY_RUNBOOK.md); T4 must use its synthetic SQLite database. Record the same build and browser/viewport privately; reset only disposable test state by authorized means. Never reset workplace DB. Explain: “We are testing the tool, not you. Please say what you expect. You may stop or skip a question.” Ask no leading UI-navigation questions. Have the observer start timing when the task is read and stop at completion/abandonment. Record assistance separately; keep assisted success distinct from unassisted success.

| Task | Starting condition / fixture | Participant instruction / goal | Success criterion |
|---|---|---|---|
| T1 Windows | Analyzer input screen; tests/fixtures/windows_shutdown_synthetic.txt | A machine experienced an unexpected restart. Use the supplied log to identify what is known and what remains uncertain. | Relevant 41/6008 evidence located; unexpected restart distinguished from proven power loss; missing evidence understood |
| T2 Veeam | Input screen; original baseline 01_report.txt + 02_Task_long.log, unchanged negative/insufficient-association fixture | Use these two Veeam files to investigate the reported issue. Explain what you found and whether the files contain enough information to establish a relationship. | Relevant error and original evidence found; does not invent a common job/session; relatedness may correctly remain unestablished |
| T3 Provenance | T2 result visible | Locate the original file and line supporting the finding | Correct source filename and relevant original line 1001 identified; do not hint the answer to participant |
| T4 History | Known synthetic result saved in isolated test session | Find and reopen that investigation later | Correct history identity and stored evidence reopened, not an unrelated/catalog entry |

For each task record: goal, starting condition, fixture, observer note, completion status (unassisted_success/assisted_success/failed/abandoned), elapsed seconds, assistance count, errors/misclicks, post-task ease (1–7) and suggested improvement. Leave values blank until measured. Optional vendor classification can be added with a distinct task ID and documented supported format.

Do not confuse automated browser assertions with human usability results. Do not infer task-time improvements from test execution duration. Close with open feedback, avoid promising production readiness, and store raw responses privately.

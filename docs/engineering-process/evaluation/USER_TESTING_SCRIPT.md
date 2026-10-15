# Task-based usability testing script — prepared, NOT RUN

Student arranges 2–5 eligible participants, preferably infrastructure engineers. Obtain permission before the session. Use only a permitted test environment, synthetic inputs and anonymized IDs. Neither participation nor consent is presumed. No invitations were sent by the agent.

Setup: same build and browser/viewport recorded privately; reset only isolated test state by authorized means. Never reset workplace DB. Explain: “We are testing the tool, not you. Please say what you expect. You may stop or skip a question.” Ask no leading UI-navigation questions. Have the observer start timing when the task is read and stop at completion/abandonment. Record assistance separately; keep assisted success distinct from unassisted success.

| Task | Starting condition / fixture | Participant instruction / goal | Success criterion |
|---|---|---|---|
| T1 Windows | Analyzer input screen; synthetic GroupPolicy 1129 text in tests or baseline demo | Investigate this Windows log and explain what it actually reports | Correct Windows identity; connectivity evidence identified; no confirmed root-cause claim |
| T2 Veeam | Input screen; baseline 01_report.txt + 02_Task_long.log | Investigate these two files together and identify the main observed error | Both files selected as bundle; observed failure distinguished from hypothesis; association read as returned (this pack expects none) |
| T3 Provenance | T2 result visible | Locate the original file and line supporting the finding | Correct source filename and relevant original line 1001 identified; do not hint the answer to participant |
| T4 History | Known synthetic result saved in isolated test session | Find and reopen that investigation later | Correct history identity and stored evidence reopened, not an unrelated/catalog entry |

For each task record: goal, starting condition, fixture, observer note, completion status (unassisted_success/assisted_success/failed/abandoned), elapsed seconds, assistance count, errors/misclicks, post-task ease (1–7) and suggested improvement. Leave values blank until measured. Optional vendor classification can be added with a distinct task ID and documented supported format.

Do not confuse automated browser assertions with human usability results. Do not infer task-time improvements from test execution duration. Close with open feedback, avoid promising production readiness, and store raw responses privately.

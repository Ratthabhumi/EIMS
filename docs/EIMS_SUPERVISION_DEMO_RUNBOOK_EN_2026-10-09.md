# EIMS supervision demo — 9 October 2026

Target: 4–5 minutes. Audience: academic supervisor visiting the workplace. This is a cooperative education progress demonstration.

Use only `EIMS_supervision_synthetic_demo_files_2026-10-09/01_report.txt` and `02_Task_long.log`. These are fictional inputs. The workplace and home databases do not need matching totals.

## Before the visit

1. Check Docker Desktop is running. If EIMS is already healthy, keep it running.
2. For a normal cold start, double-click `start_eims.bat` in the repository. It checks Docker, starts infrastructure, verifies services, runs `alembic upgrade head`, then starts backend and dashboard. Do not run a second copy over existing servers. Do not reset or seed the database. The cold-start script was inspected but not executed during this rehearsal; verify it ahead of the presentation when a restart is actually needed.
3. Open `http://localhost:8000/api/v1/health`. Expect `status: HEALTHY` and core components `UP`.
4. Open `http://localhost:3001/analyzer`. Confirm the dashboard is operational.
5. In **Analysis History**, search `VEEAM-REPLICA-SNAPSHOT-CHAIN` before recording or screen sharing. Confirm every visible row belongs to the approved synthetic demonstration. Keep the broader history out of the recording.
6. Have the two synthetic files ready. Select **Evidence Bundle**, then **English (EN)**. Do not show the whole filesystem in a file-picker recording.

## The 4–5 minute demonstration

| Time | Clicks and visible fields | Natural speaking line |
|---|---|---|
| 0:00–0:30 | Show the Analyzer and operational status. Keep History filtered to the approved demo. | “This is EIMS, the system I am developing during my cooperative education placement. I will show how an engineer can review log evidence. These two files are synthetic examples, so no company logs are used in this demonstration.” |
| 0:30–1:00 | Click **Evidence Bundle**. Select **English (EN)**. Click **Click to add files (up to 12)** and select `01_report.txt` plus `02_Task_long.log`. Confirm both filenames. Click **Analyze Log** once. | “I am adding a short report and a longer task log together. The system analyzes both inputs and keeps the source of the evidence.” |
| 1:00–1:50 | In **Diagnostic Report**, inspect **Event Details**, **Problem Summary**, **Observed Evidence**, **What Is Still Unknown**, and **Next Evidence to Collect**. | “The task log contains a snapshot revert failure. The observed messages include ‘InvalidSnapshotFormat’ and ‘A required file was not found.’ The result suggests what to investigate next, but the evidence does not identify the exact missing file.” |
| 1:50–2:40 | Scroll to **Correlated Sources**, **Failure Sequence (Observed)**, and **Observed Evidence (with source file)**. Locate `02_Task_long.log:1001`. | “The short report records an outcome on October 1, while the task log has an error on October 2. The system keeps that sequence. The correlation level is none because these files do not share enough identifiers. Time order alone does not prove that one event caused the other. This evidence points back to the original file and line 1001.” |
| 2:40–3:10 | Inspect **References Found**. Point to Broadcom article **424591**, if present. You do not need to open an external page. | “This reference is relevant to the observed snapshot revert message. It is a starting point for investigation. I would verify the environment and the article’s conditions before using any recovery procedure.” |
| 3:10–3:50 | In **Ask Follow-up Questions**, type `What evidence should we check next before attempting any recovery?` and click **Ask AI**. Wait for a response. | “I can ask a follow-up question while keeping the analysis context. In this rehearsal, the Local Offline DB mode returned the summary and evidence collection steps. I am not claiming that this is a cloud model response.” |
| 3:50–4:30 | Close the report using the **X** at its top right. In **Analysis History**, keep the synthetic diagnostic ID search, select **Newest first**, and open the first demo row. Inspect the filenames, hashes, correlation, and source line again. | “The result is saved in History, so I can reopen it without uploading the files again. The source-file information and original line number are still available.” |
| 4:30–5:00 | Close the report. Optionally choose **Oldest first**, then return to **Newest first**. Click **Event Catalog (141)**, clear its search, and show the reference notice; return to History with the demo filter. | “History contains actual analysis records. The catalog is a separate reference list of 141 event definitions. Catalog entries are not counted as analyzed logs. The next step in the project is to improve reliability and evaluate it with approved test cases.” |

The upload and follow-up may take time. If needed, omit the optional sorting/catalog segment to keep the presentation under five minutes. Repeated analysis adds a new history record; reuse a verified existing demo record when a fresh upload is unnecessary.

## What was actually observed in the rehearsal

- The live result displayed `VEEAM-REPLICA-SNAPSHOT-CHAIN`, `RevertSnapshot / InvalidSnapshotFormat`, and `A required file was not found`.
- `02_Task_long.log:1001` appeared with timestamp `02.10.2026 00:11:06.410`.
- Broadcom KB 424591 appeared in References Found.
- Correlation was `none`, with the reason that no shared identifiers, paths, or signatures were found across files. The UI also lists both input filenames under “Correlated”; explain that the explicit confidence and reason do not establish a causal link.
- The English follow-up returned a summary and evidence collection steps in Local Offline DB mode.
- Reopening the new record from History preserved both filenames and hashes, timeline, correlation, vendor references, and line 1001.

These observations apply to this running installation on 8 October 2026. Repeat the health check and short rehearsal on the presentation machine.

## If the live Analyzer fails

1. Stop after one attempt and describe the visible error without guessing its cause. Do not restart infrastructure or troubleshoot migrations during the presentation.
2. If the backend still works, open **Analysis History**, search the approved synthetic diagnostic ID, and reopen the previously verified synthetic result. Say: “The live upload is unavailable right now, so I will show a saved result from an earlier successful run.”
3. If History is also unavailable, play the recording of the actual successful rehearsal. Say: “This recording shows the workflow running successfully during rehearsal. It uses the same synthetic files.”
4. If no verified recording is available, use the existing slides and explain the workflow as a design. Do not present an expected result as a live observation.

## Record a real successful rehearsal manually

No backup video was created by this task. Use an already installed recorder; do not install new tools immediately before the visit.

**Windows screen recording:** use Snipping Tool’s Record mode if your installed version provides it. Click **New**, select only the EIMS application area, then **Start**. Alternatively use an already available Xbox Game Bar recording for the browser. Stop after reopening the synthetic result from History. Save the video locally and play it back from beginning to end. Check that text, source line, and spoken explanation are readable/audible. Availability of these recording modes depends on the installed Windows version.

**OBS, if already installed:** create a Window Capture source for the EIMS browser, preview the captured area, and enable the microphone only if you want narration. Click **Start Recording**, perform the successful sequence, then **Stop Recording**. Review the saved video. Prefer Window Capture over recording the entire desktop.

Before either method, prepare the file selection and approved History filter. Pause or crop the file-picker segment if it exposes account names or unrelated paths. Record only the synthetic workflow. Name the reviewed file `EIMS_synthetic_demo_2026-10-09.mp4` and keep an offline copy in an approved location.

## Privacy check before recording or sharing

- Close email, messaging, other browser tabs, terminals, credential dialogs, and unrelated documents. Suppress notification pop-ups using your normal presentation setup.
- Confirm only the two approved synthetic files are selected.
- Confirm the History filter shows approved synthetic demo records only. Do not scroll through unfiltered company history.
- Capture only the EIMS window or selected application area. Keep real identifiers, addresses, credentials, filesystem paths, and company data outside the frame.
- Review the entire video before copying or sharing it. If private content appears, make a new clean recording.
- Do not copy database volumes, database dumps, or workplace records. Share code and approved synthetic materials only through authorized channels.

## Supervision-day checklist

1. Open the reviewed backup video offline and confirm it plays.
2. Verify Docker and backend health before the supervisor arrives.
3. Open Analyzer, select English and Evidence Bundle, and prepare the two synthetic files.
4. Filter History to approved synthetic results; check that no unrelated data is visible.
5. Rehearse upload, line 1001, references, follow-up, and History reopening once.
6. Present for 4–5 minutes; use the saved result or reviewed recording if live analysis fails.
7. Explain correlation limits and proposed evidence collection; do not execute remediation.

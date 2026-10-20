# Demo-only handover and local Windows session access

The owner explicitly selected both tasks: preserve originals privately, replace
the USB delivery data with synthetic examples, and remove normal manual EIMS login.
No operational database reset, scanner rebuild or Docker reinstallation.

## Preservation and data boundary

All user files on the original media were copied and SHA-256 verified outside USB:
1,253 files from D: and 554 from E:. The private inventory and originals are under
`.local-private/Original_USB_20261020`, excluded from Git. Every backup file and
directory has a protected Windows DACL limited to the current user and SYSTEM.
Windows-managed System Volume Information is excluded; this is logical sanitization,
not forensic secure erasure of unallocated space or filesystem metadata.

The original handover instance was stopped to freeze its USB backups. Its database,
local sessions and credentials remain recoverable. The seven unrelated `eims`
containers remain running; no unrelated project, images or volumes were reset.

The new package identity is `eims-ff4f4779fb145282`, with a new media ID and separate
local cache. It cannot select an old operational session. A checkpoint writer now
rejects an installation/package ID mismatch before copying anything.

Synthetic assets: PC-DEMO-001, PC-DEMO-002, SRV-DEMO-001; fictional Example
Engineering Demo company/contact; documentation-range IPs and synthetic device IDs.
Every report is marked SYNTHETIC_DEMO. The dataset includes PASS/FAIL/WARNING/UNKNOWN,
Standard/Admin examples, Windows evidence, security findings and engineer context.
Inventory has 3 assets, Windows events 33, History 31, and 3 pending event analyses.
These are fixtures/actual software analysis of fixtures, not scans or human evaluation.

## Authentication and credentials

The handover backend adapter uses a private signing key protected by Windows user
ACLs. The launcher verifies current Windows SID/session, signs a 60-second one-use
proof, and opens a fragment URL. The frontend immediately removes the fragment and
exchanges it from the exact frontend origin. The server checks the signature,
server/user/session binding, expiry and replay, then verifies the existing admin
account and issues its actual role in a 15-minute JWT held only in browser memory.
Neither permanent passwords nor JWTs enter URLs, HTML, browser storage or USB files.
The signing key is local-only, never checkpointed. The authorized Windows account
and system administrators are the local trust boundary.

Protected APIs stay authenticated. The adapter is loaded only by the isolated
handover launcher; normal production/remote authentication is unchanged. No localhost
address alone grants access. Expired/missing proofs fail closed with a Start.bat
instruction; the password form is removed from the actual rebuilt frontend.

Demo checkpoints exclude `users` table data and ship blank secret placeholders,
not credentials. Restore generates fresh private installation secrets once, and
normal backend startup seeds a new admin. Existing local credentials are never
overwritten. Normal non-demo checkpoint credential preservation is unchanged.

## Verification actually performed

- **44 passed**, zero skipped/failures: session proof, replay/expiry/SID/session,
  backup/restore, credential template, stale PID, runtime and image identity tests.
  JUnit: `Final_CO-OP/verification/demo-session-tests.xml` (local, ignored).
- TypeScript and Next.js webpack production build passed. The delivered CSS source
  discovery is limited to dashboard sources; no dependency/scanner changes.
- Actual SETUP.bat with `-NoBrowser`, without the noninteractive bypass: exit 0,
  SETUP COMPLETE, no success pause and no LOCAL_ADMIN path in success output.
- Repeat Stop/Start and real headless browser: no password field; proof removed
  from URL; token absent from HTML; unauthorized History, replay and wrong origin
  each return 401. Inventory and Event-to-Analyzer navigation passed.
- Fresh isolated PostgreSQL/MinIO restore: 3 assets, 33 events, 31 History records;
  shipped user rows 0; a newly generated local admin authenticated successfully.
  This is a fresh local project/database, **not a second physical PC**.
- Standard Auditor GUI reached its operator window with an approved private test
  output; no scan ran. Both original EXE hashes and UAC manifests are unchanged.
  Admin GUI execution is NOT RUN because genuine human UAC is required.
- Existing Excel exporter generated Summary.xlsx with only the 3 synthetic rows.
  A one-page updated PDF guide was rendered and visually checked.

Integration fixes: the embedded Python launcher explicitly locates its companion
adapter and disables bytecode writes to reviewed Tools. Reused PID records return
not-owned; occupied-port checks still block startup and no unrelated PID is controlled.

Original/raw records and historical duplicate delivery folders are removed from
the delivered USB copies only after verified preservation. Real auditing later is
still supported: the existing storage-policy dialog can require a separate approved
protected output folder. Demo examples must not be presented as collected evidence.

Physical USB verification receipts are recorded locally after deployment. Company
Docker/Windows IT approvals and second-PC acceptance remain the owner's responsibility.
No additional research is required for this patch.

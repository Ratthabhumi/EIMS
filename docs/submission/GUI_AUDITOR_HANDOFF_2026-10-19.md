# GUI Auditor and Inventory review handoff — 2026-10-19

Two portable GUI executables are built from one maintained engine. Automated
acceptance passes; final hands-on release acceptance remains incomplete.
No operational database, Docker service or physical USB was changed.

## Delivered behavior

- Optional Customer/Company, Site, Department, Contact, Email, Asset Tag,
  Assigned User, Business Location, Device Role, Engineer, Ticket, Purpose and
  Notes. New sessions clear profiles; there are no credential inputs.
- Five functional module checkboxes. Disabled collectors are not executed,
  record `SKIPPED_BY_OPERATOR`, and do not contribute to applicable scoring.
  Minimum machine identity remains available.
- One background scan using the existing nine stages. Progress remains on the
  GUI thread. Review shows findings and read-only original evidence; separate
  annotations support Open, Investigating, Resolved, Accepted Risk and False
  Positive, notes, recommendations, ticket references and proposed corrections.
  Annotation history records local OS identity, not an invented EIMS login.
- Initial evidence is saved before review. Export creates a separate reviewed
  JSON and unique Excel, preserving old evidence. Excel contains business and
  review sheets, treats strings as literal data, and exports only the selected
  session rather than including earlier customers automatically.
- Inventory exposes business context in the existing Asset Detail view.
  Edits persist through the API and existing AuditLog table, separately from
  `offline_report_data`. Re-import retains manual edits; new import snapshots
  are archived in AuditLog. No database migration is required.
- Event Findings keeps its five columns and now lists persisted events,
  including those not analyzed. View Analysis opens exact saved History;
  Analyze This Event uses the persisted source and existing analyzer, then
  opens its saved result. Automatic import analysis stays capped at 10.
- Original event messages beyond the former 1,000-character import cap are
  retained under an explicit 64 KiB UTF-8 limit, with source and import
  truncation metadata kept distinct. Original occurrence, provider, channel,
  record ID and asset/event references remain associated.
- Secure-mode business/event APIs use existing authentication. Requests for
  an event belonging to another asset return 404. This is the existing
  deployment-wide access model, not a newly implemented tenant-per-asset ACL.

## Measured verification

| Check | Result |
| --- | --- |
| Auditor/export/scope/package tests | 126 passed |
| Isolated import/edit/re-import/event/auth/message tests | 6 passed |
| Latest GUI layout/export recheck | 3 passed, already included above; not added again |
| TypeScript `tsc --noEmit` | PASS |
| Dashboard `npm run build` | PASS; 12 routes generated |
| Actual Tk window, fields, immutable evidence, threaded export and Excel formulas | PASS with synthetic data |
| Native Standard GUI visual review and actual own-PC collection | PASS on preceding GUI candidate; 413 events saved, collection PARTIAL |
| Final candidate Standard launch | Attempted; final visual acceptance interrupted |
| Final candidate Admin launch | Normal RunAs requested; `EIMS Auditor — Admin` process/window observed; scan NOT RUN |
| Sixteen maintained GUI/engine module objects identical between final EXEs | PASS |
| Final source/provenance hashes and native privilege manifests | PASS |
| Physical USB / actual share-to-local acceptance | NOT RUN |
| Live PostgreSQL parallel-click and full deployment regression | NOT RUN |
| UAC refusal, clean PC, Server or enterprise EDR compatibility | NOT RUN |

Computer Use was stopped with physical Escape. No further desktop input was
performed. Do not represent that interrupted step as completed final GUI testing.
Earlier console-mode Admin tests are historical evidence, not an Admin GUI scan.
The previous console report is retained separately for that reason.

Test commands: build-env Python `-m pytest clients/usb_auditor/tests
tools/tests/test_build_usb_package.py -q`; project venv Python `-m pytest
tests/test_portable_inventory_chain.py --noconftest -q`; dashboard
`node_modules/.bin/tsc --noEmit` and `npm run build`.

Integration tests use actual repositories/controllers and disposable SQLite,
test-only JSONB adapters, a stub cache, and the protected History sandbox.
External requests/AI and operational database startup are blocked. They do not
establish live PostgreSQL concurrency acceptance. Source-row locking and a
history recheck prevent concurrent source re-analysis on PostgreSQL by design;
sequential duplicate requests were measured to return the same saved record.

Private XML/results/output indexes remain under ignored
`Final_CO-OP/verification`. Actual own-PC evidence is private in
`GUI EXE Final Local/Evidence/{reports,logs}`. No raw scans or screenshots are
included in Git or the clean executable package.

## Candidates and SHA-256

Clean Auditor folder: `dist/usb-auditor-exe/ready/EIMS_USB_Auditor`.
It contains both EXEs, shared `_internal`, notices and manifest. Keep it whole.
1,013 files, 35,681,885 bytes before ZIP compression.

| Artifact | SHA-256 |
| --- | --- |
| Auditor MANIFEST.txt | `49d636b1641dc6268ce51b4cac9b0dcb6b43bce0b1235466d1bfe3cdac31f023` |
| EIMS-Auditor-Standard.exe | `414536dc5d3566ff9a774594fea33ae0013e28e8e6f72bdf936e147d7023c2f6` |
| EIMS-Auditor-Admin.exe | `fce2b219bf7b082e4e9084a24bfd0bde689dcff93e85c43a7ea79ca57f2289fe` |
| Full source-only candidate MANIFEST.txt | `0fa0110919a79448c51d4b82828455551bea3aa7873ce13ec01f1a0497ece618` |

Full candidate: `Final_CO-OP/Two_USB/GUI_Review/Final_EIMS_Project`.
Only reviewed source/archive/ledger metadata changed from the SETUP-only
candidate. Frozen dependency files, Runtime, Start/Stop, compose and installation
identity match that baseline. Its release gate is deliberately **PENDING**.
The typed SETUP prompt remains removed; genuine IT/license approvals remain.
SETUP installation and full live deployment were not run this round.

Build recipe: `tools/build_auditor_exe.py`, `PortableAuditors.spec` and
`tools/auditor_exe_requirements.txt`. PyInstaller 6.22.3 / Python 3.14.6,
ONEDIR, windowed, asInvoker and requireAdministrator. Notices include installed
dependency/CPython and available Tcl/Tk licenses. Bit-identical rebuilds are not
claimed. Intermediate build slots are superseded and must not be distributed.

## Source change groups

- `clients/usb_auditor`: shared GUI/session model, portable bootstrap/entries,
  packaging spec, scoped orchestration, exports, collectors and regression tests.
- `backend/domain/asset_registry`: separate business edits/import snapshots and
  authenticated event actions; `analyzer/services/import_pipeline.py` preserves
  message evidence and serializes same-source analysis.
- `clients/dashboard`: AssetBusinessEditor, existing Endpoints table/actions,
  and exact History deep-link handling. Existing Analyzer layout is retained.
- `tools`: pinned EXE build, legacy source allowlist, SETUP-only and source-only
  staging helpers. No cloning receipt was promoted or physical USB replaced.

## Limits and release decision

PowerShell remains required by some collectors. Neither EXE bypasses enterprise
controls or installs services/drivers/tasks. Outputs require writable approved
storage, private ACLs or the documented encrypted-media approval attestation;
the attestation does not detect encryption. Current D: FAT32 has not been
approved for this new collection workflow. EXEs are unsigned.

Intended writes are Evidence directories/ACL, write probes, reports and logs.
Source inspection found no added OS configuration changes; a disposable-machine
before/after OS side-effect comparison was not run. Do not claim zero OS/EDR
artifacts. Previously exposed credentials are not verified rotated by this task.
Publishing reviewed source does not approve production deployment or close that
historical incident. Private authorization records and Full handover contents
remain local; only reviewed public source and the clean Auditor candidate are
eligible for GitHub delivery.

D: and E: manifest hashes still match the prior verified copy receipts. Keep
the existing USBs as fallback. Complete final GUI review and approved-media/
share acceptance, then obtain separate authorization before replacing either
physical release. No additional literature research is required for these
remaining environment/owner acceptance steps.

## USB delivery update — 2026-10-20

The owner subsequently authorized replacing both physical packages while
renaming the previous folders as backups. This supersedes the earlier
"D:/E: unchanged" delivery status, not the outstanding runtime-test limits.

| USB | Active folder | Preserved backup | Verification |
| --- | --- | --- | --- |
| D: | `EIMS_USB_Auditor` | `EIMS_USB_Auditor_Backup_2026-10-20` | 1,013 new files and all 286 old files hash-verified |
| E: | `Final_EIMS_Project` | `Final_EIMS_Project_Backup_2026-10-20` | 34 new files and all 32 old files hash-verified |

The exact volume identities were rechecked. Incoming copies were verified
before activation; no files were deleted. The Auditor manifest remains
`49d636b1641dc6268ce51b4cac9b0dcb6b43bce0b1235466d1bfe3cdac31f023`.
The Full package manifest is now
`b4e2f92c4e2fd15c5ab65eaebef441fd180ee498ab82823b0d578c0addf3c2b6`
after adding current delivery notes, source snapshot identity and exact-payload
internal-transfer review. Its production status remains NOT APPROVED; this
does not imply completion of final GUI or deployment acceptance.

D: includes `EIMS_AUDITOR_HANDOVER_2026-10-20.txt`: copy the whole Auditor
folder to approved local storage before running. No encrypted-media attestation
was invented and direct FAT32 collection remains restricted. Full EIMS includes
`DELIVERY_NOTES_2026-10-20.txt`: SETUP preserves an existing App directory;
this delivery is not an automatic source upgrade of an installed copy.
No setup, service restart, database reset or credential rotation occurred.
Detailed copy receipts remain private under `Final_CO-OP/verification`.

## Startup feedback and NTFS update — 2026-10-20

The owner explicitly confirmed formatting only D: after verified backup and
restoration. A protected local snapshot preserved 1,016 user files (35,718,016
bytes). D: was changed from FAT32 to NTFS, retained label `128 GB`, and every
backed-up user file was restored and hash-verified before replacing the program.
Windows-generated System Volume Information was regenerated, not treated as
user data. E: was not formatted. The protected backup remains local and ignored.

Auditor launcher 1.3.1 now shows a responsive startup window while checking
package files, rather than checking the whole USB before displaying anything.
It can launch directly from USB; failed/unapproved output preflight offers an
explicit approved local parent selection for a protected `EIMS_Evidence`
directory. Cancellation starts no scan. There is no silent AppData fallback and
NTFS does not imply encryption or company approval for USB evidence storage.

The actual Standard EXE was launched from D:. Its startup progress/storage
prompt was observed. With an explicit private local output argument it reached
the normal Customer & Asset GUI, showing actual Standard privilege. No audit
or customer data collection was started in that verification. Interactive folder
selection is covered by source tests; a completed native dialog selection is
not claimed. Admin scanning was not rerun this round.

SETUP's owned-command runner now emits a moving activity indicator, elapsed
time, private-log byte count and DONE/FAILED with the actual exit status. It
does not invent a download percentage or disclose child log contents. Timeout
still stops only its own child command tree. An already-running old command
does not acquire this feedback mid-execution; no install retry or service/DB
operation was triggered for this change.

Verification: **17 targeted tests passed**, including actual Tk responsiveness,
explicit output choice/cancel, immutable GUI export, private-output preservation,
live subprocess feedback, nonzero failure and bounded timeout. PowerShell parse
passed, and an isolated real `Invoke-Checked -> command_runner -> owned Python
child` invocation displayed RUNNING then DONE. No frontend code changed; the
previous TypeScript/build evidence is historical and was not rerun here.

Both updated physical packages and their dated backups were hash-verified:

| Artifact | SHA-256 of MANIFEST.txt |
| --- | --- |
| D: Auditor 1.3.1, 1,013 files | `37f191427b2afe7380e59b6cb69c0057a65d8cd40e590a2e46d460ed9bd0ff33` |
| E: progress/launcher source update, 35 files | `5f6a14801b06452e6d14858146e1472bdaff3801df6d1790fc6d4cf76521955b` |

The preserved predecessor Auditor has 1,013 files, and the predecessor Full
package has 34 files. Current dated backup paths are recorded in the private
startup delivery receipt. No protected backup was deleted, and no live
credentials, audit policy, services or database were changed.

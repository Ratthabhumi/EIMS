# USB handover hotfix — 20 October 2026

## Changes

- `portable_entry.py`: new NTFS removable Evidence uses stable Authenticated Users Modify and SYSTEM/Administrators Full Control. No Everyone access; fixed-disk output remains owner/SYSTEM private. Protected USB ACLs deliberately do not inherit this USB root's existing Everyone Full Control rule. These permissions permit authenticated Windows accounts, not specifically a company directory group; physical protection/company authorization still applies.
- `auditor_gui.py`: scan completion automatically regenerates Summary.xlsx after the original JSON/log save. Save Review writes annotations separately; Retry Excel never scans. Errors retain the raw report and previous valid workbook.
- `json_exporter.py`, `excel_exporter.py`, `review_store.py`: stable scan IDs, duplicate-ID/legacy-scan filtering, atomic `.review` notes under Evidence/reviews, immutable raw JSON and one cumulative workbook. Review notes are not an additional scan report or Excel row. Existing duplicate files are retained.
- `HandoverAuthGate.tsx`: removed only the decorative SYNTHETIC DEMO banner. Sample records and their truthful classifications are unchanged.
- Source_Code ZIPs are staged for both deliveries. Existing reviewed source allowlists/transforms were reused; evidence, credentials, databases, caches and Git history are excluded.
- `repair_auditor_usb_evidence.ps1`: owner-approved elevated repair restricted to the two existing Evidence locations. Inaccessible items require ownership only inside those locations; links are rejected. Existing Evidence was not moved or deleted.

## Verification

- 23 targeted tests PASS: startup, removable ACLs, immutable review, cumulative unique scans, Excel replacement/failure and a real Windows sharing lock.
- One actual Standard GUI scan invoked through Start Audit saved exactly one JSON, one scan log and a one-row Summary without Export. Actual reports/logs remain private locally. The initial completion-label assertion exposed an editing/encoding issue; corrected source passed saved-report GUI replay, displaying Audit Completed — Saved without another scan. The final EXEs were rebuilt after correction.
- Final Standard candidate GUI opened with default arguments. No scan ran in the distributable candidate. Admin PE manifest remains requireAdministrator; Standard remains asInvoker.
- TypeScript and Next.js webpack production build PASS. Standalone frontend HTTP startup returned 200; decorative banner absent from HTML and bundled JavaScript. This is not a full authenticated browser/DB end-to-end test.
- Actual UAC-approved repair PASS: 11 existing files backed up privately and verified unchanged across D:\EIMS_Evidence and D:\EIMS_USB_Auditor\Evidence. Both now have portable group ACLs. No unrelated folder ownership changed.
- Two real Windows accounts/second PC and actual Admin GUI scan: NOT RUN. A simulated different SID check verifies that the new USB ACL check does not require the original owner's SID; it is not a two-account acceptance result.
- Existing Docker configuration, image archive, package/media identity and EIMS_Data were not changed. Full EIMS service/database startup was not rerun under the no-Docker-changes constraint.

## Staged delivery

`Final_CO-OP/USB_Hotfix_20261020/EIMS_USB_Auditor`: 1,014 package files; manifest SHA-256 `3210d049b9fcc571ea2014723eb6b2fecaad54161917188ad8e42013712d937b`.

`Final_CO-OP/USB_Hotfix_20261020/Final_EIMS_Project`: 92 files; manifest SHA-256 `319b0e765f5954952b8e878b51ded60031db5d56d9a72a49aed032f02ba0957e`.

Owner subsequently approved physical replacement and GitHub publication. Both packages were copied, verified against their manifests and installed at D:\EIMS_USB_Auditor and E:\Final_EIMS_Project. Complete prior folders remain as D:\EIMS_USB_Auditor_Backup_20261020_Hotfix and E:\Final_EIMS_Project_Backup_20261020_Hotfix. Existing default Evidence was copied without content changes and portable ACLs reapplied before use; D:\EIMS_Evidence and EIMS_Data were retained. The deployed D: Standard EXE reached its operator GUI using default USB Evidence without a folder picker; no additional scan ran. Existing backups were not removed. Source-only publication uses the existing development branch without merging main.

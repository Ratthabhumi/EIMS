# Auditor startup confirmation patch — 2026-10-20

Scope: startup dialog only. Scanner, forms, exports, existing Evidence and USB contents are unchanged.

## Observed cause

Launching the deployed Standard EXE with default arguments reproduced the EIMS dialog `Select approved report storage`. Its reason was that the existing Evidence directory was not protected and owned by the current account. This is a separate prompt from Windows security warnings.

Both deployed EXEs have no Zone.Identifier stream and are unsigned. Their PE manifests are Standard `asInvoker` and Admin `requireAdministrator`. No trust metadata, Windows settings or privileges were changed. Other Windows warnings on other machines are not ruled out.

## Patch

The shared startup code displays the storage failure in the existing startup window and opens the folder picker directly, removing the extra Yes/No confirmation. Cancel exits without scanning. Valid default Evidence storage opens the GUI without this picker. Invalid storage still requires an explicitly chosen approved directory; no automatic fallback or ACL weakening was added. Genuine Admin UAC is retained.

## Verification and staging

- Targeted tests: `dist/usb-auditor-exe/build-env/Scripts/python.exe -m pytest clients/usb_auditor/tests/test_startup_gui.py clients/usb_auditor/tests/test_portable_entry.py -q`: 13 passed. The isolated environment reports an unrelated unknown `asyncio_mode` pytest configuration warning.
- Isolated source GUI checks for Standard and Admin: storage failure opens the picker directly, no Yes/No call; Cancel exits. No collectors ran.
- Built both EXEs with pinned PyInstaller 6.22.3; package integrity and both privilege manifests passed.
- Windows shell `open` check of the staged Standard EXE (same shell verb used by double-click): operator GUI opened with default arguments; zero scans/reports created. This is not a physical mouse double-click test.
- Admin EXE launch: NOT RUN because this session is not elevated and genuine UAC requires human approval. Its shared startup flow and PE manifest were verified separately.
- An early combined GUI test attempt failed during repeated Tcl initialization; the added multi-interpreter test was replaced with isolated per-process GUI checks. The final targeted suite passes.

Candidate: `dist/usb-auditor-startup-fix/package/EIMS_USB_Auditor` (ignored local build).

Manifest SHA-256: `e96943cc62731ef9f0675174db4b173a8d3056eac1ce4af9a437a1df07a24581`.

Initially staged without USB updates or publication. The owner subsequently approved D: replacement and GitHub publication.

## Owner-approved delivery

- Updated `D:\EIMS_USB_Auditor`; verified the deployed package manifest and all file hashes.
- Preserved the original complete folder as `D:\EIMS_USB_Auditor_Backup_20261020_Startup`.
- Copied all four original Evidence files unchanged; verified their SHA-256 hashes against both the original and backup. Candidate empty test Evidence was excluded.
- E: remains unchanged. Source changes and this report are prepared for the existing development branch; no merge to main.

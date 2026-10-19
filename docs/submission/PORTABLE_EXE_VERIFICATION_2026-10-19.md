# Portable Auditor dual EXE verification — 2026-10-19

Historical console-mode result. The subsequent GUI work is documented in
[GUI Auditor handoff](GUI_AUDITOR_HANDOFF_2026-10-19.md).

Status: **built and tested locally; USB release acceptance remains incomplete**.
Baseline: `9bf20d7`, branch `work/eims-engineering-process-2026-10`.
Changes remain uncommitted. No GitHub push, USB replacement, EIMS rebuild,
production database access or service restart was performed for this task.

## Candidate and execution

Clean candidate: `dist/usb-auditor-exe/verified/EIMS_USB_Auditor`.
Keep the whole folder together, including `_internal` and the notices.

| Executable | Native manifest | Actual own Windows 11 x64 execution |
| --- | --- | --- |
| EIMS-Auditor-Standard.exe | asInvoker | current standard user, no UAC, saved JSON/Excel/log |
| EIMS-Auditor-Admin.exe | requireAdministrator | normal UAC, administrator token, saved JSON/Excel/log |

Both returned **3 (PARTIAL)**, retained 423 bounded System/Application events,
and reported firewall collection status `ok`. Partial evidence does not establish
that every query succeeded or that the PC complies with organization policy.
Both retain JSON schema `1`; `launch_mode` and actual privilege are distinct.
Fourteen shared engine module code objects matched between the two PYZ archives.
After adding dependency notices, EXE and `_internal` hashes still match the
actual tested copy; no engine changes were made after those execution tests.

The tested folder contains spaces. PATH excluded Python, and PYTHONHOME/PYTHONPATH
were removed. This is not a test on a clean machine without installed Python.
Native manifests and included runtime support portability; wider compatibility
is not established. Native UAC cancellation was **NOT RUN**.

Default output is `Evidence/reports` (unique JSON/Excel) and `Evidence/logs`
(unique execution logs) beside the EXEs. Standard output hashes were unchanged
after Admin ran. Exact private evidence filenames are indexed in ignored
`Final_CO-OP/verification/portable-exe-output-index.json`; do not publish its
collected reports. Reports were generated in
`Final_CO-OP/verification/Portable EXE Verified Local/Evidence`.

## Tests and boundaries

| Verification | Result |
| --- | --- |
| Build env Python: `-m pytest clients/usb_auditor/tests tools/tests/test_build_usb_package.py` | 123 passed; pytest-asyncio config warning in this synchronous build environment |
| Project venv Python: `-m pytest tests/test_portable_inventory_chain.py` | 2 passed |
| Standard/Admin native execution on own PC | Both saved available evidence; PARTIAL exit 3 |
| PE privilege manifests, file manifest, source freshness, tested binary/runtime identity | PASS |
| `git diff --check`, targeted changed-source private-key/token-pattern screening | PASS; screening is not an exhaustive privacy assessment |
| Synthetic Inventory import → bounded analysis → History with source record identity | PASS, disposable SQLite, TestClient, stub cache, no AI/network requests |
| Live Full EIMS PostgreSQL/browser integration | NOT RUN |
| Physical USB EXE collection | NOT RUN; current D: is FAT32, no approved encrypted-media attestation supplied |
| Copy from approved company share and execute locally | NOT RUN; local-folder execution passed |
| Direct network output | Rejected; no silent AppData redirection |
| Clean PC / Windows Server / alternate-admin account | NOT RUN |
| Disposable-machine before/after OS state comparison | NOT RUN |

Detailed test XML: `Final_CO-OP/verification/portable-exe-engine-tests.xml` and
`portable-inventory-chain-tests.xml`. Synthetic SQLite JSONB adapters are used
only in the integration fixture; this is not PostgreSQL acceptance evidence.

## Security and execution dependencies

Both binaries are **unsigned**. Company signing/allowlisting remains an owner/IT
decision. Hash manifests detect consistency, not publisher authenticity, and
the runtime check is not a security boundary against a malicious executable.
Do not bypass EDR, App Control, UAC or PowerShell policy.

PowerShell remains in security, event, firewall and post-clone checks. Packaging
does not remove that dependency. Blocked checks must remain UNKNOWN/unavailable,
with organization policy findings distinguished from general Windows baseline.
The frozen process restores the normal DLL search path for child Windows tools.

Preflight verifies destination permissions, free space and write/read probes
before importing collectors. New local Evidence receives owner/SYSTEM access;
existing foreign Evidence is not taken over. Removable/non-ACL output requires
an IT-prepared `audit-policy.json` approval reference. This is an approval record,
**not encryption detection**. Do not use it to authorize unencrypted media.

Intentional writes: Evidence directories/ACL, temporary write probes removed
after checking, JSON, Excel and logs. Source inspection found no new configuration
mutation; collectors query system state. Windows/EDR can record execution.
No disposable-machine state-diff test was performed, so zero OS side effects
are not claimed. Automatic sync is disabled; hostname DNS lookup was removed.
Known secret fields and embedded credentials are redacted, but collected evidence
can still be sensitive and must remain private.

Messages retain full text below 64 KiB per event / 8 MiB message total, with
UTF-8 truncation/redaction metadata. Final JSON is limited to 16 MiB. No Security
channel expansion. Previous reports are not overwritten.

## Full EIMS SETUP-only patch

Candidate: `Final_CO-OP/Two_USB/SETUP_NoPrompt/Final_EIMS_Project`.
Removed only the typed `SETUP` gate in `Tools/Runtime.ps1`, and refreshed the
matching source ZIP and integrity metadata. Genuine dependency/license/IT
approval gates remain. PowerShell parsing and existing package/release checks
passed. Start/Stop, compose, dependency file and installation identity hashes
match the original. ZIP members other than Runtime.ps1 are unchanged.
Live SETUP/install and Full EIMS regression: **NOT RUN**. No active service/data
changes were made. Physical E: remains unchanged.

## Artifact hashes (SHA-256)

| Artifact | SHA-256 |
| --- | --- |
| Auditor MANIFEST.txt, 81 files / 27,309,409 bytes | `466c5c30f8668a1b1873916939d87fda387fadcf88667f9617893dfcc5b0a0e2` |
| Standard EXE | `e9499f8e5ff0720d4aa6ceb8bc78f7c01b45ff91d76652fe2ff3ca7e6fae6738` |
| Admin EXE | `addcfd54365c2d0bbbf6b2e31740bafdcad796cda3d684e51dde82ba9375f209` |
| SETUP-only candidate MANIFEST.txt | `0b4847292b25bc3171a441d697b7aed0beb63181ed37b3d95370789a32b4fa54` |

Pinned environment: `tools/auditor_exe_requirements.txt`; Python 3.14.6,
PyInstaller 6.22.3. Build recipe: `tools/build_auditor_exe.py` and
`clients/usb_auditor/PortableAuditors.spec`. BUILD_PROVENANCE records source
hashes and dependency versions. Bit-for-bit reproducible builds are not proven.
The earlier `dist/usb-auditor-exe/package` candidate is superseded, not a release.

Changed source groups: portable entry/Standard/Admin/spec; subprocess wrapper;
system/security/events/firewall/setup collectors; main/JSON/Excel exporters;
portable/event/inventory tests; EXE and legacy source packaging; Runtime.ps1 and
`tools/handover/prepare_setup_patch.py`. Existing EIMS UI is unchanged.

## Release decision and remaining owner work

Neither physical USB changed. Original D: and E: manifest hashes still match
their previously verified copy receipts. The legacy launchers remain fallback.
Existing clone receipts still describe the legacy release; this EXE candidate
has not been promoted to the physical-USB clone workflow.

1. Obtain approved encrypted media/policy and signing/allowlisting decision;
   then authorize a separate USB acceptance test without losing fallback data.
2. Test native UAC refusal and an actual company-share-to-local copy under the
   intended workstation account. Keep blocked checks explicitly partial.
3. Approve D: EXE replacement and E: SETUP-only replacement separately after
   acceptance. Until then, use the staged paths and preserve both working USBs.

No new research is required to explain the measured local result. Remaining
items require actual environment/IT acceptance, not invented test results.

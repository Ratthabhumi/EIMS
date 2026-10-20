# Full EIMS: offline prerequisite setup

Internal company handover, as confirmed by the owner. This extends the existing
prepared USB package; it does not redesign EIMS or change the Auditor.

## Delivered behavior

`SETUP.bat` checks Windows 11 x64 build 22631+, 8 GiB RAM/free working space,
hardware virtualization, WSL, local Linux Docker Engine and Compose v2. A working
local engine is reused without reinstalling/upgrading. Remote contexts and Windows
container engines stop with instructions; no context or unrelated project changes.

When needed, SETUP verifies the bundled installer's size, SHA-256 and valid vendor
Authenticode signature before launching the official UI. Docker uses
`install --user --backend=wsl-2`; it never accepts terms automatically. WSL uses
the official MSI; VirtualMachinePlatform activation uses normal Windows UAC,
`/LimitAccess` and `/norestart`. No EIMS `INSTALL`/`YES` typing is required. A protected
local checkpoint prevents repeated setup in the same boot after REBOOT REQUIRED.
Restart is manual; rerunning SETUP resumes prerequisite checks.

Elapsed time is shown while installing/starting; engine readiness waits are bounded.
Installer timeout does not kill system servicing. Cancellation/corruption blocks
EIMS setup. Vendor license, IT policy, UAC and offline signature trust remain real
requirements. An existing compatible Linux backend can be reused without installing
WSL unnecessarily.

Prepared Python/Node/frontend/images, package/media IDs, compose configuration,
database credentials and USB checkpoint behavior are preserved. No pip/npm/build
runs on the prepared path. `Start.bat` remains the subsequent-use entry point.
New readiness labels follow existing service/synthetic smoke checks, never precede them.

## Verified vendor assets (local-only, excluded from public Git)

| Asset | Bytes | SHA-256 |
|---|---:|---|
| Docker Desktop 4.85.0.235549 x64 | 625139632 | `5417cedc1aeb16b488b8084025246b64a5e9da4d71388f324b107140dfe00699` |
| WSL 2.7.11.0 x64 MSI | 258990080 | `a611ddacee689d2fb1fb5319e58af7f3998864d86cdce632eadd8e61614a0f9d` |

Both signatures were Valid: Docker Inc / Microsoft Corporation. Docker digest
matched its [official checksum file](https://desktop.docker.com/win/main/amd64/235549/checksums.txt);
WSL matched the digest/size in the [Microsoft release API](https://api.github.com/repos/microsoft/WSL/releases/tags/2.7.11).
The local catalog records exact URLs, versions, sizes and publisher patterns.

The [Docker Windows instructions](https://docs.docker.com/desktop/setup/install/windows-install/)
describe per-user WSL installation and prerequisites. The
[Microsoft offline instructions](https://learn.microsoft.com/en-us/windows/wsl/install#offline-install)
describe the MSI and Windows feature/restart requirements. No Ubuntu distribution
is bundled or required by this setup helper.

Internal use does **not** establish license eligibility. Company IT must verify
subscription entitlement, internal installer transfer permission and authorized
Windows changes using [Docker licensing guidance](https://docs.docker.com/subscription-billing/desktop-license/)
and the [subscription agreement](https://www.docker.com/legal/docker-subscription-service-agreement/).
No legal compliance or production approval is claimed. This is the remaining
research/IT question; no further architecture research is necessary for this change.

## Validation actually performed

`dist/usb-auditor-exe/build-env/Scripts/python.exe -m pytest tools/tests/test_offline_prerequisites.py tools/tests/test_handover_process_identity.py tools/tests/test_prepared_runtime.py tools/tests/test_usb_backup.py tools/tests/test_command_runner.py -q --disable-warnings --junitxml=Final_CO-OP/verification/offline-prerequisite-tests.xml`

Result: **37 passed**, zero skipped/failures (final run).
Installer/OS transition cases are mocks: existing-ready, stopped engine, missing
Docker/WSL, feature activation/reboot/same-boot/resume, cancellation/UAC rejection,
corrupt installer, disabled virtualization, remote context, Windows containers.
Additional checks cover missing/unsigned installers, bounded startup timeout,
real native subprocess argument handling, process ownership, prepared runtime,
USB snapshot preservation and command progress. Mocks do not prove a fresh install.

An earlier run encountered a transient access-denied rename in isolated backup
test storage; the complete rerun passed. Its cause was not established.

Windows PowerShell 5.1 and PowerShell 7 parsed both scripts successfully. Actual
staged `Runtime.ps1 -Action Preflight -NoBrowser` under Windows PowerShell passed:
Windows PASS, WSL READY, existing Linux Docker/Compose READY. This preflight made
no installation, credential, database or service changes. All seven existing EIMS
containers remained running. Exact package inventory, hashes and internal release
review gate passed. Prepared runtime/images and non-allowlisted baseline files
were verified byte-identical.

**NOT RUN:** installation on a clean second physical PC; real missing-component
installer/UAC/reboot flows; a new end-to-end SETUP run for this candidate. Prior
prepared EIMS startup/restore evidence belongs to
[the earlier handover](PREPARED_USB_HANDOVER_2026-10-20.md), not a new measurement.
No frontend changes: TypeScript/build/UI checks were not repeated in this change.

## Reproduce packaging / delivery boundary

Create a new local staging copy of the verified prepared package. Place the two
official assets at the catalog paths, then run:

`python tools/handover/prepare_offline_prerequisites.py <staging-folder> --baseline <verified-original-folder>`

This checks baseline preservation and signatures, refreshes helper sources/source
ledger, screens archives for private artifacts/historical defaults and regenerates
the exact security inventory, manifest and checksums. It does not download,
install or write to USB. The prepared application runtime is reused without rebuild.

Local candidate: `Final_CO-OP/Offline_Docker_Setup/Final_EIMS_Project`, 83 files,
1,276,093,192 bytes. Manifest SHA-256:
`2897a7cc5bfa7e801bf32c1201ebc598a687b36081a2becc276fd58bcb224187`.
The candidate, installer binaries, detailed test logs and private data remain ignored.
Source/public documentation only is eligible for GitHub publication.

Physical E: replacement requires separate owner approval with a dated backup and
post-copy verification. Do not alter `EIMS_Data` or D:. No production approval,
historical credential rotation or fresh-PC certification is inferred from packaging.

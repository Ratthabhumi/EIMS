# EIMS BitLocker Remediation Assistant

A **separate, manually executed** safety-first utility for BitLocker state
assessment and (only where permitted) protection resume on EIMS endpoints.

It is deliberately **isolated** from the web platform:

- It lives under `tools/bitlocker_remediation/`.
- It is **never** reachable from the dashboard, API, or any other web-triggered
  path. There is no endpoint that launches remediation.
- It must be run by a human in a local, elevated terminal.

---

## Files

| File | Purpose |
|------|---------|
| `Remediate-BitLocker.ps1` | Read-only assessment + strictly-gated resume action |
| `Run-BitLocker-Remediation.bat` | Convenience launcher (passes arguments through) |
| `remediation-audit.log` | Created at runtime — timestamped, secret-free audit trail |

---

## Usage

```powershell
# 1) Plan-only assessment (default, no change to the machine)
.\Run-BitLocker-Remediation.bat

# 2) Authorized remediation (resume suspended protection)
.\Run-BitLocker-Remediation.bat -Apply
```

Or call the script directly:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Remediate-BitLocker.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\Remediate-BitLocker.ps1 -Apply
```

### Gates for `-Apply`

1. **Plan must permit it** — only CASE 2 (encrypted + protection suspended
   + recovery protector present) can ever apply.
2. **Administrator shell required** — otherwise the tool stops (`exit 3`).
3. **Exact typed confirmation** — the operator must type
   `REMEDIATE C:` (or `REMEDIATE D:` for `-MountPoint D:`) verbatim. Any
   mismatch aborts with no change (`exit 4`).

---

## Decision Matrix

| CASE | Observed state | Decision | `-Apply` effect |
|------|----------------|----------|-----------------|
| 1 | Protection **On**, `FullyEncrypted`, 100%, recovery protector present | `NO ACTION REQUIRED` | none |
| 2 | `FullyEncrypted` but Protection **Off** (suspended), recovery protector present | `RESUME PROTECTION` | `Resume-BitLocker` only |
| 3 | Encryption / decryption in progress, or volume not yet fully encrypted | `IN PROGRESS` | none |
| 4 | Encrypted / protected but **no recovery protector** | `BLOCKED — RECOVERY / ESCROW REQUIRED` | none (never auto-creates a key) |
| 5 | `FullyDecrypted`, Protection **Off** | `ACTION REQUIRED` (approved encryption policy needed) | none (never enables BitLocker) |
| 6 | Unknown state or query failure | `FAIL SAFE` | none |

---

## What this tool will NEVER do

- Retrieve, print, write, or export a **BitLocker Recovery Password**.
- Create a recovery password or key protector (`Add-BitLockerKeyProtector` / manage-bde).
- Enable BitLocker encryption (`Enable-BitLocker`).
- Decrypt a drive (`Disable-BitLocker`).
- Reboot the machine (`Restart-Computer`, `shutdown`, etc.). If a resume cannot
  take effect until reboot, the operator is told **manually** via the log
  (`reboot_required=manual`).
- Be invoked from the dashboard, API, scheduler, or any remote trigger.

---

## Audit log

Every run appends one line to `remediation-audit.log`:

```
timestamp | hostname | mountpoint | before(volume|protection) | decision_code | case | outcome | detail
```

The log never contains secret material — only counts and status values.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Completed (no action needed, plan-only, or successful resume) |
| 3 | `-Apply` used without Administrator |
| 4 | Confirmation mismatch — aborted |
| 5 | `Resume-BitLocker` failed |

## Escalation / handover note

CASE 4 and CASE 5 are **not** solvable by this tool by design:

- CASE 4 (missing recovery protector): provision a protector through your
  approved **BitLocker recovery-key escrow process**, then re-run the tool.
- CASE 5 (unencrypted): obtain **approved encryption-enablement policy**
  sign-off before enabling BitLocker through the standard enterprise process.

This tool exists to keep endpoints *observable and recoverable* — remediation
of missing keys still requires the formal escrow/policy workflows.
# EIMS Compose host-isolation audit delta — 31 October 2026

## Provenance and boundary

Source-only continuation of Draft PR #9 (`90324cf9925bc556b77235cef2e386b1bf97a6ab`) stacked on PR #8 → #7 → #6 → #5. This branch changes only the existing read-only Compose static scanner, its hermetic tests and this note. It does not create or certify a secure deployment profile. No Docker daemon, Redis/PostgreSQL/MinIO service, physical device, USB, remote machine, credentials, operational data or Human Gold judgments were accessed. `main` remains outside this work.

## Incremental findings not covered by PR #9

PR #9 already detects privileged containers, direct host networking/PID, Docker socket mounts, and unresolved Compose include/extends. This delta adds conservative HIGH findings for:

| Rule | Static trigger | Interpretation |
| --- | --- | --- |
| `HOST_USER_NAMESPACE` | `userns_mode: host` | Host user namespace selected |
| `HOST_IPC` | `ipc: host` | Host IPC namespace shared |
| `HOST_DEVICE_ACCESS` | Nonempty `devices` or `device_cgroup_rules` | Host device access requires explicit security review |
| `ADDED_LINUX_CAPABILITIES` | Nonempty `cap_add` | Additional Linux capabilities require review; not proof of compromise |
| `DISABLED_SECURITY_PROFILE` | `seccomp:unconfined`, `apparmor:unconfined`, or `label:disable` security option | Confinement disabled |
| `INDIRECT_NETWORK_NAMESPACE` | `network_mode: service:...` or `container:...` | Referenced namespace not resolved by this scanner |
| `INDIRECT_PID_NAMESPACE` | `pid: service:...` or `container:...` | Referenced namespace not resolved by this scanner |

The scanner emits generic rule descriptions rather than capability names, device paths, inherited service identifiers or security-option strings. `--mode dev` continues to inventory findings without blocking development; `--mode secure` rejects HIGH findings. The new fixtures are synthetic and do not touch the Docker runtime.

This is a **conservative gate**, not a claim that every use of additional capabilities or host devices is malicious. Approved exceptions need an explicit threat model and a separately reviewed effective Compose configuration. The scanner still does not resolve interpolation, inherited configuration, profiles, secrets, image CVEs or runtime permissions.

## Reliability, observability and device evidence carried forward unchanged

- **Redis telemetry:** `XREAD` + in-memory cursor and `XACK` consumer-group mismatch; SQL-commit-before-ACK replay and swallowed ACK errors remain strict XFAIL. No claim of at-least-once or exactly-once durability.
- **EVTX:** PR #7 fail-closed queue acceptance and PR #8 log minimization remain. Destructive `RPOP` on MinIO failure and partial publication remain strict XFAIL; no live recovery demonstrated.
- **Dev vs secure Compose:** the existing dev Compose includes host-published ports, development credentials, floating images and an anonymously public MinIO bucket. This is *not* evidence of internet exposure and *not* an approved secure profile.
- **Observability:** FastAPI `/metrics` and a Prometheus config exist; `host.docker.internal:8000` depends on host setup. Prometheus target-UP, Grafana dashboard/datasource, Loki shipping, alerts and recovery observability remain NOT_TESTED.
- **Device capability:** Windows telemetry/USB/OCR source exists but current live hardware interoperability is NOT_TESTED. Fortinet/Cisco/VMware/Veeam log parser support is offline file-analysis capability, not live management integration. NAS/UPS/SNMP integration remains NOT_VERIFIED.
- **Graduation Analyzer:** Draft PR #10 has separate 322-test / 3-job CI evidence; Human Gold remains zero genuine judgments and secure browser runtime remains blocked. This branch does not change those results.

## Verification requirement

The branch's new tests must run in the existing `telemetry-reliability` CI job and the exact final head must be checked. Until the run completes, implementation is **PUSHED_NOT_CI_VERIFIED**, not PASS. Existing 4 strict XFAIL must not be reclassified as successes.

## Next most valuable action

The next engineering step is an explicitly approved, isolated synthetic Redis 7 + PostgreSQL 16 fault-injection test bed for `XREADGROUP`, pending reclaim, SQL stream-ID idempotency, ACK/trim retention and both crash windows. Do not change production worker semantics on the strength of static tests alone. The EVTX processing-list/DLQ/idempotency design is a separate second gate. Secure Compose deployment and live observability require operator authorization and runtime evidence.

References: [Compose services](https://docs.docker.com/reference/compose-file/services/), [Docker Engine security](https://docs.docker.com/engine/security/), [Redis XREADGROUP](https://redis.io/docs/latest/commands/xreadgroup/), [Redis XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/).

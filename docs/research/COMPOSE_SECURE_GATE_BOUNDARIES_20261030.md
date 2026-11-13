# Compose secure-gate boundary extension — 30 October 2026

## Scope and provenance

Draft PR #9 is stacked on Draft PR #8 (`audit/evtx-worker-fault-boundary-20261029`, base `133dfa55a47dc421917372a101b172c8df4cb328`), preserving PR #7 -> #6 -> #5 ancestry. This is a source-only, synthetic-only extension to the pre-existing PR #6 Compose scanner. No Docker daemon, runtime container, host network, customer data, credentials, remote machine, USB, or production resource was accessed. `main` and Human Gold are untouched.

## Newly enforced high-severity static findings

| Rule | Trigger | Why the prior scanner could give false confidence |
| --- | --- | --- |
| `HOST_NETWORK` | `network_mode: host` | Host networking does not require a `ports:` declaration |
| `PRIVILEGED_CONTAINER` | `privileged: true` | Container privileges were not inspected |
| `HOST_PID` | `pid: host` | Host PID namespace was not inspected |
| `DOCKER_SOCKET_MOUNT` | Short or long bind of `/var/run/docker.sock` or `/run/docker.sock` | Docker API control can be reachable even through a read-only socket bind |
| `UNRESOLVED_INCLUDE` | Nonempty top-level Compose `include` | Imported Compose files were never parsed |
| `UNRESOLVED_EXTENDS` | Service-level `extends` | Inherited service configuration was never parsed |

All findings use generic text without echoing file paths, mount strings or secret-like values. In `--mode dev`, findings are inventoried but do not fail CI; in `--mode secure`, any high finding exits nonzero. `include` and `extends` are **not resolved**: a high finding means **not certified**, not proof the inherited file is malicious.

Four hermetic test contracts cover short and long socket syntax, host namespace and privileged settings, inherited configuration with a synthetic sensitive filename, secure-mode failure and output redaction, and ordinary named volumes/bridge mode without false positives. Existing PR #6 scanner tests remain unchanged.

## Existing boundaries deliberately preserved

- **Development Compose is still not a secure deployment profile.** Existing inline dev credentials, host port publications, MinIO public bucket, Redis authentication gap and floating images remain in the static inventory. This PR does not rewrite `docker-compose.yml` or approve its deployment.
- **Redis Stream delivery:** `XREAD`/in-memory cursor vs `XACK` consumer-group mismatch, post-SQL-commit replay and swallowed ACK errors remain unresolved. No consumer-group migration, SQL stream-ID unique constraint, or Redis/PostgreSQL crash experiment was performed.
- **EVTX queue:** PR #7 producer fail-closed and PR #8 log minimization remain; destructive `RPOP` loss on MinIO outage/partial publication remains unresolved. Existing strict XFAIL contracts must remain visible.
- **Observability:** `/metrics` and Prometheus configuration exist, but target-UP, Grafana provisioning, Loki shipper, alert delivery and actual end-to-end operation are not verified.
- **Device capability:** Windows agent/EVTX, USB auditor and OCR code exist but live interoperability is untested. Fortinet/Cisco/VMware/Veeam parser support does not establish live device integration; NAS/UPS/SNMP are unverified.

## Acceptance and limits

This scanner is a **partial source inventory**, not a complete Compose security validator. It does not resolve `include`/`extends`, expand variables, verify secret-file permissions, evaluate build Dockerfiles, scan image CVEs, attest runtime controls, or prove isolation on an installed host. The safe-pattern fixture is synthetic and is not an approved deployment template. A secure profile needs review of its fully resolved effective configuration and runtime evidence before any release claim.

CI must be verified at the exact final PR head, including the telemetry job and pre-existing 4 strict XFAILs. The RED test-only commit is `df448f591db1db5b799cd4411014022c059e55b8`; the GREEN result is to be established from GitHub Actions, not assumed from this document.

## Next highest-value work

1. Design and test `XREADGROUP` + pending reclaim (`XPENDING`/`XAUTOCLAIM`) with PostgreSQL stream-ID dedup in an **isolated synthetic** environment; explicitly test both crash windows and retention.
2. Separately design EVTX processing-list recovery, poison-task policy and stable per-event deduplication before changing `RPOP` semantics.
3. Prepare a reviewed secure Compose profile and verify fully resolved configuration, image provenance, secrets policy, runtime target-UP and alert delivery; do not treat the current scanner as certification.

Primary references:
- Docker Compose services (host networking, privileged, PID): https://docs.docker.com/reference/compose-file/services/
- Docker Compose trust model (include/extends): https://docs.docker.com/compose/trust-model/
- Docker Engine security and daemon access: https://docs.docker.com/engine/security/
- Redis consumer-group semantics: https://redis.io/docs/latest/commands/xreadgroup/

# Public repository security review

## Findings and publication gate

Tracked Compose and application configuration contain literal development credentials/keys. Historical commits retain them. Values are intentionally not reproduced here. Candidate scan locations are recorded privately; a static candidate is not automatically a genuine secret. Repository visibility is checked against the GitHub API in the private audit.

Owner confirmation of prior usage and rotation is required before treating this exposure as resolved. A read-only connection using the preserved development configuration reached the local PostgreSQL instance during the test-safety follow-up, so deployment usage cannot be dismissed as example-only. Do not rotate credentials, restart services, rewrite history or change production configuration in this task. A remediation branch does not invalidate credentials already published. If this gate remains unresolved, create reviewed local commits and withhold remote push, as required by the task.

## Owner rotation checklist

Publication remains BLOCKED. Owner closure also requires a reviewed public-file/secret screen, read-only review of the three exact incident rows using the private report, and separate approval before any selective row cleanup. No operational access is authorized by this checklist. Keep old worktree/ZIP removal approval separate from credential maintenance and database cleanup approval.

- [ ] Identify actual deployments and whether published values were ever used (PostgreSQL, PgBouncer, MinIO, Grafana, JWT signing key, admin bearer/bootstrap settings).
- [ ] Establish a maintenance window and backup/recovery procedure; record owners, not secret values, in Git.
- [ ] Generate unique credentials privately; update all dependent services consistently. PostgreSQL and Grafana initialization variables do not change passwords already stored in existing volumes.
- [ ] Revoke or replace exposed credentials; invalidate affected sessions/tokens where applicable; verify new access and that old access fails.
- [ ] Apply environment-based configuration during an authorized deployment. Never paste operational values into tracked templates, chat reports or test artifacts.
- [ ] Review access logs and any additional historical exposure; use GitHub guidance for next steps. History rewriting is a separate authorized operation.

## Upload and response review

Existing bundle limits: 12 files, 5 MiB each, 30 MiB total, bounded reads, extension validation and safe basenames. This change adds common filename/content validation, JSON alignment, EVTX signature checking, UTF-8/binary checks and bounded PNG/JPEG validation (8 million pixels). Single-upload and paste errors now return explicit 4xx responses before analysis/persistence. Client MIME is not trusted to select the OCR path. Authorization dependency permits unauthenticated demo identity by design; protected deployment requires secure mode. Role/tenant isolation, OCR execution timeouts, reverse-proxy pre-parser request limits and external-provider privacy remain deployment/evaluation concerns. These checks are layered controls, not antivirus or a complete XML/HTML sandbox.

Treat file names, content types, HTML, XML and log text as untrusted. Extension allowlisting is not content validation. Preserve evidence filenames as display metadata only, never executable or arbitrary output paths. Source evidence can contain identifiers: avoid public raw exports. Optional AI/web processing needs explicit privacy policy; this task does not transmit company logs.

Review also found the development bootstrap password and provider request exceptions could leak secrets in logs; new code removes those values from these logging paths. Existing logs and the preserved standalone client require owner review. PDF export previously interpolated raw result strings into HTML; the new export escapes nested strings without changing original stored evidence. Phase 0 did not start a backend runtime, but a later legacy auth TestClient run started application lifespan and wrote three synthetic service-session rows; see TEST_SAFETY_INCIDENT.md. No penetration test was performed.

Compose now requires private environment credentials; the example file contains empty secret slots. The non-development settings guard also rejects empty or whitespace-only secret values, so blank template values cannot bypass the existing production guard. Live services were not restarted or reconfigured. Historical application development defaults remain in preserved code/history and must not be used operationally. Existing MinIO setup also makes its OCR bucket public; deployment privacy review is still required. This pass does not silently change that live bucket policy or rewrite supporting OCR behavior.

Sources checked 15 October 2026: [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html); [GitHub sensitive-data remediation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). OWASP informs layered upload controls; GitHub recommends revocation/rotation before history work.

## Consolidation review

Private assets are in ignored/untracked EIMS/.local-private; detailed manifests and exact incident identifiers remain outside public Git. Current tests check blank/whitespace rejection in non-development application settings. Compose required-variable expansion rejects empty/unset values but alone does not reject all whitespace-only service values: the owner must validate private deployment inputs before maintenance. This is not a completed rotation or a verified safe deployment.

Rotation sequence remains owner controlled: prepare recoverable backup and unique private values, coordinate PostgreSQL/PgBouncer/client settings, MinIO clients/bucket privacy and Grafana's persisted admin account, then update services during an authorized maintenance window. JWT changes require session/token invalidation planning. Verify authorized access with new credentials and refusal of the former credentials without recording either value in outputs. Environment initialization values do not rotate existing volume-stored accounts. No operational access, restart, credential change or push occurred in this continuation.

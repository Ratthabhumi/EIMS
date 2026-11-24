# Infrastructure Credential Rotation Acceptance

Date: 2026-11-19  
Branch: `demo/2026-11-24`  
Images: Grafana `grafana/grafana:latest` (runtime 13.1.3), MinIO `minio/minio:latest`

## Verdict

**ACCEPTED WITH LIMITATIONS**

## Strategy (evidence-based)

### Grafana

- `GF_SECURITY_ADMIN_PASSWORD` only applies on **first** DB create; volume `grafana_storage` already exists.
- Rotation used official CLI: `grafana cli admin reset-admin-password --password-from-stdin` inside `eims-grafana`.
- New admin password: login HTTP **200**; previous compose bootstrap password: HTTP **401**.
- After `docker restart eims-grafana`, new password still login **200** (persisted in Grafana SQLite volume).

### MinIO

- Did **not** rotate `MINIO_ROOT_*` in Compose (would risk breaking EIMS S3 clients that still use root).
- Created dedicated IAM user `eims_console_admin` with built-in `consoleAdmin` policy for Console (`:9001`).
- Root credentials remain for application/bootstrap; Console operators should use the IAM user.
- Backend health after change: MinIO tier **UP**; API `/minio/health/live` **200**.

## Secret storage

| Item | Location |
|---|---|
| Generated Grafana + MinIO console credentials | `%TEMP%\eims-infra-credentials.secret` (outside repo) |
| Tracked compose / docs | **No live secrets written** |

**Do not commit** the TEMP secret file. Operator handoff: retrieve from that local path on Mew only.

## Rollback

- Grafana: `grafana cli admin reset-admin-password` again with a known operator password.
- MinIO console user: `mc admin user remove` / disable; root unchanged so app path remains.

## Limitations

- Compose still embeds historical bootstrap env for Grafana/MinIO for **fresh** volume creates — operators must rotate after first boot (documented).
- Root MinIO password not rotated this round (intentional least-risk); console admin IAM user is the human admin path.
- Automated login test for MinIO Console UI HTML session not automated; IAM user creation verified via `mc admin user info`.

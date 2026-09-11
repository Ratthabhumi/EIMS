# Security Policy & Vulnerability Disclosure

The **Enterprise Infrastructure Management System (EIMS)** is a **Source-Available** engineering project maintained for technical portfolio demonstration and architectural evaluation. This document outlines our security posture, private disclosure process, authentication boundaries, and best-effort vulnerability response targets.

> [!NOTE]
> EIMS is currently in a pre-graduation engineering evaluation state and is not offered as a commercially supported SaaS product. The response timelines below represent best-effort engineering targets, not contractual Service Level Agreements (SLAs).

---

## 1. Project Status & Supported Versions

Security fixes and architectural hardening updates are applied to our current canonical release branch:

| Version | Release Status | Security Hardening Posture |
| :--- | :--- | :--- |
| `v0.3.0` | Current Canonical Release | Active hardening and security evaluation under Source-Available license. |
| `v1.x` | Future Commercial Target | Planned production support upon formal enterprise release. |

---

## 2. Reporting a Suspected Vulnerability

We request that external security researchers, architectural evaluation reviewers, and engineering observers **do not report security defects or unauthenticated exploit vectors via public GitHub Issues**. Publicly disclosing unresolved vulnerabilities endangers evaluation environments and downstream testing setups.

### Private Reporting Channel
Please report suspected vulnerabilities privately to the project maintainers:
- **Primary Channel**: Use **GitHub Private Vulnerability Reporting** via the repository Security tab (if enabled).
- **Direct Maintainer Contact**: Contact the repository owner directly through private repository channels or authorized maintainer profile links.
- **Do NOT**: Post exploit details, proof-of-concept scripts, or reproduction steps in public issues or pull request comments.

### Required Report Content
When submitting a diagnostic disclosure, please include:
1. Specific endpoint URI, architectural container (e.g., FastAPI Core Gateway, OCR Worker), or dependency implicated in the issue.
2. Step-by-step reproduction instructions and minimal proof-of-concept payload.
3. Your evaluation of the potential impact on system ACID transactional integrity, data privacy, or RBAC authorization boundaries.

---

## 3. Best-Effort Vulnerability Response Targets

Our engineering maintainers review private security disclosures on a best-effort basis against the following target timeframes:
- **Initial Acknowledgment**: Target within **48 hours** of report receipt.
- **Triage & Reproduction Confirmation**: Target within **5 business days** of acknowledgment.
- **Mitigation Target**: Target within **14 business days** for Critical vulnerabilities (CVE score >= 9.0), or within **30 business days** for Medium/High issues.

Upon validation and deployment of an official fix, credit will be given in release notes unless anonymity is requested.

---

## 4. Security Boundaries & Authentication Modes

EIMS architecture enforces strict environment-aware security boundaries via the `EIMS_AUTH_MODE` configuration:

| Mode | Authorization Surface | Deployment Context & Constraints |
| :--- | :--- | :--- |
| **Demo Mode** (`EIMS_AUTH_MODE=demo`) | Normal dashboard navigation and evaluation writes permitted without authentication. | **Restricted to local development and trusted demonstration environments.** Must NEVER be routed to or exposed on untrusted public networks. |
| **Secure Mode** (`EIMS_AUTH_MODE=secure`) | Zero-trust authentication enforced. Protected endpoints require valid JWT. Administrative mutations require an authenticated user with `role == "admin"` or an authorized server-side `EIMS_ADMIN_TOKEN`. | **Mandatory for staging, production, and any internet-accessible deployment.** |

### Secret Hygiene & Hardening Guarantees
1. **Zero Privileged Tokens in Active Frontend Source**: No frontend bundle, client-side script, or active source code file contains privileged static tokens (e.g., `EIMS-ADMIN-TOKEN` was removed in Phase 12.3; admin write operations require authenticated server credentials or Admin JWT).
2. **Environment Secret Enforcement**: The FastAPI backend validates configuration integrity during startup (`model_post_init`). In `staging` or `production` tiers, the server refuses to boot if `SECRET_KEY`, `JWT_SECRET_KEY`, `ADMIN_TOKEN`, or `ADMIN_PASSWORD` remain set to development placeholder defaults.
3. **Password Cryptography**: Operator passwords utilize PBKDF2-HMAC-SHA256 with cryptographically random 16-byte per-user salts. Plaintext credentials are never persisted to disk or database tables.

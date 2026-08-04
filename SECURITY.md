# Security Policy & Vulnerability Disclosure

The **Enterprise Infrastructure Management System (EIMS)** prioritizes strict cryptographic enforcement and platform security across our **Source-Available** architecture. This policy outlines our supported platform versions, safe private vulnerability reporting procedures, and expected response time SLAs.

---

## 1. Supported Versions

Security patches and architectural hardening updates are actively applied solely to our current major release branches:

| Major Version | Release Status | Active Security Support & Patching |
| :--- | :--- | :--- |
| `v0.x` (Sprint Dev) | Active Development | :white_check_mark: Fully Supported under Source-Available Evaluation |
| `v1.x` (Target) | Production Stable | :white_check_mark: Fully Supported upon Commercial/Enterprise Release |

---

## 2. Reporting a Suspected Vulnerability

We request that external security researchers, architectural evaluation reviewers, and engineering observers **do not report security defects or unauthenticated exploit vectors via public GitHub Issues**. Publicly disclosing unresolved vulnerabilities endangers evaluation infrastructures and future enterprise deployments.

### Private Reporting Channel
Please transmit an encrypted or private vulnerability report directly to our core engineering maintainers via GitHub Private Advisory Channels or by sending a formal notification to:
- **Project Maintainer:** [Ratthabhumi / EIMS Security Team] via GitHub Private Vulnerability Reporting on our repository interface.

### Required Report Content
When submitting a diagnostic disclosure, include:
1. Specific endpoint URI, architectural container (e.g., FastAPI Core Gateway, OCR Worker), or dependency implicated in the bug.
2. Comprehensive instructions and reproduction script samples required to validate the flaw.
3. Your evaluation of the potential impact on system ACID transactional integrity, data privacy, or RBAC authorization boundaries.

---

## 3. Vulnerability Response SLAs

Our Engineering Security Maintainers adhere to strict triage response targets upon receiving a disclosure:
- **Initial Acknowledgment:** Within **48 hours** of report receipt.
- **Triage & Reproduction Confirmation:** Within **5 business days** of acknowledgment.
- **Mitigation Release Target:** Within **14 business days** for Critical vulnerabilities (CVE score >= 9.0), or within **30 business days** for Medium/High flaws.

Once an official patch release is validated and distributed across our package registries, public acknowledgment will be credited to the reporting evaluator within our release notes unless anonymity is requested.

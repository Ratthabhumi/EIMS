# Contributing to EIMS

Thank you for your interest in the **Enterprise Infrastructure Management System (EIMS)**. To preserve architectural integrity, maintainability, and structural traceability across all system modules, internal development and authorized reviews follow our established engineering conventions.

---

## 1. Source-Available Licensing Policy & Contribution Scope

> [!IMPORTANT]
> **EIMS is a Source-Available Software Product under All Rights Reserved.** 
> This repository is maintained publicly exclusively for architectural evaluation and technical portfolio demonstration. It is **not** an open-source project.

Public repository visibility does **not** grant automatic contribution rights. Pull Requests from external parties may be reviewed, accepted, or closed without review at the sole discretion of the repository owner.

By submitting issue feedback, bug evaluations, or authorized code contributions, you explicitly acknowledge and agree that:
1. All submitted contributions become subject to our **All Rights Reserved** proprietary software policy ([LICENSE](LICENSE)).
2. Submitting contributions does not grant you, nor any third party, open-source usage rights, redistribution permissions, or commercial exploitation licenses.
3. Unauthorized commercial reproduction, redistribution, or derivation of source logic from this repository remains strictly barred.

---

## 2. Documentation-First Governance (EDS v1.0.0)

EIMS operates strictly under a **Documentation-First** software development life cycle. Our documentation foundation—the **EIMS Documentation System (EDS v1.0.0)**—serves as the project Constitution.

Before proposing database schema changes, endpoint APIs, or structural component refactoring, authorized engineers **must first update the relevant Core Law specifications**:
- [Master Plan Specification](01_EIMS_MASTER_PLAN.md)
- [Product Requirements Document](02_PRODUCT_REQUIREMENTS_DOCUMENT.md)
- [Software Architecture Document](03_SOFTWARE_ARCHITECTURE_DOCUMENT.md)
- [Database Design Specification](04_DATABASE_DESIGN.md)
- [API Specification](05_API_SPECIFICATION.md)

### Canonical Vocabulary Compliance
Do not invent subjective domain synonyms or abbreviations in source code, variable names, database tables, or documentation comments. Consult our authoritative [Terminology Standard](docs/_style/terminology.md). For example:
- **Use:** `Infrastructure Asset`, `Discovery Agent`, `Asset Registry`, `Compliance Score`, `OCR Asset Registration`, `Windows Log Analysis`, `Telemetry Collector`.
- **Prohibited:** `Scanner`, `Agent Bot`, `Machine DB`, `Security Rating`, `Image Reader`, `Win Logs`, `Input API`.

---

## 3. Git Branching & Naming Conventions

Internal development topic branches adhere to standard type prefixing:
- `feature/<ticket-id>-<short-description>` (e.g., `feature/EIMS-42-redis-ingestion-worker`)
- `fix/<ticket-id>-<short-description>` (e.g., `fix/EIMS-89-pgbouncer-connection-timeout`)
- `docs/<short-description>` (e.g., `docs/align-api-spec-error-codes`)
- `refactor/<short-description>` (e.g., `refactor/optimize-pydantic-validation`)

---

## 4. Conventional Commits Standard

To maintain a clean and traceable project history, commit messages must comply with **[Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)**:

```
<type>(<optional-scope>): <short descriptive imperative subject>

[optional body explaining technical rationale and architecture trade-offs]

[optional footer referencing issue IDs or BREAKING CHANGE declarations]
```

### Approved Commit Types:
- `feat`: Introduction of a new operational feature or ingestion API endpoint.
- `fix`: Resolution of a runtime exception, database validation error, or security flaw.
- `docs`: Additions or modifications restricted strictly to EDS documentation or Markdown contracts.
- `chore`: Maintenance operations affecting build scripts, Git ignore rules, or container orchestration without altering source logic.
- `refactor`: Structural code cleanup that neither adds a new feature nor patches a defect.
- `test`: Creation of automated unit, integration, or load benchmarking verification test suites.

---

## 5. Code Review & Pull Request Guidelines

When submitting an authorized Pull Request against `main`:
1. Use the repository checklist in `.github/pull_request_template.md`.
2. Confirm that all local tests and static checks (`npx tsc --noEmit`, pytest) succeed cleanly without errors.
3. Reference the specific Requirement ID (e.g., `Resolves REQ-DISC-03` or `Fixes NFR-SEC-01`) where applicable.
4. Obtain formal review approval from the project maintainer before merge execution.

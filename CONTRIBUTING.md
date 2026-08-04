# Contributing to EIMS

Thank you for engaging with the **Enterprise Infrastructure Management System (EIMS)**. To preserve enterprise production quality, maintainability, and structural traceability across all system modules, every developer must obey our established engineering conventions before writing code or submitting PRs.

---

## 1. Documentation-First Governance (EDS v1.0.0)

EIMS operates strictly under a **Documentation-First** software development life cycle. Our documentation foundation—the **EIMS Documentation System (EDS v1.0.0)**—serves as the project Constitution.

Before opening a Pull Request that introduces database schema changes, new endpoint APIs, or structural component refactoring, you **must first update the relevant Core Law specifications**:
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

## 2. Git Branching & Naming Conventions

Always fork the main repository and create localized topic branches for your engineering work. Branch titles must adhere to strict type prefixing:
- `feature/<ticket-id>-<short-description>` (e.g., `feature/EIMS-42-redis-ingestion-worker`)
- `fix/<ticket-id>-<short-description>` (e.g., `fix/EIMS-89-pgbouncer-connection-timeout`)
- `docs/<short-description>` (e.g., `docs/align-api-spec-error-codes`)
- `refactor/<short-description>` (e.g., `refactor/optimize-pydantic-validation`)

---

## 3. Mandatory Conventional Commits Enforcement

We reject vague commit messages (such as `"fix bug"`, `"update test"`, or `"first commit"`). Every git commit message in this project must comply with **[Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)**:

```
<type>(<optional-scope>): <short descriptive imperative subject>

[optional body explaining technical rationale and architecture trade-offs]

[optional footer referencing issue IDs or BREAKING CHANGE declarations]
```

### Approved Commit Types:
- `feat`: Introduction of a new structural operational feature or ingestion API endpoint.
- `fix`: Resolution of a runtime exception, database validation error, or security flaw.
- `docs`: Additions or modifications restricted strictly to EDS documentation or Markdown contracts.
- `chore`: Maintenance operations affecting build scripts, Git ignore rules, or container orchestration without altering source logic.
- `refactor`: Structural code cleanup that neither adds a new feature nor patches a defect.
- `test`: Creation of automated unit, integration, or load benchmarking verification test suites.

---

## 4. Code Review & PR Verification Protocol

When submitting a Pull Request against `main`:
1. Use our automated `.github/pull_request_template.md` architecture checklist.
2. Confirm that all local tests and Pydantic syntax evaluations succeed without warning output.
3. Reference the specific Requirement ID (e.g., `Resolves REQ-DISC-03` or `Fixes NFR-SEC-01`) driven by your proposed modifications.
4. Obtain formal approval from at least one Core Repository Maintainer before merge execution.

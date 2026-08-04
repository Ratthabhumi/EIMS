---
id: EDS-STD-001
version: 1.0.0
status: Approved
owner: Lead Software Architect
last_updated: 2026-08-04
review_cycle: Annual
related_documents:
  - ../_templates/document-template.md
  - writing-guide.md
  - terminology.md
---

# EIMS Document Standard

| Metadata | Value |
| :--- | :--- |
| **Document ID** | EDS-STD-001 |
| **Version** | 1.0.0 |
| **Status** | Approved |
| **Owner** | Lead Software Architect |
| **Last Updated** | 2026-08-04 |
| **Review Cycle** | Annual |
| **Related Documents** | [Document Template](../_templates/document-template.md), [Writing Guide](writing-guide.md), [Terminology](terminology.md) |

---

## 1. Purpose

This document defines the binding formatting, structure, and structural syntax standards for all documents within the EIMS Engineering Handbook. Compliance with these standards guarantees consistency, clean parsing by documentation generator pipelines (MkDocs), and readable rendering across IDEs and version control platforms.

---

## 2. Scope

These standards apply to every Markdown (`.md`) file located within the `docs/` repository hierarchy, root project architecture manuals, and repository subdirectory `README.md` implementation guides.

---

## 3. Document Metadata

Every formal engineering document must open with two standardized structures: a YAML frontmatter header followed by a rendered Markdown specification table.

### 3.1 YAML Frontmatter
Place valid YAML frontmatter at line 1 of every `.md` file to enable programmatically queryable indexing across documentation generators.
```yaml
---
id: DOC-SYS-XXX
version: 1.0.0
status: Approved | Under Review | Draft | Deprecated
owner: Lead Software Architect
last_updated: 2026-08-04
review_cycle: Quarterly
related_documents:
  - relative/path/to/document.md
---
```

### 3.2 Metadata Display Table
Immediately below the H1 Document Title and an initial horizontal divider (`---`), include the visible specification layout:
```markdown
| Metadata | Value |
| :--- | :--- |
| **Document ID** | DOC-SYS-XXX |
| **Version** | 1.0.0 |
| **Status** | Approved |
| **Owner** | Lead System Engineer |
| **Last Updated** | 2026-08-04 |
| **Review Cycle** | Bi-annual |
| **Related Documents** | [Title](../path.md) |
```

---

## 4. Heading Levels & Structural Depth

Enforce strict hierarchical structuring using standard Markdown hashes (`#`). 
- **H1 (`#`)**: Reserved solely for the singular official document title at the top of the page. Do not use multiple H1 tags in a single file.
- **H2 (`##`)**: Major primary sections (e.g., `## 1. Purpose`, `## 5. Architecture`). Number all H2 sections sequentially after the metadata block to improve programmatic readability.
- **H3 (`###`)**: Modular logical subcomponents or procedural phases within an H2 block (e.g., `### 5.1 Component Breakdown`).
- **H4 (`####`)**: Deep granular functional definitions (e.g., `#### 5.1.1 Discovery Agent Payload Schema`). 
- **Prohibited Depth**: Do not exceed H4 heading levels (`#####`). When complexity forces five-level hierarchies, refactor the section into a standalone child technical document and cross-reference it.

---

## 5. Tables

Tables must utilize explicit alignment syntax and consistent visual column padding in source Markdown.
- Always include header underline dividers (`| :--- | :--- | :--- |`).
- Prefer left-alignment (`:---`) for prose and identifiers; align numeric metrics or performance latencies right (`---:`).
- Keep cells concise; avoid embedding long multi-paragraph blocks or nested complex lists inside table cells.

---

## 6. Code Blocks

All inline syntax and multiline code excerpts must explicitly name the formal programming language or configuration schema.
- Use triple backticks with explicit lexers (e.g., `python`, `typescript`, `yaml`, `sql`, `bash`, `json`, `markdown`).
- Never leave standard code blocks unadulterated without a language annotation (` ``` ` alone is prohibited; use ` ```text ` or ` ```plain ` for console output dumps).
- Extract configuration payloads directly from verified codebase implementations rather than inventing syntactically invalid illustrative mockups.

---

## 7. Notes & Warnings

Use Material for MkDocs standard admonition formats (`!!! <type> "<Optional Title>"`) for important contextual guidance, breaking changes, or operational warnings. Avoid ad-hoc formatting such as `**IMPORTANT:**` or `> Note:`.

### 7.1 Approved Admonition Callout Types
```markdown
!!! note "Operational Note"
    Background architectural context or configuration defaults that simplify local testing.

!!! tip "Performance Optimization"
    Recommended indexing designs or connection pooling thresholds to achieve target throughput.

!!! warning "Deprecation Boundary"
    Legacy polling APIs are slated for decommissioning in Version 2.0. Migrate all discovery agents to WebSockets.

!!! danger "Security Constraint"
    Never store raw unencrypted credentials in database audit registries or terminal execution logs.
```

---

## 8. Mermaid Diagrams

Embed interactive architectural visualizations directly inside Markdown files using fenced ` ```mermaid ` code blocks. Do not export static PNG/JPEG diagrams from external proprietary graphic design software when standard Mermaid graphing syntax suffices. Refer to [Diagram Standard](diagram-standard.md) for required visual styling rules and node identifiers.

---

## 9. Footers & Revision History

Every engineering specification must terminate with two trailing components:
1. **Related Documents**: Direct relative file links to parallel architectural specifications.
2. **Revision History**: A tracking table auditing modifications, version transitions, approval timestamps, and engineering authors.

---

## 10. Versioning Rules

Documents adhere strictly to Semantic Versioning (`MAJOR.MINOR.PATCH`):
- **MAJOR (`x.0.0`)**: Comprehensive structural refactoring, major system redesigns, or status transition from Draft to Approved.
- **MINOR (`0.x.0`)**: Addition of a new structural subsection, updated integration architecture, or functional feature addition that does not invalidate prior design parameters.
- **PATCH (`0.0.x`)**: Syntax corrections, grammatical typo remediation, link adjustments, and non-breaking structural reformatting.

---

## 11. Cross References

Maintain unbroken traceability across the repository using explicit relative paths.
- **Relative Pathing**: Use direct file references (e.g., `[Database Design](../DATABASE_DESIGN.md)` or `[API Specification](../API_SPECIFICATION.md#header-section)`). Never hardcode localized desktop directory hierarchies (`C:\Users\...`) or external HTTP domain prefixes for repository-local files.
- **Single Source of Truth Check**: Before drafting technical parameters in a new document, verify whether the architecture already resides in a core document. If so, establish a cross-reference instead of duplicating specifications.

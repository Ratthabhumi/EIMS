---
id: EDS-WRIT-001
version: 1.0.0
status: Approved
owner: Lead Software Architect
last_updated: 2026-08-04
review_cycle: Annual
related_documents:
  - document-standard.md
  - terminology.md
---

# EIMS Writing Guide

| Metadata | Value |
| :--- | :--- |
| **Document ID** | EDS-WRIT-001 |
| **Version** | 1.0.0 |
| **Status** | Approved |
| **Owner** | Lead Software Architect |
| **Last Updated** | 2026-08-04 |
| **Review Cycle** | Annual |
| **Related Documents** | [Document Standard](document-standard.md), [Terminology](terminology.md) |

---

## 1. Purpose

This document establishes canonical writing principles for the EIMS project. All engineers, technical writers, and contributors must apply these conventions to guarantee that our documentation remains unambiguous, highly readable, mathematically precise, and consistent across every module of our enterprise infrastructure software.

---

## 2. Scope

This writing guide applies to all architectural specifications, operational runbooks, developer guidebooks, Architecture Decision Records (ADRs), pull request descriptions, code commit messages, inline codebase comment blocks, and API Swagger/OpenAPI descriptions.

---

## 3. Core Rhetorical Rules

### 3.1 Active Voice
Write exclusively in the active voice. Identify the precise system component, process, or actor executing the operational verb. Active syntax reduces cognitive overhead and clearly fixes technical accountability.
- **Correct (Active):** The *Discovery Agent* collects endpoint telemetry and transmits JSON payloads to the *Asset Registry*.
- **Prohibited (Passive):** Endpoint telemetry is collected and JSON payloads are transmitted to the Asset Registry by the system.

### 3.2 Present Tense
Document architectural state and implementation logic in the universal present tense. Do not use future tense ("will", "shall", "going to") when defining system features, even during preliminary architectural design phases.
- **Correct (Present):** The background scheduler triggers Windows log ingestion every five minutes and archives raw events to PostgreSQL.
- **Prohibited (Future):** The background scheduler will trigger Windows log ingestion every five minutes and will archive raw events to PostgreSQL.

### 3.3 Short Paragraphs
Restrict paragraph length to a maximum of three to four sentences. Modularize dense textual analysis into bulleted lists, numeric procedural sequences, or structural Markdown tables. Dense text walls obscure critical implementation requirements during production triage.

### 3.4 Precise Technical Language
Select rigorous software engineering terminology over ambiguous conversational phrasing. When referencing database tables, network protocols, computational algorithms, or container environments, invoke explicit architectural parameters.
- **Correct:** The service leverages PostgreSQL connection pooling via PgBouncer with a strict execution timeout of 5,000 milliseconds.
- **Prohibited:** The app connects to the database real fast and tries not to take too long when querying stuff.

---

## 4. Prohibited Content Patterns

### 4.1 No Marketing Language or Buzzwords
Eliminate promotional jargon, hyperbole, and decorative filler entirely. EIMS documentation serves professional software engineers and system operators, not corporate sales prospects.
- **Prohibited Jargon & Buzzwords:** *Next-generation, best-of-breed, paradigm shift, cloud-native magic, synergy, world-class, bulletproof, highly intelligent, out-of-the-box, turnkey, cutting-edge.*
- **Correction Protocol:** Replace speculative qualifiers with quantifiable engineering thresholds (e.g., change "ultra-fast latency" to "average query execution latency under 15 milliseconds at 99th percentile (p99)").

### 4.2 Avoid Academic or Tutorial Formats
Write like an internal production engineering team, not an academic textbook or a step-by-step consumer tutorial. Do not waste space teaching generic programming fundamentals, explaining how Docker functions theoretically, or citing basic computer science textbooks. Assume the reader is a qualified, senior-level software developer familiar with modern architectural patterns.

### 4.3 No AI-Style Repetition
Do not reiterate the introductory problem statement across consecutive sections. Do not begin every paragraph with repetitive transitioning phrases (e.g., "Furthermore", "In addition to this", "It is worth noting that"). Present data once in its designated section and terminate the explanation once the engineering requirement is fulfilled.

---

## 5. Engineering Explanation Rigor

### 5.1 Explain Design Decisions & Rationale
When presenting code structures or data schemas, do not merely transcribe literal code syntax into sentences (e.g., do not write: "The `if` statement checks if `asset_id` is null, and if so returns 400"). Instead, explicitly document the **engineering rationale, constraints, and architectural trade-offs** behind the design choices.
- **Why was this design chosen over alternatives?**
- **What scaling or consistency limits govern this choice?**
- **What failure domain results if this dependency drops offline?**

### 5.2 One Topic Per Section
Every Markdown section (delimited by an `H2` or `H3` header) must isolate exactly one structural topic, workflow, or API contract. Do not combine database index designs, UI state management rules, and IAM authorization protocols within a single unstructured prose section.

### 5.3 Consistent Tone
Maintain a professional, objective, decisive, and authoritative engineering tone across all deliverables. Avoid informal humor, self-deprecating commentary, emotional qualifiers, and speculative assumptions about future timeline roadmaps in core technical specifications.

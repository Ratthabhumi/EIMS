# Reviewer sourcing and qualification report (2026-11-22)

No reviewer was contacted, named, assumed available, or asked to commit. No candidate is listed because none could be verified from public evidence; inventing names, credentials or availability is prohibited. Packages: `asa_113005_review_package.md`, `cisco_five_page_review_assignments.md`.

## Is three independent reviewers an existing mandatory policy?
**No.** Evidence in the repository: `backend/domain/knowledge/gates.py` (lines 129 to 132) enforces only that the **approver is independent of the verifier and the validator**, that source_verified and validated decisions were made by humans, that a contributor cannot approve their own contribution (and, with drafts, the author of a submitted draft cannot approve it). Nothing forbids the same person from being both verifier and validator, and no document under `AGENTS.md`, the handoff, the acceptance ledger or the engineering memory sets a three-person quorum. The mechanical minimum today is **two distinct humans** (one verifier/validator, one approver). Three reviewers with separate domains is the owner's proposal; it is recorded here as **a decision awaiting owner confirmation**. If the owner adopts it, enforcing "verifier, validator and approver are three different people" needs a small gate change (not made). NIST SP 800-53 independent-assessor guidance concerns conflict of interest and not assessing one's own work; it does not set a number.

## Roles for ASA 113005 (proposed)
| Role | Competence | Checks |
|---|---|---|
| A. Cisco ASA / Secure Firewall specialist | ASA syslog, VPN/WebVPN/IPsec context, ASA and FTD behavior | message semantics, parser mapping, version applicability, masking |
| B. AAA / identity specialist | RADIUS, TACACS+, LDAP, Cisco ISE or equivalent; authentication vs authorization | cause hypotheses, AAA-server evidence, counters |
| C. Network security operations specialist | incident response, change control | impact, permissions, preconditions, rollback, post-check, lock-out risk |
Page assignments for the five Cisco pages follow product domain (firewall HA, BGP routing, switching, NX-OS routing), not one ASA specialist for all.

## Qualification evidence a reviewer should supply
Role history on the relevant platform with verifiable references; current or past Cisco certification where relevant, verifiable through Cisco's own credential-verification process; for AAA, demonstrable work with the named AAA platform; publications or authored Cisco/community technical content are supporting evidence only. Seniority is not required; demonstrated competence in the exact domain is.

## Independence criteria and conflict-of-interest declaration
Each reviewer: is not the author or contributor of the catalog record (the records were prepared with AI assistance and by the EIMS engineers); did not prepare or edit the evidence they review; has no financial or employment interest that depends on the outcome (declare employer, vendor relationships and any EIMS involvement); reviews first and alone, then submits their own findings; does not copy another reviewer's conclusion; records verbatim quotes and dates. A declaration form is the header of each worksheet. The system records the actor of every decision; it cannot prove the person is not delegating to a tool, so the owner should obtain a signed statement.

## Public sourcing channels (to find people; none confirmed)
Cisco official documentation authorship and the Cisco Learning Network / certification verification for credential checks; Cisco partner and professional-services channels; established network-security consultancies; specialist AAA/identity practitioners; the owner's own staff or customers' engineers who meet the criteria. The search found Cisco documentation on `show aaa-server`, TACACS+ and RADIUS configuration, and hardening guidance, which help define reviewer competence; the pages "Analyze AAA Device Administration Behavior for ASA" (named in the request) and "Testing TACACS+ Authentication and Authorization" were not found by search, so authorship claims about "Cisco HTTS engineers" are **not verified** here.

## Limitations
Availability and willingness of any person cannot be established from public pages. Cisco pages could not be read by tooling; ASA 113005 statements come from a search summary and need a verbatim read. EIMS has no reviewer sign-in (by design); a reviewer needs an existing reviewer-flagged account (granted through the admin API) before acting.

## Existing governance policy, precisely (documentation only; no code change)
Source: `backend/domain/knowledge/gates.py` and `tests/test_knowledge_gates.py`, `tests/test_knowledge_governance_api_pg.py`, `tests/test_draft_proposal_workflow_pg.py`.
| Rule | Where enforced |
|---|---|
| `source_verified`, `validated`, `approved`, `deprecated`, `superseded` require `actor_kind == "human"` (an unknown or missing kind is not human; fail closed) | `HUMAN_ONLY_TARGETS`; `test_only_an_exact_human_actor_kind_can_take_a_decision` |
| AI assistants and automation may only reopen (`candidate`) or reject at gate level; the decision API exposes no AI/automation path (the principal is a reviewer-flagged database user and the server sets `actor_kind` to `human`) | gate test `test_ai_or_automation_may_reopen_or_reject_but_that_is_all`; API tests |
| `validated` needs a prior human `source_verified` for the same content revision | `test_validated_requires_fields_and_prior_source_provenance` |
| `approved` needs prior human `source_verified` and `validated` for the current revision, not stale | `test_approved_requires_validation_current_revision_and_not_stale` |
| the approver must differ from the verifier and the validator | `test_approval_separation_of_duties` |
| a contributor cannot approve their own work; the author of a submitted draft cannot approve it | `test_contributor_cannot_approve_own_work`; `author_cannot_approve` API test |
| the verifier recorded in a source_verified decision must be the authenticated actor | `test_verifier_must_be_the_authenticated_actor` |
| the shared admin token cannot act as a reviewer | API tests |
Not required today: verifier and validator may be the same person; no minimum of three people. Mechanical minimum for an approved record: **two distinct humans** (verifier-and-validator, and an independent approver), neither of them the contributor. A three-person rule would be a new owner policy and a deliberate gate change; none was made.

## Evidence categories (so nothing is mistaken for fact)
| Category | Content in this project today |
|---|---|
| Publicly verified qualifications | none; no individual was assessed |
| Suggested qualification criteria | the competencies, qualification evidence and independence criteria above |
| Unverified candidate information | none recorded (no names were sought or invented) |
| Actual reviewer acceptance | none; nobody has been asked or has agreed |

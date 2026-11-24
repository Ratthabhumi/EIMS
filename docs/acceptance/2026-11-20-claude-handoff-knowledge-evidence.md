# Claude handoff — Evidence Integrity + Diagnostic Knowledge Expansion

**Date:** 2026-11-20  
**Branch:** `demo/2026-11-24` @ `3f2beea`  
**Cursor status:** UX close-button, spacing, Settings cleanup, and **presentation-layer** evidence honesty are done. See `docs/acceptance/2026-11-20-ux-evidence-integrity-cursor.md`.

Do **not** rewrite Analyzer three-tab shell, Incident drawer, or Settings page structure.

## Own these

1. Evidence pipeline root cause (Event ID 1026 case): parse → normalize → identity → dedupe → timeline → prompt → summary. Preserve raw evidence. Do not dedupe solely by message text when EventRecordID/TimeCreated differ.
2. Analysis contract: Event 1026 may state process termination via unhandled exception + stack frames; must not claim Git Credential Manager / credentials / network as proven root cause without more evidence.
3. Source line semantics: if offsets are excerpt positions, backend should mark provenance so UI does not guess.
4. Diagnostic Knowledge Catalog Phase 1 only first: Windows Event Logs / .NET Runtime, AD + GPO, DNS/DHCP, Networking/Firewall. Authoritative sources; lifecycle Candidate → verified → approved. No parallel store. Do not flood thousands of shallow records.
5. Coverage matrix + retrieval regression tests (Event ID, Provider, product vs root-cause language).
6. Separate Claude acceptance report. Preserve 163-record baseline + 22 candidates unless inventory proves otherwise.

## Do not

- git reset/clean/stash/commit/push without owner authorization
- Touch Operational DB
- Edit Cursor-owned presentation files unless coordinating a shared contract field
- Auto-promote Incident knowledge proposals

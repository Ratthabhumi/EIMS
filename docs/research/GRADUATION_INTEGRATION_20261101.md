# Graduation core integration — 1 November 2026

Starting HEAD: 2a0d9031297ac1063a0f327a8a76c455bb5da315. PR #10 remains Draft on #5, no merge/retarget. Final delivery HEAD and exact CI checkout are published in PR #10 after commit (avoids self-referential SHA/CI commit loops).

## Implemented and inspected

- Reused existing Windows/VMware/Fortinet production fixes unchanged. No newly reproduced Analyzer defect; no invented production RED→GREEN claim.
- Added tools/verify_graduation_delivery.py to CI: 36 prediction digests across M0/M1/Full, annotation/source provenance, strict fixture-byte hashes via existing manifest loader, 61 unreviewed claim bindings, priority packet and undefined reviewed accuracy. Existing evaluator/inspector reused, no duplicate scorer or authentication.
- Three negative controls reject changed prediction content, missing cases and duplicate cases; valid input accepted. Historical Windows raw text hashes were not portable to LF Git checkout: preserved original hashes and added explicit LF canonical text hashes, with strict fixture bytes unchanged. No frozen snapshot rewrite.
- Existing Dashboard submits file/files/text/language via BFF and renders native solutionSummary; History reconstructs saved metadata and evidence. Existing ASGI parity, duplicate-basename, missing-source inspector, privacy and PostgreSQL Thai/English tests cover the contract. BFF/session/PDF assertions pass. This is source/isolated coverage, not observed browser behavior.
- Current Full Analyzer rerun (two repetitions, all 12 DEV) produced exactly the frozen 12 prediction hashes. No changed claims/labels; 61 claims, 0 genuine review, 5 HELDOUT reserved/unexecuted. No new scientific snapshot needed.
- README, Chapters 1–5, abstracts, 15-slide source, rehearsal overlay, assembly checklist, operator script and release metadata now distinguish verified 2a0d903 engineering baseline (391 tests), historical September evidence and unmeasured quality. Chapter 2 uses the actual repository filename, not the prompt's suggested alias.

## Reproduction and local evidence

Use the existing requirements-evaluation.txt Python environment, repository root:

```powershell
python tools/verify_graduation_delivery.py --demo-output test-results/demo-UNIQUE
$env:PYTHONHASHSEED='0'
python tools/eval_analyzer.py --mode full_investigation --split dev --include-draft --annotations-v2 evaluation/analyzer/gold/manifest.v2.dev-draft.json --warmups 0 --repeats 2 --output test-results/replay-UNIQUE
python -m pytest tests/test_analyzer_reliability.py tests/test_analyzer_evaluation.py tests/test_analyzer_investigation.py tests/test_analyzer_integration_stability.py -q
node tools/test_session_proxy.cjs
node tools/test_browser_acceptance_config.cjs
```

Offline inspectors were generated for all 12 cases using the existing escaped renderer. Exact fixture hashes are in the release manifest; exact claim/source coordinates in the priority packet and predictions JSONL. Open Fortinet → VMware → Windows → heartbeat → unrelated bundle in five minutes. Optional live History replay requires approved runtime; offline serialized memory History is not PostgreSQL. CI runs PostgreSQL only in its dedicated synthetic service.

Local full pre-tooling hermetic run: 298 PASS, 1 Windows symlink skip, 2 dependency warnings; added verifier negative controls: 3 PASS. BFF/PDF: 18 PASS; config: 5 invalid + valid HTTPS PASS. New final CI supersedes these platform-specific counts and is recorded on PR #10. No operational database/services used.

## Remaining gates and merge recommendation

SCIENTIFIC_REVIEW_PENDING: owner genuinely reviews latest priority delta, then remaining DEV; never turn DRAFT scores into accuracy. No further vendor research required for this round.

BLOCKED_BY_AUTHORIZATION / RUNTIME_NOT_TESTED: previous trusted HTTPS startup was rejected by automatic policy. No approved runtime supplied; no retry on alternate ports, TLS relaxation or session injection. Existing browser harness remains BLOCKED_NOT_TESTED.

DEFERRED: DOCX/PDF/PPTX remain STALE_PENDING_REBUILD; exact assembly checklist provided, no converter on PATH or visual approval. USB hardware/production not tested. Separate Redis/EVTX recovery XFAIL contracts and 21 module setup-blocked tests are not certified by core CI.

Owner-approved merge order only: #2 → #3 → #4 → #5 → #10. Recheck each base and fresh CI after each approved merge/retarget; current mergeability is not authorization or proof of final main compatibility. #6–#9/#11 stay separate. Keep main unchanged. Preserve rollback refs; no schema downgrade/data reset. Demo checkout's existing deleted/untracked files remain untouched.

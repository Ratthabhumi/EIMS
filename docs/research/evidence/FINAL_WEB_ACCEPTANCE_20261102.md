# Graduation Web Core — final acceptance record, 2 November 2026

Verdict: **ENGINEERING_READY_BROWSER_ACCEPTANCE_PENDING**.

Verified source: `540c01e6e2644c8910eedb962c87de85f1a76dbf`. [CI 41428226311](https://github.com/Ratthabhumi/EIMS/actions/runs/41428226311) passed 3/3 jobs: 311 hermetic, 62 PostgreSQL, 46 USB isolated tests; 16 export-content tests; 8 counterexamples. Tested merge checkout: `3ec114cca09d69741084a3e98afd129ca5b9b924`.

This record distinguishes existing engineering evidence from mandatory real-browser acceptance. PASS below never certifies arbitrary logs, production or diagnostic accuracy.

| Gate | Engineering evidence | Actual browser gate |
| --- | --- | --- |
| Text input | PASS — synthetic API/PostgreSQL parity | BLOCKED |
| File upload | PASS — valid fixtures; invalid input rejected without History | BLOCKED |
| Bundle | PASS — existing synthetic integration/counterexamples | BLOCKED |
| Analyzer result | PASS — structured integration and React rendering | BLOCKED |
| Evidence viewer | PASS at source-coordinate/API/component boundary | BLOCKED — keyboard/mouse/source inspection not executed |
| History reopen | PASS — fresh owner-scoped PostgreSQL retrieval | BLOCKED — UI reload/reopen not executed |
| Markdown export | PASS — actual live/History content builders | BLOCKED — downloaded file not inspected |
| PDF export | PASS — actual escaped HTML builders | BLOCKED — download/rasterization/Thai layout/pagination not inspected |
| Authentication | PASS — isolated secure JWT/BFF tests | BLOCKED — real browser login not executed |
| Session security | PASS — isolated ownership/revocation/BFF tests | BLOCKED — browser logout/cookie replay not executed |
| Browser E2E | No browser execution this round | BLOCKED |
| Demo readiness | Engineering prerequisites partly present | BLOCKED — mandatory browser workflow pending |

## Current runtime observations

Bounded loopback connections found no listeners on 8019 (synthetic backend), 3009 (Dashboard), 3449 (HTTPS), or 55439 (dedicated test database). Docker engine version query exceeded eight seconds and was stopped without retry. An independent PowerShell inventory was also unresponsive; it is not evidence of a healthy engine. No reset, volume deletion, production fallback or service changes were performed.

Edge, existing Playwright module and local certificate/key files exist. Certificate validity ends 9 November 2026 at 04:25 UTC; existence is not proof that browser trust or HTTPS works. No private key, cookie or JWT is published. The synthetic accounts cannot be checked while the database is unavailable. Frontend build evidence is from the passing exact-source CI; no need to repeat completed build/test phases without a new source change.

Previous automatic approval rejection remains applicable to agent Dashboard startup: `blocked by policy`. No alternative port, launcher, TLS/cookie weakening or startup retry was used. Owner authorization does not itself remove the tool restriction.

## Owner-controlled next step

Restore Docker Desktop health and the existing labelled synthetic database, then provide an HTTPS runtime permitted by applicable policy. Follow [the existing runbook](../WEB_ACCEPTANCE_20261102.md). The original Dashboard command, in `clients/dashboard` with the documented environment variables, is:

```powershell
npm run start -- --hostname 127.0.0.1 --port 3009
```

Do not use owner execution to evade an applicable restriction. Once permitted services are running, execute the existing browser harness. Its current prepared checks do not establish downloaded-report acceptance; also download and inspect both Markdown and PDF from live results and reopened History, including Thai text and long multi-page content. Share sanitized results only. Stop on a missing prerequisite and retain generated History.

No newly confirmed P0/P1 defect was found this round; runtime-dependent UX and PDF correctness remain unknown. No code repair is justified solely by lack of a running environment. No source changes or repeated engineering tests were needed for this record.

OCR is optional and excluded from the selected Text/Log demo acceptance. Missing-engine error handling is covered; real OCR remains NOT_TESTED. No dependency installation.

Scientific boundary: 12 DRAFT DEV, 61 claims, zero authentic reviews, five HELDOUT reserved; diagnostic accuracy NOT_MEASURED. Freeze, production certification and merge authorization have not been granted. PR #10 remains Draft. No academic artifact work or general research.

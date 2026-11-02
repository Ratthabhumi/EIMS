# Web input acceptance — 2 November 2026

Scope changed by owner: finish core web Text/File workflow; no academic report/deck work. Start e6590f7b86793c3cbd7385744b23fefb5980c5ca. Final publication HEAD/CI/tested checkout recorded in PR #10.

## Corrected defect and verification

Single-input failures returned HTTP 200, so Dashboard treated invalid input as successful analysis. Four PostgreSQL regression cases reproduced this: whitespace text, empty attachment, invalid UTF-8, attachment over 5 MiB. Changed only these response paths to 400/413, plus sanitized parse-error text. No new History/vector export for invalid input. Existing Dashboard already displays non-2xx detail as an error and retains user input; no duplicate UI logic needed.

New parity checks: Fortinet, VMware and Windows, both Thai/English, pasted text versus attached UTF-8 file have the same metadata/diagnosis and survive a fresh owned History SELECT. Six parity cases PASS before and after. Full real synthetic PostgreSQL suite: 56 PASS. Hermetic: 301 PASS, one Windows symlink skip. BFF/PDF 18 and shared React 6 PASS. New input checks 4 FAIL → 4 PASS. Evidence: evidence/20261102-web-input/results.json. Final CI is authoritative for Linux counts.

Frozen Full replay twice per case: all 12 prediction hashes unchanged. Existing verifier: 36 digests / 61 claims PASS. No annotation/scorer/HELDOUT change or fabricated review. No new snapshot needed because valid predictions did not change.

## Browser boundary

Owner explicitly authorized synthetic runtime on 2 November. Existing labelled container eims-analyzer-integration-20261025 was started (loopback 55439), and actual synthetic FastAPI started on 8019 successfully. Frontend production build passed. Automatic approval review still rejected the exact Dashboard start command `npm run start -- --hostname 127.0.0.1 --port 3009` with `blocked by policy`. No alternate port/start method attempted. Backend was stopped; 3009/3449/8019 have no task listener. Test database retained; operational containers/data untouched.

**BROWSER_HTTPS = BLOCKED_NOT_TESTED.** The existing secure harness now additionally covers 12 Text/File/vendor/language combinations and an invalid attachment, then the existing bundle, source inspection, reload/History, cross-user, logout/replay, navigation and expiry checks. Syntax/config validation passed; these added browser actions have NOT been executed. Do not infer browser PASS from ASGI/PostgreSQL/React tests.

No Tesseract executable found on PATH: image OCR NOT_TESTED. TXT/LOG fixture coverage is not every file format, vendor/version, arbitrary log or production certification. No 100% completion/accuracy claim.

## Owner-run same approved runtime

From `C:\Users\MewMew\Desktop\Co-op\EIMS-analyzer-correctness`, first check there are no duplicate listeners on 8019/3009/3449. Use only the labelled synthetic test DB, never operational URLs. Synthetic accounts are already created by the test harness. Public test password: `synthetic-test-password-only`; usernames `synthetic-browser-review`, `synthetic-browser-other`, `synthetic-expiry`. These are not production credentials.

Terminal 1 (backend):
```powershell
$env:EIMS_TEST_DATABASE_URL='postgresql+asyncpg://eims_test:eims_synthetic_only@127.0.0.1:55439/eims_integration_test'
& C:/Users/MewMew/Desktop/Co-op/EIMS/venv/Scripts/python.exe -m uvicorn tests.analyzer_synthetic_demo_app:app --host 127.0.0.1 --port 8019
```
Terminal 2 (the exact Dashboard command the owner must run directly):
```powershell
Set-Location clients/dashboard
$env:EIMS_BACKEND_URL='http://127.0.0.1:8019'
$env:EIMS_DASHBOARD_ORIGIN='https://localhost:3449'
npm run start -- --hostname 127.0.0.1 --port 3009
```
Terminal 3 (TLS proxy, repo root):
```powershell
$env:EIMS_TEST_TLS_CERT=(Resolve-Path test-results/web-acceptance-tls/localhost.crt).Path
$env:EIMS_TEST_TLS_KEY=(Resolve-Path test-results/web-acceptance-tls/localhost.key).Path
node tools/serve_synthetic_https.cjs
```
A localhost-only certificate was generated for this authorized attempt and trusted in CurrentUser Root, valid through 9 November 2026. Key/cert remain ignored local files, not published. It is not an organization certificate. Another machine must provide its own explicitly trusted localhost certificate; do not disable verification.

Terminal 4 (test or open `https://localhost:3449/analyzer` manually):
```powershell
$env:EIMS_TEST_BROWSER_BASE_URL='https://localhost:3449'
$env:NODE_EXTRA_CA_CERTS=(Resolve-Path test-results/web-acceptance-tls/localhost.crt).Path
$env:EIMS_PLAYWRIGHT_MODULE='C:/Users/MewMew/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
node tools/verify_secure_dashboard.cjs
```
Send only sanitized test-results/secure-browser-acceptance.json and screenshots, never cookies, private keys or production logs. Stop on missing prerequisites or failure; preserve History. Use Ctrl+C in each terminal to stop only these services. The synthetic test DB may be stopped with `docker stop eims-analyzer-integration-20261025`; never delete its volume. When finished with this certificate, remove only the task-created trust entry:
```powershell
Remove-Item -LiteralPath 'Cert:/CurrentUser/Root/0B2D08ABFBF30E3BEBC313BBE8CA3B4150FDD9C1'
```
This runbook uses the same ports/security and the owner's own execution, not a workaround executed by the agent after rejection. TLS helper is loopback-only and not a production reverse proxy.

## Remaining gates

Owner action: run approved Dashboard command and browser harness; provide results so actual UI issues can be fixed. Genuine human review remains 0 / accuracy NOT_MEASURED. Academic artifacts are explicitly out of scope at owner request. No merge/retarget; core order #2 → #3 → #4 → #5 → #10 still requires explicit merge approval and fresh CI. Infrastructure stack unchanged. No new research required for the reproduced input defect.

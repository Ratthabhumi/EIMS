# Prepared USB handover — 2026-10-20

The owner selected a local working database with automatic USB recovery copies,
so unplugging the USB does not disconnect PostgreSQL from its live data files.
Python 3.14.6, Node 24.18.0, a built Next.js frontend and the pinned Linux
infrastructure images are prepared on the build PC. The prepared SETUP branch
performs no pip download, npm install, TypeScript check or frontend build.
Docker Desktop/WSL remains a host prerequisite. Target: Windows x64.

## Storage and recovery

- Immutable program files: `Final_EIMS_Project` on the USB.
- Protected working data: a per-user cache under the user's local application data.
- Private recovery copies: sibling `EIMS_Data`, excluded from public Git.
- Start initiates backup immediately, then waits 120 seconds between attempts.
- Each checkpoint contains a transactional PostgreSQL dump, MinIO objects and
  private configuration/admin record. Redis is reconstructible cache.
- A checkpoint is promoted only after pg_restore can list the archive and all
  copied files pass SHA-256 verification. Interrupted copies remain pending;
  previous completed copies are preserved. No old checkpoint is deleted.
- A missing USB leaves local work intact. Changes after the latest completed
  checkpoint do not travel to another PC until a successful save occurs.
- On another PC, SETUP restores into a fresh local session. Stale local sessions
  are preserved rather than overwritten or silently merged.
- Stop quiesces the app and attempts a final checkpoint before stopping its
  infrastructure. Failed saves are reported; local data remains available.
- Live PostgreSQL/MinIO copies do not claim a shared point-in-time transaction.
  Checkpoints are private operational records. NTFS and hashes are not encryption.

## Progress and reproducibility

The launcher invokes the command runner from the current package, preventing a
stale cached Release from suppressing the moving indicator. Release and runtime
snapshots use content-derived names, preserving previous versions. Existing
databases, private configuration and source directories are not reset.

Standalone frontend packaging follows the [official Next.js output guidance](https://nextjs.org/docs/app/api-reference/config/next-config-js/output).
Windows build junctions are copied as ordinary files; static assets and upstream
notices are included. Delivery tools are in `tools/handover`: Runtime.ps1,
prepare_portable_setup.py, prepared_runtime.py and usb_backup.py.

## Measured verification

- 18 focused tests: PASS (safe extraction, integrity, subprocess progress,
  interrupted backup, corrupt checkpoint fallback, private configuration
  preservation, fresh cache selection and resumable object restoration).
- TypeScript: PASS in the isolated sanitized application build.
- Next.js production build: PASS (16.3.0, standalone output).
- Bundled Python core dependency imports: PASS.
- PowerShell source parse: PASS.
- Full prepared SETUP and authenticated Analyzer/History smoke: PASS.
- Stop and final checkpoint: PASS. The process-time comparison now handles
  PowerShell JSON date representations without weakening ownership checks.
- Real recovery into a fresh isolated PostgreSQL/MinIO project: PASS (one
  synthetic History row, one user and one synthetic object restored). The initial
  temporary PostgreSQL initialization server is excluded by a TCP health check.
- Physical E: delivery: PASS (78 files; all copied files and 35 predecessor
  files hash-verified). Previous package retained as
  `Final_EIMS_Project_Backup_2026-10-20_Prepared`.
- Native Windows PowerShell Start, automatic USB save and Stop from E: PASS.
  The physical USB recovery copy contains the verified database and synthetic
  object. The test instance was stopped after verification.
- Manifest SHA-256: `27a886289678c8c9723f73a6fa43f17e64f96069d973f97226229ad0736ce4f8`.
- Clean second physical PC: NOT RUN. All-PC compatibility is not claimed.

Private logs, checkpoints, receipts and binary candidates stay outside public
source. The original USB package is retained until replacement verification.

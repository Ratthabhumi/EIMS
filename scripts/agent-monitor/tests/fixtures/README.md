# Synthetic fixture (test-only)

`e2e-sample-0001/` is a hand-written, synthetic Chat_HAND-style job artifact
folder used only by `tests/Test-WatchEimsAgentJobs.ps1`.

- It contains no credentials, tokens, real command lines, prompts, or customer data.
- It is not produced by the gateway and must never be treated as production evidence.
- The test copies this folder into a disposable `%TEMP%` directory; the original is
  never modified.

Files:

| File | Purpose |
|---|---|
| `stdout.log` | Sample incremental log content. |
| `stderr.log` | Empty sample error stream. |
| `exit.json` | Terminal signal (`exitCode: 0`, `status: completed`). |
| `runner.json` | Only safe metadata (PID, start time, agent label). |
| `manifest.json` | Only safe metadata (job id, agent label). |

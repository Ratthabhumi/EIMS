/* eslint-disable @typescript-eslint/no-require-imports */
const { test, expect } = require('@playwright/test');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { runtimeConfig } = require('../../../tools/verify_secure_dashboard.cjs');

test('acceptance configuration rejects plaintext HTTP and TLS bypass', async () => {
  expect(() => runtimeConfig({ EIMS_TEST_BROWSER_BASE_URL: 'http://localhost:3449' })).toThrow();
  expect(() => runtimeConfig({
    EIMS_TEST_BROWSER_BASE_URL: 'https://localhost:3449',
    EIMS_TEST_IGNORE_TLS_ERRORS: '1',
  })).toThrow();
});

test('secure dashboard browser acceptance: auth, analyzer, evidence, exports, history and isolation', async ({}, testInfo) => {
  const { base } = runtimeConfig(process.env);
  expect(new URL(base).protocol).toBe('https:');

  // Run the established browser harness in a child process. This keeps its
  // Edge event loop and response correlation independent of Playwright Test's
  // worker lifecycle while retaining a real JUnit acceptance result.
  const repoRoot = path.resolve(__dirname, '../../..');
  const resultsDir = path.resolve(process.env.EIMS_TEST_RESULTS_DIR || path.join(repoRoot, 'test-results'));
  const reportPath = path.join(resultsDir, 'secure-browser-acceptance.json');
  const child = spawn(process.execPath, [path.join(repoRoot, 'tools', 'verify_secure_dashboard.cjs')], {
    cwd: repoRoot,
    env: { ...process.env, EIMS_PLAYWRIGHT_MODULE: require.resolve('playwright') },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stdout = '';
  let stderr = '';
  child.stdout.setEncoding('utf8').on('data', chunk => { stdout += chunk; });
  child.stderr.setEncoding('utf8').on('data', chunk => { stderr += chunk; });
  const exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', resolve);
  });
  if (stdout) console.log(stdout);
  if (stderr) console.error(stderr);

  let report;
  try {
    report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  } catch {
    throw new Error(`Browser harness produced no readable report (exit ${exitCode}): ${stderr || stdout}`);
  }
  await testInfo.attach('secure-browser-acceptance.json', {
    body: Buffer.from(JSON.stringify(report, null, 2)),
    contentType: 'application/json',
  });
  expect(exitCode, `Browser harness exit: ${stderr || stdout}`).toBe(0);
  expect(report.status, JSON.stringify(report)).toBe('PASS');
  expect(report.checks.length).toBeGreaterThanOrEqual(20);
  expect(report.checks.some(check => check.includes('Second actual-login user'))).toBe(true);
  expect(report.checks.some(check => check.includes('Logout clears session'))).toBe(true);
});

/* eslint-disable @typescript-eslint/no-require-imports */
const { defineConfig } = require('@playwright/test');
const path = require('node:path');
const resultsDir = path.resolve(process.env.EIMS_TEST_RESULTS_DIR || path.resolve(__dirname, '../../test-results'));
module.exports = defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.cjs',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  // One end-to-end acceptance test: 12 analyzer cases (~8 min observed up to the Back-to-finding step), then
  // history/exports, second user, isolation, logout and expiry. Per-action timeouts stay strict (20s/60s).
  timeout: 1200000,
  expect: { timeout: 15000 },
  reporter: [['list'], ['junit', { outputFile: path.join(resultsDir, 'secure-browser-acceptance.junit.xml') }],
    ['html', { outputFolder: path.join(resultsDir, 'playwright-report'), open: 'never' }]],
  outputDir: path.join(resultsDir, 'playwright'),
  use: {
    browserName: 'chromium',
    channel: 'msedge',
    headless: true,
    baseURL: process.env.EIMS_TEST_BROWSER_BASE_URL || 'https://localhost:3449',
    ignoreHTTPSErrors: false,
    acceptDownloads: true,
    viewport: { width: 1400, height: 1000 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});

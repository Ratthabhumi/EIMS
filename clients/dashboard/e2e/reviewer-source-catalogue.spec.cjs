/* eslint-disable @typescript-eslint/no-require-imports */
const { test, expect } = require('@playwright/test');

const fixtureKey = 'eims-synthetic-browser-review-fixture';

async function signIn(page, username) {
  page.setDefaultTimeout(15000);
  page.setDefaultNavigationTimeout(15000);
  const initialSession = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith('/api/v1/auth/session')
      && response.request().method() === 'GET', { timeout: 15000 });
  await page.goto('/analyzer', { waitUntil: 'domcontentloaded' });
  await initialSession;
  await page.locator('input[name="username"]').waitFor();
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(process.env.EIMS_TEST_LOGIN_CREDENTIAL || '');
  const login = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith('/api/session/login')
      && response.request().method() === 'POST');
  await page.getByRole('button', { name: /^Sign in/ }).click();
  const response = await login;
  expect(response.status()).toBe(200);
  await page.getByText('Signed in: ' + username, { exact: true }).waitFor();
}

async function api(page, path, method = 'GET', body) {
  return page.evaluate(async ({ path, method, body }) => {
    const response = await fetch(path, {
      method,
      credentials: 'include',
      cache: 'no-store',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return {
      status: response.status,
      requestId: response.headers.get('x-request-id'),
      body: await response.json().catch(() => null),
    };
  }, { path, method, body });
}

test('Reviewer and Engineer Source Catalogue workflow, capability audit and isolation', async ({ browser }, testInfo) => {
  expect(process.env.EIMS_TEST_LOGIN_CREDENTIAL, 'synthetic login credential must be supplied by the isolated runner').toBeTruthy();
  const evidence = { fixtureKey, reviewer: {}, engineer: {}, admin: {}, boundary: 'synthetic fixture only; no vendor candidate or Approved Knowledge is changed' };

  const reviewerContext = await browser.newContext();
  const reviewer = await reviewerContext.newPage();
  await signIn(reviewer, 'synthetic-browser-review');
  await reviewer.goto('/knowledge', { waitUntil: 'domcontentloaded' });
  await reviewer.getByRole('heading', { name: 'Engineering Knowledge Base' }).waitFor();
  const fixtureCard = reviewer.locator('article').filter({ hasText: fixtureKey });
  await expect(fixtureCard).toBeVisible();
  await expect(fixtureCard.getByRole('button', { name: 'Verify source reference' })).toBeVisible();
  await fixtureCard.getByRole('textbox', { name: /Domain review evidence/ }).fill(
    'Synthetic fixture transition test only; this is not a human domain review.',
  );
  await fixtureCard.getByRole('button', { name: 'Verify source reference' }).click();
  await expect(reviewer.getByRole('status')).toContainText('This does not publish reusable Knowledge');
  await fixtureCard.getByRole('button', { name: 'Source audit history' }).click();
  await expect(fixtureCard).toContainText('verify_reference');
  await expect(fixtureCard).toContainText('synthetic-browser-review');

  const reviewerSourceState = await api(reviewer, '/api/eims/api/v1/knowledge/sources?limit=100');
  expect(reviewerSourceState.status).toBe(200);
  const fixture = reviewerSourceState.body.items.find((item) => item.sourceKey === fixtureKey);
  expect(fixture.reviewState).toBe('verified_reference');
  const realCandidates = reviewerSourceState.body.items.filter((item) => item.sourceKey !== fixtureKey);
  expect(realCandidates).toHaveLength(20);
  expect(realCandidates.every((item) => item.reviewState === 'pending_domain_review')).toBe(true);
  const published = await api(reviewer, '/api/eims/api/v1/knowledge/');
  expect(published.status).toBe(200);
  expect(published.body.items.some((item) => item.title === 'Synthetic Browser Review Fixture — Not Domain Evidence')).toBe(false);
  evidence.reviewer = {
    sourceListStatus: reviewerSourceState.status,
    fixtureState: fixture.reviewState,
    importedCandidateCount: realCandidates.length,
    importedCandidatesRemainPending: true,
    publishedKnowledgeCount: published.body.items.length,
    fixturePromotedToKnowledge: false,
    sourceAuditHistoryVisible: true,
  };
  await reviewerContext.close();

  const engineerContext = await browser.newContext();
  const engineer = await engineerContext.newPage();
  await signIn(engineer, 'synthetic-browser-other');
  await engineer.goto('/knowledge', { waitUntil: 'domcontentloaded' });
  await engineer.getByRole('heading', { name: 'Engineering Knowledge Base' }).waitFor();
  const engineerCard = engineer.locator('article').filter({ hasText: fixtureKey });
  await expect(engineerCard).toBeVisible();
  await expect(engineer.getByRole('button', { name: 'Verify source reference' })).toHaveCount(0);
  await expect(engineer.getByText('Domain review evidence (required, minimum 10 characters)')).toHaveCount(0);
  const denied = await api(engineer, `/api/eims/api/v1/knowledge/sources/${fixture.id}/review`, 'POST', {
    decision: 'verify_reference',
    note: 'Engineer must not be able to change source review state.',
  });
  expect(denied.status).toBe(403);
  evidence.engineer = {
    sourceListStatus: 200,
    reviewerControlsHidden: true,
    sourceMutationStatus: denied.status,
    mutationDenied: true,
    requestId: denied.requestId,
  };
  await engineerContext.close();

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await signIn(adminPage, 'synthetic-browser-admin');
  const users = await api(adminPage, '/api/eims/api/v1/admin/users');
  expect(users.status).toBe(200);
  const target = users.body.find((user) => user.username === 'synthetic-browser-other');
  expect(target).toBeTruthy();
  const grant = await api(adminPage, `/api/eims/api/v1/admin/users/${target.id}/knowledge-reviewer`, 'PATCH', { enabled: true });
  expect(grant.status).toBe(200);
  expect(grant.body.knowledge_reviewer).toBe(true);
  const revoke = await api(adminPage, `/api/eims/api/v1/admin/users/${target.id}/knowledge-reviewer`, 'PATCH', { enabled: false });
  expect(revoke.status).toBe(200);
  expect(revoke.body.knowledge_reviewer).toBe(false);
  const diagnostics = await api(adminPage, '/api/eims/api/v1/__test__/diagnostics');
  expect(diagnostics.status).toBe(200);
  expect(diagnostics.body.reviewer_capability_audit_events).toBeGreaterThanOrEqual(2);
  evidence.admin = {
    grantStatus: grant.status,
    revokeStatus: revoke.status,
    capabilityRestoredToFalse: revoke.body.knowledge_reviewer === false,
    auditEventCount: diagnostics.body.reviewer_capability_audit_events,
    database: diagnostics.body.database,
    databaseUser: diagnostics.body.database_user,
    pool: diagnostics.body.pool,
  };
  await adminContext.close();

  await testInfo.attach('reviewer-source-catalogue-evidence.json', {
    body: Buffer.from(JSON.stringify(evidence, null, 2)),
    contentType: 'application/json',
  });
});

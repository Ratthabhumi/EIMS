/* Real Chromium UI, intercepted synthetic API responses; never accesses the DB.
 * Usage: node tests/analyzer_catalog_ui.cjs
 * EIMS_UI_URL defaults to an isolated production preview on port 3108.
 * EIMS_PLAYWRIGHT_MODULE optionally points to a bundled Playwright module.
 */
const { chromium } = require(process.env.EIMS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.join(__dirname, '..');
const catalog = JSON.parse(execFileSync(process.env.EIMS_PYTHON || path.join(root, 'venv/Scripts/python.exe'),
  ['-c', 'import json; from backend.domain.analyzer.services.operational_catalog import get_catalog; print(json.dumps(get_catalog()))'], {cwd:root,encoding:'utf8'}));
const history = [[1,'1129','2026-10-07','windows_event','Microsoft-Windows-GroupPolicy'],
  [2,'1129','2026-10-08','palo_alto','PAN-OS/SYSTEM'],
  [3,'AINC-2026-0910-0001','2026-10-06','windows_event','Synthetic incident']].map(([id,eventId,day,family,provider]) => ({
    id,eventId,provider,created_at:day+'T10:00:00Z',username:'demo',description:'Sanitized synthetic fixture',
    eventMetadata:{sourceFamily:family,diagnosticCode:family==='palo_alto'?'SYSTEM':'',attributes:{}},
    solutionSummary:{overview:'Synthetic context',steps:[],causes:[]},searchResults:[],
  }));
const fixture = { catalog, history };
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.EIMS_UI_BROWSER ? {channel:process.env.EIMS_UI_BROWSER} : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url());
      let body = [];
      if (url.pathname === '/api/v1/history/catalog') body = { entries: fixture.catalog, count: fixture.catalog.length };
      else if (url.pathname === '/api/v1/history/') body = fixture.history;
      else if (url.pathname.endsWith('/stats')) body = {totalLogs:3, criticalErrors:0, dailyTrends:[], categoryStats:[], providerStats:[]};
      await route.fulfill({ status:200, contentType:'application/json', headers:{'Access-Control-Allow-Origin':'*'}, body:JSON.stringify(body) });
    });
    await page.goto((process.env.EIMS_UI_URL || 'http://127.0.0.1:3108') + '/analyzer');
    const panel = page.locator('#analyzer-records-panel');
    await page.getByText('3 analysis records · Sorted by analysis date').waitFor();
    assert.equal(await page.getByRole('tab', {name:'Analysis History',exact:true}).getAttribute('aria-selected'), 'true');
    let rows = panel.locator(':scope > div');
    assert.equal(await rows.count(), 3);
    assert.match(await rows.first().innerText(), /PAN-OS/);
    assert.doesNotMatch(await rows.first().innerText(), /Group Policy/);
    await page.getByLabel('History sort order').selectOption('oldest');
    assert.match(await rows.first().innerText(), /Synthetic Demo/i);
    await page.getByLabel('Search analysis history').fill('1129');
    assert.equal(await rows.count(), 2); // duplicate numeric ID retained, both families
    await page.getByLabel('Search analysis history').fill('');
    await page.getByRole('tab', {name:/Diagnostic Knowledge Catalog/}).click();
    await page.getByLabel('Catalog source family').selectOption('palo_alto');
    assert.equal(await rows.count(), 4);
    assert.match(await panel.innerText(), /Log category: SYSTEM/);
    await page.getByLabel('Search event catalog').fill('configuration');
    await page.waitForFunction(() => document.querySelector('#analyzer-records-panel').innerText.includes('Config log context'));
    assert.equal(await rows.count(), 1);
    await rows.first().click();
    await page.getByText('Diagnostic Knowledge — CONFIG', {exact:true}).waitFor();
    const official = page.getByRole('link', {name:/PAN-OS Config Log Fields/});
    assert.match(await official.getAttribute('href'), /^https:\/\/docs\.paloaltonetworks\.com\//);
    await page.getByRole('button', {name:'Close details'}).click();
    await page.getByLabel('Search event catalog').fill('');
    await page.getByLabel('Catalog source family').selectOption('windows_event');
    assert.equal(await rows.count(), 141);
    await page.getByLabel('Catalog source family').selectOption('json');
    await page.getByText(/Parser support does not imply diagnostic coverage/).waitFor();
    await page.getByRole('tab', {name:'Analysis History',exact:true}).click();
    assert.equal(await rows.count(), 3);
    await page.getByRole('tab', {name:/Diagnostic Knowledge Catalog/}).click();
    await page.getByLabel('Catalog source family').selectOption('all');
    assert.equal(await rows.count(), 163);
    await page.screenshot({path:path.join(__dirname,'../test-results/catalog-ui-1366.png')});
    await page.setViewportSize({width:1024,height:768});
    await page.getByLabel('Catalog source family').scrollIntoViewIfNeeded();
    assert(await page.getByLabel('Catalog source family').isVisible());
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({path:path.join(__dirname,'../test-results/catalog-ui-1024.png')});
    assert.deepEqual(errors, []);
    console.log('PASS: real Chromium synthetic UI; tabs, duplicates, sorting, product filter/search, references, 141 Windows, JSON fallback, laptop layouts, no page errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });

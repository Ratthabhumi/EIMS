const { chromium } = require('@playwright/test');
(async () => {
 const b = await chromium.launch({ channel: 'msedge', headless: true });
 const c = await b.newContext({ viewport: { width: 1400, height: 1000 }, ignoreHTTPSErrors: false, acceptDownloads: true });
 const p = await c.newPage();
 p.on('response', r => { try { const u = new URL(r.url()); if (u.pathname.startsWith('/api/')) console.log('EVENT', r.status(), r.request().method(), u.pathname); } catch {} });
 const initial = p.waitForResponse(r => new URL(r.url()).pathname.endsWith('/api/v1/auth/session') && r.request().method() === 'GET', { timeout: 30000 });
 await p.goto('https://localhost:13451/analyzer', { waitUntil: 'domcontentloaded' });
 console.log('GOTO_DONE');
 const r = await initial;
 console.log('MATCHED', r.status(), new URL(r.url()).pathname);
 await b.close();
})().catch(e => { console.error('PROBE_FAIL', e); process.exitCode = 1; });

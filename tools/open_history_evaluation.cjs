/* Participant browser only. Start the guarded SQLite API and UI preview first.
 * Real responses are forwarded; no operational browser/profile is reused.
 */
const {chromium,request}=require(process.env.EIMS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const ui='http://127.0.0.1:3115',api='http://127.0.0.1:3116';
(async()=>{
 const probe=await request.newContext();
 try {
  const response=await probe.get(api+'/__sandbox');
  assert.deepEqual(await response.json(),{purpose:'synthetic-history-only',dialect:'sqlite',operational_startup:false});
 } finally {await probe.dispose()}
 const browser=await chromium.launch({headless:false,channel:process.env.EIMS_UI_BROWSER || 'msedge'});
 try {
  const context=await browser.newContext();
  await context.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname.startsWith('/api/')){
    const response=await route.fetch({url:api+url.pathname+url.search});
    return route.fulfill({response,headers:{...response.headers(),'access-control-allow-origin':'*','access-control-allow-headers':'*'}});
   }
   if(url.origin===ui)return route.continue();
   return route.abort();
  });
  const page=await context.newPage();
  await page.goto(ui+'/analyzer',{waitUntil:'domcontentloaded'});
  console.log('Synthetic evaluation browser ready. All API calls go to isolated SQLite. No participant metrics are recorded automatically. Close this window to finish.');
  await new Promise(resolve=>page.once('close',resolve));
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
